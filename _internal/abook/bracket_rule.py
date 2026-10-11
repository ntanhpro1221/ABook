"""Quy ước 『』 của cả cuốn: người nghe nói một lần "lời trong 『』 của cuốn này là của X" (hay "là lời người kể") - mọi
chương, và các phần sau của cuốn, tự áp trước bước phân vai.

Đo 29-09 trên bộ LN (scripts/model_eval/analysis/bracket_flip.py): lỗi ở câu 『』 phần lớn là QUY ƯỚC RIÊNG của từng cuốn
mà model không thể tự biết. Two Childhood Friends dùng 『』 cho lời kể/thông báo - 30/35 câu, cả v3 lẫn 8B gán cho người
trong cảnh; Yamiyo no Hotaru cho linh thể Tọa Phu Đồng Tử - 43 câu, không model nào gán cho nó. Thẻ "Lời trong 『』 là của
một người?" (webui/work_items.py) sửa từng chương; chọn phạm vi "Cả cuốn" thì quyết định nằm ở đây: file
`bracket_rule.json` cạnh sổ dự án, `continuation.seed` chép sang phần sau, và
`character_registry._canonicalize_named_speakers` gán mọi câu nói mở bằng 『 cho người ấy trước khi gom tên.

Máy chủ giao diện ghi file này; dây chuyền chỉ đọc.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

FILE_NAME = "bracket_rule.json"
OPENER = "『"
MAX_NAME = 200


def load(project_root: Path) -> str:
    """Người nói mọi câu 『』 của cuốn (nhãn như dự án viết, "NARRATOR" = người kể), hay "" khi chưa quyết."""
    try:
        data = json.loads((Path(project_root) / FILE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return str(data.get("speaker") or "").strip()[:MAX_NAME] if isinstance(data, dict) else ""


def save(project_root: Path, speaker: str, *, now: float | None = None) -> bool:
    """Ghi quy ước (quyết định mới nhất thắng). Trả về True khi file đổi."""
    speaker = str(speaker).strip()[:MAX_NAME]
    if not speaker or load(project_root) == speaker:
        return False
    _write(project_root, {"version": 1, "speaker": speaker, "at": time.time() if now is None else now})
    return True


def _write(project_root: Path, data: dict[str, Any]) -> None:
    target = Path(project_root) / FILE_NAME
    temporary = target.with_name(f".{FILE_NAME}.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, target)


def carry(source_root: Path, target_root: Path) -> bool:
    """Phần sau nhận quy ước của phần trước, trừ khi nó đã có quy ước riêng."""
    rule = load(source_root)
    return bool(rule) and not load(target_root) and save(target_root, rule)
