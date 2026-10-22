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
