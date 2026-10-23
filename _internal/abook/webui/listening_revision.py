"""Bounded Lamport clock: (epoch, counter, node) orders edits across clients.

At the ceiling the whole profile clock rolls into a new epoch. Earlier field
revisions remain comparable. Peer metadata never advances the clock by itself.
"""
from typing import Any
import copy
import re
from collections.abc import Callable

MAX_COUNTER = 2**40
MAX_JUMP = 1_000_000
# Below half the range a counter is accepted whatever the receiver's clock: a new device or an empty profile must take a
# profile with millions of saves. Even a forged peer can only push a profile here, still 2^39 edits from the ceiling.
# Above it, a peer may lead the receiver by at most MAX_JUMP per exchange.
SAFE_COUNTER = MAX_COUNTER // 2
OLD_PEER = "Máy kia đang dùng bản ABook cũ, hãy cập nhật cả hai máy"
MISSING_REVISION = "Dữ liệu đồng bộ thiếu phiên bản. Bạn hãy mở lại hồ sơ trên máy gửi rồi thử lại."
JUMP_NOTICE = "Một phần dữ liệu từ máy kia có bước nhảy phiên bản bất thường. App giữ bản của bạn; bạn hãy kiểm tra và đồng bộ lại từ máy có dữ liệu đúng."


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


META_REVS = (("records", ("nameRev", "movedRev")), ("links", ("activeRev",)))


def meta_items(data: dict):
    """Record names, moves and active choices share one clock: `_clock`/`_epoch` at the top of the link table."""
    for table, keys in META_REVS:
        for row in (data.get(table) or {}).values():
            if isinstance(row, dict):
                yield from ({"rev": row[key]} for key in keys if key in row)


def epoch(state: dict, source: Callable[[dict], Any] = items) -> str:
    marker = state.get("_epoch", "")
    return max(marker if valid_epoch(marker) else "", *(order(item)[0] for item in source(state)), "")


def clock(state: dict, source: Callable[[dict], Any] = items) -> int:
    era = epoch(state, source)
    marker = state.get("_clock", 0)
    return max(marker if valid_number(marker) and state.get("_epoch", "") == era else 0,
               *(order(item)[1] for item in source(state) if order(item)[0] == era), 0)


def observe(state: dict, rev: dict, source: Callable[[dict], Any] = items) -> None:
    era, counter, _ = order({"rev": rev})
    current, tick = epoch(state, source), clock(state, source)
    if era >= current:
        if era:
            state["_epoch"] = era
        state["_clock"] = max(tick if era == current else 0, counter)


def advance(state: dict, node: str, source: Callable[[dict], Any] = items) -> dict:
    era, counter = epoch(state, source), clock(state, source) + 1
    if counter > MAX_COUNTER:
        era, counter = era + "1", 1
    rev = {"counter": counter, "node": node, **({"epoch": era} if era else {})}
    observe(state, rev, source)
    return rev


def implausible(era: str, tick: int, item: Any) -> bool:
    """A peer revision this receiver must not adopt: invalid, more than one epoch ahead, or a leap in the upper half."""
    e, c, _ = order(item)
    return (not c or e > era + "1" or (e == era and c > SAFE_COUNTER and c > tick + MAX_JUMP)
            or (e == era + "1" and c > MAX_JUMP))


def meta_newer(data: dict, theirs: Any, their_at: Any, ours: Any, our_at: Any, notify) -> bool:
    """Name, move or active choice from a peer. Both sides versioned: the revision decides, so a slow wall clock never
    reverts a later edit. A peer without metadata revisions (0.4.133) still compares wall-clock stamps."""
    if theirs is not None and implausible(epoch(data, meta_items), clock(data, meta_items), {"rev": theirs}):
        notify(JUMP_NOTICE)
        return False
    a, b = order({"rev": theirs}), order({"rev": ours})
    if a[1] and b[1]:
        return a > b
    return float(their_at or 0) > float(our_at or 0)


def adopt_meta(data: dict, row: dict, key: str, rev: Any) -> None:
    """Store a peer's metadata revision beside the value it won with; a stamp-only value (or an implausible revision) drops ours."""
    if revision({"rev": rev})[0] and not implausible(epoch(data, meta_items), clock(data, meta_items), {"rev": rev}):
        row[key] = rev
        observe(data, rev, meta_items)
    else:
        row.pop(key, None)


def upgrade_local(state: dict, node: str | Callable[[], str]) -> bool:
    """Stamp schema-checked local legacy data once. Caller locks and commits it.

    Never apply this migration to incoming peer data.
    """
    pending = []
    for key in ("last", "reading"):
        if isinstance(state.get(key), dict):
            pending.append((state[key].get("at", 0), key, state[key], "rev"))
    for key, item in state.get("chapters", {}).items():
        pending.append((item.get("at", 0), "chapters/" + key, item, "rev"))
    for item in state.get("bookmarks", []):
        pending.append((item.get("at", item.get("createdAt", 0)), "bookmarks/" + item["id"], item, "rev"))
    for field, stamp in (("rate", "rateAt"), ("finished", "finishedAt"), ("voice", "voiceAt")):
        if field in state:
            pending.append((state.get(stamp, 0), "fields/" + field, state.setdefault("_fieldRevs", {}), field))
    for key, stamp in state.get("deleted", {}).items():
        pending.append((stamp, "deleted/" + key, state.setdefault("_deletedRevs", {}), key))
    changed = False
    for _, _, target, key in sorted(pending, key=lambda row: (row[0], row[1])):
        if not revision({"rev": target.get(key)})[0]:
            target[key] = advance(state, node() if callable(node) else node)
            changed = True
    return changed


def checked_peer(ours: dict, incoming: dict, notify) -> dict:
    """Require versioned peer data; only an explicit capability can identify an old peer."""
    if incoming.get("listeningRevision") == 0:
        raise ValueError(OLD_PEER)
    state = copy.deepcopy(incoming)
    era, tick = epoch(ours), clock(ours)

    def accept(item):
        if not isinstance(item, dict) or "rev" not in item or item["rev"] is None:
            raise ValueError(MISSING_REVISION)
        if implausible(era, tick, item):
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
    fields = {key: payload[key] for key in ("listeningRevision", "last", "reading", "chapters", "bookmarks", "rate", "finished", "voice", "_fieldRevs", "_deletedRevs") if key in payload}
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
