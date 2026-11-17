"""Accepted signal warnings survive reopening; all audio here is synthesized."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from abook.audio_io import TTS_SIGNAL_EDGE_KEPT, inspect_wav
from abook.database import ProjectDB
from abook.io_utils import sha256_file
from abook.recovery import recover_project
from tests.audio_fixtures import quiet_edges
from tests.test_recovery import setup_db
from tests.test_rejected_take import _edge_pipeline, _no_sleep  # noqa: F401 - autouse fixture


def accepted_edge(tmp_path, *, reason_only=False, side="onset"):
    pipeline, chapter, row = _edge_pipeline(tmp_path, ["edge"] * 4)
    pipeline._process_single_segment(row, chapter)
    pipeline.db.mark_asr_result(row["id"], passed=True, transcript="x", similarity=1., wer=0.)
    pipeline.db.mark_verified(row["id"])
    kept = dict(pipeline.db.get_segment(row["id"]))
    if reason_only:
        signal = json.loads(kept["signal_json"])
        for key in ("signal_edge_kept", "rejection_code", "rejection_class", "signal_edge_acceptance"):
            signal.pop(key, None)
        if side == "offset":
            audio, rate = sf.read(kept["wav_path"], dtype="float32")
            sf.write(kept["wav_path"], audio[::-1], rate, subtype="PCM_16")
            kept["wav_sha256"] = sha256_file(Path(kept["wav_path"]))
            signal["rejection_reason"] = signal["rejection_reason"].replace("ONSET", "OFFSET")
        with pipeline.db.transaction() as conn:
            conn.execute("UPDATE segments SET status='verified',warning_code=NULL,signal_json=?,wav_sha256=? WHERE id=?",
                         (json.dumps(signal), kept["wav_sha256"], row["id"]))
    return pipeline, row, dict(pipeline.db.get_segment(row["id"]))


@pytest.mark.parametrize("reason_only,side", [(False, "onset"), (True, "onset"), (True, "offset")])
def test_accepted_edge_survives_two_reopens(tmp_path, reason_only, side):
    pipeline, row, kept = accepted_edge(tmp_path, reason_only=reason_only, side=side)
    assert not inspect_wav(Path(kept["wav_path"]), row["text"], pipeline.settings)[0]
    for _ in range(2):
        db = ProjectDB(pipeline.db.path)
        report = recover_project(pipeline.paths, db, pipeline.settings)
        assert report.reset_missing_or_corrupt == 0
        after = dict(db.get_segment(row["id"]))
        assert after["wav_sha256"] == kept["wav_sha256"]
        assert after["status"] != "pending"
        signal = json.loads(after["signal_json"])
        receipt = signal["signal_edge_acceptance"]
        assert receipt["wav_sha256"] == kept["wav_sha256"]
        assert receipt["policy_hash"] == pipeline.quality_policy_hash
        assert receipt["reason"].startswith("TTS_ACTIVE_" + side.upper())
        assert TTS_SIGNAL_EDGE_KEPT in after["warning_code"]
        assert pipeline._inspect_existing_segment(after)[0]
        from tests.test_word_break_gate import resume_through_chapter_loop

        calls = list(pipeline.tts.salts)
        resume_through_chapter_loop(pipeline, pipeline.db.list_chapters()[0])
        assert pipeline.tts.salts == calls


def test_recovery_checks_materialized_text_not_stretched_source(tmp_path):
    paths, settings, db, row = setup_db(tmp_path)
    text, spoken = "A" * 60, "A a."
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET text=? WHERE id=?", (text, row["id"]))
    wav = paths.chunks / "vowel.wav"
    wav.parent.mkdir(parents=True, exist_ok=True)
    sf.write(wav, quiet_edges(np.sin(np.linspace(0, 100, 48_000)) * .1), 48_000, subtype="PCM_16")
    db.mark_signal_passed(row["id"], wav_path=wav, wav_sha256=sha256_file(wav), duration=1.,
                          signal={"duration": 1., "spoken_text_sha256": hashlib.sha256(spoken.encode()).hexdigest()})
    for _ in range(2):
        report = recover_project(paths, ProjectDB(paths.db), settings, spoken_text_for_segment=lambda row: spoken)
        assert report.reset_missing_or_corrupt == 0
        assert db.get_segment(row["id"])["wav_sha256"] == sha256_file(wav)


def test_materialized_text_must_match_recorded_hash(tmp_path):
    from tests.test_recovery_signal_cache import recorded_project

    paths, settings, db, row, wav, _ = recorded_project(tmp_path)
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET signal_json=? WHERE id=?",
                     (json.dumps({"spoken_text_sha256": "different"}), row["id"]))
    report = recover_project(paths, db, settings, spoken_text_for_segment=lambda row: row["text"])
    assert report.reset_missing_or_corrupt == 0
    assert report.reset_spoken_text_drift == 1
    assert wav.is_file()


def test_wrong_checksum_resets_even_when_speech_cannot_be_derived(tmp_path):
    from tests.test_recovery_signal_cache import recorded_project

    paths, settings, db, row, wav, _ = recorded_project(tmp_path)
    data = bytearray(wav.read_bytes())
    data[4000] ^= 64
    wav.write_bytes(data)

    def unavailable(_row):
        raise ValueError("speech cannot be reconstructed")

    report = recover_project(paths, db, settings, spoken_text_for_segment=unavailable)
    assert report.reset_missing_or_corrupt == 1
    assert db.get_segment(row["id"])["wav_path"] is None


def test_passing_audio_stays_byte_identical_without_acceptance(tmp_path):
    from tests.test_recovery_signal_cache import recorded_project

    paths, settings, db, row, wav, _ = recorded_project(tmp_path)
    original = wav.read_bytes()
    for _ in range(2):
        assert recover_project(paths, ProjectDB(paths.db), settings).reset_missing_or_corrupt == 0
        assert wav.read_bytes() == original
        assert "signal_edge_acceptance" not in json.loads(db.get_segment(row["id"])["signal_json"])


@pytest.mark.parametrize("after_commit", [False, True])
def test_interrupted_acceptance_reopens_without_recutting(tmp_path, monkeypatch, after_commit):
    pipeline, row, kept = accepted_edge(tmp_path, reason_only=True)
    original = pipeline.db.remember_signal_edge_acceptance

    def interrupted(*args, **kwargs):
        if after_commit:
            original(*args, **kwargs)
        raise RuntimeError("simulated interruption")

    monkeypatch.setattr(pipeline.db, "remember_signal_edge_acceptance", interrupted)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        recover_project(pipeline.paths, pipeline.db, pipeline.settings)
    for _ in range(2):
        db = ProjectDB(pipeline.db.path)
        assert recover_project(pipeline.paths, db, pipeline.settings).reset_missing_or_corrupt == 0
        assert db.get_segment(row["id"])["wav_sha256"] == kept["wav_sha256"]


@pytest.mark.parametrize("damage", ["missing", "truncated", "hash", "hash_unchecked", "clipping", "policy", "reason", "pending", "receipt"])
def test_edge_acceptance_never_hides_other_failures(tmp_path, damage):
    pipeline, row, kept = accepted_edge(tmp_path, reason_only=True)
    wav = Path(kept["wav_path"])
    if damage == "missing":
        wav.unlink()
    elif damage == "truncated":
        wav.write_bytes(wav.read_bytes()[:200])
    elif damage in {"hash", "hash_unchecked"}:
        data = bytearray(wav.read_bytes()); data[4000] ^= 64; wav.write_bytes(data)
        if damage == "hash_unchecked":
            pipeline.settings["safety"]["verify_checksums"] = False
    else:
        signal = json.loads(kept["signal_json"])
        if damage == "clipping":
            audio, rate = sf.read(wav, dtype="float32"); audio[1000:4000] = 1.
            sf.write(wav, audio, rate, subtype="PCM_16")
            with pipeline.db.transaction() as conn:
                conn.execute("UPDATE segments SET wav_sha256=? WHERE id=?", (sha256_file(wav), row["id"]))
        elif damage == "policy":
            signal["generation_policy_hash"] = "different-policy"
        elif damage == "reason":
            signal["rejection_reason"] = "speech rate far outside safety range"
        elif damage == "pending":
            signal["quality_pending"] = True
        elif damage == "receipt":
            signal["signal_edge_acceptance"] = {"wav_sha256": "different"}
        with pipeline.db.transaction() as conn:
            conn.execute("UPDATE segments SET signal_json=? WHERE id=?", (json.dumps(signal), row["id"]))
    report = recover_project(pipeline.paths, ProjectDB(pipeline.db.path), pipeline.settings)
    assert report.reset_missing_or_corrupt == 1
    assert pipeline.db.get_segment(row["id"])["wav_path"] is None
