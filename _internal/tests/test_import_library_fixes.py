"""Nhập sách/thư viện a71: không nhập chữ mã hoá, không giấu chương mất file, lời lỗi đứng riêng."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook import importers
from abook.webui import packages
from abook.webui.server import ApiError, Server
from tests import import_fixtures as shared
from tests.test_text_books import TOKEN, _studio_with_text_book
from tests.test_webui_listen_and_sync import _request


@pytest.mark.parametrize("name", list(shared.ENCRYPTED))
def test_encrypted_epub_is_refused_but_obfuscated_fonts_preserve_the_text(tmp_path: Path, name: str) -> None:
    source = tmp_path / name
    source.write_bytes(shared.ENCRYPTED[name]())
    if name.startswith("drm"):
        with pytest.raises(importers.ImportFailed) as caught:
            importers.import_text(source)
        assert str(caught.value) == shared.DRM_ERROR
    else:
        book = importers.import_text(source)
        assert book.chapters[0].text == shared.LINE


@pytest.mark.parametrize("operation", ["preview_text_book", "add_text_book"])
def test_drm_never_reaches_the_library(tmp_path: Path, operation: str) -> None:
    studio, added = _studio_with_text_book(tmp_path)
    source = tmp_path / "drm.epub"
    source.write_bytes(shared.build_drm())
    with pytest.raises(ApiError) as caught:
        getattr(studio, operation)(str(source))
    assert caught.value.message == shared.DRM_ERROR
    assert [book["id"] for book in studio.listen_library()] == [added["id"]]


@pytest.mark.parametrize("damage", ["missing", "empty"])
def test_lost_text_is_counted_once_and_reimport_repairs_it(tmp_path: Path, damage: str) -> None:
    studio, added = _studio_with_text_book(tmp_path)
    folder = studio._listenable(added["id"])
    text = folder / "texts/2.txt"
    original = text.read_bytes()
    if damage == "missing":
        text.rename(tmp_path / "saved.txt")
    else:
        text.write_bytes(b"")
    view = studio.listen_book(added["id"])
    assert view["missingFiles"] == 1
    assert [chapter["id"] for chapter in view["chapters"] if chapter.get("lost")] == [2]
    assert view["stage"] == "text"
    again = studio.add_text_book(str(shared.FIXTURES / "epub3.epub"))
    assert (again["id"], again["how"]) == (added["id"], "repaired")
    assert text.read_bytes() == original
    packages._LOCATORS.clear()  # bộ nhớ đệm file sống hai giây, như với chương audio
    assert studio.listen_book(added["id"])["missingFiles"] == 0


def test_missing_text_endpoint_explains_repair_but_unknown_chapter_is_still_absent(tmp_path: Path) -> None:
    studio, added = _studio_with_text_book(tmp_path)
    (studio._listenable(added["id"]) / "texts/2.txt").rename(tmp_path / "saved.txt")
    server = Server(studio, port=0).start()
    try:
        missing = _request(server.port, "GET", f"/api/listen/books/{added['id']}/chapters/2/text", headers=TOKEN)
        absent = _request(server.port, "GET", f"/api/listen/books/{added['id']}/chapters/99/text", headers=TOKEN)
    finally:
        server.stop()
    assert missing[0] == absent[0] == 404
    assert json.loads(missing[1])["error"] == "Mất file chữ của chương này trên máy. Bạn hãy thêm lại đúng file sách gốc để chép bù."
    assert json.loads(absent[1])["error"] == "Chương này không có chữ riêng"


@pytest.mark.parametrize("kind", ["EPUB", "DOCX"])
@pytest.mark.parametrize("operation", ["preview_text_book", "add_text_book"])
def test_standalone_import_error_starts_with_a_capital(tmp_path: Path, kind: str, operation: str) -> None:
    studio, _ = _studio_with_text_book(tmp_path)
    source = tmp_path / ("broken." + kind.lower())
    source.write_bytes(b"not a zip")
    with pytest.raises(ApiError) as caught:
        getattr(studio, operation)(str(source))
    assert caught.value.message.startswith(f"Không phải file {kind}")
