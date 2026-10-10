"""Soát UX a21: xuất `.abookproj` của dự án 400 chương chạy đồng bộ ~86 s (băm audio + gom chương) - trình duyệt đứng chờ, không
biết tiến độ, không huỷ được. Giờ là việc nền một-lúc-một-cuốn như xuất nhạc nền: bắt đầu trả ngay, hỏi được pha + đã/tổng,
Huỷ dừng ở điểm kiểm kế và không để lại file (kể cả file tạm), đóng app thì huỷ gọn; file ra y hệt từng byte bản đồng bộ."""
from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path

import pytest

from abook.webui import export_jobs, projectfile
from abook.webui.library import book_id
from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung
from tests.test_webui_listen_and_sync import make_project


def _frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """File gói ghi giờ lúc đóng (createdAt, giờ của mục ZIP): đóng đứng giờ để hai lượt đóng cùng dự án so được từng byte."""
    class Fixed:
        @staticmethod
        def now(tz=None):  # như datetime.now
            from datetime import datetime
            return datetime(2026, 10, 10, 12, 0, 0, tzinfo=tz)

    monkeypatch.setattr(projectfile, "datetime", Fixed)
    monkeypatch.setattr(time, "localtime", lambda *_a: time.struct_time((2026, 10, 10, 12, 0, 0, 0, 283, -1)))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _slow_views(monkeypatch: pytest.MonkeyPatch, gate: threading.Event) -> None:
    """Chặn pack ở bước chụp màn xem (sau khi gom chương, trước khi băm) tới khi `gate` mở - để thử trạng thái "đang chạy" cho chắc."""
    real = projectfile.project_views.snapshot

    def slow(project_root, tick=None, verdicts=None):
        gate.wait(15)
        return real(project_root, tick, verdicts)

    monkeypatch.setattr(projectfile.project_views, "snapshot", slow)


def _wait(predicate, seconds: float = 15.0) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.03)
    return False


def _leftovers(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.rglob("*") if p.is_file()) if folder.exists() else []


def test_the_progress_callback_walks_the_phases_and_changes_nothing_in_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _frozen_clock(monkeypatch)
    project = make_project(tmp_path / "may")
    plain = projectfile.pack(project, tmp_path / "a" / "du_an.abookproj")
    seen: list[tuple[str, int, int]] = []
    watched = projectfile.pack(project, tmp_path / "b" / "du_an.abookproj", progress=lambda *step: seen.append(step))
    assert _sha(plain) == _sha(watched), "báo tiến độ không đổi một byte của file ra"
    phases = list(dict.fromkeys(phase for phase, _done, _total in seen))
    assert phases == ["prepare", "listen", "views", "hash", "write"], phases
    for phase in ("hash", "write"):
        steps = [(done, total) for name, done, total in seen if name == phase]
        assert steps and all(total == steps[0][1] and total > 0 for _done, total in steps), "tổng không đổi trong một pha"
        assert [done for done, _total in steps] == sorted(done for done, _total in steps), "đã làm chỉ tăng"
        assert steps[-1][0] <= steps[-1][1]
    assert [done for name, done, _total in seen if name == "listen"][-1] <= max(total for name, _done, total in seen if name == "listen")


def test_cancelling_in_the_middle_of_the_write_leaves_no_file_at_all(tmp_path: Path) -> None:
    project = make_project(tmp_path / "may")
    out = tmp_path / "ra" / "du_an.abookproj"

    def cancel_on_second_entry(phase: str, done: int, total: int) -> None:
        if phase == "write" and done > 0:
            raise export_jobs.Cancelled()

    with pytest.raises(export_jobs.Cancelled):
        projectfile.pack(project, out, progress=cancel_on_second_entry)
    assert _leftovers(tmp_path / "ra") == [], "không file thật, không file .part dở"


def test_a_target_that_cannot_be_written_fails_before_the_long_work(tmp_path: Path) -> None:
    project = make_project(tmp_path / "may")
    blocker = tmp_path / "la_mot_file"
    blocker.write_bytes(b"x")
    seen: list[str] = []
    with pytest.raises(OSError):
        projectfile.pack(project, blocker / "ra" / "du_an.abookproj", progress=lambda phase, _done, _total: seen.append(phase))
    assert set(seen) <= {"prepare"}, "hỏng ở chỗ ghi thì báo ngay, không băm cả dự án rồi mới báo"


def test_starting_answers_at_once_and_the_state_moves_to_done(studio, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    book = book_id(paths.root)
    gate = threading.Event()
    _slow_views(monkeypatch, gate)
    started = time.perf_counter()
    status, data = _call(server, "POST", f"/api/books/{book}/projectfile-job", {"target": str(tmp_path / "ra")})
    assert time.perf_counter() - started < 1.0, "bắt đầu trả ngay, không chờ đóng gói"
    assert status == 202 and data["state"] == "running" and data["id"]
    assert _wait(lambda: _call(server, "GET", f"/api/books/{book}/projectfile-job")[1].get("phase") == "views")
    status, running = _call(server, "GET", f"/api/books/{book}/projectfile-job")
    assert status == 200 and running["state"] == "running" and "elapsed" in running
    assert _call(server, "POST", f"/api/books/{book}/projectfile-job", {"target": str(tmp_path / "ra")})[1]["id"] == data["id"], \
        "đang chạy thì bấm lần nữa trả đúng lượt ấy (một-lúc-một-cuốn)"
    _status, jobs = _call(server, "GET", "/api/export-jobs")
    assert [item["bookId"] for item in jobs["projectfile"]] == [book], "hộp Xuất mở lại / tải lại trang vẫn tìm thấy việc đang chạy"
    gate.set()
    assert _wait(lambda: _call(server, "GET", f"/api/books/{book}/projectfile-job")[1]["state"] != "running")
    _status, done = _call(server, "GET", f"/api/books/{book}/projectfile-job")
    assert done["state"] == "done", done
    result = done["result"]
    assert Path(result["file"]).is_file() and result["size"] == Path(result["file"]).stat().st_size
    assert result["folder"] == str(tmp_path / "ra") and result["missingSources"] == []
    assert _call(server, "GET", "/api/export-jobs")[1]["projectfile"] == []
    assert app.exports and str(tmp_path / "ra") in app.exports


def test_the_background_file_is_the_same_bytes_as_the_synchronous_one(studio, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    paths, _app, server, _runner = studio
    book = book_id(paths.root)
    _frozen_clock(monkeypatch)
    status, direct = _call(server, "POST", f"/api/books/{book}/projectfile", {"target": str(tmp_path / "dong_bo")})
    assert status == 200
    _call(server, "POST", f"/api/books/{book}/projectfile-job", {"target": str(tmp_path / "nen")})
    assert _wait(lambda: _call(server, "GET", f"/api/books/{book}/projectfile-job")[1]["state"] == "done")
    background = _call(server, "GET", f"/api/books/{book}/projectfile-job")[1]["result"]
    assert Path(background["file"]).name == Path(direct["file"]).name
    assert _sha(Path(background["file"])) == _sha(Path(direct["file"]))
    assert background["size"] == direct["size"] and background["missingSources"] == direct["missingSources"]


def test_cancel_stops_the_job_and_leaves_no_file_behind(studio, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    paths, _app, server, _runner = studio
    book = book_id(paths.root)
    gate = threading.Event()
    _slow_views(monkeypatch, gate)
    _call(server, "POST", f"/api/books/{book}/projectfile-job", {"target": str(tmp_path / "ra")})
    assert _wait(lambda: _call(server, "GET", f"/api/books/{book}/projectfile-job")[1].get("phase") == "views")
    status, data = _call(server, "POST", f"/api/books/{book}/projectfile-job/cancel", {})
    assert status == 200 and data["state"] == "running", "Huỷ dừng ở điểm kiểm kế, chưa dừng ngay"
    gate.set()
    assert _wait(lambda: _call(server, "GET", f"/api/books/{book}/projectfile-job")[1]["state"] != "running")
    assert _call(server, "GET", f"/api/books/{book}/projectfile-job")[1]["state"] == "cancelled"
    assert _leftovers(tmp_path / "ra") == [], "không file thật, không file tạm"
    assert _call(server, "POST", f"/api/books/{book}/projectfile-job/cancel", {})[1]["state"] == "cancelled", "hết việc: Huỷ không làm gì thêm"


def test_a_failure_reads_plainly_and_a_new_job_can_follow(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    book = book_id(paths.root)
    app.runner.running = lambda project: True  # type: ignore[method-assign]
    _call(server, "POST", f"/api/books/{book}/projectfile-job", {"target": str(tmp_path / "ra")})
    assert _wait(lambda: _call(server, "GET", f"/api/books/{book}/projectfile-job")[1]["state"] != "running")
    failed = _call(server, "GET", f"/api/books/{book}/projectfile-job")[1]
    assert failed["state"] == "error" and "đang chạy" in failed["error"]
    app.runner.running = lambda project: False  # type: ignore[method-assign]
    _call(server, "POST", f"/api/books/{book}/projectfile-job", {"target": str(tmp_path / "ra")})
    assert _wait(lambda: _call(server, "GET", f"/api/books/{book}/projectfile-job")[1]["state"] == "done")


def test_closing_the_app_in_the_middle_cancels_cleanly_within_seconds(studio, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    book = book_id(paths.root)
    reached = threading.Event()
    real = projectfile.project_views.snapshot

    def slow(project_root, tick=None, verdicts=None):
        reached.set()
        _wait(lambda: False, 1.0)  # chụp màn xem lâu hơn một chút, chưa tới băm
        return real(project_root, tick, verdicts)

    monkeypatch.setattr(projectfile.project_views, "snapshot", slow)
    _call(server, "POST", f"/api/books/{book}/projectfile-job", {"target": str(tmp_path / "ra")})
    assert reached.wait(10)
    started = time.perf_counter()
    app.close()
    assert time.perf_counter() - started < 5.0, "đóng app không chờ lâu"
    assert app.projectfile_jobs.running() == [], "việc đã dừng, không còn luồng đóng gói chạy"
    assert _call(server, "GET", f"/api/books/{book}/projectfile-job")[1]["state"] == "cancelled"
    assert _leftovers(tmp_path / "ra") == []
