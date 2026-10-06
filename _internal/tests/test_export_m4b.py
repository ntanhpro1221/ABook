"""Xuất M4B (webui/export.export_m4b + POST/GET /api/books/<id>/m4b-job): cả cuốn trong một file AAC có mục lục chương, bìa
và tag. Âm thanh thử do ffmpeg tạo (sóng sin / im lặng) trong thư mục tạm; ffprobe đọc lại file xuất."""
from __future__ import annotations

import base64
import json
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

import pytest

from abook.io_utils import ffmpeg_available, ffmpeg_executable
from abook.webui import covers, export
from tests.test_export_series import _get, _part, _post, _studio

FFPROBE = shutil.which("ffprobe")
pytestmark = pytest.mark.skipif(not ffmpeg_available() or FFPROBE is None, reason="cần ffmpeg + ffprobe")

ONE = 1.5   # giây, chương 1: sóng sin
TWO = 2.25  # giây, chương 2: im lặng


def _ffmpeg(*args: str) -> None:
    subprocess.run([ffmpeg_executable(), "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def _mp3(path: Path, source: str, seconds: float) -> None:
    _ffmpeg("-f", "lavfi", "-i", source, "-t", str(seconds), "-ac", "1", "-ar", "24000", "-c:a", "libmp3lame", "-b:a", "48k",
            str(path))


def _book(tmp_path: Path, *, finished: int = 2) -> Path:
    """Cuốn 2 chương (fixture make_project) với MP3 thật; `finished=1`: chương 2 còn đang thu."""
    library = tmp_path / "thu_vien"
    library.mkdir()
    project = _part(tmp_path, library, "p1", "Truyện X")
    chapters = project / "output" / "chapters"
    _mp3(chapters / "00001_645.mp3", "sine=frequency=440:sample_rate=24000", ONE)
    if finished == 2:
        second = chapters / "00002_646.mp3"
        _mp3(second, "anullsrc=r=24000:cl=mono", TWO)
        with sqlite3.connect(project / "project.sqlite3") as db:
            db.execute("UPDATE chapters SET status='completed', output_mp3=? WHERE id=2", (str(second),))
            db.execute("UPDATE segments SET status='verified', wav_duration=1.0 WHERE chapter_id=2")
    return project


def _probe(path: Path) -> dict:
    result = subprocess.run([FFPROBE, "-v", "error", "-show_chapters", "-show_streams", "-show_format", "-of", "json", str(path)],
                            capture_output=True, check=True)
    return json.loads(result.stdout.decode("utf-8"))


def test_the_m4b_has_a_chapter_per_finished_chapter_with_real_boundaries_cover_and_tags(tmp_path: Path) -> None:
    project = _book(tmp_path)
    _ffmpeg("-f", "lavfi", "-i", "color=c=red:s=64x64", "-frames:v", "1", str(project / covers.COVER_FILE))
    result = export.export_m4b(project, tmp_path / "xuat")
    file = tmp_path / "xuat" / "Truyện X.m4b"
    assert Path(result["file"]) == file and result["folder"] == str(tmp_path / "xuat")
    assert result["chapters"] == 2 and result["chaptersTotal"] == 2 and result["size"] == file.stat().st_size
    assert [path.name for path in (tmp_path / "xuat").iterdir()] == ["Truyện X.m4b"], "không để lại file tạm"

    probe = _probe(file)
    chapters = probe["chapters"]
    assert [chapter["tags"]["title"] for chapter in chapters] == ["Chương 646 · Trở về (1)", "Chương 647 · Trở về (2)"]
    bounds = [(float(chapter["start_time"]), float(chapter["end_time"])) for chapter in chapters]
    expected = [(0.0, ONE), (ONE, ONE + TWO)]
    for (start, end), (want_start, want_end) in zip(bounds, expected):
        assert abs(start - want_start) <= 0.05 and abs(end - want_end) <= 0.05, bounds
    audio = [stream for stream in probe["streams"] if stream["codec_type"] == "audio"]
    pictures = [stream for stream in probe["streams"] if stream["codec_type"] == "video"]
    assert len(audio) == 1 and audio[0]["codec_name"] == "aac" and audio[0]["channels"] == 1
    assert abs(float(probe["format"]["duration"]) - (ONE + TWO)) <= 0.05
    assert len(pictures) == 1 and pictures[0]["disposition"]["attached_pic"] == 1 and pictures[0]["codec_name"] == "mjpeg"
    tags = probe["format"]["tags"]
    assert tags["major_brand"] == "M4B ", "Apple Books xếp vào sách nói"
    assert (tags["title"], tags["album"], tags["artist"], tags["album_artist"], tags["genre"]) == (
        "Truyện X", "Truyện X", "Đức Trí", "Đức Trí", "Audiobook")


def test_unfinished_chapters_are_left_out_and_the_drawn_cover_is_used(tmp_path: Path) -> None:
    project = _book(tmp_path, finished=1)
    png = tmp_path / "ve.png"
    _ffmpeg("-f", "lavfi", "-i", "color=c=blue:s=32x32", "-frames:v", "1", str(png))
    drawn = "data:image/png;base64," + base64.b64encode(png.read_bytes()).decode("ascii")
    result = export.export_m4b(project, tmp_path / "xuat", cover=drawn)
    assert result["chapters"] == 1 and result["chaptersTotal"] == 2, "giao diện nói được chương nào chưa có"
    probe = _probe(Path(result["file"]))
    assert [chapter["tags"]["title"] for chapter in probe["chapters"]] == ["Chương 646 · Trở về (1)"]
    assert [stream["codec_name"] for stream in probe["streams"] if stream["codec_type"] == "video"] == ["png"]


def test_a_book_with_nothing_finished_refuses(tmp_path: Path) -> None:
    project = _book(tmp_path, finished=1)
    (project / "output" / "chapters" / "00001_645.mp3").unlink()
    with pytest.raises(ValueError, match="chưa có chương nào"):
        export.export_m4b(project, tmp_path / "xuat")
    assert not (tmp_path / "xuat").exists()


def test_an_encoder_that_dies_reports_why_and_leaves_nothing_behind(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _book(tmp_path)
    monkeypatch.setattr(export, "_AAC_BITRATE", {1: "khong-phai-so", 2: "khong-phai-so"})
    with pytest.raises(ValueError, match="Không mã hoá được AAC"):
        export.export_m4b(project, tmp_path / "xuat")
    assert list((tmp_path / "xuat").iterdir()) == [], "thư mục tạm đã dọn, không có file dở"


def test_chapter_titles_with_metadata_syntax_survive(tmp_path: Path) -> None:
    project = _book(tmp_path)
    with sqlite3.connect(project / "project.sqlite3") as db:
        db.execute("UPDATE segments SET text=? WHERE id=1", ("Chương 1 - a=b; #c \\ d",))
    result = export.export_m4b(project, tmp_path / "xuat")
    title = export.listen_view.chapters(project)[0]["fullTitle"]
    assert "a=b; #c \\ d" in title and _probe(Path(result["file"]))["chapters"][0]["tags"]["title"] == title


def test_the_m4b_job_runs_in_the_background_and_reports_the_file(tmp_path: Path) -> None:
    project = _book(tmp_path)
    library = project.parent
    app, server = _studio(tmp_path, library)
    try:
        assert _get(server, project, "m4b-job") == (200, {"state": "idle"})
        status, started = _post(server, project, "m4b-job", {"target": str(tmp_path / "xuat")})
        deadline = time.monotonic() + 60
        job = started
        while job["state"] == "running" and time.monotonic() < deadline:
            time.sleep(0.1)
            job = _get(server, project, "m4b-job")[1]
        bookfile_job = _get(server, project, "bookfile-job")[1]
    finally:
        server.stop()
    assert status == 202 and started["id"] and job["state"] == "done", job
    assert job["result"]["file"] == str(tmp_path / "xuat" / "Truyện X.m4b") and job["result"]["chapters"] == 2
    assert job["result"]["folder"] in app.exports, "nút Mở thư mục mở được thư mục vừa xuất"
    assert bookfile_job == {"state": "idle"}, "M4B có bản ghi riêng, không lẫn với xuất file sách"
