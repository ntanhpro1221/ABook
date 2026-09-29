"""Tạm dừng tạo sách khi máy tính xách tay rút sạc, và nút "Tạm dừng"/"Tiếp tục" (power_source + supervisor).

Tạm dừng giữ tiến trình sống - dây chuyền đứng ở checkpoint (pause_requested) rồi làm tiếp đúng chỗ ấy - nên an toàn cả
giữa pha phân tích, nơi "Dừng" rồi chạy lại là ra một quyển sách khác (AGENTS.md).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from ebook_reader import background_runner, power_source
from ebook_reader.background_runner import BackgroundPaths, _pause_reason, get_status, run_supervisor, tail_log
from ebook_reader.io_utils import atomic_write_json
from ebook_reader.power_source import BatteryWatch


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "book_project"
    project.mkdir()
    (project / "project.sqlite3").write_bytes(b"test-placeholder")
    (project / "book_settings.json").write_text("{}", encoding="utf-8")
    return project


def test_a_short_unplug_does_not_pause() -> None:
    watch = BatteryWatch(grace=60)
    assert watch.update(True, now=0, wall=1000) is False
    assert watch.update(True, now=59, wall=1059) is False
    assert watch.update(False, now=60, wall=1060) is False  # cắm lại trước hạn
    assert watch.update(True, now=61, wall=1061) is False  # rút lần nữa: đếm lại từ đầu
    assert watch.update(True, now=121, wall=1121) is True


def test_plugging_back_resumes_at_once_and_an_unreadable_battery_keeps_the_verdict() -> None:
    watch = BatteryWatch(grace=60)
    watch.update(True, now=0, wall=0)
    assert watch.update(True, now=60, wall=60) is True
    assert watch.update(None, now=65, wall=65) is True  # một lần đọc lỗi không được làm sách chạy tiếp trên pin
    assert watch.update(False, now=70, wall=70) is False
    assert watch.last_plugged_wall == 70
    assert watch.update(None, now=75, wall=75) is False


def test_a_desktop_without_a_battery_never_pauses(monkeypatch) -> None:
    monkeypatch.setattr(power_source.psutil, "sensors_battery", lambda: None)
    assert power_source._psutil_on_battery() is False
    assert power_source._from_status(1, 128) is False and power_source._from_status(0, 128) is False


def test_an_unknown_power_line_is_not_read_as_running_on_battery() -> None:
    """Windows ACLineStatus 255 = không biết: psutil gộp vào "chạy pin" - máy ấy sẽ tạm dừng sau 60 giây mọi lượt."""
    assert power_source._from_status(0, 1) is True
    assert power_source._from_status(1, 8) is False
    assert power_source._from_status(255, 1) is None
    assert power_source._from_status(0, 255) is True, "BatteryFlag 255 = không rõ pin, vẫn tin ACLineStatus"


def test_the_listener_pause_wins_and_resuming_on_battery_lasts_until_the_next_charge() -> None:
    assert _pause_reason({"paused": True}, battery_pause=False, last_plugged_wall=None) == "listener"
    assert _pause_reason(None, battery_pause=True, last_plugged_wall=100.0) == "battery"
    assert _pause_reason(None, battery_pause=False, last_plugged_wall=100.0) is None
    # "Tiếp tục" bấm lúc đang dừng vì pin (sau lần cuối thấy sạc): làm tiếp trên pin.
    over = {"paused": False, "requested_at_epoch": 150.0, "overrides": "battery"}
    assert _pause_reason(over, True, 100.0) is None
    # Máy thấy sạc SAU lần bấm ấy rồi lại rút đủ lâu: lại dừng.
    assert _pause_reason(over, True, 200.0) == "battery"
    # "Tiếp tục" bấm để thôi một lần tạm dừng TAY (đang cắm sạc): rút sạc sau đó vẫn dừng.
    assert _pause_reason({"paused": False, "requested_at_epoch": 150.0, "overrides": "listener"}, True, 100.0) == "battery"


def test_the_setting_turns_it_off(tmp_path: Path, monkeypatch) -> None:
    preferences = tmp_path / "preferences.json"
    monkeypatch.setenv("EBOOK_READER_PREFERENCES", str(preferences))
    assert power_source.pause_on_battery_enabled() is True  # chưa mở app lần nào (CLI)
    preferences.write_text('{"pauseOnBattery": false}', encoding="utf-8")
    assert power_source.pause_on_battery_enabled() is False
    preferences.write_text('{"theme": "dark"}', encoding="utf-8")
    assert power_source.pause_on_battery_enabled() is True
    preferences.write_text("{hỏng", encoding="utf-8")
    assert power_source.pause_on_battery_enabled() is True


def _fake_worker_waits_for_a_pause(
    project_root: str,
    message_queue: Any,
    pause_event: Any,
    _stop_event: Any,
    _parent_pid: int,
    _resource_overrides: dict[str, Any] | None,
    _resource_queue: Any,
) -> None:
    """Như dây chuyền: đứng khi được bảo tạm dừng, rồi làm tiếp. Báo lúc thấy tạm dừng bằng một file cạnh project (test
    dùng nó làm "cắm sạc lại" / "người dùng bấm Tiếp tục")."""
    message_queue.put({"kind": "worker_ready", "pid": os.getpid(), "project_root": project_root})
    if not pause_event.wait(10.0):
        message_queue.put({"kind": "finished", "ok": False, "text": "never paused"})
        return
    Path(project_root, "saw_pause").touch()
    deadline = time.monotonic() + 10.0
    while pause_event.is_set() and time.monotonic() < deadline:
        time.sleep(0.02)
    text = "never resumed" if pause_event.is_set() else "paused and resumed"
    message_queue.put({"kind": "finished", "ok": not pause_event.is_set(), "text": text})


def test_the_supervisor_pauses_on_battery_and_resumes_when_charging(tmp_path: Path, monkeypatch) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("EBOOK_READER_PREFERENCES", str(tmp_path / "preferences.json"))
    monkeypatch.setattr(background_runner, "POWER_CHECK_SECONDS", 0.0)
    monkeypatch.setattr(power_source, "GRACE_SECONDS", 0.0)
    # Chạy pin cho tới khi worker đã đứng, rồi "cắm sạc lại".
    monkeypatch.setattr(power_source, "on_battery", lambda: not (project / "saw_pause").exists())

    exit_code = run_supervisor(project, "fake-battery", worker_target=_fake_worker_waits_for_a_pause, poll_seconds=0.01)

    log = tail_log(project, lines=40)
    assert exit_code == 0, log
    assert get_status(project).detail == "paused and resumed"
    assert "PAUSE reason=battery" in log
    assert "RESUME" in log


def test_the_setting_off_keeps_working_on_battery(tmp_path: Path, monkeypatch) -> None:
    project = _make_project(tmp_path)
    preferences = tmp_path / "preferences.json"
    preferences.write_text(json.dumps({"pauseOnBattery": False}), encoding="utf-8")
    monkeypatch.setenv("EBOOK_READER_PREFERENCES", str(preferences))
    monkeypatch.setattr(background_runner, "POWER_CHECK_SECONDS", 0.0)
    monkeypatch.setattr(power_source, "GRACE_SECONDS", 0.0)
    monkeypatch.setattr(power_source, "on_battery", lambda: True)

    from test_background_runner import _fake_worker_success

    assert run_supervisor(project, "fake-off", worker_target=_fake_worker_success, poll_seconds=0.01) == 0
    assert "PAUSE" not in tail_log(project, lines=40)


def _fake_worker_presses_continue(
    project_root: str,
    message_queue: Any,
    pause_event: Any,
    _stop_event: Any,
    _parent_pid: int,
    _resource_overrides: dict[str, Any] | None,
    _resource_queue: Any,
) -> None:
    """Đứng theo yêu cầu "Tạm dừng" của người dùng, rồi tự "bấm Tiếp tục" (ghi lại yêu cầu với paused=false)."""
    message_queue.put({"kind": "worker_ready", "pid": os.getpid(), "project_root": project_root})
    if not pause_event.wait(10.0):
        message_queue.put({"kind": "finished", "ok": False, "text": "never paused"})
        return
    request_path = BackgroundPaths.for_project(project_root).pause_request
    request = json.loads(request_path.read_text(encoding="utf-8"))
    atomic_write_json(request_path, {**request, "paused": False, "requested_at_epoch": time.time()})
    deadline = time.monotonic() + 10.0
    while pause_event.is_set() and time.monotonic() < deadline:
        time.sleep(0.02)
    text = "never resumed" if pause_event.is_set() else "paused and resumed"
    message_queue.put({"kind": "finished", "ok": not pause_event.is_set(), "text": text})


def test_the_listener_can_pause_and_continue_a_running_book(tmp_path: Path, monkeypatch) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("EBOOK_READER_PREFERENCES", str(tmp_path / "preferences.json"))
    monkeypatch.setattr(background_runner, "POWER_CHECK_SECONDS", 0.0)
    monkeypatch.setattr(power_source, "on_battery", lambda: False)
    paths = BackgroundPaths.for_project(project)
    paths.ensure_root()
    atomic_write_json(paths.pause_request, {
        "schema_version": 1, "project_root": str(project.resolve()), "instance_id": "fake-listener",
        "requested_at": "2026-09-29T00:00:00Z", "requested_at_epoch": time.time(), "requester_pid": os.getpid(),
        "paused": True,
    })

    exit_code = run_supervisor(project, "fake-listener", worker_target=_fake_worker_presses_continue, poll_seconds=0.01)

    log = tail_log(project, lines=40)
    assert exit_code == 0, log
    assert get_status(project).detail == "paused and resumed"
    assert "PAUSE reason=listener" in log
    assert "RESUME" in log


def test_a_pause_request_of_another_run_is_ignored(tmp_path: Path, monkeypatch) -> None:
    project = _make_project(tmp_path)
    monkeypatch.setenv("EBOOK_READER_PREFERENCES", str(tmp_path / "preferences.json"))
    monkeypatch.setattr(power_source, "on_battery", lambda: False)
    paths = BackgroundPaths.for_project(project)
    paths.ensure_root()
    atomic_write_json(paths.pause_request, {
        "schema_version": 1, "project_root": str(project.resolve()), "instance_id": "an-old-run", "paused": True,
    })

    from test_background_runner import _fake_worker_success

    assert run_supervisor(project, "a-new-run", worker_target=_fake_worker_success, poll_seconds=0.01) == 0
    assert "PAUSE" not in tail_log(project, lines=40)


def test_a_run_started_by_older_code_says_it_cannot_pause(tmp_path: Path, monkeypatch) -> None:
    """Supervisor khởi động bằng mã cũ (trước tính năng này) không đọc pause.request - app phải nói thật, không ghi yêu
    cầu rồi báo "Đang tạm dừng" (soát QA 29-09)."""
    import pytest

    from ebook_reader.background_runner import BackgroundIdentityError, request_pause

    project = _make_project(tmp_path)
    paths = BackgroundPaths.for_project(project)
    paths.ensure_root()
    state = {"schema_version": 1, "project_root": str(project.resolve()), "instance_id": "old-run", "state": "running",
             "supervisor_pid": os.getpid(), "supervisor_create_time": 1.0, "worker_pid": 1234}
    atomic_write_json(paths.state, state)
    monkeypatch.setattr(background_runner, "_validate_supervisor_identity", lambda state, root: (True, None))
    with pytest.raises(BackgroundIdentityError, match="bản cũ"):
        request_pause(project, True)
    assert not paths.pause_request.exists()
    assert get_status(project).can_pause is False

    atomic_write_json(paths.state, {**state, "pause_reason": "battery"})
    request_pause(project, False)
    written = json.loads(paths.pause_request.read_text(encoding="utf-8"))
    assert written["paused"] is False and written["overrides"] == "battery", "Tiếp tục vượt đúng lần dừng vì pin"
    assert get_status(project).can_pause is True
