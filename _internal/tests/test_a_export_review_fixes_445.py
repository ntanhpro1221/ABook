"""Soát mã trước 0.4.45 (xuất `.abookproj` chạy nền): bốn lỗi.
2. `.abook` và `.abookproj` dùng chung khoá nhạc `str(project)` - hai lượt cùng cuốn ghi đè trạng thái và huỷ chéo.
3. File `.<tên>.abookproj.<hex>.part` + thư mục `abookproj-*` sót khi đóng app giữa lúc gói; file lớn băm/ghi một mạch không dừng được.
4. `BookFileJobs.shutdown` join luồng chưa start (RuntimeError) làm `App.close()` bỏ qua dọn Thùng rác."""
from __future__ import annotations

import hashlib
import os
import threading
import time
from pathlib import Path

import pytest

from abook.webui import bookfile, export_jobs, export_leftovers, projectfile
from abook.webui.library import book_id
from tests.test_a_music_export_shows_progress_and_can_be_cancelled import _slow_app
from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung
from tests.test_bookfile_music import BATTLE, CALM, _plan
from tests.test_webui_listen_and_sync import make_project


def _wait(predicate, seconds: float = 15.0) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.03)
    return False


# ---------------------------------------------------------------- 2. khoá nhạc theo kiểu xuất

def test_the_two_export_kinds_keep_their_music_state_apart(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, app, _server, _runner = studio
    project = make_project(tmp_path / "may")
    _plan(project)
    _slow_app(app, tmp_path)
    book_key, proj_key = app.music_key(project), app.music_key(project, "projectfile")
    assert book_key != proj_key
    with app.music_exporting(book_key, [project]):
        with app.music_exporting(proj_key, [project]):
            assert app.music_export_status(book_key)["active"] and app.music_export_status(proj_key)["active"]
            assert app.cancel_music_export(proj_key) is True
            assert not app._music_exports[book_key]["cancel"].is_set(), "huỷ .abookproj không huỷ nhạc của .abook"
        assert app.music_export_status(book_key)["active"], ".abookproj xong không xoá trạng thái của .abook"


def test_cancelling_the_projectfile_job_leaves_the_bookfile_music_alone(studio, tmp_path: Path,  # noqa: F811
                                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    paths, app, server, _runner = studio
    book = book_id(paths.root)
    gate = threading.Event()
    _slow_app(app, tmp_path, gate)

    def pack_two_tracks(project, out, *, running, music_track, progress=None, verdicts=None):
        music_track(CALM)
        music_track(BATTLE)
        raise AssertionError("đã huỷ thì không tới đây")

    monkeypatch.setattr("abook.webui.projectfile.pack", pack_two_tracks)
    # Một lượt xuất .abook đang tải nhạc của cùng cuốn (đặt trạng thái như `post_bookfile_job` làm).
    with app.music_exporting(app.music_key(paths.root), [paths.root]):
        status, started = _call(server, "POST", f"/api/books/{book}/projectfile-job", {"target": str(tmp_path / "out")})
        assert status == 202
        assert _wait(lambda: _call(server, "GET", f"/api/books/{book}/music-export?kind=projectfile")[1].get("active"))
        # Hai trạng thái đọc riêng: .abook không thấy tiến độ của .abookproj.
        assert _call(server, "GET", f"/api/books/{book}/music-export")[1]["done"] == 0
        assert _call(server, "POST", f"/api/books/{book}/projectfile-job/cancel", {})[0] == 200
        assert not app._music_exports[app.music_key(paths.root)]["cancel"].is_set(), "huỷ việc gói dự án không huỷ nhạc .abook"
        gate.set()
        assert _wait(lambda: _call(server, "GET", f"/api/books/{book}/projectfile-job")[1]["state"] == "cancelled")
        assert app.music_export_status(app.music_key(paths.root))["active"], "lượt .abook vẫn còn trạng thái của nó"
    assert _call(server, "GET", f"/api/books/{book}/music-export?kind=projectfile")[1]["active"] is False
    assert started["id"]


# ---------------------------------------------------------------- 3. dọn file tạm sót lại

def _aged(path: Path, seconds: float) -> None:
    stamp = time.time() - seconds
    os.utime(path, (stamp, stamp))


def test_the_sweep_removes_only_old_files_in_the_project_file_temp_pattern(tmp_path: Path) -> None:
    folder, scratch = tmp_path / "xuat", tmp_path / "tmp"
    folder.mkdir()
    scratch.mkdir()
    stale = folder / ".Sach.abookproj.1a2b3c4d.part"
    fresh = folder / ".Sach.abookproj.5e6f7a8b.part"
    others = [folder / ".Sach.abook.1a2b3c4d.part", folder / "Sach.abookproj", folder / "ghi chu.part", folder / ".Sach.abookproj.xyz.part"]
    for path in (stale, fresh, *others):
        path.write_bytes(b"x")
    for path in (stale, *others):
        _aged(path, 3600)
    old_dir, young_dir, stranger = scratch / "abookproj-ab12_cd9", scratch / "abookproj-zz99zz99", scratch / "abookproj-nope"
    for directory in (old_dir, young_dir, stranger):
        (directory / "views").mkdir(parents=True)
        (directory / "views" / "a.json").write_bytes(b"{}")
    for directory in (old_dir, stranger):
        _aged(directory / "views" / "a.json", 3600)
        _aged(directory / "views", 3600)
        _aged(directory, 3600)

    removed = export_leftovers.sweep([folder, tmp_path / "khong_co"], scratch)

    assert sorted(path.name for path in removed) == sorted([stale.name, old_dir.name])
    assert not stale.exists() and not old_dir.exists()
    assert fresh.exists() and young_dir.exists(), "đang gói (còn mới) thì không đụng"
    assert all(path.exists() for path in others) and stranger.exists(), "chỉ đúng mẫu tên của projectfile.py"


def test_the_app_remembers_export_folders_and_sweeps_them_at_start(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    book = book_id(paths.root)
    out = tmp_path / "noi_luu"
    out.mkdir()
    leftover = out / ".Cu.abookproj.00ff00ff.part"
    leftover.write_bytes(b"do")
    _aged(leftover, 3600)
    default = tmp_path / "Đã xuất"
    default.mkdir()
    default_leftover = default / ".Cu.abookproj.00ff00fe.part"
    default_leftover.write_bytes(b"do")
    _aged(default_leftover, 3600)

    # Chọn nơi lưu ở một lượt gói (kể cả khi nó hỏng/huỷ) là nhớ lại: app mở lại vẫn biết chỗ dọn.
    status, _data = _call(server, "POST", f"/api/books/{book}/projectfile-job", {"target": str(out)})
    assert status == 202
    assert _wait(lambda: _call(server, "GET", f"/api/books/{book}/projectfile-job")[1]["state"] != "running")
    assert str(out) in [str(item) for item in app.export_folders.recent()]

    app.sweep_export_leftovers()

    assert not leftover.exists() and not default_leftover.exists()


def test_a_big_file_reports_and_stops_in_the_middle_not_only_between_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.test_a_projectfile_export_runs_in_the_background import _frozen_clock

    _frozen_clock(monkeypatch)
    monkeypatch.setattr(bookfile, "_TICK", 64 * 1024)
    project = make_project(tmp_path / "may")
    big = project / "output" / "chapters" / "00001_645.mp3"
    big.write_bytes(b"ID3" + os.urandom(6 * 1024 * 1024))
    seen: list[tuple[str, int, int]] = []
    watched = projectfile.pack(project, tmp_path / "a" / "du_an.abookproj", progress=lambda *step: seen.append(step))
    for phase in ("hash", "write"):
        steps = [done for name, done, _total in seen if name == phase]
        assert len(steps) > 6 and steps == sorted(steps), f"{phase}: báo nhiều lần trong một file lớn, đã làm chỉ tăng"
        assert all(done <= total for name, done, total in seen if name == phase)
    # Không báo tiến độ (đường `ZipFile.write`) ra đúng từng byte như đường có điểm kiểm giữa file.
    plain = projectfile.pack(project, tmp_path / "b" / "du_an.abookproj")
    assert hashlib.sha256(plain.read_bytes()).hexdigest() == hashlib.sha256(watched.read_bytes()).hexdigest()

    for phase in ("hash", "write"):
        hits = 0

        def cancel_inside(name: str, done: int, total: int, phase: str = phase) -> None:
            nonlocal hits
            if name == phase and 0 < done < total:
                hits += 1
                if hits == 3:
                    raise export_jobs.Cancelled()

        target = tmp_path / phase / "du_an.abookproj"
        with pytest.raises(export_jobs.Cancelled):
            projectfile.pack(project, target, progress=cancel_inside)
        assert hits == 3
        assert not [p for p in (tmp_path / phase).rglob("*") if p.is_file()], "huỷ giữa file: không file thật, không .part"


# ---------------------------------------------------------------- 4. shutdown không join luồng chưa start

def test_shutdown_does_not_choke_on_a_thread_that_has_not_started_yet() -> None:
    jobs = export_jobs.BookFileJobs()
    with jobs._lock:  # như `start()` cũ: đã ghi nhận luồng nhưng chưa kịp `thread.start()`
        jobs._state["k"] = {"state": "running", "id": "x", "startedAt": 0.0}
        jobs._stops["k"] = threading.Event()
        jobs._threads["k"] = threading.Thread(target=lambda: None)
    jobs.shutdown(timeout=0.2)  # trước khi sửa: RuntimeError cannot join thread before it is started


def test_start_registers_the_thread_only_once_it_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Đóng app đúng lúc việc vừa bắt đầu: `shutdown` chờ `start` xong rồi join luồng đã chạy thật, không nổ."""
    jobs = export_jobs.BookFileJobs()
    errors: list[BaseException] = []
    real_start = threading.Thread.start
    entered = threading.Event()

    def slow_start(self):
        if self.name != "bookfile-export":
            return real_start(self)

        def closer() -> None:
            entered.set()
            try:
                jobs.shutdown(timeout=2.0)
            except BaseException as error:  # noqa: BLE001
                errors.append(error)

        closing = threading.Thread(target=closer)
        real_start(closing)
        entered.wait(2)
        time.sleep(0.2)  # shutdown chạy xen vào giữa `start()`
        real_start(self)
        closing.join(5)

    monkeypatch.setattr(threading.Thread, "start", slow_start)
    try:
        result = jobs.start("k", lambda: {"ok": True})
    finally:
        monkeypatch.undo()
    assert result["state"] in ("running", "done")
    assert errors == [], errors
    assert _wait(lambda: jobs.status("k")["state"] == "done")
