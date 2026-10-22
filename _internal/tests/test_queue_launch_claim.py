"""Nhận lượt phải kiểm lại hàng và máy rảnh; hàng trên đĩa còn tới khi jobs nhận start."""
import json

import pytest

from abook.webui import server as server_module
from abook.webui.library import book_id
from tests.test_a_project_can_be_renamed_or_deleted import studio  # noqa: F401
from tests.test_create_many_volumes import _chapters


def _queued(studio, tmp_path, monkeypatch):
    paths, app, _server, runner = studio
    folder = _chapters(tmp_path / "second", ["Chương 1"])
    second = app._create_book({"profile": "fast"}, [str(next(folder.glob("*.txt")))], "Hai", None)
    app.queue = [book_id(second)]
    app._save_queue()
    rounds = 0

    def sleep(seconds):
        nonlocal rounds
        if seconds == 15:
            rounds += 1
            if rounds > 1:
                raise SystemExit

    monkeypatch.setattr(server_module.time, "sleep", sleep)
    return paths, app, runner, second


@pytest.mark.parametrize("action", ["start", "remove"])
def test_user_action_between_head_lookup_and_claim_is_rechecked(studio, tmp_path, monkeypatch, action):
    paths, app, runner, second = _queued(studio, tmp_path, monkeypatch)
    resolve = app.library.resolve
    launched = []
    fired = False

    def interleave(value):
        nonlocal fired
        path = resolve(value)
        if not fired and value == book_id(second):
            fired = True
            if action == "remove":
                app.stop(value)
            else:
                app.start(book_id(paths.root))
        return path

    def launch(path, **kwargs):
        launched.append(path)
        runner._running.add(str(path))

    monkeypatch.setattr(app.library, "resolve", interleave)
    monkeypatch.setattr(app, "_launch", launch)
    with pytest.raises(SystemExit):
        app._drain_queue()
    assert second not in launched
    assert launched == ([paths.root] if action == "start" else [])


def test_interruption_before_jobs_accept_start_preserves_saved_queue(studio, tmp_path, monkeypatch):
    _paths, app, _runner, second = _queued(studio, tmp_path, monkeypatch)

    def interrupted():
        assert json.loads(app._queue_path.read_text(encoding="utf-8")) == [book_id(second)]
        raise SystemExit

    monkeypatch.setattr(app.previews, "shutdown", interrupted)
    with pytest.raises(SystemExit):
        app._drain_queue()
    assert json.loads(app._queue_path.read_text(encoding="utf-8")) == [book_id(second)]
    assert not app.jobs.starting(second)


def test_accepted_start_removes_saved_queue(studio, tmp_path, monkeypatch):
    _paths, app, runner, second = _queued(studio, tmp_path, monkeypatch)
    monkeypatch.setattr(runner, "start", lambda path: runner._running.add(str(path)))
    with pytest.raises(SystemExit):
        app._drain_queue()
    assert json.loads(app._queue_path.read_text(encoding="utf-8")) == []
    assert runner.running(second) or app.jobs.starting(second)


def test_start_during_drainer_preparation_sees_the_claim(studio, tmp_path, monkeypatch):
    paths, app, runner, second = _queued(studio, tmp_path, monkeypatch)
    entered = False

    def user_starts_other_book():
        nonlocal entered
        if not entered:
            entered = True
            assert app.jobs.starting(second)
            app.start(book_id(paths.root))

    monkeypatch.setattr(app.previews, "shutdown", user_starts_other_book)
    monkeypatch.setattr(runner, "start", lambda path: runner._running.add(str(path)))
    # Không tạo người xếp hàng nền: vòng gọi trực tiếp này đang giữ lượt ấy.
    import threading
    app._queue_thread = threading.current_thread()
    with pytest.raises(SystemExit):
        app._drain_queue()
    assert app.queue == [book_id(paths.root)]
    assert not runner.running(paths.root) and not app.jobs.starting(paths.root)
