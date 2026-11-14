"""Read-only scene-marker projection; never infer people or edit source rows."""
from __future__ import annotations

import hashlib
import json
from typing import Any


def project_scenes(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A marker is AFTER its row, including narration. No marker means unknown scenes."""
    known = any(line.get("sceneBreak") for line in lines)
    scene = 1
    out = []
    for line in lines:
        out.append({**line, "scene": scene if known else None})
        if line.get("sceneBreak"):
            scene += 1
    return out


def scope_revision(lines: list[dict[str, Any]]) -> str:
    fields = ("stableId", "textSha256", "seq", "speaker", "current", "kind", "editable", "scene", "sceneBreak", "wish", "lineWish")
    payload = [{key: line.get(key) for key in fields} for line in lines]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def scope_lines(lines: list[dict[str, Any]], anchor: str, mode: str,
                start: int, end: int) -> list[dict[str, Any]]:
    """Return the original opaque role only, across the full chapter, never display labels."""
    base = next((line for line in lines if line["stableId"] == anchor), None)
    if base is None or mode not in ("line", "scene", "chapter", "manual"):
        return []
    if mode == "scene" and base.get("scene") is None:
        return []
    if mode == "manual" and (not isinstance(start, int) or not isinstance(end, int) or start < 0 or end < start):
        return []
    return [line for line in lines if line.get("editable") and line.get("kind") in ("dialogue", "thought")
            and (line.get("speaker") or line["current"]) == (base.get("speaker") or base["current"])
            and (mode != "line" or line["stableId"] == anchor)
            and (mode != "scene" or line.get("scene") == base["scene"])
            and (mode != "manual" or start <= line["seq"] <= end)]
