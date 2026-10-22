"""Soát a96 V8: nhật ký phụ (events.jsonl, supervisor.log) không ghi được không được giết worker đang làm sách."""
from __future__ import annotations

import errno
from pathlib import Path

import pytest

from abook import background_runner as runner


@pytest.fixture(autouse=True)
def _fast_log_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "LOG_RETRY_DELAY_SECONDS", 0.0)
    runner._LOG_LOSS.clear()


def _paths(tmp_path: Path):
    paths = runner.BackgroundPaths.for_project(tmp_path)
    paths.ensure_root()
    return paths


def _fail_on(monkeypatch: pytest.MonkeyPatch, names: set[str], error: OSError, times: int | None = None) -> list[str]:
    real_open = Path.open
    seen: list[str] = []

    def open_file(path, *args, **kwargs):
        if path.name in names and (times is None or len(seen) < times):
            seen.append(path.name)
            raise error
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_file)
    return seen


def test_a_full_disk_on_the_event_log_does_not_escape_the_handler(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Đảo khẳng định của test nháp a96: trước đây ENOSPC ném ra khỏi `_record_worker_event` trước cả `last_event`."""
    paths = _paths(tmp_path)
    _fail_on(monkeypatch, {runner.EVENTS_FILE_NAME}, OSError(errno.ENOSPC, "No space left on device"))
    state = {"state": "running"}
    event = runner._record_worker_event(paths, state, {"kind": "progress", "done": 3})
    assert state["last_event"]["done"] == 3 and event["done"] == 3
    assert state["log_lost"]["lines"] == 1 and "events.jsonl" in state["log_lost"]["lastError"]
    # supervisor.log vẫn ghi được: dòng EVENT ở đó còn nguyên
    assert "EVENT progress" in paths.log.read_text(encoding="utf-8")


def test_a_lock_that_clears_on_the_second_try_loses_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _paths(tmp_path)
    seen = _fail_on(monkeypatch, {runner.EVENTS_FILE_NAME}, PermissionError(errno.EACCES, "locked by antivirus"), times=1)
    state: dict = {}
    runner._record_worker_event(paths, state, {"kind": "progress", "done": 1})
    assert seen == [runner.EVENTS_FILE_NAME]
    assert "log_lost" not in state
    assert '"done":1' in paths.events.read_text(encoding="utf-8")


def test_a_log_that_stays_locked_is_not_hammered_on_every_event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _paths(tmp_path)
    seen = _fail_on(monkeypatch, {runner.EVENTS_FILE_NAME, runner.LOG_FILE_NAME}, PermissionError(errno.EACCES, "locked"))
    state: dict = {}
    for number in range(20):
        runner._record_worker_event(paths, state, {"kind": "progress", "done": number})
    # Nghỉ sau lần thất bại đầu: chỉ vài lần thử, không 20 x 3 x 2
    assert len(seen) <= runner.LOG_WRITE_ATTEMPTS * 2
    assert state["last_event"]["done"] == 19 and state["log_lost"]["lines"] == 40  # 20 dòng events + 20 dòng log
    lost = runner.log_loss(paths)
    assert lost is not None and lost["lines"] == 40 and lost["since"]


def test_the_log_is_written_again_after_the_pause(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _paths(tmp_path)
    _fail_on(monkeypatch, {runner.EVENTS_FILE_NAME}, OSError(errno.ENOSPC, "No space left on device"), times=runner.LOG_WRITE_ATTEMPTS)
    state: dict = {}
    runner._record_worker_event(paths, state, {"kind": "progress", "done": 1})
    monkeypatch.setattr(runner, "LOG_RETRY_PAUSE_SECONDS", 0.0)
    runner._LOG_LOSS[str(paths.root)].retry_at.clear()
    runner._record_worker_event(paths, state, {"kind": "progress", "done": 2})
    assert '"done":2' in paths.events.read_text(encoding="utf-8") and '"done":1' not in paths.events.read_text(encoding="utf-8")
    assert runner.log_loss(paths)["lines"] == 1  # dòng đầu mất và được đếm
