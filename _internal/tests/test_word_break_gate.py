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
    assert voice_balance.constants_for("vieneu", "3.8.3", "Ngọc Linh").word_break_gate == {"metric": "silence_ms", "threshold": 72.8}
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

    def generate_one(self, row, profile, seed, *, sampling, **kwargs):
        from vieneu_utils import phonemize_text as pt
        chunks = pt.normalize_to_chunks_v3(row["text"])
        phones = [pt._phonemize_cached(s) for s in chunks]
        self.calls.append(dict(text=row["text"], phones=phones, sampling=dict(sampling), seed=seed))
        pause = .12 if self.modes[min(len(self.calls)-1,len(self.modes)-1)] == "gap" else 0.
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


def test_crash_after_reservation_spends_budget_across_reopen(tmp_path, monkeypatch):
    pipeline, chapter, row, engine = scenario(tmp_path, monkeypatch, ["gap"])
    original = pipeline.tts.synthesize_atomic
    def interrupted(*args, **kwargs):
        if kwargs.get("seed_salt", "").startswith("word_break_candidate_"):
            raise SystemExit("crash after reservation")
        return original(*args, **kwargs)
    pipeline.tts.synthesize_atomic = interrupted
    with pytest.raises(SystemExit):
        pipeline._process_single_segment(row, chapter)
    reopened = ProjectDB(pipeline.paths.db)
    pipeline.db = reopened
    pipeline.tts.db = reopened
    pipeline.tts.synthesize_atomic = lambda *a,**k:pytest.fail("spent retry was regenerated after reopen")
    pipeline._process_single_segment(reopened.get_segment(int(row["id"])), chapter)
    assert len(engine.calls) == 1
    current = reopened.get_segment(int(row["id"]))
    gate = json.loads(current["signal_json"])[word_break.FIELD]
    assert gate["retry_count"] == 1
    assert gate["retry_state"] == "failed"
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
