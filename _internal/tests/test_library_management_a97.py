"""Quản lý thư viện (soát a97): đổi thư viện khác không chuyển hồ sơ nghe, thư viện mặc định biến mất vẫn báo, xoá không dời dự án vừa
được Bắt đầu, liên kết bộ truyện giữ qua máy nhận, phiên bản bìa theo nội dung."""
from __future__ import annotations

import io
import json
import os
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from abook.webui import book_edits, covers, packages, store
from abook.webui.library import Library, Preferences, book_id
from abook.webui.listening import Listening
from abook.webui.server import ApiError, App, Handler
from tests.test_webui_listen_and_sync import make_project


def bare_app(tmp_path, monkeypatch, root):
    monkeypatch.setenv("ABOOK_PREFERENCES", str(tmp_path / "prefs/preferences.json"))
    app = object.__new__(App)
    app.preferences = Preferences(tmp_path / "prefs/preferences.json")
    app.preferences.update({"libraryRoot": str(root)})
    app.library = Library(app.preferences)
    app.listening = Listening(tmp_path / "prefs/listening.json")
    return app


def png(color, size=(128, 128)):
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, "PNG")
    return out.getvalue()


# ---- C1 -----------------------------------------------------------------------------------------------------------------


def test_switching_to_another_library_keeps_each_books_own_listening_state(tmp_path, monkeypatch):
    first, second = tmp_path / "lib-A", tmp_path / "lib-B"
    first.mkdir()
    second.mkdir()
    a = make_project(first, "Dế Mèn phiêu lưu ký")
    b = make_project(second, "Tắt đèn")  # cùng đường tương đối sach_thu, nội dung khác
    (b / "output/chapters/00001_645.mp3").write_bytes(b"DIFFERENT-AUDIO")
    app = bare_app(tmp_path, monkeypatch, first)
    old_id, new_id = book_id(a), book_id(b)
    app.listening.progress(old_id, 1, 17.5, 100)
    app.listening.add_bookmark(old_id, 1, 12, "Dế Mèn gặp Dế Choắt")
    app.preferences.remember_position(old_id, 1, 17.5, 100)
    request = SimpleNamespace(app=app, _body=lambda: {"libraryRoot": str(second)}, _send_json=lambda *args: None)
    Handler.put_preferences(request, {})
    assert store.summarize(b)["title"] == "Tắt đèn"
    assert app.listening.get(old_id)["bookmarks"][0]["note"] == "Dế Mèn gặp Dế Choắt"
    assert not app.listening.get(new_id).get("bookmarks") and app.listening.get(new_id).get("last") is None
    positions = app.preferences.get()["positions"]
    assert old_id in positions and new_id not in positions


def test_real_library_move_still_keeps_the_listening_state(tmp_path, monkeypatch):
    root = tmp_path / "before"
    root.mkdir()
    project = make_project(root)
    app = bare_app(tmp_path, monkeypatch, root)
    old_id = book_id(project)
    app.listening.progress(old_id, 1, 17.5, 100)
    moved = tmp_path / "after"
    root.rename(moved)
    app.preferences.update({"libraryRoot": str(moved)})
    app.adopt_moved_library(root)
    assert app.listening.get(book_id(moved / project.name))["last"]["seconds"] == 17.5


# ---- V4 -----------------------------------------------------------------------------------------------------------------


def test_previously_seen_default_library_that_vanishes_is_reported(tmp_path, monkeypatch):
    home = tmp_path / "fake-home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    root = home / "Audiobooks"
    root.mkdir(parents=True)
    make_project(root)
    app = bare_app(tmp_path, monkeypatch, root)
    assert app.library.projects()
    assert app.preferences.get()["libraryRootSeen"] == str(root)
    root.rename(home / "Audiobooks-moved")
    assert app.library.root_missing() is True
    with pytest.raises(ApiError):
        app.require_library_root()


def test_default_library_never_seen_is_still_a_first_run(tmp_path, monkeypatch):
    home = tmp_path / "fake-home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    app = bare_app(tmp_path, monkeypatch, home / "Audiobooks")
    assert app.library.root_missing() is False
    app.require_library_root()


# ---- V5 -----------------------------------------------------------------------------------------------------------------


def _delete_race_app(tmp_path, monkeypatch, project_root):
    app = bare_app(tmp_path, monkeypatch, project_root)
    app.read_only = False
    app.studio = None
    app._queue_lock = threading.RLock()
    app._deleting = set()
    app.queue = []
    state = {"starting": False}
    app.runner = SimpleNamespace(running=lambda path: False)

    def reserve(path):
        state["starting"] = True
        return True

    app.jobs = SimpleNamespace(starting=lambda path: state["starting"], reserve=reserve)
    app.summary = lambda path: {"starting": state["starting"]}
    app._launch = lambda path, **kwargs: None  # giữ khởi động trước khi có worker / file mở
    return app, state


def test_start_arriving_during_a_delete_is_refused_and_the_project_is_not_half_taken(tmp_path, monkeypatch):
    root = tmp_path / "library"
    root.mkdir()
    project = make_project(root)
    app, state = _delete_race_app(tmp_path, monkeypatch, root)
    identifier = book_id(project)
    checked, started = threading.Event(), threading.Event()
    errors = []

    def dequeue(value):
        checked.set()
        assert started.wait(3)
        return False

    app._dequeue = dequeue
    held = root / ".scratch-held-project"

    def discard(folder, *args, **kwargs):
        folder.rename(held)  # chỉ trong thư mục thử, không đụng Thùng rác thật
        return "scratch-token"

    app._discard = discard

    def delete():
        try:
            app.delete(identifier, undo=True)
        except Exception as error:  # noqa: BLE001
            errors.append(error)

    thread = threading.Thread(target=delete)
    thread.start()
    refused = None
    try:
        assert checked.wait(3)
        try:
            app.start(identifier, now=True)
        except ApiError as error:
            refused = error
    finally:
        started.set()
        thread.join(3)
    assert not thread.is_alive() and errors == []
    assert refused is not None and state["starting"] is False  # Bắt đầu tới giữa lúc xoá: bị từ chối, không giữ lượt khởi động
    assert held.is_dir() and not project.exists()
    assert app._deleting == set()


def test_delete_refuses_when_a_start_already_holds_the_project(tmp_path, monkeypatch):
    root = tmp_path / "library"
    root.mkdir()
    project = make_project(root)
    app, state = _delete_race_app(tmp_path, monkeypatch, root)
    app._dequeue = lambda value: False
    app._discard = lambda *args, **kwargs: pytest.fail("không được dời dự án đang được khởi động")
    state["starting"] = True
    with pytest.raises(ApiError):
        app.delete(book_id(project), undo=True)
    assert project.is_dir() and app._deleting == set()


# ---- T2 -----------------------------------------------------------------------------------------------------------------


def test_two_project_covers_in_one_second_get_different_urls(tmp_path, monkeypatch):
    real_replace = os.replace
    times = iter([1730000000.1, 1730000000.8, 1730000000.9])

    def replace(source, target):
        real_replace(source, target)
        if Path(target).name == "cover.jpg":
            stamp = next(times)
            os.utime(target, (stamp, stamp))

    monkeypatch.setattr(covers.os, "replace", replace)
    covers.save_cover_bytes(tmp_path, png("red"))
    first = covers.cover_view(tmp_path, "abc")
    covers.save_cover_bytes(tmp_path, png("blue"))
    second = covers.cover_view(tmp_path, "abc")
    assert first["url"] != second["url"]
    # Cùng một ảnh thì cùng phiên bản (điện thoại tính cùng công thức).
    covers.save_cover_bytes(tmp_path, png("blue"))
    assert covers.cover_view(tmp_path, "abc")["url"] == second["url"]


def test_package_covers_in_one_second_get_different_urls(tmp_path):
    book_edits.set_cover(tmp_path, png("red"))
    first = book_edits.cover_view(tmp_path, "abc")
    book_edits.set_cover(tmp_path, png("blue"))
    assert first["url"] != book_edits.cover_view(tmp_path, "abc")["url"]
    assert 0 <= first["version"] < covers.VERSION_MODULUS  # lớp sửa nhận phiên bản tới 10**10


def test_content_version_is_a_stable_function_of_the_bytes():
    assert covers.content_version(b"abc") == covers.content_version(b"abc") != covers.content_version(b"abd")
    # Đối chiếu với bản Kotlin (Store.kt coverVersion): 8 byte đầu SHA-256 big-endian, chia dư 10^10.
    assert covers.content_version(b"abc") == int.from_bytes(bytes.fromhex("ba7816bf8f01cfea"), "big") % 10**10


# ---- V2 -----------------------------------------------------------------------------------------------------------------


def _remote_book(folder: Path, identifier: str, title: str, computer: str, series=None) -> None:
    folder.mkdir(parents=True)
    raw = {"format": "abook-book/1", "id": identifier, "title": title, "chaptersTotal": 1, "complete": True, "narrator": "Đức Trí",
           "chapters": [{"id": 1, "index": 1, "title": "Chương 1", "available": True, "file": "chapters/1.mp3", "duration": 100}],
           "package": {"remote": {"computer": computer, "book": identifier}, "files": {}}}
    if series:
        raw["series"] = series
    (folder / "book.json").write_text(json.dumps(raw), encoding="utf-8")


def test_remote_package_keeps_its_series_link_when_the_part_is_renamed(tmp_path):
    shelf = tmp_path / "library" / "Trên máy khác" / "May A (paired-p)"
    _remote_book(shelf / "Gốc (aaaaaaaa)", "remote-first", "Bộ truyện", "paired-pc")
    second = shelf / "Ngày trở về (bbbbbbbb)"
    _remote_book(second, "remote-second", "Ngày trở về", "paired-pc", {"root": "remote-first", "part": 2})
    result = packages.listen(second, "local-second", {}, with_chapters=False)
    assert result["series"] == {"root": book_id(shelf / "Gốc (aaaaaaaa)"), "part": 2}


def test_remote_package_series_root_is_namespaced_when_the_first_part_is_not_here(tmp_path):
    second = tmp_path / "received"
    _remote_book(second, "remote-second", "Ngày trở về", "paired-pc", {"root": "remote-first", "part": 2})
    result = packages.listen(second, "local-second", {}, with_chapters=False)
    assert result["series"] == {"root": "paired-pc:remote-first", "part": 2}


def test_package_without_a_series_link_has_none(tmp_path):
    folder = tmp_path / "received"
    _remote_book(folder, "remote-one", "Một mình", "paired-pc")
    assert packages.listen(folder, "x", {}, with_chapters=False)["series"] is None


# ---- V1 -----------------------------------------------------------------------------------------------------------------


def test_renaming_a_book_changes_only_the_metadata_stamp_phones_compare(tmp_path, monkeypatch):
    from abook.webui import sync
    from abook.webui.sync import Devices, SyncApp

    root = tmp_path / "library"
    root.mkdir()
    project = make_project(root, "Tên cũ")
    app = bare_app(tmp_path, monkeypatch, root)
    sharer = SyncApp(app.library, app.listening, Devices(tmp_path / "devices.json"), "Máy thử")
    identifier = book_id(project)
    before = sync.manifest(project, identifier, app.listening)
    listed_before = sharer.library_view()[0]
    store.set_display_title(project, "Tên mới")
    after = sync.manifest(project, identifier, app.listening)
    listed_after = sharer.library_view()[0]
    assert before["metaVersion"] != after["metaVersion"]
    assert (before["audioVersion"], before["version"]) == (after["audioVersion"], after["version"])  # audio không đổi: không bắt tải lại
    assert listed_before["metaVersion"] == before["metaVersion"] and listed_after["metaVersion"] == after["metaVersion"]
    assert after["metaVersion"] == sync.listen_view.metadata_version(after) and after["metaVersion"] == sync.manifest(project, identifier, app.listening)["metaVersion"]


def test_metadata_version_covers_author_narrator_series_and_chapter_titles():
    from abook.webui.listen_view import metadata_version

    base = {"title": "A", "author": "T", "narrator": "N", "series": {"root": "r", "part": 2},
            "chapters": [{"id": 1, "title": "Một", "subtitle": "", "fullTitle": "Chương 1 Một"}]}
    seen = {metadata_version(base)}
    for change in ({"title": "B"}, {"author": "U"}, {"narrator": "M"}, {"series": {"root": "r", "part": 3}}, {"series": None},
                   {"chapters": [{"id": 1, "title": "Hai", "subtitle": "", "fullTitle": "Chương 1 Hai"}]}):
        seen.add(metadata_version({**base, **change}))
    assert len(seen) == 7
    assert metadata_version({**base, "duration": 5, "version": "x"}) == metadata_version(base)
