"""Meter chỉ đọc trên tín hiệu tổng hợp, cảnh báo không thành cổng chặn."""
from __future__ import annotations

import io
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from abook.book_levels import measure_finished_book, perceived_level
from abook.pipeline import BookPipeline


def test_relative_phon_gain_silence_and_short_input():
    rate = 48000
    x = .03*np.sin(2*np.pi*1000*np.arange(2*rate)/rate)
    assert perceived_level(x*2, rate)-perceived_level(x, rate) == pytest.approx(6, abs=.7)
    assert perceived_level(np.r_[np.zeros(rate), x, np.zeros(rate)], rate) == pytest.approx(perceived_level(x, rate), abs=.05)
    assert perceived_level(np.zeros(rate), rate) is None
    assert perceived_level(x[:1000], rate) is None


def _book(delta):
    rate = 48000
    t = np.arange(24*rate)/rate
    files = {}
    chapters = []
    for i in (1, 2):
        x = .03*10**(delta*(i-1)/20)*np.sin(2*np.pi*1000*t)
        data = io.BytesIO()
        sf.write(data, x, rate, format="WAV", subtype="FLOAT")
        files[i] = data.getvalue()
        chapters.append({"id": i, "file": i, "segments": [
            {"voice": str(i), "stable_id": f"{i}_{j}", "start": 2*j, "end": 2*j+2, "volume": "normal"}
            for j in range(12)]})
    return chapters, lambda i: sf.SoundFile(io.BytesIO(files[i]))


def test_finished_signal_warning_and_pass_are_deterministic():
    chapters, opener = _book(0)
    a = measure_finished_book(chapters, opener)
    assert a == measure_finished_book(chapters, opener)
    assert a["verdict"] == "pass"
    assert all(v["n"] == 12 and len(v["ci95_phon"]) == 2 for v in a["voices"].values())
    chapters, opener = _book(6)
    warning = measure_finished_book(chapters, opener)
    assert warning["verdict"] == "warning"
    assert "VOICE_LEVEL_SPREAD" in warning["flags"]
    assert "CHAPTER_LEVEL_DELTA" in warning["flags"]


def test_missing_coverage_never_claims_pass():
    assert measure_finished_book([])["verdict"] == "insufficient_data"


def test_meter_failure_does_not_block_pipeline(tmp_path, monkeypatch):
    import abook.book_levels as levels
    import abook.webui.store as store
    monkeypatch.setattr(store, "chapter_script", lambda *a: {"timed": True, "segments": []})
    monkeypatch.setattr(levels, "measure_finished_book", lambda *a: (_ for _ in ()).throw(RuntimeError("synthetic failure")))
    artifacts = []
    pipeline = object.__new__(BookPipeline)
    pipeline.paths = SimpleNamespace(root=tmp_path, reports=tmp_path)
    pipeline.db = SimpleNamespace(list_voice_profiles=lambda: [], list_segments=lambda: [],
        register_artifact=lambda **kw: artifacts.append(kw), event=lambda *a: None)
    pipeline.log = lambda *a: None
    audio = tmp_path/'synthetic.mp3'
    audio.write_bytes(b'current audio')
    pipeline._check_finished_book_levels([{"id": 1, "chapter_index": 1, "output_mp3": str(audio)}])
    assert pipeline._book_levels["verdict"] == "warning"
    assert pipeline._book_levels['error'] == 'synthetic failure'
    assert (tmp_path/"levelQa.json").is_file()
    assert artifacts[0]["kind"] == "book_qa"


def test_level_warning_never_changes_book_completion(tmp_path):
    pipeline = object.__new__(BookPipeline)
    updates = []
    pipeline.paths = SimpleNamespace(root=tmp_path, output=tmp_path)
    pipeline.settings = {"audio": {"create_m3u8": False}}
    pipeline.db = SimpleNamespace(list_chapters=lambda: [{"id":1, "status":"completed", "output_mp3":"synthetic.mp3"}],
        update_book=lambda **kw: updates.append(kw), book=lambda: {"title":"Synthetic"})
    pipeline._state = lambda *a: None
    pipeline.notifier = SimpleNamespace(notify=lambda *a, **kw: None)
    pipeline._check_finished_book_levels = lambda *a: setattr(pipeline, "_book_levels", {"verdict":"warning"})
    pipeline._finalize_book()
    assert pipeline._book_levels["verdict"] == "warning"
    assert updates == [{"status":"completed", "stage":"completed", "error":None}]


def test_independent_holdout_excludes_previously_measured_lines():
    chapters, opener = _book(0)
    first = measure_finished_book(chapters, opener)
    holdout = measure_finished_book(chapters, opener, seed='holdout-v2', exclude=set(first['measured_ids']))
    assert not set(holdout['measured_ids']) & set(first['measured_ids'])
    assert holdout['verdict'] == 'insufficient_data'


def test_zero_eligible_lines_is_reported_without_a_voice_delta():
    chapters, opener = _book(0)
    chapters[0]['segments'].append(dict(voice='sparse', stable_id='sparse', start=0, end=.1, volume='soft'))
    result = measure_finished_book(chapters, opener)
    assert result['insufficient_voices']['sparse'] == 0
    assert 'sparse' not in result['voices']


def test_detector_warns_without_changing_audio_and_reuses_unchanged_measurement(tmp_path, monkeypatch):
    from abook import book_levels, voice_balance
    from abook.webui import store
    from abook.io_utils import sha256_file
    audio = tmp_path/'finished.mp3'
    audio.write_bytes(b'current verified master')
    monkeypatch.setattr(voice_balance, 'voice_key_for_profile', lambda _: 'synthetic')
    monkeypatch.setattr(store, 'chapter_script', lambda *a: dict(timed=True, segments=[dict(id=7, start=0, end=2)]))
    calls = []
    def measure(inputs):
        calls.append(inputs)
        return dict(meter=book_levels.METER, verdict='warning', flags=['VOICE_LEVEL_SPREAD'],
                    voice_spread_phon=8, chapters={'1': {'delta_phon': 3}})
    monkeypatch.setattr(book_levels, 'measure_finished_book', measure)
    pipeline = object.__new__(BookPipeline)
    pipeline.paths = SimpleNamespace(root=tmp_path, reports=tmp_path/'reports')
    pipeline.db = SimpleNamespace(list_voice_profiles=lambda: [dict(id=1)],
        list_segments=lambda: [dict(id=7, voice_profile_id=1, stable_id='stable')],
        register_artifact=lambda **kw: None, event=lambda *a: None)
    pipeline.log = lambda *a: None
    pipeline._publish_verified_chapter = lambda *a: pytest.fail('detector must never master audio')
    chapters = [dict(id=1, output_mp3=str(audio))]
    before = sha256_file(audio)
    pipeline._check_finished_book_levels(chapters)
    first = pipeline._book_levels
    assert first['verdict'] == 'warning'
    assert 'corrections' not in first and 'rounds' not in first
    assert first['audio_sha256'] == {'1': before}
    assert sha256_file(audio) == before
    pipeline._check_finished_book_levels(chapters)
    assert len(calls) == 1
    assert pipeline._book_levels == first
    audio.write_bytes(b'new verified master')
    pipeline._check_finished_book_levels(chapters)
    assert len(calls) == 2
    assert pipeline._book_levels['audio_sha256']['1'] == sha256_file(audio)
