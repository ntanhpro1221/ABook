"""GET /api/music/track của bài chưa có trong bộ đệm: byte đầu tới trình phát ngay khi nguồn gửi, không chờ trọn bài (nhạc chương đầu
khi bộ đệm trống phải vào trong vài giây - trình phát máy tính còn bỏ bài nếu 30 s không nhận byte nào). Nhiều người xin cùng lúc
thì cả bài chỉ tải một lần; tải hỏng giữa chừng thì người xin thấy tải hỏng và bộ đệm không giữ bài cụt."""
from __future__ import annotations

import hashlib
import http.client
import io
import threading
import urllib.request
from pathlib import Path
from urllib.parse import quote

import pytest

from tests.test_a_project_can_be_renamed_or_deleted import studio  # noqa: F401 - fixture dùng chung
from tests.test_music_api import _no_background_warming, _with_catalog  # noqa: F401 - fixture tự dùng

LINK = "https://x/slow.mp3"
BODY = b"ID3" + bytes(range(256)) * 1200  # ~300 KB: vài khúc 64 KB


class _HeldSource(io.RawIOBase):
    """Nguồn gửi khúc đầu rồi đứng chờ `release` (mạng chậm); `cut`: nguồn ngắt kết nối sau khúc đầu."""

    def __init__(self, body: bytes, release: threading.Event, cut: bool = False) -> None:
        self.body, self.release, self.cut, self.at = body, release, cut, 0
        self.headers = {"Content-Length": str(len(body))}

    def read(self, size: int = -1) -> bytes:
        if self.at > 0:
            assert self.release.wait(20), "test không thả nguồn"
            if self.cut:
                raise ConnectionResetError("nguồn ngắt giữa bài")
        chunk = self.body[self.at:self.at + (size if size > 0 else len(self.body))]
        self.at += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        self.close()


def _serve(app, monkeypatch, body: bytes = BODY, sha1: str | None = None, cut: bool = False):
    info = {"bytes": len(BODY), "sha1": sha1 or hashlib.sha1(BODY).hexdigest()}
    monkeypatch.setattr(app.music_catalog(), "lookup", lambda links: {link: info for link in links})
    release, calls = threading.Event(), []

    def open_(request, timeout=0):
        calls.append(request.full_url)
        return _HeldSource(body, release, cut)

    monkeypatch.setattr(urllib.request, "urlopen", open_)
    return release, calls


def _get(port: int) -> http.client.HTTPResponse:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request("GET", "/api/music/track?link=" + quote(LINK, safe=""), headers={"X-Ebook-Token": "t"})
    return connection.getresponse()


def _cache_files(app) -> list[Path]:
    folder = app.music_dir / "files"
    return sorted(folder.iterdir()) if folder.is_dir() else []


def test_the_first_bytes_arrive_before_the_download_finishes(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    release, calls = _serve(app, monkeypatch)
    response = _get(server.port)  # nguồn còn đang giữ phần sau: câu trả lời đã phải tới
    assert response.status == 200 and response.getheader("Content-Length") == str(len(BODY))
    head = response.read(4096)
    assert head == BODY[:4096] and not release.is_set()
    assert not app._music_file(LINK).exists(), "bài chưa tải xong thì chưa thành file bộ đệm"
    release.set()
    assert head + response.read() == BODY
    assert calls == [LINK]
    assert _cache_files(app) == [app._music_file(LINK)] and app._music_file(LINK).read_bytes() == BODY


def test_two_players_asking_at_once_share_one_download(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    release, calls = _serve(app, monkeypatch)
    first = _get(server.port)
    head = first.read(1000)
    app.music_warm(LINK)  # luồng tải sẵn xin cùng bài giữa chừng: chờ bài đang tải, không tải lần hai
    second = _get(server.port)  # người thứ hai đọc theo file đang ghi, từ byte 0
    assert second.status == 200 and second.read(1000) == BODY[:1000]
    release.set()
    assert head + first.read() == BODY
    assert BODY[:1000] + second.read() == BODY
    assert calls == [LINK]
    third = _get(server.port)  # đã có trong bộ đệm: file như cũ (tua được)
    assert third.read() == BODY and third.getheader("Accept-Ranges") == "bytes"
    assert calls == [LINK]


@pytest.mark.parametrize("broken", ["cut", "wrong_sha1"])
def test_a_broken_download_reaches_the_player_as_an_error_and_leaves_no_cache(studio, tmp_path: Path, monkeypatch,  # noqa: F811
                                                                             broken: str) -> None:
    """Nguồn ngắt giữa bài, hay gửi đủ byte mà sai sha1 danh mục: kết nối bị cắt trước byte cuối, không file bộ đệm, không file dở."""
    _paths, app, server, _runner = studio
    _with_catalog(app, tmp_path)
    release, _calls = _serve(app, monkeypatch, cut=broken == "cut",
                             sha1=hashlib.sha1(b"bai khac").hexdigest() if broken == "wrong_sha1" else None)
    response = _get(server.port)
    assert response.read(1000) == BODY[:1000]
    release.set()
    with pytest.raises(http.client.IncompleteRead):
        response.read()
    assert _cache_files(app) == []
    with pytest.raises(http.client.IncompleteRead):  # lần sau tải lại từ đầu, lại hỏng: lại là lỗi, không phải bài cụt
        _get(server.port).read()
    assert _cache_files(app) == []
