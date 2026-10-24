"""Mã sách không mang đường dẫn (docs/BOOK_IDS.md; soát UX 29-09, mục 23).

Mã sách là HMAC của đường dẫn với khoá bí mật của máy: `#/book/<mã>` trên thanh địa chỉ (nghe từ xa bằng trình duyệt),
link, ảnh chụp màn hình không giải ra được tên tài khoản Windows.
"""
from __future__ import annotations

import base64
import binascii
import os
from pathlib import Path

from abook.webui import library as library_module
from abook.webui.library import book_id
from tests.test_webui_listen_and_sync import library  # noqa: F401 - library là fixture


def test_the_id_says_nothing_about_the_folder(library) -> None:  # noqa: F811 - fixture
    lib, project, _listening = library
    identifier = book_id(project)

    assert library_module.ID_PATTERN.fullmatch(identifier)
    assert book_id(project) == identifier == book_id(project / "." / ".." / project.name), "cùng thư mục thì cùng mã"
    if os.name == "nt":
        assert book_id(Path(str(project).upper())) == identifier, "Windows không phân biệt hoa thường"
    try:
        decoded = base64.urlsafe_b64decode(identifier + "=" * (-len(identifier) % 4))
    except (ValueError, binascii.Error):
        decoded = b""
    for piece in (project.name, "thu_vien", Path.home().name):
        assert piece not in identifier and piece.encode("utf-8") not in decoded
    assert lib.resolve(identifier) == project.resolve()


def test_each_computer_has_its_own_ids_and_keeps_them(tmp_path: Path, monkeypatch) -> None:
    folder = tmp_path / "Sách"
    monkeypatch.setenv("ABOOK_PREFERENCES", str(tmp_path / "may_a" / "preferences.json"))
    first = book_id(folder)
    monkeypatch.setenv("ABOOK_PREFERENCES", str(tmp_path / "may_b" / "preferences.json"))
    assert book_id(folder) != first, "khoá bí mật của mỗi máy: đoán tên tài khoản rồi băm thử không ra mã"

    monkeypatch.setenv("ABOOK_PREFERENCES", str(tmp_path / "may_a" / "preferences.json"))
    library_module._ID_KEYS.clear()  # như mở lại app: khoá đọc lại từ đĩa
    assert book_id(folder) == first
    assert len((tmp_path / "may_a" / library_module.ID_KEY_FILE).read_text(encoding="ascii").strip()) == 64
