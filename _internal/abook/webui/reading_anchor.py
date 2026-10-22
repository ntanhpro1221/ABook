"""Chỗ nghe theo chữ, độc lập với bộ đệm audio (ReadingAnchor.kt, listen/readingAnchor.ts).

`textHash` là băm CẢ chương; `paragraphHash` (không bắt buộc) là băm riêng đoạn đang nghe - sửa một ký tự ở đoạn khác thì băm chương lệch nhưng chỗ nghe vẫn
tìm lại được nhờ băm đoạn (soát a79 lỗi 5). Cách băm và cách khôi phục nằm ở hai bản kia; ở đây chỉ kiểm hình dạng rồi giữ nguyên để lưu / đồng bộ."""
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
    saved = {"segment": int(anchor["segment"]), "charOffset": int(anchor["charOffset"]), "textHash": anchor["textHash"]}
    if "paragraphHash" in anchor:
        if not re.fullmatch(r"fnv1a64:[0-9a-f]{16}", str(anchor["paragraphHash"])):
            return None
        saved["paragraphHash"] = anchor["paragraphHash"]
    return saved
