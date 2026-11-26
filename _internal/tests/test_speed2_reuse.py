"""Finite repair budgets and content-addressed chapter reuse, without model inference."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import abook.pipeline as pipeline_module
from abook.database import ProjectDB
from abook.io_utils import sha256_file
from tests.test_pipeline_mock import (
    PassingShortVerifier,
    ScriptedShortTTS,
    _asr_result,
    _asr_signal_pipeline,
    _checkpoint_short_ceiling_incumbent,
    _short_tts_pipeline,
)


def _exhausted(tmp_path):
    pipeline, chapter, row = _short_tts_pipeline(tmp_path, repair_rounds=2)
    endpoint = {"duration": 0.96, "generation_ceiling_hit": 1.0,
                "generation_endpoint_active": 1.0, "trailing_rms": 0.05}
    _checkpoint_short_ceiling_incumbent(pipeline, row)
    scripted = ScriptedShortTTS([endpoint, endpoint])
    pipeline.tts = scripted.bind(pipeline.settings, pipeline.db)
    verifier = PassingShortVerifier()
    pipeline._verify_chapter_audio(chapter, verifier)
    assert pipeline.db.get_segment(int(row["id"]))["status"] == "failed"
    return pipeline, chapter, row, scripted, verifier


def test_exhausted_retry_survives_reopen_without_erasing_evidence(tmp_path, monkeypatch):
    pipeline, _, row, scripted, verifier = _exhausted(tmp_path)
    before = dict(pipeline.db.get_segment(int(row["id"])))
    candidates = [dict(c) for c in pipeline.db.list_segment_candidates()]
    pipeline.db = ProjectDB(pipeline.db.path)
    monkeypatch.setattr(pipeline, "_publish_verified_chapter", lambda _: None)

    for _ in range(2):
        assert pipeline.db.retry_failed_segments("automatic retry") == []
        pipeline._process_chapter(pipeline.db.list_chapters()[0], verifier)

    assert dict(pipeline.db.get_segment(int(row["id"]))) == before
    assert [dict(c) for c in pipeline.db.list_segment_candidates()] == candidates
    assert len(scripted.calls) == 2
    assert verifier.calls == 5


@pytest.mark.parametrize("changed", ["text", "reading", "voice", "seed", "settings", "policy"])
def test_new_inputs_allow_retry_of_an_exhausted_segment(tmp_path, changed):
    pipeline, _, row, _, _ = _exhausted(tmp_path)
    db = pipeline.db
    if changed == "reading":
        db.set_listener_pronunciation(surface="Điên", normalized_surface="điên",
                                      spoken_form="Điền", source="listener")
    elif changed == "policy":
        policy = copy.deepcopy(pipeline.quality_policy)
        policy["algorithms"]["asr_content"] = "new-test-policy"
        from abook.quality_policy import QUALITY_POLICY_VERSION, quality_policy_hash
        db.set_current_quality_policy(policy_hash=quality_policy_hash(policy),
                                      policy_version=QUALITY_POLICY_VERSION, policy=policy)
    with db.transaction() as conn:
        if changed == "text":
            conn.execute("UPDATE segments SET listener_text=? WHERE id=?", ("Lời đọc mới.", row["id"]))
        elif changed == "voice":
            conn.execute("UPDATE voice_profiles SET preset_name='New preset' WHERE id=?", (row["voice_profile_id"],))
        elif changed == "seed":
            conn.execute("UPDATE segments SET listener_retakes=listener_retakes+1 WHERE id=?", (row["id"],))
        elif changed == "settings":
            settings = json.loads(db.book()["settings_json"])
            settings["tts"]["max_retries"] += 1
            conn.execute("UPDATE book SET settings_json=?", (json.dumps(settings),))
    assert db.retry_failed_segments("new input", stable_id=str(row["stable_id"])) == [row["stable_id"]]
    assert db.get_segment(int(row["id"]))["status"] == "analyzed"
    assert db.list_segment_candidates() == []


def test_unrelated_reading_does_not_reopen_exhausted_schedule(tmp_path):
    pipeline, _, row, _, _ = _exhausted(tmp_path)
    pipeline.db.set_listener_pronunciation(surface="Unrelated", normalized_surface="unrelated",
                                         spoken_form="Khác", source="listener")
    assert pipeline.db.retry_failed_segments("same segment inputs") == []
    assert pipeline.db.get_segment(int(row["id"]))["status"] == "failed"


def test_warning_chapter_reuses_assembly_and_keeps_qa(tmp_path, monkeypatch):
    pipeline, chapter, row, _ = _asr_signal_pipeline(tmp_path, repair_rounds=0)
    pipeline.db.mark_failed(int(row["id"]), "Still needs listening")
    monkeypatch.setattr(pipeline, "_grant_machine_acceptances", lambda _: None)
    original = pipeline_module.assemble_chapter_atomic_with_metrics
    calls = []

    def assemble(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(pipeline_module, "assemble_chapter_atomic_with_metrics", assemble)
    pipeline._publish_verified_chapter(chapter)
    artifact = pipeline.db.artifact_by_key("chapter_mp3:1")
    output = Path(artifact["path"])
    before = output.read_bytes()
    pipeline.db = ProjectDB(pipeline.db.path)
    pipeline._publish_verified_chapter(pipeline.db.list_chapters()[0])

    assert len(calls) == 1
    assert output.read_bytes() == before
    assert pipeline.db.list_chapters()[0]["status"] == "warning"
    assert pipeline.db.get_segment(int(row["id"]))["status"] == "failed"
    from abook.database import QUALITY_SCOPE_CHAPTER
    from abook.quality_policy import CHAPTER_QUALITY_STAGE
    check = pipeline.db.latest_quality_check(
        scope=QUALITY_SCOPE_CHAPTER, stage=CHAPTER_QUALITY_STAGE,
        chapter_id=int(chapter["id"]),
    )
    assert check["verdict"] == "fail"
    assert check["artifact_sha256"] == artifact["sha256"]


@pytest.mark.parametrize("changed", ["wav", "break", "settings", "title", "output", "manifest",
                                    "metadata_shape", "qa", "qa_shape", "unverified"])
def test_assembly_cache_invalidates_changed_inputs_or_evidence(tmp_path, monkeypatch, changed):
    pipeline, chapter, row, _ = _asr_signal_pipeline(tmp_path, repair_rounds=0)
    pipeline.db.mark_failed(int(row["id"]), "Review")
    monkeypatch.setattr(pipeline, "_grant_machine_acceptances", lambda _: None)
    pipeline._publish_verified_chapter(chapter)
    artifact = pipeline.db.artifact_by_key("chapter_mp3:1")
    if changed == "wav":
        import soundfile as sf
        wav = Path(row["wav_path"])
        samples, rate = sf.read(wav)
        sf.write(wav, samples * 0.8, rate, subtype="PCM_16")
        with pipeline.db.transaction() as conn:
            conn.execute("UPDATE segments SET wav_sha256=? WHERE id=?", (sha256_file(wav), row["id"]))
    elif changed == "break":
        with pipeline.db.transaction() as conn:
            conn.execute("UPDATE segments SET break_ms=break_ms+1 WHERE id=?", (row["id"],))
    elif changed == "settings":
        pipeline.settings["audio"]["mp3_bitrate"] = "128k"
    elif changed == "title":
        chapter = dict(chapter, title="Changed title")
    elif changed == "output":
        Path(artifact["path"]).write_bytes(b"Changed output")
    elif changed == "manifest":
        with pipeline.db.transaction() as conn:
            conn.execute("UPDATE artifacts SET metadata_json='{}' WHERE artifact_key='chapter_mp3:1'")
    elif changed == "metadata_shape":
        with pipeline.db.transaction() as conn:
            conn.execute("UPDATE artifacts SET metadata_json='[]' WHERE artifact_key='chapter_mp3:1'")
    elif changed == "qa":
        with pipeline.db.transaction() as conn:
            conn.execute("UPDATE quality_checks SET metrics_json='{}' WHERE chapter_id=?", (chapter["id"],))
    elif changed == "qa_shape":
        with pipeline.db.transaction() as conn:
            conn.execute("UPDATE quality_checks SET metrics_json='[]' WHERE chapter_id=?", (chapter["id"],))
    else:
        with pipeline.db.transaction() as conn:
            conn.execute("UPDATE artifacts SET verified=0 WHERE artifact_key='chapter_mp3:1'")

    class Reassembled(Exception):
        pass

    def assemble(*_args, **_kwargs):
        raise Reassembled

    monkeypatch.setattr(pipeline_module, "assemble_chapter_atomic_with_metrics", assemble)
    with pytest.raises(Reassembled):
        pipeline._publish_verified_chapter(chapter)


def test_manifest_is_ordered_and_hashes_bytes_not_timestamps(tmp_path):
    from abook.audio_io import chapter_assembly_manifest
    one, two = tmp_path / "one.wav", tmp_path / "two.wav"
    one.write_bytes(b"one")
    two.write_bytes(b"two")
    args = {"settings": {"audio": {}}, "title": "Chapter", "book_title": "Book", "track": 1}
    before = chapter_assembly_manifest([(one, 10), (two, 20)], **args)
    assert before != chapter_assembly_manifest([(two, 20), (one, 10)], **args)
    stamp = one.stat()
    one.write_bytes(b"new")
    import os
    os.utime(one, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert before != chapter_assembly_manifest([(one, 10), (two, 20)], **args)


def test_crash_before_exhaustion_commit_replays_spent_budget_without_generation(tmp_path, monkeypatch):
    pipeline, chapter, row = _short_tts_pipeline(tmp_path, repair_rounds=2)
    endpoint = {"duration": 0.96, "generation_ceiling_hit": 1.0,
                "generation_endpoint_active": 1.0, "trailing_rms": 0.05}
    _checkpoint_short_ceiling_incumbent(pipeline, row)
    scripted = ScriptedShortTTS([endpoint, endpoint])
    pipeline.tts = scripted.bind(pipeline.settings, pipeline.db)
    verifier = PassingShortVerifier()
    original = pipeline.db._segment_retry_input_sha256_conn

    def crash(*_args):
        raise RuntimeError("crash before exhaustion commit")

    monkeypatch.setattr(pipeline.db, "_segment_retry_input_sha256_conn", crash)
    with pytest.raises(RuntimeError, match="crash before exhaustion commit"):
        pipeline._verify_chapter_audio(chapter, verifier)
    assert pipeline.db.get_segment(int(row["id"]))["status"] == "signal_passed"
    assert len(pipeline.db.list_segment_candidates()) == 2
    monkeypatch.setattr(pipeline.db, "_segment_retry_input_sha256_conn", original)
    pipeline.db = ProjectDB(pipeline.db.path)
    pipeline._verify_chapter_audio(chapter, verifier)
    assert len(scripted.calls) == 2
    assert pipeline.db.get_segment(int(row["id"]))["status"] == "failed"
    assert pipeline.db.retry_failed_segments("after crash") == []


def test_crash_after_mp3_replace_does_not_publish_a_cache_entry(tmp_path, monkeypatch):
    pipeline, chapter, row, _ = _asr_signal_pipeline(tmp_path, repair_rounds=0)
    pipeline.db.mark_failed(int(row["id"]), "Review")
    monkeypatch.setattr(pipeline, "_grant_machine_acceptances", lambda _: None)
    original = pipeline._register_chapter_assembly

    def crash(*_args, **_kwargs):
        raise RuntimeError("crash before artifact registration")

    monkeypatch.setattr(pipeline, "_register_chapter_assembly", crash)
    with pytest.raises(RuntimeError, match="crash before artifact registration"):
        pipeline._publish_verified_chapter(chapter)
    assert Path(chapter["output_mp3"]).is_file()
    pipeline.db = ProjectDB(pipeline.db.path)
    manifest = pipeline._chapter_assembly_manifest(
        chapter, pipeline._chapter_delivery_wavs(chapter, pipeline.db.list_segments()),
    )
    assert pipeline._cached_chapter_assembly(chapter, manifest) is None
    monkeypatch.setattr(pipeline, "_register_chapter_assembly", original)
    pipeline._publish_verified_chapter(chapter)
    assert pipeline._cached_chapter_assembly(chapter, manifest) is not None
    assert pipeline.db.list_chapters()[0]["status"] == "warning"


def test_completed_chapter_shortcut_checks_break_manifest_without_decoding(tmp_path, monkeypatch):
    from abook.asr import ASR_PASS

    pipeline, chapter, row, expected = _asr_signal_pipeline(tmp_path, repair_rounds=0)
    # The generic ASR fixture is a 4 Hz wave, which legitimately triggers flat-top QA.
    # Use an audible tone for this completed-chapter case.
    from tests.test_audio_assembly import _write_test_tone
    _write_test_tone(Path(row["wav_path"]), pipeline.settings, 440, seconds=2.0)
    with pipeline.db.transaction() as conn:
        conn.execute("UPDATE segments SET wav_sha256=? WHERE id=?", (sha256_file(Path(row["wav_path"])), row["id"]))
    row = dict(pipeline.db.get_segment(int(row["id"])))
    pipeline._record_segment_audio_pass(
        row, _asr_result(ASR_PASS, expected, similarity=1.0, wer=0.0),
        confirmation=False, decode_evidence=[],
    )
    pipeline._verify_chapter_perceptual_audio(chapter)
    pipeline._publish_verified_chapter(chapter)
    assert pipeline.db.list_chapters()[0]["status"] == "completed", json.loads(
        pipeline.db.artifact_by_key("chapter_mp3:1")["metadata_json"]
    )["quality_metrics"]

    def unexpected(*_args, **_kwargs):
        pytest.fail("an unchanged completed chapter must not decode or encode again")

    monkeypatch.setattr(pipeline_module, "verify_mp3", unexpected)
    monkeypatch.setattr(pipeline_module, "assemble_chapter_atomic_with_metrics", unexpected)
    pipeline._process_chapter(pipeline.db.list_chapters()[0], PassingShortVerifier())
    with pipeline.db.transaction() as conn:
        conn.execute("UPDATE segments SET break_ms=break_ms+1 WHERE id=?", (row["id"],))
    chapter = pipeline.db.list_chapters()[0]
    manifest = pipeline._chapter_assembly_manifest(chapter, pipeline._chapter_delivery_wavs(chapter, pipeline.db.list_segments()))
    assert pipeline._cached_chapter_assembly(chapter, manifest) is None
