"""Soát a79 lỗi 7 và 9: "Làm trước" không kẹt khi đọc lỗi lạ / khi huỷ, và bộ đệm dọn file ghi dở cũ."""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from abook.readaloud import cache as clip_cache
from abook.readaloud.model import VoiceError
from abook.readaloud.prepare import Prepare


def _prepare(clip) -> Prepare:
    return Prepare(clip, lambda: 0, 10**9)


def test_an_unexpected_error_ends_the_job_instead_of_leaving_it_running() -> None:
    def clip(voice, text, origin, readings, book):
        raise OSError("Ổ đĩa đã đầy")

    prepare = _prepare(clip)
    prepare.start("fake:ngoc", ["Một hai ba.", "Bốn năm sáu."], "Chương 1")
    prepare.join(10)
    status = prepare.status()
    assert status["state"] == "error" and "đầy" in status["error"]
    assert status["done"] == 0, "dừng ngay ở đoạn hỏng, không bỏ qua rồi làm tiếp"


def test_an_error_without_a_message_still_says_what_it_was() -> None:
    def clip(voice, text, origin, readings, book):
        raise RuntimeError()

    prepare = _prepare(clip)
    prepare.start("fake:ngoc", ["Một hai ba."])
    prepare.join(10)
    assert prepare.status()["error"] == "RuntimeError"


def test_known_voice_errors_keep_their_old_behaviour() -> None:
    calls: list[str] = []

    def clip(voice, text, origin, readings, book):
        calls.append(text)
        if text == "rỗng":
            raise VoiceError("không có chữ", reason="empty")
        if text == "hỏng":
            raise ValueError("chữ lạ")

    prepare = _prepare(clip)
    prepare.start("fake:ngoc", ["rỗng", "hỏng", "Xong."])
    prepare.join(10)
    status = prepare.status()
    assert status["state"] == "done" and status["done"] == 3 and status["failed"] == 2 and calls == ["rỗng", "hỏng", "Xong."]


def test_replacing_a_job_does_not_wait_for_the_old_clip_nor_get_its_late_results() -> None:
    release = threading.Event()
    entered = threading.Event()

    def clip(voice, text, origin, readings, book):
        if text == "chậm":
            entered.set()
            release.wait(20)  # một đoạn đọc rất lâu
            raise OSError("trễ")

    prepare = _prepare(clip)
    prepare.start("fake:ngoc", ["chậm", "sau"], "Cũ")
    assert entered.wait(5)
    began = time.perf_counter()
    prepare.start("fake:ngoc", ["mới"], "Mới")
    assert time.perf_counter() - began < 10, "việc mới không phải đợi 30 giây cho đoạn cũ"
    release.set()
    prepare.join(10)
    time.sleep(0.2)
    status = prepare.status()
    assert status["label"] == "Mới" and status["error"] == "", "lỗi muộn của việc cũ không đè lên việc mới"


def test_cancel_returns_quickly_even_when_a_clip_is_stuck() -> None:
    release = threading.Event()
    entered = threading.Event()

    def clip(voice, text, origin, readings, book):
        entered.set()
        release.wait(20)

    prepare = _prepare(clip)
    prepare.start("fake:ngoc", ["kẹt"])
    assert entered.wait(5)
    began = time.perf_counter()
    prepare.cancel()
    assert time.perf_counter() - began < 10
    assert prepare.status()["state"] == "cancelled"
    release.set()
    prepare.join(10)
    assert prepare.status()["state"] == "cancelled", "luồng cũ chạy xong cũng không đổi trạng thái đã huỷ"


def test_stale_part_files_are_swept_but_a_fresh_one_is_kept(tmp_path: Path) -> None:
    folder = tmp_path / "cache"
    folder.mkdir()
    old, fresh = folder / ("a" * 64 + ".mp3.part"), folder / ("b" * 64 + ".mp3.part")
    old.write_bytes(b"x")
    fresh.write_bytes(b"y")
    long_ago = time.time() - clip_cache.STALE_PART_SECONDS - 60
    os.utime(old, (long_ago, long_ago))
    clip_cache.ClipCache(folder, limit=10_000)
    assert not old.exists(), "file ghi dở của lần chạy trước đã chết"
    assert fresh.exists(), "file mới có thể là lần ghi đang chạy"


def test_trim_over_the_limit_also_sweeps_stale_part_files(tmp_path: Path) -> None:
    store = clip_cache.ClipCache(tmp_path / "c", limit=100)
    store.folder.mkdir(parents=True, exist_ok=True)
    stale = store.folder / ("c" * 64 + ".wav.part")
    stale.write_bytes(b"z")
    long_ago = time.time() - clip_cache.STALE_PART_SECONDS - 60
    os.utime(stale, (long_ago, long_ago))
    store.put("d" * 64, b"x" * 300, "mp3", 1000, [])  # vượt trần 100 byte
    assert not stale.exists()
