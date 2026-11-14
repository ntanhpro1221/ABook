"""Original fixtures: display names must never change source or analysis inputs."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import unicodedata
import zipfile
from pathlib import Path

import pytest

from abook import chapter_titles as titles, importers
from abook.webui import actions, humanize, store
from tests.project_tables import create_project_tables

CASES = json.loads((Path(__file__).parent / "fixtures/chapter_titles.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("text,expected", CASES)
def test_shared_heading_cases(text, expected):
    assert titles.first_heading(text) == expected
    assert titles.first_heading(unicodedata.normalize("NFD", text)) == expected


def test_numbered_subtitle_and_display_position():
    assert humanize.chapter_names("013", "Đoạn kết", index=8) == ("Đoạn kết", "")
    assert humanize.chapter_names("013", "Câu văn bình thường.", index=8) == ("Chương 8", "")
    assert humanize.chapter_names("013", "Chương XIV: Đảo mây", index=8) == ("Chương XIV", "Đảo mây")
    assert humanize.chapter_names("0000 Lời bạt", None, index=8) == ("Lời bạt", "")
    assert humanize.chapter_names("Tên đã đặt", None, index=8) == ("Tên đã đặt", "")


@pytest.mark.parametrize("heading,kind", [("Đoạn kết", "narration"), ("Chương Một", "narration"), ("Chương 3", "heading")])
def test_display_rules_do_not_change_music_model_segment_kinds(heading, kind):
    from abook.webui import music_nnscene

    text = heading + "\n\nChiếc hộp màu tím nằm trên bàn."
    script, _ = music_nnscene.chapter_script(1, "Stored chapter metadata", text)
    assert script["segments"][0]["text"] == heading
    assert script["segments"][0]["kind"] == kind
    assert script["title"] == "Stored chapter metadata"
    assert humanize.chapter_names("013", text, index=1)[0] == heading


@pytest.mark.parametrize("segmented", [False, True])
def test_project_names_and_overrides_are_read_only(tmp_path, segmented):
    source = tmp_path / "013.txt"
    raw = "Đảo pha lê\n\nChiếc hộp nằm trên bàn.\n".encode()
    source.write_bytes(raw)
    db = sqlite3.connect(tmp_path / "project.sqlite3")
    db.row_factory = sqlite3.Row
    create_project_tables(db, "chapters", "segments")
    db.execute("INSERT INTO chapters(id,chapter_index,title,input_path) VALUES(14,8,'013',?)", (str(source),))
    if segmented:
        db.execute("INSERT INTO segments(chapter_id,seq,text) VALUES(14,1,'Đảo pha lê')")
    before = db.total_changes
    assert store.chapter_names(db, tmp_path)[14]["full"] == "Đảo pha lê"
    assert db.total_changes == before
    assert source.read_bytes() == raw
    (tmp_path / store.CHAPTER_TITLES_FILE).write_text(json.dumps({"14": {"title": "Tên tự chọn"}}), encoding="utf-8")
    assert store.chapter_names(db, tmp_path)[14]["name"] == "Tên tự chọn"
    db.close()


def test_txt_metadata_does_not_rewrite_sources_or_splits(tmp_path):
    text = "Đoạn kết\n\nChiếc hộp nằm trên bàn.\n"
    path = tmp_path / "013.txt"
    path.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    book = importers.import_text(tmp_path)
    chapter = book.chapters[0]
    assert chapter.title == "Chương 13"  # The original internal title stays fixed.
    assert chapter.name == "Đoạn kết"
    assert book.chapter_source(chapter) == text
    assert importers.select_chapters(book, [(1, "")]).chapters[0].name == "Đoạn kết"
    assert importers.select_chapters(book, [(1, "Tên riêng")]).chapter_source(chapter) == text
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert importers.split_txt_chapters(text) == []
    scanned = actions.scan_inputs([str(tmp_path)])
    assert scanned["files"][0]["title"] == "Đoạn kết"


def test_filename_number_is_not_a_chapter_number(tmp_path):
    for stem in ("003", "013"):
        (tmp_path / f"{stem}.txt").write_text("Một chiếc lá rơi.\n", encoding="utf-8")
    book = importers.import_text(tmp_path)
    assert [chapter.name for chapter in book.chapters] == ["Chương 1", "Chương 2"]
    assert [chapter.title for chapter in book.chapters] == ["Chương 3", "Chương 13"]


def test_numeric_file_labels_use_book_order_even_without_gaps(tmp_path):
    assert titles.fallback_positions(["645", "646", "647"]) == [1, 2, 3]
    assert titles.fallback_positions(["0000 Mở đầu", "001", "002", "Lời bạt"]) == [None, 2, 3, None]
    assert titles.fallback_positions(["003", "013"]) == [1, 2]
    assert titles.fallback_positions(["001", "003", "002"]) == [1, 2, 3]
    assert titles.file_number("Chương 13") == 13 and titles.file_number("0013 - 13") == 13
    assert titles.file_number("Tên riêng") is None and titles.file_number("1984 năm ấy") is None
    for stem in ("187", "188"):
        (tmp_path / f"{stem}.txt").write_text("Một chiếc lá rơi.\n", encoding="utf-8")
    assert [chapter.name or chapter.title for chapter in importers.import_text(tmp_path).chapters] == ["Chương 1", "Chương 2"]
    assert [row["title"] for row in actions.scan_inputs([str(tmp_path)])["files"]] == ["Chương 1", "Chương 2"]
    (tmp_path / "187.txt").write_text("Chương 187\n\nMột chiếc lá rơi.\n", encoding="utf-8")
    assert importers.import_text(tmp_path).chapters[0].title == "Chương 187"
    assert actions.scan_inputs([str(tmp_path)])["files"][0]["title"] == "Chương 187"


def test_running_pdf_header_and_preamble_are_not_chapter_names():
    pages = [["TÊN SÁCH", f"Một câu chuyện ở trang {page}, còn nguyên nội dung để bạn nghe.", str(page)] for page in (1, 2, 3)]
    book = importers.import_pdf_pages(pages, "Sách")
    assert [chapter.name for chapter in book.chapters] == [""] * len(book.chapters)


@pytest.mark.parametrize("suffix", [".epub", ".docx"])
def test_document_display_titles_keep_the_original_body(tmp_path, suffix):
    path = tmp_path / ("013" + suffix)
    heading, body = "Đoạn kết", "Chiếc hộp nằm trên bàn. " * 8
    with zipfile.ZipFile(path, "w") as archive:
        if suffix == ".epub":
            archive.writestr("META-INF/container.xml", '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="book.opf"/></rootfiles></container>')
            archive.writestr("book.opf", '<package xmlns="http://www.idpf.org/2007/opf"><metadata/><manifest><item id="c" href="c.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="c"/></spine></package>')
            archive.writestr("c.xhtml", f"<html><body><h1>{heading}</h1><p>{body}</p></body></html>")
        else:
            archive.writestr("word/document.xml", f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>{heading}</w:t></w:r></w:p><w:p><w:r><w:t>{body}</w:t></w:r></w:p></w:body></w:document>')
    raw = path.read_bytes()
    book = importers.import_text(path)
    assert len(book.chapters) == 1
    chapter = book.chapters[0]
    assert (chapter.name or chapter.title) == heading
    assert book.to_dict()["chapters"][0]["title"] == chapter.title
    from abook.webui import textbook

    assert textbook.preview(book)["chapters"][0]["title"] == heading
    assert heading in book.chapter_source(chapter)
    assert body.strip() in book.chapter_source(chapter)
    assert path.read_bytes() == raw


def test_packed_book_uses_the_display_name_without_changing_model_rows(tmp_path):
    from abook.webui import bookfile
    from tests.test_webui_listen_and_sync import make_project

    project = make_project(tmp_path)
    source = project / "sources/a.txt"
    source.parent.mkdir()
    raw = "Đoạn kết\n\nChiếc chuông màu tím nằm trong hộp.\n".encode()
    source.write_bytes(raw)
    with sqlite3.connect(project / "project.sqlite3") as db:
        db.execute("UPDATE segments SET text='Đoạn kết' WHERE id=1")
        before = tuple(tuple(row) for row in db.execute("SELECT * FROM segments ORDER BY id"))
        chapters = tuple(tuple(row) for row in db.execute("SELECT * FROM chapters ORDER BY id"))
    packed = bookfile.pack(project, tmp_path / "display.abook", partial=True)
    with zipfile.ZipFile(packed) as archive:
        book = json.loads(archive.read("book.json"))
        assert book["chapters"][0]["title"] == "Đoạn kết"
        assert book["chapters"][0]["fullTitle"] == "Đoạn kết"
    with sqlite3.connect(project / "project.sqlite3") as db:
        assert tuple(tuple(row) for row in db.execute("SELECT * FROM segments ORDER BY id")) == before
        assert tuple(tuple(row) for row in db.execute("SELECT * FROM chapters ORDER BY id")) == chapters
    assert source.read_bytes() == raw


def test_audit_covers_packages_and_extracted_library_books_without_writes(tmp_path):
    from scripts import audit_chapter_titles as audit

    book = {"title": "Sách tự viết", "package": {}, "chapters": [
        {"id": 14, "index": 8, "title": "Chương 13", "fullTitle": "Chương 13", "script": "scripts/14.json"}]}
    script = {"segments": [{"text": "Đoạn kết"}]}
    package = tmp_path / "synthetic.abook"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("book.json", json.dumps(book))
        archive.writestr("scripts/14.json", json.dumps(script))
    (tmp_path / "scripts").mkdir()
    (tmp_path / "book.json").write_text(json.dumps(book), encoding="utf-8")
    (tmp_path / "scripts/14.json").write_text(json.dumps(script), encoding="utf-8")
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    expected = [{"chapterId": 14, "index": 8, "before": "Chương 13", "after": "Đoạn kết"}]
    assert audit.package(package)["changes"] == expected
    assert audit.installed(tmp_path / "book.json")["changes"] == expected
    assert {path: path.read_bytes() for path in before} == before
    edits = {"chapters": {"14": {"title": "Tên người nghe đặt"}}}
    (tmp_path / "edits.json").write_text(json.dumps(edits), encoding="utf-8")
    assert audit.installed(tmp_path / "book.json")["changes"] == []
    book["chapters"][0]["script"] = "../outside.json"
    (tmp_path / "book.json").write_text(json.dumps(book), encoding="utf-8")
    with pytest.raises(ValueError, match="unsafe package member"):
        audit.installed(tmp_path / "book.json")
