"""Thumbnail của Explorer cho .abook / .abookproj (windows/thumbnail): bìa sách thay cho icon.

Chạy DLL thật qua `thumbnail_probe` - nạp thẳng, đưa stream của file như Explorer, không đụng registry. Bỏ qua khi
không phải Windows hay máy không có MinGW-w64 (DLL phát hành được build sẵn).
"""
from __future__ import annotations

import io
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from abook.webui import bookfile, covers
from tests.test_webui_listen_and_sync import make_project

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_thumbnail_handler

pytestmark = pytest.mark.skipif(sys.platform != "win32" or build_thumbnail_handler.compiler() is None,
                                reason="thumbnail handler chỉ có trên Windows, cần MinGW-w64 để build")

COVER_SIZE = (600, 900)
TOP, BOTTOM = (200, 40, 40), (30, 90, 200)


@pytest.fixture(scope="module")
def handler() -> tuple[Path, Path]:
    return build_thumbnail_handler.build()


def _cover() -> bytes:
    """Bìa 2:3, nửa trên đỏ, nửa dưới xanh - thumbnail phải giữ đúng tỉ lệ và đúng chiều."""
    image = Image.new("RGB", COVER_SIZE, TOP)
    image.paste(BOTTOM, (0, COVER_SIZE[1] // 2, COVER_SIZE[0], COVER_SIZE[1]))
    raw = io.BytesIO()
    image.save(raw, "JPEG", quality=92)
    return raw.getvalue()


def _package(path: Path, *, cover: bytes | None, compress_cover: bool = False, padding: int = 0) -> Path:
    """Gói kiểu .abook: mimetype không nén đứng đầu, bìa không nén (như bookfile.py), vài MB 'audio'."""
    with zipfile.ZipFile(path, "w", allowZip64=True) as archive:
        archive.writestr(zipfile.ZipInfo("mimetype"), bookfile.MIMETYPE)
        archive.writestr("book.json", "{}", compress_type=zipfile.ZIP_DEFLATED)
        if cover is not None:
            info = zipfile.ZipInfo("cover.jpg")
            info.compress_type = zipfile.ZIP_DEFLATED if compress_cover else zipfile.ZIP_STORED
            archive.writestr(info, cover)
        archive.writestr(zipfile.ZipInfo("chapters/00001_1.mp3"), b"\x00" * (3 << 20))
        for index in range(padding):
            archive.writestr(zipfile.ZipInfo(f"samples/{index}.wav"), b"")
    return path


def _probe(handler: tuple[Path, Path], file: Path, size: int, out: Path) -> subprocess.CompletedProcess:
    dll, probe = handler
    return subprocess.run([str(probe), str(dll), str(file), str(size), str(out)], capture_output=True, text=True,
                          check=False, timeout=60)


def _assert_is_the_cover(image_path: Path, size: int) -> None:
    image = Image.open(image_path).convert("RGB")
    assert image.size == (round(size * 2 / 3), size), "vừa khung, giữ tỉ lệ 2:3 của bìa"
    width, height = image.size
    top = image.getpixel((width // 2, height // 4))
    bottom = image.getpixel((width // 2, height * 3 // 4))
    assert all(abs(a - b) < 24 for a, b in zip(top, TOP)), top
    assert all(abs(a - b) < 24 for a, b in zip(bottom, BOTTOM)), bottom


def test_the_thumbnail_is_the_book_cover(handler, tmp_path: Path) -> None:
    file = _package(tmp_path / "sach.abook", cover=_cover())
    result = _probe(handler, file, 256, tmp_path / "thumb.png")
    assert result.returncode == 0, result.stdout + result.stderr
    _assert_is_the_cover(tmp_path / "thumb.png", 256)


def test_a_book_without_a_cover_keeps_its_icon(handler, tmp_path: Path) -> None:
    """Handler từ chối thì Explorer hiện icon loại file - không có bìa, không có thumbnail."""
    file = _package(tmp_path / "khong_bia.abook", cover=None)
    result = _probe(handler, file, 256, tmp_path / "thumb.png")
    assert result.returncode == 2 and "no-thumbnail" in result.stdout
    assert not (tmp_path / "thumb.png").exists()


def test_a_compressed_cover_or_a_foreign_file_is_declined(handler, tmp_path: Path) -> None:
    compressed = _package(tmp_path / "bia_nen.abook", cover=_cover(), compress_cover=True)
    assert _probe(handler, compressed, 128, tmp_path / "a.png").returncode == 2
    junk = tmp_path / "rac.abook"
    junk.write_bytes(b"not a zip at all" * 1000)
    assert _probe(handler, junk, 128, tmp_path / "b.png").returncode == 2


def test_zip64_packages_still_show_their_cover(handler, tmp_path: Path) -> None:
    """Hơn 65 535 mục buộc Python ghi mục lục ZIP64 - như một cuốn rất dài."""
    file = _package(tmp_path / "zip64.abook", cover=_cover(), padding=65_600)
    with open(file, "rb") as handle:
        handle.seek(-22 - 20, 2)
        assert handle.read(4) == b"PK\x06\x07", "gói thử phải thật sự là ZIP64"
    result = _probe(handler, file, 96, tmp_path / "thumb.png")
    assert result.returncode == 0, result.stdout + result.stderr
    _assert_is_the_cover(tmp_path / "thumb.png", 96)


def test_a_real_book_file_shows_its_cover(handler, tmp_path: Path) -> None:
    """File do chính bookfile.pack ghi: bìa người dùng đặt cho sách hiện ra ở Explorer."""
    project = make_project(tmp_path)
    covers.save_cover_bytes(project, _cover())
    file = bookfile.pack(project, tmp_path / f"sach{bookfile.EXTENSION}")
    result = _probe(handler, file, 256, tmp_path / "thumb.png")
    assert result.returncode == 0, result.stdout + result.stderr
    image = Image.open(tmp_path / "thumb.png")
    assert max(image.size) == 256
