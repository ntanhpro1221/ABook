import threading

from abook.webui import bookfile
from tests.test_bookfile_job import _wait
from tests.test_export_series import series, _studio, _get, _post  # noqa: F401


def test_series_pack_has_progress_and_can_stop_before_publishing(series, tmp_path):
    from abook.webui.export_jobs import Cancelled
    import pytest

    _library, parts = series
    seen = []

    def progress(phase, done, total):
        seen.append(phase)
        if phase == "write" and done > 0:
            raise Cancelled()

    with pytest.raises(Cancelled):
        bookfile.pack_series(parts, tmp_path / "out.abook", progress=progress)
    assert {"prepare", "listen", "hash", "write"} <= set(seen)
    assert not list(tmp_path.glob("*.abook")) and not list(tmp_path.glob("*.part"))


def test_series_job_reconnects_with_same_id_and_progress(series, tmp_path, monkeypatch):
    library, parts = series
    app, server = _studio(tmp_path, library)
    reached, release = threading.Event(), threading.Event()
    real = bookfile.seal

    def slow(*args, **kwargs):
        if kwargs.get("progress"):
            kwargs["progress"]("hash", 1, 3)
        reached.set()
        assert release.wait(10)
        return real(*args, **kwargs)

    monkeypatch.setattr(bookfile, "seal", slow)
    try:
        status, started = _post(server, parts[0], "bookfile-job", {"target": str(tmp_path / "out"), "series": True, "single": True})
        assert status == 202 and started["id"] and reached.wait(10)
        current = _get(server, parts[0], "bookfile-job")[1]
        assert current["id"] == started["id"] and current.get("phase") == "hash"
        assert (current["done"], current["total"]) == (1, 3)
        release.set()
        done = _wait(server, parts[0])
        assert done["id"] == started["id"] and len(done["result"]["parts"]) == 3
        assert _get(server, parts[0], "bookfile-job")[1]["result"] == done["result"]
    finally:
        release.set()
        app.bookfile_jobs.shutdown()
        server.stop()
