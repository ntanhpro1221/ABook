"""Soát a61 (uxfix69): "Xuất MP3" của Studio là việc nền như M4B (POST /api/books/<id>/mp3-job -> 202 ngay, GET mp3-job, POST mp3-job/cancel):
đóng hộp Xuất giữa chừng không mất tiến độ lẫn nút Huỷ. Đường đồng bộ cũ `POST /export` không còn."""
from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path

import pytest

from abook.webui import export
from abook.webui.library import book_id
from tests.test_export_music import _studio_book
from tests.test_webui_listen_and_sync import _request
from tests.test_export_series import _get, _mp3_job, _part, _post, _studio, fake_ffmpeg, series  # noqa: F401 - fixture


def _wait(predicate, seconds: float = 20.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_the_job_answers_202_at_once_and_reports_chapter_progress(series, tmp_path: Path, fake_ffmpeg, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    library, parts = series
    app, server = _studio(tmp_path, library)
    gate = threading.Event()
    seen = threading.Event()
    real = export.write_chapter

    def slow(*args, **kwargs):  # chương đang ghi: đứng lại cho test hỏi tiến độ
        seen.set()
        gate.wait(20)
        return real(*args, **kwargs)

    monkeypatch.setattr(export, "write_chapter", slow)
    try:
        started = time.monotonic()
        status, job = _post(server, parts[0], "mp3-job", {"target": str(tmp_path / "xuat")})
        assert status == 202 and job["state"] == "running" and time.monotonic() - started < 2.0
        assert seen.wait(20)
        running = _get(server, parts[0], "mp3-job")[1]
        assert (running["state"], running["phase"], running["chapter"], running["chapters"]) == ("running", "chapters", 1, 1)
        assert app.running_exports()["mp3"][0]["bookId"] == book_id(parts[0]), "giao diện mở lại thấy việc đang chạy"
        gate.set()
        assert _wait(lambda: _get(server, parts[0], "mp3-job")[1]["state"] == "done")
    finally:
        gate.set()
        server.stop()
    assert app.mp3_jobs.status(str(parts[0]))["result"]["files"] == 1
    assert str(tmp_path / "xuat" / "Truyện X") in app.exports


def test_cancelling_between_chapters_ends_cancelled_within_two_seconds_and_removes_the_half_written_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, _tracks = _studio_book(tmp_path)  # hai chương: huỷ sau chương 1 thì chương 2 không được ghi
    app, server = _studio(tmp_path, project.parent)
    monkeypatch.setattr(export, "ffmpeg_executable", lambda: "ffmpeg")
    wrote = threading.Event()
    gate = threading.Event()

    def copy(command: list[str], **_: object) -> None:
        shutil.copyfile(Path(command[command.index("-i") + 1]), Path(command[-1]))
        wrote.set()
        gate.wait(20)  # chương đã ghi xong: chờ test bấm Huỷ

    monkeypatch.setattr(export, "run_hidden", copy)
    target = tmp_path / "xuat"
    try:
        assert _post(server, project, "mp3-job", {"target": str(target)})[0] == 202
        assert wrote.wait(20)
        status, answer = _post(server, project, "mp3-job/cancel", {})
        assert status == 200 and answer["state"] == "running"
        asked = time.monotonic()
        gate.set()
        assert _wait(lambda: _get(server, project, "mp3-job")[1]["state"] == "cancelled")
        assert time.monotonic() - asked < 2.0
    finally:
        gate.set()
        server.stop()
    assert not target.exists() or sorted(target.rglob("*")) == [], "thư mục xuất dở bị xoá"


def test_closing_the_app_stops_a_running_mp3_job(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    library = tmp_path / "thu_vien"
    library.mkdir()
    project = _part(tmp_path, library, "p1", "Truyện X")
    app, server = _studio(tmp_path, library)
    monkeypatch.setattr(export, "ffmpeg_executable", lambda: "ffmpeg")
    started = threading.Event()

    def slow(command: list[str], **_: object) -> None:
        started.set()
        time.sleep(0.4)
        shutil.copyfile(Path(command[command.index("-i") + 1]), Path(command[-1]))

    monkeypatch.setattr(export, "run_hidden", slow)
    try:
        assert _post(server, project, "mp3-job", {"target": str(tmp_path / "xuat")})[0] == 202
        assert started.wait(20)
        begun = time.monotonic()
        app.close()
        assert time.monotonic() - begun < 5.0
        assert app.mp3_jobs.status(str(project))["state"] in ("cancelled", "done"), "luồng đã dừng, không còn chạy"
    finally:
        server.stop()


def test_a_failure_is_recorded_as_an_error_with_words_not_a_server_error(tmp_path: Path) -> None:
    library = tmp_path / "thu_vien"
    library.mkdir()
    project = _part(tmp_path, library, "p1", "Truyện X", finished=False)  # không có chương nào nghe được
    app, server = _studio(tmp_path, library)
    try:
        job = _mp3_job(server, project, {"target": str(tmp_path / "xuat")})
    finally:
        server.stop()
    assert job["state"] == "error" and "chưa có chương nào nghe được" in job["error"]
    assert not (tmp_path / "xuat" / "Truyện X").exists() or not any((tmp_path / "xuat" / "Truyện X").iterdir())


def test_the_old_synchronous_export_route_is_gone(tmp_path: Path) -> None:
    project, _tracks = _studio_book(tmp_path)
    app, server = _studio(tmp_path, project.parent)
    try:
        status, _data, _ = _request(server.port, "POST", f"/api/books/{book_id(project)}/export", headers={"X-Ebook-Token": "t"},
                                    body={"target": str(tmp_path / "xuat")})
    finally:
        server.stop()
    assert status in (404, 405)
    assert not (tmp_path / "xuat").exists()
