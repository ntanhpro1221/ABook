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
    pipeline._check_finished_book_levels([{"id": 1, "chapter_index": 1, "output_mp3": "synthetic.mp3"}])
    assert pipeline._book_levels["verdict"] == "warning"
    assert (tmp_path/"book_levels.json").is_file()
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
