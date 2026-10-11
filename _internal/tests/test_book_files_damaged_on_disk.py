"""File sách hỏng và sách đã nhập mất file (soát a28 lỗi 7, 9).

Trước đây: `.abook` cắt cụt / 0 byte báo "Đây không phải file sách của app" (sai chẩn đoán - là file của app chép chưa xong), lật một bit
trong audio thì 500 "BadZipFile: Bad CRC-32 ...". Sách đã nhập mất một chương / chương 0 byte thì trang sách nói "file sách này chỉ có các
chương đã làm", chương 0 byte vẫn "3 phút", và mở lại đúng file .abook gốc chỉ trả "existing" - không có đường sửa.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from abook.webui import bookfile, packages
from abook.webui.server import ApiError
from tests.test_desktop_opens_book_files import _app, _produced


@pytest.mark.parametrize("damage", ["half", "empty", "tail"])
def test_a_cut_book_file_says_it_is_damaged_not_foreign(tmp_path: Path, damage: str) -> None:
    _project, file = _produced(tmp_path)
    data = file.read_bytes()
    file.write_bytes({"half": data[: len(data) // 2], "empty": b"", "tail": data[:-1024]}[damage])
    app = _app(tmp_path, tmp_path / "thu_vien")
    with pytest.raises(ApiError) as caught:
        app.open_book_file(str(file))
    assert caught.value.message == bookfile.DAMAGED


def test_a_flipped_bit_in_a_chapter_is_a_damaged_file_not_a_crash(tmp_path: Path) -> None:
    _project, file = _produced(tmp_path)
    with zipfile.ZipFile(file) as archive:
        info = archive.getinfo("chapters/00001_645.mp3")
    data = bytearray(file.read_bytes())
    start = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
    data[start + 100] ^= 0x01
    file.write_bytes(bytes(data))
    app = _app(tmp_path, tmp_path / "thu_vien")
    with pytest.raises(ApiError) as caught:
        app.open_book_file(str(file))
    assert "hỏng" in caught.value.message and "CRC" not in caught.value.message
    assert not list((tmp_path / "thu_vien" / packages.IMPORTED_FOLDER).glob("*")), "không để nửa cuốn"


def test_a_lost_chapter_is_named_and_reopening_the_file_copies_it_back(tmp_path: Path) -> None:
    _project, file = _produced(tmp_path)
    app = _app(tmp_path, tmp_path / "thu_vien")
    opened = app.open_book_file(str(file))
    app.listening.progress(opened["id"], 1, 4.0, 10.0)
    folder = app.library.resolve_listenable(opened["id"])
    assert folder is not None
    mp3 = folder / "chapters" / "00001_645.mp3"
    mp3.write_bytes(b"")  # chương 0 byte (chép hỏng)
    packages._LOCATORS.clear()
    view = app.listen_book(opened["id"])
    first = view["chapters"][0]
    assert (first["available"], first["duration"], first.get("lost")) == (False, 0.0, True), "0 byte: không '3 phút', không phát"
    assert view["missingFiles"] == 1

    again = app.open_book_file(str(file))

    assert (again["id"], again["how"]) == (opened["id"], "repaired")
    assert mp3.stat().st_size > 0
    packages._LOCATORS.clear()
    view = app.listen_book(opened["id"])
    assert view["chapters"][0]["available"] and view["missingFiles"] == 0
    assert app.listening.get(opened["id"])["last"]["seconds"] == 4.0, "chỗ nghe giữ nguyên"
