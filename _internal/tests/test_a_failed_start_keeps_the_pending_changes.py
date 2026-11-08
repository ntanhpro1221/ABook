"""Soát UX a20: khởi động lượt chạy hỏng (chưa cài Studio, thiếu Ollama...) không được làm mất sửa chờ áp.

`App._launch` khởi động chạy nền (Jobs.start) nên trước đây ghi mốc "đã áp" ngay, dù runner chưa chạy: nút "Áp dụng N thay
đổi" biến mất trong khi sửa vẫn nằm trong overrides.json. Mốc chỉ ghi khi khởi động xong và không lỗi."""
from __future__ import annotations

import threading
import time
from pathlib import Path

from abook.listener_overrides import request_pronunciation
from abook.webui import store
from abook.webui.actions import FakeRunner
from tests.test_listener_speakers import _book


class _BrokenRunner(FakeRunner):
    def start(self, project_root: Path) -> None:
        raise RuntimeError("Không thấy Ollama của Studio - bấm Cài tiếp để tải lại.")


def _app(tmp_path: Path, runner: FakeRunner, monkeypatch):
    from abook.config import build_settings, save_settings
    from abook.webui.library import Preferences
    from abook.webui.listening import Listening
    from abook.webui.server import App

    paths, _db = _book(tmp_path)
    save_settings(paths.settings, build_settings())
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=runner, token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    completed = threading.Event()
    start = app.jobs.start

    def start_notifying(project_root, on_done=None, *, reserved=False):
        def done():
            try:
                if on_done:
                    on_done()
            finally:
                completed.set()

        start(project_root, on_done=done, reserved=reserved)

    monkeypatch.setattr(app.jobs, "start", start_notifying)
    return paths, app, completed


def _wait_idle(app, path: Path, completed: threading.Event) -> None:
    # Jobs clears its starting flag before calling on_done. Wait for that actual
    # callback, including its file write, instead of guessing a scheduling delay.
    assert completed.wait(10), "start callback did not finish"
    assert not app.jobs.starting(path)


def test_a_failed_start_leaves_the_edits_pending(tmp_path: Path, monkeypatch) -> None:
    paths, app, completed = _app(tmp_path, _BrokenRunner(), monkeypatch)
    request_pronunciation(paths.root, "Rhine", "Rin-nơ", now=time.time())
    app._launch(paths.root)
    _wait_idle(app, paths.root, completed)
    assert app.jobs.error(paths.root), "lỗi khởi động tới được người dùng"
    assert not (paths.root / store.RUN_MARKER).exists(), "khởi động hỏng: không có mốc 'đã áp'"
    assert store.pending_changes(paths.root, store.changes_since(paths.root, 0.0)) == 1


def test_a_start_that_worked_marks_the_edits_as_applied(tmp_path: Path, monkeypatch) -> None:
    paths, app, completed = _app(tmp_path, FakeRunner(), monkeypatch)
    request_pronunciation(paths.root, "Rhine", "Rin-nơ", now=time.time())
    app._launch(paths.root)
    _wait_idle(app, paths.root, completed)
    assert (paths.root / store.RUN_MARKER).exists()
    assert store.pending_changes(paths.root, store.changes_since(paths.root, 0.0)) == 0
