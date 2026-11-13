"""Chương chưa tách câu (dự án chưa chạy) lấy tên theo dòng đầu file nguồn, không theo tên file - 2026-09-29.

Nguồn cuốn 2 đánh số file lệch một so với truyện: "767.txt" mở đầu "Chương 768 - Mô hình chân không mới". Trang dự án
của phần 2 (chưa chạy) từng ghi "Chương 767" ngay sau "Chương 767" cuối phần 1 - trông như làm lại một chương.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from abook.webui.store import chapter_names
from tests.project_tables import create_project_tables


def test_an_unsegmented_chapter_takes_its_heading_from_the_file(tmp_path: Path) -> None:
    source = tmp_path / "767.txt"
    source.write_text("\n\nChương 768 - Mô hình chân không mới\nNội dung…\n" + "chữ " * 3000, encoding="utf-8")
    db = sqlite3.connect(tmp_path / "project.sqlite3")  # thư mục sách = chỗ của sổ (book_paths.connection_root)
    db.row_factory = sqlite3.Row
    create_project_tables(db, "chapters", "segments")
    db.execute("INSERT INTO chapters (id, chapter_index, title, input_path) VALUES (1, 1, '767', ?)", (str(source),))
    db.execute("INSERT INTO chapters (id, chapter_index, title, input_path) VALUES (2, 2, '768', ?)",
               (str(tmp_path / "missing.txt"),))

    names = chapter_names(db, tmp_path)  # chỉ đọc nguồn nằm trong thư mục sách (book_paths)

    assert names[1]["name"] == "Chương 768" and names[1]["subtitle"] == "Mô hình chân không mới"
    assert names[2]["name"] == "Chương 768", "file mất: tên theo tên file như trước"
