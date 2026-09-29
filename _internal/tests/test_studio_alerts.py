"""Điện thoại báo "sách xong", "có việc mới cần duyệt", "dừng vì lỗi" (StudioAlerts.kt): máy tính trả trạng thái sản xuất
gọn qua cổng đồng bộ (`GET /sync/v1/studio`) - CHỈ cho thiết bị được phép điều khiển sản xuất, khi công tắc Studio từ xa
đang bật (cùng hai điều kiện với Studio từ xa). Điện thoại tự so với lần hỏi trước; máy tính không nhớ gì cho từng máy.
"""
from __future__ import annotations

import json
from pathlib import Path

from ebook_reader.webui.remote_studio import StudioGate
from ebook_reader.webui.sync import Devices, SyncApp, SyncServer
from tests.test_webui_listen_and_sync import _request, library  # noqa: F401 - fixture dùng chung


def test_the_phone_reads_a_compact_production_status_only_when_allowed(library, tmp_path: Path) -> None:  # noqa: F811
    lib, project, listening = library
    devices = Devices(tmp_path / "devices.json")
    switch = {"on": False}
    gate = StudioGate(allowed=lambda: switch["on"], port=lambda: 0, token=None, static_dir=tmp_path)
    app = SyncApp(lib, listening, devices, "Máy thử", studio=gate)
    server = SyncServer(app, host="127.0.0.1", port=0).start()
    try:
        code = devices.start_pairing()["code"]
        _status, data, _ = _request(server.port, "POST", "/sync/v1/pair", body={"code": code, "device": "Pixel"})
        token = json.loads(data)["token"]
        status, data, _ = _request(server.port, "GET", "/sync/v1/studio", token)
        assert status == 403 and "chưa cho phép" in json.loads(data)["error"], "công tắc Studio từ xa đang tắt"
        switch["on"] = True
        status, data, _ = _request(server.port, "GET", "/sync/v1/studio", token)
        assert status == 403 and "điều khiển sản xuất" in json.loads(data)["error"], "ghép lúc công tắc tắt: chỉ quyền nghe"
        assert devices.set_studio(devices.list()[0]["id"], True)
        status, data, _ = _request(server.port, "GET", "/sync/v1/studio", token)
        view = json.loads(data)
        assert status == 200 and view["name"] == "Máy thử" and view["at"] > 0
        assert "onBattery" in view, "điện thoại báo máy tuột sạc cả khi không có sách nào chạy"
        (book,) = view["books"]
        assert {"id", "title", "phase", "statusLabel", "running", "paused", "chapters", "work", "lastError"} <= set(book)
        assert book["paused"] is None
        assert book["chapters"]["total"] >= 1 and book["running"] is False
        assert book["work"] is None, "sách đời cũ của fixture không dựng được hộp việc: 'không biết', vẫn có mặt"
        status, _data, _ = _request(server.port, "GET", "/sync/v1/studio")
        assert status == 401, "chưa ghép thì không thấy gì"
    finally:
        server.stop()


def test_the_work_count_is_recomputed_only_when_the_book_changes(library, monkeypatch) -> None:  # noqa: F811
    """Điện thoại hỏi mỗi 15 phút: dựng lại hộp việc (đọc cả sách) chỉ khi DB hay file yêu cầu của người nghe đổi."""
    from ebook_reader.webui import work_items as module

    lib, project, listening = library
    calls = []

    def counting(path):
        calls.append(path)
        return {"items": [{"kind": "speaker"}] * 3}

    monkeypatch.setattr(module, "work_items", counting)
    app = SyncApp(lib, listening, Devices(project.parent / "devices.json"), "Máy thử")
    first = app.studio_view()
    second = app.studio_view()
    assert first == second and first[0]["work"] == 3 and len(calls) == 1
    (project / "overrides.json").write_text(json.dumps({"voices": {}}), encoding="utf-8")
    app.studio_view()
    assert len(calls) == 2, "người nghe vừa ghi một yêu cầu: đếm lại"


def test_the_phone_learns_that_the_computer_paused_on_battery(library, monkeypatch) -> None:  # noqa: F811
    """Máy tính rút sạc thì tự tạm dừng (power_source); điện thoại báo "Máy tính đang chạy pin" - ngày 24-09 sạc tuột 22:50
    mà tới 00:07 mới có người biết."""
    from ebook_reader import background_runner
    from ebook_reader.background_runner import BackgroundStatus

    lib, project, listening = library
    monkeypatch.setattr(background_runner, "get_status", lambda path: BackgroundStatus(
        project_root=Path(path), state="running", running=True, pause_reason="battery"))
    app = SyncApp(lib, listening, Devices(project.parent / "devices.json"), "Máy thử")
    assert app.studio_view()[0]["paused"] == "battery"
