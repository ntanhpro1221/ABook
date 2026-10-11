"""Trình tạo sách với thư mục hàng nghìn chương (soát uxfix30): bước chọn truyện mở mỗi file NĂM lần (chữ đầu, dòng đầu, ghi công
đầu, ghi công cuối, sha256) - mỗi lần mở ~1 ms trên Windows; bấm "Tạo" lại quét y như thế chỉ để lấy danh sách file. Thư mục 3000
chương: quét 6,4 -> 4,7 s, tạo 12 -> 5,7 s, kết quả quét và dự án tạo ra giống hệt."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from abook.webui import actions

HEAD = "Chương 1: Mở đầu\n\nTranslator: NicK\n\nEditor: Deemo\n\n“Ồ… Ta biết rồi.”\n\nCô gật đầu.\n"
TAIL = "\n\nLucien bước vào làng.\n\nỦng hộ nhóm dịch qua Momo 0912345678\n\nĐọc truyện full tại truyenfull.vn\n"


def _folder(tmp_path: Path) -> dict[str, bytes]:
    files = {
        "001.txt": (HEAD + "\n\n".join(f"Câu kể thứ {n}." for n in range(900)) + TAIL).encode("utf-8"),  # > 8 KB
        "002.txt": ("﻿\n\n" + HEAD + TAIL).replace("\n", "\r\n").encode("utf-8"),
        "003.txt": b"",
        "004.txt": "Chương 4\n\nCâu kể.\n".encode(),  # quá ba file: không xét tách file (txt_split đọc lại cả file)
    }
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    return files


def test_each_chapter_file_is_opened_once_and_reads_the_same(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    files = _folder(tmp_path)
    opened: list[str] = []
    real_open = Path.open

    def counting_open(self: Path, *args, **kwargs):
        opened.append(self.name)
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counting_open)
    rows = {row["name"]: row for row in actions.scan_inputs([str(tmp_path)])["files"]}
    assert sorted(opened) == sorted(files), opened
    long, crlf, empty = rows["001.txt"], rows["002.txt"], rows["003.txt"]
    assert [row["sha256"] for row in rows.values()] == [hashlib.sha256(files[name]).hexdigest() for name in sorted(files)]
    assert [row["bytes"] for row in rows.values()] == [len(files[name]) for name in sorted(files)]
    assert long["firstLine"] == crlf["firstLine"] == "Chương 1: Mở đầu" and empty["firstLine"] == ""
    assert long["credits"] == crlf["credits"] == ["Translator: NicK", "Editor: Deemo"] and empty["credits"] == []
    assert long["tailCredits"] == crlf["tailCredits"] == ["Ủng hộ nhóm dịch qua Momo 0912345678", "Đọc truyện full tại truyenfull.vn"]


def test_creating_the_book_does_not_read_the_chapters_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "nguon"
    source.mkdir()
    _folder(source)

    def scanned(*_args, **_kwargs):
        raise AssertionError("tạo sách quét lại cả thư mục")

    monkeypatch.setattr(actions, "scan_inputs", scanned)
    assert actions.input_files([str(source)]) == [(source / f"00{n}.txt").resolve() for n in range(1, 5)]
    root = actions.create_book(tmp_path / "thu_vien", [str(source)], "Thử", "high_quality", "")
    assert (root / "project.sqlite3").is_file()
