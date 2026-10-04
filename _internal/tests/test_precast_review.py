"""Studio: "Duyệt trước khi thu" - mốc phân tích xong, và tuỳ chọn "Chờ tôi duyệt trước khi thu" (webui/precast.py).

Sửa trước khi thu là miễn phí, sửa sau phải thu lại: Studio nhận ra lúc phân vai vừa khoá mà chưa thu chương nào, báo một lần,
và chỉ khi người dùng bật tuỳ chọn thì TẠM DỪNG (không bao giờ dừng - AGENTS.md) đúng một lần. Mặc định dây chuyền không chờ ai."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.test_listener_speakers import _book


def _fresh_cast(db) -> None:
    """Phân vai vừa khoá: mọi câu đã phân tích, chưa câu nào thu, chương chưa xong (như lúc Pipeline.run qua finalize_casting)."""
    with db.connect() as connection:
        connection.execute("UPDATE segments SET status='analyzed', wav_path=NULL, wav_sha256=NULL")
        connection.execute("UPDATE chapters SET status='pending', completed_at=NULL")
    db.update_book(status="casting", stage="voice_cast_locked")


@pytest.fixture
def studio(tmp_path):
    from abook.config import build_settings, save_settings
    from abook.webui.actions import FakeRunner
    from abook.webui.library import Preferences
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server

    paths, db = _book(tmp_path)
    save_settings(paths.settings, build_settings())
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    runner = FakeRunner()
    pauses: list[tuple[str, bool]] = []
    original = runner.pause

    def counted(project_root, paused):
        pauses.append((str(project_root), paused))
        original(project_root, paused)

    runner.pause = counted
    app = App(preferences=preferences, runner=runner, token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    toasts: list[tuple[str, str]] = []
    app.notify_desktop = lambda title, message: toasts.append((title, message))
    server = Server(app, port=0).start()
    try:
        yield paths, db, server, app, runner, pauses, toasts
    finally:
        server.stop()


def _call(server, method: str, path: str, body: dict | None = None):
    from tests.test_webui_listen_and_sync import _request

    status, data, _ = _request(server.port, method, path, headers={"X-Ebook-Token": "t"}, body=body)
    return status, json.loads(data or b"{}")


def _url(paths) -> str:
    from abook.webui.library import book_id

    return f"/api/books/{book_id(paths.root)}"


def test_the_milestone_is_a_locked_cast_with_nothing_pending(tmp_path) -> None:
    from abook.webui import precast, store

    paths, db = _book(tmp_path)
    summary = store.summarize(paths.root)
    assert summary["castLocked"] is True
    assert not precast.due(paths.root, summary), "chương đã thu xong: không còn là lúc 'trước khi thu'"

    _fresh_cast(db)
    assert precast.due(paths.root, store.summarize(paths.root))

    with db.connect() as connection:
        connection.execute("UPDATE segments SET status='pending' WHERE seq = 1")
    assert not precast.ready(store.summarize(paths.root)), "còn câu chưa phân tích: chưa tới mốc"


def test_studio_only_announces_and_says_the_book_is_waiting(studio) -> None:
    """Giữ là việc của supervisor; Studio chờ nó giữ rồi mới báo, để lời báo nói đúng "đang chờ duyệt"."""
    from abook.webui import precast

    paths, db, server, app, runner, pauses, toasts = studio
    _fresh_cast(db)
    status, data = _call(server, "PUT", _url(paths) + "/precast", {"wait": True})
    assert status == 200 and data["wait"] is True and data["ready"] is True
    runner._running.add(str(paths.root.resolve()))

    assert app._precast_tick(now=0.0) == 1
    assert pauses == [] and toasts == [], "Studio không tự tạm dừng, và chưa báo khi supervisor chưa kịp giữ"

    precast.mark_held(paths.root)  # supervisor giữ (background_runner._hold_for_review)
    runner._paused[str(paths.root.resolve())] = "listener"
    app._precast_tick(now=5.0)
    assert pauses == [] and len(toasts) == 1 and "Thu âm" in toasts[0][1]
    status, data = _call(server, "GET", _url(paths))
    assert data["book"]["precast"]["held"] is True

    app._precast_tick(now=10.0)
    assert len(toasts) == 1, "mốc chỉ báo một lần"

    status, data = _call(server, "POST", _url(paths) + "/pause", {"paused": False})  # nút "Thu âm"
    assert status == 202 and data["paused"] is None and data["precast"]["held"] is False
    assert precast.read(paths.root)["releasedAt"] is not None
    assert not precast.hold_due(paths.root), "đã giữ một lần: supervisor không giữ lại"


def test_studio_announces_anyway_when_the_supervisor_never_holds(studio) -> None:
    paths, db, server, app, runner, pauses, toasts = studio
    _fresh_cast(db)
    _call(server, "PUT", _url(paths) + "/precast", {"wait": True})
    runner._running.add(str(paths.root.resolve()))
    app._precast_tick(now=0.0)
    app._precast_tick(now=31.0)
    assert len(toasts) == 1 and "không phải thu lại" in toasts[0][1]


def test_by_default_the_line_does_not_wait(studio) -> None:
    paths, db, server, app, runner, pauses, toasts = studio
    _fresh_cast(db)
    runner._running.add(str(paths.root.resolve()))

    app._precast_tick()
    assert pauses == [], "tắt (mặc định): không tạm dừng"
    assert len(toasts) == 1 and "không phải thu lại" in toasts[0][1], "vẫn báo để người dùng mở màn duyệt"
    status, data = _call(server, "GET", _url(paths) + "/precast")
    assert data["wait"] is False and data["held"] is False and data["announcedAt"]


def test_a_book_already_recording_is_not_announced(studio) -> None:
    paths, _db, _server, app, runner, pauses, toasts = studio
    _call(_server, "PUT", _url(paths) + "/precast", {"wait": True})
    runner._running.add(str(paths.root.resolve()))  # bộ thử: chương đã thu xong
    app._precast_tick()
    assert pauses == [] and toasts == []


def test_the_review_says_how_far_recording_has_reached(studio) -> None:
    paths, db, server, _app, _runner, _pauses, _toasts = studio
    status, data = _call(server, "GET", _url(paths) + "/precast")
    assert status == 200
    assert data["recordedChapters"] == 1 and data["recordedThrough"]["id"] and data["upcoming"] == []

    _fresh_cast(db)
    status, data = _call(server, "GET", _url(paths) + "/precast")
    assert data["recordedThrough"] is None and [chapter["id"] for chapter in data["upcoming"]] == [data["chapters"]]


def test_work_cards_say_which_chapters_they_touch(tmp_path) -> None:
    from abook.webui.work_items import work_items

    paths, db = _book(tmp_path)
    with db.connect() as connection:
        connection.execute("UPDATE segments SET speaker='NPC_LOCAL_GUARD' WHERE stable_id='c1s4'")
        chapter_id = connection.execute("SELECT chapter_id FROM segments WHERE stable_id='c1s4'").fetchone()[0]
    unnamed = [item for item in work_items(paths.root)["items"] if item["kind"] == "unnamed"]
    assert unnamed and unnamed[0]["chapters"] == [chapter_id]


def test_the_phone_can_review_through_the_remote_studio() -> None:
    from abook.webui.remote_studio import permitted

    assert permitted("GET", "/api/books/abc123/precast")
    assert permitted("PUT", "/api/books/abc123/precast")


# ---- Supervisor giữ (background_runner._hold_for_review): sống cả khi app đóng -------------------------------------------


def _fake_worker_reviewed(project_root, message_queue, pause_event, _stop_event, _parent_pid, _resource_overrides,
                          _resource_queue) -> None:
    """Như dây chuyền sau phân vai: đứng khi được bảo tạm dừng. Thấy tạm dừng thì đóng vai người duyệt bấm "Thu âm" (yêu cầu
    làm tiếp cùng đường với request_pause + sổ của Studio), rồi xem supervisor có giữ lại lần nữa không."""
    import json as _json
    import os
    import time

    from abook import background_runner
    from abook.webui import precast

    message_queue.put({"kind": "worker_ready", "pid": os.getpid(), "project_root": project_root})
    if not pause_event.wait(3.0):
        message_queue.put({"kind": "finished", "ok": True, "text": "never paused"})
        return
    paths = background_runner.BackgroundPaths.for_project(project_root)
    state = _json.loads(paths.state.read_text(encoding="utf-8"))
    precast.release(Path(project_root))
    background_runner._write_pause_request(paths, state, False)
    deadline = time.monotonic() + 5.0
    while pause_event.is_set() and time.monotonic() < deadline:
        time.sleep(0.02)
    time.sleep(0.5)  # vài nhịp kiểm nữa: không được giữ lại
    text = "held again" if pause_event.is_set() else "held once"
    message_queue.put({"kind": "finished", "ok": True, "text": text})


def _supervise(tmp_path, monkeypatch, *, wait: bool):
    from abook import background_runner, power_source
    from abook.webui import precast

    paths, db = _book(tmp_path)
    _fresh_cast(db)
    if wait:
        precast.set_wait(paths.root, True)
    monkeypatch.setenv("ABOOK_PREFERENCES", str(tmp_path / "preferences.json"))
    monkeypatch.setattr(background_runner, "POWER_CHECK_SECONDS", 0.0)
    monkeypatch.setattr(power_source, "on_battery", lambda: False)
    code = background_runner.run_supervisor(paths.root, "fake-precast", worker_target=_fake_worker_reviewed,
                                            poll_seconds=0.01)
    return paths, code, background_runner.tail_log(paths.root, lines=60)


def test_the_supervisor_holds_once_for_review_without_the_app(tmp_path, monkeypatch) -> None:
    from abook.background_runner import get_status
    from abook.webui import precast

    paths, code, log = _supervise(tmp_path, monkeypatch, wait=True)
    assert code == 0, log
    assert get_status(paths.root).detail == "held once", log
    assert log.count("PRECAST_HOLD analysis done") == 1
    assert precast.read(paths.root)["heldAt"] is not None


def test_the_supervisor_does_not_hold_when_waiting_is_off(tmp_path, monkeypatch) -> None:
    from abook.background_runner import get_status
    from abook.webui import precast

    paths, code, log = _supervise(tmp_path, monkeypatch, wait=False)
    assert code == 0, log
    assert get_status(paths.root).detail == "never paused"
    assert "PRECAST_HOLD" not in log and precast.read(paths.root)["heldAt"] is None


def test_an_unreadable_book_never_holds(tmp_path) -> None:
    from abook.webui import precast

    root = tmp_path / "broken"
    root.mkdir()
    precast.set_wait(root, True)
    (root / "project.sqlite3").write_bytes(b"not a database")
    assert precast.hold_due(root) is False
