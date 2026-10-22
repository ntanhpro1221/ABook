"""Soát a96 V7: FFmpeg thất bại vì ổ đích (hết chỗ, không ghi được) không được báo là "file nguồn hay ảnh bìa hỏng"."""
from __future__ import annotations

import errno
import subprocess
from pathlib import Path

import pytest

from abook.webui import export, humanize
from abook.webui.export_jobs import BookFileJobs


def _fail(stderr: str):
    def run(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["ffmpeg"], stderr=stderr)
    return run


def _write(tmp_path: Path):
    return export.write_chapter("fake-ffmpeg", tmp_path / "good.mp3", tmp_path / "Sách" / "out.mp3", None,
                                title="Chương 1", album="Sách", narrator="Người kể", number=1, total=1)


@pytest.mark.parametrize("stderr", ["av_interleaved_write_frame(): No space left on device",
                                    "Error writing trailer: [WinError 112] There is not enough space on the disk"])
def test_a_full_destination_drive_is_reported_as_the_drive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stderr: str) -> None:
    (tmp_path / "Sách").mkdir()
    monkeypatch.setattr(export, "run_hidden", _fail(stderr))
    with pytest.raises(OSError) as caught:
        _write(tmp_path)
    assert caught.value.errno == errno.ENOSPC and humanize.is_write_problem(caught.value)
    assert "đã đầy" in humanize.write_error(caught.value) and "Sách" in humanize.write_error(caught.value)
    assert caught.value.detail == stderr  # stderr còn nguyên cho "Chi tiết"
    assert not (tmp_path / "Sách" / "out.mp3.part").exists()


def test_a_refused_write_is_a_permission_problem_of_the_destination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "Sách").mkdir()
    monkeypatch.setattr(export, "run_hidden", _fail("Error opening output file out.mp3.part: Permission denied"))
    with pytest.raises(PermissionError) as caught:
        _write(tmp_path)
    assert "chỉ đọc hoặc app không có quyền ghi" in humanize.write_error(caught.value)


def test_a_source_the_app_cannot_read_still_blames_the_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "Sách").mkdir()
    for stderr in ("good.mp3: Invalid data found when processing input", "Error opening input file good.mp3: Permission denied"):
        monkeypatch.setattr(export, "run_hidden", _fail(stderr))
        with pytest.raises(ValueError, match="không đọc được") as caught:
            _write(tmp_path)
        assert stderr.split(":")[-1].strip() in caught.value.detail


def test_an_unknown_ffmpeg_failure_does_not_claim_the_source_is_broken(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "Sách").mkdir()
    monkeypatch.setattr(export, "run_hidden", _fail("Conversion failed!"))
    with pytest.raises(ValueError) as caught:
        _write(tmp_path)
    assert "không đọc được" not in str(caught.value) and "chưa rõ nguyên nhân" in str(caught.value)
    assert caught.value.detail == "Conversion failed!"


def test_the_export_job_shows_the_drive_message_and_keeps_the_detail() -> None:
    jobs = BookFileJobs()

    def work():
        raise export.ffmpeg_failure(subprocess.CalledProcessError(1, ["ffmpeg"], stderr="No space left on device"),
                                    Path("D:/Xuất/Sách/01.mp3"), "nguồn hỏng", "chưa rõ")

    jobs.start("sach", work)
    import time
    for _ in range(100):
        status = jobs.status("sach")
        if status["state"] != "running":
            break
        time.sleep(0.05)
    assert status["state"] == "error" and "đã đầy" in status["error"] and "nguồn hỏng" not in status["error"]
    assert status["detail"] == "No space left on device"
