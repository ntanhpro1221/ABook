from __future__ import annotations

import os

import numpy as np
import pytest
import soundfile as sf

from abook import audio_io
from abook.database import ProjectDB
from abook.io_utils import sha256_file
from abook.recovery import recover_project
from tests.audio_fixtures import quiet_edges
from tests.test_recovery import setup_db


def recorded_project(tmp_path):
    paths, settings, db, row = setup_db(tmp_path)
    wav = paths.chunks / "take.wav"
    wav.parent.mkdir(parents=True, exist_ok=True)
    audio = quiet_edges(np.sin(np.linspace(0, 300, 48_000, dtype=np.float32)) * 0.1)
    sf.write(wav, audio, 48_000, subtype="PCM_16")
    db.mark_signal_passed(
        int(row["id"]), wav_path=wav, wav_sha256=sha256_file(wav),
        duration=1.0, signal={"duration": 1.0},
    )
    return paths, settings, db, row, wav, audio


def count_measurements(monkeypatch):
    calls = []
    original = audio_io.signal_metrics

    def measured(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(audio_io, "signal_metrics", measured)
    return calls


def test_signal_cache_survives_reopen_and_preserves_all_inspection_metrics(tmp_path, monkeypatch):
    paths, settings, db, row, wav, _ = recorded_project(tmp_path)
    expected = audio_io.inspect_wav(wav, row["text"], settings, segment=row)
    calls = count_measurements(monkeypatch)
    first = recover_project(paths, db, settings)
    reopened = ProjectDB(paths.db)
    second = recover_project(paths, reopened, settings)
    assert first == second
    assert second.recovered_verified == 1
    assert len(calls) == 1
    cached = reopened.load_wav_signal_metrics(audio_io.signal_metrics_cache_version())
    measurements = cached[sha256_file(wav)]
    assert "loudness_lufs" not in measurements
    assert "pace_outlier" not in measurements
    assert audio_io.inspect_wav(
        wav, row["text"], settings, segment=row, signal_measurements=measurements,
    ) == expected
    assert len(calls) == 1


@pytest.mark.parametrize("update_checkpoint", [True, False])
def test_changed_content_misses_even_with_same_size_and_mtime(tmp_path, monkeypatch, update_checkpoint):
    paths, settings, db, row, wav, audio = recorded_project(tmp_path)
    calls = count_measurements(monkeypatch)
    recover_project(paths, db, settings)
    before = wav.stat()
    old_sha = sha256_file(wav)
    sf.write(wav, audio * 0.8, 48_000, subtype="PCM_16")
    os.utime(wav, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert wav.stat().st_size == before.st_size
    assert wav.stat().st_mtime_ns == before.st_mtime_ns
    assert sha256_file(wav) != old_sha
    if update_checkpoint:
        with db.connect() as conn:
            conn.execute("UPDATE segments SET wav_sha256=? WHERE id=?", (sha256_file(wav), row["id"]))
    report = recover_project(paths, db, settings)
    assert len(calls) == 2
    assert report.recovered_verified == int(update_checkpoint)
    assert report.reset_missing_or_corrupt == int(not update_checkpoint)


@pytest.mark.parametrize("parameter", ["SIGNAL_METRICS_CACHE_VERSION", "SEGMENT_EDGE_WINDOW_SECONDS", "SEGMENT_ONSET_CLICK_SHORT_SECONDS", "implementation"])
def test_measurement_version_and_parameters_invalidate_cache(tmp_path, monkeypatch, parameter):
    paths, settings, db, _, wav, _ = recorded_project(tmp_path)
    calls = count_measurements(monkeypatch)
    old_version = audio_io.signal_metrics_cache_version()
    recover_project(paths, db, settings)
    if parameter == "implementation":
        monkeypatch.setattr(audio_io, "sha256_file", lambda _: "changed-implementation")
    else:
        monkeypatch.setattr(audio_io, parameter, getattr(audio_io, parameter) * 2)
    new_version = audio_io.signal_metrics_cache_version()
    assert old_version != new_version
    recover_project(paths, db, settings)
    recover_project(paths, db, settings)
    assert len(calls) == 2
    assert sha256_file(wav) in db.load_wav_signal_metrics(old_version)
    assert sha256_file(wav) in db.load_wav_signal_metrics(new_version)


@pytest.mark.parametrize("change", ["threshold", "text", "sample_rate"])
def test_cached_measurements_do_not_cache_validation_decisions(tmp_path, monkeypatch, change):
    paths, settings, db, row, _, _ = recorded_project(tmp_path)
    calls = count_measurements(monkeypatch)
    recover_project(paths, db, settings)
    if change == "threshold":
        settings["tts"]["min_rms"] = 0.5
    elif change == "sample_rate":
        settings["tts"]["sample_rate"] = 24_000
    else:
        with db.connect() as conn:
            conn.execute("UPDATE segments SET text=? WHERE id=?", ("Một câu rất dài. " * 100, row["id"]))
    report = recover_project(paths, db, settings)
    assert report.reset_missing_or_corrupt == 1
    assert len(calls) == 1


def test_interrupted_scan_reopens_committed_measurement(tmp_path, monkeypatch):
    paths, settings, db, _, _, _ = recorded_project(tmp_path)
    calls = count_measurements(monkeypatch)
    store = db.store_wav_signal_metrics

    def interrupt_after_commit(*args):
        store(*args)
        raise RuntimeError("simulated interruption after cache commit")

    monkeypatch.setattr(db, "store_wav_signal_metrics", interrupt_after_commit)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        recover_project(paths, db, settings)
    assert recover_project(paths, ProjectDB(paths.db), settings).recovered_verified == 1
    assert len(calls) == 1


def test_same_content_at_another_path_reuses_measurement(tmp_path, monkeypatch):
    paths, settings, db, row, wav, _ = recorded_project(tmp_path)
    calls = count_measurements(monkeypatch)
    recover_project(paths, db, settings)
    other = wav.with_name("same-content.wav")
    other.write_bytes(wav.read_bytes())
    with db.connect() as conn:
        conn.execute("UPDATE segments SET wav_path=? WHERE id=?", (str(other), row["id"]))
    assert recover_project(paths, db, settings).recovered_verified == 1
    assert len(calls) == 1


def test_disabled_checksum_gate_still_keys_measurements_by_actual_content(tmp_path, monkeypatch):
    paths, settings, db, _, wav, audio = recorded_project(tmp_path)
    settings["safety"]["verify_checksums"] = False
    calls = count_measurements(monkeypatch)
    recover_project(paths, db, settings)
    sf.write(wav, audio * 0.8, 48_000, subtype="PCM_16")
    assert recover_project(paths, db, settings).recovered_verified == 1
    assert len(calls) == 2


def test_cached_signal_does_not_bypass_spoken_text_drift(tmp_path, monkeypatch):
    paths, settings, db, _, _, _ = recorded_project(tmp_path)
    calls = count_measurements(monkeypatch)
    recover_project(paths, db, settings)
    report = recover_project(paths, db, settings, spoken_text_drifted=lambda row: True)
    assert report.reset_spoken_text_drift == 1
    assert len(calls) == 1


def test_cached_signal_still_requires_current_audio_qa(tmp_path, monkeypatch):
    paths, settings, db, row, _, _ = recorded_project(tmp_path)
    calls = count_measurements(monkeypatch)
    recover_project(paths, db, settings)
    db.mark_verified(int(row["id"]))
    report = recover_project(paths, db, settings)
    assert report.requeued_asr == 1
    assert len(calls) == 1
