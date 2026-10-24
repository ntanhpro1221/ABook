"""Soát a88: Dừng / Tạm dừng / Tiếp tục / hồi phục sự cố.

V1 "đang dừng" có trạng thái riêng; V2 tiến trình chết thì sách hết chạy ngay và "Dừng" nói tiếng Việt; V4 bấm "Tiếp tục" hai lần
không làm mất sự đồng ý chạy pin; V6 máy tính báo ra màn hình khi sách tạm dừng vì pin; T1 "Tiếp tục" trên pin là đồng ý thật;
T4 sự cố nói nguyên nhân; T5 cuốn xếp hàng sau cuốn đang tạm dừng nói vì sao chờ; T6 máy được giữ thức khi sách chạy."""
from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from abook import background_runner, power_source
from abook.background_runner import BackgroundIdentityError, BackgroundPaths
from abook.database import ProjectDB
from tests.test_listener_speakers import _book
from tests.test_webui_listen_and_sync import library  # noqa: F401 - fixture dùng chung


@pytest.fixture
def studio(tmp_path):
    from abook.config import build_settings, save_settings
    from abook.webui.actions import BackgroundRunner
    from abook.webui.library import Preferences
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server

    paths, db = _book(tmp_path)
    save_settings(paths.settings, build_settings())
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=BackgroundRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    try:
        yield paths, db, server, app
    finally:
        server.stop()


def _call(server, method: str, path: str, body: dict | None = None):
    from tests.test_webui_listen_and_sync import _request

    status, data, _ = _request(server.port, method, path, headers={"X-Ebook-Token": "t"}, body=body)
    return status, json.loads(data or b"{}")


def _write_state(paths, state: str, **extra) -> None:
    root = paths if isinstance(paths, Path) else paths.root
    folder = root / "runtime" / "background"
    folder.mkdir(parents=True, exist_ok=True)
    body = {"schema_version": 1, "instance_id": "abc", "state": state, "supervisor_pid": 99999, "supervisor_create_time": 1.0,
            "worker_pid": 1, "pause_reason": None, **extra}
    if state in ("stopped", "failed", "completed"):
        body.setdefault("finished_at", background_runner._utc_now())
    (folder / "state.json").write_text(json.dumps(body), encoding="utf-8")


def _alive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(background_runner, "_validate_supervisor_identity", lambda state, root: (True, "ok"))


def _working_with_a_fresh_lease(db) -> None:
    """Sổ đang ở pha phân tích, nhịp tim worker mới đây - cái làm trang báo "đang chạy" thêm 120 giây sau khi tiến trình chết."""
    db.update_book(status="analyzing", stage="analysis")
    with db.connect() as connection:
        connection.execute("UPDATE segments SET status='pending', wav_path=NULL, wav_sha256=NULL WHERE seq >= 2")
        connection.execute("INSERT OR REPLACE INTO worker_leases(worker_name,pid,generation,state,heartbeat_at) VALUES ('w',1,1,'running',?)",
                           (time.time(),))


# ---- V1: "đang dừng" ----

def test_a_book_being_stopped_says_so_and_cannot_be_paused(studio, monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui.library import book_id

    paths, _db, server, _app = studio
    _alive(monkeypatch)
    _write_state(paths, "stopping", stop_requested=True, pause_reason="listener")
    bid = book_id(paths.root)
    status, data = _call(server, "GET", f"/api/books/{bid}")
    book = data["book"]
    assert book["running"] is True and book["stopping"] is True
    assert book["canPause"] is False and book["paused"] is None
    assert book["statusLabel"] == "Đang dừng…" and book["eta"] is None

    status, data = _call(server, "POST", f"/api/books/{bid}/pause", {"paused": True})
    assert status == 409 and "đang dừng" in data["error"] and "không đang chạy" not in data["error"]
    status, data = _call(server, "POST", f"/api/books/{bid}/pause", {"paused": False})
    assert status == 409 and "đang dừng" in data["error"]


def test_pressing_stop_answers_with_the_stopping_state(studio, monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui.library import book_id

    paths, _db, server, _app = studio
    _alive(monkeypatch)
    _write_state(paths, "running", pause_reason="listener")
    status, data = _call(server, "POST", f"/api/books/{book_id(paths.root)}/stop")
    assert status == 202 or status == 200
    assert data["stopping"] is True and data["paused"] is None and data["canPause"] is False
    assert data["statusLabel"] == "Đang dừng…"
    assert BackgroundPaths.for_project(paths.root).stop_request.is_file()


# ---- V2: tiến trình chết ----

def test_stop_on_a_dead_supervisor_says_the_book_is_no_longer_running(studio) -> None:
    from abook.webui.library import book_id

    paths, _db, server, _app = studio
    _write_state(paths, "running")  # supervisor_pid 99999 không tồn tại
    bid = book_id(paths.root)
    status, data = _call(server, "POST", f"/api/books/{bid}/stop")
    assert status == 409 and data["error"] == "Sách đã không còn chạy"
    status, data = _call(server, "POST", f"/api/books/{bid}/pause", {"paused": True})
    assert status == 409 and "không đang chạy" in data["error"]


def test_a_dead_supervisor_ends_the_run_at_once_even_with_a_fresh_heartbeat(studio) -> None:
    from abook.webui.library import book_id

    paths, db, server, _app = studio
    _working_with_a_fresh_lease(db)
    _write_state(paths, "running")
    status, data = _call(server, "GET", f"/api/books/{book_id(paths.root)}")
    book = data["book"]
    assert book["running"] is False and book["interrupted"] is True, "nhịp tim cũ không được nói thay supervisor đã chết"
    assert book["runEnd"]["state"] == "lost" and "không còn chạy" in book["runEnd"]["detail"]


def test_a_run_without_a_supervisor_still_reads_the_heartbeat_in_the_ledger(studio) -> None:
    """Chạy bằng dòng lệnh (không supervisor, không state.json): nhịp tim là nguồn duy nhất."""
    from abook.webui.library import book_id

    paths, db, server, _app = studio
    _working_with_a_fresh_lease(db)
    status, data = _call(server, "GET", f"/api/books/{book_id(paths.root)}")
    assert data["book"]["running"] is True


def test_a_heartbeat_older_than_the_supervisors_end_does_not_count_but_a_newer_one_does(studio) -> None:
    """Vừa bấm Dừng: nhịp tim cuối của worker không giữ trang ở "đang chạy" 120 giây. Chạy bằng dòng lệnh SAU lượt của app: nhịp tim mới
    hơn lúc supervisor kết thúc thì vẫn là đang chạy."""
    from abook.webui.library import book_id

    paths, db, server, _app = studio
    _working_with_a_fresh_lease(db)
    ended = time.time() - 30
    _write_state(paths, "stopped", finished_at=background_runner.datetime.fromtimestamp(ended, background_runner.UTC).isoformat())
    status, data = _call(server, "GET", f"/api/books/{book_id(paths.root)}")
    assert data["book"]["running"] is True, "nhịp tim (vừa ghi) mới hơn lúc supervisor kết thúc: có người đang chạy sách này"
    with db.connect() as connection:
        connection.execute("UPDATE worker_leases SET heartbeat_at=?", (ended - 5,))
    status, data = _call(server, "GET", f"/api/books/{book_id(paths.root)}")
    assert data["book"]["running"] is False


def test_the_command_line_stop_keeps_its_error_for_a_dead_supervisor(studio) -> None:
    paths, _db, _server, _app = studio
    _write_state(paths, "running")
    with pytest.raises(BackgroundIdentityError, match="supervisor không còn chạy"):
        background_runner.request_stop(paths.root, wait=False)


# ---- V4 + T1: "Tiếp tục" trên pin ----

def _paused_for_battery(paths, instance: str = "abc") -> dict:
    return {"instance_id": instance, "project_root": str(paths.root), "pause_reason": "battery", "battery_pause": True}


def test_a_second_continue_keeps_the_consent_to_run_on_battery(tmp_path: Path) -> None:
    from abook.background_runner import _pause_reason, _pause_request, _write_pause_request

    paths = BackgroundPaths.for_project(tmp_path)
    paths.ensure_root()
    first = {"instance_id": "abc", "pause_reason": "battery", "battery_pause": True}
    _write_pause_request(paths, first, False)
    request = _pause_request(paths, "abc")
    assert request["overrides"] == "battery"
    # Sách đã chạy lại (pause_reason rỗng) nhưng máy vẫn chạy pin: bấm "Tiếp tục" lần hai.
    second = {"instance_id": "abc", "pause_reason": None, "battery_pause": True}
    _write_pause_request(paths, second, False)
    again = _pause_request(paths, "abc")
    assert again["overrides"] == "battery" and again["paused"] is False
    assert _pause_reason(again, True, request["requested_at_epoch"] - 1) is None, "vẫn làm tiếp trên pin"


def test_a_second_continue_with_nothing_to_override_keeps_the_earlier_request(tmp_path: Path) -> None:
    from abook.background_runner import _pause_request, _write_pause_request

    paths = BackgroundPaths.for_project(tmp_path)
    paths.ensure_root()
    _write_pause_request(paths, {"instance_id": "abc", "pause_reason": "battery", "battery_pause": False}, False)
    before = _pause_request(paths, "abc")
    _write_pause_request(paths, {"instance_id": "abc", "pause_reason": None, "battery_pause": False}, False)
    assert _pause_request(paths, "abc") == before


def test_continuing_a_manual_pause_on_battery_is_consent_to_work_on_battery(tmp_path: Path) -> None:
    """T1: sách dừng vì "listener" trong lúc máy chạy pin; "Tiếp tục" mà dừng lại ngay vì pin thì toast nói sai."""
    from abook.background_runner import _pause_reason, _pause_request, _write_pause_request

    paths = BackgroundPaths.for_project(tmp_path)
    paths.ensure_root()
    _write_pause_request(paths, {"instance_id": "abc", "pause_reason": "listener", "battery_pause": True}, False)
    request = _pause_request(paths, "abc")
    assert request["overrides"] == "battery"
    assert _pause_reason(request, True, request["requested_at_epoch"] - 1) is None
    # Đang cắm sạc lúc bấm: vẫn chỉ vượt lần dừng tay (test_pause_on_battery: rút sạc sau đó vẫn dừng).
    _write_pause_request(paths, {"instance_id": "abc", "pause_reason": "listener", "battery_pause": False}, False)
    assert _pause_request(paths, "abc")["overrides"] == "listener"


# ---- V6: thông báo ra màn hình khi sách tạm dừng vì pin ----

def test_the_desktop_is_told_once_when_a_book_pauses_for_the_battery(studio, monkeypatch: pytest.MonkeyPatch) -> None:
    paths, _db, _server, app = studio
    _alive(monkeypatch)
    toasts: list[tuple[str, str]] = []
    app.notify_desktop = lambda title, message: toasts.append((title, message))
    _write_state(paths, "running", pause_reason="battery", battery_pause=True)

    app._precast_tick(now=0.0)
    assert len(toasts) == 1 and "pin" in toasts[0][0] and "cắm sạc" in toasts[0][1] and "Tiếp tục" in toasts[0][1]
    app._precast_tick(now=5.0)
    assert len(toasts) == 1, "một lần mỗi lần dừng"

    _write_state(paths, "running", pause_reason=None)  # cắm sạc / bấm Tiếp tục
    app._precast_tick(now=10.0)
    _write_state(paths, "running", pause_reason="battery", battery_pause=True)  # rút sạc lần nữa
    app._precast_tick(now=15.0)
    assert len(toasts) == 2

    _write_state(paths, "running", pause_reason="listener")  # người dùng bấm Tạm dừng: không phải chuyện pin
    app._precast_tick(now=20.0)
    assert len(toasts) == 2


# ---- T4: sự cố nói nguyên nhân ----

def test_a_crashed_run_says_why_and_a_stop_you_pressed_does_not(studio) -> None:
    from abook.webui.library import book_id

    paths, db, server, app = studio
    _working_with_a_fresh_lease(db)
    bid = book_id(paths.root)
    _write_state(paths, "failed", detail="worker thoát với exit code 3221225477", exit_code=1)
    status, data = _call(server, "GET", f"/api/books/{bid}")
    assert data["book"]["runEnd"] == {"state": "failed", "detail": "worker thoát với exit code 3221225477", "exitCode": 1}

    _write_state(paths, "stopped", detail="worker đã dừng sạch", exit_code=0, stop_requested=True)
    status, data = _call(server, "GET", f"/api/books/{bid}")
    assert data["book"]["runEnd"] is None, "bạn bấm Dừng - không phải sự cố"


def test_the_phone_is_told_apart_a_stop_from_a_crash(library, tmp_path: Path) -> None:  # noqa: F811
    from abook.webui.sync import Devices, SyncApp

    lib, project, listening = library
    sync = SyncApp(lib, listening, Devices(tmp_path / "devices.json"), "Máy thử")
    _working_with_a_fresh_lease(ProjectDB(project / "project.sqlite3"))  # sổ đang ở pha phân tích, nhịp tim còn mới
    _write_state(project, "stopped", detail="worker đã dừng sạch", exit_code=0, stop_requested=True)
    (book,) = sync.studio_view()
    assert book["end"] == "stopped" and book["endDetail"] == "" and book["running"] is False

    _write_state(project, "failed", detail="worker thoát với exit code 3221225477", exit_code=1)
    (book,) = sync.studio_view()
    assert book["end"] == "failed" and "3221225477" in book["endDetail"]

    _write_state(project, "running")  # supervisor chết giữa chừng
    (book,) = sync.studio_view()
    assert book["end"] == "lost" and book["running"] is False, "nhịp tim còn mới nhưng supervisor đã chết"


# ---- T5: cuốn xếp hàng sau cuốn đang tạm dừng ----

def test_a_queued_book_says_it_waits_behind_a_paused_one(studio, monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui.library import book_id

    paths, _db, server, app = studio
    _alive(monkeypatch)
    _write_state(paths, "running", pause_reason="listener")
    other = paths.root.parent / "cuon_hai"
    other.mkdir()
    monkeypatch.setattr(app, "queue", [book_id(other)])
    monkeypatch.setattr(app, "_busy_elsewhere", lambda path=None: paths.root if path != paths.root else None)
    blocker = app._queue_blocker(other)
    assert blocker["paused"] == "listener" and blocker["id"] == book_id(paths.root) and blocker["title"]

    _write_state(paths, "running", pause_reason=None)
    assert app._queue_blocker(other) is None, "cuốn kia đang chạy thật: hàng sẽ tự đi tiếp"


# ---- T6: giữ máy thức khi sách chạy ----

def test_the_supervisor_keeps_the_machine_awake_only_while_the_book_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.background_runner import run_supervisor
    from tests.test_pause_on_battery import _fake_worker_waits_for_a_pause, _make_project

    project = _make_project(tmp_path)
    monkeypatch.setenv("ABOOK_PREFERENCES", str(tmp_path / "preferences.json"))
    monkeypatch.setattr(background_runner, "POWER_CHECK_SECONDS", 0.0)
    monkeypatch.setattr(power_source, "GRACE_SECONDS", 0.0)
    polls = iter(range(10**6))
    # Cắm sạc một lúc (sách chạy), rồi rút sạc cho tới khi worker đã đứng, rồi cắm lại.
    monkeypatch.setattr(power_source, "on_battery", lambda: next(polls) > 5 and not (project / "saw_pause").exists())
    calls: list[bool] = []
    monkeypatch.setattr(power_source, "keep_awake", lambda on: calls.append(on))

    assert run_supervisor(project, "fake-awake", worker_target=_fake_worker_waits_for_a_pause, poll_seconds=0.01) == 0
    # Chạy (giữ thức) -> dừng vì pin (nhả) -> cắm sạc làm tiếp (giữ) -> xong (nhả).
    assert calls[0] is True and calls[-1] is False
    assert False in calls[1:-1], "tạm dừng thì máy được ngủ"
    assert calls.count(True) >= 2


def test_keep_awake_asks_windows_once_per_change_and_nothing_elsewhere(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[int] = []
    fake = SimpleNamespace(kernel32=SimpleNamespace(SetThreadExecutionState=lambda flags: sent.append(int(flags.value))))
    import ctypes

    monkeypatch.setattr(ctypes, "windll", fake, raising=False)
    monkeypatch.setattr(power_source, "_awake", False)
    monkeypatch.setattr(power_source.os, "name", "nt")
    power_source.keep_awake(True)
    power_source.keep_awake(True)
    power_source.keep_awake(False)
    power_source.keep_awake(False)
    assert sent == [power_source.ES_CONTINUOUS | power_source.ES_SYSTEM_REQUIRED, power_source.ES_CONTINUOUS]

    monkeypatch.setattr(power_source.os, "name", "posix")
    sent.clear()
    power_source.keep_awake(True)
    power_source.keep_awake(False)
    assert sent == [], "không phải Windows: không làm gì"
