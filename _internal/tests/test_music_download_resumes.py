"""Bài nhạc nền tải đứt giữa chừng (nguồn chậm 11-30 KB/s, Wi-Fi chập chờn) không mất phần đã tải: `.part` của bài nằm lại, lượt
sau (hay ngay trong lượt, khi nguồn vừa gửi thêm byte) tải tiếp bằng Range; nguồn không trả 206 thì tải lại từ 0. Đứt sau khi đã có
byte là nguồn chậm, không phải mất mạng: nguồn không bị cho nghỉ 5 phút, luồng tải sẵn xếp bài lại. Đo 01-11 (CS1): lượt tải sẵn đứt
lúc ~13 MB thì xoá trắng, chương sau tải lại từ 0 ở 30 KB/s nên cả chương không có nhạc.
Máy chủ HTTP thật trên 127.0.0.1, mỗi kết nối một câu trả lời soạn sẵn, ghi lại yêu cầu (để xem dòng Range)."""
from __future__ import annotations

import socket
import threading
import time
import urllib.request
from http import HTTPStatus
from pathlib import Path

import pytest

from abook.webui.server import ApiError, LiveTrack
from tests.test_a_project_can_be_renamed_or_deleted import studio  # noqa: F401 - fixture dùng chung
from tests.test_music_api import CALM, CALM2, _with_catalog

_URLOPEN = urllib.request.urlopen  # bản thật, lấy trước mọi monkeypatch (đổi cổng lần hai không được gọi qua bản vá lần một)
FULL = b"ID3" + bytes(range(256)) * 3 + b"\x07" * 229  # 1000 byte, mỗi chỗ một giá trị khác nhau đủ để thấy nối sai chỗ
assert len(FULL) == 1000


def _ok(body: bytes, length: int = 1000) -> bytes:
    return b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % length + body


def _partial(start: int, body: bytes) -> bytes:
    return (b"HTTP/1.1 206 Partial Content\r\nContent-Range: bytes %d-999/1000\r\nContent-Length: %d\r\nConnection: close\r\n\r\n"
            % (start, 1000 - start) + body)


def _serve(replies: list[bytes]) -> tuple[int, list[str]]:
    """Máy chủ trả lần lượt `replies` (mỗi kết nối một câu, gửi xong thì đóng - câu hứa nhiều byte hơn là một lần đứt), hết thì
    đóng cổng (kết nối sau bị từ chối = mất mạng). Trả (cổng, các yêu cầu đã nhận)."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(len(replies))
    seen: list[str] = []

    def serve() -> None:
        with listener:
            listener.settimeout(10)
            for reply in replies:
                conn, _addr = listener.accept()
                with conn:
                    seen.append(conn.recv(65536).decode("latin-1"))
                    conn.sendall(reply)

    threading.Thread(target=serve, daemon=True).start()
    return listener.getsockname()[1], seen


def _to_local(monkeypatch, port: int) -> None:
    def local(request, timeout=0):
        return _URLOPEN(urllib.request.Request(f"http://127.0.0.1:{port}/track.mp3", headers=dict(request.header_items())), timeout=5)

    monkeypatch.setattr(urllib.request, "urlopen", local)


def _range(request: str) -> str | None:
    return next((line.split(":", 1)[1].strip() for line in request.splitlines() if line.lower().startswith("range:")), None)


def _parts(app) -> list[Path]:
    return list((app.music_dir / "files").glob("*.part"))


def test_a_cut_off_download_goes_on_from_the_byte_it_reached(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    _paths, app, _server, _runner = studio
    _with_catalog(app, tmp_path)
    port, seen = _serve([_ok(FULL[:300]), _partial(300, FULL[300:])])
    _to_local(monkeypatch, port)
    path = app.music_track_for_export(CALM)
    assert path is not None and path.read_bytes() == FULL, "nối phần tải tiếp sai chỗ"
    assert [_range(r) for r in seen] == [None, "bytes=300-"]
    assert not _parts(app)


def test_the_next_download_resumes_what_the_last_one_kept(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    _paths, app, _server, _runner = studio
    _with_catalog(app, tmp_path)
    port, _seen = _serve([_ok(FULL[:300])])  # đứt ở byte 300, rồi mất mạng hẳn
    _to_local(monkeypatch, port)
    assert app.music_track_for_export(CALM) is None
    assert app.music_track_cached(CALM) is None, "phần dở thành bài trong bộ đệm"
    assert [p.stat().st_size for p in _parts(app)] == [300], "phần đã tải bị bỏ"
    # Đã nhận được byte = nguồn chậm, không phải mất mạng: nguồn không nghỉ, bài không bị đánh dấu hỏng.
    assert CALM not in app._music_unavailable
    assert app.music_track_available(CALM2) is True
    port, seen = _serve([_partial(300, FULL[300:])])
    _to_local(monkeypatch, port)
    path = app.music_track_for_export(CALM)
    assert path is not None and path.read_bytes() == FULL
    assert [_range(r) for r in seen] == ["bytes=300-"]
    assert not _parts(app)


def test_a_source_that_ignores_the_range_is_downloaded_again_from_zero(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    _paths, app, _server, _runner = studio
    _with_catalog(app, tmp_path)
    port, _seen = _serve([_ok(FULL[:300])])
    _to_local(monkeypatch, port)
    assert app.music_track_for_export(CALM) is None
    port, seen = _serve([_ok(FULL)])  # trả 200 cả bài dù được xin từ byte 300
    _to_local(monkeypatch, port)
    path = app.music_track_for_export(CALM)
    assert path is not None and path.read_bytes() == FULL, "nối cả bài vào sau phần cũ"
    assert [_range(r) for r in seen] == ["bytes=300-"]


def test_a_range_the_source_cannot_serve_starts_over(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    _paths, app, _server, _runner = studio
    _with_catalog(app, tmp_path)
    port, _seen = _serve([_ok(FULL[:300])])
    _to_local(monkeypatch, port)
    assert app.music_track_for_export(CALM) is None
    port, seen = _serve([b"HTTP/1.1 416 Range Not Satisfiable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n", _ok(FULL)])
    _to_local(monkeypatch, port)
    path = app.music_track_for_export(CALM)
    assert path is not None and path.read_bytes() == FULL
    assert [_range(r) for r in seen] == ["bytes=300-", None]


def test_a_cut_before_any_byte_is_still_a_network_failure(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    _paths, app, _server, _runner = studio
    _with_catalog(app, tmp_path)
    port, _seen = _serve([_ok(b"")])
    _to_local(monkeypatch, port)
    assert app.music_track_for_export(CALM) is None
    assert not _parts(app), "giữ file dở rỗng"
    assert app.music_track_available(CALM2) is False, "đứt khi chưa có byte nào là mất mạng: nguồn phải nghỉ"


def test_a_reader_following_the_download_reads_on_across_a_resume(tmp_path: Path) -> None:
    part = tmp_path / "t.mp3.part"
    live = LiveTrack(1000)
    got: list[bytes] = []
    errors: list[Exception] = []

    def read() -> None:
        try:
            got.extend(live.chunks(idle=5))
        except ApiError as exc:
            errors.append(exc)

    live.begin(part)
    part.write_bytes(FULL[:300])
    live.grew(300)
    reader = threading.Thread(target=read)
    reader.start()
    deadline = time.monotonic() + 5
    while sum(map(len, got)) < 300 and time.monotonic() < deadline:
        time.sleep(0.01)
    live.discard(part, keep=True)  # đứt
    live.begin(part, 300)  # tải tiếp đúng chỗ người đọc đứng
    with part.open("ab") as sink:
        sink.write(FULL[300:])
    live.grew(1000)
    target = tmp_path / "t.mp3"
    live.finish(target, part)
    reader.join(5)
    assert not errors and b"".join(got) == FULL


def test_a_reader_cannot_go_on_when_the_source_starts_again_from_zero(tmp_path: Path) -> None:
    part = tmp_path / "t.mp3.part"
    live = LiveTrack(1000)
    live.begin(part)
    part.write_bytes(FULL[:300])
    live.grew(300)
    chunks = live.chunks(idle=5)
    assert next(chunks) == FULL[:300]
    live.begin(part, 0)
    with pytest.raises(ApiError) as caught:
        next(chunks)
    assert caught.value.status == HTTPStatus.BAD_GATEWAY


def test_the_warm_queue_retries_a_track_whose_download_made_progress(studio, tmp_path: Path, monkeypatch, caplog) -> None:  # noqa: F811
    _paths, app, _server, _runner = studio
    _with_catalog(app, tmp_path)
    calls: list[str] = []

    def flaky(link: str, **_fetch):
        calls.append(link)
        part = app._music_part(app._music_file(link))
        part.parent.mkdir(parents=True, exist_ok=True)
        if len(calls) == 1:
            part.write_bytes(FULL[:300])  # nguồn chậm: được một ít rồi đứt
            raise ApiError(HTTPStatus.BAD_GATEWAY, "đứt")
        if len(calls) == 2:
            raise ApiError(HTTPStatus.BAD_GATEWAY, "đứt, không thêm byte nào")
        return part

    monkeypatch.setattr(app, "music_track_file", flaky)
    monkeypatch.setattr(app, "music_track_available", lambda *_a, **_k: True)
    with caplog.at_level("WARNING"):
        assert app.music_warm(CALM)
        deadline = time.monotonic() + 5
        while (app._music_warm_thread is not None or len(calls) < 2) and time.monotonic() < deadline:
            time.sleep(0.01)
    assert calls == [CALM, CALM], "bài có tiến triển không được xếp lại / bài không tiến triển bị xếp lại mãi"
    assert sum("tải sẵn nhạc" in r.getMessage() for r in caplog.records) == 2, "tải sẵn hỏng mà không có dòng log"
