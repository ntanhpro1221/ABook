"""Cover decoders accept the supported formats, including at export boundaries."""

import base64
import io
from pathlib import Path

import pytest
from PIL import Image

from abook.webui import covers, export


def image_bytes(kind: str) -> bytes:
    buffer = io.BytesIO()
    with Image.new("1" if kind == "XBM" else "RGB", (96, 128)) as image:
        image.save(buffer, kind)
    return buffer.getvalue()


@pytest.mark.parametrize("kind", ["JPEG", "PNG", "WEBP", "GIF", "BMP"])
def test_supported_cover_formats_render_and_export(tmp_path: Path, kind: str) -> None:
    raw = image_bytes(kind)
    jpeg, meta = covers.render_cover(raw)
    with Image.open(io.BytesIO(jpeg)) as rendered:
        assert rendered.format == "JPEG"
        assert rendered.size == (96, 128)
        rendered.load()
    assert (meta["width"], meta["height"]) == (96, 128)
    assert covers.clean_color(meta["color"]) == meta["color"]
    source = tmp_path / "cover.jpg"
    source.write_bytes(raw)
    assert export.usable_cover(source) == source


@pytest.mark.parametrize("kind", ["TIFF", "XBM"])
def test_other_cover_formats_follow_existing_error_contract(tmp_path: Path, kind: str) -> None:
    raw = image_bytes(kind)
    # Confirm valid fixtures: rejection must come from the format boundary.
    with Image.open(io.BytesIO(raw)) as image:
        assert image.format == kind
        image.load()
    with pytest.raises(covers.CoverError, match="^Không đọc được ảnh này$"):
        covers.render_cover(raw)
    # A claimed MIME type or filename must not bypass the decoder allowlist.
    data_url = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
    with pytest.raises(covers.CoverError, match="^Không đọc được ảnh này$"):
        covers.save_cover(tmp_path, data_url)
    assert not (tmp_path / covers.COVER_FILE).exists()
    assert not (tmp_path / covers.META_FILE).exists()
    source = tmp_path / "cover.jpg"
    source.write_bytes(raw)
    assert export.usable_cover(source) is None
