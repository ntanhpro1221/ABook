"""Lúc mở app, luồng "trash-sweep" (`App._sweep_trash_at_start`) chạy ngay trong `App.__init__` và dọn cả chương đã ghép của
"Xuất sách nói" (`_sweep_listen_work`). Bản 0.4.174 thả luồng ấy TRƯỚC khi `export_work_dir` / `listen_exports` có mặt, nên
host.log của chủ sách 24-11 có `AttributeError: 'App' object has no attribute 'export_work_dir'` mỗi lần luồng chạy nhanh hơn
phần còn lại của `__init__`. Bài này cho luồng chạy ĐỒNG BỘ ngay lúc `start()` (trường hợp xấu nhất của cuộc đua)."""
from __future__ import annotations

import threading
from pathlib import Path

import pytest


def test_the_start_sweep_never_runs_before_the_app_has_what_it_sweeps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui import server
    from abook.webui.actions import FakeRunner
    from abook.webui.library import Preferences
    from abook.webui.listening import Listening

    errors: list[BaseException] = []
    swept: list[str] = []
    real_thread = threading.Thread

    class EagerSweep(real_thread):
        def start(self) -> None:
            if self.name != "trash-sweep":
                return super().start()
            try:
                self.run()  # chạy ngay, trên luồng đang dựng App
                swept.append(self.name)
            except BaseException as error:  # noqa: BLE001 - đúng thứ luồng thật nuốt vào host.log
                errors.append(error)

    monkeypatch.setattr(server.threading, "Thread", EagerSweep)
    monkeypatch.setattr(server.App, "_fake_run", lambda self: False)  # bản thật: có dọn lúc mở
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path / "library")})
    (tmp_path / "library").mkdir()
    app = server.App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    try:
        assert errors == [], f"luồng dọn lúc mở văng: {errors!r}"
        assert swept == ["trash-sweep"], "lúc mở app phải dọn Thùng rác chờ"
    finally:
        app.close()
