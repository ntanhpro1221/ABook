"""Đóng app trong hạn của vỏ Tauri (soát a73, F6): vỏ chờ host 5 giây (HOST_STOP_GRACE, shell/src-tauri/src/main.rs) rồi giết.
`App.close` từng chờ lần lượt ba loại lượt xuất, mỗi loại tới 3 giây, RỒI mới dọn Thùng rác - ba lượt xuất chậm dừng là quá 5 giây và
cuốn vừa xoá không kịp vào Thùng rác. Giờ: bảo dừng cùng lúc, chờ chung một hạn, Thùng rác làm trước."""
from __future__ import annotations

import re
import threading
import time
from pathlib import Path

from abook.webui import export_jobs
from abook.webui import server as server_module
from abook.webui import actions, trash_pending
from tests.test_a_project_can_be_renamed_or_deleted import studio  # noqa: F401 - fixture dùng chung

MAIN_RS = Path(__file__).resolve().parents[1] / "shell" / "src-tauri" / "src" / "main.rs"


def _slow_job(jobs: export_jobs.BookFileJobs, key: str, release: threading.Event) -> None:
    """Một lượt xuất đang ở giữa một bước dài (mã hoá một chương): bảo dừng thì phải chờ bước ấy xong mới dừng."""
    def work() -> dict:
        release.wait(10)
        return {"ok": True}

    jobs.start(key, work)
    assert jobs.status(key)["state"] == "running"


def test_closing_with_three_slow_exports_finishes_inside_the_shell_grace_and_sweeps_the_trash_first(studio, monkeypatch) -> None:  # noqa: F811
    _paths, app, _server, _runner = studio
    grace = int(re.search(r"HOST_STOP_GRACE: Duration = Duration::from_secs\((\d+)\)", MAIN_RS.read_text(encoding="utf-8"))[1])
    release = threading.Event()
    for jobs in (app.projectfile_jobs, app.m4b_jobs, app.mp3_jobs):
        _slow_job(jobs, "cuon", release)
    swept: list[float] = []
    real_sweep = app.sweep_trash
    monkeypatch.setattr(app, "sweep_trash", lambda *args, **kwargs: (swept.append(time.monotonic()), real_sweep(*args, **kwargs)))

    begun = time.monotonic()
    try:
        app.close()
        took = time.monotonic() - begun
    finally:
        release.set()

    assert took < server_module.CLOSE_SECONDS + 1.0 < grace, f"đóng app mất {took:.1f} giây"
    assert swept and swept[0] - begun < 1.0, "Thùng rác trước, không chờ các lượt xuất"


def test_slow_trash_does_not_hold_close_past_the_shared_deadline(studio, monkeypatch):
    _paths, app, _server, _runner = studio
    entered, release = threading.Event(), threading.Event()
    workers = []

    def slow_sweep(**kwargs):
        workers.append(threading.current_thread())
        entered.set()
        release.wait(1.0)

    monkeypatch.setattr(server_module, "CLOSE_SECONDS", 0.05)
    monkeypatch.setattr(app, "sweep_trash", slow_sweep)
    begun = time.monotonic()
    try:
        app.close()
        took = time.monotonic() - begun
        assert entered.is_set()
        assert took < 0.5
    finally:
        release.set()
        for thread in workers:
            if thread is not threading.current_thread():
                thread.join(2)
                assert not thread.is_alive()


def test_next_open_finishes_trash_interrupted_in_recycling(tmp_path, monkeypatch):
    root = tmp_path / "library"
    original = root / "book"
    original.mkdir(parents=True)
    (original / "audio.wav").write_bytes(b"audio")
    pending = trash_pending.TrashPending()
    monkeypatch.setattr(actions, "recycle_bin_available", lambda path: None)
    token = pending.hold(root, original, kind="project")
    moved = []

    def interrupted(path):
        raise SystemExit  # host chết sau khi rename, trước khi Recycle Bin nhận

    monkeypatch.setattr(actions, "move_to_recycle_bin", interrupted)
    monkeypatch.setattr(actions, "recycle_bin_available", lambda path: None)
    monkeypatch.setattr(actions, "recycle_bin_accepts", lambda path: True)
    try:
        pending.sweep(root, everything=True, ask=False)
    except SystemExit:
        pass
    import json
    import shutil
    meta = json.loads((root / trash_pending.FOLDER / token / trash_pending.META).read_text(encoding="utf-8"))
    assert meta["phase"] == "recycling" and Path(meta["via"]).is_dir()

    def recycle(path):
        moved.append(path)
        assert (path / "audio.wav").read_bytes() == b"audio"
        shutil.rmtree(path)

    monkeypatch.setattr(actions, "move_to_recycle_bin", recycle)
    # Cùng đường mở app: quét everything với một TrashPending mới, không dựa vào RAM phiên cũ.
    assert trash_pending.TrashPending().sweep(root, everything=True) == 0
    assert moved == [original]
    assert not (root / trash_pending.FOLDER / token).exists()
