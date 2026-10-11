"""Bìa hỏng không chặn xuất MP3 / M4B (soát a28 lỗi 8).

Trước đây: cover.jpg rác -> xuất MP3 trả 500 "CalledProcessError: Command '[...ffmpeg...]'" (lộ cả lệnh) và để lại `.mp3.part`; M4B báo lỗi
dán nguyên stderr ffmpeg. Giờ: ảnh được kiểm bằng Pillow trước, hỏng thì dùng bìa vẽ từ tên và kết quả nói `coverBroken`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from abook.io_utils import ffmpeg_available
from abook.webui import covers, export
from tests.test_export_m4b import _book

pytestmark = pytest.mark.skipif(not ffmpeg_available(), reason="cần ffmpeg")


def _broken_cover(project: Path) -> None:
    (project / covers.COVER_FILE).write_bytes(b"\xff\xd8\xff\xe0" + b"rac" * 200)  # đầu JPEG, ruột rác


def test_mp3_export_with_a_broken_cover_still_exports_and_says_so(tmp_path: Path) -> None:
    project = _book(tmp_path)
    _broken_cover(project)
    result = export.export_book(project, tmp_path / "xuat")
    assert result["files"] == 2 and result["coverBroken"] is True
    folder = Path(result["folder"])
    assert not list(folder.glob("*.part"))
    assert not list(folder.glob("cover.jpg")), "bìa hỏng không bị chép theo"


def test_m4b_export_with_a_broken_cover_still_exports_and_says_so(tmp_path: Path) -> None:
    project = _book(tmp_path)
    _broken_cover(project)
    result = export.export_m4b(project, tmp_path / "xuat")
    assert Path(result["file"]).is_file() and result["coverBroken"] is True
    assert [path.name for path in (tmp_path / "xuat").iterdir()] == ["Truyện X.m4b"]


def test_a_chapter_ffmpeg_cannot_read_leaves_no_part_and_no_command(tmp_path: Path) -> None:
    project = _book(tmp_path)
    (project / "output" / "chapters" / "00001_645.mp3").write_bytes(b"khong phai am thanh" * 50)
    with pytest.raises(ValueError) as caught:
        export.export_book(project, tmp_path / "xuat")
    assert "ffmpeg" not in str(caught.value).lower() and "Command" not in str(caught.value)
    assert not list((tmp_path / "xuat").rglob("*.part"))
