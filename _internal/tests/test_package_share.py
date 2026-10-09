"""Sách nhập từ file ("Thêm sách") sang được máy đã ghép (webui/package_share.py, sync.py).

Máy kia ("A") chỉ có cuốn `base` nhập từ file (thư mục chép từ bộ ví dụ) và một bản soi cuốn của máy thứ ba dưới `Trên máy khác/`:
máy đã ghép thấy `base`, không thấy bản soi (chống vòng). Máy này ("B") là App ghép với cổng đồng bộ thật của A bằng mã 6 số.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from abook.webui import book_edits, book_wishes, packages, remote_books
from abook.webui.fingerprints import Fingerprints
from abook.webui.library import Library, Preferences, book_id
from abook.webui.listening import Listening
from abook.webui.server import App
from abook.webui.actions import FakeRunner
from abook.webui.sync import Devices, SyncApp, SyncServer, manifest
from tests import book_edits_fixtures as shared
from tests.test_text_books import _book_file
from tests.test_webui_listen_and_sync import library, make_project  # noqa: F401 - fixture dùng chung


def _holder(tmp_path: Path) -> tuple[Library, SyncApp, Path, Path]:
    """Máy A: thư viện chỉ có cuốn nhập `base` + một cuốn ảo của máy khác. Trả (thư viện, SyncApp, thư mục `base`, thư mục cuốn ảo)."""
    root = tmp_path / "kia" / "thu_vien"
    folder = root / packages.IMPORTED_FOLDER / "base"
    shutil.copytree(shared.BASE, folder)
    mirror = root / remote_books.REMOTE_FOLDER / "Máy C (cccccccc)" / "Sách C (11111111)"
    shutil.copytree(shared.BASE, mirror)
    book = json.loads((mirror / "book.json").read_text(encoding="utf-8"))
    book["title"] = "Bản soi của máy C"
    book["package"]["remote"] = {"computer": "cccccccccccc", "book": "d" * 24}
    (mirror / "book.json").write_bytes(json.dumps(book, ensure_ascii=False).encode("utf-8"))
    preferences = Preferences(tmp_path / "kia" / "preferences.json")
    preferences.update({"libraryRoot": str(root)})
    lib = Library(preferences)
    sync = SyncApp(lib, Listening(tmp_path / "kia" / "listening.json"), Devices(tmp_path / "kia" / "devices.json"), "Máy A")
    return lib, sync, folder.resolve(), mirror.resolve()


def test_the_other_computer_lists_an_imported_book_but_not_a_mirror_of_a_third(tmp_path: Path) -> None:
    lib, sync, folder, mirror = _holder(tmp_path)
    assert packages.is_package(mirror) and mirror in packages.folders(lib.root), "bản soi vẫn là sách nghe được ở máy A"
    books = sync.library_view()
    assert [book["id"] for book in books] == [book_id(folder)], "chỉ cuốn nhập từ file, không bản soi (chống vòng soi nhau)"
    (entry,) = books
    assert entry["title"] == "Sách thử · Tập 1" and entry["chaptersAvailable"] == 1 and entry["series"] is None
    assert entry["cover"] and set(entry["cover"]) == {"color", "version"}
    assert sync.book(book_id(mirror)) is None, "bản soi cũng không tải được qua cổng đồng bộ"
    assert sync.book(book_id(folder)) == folder


def test_a_package_lists_with_the_same_keys_as_a_project(library, tmp_path: Path) -> None:  # noqa: F811
    lib, project, listening = library
    project_sync = SyncApp(lib, listening, Devices(tmp_path / "d1.json"), "Máy dự án")
    _lib, package_sync, _folder, _mirror = _holder(tmp_path)
    (theirs,) = package_sync.library_view()
    (mine,) = project_sync.library_view()
    assert set(theirs) >= set(mine) - {"wordsVersion"}


def test_the_manifest_of_a_package_has_the_shape_of_a_projects(library, tmp_path: Path) -> None:  # noqa: F811
    lib, project, listening = library
    project_book = manifest(project, book_id(project), listening)
    _lib, sync, folder, _mirror = _holder(tmp_path)
    key = book_id(folder)
    book = sync.book_manifest(folder, key)
    assert set(book) >= {"format", "id", "title", "narrator", "duration", "chaptersTotal", "chaptersAvailable", "complete", "series",
                         "version", "chapters", "cast", "samples", "cover", "music"}
    assert set(book) - {"music", "wordsVersion", "author"} == set(project_book) - {"music", "wordsVersion"}
    assert book["id"] == key and "package" not in book
    chapter = next(chapter for chapter in book["chapters"] if chapter["available"])
    assert set(chapter) >= set(next(item for item in project_book["chapters"] if item["available"]))
    assert chapter["file"].startswith("chapters/") and chapter["size"] == (folder / chapter["file"]).stat().st_size
    assert chapter["script"] == f"scripts/{chapter['id']}.json"
    assert book["cast"] == "cast.json" and book["samples"] == ["samples/3.wav"]
    assert book["cover"]["file"] == "cover.jpg" and book["cover"]["version"] and book["cover"]["color"]
    for name, track in book["music"]["tracks"].items():
        assert track["size"] == (folder / name).stat().st_size
    unavailable = [item for item in book["chapters"] if not item["available"]]
    assert all(item["file"] is None and item["size"] == 0 for item in unavailable if "text" not in item)


def test_the_manifest_follows_what_the_listener_changed_here_and_its_version_moves(tmp_path: Path) -> None:
    _lib, sync, folder, _mirror = _holder(tmp_path)
    key = book_id(folder)
    before = sync.book_manifest(folder, key)
    book_edits.set_title(folder, "Tên người nghe đặt")
    book_edits.set_chapter_title(folder, 1, "Chương mở đầu")
    after = sync.book_manifest(folder, key)
    assert after["title"] == "Tên người nghe đặt" and after["chapters"][0]["title"] == "Chương mở đầu"
    assert after["version"] != before["version"] and sync.library_view()[0]["title"] == "Tên người nghe đặt"
    assert sync.book_manifest(folder, key)["version"] == after["version"], "không đổi gì thì phiên bản không đổi"


def test_only_names_in_the_manifest_are_served_and_scripts_and_cast_carry_the_edits(tmp_path: Path) -> None:
    _lib, sync, folder, _mirror = _holder(tmp_path)
    book_edits.set_character_name(folder, "HEIDI", "Hây-đi mới")
    book_edits.set_chapter_title(folder, 1, "Chương mở đầu")
    book = sync.book_manifest(folder, book_id(folder))
    chapter = next(item for item in book["chapters"] if item["available"])
    assert sync.resolve_file(folder, chapter["file"]) == (folder / chapter["file"]).resolve()
    script = json.loads(sync.resolve_file(folder, chapter["script"]))
    assert "Hây-đi mới" in {segment.get("speaker") for segment in script["segments"]}
    cast = json.loads(sync.resolve_file(folder, "cast.json"))
    assert "Hây-đi mới" in {person.get("displayName") for person in cast["characters"]}
    assert sync.resolve_file(folder, "samples/3.wav") is not None
    assert sync.resolve_file(folder, "cover.jpg") == folder / "cover.jpg"
    (name, _track) = next(iter(book["music"]["tracks"].items()))
    assert sync.resolve_file(folder, name) == (folder / name).resolve()
    (folder / "bi_mat.txt").write_text("không được lộ", encoding="utf-8")
    (folder / "music" / ("0" * 40 + ".mp3")).write_bytes(b"ID3")
    (folder / "chapters" / "ngoai_gói.mp3").write_bytes(b"ID3")
    for outside in ("book.json", "bi_mat.txt", "../bi_mat.txt", "edits.json", "scripts/9.json", "chapters/ngoai_gói.mp3",
                    "music/" + "0" * 40 + ".mp3", "samples/4.wav", "texts/1.txt", "download.json"):
        assert sync.resolve_file(folder, outside) is None, outside


def test_a_text_only_package_is_shared_with_its_text(tmp_path: Path) -> None:
    root = tmp_path / "kia" / "thu_vien"
    root.mkdir(parents=True)
    folder, how = packages.import_file(_book_file(tmp_path), root, [], Fingerprints(tmp_path / "fp.json"))
    assert how == "new"
    preferences = Preferences(tmp_path / "kia" / "preferences.json")
    preferences.update({"libraryRoot": str(root)})
    sync = SyncApp(Library(preferences), Listening(tmp_path / "kia" / "listening.json"), Devices(tmp_path / "kia" / "d.json"), "Máy A")
    (entry,) = sync.library_view()
    book = sync.book_manifest(folder, entry["id"])
    assert book["chaptersAvailable"] == 0 and book["chapters"], "sách chỉ-chữ: thấy sách, chưa chương nào nghe được"
    chapter = book["chapters"][0]
    assert chapter["state"] == "text" and chapter["text"].startswith("texts/") and "file" not in chapter
    author = packages.manifest(folder).get("author")
    assert author and entry["author"] == author == book["author"], "tác giả đi theo thẻ và sách: máy kia tìm và hiện được"
    served = sync.resolve_file(folder, chapter["text"])
    assert isinstance(served, bytes) and served.decode("utf-8").strip()
    assert sync.resolve_file(folder, "texts/99999.txt") is None


def test_match_finds_an_imported_book_by_its_chapter_prints(tmp_path: Path) -> None:
    _lib, sync, folder, _mirror = _holder(tmp_path)
    prints = packages.chapter_prints(packages.manifest(folder))
    assert prints, "bộ ví dụ có audio nên có mã băm"
    assert sync.match([{"key": "khoa-cua-dien-thoai", "chapters": prints}]) == {"khoa-cua-dien-thoai": book_id(folder)}
    assert sync.match([{"key": book_id(folder)}]) == {book_id(folder): book_id(folder)}
    assert sync.match([{"key": "la", "chapters": {"chapters/khac.mp3": {"size": 1, "sha256": "0" * 64}}}]) == {}


# ---- hai máy: A giữ cuốn nhập từ file, B ghép và nghe --------------------------------------------------------------------


def _pair(tmp_path: Path, holder: tuple[Library, SyncApp, Path, Path] | None = None):
    lib, sync, folder, mirror = holder or _holder(tmp_path)
    sync.name = "Máy A"
    server = SyncServer(sync, host="127.0.0.1", port=0).start()
    preferences = Preferences(tmp_path / "nay" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path / "nay" / "thu_vien")})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "nay" / "l.json"))
    app.edits_send_delay = None
    view = app.pair_computer(f"127.0.0.1:{server.port}", sync.devices.start_pairing()["code"])
    (computer,) = [item["id"] for item in view["computers"]]
    return app, server, sync, folder, mirror, computer


def test_the_paired_computer_hears_the_imported_book_as_if_it_were_a_project(tmp_path: Path) -> None:
    app, server, _sync, folder, _mirror, computer = _pair(tmp_path)
    try:
        books = [item for item in app.listen_library() if item.get("remote")]
        (book,) = books
        assert book["title"] == "Sách thử · Tập 1", "chỉ một cuốn: bản soi của máy thứ ba không đi qua A"
        path = app._listenable(book["id"])
        assert remote_books.remote_of(packages.manifest(path))["computer"] == computer
        audio = packages.chapter_file(path, 1)
        assert audio is not None and audio.read_bytes() == (folder / "chapters" / "00001_645.mp3").read_bytes()
        script = packages.script(path, 1)
        assert script["segments"][0]["kind"] == "heading"
        assert packages.cast(path)["characters"]
        assert packages.sample_file(path, 3) is not None
        done = app.remote_downloads.start(path, wait=True)
        assert done["state"] == "done" and done["filesDone"] == done["files"] > 0, done
        assert not list(path.rglob("*.part"))
        # B không chia sẻ lại: bản soi của A không hiện trong thư viện B trả cho máy đã ghép.
        b_sync = SyncApp(app.library, app.listening, Devices(tmp_path / "nay" / "devices.json"), "Máy B")
        assert b_sync.library_view() == []
        assert b_sync.book(book["id"]) is None
    finally:
        server.stop()


def test_the_paired_computer_reads_a_text_only_imported_book(tmp_path: Path) -> None:
    root = tmp_path / "kia" / "thu_vien"
    root.mkdir(parents=True)
    folder, _how = packages.import_file(_book_file(tmp_path), root, [], Fingerprints(tmp_path / "fp.json"))
    preferences = Preferences(tmp_path / "kia" / "preferences.json")
    preferences.update({"libraryRoot": str(root)})
    lib = Library(preferences)
    sync = SyncApp(lib, Listening(tmp_path / "kia" / "listening.json"), Devices(tmp_path / "kia" / "devices.json"), "Máy A")
    app, server, _sync, _folder, _mirror, _computer = _pair(tmp_path, (lib, sync, folder, folder))
    try:
        (book,) = [item for item in app.listen_library() if item.get("remote")]
        path = app._listenable(book["id"])
        chapters = packages.manifest(path)["chapters"]
        assert chapters and all(chapter.get("text") and not chapter.get("file") for chapter in chapters)
        text = packages.chapter_text(path, chapters[0]["id"])
        assert text and text.strip() == (folder / chapters[0]["text"]).read_text(encoding="utf-8").strip()
        assert app.listen_book(book["id"])["stage"] == "text"
    finally:
        server.stop()


def test_edits_from_the_other_computer_land_in_the_packages_own_edits_layer(tmp_path: Path) -> None:
    app, server, _sync, folder, _mirror, _computer = _pair(tmp_path)
    try:
        (book,) = [item for item in app.listen_library() if item.get("remote")]
        value = book["id"]
        path = app._listenable(value)
        app.rename(value, "Tên đặt ở máy B")
        book_edits.set_chapter_title(path, 1, "Chương mở đầu")
        book_wishes.request_pronunciation(path, "Lucien", "Lu-xi-en", now=1000.0)
        assert app.listen_book(value)["editsSync"]["pending"] == 3
        state = app.send_remote_edits(value)
        assert state["pending"] == 0 and state["last"]["state"] == "sent", state
        assert (state["last"]["applied"], state["last"]["waiting"], state["last"]["conflicts"]) == (2, 1, [])
        layer = book_edits.load(folder)
        assert layer["title"] == "Tên đặt ở máy B" and layer["chapters"]["1"]["title"] == "Chương mở đầu"
        assert book_wishes.count(layer["wishes"]) == 1, "ý muốn chờ Studio nằm trong lớp sửa của cuốn, không mất"
        assert app.listen_book(value)["title"] == "Tên đặt ở máy B", "B thấy sách theo bản mới của A"

        # Người nghe ở A đổi tên sau lần gửi trước, B lại đổi: bên đến sau thắng, nhưng báo.
        book_edits.set_title(folder, "Chủ máy A đặt lại")
        app.rename(value, "Máy B đặt lần hai")
        state = app.send_remote_edits(value)
        (conflict,) = state["last"]["conflicts"]
        assert conflict == ("Tên sách: máy kia (Máy A) đã đổi thành “Chủ máy A đặt lại” trước đó, "
                            "bản của bạn “Máy B đặt lần hai” đã thay vào")
        assert book_edits.load(folder)["title"] == "Máy B đặt lần hai"
    finally:
        server.stop()


def test_a_bad_edits_package_changes_nothing_in_a_package(tmp_path: Path) -> None:
    from abook.webui import edits_inbox

    _lib, sync, folder, _mirror = _holder(tmp_path)
    bad = tmp_path / "hong.zip"
    bad.write_bytes(b"khong phai zip")
    with pytest.raises(edits_inbox.InboundError):
        sync.receive_edits(folder, {"id": "abc", "name": "Pixel"}, bad)
    assert book_edits.is_empty(book_edits.load(folder))
    with pytest.raises(LookupError):
        sync.receive_edits(tmp_path, {"id": "abc", "name": "Pixel"}, bad)


def test_a_skipped_line_is_still_skipped_after_it_was_sent_for_an_imported_book(tmp_path: Path) -> None:
    """Máy A giữ cuốn nhập từ file không đưa `skip` vào manifest (sở thích người nghe từng máy): B bỏ dòng, gửi xong vẫn phải bỏ ở B."""
    app, server, _sync, folder, _mirror, _computer = _pair(tmp_path)
    try:
        (book,) = [item for item in app.listen_library() if item.get("remote")]
        value = book["id"]
        path = app._listenable(value)
        book_edits.set_skip_line(path, [1], "Dịch: Nhóm Lục Bình", True)
        assert app.listen_book(value)["editsSync"]["pending"] == 1
        state = app.send_remote_edits(value)
        assert state["last"]["state"] == "sent" and state["pending"] == 0, state
        assert book_edits.load(folder)["skip"] == {"1": ["Dịch: Nhóm Lục Bình"]}, "máy A nhận và giữ trong lớp sửa của cuốn"
        assert packages.edited_manifest(path)["chapters"][0]["skip"] == ["Dịch: Nhóm Lục Bình"], "B vẫn bỏ dòng ấy sau khi gửi"
    finally:
        server.stop()
