"""Huỷ tải giọng ZeroTTS / Supertonic ở hộp "Đổi giọng" của Studio: cùng khung với VieNeu (voice_module.ModuleCore) - dừng giữa chừng, cờ
`cancelled` cho giao diện nói "Đã huỷ", lần tải sau làm tiếp. Không tải gì thật: hàm tải bị thay bằng giả."""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pytest

from abook.webui import server, studio_setup, supertonic_module, voice_picker, zerotts_module


@pytest.fixture
def module(tmp_path: Path):
    folder = tmp_path / zerotts_module.FOLDER
    zerotts_module.configure(folder)
    yield folder
    zerotts_module.join(10)
    zerotts_module.configure(None)


def test_cancelling_a_zerotts_download_stops_it_and_the_next_start_downloads_again(module: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[bool] = []

    def cancelling(item, target, progress, cancelled):
        voice_picker.cancel_engine_module("zerotts")
        seen.append(cancelled())
        raise studio_setup.Cancelled()

    monkeypatch.setattr(studio_setup, "download", cancelling)
    zerotts_module.start()
    zerotts_module.join(10)
    status = voice_picker.engine_module_status("zerotts")
    assert seen == [True], "cờ huỷ tới tận hàm tải"
    assert status["state"] == "missing" and status["cancelled"] is True and status["cancellable"] is False and status["error"] == ""

    started: list[str] = []

    def completing(item, target, progress, cancelled):
        started.append(item.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if item is zerotts_module.CODE:  # wheel giả có đúng một file mã
            with zipfile.ZipFile(target, "w") as bundle:
                bundle.writestr("zerotts/synthesizer.py", "")
        else:
            target.write_bytes(b"x")
        progress(item.size, item.size)
        return target

    monkeypatch.setattr(studio_setup, "download", completing)
    zerotts_module.start()
    zerotts_module.join(10)
    assert started[0] == zerotts_module.CODE.name and len(started) == 1 + len(zerotts_module.MODEL_FILES), "tải lại từ đầu, không lỡ phần nào"
    assert zerotts_module.installed() is not None and zerotts_module.status()["state"] == "ready"
    assert zerotts_module.status()["cancelled"] is False, "bắt đầu tải lại xoá dấu Huỷ"


def test_cancel_without_a_download_does_nothing(module: Path) -> None:
    status = voice_picker.cancel_engine_module("zerotts")
    assert status["cancelled"] is False and status["cancellable"] is False


def test_the_cancel_button_is_offered_only_while_downloading(module: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert zerotts_module.status()["cancellable"] is False
    monkeypatch.setitem(zerotts_module._core.state, "downloading", True)
    assert zerotts_module.status()["cancellable"] is True


def test_supertonic_cancel_goes_through_the_same_box_route(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(supertonic_module, "cancel", lambda: calls.append("cancel"))
    monkeypatch.setattr(supertonic_module, "status", lambda: {
        "state": "downloading", "done": 1, "total": 2, "error": "", "reason": "", "cancelled": False, "choices": [{"bytes": 5}]})
    status = voice_picker.cancel_engine_module("supertonic")
    assert calls == ["cancel"] and status["cancellable"] is True and status["cancelled"] is False
    with pytest.raises(ValueError):
        voice_picker.cancel_engine_module("vieneu")


def test_the_server_routes_the_box_cancel_to_zerotts_and_supertonic() -> None:
    routed = {engine: [handler for method, pattern, handler in server.ROUTES
                       if method == "POST" and pattern.fullmatch(f"/api/studio/{engine}/cancel")] for engine in ("zerotts", "supertonic")}
    assert all(handlers == [server.Handler.post_studio_engine_cancel] for handlers in routed.values()), routed
    assert not any(pattern.fullmatch("/api/studio/zerotts/cancel") and handler is server.Handler.post_studio_engine
                   for method, pattern, handler in server.ROUTES if method == "POST")
    assert re.fullmatch(r"/api/studio/(zerotts|supertonic)", "/api/studio/zerotts")
