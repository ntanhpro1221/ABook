"""Soát a92 V3: bước "Tải Whisper" làm tiếp được phần tải dở. `whisper.load_model("turbo")` tự tải bằng `_download` của
openai-whisper - file dở sai băm thì mở lại bằng `wb`, không Range. Giờ app tải checkpoint bằng downloader của Studio (Range, kiểm
băm) rồi nạp từ đường dẫn file. Mạng ở đây là giả."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

from abook.webui import studio_setup
from abook.webui.studio_setup import SetupError, StudioSetup

PAYLOAD = b"0123456789abcdef" * 4096
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()
URL = f"https://openaipublic.example.invalid/whisper/models/{DIGEST}/large-v3-turbo.pt"


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, status: int, headers: dict[str, str]) -> None:
        super().__init__(body)
        self.status, self.headers = status, headers

    def __enter__(self): return self
    def __exit__(self, *_exc): return False
    def info(self): return self.headers


class FakeNetwork:
    def __init__(self, supports_range: bool = True) -> None:
        self.requests: list[tuple[str, str, str | None]] = []
        self.supports_range = supports_range

    def urlopen(self, request, timeout=None):  # noqa: ANN001
        method = request.get_method()
        rng = request.headers.get("Range")
        self.requests.append((method, request.full_url, rng))
        if method == "HEAD":
            return FakeResponse(b"", 200, {"Content-Length": str(len(PAYLOAD))})
        if rng and self.supports_range:
            start = int(rng.removeprefix("bytes=").rstrip("-"))
            return FakeResponse(PAYLOAD[start:], 206, {"Content-Length": str(len(PAYLOAD) - start)})
        return FakeResponse(PAYLOAD, 200, {"Content-Length": str(len(PAYLOAD))})


def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, network: FakeNetwork) -> StudioSetup:
    monkeypatch.setattr(studio_setup.urllib.request, "urlopen", network.urlopen)
    setup = StudioSetup(tmp_path / "Studio", tmp_path / "app", gpu=lambda: None)
    setup._whisper_pin = lambda: URL  # type: ignore[method-assign]
    return setup


def _checkpoint(setup: StudioSetup) -> Path:
    return setup.runtime / "models" / "whisper" / "large-v3-turbo.pt"


def test_a_partial_download_left_by_whisper_itself_is_continued_with_a_range_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    network = FakeNetwork()
    setup = _setup(tmp_path, monkeypatch, network)
    partial = _checkpoint(setup)
    partial.parent.mkdir(parents=True)
    partial.write_bytes(PAYLOAD[: len(PAYLOAD) * 6 // 10])  # whisper ghi thẳng vào tên cuối: dở 6/10
    setup._fetch_whisper_checkpoint()
    gets = [request for request in network.requests if request[0] == "GET"]
    assert gets == [("GET", URL, f"bytes={len(PAYLOAD) * 6 // 10}-")], "chỉ xin phần còn thiếu"
    assert _checkpoint(setup).read_bytes() == PAYLOAD
    assert not _checkpoint(setup).with_name(_checkpoint(setup).name + ".part").exists()


def test_a_part_file_from_the_studio_downloader_continues_too_and_a_finished_file_is_not_fetched_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    network = FakeNetwork()
    setup = _setup(tmp_path, monkeypatch, network)
    target = _checkpoint(setup)
    target.parent.mkdir(parents=True)
    target.with_name(target.name + ".part").write_bytes(PAYLOAD[:1000])
    setup._fetch_whisper_checkpoint()
    assert [r[2] for r in network.requests if r[0] == "GET"] == ["bytes=1000-"]
    network.requests.clear()
    setup._fetch_whisper_checkpoint()
    assert [r for r in network.requests if r[0] == "GET"] == [], "đã đủ và đúng băm: không tải lại"


def test_a_server_that_ignores_range_restarts_cleanly_and_a_wrong_hash_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    network = FakeNetwork(supports_range=False)
    setup = _setup(tmp_path, monkeypatch, network)
    target = _checkpoint(setup)
    target.parent.mkdir(parents=True)
    target.write_bytes(PAYLOAD[:500])
    setup._fetch_whisper_checkpoint()
    assert target.read_bytes() == PAYLOAD, "máy chủ không nhận Range: tải lại đủ, file đúng"

    bad = _setup(tmp_path / "bad", monkeypatch, FakeNetwork())
    bad._whisper_pin = lambda: URL.replace(DIGEST, "0" * 64)  # type: ignore[method-assign]
    with pytest.raises(SetupError, match="không đúng bản đã ghim"):
        bad._fetch_whisper_checkpoint()
    assert not _checkpoint(bad).exists()


def test_the_asr_step_fetches_the_checkpoint_first_and_loads_it_from_its_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    setup = _setup(tmp_path, monkeypatch, FakeNetwork())
    order: list[str] = []
    setup._fetch_whisper_checkpoint = lambda: order.append("fetch")  # type: ignore[method-assign]
    setup._run = lambda command, what: order.append(what) or ""  # type: ignore[method-assign]
    setup._step_asr()
    assert order == ["fetch", "Tải Whisper"]
    assert 'load_model("turbo"' not in studio_setup.ASR_SCRIPT and "_MODELS" in studio_setup.ASR_SCRIPT
    assert "faster_whisper" in studio_setup.ASR_SCRIPT, "bộ nhận dạng thứ hai vẫn được tải và kiểm"


def test_the_pin_is_read_from_the_installed_whisper_package(tmp_path: Path) -> None:
    if importlib.util.find_spec("whisper") is None:
        pytest.skip("không có openai-whisper trong môi trường thử")
    setup = StudioSetup(tmp_path / "Studio", tmp_path / "app", gpu=lambda: None)
    setup.venv = Path(sys.executable).parents[1]  # python của môi trường thử đóng vai python của Studio
    url = setup._whisper_pin()
    assert url.startswith("https://") and url.endswith("/large-v3-turbo.pt")
    assert len(url.split("/")[-2]) == 64, "băm SHA-256 nằm trong đường dẫn, như openai-whisper tự kiểm"
