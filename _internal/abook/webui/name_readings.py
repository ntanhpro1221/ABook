"""Mục "Cách đọc tên" của tab Nhân vật: MỌI cách đọc của cuốn (bảng `pronunciations`), không chỉ chỗ máy kém tin.

Hộp việc chỉ hỏi cách đọc máy tự đoán dưới 0,9, và thẻ biến mất khi cách đọc đã ghim - nên một tên máy chắc mà đọc sai, hay
một cách đọc người nghe đã chọn rồi muốn đổi, không có chỗ nào sửa (soát 29-09). Ở đây mỗi tên một dòng: đọc thế nào, ai
quyết (máy đoán hay người nghe), bao nhiêu câu có tên ấy, một câu mẫu để nghe, và yêu cầu đang chờ áp. Sửa đi đúng đường
của thẻ: POST /pronunciation -> overrides.json, dây chuyền áp ở ranh giới chương (listener_overrides.py)."""
from __future__ import annotations

import re
from collections import defaultdict
from contextlib import closing
from pathlib import Path
from typing import Any

from . import store
from .work_items import _example

WORD = re.compile(r"\w+")


def name_readings(project_root: Path) -> dict[str, Any]:
    """{"items": [...], "unseen": N} xếp theo số câu có tên (nhiều trước). Đếm như TTS khớp (`tts._load_pronunciations`):
    nguyên từ, không phân biệt hoa thường. Câu mẫu ưu tiên câu đã thu, để nghe máy đang đọc tên ấy thế nào."""
    from ..database import LISTENER_PRONUNCIATION_SOURCE
    from ..listener_overrides import pronunciation_requests, read_overrides, surface_key

    wishes = {surface_key(entry["surface"]): entry for entry in pronunciation_requests(read_overrides(project_root))}
    if not (Path(project_root) / store.DB_NAME).is_file():
        return {"items": []}
    with closing(store.connect(project_root)) as connection:
        tables = store._table_names(connection)
        rows = connection.execute(
            "SELECT surface, normalized_surface, spoken_form, confidence, source FROM pronunciations"
        ).fetchall() if "pronunciations" in tables else []
        # Tên người nghe vừa thêm (chưa có dòng nào trong bảng) cũng là một dòng, đang chờ áp.
        surfaces = {str(row["normalized_surface"]): str(row["surface"]) for row in rows}
        surfaces.update({key: str(entry["surface"]) for key, entry in wishes.items() if key not in surfaces})
        # Khoá bảng là cả cụm đã chuẩn hoá; từ trong câu so bằng casefold - tên nhiều từ (hiếm) không bao giờ khớp một từ,
        # đúng như TTS chỉ ghi đè từng từ.
        lines: dict[str, int] = defaultdict(int)
        examples: dict[str, Any] = {}
        names = store.chapter_names(connection) if "segments" in tables else {}
        for segment in connection.execute(
            "SELECT id, chapter_id, seq, text, speaker, wav_path FROM segments ORDER BY wav_path IS NULL, chapter_id, seq"
        ) if "segments" in tables else ():
            for word in {word.casefold() for word in WORD.findall(str(segment["text"] or ""))} & surfaces.keys():
                lines[word] += 1
                examples.setdefault(word, segment)
        items: list[dict[str, Any]] = []
        known = {str(row["normalized_surface"]): row for row in rows}
        for key, surface in surfaces.items():
            row = known.get(key)
            spoken = str(row["spoken_form"]) if row is not None else ""
            wish = wishes.get(key)
            # Yêu cầu bằng đúng cách đang đọc (đã áp, hay "Đúng rồi, giữ") không đổi gì - không phải "chờ áp dụng" mà là
            # người nghe đã quyết, như `store._kept_as_is`.
            kept = wish is not None and wish["spoken_form"] == spoken
            by_listener = kept or (row is not None and str(row["source"]) == LISTENER_PRONUNCIATION_SOURCE)
            waiting = wish is not None and not kept
            items.append({
                "surface": surface,
                "spoken": spoken,
                "byListener": by_listener,
                "confidence": round(float(row["confidence"]), 2) if row is not None else None,
                "lines": lines.get(key, 0),
                "requested": wish["spoken_form"] if waiting else None,
                "example": _example(examples[key], names) if key in examples else None,
            })
    # Bảng mang cả tên của những chương khác trong cuốn (hạt giống từ phần trước): tên máy đoán mà phần này không có câu nào
    # thì không đổi gì ở đây - chỉ đếm (lô 18: 997/1136 dòng).
    shown = [item for item in items if item["lines"] or item["byListener"] or item["requested"]]
    shown.sort(key=lambda item: (-item["lines"], item["surface"].casefold()))
    return {"items": shown, "unseen": len(items) - len(shown)}
