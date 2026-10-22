"""A synthesis worker that dies outright must cost speed, never the run.

mp.Pool replaces a dead child but the task it held is gone, so imap waits for a result that
cannot come. The pool has to notice, give up on itself in bounded time and raise, because the
caller's existing handling of an exception is "redo these segments one by one, same seeds".
"""

from __future__ import annotations

import multiprocessing as mp
import os
import threading
import time
from pathlib import Path

import pytest

from abook.tts_pool import SynthesisPool


class FakeCoordinator:
    def synthesize_atomic(self, row, output, *args, **kwargs):
        if row["stable_id"] == "child-dies":
            os._exit(71)  # native runtime kill: no exception, no result
        if row["stable_id"] == "child-hangs":
            time.sleep(600)
        return "checksum", {}, 1


def fake_pool_init():
    from abook import tts_pool

    tts_pool._COORDINATOR[:] = [FakeCoordinator()]


def _pool_with_fake_children(workers: int, **kwargs) -> SynthesisPool:
    pool = SynthesisPool({}, Path("unused.sqlite"), workers=workers, **kwargs)
    pool._pool = mp.get_context("spawn").Pool(workers, initializer=fake_pool_init)
    return pool


def _run_in_thread(pool: SynthesisPool, jobs: list[dict]) -> tuple[threading.Thread, list]:
    result: list = []

    def run() -> None:
        try:
            result.append(pool.synthesize_many(jobs))
        except Exception as exc:  # noqa: BLE001
            result.append(exc)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, result


def test_a_worker_that_dies_makes_the_batch_raise_instead_of_waiting_forever() -> None:
    pool = _pool_with_fake_children(1, poll_seconds=0.2)
    raw = pool._pool
    try:
        thread, result = _run_in_thread(pool, [{"row": {"stable_id": "child-dies"}, "output": "unused.wav"}])
        thread.join(60)
        assert not thread.is_alive(), "synthesize_many is still waiting for a dead worker"
        assert isinstance(result[0], RuntimeError)
        assert "0/1" in str(result[0])
        assert pool._pool is None  # the broken pool is dropped, not reused
    finally:
        raw.terminate()
        raw.join()


def test_a_hung_worker_is_given_up_on_after_the_stall_limit() -> None:
    pool = _pool_with_fake_children(1, poll_seconds=0.2, stall_seconds=3)
    raw = pool._pool
    try:
        thread, result = _run_in_thread(pool, [{"row": {"stable_id": "child-hangs"}, "output": "unused.wav"}])
        thread.join(60)
        assert not thread.is_alive()
        assert isinstance(result[0], RuntimeError)
        assert "giây" in str(result[0])
    finally:
        raw.terminate()
        raw.join()


def test_a_healthy_batch_still_returns_everything_in_order() -> None:
    pool = _pool_with_fake_children(2, poll_seconds=0.2)
    raw = pool._pool
    try:
        jobs = [{"row": {"stable_id": name}, "output": "unused.wav"} for name in ("c", "a", "b")]
        thread, result = _run_in_thread(pool, jobs)
        thread.join(60)
        assert not thread.is_alive()
        assert [item["stable_id"] for item in result[0]] == ["c", "a", "b"]
    finally:
        raw.terminate()
        raw.join()


def test_close_does_not_hang_on_a_pool_holding_a_lost_task() -> None:
    pool = _pool_with_fake_children(1, poll_seconds=0.2)
    pool._pool.imap(__import__("abook.tts_pool", fromlist=["x"])._worker_job, [{"row": {"stable_id": "child-dies"}, "output": "x"}])
    time.sleep(3)
    import abook.tts_pool as module

    original = module.TTS_POOL_JOIN_SECONDS
    module.TTS_POOL_JOIN_SECONDS = 2.0
    try:
        started = time.monotonic()
        pool.close()
        assert time.monotonic() - started < 30
    finally:
        module.TTS_POOL_JOIN_SECONDS = original
