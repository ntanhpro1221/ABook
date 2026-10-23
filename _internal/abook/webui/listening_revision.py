"""Bounded Lamport clock: (epoch, counter, node) orders edits across clients.

At the ceiling the whole profile clock rolls into a new epoch. Earlier field
revisions remain comparable. Peer metadata never advances the clock by itself.
"""
from typing import Any
import copy
import re

MAX_COUNTER = 2**40
MAX_JUMP = 1_000_000
OLD_PEER = "Máy kia đang dùng bản ABook cũ, hãy cập nhật cả hai máy"
JUMP_NOTICE = "Phiên bản đồng bộ bất thường; giữ bản của bạn — bạn đồng bộ từ máy có bản đúng."


def valid_epoch(value: Any) -> bool:
    # Unary epochs grow only once per trillion edits, with no numeric ceiling.
    # Prefix ordering is identical in Python, Kotlin and JS; peers may advance one epoch.
    return isinstance(value, str) and re.fullmatch(r"1*", value) is not None


def valid_number(value: Any, minimum: int = 0) -> bool:
    return type(value) is int and minimum <= value <= MAX_COUNTER


def revision(item: Any) -> tuple[int, str]:
    value = item.get("rev") if isinstance(item, dict) else None
    if (isinstance(value, dict) and valid_number(value.get("counter"), 1)
            and valid_epoch(value.get("epoch", "")) and isinstance(value.get("node"), str)
            and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value["node"])):
        return value["counter"], value["node"]
    return 0, ""


def order(item: Any) -> tuple[str, int, str]:
    counter, node = revision(item)
    return (item["rev"].get("epoch", ""), counter, node) if counter else ("", 0, "")


def newer(theirs: dict, ours: dict | None) -> bool:
    if ours is None:
        return True
    a, b = order(theirs), order(ours)
    if a[1] or b[1]:
        return a > b
    return float(theirs.get("at") or 0) > float(ours.get("at") or 0)


def items(state: dict):
    for key in ("last", "reading"):
        if isinstance(state.get(key), dict):
            yield state[key]
    yield from state.get("chapters", {}).values()
    yield from state.get("bookmarks", [])
    for key in ("_fieldRevs", "_deletedRevs"):
        yield from ({"rev": value} for value in state.get(key, {}).values())


def epoch(state: dict) -> str:
    marker = state.get("_epoch", "")
    return max(marker if valid_epoch(marker) else "", *(order(item)[0] for item in items(state)), "")


def clock(state: dict) -> int:
    era = epoch(state)
    marker = state.get("_clock", 0)
    return max(marker if valid_number(marker) and state.get("_epoch", "") == era else 0,
               *(order(item)[1] for item in items(state) if order(item)[0] == era), 0)


def observe(state: dict, rev: dict) -> None:
    era, counter, _ = order({"rev": rev})
    current, tick = epoch(state), clock(state)
    if era >= current:
        if era:
            state["_epoch"] = era
        state["_clock"] = max(tick if era == current else 0, counter)


def advance(state: dict, node: str) -> dict:
    era, counter = epoch(state), clock(state) + 1
    if counter > MAX_COUNTER:
        era, counter = era + "1", 1
    rev = {"counter": counter, "node": node, **({"epoch": era} if era else {})}
    observe(state, rev)
    return rev


def checked_peer(ours: dict, incoming: dict, notify) -> dict:
    """Reject old peers atomically; discard suspicious fields with a visible notice."""
    state = copy.deepcopy(incoming)
    era, tick = epoch(ours), clock(ours)

    def accept(item):
        if not isinstance(item, dict) or "rev" not in item or item["rev"] is None:
            raise ValueError(OLD_PEER)
        e, c, _ = order(item)
        if (not c or e > era + "1" or (e == era and c > tick + MAX_JUMP)
                or (e == era + "1" and c > MAX_JUMP)):
            notify(JUMP_NOTICE)
            return False
        return True

    for key in ("last", "reading"):
        if state.get(key) is not None and not accept(state[key]):
            state.pop(key)
    state["chapters"] = {k: v for k, v in (state.get("chapters") or {}).items() if accept(v)}
    state["bookmarks"] = [v for v in (state.get("bookmarks") or []) if accept(v)]
    for field, stamp in (("rate", "rateAt"), ("finished", "finishedAt"), ("voice", "voiceAt")):
        if field in state and not accept({"rev": state.get("_fieldRevs", {}).get(field)}):
            state.pop(field)
            state.pop(stamp, None)
    for key in list(state.get("deleted") or {}):
        if not accept({"rev": state.get("_deletedRevs", {}).get(key)}):
            state["deleted"].pop(key)
    # Raw _clock/_epoch, or orphan revision maps, are never evidence of edits.
    state.pop("_clock", None)
    state.pop("_epoch", None)
    state["_fieldRevs"] = {key: incoming["_fieldRevs"][key] for key in ("rate", "finished", "voice")
                           if key in state and key in incoming.get("_fieldRevs", {})}
    state["_deletedRevs"] = {key: incoming["_deletedRevs"][key] for key in state.get("deleted", {})}
    return state


def require_peer_revisions(payload: dict) -> None:
    """Preflight the entire exchange before record deletions or other side effects."""
    fields = {key: payload[key] for key in ("last", "reading", "chapters", "bookmarks", "rate", "finished", "voice", "_fieldRevs", "_deletedRevs") if key in payload}
    if isinstance(payload.get("deleted"), dict):
        fields["deleted"] = payload["deleted"]
    try:
        checked_peer({}, fields, lambda _text: None)
    except ValueError as error:
        from . import notices
        notices.NOTICES.add(str(error))
        raise
    if isinstance(payload.get("activeState"), dict):
        require_peer_revisions(payload["activeState"])
