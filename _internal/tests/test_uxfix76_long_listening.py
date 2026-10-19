"""Soát a69 (nghe lâu): giọng trên máy nhả model khi thôi dùng, bộ đệm clip không quét cả thư mục mỗi lần ghi + trần theo chỗ trống, sổ khoá tải nhạc
không phình."""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import numpy as np

from abook.readaloud import cache as clip_cache
from abook.readaloud import service as readaloud_service
from abook.readaloud.service import ReadAloud
from abook.readaloud.supertonic import Installed, SupertonicProvider
from tests.test_a_project_can_be_renamed_or_deleted import studio  # noqa: F401 - fixture dùng chung
from tests.test_music_api import CALM, CALM2, _with_catalog
from tests.test_music_truncated_download import _FULL, _cut_server, _to_local


class _Engine:
    SAMPLE_RATE = 44_100

    def infer(self, text: str, _name: str, _rng, _speed: float = 1.0) -> np.ndarray:
        return 0.3 * np.sin(np.arange(int(0.2 * max(1, len(text.split())) * self.SAMPLE_RATE)) / 3).astype(np.float32)


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _local_voice(tmp_path: Path) -> tuple[ReadAloud, list[_Engine], _Clock]:
    made: list[_Engine] = []

    def make(_found: Installed) -> _Engine:
        made.append(_Engine())
        return made[-1]

    provider = SupertonicProvider(lambda: Installed(tmp_path, False), engines=make, aligner=lambda: None, normalize=" ".join)
    clock = _Clock()
    return ReadAloud(tmp_path / "cache", [provider], clock=clock), made, clock


def test_a_local_voice_lets_go_of_its_model_after_three_idle_minutes(tmp_path: Path) -> None:
    service, made, clock = _local_voice(tmp_path)
    service.clip("supertonic:F1", "Một đoạn đầu.")
    provider = service.providers["supertonic"]
    assert len(made) == 1 and provider._engine is not None
    clock.now += readaloud_service.IDLE_SECONDS - 1
    assert service.release_idle() == [] and provider._engine is not None, "chưa đủ 3 phút: giữ"
    clock.now += 2
    assert service.release_idle() == ["supertonic"] and provider._engine is None, "3 phút không đọc gì: nhả model"
    assert service.release_idle() == [], "đã nhả thì thôi"
    service.clip("supertonic:F1", "Đoạn kế sau khi nhả.")
    assert len(made) == 2 and provider._engine is not None, "lần dùng sau nạp lại như thường"


def test_background_work_keeps_the_model(tmp_path: Path) -> None:
    service, _made, clock = _local_voice(tmp_path)
    service.clip("supertonic:F1", "Một đoạn đầu.")
    with service.holding("supertonic:F1"):  # xuất sách nói đứng chờ người nghe giữa các đoạn
        clock.now += 10 * readaloud_service.IDLE_SECONDS
        assert service.release_idle() == []
    clock.now += readaloud_service.IDLE_SECONDS
    assert service.release_idle() == ["supertonic"]


def test_a_read_in_flight_is_never_released(tmp_path: Path) -> None:
    service, _made, clock = _local_voice(tmp_path)
    started, go = threading.Event(), threading.Event()
    provider = service.providers["supertonic"]
    real = provider.synthesize

    def slow(*args, **kwargs):
        started.set()
        go.wait(5)
        return real(*args, **kwargs)

    provider.synthesize = slow  # type: ignore[method-assign]
    reader = threading.Thread(target=service.clip, args=("supertonic:F1", "Đoạn đang đọc dở."))
    reader.start()
    assert started.wait(5)
    clock.now += 10 * readaloud_service.IDLE_SECONDS
    assert service.release_idle() == [], "đang đọc: không nhả"
    go.set()
    reader.join(5)


def test_the_cache_ceiling_follows_free_space(tmp_path: Path, monkeypatch) -> None:
    free = {"bytes": 0}
    monkeypatch.setattr(clip_cache.shutil, "disk_usage", lambda _path: type("U", (), {"free": free["bytes"]})())
    free["bytes"] = 4 * 1024**3  # 5 % = 205 MB: không dưới trần cũ
    assert clip_cache.default_limit(tmp_path / "chua-co" / "cache") == clip_cache.LIMIT_BYTES
    free["bytes"] = 20 * 1024**3  # 5 % = 1 GB
    assert clip_cache.default_limit(tmp_path) == 1024**3
    free["bytes"] = 400 * 1024**3
    assert clip_cache.default_limit(tmp_path) == clip_cache.MAX_LIMIT_BYTES
    assert clip_cache.ClipCache(tmp_path).limit == clip_cache.MAX_LIMIT_BYTES


def test_writing_under_the_ceiling_never_scans_the_folder(tmp_path: Path, monkeypatch) -> None:
    store = clip_cache.ClipCache(tmp_path / "c", limit=10_000)
    store.put(clip_cache.clip_key("edge", "v", "đầu"), b"a" * 100, "mp3", 100, [[0, 100]])  # lần đầu tính cỡ thư mục một lần
    scans = []
    real = store._entries
    monkeypatch.setattr(store, "_entries", lambda: scans.append(1) or real())
    for n in range(20):
        store.put(clip_cache.clip_key("edge", "v", f"đoạn {n}"), b"b" * 100, "mp3", 100, [[0, 100]])
    assert scans == [], "dưới trần: tổng đang chạy, không quét thư mục"


def test_over_the_ceiling_trims_with_room_to_spare(tmp_path: Path) -> None:
    store = clip_cache.ClipCache(tmp_path / "c", limit=10_000)
    keys = [clip_cache.clip_key("edge", "v", f"đoạn {n}") for n in range(12)]
    for n, key in enumerate(keys):
        store.put(key, b"x" * 900, "wav", 100, [[0, 100]])
        os.utime(tmp_path / "c" / f"{key}.json", (1000 + n, 1000 + n))  # thứ tự dùng rõ ràng
    assert store.size() <= 10_000 * clip_cache.TRIM_TO, "tỉa xuống dưới trần một khoảng: lần ghi kế không phải tỉa lại"
    assert store.get(keys[-1]) is not None and store.get(keys[0]) is None, "bỏ clip lâu không dùng nhất trước"
    assert store.size() == sum(entry.stat().st_size for entry in (tmp_path / "c").iterdir()), "tổng đang chạy đúng với đĩa"


def test_music_fetch_locks_go_away_when_downloads_finish(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    _paths, app, _server, _runner = studio
    _with_catalog(app, tmp_path)
    _to_local(monkeypatch, _cut_server(b"HTTP/1.1 200 OK\r\nContent-Length: 1000\r\nConnection: close\r\n\r\n", _FULL))
    assert app.music_track_for_export(CALM) is not None
    assert app._music_fetching == {}, "tải xong: sổ khoá về rỗng (soát a69: 9 -> 14 khoá chỉ thêm không bớt)"
    _to_local(monkeypatch, _cut_server(b"HTTP/1.1 200 OK\r\nContent-Length: 1000\r\nConnection: close\r\n\r\n", _FULL[:300]))
    assert app.music_track_for_export(CALM2) is None
    assert app._music_fetching == {}, "tải hỏng: khoá của bài không ở lại"


def test_the_idle_timer_does_not_keep_a_thread_forever(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(readaloud_service, "IDLE_SECONDS", 0.05)
    service, _made, _clock = _local_voice(tmp_path)
    service._clock = time.monotonic
    service.clip("supertonic:F1", "Một đoạn đầu.")
    deadline = time.monotonic() + 5
    while service.providers["supertonic"]._engine is not None and time.monotonic() < deadline:
        time.sleep(0.02)
    assert service.providers["supertonic"]._engine is None, "hẹn giờ tự nhả"
    while service._idle_timer is not None and time.monotonic() < deadline:
        time.sleep(0.02)
    assert service._idle_timer is None, "nhả xong không hẹn tiếp"
