"""Validate the current cast.json shape before edits or client rendering."""
from __future__ import annotations

import math
from typing import Any


def valid_cast(value: Any) -> bool:
    def number(item: Any) -> bool:
        return (type(item) is int or type(item) is float and math.isfinite(item)) and item >= 0

    def chapters(items: Any) -> bool:
        return isinstance(items, list) and all(isinstance(item, dict) and type(item.get("id")) in (int, float)
                                                and (type(item["id"]) is int or math.isfinite(item["id"])) and item["id"] % 1 == 0
                                                and isinstance(item.get("title"), str) for item in items)

    def counts(item: Any) -> bool:
        return isinstance(item, dict) and number(item.get("lines")) and item["lines"] % 1 == 0 and number(item.get("seconds"))

    def people(items: Any) -> bool:
        return isinstance(items, list) and all(counts(item) and all(isinstance(item.get(key), str)
                                                                   for key in ("name", "displayName", "gender")) for item in items)

    if not isinstance(value, dict) or not all(people(value.get(key)) for key in ("characters", "extras")):
        return False
    narrator = value.get("narrator")
    if not counts(narrator) or not isinstance(narrator.get("voice"), str):
        return False
    voices = narrator.get("chapterVoices")
    return (number(narrator.get("voiceLines")) and narrator["voiceLines"] % 1 == 0 and number(narrator.get("voiceSeconds"))
            and chapters(narrator.get("exceptChapters")) and isinstance(voices, list)
            and all(counts(item) and isinstance(item.get("voice"), str) and chapters(item.get("chapters")) for item in voices)
            and ("carried" not in value or people(value["carried"])))
