"""Dự án hỏng báo bằng lời người dùng hiểu, không lộ tên cột SQL (soát UX a11)."""
from __future__ import annotations

import sqlite3

from abook.webui.server import broken_reason


def test_a_database_error_is_told_without_the_sql() -> None:
    said = broken_reason(sqlite3.OperationalError("no such column: total_segments"))
    assert "total_segments" not in said and "sổ làm việc" in said


def test_any_other_error_keeps_its_own_words() -> None:
    assert broken_reason(OSError("Không thấy thư mục")) == "Không thấy thư mục"
