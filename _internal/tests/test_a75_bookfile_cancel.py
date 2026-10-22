import threading
from pathlib import Path

import pytest

from abook.webui import bookfile, export_jobs
from tests.test_bookfile_job import _wait
from tests.test_export_series import _get, _part, _post, _studio


def test_cancel_endpoint_stops_packaging_and_removes_partial(tmp_path, monkeypatch):
    library = tmp_path / "library"
    library.mkdir()
    project = _part(tmp_path, library, "p1", "Sách thử")
    app, server = _studio(tmp_path, library)
    entered, release = threading.Event(), threading.Event()
    real = bookfile.write_entries

    def slow(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        return real(*args, **kwargs)

    monkeypatch.setattr(bookfile, "write_entries", slow)
    target = tmp_path / "out"
    try:
        assert _post(server, project, "bookfile-job", {"target": str(target)})[0] == 202
        assert entered.wait(10)
        assert _post(server, project, "bookfile-job/cancel", {})[0] == 200
        release.set()
        assert _wait(server, project, "cancelled")["state"] == "cancelled"
    finally:
        release.set()
        server.stop()
        app.bookfile_jobs.shutdown()
    assert not list(target.rglob("*"))


def test_cancel_during_hash_leaves_no_package(tmp_path, monkeypatch):
    monkeypatch.setattr(bookfile, "_TICK", 1024)
    source = tmp_path / "source.mp3"
    source.write_bytes(b"x" * 4096)
    out = tmp_path / "out.abook"

    def progress(phase, done, total):
        if phase == "hash" and done > 0:
            raise export_jobs.Cancelled()

    with pytest.raises(export_jobs.Cancelled):
        bookfile.seal({"title": "Sách", "chapters": []}, {"chapters/1.mp3": source}, out, producer="test", version=1, progress=progress)
    assert not out.exists() and not list(tmp_path.glob("*.part"))


def test_app_close_shuts_down_bookfile_jobs(tmp_path, monkeypatch):
    library = tmp_path / "library"
    library.mkdir()
    app, server = _studio(tmp_path, library)
    calls = []
    # Đóng app bảo mọi lượt xuất dừng CÙNG LÚC (stop_all) rồi chờ chung một hạn CLOSE_SECONDS, không shutdown từng loại.
    monkeypatch.setattr(app.bookfile_jobs, "stop_all", lambda: calls.append(True) or [])
    try:
        app.close()
        assert calls
    finally:
        server.stop()
