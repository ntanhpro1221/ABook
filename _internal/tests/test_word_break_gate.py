from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from abook import tts, voice_balance, word_break
from abook.database import ProjectDB
from abook.pipeline import BookPipeline
from tests.test_pipeline_mock import _short_tts_pipeline


TEXT = "Khoảnh khắc kỳ diệu hôm nay đã làm mọi người bất ngờ."


def test_calibrated_voices_only():
    assert voice_balance.constants_for("vieneu", "3.8.3", "Ngọc Linh").word_break_gate == {
        "metric": "silence_ms", "threshold": 72.8, "calibrated_r": 1.0447, "calibrated_x": 1.0}
    assert voice_balance.constants_for("vieneu", "3.8.3", "Đức Trí").word_break_gate["metric"] == "closure_hgb_v1"
    for name in ("Kim Thanh", "Đoan Trang", "Xuân Vĩnh"):
        assert voice_balance.constants_for("vieneu", "3.8.3", name).word_break_gate is None


def test_bad_thresholds_and_borrowed_classifier_are_refused():
    for value in (0, -1, float("nan"), True):
        table = copy.deepcopy(voice_balance.load_table())
        table["voices"]["vieneu@3.8.3/Ngọc Linh"]["word_break_gate"]["threshold"] = value
        with pytest.raises(voice_balance.VoiceBalanceError):
            voice_balance._validate(table)
    table = copy.deepcopy(voice_balance.load_table())
    table["voices"]["vieneu@3.8.3/Kim Thanh"]["word_break_gate"] = table["voices"]["vieneu@3.8.3/Đức Trí"]["word_break_gate"]
    with pytest.raises(voice_balance.VoiceBalanceError):
        voice_balance._validate(table)


@pytest.mark.parametrize("source", ["lại.Khoảnh", "khoảnh\nkhắc", "khoảnh,khắc", "khoảnh-khắc", "khoảnh;khắc"])
def test_internal_punctuation_and_newlines_are_excluded(source):
    assert word_break._has_internal_punctuation(source)


def test_tokenizer_and_compound_groups():
    assert word_break.tokenize("Khoảnh khắc kỳ diệu.") == "Khoảnh_khắc kỳ_diệu ."
    reference, groups = word_break.plan(TEXT, TEXT, lambda s:s)
    assert reference.startswith("khoảnh khắc")
    assert any(g["source"] == "Khoảnh khắc" and g["lo"] == 0 and g["hi"] == 2 for g in groups)
    _, punctuated = word_break.plan("lại.Khoảnh khắc", "lại.Khoảnh khắc", lambda s:s)
    assert all("lại.Khoảnh" not in g["source"] for g in punctuated)
    _, newline = word_break.plan("khoảnh\nkhắc", "khoảnh\nkhắc", lambda s:s)
    assert newline == []


def test_gap_window_uses_energy_inside_aligned_word():
    sr = 48000
    tone = np.sin(np.arange(sr)*2*np.pi*200/sr).astype("float32")*.1
    tone[round(.44*sr):round(.56*sr)] = 0
    values = word_break.gaps(tone, sr, [[.1,.44],[.56,.9]])
    assert values[0] == pytest.approx(120, abs=5)


class Engine:
    name = "vieneu"
    sample_rate = 48000
    native_tempo = True

    def __init__(self, modes):
        self.modes = modes
        self.calls = []
        self.spans = []

    def pause_for(self, seed):
        return .12 if self.modes[min(len(self.calls)-1,len(self.modes)-1)] == "gap" else 0.

    def generate_one(self, row, profile, seed, *, sampling, **kwargs):
        from vieneu_utils import phonemize_text as pt
        chunks = pt.normalize_to_chunks_v3(row["text"])
        phones = [pt._phonemize_cached(s) for s in chunks]
        self.calls.append(dict(text=row["text"], phones=phones, sampling=dict(sampling), seed=seed))
        pause = self.pause_for(seed)
        count = len(word_break.norm(" ".join(chunks)).split())
        self.spans = []
        at = .08
        for i in range(count):
            self.spans.append([at,at+.2])
            at += .2 + (pause if i == 0 else 0)
        wave = np.sin(np.arange(round((at+.08)*48000))*2*np.pi*200/48000).astype("float32")*.1
        wave[:3840] = 0
        wave[round(at*48000):] = 0
        if pause:
            wave[round(.28*48000):round((.28+pause)*48000)] = 0
        return wave


def scenario(tmp_path, monkeypatch, modes, source=TEXT):
    pipeline, chapter, row = _short_tts_pipeline(tmp_path, source_text=source)
    with pipeline.db.transaction() as conn:
        conn.execute("UPDATE voice_profiles SET preset_name='Ngọc Linh'")
    engine = Engine(modes)
    pipeline.tts.engine_for_profile = lambda _profile:engine
    pipeline.tts.release_inference_cache = lambda:None
    monkeypatch.setattr(word_break, "_aligner", lambda _folder:type("Aligner", (), {"align":lambda _self,wave,text:(engine.spans,.99)})())
    monkeypatch.setattr(word_break, "ASSETS", Path(word_break.__file__).parent/"assets")
    from abook.webui import word_timing
    monkeypatch.setattr(word_timing, "model_dir", lambda:tmp_path)
    pipeline._wait_pause_or_stop = lambda:None
    return pipeline, chapter, row, engine


@pytest.mark.parametrize("modes,expected", [(["clean"],1),(["gap","clean"],2),(["gap","gap"],2)])
def test_app_engine_wav_retries_once_and_preserves_phonemes(tmp_path, monkeypatch, modes, expected):
    pipeline, chapter, row, engine = scenario(tmp_path, monkeypatch, modes)
    pipeline._process_single_segment(row, chapter)
    assert len(engine.calls) == expected
    current = pipeline.db.get_segment(int(row["id"]))
    assert current["status"] == "signal_passed"
    gate = json.loads(current["signal_json"])[word_break.FIELD]
    assert gate["retry_count"] == expected-1
    if expected == 2:
        assert engine.calls[0]["seed"] != engine.calls[1]["seed"]
        for key in ("text","phones","sampling"):
            assert engine.calls[0][key] == engine.calls[1][key]
        assert gate["triggered"] and gate["before"]["fired"]
        assert gate["after"]["fired"] == (modes[1] == "gap")
        assert gate["fired"] == (modes[1] == "gap")
        assert Path(current["wav_path"]).is_file()
        assert len(list(pipeline._segment_candidate_root().glob("*.word_break.wav"))) == 1


def test_source_period_does_not_trigger_retry(tmp_path, monkeypatch):
    pipeline, chapter, row, engine = scenario(tmp_path, monkeypatch, ["gap"], source="lại.Khoảnh")
    pipeline._process_single_segment(row, chapter)
    assert len(engine.calls) == 1
    gate = json.loads(pipeline.db.get_segment(int(row["id"]))["signal_json"])[word_break.FIELD]
    assert gate["status"] == "no_groups"
    assert not gate["fired"]


def test_inconclusive_retry_retains_measured_incumbent(tmp_path, monkeypatch):
    pipeline, chapter, row, engine = scenario(tmp_path, monkeypatch, ["gap", "clean"])
    monkeypatch.setattr(word_break, "_aligner", lambda _folder:type("Aligner", (), {
        "align":lambda _self,wave,text:(engine.spans,.99) if len(engine.calls) == 1 else None,
    })())
    pipeline._process_single_segment(row, chapter)
    current = pipeline.db.get_segment(int(row["id"]))
    signal = json.loads(current["signal_json"])
    gate = signal[word_break.FIELD]
    assert len(engine.calls) == 2
    assert current["generation_seed"] == engine.calls[0]["seed"]
    assert gate["fired"] and gate["retry_count"] == 1
    assert gate["after"]["status"] == "inconclusive"
    assert gate["before"]["status"] == "measured"


def test_chapter_loop_leaves_a_finished_failed_take_alone(tmp_path, monkeypatch):
    """Only a call a crash left open is owed a replay; a take no call is making keeps today's rule."""
    pipeline, chapter, row, engine = scenario(tmp_path, monkeypatch, ["clean"])
    pipeline._keep_usable_take(row, *_clean_take(pipeline, row, tmp_path))
    reopened = ProjectDB(pipeline.paths.db)
    reopened.reset_in_progress_segments("crash before quality decision")
    pipeline.db = reopened
    assert pipeline._owed_take_session(reopened.get_segment(int(row["id"]))) is None


def _clean_take(pipeline, row, tmp_path):
    checksum, metrics, seed = pipeline.tts.synthesize_atomic(row, tmp_path/"clean.wav", seed_salt="primary_0")
    return tmp_path/"clean.wav", checksum, metrics, seed


def test_crash_after_reservation_reruns_the_reserved_seed_after_reopen(tmp_path, monkeypatch):
    pipeline, chapter, row, engine = scenario(tmp_path, monkeypatch, ["gap", "clean"])
    original = pipeline.tts.synthesize_atomic
    def interrupted(*args, **kwargs):
        if kwargs.get("seed_salt", "").startswith("word_break_candidate_"):
            raise SystemExit("crash after reservation")
        return original(*args, **kwargs)
    pipeline.tts.synthesize_atomic = interrupted
    with pytest.raises(SystemExit):
        pipeline._process_single_segment(row, chapter)
    reserved_seed = pipeline.tts.generation_seed(row, "word_break_candidate_0_0")
    reopened = ProjectDB(pipeline.paths.db)
    pipeline.db = reopened
    pipeline.tts.db = reopened
    pipeline.tts.synthesize_atomic = original
    pipeline._process_single_segment(reopened.get_segment(int(row["id"])), chapter)
    assert [call["seed"] for call in engine.calls[1:]] == [reserved_seed]
    current = reopened.get_segment(int(row["id"]))
    gate = json.loads(current["signal_json"])[word_break.FIELD]
    assert gate["retry_count"] == 1
    assert gate["retry_state"] == "complete"
    assert current["generation_seed"] == reserved_seed
    assert current["status"] == "signal_passed"


def test_asr_candidate_uses_one_same_delivery_retry_without_promoting_incumbent(tmp_path, monkeypatch):
    pipeline, chapter, row, engine = scenario(tmp_path, monkeypatch, ["clean","gap","clean"])
    pipeline._process_single_segment(row, chapter)
    row = pipeline.db.get_segment(int(row["id"]))
    incumbent = row["wav_sha256"]
    candidate = pipeline._allocate_segment_candidate(row, 0, 2)
    result = pipeline._process_segment_candidate(row, candidate, chapter)
    assert result["state"] == "signal_passed"
    assert result["tts_attempt"] == 1
    assert result["generation_seed"] == engine.calls[2]["seed"]
    assert len(engine.calls) == 3
    for field in ("text","phones","sampling"):
        assert engine.calls[1][field] == engine.calls[2][field]
    signal = json.loads(result["signal_json"])
    assert signal[word_break.FIELD]["retry_count"] == 1
    assert not signal[word_break.FIELD]["fired"]
    assert pipeline.db.get_segment(int(row["id"]))["wav_sha256"] == incumbent
    assert not pipeline._resume_word_break_retry(row)


# --- Same book, same audio: the retry is a pure function of (input, reserved seed). ---

OOM = "CUDA out of memory. Tried to allocate 20.00 MiB"
PAUSES = {"clean": 0., "gap": .12, "big": .2}
RETRY_SALT = "word_break_candidate_0_0"
CANDIDATE_SALT = "asr_clarity_candidate_0_0"


class SeededEngine(Engine):
    """Audio depends on the seed alone, as the real engine's does: a replay must agree."""

    def __init__(self):
        super().__init__([])
        self.pauses = {}

    def pause_for(self, seed):
        return self.pauses.get(seed, 0.)

    def generate_one(self, row, profile, seed, *, sampling, **kwargs):
        wave = super().generate_one(row, profile, seed, sampling=sampling, **kwargs)
        return wave*(.8+(seed % 97)/485)


def seeded(tmp_path, monkeypatch, plan, *, retries=4, outliers=()):
    tmp_path.mkdir(parents=True, exist_ok=True)
    pipeline, chapter, row, _engine = scenario(tmp_path, monkeypatch, ["clean"])
    engine = SeededEngine()
    pipeline.tts.engine_for_profile = lambda _profile:engine
    monkeypatch.setattr(word_break, "_aligner", lambda _folder:type("Aligner", (), {"align":lambda _self,wave,text:(engine.spans,.99)})())
    monkeypatch.setattr("abook.pipeline.time.sleep", lambda _seconds:None)
    engine.pauses = {pipeline.tts.generation_seed(row, salt):PAUSES[mode] for salt, mode in plan.items()}
    pipeline.settings["tts"]["max_retries"] = retries
    if outliers:
        pipeline.settings["quality_profile"] = "high_quality"
        bad = {pipeline.tts.generation_seed(row, salt) for salt in outliers}
        original = pipeline.tts.synthesize_atomic
        def flagged(*args, **kwargs):
            checksum, metrics, seed = original(*args, **kwargs)
            if seed in bad:
                metrics["pace_outlier"] = True
                metrics["chars_per_second"] = 99.
            return checksum, metrics, seed
        pipeline.tts.synthesize_atomic = flagged
    return pipeline, chapter, row, engine


def stable(value):
    if isinstance(value, dict):
        return {k:stable(v) for k,v in value.items() if k != "seconds"}
    if isinstance(value, list):
        return [stable(v) for v in value]
    return value


def reservation(pipeline):
    with pipeline.db.transaction() as conn:
        rows = conn.execute("SELECT * FROM artifacts WHERE kind='word_break_candidate'").fetchall()
    return [stable({**json.loads(item["metadata_json"]), "sha256":item["sha256"]}) for item in rows]


def segment_outcome(pipeline, row):
    current = pipeline.db.get_segment(int(row["id"]))
    return dict(sha=current["wav_sha256"], seed=current["generation_seed"], status=current["status"],
                duration=current["wav_duration"], warning=current["warning_code"],
                signal=stable(json.loads(current["signal_json"])), ledger=reservation(pipeline))


def candidate_outcome(pipeline, row, candidate):
    current = pipeline.db.get_segment_candidate(int(candidate["id"]))
    return dict(sha=current["wav_sha256"], seed=current["generation_seed"], state=current["state"],
                attempt=current["tts_attempt"], signal=stable(json.loads(current["signal_json"] or "{}")),
                ledger=reservation(pipeline), segment=stable(json.loads(pipeline.db.get_segment(int(row["id"]))["signal_json"])))


def reopen(pipeline, row):
    """A dead process: only what SQLite and the disk hold survives; recovery runs first."""
    for name in ("_accept_retained_take", "_keep_usable_take", "_checkpoint_segment_candidate_signal"):
        pipeline.__dict__.pop(name, None)
    pipeline.tts.synthesize_atomic = pipeline.tts._real_synthesize
    db = ProjectDB(pipeline.paths.db)
    pipeline.db = db
    pipeline.tts.db = db
    pipeline._recover()
    return db.get_segment(int(row["id"]))


def install_fault(pipeline, point):
    """Kill the process (BaseException, past every handler) or fail once at one named point."""
    pipeline.tts._real_synthesize = real = pipeline.tts.synthesize_atomic
    state = pipeline._fault_state = dict(left=1)
    def die():
        if state["left"]:
            state["left"] = 0
            raise SystemExit("crash at "+point)
    def wrap(owner, name, after=False):
        original = getattr(owner, name)
        def wrapped(*args, **kwargs):
            if not after:
                die()
            result = original(*args, **kwargs)
            if after:
                die()
            return result
        setattr(owner, name, wrapped)
    if point in {"after_reservation", "oom", "disk"}:
        def synth(*args, **kwargs):
            if str(kwargs.get("seed_salt", "")).startswith("word_break_candidate_") and state["left"]:
                state["left"] = 0
                if point == "after_reservation":
                    raise SystemExit("crash at "+point)
                raise RuntimeError(OOM) if point == "oom" else PermissionError("WAV locked by antivirus")
            return real(*args, **kwargs)
        pipeline.tts.synthesize_atomic = synth
        pipeline._recover_from_memory_pressure = lambda _where, _error:True
    elif point == "before_reservation":
        wrap(pipeline.db, "reserve_word_break_retry")
    elif point == "after_synthesis":
        wrap(pipeline.db, "finish_word_break_retry")
    elif point == "after_finish":
        wrap(pipeline.db, "finish_word_break_retry", after=True)
    elif point == "before_annotate":
        wrap(pipeline.db, "annotate_word_break_retry")
    elif point == "before_accept":
        wrap(pipeline, "_accept_retained_take")
    elif point == "before_checkpoint":
        wrap(pipeline, "_checkpoint_segment_candidate_signal")
    elif point == "after_restart":
        wrap(pipeline.db, "restart_segment_candidate_generation", after=True)
    elif point != "none":
        raise AssertionError(point)


SINGLE_PLANS = {
    "retry_wins": dict(plan={"primary_0":"gap", RETRY_SALT:"clean"}),
    "first_take_wins": dict(plan={"primary_0":"gap", RETRY_SALT:"big"}),
    "retry_rejected_by_pace_then_new_attempt": dict(plan={"primary_0":"gap", RETRY_SALT:"clean", "primary_1":"clean"},
                                                     outliers=(RETRY_SALT,)),
}
SINGLE_POINTS = ["before_reservation", "after_reservation", "after_synthesis", "after_finish", "before_annotate", "before_accept", "oom", "disk"]


class TtsStageDone(Exception):
    pass


def resume_through_chapter_loop(pipeline, chapter):
    """Resume the way a worker does: the chapter loop decides whether the segment runs at all."""
    def done(*_args, **_kwargs):
        raise TtsStageDone
    pipeline._verify_chapter_audio = done
    pipeline._resource_gate = lambda *_a, **_k:None
    pipeline._prefetch_segment_batch = lambda *_a, **_k:{}
    with pytest.raises(TtsStageDone):
        pipeline._process_chapter(pipeline.db.list_chapters()[0], None)


def run_single(tmp_path, monkeypatch, config, point):
    pipeline, chapter, row, engine = seeded(tmp_path, monkeypatch, **config)
    install_fault(pipeline, point)
    try:
        pipeline._process_single_segment(row, chapter)
    except SystemExit:
        row = reopen(pipeline, row)
        resume_through_chapter_loop(pipeline, chapter)
    assert point == "none" or not pipeline._fault_state["left"], "the fault never happened"
    return segment_outcome(pipeline, row)


@pytest.mark.parametrize("name", SINGLE_PLANS)
@pytest.mark.parametrize("point", SINGLE_POINTS)
def test_single_take_outcome_is_the_same_with_any_interruption(tmp_path, monkeypatch, name, point):
    config = SINGLE_PLANS[name]
    expected = run_single(tmp_path/"a", monkeypatch, config, "none")
    assert expected["status"] == "signal_passed"
    assert run_single(tmp_path/"b", monkeypatch, config, point) == expected


def test_uninterrupted_reference_runs_pick_the_expected_take(tmp_path, monkeypatch):
    won = run_single(tmp_path/"a", monkeypatch, SINGLE_PLANS["retry_wins"], "none")
    assert won["signal"][word_break.FIELD]["retry_state"] == "complete" and not won["signal"][word_break.FIELD]["fired"]
    kept = run_single(tmp_path/"b", monkeypatch, SINGLE_PLANS["first_take_wins"], "none")
    assert kept["signal"][word_break.FIELD]["fired"] and kept["signal"][word_break.FIELD]["after"]["fired"]
    assert kept["sha"] != won["sha"] and kept["seed"] != won["seed"]
    third = run_single(tmp_path/"c", monkeypatch, SINGLE_PLANS["retry_rejected_by_pace_then_new_attempt"], "none")
    assert not third["signal"].get("pace_outlier")
    assert third["seed"] not in (won["seed"], kept["seed"])


CANDIDATE_PLANS = {
    "retry_wins": dict(plan={CANDIDATE_SALT:"gap", RETRY_SALT:"clean"}),
    "first_take_wins": dict(plan={CANDIDATE_SALT:"gap", RETRY_SALT:"big"}),
    "last_attempt_retry_wins": dict(plan={CANDIDATE_SALT:"gap", RETRY_SALT:"clean"}, retries=1),
}
CANDIDATE_POINTS = ["after_reservation", "after_synthesis", "after_finish", "after_restart", "before_checkpoint", "oom", "disk"]


def run_candidate(tmp_path, monkeypatch, config, point):
    pipeline, chapter, row, engine = seeded(tmp_path, monkeypatch, **config)
    pipeline._process_single_segment(row, chapter)
    row = pipeline.db.get_segment(int(row["id"]))
    candidate = pipeline._allocate_segment_candidate(row, 0, 2)
    install_fault(pipeline, point)
    try:
        pipeline._process_segment_candidate(row, candidate, chapter)
    except SystemExit:
        row = reopen(pipeline, row)
        pipeline._process_segment_candidate(row, candidate, chapter)
    # A first take that keeps its place never moves the candidate's seed: no restart to crash after.
    assert point in {"none", "after_restart"} or not pipeline._fault_state["left"], "the fault never happened"
    return candidate_outcome(pipeline, row, candidate)


@pytest.mark.parametrize("name", CANDIDATE_PLANS)
@pytest.mark.parametrize("point", CANDIDATE_POINTS)
def test_candidate_outcome_is_the_same_with_any_interruption(tmp_path, monkeypatch, name, point):
    config = CANDIDATE_PLANS[name]
    expected = run_candidate(tmp_path/"a", monkeypatch, config, "none")
    assert expected["state"] == "signal_passed"
    assert run_candidate(tmp_path/"b", monkeypatch, config, point) == expected


# F1
def test_engine_wrapped_out_of_memory_is_still_transient(tmp_path, monkeypatch):
    from abook.audio_io import AudioQualityError
    pipeline, chapter, row, engine = seeded(tmp_path, monkeypatch, {"primary_0":"gap", RETRY_SALT:"clean"})
    real = pipeline.tts.synthesize_atomic
    state = dict(left=1)
    def wrapped(*args, **kwargs):
        if str(kwargs.get("seed_salt", "")).startswith("word_break_candidate_") and state["left"]:
            state["left"] = 0
            raise AudioQualityError(OOM) from RuntimeError(OOM)
        return real(*args, **kwargs)
    pipeline.tts.synthesize_atomic = wrapped
    pipeline._recover_from_memory_pressure = lambda _where, _error:True
    pipeline._process_single_segment(row, chapter)
    assert pipeline.db.get_segment(int(row["id"]))["generation_seed"] == pipeline.tts.generation_seed(row, RETRY_SALT)


def test_transient_memory_error_reruns_the_reserved_seed(tmp_path, monkeypatch):
    pipeline, chapter, row, engine = seeded(tmp_path, monkeypatch, {"primary_0":"gap", RETRY_SALT:"clean"})
    install_fault(pipeline, "oom")
    pipeline._process_single_segment(row, chapter)
    current = pipeline.db.get_segment(int(row["id"]))
    gate = json.loads(current["signal_json"])[word_break.FIELD]
    assert gate["retry_state"] == "complete" and not gate["fired"]
    assert current["generation_seed"] == pipeline.tts.generation_seed(row, RETRY_SALT)


@pytest.mark.parametrize("error", [RuntimeError(OOM), PermissionError("locked")])
def test_environment_failure_that_never_clears_stops_without_spending_the_budget(tmp_path, monkeypatch, error):
    from abook.pipeline import CriticalResourceStop
    pipeline, chapter, row, engine = seeded(tmp_path, monkeypatch, {"primary_0":"gap", RETRY_SALT:"clean"})
    real = pipeline.tts.synthesize_atomic
    def always(*args, **kwargs):
        if str(kwargs.get("seed_salt", "")).startswith("word_break_candidate_"):
            raise error
        return real(*args, **kwargs)
    pipeline.tts.synthesize_atomic = always
    pipeline._recover_from_memory_pressure = lambda _where, _error:False
    with pytest.raises(CriticalResourceStop):
        pipeline._process_single_segment(row, chapter)
    assert reservation(pipeline)[0]["state"] == "reserved"
    pipeline.tts.synthesize_atomic = real
    pipeline._process_single_segment(pipeline.db.get_segment(int(row["id"])), chapter)
    assert reservation(pipeline)[0]["state"] == "complete"


def test_quality_verdict_is_final_and_replays_without_synthesis(tmp_path, monkeypatch):
    from abook.audio_io import AudioQualityError
    pipeline, chapter, row, engine = seeded(tmp_path, monkeypatch, {"primary_0":"gap", RETRY_SALT:"clean"})
    real = pipeline.tts.synthesize_atomic
    def refuse(*args, **kwargs):
        if str(kwargs.get("seed_salt", "")).startswith("word_break_candidate_"):
            raise AudioQualityError("TTS_ACTIVE_OFFSET")
        return real(*args, **kwargs)
    pipeline.tts.synthesize_atomic = refuse
    pipeline._process_single_segment(row, chapter)
    current = pipeline.db.get_segment(int(row["id"]))
    gate = json.loads(current["signal_json"])[word_break.FIELD]
    assert gate["retry_state"] == "failed" and gate["fired"] and "TTS_ACTIVE_OFFSET" in gate["error"]
    assert current["status"] == "signal_passed"
    assert current["generation_seed"] == pipeline.tts.generation_seed(row, "primary_0")
    calls = len(engine.calls)
    pipeline._process_single_segment(pipeline.db.get_segment(int(row["id"])), chapter)
    assert len(engine.calls) == calls


def test_lost_retry_file_is_regenerated_from_its_seed(tmp_path, monkeypatch):
    pipeline, chapter, row, engine = seeded(tmp_path, monkeypatch, {"primary_0":"gap", RETRY_SALT:"clean"})
    install_fault(pipeline, "after_finish")
    with pytest.raises(SystemExit):
        pipeline._process_single_segment(row, chapter)
    row = reopen(pipeline, row)
    lost = next(pipeline._segment_candidate_root().glob("*.word_break.wav"))
    lost.unlink()
    resume_through_chapter_loop(pipeline, chapter)
    current = pipeline.db.get_segment(int(row["id"]))
    assert current["generation_seed"] == pipeline.tts.generation_seed(row, RETRY_SALT)
    assert json.loads(current["signal_json"])[word_break.FIELD]["retry_state"] == "complete"


# F2
def test_resume_refuses_the_outlier_take_a_crash_left_selected(tmp_path, monkeypatch):
    pipeline, chapter, row, engine = seeded(tmp_path, monkeypatch, {"primary_0":"gap", RETRY_SALT:"clean"},
                                            outliers=(RETRY_SALT,))
    install_fault(pipeline, "before_annotate")
    with pytest.raises(SystemExit):
        pipeline._process_single_segment(row, chapter)
    row = reopen(pipeline, row)
    resume_through_chapter_loop(pipeline, chapter)
    current = pipeline.db.get_segment(int(row["id"]))
    assert not json.loads(current["signal_json"]).get("pace_outlier")
    assert current["generation_seed"] == pipeline.tts.generation_seed(row, "primary_1")


def test_last_attempt_candidate_retry_survives_a_crash(tmp_path, monkeypatch):
    outcome = run_candidate(tmp_path, monkeypatch, CANDIDATE_PLANS["last_attempt_retry_wins"], "after_reservation")
    assert outcome["state"] == "signal_passed"
    assert outcome["signal"][word_break.FIELD]["retry_state"] == "complete"


# F3
@pytest.mark.parametrize("deterministic", [True, False])
def test_failed_candidate_retry_keeps_the_first_take(tmp_path, monkeypatch, deterministic):
    from abook.audio_io import AudioQualityError
    pipeline, chapter, row, engine = seeded(tmp_path, monkeypatch, {CANDIDATE_SALT:"gap", RETRY_SALT:"clean"})
    pipeline._process_single_segment(row, chapter)
    row = pipeline.db.get_segment(int(row["id"]))
    candidate = pipeline._allocate_segment_candidate(row, 0, 2)
    real = pipeline.tts.synthesize_atomic
    state = dict(left=1)
    def flaky(*args, **kwargs):
        if str(kwargs.get("seed_salt", "")).startswith("word_break_candidate_") and (deterministic or state["left"]):
            state["left"] = 0
            raise AudioQualityError("TTS_ACTIVE_OFFSET") if deterministic else RuntimeError(OOM)
        return real(*args, **kwargs)
    pipeline.tts.synthesize_atomic = flaky
    pipeline._recover_from_memory_pressure = lambda _where, _error:True
    result = pipeline._process_segment_candidate(row, candidate, chapter)
    assert result["state"] == "signal_passed"
    gate = json.loads(result["signal_json"])[word_break.FIELD]
    if deterministic:
        assert result["generation_seed"] == pipeline.tts.generation_seed(row, CANDIDATE_SALT)
        assert gate["retry_state"] == "failed" and gate["fired"]
        assert result["tts_attempt"] == 0
    else:
        assert result["generation_seed"] == pipeline.tts.generation_seed(row, RETRY_SALT)
        assert gate["retry_state"] == "complete"


# F4
def test_candidate_keeps_the_first_take_when_the_retry_is_worse(tmp_path, monkeypatch):
    pipeline, chapter, row, engine = seeded(tmp_path, monkeypatch, {CANDIDATE_SALT:"gap", RETRY_SALT:"big"})
    pipeline._process_single_segment(row, chapter)
    row = pipeline.db.get_segment(int(row["id"]))
    candidate = pipeline._allocate_segment_candidate(row, 0, 2)
    result = pipeline._process_segment_candidate(row, candidate, chapter)
    gate = json.loads(result["signal_json"])[word_break.FIELD]
    assert result["generation_seed"] == pipeline.tts.generation_seed(row, CANDIDATE_SALT)
    assert result["tts_attempt"] == 0
    assert gate["before"]["max_gap_ms"] < gate["after"]["max_gap_ms"]
    assert hashlib.sha256(Path(result["wav_path"]).read_bytes()).hexdigest() == result["wav_sha256"]


# F5
def test_clarity_retry_keeps_the_repair_round_on_the_selected_take(tmp_path, monkeypatch):
    from abook.pipeline import DELIVERY_CLARITY
    pipeline, chapter, row, engine = scenario(tmp_path, monkeypatch, ["gap", "clean"])
    pipeline._process_single_segment(row, chapter, seed_salt_prefix="asr_clarity_repair_0",
                                     repair_short_utterance=True, delivery_mode=DELIVERY_CLARITY, asr_repair_round=0)
    signal = json.loads(pipeline.db.get_segment(int(row["id"]))["signal_json"])
    assert len(engine.calls) == 2
    assert signal[word_break.FIELD]["retry_state"] == "complete"
    assert signal["tts_delivery_mode"] == DELIVERY_CLARITY
    assert signal["asr_clarity_repair_round"] == 0


def test_a_later_clarity_call_is_not_answered_by_the_primary_retry(tmp_path, monkeypatch):
    from abook.pipeline import DELIVERY_CLARITY
    pipeline, chapter, row, engine = scenario(tmp_path, monkeypatch, ["gap", "clean", "clean"])
    pipeline._process_single_segment(row, chapter)
    assert len(engine.calls) == 2
    pipeline._process_single_segment(pipeline.db.get_segment(int(row["id"])), chapter, seed_salt_prefix="asr_clarity_repair_0",
                                     repair_short_utterance=True, delivery_mode=DELIVERY_CLARITY, asr_repair_round=0)
    assert len(engine.calls) == 3


# F6
def test_candidate_retry_leaves_the_incumbent_signal_alone(tmp_path, monkeypatch):
    pipeline, chapter, row, engine = seeded(tmp_path, monkeypatch, {CANDIDATE_SALT:"gap", RETRY_SALT:"clean"})
    pipeline._process_single_segment(row, chapter)
    row = pipeline.db.get_segment(int(row["id"]))
    before = json.loads(row["signal_json"])
    candidate = pipeline._allocate_segment_candidate(row, 0, 2)
    result = pipeline._process_segment_candidate(row, candidate, chapter)
    assert json.loads(pipeline.db.get_segment(int(row["id"]))["signal_json"]) == before
    assert json.loads(result["signal_json"])[word_break.FIELD]["retry_count"] == 1


# F7
def write_tone(path, sr=48000, seconds=1.2, silences=((.28,.60),)):
    import soundfile as sf
    wave = np.sin(np.arange(round(seconds*sr))*2*np.pi*200/sr).astype("float32")*.1
    for lo, hi in silences:
        wave[round(lo*sr):round(hi*sr)] = 0
    sf.write(path, wave, sr)


def measure_with_spans(tmp_path, monkeypatch, spans, source="Khoảnh khắc kỳ diệu"):
    from abook.webui import word_timing
    monkeypatch.setattr(word_timing, "model_dir", lambda:tmp_path)
    monkeypatch.setattr(word_break, "_aligner", lambda _folder:type("Aligner", (), {"align":lambda _self,wave,text:(spans,.99)})())
    write_tone(tmp_path/"take.wav")
    return word_break.measure(tmp_path/"take.wav", "vieneu@3.8.3/Ngọc Linh", source, source, lambda s:s)


def test_syllable_aligned_inside_the_silence_is_not_a_word_break(tmp_path, monkeypatch):
    # "gọi" 6.20-6.28 inside the comma pause 6.010-6.315: CTC misplaced the syllable, nobody paused in the word.
    gate = measure_with_spans(tmp_path, monkeypatch, [[.08,.28],[.45,.55],[.62,.8],[.8,.95]])
    assert gate["status"] == "measured"
    swallowed = gate["boundaries"][0]
    assert swallowed["gap_ms"] > 72.8
    assert swallowed["status"] == "inconclusive" and not swallowed["flagged"]
    assert not gate["fired"]
    assert gate["flagged_words"] == 0


def test_real_pause_between_syllables_still_fires(tmp_path, monkeypatch):
    gate = measure_with_spans(tmp_path, monkeypatch, [[.08,.28],[.60,.8],[.8,.95],[.95,1.1]])
    assert gate["fired"] and gate["boundaries"][0]["flagged"]


# F8
def test_preview_synthesis_skips_the_gate_measurement(tmp_path, monkeypatch):
    pipeline, chapter, row, engine = scenario(tmp_path, monkeypatch, ["gap"])
    monkeypatch.setattr(word_break, "measure", lambda *a,**k:pytest.fail("preview must not load the aligner"))
    _checksum, metrics, _seed = pipeline.tts.synthesize_atomic(row, tmp_path/"preview.wav", seed_salt="x", measure_word_break=False)
    assert word_break.FIELD not in metrics
    import abook.webui.reading_preview as preview
    assert "measure_word_break=False" in Path(preview.__file__).read_text(encoding="utf8")


def test_pool_budget_counts_the_aligner_each_worker_loads():
    from abook.perceptual_qa import PERCEPTUAL_WORKER_RAM_GB
    from abook.pipeline import TTS_WORKER_RAM_GB
    assert TTS_WORKER_RAM_GB >= PERCEPTUAL_WORKER_RAM_GB + .28


# F9
@pytest.mark.parametrize("error", [KeyError("x"), IndexError("x"), TypeError("x"), MemoryError()])
def test_measure_failure_is_inconclusive_not_a_tts_failure(tmp_path, monkeypatch, error):
    def boom(*_args):
        raise error
    monkeypatch.setattr(word_break, "plan", boom)
    monkeypatch.setattr(word_break.time, "sleep", lambda _seconds:None)
    gate = word_break.measure(tmp_path/"none.wav", "vieneu@3.8.3/Ngọc Linh", TEXT, TEXT, lambda s:s)
    assert gate["status"] == "inconclusive" and not gate["fired"]


def test_measure_rides_out_a_passing_memory_shortage(tmp_path, monkeypatch):
    real = word_break.plan
    state = dict(left=1)
    def once(*args):
        if state["left"]:
            state["left"] = 0
            raise MemoryError()
        return real(*args)
    monkeypatch.setattr(word_break, "plan", once)
    monkeypatch.setattr(word_break.time, "sleep", lambda _seconds:None)
    gate = measure_with_spans(tmp_path, monkeypatch, [[.08,.28],[.60,.8],[.8,.95],[.95,1.1]])
    assert gate["status"] == "measured"


# F10
def test_rank_counts_flagged_words_before_gap_of_flagged_boundaries():
    rank = BookPipeline._usable_take_rank
    def take(*boundaries):
        return {word_break.FIELD: dict(status="measured", fired=any(f for _, f, _ in boundaries),
                                       flagged_words=len({w for _, f, w in boundaries if f}),
                                       max_gap_ms=max(g for g, _, _ in boundaries),
                                       boundaries=[dict(gap_ms=g, flagged=f) for g, f, _ in boundaries])}
    # One flagged word beats two, however long a natural closure elsewhere in the take runs.
    assert rank(take((300., False, 0), (100., True, 1))) < rank(take((80., True, 0), (80., True, 1)))
    # Among equal counts only flagged boundaries compare.
    assert rank(take((90., True, 0), (300., False, 1))) < rank(take((100., True, 0)))
    assert rank(take((90., False, 0))) < rank(take((90., True, 0)))


# F11
def test_gate_is_bound_to_the_tempo_it_was_calibrated_at():
    table = copy.deepcopy(voice_balance.load_table())
    table["voices"]["vieneu@3.8.3/Đức Trí"]["r"] = 1.3
    with pytest.raises(voice_balance.VoiceBalanceError, match="calibrated_r"):
        voice_balance._validate(table)
    table = copy.deepcopy(voice_balance.load_table())
    table["voices"]["vieneu@3.8.3/Ngọc Linh"]["word_break_gate"]["calibrated_x"] = 1.1
    with pytest.raises(voice_balance.VoiceBalanceError, match="calibrated_x"):
        voice_balance._validate(table)
    table = copy.deepcopy(voice_balance.load_table())
    del table["voices"]["vieneu@3.8.3/Ngọc Linh"]["word_break_gate"]["calibrated_r"]
    with pytest.raises(voice_balance.VoiceBalanceError):
        voice_balance._validate(table)


# F12
def test_missing_aligner_is_reported_once(tmp_path, monkeypatch):
    from abook.webui import word_timing
    pipeline, chapter, row, engine = scenario(tmp_path, monkeypatch, ["gap"])
    monkeypatch.setattr(word_timing, "model_dir", lambda:None)
    logged = []
    pipeline.log = logged.append
    pipeline._process_single_segment(row, chapter)
    pipeline._note_word_break_gate({"status":"inconclusive", "reason":word_break.ALIGNER_MISSING})
    gate = json.loads(pipeline.db.get_segment(int(row["id"]))["signal_json"])[word_break.FIELD]
    assert gate["status"] == "inconclusive" and gate["reason"] == word_break.ALIGNER_MISSING
    assert sum("thước căn chỉnh" in line for line in logged) == 1
    with pipeline.db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM runtime_events WHERE code='WORD_BREAK_ALIGNER_MISSING'").fetchone()[0] == 1
