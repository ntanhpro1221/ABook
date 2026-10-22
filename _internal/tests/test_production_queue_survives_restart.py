"""Hàng đợi sản xuất sống qua lần đóng / mở app (soát a73, F1): cuốn thứ hai xếp hàng sau cuốn đang chạy, đóng app rồi
mở lại thì hàng còn nguyên và tự chạy tiếp khi cuốn đang chạy (worker sống ngoài app) xong - đúng lời hứa "tự bắt đầu
khi cuốn ấy xong" lúc tạo sách."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from abook.webui import server as server_module
from abook.webui.library import book_id
from tests.test_a_project_can_be_renamed_or_deleted import studio  # noqa: F401 - fixture dùng chung
from tests.test_create_many_volumes import _chapters


def _reopen(app, running: Path):
    """Mở lại app trên cùng thư mục dữ liệu; worker của `running` vẫn sống (nó chạy ngoài app)."""
    from abook.webui.actions import FakeRunner
    from abook.webui.listening import Listening
    from abook.webui.server import App

    runner = FakeRunner()
    runner._running.add(str(running))
    return App(preferences=app.preferences, runner=runner, token="t", listening=Listening(app.listening.path))


def test_the_saved_queue_drains_after_the_app_is_reopened(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    paths, app, _server, _runner = studio
    folder = _chapters(tmp_path / "sach2", ["Chương 1"])
    second = app._create_book({"profile": "fast"}, [str(next(folder.glob("*.txt")))], "Sách hai", None)
    saved = app.preferences.path.with_name(server_module.QUEUE_FILE)
    # Hàng của lần mở trước; mục trỏ dự án đã mất (xoá ngoài app) thì bỏ lúc mở lại, mục trùng chỉ giữ một.
    saved.write_bytes(json.dumps(["khong-con-du-an-nay", book_id(second), book_id(second)]).encode("utf-8"))

    real_sleep = time.sleep
    parked, release = threading.Event(), threading.Event()
    rounds = {"main": 0, "queue": 0}

    def one_round(seconds: float) -> None:
        if seconds != 15:
            return real_sleep(seconds)
        if threading.current_thread().name == "production-queue":
            rounds["queue"] += 1
            if rounds["queue"] == 2:  # người xếp hàng của app mở lại: một lượt rồi đứng chờ bài thử
                parked.set()
                release.wait(10)
            return None
        rounds["main"] += 1
        if rounds["main"] == 2:
            raise SystemExit  # cắt vòng lặp gọi trực tiếp sau một lượt
        return None

    monkeypatch.setattr(server_module.time, "sleep", one_round)
    reopened = _reopen(app, paths.root)

    assert reopened.queue == [book_id(second)]
    assert json.loads(saved.read_text(encoding="utf-8")) == [book_id(second)]
    thread = reopened._queue_thread
    assert thread is not None, "mở lại app là người xếp hàng chạy tiếp, không cần bấm gì"
    assert parked.wait(5)
    assert reopened.queue == [book_id(second)], "cuốn trước còn chạy: vẫn chờ"
    assert not reopened.jobs.starting(second) and not reopened.runner.running(second)

    reopened.runner._running.clear()  # cuốn trước xong
    try:
        reopened._drain_queue()
    except SystemExit:
        pass
    release.set()
    thread.join(5)

    assert reopened.queue == [] and json.loads(saved.read_text(encoding="utf-8")) == []
    assert reopened.jobs.starting(second) or reopened.runner.running(second), "tới lượt thì tự bắt đầu"
    assert not thread.is_alive() and reopened._queue_thread is None


def test_stopping_a_queued_book_takes_it_off_the_saved_queue(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, _server, _runner = studio
    folder = _chapters(tmp_path / "sach2", ["Chương 1"])
    second = app._create_book({"profile": "fast"}, [str(next(folder.glob("*.txt")))], "Sách hai", None)
    app.start(book_id(paths.root), now=True)
    app.start(book_id(second))
    saved = app.preferences.path.with_name(server_module.QUEUE_FILE)
    assert json.loads(saved.read_text(encoding="utf-8")) == [book_id(second)], "ghi ra đĩa ngay khi xếp hàng"

    app.stop(book_id(second))

    assert app.queue == []
    assert json.loads(saved.read_text(encoding="utf-8")) == []
    assert _reopen(app, paths.root).queue == [], "bỏ khỏi hàng rồi thì mở lại app không chạy nó"
