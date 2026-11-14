"""Read-only voice-channel evidence and bounded context, never speaker inference."""
from __future__ import annotations

import re
from typing import Any


REMOTE_VOICE = re.compile(
    r"đầu dây bên kia|(?:giọng|tiếng)[^.!?\n]{0,80}(?:qua điện thoại|từ điện thoại|qua bộ đàm|từ bộ đàm|từ loa|ngoài khung|ngoài cửa|bên ngoài)"
    r"|(?:điện thoại|bộ đàm|loa)[^.!?\n]{0,40}(?:vang lên|cất tiếng)", re.IGNORECASE,
)
# Merely mentioning a crowd is insufficient: narration must describe collective speech.
COLLECTIVE_VOICE = re.compile(
    r"(?:đám đông|mọi người|cả (?:bọn|nhóm)|nhóm [^.!?\n]{1,30})[^.!?\n]{0,30}"
    r"(?:đồng thanh|cùng (?:hô|hét|nói|đáp))|(?:đồng thanh)\s+(?:hô|hét|nói|đáp)", re.IGNORECASE,
)
CONTEXT_RADIUS = 8


def nearby_dialogue(anchor: Any, rows: list[Any], wishes: dict) -> list[Any]:
    """A context window, not a call/scene boundary. Additional lines start unselected.

    Preserve individual decisions, including stale wishes: only their own editor may replace them.
    Thoughts and narration can never join this speaker batch.
    """
    chapter, seq = int(anchor["chapter_id"]), int(anchor["seq"])
    return [row for row in rows
            if int(row["chapter_id"]) == chapter and abs(int(row["seq"]) - seq) <= CONTEXT_RADIUS
            and row["kind"] == "dialogue" and row["stable_id"] and row["text_sha256"]
            and (str(row["stable_id"]) == str(anchor["stable_id"]) or str(row["stable_id"]) not in wishes)]
