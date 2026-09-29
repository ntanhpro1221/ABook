"""Tự chọn đường (feat/auto-route): lời đáp ghép kèm các đường tới máy tính - địa chỉ LAN + cổng đồng bộ, và địa chỉ
Bluetooth khi cổng Bluetooth đang nghe. Điện thoại ghép một lần, rồi dùng Wi-Fi khi được, Bluetooth khi không."""
from __future__ import annotations

import json
from pathlib import Path

from ebook_reader.webui.actions import FakeRunner
from ebook_reader.webui.server import App
from tests.test_webui_listen_and_sync import _request, library  # noqa: F401 - fixture dùng chung


def test_the_pairing_answer_names_every_way_back_to_this_computer(library, tmp_path: Path) -> None:  # noqa: F811
    lib, _project, listening = library
    app = App(preferences=lib.preferences, runner=FakeRunner(), token="t", listening=listening)
    app.sync_host, app.sync_port = "127.0.0.1", 0
    app.set_sync(True)
    try:
        code = app.devices.start_pairing()["code"]
        status, data, _ = _request(app.sync_server.port, "POST", "/sync/v1/pair", body={"code": code, "device": "Pixel"})
        reply = json.loads(data)
        assert status == 200 and reply["token"]
        assert reply["routes"]["port"] == app.sync_server.port
        assert reply["routes"]["lan"] == [], "chỉ nghe 127.0.0.1: không có địa chỉ LAN nào để đưa"
        assert reply["routes"]["bluetooth"] == "", "Bluetooth không nghe: không hứa đường Bluetooth"

        class Radio:
            @staticmethod
            def view() -> dict:
                return {"running": True, "address": "AA:BB:CC:DD:EE:FF"}

            @staticmethod
            def stop() -> None:
                return None

        app.bluetooth = Radio()
        assert app.routes()["bluetooth"] == "AA:BB:CC:DD:EE:FF"
        app.sync_host = "0.0.0.0"
        assert "127.0.0.1" not in app.routes()["lan"]
    finally:
        app.close()


def test_the_library_listing_repeats_the_routes(library, tmp_path: Path) -> None:  # noqa: F811
    """Đường chỉ báo lúc ghép thì địa chỉ có SAU đó (cài Tailscale sau khi ghép) không bao giờ tới điện thoại: danh sách
    thư viện - điện thoại hỏi mỗi lần mở - mang lại các đường, như lời đáp ghép."""
    lib, _project, listening = library
    app = App(preferences=lib.preferences, runner=FakeRunner(), token="t", listening=listening)
    app.sync_host, app.sync_port = "127.0.0.1", 0
    app.set_sync(True)
    try:
        code = app.devices.start_pairing()["code"]
        _status, data, _ = _request(app.sync_server.port, "POST", "/sync/v1/pair", body={"code": code, "device": "Pixel"})
        token = json.loads(data)["token"]
        status, data, _ = _request(app.sync_server.port, "GET", "/sync/v1/library", token)
        reply = json.loads(data)
        assert status == 200 and reply["routes"] == app.routes()
    finally:
        app.close()
