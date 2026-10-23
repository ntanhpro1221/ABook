"""Partial ZIP install through HTTP redirects, interrupted transfers, and integrity failures."""
from __future__ import annotations

import hashlib
import io
import random
import struct
import sys
import threading
import zipfile
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from abook import io_utils
from abook.webui import ffmpeg_setup as ff, studio_setup as setup, zip_range


@pytest.fixture
def remote_zip(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)
    payload = b"MZ" + random.Random(135).randbytes(300000)
    member = "release/bin/ffmpeg.exe"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("release/bin/ffplay.exe", random.Random(1).randbytes(300000))
        z.writestr(member, payload)
        z.writestr("release/bin/ffprobe.exe", random.Random(2).randbytes(300000))
        info = z.getinfo(member)
    data = buffer.getvalue()
    names, extra = struct.unpack_from("<HH", data, info.header_offset + 26)
    start = info.header_offset + 30 + names + extra
    compressed = data[start:start + info.compress_size]
    state = SimpleNamespace(mode="ok", requests=[], payload=payload, data=data, start=start, compressed=compressed,
                            total=len(data), crc=info.CRC, fail_once=False, transferred=0)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            if self.path == "/release":
                self.send_response(302)
                self.send_header("Location", "/asset")
                self.end_headers()
                return
            first, last = map(int, self.headers["Range"][6:].split("-"))
            state.requests.append((first, last))
            mode = state.mode
            self.send_response(200 if mode == "ignore" else 206)
            if mode != "missing":
                self.send_header("Content-Range", f"bytes {first + (mode == 'wrong')}-{last}/{len(data)}")
            self.end_headers()
            body = data[first:last + 1]
            if mode == "short":
                body = body[:-1]
            if state.fail_once and first == start:
                state.fail_once = False
                body = body[:65536]
            state.transferred += len(body)
            try:
                self.wfile.write(body)
            except (ConnectionError, OSError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    item = setup.Download("ffmpeg", f"http://127.0.0.1:{server.server_port}/release",
                          hashlib.sha256(compressed).hexdigest(), len(compressed))
    monkeypatch.setattr(ff, "WHEEL", item)
    monkeypatch.setattr(ff, "MEMBER", member)
    monkeypatch.setattr(ff, "ARCHIVE_SIZE", len(data))
    monkeypatch.setattr(ff, "EXE_SIZE", len(payload))
    monkeypatch.setattr(ff, "EXE_CRC", info.CRC)
    monkeypatch.setattr(ff, "EXE_SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(setup.time, "sleep", lambda _: None)
    ff.configure(tmp_path / "install")
    state.folder = tmp_path / "install"
    state.item = item
    yield state
    ff.configure(None)
    server.shutdown()
    server.server_close()


def test_ffmpeg_range_install_follows_redirect_reads_only_member_and_skips_same_pin(remote_zip):
    r = remote_zip
    seen = []
    exe = ff.install(lambda done, total: seen.append((done, total)))
    assert exe.read_bytes() == r.payload
    assert r.transferred < len(r.compressed) + 65536 < r.total
    assert (r.start, r.start + len(r.compressed) - 1) in r.requests
    assert seen[-1] == (len(r.compressed), len(r.compressed))
    assert io_utils.ffmpeg_executable() == str(exe)
    assert not list(r.folder.glob("*.part")) and not (r.folder / "ffmpeg.deflate").exists()
    before = list(r.requests)
    ff.install(lambda *_: None)
    assert r.requests == before


def test_ffmpeg_range_reconnect_resumes_exact_compressed_bytes(remote_zip):
    r = remote_zip
    r.fail_once = True
    ff.install(lambda *_: None)
    assert (r.start + 65536, r.start + len(r.compressed) - 1) in r.requests
    assert (r.folder / "ffmpeg.exe").read_bytes() == r.payload


def test_ffmpeg_range_cancel_keeps_part_and_next_install_resumes(remote_zip):
    r = remote_zip
    stop = threading.Event()
    with pytest.raises(setup.Cancelled):
        ff.install(lambda done, total: stop.set() if done >= 65536 else None, stop.is_set)
    part = r.folder / "ffmpeg.deflate.part"
    have = part.stat().st_size
    assert 0 < have < len(r.compressed)
    assert not (r.folder / "installed.sha256").exists()
    ff.install(lambda *_: None)
    assert (r.start + have, r.start + len(r.compressed) - 1) in r.requests
    assert not part.exists()


@pytest.mark.parametrize("mode", ["ignore", "wrong", "missing", "short"])
def test_ffmpeg_range_bad_metadata_never_installs(remote_zip, mode):
    r = remote_zip
    r.mode = mode
    with pytest.raises((setup.SetupError, ConnectionError)):
        ff.install(lambda *_: None)
    assert not (r.folder / "ffmpeg.exe").exists()
    assert not (r.folder / "installed.sha256").exists()


@pytest.mark.parametrize("mode", ["ignore", "wrong", "missing"])
def test_ffmpeg_range_payload_requires_exact_206_before_appending(remote_zip, mode):
    r = remote_zip
    r.folder.mkdir()
    part = r.folder / "download.part"
    part.write_bytes(r.compressed[:123])
    r.mode = mode
    with pytest.raises(setup.RangeUnavailable, match="Range") as failure:
        setup.download(r.item, r.folder / "download", lambda *_: None, lambda: False,
                       byte_range=(r.start, r.total))
    assert "HTTP Range" in setup.download_failure("ffmpeg", failure.value)[0]
    assert part.read_bytes() == r.compressed[:123]


@pytest.mark.parametrize("failure", ["compressed_sha", "exe_sha", "crc", "size"])
def test_ffmpeg_range_integrity_failure_preserves_previous_exe_and_stamp(remote_zip, monkeypatch, failure):
    r = remote_zip
    r.folder.mkdir()
    (r.folder / "ffmpeg.exe").write_bytes(b"old executable")
    (r.folder / "installed.sha256").write_text("old stamp")
    if failure == "compressed_sha":
        monkeypatch.setattr(ff, "WHEEL", setup.Download(r.item.name, r.item.url, "0" * 64, r.item.size))
    else:
        attr = {"exe_sha": "EXE_SHA256", "crc": "EXE_CRC", "size": "EXE_SIZE"}[failure]
        monkeypatch.setattr(ff, attr, "0" * 64 if failure == "exe_sha" else 1)
    with pytest.raises(setup.SetupError, match="tải về sai bản" if failure == "compressed_sha" else "ghim"):
        ff.install(lambda *_: None)
    assert (r.folder / "ffmpeg.exe").read_bytes() == b"old executable"
    assert (r.folder / "installed.sha256").read_text() == "old stamp"
    assert not (r.folder / "ffmpeg.exe.part").exists()


@pytest.mark.parametrize("failure", ["crc", "size", "truncated", "trailing", "cancel"])
def test_ffmpeg_inflate_rejects_bad_member_and_cleans_output(tmp_path: Path, failure):
    payload = b"MZ" * 10000
    source, target = tmp_path / "compressed", tmp_path / "ffmpeg.exe.part"
    data = zlib.compress(payload)[2:-4]
    source.write_bytes(data[:-1] if failure == "truncated" else data + b"x" if failure == "trailing" else data)
    with pytest.raises((setup.SetupError, setup.Cancelled)):
        zip_range.inflate(source, target, len(payload) - (failure == "size"), hashlib.sha256(payload).hexdigest(),
                          zlib.crc32(payload) + (failure == "crc"), lambda: failure == "cancel")
    assert not target.exists()


def test_ffmpeg_range_bounds_metadata_before_any_network():
    remote = zip_range._Remote("https://invalid.example", 1000000, lambda: False)
    with pytest.raises(setup.SetupError):
        remote.read(131073)
    remote.seek(-1)
    with pytest.raises(setup.SetupError):
        remote.read(1)
