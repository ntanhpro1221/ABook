"""Soát a106r: tải mô-đun giọng trên máy tính. Mạng ở đây là giả."""
from __future__ import annotations

import hashlib
import io
import ssl
from pathlib import Path

import pytest

from abook.webui import studio_setup
from abook.webui.studio_setup import Download, SetupError, download, download_failure

DATA = b"x" * 300_000


class Response(io.BytesIO):
    status = 200

    def __init__(self, body: bytes, status: int = 200, fail_at: int = 0) -> None:
        super().__init__(body)
        self.status = status
        self.reads = 0
        self.fail_at = fail_at

    def read(self, size: int = -1) -> bytes:
        self.reads += 1
        if self.fail_at and self.reads == self.fail_at:
            raise ssl.SSLEOFError(8, "EOF occurred in violation of protocol (_ssl.c:2426)")
        return super().read(size)

    def __enter__(self): return self
    def __exit__(self, *_exc): return False


def item() -> Download:
    return Download("m.bin", "https://example.invalid/m.bin", hashlib.sha256(DATA).hexdigest(), len(DATA))


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(studio_setup.time, "sleep", lambda _seconds: None)


def test_an_ssl_error_in_the_middle_of_a_download_is_retried_from_the_part_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ranges: list[str | None] = []

    def urlopen(request, timeout=None):  # noqa: ANN001
        ranges.append(request.headers.get("Range"))
        if len(ranges) == 1:
            return Response(DATA, fail_at=3)  # hai khúc về rồi TLS đứt
        start = int(request.headers["Range"].removeprefix("bytes=").rstrip("-"))
        return Response(DATA[start:], status=206)

    monkeypatch.setattr(studio_setup.urllib.request, "urlopen", urlopen)
    target = tmp_path / "m.bin"
    assert download(item(), target, lambda _done, _total: None, lambda: False) == target
    assert target.read_bytes() == DATA
    assert ranges[0] is None and ranges[1] == f"bytes={2 << 16}-"  # tiếp bằng Range từ chỗ đã có
    assert not target.with_name("m.bin.part").exists()


def test_an_ssl_error_that_keeps_happening_is_reported_as_a_network_problem(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def urlopen(request, timeout=None):  # noqa: ANN001
        raise ssl.SSLError(1, "[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol")

    monkeypatch.setattr(studio_setup.urllib.request, "urlopen", urlopen)
    with pytest.raises(SetupError) as raised:
        download(item(), tmp_path / "m.bin", lambda _done, _total: None, lambda: False)
    assert str(raised.value) == studio_setup.NETWORK_FAILURE.format(retry="Cài tiếp")
    sentence, _detail = download_failure("giọng VieNeu", raised.value)
    assert "kết nối" in sentence and "ổ đĩa" not in sentence
    bare, _ = download_failure("giọng VieNeu", ssl.SSLError("bad"))  # lỗi SSL chưa bọc cũng là mạng, không phải ổ đĩa
    assert "kết nối" in bare and "ổ đĩa" not in bare


def _free(monkeypatch: pytest.MonkeyPatch, free: int) -> list[Path]:
    asked: list[Path] = []

    def usage(path):  # noqa: ANN001
        asked.append(Path(path))
        return type("Usage", (), {"total": 10**12, "used": 0, "free": free})()

    monkeypatch.setattr(studio_setup.shutil, "disk_usage", usage)
    return asked


def test_download_refuses_before_the_first_byte_when_the_disk_cannot_hold_the_rest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[object] = []
    monkeypatch.setattr(studio_setup.urllib.request, "urlopen", lambda *a, **k: opened.append(a))
    asked = _free(monkeypatch, studio_setup.SPACE_MARGIN + len(DATA) - 1)
    with pytest.raises(studio_setup.NoSpace) as raised:
        download(item(), tmp_path / "m.bin", lambda _done, _total: None, lambda: False)
    assert opened == [] and asked == [tmp_path]
    sentence, detail = download_failure("giọng VieNeu", raised.value)
    assert "Thiếu chỗ tải" in sentence and "bạn dọn ổ" in sentence and "cần" in sentence and "còn" in sentence and "Thử lại" in sentence and "không ghi được" not in sentence
    assert detail == ""


def test_download_counts_only_what_is_still_missing_and_allows_exactly_enough(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "m.bin"
    target.with_name("m.bin.part").write_bytes(DATA[:200_000])  # đã tải 200 KB: chỉ còn thiếu phần sau
    seen: list[str | None] = []

    def urlopen(request, timeout=None):  # noqa: ANN001
        seen.append(request.headers.get("Range"))
        return Response(DATA[200_000:], status=206)

    monkeypatch.setattr(studio_setup.urllib.request, "urlopen", urlopen)
    _free(monkeypatch, studio_setup.SPACE_MARGIN + len(DATA) - 200_000)
    assert download(item(), target, lambda _done, _total: None, lambda: False) == target
    assert seen == ["bytes=200000-"] and target.read_bytes() == DATA


def test_disk_that_cannot_be_asked_does_not_stop_the_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(studio_setup.urllib.request, "urlopen", lambda request, timeout=None: Response(DATA))

    def broken(_path):  # noqa: ANN001
        raise OSError("no such volume")

    monkeypatch.setattr(studio_setup.shutil, "disk_usage", broken)
    assert download(item(), tmp_path / "m.bin", lambda _done, _total: None, lambda: False).read_bytes() == DATA
