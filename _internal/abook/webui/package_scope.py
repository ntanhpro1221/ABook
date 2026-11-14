"""Packaged read-along rows projected for explicit, marker-free role corrections."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from ..aliases import key
from ..listener_overrides import character_key
from . import book_edits, book_wishes
from .script_scope import scope_revision


def package_chapter(folder: Path, chapter_id: int) -> dict[str, Any] | None:
    index = book_wishes.Lines(folder)
    chapter = index.chapter(chapter_id)
    if chapter is None:
        return None
    cast = book_wishes.people(folder)
    wishes = book_edits.load(folder).get("wishes") or {}
    lines = []
    for seq, row in enumerate(index.segments(chapter)):
        stable_id, sha = row["stableId"], str(row.get("textSha256") or "")
        shown = str(row.get("speaker") or "")
        matches = [person for person in cast if any(key(shown) == key(str(person.get(field) or ""))
                   for field in ("name", "displayName", "originalName"))] if shown else []
        # An ambiguous display label cannot establish a shared identity.
        current = character_key(matches[0]["name"]) if len(matches) == 1 else "line:" + stable_id
        kind = str(row.get("kind") or "narration")
        wish = (wishes.get("speakers") or {}).get(stable_id)
        delivery = (wishes.get("lines") or {}).get(stable_id)
        wish = wish if wish and wish.get("text_sha256") == sha else None
        delivery = delivery if delivery and delivery.get("text_sha256") == sha else None
        lines.append({"segmentId": int(row.get("id") or 0), "stableId": stable_id, "textSha256": sha,
                      "seq": seq, "paragraph": row.get("paragraph"), "text": str(row.get("text") or ""),
                      "kind": kind, "speaker": current, "current": current, "label": shown,
                      "editable": kind in ("dialogue", "thought") and bool(sha), "hasAudio": False,
                      "hint": None, "scene": None, "sceneBreak": False,
                      "wish": {"value": wish["speaker"], "label": wish["speaker"], "state": "pending"} if wish else None,
                      "lineWish": {"kind": delivery.get("kind", ""), "emotion": delivery.get("emotion", ""),
                                   "intensity": delivery.get("intensity"), "spoken": delivery.get("spoken"), "state": "pending"} if delivery else None,
                      "emotion": None, "intensity": None, "spoken": None})
    counts = Counter(line["current"] for line in lines if line["editable"])
    people = [{"value": character_key(person["name"]), "label": str(person.get("displayName") or person["name"]),
               "lines": counts[character_key(person["name"])]} for person in cast if person.get("voice")]
    order = [item["id"] for item in index.chapters]
    position = order.index(chapter_id)
    return {"chapterId": chapter_id, "index": int(chapter.get("index") or chapter_id),
            "title": str(chapter.get("fullTitle") or chapter.get("title") or ""),
            "previous": order[position - 1] if position else None,
            "next": order[position + 1] if position + 1 < len(order) else None,
            "castReady": bool(people), "cast": [person for person in people if person["lines"]],
            "others": [person for person in people if not person["lines"]], "firstPerson": None,
            "lines": lines, "scopeRevision": scope_revision(lines)}


def package_contents(folder: Path) -> dict[str, Any]:
    index = book_wishes.Lines(folder)
    chapters = []
    for chapter in index.chapters:
        rows = index.segments(chapter)
        chapters.append({"chapterId": chapter["id"], "index": int(chapter.get("index") or chapter["id"]),
                         "title": str(chapter.get("fullTitle") or chapter.get("title") or ""),
                         "lines": len(rows), "speech": sum(row.get("kind") in ("dialogue", "thought") for row in rows),
                         "hints": 0, "decided": 0})
    return {"castReady": any(person.get("voice") for person in book_wishes.people(folder)), "chapters": chapters}
