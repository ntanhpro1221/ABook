"""Soát a61 (xuất trên máy tính): M4B không huỷ được ở pha nào, im lặng suốt lúc tải nhạc nền, `.m4b-*` của lượt bị tắt ngang ở thư mục tự chọn
không bao giờ được dọn, và `#EXTINF` của `.m3u8` lấy độ dài ước của sổ (lệch 4-9 giây). Huỷ MP3 cùng cơ chế."""
from __future__ import annotations

import os
import re
import shutil
import threading
import time
from pathlib import Path

import pytest

from abook.io_utils import ffmpeg_available
from abook.readaloud import mp3
from abook.webui import export, export_jobs
from tests.test_export_music import LINK_A, LINK_B, _studio_book
from tests.test_export_series import _get, _mp3_job, _post, _studio

pytestmark = pytest.mark.skipif(not ffmpeg_available(), reason="cần ffmpeg")


def _wait(predicate, seconds: float = 20.0) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.03)
    return False


def _leftovers(folder: Path) -> list[str]:
    return sorted(entry.name for entry in folder.rglob("*")) if folder.exists() else []


def _downloading_app(app, tracks: dict[str, Path], gate: threading.Event | None = None) -> list[str]:
    """Bộ đệm nhạc rỗng; `music_track_for_export` "tải" bài (chờ `gate` nếu có) rồi bài nằm trong bộ đệm."""
    cache: dict[str, Path] = {}
    fetched: list[str] = []

    def fetch(link: str, **_fetch) -> Path | None:
        if link not in cache:
            if gate is not None:
                gate.wait(20)
            cache[link] = tracks[link]
            fetched.append(link)
        return cache[link]

    app.music_track_cached = cache.get  # type: ignore[method-assign]
    app.music_track_for_export = fetch  # type: ignore[method-assign]
    return fetched


# ---- M4B: tiến độ tải nhạc + Huỷ ở mọi pha ------------------------------------------------------------------------------------

def test_the_m4b_job_says_it_is_downloading_music_and_cancel_there_writes_nothing(tmp_path: Path) -> None:
    project, tracks = _studio_book(tmp_path)
    app, server = _studio(tmp_path, project.parent)
    gate = threading.Event()
    fetched = _downloading_app(app, tracks, gate)
    target = tmp_path / "xuat"
    target.mkdir()
    try:
        assert _post(server, project, "m4b-job", {"target": str(target), "music": True})[0] == 202
        assert _wait(lambda: _get(server, project, "m4b-job")[1].get("phase") == "music-fetch")
        job = _get(server, project, "m4b-job")[1]
        assert (job["state"], job["done"], job["total"]) == ("running", 0, 2), "bài 1/2 đang tải"
        status, cancelling = _post(server, project, "m4b-job/cancel", {})
        assert status == 200 and cancelling["state"] == "running"
        asked = time.monotonic()
        gate.set()  # bài đang tải xong; bài kế không được tải nữa
        assert _wait(lambda: _get(server, project, "m4b-job")[1]["state"] == "cancelled")
        assert time.monotonic() - asked < 2.0
    finally:
        gate.set()
        server.stop()
    assert fetched == [LINK_A], "dừng trước bài kế"
    assert _leftovers(target) == [], "không file M4B, không thư mục tạm"
    assert str(target) in [str(item) for item in app.export_folders.recent()], "thư mục tự chọn được ghi nhớ để lần mở sau dọn"


def test_the_m4b_job_can_be_cancelled_while_mixing_and_leaves_no_scratch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, tracks = _studio_book(tmp_path)
    app, server = _studio(tmp_path, project.parent)
    _downloading_app(app, tracks)
    target = tmp_path / "xuat"
    mixing = threading.Event()
    release = threading.Event()
    real = export.pump_mixed

    def slow_pump(*args, **kwargs):  # chương 1 đang trộn: chờ cho test bấm Huỷ giữa chừng
        mixing.set()
        release.wait(20)
        return real(*args, **kwargs)

    monkeypatch.setattr(export, "pump_mixed", slow_pump)
    try:
        assert _post(server, project, "m4b-job", {"target": str(target), "music": True})[0] == 202
        assert mixing.wait(20)
        assert any(name.startswith(".m4b-") for name in os.listdir(target)), "thư mục tạm cạnh nơi lưu đang có"
        assert _get(server, project, "m4b-job")[1].get("phase") == "music"
        _post(server, project, "m4b-job/cancel", {})
        asked = time.monotonic()
        release.set()
        assert _wait(lambda: _get(server, project, "m4b-job")[1]["state"] == "cancelled")
        assert time.monotonic() - asked < 2.0
    finally:
        release.set()
        server.stop()
    assert _leftovers(target) == []


@pytest.mark.parametrize("when", ["feed", "peaks", "mux"])
def test_export_m4b_stops_at_every_step_and_cleans_its_scratch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, when: str) -> None:
    project, tracks = _studio_book(tmp_path)
    flag = threading.Event()
    measured: list[float] = []
    real_peak = export.true_peak_dbtp

    def peak(*args, **kwargs):
        measured.append(1.0)
        if when == "mux" and len(measured) == 2:
            flag.set()  # huỷ ở lần đo cuối (chương 2/2), trước lượt ghép
        return real_peak(*args, **kwargs)

    monkeypatch.setattr(export, "true_peak_dbtp", peak)
    options = {
        "feed": {"progress": lambda _chapter, _chapters: flag.set()},  # pha trộn chương 1
        "peaks": {"peaks": lambda _round, _over: flag.set()},  # trước chương đầu được đo đỉnh
        "mux": {},
    }[when]
    with pytest.raises(export_jobs.Cancelled):
        export.export_m4b(project, tmp_path / "xuat", music=tracks.get, cancelled=flag.is_set, **options)
    assert _leftovers(tmp_path / "xuat") == []
    assert (len(measured) == 0) if when in ("feed", "peaks") else (len(measured) == 2)


# ---- MP3: Huỷ cùng cơ chế -----------------------------------------------------------------------------------------------------

def test_cancelling_an_mp3_export_removes_the_half_written_folder(tmp_path: Path) -> None:
    project, tracks = _studio_book(tmp_path)
    target = tmp_path / "xuat"
    with pytest.raises(export_jobs.Cancelled):
        export.export_book(project, target, music=tracks.get, cancelled=lambda: any(target.rglob("01 - *.mp3")))
    assert _leftovers(target) == [], "chương 1 đã ghi, thư mục bản xuất và thư mục tạm .music-* đều bị xoá"


def test_the_mp3_job_reports_its_downloads_and_cancel_ends_it_cancelled_with_nothing_left(tmp_path: Path) -> None:
    project, tracks = _studio_book(tmp_path)
    app, server = _studio(tmp_path, project.parent)
    gate = threading.Event()
    fetched = _downloading_app(app, tracks, gate)
    target = tmp_path / "xuat"
    try:
        assert _post(server, project, "mp3-job", {"target": str(target), "music": True})[0] == 202
        assert _wait(lambda: _get(server, project, "mp3-job")[1].get("phase") == "music-fetch")
        job = _get(server, project, "mp3-job")[1]
        assert (job["state"], job["done"], job["total"]) == ("running", 0, 2), "bài 1/2 đang tải"
        status, cancelling = _post(server, project, "mp3-job/cancel", {})
        assert status == 200 and cancelling["state"] == "running"
        asked = time.monotonic()
        gate.set()  # bài đang tải xong; bài kế không được tải nữa
        assert _wait(lambda: _get(server, project, "mp3-job")[1]["state"] == "cancelled")
        assert time.monotonic() - asked < 2.0
    finally:
        gate.set()
        server.stop()
    assert fetched == [LINK_A], "dừng trước bài kế"
    assert _leftovers(target) == []
    assert str(target) in [str(item) for item in app.export_folders.recent()]


def test_an_mp3_job_without_music_does_not_claim_to_download(tmp_path: Path) -> None:
    project, _tracks = _studio_book(tmp_path)
    app, server = _studio(tmp_path, project.parent)
    try:
        with app.music_exporting(app.music_key(project, "mp3"), []):
            assert _get(server, project, "music-export")[1] == {"active": False, "done": 0, "total": 0}, "music-export chỉ nói về .abook / .abookproj"
        assert _mp3_job(server, project, {"target": str(tmp_path / "xuat")})["state"] == "done"
    finally:
        server.stop()


# ---- dọn file tạm của lượt bị tắt ngang ở thư mục tự chọn -----------------------------------------------------------------------

def test_scratch_of_an_export_killed_in_a_chosen_folder_is_swept_once_old(tmp_path: Path) -> None:
    project, _tracks = _studio_book(tmp_path)
    app, server = _studio(tmp_path, project.parent)
    chosen = tmp_path / "o_rieng"
    try:
        assert _mp3_job(server, project, {"target": str(chosen)})["state"] == "done"  # MP3 ghi nhớ thư mục như .abookproj
    finally:
        server.stop()
    assert str(chosen) in [str(item) for item in app.export_folders.recent()]
    old, fresh = chosen / ".m4b-abcd_123", chosen / ".music-x9y8z7w6"
    young = chosen / ".m4b-young_12"
    for folder in (old, fresh, young):
        folder.mkdir()
        (folder / "audio.m4a").write_bytes(b"x" * 10)
    two_hours = time.time() - 2 * 3600
    for path in (old, old / "audio.m4a", fresh, fresh / "audio.m4a"):
        os.utime(path, (two_hours, two_hours))
    removed = app.sweep_export_leftovers()
    assert old in removed and fresh in removed and not old.exists() and not fresh.exists()
    assert young.exists(), "chưa quá 1 giờ: có thể là lượt đang chạy"
    shutil.rmtree(young)


def test_a_chapter_cut_mid_write_is_swept_but_other_part_files_are_not(tmp_path: Path) -> None:
    """Soát a73 (F5): xuất MP3 ghi từng chương ra "<NN - tên>.mp3.part" trong thư mục cuốn rồi mới đổi tên; app tắt ngang lúc ấy thì
    file dở nằm lại mãi. Chỉ đúng mẫu tên chương của app - file ".mp3.part" của trình duyệt đang tải cạnh đó không bị đụng."""
    project, _tracks = _studio_book(tmp_path)
    app, server = _studio(tmp_path, project.parent)
    chosen = tmp_path / "o_rieng"
    try:
        assert _mp3_job(server, project, {"target": str(chosen)})["state"] == "done"
    finally:
        server.stop()
    book = next(entry for entry in chosen.iterdir() if entry.is_dir())
    cut, young = book / "01 - Chương một.mp3.part", book / "02 - Chương hai.mp3.part"
    browser, note = chosen / "bai hat.mp3.part", book / "ghi chu.mp3.part"
    for path in (cut, young, browser, note):
        path.write_bytes(b"x" * 10)
    two_hours = time.time() - 2 * 3600
    for path in (cut, browser, note):
        os.utime(path, (two_hours, two_hours))
    removed = app.sweep_export_leftovers()
    assert cut in removed and not cut.exists()
    assert young.exists() and browser.exists() and note.exists()


# ---- #EXTINF = độ dài thật của file đã ghi -----------------------------------------------------------------------------------

def test_the_playlist_gives_each_chapter_its_real_length(tmp_path: Path) -> None:
    project, tracks = _studio_book(tmp_path)
    for music in (None, tracks.get):
        folder = Path(export.export_book(project, tmp_path / ("co" if music else "khong"), music=music)["folder"])
        playlist = next(folder.glob("*.m3u8")).read_text(encoding="utf-8")
        # Ghi nguyên tử (soát a73, F5): không sót tên tạm, và đúng byte như điện thoại (LF, không CRLF của write_text trên Windows).
        assert b"\r" not in next(folder.glob("*.m3u8")).read_bytes() and not list(folder.glob("*.part"))
        lengths = [int(value) for value in re.findall(r"#EXTINF:(\d+),", playlist)]
        files = sorted(folder.glob("*.mp3"))
        assert lengths == [round(mp3.duration_ms(file.read_bytes()) / 1000) for file in files] == [20, 6]
