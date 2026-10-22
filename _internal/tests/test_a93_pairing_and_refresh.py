"""a93 #2 + #3: ghép lại cùng máy ở địa chỉ khác vẫn là một máy; sách đã mất bên máy kia được dọn khi chưa tải."""
from __future__ import annotations

from pathlib import Path

from abook.webui import remote_books
from abook.webui.library import Preferences
from abook.webui.listening import Listening
from abook.webui.server import App
from abook.webui.sync import Devices, SyncApp, SyncServer
from tests.test_webui_listen_and_sync import FakeRunner, library  # noqa: F401


def _pair(library, tmp_path: Path):
    other_library, _project, other_listening = library
    devices = Devices(tmp_path / "kia" / "devices.json")
    other = SyncServer(SyncApp(other_library, other_listening, devices, "May kia"), host="127.0.0.1", port=0).start()
    preferences = Preferences(tmp_path / "nay" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path / "nay" / "thu_vien")})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "nay" / "l.json"))
    return other, devices, app


def _virtual_books(app) -> list[dict]:
    return [b for b in app.listen_library() if b.get("remote")]


def test_pairing_the_same_machine_at_a_new_address_keeps_one_computer(library, tmp_path):
    other, devices, app = _pair(library, tmp_path)
    try:
        app.pair_computer(f"127.0.0.1:{other.port}", devices.start_pairing()["code"])
        first = app.computers_view()["computers"]
        assert len(first) == 1
        key = first[0]["id"]
        app.refresh_remote(wait=True)
        before = [b["id"] for b in _virtual_books(app)]
        assert before
        app.pair_computer(f"localhost:{other.port}", devices.start_pairing()["code"])  # cùng máy, cùng chứng chỉ, địa chỉ khác
        computers = app.computers_view()["computers"]
        assert [c["id"] for c in computers] == [key], "cùng vân tay chứng chỉ -> cùng một bản ghi"
        assert computers[0]["host"] == "localhost"
        assert len(devices.list()) == 1
        app.refresh_remote(wait=True)
        assert [b["id"] for b in _virtual_books(app)] == before, "sách ảo không nhân đôi, mã sách giữ nguyên"
        assert app.computers.get(key)["host"] == "localhost" and app.computers.get(key)["token"]
    finally:
        other.stop()


def test_a_book_the_other_machine_no_longer_lists_is_dropped_unless_downloaded(library, tmp_path, monkeypatch):
    other, devices, app = _pair(library, tmp_path)
    try:
        app.pair_computer(f"127.0.0.1:{other.port}", devices.start_pairing()["code"])
        app.refresh_remote(wait=True)
        assert len(_virtual_books(app)) == 1
        root = tmp_path / "nay" / "thu_vien"
        package = next((root / remote_books.REMOTE_FOLDER).rglob("book.json")).parent
        # Máy kia mất cuốn, nhưng máy này đã tải một chương về: giữ.
        (package / "chapters").mkdir()
        (package / "chapters" / "00001.mp3").write_bytes(b"ID3")
        monkeypatch.setattr(SyncApp, "library_view", lambda self: [])
        app.refresh_remote(wait=True)
        assert package.is_dir() and len(_virtual_books(app)) == 1
        # Chưa tải gì (chỉ sổ + bìa): dọn.
        (package / "chapters" / "00001.mp3").unlink()
        (package / "chapters").rmdir()
        app.refresh_remote(wait=True)
        assert not package.exists() and _virtual_books(app) == []
    finally:
        other.stop()


def test_a_failed_refresh_removes_nothing(library, tmp_path):
    other, devices, app = _pair(library, tmp_path)
    try:
        app.pair_computer(f"127.0.0.1:{other.port}", devices.start_pairing()["code"])
        app.refresh_remote(wait=True)
        before = _virtual_books(app)
        assert len(before) == 1
        other.stop()  # máy kia tắt: lần làm mới lỗi
        app.refresh_remote(wait=True)
        assert [b["id"] for b in _virtual_books(app)] == [b["id"] for b in before]
    finally:
        other.stop()
