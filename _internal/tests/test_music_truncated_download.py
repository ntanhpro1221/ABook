"""Tải bài nhạc nền bị đứt giữa chừng (Wi-Fi rớt, máy chủ nguồn đóng kết nối): không được giữ file cụt trong bộ đệm như bài tốt -
bài cụt sẽ phát (và lặp) mãi một mẩu đầu bài. Coi như lỗi mạng: không lưu, cả máy tạm coi là offline, lần sau tải lại từ đầu.
Dùng máy chủ HTTP thật trên 127.0.0.1 để http.client cư xử đúng như ngoài đời (đọc hết dữ liệu sớm trả b"", hay ném IncompleteRead)."""
from __future__ import annotations

import socket
import threading
import urllib.request
from pathlib import Path

import pytest

from tests.test_a_project_can_be_renamed_or_deleted import studio  # noqa: F401 - fixture dùng chung
from tests.test_music_api import CALM, CALM2, _with_catalog

_FULL = b"ID3" + b"\x01" * 997


def _cut_server(head: bytes, body: bytes) -> int:
    """Máy chủ một lần: gửi `head` + `body` rồi đóng kết nối (dù đầu trả lời hứa nhiều hơn). Trả cổng."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)

    def serve() -> None:
        with listener:
            listener.settimeout(10)
            conn, _addr = listener.accept()
            with conn:
                conn.recv(65536)
                conn.sendall(head + body)

    threading.Thread(target=serve, daemon=True).start()
    return listener.getsockname()[1]


def _to_local(monkeypatch, port: int) -> None:
    real = urllib.request.urlopen
    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout=0: real(f"http://127.0.0.1:{port}/track.mp3", timeout=5))


@pytest.mark.parametrize("head, body", [
    (b"HTTP/1.1 200 OK\r\nContent-Length: 1000\r\nConnection: close\r\n\r\n", _FULL[:300]),
    (b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n", b"3e8\r\n" + _FULL[:300]),
], ids=["content-length", "chunked"])
def test_a_download_cut_off_midway_is_not_kept_as_the_track(studio, tmp_path: Path, monkeypatch, head: bytes,  # noqa: F811
                                                            body: bytes) -> None:
    _paths, app, _server, _runner = studio
    _with_catalog(app, tmp_path)
    _to_local(monkeypatch, _cut_server(head, body))
    assert app.music_track_for_export(CALM) is None, "bài tải đứt giữa chừng mà vẫn trả file"
    assert app.music_track_cached(CALM) is None, "file cụt nằm trong bộ đệm như bài tốt"
    assert not list((app.music_dir / "files").glob("*.part"))
    # Đứt kết nối là lỗi mạng: bài không bị đánh dấu hỏng 24 giờ, chỉ cả máy tạm coi là offline.
    assert CALM not in app._music_unavailable
    assert app.music_track_available(CALM2) is False


def test_a_whole_download_is_kept(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    _paths, app, _server, _runner = studio
    _with_catalog(app, tmp_path)
    _to_local(monkeypatch, _cut_server(b"HTTP/1.1 200 OK\r\nContent-Length: 1000\r\nConnection: close\r\n\r\n", _FULL))
    path = app.music_track_for_export(CALM)
    assert path is not None and path.read_bytes() == _FULL
