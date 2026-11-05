"""Các câu giả chứng minh master giữ offset và neo trung bình cả sách."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from abook import voice_balance
from abook.audio_io import VOICE_BALANCE_FIELD, ChapterQualityError, assemble_chapter_atomic_with_metrics, level_segment
from abook.chapter_loudness import chapter_level_plan
from abook.config import build_settings
from abook.pipeline import BookPipeline


def row(chapter, seconds, offset, checksum="wave", **extra):
    return {"chapter_id": chapter, "stable_id": f"s{chapter}", "wav_sha256": checksum,
        "wav_duration": seconds, "signal_json": json.dumps({"level_speech_seconds": seconds,
        "applied_level_offset_db": offset}), **extra}


def test_weighted_relative_targets_and_cache_locality():
    settings = build_settings()
    rows = [row(1, 1, 3), row(2, 3, 0)]
    a = chapter_level_plan(rows, [], settings)
    assert a[1]["target_lufs"] == pytest.approx(-17.75)
    assert a[2]["target_lufs"] == pytest.approx(-20.75)
    assert sum(a[c]["speech_seconds"]*(a[c]["target_lufs"]+20) for c in a) == pytest.approx(0)
    assert a == chapter_level_plan(list(reversed(rows)), [], settings)
    b = chapter_level_plan([rows[0], row(2, 3, 0, checksum="new")], [], settings)
    assert a[1]["signature"] == b[1]["signature"]
    assert a[2]["signature"] != b[2]["signature"]
    c = chapter_level_plan([rows[0], row(2, 3, 1)], [], settings)
    assert all(c[k]["signature"] != a[k]["signature"] for k in a)


def test_split_parts_use_applied_offsets_and_speech_time():
    r = row(1, 99, 99)
    r["signal_json"] = json.dumps({"split_parts": [
        {"level_speech_seconds": 1, "applied_level_offset_db": 3},
        {"level_speech_seconds": 3, "applied_level_offset_db": 1}]})
    plan = chapter_level_plan([r, row(2, 4, 0)], [], build_settings())
    assert plan[1]["speech_seconds"] == 4
    assert plan[1]["chapter_offset_db"] == 1.5
    assert plan[1]["target_lufs"]-plan[2]["target_lufs"] == 1.5


def test_pipeline_refreshes_only_changed_chapter_signatures():
    pipeline = object.__new__(BookPipeline)
    pipeline.settings = build_settings()
    chapters = [{"id": i, "chapter_index": i, "status": "completed"} for i in (1, 2)]
    rows = [row(1, 2, 3), row(2, 2, 0)]
    artifacts = {}
    pipeline.db = SimpleNamespace(list_chapters=lambda: chapters, list_segments=lambda: rows,
        list_voice_profiles=lambda: [], artifact_by_key=lambda k: artifacts.get(k))
    pipeline._wait_pause_or_stop = lambda: None
    pipeline._apply_listener_overrides = lambda: set()
    pipeline._process_chapter = lambda *a: None
    pipeline._safe_export_reports = lambda **kw: None
    pipeline.emit = lambda *a: None
    pipeline.perceptual_qa = SimpleNamespace(unload=lambda: None)
    published = []
    def publish(ch):
        published.append(ch["id"])
        artifacts[f"chapter_mp3:{ch['id']}"] = {"metadata_json": json.dumps({"chapter_level": pipeline._chapter_level(ch)})}
    pipeline._publish_verified_chapter = publish
    pipeline._process_all_chapters(None)
    assert published == [1, 2]
    published.clear()
    pipeline._process_all_chapters(None)
    assert published == []
    rows[0]["wav_sha256"] = "changed audio, same mean"
    pipeline._process_all_chapters(None)
    assert published == [1]
    published.clear()
    rows[0] = row(1, 2, 2)
    pipeline._process_all_chapters(None)
    assert published == [1, 2]


@pytest.mark.parametrize("amplitude,limited", [(.03, False), (.7, True)])
def test_real_ffmpeg_preserves_applied_voice_difference(tmp_path: Path, monkeypatch, amplitude, limited):
    settings = build_settings()
    rate = int(settings["tts"]["sample_rate"])
    key = "synthetic"
    # Không gọi model hay dùng audio của sách thật.
    monkeypatch.setattr(voice_balance, "constants_for_key", lambda _: type("C", (), {"o_db": 3.0,
        "ref_lufs": voice_balance.level_lufs()})())
    t = np.arange(rate*5)/rate
    source = amplitude*np.sin(2*np.pi*440*t)
    source[:int(.03*rate)] *= np.linspace(0, 1, int(.03*rate))
    source[-int(.03*rate):] *= np.linspace(1, 0, int(.03*rate))
    segment = {VOICE_BALANCE_FIELD: key, "volume": "normal", "speaker": "", "emotion": "neutral", "intensity": 0}
    high, info = level_segment(source, rate, segment, settings)
    assert (info["peak_limited_db"] > 0) is limited
    assert info["applied_level_offset_db"] == pytest.approx(3-info["peak_limited_db"])
    assert np.max(abs(high)) <= 10**(settings["audio"]["segment_peak_dbfs"]/20)+1e-6
    rows = [row(1, info["level_speech_seconds"], info["applied_level_offset_db"]), row(2, 5, 0)]
    plan = chapter_level_plan(rows, [], settings)
    outputs = []
    for chapter, audio in ((1, high), (2, source)):
        wav = tmp_path/f"{chapter}.wav"
        sf.write(wav, audio, rate, subtype="PCM_16")
        result = assemble_chapter_atomic_with_metrics([wav], tmp_path/f"{chapter}.mp3", settings,
            title="Synthetic", book_title="Synthetic", track=chapter, target_lufs=plan[chapter]["target_lufs"])
        outputs.append(result.quality.integrated_loudness_lufs)
        assert result.quality.true_peak_db <= settings["audio"]["true_peak_db"]+.5
    assert outputs[0]-outputs[1] == pytest.approx(info["applied_level_offset_db"], abs=.15)
    if not limited:
        assert outputs[0]-outputs[1] == pytest.approx(3, abs=.15)


def test_real_ffmpeg_chapter_peak_limiter_keeps_ceiling_at_shifted_target(tmp_path):
    settings = build_settings()
    rate = int(settings["tts"]["sample_rate"])
    t = np.arange(8*rate)/rate
    x = .008*np.sin(2*np.pi*440*t)+.7*np.exp(-((t-4)/.004)**2)*np.sin(2*np.pi*1000*t)
    wav = tmp_path/"crest.wav"
    sf.write(wav, x, rate, subtype="PCM_16")
    output = tmp_path/"crest.mp3"
    output.write_bytes(b"previous verified artifact")
    with pytest.raises(ChapterQualityError, match="loudness off target") as error:
        assemble_chapter_atomic_with_metrics([wav], output, settings,
            title="Synthetic", book_title="Synthetic", track=1, target_lufs=-17)
    q = error.value.metrics
    # Đích không đạt được mà vẫn giữ trần: cổng QA từ chối, không nới trần hay đè MP3 cũ.
    assert q["mastering_input_true_peak_db"]+(-17-q["mastering_input_lufs"]) > settings["audio"]["true_peak_db"]
    assert q["true_peak_db"] <= settings["audio"]["true_peak_db"]+.5
    assert output.read_bytes() == b"previous verified artifact"
