"""Soát a92 V2: đóng app khi đang cài Studio không để tiến trình cài sống mồ côi, và lần mở sau không cài chồng.
Tiến trình con dùng ở đây vô hại: python ngủ có hạn, ghi file trong thư mục thử."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest

from abook.webui import install_lock, studio_setup
from abook.webui.install_lock import InstallLock
from abook.webui.server import App
from abook.webui.studio_setup import StudioSetup

NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _setup(tmp_path: Path) -> StudioSetup:
    return StudioSetup(tmp_path / "Studio", tmp_path / "app", gpu=lambda: None)


def _sleeper(seconds: int = 40) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", f"import time; time.sleep({seconds})"], creationflags=NO_WINDOW)


def _wait_gone(pids: list[int], seconds: float = 8.0) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if not any(psutil.pid_exists(pid) and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE for pid in pids):
            return True
        time.sleep(0.1)
    return False


def test_closing_the_app_stops_and_waits_for_the_studio_install() -> None:
    calls: list[str] = []

    class Jobs:
        def running(self): return []
        def stop_all(self): return []

    fake = SimpleNamespace(
        bookfile_jobs=Jobs(), projectfile_jobs=Jobs(), m4b_jobs=Jobs(), mp3_jobs=Jobs(), listen_exports=Jobs(),
        studio=SimpleNamespace(stop=lambda: calls.append("stop"), wait=lambda timeout=None: calls.append(f"wait<={timeout is not None}")),
        _trash_sweeper=SimpleNamespace(cancel=lambda: None), sweep_trash=lambda **_: None, _stop_sync=lambda: None,
        cast=SimpleNamespace(close=lambda: None), previews=SimpleNamespace(shutdown=lambda: None),
    )
    App.close(fake)
    assert calls == ["stop", "wait<=True"], "bảo dừng đầu tiên, chờ có hạn ở cuối"
    App.close(SimpleNamespace(**{**fake.__dict__, "studio": None}))  # bản dev không có Studio: vẫn đóng được


def test_stopping_an_install_kills_the_whole_process_tree_of_that_job_only(tmp_path: Path) -> None:
    setup = _setup(tmp_path)
    bystander = _sleeper()  # tiến trình không thuộc lượt cài: không được đụng
    grandchild = tmp_path / "grandchild.pid"
    code = ("import subprocess,sys,time,pathlib;"
            f"c=subprocess.Popen([sys.executable,'-c','import time; time.sleep(40)']);"
            f"pathlib.Path({str(grandchild)!r}).write_text(str(c.pid));time.sleep(40)")
    errors: list[BaseException] = []

    def job() -> None:
        try:
            setup._run([sys.executable, "-c", code], "lệnh thử")
        except BaseException as error:  # noqa: BLE001
            errors.append(error)

    thread = threading.Thread(target=job, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if grandchild.is_file() and setup._process is not None:
                break
            time.sleep(0.1)
        child_pid, grand_pid = setup._process.pid, int(grandchild.read_text())
        setup.stop()
        thread.join(10)
        assert not thread.is_alive()
        assert _wait_gone([child_pid, grand_pid]), "cả tiến trình con lẫn cháu của lượt cài đều bị thu hồi"
        assert bystander.poll() is None, "tiến trình ngoài lượt cài còn nguyên"
    finally:
        bystander.kill()
        bystander.wait()


def test_the_lock_names_a_live_install_and_forgets_a_dead_one(tmp_path: Path) -> None:
    first, second = InstallLock(tmp_path), InstallLock(tmp_path)
    assert first.acquire("cài Studio") is None and first.holder() is None, "chính mình giữ khoá thì không phải lượt khác"
    # Tiến trình khác (giả bằng cách ghi khoá của một tiến trình thật còn sống) giữ khoá: người sau thấy và không cài chồng.
    live = _sleeper()
    try:
        first.release()
        started = install_lock.process_started(live.pid)
        (tmp_path / install_lock.LOCK_FILE).write_text(json.dumps(
            {"pid": live.pid, "started": started, "since": time.time(), "what": "cài Studio", "child": None}), encoding="utf-8")
        other = second.acquire("cài Studio")
        assert other is not None and other["pid"] == live.pid and other["orphan"] is False
    finally:
        live.kill()
        live.wait()
    assert second.acquire("cài Studio") is None, "tiến trình giữ khoá đã chết: khoá chết, lấy lại được"
    # pid bị máy dùng lại cho tiến trình khác (thời điểm bắt đầu không khớp) cũng là khoá chết.
    second.release()
    (tmp_path / install_lock.LOCK_FILE).write_text(json.dumps(
        {"pid": psutil.Process().pid, "started": 1.0, "since": 1.0, "what": "x", "child": None}), encoding="utf-8")
    assert InstallLock(tmp_path).acquire("cài Studio") is None


def test_an_install_child_orphaned_by_a_dead_host_blocks_a_second_install_until_stopped(tmp_path: Path) -> None:
    setup = _setup(tmp_path)
    orphan = _sleeper()
    (tmp_path / "Studio").mkdir()
    try:
        # Host cũ đã chết (pid chưa từng có), nhưng tiến trình con của lượt cài còn chạy.
        (tmp_path / "Studio" / install_lock.LOCK_FILE).write_text(json.dumps({
            "pid": 2**22 + 12345, "started": 1.0, "since": time.time() - 60, "what": "cài Studio",
            "child": {"pid": orphan.pid, "started": install_lock.process_started(orphan.pid)}}), encoding="utf-8")
        status = setup.status()
        assert status["leftover"] and status["leftover"]["orphan"] is True and status["leftover"]["childPid"] == orphan.pid
        status = setup.start()
        assert status["running"] is False and "Lượt cài cũ còn chạy" in status["error"], "báo rõ, không cài chồng"
        assert setup._thread is None
        setup.cancel()  # Dừng lượt cũ
        assert _wait_gone([orphan.pid]), "tiến trình mồ côi bị dừng"
        assert setup.status()["leftover"] is None
        assert not (tmp_path / "Studio" / install_lock.LOCK_FILE).exists()
    finally:
        if orphan.poll() is None:
            orphan.kill()
        orphan.wait()


def test_a_second_app_window_installing_is_reported_and_left_alone(tmp_path: Path) -> None:
    setup = _setup(tmp_path)
    other_app = _sleeper()
    (tmp_path / "Studio").mkdir()
    try:
        (tmp_path / "Studio" / install_lock.LOCK_FILE).write_text(json.dumps({
            "pid": other_app.pid, "started": install_lock.process_started(other_app.pid), "since": time.time(), "what": "cài Studio",
            "child": None}), encoding="utf-8")
        status = setup.start()
        assert "ABook khác đang cài Studio" in status["error"] and not status["running"]
        setup.cancel()
        assert other_app.poll() is None, "app khác đang cài không bị giết"
    finally:
        other_app.kill()
        other_app.wait()


def test_a_normal_install_takes_and_releases_the_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    setup = _setup(tmp_path)
    seen: list[bool] = []

    def run_all() -> None:
        seen.append((tmp_path / "Studio" / install_lock.LOCK_FILE).is_file())

    monkeypatch.setattr(StudioSetup, "installed", lambda self: False)
    monkeypatch.setattr(StudioSetup, "_run_all", lambda self: (run_all(), self._install_lock.release()))
    setup.start()
    setup.wait(10)
    assert seen == [True]
    assert not (tmp_path / "Studio" / install_lock.LOCK_FILE).exists()
