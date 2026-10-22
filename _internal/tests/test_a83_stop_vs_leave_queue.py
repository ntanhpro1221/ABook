"""Soát a83 B1: "Bỏ xếp hàng" là lệnh RIÊNG (`/dequeue`), không bao giờ dừng một cuốn đã vào chạy - dừng giữa pha phân tích là đổi quyển sách."""
from __future__ import annotations

from pathlib import Path

import pytest

from abook.webui.library import book_id
from abook.webui.server import ApiError
from tests import book_edits_fixtures as shared
from tests import test_edits_inbox as T
from tests.test_bookfile_music import _plan


@pytest.fixture()
def book(tmp_path: Path):
    producer = tmp_path / "may_tinh"
    producer.mkdir()
    project = shared.make_base_project(producer)
    _plan(project)
    app = T._app(tmp_path, project)
    return app, project, book_id(project)


def test_leave_queue_removes_a_queued_book(book) -> None:
    app, project, bid = book
    app.queue.append(bid)
    app.leave_queue(bid)
    assert bid not in app.queue
    assert not app.runner.running(project)


def test_leave_queue_never_stops_a_book_that_already_started(book) -> None:
    app, project, bid = book
    app.runner.start(project)  # hàng vừa trao lượt: đã chạy, không còn trong hàng
    with pytest.raises(ApiError) as caught:
        app.leave_queue(bid)
    assert caught.value.status == 409
    assert "đã bắt đầu chạy" in caught.value.message
    assert app.runner.running(project)


def test_leave_queue_never_stops_a_book_that_is_starting(book) -> None:
    app, project, bid = book
    app.queue.append(bid)
    assert app.jobs.reserve(project)
    with pytest.raises(ApiError):
        app.leave_queue(bid)
    assert bid in app.queue or app.jobs.starting(project)


def test_remote_studio_lets_the_phone_leave_the_queue() -> None:
    from abook.webui.remote_studio import permitted

    assert permitted("POST", "/api/books/0123456789ab/dequeue")
