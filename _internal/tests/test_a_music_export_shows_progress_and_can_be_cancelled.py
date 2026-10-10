"""Soát UX a20: xuất .abook / .abookproj có nhạc nền chưa tải thì máy chủ tải ngầm vài phút mà hộp Xuất chỉ nói "mất vài phút".
Giờ hộp hỏi được "đang tải bài k/n" và bấm Huỷ được (dừng trước bài kế, không ghi file sách nào)."""
from __future__ import annotations

import json
import threading
from pathlib import Path

from abook.webui import bookfile, export_jobs, music_plan
from abook.webui.library import book_id
from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung
from tests.test_bookfile_music import BATTLE, CALM, _plan
from tests.test_webui_listen_and_sync import make_project

import pytest


def _slow_app(app, tmp_path: Path, gate: threading.Event | None = None):
    """Bộ đệm rỗng; mỗi bài "tải" khi gọi `music_track_for_export` (có thể chờ `gate`), rồi nằm trong bộ đệm."""
    cache: dict[str, Path] = {}
    folder = tmp_path / "cache"
    folder.mkdir(exist_ok=True)
    fetched: list[str] = []

    def cached(link: str) -> Path | None:
        return cache.get(link)

    def fetch(link: str) -> Path | None:
        if link in cache:
            return cache[link]
        if gate is not None:
            gate.wait(10)
        path = folder / music_plan.track_name(link).split("/")[1]
        path.write_bytes(b"ID3" + link.encode() * 20)
        cache[link] = path
        fetched.append(link)
        return path

    app.music_track_cached = cached  # type: ignore[method-assign]
    app.music_track_for_export = fetch  # type: ignore[method-assign]
    return fetched


def test_progress_counts_the_tracks_that_had_to_be_downloaded(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, app, _server, _runner = studio
    project = make_project(tmp_path / "may")
    _plan(project)
    fetched = _slow_app(app, tmp_path)
    key = str(project)
    assert app.music_export_status(key) == {"active": False, "done": 0, "total": 0}
    with app.music_exporting(key, [project]) as music:
        assert app.music_export_status(key) == {"active": True, "done": 0, "total": 2}
        out = bookfile.pack(project, tmp_path / f"sach{bookfile.EXTENSION}", music_track=music)
        assert app.music_export_status(key) == {"active": True, "done": 2, "total": 2}
    assert out.is_file() and sorted(fetched) == sorted([CALM, BATTLE])
    assert app.music_export_status(key)["active"] is False, "xuất xong: không còn báo đang tải"


def test_cancel_stops_before_the_next_download_and_writes_no_book_file(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, app, _server, _runner = studio
    project = make_project(tmp_path / "may")
    _plan(project)
    gate = threading.Event()
    _slow_app(app, tmp_path, gate)
    key = str(project)
    target = tmp_path / f"sach{bookfile.EXTENSION}"
    outcome: list[BaseException] = []

    def pack() -> None:
        try:
            with app.music_exporting(key, [project]) as music:
                bookfile.pack(project, target, music_track=music)
        except BaseException as error:  # noqa: BLE001 - kiểm đúng loại lỗi bên dưới
            outcome.append(error)

    worker = threading.Thread(target=pack)
    worker.start()
    for _ in range(100):
        if app.music_export_status(key)["active"]:
            break
        threading.Event().wait(0.05)
    assert app.cancel_music_export(key) is True
    gate.set()  # bài đang tải dở xong, rồi gặp Huỷ trước bài kế
    worker.join(10)
    assert len(outcome) == 1 and isinstance(outcome[0], export_jobs.Cancelled)
    assert not target.exists() and not list(tmp_path.glob("*.part")), "huỷ: không file sách nào, không file dở"
    assert app.cancel_music_export(key) is False, "hết lượt xuất: không còn gì để huỷ"


def test_the_http_cancel_of_a_projectfile_export_answers_with_the_cancelled_reason(studio, tmp_path: Path,  # noqa: F811
                                                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    paths, app, server, _runner = studio
    gate = threading.Event()
    _slow_app(app, tmp_path, gate)

    def pack_two_tracks(project, out, *, running, music_track):  # việc đóng gói thật chỉ gọi nguồn nhạc cho từng bài
        music_track(CALM)
        music_track(BATTLE)
        raise AssertionError("đã huỷ thì không tới đây")

    monkeypatch.setattr("abook.webui.projectfile.pack", pack_two_tracks)
    book = book_id(paths.root)
    result: dict[str, object] = {}

    def export() -> None:
        result["status"], result["data"] = _call(server, "POST", f"/api/books/{book}/projectfile", {"target": str(tmp_path / "out")})

    worker = threading.Thread(target=export)
    worker.start()
    for _ in range(100):
        _status, data = _call(server, "GET", f"/api/books/{book}/music-export")
        if data.get("active"):
            break
        threading.Event().wait(0.05)
    assert data["active"] is True and data["done"] == 0
    status, data = _call(server, "POST", f"/api/books/{book}/music-export/cancel", {})
    assert status == 200 and data == {"cancelling": True}
    gate.set()
    worker.join(15)
    assert result["status"] == 409 and result["data"]["reason"] == "cancelled"  # type: ignore[index]
    assert _call(server, "GET", f"/api/books/{book}/music-export")[1]["active"] is False
