"""Ảnh bìa thật (webui/covers.py): lưu một lần đã chuẩn hoá, đi theo sách sang điện thoại và vào file MP3 xuất ra."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import pytest
from PIL import Image

from ebook_reader.webui import covers


def data_url(image: Image.Image, kind: str = "PNG") -> str:
    buffer = io.BytesIO()
    image.save(buffer, kind)
    mime = {"PNG": "png", "JPEG": "jpeg", "WEBP": "webp"}[kind]
    return f"data:image/{mime};base64," + base64.b64encode(buffer.getvalue()).decode()


def test_a_big_portrait_photo_is_stored_small_with_its_colour(tmp_path: Path) -> None:
    photo = Image.new("RGB", (2400, 3600), (180, 40, 60))
    meta = covers.save_cover(tmp_path, data_url(photo, "JPEG"))
    stored = Image.open(tmp_path / covers.COVER_FILE)
    assert stored.format == "JPEG"
    assert max(stored.size) == covers.MAX_SIDE and stored.size[0] < stored.size[1], "giữ tỉ lệ dọc, chỉ thu nhỏ"
    assert (meta["width"], meta["height"]) == stored.size
    red, green, blue = (int(meta["color"][i:i + 2], 16) for i in (1, 3, 5))
    assert red > green and red > blue, f"màu chủ đạo của một ảnh đỏ phải đỏ, được {meta['color']}"
    assert json.loads((tmp_path / covers.META_FILE).read_text(encoding="utf-8"))["color"] == meta["color"]


def test_transparency_becomes_white_not_black(tmp_path: Path) -> None:
    logo = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    covers.save_cover(tmp_path, data_url(logo))
    assert Image.open(tmp_path / covers.COVER_FILE).getpixel((10, 10))[0] > 240


@pytest.mark.parametrize("bad", ["", "hello", "data:image/png;base64,####", "data:text/plain;base64,aGVsbG8="])
def test_what_is_not_an_image_is_refused_with_a_reason(tmp_path: Path, bad: str) -> None:
    with pytest.raises(covers.CoverError):
        covers.save_cover(tmp_path, bad)
    assert covers.cover_file(tmp_path) is None


def test_a_tiny_image_is_refused(tmp_path: Path) -> None:
    with pytest.raises(covers.CoverError, match="quá nhỏ"):
        covers.save_cover(tmp_path, data_url(Image.new("RGB", (40, 40), "blue")))


def test_the_view_carries_a_versioned_url_and_removal_forgets_everything(tmp_path: Path) -> None:
    assert covers.cover_view(tmp_path, "BOOK") is None
    covers.save_cover(tmp_path, data_url(Image.new("RGB", (500, 500), (20, 90, 160))))
    view = covers.cover_view(tmp_path, "BOOK")
    assert view["url"] == f"/media/books/BOOK/cover?v={view['version']}"
    covers.remove_cover(tmp_path)
    assert covers.cover_view(tmp_path, "BOOK") is None
    assert not (tmp_path / covers.META_FILE).exists()
    covers.remove_cover(tmp_path)  # gỡ hai lần không lỗi


def test_the_colour_prefers_a_hue_over_a_grey_background(tmp_path: Path) -> None:
    poster = Image.new("RGB", (400, 400), (235, 235, 235))
    poster.paste((30, 120, 200), (100, 100, 300, 300))  # một khối xanh giữa nền xám nhạt chiếm phần lớn
    meta = covers.save_cover(tmp_path, data_url(poster))
    red, green, blue = (int(meta["color"][i:i + 2], 16) for i in (1, 3, 5))
    assert blue > red, f"màu nhuộm phải là màu xanh của hình, không phải nền xám: {meta['color']}"
