"""Lớp sửa của người nghe (webui/book_edits.py, docs/EDITING.md): cuốn nhập từ file `.abook` không có xưởng, nhưng người nghe
vẫn đổi được tên sách, bìa, tên nhân vật, tên chương, nhạc nền - áp ngay, không đụng lớp sách, mang theo khi lưu thành file
(phiên bản 4), không mất khi nhập lại, và chủ máy sản xuất áp được vào dự án.

Phần đầu so với bộ ví dụ dùng chung với app Android (tests/fixtures/book_edits/): Python và Kotlin cùng ra đúng những file ấy.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import zipfile
from pathlib import Path
from typing import Any

import pytest

from abook import names as renames
from abook.webui import book_edits, bookfile, covers, music_plan, packages, store
from abook.webui.actions import FakeRunner
from abook.webui.bookfile import BookFile, BookFileError
from abook.webui.library import Preferences, book_id
from abook.webui.listening import Listening
from abook.webui.remote_studio import permitted
from abook.webui.server import App, Server
from tests import book_edits_fixtures as shared
from tests.test_bookfile_music import _plan, _tracks
from tests.test_music_api import _with_catalog
from tests.test_webui_listen_and_sync import _request, make_project

TOKEN = {"X-Ebook-Token": "t"}
CASES = sorted(shared.CASES)


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _app(tmp_path: Path, library_root: Path) -> App:
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(library_root)})
    return App(preferences=preferences, runner=FakeRunner(), token="t",
               listening=Listening(tmp_path / "prefs" / "listening.json"))


@pytest.fixture()
def imported(tmp_path: Path):
    """Một máy KHÔNG có xưởng: thư viện chỉ có cuốn `base` nhập từ file (thư mục chép từ bộ ví dụ), server thật đang chạy."""
    library = tmp_path / "thu_vien"
    folder = library / packages.IMPORTED_FOLDER / "base"
    shutil.copytree(shared.BASE, folder)
    app = _app(tmp_path, library)
    server = Server(app, port=0).start()
    identifier = book_id(folder)

    def raw(method: str, path: str, body: dict | None = None):
        return _request(server.port, method, path.replace("{id}", identifier), headers=TOKEN, body=body)

    def call(method: str, path: str, body: dict | None = None):
        status, data, _ = raw(method, path, body)
        return status, json.loads(data) if data and data[:1] in b"{[" else data

    call.raw = raw  # type: ignore[attr-defined]
    try:
        yield app, folder, identifier, call
    finally:
        server.stop()


# ---- bộ ví dụ dùng chung ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES)
def test_the_listener_sees_what_the_golden_file_says(case: str) -> None:
    edits = book_edits.parse((shared.FIXTURES / "edits" / f"{case}.json").read_bytes())
    assert shared.overlay_views(shared.BASE, edits) == _read(shared.FIXTURES / "expected" / f"{case}.json")


def test_a_series_file_renames_its_parts_and_follows_the_series_wide_chapter_ids() -> None:
    edits = book_edits.validate({**shared.HEAD, "title": "Tên khác", "chapters": {"200001": {"title": "Chương Một"}}})
    shown = book_edits.apply_manifest(_read(shared.FIXTURES / "series" / "book.json"), edits)
    golden = _read(shared.FIXTURES / "expected" / "series_title_and_chapter.json")["manifest"]
    assert {key: value for key, value in shown.items() if key != "package"} == golden
    assert [part["title"] for part in shown["parts"]] == ["Tên khác · Phần 1", "Tên khác · Phần 2"]
    assert [chapter["fullTitle"] for chapter in shown["chapters"]] == ["Chương 1", "Chương Một · Mở đầu"]


@pytest.mark.parametrize("name", sorted([*shared.INVALID, *shared.INVALID_RAW]))
def test_a_bad_edits_file_is_refused_whole(name: str) -> None:
    with pytest.raises(book_edits.EditsError):
        book_edits.parse((shared.FIXTURES / "invalid" / f"{name}.json").read_bytes())


def test_an_oversized_or_overlong_edits_file_is_refused() -> None:
    too_many_people = {**shared.HEAD, "characters": {f"P{i}": "x" for i in range(book_edits.MAX_CHARACTERS + 1)}}
    too_many_chapters = {**shared.HEAD, "chapters": {str(i): {"title": "x"} for i in range(book_edits.MAX_CHAPTERS + 1)}}
    for value in (too_many_people, too_many_chapters):
        with pytest.raises(book_edits.EditsError):
            book_edits.validate(value)
    with pytest.raises(book_edits.EditsError, match="quá lớn"):
        book_edits.parse(b" " * (book_edits.MAX_EDITS_BYTES + 1))


@pytest.mark.parametrize("name", sorted(shared.MERGE_CASES))
def test_merging_two_layers_follows_the_golden_file(name: str) -> None:
    golden = _read(shared.FIXTURES / "merge" / f"{name}.json")
    merged, report = book_edits.merge(golden["local"], golden["incoming"])
    assert book_edits._ordered(merged) == golden["merged"] and report == golden["report"]


def test_writers_store_the_minimum_and_a_noop_edit_never_counts(tmp_path: Path) -> None:
    folder = tmp_path / "base"
    shutil.copytree(shared.BASE, folder)
    book_edits.set_title(folder, "Sách thử · Tập 1")  # đúng tên người làm sách đặt
    book_edits.set_music(folder, {"enabled": True, "levelDb": -18})  # đúng mức của sách
    book_edits.set_chapter_title(folder, 1, "Chương 646", None)
    assert not (folder / book_edits.EDITS_FILE).exists(), "không có thay đổi thật thì không có file"
    book_edits.set_title(folder, "Tên khác")
    assert book_edits.count(book_edits.load(folder)) == 1
    assert (folder / book_edits.EDITS_FILE).read_bytes().endswith(b"\n") and b"\r" not in (folder / book_edits.EDITS_FILE).read_bytes()


def test_the_book_layer_is_never_modified_in_place(imported) -> None:
    app, folder, _identifier, call = imported
    before = {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()}
    call("PUT", "/api/books/{id}/title", {"title": "Mới"})
    call("POST", "/api/books/{id}/characters/rename", {"character": "LUCIEN", "name": "Lu"})
    call("PUT", "/api/books/{id}/chapters/1/title", {"title": "Một"})
    call("PUT", "/api/books/{id}/music", {"levelDb": -30})
    call("PUT", "/api/books/{id}/cover", {"image": shared.cover_data_url()})
    after = {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()}
    changed = {path.relative_to(folder).as_posix() for path in after if before.get(path) != after[path]}
    assert changed == {"edits.json", "edits/cover.jpg"}, "mọi thay đổi nằm ở lớp sửa; book.json, cast, bìa gốc nguyên"


# ---- hợp đồng máy chủ <-> LocalStudio (Kotlin) -----------------------------------------------------------------------


def _scrub(value: Any, volatile: list[str]) -> Any:
    if isinstance(value, dict):
        return {key: _scrub(item, volatile) for key, item in value.items() if key not in volatile}
    if isinstance(value, list):
        return [_scrub(item, volatile) for item in value]
    return value


@pytest.mark.parametrize("name", sorted(shared.CONTRACT))
def test_the_server_still_answers_as_the_recorded_contract(name: str) -> None:
    """Chuỗi yêu cầu của từng ca chạy lại qua máy chủ thật phải ra đúng lời đáp đã ghi - LocalStudio.kt đáp y hệt (test JVM)."""
    golden = _read(shared.FIXTURES / "contract" / f"{name}.json")
    fresh = shared.record_contract(shared.BASE, shared.CONTRACT[name])
    assert _scrub(fresh, golden["volatile"]) == _scrub(golden["steps"], golden["volatile"])


# ---- người nghe trên máy tính không có xưởng ------------------------------------------------------------------------


def test_every_edit_shows_where_the_listener_looks(imported) -> None:
    app, folder, identifier, call = imported
    assert call("PUT", "/api/books/{id}/title", {"title": "  Sách  của   tôi "})[1] == {"title": "Sách của tôi"}
    assert call("POST", "/api/books/{id}/characters/rename", {"character": "LUCIEN", "name": "Lu-xi-en"})[0] == 200
    assert call("PUT", "/api/books/{id}/chapters/1/title", {"title": "Chương Một", "subtitle": ""})[0] == 200
    assert call("PUT", "/api/books/{id}/cover", {"image": shared.cover_data_url()})[0] == 200
    view = app.listen_book(identifier)
    assert view["title"] == "Sách của tôi" and view["edits"] == 4
    assert [chapter["fullTitle"] for chapter in view["chapters"]] == ["Chương Một", "Chương 647 · Trở về (2)"]
    assert view["cover"]["url"].startswith(f"/media/books/{identifier}/cover?v=") and view["cover"]["width"] == 96
    assert view["lastChapterTitle"] == "" and [book["title"] for book in app.listen_library()] == ["Sách của tôi"]
    _status, cast = call("GET", "/api/books/{id}/cast")
    assert [person["displayName"] for person in cast["characters"]] == ["Hây-đi", "Lu-xi-en"]
    assert cast["characters"][1]["originalName"] == "Lucien" and cast["characters"][0]["firstChapter"] == "Chương Một", "người đầu tiên nói ở chương đã đổi tên"
    _status, script = call("GET", "/api/books/{id}/chapters/1/script")
    assert script["title"] == "Chương Một" and [s["speaker"] for s in script["segments"] if s["speaker"]] == ["Lu-xi-en", "Hây-đi"]
    assert all(s.get("stableId") and s.get("textSha256") for s in script["segments"]), "lớp sách mang mã ổn định của câu"
    status, data, _headers = call.raw("GET", "/media/books/{id}/cover")
    assert status == 200 and data[:3] == bytes([0xFF, 0xD8, 0xFF]) and data == (folder / book_edits.EDITS_COVER).read_bytes()


def test_removing_the_cover_draws_one_from_the_title_and_the_book_layer_keeps_its_own(imported) -> None:
    app, folder, identifier, call = imported
    assert app.listen_book(identifier)["cover"] is not None
    assert call("DELETE", "/api/books/{id}/cover") == (200, {"cover": None})
    assert app.listen_book(identifier)["cover"] is None and (folder / "cover.jpg").is_file()
    assert call("DELETE", "/api/books/{id}/edits")[1] == {"applied": 0, "waiting": 0}
    assert app.listen_book(identifier)["cover"] is not None, "bỏ mọi thay đổi: bìa của người làm sách trở lại"


def test_the_player_gets_the_music_the_listener_left(imported) -> None:
    app, _folder, identifier, call = imported
    assert [(cue["start"], cue["gainDb"]) for cue in app.music_cues(identifier, 1)["cues"]] == [(0.0, -7.39), (60.0, -28.19)]
    call("PUT", "/api/books/{id}/music", {"silence": {"1:60000": True}, "levelDb": -12})
    cues = app.music_cues(identifier, 1)
    assert cues["levelDb"] == -12.0 and [cue["start"] for cue in cues["cues"]] == [0.0], "đoạn im lặng bị bỏ, mức mới"
    assert cues["cues"][0]["gainDb"] == music_plan.cue_gain_db(-12.0, -26.0, 0.1), "tính lại bằng đúng công thức của người làm sách"
    assert cues["credits"], "ghi công bài còn phát vẫn hiện"
    call("PUT", "/api/books/{id}/music", {"enabled": False})
    assert app.music_cues(identifier, 1)["cues"] == []
    status, view = call("GET", "/api/books/{id}/music")
    assert (status, view["enabled"], len(view["cues"]), view["cues"][1]["silenced"]) == (200, False, 2, True)


def test_a_phone_style_sequence_of_edits_leaves_a_minimal_file(imported) -> None:
    _app_, folder, _identifier, call = imported
    call("POST", "/api/books/{id}/characters/rename", {"character": "HEIDI", "name": "Heidi"})  # về tên gốc (người làm sách đã đổi)
    assert book_edits.load(folder)["characters"] == {"HEIDI": "Heidi"}, "tên gốc khác tên người làm sách đặt thì phải ghi rõ"
    call("POST", "/api/books/{id}/characters/rename", {"character": "HEIDI", "name": "Hây-đi"})  # đúng tên người làm sách đặt
    call("PUT", "/api/books/{id}/chapters/2/title", {"subtitle": "Hết"})
    call("PUT", "/api/books/{id}/chapters/2/title", {"revert": True})
    assert book_edits.is_empty(book_edits.load(folder)) and not (folder / book_edits.EDITS_FILE).exists()


def test_a_linked_book_and_an_unknown_book_cannot_be_edited(imported, tmp_path: Path) -> None:
    app, _folder, _identifier, call = imported
    assert call("PUT", "/api/books/nope/title", {"title": "x"})[0] == 404
    # sách "Trên máy khác": gói mang `package.remote` (remote_books.remote_of) - nghe thẳng, chưa phải của máy này
    from abook.webui import remote_books

    remote = tmp_path / "thu_vien" / remote_books.REMOTE_FOLDER / "m1" / "b1"
    shutil.copytree(shared.BASE, remote)
    data = _read(remote / "book.json")
    data["package"]["remote"] = {"computer": "m1", "book": "b1"}
    (remote / "book.json").write_bytes(json.dumps(data).encode("utf-8"))
    status, data = call("PUT", f"/api/books/{book_id(remote)}/title", {"title": "x"})
    assert status == 409 and "máy tính khác" in data["error"]
    assert app.capabilities(remote) == {"toolchain": True, "workshop": False, "link": True}


# ---- khả năng của máy --------------------------------------------------------------------------------------------


def test_the_app_reports_what_this_machine_can_do_with_the_open_book(imported) -> None:
    app, _folder, identifier, call = imported
    _status, info = call("GET", "/api/app")
    assert info["capabilities"] == {"toolchain": True, "workshop": False, "link": False}, "bản dev: Studio là runtime cạnh mã"
    _status, info = call("GET", f"/api/app?book={identifier}")
    assert info["capabilities"] == {"toolchain": True, "workshop": False, "link": False}
    assert app.listen_book(identifier)["capabilities"] == {"toolchain": True, "workshop": False, "link": False}
    assert [book["capabilities"]["workshop"] for book in app.listen_library()] == [False]

    class Missing:  # app đóng gói chưa cài Studio
        def installed(self) -> bool:
            return False

        def outdated(self) -> bool:
            return False

    app.studio = Missing()
    assert app.capabilities()["toolchain"] is False
    app.studio = type("Old", (), {"installed": lambda self: True, "outdated": lambda self: True})()
    assert app.capabilities()["toolchain"] is False, "Studio cũ cũng không dùng được"


def test_a_project_has_a_workshop_and_the_chapter_title_lives_next_to_its_book(tmp_path: Path) -> None:
    library = tmp_path / "thu_vien"
    library.mkdir()
    project = make_project(library)
    app = _app(tmp_path, library)
    server = Server(app, port=0).start()
    try:
        identifier = book_id(project)
        status, data, _ = _request(server.port, "PUT", f"/api/books/{identifier}/chapters/1/title", headers=TOKEN,
                                   body={"title": "Chương Một", "subtitle": "Mở đầu"})
        assert status == 200 and json.loads(data) == {"chapterId": 1, "title": "Chương Một", "subtitle": "Mở đầu",
                                                      "fullTitle": "Chương Một · Mở đầu"}
        assert json.loads((project / store.CHAPTER_TITLES_FILE).read_text(encoding="utf-8")) == {
            "1": {"title": "Chương Một", "subtitle": "Mở đầu"}}
        assert not (project / book_edits.EDITS_FILE).exists(), "cuốn có xưởng không bao giờ có edits.json"
        view = app.listen_book(identifier)
        assert view["chapters"][0]["fullTitle"] == "Chương Một · Mở đầu" and view["capabilities"]["workshop"] is True
        assert store.chapter_script(project, 1)["title"] == "Chương Một · Mở đầu"
        status, data, _ = _request(server.port, "GET", f"/api/app?book={identifier}", headers=TOKEN)
        assert json.loads(data)["capabilities"]["workshop"] is True
        status, data, _ = _request(server.port, "PUT", f"/api/books/{identifier}/chapters/1/title", headers=TOKEN, body={"revert": True})
        assert json.loads(data)["fullTitle"] == "Chương 646 · Trở về (1)" and not (project / store.CHAPTER_TITLES_FILE).exists()
        status, _data, _ = _request(server.port, "PUT", f"/api/books/{identifier}/chapters/99/title", headers=TOKEN, body={"title": "x"})
        assert status == 404
        status, data, _ = _request(server.port, "POST", f"/api/books/{identifier}/save", headers=TOKEN, body={})
        assert status == 409 and "Xuất" in json.loads(data)["error"], "dự án có xưởng: dùng Xuất"
    finally:
        server.stop()
    assert permitted("PUT", f"/api/books/{identifier}/chapters/1/title") and not permitted("PUT", f"/api/books/{identifier}/title")


# ---- lưu thành file, mở lại, nhập lại ---------------------------------------------------------------------------------


def _edited_library(tmp_path: Path, name: str = "may_a") -> tuple[App, Path, str]:
    library = tmp_path / name
    folder = library / packages.IMPORTED_FOLDER / "base"
    shutil.copytree(shared.BASE, folder)
    return _app(tmp_path / name, library), folder, book_id(folder)


def test_saving_writes_a_version_4_file_another_computer_opens_with_the_edits(tmp_path: Path) -> None:
    app, folder, _identifier = _edited_library(tmp_path)
    book_edits.set_title(folder, "Sách của tôi")
    book_edits.set_character_name(folder, "LUCIEN", "Lu-xi-en")
    book_edits.set_cover(folder, shared.tiny_cover(), now=1759400000)
    book_edits.set_music(folder, {"silence": {"1:0": True}})
    server = Server(app, port=0).start()
    try:
        status, data, _ = _request(server.port, "POST", f"/api/books/{book_id(folder)}/save", headers=TOKEN, body={})
        saved = json.loads(data)
        status_proj, data_proj, _ = _request(server.port, "POST", f"/api/books/{book_id(folder)}/save", headers=TOKEN,
                                            body={"as": "abookproj"})
    finally:
        server.stop()
    assert status == 200 and saved["edits"] == 4 and Path(saved["file"]).name == "Sách của tôi.abook"
    assert status_proj == 409 and "dựng xưởng" in json.loads(data_proj)["error"]
    with zipfile.ZipFile(saved["file"]) as archive:
        first = archive.infolist()[0]
        assert (first.filename, first.compress_type) == ("mimetype", zipfile.ZIP_STORED)
        assert archive.getinfo("chapters/00001_645.mp3").compress_type == zipfile.ZIP_STORED
        assert archive.getinfo("edits/cover.jpg").compress_type == zipfile.ZIP_STORED
        assert {"edits.json", "edits/cover.jpg", "cover.jpg"} <= set(archive.namelist()), "bìa gốc nguyên, bìa mới ở edits/"
        readium = json.loads(archive.read("manifest.json"))
        assert readium["metadata"]["title"] == "Sách của tôi", "app khác đọc Readium cũng thấy tên mới"
    with BookFile(saved["file"]) as opened:
        opened.verify()
        assert opened.book["package"]["version"] == 4 and book_edits.count(opened.edits) == 4
        assert json.loads(opened.read("book.json"))["title"] == "Sách thử · Tập 1", "lớp sách không bị sửa tại chỗ"
    other, _other_folder, _ = _edited_library(tmp_path, "may_b")
    shutil.rmtree(_other_folder)
    opened_on_b = other.open_book_file(saved["file"])
    assert opened_on_b["how"] == "new"
    view = other.listen_book(opened_on_b["id"])
    assert view["title"] == "Sách của tôi" and view["edits"] == 4 and view["cover"]["version"] == 1759400000
    assert [person["displayName"] for person in packages.cast(other.library.resolve_listenable(opened_on_b["id"]))["characters"]
            ] == ["Hây-đi", "Lu-xi-en"]


def test_a_book_without_edits_saves_in_the_producers_own_version(tmp_path: Path) -> None:
    _app_, folder, _identifier = _edited_library(tmp_path)
    out = bookfile.repack(folder, tmp_path / "ra.abook")
    with BookFile(out) as opened:
        opened.verify()
        assert opened.book["package"]["version"] == 2 and book_edits.is_empty(opened.edits) and "edits.json" not in opened.content
        assert opened.chapter_prints == BookFile(shared.FIXTURES / "written" / "python_v4.abook").chapter_prints


def test_opening_the_same_book_again_keeps_the_listeners_edits(tmp_path: Path) -> None:
    producer = tmp_path / "may_san_xuat"
    producer.mkdir()
    project = make_project(producer)
    first = bookfile.pack(project, tmp_path / "v1.abook")
    app = _app(tmp_path, tmp_path / "thu_vien")
    opened = app.open_book_file(str(first))
    folder = app.library.resolve_listenable(opened["id"])
    book_edits.set_title(folder, "Tên của tôi")
    book_edits.set_character_name(folder, "LUCIEN", "Mine")
    # file nhiều chương hơn: thư mục bị thay tại chỗ - nhưng phần sửa không mất, bên này thắng khi trùng khoá
    mp3 = project / "output" / "chapters" / "00002_646.mp3"
    mp3.write_bytes(b"ID3" + bytes(range(255, -1, -1)) * 40)
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("UPDATE chapters SET status='completed', output_mp3=?, completed_at=1 WHERE id=2", (str(mp3),))
    db.commit()
    db.close()
    fuller = bookfile.pack(project, tmp_path / "v2.abook")
    again = app.open_book_file(str(fuller))
    assert again["how"] == "updated" and again["id"] == opened["id"]
    assert book_edits.load(folder) == {"format": "abook-edits", "version": 1, "title": "Tên của tôi", "characters": {"LUCIEN": "Mine"}}
    assert app.listen_book(opened["id"])["title"] == "Tên của tôi"


def test_a_file_with_edits_merges_into_a_book_that_is_already_complete(tmp_path: Path) -> None:
    app, folder, identifier = _edited_library(tmp_path)
    book_edits.set_title(folder, "Của tôi")
    book_edits.set_music(folder, {"silence": {"1:0": True}})
    with_edits = shared.FIXTURES / "written" / "python_v4.abook"  # phần sửa `everything`: tên Sách của tôi, bìa, Lu-xi-en, ...
    # cùng cuốn, không nhiều chương hơn: không giải nén lại, nhưng phần sửa của file vẫn được hợp vào
    result = app.open_book_file(str(with_edits))
    assert result["how"] == "existing" and result["id"] == identifier and result["merge"]["conflicts"] >= 1
    edits = book_edits.load(folder)
    assert edits["title"] == "Của tôi", "khoá cả hai cùng có: bên máy này thắng"
    assert edits["characters"] == {"LUCIEN": "Lu-xi-en"} and edits["chapters"]["1"] == {"title": "Chương Một"}
    assert edits["music"]["silenced"] == ["1:0"] and edits["music"]["levelDb"] == -12.0
    assert (folder / book_edits.EDITS_COVER).is_file() and edits["cover"]["version"] == 1759400000, "bìa file mang theo lấy về"


def test_opening_a_file_without_edits_still_reports_the_edits_kept_on_this_machine(tmp_path: Path) -> None:
    app, folder, identifier = _edited_library(tmp_path)
    plain = bookfile.repack(folder, tmp_path / "khong_sua.abook")  # đóng gói từ chính cuốn này, lúc chưa sửa gì
    book_edits.set_title(folder, "Của tôi")
    book_edits.set_character_name(folder, "LUCIEN", "Lu-xi-en")
    assert book_edits.is_empty(BookFile(plain).edits)
    result = app.open_book_file(str(plain))
    assert result["how"] == "existing" and result["id"] == identifier
    assert result["merge"]["kept"] == 2 and result["merge"]["adopted"] == 0 and "edits" not in result
    assert book_edits.load(folder)["title"] == "Của tôi"


def _forged(tmp_path: Path, edits_bytes: bytes, *, cover: bytes | None = None, version: int = 4) -> Path:
    """File phiên bản `version` mang `edits.json` do người lạ viết: dựng từ file đúng rồi thay phần sửa và ghi lại mã băm."""
    source = shared.FIXTURES / "written" / "python_v4.abook"
    target = tmp_path / "gia.abook"
    with zipfile.ZipFile(source) as archive, zipfile.ZipFile(target, "w") as sink:
        book = json.loads(archive.read("book.json"))
        files = {name: meta for name, meta in book["package"]["files"].items()}
        replacement = {book_edits.EDITS_FILE: edits_bytes, **({book_edits.EDITS_COVER: cover} if cover is not None else {})}
        for name, data in replacement.items():
            files[name] = bookfile.describe(data)
        if cover is None:
            files.pop(book_edits.EDITS_COVER, None)
        book["package"] = {**book["package"], "version": version, "files": files}
        for info in archive.infolist():
            if info.filename in (book_edits.EDITS_FILE, book_edits.EDITS_COVER) and info.filename not in replacement:
                continue
            data = json.dumps(book).encode() if info.filename == "book.json" else replacement.get(info.filename, archive.read(info.filename))
            sink.writestr(info, data)
    return target


def test_a_file_with_a_malformed_edits_layer_is_refused_whole(tmp_path: Path) -> None:
    good_cover = shared.tiny_cover()
    for broken in (b"{", b'{"format": "abook-edits", "version": 1, "title": "  x"}',
                   b'{"format": "abook-edits", "version": 1, "wishes": []}'):
        with pytest.raises(BookFileError):
            BookFile(_forged(tmp_path, broken, cover=good_cover))
    cover_meta = b'{"format": "abook-edits", "version": 1, "cover": {"color": "", "width": 1, "height": 1, "version": 1}}'
    with pytest.raises(BookFileError, match="bìa"):
        BookFile(_forged(tmp_path, cover_meta, cover=None))  # nói có bìa sửa mà thiếu file
    with pytest.raises(BookFileError, match="bìa"):
        BookFile(_forged(tmp_path, b'{"format": "abook-edits", "version": 1, "title": "x"}', cover=good_cover))
    with pytest.raises(BookFileError, match="không dùng được"):
        BookFile(_forged(tmp_path, cover_meta, cover=b"not a jpeg"))
    with pytest.raises(BookFileError, match="quá lớn"):
        BookFile(_forged(tmp_path, b" " * (book_edits.MAX_EDITS_BYTES + 1), cover=good_cover))
    with pytest.raises(BookFileError, match="mục lạ"):
        BookFile(_forged(tmp_path, cover_meta, cover=good_cover, version=3))  # phiên bản cũ không có lớp sửa
    BookFile(_forged(tmp_path, cover_meta, cover=good_cover)).close()


def test_an_abook_never_carries_a_projects_private_parts(tmp_path: Path) -> None:
    for name in ("project/project.sqlite3", "sources/1_a.txt", "views/work.json"):
        target = tmp_path / "la.abook"
        with zipfile.ZipFile(shared.FIXTURES / "written" / "python_v4.abook") as archive, zipfile.ZipFile(target, "w") as sink:
            book = json.loads(archive.read("book.json"))
            book["package"]["files"][name] = bookfile.describe(b"x")
            for info in archive.infolist():
                sink.writestr(info, json.dumps(book).encode() if info.filename == "book.json" else archive.read(info.filename))
            sink.writestr(name, b"x")
        with pytest.raises(BookFileError, match="mục lạ"):
            BookFile(target)


def test_files_written_by_each_platform_open_on_the_other() -> None:
    written = shared.FIXTURES / "written"
    for path in sorted(written.glob("*.abook")):  # python_v4 (repack) và kotlin_v4 (BookDocumentWriter)
        with BookFile(path) as opened:
            opened.verify()
            assert opened.book["package"]["version"] == 4 and not book_edits.is_empty(opened.edits), path.name
            with zipfile.ZipFile(path) as archive:
                assert archive.infolist()[0].filename == "mimetype" and archive.infolist()[0].compress_type == zipfile.ZIP_STORED
                assert all(archive.getinfo(name).compress_type == zipfile.ZIP_STORED
                           for name in archive.namelist() if name.endswith((".mp3", ".wav", ".jpg"))), path.name
    assert (written / "python_v4.abook").is_file()


# ---- "Nhạc của tôi" trên sách không có xưởng (docs/MUSIC_IMPORT.md): ghim bài của người nghe vào một mốc nhạc -----------------


def _my_tone(app: App) -> str:
    """Nhập bài mẫu vào kho "Nhạc của tôi" của máy; trả link của nó."""
    return app.my_music.import_file(shared.FIXTURES / "track" / "tone.wav")[0]["link"]


def test_pinning_one_of_my_tracks_puts_its_file_in_the_book_and_the_player_plays_it(imported) -> None:
    app, folder, identifier, call = imported
    link = _my_tone(app)
    assert link == shared.TRACK_LINK
    before = {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()}
    status, view = call("PUT", "/api/books/{id}/music", {"pins": {"1:0": link}})
    name = f"music/{shared.TRACK_SHA}.wav"
    assert status == 200 and view["cues"][0]["pinned"] is True and "pinned" not in view["cues"][1]
    assert (folder / name).read_bytes() == shared.tone_wav(), "file bài đi vào thư mục sách, đúng chỗ bài của người làm sách nằm"
    after = {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()}
    assert {path.relative_to(folder).as_posix() for path in after if before.get(path) != after[path]} == {"edits.json", name}
    stored = book_edits.load(folder)["music"]
    assert stored["pins"] == {"1:0": link} and stored["tracks"][shared.TRACK_SHA]["ext"] == "wav"
    cues = app.music_cues(identifier, 1)
    assert [cue["start"] for cue in cues["cues"]] == [0.0, 60.0]
    pinned = cues["cues"][0]
    assert pinned["src"].endswith(f"/music/files/{shared.TRACK_SHA}.wav") and pinned["link"] == link
    assert pinned["gainDb"] == music_plan.cue_gain_db(-18.0, stored["tracks"][shared.TRACK_SHA].get("lufs"), None)
    assert cues["credits"][link] == {"title": "tone"}, "chỉ tên bài (và nghệ sĩ nếu có), không giấy phép"
    served = call.raw("GET", pinned["src"].replace(identifier, "{id}"))
    assert served[0] == 200 and served[1] == shared.tone_wav()
    assert call("PUT", "/api/books/{id}/music", {"pins": {"1:0": None}})[0] == 200
    assert not (folder / name).exists() and book_edits.is_empty(book_edits.load(folder)) and not (folder / "edits.json").exists()
    assert call.raw("GET", f"/api/books/{{id}}/music/files/{shared.TRACK_SHA}.wav")[0] == 404, "bỏ ghim thì file không còn được phục vụ"


def test_a_pin_that_does_not_fit_is_refused_with_a_sentence_and_changes_nothing(imported) -> None:
    app, folder, _identifier, call = imported
    link = _my_tone(app)
    cases = [({"pins": {"1:0": f"local:{shared.OTHER_SHA}"}}, "không còn trong Nhạc của tôi"),
             ({"pins": {"1:0": "https://x/y.mp3"}}, "Chỉ đổi được sang bài trong Nhạc của tôi"),
             ({"pins": {"7:7": link}}, "Không có đoạn nhạc này"),
             ({"pins": "tone"}, "không hợp lệ"),
             ({"volume": 3}, "đổi bài")]
    for body, message in cases:
        status, answer = call("PUT", "/api/books/{id}/music", body)
        assert status == 400 and message in answer["error"], body
    assert not (folder / "edits.json").exists() and not (folder / "music" / f"{shared.TRACK_SHA}.wav").exists()
    app.my_music.remove(shared.TRACK_SHA)
    assert call("PUT", "/api/books/{id}/music", {"pins": {"1:0": link}})[0] == 400, "bài vừa xoá khỏi kho thì không ghim được"


def test_the_alternatives_of_a_book_without_a_workshop_are_my_tracks_only(imported) -> None:
    app, _folder, _identifier, call = imported
    assert call("GET", "/api/books/{id}/music/scenes/1:0/alternatives")[1] == {"key": "1:0", "alternatives": [], "mine": []}
    link = _my_tone(app)
    mine = call("GET", "/api/books/{id}/music/scenes/1:0/alternatives")[1]["mine"]
    assert [(item["link"], item["analysed"], item["fits"]) for item in mine] == [(link, False, False)]
    call("PUT", "/api/books/{id}/music", {"pins": {"1:0": link}})
    assert call("GET", "/api/books/{id}/music/scenes/1:0/alternatives")[1]["mine"] == [], "bài đang dùng ở mốc này không nằm trong danh sách đổi"
    assert len(call("GET", "/api/books/{id}/music/scenes/1:60000/alternatives")[1]["mine"]) == 1
    assert call("GET", "/api/books/{id}/music/scenes/9:9/alternatives")[0] == 404


def test_clearing_all_edits_also_drops_the_pinned_files_but_never_a_book_layer_file(imported) -> None:
    app, folder, _identifier, call = imported
    link = _my_tone(app)
    call("PUT", "/api/books/{id}/music", {"pins": {"1:0": link, "1:60000": link}})
    assert (folder / "music" / f"{shared.TRACK_SHA}.wav").is_file() and book_edits.count(book_edits.load(folder)) == 2
    layer = {name for name in book_edits._base(folder)["package"]["files"]}
    call("DELETE", "/api/books/{id}/edits")
    assert not (folder / "music" / f"{shared.TRACK_SHA}.wav").exists()
    assert all((folder / name).is_file() for name in layer if name != "edits.json")


def test_saving_carries_the_pinned_track_and_another_computer_plays_it(tmp_path: Path) -> None:
    app, folder, _identifier = _edited_library(tmp_path)
    link = _my_tone(app)
    book_edits.set_music(folder, {"pins": {"1:0": link}}, app._my_track)
    out = bookfile.repack(folder, tmp_path / "co_nhac.abook")
    name = f"music/{shared.TRACK_SHA}.wav"
    with zipfile.ZipFile(out) as archive:
        assert archive.getinfo(name).compress_type == zipfile.ZIP_STORED and archive.read(name) == shared.tone_wav()
    with BookFile(out) as opened:
        opened.verify()
        assert opened.book["package"]["version"] == 4 and name in opened.content
        assert book_edits.pinned_files(opened.edits) == [name]
        assert name not in json.loads(opened.read("book.json")).get("music", {}).get("tracks", {}), "lớp sách không bị sửa tại chỗ"
    other, other_folder, _ = _edited_library(tmp_path, "may_b")
    shutil.rmtree(other_folder)
    opened_on_b = other.open_book_file(str(out))
    assert opened_on_b["how"] == "new"
    path = other.library.resolve_listenable(opened_on_b["id"])
    assert (path / name).read_bytes() == shared.tone_wav()
    played = other.music_cues(opened_on_b["id"], 1)["cues"]
    assert played[0]["link"] == link and played[0]["src"].endswith(f"/music/files/{shared.TRACK_SHA}.wav")
    assert packages.music_file(path, name) == path / name
    assert other.my_music.entries() == [], "máy kia không có bài này trong kho của nó - vẫn phát được vì nó nằm trong sách"


def test_the_file_a_phone_wrote_is_opened_and_its_pinned_track_kept(tmp_path: Path) -> None:
    pinned = shared.FIXTURES / "written" / "python_v4_pins.abook"
    app, folder, identifier = _edited_library(tmp_path)
    book_edits.set_music(folder, {"levelDb": -30})
    result = app.open_book_file(str(pinned))  # cùng cuốn, không nhiều chương hơn: không giải nén lại, phần sửa được hợp vào
    assert result["how"] == "existing" and result["id"] == identifier
    edits = book_edits.load(folder)
    assert edits["music"]["levelDb"] == -30.0 and edits["music"]["pins"] == {"1:0": shared.TRACK_LINK}
    assert (folder / "music" / f"{shared.TRACK_SHA}.wav").read_bytes() == shared.tone_wav(), "file bài ghim lấy về từ file"
    assert app.music_cues(identifier, 1)["cues"][0]["link"] == shared.TRACK_LINK


def test_opening_a_fuller_file_again_keeps_the_pinned_file_of_this_machine(tmp_path: Path) -> None:
    app, folder, identifier = _edited_library(tmp_path)
    book_edits.set_music(folder, {"pins": {"1:0": _my_tone(app)}}, app._my_track)
    plain = tmp_path / "nguyen_ban.abook"
    shutil.copytree(shared.BASE, tmp_path / "goc")
    bookfile.repack(tmp_path / "goc", plain)
    with BookFile(plain) as opened:
        opened.extract(folder.parent, folder.name)  # nhập lại tại chỗ, như "updated"
    assert (folder / "music" / f"{shared.TRACK_SHA}.wav").read_bytes() == shared.tone_wav()
    assert book_edits.load(folder)["music"]["pins"] == {"1:0": shared.TRACK_LINK}


def test_a_file_whose_pinned_track_is_missing_is_refused_whole(tmp_path: Path) -> None:
    edits = book_edits.dump(book_edits.validate({**shared.HEAD, "music": shared.PINS}))
    with pytest.raises(BookFileError, match="thiếu bài nhạc"):
        BookFile(_forged(tmp_path, edits))


def _producer_project(tmp_path: Path) -> Path:
    producer = tmp_path / "may_san_xuat"
    producer.mkdir()
    project = shared.make_base_project(producer)
    _plan(project)
    return project


def _carry_tone(name: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(shared.FIXTURES / "track" / "tone.wav", target)


def test_the_producer_skips_a_pin_whose_file_is_not_in_the_book(tmp_path: Path) -> None:
    project = _producer_project(tmp_path)
    app = _app(tmp_path, project.parent)
    book_edits.stash_incoming(project, book_edits.validate({**shared.HEAD, "music": shared.PINS}), None)
    folded = book_edits.fold(project, app.my_music)
    assert folded["skipped"] == 1 and folded["applied"] == 0 and folded["music"] is False
    assert folded["reasons"] == ["1:0: file nhạc không có trong sách"]
    assert all(not link.startswith("local:") for link in music_plan.read_overrides(project)["pins"].values())
    assert app.my_music.entries() == []


def test_the_producer_takes_a_listeners_pinned_track_into_their_own_store_and_pins_it(tmp_path: Path) -> None:
    project = _producer_project(tmp_path)
    app = _app(tmp_path, project.parent)
    book_edits.stash_incoming(project, book_edits.validate({**shared.HEAD, "music": shared.PINS}), None, _carry_tone)
    assert (project / book_edits.INCOMING_MUSIC / f"{shared.TRACK_SHA}.wav").is_file()
    folded = book_edits.fold(project, app.my_music)
    assert (folded["applied"], folded["skipped"], folded["music"]) == (1, 0, True) and "reasons" not in folded
    # mốc 1:0 = hai đoạn CALM (1:1, 1:5); đoạn BATTLE (1:9) không đổi
    assert music_plan.read_overrides(project)["pins"] == {"1:1": shared.TRACK_LINK, "1:5": shared.TRACK_LINK}
    mine = app.my_music.lookup([shared.TRACK_LINK])[shared.TRACK_LINK]
    assert app.my_music.file(shared.TRACK_LINK) is not None
    assert (mine["title"], mine["creator"]) == ("Bài của tôi", "Tôi"), "file không có thẻ: lấy tên từ lớp sửa"
    assert not (project / book_edits.INCOMING_MUSIC).exists() and not (project / book_edits.INCOMING_FILE).exists()
    # áp lần nữa không nhập thêm bản nào (cùng sha1)
    book_edits.stash_incoming(project, book_edits.validate({**shared.HEAD, "music": shared.PINS}), None, _carry_tone)
    book_edits.fold(project, app.my_music)
    assert len(app.my_music.entries()) == 1


def test_the_producer_skips_a_pin_on_a_cue_the_project_no_longer_has(tmp_path: Path) -> None:
    project = _producer_project(tmp_path)
    app = _app(tmp_path, project.parent)
    edits = book_edits.validate({**shared.HEAD, "music": {"pins": {"1:777": shared.TRACK_LINK}, "tracks": shared.PINS["tracks"]}})
    book_edits.stash_incoming(project, edits, None, _carry_tone)
    folded = book_edits.fold(project, app.my_music)
    assert (folded["applied"], folded["skipped"], folded["reasons"]) == (0, 1, ["1:777: mốc nhạc này không còn trong dự án"])
    assert app.my_music.entries() == []


def test_a_file_that_is_not_the_pinned_track_is_not_taken(tmp_path: Path) -> None:
    project = _producer_project(tmp_path)
    app = _app(tmp_path, project.parent)

    def other(name: str, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"not audio")

    book_edits.stash_incoming(project, book_edits.validate({**shared.HEAD, "music": shared.PINS}), None, other)
    folded = book_edits.fold(project, app.my_music)
    assert (folded["applied"], folded["skipped"]) == (0, 1) and folded["music"] is False and app.my_music.entries() == []


# ---- chủ máy sản xuất ---------------------------------------------------------------------------------------------------


def _producer_with_a_file_of_edits(tmp_path: Path):
    producer = tmp_path / "may_san_xuat"
    producer.mkdir()
    project = shared.make_base_project(producer)
    _plan(project)
    packed = bookfile.pack(project, tmp_path / "v1.abook", music_track=_tracks(tmp_path))
    listener = tmp_path / "nguoi_nghe"
    listener.mkdir()
    folder = BookFile(packed).extract(listener / "thu_vien", "b")
    book_edits.set_title(folder, "Tên người nghe đặt")
    book_edits.set_character_name(folder, "LUCIEN", "Lu-xi-en")
    book_edits.set_chapter_title(folder, 1, "Chương Một", "Mở")
    book_edits.set_cover(folder, shared.tiny_cover(), now=7)
    book_edits.set_music(folder, {"enabled": False, "levelDb": -26, "silence": {"1:60000": True}})
    return project, bookfile.repack(folder, tmp_path / "da_sua.abook")


def test_the_producer_is_offered_the_edits_and_nothing_applies_until_they_agree(tmp_path: Path) -> None:
    project, edited = _producer_with_a_file_of_edits(tmp_path)
    app = _app(tmp_path, project.parent)
    _with_catalog(app, tmp_path)  # danh mục nhạc thử: không hỏi mạng khi dựng lại rãnh nhạc
    server = Server(app, port=0).start()
    identifier = book_id(project)
    try:
        opened = app.open_book_file(str(edited))
        assert (opened["id"], opened["how"], opened["edits"]) == (identifier, "project", 7)
        assert not (project / "studio_title.json").exists() and not (project / store.CHAPTER_TITLES_FILE).exists()
        status, data, _ = _request(server.port, "GET", f"/api/books/{identifier}/edits", headers=TOKEN)
        assert json.loads(data) == {"applied": 0, "waiting": 7}
        status, data, _ = _request(server.port, "POST", f"/api/books/{identifier}/edits/fold", headers=TOKEN, body={})
        report = json.loads(data)
        assert (status, report["applied"], report["skipped"], report["music"]) == (200, 7, 0, True)
    finally:
        server.stop()
    assert store.display_title(project, "") == "Tên người nghe đặt"
    assert renames.shown(project, "LUCIEN") == "Lu-xi-en" and covers.cover_file(project) is not None
    assert store.chapter_title_overrides(project) == {1: {"title": "Chương Một", "subtitle": "Mở"}}
    overrides = music_plan.read_overrides(project)
    assert overrides["enabled"] is False and overrides["levelDb"] == -26.0
    assert not (project / book_edits.INCOMING_FILE).exists() and book_edits.incoming(project) == book_edits.empty()


def test_silenced_cues_map_back_to_the_scenes_they_were_cut_from(tmp_path: Path) -> None:
    project, edited = _producer_with_a_file_of_edits(tmp_path)
    app = _app(tmp_path, project.parent)
    app.open_book_file(str(edited))
    book_edits.fold(project)
    # cue 1:60000 = đoạn 60-90 s (bài BATTLE); đoạn 0-30 và 30-60 giữ nguyên
    assert music_plan.read_overrides(project)["silenced"] == ["1:9"]


def test_dismissing_the_offer_applies_nothing(tmp_path: Path) -> None:
    project, edited = _producer_with_a_file_of_edits(tmp_path)
    app = _app(tmp_path, project.parent)
    server = Server(app, port=0).start()
    try:
        app.open_book_file(str(edited))
        status, data, _ = _request(server.port, "DELETE", f"/api/books/{book_id(project)}/edits", headers=TOKEN)
        assert status == 200 and json.loads(data) == {"applied": 0, "waiting": 0}
    finally:
        server.stop()
    assert not (project / book_edits.INCOMING_FILE).exists() and not (project / "studio_title.json").exists()
    assert renames.shown(project, "LUCIEN") == ""


def test_a_project_script_carries_the_stable_id_and_text_hash(tmp_path: Path) -> None:
    producer = tmp_path / "p"
    producer.mkdir()
    project = shared.make_base_project(producer)
    segments = store.chapter_script(project, 1)["segments"]
    assert all(segment["stableId"].startswith("c1_s") and len(segment["textSha256"]) == 64 for segment in segments)
    packed = bookfile.pack(project, tmp_path / "s.abook")
    with BookFile(packed) as opened:
        assert json.loads(opened.read("scripts/1.json"))["segments"][0]["stableId"] == segments[0]["stableId"]
    (tmp_path / "q").mkdir()
    plain = make_project(tmp_path / "q")
    assert "stableId" not in store.chapter_script(plain, 1)["segments"][0], "sổ cũ không có cột thì không có khoá - chỉ cộng thêm"


def test_odd_request_bodies_are_refused_or_ignored_not_crashes(imported) -> None:
    app, folder, identifier, call = imported
    # name: null / số = bỏ tên đã đặt, không bao giờ thành chữ "None"
    call("POST", "/api/books/{id}/characters/rename", {"character": "LUCIEN", "name": "Lu"})
    status, answer = call("POST", "/api/books/{id}/characters/rename", {"character": "LUCIEN", "name": None})
    assert (status, answer["name"], answer["renamed"]) == (200, "Lucien", False)
    assert "None" not in (folder / book_edits.EDITS_FILE).read_text(encoding="utf-8") if (folder / book_edits.EDITS_FILE).exists() else True
    for silence in ("1:60000", ["1:60000"], 5):
        assert call("PUT", "/api/books/{id}/music", {"silence": silence})[0] == 400
    # sách vốn không có bìa: bỏ bìa không phải một thay đổi
    (folder / "cover.jpg").unlink()
    call("DELETE", "/api/books/{id}/cover")
    assert not (folder / book_edits.EDITS_FILE).exists() and app.listen_book(identifier)["edits"] == 0


def test_a_pin_in_an_edited_file_reaches_the_producers_store_through_the_open_and_fold(tmp_path: Path) -> None:
    project = _producer_project(tmp_path)
    packed = bookfile.pack(project, tmp_path / "v1.abook", music_track=_tracks(tmp_path))
    listener = tmp_path / "nguoi_nghe"
    listener.mkdir()
    folder = BookFile(packed).extract(listener / "thu_vien", "b")
    theirs = _app(tmp_path / "nguoi", listener)
    book_edits.set_music(folder, {"pins": {"1:0": _my_tone(theirs)}}, theirs._my_track)
    edited = bookfile.repack(folder, tmp_path / "da_sua.abook")
    app = _app(tmp_path, project.parent)
    assert app.open_book_file(str(edited))["how"] == "project"
    folded = book_edits.fold(project, app.my_music)
    assert (folded["applied"], folded["skipped"]) == (1, 0)
    assert app.my_music.file(shared.TRACK_LINK) is not None
    assert music_plan.read_overrides(project)["pins"] == {"1:1": shared.TRACK_LINK, "1:5": shared.TRACK_LINK}
