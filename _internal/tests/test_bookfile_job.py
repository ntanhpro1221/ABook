"""Xuất file sách chạy nền (webui/export_jobs.py + POST/GET /api/books/<id>/bookfile-job): bấm là có mã ngay, đóng gói chạy trong luồng,
hỏi trạng thái lại được sau khi tải lại trang (bản ghi nhớ lần xuất gần nhất của cuốn)."""
from __future__ import annotations

import threading
import time
from pathlib import Path

from abook.webui import bookfile
from abook.webui.export_jobs import BookFileJobs
from tests.test_export_series import _get, _part, _post, _studio


def _wait(server, project: Path, state: str = "done") -> dict:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        status, job = _get(server, project, "bookfile-job")
        assert status == 200
        if job["state"] == state:
            return job
        time.sleep(0.05)
    raise AssertionError(f"việc xuất không tới trạng thái {state}: {job}")


def test_a_book_never_exported_reports_idle(tmp_path: Path) -> None:
    library = tmp_path / "thu_vien"
    library.mkdir()
    book = _part(tmp_path, library, "p1", "Truyện X")
    app, server = _studio(tmp_path, library)
    try:
        assert _get(server, book, "bookfile-job") == (200, {"state": "idle"})
    finally:
        server.stop()


def test_starting_an_export_returns_at_once_and_the_status_ends_with_the_file(tmp_path: Path) -> None:
    library = tmp_path / "thu_vien"
    library.mkdir()
    book = _part(tmp_path, library, "p1", "Truyện X")
    app, server = _studio(tmp_path, library)
    try:
        status, started = _post(server, book, "bookfile-job", {"target": str(tmp_path / "xuat")})
        done = _wait(server, book)
        again = _get(server, book, "bookfile-job")[1]  # "tải lại trang": hỏi lại vẫn thấy lần xuất vừa xong
    finally:
        server.stop()
    assert status == 202 and started["state"] in ("running", "done") and started["id"]
    file = tmp_path / "xuat" / f"Truyện X{bookfile.EXTENSION}"
    assert done["id"] == started["id"] and done["result"]["file"] == str(file) and file.is_file()
    assert done["result"]["size"] == file.stat().st_size and done["finishedAt"] >= done["startedAt"]
    assert again["state"] == "done" and again["result"] == done["result"]
    assert done["result"]["folder"] in app.exports, "nút Mở thư mục mở được thư mục vừa xuất"
    with bookfile.BookFile(file) as opened:
        opened.verify()


def test_a_failing_pack_ends_as_an_error_the_listener_can_read(tmp_path: Path, monkeypatch) -> None:
    library = tmp_path / "thu_vien"
    library.mkdir()
    book = _part(tmp_path, library, "p1", "Truyện X")

    def refuse(*_args, **_kwargs):
        raise bookfile.BookFileError("Ổ đĩa đầy")

    monkeypatch.setattr(bookfile, "pack", refuse)
    app, server = _studio(tmp_path, library)
    try:
        status, _ = _post(server, book, "bookfile-job", {"target": str(tmp_path / "xuat")})
        failed = _wait(server, book, "error")
        # lỗi không chặn lần xuất sau
        monkeypatch.undo()
        _post(server, book, "bookfile-job", {"target": str(tmp_path / "xuat")})
        retried = _wait(server, book)
    finally:
        server.stop()
    assert status == 202 and failed["error"] == "Ổ đĩa đầy" and "result" not in failed
    assert retried["id"] != failed["id"] and Path(retried["result"]["file"]).is_file()


def test_the_job_refuses_a_request_the_plain_export_would_refuse(tmp_path: Path) -> None:
    """Kiểm đầu vào (cả bộ mà cuốn lẻ) xảy ra ngay lúc bắt đầu, không để thành một việc nền chết."""
    library = tmp_path / "thu_vien"
    library.mkdir()
    lone = _part(tmp_path, library, "p1", "Cuốn lẻ")
    app, server = _studio(tmp_path, library)
    try:
        status, result = _post(server, lone, "bookfile-job", {"target": str(tmp_path / "xuat"), "series": True})
        idle = _get(server, lone, "bookfile-job")[1]
    finally:
        server.stop()
    assert status == 409 and "chưa có phần nào khác" in result["error"] and idle == {"state": "idle"}


def test_a_second_start_while_running_returns_the_running_job() -> None:
    now = [100.0]
    jobs = BookFileJobs(clock=lambda: now[0])
    release = threading.Event()
    calls: list[int] = []

    def work() -> dict:
        calls.append(1)
        release.wait(5)
        return {"file": "x.abook", "folder": "d", "size": 3}

    first = jobs.start("a", work)
    now[0] = 107.5
    second = jobs.start("a", work)
    other = jobs.start("b", lambda: {"file": "y.abook", "folder": "d", "size": 1})
    assert first["state"] == "running" and second["id"] == first["id"] and second["elapsed"] == 7.5
    assert other["id"] != first["id"], "mỗi cuốn một bản ghi"
    release.set()
    deadline = time.monotonic() + 5
    while jobs.status("a")["state"] == "running" and time.monotonic() < deadline:
        time.sleep(0.01)
    assert jobs.status("a")["state"] == "done" and calls == [1], "không đóng gói hai lần cùng lúc"
