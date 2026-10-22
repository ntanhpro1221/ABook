"""Chỗ nghe theo chữ, độc lập với bộ đệm audio (ReadingAnchor.kt, listen/readingAnchor.ts)."""
from __future__ import annotations

import re
from typing import Any


def validated(anchor: Any) -> dict[str, Any] | None:
    if not isinstance(anchor, dict) or not re.fullmatch(r"fnv1a64:[0-9a-f]{16}", str(anchor.get("textHash", ""))):
        return None
    for key in ("segment", "charOffset"):
        value = anchor.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 2**31 - 1 or value != int(value):
            return None
    return {"segment": int(anchor["segment"]), "charOffset": int(anchor["charOffset"]), "textHash": anchor["textHash"]}
