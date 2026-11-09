"""Same input and seed, same audio: whatever the machine's load, and wherever a crash lands.

Every synthesis call keeps a ledger (the take session). A resume puts the segment back where
the call found it and replays the call; takes it already made are read back, the one it was
making is synthesized again from its reserved seed. Out-of-memory errors rerun the same take
on their own budget. Each case below compares the resumed or loaded run with an unbroken one,
byte for byte (the WAV checksum) and record for record.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook import word_break
from abook.database import ProjectDB
from abook.pipeline import CriticalResourceStop
from tests.test_word_break_gate import (
    OOM, RETRY_SALT, CANDIDATE_SALT, TtsStageDone, candidate_outcome, resume_through_chapter_loop,
    seeded, stable,
)


def outcome(pipeline, row):
    """Everything the book keeps about this segment, except clocks and file names."""
    current = pipeline.db.get_segment(int(row["id"]))
    with pipeline.db.transaction() as conn:
        artifacts = conn.execute(
            "SELECT artifact_key,kind,sha256,metadata_json FROM artifacts WHERE kind NOT IN ('take_session') "
            "ORDER BY artifact_key").fetchall()
    ledger = [stable(dict(key=item["artifact_key"], kind=item["kind"], sha=item["sha256"],
                          meta={k: v for k, v in json.loads(item["metadata_json"] or "{}").items() if k != "path"}))
              for item in artifacts]
    session = pipeline.db.artifact_by_key(pipeline._take_session_key(row))
    return dict(sha=current["wav_sha256"], seed=current["generation_seed"], status=current["status"],
                duration=current["wav_duration"], warning=current["warning_code"],
                error=current["error"], session=json.loads(session["metadata_json"]),
                segment_record={key: current[key] for key in current.keys()
                                if key not in {"updated_at", "wav_path", "signal_json"}},
                audio_bytes=Path(current["wav_path"]).read_bytes(),
                delivery=current["generation_delivery_mode"], round=current["generation_repair_round"],
                signal=stable(json.loads(current["signal_json"] or "{}")), ledger=ledger,
                bytes_ok=bool(current["wav_path"]) and _sha(current["wav_path"]) == current["wav_sha256"])


def _sha(path):
    import hashlib
    from pathlib import Path
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


PLANS = {
    # No word-break gate fires on any of these.
    "plain_first_take": dict(plan={}, ungated=True),
    "plain_outlier_then_clean": dict(plan={}, ungated=True, outliers=("primary_0",)),
    "plain_two_outliers": dict(plan={}, ungated=True, outliers=("primary_0", "primary_1")),
    "plain_every_attempt_refused": dict(plan={}, ungated=True, retries=2, outliers=("primary_0", "primary_1"), refuse_split=True),
    "gated_clean": dict(plan={}),
    # The gate fires.
    "gated_retry_wins": dict(plan={"primary_0": "gap", RETRY_SALT: "clean"}),
    "gated_first_take_wins": dict(plan={"primary_0": "gap", RETRY_SALT: "big"}),
    "gated_retry_refused_then_new_attempt": dict(plan={"primary_0": "gap", RETRY_SALT: "clean"},
                                                 outliers=(RETRY_SALT,)),
}


def build(tmp_path, monkeypatch, config):
    config = dict(config)
    refuse_split = config.pop("refuse_split", False)
    ungated = config.pop("ungated", False)
    source = config.pop("source", None)
    pipeline, chapter, row, engine = seeded(tmp_path, monkeypatch, **config)
    if source is not None:
        with pipeline.db.transaction() as conn:
            conn.execute("UPDATE segments SET text=? WHERE id=?", (source, int(row["id"])))
        row = pipeline.db.get_segment(int(row["id"]))
    if ungated:
        with pipeline.db.transaction() as conn:
            conn.execute("UPDATE voice_profiles SET preset_name='Đoan Trang'")
    if refuse_split:
        from abook.audio_io import AudioQualityError

        def refuse(*_args, **_kwargs):
            raise AudioQualityError("no natural boundary outside pronunciation spans")
        pipeline._synthesize_split = refuse
    salts = []
    real = pipeline.tts.synthesize_atomic

    def logged(*args, **kwargs):
        salts.append(str(kwargs.get("seed_salt", "")))
        return real(*args, **kwargs)
    pipeline.tts.synthesize_atomic = logged
    pipeline.tts._real_synthesize = logged
    pipeline._salts = salts
    return pipeline, chapter, row, engine


WRAPPED = ("_accept_retained_take", "_close_take_session", "_session_attempt_path", "_session_synthesis",
           "_recover_from_memory_pressure", "_keep_usable_take", "_checkpoint_segment_candidate_signal")


def reopen(pipeline, row):
    """A dead process: only SQLite and the disk survive, and recovery runs first."""
    for name in WRAPPED:
        pipeline.__dict__.pop(name, None)
    pipeline.tts.synthesize_atomic = pipeline.tts._real_synthesize
    db = ProjectDB(pipeline.paths.db)
    pipeline.db = db
    pipeline.tts.db = db
    pipeline._recover()
    return db.get_segment(int(row["id"]))


def install(pipeline, kind, salt):
    """One fault: a kill (SystemExit, past every handler) or memory taken by another program."""
    real = pipeline.tts._real_synthesize
    state = pipeline._fault_state = dict(left=1)

    def fire():
        state["left"] = 0
        raise SystemExit(f"crash at {kind} {salt}")

    def wrap(name, *, after, when=lambda *a, **k: True, owner=None):
        owner = pipeline if owner is None else owner
        original = getattr(owner, name)

        def wrapped(*args, **kwargs):
            hit = state["left"] and when(*args, **kwargs)
            if hit and not after:
                fire()
            result = original(*args, **kwargs)
            if hit and after:
                fire()
            return result
        setattr(owner, name, wrapped)

    def synth(*args, **kwargs):
        mine = str(kwargs.get("seed_salt", "")) == salt
        if mine and kind == "kill_during_synthesis" and state["left"]:
            fire()
        if mine and kind in {"oom_once", "oom_lasting"} and (state["left"] or kind == "oom_lasting"):
            state["left"] = 0
            raise RuntimeError(OOM)
        result = real(*args, **kwargs)
        if mine and kind == "kill_after_synthesis" and state["left"]:
            fire()
        return result
    pipeline.tts.synthesize_atomic = synth
    if kind == "oom_once":
        pipeline._recover_from_memory_pressure = lambda _where, _error: True
    elif kind == "oom_lasting":
        pipeline._recover_from_memory_pressure = lambda _where, _error: False
    elif kind == "kill_after_reservation":
        if salt.startswith("word_break_candidate_"):
            wrap("reserve_word_break_retry", owner=pipeline.db, after=True,
                 when=lambda **kwargs: kwargs["metadata"]["seed_salt"] == salt)
        else:
            wrap("_session_attempt_path", after=True, when=lambda _row, _session, s, _fresh: s == salt)
    elif kind == "kill_after_record":
        if salt.startswith("word_break_candidate_"):
            wrap("finish_word_break_retry", owner=pipeline.db, after=True)
        else:
            wrap("_session_synthesis", after=True, when=lambda _row, _session, s, _synth: s == salt)
    elif kind == "before_accept":
        wrap("_accept_retained_take", after=False)
    elif kind == "after_accept":
        wrap("_accept_retained_take", after=True)
    elif kind == "before_close":
        wrap("_close_take_session", after=False)
    elif kind in {"before_candidate_accept", "after_candidate_accept"}:
        wrap("_checkpoint_segment_candidate_signal", after=kind == "after_candidate_accept")
    elif kind not in {"kill_during_synthesis", "kill_after_synthesis", "none"}:
        raise AssertionError(kind)


CLARITY = dict(seed_salt_prefix="asr_clarity_repair_0", repair_short_utterance=True, asr_repair_round=0)


def run(tmp_path, monkeypatch, config, kind="none", salt="", *, clarity=False):
    pipeline, chapter, row, engine = build(tmp_path, monkeypatch, config)
    call = {}
    if clarity:
        from abook.pipeline import DELIVERY_CLARITY, SEGMENT_AUDIO_QUALITY_STAGE, QUALITY_SCOPE_SEGMENT
        from abook.quality_policy import QUALITY_POLICY_VERSION
        # A repair of a take the primary call already made and accepted.
        pipeline._process_single_segment(row, chapter)
        row = pipeline.db.get_segment(int(row["id"]))
        # Two independent defects make a new gated take preferable to this incumbent.
        # Otherwise the selector correctly keeps an ASR-refused clean take over a new gap.
        incumbent_signal = json.loads(row["signal_json"])
        incumbent_signal.update(pace_outlier=True, chars_per_second=99.0)
        pipeline.db.mark_signal_passed(
            int(row["id"]), wav_path=Path(row["wav_path"]), wav_sha256=row["wav_sha256"],
            duration=row["wav_duration"], signal=incumbent_signal, generation_seed=row["generation_seed"],
        )
        row = pipeline.db.get_segment(int(row["id"]))
        pipeline.db.record_quality_check(
            scope=QUALITY_SCOPE_SEGMENT, stage=SEGMENT_AUDIO_QUALITY_STAGE, segment_id=int(row["id"]),
            artifact_sha256=row["wav_sha256"], policy_hash=pipeline.quality_policy_hash,
            policy_version=QUALITY_POLICY_VERSION, verdict="fail", metrics={"reason": "ASR_MISMATCH"},
        )
        call = dict(CLARITY, delivery_mode=DELIVERY_CLARITY)
    install(pipeline, kind, salt)
    try:
        pipeline._process_single_segment(row, chapter, **call)
    except (SystemExit, CriticalResourceStop):
        # A kill, or a stop at a safe checkpoint when the shortage would not end.
        row = reopen(pipeline, row)
        resume_through_chapter_loop(pipeline, chapter)
    assert kind == "none" or not pipeline._fault_state["left"], f"{kind} {salt} never happened"
    return outcome(pipeline, row), pipeline, row


def reference(tmp_path, monkeypatch, name):
    expected, pipeline, _row = run(tmp_path / "unbroken", monkeypatch, PLANS[name])
    assert expected["bytes_ok"]
    return expected, list(dict.fromkeys(pipeline._salts))


PER_SALT = ["kill_after_reservation", "kill_during_synthesis", "kill_after_synthesis", "kill_after_record",
            "oom_once", "oom_lasting"]
ONCE = ["before_accept", "after_accept", "before_close"]


@pytest.mark.parametrize("name", PLANS)
@pytest.mark.parametrize("kind", PER_SALT)
def test_every_attempt_survives_kills_and_memory_shortages(tmp_path, monkeypatch, name, kind):
    expected, salts = reference(tmp_path, monkeypatch, name)
    for salt in salts:
        got, _pipeline, _row = run(tmp_path / f"{kind}_{salt}", monkeypatch, PLANS[name], kind, salt)
        assert got == expected, f"{name}: {kind} at {salt}"


@pytest.mark.parametrize("name", PLANS)
@pytest.mark.parametrize("kind", ONCE)
def test_the_quality_decision_survives_kills(tmp_path, monkeypatch, name, kind):
    expected, _salts = reference(tmp_path, monkeypatch, name)
    if kind in {"before_accept", "after_accept"} and expected["status"] != "signal_passed":
        pytest.skip("this plan never accepts a take")
    got, _pipeline, _row = run(tmp_path / kind, monkeypatch, PLANS[name], kind)
    assert got == expected


def test_reference_runs_cover_both_kinds_of_segment(tmp_path, monkeypatch):
    seen = {}
    for name in PLANS:
        expected, salts = reference(tmp_path / name, monkeypatch, name)
        seen[name] = (expected, salts)
    assert seen["plain_first_take"][1] == ["primary_0"]
    assert seen["plain_outlier_then_clean"][1] == ["primary_0", "primary_1"]
    assert seen["plain_every_attempt_refused"][0]["status"] == "failed"
    assert seen["plain_first_take"][0]["signal"][word_break.FIELD]["status"] == "off"
    assert RETRY_SALT in seen["gated_retry_wins"][1]
    assert not seen["plain_first_take"][0]["signal"].get(word_break.FIELD, {}).get("fired")
    assert seen["gated_retry_wins"][0]["signal"][word_break.FIELD]["retry_count"] == 1


# F13: the probe from wbgate2, now the opposite assertion.
def test_first_take_out_of_memory_keeps_its_seed(tmp_path, monkeypatch):
    got, pipeline, row = run(tmp_path, monkeypatch, PLANS["plain_first_take"], "oom_once", "primary_0")
    assert got["seed"] == pipeline.tts.generation_seed(row, "primary_0")
    # The refused call never reached the engine; the one that did used the same seed.
    assert pipeline._salts == ["primary_0"]


@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("native", [False, True])
def test_transient_shortage_retries_inside_the_call_without_a_stop(tmp_path, monkeypatch, wrapped, native):
    from abook.audio_io import AudioQualityError
    pipeline, chapter, row, _engine = build(tmp_path, monkeypatch, PLANS["plain_first_take"])
    original = pipeline.tts.synthesize_atomic
    calls = []
    recoveries = []

    def synthesize(*args, **kwargs):
        calls.append(kwargs["seed_salt"])
        if len(calls) < 3:
            error = MemoryError() if native else RuntimeError(OOM)
            if wrapped:
                raise AudioQualityError("engine failed") from error
            raise error
        return original(*args, **kwargs)

    pipeline.tts.synthesize_atomic = synthesize
    pipeline._recover_from_memory_pressure = lambda *args: recoveries.append(args) or True
    pipeline._process_single_segment(row, chapter)
    assert calls == ["primary_0"] * 3
    assert len(recoveries) == 2
    assert pipeline.db.get_segment(int(row["id"]))["status"] == "signal_passed"


def test_lasting_shortage_stops_instead_of_spending_an_attempt(tmp_path, monkeypatch):
    pipeline, chapter, row, _engine = build(tmp_path, monkeypatch, PLANS["plain_first_take"])
    install(pipeline, "oom_lasting", "primary_0")
    with pytest.raises(CriticalResourceStop):
        pipeline._process_single_segment(row, chapter)
    assert "primary_1" not in pipeline._salts


# F14: the case review named - no gate, crash before the take is accepted.
def test_plain_take_killed_before_accept_is_not_frozen_as_failed(tmp_path, monkeypatch):
    got, pipeline, row = run(tmp_path, monkeypatch, PLANS["plain_first_take"], "before_accept")
    assert got["status"] == "signal_passed"
    assert not got["signal"].get("quality_pending")


def test_finished_takes_are_read_back_not_synthesized_again(tmp_path, monkeypatch):
    """A replay must not depend on the engine repeating itself: only the take in flight reruns."""
    pipeline, chapter, row, _engine = build(tmp_path, monkeypatch, PLANS["plain_two_outliers"])
    install(pipeline, "kill_during_synthesis", "primary_2")
    with pytest.raises(SystemExit):
        pipeline._process_single_segment(row, chapter)
    before = list(pipeline._salts)
    row = reopen(pipeline, row)
    resume_through_chapter_loop(pipeline, chapter)
    assert pipeline._salts[len(before):] == ["primary_2"]


def test_a_finished_call_is_not_replayed(tmp_path, monkeypatch):
    got, pipeline, row = run(tmp_path, monkeypatch, PLANS["plain_every_attempt_refused"])
    assert got["status"] == "failed"
    calls = len(pipeline._salts)
    resume_through_chapter_loop(pipeline, pipeline.db.list_chapters()[0])
    assert len(pipeline._salts) == calls


def test_an_edited_source_is_not_answered_by_the_old_call(tmp_path, monkeypatch):
    pipeline, chapter, row, _engine = build(tmp_path, monkeypatch, PLANS["plain_outlier_then_clean"])
    install(pipeline, "kill_during_synthesis", "primary_1")
    with pytest.raises(SystemExit):
        pipeline._process_single_segment(row, chapter)
    row = reopen(pipeline, row)
    assert pipeline._owed_take_session(row) is not None
    edited = {**dict(row), "listener_retakes": int(row["listener_retakes"]) + 1}
    assert pipeline._owed_take_session(edited) is None


# Candidate path: the same memory rule.
def run_candidate(tmp_path, monkeypatch, kind):
    pipeline, chapter, row, engine = build(tmp_path, monkeypatch, dict(plan={CANDIDATE_SALT: "clean"}))
    pipeline._process_single_segment(row, chapter)
    row = pipeline.db.get_segment(int(row["id"]))
    candidate = pipeline._allocate_segment_candidate(row, 0, 2)
    install(pipeline, kind, CANDIDATE_SALT)
    try:
        pipeline._process_segment_candidate(row, candidate, chapter)
    except CriticalResourceStop:
        row = reopen(pipeline, row)
        pipeline._process_segment_candidate(row, candidate, chapter)
    assert kind == "none" or not pipeline._fault_state["left"]
    return candidate_outcome(pipeline, row, candidate)


@pytest.mark.parametrize("kind", ["oom_once", "oom_lasting"])
def test_candidate_memory_shortage_keeps_the_candidate_seed(tmp_path, monkeypatch, kind):
    expected = run_candidate(tmp_path / "a", monkeypatch, "none")
    assert expected["state"] == "signal_passed" and expected["attempt"] == 0
    assert run_candidate(tmp_path / "b", monkeypatch, kind) == expected


CLARITY_PLANS = {
    "clarity_plain": dict(plan={}, ungated=True, outliers=("asr_clarity_repair_0_0",)),
    "clarity_gated": dict(plan={"asr_clarity_repair_0_0": "gap", RETRY_SALT: "clean"}),
}


@pytest.mark.parametrize("name", CLARITY_PLANS)
@pytest.mark.parametrize("kind", ["kill_during_synthesis", "kill_after_record", "oom_once", "before_accept"])
def test_interrupted_clarity_call_replays_as_the_same_round(tmp_path, monkeypatch, name, kind):
    expected, pipeline, _row = run(tmp_path / "unbroken", monkeypatch, CLARITY_PLANS[name], clarity=True)
    assert expected["delivery"] == "clarity" and expected["round"] == 0
    salts = [s for s in dict.fromkeys(pipeline._salts) if not s.startswith("primary_")]
    for salt in (salts if kind != "before_accept" else [""]):
        got, _p, _r = run(tmp_path / f"{kind}_{salt}", monkeypatch, CLARITY_PLANS[name], kind, salt, clarity=True)
        assert got == expected, f"{name}: {kind} at {salt}"


def candidate_run(tmp_path, monkeypatch, config, kind="none", salt=""):
    pipeline, chapter, row, _engine = build(tmp_path, monkeypatch, config)
    pipeline._process_single_segment(row, chapter)
    row = pipeline.db.get_segment(int(row["id"]))
    pipeline._salts.clear()
    candidate = pipeline._allocate_segment_candidate(row, 0, 2)
    install(pipeline, "none" if kind == "candidate_reserved" else kind, salt)
    try:
        if kind == "candidate_reserved":
            pipeline._fault_state["left"] = 0
            raise SystemExit("candidate reserved")
        pipeline._process_segment_candidate(row, candidate, chapter)
    except (SystemExit, CriticalResourceStop):
        row = reopen(pipeline, row)
        pipeline._process_segment_candidate(row, candidate, chapter)
    assert kind == "none" or not pipeline._fault_state["left"], f"{kind} {salt} never happened"
    current = pipeline.db.get_segment_candidate(int(candidate["id"]))
    result = candidate_outcome(pipeline, row, candidate)
    result["bytes_sha"] = _sha(current["wav_path"])
    result["audio_bytes"] = Path(current["wav_path"]).read_bytes()
    assert result["bytes_sha"] == result["sha"]
    return result, list(dict.fromkeys(pipeline._salts))


@pytest.mark.parametrize("ungated", [True, False])
@pytest.mark.parametrize("kind", ["candidate_reserved", "kill_during_synthesis", "kill_after_synthesis",
                                  "oom_once", "oom_lasting", "before_candidate_accept", "after_candidate_accept"])
def test_every_candidate_attempt_replays_its_reservation(tmp_path, monkeypatch, ungated, kind):
    from abook.pipeline import BookPipeline, PRONUNCIATION_DELIVERY_LOCKED
    salts = [BookPipeline._segment_candidate_seed_salt(0, i, PRONUNCIATION_DELIVERY_LOCKED) for i in range(3)]
    config = dict(plan={}, ungated=ungated, outliers=tuple(salts[:2]))
    expected, used = candidate_run(tmp_path / "unbroken", monkeypatch, config)
    assert used == salts
    per_salt = kind in {"kill_during_synthesis", "kill_after_synthesis", "oom_once", "oom_lasting"}
    for salt in used if per_salt else [""]:
        got, _used = candidate_run(tmp_path / f"{kind}_{salt}", monkeypatch, config, kind, salt)
        assert got == expected


@pytest.mark.parametrize("candidate", [False, True])
@pytest.mark.parametrize("ungated", [True, False])
@pytest.mark.parametrize("kind", ["kill_during_synthesis", "kill_after_synthesis", "oom_once", "oom_lasting"])
def test_split_parts_keep_their_seeds_across_faults(tmp_path, monkeypatch, candidate, ungated, kind):
    from tests.test_word_break_gate import TEXT
    from abook.pipeline import BookPipeline, PRONUNCIATION_DELIVERY_LOCKED
    salts = ([BookPipeline._segment_candidate_seed_salt(0, i, PRONUNCIATION_DELIVERY_LOCKED) for i in range(2)]
             if candidate else ["primary_0", "primary_1"])
    config = dict(plan={}, source=" ".join([TEXT] * 4), ungated=ungated, retries=2, outliers=tuple(salts))
    if candidate:
        expected, used = candidate_run(tmp_path / "unbroken", monkeypatch, config)
    else:
        expected, pipeline, _row = run(tmp_path / "unbroken", monkeypatch, config)
        used = list(dict.fromkeys(pipeline._salts))
    parts = [salt for salt in used if "_part_" in salt]
    assert len(parts) >= 2
    assert expected.get("status", expected.get("state")) == "signal_passed"
    for salt in parts:
        if candidate:
            got, _ = candidate_run(tmp_path / salt, monkeypatch, config, kind, salt)
        else:
            got, _pipeline, _row = run(tmp_path / salt, monkeypatch, config, kind, salt)
        assert got == expected
