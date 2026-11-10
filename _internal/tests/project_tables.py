"""Bảng project cho test, dựng từ chính `abook.database.SCHEMA`.

Test không chép tay `CREATE TABLE segments (...)` nữa: thêm một cột vào schema thật thì mọi
fixture có ngay cột ấy, không đỏ hàng loạt vì `KeyError` trên một bảng chép thiếu.

Bảng dựng ở đây có đúng tên cột, kiểu, giá trị mặc định, khoá chính và ràng buộc UNIQUE của
bảng thật. `NOT NULL`, `CHECK` và khoá ngoại được bỏ để một test chỉ chèn những cột nó cần.
Test cần đủ ràng buộc thì dùng `ProjectDatabase` thật.
"""
from __future__ import annotations

import sqlite3
from functools import lru_cache

from abook.database import SCHEMA


def _quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


@lru_cache(maxsize=1)
def _tables() -> dict[str, str]:
    real = sqlite3.connect(":memory:")
    try:
        real.executescript(SCHEMA)
        names = [row[0] for row in real.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {name: _loose_table(real, name) for name in names}
    finally:
        real.close()


def _loose_table(real: sqlite3.Connection, table: str) -> str:
    columns = list(real.execute(f"PRAGMA table_info({_quoted(table)})"))
    key = [row[1] for row in sorted((row for row in columns if row[5]), key=lambda row: row[5])]
    rowid_alias = len(key) == 1 and next(row[2] for row in columns if row[1] == key[0]).upper() == "INTEGER"
    parts = []
    for _cid, name, kind, _notnull, default, _pk in columns:
        part = f"{_quoted(name)} {kind}".rstrip()
        if rowid_alias and name == key[0]:
            part += " PRIMARY KEY"
        if default is not None:
            part += f" DEFAULT {default}"
        parts.append(part)
    if key and not rowid_alias:
        parts.append(f"PRIMARY KEY ({', '.join(map(_quoted, key))})")
    for _seq, index, unique, origin, _partial in real.execute(f"PRAGMA index_list({_quoted(table)})"):
        if unique and origin == "u":
            members = [row[2] for row in real.execute(f"PRAGMA index_info({_quoted(index)})")]
            parts.append(f"UNIQUE ({', '.join(map(_quoted, members))})")
    return f"CREATE TABLE {_quoted(table)} (\n    " + ",\n    ".join(parts) + "\n);\n"


def project_tables_sql(*tables: str) -> str:
    """Câu `CREATE TABLE` của các bảng project được nêu tên, theo thứ tự được nêu."""
    known = _tables()
    missing = [name for name in tables if name not in known]
    if missing:
        raise KeyError(f"abook.database.SCHEMA không có bảng: {', '.join(missing)}")
    return "".join(known[name] for name in tables)


def create_project_tables(connection: sqlite3.Connection, *tables: str) -> None:
    """Dựng các bảng project được nêu tên trong `connection`; không commit thay người gọi."""
    for name in tables:
        connection.execute(project_tables_sql(name))
