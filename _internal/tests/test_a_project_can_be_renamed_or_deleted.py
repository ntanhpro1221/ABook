"""Studio: đổi tên và xoá một dự án (soát UX 29-09: không có cách nào bỏ một dự án thử, hay sửa tên suy từ tên file).

Đổi tên chỉ đổi tên HIỆN - máy chủ giao diện không bao giờ ghi sổ của dây chuyền. Xoá chuyển cả thư mục dự án vào Thùng
rác (khôi phục được), không khi sách đang chạy, và chỉ từ chính máy này - Studio từ xa không có hai đường ấy."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tests.test_listener_speakers import _book


@pytest.fixture
def studio(tmp_path: Path):
    from ebook_reader.config import build_settings, save_settings
    from ebook_reader.webui.actions import FakeRunner
    from ebook_reader.webui.library import Preferences
    from ebook_reader.webui.listening import Listening
    from ebook_reader.webui.server import App, Server

    paths, _db = _book(tmp_path)
    save_settings(paths.settings, build_settings())
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    runner = FakeRunner()
    app = App(preferences=preferences, runner=runner, token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    try:
        yield paths, app, server, runner
    finally:
        server.stop()


def _call(server, method: str, path: str, body: dict | None = None):
    from tests.test_webui_listen_and_sync import _request

    status, data, _ = _request(server.port, method, path, headers={"X-Ebook-Token": "t"}, body=body)
    return status, json.loads(data or b"{}")


def test_a_rename_shows_everywhere_and_leaves_the_pipeline_book_alone(studio) -> None:
    from ebook_reader.webui.library import book_id
    from ebook_reader.webui.remote_studio import permitted

    paths, _app, server, _runner = studio
    path = f"/api/books/{book_id(paths.root)}"
    before = paths.db.read_bytes()
    status, data = _call(server, "PUT", path + "/title", {"title": "  Ma pháp\tthần   tọa \n"})
    assert status == 200 and data["title"] == "Ma pháp thần tọa", "gộp khoảng trắng, bỏ ký tự điều khiển"
    status, data = _call(server, "GET", "/api/library")
    assert [book["title"] for book in data["books"]] == ["Ma pháp thần tọa"], "thư viện thấy tên mới ngay (bộ đệm theo mốc file)"
    status, data = _call(server, "PUT", path + "/title", {"title": " \n "})
    assert status == 400 and "trống" in data["error"]
    assert paths.db.read_bytes() == before, "chỉ dây chuyền được ghi SQLite của sách"
    assert not permitted("PUT", path + "/title") and not permitted("DELETE", path), "Studio từ xa không đổi tên, không xoá"


def test_a_running_book_is_not_deleted(studio) -> None:
    from ebook_reader.webui.library import book_id

    paths, _app, server, runner = studio
    runner._running.add(str(paths.root.resolve()))
    status, data = _call(server, "DELETE", f"/api/books/{book_id(paths.root)}")
    assert status == 409 and "dừng sách" in data["error"]
    assert paths.root.is_dir()


def test_a_deleted_project_goes_to_the_recycle_bin_and_leaves_the_list(studio, monkeypatch: pytest.MonkeyPatch) -> None:
    from ebook_reader.webui import actions
    from ebook_reader.webui.library import book_id

    paths, app, server, _runner = studio
    moved: list[Path] = []

    def recycle(path: Path) -> None:  # không đụng Thùng rác thật của máy chạy test
        moved.append(path)
        shutil.rmtree(path)

    monkeypatch.setattr(actions, "move_to_recycle_bin", recycle)
    app.preferences.add_recent(paths.root)
    source = paths.root.parent / "001.txt"
    status, _data = _call(server, "DELETE", f"/api/books/{book_id(paths.root)}")
    assert status == 200 and moved == [paths.root.resolve()]
    status, data = _call(server, "GET", "/api/library")
    assert data["books"] == [] and app.preferences.get()["recents"] == []
    assert source.is_file(), "file truyện gốc nằm ngoài thư mục dự án - không bị đụng"
    status, _data = _call(server, "DELETE", f"/api/books/{book_id(paths.root)}")
    assert status == 404


def test_a_failed_move_says_what_to_close(studio, monkeypatch: pytest.MonkeyPatch) -> None:
    from ebook_reader.webui import actions
    from ebook_reader.webui.library import book_id

    paths, _app, server, _runner = studio

    def locked(_path: Path) -> None:
        raise OSError("SHFileOperationW trả 0x20")

    monkeypatch.setattr(actions, "move_to_recycle_bin", locked)
    status, data = _call(server, "DELETE", f"/api/books/{book_id(paths.root)}")
    assert status == 409 and "đang mở" in data["error"]
    assert paths.root.is_dir()
