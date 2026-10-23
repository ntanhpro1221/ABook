"""Ảnh bìa thật (webui/covers.py): lưu một lần đã chuẩn hoá, đi theo sách sang điện thoại và vào file MP3 xuất ra."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import pytest
from PIL import Image

from abook.webui import covers


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


def test_only_the_providers_image_hosts_can_be_fetched() -> None:
    from abook.webui import cover_search

    assert cover_search.allowed_image_url("https://is1-ssl.mzstatic.com/image/thumb/x/1000x1000bb.jpg")
    assert cover_search.allowed_image_url("https://covers.openlibrary.org/b/id/42-L.jpg")
    for bad in ("http://covers.openlibrary.org/b/id/42-L.jpg", "https://127.0.0.1/x.jpg", "https://evil.example/x.jpg",
                "file:///C:/Windows/win.ini", "https://covers.openlibrary.org.evil.example/x.jpg"):
        assert not cover_search.allowed_image_url(bad), bad
    with pytest.raises(covers.CoverError):
        cover_search.download_image("http://192.168.1.1/admin.png")


def test_a_failing_provider_does_not_spoil_the_search(monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui import cover_search

    def works(query: str) -> list[dict]:
        hit = {"provider": "A", "title": query, "author": "", "thumb": "https://covers.openlibrary.org/b/id/1-M.jpg",
               "url": "https://covers.openlibrary.org/b/id/1-L.jpg"}
        return [hit, dict(hit), {**hit, "url": "https://evil.example/2.jpg"}]

    def breaks(query: str) -> list[dict]:
        raise OSError("429 quota")

    monkeypatch.setattr(cover_search, "PROVIDERS", [works, breaks])
    found = cover_search.search("  Tên   sách ")
    assert found["query"] == "Tên sách"
    assert [item["url"] for item in found["results"]] == ["https://covers.openlibrary.org/b/id/1-L.jpg"], \
        "trùng thì gộp, host lạ thì bỏ"
    assert found["failed"] == ["breaks"]
    assert cover_search.search("x")["results"] == []


def test_a_source_that_trickles_cannot_hold_the_whole_search_past_its_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    import threading
    import time

    from abook.webui import cover_search

    release = threading.Event()
    hit = {"provider": "A", "title": "x", "author": "", "thumb": "https://covers.openlibrary.org/b/id/1-M.jpg",
           "url": "https://covers.openlibrary.org/b/id/1-L.jpg"}

    def works(_query: str) -> list[dict]:
        return [hit]

    def trickles(_query: str) -> list[dict]:
        release.wait(30)  # nguồn nhỏ giọt: từng thao tác socket đều chưa quá hạn nhưng không bao giờ xong
        return []

    monkeypatch.setattr(cover_search, "PROVIDERS", [works, trickles])
    monkeypatch.setattr(cover_search, "SEARCH_DEADLINE", 0.4)
    started = time.monotonic()
    try:
        found = cover_search.search("Tên sách")
        assert time.monotonic() - started < 3, "ra khỏi khối tìm không được chờ luồng của nguồn treo"
    finally:
        release.set()
    assert [item["url"] for item in found["results"]] == [hit["url"]] and found["failed"] == ["trickles"]


def test_a_dribbling_download_is_dropped_and_the_listener_never_sees_the_library_error_text(monkeypatch: pytest.MonkeyPatch) -> None:
    import time
    import urllib.error

    from abook.webui import cover_search

    url = "https://covers.openlibrary.org/b/id/1-L.jpg"
    for error in (urllib.error.URLError("[Errno 11001] getaddrinfo failed"),
                  urllib.error.HTTPError(url, 503, "Service Unavailable", {}, None),  # type: ignore[arg-type]
                  TimeoutError("timed out")):
        def refuse(*_args, _error=error, **_kwargs):
            raise _error

        monkeypatch.setattr(cover_search.urllib.request, "urlopen", refuse)
        with pytest.raises(covers.CoverError) as caught:
            cover_search.download_image(url)
        message = str(caught.value)
        assert message == cover_search.DOWNLOAD_FAILED
        assert "urlopen" not in message and "HTTP Error" not in message and "Errno" not in message

    class Dribble:
        def read(self, _amount: int) -> bytes:
            time.sleep(0.02)
            return b"x"

    with pytest.raises(TimeoutError):
        cover_search._read_within(Dribble(), covers.MAX_UPLOAD_BYTES, 0.2)


def test_a_picture_with_too_many_pixels_is_refused_before_it_is_unpacked() -> None:
    # PNG đơn sắc nén còn vài chục KB nhưng giải nén ra ~200 MB: không được giải nén.
    huge = Image.new("L", (8000, 8000), 7)
    buffer = io.BytesIO()
    huge.save(buffer, "PNG", optimize=False)
    assert len(buffer.getvalue()) < covers.MAX_UPLOAD_BYTES
    with pytest.raises(covers.CoverError, match="Ảnh vượt 40 triệu điểm ảnh"):
        covers.render_cover(buffer.getvalue())

    # Ảnh chụp điện thoại lớn (JPEG) vẫn dùng được: giải mã thẳng ở cỡ nhỏ.
    photo = io.BytesIO()
    Image.new("RGB", (8000, 6000), (180, 40, 60)).save(photo, "JPEG", quality=60)
    jpeg, meta = covers.render_cover(photo.getvalue())
    assert max(meta["width"], meta["height"]) <= covers.MAX_SIDE and jpeg
