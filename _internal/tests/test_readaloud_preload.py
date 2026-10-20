"""Nạp sẵn model giọng trên máy lúc mở trang sách (`ReadAloud.preload`, POST /api/readaloud/warm; livejoin3): bấm phát không phải chờ nạp ~4,6 s."""
from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np

from abook import power_source
from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung
from abook.readaloud import service as readaloud_service
from abook.readaloud.service import ReadAloud
from abook.readaloud.supertonic import Installed, SupertonicProvider


class _Engine:
    SAMPLE_RATE = 44_100

    def infer(self, text: str, _name: str, _rng, _speed: float = 1.0) -> np.ndarray:
        return 0.3 * np.sin(np.arange(int(0.2 * max(1, len(text.split())) * self.SAMPLE_RATE)) / 3).astype(np.float32)


class _Clock:
    now = 1000.0

    def __call__(self) -> float:
        return self.now


def _service(tmp_path: Path, spare=lambda: True) -> tuple[ReadAloud, list[_Engine], _Clock, threading.Event]:
    made: list[_Engine] = []
    gate = threading.Event()
    gate.set()

    def make(_found: Installed) -> _Engine:
        gate.wait(5)
        made.append(_Engine())
        return made[-1]

    provider = SupertonicProvider(lambda: Installed(tmp_path, False), engines=make, aligner=lambda: None, normalize=" ".join)
    clock = _Clock()
    return ReadAloud(tmp_path / "cache", [provider], clock=clock, spare=spare), made, clock, gate


def _until(condition, seconds: float = 5.0) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


def test_opening_a_book_loads_the_engine_before_anyone_presses_play(tmp_path: Path) -> None:
    service, made, _clock, _gate = _service(tmp_path)
    provider = service.providers["supertonic"]
    assert service.preload("supertonic:F1") is True
    assert _until(lambda: provider._engine is not None), "model nạp ở nền"
    assert len(made) == 1
    service.clip("supertonic:F1", "Một đoạn đầu.")
    assert len(made) == 1, "bấm phát dùng đúng engine đã nạp sẵn, không nạp lại"


def test_preload_is_one_use_and_the_idle_release_still_applies(tmp_path: Path) -> None:
    service, made, clock, _gate = _service(tmp_path)
    provider = service.providers["supertonic"]
    service.preload("supertonic:F1")
    assert _until(lambda: provider._engine is not None and not service._preloading)
    clock.now += readaloud_service.IDLE_SECONDS - 1
    assert service.release_idle() == [], "nạp sẵn tính là một lần dùng: chưa đủ 3 phút thì giữ"
    clock.now += 2
    assert service.release_idle() == ["supertonic"] and provider._engine is None, "3 phút không ai dùng: nhả như thường"
    assert len(made) == 1


def test_preload_while_the_engine_is_loading_does_not_load_twice(tmp_path: Path) -> None:
    service, made, _clock, gate = _service(tmp_path)
    gate.clear()
    assert service.preload("supertonic:F1") is True
    assert service.preload("supertonic:F1") is False, "đang nạp: bỏ trùng"
    gate.set()
    assert _until(lambda: not service._preloading)
    assert len(made) == 1


def test_a_machine_without_spare_does_not_preload(tmp_path: Path) -> None:
    service, made, _clock, _gate = _service(tmp_path, spare=lambda: False)
    assert service.preload("supertonic:F1") is False
    time.sleep(0.05)
    assert made == [] and service.providers["supertonic"]._engine is None


def test_voices_without_an_engine_or_not_installed_are_skipped(tmp_path: Path) -> None:
    service, made, _clock, _gate = _service(tmp_path)
    assert service.preload("edge:vi-VN-HoaiMyNeural") is False, "giọng trực tuyến: không có gì để nạp"
    assert service.preload("supertonic:NoSuchVoice") is False
    assert service.preload("") is False
    assert made == []


def test_spare_signal_declines_on_a_low_battery_or_low_memory(monkeypatch) -> None:
    class Battery:
        def __init__(self, percent: float) -> None:
            self.percent = percent

    class Memory:
        def __init__(self, available: int) -> None:
            self.available = available

    def spare(percent: float | None, plugged_in: bool, available: int) -> bool:
        monkeypatch.setattr(power_source.psutil, "sensors_battery", lambda: None if percent is None else Battery(percent))
        monkeypatch.setattr(power_source, "on_battery", lambda: not plugged_in)
        monkeypatch.setattr(power_source.psutil, "virtual_memory", lambda: Memory(available))
        return power_source.spare_for_preload()

    gib = 1 << 30
    assert spare(15, False, 4 * gib) is False, "pin 15 % không sạc: không nạp"
    assert spare(15, True, 4 * gib) is True, "pin yếu mà đang sạc: nạp"
    assert spare(80, False, 4 * gib) is True
    assert spare(None, True, 4 * gib) is True, "máy bàn"
    assert spare(80, True, gib // 2) is False, "còn trống dưới 1 GiB RAM: không nạp"


def test_the_endpoint_answers_at_once_and_hands_the_voice_to_preload(studio, monkeypatch) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    asked: list[str] = []
    monkeypatch.setattr(app.readaloud, "preload", lambda voice: asked.append(voice) or True)
    status, answer = _call(server, "POST", "/api/readaloud/warm?voice=supertonic%3AF1")
    assert status == 200 and answer == {"started": True} and asked == ["supertonic:F1"]
    status, answer = _call(server, "POST", "/api/readaloud/warm")
    assert status == 200 and asked[-1] == "", "thiếu giọng: preload từ chối (False)"
