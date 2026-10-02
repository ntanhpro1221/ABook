"""Tên hiển thị người nghe đặt cho một nhân vật (tab Nhân vật, "Đổi tên"): chỉ là cái TÊN trên màn hình.

Không đụng sổ nhân vật (`characters.display_name` bị bước phân vai ghi đè mỗi lần), không đụng câu, giọng hay audio - nên
không phải thay đổi chờ "Áp dụng": có hiệu lực ngay. File `names.json` cạnh sổ dự án, máy chủ giao diện ghi (dây chuyền
không đọc): {"<tên nhân vật như dự án viết>": {"name": "<tên hiển thị>", "renamed_at": "<ISO>"}}.
`continuation.seed` chép nó sang phần sau (như `aliases.json`); file .abook lấy tên từ `store.cast` nên cũng mang theo.
"""
from __future__ import annotations

import json
import time
import unicodedata
from pathlib import Path
from typing import Any

from .io_utils import atomic_write_json

FILE_NAME = "names.json"
MAX_NAME = 80


def clean(name: Any) -> str:
    """Tên người gõ: NFC, một dấu cách giữa các từ, không dài quá `MAX_NAME`."""
    return " ".join(unicodedata.normalize("NFC", str(name or "")).split())[:MAX_NAME]


def name_key(character: str) -> str:
    from .aliases import key

    return key(character)


def _entries(project_root: Path) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads((Path(project_root) / FILE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(character): entry for character, entry in data.items()
            if isinstance(entry, dict) and clean(entry.get("name")) and str(character).strip()}


def load(project_root: Path) -> dict[str, str]:
    """{khoá nhân vật (`aliases.key`): tên hiển thị}. Không có file thì rỗng."""
    return {name_key(character): clean(entry["name"]) for character, entry in _entries(project_root).items()}


def shown(project_root: Path, character: str) -> str:
    """Tên người nghe đặt cho nhân vật này, hay "" khi chưa đặt."""
    return load(project_root).get(name_key(character), "")


def set_name(project_root: Path, character: str, name: str, original: str = "", *, now: float | None = None) -> bool:
    """Đặt tên hiển thị. Tên rỗng hay trùng `original` (tên gốc) thì bỏ tên đã đặt - trở về tên gốc. Trả về True khi file đổi."""
    character = str(character).strip()
    name = clean(name)
    entries = _entries(project_root)
    mine = {raw for raw in entries if name_key(raw) == name_key(character)}
    current = clean(entries[next(iter(mine))]["name"]) if mine else ""
    if not name or name == clean(original):
        if not mine:
            return False
        kept = {raw: entry for raw, entry in entries.items() if raw not in mine}
    else:
        if name == current:
            return False
        kept = {raw: entry for raw, entry in entries.items() if raw not in mine}
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() if now is None else now))
        kept[character] = {"name": name, "renamed_at": stamp + "Z"}
    atomic_write_json(Path(project_root) / FILE_NAME, kept)
    return True


def carry(source_root: Path, target_root: Path) -> int:
    """Chép tên của phần trước sang phần sau (giữ cái phần sau đã đặt). Trả về số tên thêm."""
    have = load(target_root)
    entries = _entries(target_root)
    added = 0
    for character, entry in _entries(source_root).items():
        if name_key(character) in have:
            continue
        entries[character] = {"name": clean(entry["name"]), "renamed_at": str(entry.get("renamed_at") or "")}
        added += 1
    if added:
        atomic_write_json(Path(target_root) / FILE_NAME, entries)
    return added
