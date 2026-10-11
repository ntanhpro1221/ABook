"""File trạng thái hỏng không được làm mất dữ liệu người dùng im lặng (soát a28 lỗi 1, 2, 3, 6, 10, 14).

Trước đây: preferences.json / listening.json / devices.json cắt nửa thì app im lặng về mặc định và lần ghi kế ĐÈ lên - mất chỗ nghe, dấu
trang, cài đặt, máy đã ghép. `[1]` trong preferences.json làm máy chủ không khởi động. book_ids.key hỏng hay thư viện chuyển chỗ thì mọi mã
sách đổi - chỗ nghe mồ côi. Hai tiến trình cùng hồ sơ đè mất cập nhật của nhau.
"""
from __future__ import annotations

import json
import multiprocessing
import os
from pathlib import Path

import pytest

from abook.webui import library as library_module
from abook.webui import notices
from abook.webui.actions import FakeRunner
from abook.webui.library import Library, Preferences, book_id
from abook.webui.listening import Listening
from abook.webui.server import App, Server
from abook.webui.sync import Devices
from tests.test_webui_listen_and_sync import _request, make_project


@pytest.fixture(autouse=True)
def _fresh_notices():
    notices.NOTICES.clear()
    yield
    notices.NOTICES.clear()


def _kept(folder: Path, name: str) -> list[Path]:
    return sorted(folder.glob(f"{name}.hong-*"))


@pytest.mark.parametrize("content", [b'{"theme": "dark", "volume": 0.4', b"", b"x", b"\xff\xfe\x00"])
def test_a_damaged_preferences_file_is_kept_and_reported(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "preferences.json"
    path.write_bytes(content)
    preferences = Preferences(path)
    assert preferences.get()["theme"] == "system"
    kept = _kept(tmp_path, "preferences.json")
    assert len(kept) == 1 and kept[0].read_bytes() == content, "bản hỏng phải được giữ nguyên"
    assert any(kept[0].name in item["text"] for item in notices.NOTICES.all()), "báo một dòng, nói bản cũ ở đâu"
    preferences.update({"volume": 0.3})
    assert kept[0].read_bytes() == content, "lần ghi kế không được đè bản cũ"


@pytest.mark.parametrize("content", ["[1]", "null", "5", '"abc"'])
def test_preferences_that_are_not_an_object_never_stop_the_app(tmp_path: Path, content: str) -> None:
    path = tmp_path / "preferences.json"
    path.write_text(content, encoding="utf-8")
    preferences = Preferences(path)  # trước đây: TypeError -> máy chủ không khởi động
    assert preferences.get()["volume"] == 0.9
    assert len(_kept(tmp_path, "preferences.json")) == 1


def test_wrongly_typed_preferences_fall_back_one_key_at_a_time(tmp_path: Path) -> None:
    path = tmp_path / "preferences.json"
    path.write_text(json.dumps({"libraryRoot": 5, "theme": "tím", "volume": 0.4, "recents": "abc", "positions": [],
                                "syncEnabled": "yes", "playbackRate": True, "custom": {"x": 1}}), encoding="utf-8")
    preferences = Preferences(path)
    data = preferences.get()
    assert data["volume"] == 0.4, "khoá đúng kiểu giữ nguyên"
    assert isinstance(data["libraryRoot"], str) and data["libraryRoot"]
    assert (data["theme"], data["recents"], data["positions"], data["syncEnabled"], data["playbackRate"]) == ("system", [], {}, False, 1.0)
    assert data["custom"] == {"x": 1}, "khoá lạ không xét"
    assert len(_kept(tmp_path, "preferences.json")) == 1 and notices.NOTICES.all()
    assert json.loads(path.read_text(encoding="utf-8"))["volume"] == 0.4, "bản sạch được ghi lại ngay"
    Preferences(path)
    assert len(_kept(tmp_path, "preferences.json")) == 1, "lần mở sau không báo lại"
    Library(preferences).projects()  # libraryRoot 5 từng làm mọi yêu cầu 500


def test_preferences_refuse_values_of_the_wrong_kind(tmp_path: Path) -> None:
    preferences = Preferences(tmp_path / "preferences.json")
    before = preferences.get()["libraryRoot"]
    preferences.update({"libraryRoot": 5, "theme": "tím"})
    preferences.update({"libraryRoot": "   "})
    assert preferences.get()["libraryRoot"] == before and preferences.get()["theme"] == "system"


@pytest.mark.parametrize("content", [b'{"version": 2, "records": {"r-1"', b"", b"[1]", b'{"version": 2, "records": {"r": "x"}}'])
def test_a_damaged_listening_file_is_kept_not_overwritten(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "listening.json"
    path.write_bytes(content)
    listening = Listening(path)
    listening.progress("b" * 24, 1, 5.0, 100.0)  # lần ghi kế
    kept = _kept(tmp_path, "listening.json")
    assert len(kept) == 1 and kept[0].read_bytes() == content
    assert any("Hồ sơ nghe" in item["text"] for item in notices.NOTICES.all())


@pytest.mark.parametrize("content", [b'{"devices": {"ab', b"[1]", b"null", b'{"devices": {"x": "str"}}', b'{"devices": []}'])
def test_a_damaged_paired_devices_file_is_kept(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "devices.json"
    path.write_bytes(content)
    devices = Devices(path)
    assert devices.list() == []
    assert len(_kept(tmp_path, "devices.json")) == 1


def test_state_files_are_written_whole(tmp_path: Path) -> None:
    preferences = Preferences(tmp_path / "preferences.json")
    preferences.update({"volume": 0.5})
    listening = Listening(tmp_path / "listening.json")
    listening.progress("c" * 24, 2, 7.0, 100.0)
    assert json.loads((tmp_path / "preferences.json").read_text(encoding="utf-8"))["volume"] == 0.5
    assert json.loads((tmp_path / "listening.json").read_text(encoding="utf-8"))["links"]
    assert not list(tmp_path.glob("*.tmp")) and not list(tmp_path.glob("*.part"))


# ---- khoá mã sách --------------------------------------------------------------------------------------------


def test_a_damaged_book_id_key_comes_back_from_its_copy(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ABOOK_PREFERENCES", str(tmp_path / "data" / "preferences.json"))
    folder = tmp_path / "Sách"
    first = book_id(folder)
    key = tmp_path / "data" / library_module.ID_KEY_FILE
    assert (tmp_path / "data" / "book_ids.key.bak").is_file()
    for damage in (b"zz", b"", b"@NONE"):
        key.write_bytes(damage)
        library_module._ID_KEYS.clear()
        assert book_id(folder) == first, "khoá hỏng mà âm thầm đổi thì mọi chỗ nghe mồ côi"
        assert any(path.read_bytes() == damage for path in _kept(key.parent, key.name))
    assert notices.NOTICES.all()


def test_a_damaged_book_id_key_without_a_copy_is_reported(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ABOOK_PREFERENCES", str(tmp_path / "data" / "preferences.json"))
    key = tmp_path / "data" / library_module.ID_KEY_FILE
    key.parent.mkdir()
    key.write_bytes(b"zz")
    library_module._ID_KEYS.clear()
    value = book_id(tmp_path / "Sách")
    assert library_module.ID_PATTERN.fullmatch(value)
    assert len(_kept(key.parent, key.name)) == 1
    assert any("chỗ nghe" in item["text"] for item in notices.NOTICES.all())
    assert len(bytes.fromhex(key.read_text(encoding="ascii"))) == 32, "khoá mới đầy đủ"
    library_module._ID_KEYS.clear()
    assert book_id(tmp_path / "Sách") == value


# ---- thư viện chuyển chỗ -------------------------------------------------------------------------------------


def _app(tmp_path: Path, root: Path) -> App:
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(root)})
    return App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "listening.json"))


def test_moving_the_library_keeps_places_and_bookmarks(tmp_path: Path) -> None:
    root = tmp_path / "thu_vien"
    root.mkdir()
    project = make_project(root)
    app = _app(tmp_path, root)
    old = book_id(project)
    app.listening.progress(old, 1, 17.5, 100.0)
    app.listening.add_bookmark(old, 1, 12.0, "đoạn hay")
    app.preferences.remember_position(old, 1, 17.5, 100.0)
    moved = tmp_path / "thu_vien_moi"
    root.rename(moved)
    server = Server(app, port=0).start()
    try:
        status, _data, _ = _request(server.port, "PUT", "/api/preferences", headers={"X-Ebook-Token": "t"},
                                    body={"libraryRoot": str(moved)})
        assert status == 200
        status, _data, _ = _request(server.port, "PUT", "/api/preferences", headers={"X-Ebook-Token": "t"}, body={"libraryRoot": ""})
        assert status == 400, "thư viện rỗng tên không được nhận"
    finally:
        server.stop()
    new = book_id(moved / project.name)
    assert new != old
    state = app.listening.get(new)
    assert state["last"]["seconds"] == 17.5 and state["bookmarks"][0]["note"] == "đoạn hay"
    assert app.preferences.get()["positions"][new]["seconds"] == 17.5


def test_a_vanished_library_is_reported_and_not_recreated(tmp_path: Path) -> None:
    root = tmp_path / "thu_vien"
    root.mkdir()
    make_project(root)
    app = _app(tmp_path, root)
    assert app.library_view()["rootMissing"] is False  # app đang chạy, đã hiện thư viện
    root.rename(tmp_path / "doi_ten")
    assert app.library_view()["rootMissing"] is True
    source = tmp_path / "truyen.txt"
    source.write_text("Chương 1\n\nMột hai ba bốn năm sáu bảy tám chín mười.\n" * 30, encoding="utf-8")
    with pytest.raises(Exception) as caught:
        app.add_text_book(str(source))
    assert "thu_vien" in str(getattr(caught.value, "message", caught.value))
    assert not root.exists(), "nhập sách không được tự tạo lại thư mục thư viện rỗng"


def test_a_read_only_folder_is_named_not_dumped(tmp_path: Path) -> None:
    from abook.webui import humanize

    error = PermissionError(13, "Permission denied", str(tmp_path / "Truyện hay" / "names.json.part"))
    text = humanize.write_error(error)
    assert "Truyện hay" in text and "chỉ đọc" in text and "Cài đặt" in text
    assert str(tmp_path) not in text and "Errno" not in text


# ---- hai tiến trình cùng hồ sơ ------------------------------------------------------------------------------


def _other_process(folder: str) -> None:
    Listening(Path(folder) / "listening.json").add_bookmark("b" * 24, 3, 64.0, "của B")
    Preferences(Path(folder) / "preferences.json").update({"volume": 0.3})


def test_two_processes_on_one_profile_keep_both_changes(tmp_path: Path) -> None:
    listening = Listening(tmp_path / "listening.json")
    preferences = Preferences(tmp_path / "preferences.json")
    listening.progress("a" * 24, 1, 5.0, 100.0)
    preferences.update({"theme": "light"})
    process = multiprocessing.get_context("spawn").Process(target=_other_process, args=(str(tmp_path),))
    process.start()
    process.join(60)
    assert process.exitcode == 0
    listening.progress("a" * 24, 3, 100.0, 200.0)  # bên A ghi sau: không được đè dấu trang của B
    preferences.update({"playbackRate": 1.25})
    again = Listening(tmp_path / "listening.json")
    assert again.get("a" * 24)["last"]["seconds"] == 100.0
    assert again.get("b" * 24)["bookmarks"][0]["note"] == "của B"
    stored = Preferences(tmp_path / "preferences.json").get()
    assert (stored["theme"], stored["volume"], stored["playbackRate"]) == ("light", 0.3, 1.25)
    assert os.path.exists(tmp_path / "listening.json.lock")


# ---- sổ làm việc của dự án: bị giữ / hỏng / tạo dở ----------------------------------------------------------


def _row(app: App) -> dict:
    (book,) = app.library_view()["books"]
    return book


@pytest.mark.skipif(os.name != "nt", reason="khoá không chia sẻ kiểu Windows")
def test_a_project_held_by_another_program_is_not_called_broken(tmp_path: Path) -> None:
    import ctypes
    from ctypes import wintypes

    root = tmp_path / "thu_vien"
    root.mkdir()
    project = make_project(root)
    app = _app(tmp_path, root)
    create = ctypes.windll.kernel32.CreateFileW
    create.restype = wintypes.HANDLE
    handle = create(str(project / "project.sqlite3"), 0x80000000, 0, None, 3, 0x80, None)  # GENERIC_READ, không chia sẻ
    assert handle not in (None, wintypes.HANDLE(-1).value)
    try:
        row = _row(app)
    finally:
        ctypes.windll.kernel32.CloseHandle(wintypes.HANDLE(handle))
    assert row["brokenKind"] == "busy" and "chương trình khác" in row["broken"] and "hỏng" not in row["broken"]
    assert "brokenKind" not in _row(app), "nhả khoá thì tự về"


def test_a_damaged_project_offers_its_backup(tmp_path: Path) -> None:
    from abook.database import ProjectDB

    root = tmp_path / "thu_vien"
    root.mkdir()
    project = make_project(root)
    ProjectDB(project / "project.sqlite3")  # nâng cấp: dây chuyền chụp bản sao .pre-v*.bak
    database = project / "project.sqlite3"
    database.write_bytes(database.read_bytes()[:1000])
    app = _app(tmp_path, root)
    row = _row(app)
    assert row["brokenKind"] == "damaged" and row["backup"] is True and "bản sao" in row["broken"]
    server = Server(app, port=0).start()
    try:
        status, data, _ = _request(server.port, "POST", f"/api/books/{row['id']}/restore-backup", headers={"X-Ebook-Token": "t"})
    finally:
        server.stop()
    assert status == 200, data
    assert list(project.glob("project.sqlite3.hong-*")), "bản hỏng được giữ"
    assert _row(app)["title"] == "Sách thử · Tập 1"


def test_an_unfinished_project_says_how_to_fix_it(tmp_path: Path) -> None:
    import sqlite3

    root = tmp_path / "thu_vien"
    root.mkdir()
    project = make_project(root)
    with sqlite3.connect(project / "project.sqlite3") as connection:
        connection.execute("DELETE FROM book")
    connection.close()
    row = _row(_app(tmp_path, root))
    assert row["brokenKind"] == "unfinished" and "tạo lại" in row["broken"] and str(tmp_path) not in row["broken"]


# ---- rác sau khi tắt ngang ------------------------------------------------------------------------------------------------


def test_leftovers_of_cut_imports_exports_and_downloads_are_swept(tmp_path: Path) -> None:
    import time as clock

    from abook.webui import export_leftovers

    library, imported, out, scratch, music = (tmp_path / "tv", tmp_path / "tv" / "Sách đã nhập", tmp_path / "xuat", tmp_path / "tmp",
                                              tmp_path / "music")
    for folder in (imported, out, scratch, music):
        folder.mkdir(parents=True)
    staging = imported / ".truyen lon (8ec4d63f).b5d05af4.part"
    (staging / "texts").mkdir(parents=True)
    (staging / "texts" / "1.txt").write_text("x", encoding="utf-8")
    book_part = out / ".Truyện thử.abook.ccf6ac59.part"
    book_part.write_bytes(b"x")
    text_scratch = scratch / "abook-text-ab12cd_9"
    text_scratch.mkdir()
    track = music / "0f9f.fa34a437.part"
    track.write_bytes(b"x")
    lone_old = imported / ".Sách mồ côi.1a2b3c4d.old"
    lone_old.mkdir()
    twin = imported / "Sách đủ"
    twin.mkdir()
    twin_old = imported / ".Sách đủ.5e6f7a8b.old"
    twin_old.mkdir()
    keep = [imported / "ghi chu.part", out / "Sach.abook", scratch / "abook-text-x", music / "bai.mp3"]
    for path in keep:
        path.write_bytes(b"x")
    later = clock.time() + 2 * export_leftovers.CRASH_AGE

    assert export_leftovers.sweep_crashed([out], [library, imported], scratch, music, now=clock.time()) == [], "còn mới: không đụng"
    removed = export_leftovers.sweep_crashed([out], [library, imported], scratch, music, now=later)

    assert not any(path.exists() for path in (staging, book_part, text_scratch, track, twin_old))
    assert (imported / "Sách mồ côi").is_dir() and not lone_old.exists(), "bản .old không có bản chính: trả lại tên, không xoá"
    assert all(path.exists() for path in keep) and twin.is_dir()
    assert len(removed) == 6


@pytest.mark.parametrize("content", [b'{"title": "Chuy', b"", b"[1]"])
def test_a_cut_epub_sidecar_is_redone_not_a_permanent_import_error(tmp_path: Path, content: bytes) -> None:
    """Lỗi 17: sidecar EPUB cụt (tắt ngang lúc ghi) làm nhập lại đúng file ấy lỗi mãi. Giờ tách lại; sidecar ghi nguyên tử."""
    from abook import importers
    from tests.import_fixtures import FIXTURES

    folder, info = importers.extract(FIXTURES / "epub3.epub", tmp_path / "lib")
    (folder / importers.SIDECAR).write_bytes(content)
    again, same = importers.extract(FIXTURES / "epub3.epub", tmp_path / "lib")
    assert again == folder and same == info
    assert json.loads((folder / importers.SIDECAR).read_text(encoding="utf-8")) == info
    assert not list(folder.glob("*.tmp")) and not list(folder.glob("*.part"))
