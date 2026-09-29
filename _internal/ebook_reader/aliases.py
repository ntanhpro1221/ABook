"""Bí danh người nghe đã xác nhận: "Thiên Biến Vạn Hóa" là Krai - quyết một lần, các phần sau của cuốn tự hiểu.

Thẻ "Một người hai tên" (webui/work_items.py) sửa người nói của TỪNG câu trong một dự án (overrides.json `speakers`, theo mã
câu). Phần sau của cuốn ("Làm tiếp cuốn này", continuation.py) là một dự án khác với mã câu khác, nên quyết định ở cấp TÊN
nằm ở đây: file `aliases.json` cạnh sổ dự án. `continuation.seed` chép nó sang phần sau, và bước gom tên trước khi phân vai
(`character_registry._canonicalize_named_speakers`) trỏ nhãn bí danh về người ấy - câu của bí danh không bao giờ có giọng
thứ hai.

Máy chủ giao diện ghi file này (như overrides.json); dây chuyền chỉ đọc. Khoá so tên như `character_registry.identity_key`
(hoa/thường, khoảng trắng, gạch dưới) sau khi chuẩn hoá Unicode NFC.
"""
from __future__ import annotations

import json
import os
import time
import unicodedata
from pathlib import Path
from typing import Any

FILE_NAME = "aliases.json"
MAX_NAME = 200


def key(name: str) -> str:
    """Khoá so hai cách viết một tên: như `identity_key`, thêm NFC (bàn phím và file nguồn có thể dựng dấu khác nhau)."""
    from .character_registry import identity_key

    return identity_key(unicodedata.normalize("NFC", str(name)))


def _entries(project_root: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads((Path(project_root) / FILE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    entries = data.get("aliases") if isinstance(data, dict) else None
    return [entry for entry in entries or [] if isinstance(entry, dict)
            and str(entry.get("alias") or "").strip() and str(entry.get("person") or "").strip()]


def load(project_root: Path) -> dict[str, str]:
    """{khoá bí danh: người} - người là tên nhân vật như dự án viết (nhãn người nói), đã đi hết chuỗi (A là B, B là C -> A
    là C). Không có file thì rỗng."""
    direct = {key(entry["alias"]): str(entry["person"]).strip() for entry in _entries(project_root)}
    resolved: dict[str, str] = {}
    for alias, person in direct.items():
        seen = {alias}
        while key(person) in direct and key(person) not in seen:
            seen.add(key(person))
            person = direct[key(person)]
        resolved[alias] = person
    return resolved


def _write(project_root: Path, entries: list[dict[str, Any]]) -> None:
    target = Path(project_root) / FILE_NAME
    temporary = target.with_name(f".{FILE_NAME}.tmp")
    temporary.write_text(json.dumps({"version": 1, "aliases": entries}, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, target)


def add(project_root: Path, alias: str, person: str, *, now: float | None = None) -> bool:
    """Ghi "`alias` là `person`". Quyết định mới nhất thắng: bí danh ấy từng trỏ về người khác, hay người ấy từng bị ghi là
    bí danh của `alias` (chiều ngược), thì bản cũ bỏ đi. Ai đang trỏ về `alias` được trỏ thẳng về `person`. Trả về True khi
    file đổi."""
    alias, person = str(alias).strip()[:MAX_NAME], str(person).strip()[:MAX_NAME]
    if not alias or not person or key(alias) == key(person):
        return False
    entries = _entries(project_root)
    if any(key(entry["alias"]) == key(alias) and key(entry["person"]) == key(person) for entry in entries):
        return False
    kept = [entry for entry in entries if key(entry["alias"]) != key(alias)
            and not (key(entry["alias"]) == key(person) and key(entry["person"]) == key(alias))]
    for entry in kept:
        if key(entry["person"]) == key(alias):
            entry["person"] = person
    kept.append({"alias": alias, "person": person, "at": time.time() if now is None else now})
    _write(project_root, kept)
    return True


def carry(source_root: Path, target_root: Path) -> int:
    """Chép mọi bí danh của phần trước sang phần sau (giữ cái phần sau đã có). Trả về số bí danh thêm."""
    added = 0
    have = load(target_root)
    for entry in _entries(source_root):
        if key(entry["alias"]) in have:
            continue
        if add(target_root, entry["alias"], entry["person"], now=float(entry.get("at") or time.time())):
            added += 1
    return added
