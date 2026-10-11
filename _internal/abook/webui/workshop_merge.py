"""Mở file dự án `.abookproj` của CÙNG dự án đã có ở máy này (soát UX a25 T5): sửa của người dùng trong xưởng của file - yêu cầu
chờ dây chuyền (`overrides.json`: cách đọc, ai nói câu nào, cách đọc câu, giọng, thu lại, cả những thẻ đã quyết "giữ nguyên"),
phán quyết "Cần nghe lại" (`reviews.json`) và các thẻ đã quyết ghi ở file riêng (`aliases.json` "một người hai tên",
`bracket_rule.json` người nói câu 『』, `narrator_sections.json` người kể theo đoạn) - được GỘP vào dự án, không bị bỏ im lặng.

Luật gộp (bản Kotlin: WorkshopMerge.kt; hai bên đáp chung tests/fixtures/book_edits/workshop_merge/): mục chỉ có ở một bên thì
lấy; cùng khoá khác giá trị thì bản có mốc thời gian của mục mới hơn thắng (`requested_at` / `at`; thiếu mốc = cũ nhất), bằng
nhau thì giữ bản của máy này. Mục lấy từ file mang thêm `merged_at`: với máy này nó là sửa MỚI, nên hộp "Áp dụng N thay đổi" (chỉ kể
yêu cầu ghi sau lần chạy cuối) vẫn hiện nó - còn mốc gốc giữ nguyên để lần gộp sau vẫn so đúng sửa nào mới hơn."""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .. import aliases, bracket_rule, listener_overrides, narrator_sections
from .reviews import REVIEWS_NAME, Reviews

MERGED_AT = "merged_at"
# Không phải giá trị của sửa: mốc thời gian và yêu cầu cũ mà yêu cầu này đã thay ("Hoàn tác").
_NOT_VALUE = ("requested_at", "at", MERGED_AT, "replaced")
_RULE = "rule"


def _same(data: Any) -> dict[str, Any]:
    return dict(data) if isinstance(data, dict) else {}


def _aliases_in(data: Any) -> dict[str, Any]:
    rows = data.get("aliases") if isinstance(data, dict) else None
    return {aliases.key(str(row["alias"])): row for row in rows
            if isinstance(row, dict) and str(row.get("alias") or "").strip()} if isinstance(rows, list) else {}


def _aliases_out(entries: dict[str, Any]) -> dict[str, Any]:
    return {"version": 1, "aliases": [entries[key] for key in sorted(entries)]}


def _rule_in(data: Any) -> dict[str, Any]:
    return {_RULE: data} if isinstance(data, dict) and str(data.get("speaker") or "").strip() else {}


def _rule_out(entries: dict[str, Any]) -> dict[str, Any]:
    return dict(entries.get(_RULE) or {})


def _sections_in(data: Any) -> dict[str, Any]:
    sections = data.get("sections") if isinstance(data, dict) else None
    entries: dict[str, Any] = {}
    for chapter, rows in sections.items() if isinstance(sections, dict) else ():
        for row in rows if isinstance(rows, list) else ():
            if isinstance(row, dict) and isinstance(row.get("from_seq"), int) and isinstance(row.get("to_seq"), int):
                entries[f"{chapter}:{row['from_seq']}:{row['to_seq']}"] = row
    return entries


def _sections_out(entries: dict[str, Any]) -> dict[str, Any]:
    sections: dict[str, list[Any]] = {}
    for key, row in entries.items():
        sections.setdefault(key.split(":", 1)[0], []).append(row)
    return {"version": 1, "sections": {chapter: sorted(rows, key=lambda row: row["from_seq"]) for chapter, rows in sections.items()}}


# Tên file trong thư mục dự án -> (trường mốc của từng mục, đọc nội dung ra {khoá: mục}, dựng lại nội dung từ {khoá: mục}).
# `overrides.json` gộp theo từng phần (merge_overrides).
FILES: dict[str, tuple[str, Callable[[Any], dict[str, Any]], Callable[[dict[str, Any]], dict[str, Any]]]] = {
    listener_overrides.OVERRIDES_FILE: ("requested_at", _same, _same),
    REVIEWS_NAME: ("at", _same, _same),
    aliases.FILE_NAME: ("at", _aliases_in, _aliases_out),
    bracket_rule.FILE_NAME: ("at", _rule_in, _rule_out),
    narrator_sections.FILE_NAME: ("at", _sections_in, _sections_out),
}


def _stamp(entry: dict[str, Any], field: str) -> float:
    value = entry.get(field)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else float("-inf")


def _value(entry: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in entry.items() if key not in _NOT_VALUE}


def merge_entries(mine: dict[str, Any], theirs: dict[str, Any], field: str,
                  now: float | None = None) -> tuple[dict[str, Any], int, int]:
    """{khoá: mục} của máy này gộp với của file -> (kết quả, số mục lấy từ file, số mục giữ bản máy này vì mới hơn hay bằng).
    `now`: có thì mục lấy từ file mang `merged_at`."""
    merged = dict(mine)
    taken = kept = 0
    for key, entry in theirs.items():
        if not isinstance(entry, dict):
            continue
        local = merged.get(key)
        if isinstance(local, dict):
            if _value(local) == _value(entry):
                continue
            if _stamp(entry, field) <= _stamp(local, field):
                kept += 1
                continue
        merged[key] = {**entry, MERGED_AT: now} if now is not None else dict(entry)
        taken += 1
    return merged, taken, kept


def merge_overrides(mine: dict[str, Any], theirs: dict[str, Any], now: float) -> tuple[dict[str, Any], int, int]:
    """`overrides.json`: gộp từng mục của mọi phần ({khoá: mục}); phần khác (`version`) giữ của máy này."""
    merged = dict(mine)
    taken = kept = 0
    for section, entries in theirs.items():
        if not isinstance(entries, dict):
            continue
        local = merged.get(section)
        merged[section], got, held = merge_entries(local if isinstance(local, dict) else {}, entries, "requested_at", now)
        taken += got
        kept += held
    return merged, taken, kept


def merge_file(name: str, mine: Any, theirs: Any, now: float) -> tuple[dict[str, Any], int, int]:
    """Nội dung một file của máy này gộp với của file dự án -> (nội dung gộp, số mục lấy, số mục giữ)."""
    if name == listener_overrides.OVERRIDES_FILE:
        return merge_overrides(_same(mine), _same(theirs), now)
    field, entries_of, content_of = FILES.get(name, ("at", _same, _same))
    merged, taken, kept = merge_entries(entries_of(mine), entries_of(theirs), field)
    return content_of(merged), taken, kept


def merge_files(mine: dict[str, Any], theirs: dict[str, Any], now: float) -> tuple[dict[str, Any], dict[str, int]]:
    """{tên file: nội dung} của máy này gộp với của file - cùng hình dạng ca hợp đồng (`workshop_merge/<ca>.json`)."""
    merged: dict[str, Any] = {}
    report = {"merged": 0, "kept": 0}
    for name in sorted(set(mine) | set(theirs)):
        merged[name], taken, kept = merge_file(name, mine.get(name), theirs.get(name), now)
        report["merged"] += taken
        report["kept"] += kept
    return merged, report


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write(project_root: Path, name: str, content: dict[str, Any]) -> None:
    """Ghi bằng đúng đường ghi của từng file (thay nguyên tử)."""
    if name == listener_overrides.OVERRIDES_FILE:
        listener_overrides._write(project_root, content)
    elif name == aliases.FILE_NAME:
        aliases._write(project_root, content["aliases"])
    elif name == bracket_rule.FILE_NAME:
        bracket_rule._write(project_root, content)
    elif name == narrator_sections.FILE_NAME:
        narrator_sections._write(project_root, {int(chapter): rows for chapter, rows in content["sections"].items()})


def merge_workshop(project_root: Path, member: Callable[[str], bytes | None], reviews: Reviews,
                   now: float) -> dict[str, int]:
    """Gộp sửa trong xưởng của file (`member("overrides.json")` -> byte của `project/overrides.json`, None khi file không có) vào
    dự án `project_root`. Trả {"merged": N, "kept": M}."""
    root = Path(project_root)
    report = {"merged": 0, "kept": 0}
    for name, (field, _entries_of, _content_of) in FILES.items():
        raw = member(name)
        try:
            theirs = json.loads(raw.decode("utf-8")) if raw is not None else None
        except (UnicodeDecodeError, ValueError):
            theirs = None
        if not isinstance(theirs, dict) or not theirs:
            continue
        if name == REVIEWS_NAME:
            taken, kept = reviews.merge(root, lambda mine, incoming=theirs, stamp=field: merge_entries(mine, incoming, stamp))
        else:
            mine = listener_overrides.read_overrides(root) if name == listener_overrides.OVERRIDES_FILE else _read(root / name)
            merged, taken, kept = merge_file(name, mine, theirs, now)
            if taken:
                _write(root, name, merged)
        report["merged"] += taken
        report["kept"] += kept
    return report
