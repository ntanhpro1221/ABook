"""Durable, compensating cast operations. No story text belongs in receipts.

The file journal precedes alias publication. SQLite commits the actual before/after
receipt together with every segment change. File projections are replayable caches.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from . import aliases, listener_overrides as wishes
from .io_utils import atomic_write_json

RECEIPT_CODE = "CAST_OPERATION_COMMITTED_V1"
SECTION = "cast_operations"
ID = re.compile(r"[0-9a-f]{32}")
DECISIONS = ("speaker", "canonical_character_id", "voice_profile_id", "gender", "age", "kind", "emotion",
             "intensity", "listener_retakes", "listener_retake_at")
RESTORE = ("speaker", "canonical_character_id", "voice_profile_id", "gender", "age")


def operation_id(value: Any = None) -> str:
    value = uuid.uuid4().hex if value is None else value
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError("Invalid cast operation ID")
    return value


def undo_id(original: str) -> str:
    return uuid.uuid5(uuid.UUID(operation_id(original)), "undo-cast-v1").hex


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _request_digest(value: Any) -> str:
    return _digest({key: item for key, item in value.items() if key != "replaced"} if isinstance(value, dict) else value)


def _alias_delta(source: str, target: str, now: float, op: str, root: Path) -> list[dict[str, Any]]:
    before = {aliases.key(item["alias"]): item for item in aliases._entries(root)}
    decided = aliases.decide(list(before.values()), source, target, now)
    if decided is None:
        return []
    after = {aliases.key(item["alias"]): item for item in decided}
    delta = []
    for key in sorted(before.keys() | after.keys()):
        old, new = before.get(key), after.get(key)
        if old == new:
            continue
        if new is not None:
            new = {**new, "operation_id": op}
        delta.append({"key": key, "before": old, "after": new})
    return delta


def publish_aliases(root: Path, delta: list[dict[str, Any]], *, reverse: bool = False) -> int:
    """CAS each alias, including ownership. A newer alias always wins."""
    entries = {aliases.key(item["alias"]): item for item in aliases._entries(root)}
    conflicts = 0
    changed = False
    for item in delta:
        expected, wanted = (item["after"], item["before"]) if reverse else (item["before"], item["after"])
        current = entries.get(item["key"])
        if current == wanted:
            continue
        if current != expected:
            conflicts += 1
            continue
        if wanted is None:
            entries.pop(item["key"], None)
        else:
            entries[item["key"]] = wanted
        changed = True
    if changed:
        aliases._write(root, list(entries.values()))
    return conflicts


def alias_conflicts(root: Path, delta: list[dict[str, Any]]) -> int:
    entries = {aliases.key(item["alias"]): item for item in aliases._entries(root)}
    return sum(entries.get(item["key"]) not in (item["before"], item["after"]) for item in delta)


def request_batch(root: Path, lines: list[tuple[str, str]], target: str, *, now: float,
                  source: str = "", new_gender: str = "", op: str | None = None) -> str:
    """Publish the batch and its wishes in a single durable file replacement."""
    op = operation_id(op)
    with wishes.edit_turn(root):
        data = wishes.read_overrides(root)
        operations = data.setdefault(SECTION, {})
        intent = {"operation_id": op, "kind": "merge" if source else "split", "source": source,
                  "target": target, "new_gender": new_gender,
                  "lines": [[str(stable), str(sha)] for stable, sha in sorted(set(lines))]}
        previous = operations.get(op)
        if previous is not None:
            if previous["intent"] != intent:
                raise ValueError("Cast operation ID reused with different content")
            if not previous.get("cancelled") and not previous.get("finished"):
                publish_aliases(root, previous.get("aliases", []))
            return op
        entries = data.setdefault("speakers", {})
        for stable, sha in intent["lines"]:
            entry = {"speaker": target, "text_sha256": sha, "requested_at": float(now), "operation_id": op}
            if new_gender:
                entry["new"] = {"gender": new_gender}
            entries[stable] = wishes._replacing(entries.get(stable), entry)
        delta = _alias_delta(source, target, now, op, root) if source else []
        operations[op] = {"intent": intent, "requested_at": float(now), "aliases": delta}
        wishes._write(root, data)
        publish_aliases(root, delta)
    return op


def request_undo(root: Path, original: str, *, now: float) -> str:
    original, op = operation_id(original), undo_id(original)
    with wishes.edit_turn(root):
        data = wishes.read_overrides(root)
        operations = data.setdefault(SECTION, {})
        if op not in operations or operations[op].get("cancelled"):
            operations[op] = {"intent": {"operation_id": op, "kind": "undo", "original": original},
                              "requested_at": float(now)}
            data.setdefault("cast_undos", {})[op] = {"original": original, "requested_at": float(now)}
            wishes._write(root, data)
    return op


def import_id(entries: Any) -> str:
    """A retry of the exact same portable batch has the same operation ID."""
    return uuid.uuid5(uuid.NAMESPACE_URL, "abook-cast-v1:" + _digest(entries)).hex


def cancel_batches(root: Path, data: dict[str, Any], removed: dict[str, Any]) -> None:
    """Pending unmerge retains the old withdrawal path and restores owned aliases."""
    owned = {entry.get("operation_id") for entry in removed.values()}
    reversing = []
    for op in owned - {None}:
        operation = (data.get(SECTION) or {}).get(op)
        if operation and not operation.get("finished") and not any(item.get("operation_id") == op for item in (data.get("speakers") or {}).values()):
            operation["cancelled"] = True
            reversing.append(operation.get("aliases", []))
    if reversing:
        # Removal and every cancellation flag must share the same durable replacement.
        wishes._write(root, data)
    for delta in reversing:
        publish_aliases(root, delta, reverse=True)


def receipts(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    try:
        rows = conn.execute("SELECT details_json FROM runtime_events WHERE code=? ORDER BY id", (RECEIPT_CODE,))
    except sqlite3.OperationalError as error:
        if "no such table" not in str(error):
            raise
        return {}
    found = {}
    for row in rows:
        entry = json.loads(row[0])
        if entry.get("version") == 1 and ID.fullmatch(str(entry.get("operation_id", ""))):
            found[entry["operation_id"]] = entry
    return found


def _profile(conn: sqlite3.Connection, identity: Any) -> dict[str, Any] | None:
    row = conn.execute("SELECT voice_key,engine,preset_name,seed FROM voice_profiles WHERE id=?", (identity,)).fetchone()
    return dict(row) if row else None


def _person(conn: sqlite3.Connection, identity: Any) -> dict[str, Any] | None:
    row = conn.execute("SELECT canonical_name,gender,age,locked,locked_voice_key FROM characters WHERE id=?", (identity,)).fetchone()
    return dict(row) if row else None


def _state(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    return {**{key: row[key] for key in DECISIONS}, "spoken_sha256": _digest(row["listener_text"]),
            "voice": _profile(conn, row["voice_profile_id"]), "person": _person(conn, row["canonical_character_id"])}


def _guards(data: dict[str, Any], stable: str, names: list[str]) -> dict[str, Any]:
    # Hash user-entered spoken text as well; the receipt never contains book text.
    return {section: _request_digest((data.get(section) or {}).get(stable)) for section in ("speakers", "lines", "retakes")} | {
        "voices": {wishes.character_key(name): _request_digest((data.get("voices") or {}).get(wishes.character_key(name)))
                   for name in names}}


def _write_speaker(conn: sqlite3.Connection, db: Any, row: sqlite3.Row, target: dict[str, Any], now: float) -> bool:
    revoice = row["voice_profile_id"] != target["voice_profile_id"]
    conn.execute("UPDATE segments SET speaker=?,canonical_character_id=?,voice_profile_id=?,gender=?,age=?,updated_at=? WHERE id=?",
                 (*[target[key] for key in RESTORE], now, int(row["id"])))
    reset = revoice and row["status"] in {"signal_passed", "asr_passed", "verified", "warning", "failed"}
    if reset:
        reason = "Listener cast operation changed the recorded voice"
        db._reset_segment_pending_conn(conn, int(row["id"]), reason, now)
        db._refresh_chapter_counts_conn(conn, int(row["chapter_id"]))
        db._mark_listener_redo_conn(conn, int(row["chapter_id"]), reason)
    return bool(reset)


def apply_operation(db: Any, conn: sqlite3.Connection, operation: dict[str, Any], data: dict[str, Any],
                    voices: dict[str, Any]) -> dict[str, Any]:
    """Caller owns BEGIN IMMEDIATE. Changes and receipt cannot commit separately."""
    intent = operation["intent"]
    op = operation_id(intent["operation_id"])
    known = receipts(conn)
    if op in known:
        if known[op]["intent_sha256"] != _digest(intent):
            raise ValueError("Cast operation ID reused with different content")
        return known[op]
    now = time.time()
    kind = intent["kind"]
    origin = known.get(intent.get("original")) if kind == "undo" else None
    if kind == "undo" and (origin is None or origin["kind"] == "undo"):
        raise ValueError("No proven cast before-state")
    result: dict[str, Any] = {"version": 1, "operation_id": op, "kind": kind, "intent_sha256": _digest(intent),
                              "source": intent.get("source", ""), "target": intent.get("target", ""),
                              "original": intent.get("original", ""), "at": now,
                              "alias_conflicts": operation.get("alias_conflicts", 0),
                              "lines": [], "conflicts": [], "chapters": [], "aliases": operation.get("aliases", [])}
    members = origin["lines"] if origin else [{"stable_id": stable, "text_sha256": sha} for stable, sha in intent["lines"]]
    for member in members:
        stable = member["stable_id"]
        row = conn.execute("SELECT * FROM segments WHERE stable_id=?", (stable,)).fetchone()
        problem = "unknown_line" if row is None else "source_changed" if row["text_sha256"] != member["text_sha256"] else ""
        before = _state(conn, row) if not problem else None
        names = member.get("names", []) if origin else [str(row["speaker"]) if row else "", intent["target"]]
        guard = _guards(data, stable, names)
        if not problem and origin:
            if before != member["after"] or guard != member["guards"]:
                problem = "newer_decision"
            saved = member["before"]
            if (not problem and (_profile(conn, saved["voice_profile_id"]) != saved["voice"]
                                 or _person(conn, saved["canonical_character_id"]) != saved["person"])):
                problem = "voice_changed"
            target = saved
        elif not problem:
            entry = (data.get("speakers") or {}).get(stable) or {}
            if entry.get("operation_id") != op:
                problem = "newer_decision"
            target, rejected = wishes.speaker_target(conn, stable_id=stable, text_sha256=member["text_sha256"],
                                                      speaker=intent["target"], new_gender=intent.get("new_gender", ""))
            if rejected:
                problem = rejected
            if not problem and target is not None:
                if target.get("create"):
                    target = db._create_listener_character_conn(conn, target, target["create"], voices, now)
                target = {**target, "canonical_character_id": target["character_id"]}
        if problem:
            result["conflicts"].append({"stable_id": stable, "reason": problem})
            continue
        reset = _write_speaker(conn, db, row, target, now)
        after = _state(conn, conn.execute("SELECT * FROM segments WHERE id=?", (row["id"],)).fetchone())
        entry = (data.get("speakers") or {}).get(stable) or {}
        result["lines"].append({"stable_id": stable, "text_sha256": member["text_sha256"], "before": before,
                                "after": after, "names": names, "guards": guard, "reset": reset,
                                "previous_wish": member.get("previous_wish") if origin else entry.get("replaced")})
        if reset:
            result["chapters"].append(int(row["chapter_id"]))
    result["chapters"] = sorted(set(result["chapters"]))
    if origin:
        result["aliases"] = origin.get("aliases", [])
    # Deliberately last inside this transaction: a failure here rolls back the applied rows.
    conn.execute("INSERT INTO runtime_events(timestamp,level,code,message,details_json) VALUES(?,?,?,?,?)",
                 (now, "info", RECEIPT_CODE, "Listener cast operation committed",
                  json.dumps(result, ensure_ascii=False, allow_nan=False)))
    return result


def apply_pending(db: Any, root: Path, voices: dict[str, Any]) -> set[int]:
    """Worker boundary; serialize the journal snapshot against every Studio writer."""
    chapters: set[int] = set()
    with wishes.edit_turn(root):
        data = wishes.read_overrides(root)
        operations = data.get(SECTION) or {}
        with db.connect() as conn:
            known = receipts(conn)
        committed = set(known)
        for op, operation in sorted(operations.items(), key=lambda item: (item[1]["requested_at"], item[0])):
            if operation.get("finished") and op in committed:
                continue
            if operation.get("cancelled"):
                publish_aliases(root, operation.get("aliases", []), reverse=True)
                continue
            if operation["intent"]["kind"] != "undo":
                publish_aliases(root, operation.get("aliases", []))
            original = known.get(operation["intent"].get("original"))
            candidate = {**operation, "alias_conflicts": alias_conflicts(root, original["aliases"] if original else operation.get("aliases", []))}
            result = db.apply_listener_cast_operation(candidate, data, voices=voices)
            known[op] = result
            if op not in committed:
                chapters.update(result["chapters"])
            if result["kind"] == "undo":
                publish_aliases(root, result["aliases"], reverse=True)
                for member in result["lines"]:
                    entries = data.get("speakers") or {}
                    stable = member["stable_id"]
                    if _request_digest(entries.get(stable)) != member["guards"]["speakers"]:
                        continue
                    if member["previous_wish"] is None:
                        entries.pop(stable, None)
                    else:
                        entries[stable] = member["previous_wish"]
            operation["finished"] = True
            wishes._write(root, data)
        # Projection is disposable; losing it cannot replay the database changes.
        with db.connect() as conn:
            all_receipts = receipts(conn)
        atomic_write_json(Path(root) / "cast_history.json", summary(all_receipts, data))
    return chapters


def summary(known: dict[str, dict[str, Any]], data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data or {}
    undone = {entry["original"]: entry for entry in known.values() if entry["kind"] == "undo"}
    queued = {entry["intent"].get("original") for entry in (data.get(SECTION) or {}).values()
              if entry["intent"]["kind"] == "undo" and not entry.get("cancelled")}
    items = []
    for op, receipt in sorted(known.items(), key=lambda item: (item[1]["at"], item[0]), reverse=True):
        if receipt["kind"] == "undo":
            continue
        undo = undone.get(op)
        items.append({"operationId": op, "source": receipt["source"], "target": receipt["target"],
                      "kind": receipt["kind"], "lines": len(receipt["lines"]), "at": receipt["at"],
                      "conflicts": len({item["stable_id"] for item in receipt["conflicts"] + (undo["conflicts"] if undo else [])}),
                      "aliasConflicts": (undo or receipt).get("alias_conflicts", 0),
                      "state": "undone" if undo else "pending" if op in queued else "applied"})
    return {"items": items, "manualOnly": not bool(items)}


def history(root: Path, *, package: bool = False) -> dict[str, Any]:
    if package:
        from .webui import packages
        found = packages.raw_cast(root).get("castHistory")
        if not isinstance(found, dict) or not isinstance(found.get("items"), list):
            return {"items": [], "manualOnly": True}
        items = []
        for item in found["items"][:2000]:
            if (isinstance(item, dict) and ID.fullmatch(str(item.get("operationId", "")))
                    and item.get("state") in {"applied", "pending", "undone"}
                    and all(isinstance(item.get(key), str) and len(item[key]) <= 200 for key in ("source", "target"))
                    and all(type(item.get(key)) is int and 0 <= item[key] <= 1000000 for key in ("lines", "conflicts"))):
                items.append({**{key: item[key] for key in ("operationId", "source", "target", "lines", "conflicts", "state")},
                              "aliasConflicts": item.get("aliasConflicts", 0) if type(item.get("aliasConflicts", 0)) is int else 0})
        from .webui import book_edits

        pending = (book_edits.load(root).get("wishes") or {}).get("cast_undos") or {}
        for item in items:
            if undo_id(item["operationId"]) in pending:
                item["state"] = "pending"
        return {"items": items, "manualOnly": not bool(items)}
    path = Path(root) / "project.sqlite3"
    if not path.is_file():
        return {"items": [], "manualOnly": True}
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        return summary(receipts(conn), wishes.read_overrides(root))
    finally:
        conn.close()


def with_history(root: Path, cast: dict[str, Any]) -> dict[str, Any]:
    projection = history(root)
    return {**cast, **({"castHistory": projection} if projection["items"] else {})}
