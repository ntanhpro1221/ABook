"""Reopening a recorded book measures only the WAVs it has never measured."""
from __future__ import annotations

import numpy as np
import soundfile as sf

from abook import audio_io
from abook.audio_io import inspect_wav
from abook.io_utils import sha256_file
from abook.models import ProjectPaths
from abook.pipeline import QUALITY_POLICY_VERSION, BookPipeline
from tests.audio_fixtures import quiet_edges
from tests.test_recovery import setup_db

RATE = 48_000


def _tone(index: int) -> np.ndarray:
    # Distinct content per take, so every WAV has its own hash.
    return quiet_edges(np.sin(np.linspace(0, 300 + index, RATE, dtype=np.float32)) * 0.1)


def _clicky() -> np.ndarray:
    audio = _tone(0).copy()
    audio[int(0.03 * RATE):int(0.03 * RATE) + 40] += 0.5
    return np.clip(audio, -1.0, 1.0)


def _project(tmp_path, count: int, take=None):
    paths, settings, db, _row = setup_db(tmp_path)
    chapter_id = int(db.list_chapters()[0]["id"])
    with db.connect() as conn:  # setup_db seeds one segment; this fixture wants N
        conn.execute("DELETE FROM segments")
    db.replace_chapter_segments(chapter_id, [
        {"stable_id": f"c1s{i}", "seq": i, "text": "Xin chào thế giới",
         "text_sha256": f"t{i}", "kind_hint": "narration"}
        for i in range(count)
    ])
    wavs = []
    for row in db.list_segments(chapter_id=chapter_id):
        wav = paths.chunks / f"take{int(row['seq'])}.wav"
        wav.parent.mkdir(parents=True, exist_ok=True)
        sf.write(wav, (take or _tone)(int(row["seq"])), RATE, subtype="PCM_16")
        db.mark_signal_passed(int(row["id"]), wav_path=wav, wav_sha256=sha256_file(wav),
                              duration=1.0, signal={"duration": 1.0})
        wavs.append(wav)
    return paths, settings, db, wavs


def _pipeline(paths: ProjectPaths, db, settings) -> BookPipeline:
    pipeline = BookPipeline(
        paths=paths, db=db, settings=settings,
        pause_requested=lambda: False, stop_requested=lambda: False,
        emit=lambda _kind, _payload: None,
    )
    # A project that already has segments was opened before: it carries its quality policy.
    db.set_current_quality_policy(
        policy_hash=pipeline.quality_policy_hash,
        policy_version=QUALITY_POLICY_VERSION,
        policy=pipeline.quality_policy,
    )
    return pipeline


def _count(monkeypatch) -> list[int]:
    calls: list[int] = []
    original = audio_io.signal_metrics

    def measured(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(audio_io, "signal_metrics", measured)
    return calls


def _inspect_all(pipeline: BookPipeline, db) -> list[tuple[bool, dict]]:
    return [pipeline._inspect_existing_segment(row) for row in db.list_segments()]


def test_second_open_measures_no_wav(tmp_path, monkeypatch):
    paths, settings, db, _ = _project(tmp_path, 6)
    calls = _count(monkeypatch)
    first = _pipeline(paths, db, settings)
    first.prepare_recovery()
    _inspect_all(first, db)
    assert len(calls) == 6
    calls.clear()
    second = _pipeline(paths, db, settings)
    second.prepare_recovery()
    _inspect_all(second, db)
    assert calls == []


def test_changed_wav_is_the_only_one_measured_again(tmp_path, monkeypatch):
    paths, settings, db, wavs = _project(tmp_path, 5)
    first = _pipeline(paths, db, settings)
    first.prepare_recovery()
    calls = _count(monkeypatch)
    sf.write(wavs[2], _tone(99) * 0.7, RATE, subtype="PCM_16")
    with db.connect() as conn:
        conn.execute("UPDATE segments SET wav_sha256=? WHERE wav_path=?",
                     (sha256_file(wavs[2]), str(wavs[2])))
    second = _pipeline(paths, db, settings)
    second.prepare_recovery()
    _inspect_all(second, db)
    assert len(calls) == 1


def test_new_measurement_version_measures_everything_again(tmp_path, monkeypatch):
    paths, settings, db, _ = _project(tmp_path, 4)
    _pipeline(paths, db, settings).prepare_recovery()
    calls = _count(monkeypatch)
    monkeypatch.setattr(audio_io, "SIGNAL_METRICS_CACHE_VERSION", audio_io.SIGNAL_METRICS_CACHE_VERSION + 1)
    second = _pipeline(paths, db, settings)
    second.prepare_recovery()
    _inspect_all(second, db)
    assert len(calls) == 4


def test_verdicts_match_with_and_without_the_cache(tmp_path):
    paths, settings, db, wavs = _project(tmp_path, 4, take=lambda i: _clicky() if i % 2 else _tone(i))
    plain = [inspect_wav(wav, "Xin chào thế giới", settings) for wav in wavs]
    pipeline = _pipeline(paths, db, settings)
    cold = _inspect_all(pipeline, db)
    warm = _inspect_all(_pipeline(paths, db, settings), db)
    assert all(ok for ok, _ in cold)
    assert [(ok, metrics) for ok, metrics, _ in plain] == cold == warm
    ratios = [metrics["onset_click_ratio"] for _, metrics in cold]
    assert max(ratios) > min(ratios)  # the set really holds a clicky and a clean take
