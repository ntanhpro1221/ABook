"""rejtake: a take the signal gate refused never becomes `verified`.

Everything here is synthetic - sine tones with a loud first 10 ms stand in for the onset pop
of lines 508/751 of a real book; no audio or text from any book is used.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from abook import pipeline as pipeline_module
from abook.audio_io import (
    SEGMENT_EDGE_MAX_RMS,
    TTS_SIGNAL_EDGE_KEPT,
    AudioQualityError,
    SignalRejectedTake,
    atomic_write_wav,
    rejected_take_path,
    segment_gain_db,
)
from abook.database import ProjectDB
from abook.io_utils import sha256_file
from abook.pipeline import BookPipeline, RetainedTakeRejected
from tests.audio_fixtures import quiet_edges
from tests.test_pipeline_mock import _short_tts_pipeline, _voiced

LONG_TEXT = "Người ấy đặt chiếc túi xuống ghế gỗ rồi chậm rãi bước ra phía cửa sổ."


def _tone(seconds: float, rate: int, *, edge: bool = False, amplitude: float = .12, phase: float = 0.) -> np.ndarray:
    audio = quiet_edges(np.sin(phase + np.linspace(0, 50 * seconds, round(seconds * rate), dtype=np.float32))
                        * amplitude, rate)
    if edge:
        audio[: rate // 100] = .25  # a pop in the first 10 ms: TTS_ACTIVE_ONSET after any locked gain
    return audio


class EdgeScriptTTS:
    """A coordinator that writes through the real writer; each outcome is 'edge', 'clean' or an exception.

    Every seed gets its own audio (the tone's phase), as a real engine's would: two clean takes
    of different seeds never share a checksum, so a kept earlier take is a different file from
    the one just checked and the high-quality gate in `_accept_retained_take` really runs.
    """

    def __init__(self, pipeline: BookPipeline, outcomes: list) -> None:
        self.settings, self.db = pipeline.settings, pipeline.db
        self.outcomes = list(outcomes)
        self.salts: list[str] = []

    def generation_seed(self, _row, seed_salt=""):
        return 1000 + len(str(seed_salt)) + sum(map(ord, str(seed_salt)))

    def spoken_text(self, row):
        return str(row["text"])

    def locked_voice_provenance(self, row):
        return {"voice_profile_id": int(row["voice_profile_id"])}

    def unload_all(self):
        pass

    def synthesize_atomic(self, row, output, seed_salt="", *, repair_short_utterance=False, delivery_mode="primary"):
        self.salts.append(seed_salt)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        kind, flags = outcome if isinstance(outcome, tuple) else (outcome, {})
        rate = int(self.settings["tts"]["sample_rate"])
        seed = self.generation_seed(row, seed_salt)
        audio = _tone(1.2, rate, edge=kind == "edge", amplitude=1.4 if kind == "clipped" else .12,
                      phase=(seed % 997) * 0.01)
        if kind == "clipped":
            audio = np.clip(audio, -1.0, 1.0)
        provenance = {"spoken_text_sha256": hashlib.sha256(str(row["text"]).encode()).hexdigest(),
                      "voice_profile_id": int(row["voice_profile_id"]), "tts_delivery_mode": delivery_mode}
        try:
            checksum, metrics = atomic_write_wav(output, audio, rate, str(row["text"]), self.settings,
                                                 segment=_voiced(self.db, row), keep_rejected=True)
        except SignalRejectedTake as exc:
            exc.metrics.update(provenance, **flags)
            exc.seed = seed
            raise
        metrics.setdefault("chars_per_second", len(str(row["text"])) / metrics["duration"])
        metrics.update(provenance, **flags)
        return checksum, metrics, seed


def _edge_pipeline(tmp_path, outcomes, *, profile="standard", text="Một câu ngắn."):
    pipeline, chapter, row = _short_tts_pipeline(tmp_path, source_text=text)
    pipeline.settings["quality_profile"] = profile
    pipeline.tts = EdgeScriptTTS(pipeline, outcomes)
    return pipeline, chapter, row


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(pipeline_module.time, "sleep", lambda _: None)


def _signal(db, row):
    return json.loads(db.get_segment(row["id"])["signal_json"] or "{}")


# 1 ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("edge", ["onset", "offset"])
def test_signal_rejected_take_is_canonical_pcm16_and_leveled(tmp_path, edge):
    pipeline, _chapter, row = _short_tts_pipeline(tmp_path, source_text=LONG_TEXT)
    settings, rate = pipeline.settings, int(pipeline.settings["tts"]["sample_rate"])
    voiced = _voiced(pipeline.db, row)
    raw = _tone(4.0, rate, edge=True)
    if edge == "offset":
        raw = raw[::-1].copy()
    output = tmp_path / "take.wav"
    with pytest.raises(SignalRejectedTake) as caught:
        atomic_write_wav(output, raw, rate, LONG_TEXT, settings, segment=voiced, keep_rejected=True)
    exc = caught.value
    assert not output.exists(), "a refused take never lands on the caller's output path"
    assert exc.path == rejected_take_path(output) and exc.path.is_file()
    info = sf.info(exc.path)
    assert (info.format, info.subtype, info.channels, info.samplerate) == ("WAV", "PCM_16", 1, rate)
    assert sha256_file(exc.path) == exc.checksum
    stored, _ = sf.read(exc.path, dtype="float32")
    gain = segment_gain_db(voiced, settings)
    expected_peak = min(float(np.max(np.abs(raw))) * 10 ** (gain / 20), 10 ** (float(settings["audio"].get("segment_peak_dbfs", -2.0)) / 20))
    assert abs(float(np.max(np.abs(stored))) - expected_peak) < 2e-3, "same gain and peak cap as a passing take"
    metrics = exc.metrics
    assert metrics["signal_rejected"] and metrics["rejection_class"] == "edge"
    assert metrics["rejection_code"] == "TTS_ACTIVE_" + edge.upper()
    assert metrics[edge + "_rms"] > SEGMENT_EDGE_MAX_RMS
    assert "chars_per_second" in metrics and "pace_outlier" in metrics and "measured_silence_seconds" in metrics
    assert "level_gain_db" in metrics


def test_pcm_quantization_edge_rejection_is_retained(tmp_path):
    pipeline, _chapter, _row = _short_tts_pipeline(tmp_path)
    rate = int(pipeline.settings["tts"]["sample_rate"])
    raw = _tone(1.2, rate)
    raw[:rate // 100] = -.049999  # below 0.05 before PCM_16 quantization
    with pytest.raises(SignalRejectedTake) as caught:
        atomic_write_wav(tmp_path / "q.wav", raw, rate, "Một câu ngắn.", pipeline.settings, keep_rejected=True)
    assert caught.value.code == "TTS_ACTIVE_ONSET"
    assert caught.value.metrics["onset_rms"] > SEGMENT_EDGE_MAX_RMS


def test_clipped_take_is_kept_as_pcm16_with_safe_peak(tmp_path):
    pipeline, _chapter, row = _short_tts_pipeline(tmp_path, source_text=LONG_TEXT)
    rate = int(pipeline.settings["tts"]["sample_rate"])
    raw = np.clip(_tone(4.0, rate, amplitude=1.4), -1.0, 1.0)
    with pytest.raises(SignalRejectedTake) as caught:
        atomic_write_wav(tmp_path / "c.wav", raw, rate, LONG_TEXT, pipeline.settings,
                         segment=_voiced(pipeline.db, row), keep_rejected=True)
    assert caught.value.rejection_class == "clipped" and caught.value.code == "TTS_CLIPPING"
    assert sf.info(caught.value.path).subtype == "PCM_16"
    assert float(np.max(np.abs(sf.read(caught.value.path, dtype="float32")[0]))) <= 1.0


# 5 ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("case", ["low_rms", "too_short", "too_long", "nan", "inf", "empty", "silence", "pace"])
def test_fatal_signal_rejections_keep_no_take(tmp_path, case):
    pipeline, _chapter, row = _short_tts_pipeline(tmp_path, source_text=LONG_TEXT)
    rate = int(pipeline.settings["tts"]["sample_rate"])
    audio = {
        "low_rms": _tone(4.0, rate, amplitude=1e-4, edge=False),
        "too_short": _tone(.1, rate),
        "too_long": _tone(120.0, rate),
        "nan": np.where(np.arange(4 * rate) == 7, np.nan, _tone(4.0, rate)).astype(np.float32),
        "inf": np.full(4 * rate, np.inf, dtype=np.float32),
        "empty": np.zeros(0, dtype=np.float32),
        "silence": np.zeros(4 * rate, dtype=np.float32),
        "pace": _tone(1.0, rate),  # 70 characters in one second: far outside the safe band
    }[case]
    if case not in ("silence", "low_rms", "inf", "empty"):
        audio[: rate // 100] = np.where(np.isnan(audio[: rate // 100]), np.nan, .25)  # an edge pop too: still fatal
    output = tmp_path / "f.wav"
    with pytest.raises(AudioQualityError) as caught:
        atomic_write_wav(output, audio, rate, LONG_TEXT, pipeline.settings,
                         segment=_voiced(pipeline.db, row), keep_rejected=True)
    assert not isinstance(caught.value, SignalRejectedTake)
    assert not output.exists() and not rejected_take_path(output).exists()
    assert not list(tmp_path.glob("f*.wav"))


# 2 + G: the 508/751 regression ----------------------------------------------------------------
INCONCLUSIVE = {"word_break_gate": {"status": "inconclusive", "reason": "aligner missing"}}


@pytest.mark.parametrize("soft", [
    {"pace_outlier": 1.0},
    {"generation_ceiling_hit": 1.0},
    INCONCLUSIVE,
    {**INCONCLUSIVE, "repeated_utterance_score": None},
    {**INCONCLUSIVE, "repeated_utterance_score": 0.2},
    {"repeated_utterance_score": 0.05},
], ids=["pace", "ceiling", "inconclusive", "inconclusive_repeat_none", "inconclusive_repeat_positive", "repeat_positive"])
def test_clean_take_with_one_soft_flag_replaces_signal_rejected_take(tmp_path, soft):
    """508/751: primary_0 popped at the onset, primary_1 was clean but carried a soft flag
    (inconclusive word-break, no or a positive repeat score) - and the popped take won the tie."""
    pipeline, chapter, row = _edge_pipeline(tmp_path, [("edge", INCONCLUSIVE if "word_break_gate" in soft else {}),
                                                       ("clean", soft)])
    pipeline._process_single_segment(row, chapter)
    current = pipeline.db.get_segment(row["id"])
    signal = json.loads(current["signal_json"])
    assert current["status"] == "signal_passed"
    assert not signal.get("signal_rejected")
    assert ".primary_1." in Path(current["wav_path"]).name
    assert sf.info(current["wav_path"]).subtype == "PCM_16"
    assert TTS_SIGNAL_EDGE_KEPT not in str(current["warning_code"] or "")
    pipeline.db.mark_asr_result(row["id"], passed=True, transcript="x", similarity=1.0, wer=0.0)
    pipeline.db.mark_verified(row["id"])
    assert pipeline.db.get_segment(row["id"])["status"] in {"verified", "warning"}


@pytest.mark.parametrize("old,new", [
    ({}, {"pace_outlier": 1}),
    ({}, INCONCLUSIVE),
    ({"repeated_utterance_score": None}, {"repeated_utterance_score": 0.3}),
    ({}, {"word_break_gate": {"fired": True, "flagged_words": 2, "boundaries": [{"gap_ms": 90, "flagged": True}]}}),
], ids=["pace", "inconclusive", "repeat", "fired"])
def test_every_signal_pass_outranks_every_refused_take(old, new):
    rank = BookPipeline._usable_take_rank
    for rejected_class in ("edge", "clipped", "unknown"):
        refused = {**old, "signal_rejected": True, "rejection_class": rejected_class}
        assert rank(new) < rank(refused)
        assert rank(new, qa_failed=True) < rank(refused)
    assert rank({"signal_rejected": True, "rejection_class": "edge"}) < rank({"signal_rejected": True})


# 3 ------------------------------------------------------------------------------------------
def test_accept_retained_take_refuses_signal_rejected_unless_exhausted(tmp_path):
    pipeline, _chapter, row = _short_tts_pipeline(tmp_path, source_text="Một câu ngắn.")
    rate = int(pipeline.settings["tts"]["sample_rate"])
    with pytest.raises(SignalRejectedTake) as caught:
        atomic_write_wav(tmp_path / "e.wav", _tone(1.2, rate, edge=True), rate, "Một câu ngắn.", pipeline.settings,
                         segment=_voiced(pipeline.db, row), keep_rejected=True)
    exc = caught.value
    pipeline.db.mark_generating(row["id"], 5)
    pipeline._keep_usable_take(row, exc.path, exc.checksum, dict(exc.metrics), 5)
    with pytest.raises(RetainedTakeRejected):
        pipeline._accept_retained_take(row, exc.checksum)
    assert pipeline.db.get_segment(row["id"])["status"] == "generating"
    with pytest.raises(ValueError):
        pipeline.db.mark_signal_passed(row["id"], wav_path=exc.path, wav_sha256=exc.checksum, duration=1.2,
                                       signal=dict(exc.metrics), warning_codes=(TTS_SIGNAL_EDGE_KEPT,))
    pipeline._accept_retained_take(row, None, exhausted=True)
    current = pipeline.db.get_segment(row["id"])
    assert current["status"] == "signal_passed" and TTS_SIGNAL_EDGE_KEPT in current["warning_code"]


def test_accept_checks_the_retained_take_not_the_one_just_measured(tmp_path):
    """The queue kept an earlier take: the high-quality gate must look at it, not at the new one."""
    pipeline, _chapter, row = _short_tts_pipeline(tmp_path, source_text="Một câu ngắn.")
    pipeline.settings["quality_profile"] = "high_quality"
    path = tmp_path / "kept.wav"
    sf.write(path, _tone(1.2, int(pipeline.settings["tts"]["sample_rate"])), int(pipeline.settings["tts"]["sample_rate"]), subtype="PCM_16")
    pipeline.db.mark_generating(row["id"], 3)
    pipeline._keep_usable_take(row, path, sha256_file(path), {"duration": 1.2, "pace_outlier": 1.0}, 3)
    with pytest.raises(AudioQualityError, match="high-quality"):
        pipeline._accept_retained_take(row, "f" * 64)
    assert pipeline.db.get_segment(row["id"])["status"] == "generating"


# 4 ------------------------------------------------------------------------------------------
def test_exhausted_edge_rejection_ends_warning_never_verified(tmp_path):
    pipeline, chapter, row = _edge_pipeline(tmp_path, ["edge"] * 10)
    pipeline.settings["tts"]["max_retries"] = 10
    pipeline._process_single_segment(row, chapter)
    current = pipeline.db.get_segment(row["id"])
    signal = json.loads(current["signal_json"])
    assert current["status"] == "signal_passed"
    assert TTS_SIGNAL_EDGE_KEPT in current["warning_code"]
    assert signal["signal_rejected"] and signal["signal_edge_kept"] and not signal.get("quality_pending")
    assert sf.info(current["wav_path"]).subtype == "PCM_16"
    pipeline.db.mark_asr_result(row["id"], passed=True, transcript="x", similarity=1.0, wer=0.0)
    pipeline.db.mark_verified(row["id"])
    assert pipeline.db.get_segment(row["id"])["status"] == "warning"
    pipeline.db.mark_perceptual_result(row["id"])
    final = pipeline.db.get_segment(row["id"])
    assert final["status"] == "warning" and TTS_SIGNAL_EDGE_KEPT in final["warning_code"]
    assert "SEGMENT_SIGNAL_EDGE_KEPT" in [str(item["code"]) for item in pipeline.db.list_events()]
    assert pipeline.tts.salts == [f"primary_{index}" for index in range(10)]
    # F5: the losing attempts are gone; only the kept take remains among this line's files.
    stem = Path(current["wav_path"]).name.split(".")[0]
    left = sorted(p.name for p in Path(current["wav_path"]).parent.glob(stem + "*.wav"))
    assert left == [Path(current["wav_path"]).name]


def test_exhausted_clipped_take_stays_failed_with_audio(tmp_path):
    pipeline, chapter, row = _edge_pipeline(tmp_path, ["clipped"] * 4)
    pipeline._process_single_segment(row, chapter)
    current = pipeline.db.get_segment(row["id"])
    assert current["status"] == "failed" and pipeline._has_real_audio(current)
    assert set(current["warning_code"].split("|")) >= {"SEGMENT_FAILED", "TTS_SIGNAL_CLIPPED"}
    assert json.loads(current["signal_json"])["rejection_class"] == "clipped"
    assert sf.info(current["wav_path"]).subtype == "PCM_16"


# 6 ------------------------------------------------------------------------------------------
def test_non_signal_errors_are_not_labelled_signal_rejected(tmp_path):
    outcomes = [("clean", {"pace_outlier": 1.0}), RuntimeError("engine hiccup"),
                ("clean", {"pace_outlier": 1.0}), ("clean", {"pace_outlier": 1.0}), ("clean", {"pace_outlier": 1.0})]
    pipeline, chapter, row = _edge_pipeline(tmp_path, outcomes, profile="high_quality")
    pipeline._process_single_segment(row, chapter)
    current = pipeline.db.get_segment(row["id"])
    signal = json.loads(current["signal_json"])
    assert current["status"] == "failed" and pipeline._has_real_audio(current)
    assert not signal.get("signal_rejected") and "rejection_class" not in signal
    assert "TTS_SIGNAL" not in str(current["warning_code"])
    # The engine's error was retried on the same seed (salt) instead of spending attempt 1.
    assert pipeline.tts.salts[1:3] == ["primary_1"] * 2


# 7 + D --------------------------------------------------------------------------------------
def test_resume_does_not_resynthesize_edge_kept_take(tmp_path):
    from abook.recovery import recover_project

    pipeline, chapter, row = _edge_pipeline(tmp_path, ["edge"] * 4)
    pipeline._process_single_segment(row, chapter)
    pipeline.db.mark_asr_result(row["id"], passed=True, transcript="x", similarity=1.0, wer=0.0)
    pipeline.db.mark_verified(row["id"])
    kept = pipeline.db.get_segment(row["id"])
    assert pipeline.db.current_quality_policy()["policy_hash"] == pipeline.quality_policy_hash
    valid, _ = pipeline._inspect_existing_segment(kept)
    assert valid, "same policy: the edge gate is waived for this take"
    report = recover_project(pipeline.paths, ProjectDB(pipeline.db.path), pipeline.settings)
    assert report.reset_missing_or_corrupt == 0
    after = pipeline.db.get_segment(row["id"])
    assert after["wav_sha256"] == kept["wav_sha256"] and after["status"] != "pending"
    from tests.test_word_break_gate import resume_through_chapter_loop

    calls = list(pipeline.tts.salts)
    resume_through_chapter_loop(pipeline, chapter)
    assert pipeline.tts.salts == calls, "the actual chapter resume must not call TTS again"
    pipeline.quality_policy_hash = "another-policy"
    valid, _ = pipeline._inspect_existing_segment(after)
    assert not valid, "another policy re-judges the take with the edge gate"


def test_ledger_replays_a_refused_take_with_its_audio(tmp_path):
    """A crash after a refused attempt: the replay must keep the same refused take, not lose it."""
    pipeline, chapter, row = _edge_pipeline(tmp_path, ["edge", RuntimeError("crash")])
    session = pipeline._begin_take_session(row, {"x": 1})
    output = pipeline._session_attempt_path(row, session, "primary_0", tmp_path / "a.primary_0.wav")
    calls = []

    def synthesize():
        calls.append(1)
        return (output, *pipeline.tts.synthesize_atomic(row, output, seed_salt="primary_0"))

    with pytest.raises(SignalRejectedTake) as first:
        pipeline._session_synthesis(row, session, "primary_0", synthesize)
    with pytest.raises(SignalRejectedTake) as replay:
        pipeline._session_synthesis(row, session, "primary_0", synthesize)
    assert calls == [1]
    assert replay.value.checksum == first.value.checksum and replay.value.path == first.value.path
    assert replay.value.seed == first.value.seed and replay.value.rejection_class == "edge"


# 8 ------------------------------------------------------------------------------------------
def test_edge_kept_warning_does_not_block_chapter(tmp_path):
    pipeline, chapter, row = _edge_pipeline(tmp_path, ["edge"] * 4, profile="high_quality")
    pipeline._process_single_segment(row, chapter)
    pipeline.db.mark_asr_result(row["id"], passed=True, transcript="x", similarity=1.0, wer=0.0)
    pipeline.db.mark_verified(row["id"])
    rows = pipeline.db.list_segments(chapter_id=int(chapter["id"]))
    assert pipeline.db.get_segment(row["id"])["status"] == "warning"
    assert pipeline._high_quality_blocking_segment_warnings(rows) == []


# F2 / F4 ------------------------------------------------------------------------------------
def test_locked_destination_is_retried_not_judged(tmp_path, monkeypatch):
    import os

    from abook import io_utils

    pipeline, _chapter, row = _short_tts_pipeline(tmp_path, source_text="Một câu ngắn.")
    rate = int(pipeline.settings["tts"]["sample_rate"])
    real, failures = os.replace, [2]

    def flaky(src, dst):
        if failures[0]:
            failures[0] -= 1
            raise PermissionError(13, "held by a scanner")
        return real(src, dst)

    monkeypatch.setattr(io_utils.os, "replace", flaky)
    monkeypatch.setattr(io_utils.time, "sleep", lambda _: None)
    checksum, _ = atomic_write_wav(tmp_path / "ok.wav", _tone(1.2, rate), rate, "Một câu ngắn.", pipeline.settings,
                                   segment=_voiced(pipeline.db, row))
    assert sha256_file(tmp_path / "ok.wav") == checksum


def _caused(message: str, cause: BaseException) -> AudioQualityError:
    """An engine failure the way VieNeu reports it (tts.py generate_one): wrapped, with its cause."""
    error = AudioQualityError(message)
    error.__cause__ = cause
    return error


@pytest.mark.parametrize("cause", [OSError(5, "disk went away"), MemoryError(),
                                   RuntimeError("CUDA error: an illegal memory access was encountered"),
                                   ConnectionResetError("connection reset by peer")],
                         ids=["oserror", "memoryerror", "cuda", "connection"])
@pytest.mark.parametrize("wrapped", [False, True], ids=["direct", "wrapped"])
def test_persistent_machine_fault_stops_without_spending_the_attempt(tmp_path, monkeypatch, cause, wrapped):
    pipeline, _chapter, _row = _short_tts_pipeline(tmp_path)
    monkeypatch.setattr(pipeline, "_recover_from_memory_pressure", lambda *_a: True)
    calls = []

    def broken():
        calls.append(1)
        raise _caused("engine failed", cause) if wrapped else cause

    with pytest.raises(pipeline_module.CriticalResourceStop):
        pipeline._through_machine_faults("thử", broken)
    assert len(calls) >= pipeline_module.WORD_BREAK_RETRY_ENVIRONMENT_ATTEMPTS


def test_named_machine_fault_without_a_cause_is_not_an_audio_verdict(tmp_path):
    pipeline, _chapter, _row = _short_tts_pipeline(tmp_path)
    calls = []

    def broken():
        calls.append(1)
        raise AudioQualityError("CUDA error: device-side assert triggered")

    with pytest.raises(pipeline_module.CriticalResourceStop):
        pipeline._through_machine_faults("thử", broken)
    assert len(calls) == pipeline_module.WORD_BREAK_RETRY_ENVIRONMENT_ATTEMPTS


@pytest.mark.parametrize("fault", [
    _caused("phonemizer: unsupported symbol", ValueError("unsupported symbol")),
    RuntimeError("configured split changed the spoken text"),
    KeyError("missing span"),
], ids=["engine_wrapped", "split_invariant", "keyerror"])
def test_persistent_deterministic_fault_is_the_take_verdict(tmp_path, fault):
    """Retried on the same seed, then filed as the take's verdict - never a stop of the whole book."""
    pipeline, _chapter, _row = _short_tts_pipeline(tmp_path)
    calls = []

    def broken():
        calls.append(1)
        raise fault

    with pytest.raises(AudioQualityError) as caught:
        pipeline._through_machine_faults("thử", broken)
    assert len(calls) == pipeline_module.WORD_BREAK_RETRY_ENVIRONMENT_ATTEMPTS
    assert caught.value.__cause__ is fault

    def verdict():
        calls.append(1)
        raise AudioQualityError("TTS_ACTIVE_ONSET: first 5 ms")

    calls.clear()
    with pytest.raises(AudioQualityError):
        pipeline._through_machine_faults("thử", verdict)
    assert calls == [1], "a validator's own verdict is not retried"


def test_state_write_failures_never_end_the_worker(tmp_path, monkeypatch):
    from abook import background_runner as runner

    paths = runner.BackgroundPaths.for_project(tmp_path)
    paths.ensure_root()
    real, failures = runner.atomic_write_json, [1]
    sleeps: list[float] = []

    def flaky(path, payload):
        if failures[0]:
            failures[0] -= 1
            raise PermissionError(13, "state.json held")
        return real(path, payload)

    monkeypatch.setattr(runner, "atomic_write_json", flaky)
    monkeypatch.setattr(runner.time, "sleep", sleeps.append)
    state = {"state": "running"}
    assert runner._write_live_state(paths, state) is False, "one try: a held file is not waited for"
    assert "state_write_lost" in state and sleeps == []
    assert runner._write_live_state(paths, state)
    assert json.loads(paths.state.read_text(encoding="utf-8"))["state_write_lost"], "the loss is reported once written"
    assert "state_write_lost" not in state and sleeps == []


def test_held_state_file_is_retried_later_from_after_the_failed_write(tmp_path, monkeypatch):
    from abook import background_runner as runner

    paths = runner.BackgroundPaths.for_project(tmp_path)
    paths.ensure_root()
    clock = [100.0]

    def held(path, payload):
        clock[0] += 2.0  # a slow failure: the back-off counts from after it
        raise PermissionError(13, "state.json held")

    monkeypatch.setattr(runner, "atomic_write_json", held)
    monkeypatch.setattr(runner.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(runner.time, "sleep", lambda _s: pytest.fail("the supervisor loop must never sleep on state.json"))
    writer = runner._LiveStateWriter(paths)
    assert writer.due(clock[0], False) is False and writer.due(clock[0], True) is True
    state = {"state": "running"}
    assert writer.write(state) is False
    assert writer.retry_at == 102.0 + runner.STATE_LIVE_RETRY_FIRST_SECONDS
    assert writer.due(102.5, True) is False, "a heartbeat or event during the back-off does not write"
    assert writer.due(writer.retry_at, False) is True, "the lost write is owed even with nothing new"
    clock[0] = writer.retry_at
    writer.write(state)
    assert writer.retry_at == clock[0] + 2 * runner.STATE_LIVE_RETRY_FIRST_SECONDS
    for _ in range(10):
        clock[0] = writer.retry_at
        writer.write(state)
    assert writer.backoff == runner.STATE_WRITE_RETRY_SECONDS
    monkeypatch.setattr(runner, "atomic_write_json", lambda path, payload: None)
    assert writer.write(state) and writer.retry_at is None
    assert writer.backoff == runner.STATE_LIVE_RETRY_FIRST_SECONDS


@pytest.mark.parametrize("fault", [PermissionError("locked"), RuntimeError("CUDA error: device-side assert triggered")],
                         ids=["oserror", "cuda"])
def test_persistent_machine_fault_is_not_written_as_a_seed_verdict(tmp_path, fault):
    pipeline, _chapter, row = _edge_pipeline(tmp_path, [fault] * 3)
    session = pipeline._begin_take_session(row, {"test": "machine-fault"})
    output = pipeline._session_attempt_path(row, session, "primary_0", tmp_path / "attempt.wav")
    with pytest.raises(pipeline_module.CriticalResourceStop):
        pipeline._session_synthesis(row, session, "primary_0", lambda: (
            output, *pipeline.tts.synthesize_atomic(row, output, seed_salt="primary_0")))
    saved = json.loads(pipeline.db.artifact_by_key(pipeline._take_session_key(row))["metadata_json"])
    assert "error" not in saved["attempts"]["primary_0"]
    assert not _signal(pipeline.db, row).get("signal_rejected")
    pipeline.tts.outcomes = ["clean"]
    pipeline._session_synthesis(row, saved, "primary_0", lambda: (
        output, *pipeline.tts.synthesize_atomic(row, output, seed_salt="primary_0")))
    assert pipeline.tts.salts == ["primary_0"] * 4


def test_deterministic_engine_fault_is_written_as_the_seed_verdict(tmp_path):
    fault = _caused("phonemizer: unsupported symbol", ValueError("unsupported symbol"))
    pipeline, _chapter, row = _edge_pipeline(tmp_path, [fault] * 3)
    session = pipeline._begin_take_session(row, {"test": "engine-fault"})
    output = pipeline._session_attempt_path(row, session, "primary_0", tmp_path / "attempt.wav")
    with pytest.raises(AudioQualityError, match="phonemizer"):
        pipeline._session_synthesis(row, session, "primary_0", lambda: (
            output, *pipeline.tts.synthesize_atomic(row, output, seed_salt="primary_0")))
    saved = json.loads(pipeline.db.artifact_by_key(pipeline._take_session_key(row))["metadata_json"])
    assert saved["attempts"]["primary_0"]["error"] == "phonemizer: unsupported symbol"
    assert saved["attempts"]["primary_0"]["quality"] is True
    # A replay reads the verdict from the ledger: the seed is not synthesized again.
    with pytest.raises(AudioQualityError, match="phonemizer"):
        pipeline._session_synthesis(row, saved, "primary_0", lambda: pytest.fail("replayed verdict re-synthesized"))
    assert pipeline.tts.salts == ["primary_0"] * 3


def test_deterministic_engine_fault_fails_the_line_and_the_chapter_goes_on(tmp_path):
    """A line the engine can never read ends failed; the next line is read; a resume does not stick on it."""
    from tests.test_word_break_gate import resume_through_chapter_loop

    pipeline, chapter, _row = _edge_pipeline(tmp_path, [], text="Một câu ngắn.\n\nCâu thứ hai.")
    bad, good = pipeline.db.list_segments(chapter_id=int(chapter["id"]))[:2]
    retries = int(pipeline.settings["tts"]["max_retries"])
    attempts = pipeline_module.WORD_BREAK_RETRY_ENVIRONMENT_ATTEMPTS

    def fault():
        return _caused("phonemizer: unsupported symbol", ValueError("unsupported symbol"))

    pipeline.tts.outcomes = [fault() for _ in range(retries * attempts)] + ["clean"]
    resume_through_chapter_loop(pipeline, chapter)
    assert pipeline.tts.salts == [f"primary_{index}" for index in range(retries) for _ in range(attempts)] + ["primary_0"]
    assert pipeline.db.get_segment(bad["id"])["status"] == "failed"
    assert pipeline.db.get_segment(good["id"])["status"] == "signal_passed"
    assert "SEGMENT_TTS_FAILED" in [str(item["code"]) for item in pipeline.db.list_events()]
    # A resume runs the chapter loop to its end instead of stopping on the same line.
    pipeline.tts.outcomes = [fault() for _ in range(retries * attempts)]
    resume_through_chapter_loop(pipeline, chapter)
    assert pipeline.db.get_segment(bad["id"])["status"] == "failed"
    assert pipeline.db.get_segment(good["id"])["status"] == "signal_passed"


def test_deterministic_split_error_fails_the_line_instead_of_stopping_the_run(tmp_path, monkeypatch):
    text = LONG_TEXT + " " + LONG_TEXT
    pipeline, chapter, row = _edge_pipeline(tmp_path, [AudioQualityError("no take")] * 20, text=text)
    calls = []

    def split(*_a, **_k):
        calls.append(1)
        raise RuntimeError("configured split changed the spoken text")

    monkeypatch.setattr(pipeline, "_synthesize_split", split)
    pipeline._process_single_segment(row, chapter)
    assert pipeline.db.get_segment(row["id"])["status"] == "failed"
    assert len(calls) == pipeline_module.WORD_BREAK_RETRY_ENVIRONMENT_ATTEMPTS
    # Closed: a resume of this line starts a new call, it does not replay the split forever.
    session = json.loads(pipeline.db.artifact_by_key(pipeline._take_session_key(row))["metadata_json"])
    assert session["state"] == "closed"


@pytest.mark.parametrize("soft", [
    {"generation_ceiling_hit": 1.0},
    {"word_break_gate": {"status": "measured", "fired": True, "flagged_words": 1,
                         "boundaries": [{"gap_ms": 90.0, "flagged": True}]}},
], ids=["ceiling", "word_break_fired"])
def test_high_quality_keeps_the_take_its_gate_accepts_over_a_pace_outlier(tmp_path, monkeypatch, soft):
    """primary_0 is clean but off pace (high_quality refuses it); primary_1 carries a flag the
    profile accepts. The accepted take must be kept and passed, not lost to the earlier one."""
    pipeline, chapter, row = _edge_pipeline(tmp_path, [("clean", {"pace_outlier": 1.0})] + [("clean", soft)] * 20,
                                            profile="high_quality")
    # The word-break retry is not under test here: no reservation, the measured gate stands.
    monkeypatch.setattr(pipeline, "_retry_word_break_once", lambda *_a, **_k: None)
    pipeline._process_single_segment(row, chapter)
    current = pipeline.db.get_segment(row["id"])
    signal = json.loads(current["signal_json"])
    assert current["status"] == "signal_passed"
    assert ".primary_1." in Path(current["wav_path"]).name and not signal.get("pace_outlier")
    assert Path(current["wav_path"]).is_file() and sha256_file(Path(current["wav_path"])) == current["wav_sha256"]
    assert pipeline.tts.salts == ["primary_0", "primary_1"]


def test_high_quality_rank_puts_its_refusals_right_after_the_signal_tier():
    rank = BookPipeline._usable_take_rank
    pace, ceiling = {"pace_outlier": 1.0}, {"generation_ceiling_hit": 1.0}
    doubled = {"repeated_utterance_score": 0.9}
    fired = {"word_break_gate": {"fired": True, "flagged_words": 3, "boundaries": [{"gap_ms": 200, "flagged": True}]}}
    for refused in (pace, doubled):
        for accepted in (ceiling, fired, INCONCLUSIVE, {**ceiling, **fired}):
            assert rank(accepted, high_quality=True) < rank(refused, high_quality=True)
            assert rank(accepted, qa_failed=True, high_quality=True) < rank(refused, high_quality=True)
        # Still behind the signal tier: any signal pass beats any refused take.
        assert rank(refused, high_quality=True) < rank({"signal_rejected": True, "rejection_class": "edge"},
                                                       high_quality=True)
    # The standard profile does not refuse a pace outlier, so it stays one soft flag there.
    assert rank(pace) == rank(ceiling)


def test_checkpoint_error_does_not_relabel_clean_audio(tmp_path, monkeypatch):
    pipeline, _chapter, row = _edge_pipeline(tmp_path, ["clean"])
    pipeline.db.mark_generating(row["id"], 1)
    path = tmp_path / "ok.wav"
    checksum, metrics, seed = pipeline.tts.synthesize_atomic(row, path, seed_salt="primary_0")
    pipeline._keep_usable_take(row, path, checksum, metrics, seed)
    monkeypatch.setattr(pipeline.db, "mark_signal_passed", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("write failed")))
    with pytest.raises(RuntimeError, match="write failed"):
        pipeline._accept_retained_take(row, checksum)
    assert not _signal(pipeline.db, row).get("signal_rejected")


@pytest.mark.parametrize("refused", [False, True])
def test_split_ledger_replays_after_crash_without_resynthesizing(tmp_path, monkeypatch, refused):
    text = LONG_TEXT + " " + LONG_TEXT
    pipeline, chapter, row = _edge_pipeline(tmp_path, [AudioQualityError("no take")] * 4, text=text)
    calls = []

    def split(item, output, **kwargs):
        calls.append(kwargs["seed_salt_prefix"])
        if refused:
            raise AudioQualityError("no natural boundary")
        rate = int(pipeline.settings["tts"]["sample_rate"])
        atomic_write_wav(output, _tone(8., rate), rate, text, pipeline.settings, segment=_voiced(pipeline.db, item))
        return [{"voice_profile_id": int(item["voice_profile_id"])}]

    monkeypatch.setattr(pipeline, "_synthesize_split", split)
    close = pipeline._close_take_session

    def crash(*args):
        raise SystemExit("before close")

    monkeypatch.setattr(pipeline, "_close_take_session", crash)
    with pytest.raises(SystemExit):
        pipeline._process_single_segment(row, chapter)
    pipeline.db = ProjectDB(pipeline.db.path)
    pipeline.tts.db = pipeline.db
    monkeypatch.setattr(pipeline, "_close_take_session", close)
    pipeline._process_single_segment(pipeline.db.get_segment(row["id"]), chapter)
    assert calls == ["primary_split"]
    assert pipeline.db.get_segment(row["id"])["status"] == ("failed" if refused else "signal_passed")


def test_session_cleanup_preserves_artifact_references(tmp_path):
    pipeline, _chapter, row = _edge_pipeline(tmp_path, [])
    session = pipeline._begin_take_session(row, {"test": "cleanup"})
    evidence, loser = tmp_path / "evidence.wav", tmp_path / "loser.wav"
    evidence.write_bytes(b"artifact evidence")
    loser.write_bytes(b"unreferenced take")
    orphan = rejected_take_path(loser)
    orphan.write_bytes(b"stale rejected take")
    pipeline.db.register_artifact(artifact_key="evidence", kind="test", path=evidence,
                                  sha256=sha256_file(evidence), verified=False)
    session["attempts"].update(a={"path": str(evidence)}, b={"path": str(loser)})
    pipeline._close_take_session(row, session)
    assert evidence.exists() and not loser.exists() and not orphan.exists()


@pytest.mark.parametrize("keep", [False, True], ids=["preview", "pipeline"])
def test_only_a_caller_that_asks_keeps_a_refused_take_on_disk(tmp_path, monkeypatch, keep):
    """A preview or probe (`reading_preview`, `scripts/probe_*`) never leaves an orphan .rejected.wav."""
    from abook.character_registry import voice_profile_spec
    from abook.config import build_settings
    from abook.tts import TTSCoordinator
    from tests.test_engine_voices import ZEROTTS, _row

    db = ProjectDB(tmp_path / "p.sqlite3")
    coordinator = TTSCoordinator(build_settings(), db, lambda _message: None)
    row = _row(db, voice_profile_spec(ZEROTTS))
    engine = coordinator.engine("zerotts")
    engine.sample_rate = 48_000
    monkeypatch.setattr(engine, "generate_one", lambda *_a, **_k: _tone(5.0, 48_000, edge=True))
    output = tmp_path / "preview" / "a.wav"
    with pytest.raises(AudioQualityError) as caught:
        coordinator.synthesize_atomic(row, output, **({"keep_rejected": True} if keep else {}))
    assert isinstance(caught.value, SignalRejectedTake) is keep
    assert not output.exists()
    assert rejected_take_path(output).is_file() is keep
