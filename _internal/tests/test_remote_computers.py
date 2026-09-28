"""Máy tính nghe thẳng thư viện của máy tính KHÁC (mạng trạm, bước 3 - webui/remote_books.py).

Hai máy trong một bài: "máy kia" là cổng đồng bộ thật với một cuốn đã thu một chương; "máy này" ghép bằng đúng mã 6 số
điện thoại dùng, thấy cuốn ấy như một cuốn đã nhập ảo, và file (chương, văn bản đọc theo, nhân vật) được tải lần đầu cần
tới. Máy kia tắt: phần đã tải vẫn nghe được; thôi ghép: thư mục đệm biến mất.
"""
from __future__ import annotations

import json
from pathlib import Path

from ebook_reader.webui import packages
from ebook_reader.webui.library import Preferences, book_id
from ebook_reader.webui.listening import Listening
from ebook_reader.webui.remote_books import REMOTE_FOLDER
from ebook_reader.webui.server import App
from ebook_reader.webui.sync import Devices, SyncApp, SyncServer
from tests.test_webui_listen_and_sync import FakeRunner, library  # noqa: F401 - fixture dùng chung


def test_this_computer_listens_to_a_book_on_another_computer(library, tmp_path: Path) -> None:  # noqa: F811
    other_library, project, other_listening = library
    devices = Devices(tmp_path / "kia" / "devices.json")
    other = SyncServer(SyncApp(other_library, other_listening, devices, "Máy kia"), host="127.0.0.1", port=0).start()
    preferences = Preferences(tmp_path / "nay" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path / "nay" / "thu_vien")})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "nay" / "l.json"))
    try:
        code = devices.start_pairing()["code"]
        view = app.pair_computer(f"127.0.0.1:{other.port}", code)
        assert [computer["name"] for computer in view["computers"]] == ["Máy kia"]
        assert "token" not in json.dumps(view), "mã thiết bị không bao giờ ra giao diện"

        books = app.listen_library()
        (book,) = [item for item in books if item.get("remote")]
        assert book["remote"] == {"computer": "Máy kia"} and book["chaptersAvailable"] == 1
        path = app._listenable(book["id"])
        assert REMOTE_FOLDER in str(path) and packages.is_package(path)
        chapter = app.listen_book(book["id"])["chapters"][0]
        assert chapter["available"] is True, "chương máy kia có là nghe được, dù chưa tải"

        audio = packages.chapter_file(path, chapter["id"])
        remote_audio = next((project / "output" / "chapters").glob("*.mp3"))
        assert audio is not None and audio.read_bytes() == remote_audio.read_bytes(), "tải đúng file lần đầu cần tới"
        assert packages.script(path, chapter["id"])["segments"], "văn bản đọc theo cũng tải về"
        assert set(packages.cast(path)) >= {"characters", "extras"}
    finally:
        other.stop()

    app.refresh_remote(wait=True)
    (computer,) = app.computers_view()["computers"]
    assert computer["error"], "máy kia tắt: nói rõ, không làm hỏng thư viện"
    assert packages.chapter_file(path, chapter["id"]) == audio, "phần đã tải vẫn nghe được"
    assert any(item.get("remote") for item in app.listen_library())

    app.forget_computer(computer["id"])
    assert not path.exists() and app.computers_view()["computers"] == []
    assert not any(item.get("remote") for item in app.listen_library())


def test_the_place_you_are_listening_travels_both_ways_between_computers(library, tmp_path: Path) -> None:  # noqa: F811
    """Như điện thoại với máy tính: nghe ở máy này thì máy kia biết, nghe ở máy kia thì mở sách ở máy này thấy - gộp theo
    mốc thời gian từng phần, bên mới hơn thắng."""
    import time

    other_library, project, other_listening = library
    devices = Devices(tmp_path / "kia" / "devices.json")
    other = SyncServer(SyncApp(other_library, other_listening, devices, "Máy kia"), host="127.0.0.1", port=0).start()
    preferences = Preferences(tmp_path / "nay" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path / "nay" / "thu_vien")})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "nay" / "l.json"))
    try:
        app.pair_computer(f"127.0.0.1:{other.port}", devices.start_pairing()["code"])
        (book,) = [item for item in app.listen_library() if item.get("remote")]
        chapter = app.listen_book(book["id"])["chapters"][0]["id"]
        remote_id = book_id(project)

        app.listening.progress(book["id"], chapter, 42.0, 100.0)
        app.sync_remote_state(book["id"], wait=True)
        assert other_listening.get(remote_id)["last"]["seconds"] == 42.0, "máy kia biết máy này nghe tới đâu"

        time.sleep(0.05)
        other_listening.progress(remote_id, chapter, 77.0, 100.0)
        view = app.listen_book(book["id"])
        assert view["state"]["last"]["seconds"] == 77.0, "mở sách ở máy này thấy chỗ vừa nghe ở máy kia"
    finally:
        other.stop()


def test_pairing_refuses_a_bad_code_or_address_with_a_readable_reason(library, tmp_path: Path) -> None:  # noqa: F811
    import pytest

    from ebook_reader.webui.server import ApiError

    other_library, _project, other_listening = library
    devices = Devices(tmp_path / "kia" / "devices.json")
    other = SyncServer(SyncApp(other_library, other_listening, devices, "Máy kia"), host="127.0.0.1", port=0).start()
    preferences = Preferences(tmp_path / "nay" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path / "nay")})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "nay" / "l.json"))
    try:
        devices.start_pairing()
        with pytest.raises(ApiError, match="Mã ghép nối sai"):
            app.pair_computer(f"127.0.0.1:{other.port}", "000000" if devices.pairing()["code"] != "000000" else "111111")
        with pytest.raises(ApiError, match="mã 6 số"):
            app.pair_computer("", "12")
    finally:
        other.stop()
    assert app.computers_view()["computers"] == [] and book_id(tmp_path) != ""
