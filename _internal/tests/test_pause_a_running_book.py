"""Studio: "Tạm dừng" / "Tiếp tục" một cuốn đang chạy, và máy tự tạm dừng khi rút sạc (power_source).

Tạm dừng giữ tiến trình sống - dây chuyền đứng ở checkpoint kế rồi làm tiếp đúng chỗ ấy - nên an toàn cả giữa pha phân tích,
nơi "Dừng" rồi chạy lại là ra một quyển sách khác (AGENTS.md). Trang sách phải nói đang tạm dừng vì sao, không nói "Đã dừng"."""
from __future__ import annotations

import json

import pytest

from tests.test_listener_speakers import _book


@pytest.fixture
def studio(tmp_path):
    from ebook_reader.config import build_settings, save_settings
    from ebook_reader.webui.actions import FakeRunner
    from ebook_reader.webui.library import Preferences
    from ebook_reader.webui.listening import Listening
    from ebook_reader.webui.server import App, Server

    paths, db = _book(tmp_path)
    save_settings(paths.settings, build_settings())
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    runner = FakeRunner()
    app = App(preferences=preferences, runner=runner, token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    try:
        yield paths, db, server, runner
    finally:
        server.stop()


def _call(server, method: str, path: str, body: dict | None = None):
    from tests.test_webui_listen_and_sync import _request

    status, data, _ = _request(server.port, method, path, headers={"X-Ebook-Token": "t"}, body=body)
    return status, json.loads(data or b"{}")


def test_pausing_needs_a_running_book(studio) -> None:
    from ebook_reader.webui.library import book_id

    paths, _db, server, _runner = studio
    status, data = _call(server, "POST", f"/api/books/{book_id(paths.root)}/pause", {"paused": True})
    assert status == 409 and "không đang chạy" in data["error"]


def test_the_listener_pauses_and_continues_a_running_book(studio) -> None:
    from ebook_reader.webui.library import book_id

    paths, db, server, runner = studio
    runner._running.add(str(paths.root.resolve()))
    path = f"/api/books/{book_id(paths.root)}"

    status, data = _call(server, "POST", path + "/pause", {"paused": True})
    assert status == 202 and data["paused"] == "listener"
    assert data["statusLabel"] == "Đang tạm dừng…", "dây chuyền chưa tới checkpoint: còn làm nốt việc dở"

    db.update_book(status="paused", stage="paused")  # dây chuyền đã đứng (Pipeline._wait_pause_or_stop)
    status, data = _call(server, "GET", path)
    data = data["book"]
    assert data["paused"] == "listener" and data["statusLabel"] == "Đã tạm dừng"
    assert data["phase"] != "stopped", "tiến trình còn sống - không phải 'Đã dừng'"

    status, data = _call(server, "POST", path + "/pause", {"paused": False})
    assert status == 202 and data["paused"] is None


def test_a_book_paused_for_the_battery_says_so(studio) -> None:
    from ebook_reader.webui.library import book_id

    paths, db, server, runner = studio
    runner._running.add(str(paths.root.resolve()))
    runner._paused[str(paths.root.resolve())] = "battery"
    db.update_book(status="paused", stage="paused")
    status, data = _call(server, "GET", f"/api/books/{book_id(paths.root)}")
    data = data["book"]
    assert data["paused"] == "battery"
    assert data["statusLabel"] == "Tạm dừng · máy đang chạy pin"
    assert data["eta"] is None


def test_the_phone_can_pause_through_the_remote_studio() -> None:
    from ebook_reader.webui.remote_studio import permitted

    assert permitted("POST", "/api/books/abc123/pause")


def test_a_paused_book_whose_process_died_reads_as_interrupted_mid_phase(tmp_path) -> None:
    """Máy tắt khi đang tạm dừng: sổ còn status "paused". Trang sách nói tạm ngưng ĐÚNG pha, để người dùng biết (pha phân
    tích) chạy tiếp là ra sách khác."""
    from ebook_reader.webui import store

    paths, db = _book(tmp_path)
    db.update_book(status="paused", stage="paused")
    with db.connect() as connection:
        connection.execute("UPDATE segments SET status='pending', wav_path=NULL, wav_sha256=NULL WHERE seq >= 2")
    summary = store.summarize(paths.root, running=False)
    assert summary["phase"] == "analysis"
    assert summary["interrupted"] is True
    assert summary["statusLabel"] == "Tạm ngưng lúc phân tích truyện"

    with db.connect() as connection:
        connection.execute("UPDATE segments SET status='verified', wav_path='take.wav', wav_sha256='sha'")
    assert store.summarize(paths.root, running=False)["phase"] == "synthesis"


def test_the_setting_is_saved_with_the_other_preferences(tmp_path, monkeypatch) -> None:
    from ebook_reader import power_source
    from ebook_reader.webui.library import Preferences

    preferences = Preferences(tmp_path / "preferences.json")
    assert preferences.get()["pauseOnBattery"] is True
    preferences.update({"pauseOnBattery": False})
    monkeypatch.setenv("EBOOK_READER_PREFERENCES", str(tmp_path / "preferences.json"))
    assert power_source.pause_on_battery_enabled() is False, "supervisor đọc đúng file, đúng khoá"


def test_the_settings_screen_can_turn_it_off(studio) -> None:
    _paths, _db, server, _runner = studio
    status, data = _call(server, "PUT", "/api/preferences", {"pauseOnBattery": False})
    assert status == 200 and data["pauseOnBattery"] is False
    status, data = _call(server, "PUT", "/api/preferences", {"pauseOnBattery": "no"})
    assert data["pauseOnBattery"] is False, "giá trị hỏng không được ghi"
    status, data = _call(server, "PUT", "/api/preferences", {"pauseOnBattery": True})
    assert data["pauseOnBattery"] is True


def test_the_supervisor_reads_the_same_preferences_file_as_the_app(tmp_path, monkeypatch) -> None:
    """power_source chép cách tìm preferences.json của webui.library (supervisor không nhập webui) - hai bên phải trùng."""
    from ebook_reader import power_source
    from ebook_reader.webui import library

    monkeypatch.delenv("EBOOK_READER_PREFERENCES", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert power_source._preferences_path() == library.preferences_path()
    monkeypatch.setenv("EBOOK_READER_PREFERENCES", str(tmp_path / "rieng.json"))
    assert power_source._preferences_path() == library.preferences_path()
