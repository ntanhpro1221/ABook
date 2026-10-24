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
    assert json.loads(missing[1])["error"] == "Mất chữ chương — bạn thêm lại đúng file sách gốc để chép bù."
    assert json.loads(absent[1])["error"] == "Chương này không có chữ riêng"


@pytest.mark.parametrize("kind", ["EPUB", "DOCX"])
@pytest.mark.parametrize("operation", ["preview_text_book", "add_text_book"])
def test_standalone_import_error_starts_with_a_capital(tmp_path: Path, kind: str, operation: str) -> None:
    studio, _ = _studio_with_text_book(tmp_path)
    source = tmp_path / ("broken." + kind.lower())
    source.write_bytes(b"not a zip")
    with pytest.raises(ApiError) as caught:
        getattr(studio, operation)(str(source))
    assert caught.value.message == f"File {kind} hỏng hoặc sai định dạng. Tải lại hoặc dùng TXT."


def test_audio_with_missing_text_still_counts_as_one_complete_chapter(tmp_path: Path) -> None:
    studio, added = _studio_with_text_book(tmp_path)
    folder = studio._listenable(added["id"])
    manifest_path = folder / "book.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["complete"] = True
    for chapter in manifest["chapters"]:
        chapter["available"] = True
        chapter["file"] = f"{chapter['id']}.mp3"
        (folder / chapter["file"]).write_bytes(b"audio")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (folder / "texts/2.txt").rename(tmp_path / "saved.txt")
    view = studio.listen_book(added["id"])
    assert view["missingFiles"] == 1
    assert all(chapter["available"] for chapter in view["chapters"])
    assert view["complete"] is True


ENTITY_ERROR = "Có nội dung XML lạ (khai báo entity) - không mở để giữ an toàn máy"


@pytest.mark.parametrize(("name", "error"), [
    ("entity_utf16.epub", ENTITY_ERROR), ("entity_utf16be.epub", ENTITY_ERROR),
    ("xml_shift_jis.epub", importers.BROKEN.format(kind="EPUB")), ("xml_gb2312.epub", importers.BROKEN.format(kind="EPUB")),
    ("xml_euc_kr.epub", importers.BROKEN.format(kind="EPUB")),
])
def test_utf16_entities_and_multibyte_xml_declarations_fail_in_words(tmp_path: Path, name: str, error: str) -> None:
    source = tmp_path / name
    source.write_bytes(shared.XML_ENCODINGS[name]())
    with pytest.raises(importers.ImportFailed) as caught:
        importers.import_text(source)
    assert str(caught.value) == error


def test_xml_follows_only_its_own_declaration(tmp_path: Path) -> None:
    for name in ("nav_meta_charset.epub", "xml_koi8r.epub"):
        (tmp_path / name).write_bytes(shared.XML_ENCODINGS[name]())
    nav = importers.import_text(tmp_path / "nav_meta_charset.epub")
    assert [chapter.title for chapter in nav.chapters] == ["Chương 1: Bến đò", "Chương 2: Mưa"]
    assert importers.import_text(tmp_path / "xml_koi8r.epub").title == "Книга"


@pytest.mark.parametrize("name", ["entity_utf16_ws.epub", "entity_utf16be_ws.epub", "entity_long_comment.epub"])
def test_the_entity_guard_reads_the_whole_file_in_any_encoding(tmp_path: Path, name: str) -> None:
    source = tmp_path / name
    source.write_bytes(shared.XML_ENCODINGS[name]())
    with pytest.raises(importers.ImportFailed) as caught:
        importers.import_text(source)
    assert str(caught.value) == ENTITY_ERROR


@pytest.mark.parametrize("name", ["nav_cp1258.epub", "nav_cp1252_undefined.epub"])
def test_a_table_of_contents_that_does_not_decode_is_dropped_not_patched(tmp_path: Path, name: str) -> None:
    source = tmp_path / name
    source.write_bytes(shared.XML_ENCODINGS[name]())
    book = importers.import_text(source)
    assert len(book.chapters) == 2
    assert not any("\ufffd" in chapter.title or "Café" in chapter.title for chapter in book.chapters), "mục lục hỏng: tên chương theo spine"


def test_encoding_names_are_normalised_the_same_way_on_both_platforms(tmp_path: Path) -> None:
    for name, title in (("xml_utf8_name.epub", "Tên sách"), ("xml_latin1_name.epub", "Café")):
        (tmp_path / name).write_bytes(shared.XML_ENCODINGS[name]())
        assert importers.import_text(tmp_path / name).title == title
    results = {case["case"]: case.get("text", case.get("error")) for case in shared.xml_case_results()}
    # Các bí danh codecs.lookup trong whitelist được bổ sung vào fixture chung; chúng đều chứa chữ A.
    aliases = [case for case in results if case.startswith("alias ")]
    assert aliases
    for case in aliases:
        assert results.pop(case) == "A", case
    broken = importers.BROKEN.format(kind="EPUB")
    readable = {"utf8 (utf-8)": "Tên sách", "UTF-8 (utf-8)": "Tên sách", "utf-16 (utf-16)": "Tên sách", "UTF-16BE (utf-16-be)": "Tên",
                "latin-1 (latin-1)": "Café", "latin1 (latin-1)": "Café", "iso-8859-1 (latin-1)": "Café", "iso8859-1 (latin-1)": "Café",
                "windows-1252 (cp1252)": "Café “x”", "cp1252 (cp1252)": "Café", "windows-1258 (cp1258)": "Tên", "cp1258 (cp1258)": "Tên",
                "ascii (ascii)": "abc", "us-ascii (ascii)": "abc", "KOI8-R (koi8-r)": "Книга", "iso-8859-15 (iso8859-15)": "Café €", "utf-8 bom": "Tên",
                "utf-16-le không bom": "Tên", "utf-16-be không bom": "Tên"}
    for case, text in readable.items():
        assert results.pop(case) == text, case
    for case in ("entity utf-16-le không bom, mở bằng xuống dòng", "entity utf-16-be không bom, mở bằng dấu cách", "entity sau chú thích dài",
                 "entity chữ thường"):
        assert results.pop(case) == ENTITY_ERROR, case
    # Còn lại đều là file hỏng: UTF-16 khai trên file một byte, đầu UTF-16 lệch, UTF-32, bảng mã nhiều byte (kể cả có trạng thái: ISO-2022-JP,
    # HZ), bảng mã một byte ngoài danh sách chung hai bên (mac-roman), tên lạ, byte ngoài bảng mã.
    assert set(results) == {"utf-16 (utf-8)", "UTF-16LE (utf-16-be)", "us-ascii (utf-8)", "UTF-32 (utf-32)", "shift_jis (shift_jis)",
                            "ISO-2022-JP (iso2022_jp)", "HZ-GB-2312 (hz)", "mac-roman (mac-roman)",
                            "foo (utf-8)", "windows-1252 0x81", "windows-1252 0x8D", "utf-8 hỏng"}
    assert set(results.values()) == {broken}
