"""Bài nhạc tải từ NGUỒN GỐC phải khớp `bytes` / `sha1` của danh mục như bản sao (Android: MusicCatalog.download): bản cụt hay bị đổi mà
Content-Length tự nhất quán không được cất như bài tốt, và bài đã nằm sẵn trong bộ đệm mà sai cỡ / sai hash thì bị loại, tải lại."""
from __future__ import annotations

import hashlib
import io
import urllib.request
from pathlib import Path

import pytest

from abook.webui import music_catalog
from abook.webui.server import ApiError
from tests.test_a_project_can_be_renamed_or_deleted import studio  # noqa: F401 - fixture dùng chung
from tests.test_music_api import CALM, _with_catalog

GOOD = b"ID3" + b"\x01" * 997


def _body(data: bytes) -> io.BytesIO:
    response = io.BytesIO(data)
    response.headers = {"Content-Length": str(len(data))}  # type: ignore[attr-defined]
    return response


def _setup(app, tmp_path: Path, monkeypatch, bodies: dict[str, bytes], *, mirrors: list[str] | None = None):
    _with_catalog(app, tmp_path)
    info = {"bytes": len(GOOD), "sha1": hashlib.sha1(GOOD).hexdigest(), **({"mirrors": mirrors} if mirrors else {})}
    monkeypatch.setattr(app.music_catalog(), "lookup", lambda links: {link: info for link in links})
    calls: list[str] = []

    def open_(request, timeout=0):
        calls.append(request.full_url)
        return _body(bodies[request.full_url])

    monkeypatch.setattr(urllib.request, "urlopen", open_)
    return calls


@pytest.mark.parametrize("bad", [b"ID3" + b"\x01" * 297, b"ID3" + b"\x02" * 997], ids=["short-with-honest-length", "same-size-wrong-content"])
def test_an_original_download_that_differs_from_the_catalog_is_not_kept(studio, tmp_path: Path, monkeypatch, bad: bytes) -> None:  # noqa: F811
    _paths, app, _server, _runner = studio
    calls = _setup(app, tmp_path, monkeypatch, {CALM: bad})
    with pytest.raises(ApiError):
        app.music_track_file(CALM)
    assert app.music_track_cached(CALM) is None, "bản sai cỡ / sai hash nằm trong bộ đệm như bài tốt"
    assert not list((app.music_dir / "files").glob("*.part"))
    assert calls == [CALM]


def test_a_bad_original_falls_back_to_the_matching_mirror(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    _paths, app, _server, _runner = studio
    mirror = "https://archive.org/download/abook-music-x/a.mp3"
    calls = _setup(app, tmp_path, monkeypatch, {CALM: GOOD[:300], mirror: GOOD}, mirrors=[mirror])
    assert app.music_track_file(CALM).read_bytes() == GOOD
    assert calls == [CALM, mirror]


@pytest.mark.parametrize("stale", [b"ID3" + b"\x01" * 297, b"ID3" + b"\x02" * 997], ids=["wrong-size", "wrong-hash"])
def test_a_cached_track_that_differs_from_the_catalog_is_dropped_and_downloaded_again(studio, tmp_path: Path, monkeypatch, stale: bytes) -> None:  # noqa: F811
    _paths, app, _server, _runner = studio
    calls = _setup(app, tmp_path, monkeypatch, {CALM: GOOD})
    target = app._music_file(CALM)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(stale)
    assert app.music_track_file(CALM).read_bytes() == GOOD
    assert calls == [CALM]
    app.music_track_file(CALM)  # bản tốt: dùng lại, không tải nữa
    assert calls == [CALM]


def test_a_good_cached_track_is_served_without_the_network_and_an_unreadable_catalog_keeps_it(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    _paths, app, _server, _runner = studio
    calls = _setup(app, tmp_path, monkeypatch, {})
    target = app._music_file(CALM)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(GOOD)
    assert app.music_track_file(CALM) == target and not calls

    def offline(links):
        raise music_catalog.CatalogError("mất mạng")

    stale = app._music_file("https://x/other.mp3")
    stale.write_bytes(b"ID3short")
    monkeypatch.setattr(app.music_catalog(), "lookup", offline)
    assert app.music_track_file("https://x/other.mp3") == stale and stale.read_bytes() == b"ID3short", "chưa đọc được danh mục thì giữ bài đang có"
