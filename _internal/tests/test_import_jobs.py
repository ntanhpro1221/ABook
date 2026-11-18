"""Lượt thêm sách là việc của máy chủ (abook/webui/import_jobs.py), không của màn "Thêm sách": sổ lượt, ghi qua lần khởi động lại, Thử lại, và
lỗi của lượt trước không bao giờ dính sang lượt sau (bản bench 15-11: .abook hỏng rồi TXT báo "Đây không phải file sách của app.")."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from abook.webui import import_jobs
from abook.webui.server import ApiError, Server
from tests import import_fixtures
from tests.async_wait import wait_for
from tests.test_project_file import _app
from tests.test_webui_listen_and_sync import _request

IMPORTS = import_fixtures.FIXTURES


def test_the_register_counts_every_change_and_never_shows_paths() -> None:
    jobs = import_jobs.ImportJobs(clock=lambda: 100.0)
    first = jobs.begin("book", "Sách.abook", {"path": "C:/riêng/Sách.abook"})
    assert jobs.revision == 1
    jobs.fail(first, "Đây không phải file sách của app.")
    second = jobs.begin("text", "Sách thử", {"path": "C:/riêng/Sách.txt"})
    jobs.finish(second, {"id": "b1", "how": "new", "chapters": 3})
    view = jobs.view()
    assert view["revision"] == 4
    assert [row["state"] for row in view["jobs"]] == ["failed", "done"]
    assert view["jobs"][0]["problem"] == "Đây không phải file sách của app."
    assert view["jobs"][1]["result"] == {"id": "b1", "how": "new"}
    assert "C:/riêng" not in json.dumps(view, ensure_ascii=False)
    assert not jobs.dismiss("khongco") and jobs.dismiss(first) and len(jobs.view()["jobs"]) == 1


def test_only_the_latest_ended_jobs_are_kept_and_running_ones_never_drop() -> None:
    jobs = import_jobs.ImportJobs()
    running = jobs.begin("book", "Đang chạy.abook", {"path": "x"})
    for index in range(import_jobs.KEEP + 5):
        jobs.finish(jobs.begin("book", f"{index}.abook", {"path": str(index)}), {"id": str(index), "how": "new"})
    rows = jobs.view()["jobs"]
    assert rows[0]["id"] == running and rows[0]["state"] == "running"
    assert len(rows) == import_jobs.KEEP + 1
    assert rows[-1]["name"] == f"{import_jobs.KEEP + 4}.abook"
    assert not jobs.dismiss(running)


def test_a_job_cut_by_closing_the_app_comes_back_as_interrupted_and_its_staging_is_swept(tmp_path: Path) -> None:
    journal = tmp_path / import_jobs.FILE_NAME
    library = tmp_path / "library"
    library.mkdir()
    old_part = library / ".cu.00000000.part"
    old_part.mkdir()
    # Một giờ trước lúc thư mục ấy được tạo - mốc lấy từ chính ổ đĩa, không từ đồng hồ của test.
    hour_ago = old_part.stat().st_mtime - 3600
    import os
    os.utime(old_part, (hour_ago, hour_ago))
    jobs = import_jobs.ImportJobs(journal)
    cut = jobs.begin("book", "Sách lớn.abook", {"path": str(tmp_path / "Sách lớn.abook"), "allowOlder": False})
    left = library / ".Sach.1a2b3c4d.part"
    (left / "chapters").mkdir(parents=True)
    (left / "chapters" / "1.mp3").write_bytes(b"nua chung")
    book = library / "Sach cu"
    book.mkdir()
    unrelated = library / ".personal.part"
    unrelated.mkdir()
    # App thoát ở đây (không finish / fail). Lần mở sau:
    again = import_jobs.ImportJobs(journal)
    row = again.view()["jobs"][0]
    assert row["id"] == cut and row["state"] == "interrupted"
    assert again.get(cut)["params"]["path"].endswith("Sách lớn.abook"), "Thử lại cần đủ thông số của lượt"
    assert import_jobs.sweep_parts(library, again.interrupted) == 1
    assert not left.exists(), "thư mục tạm của lượt dở bị dọn - không bao giờ thành nửa cuốn"
    assert old_part.exists() and book.exists() and unrelated.exists(), "only app staging created since the interrupted job is removed"
    assert json.loads(journal.read_text(encoding="utf-8"))[0]["state"] == "interrupted"


def _wait(app, predicate, seconds: float = 20.0):
    """Sổ lượt khi `predicate` đúng; `seconds` chỉ là chốt chặn treo (nhân hệ số máy tải - tests/async_wait.py)."""
    view = wait_for(lambda: (lambda current: current if predicate(current) else None)(app.import_jobs.view()), seconds, 0.05)
    if not view:
        raise AssertionError(app.import_jobs.view())
    return view


def test_every_import_is_a_job_and_a_broken_book_file_never_spoils_the_next_text(tmp_path: Path) -> None:
    library = tmp_path / "library"
    app = _app(tmp_path, library)
    broken = tmp_path / "Sach_lon.abook"
    broken.write_bytes(bytes(64 * 1024))
    with pytest.raises(ApiError) as refused:
        app.open_book_file(str(broken))
    txt = tmp_path / "Sach_thu.txt"
    shutil.copyfile(IMPORTS / "whole.txt", txt)
    app.preview_text_book(str(txt))
    added = app.add_text_book(str(txt), "Sách thử")
    assert added["how"] == "new"
    view = app.import_jobs.view()
    assert [(row["kind"], row["state"]) for row in view["jobs"]] == [("book", "failed"), ("text", "done")]
    assert view["jobs"][0]["problem"] == refused.value.message
    assert view["jobs"][1]["result"]["id"] == added["id"] and view["jobs"][1]["problem"] == ""


def test_a_broken_text_never_spoils_the_next_book_file(tmp_path: Path) -> None:
    from tests.test_text_books import _book_file

    library = tmp_path / "library"
    app = _app(tmp_path, library)
    broken = tmp_path / "Sach_hong.txt"
    broken.write_bytes(b"Noi dung.\x81")
    with pytest.raises(ApiError):
        app.add_text_book(str(broken), "Hỏng")
    opened = app.open_book_file(str(_book_file(tmp_path)))
    assert opened["how"] == "new"
    rows = app.import_jobs.view()["jobs"]
    assert [(row["kind"], row["state"]) for row in rows] == [("text", "failed"), ("book", "done")]
    assert rows[1]["result"] == {"id": opened["id"], "how": "new"} and rows[1]["problem"] == ""


def test_retry_runs_the_same_job_again_in_the_background(tmp_path: Path) -> None:
    library = tmp_path / "library"
    app = _app(tmp_path, library)
    txt = tmp_path / "Sach_thu.txt"
    with pytest.raises(ApiError):
        app.add_text_book(str(txt), "Sách thử")  # file chưa có
    failed = app.import_jobs.view()["jobs"][0]
    assert failed["state"] == "failed"
    shutil.copyfile(IMPORTS / "whole.txt", txt)
    assert app.retry_import(failed["id"])["retrying"] is True
    view = _wait(app, lambda v: v["jobs"] and v["jobs"][-1]["state"] == "done")
    assert [row["id"] for row in view["jobs"]] != [failed["id"]], "lượt cũ rời sổ, lượt mới thay chỗ"
    assert view["jobs"][-1]["result"]["how"] == "new"
    with pytest.raises(ApiError):
        app.retry_import(view["jobs"][-1]["id"])  # lượt đã xong thì không có gì để thử lại


def test_the_jobs_route_is_what_the_app_level_watchers_read(tmp_path: Path) -> None:
    library = tmp_path / "library"
    app = _app(tmp_path, library)
    txt = tmp_path / "Sach_thu.txt"
    shutil.copyfile(IMPORTS / "whole.txt", txt)
    server = Server(app, port=0).start()
    try:
        headers = {"X-Ebook-Token": "t"}
        status, data, _ = _request(server.port, "GET", "/api/listen/import/jobs", headers=headers)
        assert status == 200 and json.loads(data) == {"revision": 0, "jobs": []}
        status, data, _ = _request(server.port, "POST", "/api/listen/import", headers=headers, body={"path": str(txt), "title": "Sách thử"})
        assert status == 200
        status, data, _ = _request(server.port, "GET", "/api/listen/import/jobs", headers=headers)
        view = json.loads(data)
        assert view["revision"] == 2 and view["jobs"][0]["state"] == "done" and view["jobs"][0]["name"] == "Sách thử"
        job = view["jobs"][0]["id"]
        status, _, _ = _request(server.port, "POST", f"/api/listen/import/jobs/{job}/retry", headers=headers)
        assert status == 404
        status, data, _ = _request(server.port, "DELETE", f"/api/listen/import/jobs/{job}", headers=headers)
        assert status == 200 and json.loads(data) == {"removed": True}
    finally:
        server.stop()


def test_retry_is_visible_before_its_thread_starts(tmp_path: Path, monkeypatch) -> None:
    app = _app(tmp_path, tmp_path / "library")
    txt = tmp_path / "Sach_thu.txt"
    with pytest.raises(ApiError):
        app.add_text_book(str(txt), "Sách thử")
    failed = app.import_jobs.view()["jobs"][0]
    shutil.copyfile(IMPORTS / "whole.txt", txt)
    pending = []

    class DeferredThread:
        def __init__(self, *, target, args, **_kwargs):
            pending.append(lambda: target(*args))

        def start(self):
            pass

    monkeypatch.setattr("abook.webui.server.threading.Thread", DeferredThread)
    app.retry_import(failed["id"])
    running = app.import_jobs.view()["jobs"]
    assert len(running) == 1 and running[0]["state"] == "running"
    assert running[0]["id"] != failed["id"]
    pending.pop()()
    done = app.import_jobs.view()["jobs"]
    assert len(done) == 1 and done[0]["id"] == running[0]["id"] and done[0]["state"] == "done"
