"""Sách CHỈ-CÓ-CHỮ (docs/LISTEN_ANYTHING.md mục 1, giai đoạn 0): EPUB / DOCX / PDF / thư mục TXT vào thư viện, đọc được, chưa có audio.

Định dạng phiên bản 5 (`texts/<n>.txt`, `chapters[i].state` "text"), nhận ra một cuốn bằng mã băm chữ khi không có audio,
nhập qua máy chủ (xem trước -> thêm), đọc chữ chương, lớp sửa + "Lưu thành .abook", và "Làm sách nói từ cuốn này".
Bộ ví dụ dùng chung với Kotlin: tests/text_book_fixtures.py.
"""
from __future__ import annotations

import io
import json
import shutil
import sqlite3
import zipfile
from pathlib import Path
from typing import Any

import pytest

from abook import importers
from abook.webui import book_edits, bookfile, packages, projectfile, store, textbook, workshop
from abook.webui.bookfile import BookFile, BookFileError
from abook.webui.fingerprints import Fingerprints, identity_prints, is_text_identity
from abook.webui.library import book_id
from abook.webui.server import Server
from tests import import_fixtures, text_book_fixtures
from tests.test_project_file import _app, _project
from tests.test_webui_listen_and_sync import _request

TOKEN = {"X-Ebook-Token": "t"}
IMPORTS = import_fixtures.FIXTURES
FIXTURES = text_book_fixtures.FIXTURES


def _epub_book() -> importers.ImportedBook:
    return importers.import_text(IMPORTS / "epub3.epub")


def _book_file(tmp_path: Path, book: importers.ImportedBook | None = None, name: str = "chu.abook") -> Path:
    return textbook.build(book or _epub_book(), tmp_path / name)


def _png(size: tuple[int, int] = (240, 320)) -> bytes:
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", size, (200, 40, 40)).save(out, "PNG")
    return out.getvalue()


def _rewrite(path: Path, target: Path, change) -> Path:
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(target, "w") as sink:
        for info in source.infolist():
            data = change(info.filename, source.read(info.filename))
            if data is not None:
                sink.writestr(info, data)
    return target


# ---- định dạng -----------------------------------------------------------------------------------------------------------


def test_the_committed_text_book_fixtures_are_what_python_writes_today() -> None:
    assert (FIXTURES / "cases.json").read_bytes() == text_book_fixtures.cases_bytes(), \
        "cases.json lỗi thời - chạy lại: python -m tests.text_book_fixtures"


def test_a_text_book_is_a_book_file_with_no_audio_at_all(tmp_path: Path) -> None:
    path = _book_file(tmp_path)
    with zipfile.ZipFile(path) as archive:
        assert archive.infolist()[0].filename == "mimetype" and archive.infolist()[0].compress_type == zipfile.ZIP_STORED
    with BookFile(path) as opened:
        opened.verify()
        assert opened.book["package"]["version"] == 5 == bookfile.FORMAT_VERSION
        assert opened.content == ["texts/1.txt", "texts/2.txt", "texts/3.txt"]
        chapters = opened.book["chapters"]
        assert [(chapter["state"], chapter["text"], chapter["available"], chapter["duration"]) for chapter in chapters] == [
            ("text", f"texts/{number}.txt", False, 0) for number in (1, 2, 3)]
        assert all("file" not in chapter and "script" not in chapter for chapter in chapters)
        assert (opened.book["title"], opened.book["author"], opened.book["chaptersAvailable"], opened.book["complete"]) == (
            "Chuyến phà cuối ngày", "Lê Thử Nghiệm", 0, False)
        assert opened.read("texts/1.txt").decode("utf-8").startswith("Chương 1: Bến phà lúc bình minh\n\nSương còn phủ kín")
        assert json.loads(opened.read("manifest.json"))["readingOrder"] == [], "không audio thì Readium không có gì để phát"


def test_the_text_of_a_chapter_is_the_file_studio_would_read(tmp_path: Path) -> None:
    """Tên chương + dòng trống + chữ (EPUB / DOCX / PDF); TXT nguyên văn vì tên chương nằm sẵn trong file."""
    epub = _epub_book()
    assert epub.chapter_source(epub.chapters[1]) == f"{epub.chapters[1].title}\n\n{epub.chapters[1].text}\n"
    folder = importers.import_text(IMPORTS / "txt")
    assert folder.chapter_source(folder.chapters[0]) == folder.chapters[0].text + "\n"
    extracted, _ = importers.extract(IMPORTS / "epub3.epub", tmp_path / "studio")
    written = sorted(extracted.glob("*.txt"))
    assert [path.read_text(encoding="utf-8") for path in written] == [epub.chapter_source(chapter) for chapter in epub.chapters], \
        "thư mục chương của Studio và chữ của sách chỉ-chữ là cùng một hàm"


def test_chapter_texts_exist_only_from_version_5(tmp_path: Path) -> None:
    path = _book_file(tmp_path)

    def older(name: str, data: bytes) -> bytes:
        if name != "book.json":
            return data
        book = json.loads(data)
        book["package"]["version"] = 4
        return json.dumps(book).encode()

    with pytest.raises(BookFileError, match="lạ"):
        BookFile(_rewrite(path, tmp_path / "cu.abook", older))


def test_a_chapter_whose_text_is_missing_is_refused(tmp_path: Path) -> None:
    path = _book_file(tmp_path)

    def dangling(name: str, data: bytes) -> bytes:
        if name != "book.json":
            return data
        book = json.loads(data)
        book["chapters"][0]["text"] = "texts/99.txt"
        return json.dumps(book).encode()

    with pytest.raises(BookFileError, match="thiếu chữ"):
        BookFile(_rewrite(path, tmp_path / "hong.abook", dangling))


@pytest.mark.parametrize("name", ["texts/../x.txt", "texts/a.txt", "texts/1.mp3", "texts/1/2.txt", "texts/1234567890.txt"])
def test_text_entries_outside_the_layout_are_refused(tmp_path: Path, name: str) -> None:
    path = _book_file(tmp_path)
    target = tmp_path / "la.abook"
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(target, "w") as sink:
        for info in source.infolist():
            sink.writestr(info, source.read(info.filename))
        sink.writestr(name, b"x")
    with pytest.raises(BookFileError, match="lạ"):
        BookFile(target)


def test_a_book_with_nothing_in_it_is_still_not_packed(tmp_path: Path) -> None:
    with pytest.raises(BookFileError, match="chưa có chương nào"):
        bookfile.seal({"title": "Rỗng", "chapters": []}, {}, tmp_path / "rong.abook", producer="t", version=5)
    assert not list(tmp_path.glob("*.abook*")), "không để lại file dở"


def test_a_cover_is_stored_as_a_jpeg_with_its_colour(tmp_path: Path) -> None:
    book = _epub_book()
    book.cover_bytes, book.cover_type = _png(), "image/png"
    with BookFile(_book_file(tmp_path, book)) as opened:
        opened.verify()
        assert "cover.jpg" in opened.content and opened.read("cover.jpg")[:3] == b"\xff\xd8\xff"
        cover = opened.book["cover"]
        assert (cover["file"], cover["width"], cover["height"]) == ("cover.jpg", 240, 320) and cover["color"].startswith("#")
    book.cover_bytes = b"not an image"
    with BookFile(_book_file(tmp_path, book, "hong.abook")) as opened:
        assert "cover.jpg" not in opened.content and opened.book["cover"] is None, "bìa hỏng không chặn việc nhập sách"


# ---- nhận ra một cuốn khi không có audio -------------------------------------------------------------------------------


def test_a_book_without_audio_is_known_by_the_hashes_of_its_texts(tmp_path: Path) -> None:
    with BookFile(_book_file(tmp_path)) as first, BookFile(_book_file(tmp_path, name="lai.abook")) as again:
        assert first.chapter_prints.keys() == {"texts/1.txt", "texts/2.txt", "texts/3.txt"}
        assert first.chapter_prints == again.chapter_prints and first.content_key == again.content_key
        assert is_text_identity(first.chapter_prints)
    other = _epub_book()
    other.chapters[0].text += "\n\nMột đoạn nữa."
    with BookFile(_book_file(tmp_path, other, "khac.abook")) as different, BookFile(_book_file(tmp_path)) as same:
        assert different.content_key != same.content_key, "đổi một chữ là cuốn khác - không cùng một thư mục"


def test_audio_still_wins_as_the_identity_of_a_book_that_has_it() -> None:
    files = {"chapters/x.mp3": {"size": 1, "sha256": "a"}, "texts/1.txt": {"size": 2, "sha256": "b"}, "cast.json": {"size": 3, "sha256": "c"}}
    assert set(identity_prints(files)) == {"chapters/x.mp3"}
    assert set(identity_prints({"texts/1.txt": files["texts/1.txt"], "cast.json": files["cast.json"]})) == {"texts/1.txt"}
    assert identity_prints({"cast.json": files["cast.json"]}) == {} and not is_text_identity({})


def test_the_same_file_added_twice_is_one_book_and_a_text_never_matches_a_project(tmp_path: Path) -> None:
    library = tmp_path / "thu_vien"
    fingerprints = Fingerprints(tmp_path / "fp.json")
    project = _project(tmp_path / "du_an")
    first, how, _ = textbook.add_to_library(IMPORTS / "epub3.epub", None, library, [project], fingerprints)
    again, how_again, _ = textbook.add_to_library(IMPORTS / "epub3.epub", None, library, [project], fingerprints)
    assert (how, how_again, again) == ("new", "existing", first)
    assert [path.name for path in (library / packages.IMPORTED_FOLDER).iterdir()] == [first.name], "một thư mục, không để lại bản tạm"
    assert not fingerprints.shares_a_chapter(project, packages.chapter_prints(packages.manifest(first)))


def test_two_books_that_share_one_chapter_text_stay_two_books(tmp_path: Path) -> None:
    """Hai cuốn có thể chung một chương ngắn ("Lời nói đầu"): chữ phải trùng CẢ BỘ mới là một cuốn."""
    library = tmp_path / "thu_vien"
    fingerprints = Fingerprints(tmp_path / "fp.json")
    first = _epub_book()
    second = _epub_book()
    second.title = "Cuốn khác"
    second.chapters = second.chapters[:1] + [importers.Chapter("Chương mới", "Chữ hoàn toàn khác.")]
    folder_a, _, _ = textbook.add_to_library(_write_txt(tmp_path / "a", first), None, library, [], fingerprints)
    folder_b, how, _ = textbook.add_to_library(_write_txt(tmp_path / "b", second), None, library, [], fingerprints)
    assert how == "new" and folder_a != folder_b


def _write_txt(folder: Path, book: importers.ImportedBook) -> Path:
    folder.mkdir(parents=True)
    for number, chapter in enumerate(book.chapters, start=1):
        (folder / f"{number:03d}.txt").write_text(book.chapter_source(chapter), encoding="utf-8", newline="\n")
    return folder


# ---- thư viện và trang đọc -----------------------------------------------------------------------------------------------


def _studio_with_text_book(tmp_path: Path):
    studio = _app(tmp_path / "studio", tmp_path / "thu_vien")
    added = studio.add_text_book(str(IMPORTS / "epub3.epub"))
    return studio, added


def test_the_library_shows_a_text_book_as_text_only_with_its_chapters(tmp_path: Path) -> None:
    studio, added = _studio_with_text_book(tmp_path)
    assert added["how"] == "new" and added["chapters"] == 3
    library = studio.listen_library()
    shown = next(book for book in library if book["id"] == added["id"])
    assert (shown["stage"], shown["chaptersTotal"], shown["chaptersAvailable"], shown["imported"]) == ("text", 3, 0, True)
    book = studio.listen_book(added["id"])
    assert [(chapter["state"], chapter["available"]) for chapter in book["chapters"]] == [("text", False)] * 3
    assert book["studioProject"] is None and book["capabilities"]["workshop"] is False
    assert book["progress"]["fraction"] == 0 and book["duration"] == 0


def test_a_text_book_serves_the_text_of_each_chapter_and_nothing_else(tmp_path: Path) -> None:
    studio, added = _studio_with_text_book(tmp_path)
    server = Server(studio, port=0).start()
    try:
        status, data, _ = _request(server.port, "GET", f"/api/listen/books/{added['id']}/chapters/2/text", headers=TOKEN)
        missing = _request(server.port, "GET", f"/api/listen/books/{added['id']}/chapters/9/text", headers=TOKEN)
        script = _request(server.port, "GET", f"/api/books/{added['id']}/chapters/2/script", headers=TOKEN)
        cast = _request(server.port, "GET", f"/api/books/{added['id']}/cast", headers=TOKEN)
    finally:
        server.stop()
    text = json.loads(data)["text"]
    assert status == 200 and text.startswith("Chương 2: Người khách lạ\n\nDịch: Nhóm Lục Bình") and "Mát-xcơ-va" in text
    assert missing[0] == 404 and script[0] == 404, "không kịch bản giả - màn đọc dựng đoạn từ chữ (textScript.ts)"
    assert cast[0] == 200 and json.loads(cast[1])["characters"] == []


def test_a_listener_edits_a_text_book_and_saves_it_as_a_book_file(tmp_path: Path) -> None:
    studio, added = _studio_with_text_book(tmp_path)
    folder = studio._listenable(added["id"])
    book_edits.set_title(folder, "Tên tôi đặt")
    book_edits.set_chapter_title(folder, 2, "Khách lạ", None)
    server = Server(studio, port=0).start()
    try:
        status, data, _ = _request(server.port, "POST", f"/api/books/{added['id']}/save", headers=TOKEN,
                                   body={"target": str(tmp_path / "xuat"), "as": "abook"})
        project_status, project_data, _ = _request(server.port, "POST", f"/api/books/{added['id']}/save", headers=TOKEN,
                                                   body={"target": str(tmp_path / "xuat"), "as": "abookproj"})
    finally:
        server.stop()
    saved = json.loads(data)
    assert status == 200 and saved["edits"] == 2
    with BookFile(Path(saved["file"])) as opened:
        opened.verify()
        assert opened.book["package"]["version"] == 5 and "edits.json" in opened.content
        assert opened.edits["title"] == "Tên tôi đặt" and sorted(name for name in opened.content if name.startswith("texts/")) == [
            "texts/1.txt", "texts/2.txt", "texts/3.txt"]
        assert opened.book["title"] == "Chuyến phà cuối ngày", "lớp sách không bị sửa tại chỗ"
        assert json.loads(opened.read("manifest.json"))["metadata"]["title"] == "Tên tôi đặt"
    assert project_status == 200
    with projectfile.ProjectFile(Path(json.loads(project_data)["file"])) as project:
        project.verify()
        assert project.workshop == projectfile.PENDING and project.listenable and project.chapter_prints.keys() == {
            "texts/1.txt", "texts/2.txt", "texts/3.txt"}


def test_a_saved_text_book_opens_again_as_the_same_book_with_its_edits(tmp_path: Path) -> None:
    studio, added = _studio_with_text_book(tmp_path)
    folder = studio._listenable(added["id"])
    book_edits.set_title(folder, "Tên tôi đặt")
    out = bookfile.repack(folder, tmp_path / "luu.abook")
    other = _app(tmp_path / "may_khac", tmp_path / "thu_vien_khac")
    opened = other.open_book_file(str(out))
    assert opened["how"] == "new"
    assert other.listen_book(opened["id"])["title"] == "Tên tôi đặt"
    again = other.open_book_file(str(out))
    assert again["id"] == opened["id"] and again["how"] == "existing"


# ---- nhập qua máy chủ ------------------------------------------------------------------------------------------------------


def test_the_import_flow_previews_the_chapters_then_adds_the_book(tmp_path: Path) -> None:
    studio = _app(tmp_path / "studio", tmp_path / "thu_vien")
    server = Server(studio, port=0).start()
    try:
        status, data, _ = _request(server.port, "POST", "/api/listen/import/preview", headers=TOKEN,
                                   body={"path": f'"{IMPORTS / "epub3.epub"}"'})
        empty_library = _request(server.port, "GET", "/api/listen/library", headers=TOKEN)
        added = _request(server.port, "POST", "/api/listen/import", headers=TOKEN,
                         body={"path": str(IMPORTS / "epub3.epub"), "title": "  Tên   đặt lại "})
    finally:
        server.stop()
    preview = json.loads(data)
    assert status == 200 and preview["title"] == "Chuyến phà cuối ngày" and preview["totals"] == {
        "chapters": 3, "words": sum(row["words"] for row in preview["chapters"] if row["included"])}
    assert [row["title"] for row in preview["chapters"]][1] == "Chương 1: Bến phà lúc bình minh", "hàng 1 là trang đề tựa rất ngắn, chưa tích"
    assert preview["chapters"][1]["firstLine"] == "Chương 1: Bến phà lúc bình minh" and preview["chapters"][1]["words"] > 20
    assert any("ghi công" in note and "không tự bỏ" in note for note in preview["notes"]), "gợi ý hiện ra, không tự áp"
    assert json.loads(empty_library[1]) == [], "xem trước chưa ghi gì vào thư viện"
    result = json.loads(added[1])
    assert added[0] == 200 and result["how"] == "new" and result["chapters"] == 3
    assert studio.listen_book(result["id"])["title"] == "Tên đặt lại"
    text = studio._listenable(result["id"]) / "texts" / "2.txt"
    assert "Dịch: Nhóm Lục Bình" in text.read_text(encoding="utf-8"), "dòng ghi công vẫn nằm trong chữ - không bao giờ tự bỏ"


def test_a_whole_story_txt_is_split_into_chapters_only_when_the_listener_ticks_it(tmp_path: Path) -> None:
    studio = _app(tmp_path / "studio", tmp_path / "thu_vien")
    server = Server(studio, port=0).start()
    whole = str(IMPORTS / "whole.txt")
    try:
        plain = json.loads(_request(server.port, "POST", "/api/listen/import/preview", headers=TOKEN, body={"path": whole})[1])
        split = json.loads(_request(server.port, "POST", "/api/listen/import/preview", headers=TOKEN,
                                    body={"path": whole, "splitChapters": True})[1])
        added = json.loads(_request(server.port, "POST", "/api/listen/import", headers=TOKEN,
                                    body={"path": whole, "splitChapters": True})[1])
    finally:
        server.stop()
    assert plain["totals"]["chapters"] == 1 and plain["splitOffer"] == 4, "mặc định một chương, và cho biết tách sẽ ra bao nhiêu"
    assert split["totals"]["chapters"] == 4 and split["splitOffer"] == 4
    assert [row["title"] for row in split["chapters"]][:2] == ["Mở đầu", "Chương 1: Bến phà lúc bình minh"]
    assert added["chapters"] == 4 and len(studio.listen_book(added["id"])["chapters"]) == 4
    assert "splitOffer" not in studio.preview_text_book(str(IMPORTS / "epub3.epub")), "sách không có gì để tách thì không có gợi ý"


def test_the_preview_lists_very_short_items_unticked_and_the_totals_count_only_the_ticked(tmp_path: Path) -> None:
    studio = _app(tmp_path / "studio", tmp_path / "thu_vien")
    preview = studio.preview_text_book(str(IMPORTS / "epub3.epub"))
    assert [(row["index"], row["included"], row.get("short")) for row in preview["chapters"]] == [
        (1, False, True), (2, True, None), (3, True, None), (4, True, None)], "bìa ở đúng chỗ của nó, chưa tích"
    assert preview["chapters"][0]["title"] == "Chuyến phà cuối ngày"
    assert preview["totals"] == {"chapters": 3, "words": sum(row["words"] for row in preview["chapters"][1:])}
    assert "1 mục rất ngắn chưa chọn - tích nếu muốn giữ." in preview["notes"]
    assert preview["suggestions"] == [{"chapter": 3, "line": "Dịch: Nhóm Lục Bình"}], "gợi ý đánh số theo danh sách xem trước"
    assert studio.preview_text_book(str(IMPORTS / "epub3.epub"))["existing"] is None


def test_a_listener_unticks_chapters_renames_one_and_brings_back_a_short_item(tmp_path: Path) -> None:
    studio = _app(tmp_path / "studio", tmp_path / "thu_vien")
    source = str(IMPORTS / "epub3.epub")
    added = studio.add_text_book(source, chapters=[{"index": 1, "title": "Trang đề tựa"}, {"index": 3, "title": "  Người   khách  "},
                                                   {"index": 4}])
    assert added["how"] == "new" and added["chapters"] == 3
    book = studio.listen_book(added["id"])
    assert [chapter["title"] for chapter in book["chapters"]] == ["Trang đề tựa", "Người khách", "Chương 3"], "đúng thứ tự trong file"
    folder = studio._listenable(added["id"])
    texts = [(folder / "texts" / f"{number}.txt").read_text(encoding="utf-8") for number in (1, 2, 3)]
    assert texts[0].strip() == "Chuyến phà cuối ngày", "mục ngắn vào sách với chữ của nó"
    assert texts[1].startswith("Chương 2: Người khách lạ\n\nDịch: Nhóm Lục Bình"), "đổi tên chỉ đổi tên - chữ của chương giữ nguyên, kể cả dòng tên đầu chương"
    assert texts[2].startswith("Chương 3\n\nCơn mưa cuối mùa")
    assert studio.add_text_book(source)["how"] == "new", "bộ chương mặc định khác bộ này: là một cuốn khác"


def test_a_txt_keeps_its_own_heading_line_when_the_listener_renames_the_chapter(tmp_path: Path) -> None:
    studio = _app(tmp_path / "studio", tmp_path / "thu_vien")
    whole = str(IMPORTS / "whole.txt")
    added = studio.add_text_book(whole, split_chapters=True, chapters=[{"index": 1, "title": "Lời mở"}, {"index": 3, "title": "Khách lạ"}])
    book = studio.listen_book(added["id"])
    assert [chapter["title"] for chapter in book["chapters"]] == ["Lời mở", "Khách lạ"]
    second = (studio._listenable(added["id"]) / "texts" / "2.txt").read_text(encoding="utf-8")
    assert second.startswith("Chương 2: Người khách lạ\nDịch: Nhóm Lục Bình"), "dòng 'Chương 2' vẫn nằm trong chữ"


def test_adding_with_every_chapter_unticked_or_a_wrong_list_is_refused_and_adds_nothing(tmp_path: Path) -> None:
    studio = _app(tmp_path / "studio", tmp_path / "thu_vien")
    for bad in ([], [{"index": 9}], [{"index": 2}, {"index": 2}], [{"index": "2"}], [{"title": "x"}], "2", [{"index": 2, "title": 5}]):
        with pytest.raises(Exception) as error:
            studio.add_text_book(str(IMPORTS / "epub3.epub"), chapters=bad)
        assert getattr(error.value, "status", None) == 400, bad
    assert studio.listen_library() == []


def test_the_import_route_takes_the_chapter_choice_as_json(tmp_path: Path) -> None:
    studio = _app(tmp_path / "studio", tmp_path / "thu_vien")
    server = Server(studio, port=0).start()
    source = str(IMPORTS / "epub3.epub")
    try:
        none = _request(server.port, "POST", "/api/listen/import", headers=TOKEN, body={"path": source, "chapters": []})
        added = _request(server.port, "POST", "/api/listen/import", headers=TOKEN,
                         body={"path": source, "chapters": [{"index": 3, "title": "Khách lạ"}, {"index": 2}]})
    finally:
        server.stop()
    assert none[0] == 400 and "ít nhất một chương" in json.loads(none[1])["error"]
    result = json.loads(added[1])
    assert added[0] == 200 and result["chapters"] == 2
    assert [chapter["title"] for chapter in studio.listen_book(result["id"])["chapters"]] == ["Chương 1: Bến phà lúc bình minh", "Khách lạ"]


def test_the_preview_asks_about_an_existing_book_by_the_default_chapters_only(tmp_path: Path) -> None:
    studio = _app(tmp_path / "studio", tmp_path / "thu_vien")
    source = str(IMPORTS / "epub3.epub")
    first = studio.add_text_book(source, chapters=[{"index": 2}, {"index": 3}, {"index": 4, "title": "Tên khác"}])
    assert studio.preview_text_book(source)["existing"]["id"] == first["id"], "bộ chương mặc định = bộ đã thêm (tên khác không tính)"
    assert studio.add_text_book(source, chapters=[{"index": 2}, {"index": 3}, {"index": 4}])["how"] == "existing", "đổi tên không làm thành cuốn khác"
    other = studio.add_text_book(source, chapters=[{"index": 2}, {"index": 3}])
    assert other["how"] == "new" and other["id"] != first["id"], "bỏ một chương = bộ chữ khác = cuốn khác"
    copy = studio.add_text_book(source, "Bản riêng", separate=True, chapters=[{"index": 2}, {"index": 3}, {"index": 4}])
    assert copy["how"] == "new" and copy["id"] not in (first["id"], other["id"])


def test_adding_the_same_book_again_says_it_is_already_there(tmp_path: Path) -> None:
    studio = _app(tmp_path / "studio", tmp_path / "thu_vien")
    first = studio.add_text_book(str(IMPORTS / "epub3.epub"))
    again = studio.add_text_book(str(IMPORTS / "epub3.epub"), "Tên khác")
    assert (first["how"], again["how"], again["id"]) == ("new", "existing", first["id"])


def test_the_preview_already_knows_the_book_is_there_and_a_separate_copy_can_still_be_added(tmp_path: Path) -> None:
    studio = _app(tmp_path / "studio", tmp_path / "thu_vien")
    assert studio.preview_text_book(str(IMPORTS / "epub3.epub"))["existing"] is None
    first = studio.add_text_book(str(IMPORTS / "epub3.epub"))
    book_edits.set_title(studio._listenable(first["id"]), "Tên tôi đặt")
    preview = studio.preview_text_book(str(IMPORTS / "epub3.epub"))
    assert preview["existing"] == {"id": first["id"], "title": "Tên tôi đặt"}, "hỏi ngay ở bước xem trước, với tên đang hiện"
    copy = studio.add_text_book(str(IMPORTS / "epub3.epub"), "Bản thứ hai", separate=True)
    assert copy["how"] == "new" and copy["id"] != first["id"]
    assert studio.listen_book(copy["id"])["title"] == "Bản thứ hai", "tên người dùng sửa không bị bỏ âm thầm"
    assert studio.add_text_book(str(IMPORTS / "epub3.epub"))["how"] == "existing"


def test_the_book_page_shows_the_author_of_the_file(tmp_path: Path) -> None:
    studio, added = _studio_with_text_book(tmp_path)
    assert studio.listen_book(added["id"])["author"] == "Lê Thử Nghiệm"
    assert next(book for book in studio.listen_library() if book["id"] == added["id"])["author"] == "Lê Thử Nghiệm"


def test_a_txt_folder_keeps_the_chapter_names_the_preview_showed(tmp_path: Path) -> None:
    studio = _app(tmp_path / "studio", tmp_path / "thu_vien")
    preview = studio.preview_text_book(str(IMPORTS / "txt"))
    added = studio.add_text_book(str(IMPORTS / "txt"))
    shown = [chapter["fullTitle"] for chapter in studio.listen_book(added["id"])["chapters"]]
    assert shown == [row["title"] for row in preview["chapters"]] and "Chương hai" in shown, "dòng tiêu đề trong file là tên chương"


def test_a_credit_line_suggestion_is_skipped_only_when_the_listener_accepts_it(tmp_path: Path) -> None:
    studio, added = _studio_with_text_book(tmp_path)
    preview = studio.preview_text_book(str(IMPORTS / "epub3.epub"))
    assert preview["suggestions"] == [{"chapter": 3, "line": "Dịch: Nhóm Lục Bình"}], \
        "đánh số theo hàng của bước xem trước (hàng 1 là bìa chưa tích); trong sách mặc định nó là chương 2"
    folder = studio._listenable(added["id"])
    server = Server(studio, port=0).start()
    try:
        before = json.loads(_request(server.port, "GET", f"/api/books/{added['id']}/suggestions", headers=TOKEN)[1])
        status, data, _ = _request(server.port, "PUT", f"/api/books/{added['id']}/skip", headers=TOKEN,
                                   body={"line": "Dịch: Nhóm Lục Bình", "chapters": [2], "skip": True})
        after = json.loads(_request(server.port, "GET", f"/api/books/{added['id']}/suggestions", headers=TOKEN)[1])
        missing = _request(server.port, "PUT", f"/api/books/{added['id']}/skip", headers=TOKEN,
                           body={"line": "Dịch: A", "chapters": [9], "skip": True})
    finally:
        server.stop()
    assert before["suggestions"] == [{"chapter": 2, "title": "Chương 2: Người khách lạ", "line": "Dịch: Nhóm Lục Bình", "skipped": False}]
    assert status == 200 and json.loads(data) == {"skip": {"2": ["Dịch: Nhóm Lục Bình"]}} and after["suggestions"][0]["skipped"]
    assert missing[0] == 400
    chapters = studio.listen_book(added["id"])["chapters"]
    assert chapters[1]["skip"] == ["Dịch: Nhóm Lục Bình"] and "skip" not in chapters[0], "màn đọc nhận dòng cần bỏ (textScript.ts)"
    assert "Dịch: Nhóm Lục Bình" in (folder / "texts" / "2.txt").read_text(encoding="utf-8"), "chữ của sách không đổi"
    assert studio.listen_book(added["id"])["edits"] == 1
    book_edits.set_skip_line(folder, [2], "Dịch: Nhóm Lục Bình", False)
    assert "skip" not in studio.listen_book(added["id"])["chapters"][1] and book_edits.load(folder) == book_edits.empty()


def test_a_text_folder_and_a_docx_come_in_like_an_epub(tmp_path: Path) -> None:
    studio = _app(tmp_path / "studio", tmp_path / "thu_vien")
    folder = studio.add_text_book(str(IMPORTS / "txt"))
    docx = studio.add_text_book(str(IMPORTS / "headings.docx"))
    assert folder["id"] != docx["id"]
    assert {book["stage"] for book in studio.listen_library()} == {"text"}


def test_unreadable_input_is_refused_in_words_the_user_can_act_on(tmp_path: Path) -> None:
    from abook.webui.server import ApiError

    studio = _app(tmp_path / "studio", tmp_path / "thu_vien")
    with pytest.raises(ApiError, match="ảnh chụp"):
        studio.preview_text_book(str(IMPORTS / "scan.pdf"))
    with pytest.raises(ApiError, match="Không thấy file"):
        studio.add_text_book(str(tmp_path / "khong_co.epub"))
    (tmp_path / "rac.docx").write_bytes(b"not a docx")
    with pytest.raises(ApiError, match="DOCX"):
        studio.add_text_book(str(tmp_path / "rac.docx"))
    assert studio.listen_library() == []


def test_a_read_only_app_does_not_add_books(tmp_path: Path) -> None:
    from abook.webui.server import ApiError

    studio = _app(tmp_path / "studio", tmp_path / "thu_vien")
    studio.read_only = True
    with pytest.raises(ApiError, match="chỉ xem"):
        studio.add_text_book(str(IMPORTS / "epub3.epub"))


def test_the_devices_that_only_listen_never_import_by_path() -> None:
    from abook.webui import remote_studio

    allowed = {(method, pattern.pattern) for method, pattern in remote_studio.ALLOWED}
    assert not any("import" in pattern for _, pattern in allowed), "đường dẫn nằm trên máy này - thiết bị ở xa không có"
    assert ("GET", r"/api/listen/books/[A-Za-z0-9_-]+/chapters/\d+/text") in allowed, "nhưng đọc chữ chương thì có"


# ---- làm sách nói từ cuốn chỉ-chữ ---------------------------------------------------------------------------------------------


def test_a_text_book_becomes_a_studio_project_from_its_own_texts(tmp_path: Path) -> None:
    studio, added = _studio_with_text_book(tmp_path)
    server = Server(studio, port=0).start()
    try:
        status, data, _ = _request(server.port, "POST", f"/api/books/{added['id']}/workshop", headers=TOKEN, body={})
        again = _request(server.port, "POST", f"/api/books/{added['id']}/workshop", headers=TOKEN, body={})
    finally:
        server.stop()
    built = json.loads(data)
    assert status == 201 and built["chapters"] == 3 and built["chaptersWithoutText"] == 0 and built["voices"] == 0
    assert again[0] == 409 and "đã dựng" in json.loads(again[1])["error"]
    project = studio.library.resolve(built["id"])
    assert project is not None and store.is_project(project)
    source = sorted((studio.library.root / workshop.SOURCE_FOLDER).rglob("*.txt"))
    assert [path.name for path in source] == ["00001.txt", "00002.txt", "00003.txt"]
    epub = _epub_book()
    assert [path.read_text(encoding="utf-8") for path in source] == [epub.chapter_source(chapter) for chapter in epub.chapters], \
        "Studio đọc đúng chữ như khi đưa thẳng file EPUB vào trình tạo sách"
    assert studio.listen_book(added["id"])["studioProject"] == built["id"], "giao diện mời mở dự án thay vì làm thêm cái nữa"
    assert store.summarize(project, running=False)["title"] == "Chuyến phà cuối ngày"


def test_making_audio_from_a_text_book_needs_the_studio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui.server import ApiError

    studio, added = _studio_with_text_book(tmp_path)
    monkeypatch.setattr(studio, "capabilities", lambda path=None: {"toolchain": False, "workshop": False, "link": False})
    with pytest.raises(ApiError, match="Cần cài Studio"):
        studio.build_workshop(added["id"])


# ---- một dự án chưa có audio nào ---------------------------------------------------------------------------------------------


def _no_audio_project(tmp_path: Path) -> Path:
    project = _project(tmp_path)
    with sqlite3.connect(project / store.DB_NAME) as db:
        db.execute("UPDATE chapters SET status = 'pending', output_mp3 = NULL")
    shutil.rmtree(project / "output" / "chapters")
    return project


def test_a_project_with_no_audio_yet_packs_its_sources_as_a_text_only_book(tmp_path: Path) -> None:
    project = _no_audio_project(tmp_path)
    layer_book, files = bookfile.listening_layer(project)
    assert [(chapter["state"], chapter["text"]) for chapter in layer_book["chapters"]] == [
        ("text", "texts/1.txt"), ("text", "texts/2.txt")]
    assert all("file" not in chapter for chapter in layer_book["chapters"]), "không khoá null cho audio (Android đọc ra chữ \"null\")"
    assert all(chapter["script"] in files for chapter in layer_book["chapters"] if "script" in chapter), "kịch bản chỉ khi có file"
    path = bookfile.pack(project, tmp_path / "chua_co_tieng.abook")
    with BookFile(path) as opened:
        opened.verify()
        assert opened.book["package"]["version"] == 5 and opened.content_key.startswith("f-")
        assert opened.read("texts/1.txt").decode("utf-8").startswith("Chương 645 - Trở về (1)")
    packed = projectfile.pack(project, tmp_path / "du_an.abookproj")
    with projectfile.ProjectFile(packed) as opened:
        opened.verify()
        assert opened.listenable and opened.book["package"]["version"] == 5
        assert set(opened.chapter_prints) == {"texts/1.txt", "texts/2.txt"}


def test_a_chapter_gets_its_audio_back_when_the_project_has_any(tmp_path: Path) -> None:
    """Chỉ cuốn CHƯA có audio nào mới thành sách chỉ-chữ - cuốn đang làm dở không mang chữ nguồn theo (đã giữ như trước)."""
    layer_book, files = bookfile.listening_layer(_project(tmp_path))
    assert not any(name.startswith("texts/") for name in files)
    assert all("text" not in chapter for chapter in layer_book["chapters"])


# ---- hai bản cài đọc file của nhau --------------------------------------------------------------------------------------------


def test_the_file_the_phone_writes_for_a_text_book_opens_here_and_is_the_same_book() -> None:
    """`kotlin_text.abook`: cuốn chỉ-chữ qua `BookFileImport` rồi `BookDocumentWriter` ("Lưu thành .abook" kèm một thay đổi của người nghe),
    sao từ mobile/android/app/build/ sau :app:testDebugUnitTest (TextBookTest). Python mở được, kiểm hết cỡ + mã băm, ra đúng tên thư mục."""
    with BookFile(FIXTURES / "kotlin_text.abook") as phone, BookFile(FIXTURES / "python_text.abook") as computer:
        phone.verify()
        assert phone.book["package"]["version"] == 5 and phone.edits["title"] == "Tên tôi đặt"
        assert phone.content_key == computer.content_key, "cùng sách, hai nơi ghi: cùng tên thư mục"
        assert {name: phone.read(name) for name in phone.content if name.startswith("texts/")} == {
            name: computer.read(name) for name in computer.content if name.startswith("texts/")}
        assert {key: value for key, value in phone.book.items() if key != "package"} == {
            key: value for key, value in computer.book.items() if key != "package"}, "lớp sách y nguyên, chỉ thêm lớp sửa"


def test_the_preview_knows_the_same_file_was_added_before_whatever_chapters_were_picked(tmp_path: Path) -> None:
    studio = _app(tmp_path / "studio", tmp_path / "thu_vien")
    source = str(IMPORTS / "epub3.epub")
    assert studio.preview_text_book(source)["sameSource"] is None
    first = studio.add_text_book(source, chapters=[{"index": 2}, {"index": 3}])
    preview = studio.preview_text_book(source)
    assert preview["existing"] is None, "bộ chương mặc định khác bộ đã thêm"
    assert preview["sameSource"] == {"id": first["id"], "title": "Chuyến phà cuối ngày", "chapters": 2}, "nhưng đúng file ấy đã được thêm"
    whole = str(IMPORTS / "whole.txt")
    one_chapter = studio.add_text_book(whole)
    assert studio.preview_text_book(whole, split_chapters=True)["sameSource"]["id"] == one_chapter["id"], "tách chương hay không vẫn là file ấy"
    assert studio.preview_text_book(str(IMPORTS / "plain.docx"))["sameSource"] is None, "file khác thì không"
    # "Thêm bản riêng" cũng nhớ nguồn; đổi tên sách thì tên hiện ra là tên người nghe đặt
    book_edits.set_title(studio._listenable(first["id"]), "Tên tôi đặt")
    assert studio.preview_text_book(source)["sameSource"]["title"] == "Tên tôi đặt"
