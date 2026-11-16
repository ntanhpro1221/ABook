import json
import zipfile

import pytest

from abook import book_metadata, importers
from abook.hako_import import metadata
from abook.webui import book_edits, bookfile, listen_view, textbook


def test_hako_full_paragraphs():
    first = "Một chiếc thuyền giấy trôi quanh hồ nhỏ. " * 40
    page = f'''<div class="info-item">Tác giả: Người Viết</div>
    <div class="info-item">Họa sĩ: Người Vẽ</div>
    <div class="info-item">Tên khác: Paper Lake; 湖</div>
    <div class="series-gernes"><a>Fantasy</a><a>Adventure</a></div>
    <div class="summary-content"><p>{first}</p><p>Đoạn <b>thứ hai</b>.</p></div>'''
    found = metadata(page, "https://docln.net/truyen/123-example")
    assert found["summary"] == first.strip() + "\n\nĐoạn thứ hai."
    assert len(found["summary"]) > 600
    assert found["illustrator"] == "Người Vẽ"
    assert found["altTitles"] == ["Paper Lake", "湖"]
    assert found["genres"] == ["Fantasy", "Adventure"]


def test_epub_metadata(tmp_path):
    path = tmp_path / "original.epub"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("META-INF/container.xml", '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="book.opf"/></rootfiles></container>')
        z.writestr("book.opf", '''<package xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/">
        <metadata><dc:title>Hồ giấy</dc:title><dc:creator>Người Viết</dc:creator>
        <dc:description>&lt;p&gt;Đầu tiên.&lt;/p&gt;&lt;p&gt;Sau đó.&lt;/p&gt;</dc:description>
        <dc:subject>Fantasy</dc:subject><dc:subject>Adventure</dc:subject>
        <dc:contributor id="artist">Người Vẽ</dc:contributor><meta refines="#artist" property="role">ill</meta></metadata>
        <manifest><item id="c" href="c.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="c"/></spine></package>''')
        z.writestr("c.xhtml", '<html xmlns="http://www.w3.org/1999/xhtml"><body><h1>Chương 1</h1><p>' + "Một chiếc thuyền giấy nằm cạnh cửa sổ. " * 10 + '</p></body></html>')
    book = importers.import_text(path)
    assert book.metadata() == {"author": "Người Viết", "illustrator": "Người Vẽ", "genres": ["Fantasy", "Adventure"], "summary": "Đầu tiên.\n\nSau đó."}
    assert textbook.book_json(book, textbook.texts_of(book), None)["summary"] == book.summary


def test_txt_and_folder(tmp_path):
    path = tmp_path / "book.txt"
    story = "Hồ giấy\nTác giả: Người Viết\nHọa sĩ: Người Vẽ\nTên khác: Paper Lake; 湖\nThể loại: Fantasy, Adventure\nTóm tắt: Một chiếc thuyền.\n\nChương 1\n" + "Câu chuyện tự viết. " * 20
    path.write_text(story, encoding="utf-8")
    book = importers.import_text(path)
    assert book.illustrator == "Người Vẽ"
    assert book.summary == "Một chiếc thuyền."
    assert book.chapters[0].text == story.strip()
    details = {"author": "Người Khác", "summary": "Đoạn một.\n\nĐoạn hai.", "genres": ["Adventure"]}
    (tmp_path / "metadata.json").write_text(json.dumps(details), encoding="utf-8")
    assert importers.import_text(tmp_path).metadata() == details


def test_metadata_edits_preserve_audio_and_cast(tmp_path):
    book = {"format": "abook-book/1", "title": "Hồ giấy", "version": "original", "audioVersion": "audio-fixed", "chapters": [], "volumes": [{"id": 1, "number": 1, "title": "Quyển 1", "chapters": []}]}
    (tmp_path / "book.json").write_text(json.dumps(book), encoding="utf-8")
    (tmp_path / "audio.mp3").write_bytes(b"original-audio")
    (tmp_path / "cast.json").write_bytes(b'{"characters":[]}')
    details = {"author": "Người Viết", "summary": "Đoạn một.\n\nĐoạn hai.", "altTitles": ["Paper Lake"]}
    book_edits.set_metadata(tmp_path, details)
    edits = book_edits.load(tmp_path)
    assert book_edits.count(edits) == 3
    assert book_edits.validate(json.loads(book_edits.dump(edits))) == edits
    updated = book_edits.apply_manifest(book, edits)
    assert updated["summary"] == details["summary"]
    assert updated["audioVersion"] == "audio-fixed" and updated["version"] == "original"
    assert listen_view.metadata_version(updated) != listen_view.metadata_version(book)
    assert (tmp_path / "audio.mp3").read_bytes() == b"original-audio"
    assert (tmp_path / "cast.json").read_bytes() == b'{"characters":[]}'


@pytest.mark.parametrize("details", [{}, {"summary": "A\n\nB", "genres": ["Story"]}])
def test_optional_manifest(details):
    bookfile.check_shape({"title": "Hồ giấy", **details})


def test_export_writes_descriptive_edits_into_book_json(tmp_path):
    book = importers.ImportedBook("Hồ giấy", chapters=[importers.Chapter("Chương một", "Một chiếc thuyền giấy nằm cạnh cửa sổ. " * 10)])
    texts = textbook.texts_of(book)
    base = textbook.book_json(book, texts, None)
    edits = {**book_edits.empty(), "author": "Người Viết", "summary": "Đầu tiên.\n\nSau đó."}
    out = bookfile.seal(base, {**texts, "edits.json": book_edits.dump(edits)}, tmp_path / "edited.abook", producer="test", version=6, edits=edits)
    with zipfile.ZipFile(out) as archive:
        raw = json.loads(archive.read("book.json"))
        assert raw["author"] == "Người Viết" and raw["summary"] == edits["summary"]
        assert archive.read("texts/1.txt") == texts["texts/1.txt"]
        assert raw["version"] == base["version"]


@pytest.mark.parametrize("details", [{"genres": "Story"}, {"altTitles": [1]}, {"source": {"url": 1, "site": "Hako"}}])
def test_invalid_shape(details):
    with pytest.raises(bookfile.BookFileError):
        bookfile.check_shape(details)


def test_cleared_lists_do_not_create_empty_chips():
    assert book_metadata.validate({"genres": ["", " ", "Fantasy"], "altTitles": [""]}) == {"genres": ["Fantasy"], "altTitles": []}


def test_project_metadata_has_a_separate_revision_and_travels_in_project_file(tmp_path):
    from abook.webui import sync, projectfile
    from abook.webui.listening import Listening
    from tests.test_project_file import _project
    project = _project(tmp_path)
    listening = Listening(tmp_path / "listen.json")
    before = sync.manifest(project, "sample", listening)
    audio = project / "output/chapters/00001_645.mp3"
    audio_before = audio.read_bytes()
    details = {"author": "Người Viết", "illustrator": "Người Vẽ", "summary": "Đoạn đầu.\n\nĐoạn cuối.", "genres": ["Fantasy"]}
    book_metadata.save(project, details)
    after = sync.manifest(project, "sample", listening)
    assert before["version"] == after["version"]
    assert before["audioVersion"] == after["audioVersion"]
    assert before["metaVersion"] != after["metaVersion"]
    assert audio.read_bytes() == audio_before
    assert all(after[key] == value for key, value in details.items())
    packed = projectfile.pack(project, tmp_path / "sample.abookproj")
    with zipfile.ZipFile(packed) as archive:
        assert json.loads(archive.read("project/book_metadata.json")) == details
        assert all(json.loads(archive.read("book.json"))[key] == value for key, value in details.items())
