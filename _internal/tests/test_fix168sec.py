"""Untrusted take ledgers and synthesis bugs never become file access or seed verdicts.

All text and bytes in these cases are synthetic. No model, network or book corpus is used.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from abook import book_paths, continuation, pipeline as pipeline_module
from abook.audio_io import AudioQualityError, SignalRejectedTake, rejected_take_path
from abook.database import ProjectDB
from abook.pipeline import CriticalResourceStop
from abook.text_processing import load_and_segment_chapter
from tests.test_rejected_take import _edge_pipeline


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_module.time, "sleep", lambda _seconds: None)
    return _edge_pipeline(tmp_path, [], text="Đèn báo đã bật.")


@pytest.fixture(params=["absolute", "parent", "unc"])
def bad_path(request, tmp_path):
    outside = tmp_path / "forbidden.wav"
    outside.write_bytes(b"outside evidence must survive")
    rejected_take_path(outside).write_bytes(b"outside rejected evidence must survive")
    value = {"absolute": str(outside), "parent": "../forbidden.wav", "unc": r"\\host\share\a.wav"}[request.param]
    return value, outside


def guard_paths(monkeypatch, outside):
    """Fail before resolve as well as before reading, hashing, probing or deleting."""
    forbidden = ("forbidden", "\\\\host", "//host")

    def guard(real):
        def checked(path, *args, **kwargs):
            text = os.fspath(path).casefold()
            assert not any(token in text for token in forbidden), f"unsafe I/O: {text}"
            return real(path, *args, **kwargs)
        return checked

    for name in ("resolve", "is_file", "stat", "unlink", "open"):
        monkeypatch.setattr(Path, name, guard(getattr(Path, name)))
    monkeypatch.setattr(pipeline_module, "sha256_file", guard(pipeline_module.sha256_file))


@pytest.mark.parametrize("field", ["path", "rejected_path", "rejected"])
def test_cleanup_skips_every_unsafe_ledger_path(setup, bad_path, monkeypatch, caplog, field):
    pipeline, _chapter, row = setup
    value, outside = bad_path
    session = pipeline._begin_take_session(row, {"test": "unsafe-cleanup"})
    loser = pipeline.paths.root / "loser.wav"
    loser.write_bytes(b"unused local take")
    session["attempts"] = {"bad": {field: {"path": value} if field == "rejected" else value},
                           "good": {"path": str(loser)}}
    # Segment and artifact rows also remain untrusted when the session closes.
    with pipeline.db.transaction() as conn:
        conn.execute("UPDATE segments SET wav_path=? WHERE id=?", (value, row["id"]))
    pipeline.db.register_artifact(artifact_key="unsafe", kind="test", path=outside,
                                  sha256=None, verified=False)
    with monkeypatch.context() as guarded:
        guard_paths(guarded, outside)
        pipeline._close_take_session(row, session)
        assert not loser.exists()
    assert outside.read_bytes() == b"outside evidence must survive"
    assert rejected_take_path(outside).read_bytes() == b"outside rejected evidence must survive"
    assert "unsafe book path" in caplog.text
    assert session["state"] == "closed"


@pytest.mark.parametrize("rejected", [False, True], ids=["successful-take", "rejected-take"])
def test_replay_never_hashes_or_resolves_unsafe_record(setup, bad_path, monkeypatch, caplog, rejected):
    pipeline, _chapter, row = setup
    value, outside = bad_path
    session = pipeline._begin_take_session(row, {"test": "unsafe-replay"})
    fresh = pipeline.paths.root / "fresh.wav"
    record = dict(path=str(fresh), seed=7)
    if rejected:
        record.update(error="edge refused", quality=True, rejected_path=value,
                      rejected=dict(path=value, sha256="0" * 64, metrics={}, seed=7, code="edge", **{"class": "edge"}))
    else:
        record.update(path=value, sha256="0" * 64, metrics={})
    session["attempts"]["primary_0"] = record
    pipeline._write_take_session(row, session)
    pipeline.db = ProjectDB(pipeline.db.path)  # replay the actual JSON from disk
    saved = json.loads(pipeline.db.artifact_by_key(pipeline._take_session_key(row))["metadata_json"])
    calls = []
    with monkeypatch.context() as guarded:
        guard_paths(guarded, outside)
        output = pipeline._session_attempt_path(row, saved, "primary_0", fresh)

        def synthesize():
            calls.append(output)
            return output, "1" * 64, {"duration": 1.0}, 7

        assert pipeline._session_synthesis(row, saved, "primary_0", synthesize)[0] == fresh
    assert calls == [fresh] and "unsafe book path" in caplog.text
    assert outside.read_bytes() == b"outside evidence must survive"


def test_unsafe_exception_and_retention_output_are_ignored(setup, bad_path, monkeypatch, caplog):
    pipeline, _chapter, row = setup
    value, outside = bad_path
    error = SignalRejectedTake("edge refused", code="edge", rejection_class="edge", path=Path(value),
                               checksum="0" * 64, metrics={"duration": 1.0})
    with monkeypatch.context() as guarded:
        guard_paths(guarded, outside)
        pipeline._retain_rejected_output(row, pipeline.paths.root / "fresh.wav", error, "primary_0", "primary", None)
        assert pipeline._keep_usable_take(row, Path(value), "0" * 64, {"duration": 1.0}, 7) is False
    assert pipeline.db.get_segment(row["id"])["wav_path"] is None
    assert "unsafe book path" in caplog.text


@pytest.mark.parametrize("code", [1, 2, 3, 4], ids=["format", "system", "malformed", "encoding"])
@pytest.mark.parametrize("context", ["none", "disk", "bug"])
def test_provider_retention_only_ignores_known_decode_failures(setup, monkeypatch, code, context):
    pipeline, _chapter, row = setup
    output = pipeline.paths.root / "provider.wav"
    output.write_bytes(b"synthetic undecodable bytes")

    def info(_path):
        error = pipeline_module.sf.LibsndfileError(code)
        if context == "disk":
            error.__context__ = OSError("synthetic read failure")
        elif context == "bug":
            error.__context__ = TypeError("synthetic decoder bug")
        raise error

    monkeypatch.setattr(pipeline_module.sf, "info", info)
    args = (row, output, AudioQualityError("provider refused audio"), "primary_0", "primary", None)
    if code == 2 or context != "none":
        with pytest.raises(CriticalResourceStop):
            pipeline._retain_rejected_output(*args)
    else:
        pipeline._retain_rejected_output(*args)
    assert pipeline.db.get_segment(row["id"])["wav_path"] is None


def test_retry_cleanup_never_unlinks_unsafe_exception_path(setup, bad_path, monkeypatch):
    pipeline, _chapter, row = setup
    value, outside = bad_path
    metadata = dict(state="reserved", context={}, source_metrics={}, before={})
    artifact = dict(path=str(pipeline.paths.root / "retry.wav"), metadata_json=json.dumps(metadata))
    finished = []

    def finish(_key, **kwargs):
        finished.append(kwargs)
        metadata["state"] = "failed"
        artifact["metadata_json"] = json.dumps(metadata)

    monkeypatch.setattr(pipeline.db, "artifact_by_key", lambda _key: artifact)
    monkeypatch.setattr(pipeline.db, "finish_word_break_retry", finish)

    def refuse(*_args):
        raise SignalRejectedTake("edge refused", code="edge", rejection_class="edge", path=Path(value),
                                 checksum="0" * 64, metrics={})

    monkeypatch.setattr(pipeline, "_word_break_retake", refuse)
    with monkeypatch.context() as guarded:
        guard_paths(guarded, outside)
        assert pipeline._settle_word_break_retry(row, "retry")["state"] == "failed"
    assert len(finished) == 1 and outside.exists()


BUG_TYPES = [TypeError, KeyError, AttributeError, NameError, AssertionError]


@pytest.mark.parametrize("bug_type", BUG_TYPES)
@pytest.mark.parametrize("wrapped", [False, True], ids=["direct", "wrapped-context"])
def test_programming_fault_is_fatal_without_recording_or_spending_seed(setup, bug_type, wrapped):
    pipeline, chapter, row = setup
    bug = bug_type("synthetic bug")
    error = AudioQualityError("engine failed") if wrapped else bug
    if wrapped:
        error.__context__ = bug
    pipeline.tts.outcomes = [error, "clean"]
    with pytest.raises(CriticalResourceStop):
        pipeline._process_single_segment(row, chapter)
    current = pipeline.db.get_segment(row["id"])
    saved = json.loads(pipeline.db.artifact_by_key(pipeline._take_session_key(row))["metadata_json"])
    assert current["status"] != "failed"
    assert saved["state"] == "open" and set(saved["attempts"]) == {"primary_0"}
    assert "error" not in saved["attempts"]["primary_0"]
    assert pipeline.tts.salts == ["primary_0"]


def test_book_file_exception_is_fatal_without_a_seed_verdict(setup, bad_path):
    pipeline, _chapter, row = setup
    value, _outside = bad_path
    session = pipeline._begin_take_session(row, {"test": "path-bug"})
    pipeline._session_attempt_path(row, session, "primary_0", pipeline.paths.root / "a.wav")
    with pytest.raises(CriticalResourceStop):
        pipeline._session_synthesis(row, session, "primary_0", lambda: pipeline._book_file(value))
    saved = json.loads(pipeline.db.artifact_by_key(pipeline._take_session_key(row))["metadata_json"])
    assert "error" not in saved["attempts"]["primary_0"] and saved["state"] == "open"


@pytest.mark.parametrize("point", ["_keep_usable_take", "_accept_retained_take", "_close_take_session"])
def test_post_synthesis_bug_does_not_fail_or_close_the_session(setup, monkeypatch, point):
    pipeline, chapter, row = setup
    pipeline.tts.outcomes = ["clean"]

    def broken(*_args, **_kwargs):
        raise KeyError("checkpoint bug")

    monkeypatch.setattr(pipeline, point, broken)
    with pytest.raises(CriticalResourceStop):
        pipeline._process_single_segment(row, chapter)
    current = pipeline.db.get_segment(row["id"])
    saved = json.loads(pipeline.db.artifact_by_key(pipeline._take_session_key(row))["metadata_json"])
    assert current["status"] != "failed" and saved["state"] == "open"
    assert "error" not in saved["attempts"]["primary_0"]


@pytest.mark.parametrize("suppress", [False, True])
@pytest.mark.parametrize("fault", [PermissionError("synthetic held file"), pipeline_module.sf.LibsndfileError(2)],
                         ids=["oserror", "sndfile_system"])
def test_context_only_oserror_preserves_reservation_and_seed_on_reopen(setup, suppress, fault):
    pipeline, chapter, row = setup

    def wrapped_disk_fault():
        try:
            raise fault
        except (OSError, pipeline_module.sf.LibsndfileError):
            if suppress:
                raise RuntimeError("engine wrapper") from None
            raise RuntimeError("engine wrapper")

    with pytest.raises(RuntimeError) as caught:
        wrapped_disk_fault()
    error = caught.value
    assert error.__cause__ is None and pipeline_module._is_machine_fault(error)
    pipeline.tts.outcomes = [error] * pipeline_module.WORD_BREAK_RETRY_ENVIRONMENT_ATTEMPTS
    with pytest.raises(CriticalResourceStop):
        pipeline._process_single_segment(row, chapter)
    saved = json.loads(pipeline.db.artifact_by_key(pipeline._take_session_key(row))["metadata_json"])
    assert "error" not in saved["attempts"]["primary_0"] and saved["state"] == "open"
    pipeline.db = ProjectDB(pipeline.db.path)
    pipeline.tts.db = pipeline.db
    pipeline.tts.outcomes = ["clean"]
    pipeline._process_single_segment(pipeline.db.get_segment(row["id"]), chapter)
    assert pipeline.tts.salts == ["primary_0"] * (pipeline_module.WORD_BREAK_RETRY_ENVIRONMENT_ATTEMPTS + 1)
    assert pipeline.db.get_segment(row["id"])["status"] == "signal_passed"


def test_both_exception_edges_and_cycles_are_examined():
    wrapper, cause = RuntimeError("wrapper"), ValueError("cause")
    disk = OSError("disk")
    wrapper.__cause__, wrapper.__context__ = cause, disk
    cause.__context__ = wrapper
    assert pipeline_module._is_machine_fault(wrapper)
    wrapper.__context__ = KeyError("bug")
    assert not pipeline_module._is_machine_fault(wrapper)
    assert pipeline_module._is_fatal_synthesis_error(wrapper)
    assert len(list(pipeline_module._exception_chain(wrapper))) == 3


def test_unclassified_runtime_error_does_not_become_an_audio_verdict(setup):
    pipeline, chapter, row = setup
    pipeline.tts.outcomes = [RuntimeError("unclassified failure")]
    with pytest.raises(CriticalResourceStop):
        pipeline._process_single_segment(row, chapter)
    saved = json.loads(pipeline.db.artifact_by_key(pipeline._take_session_key(row))["metadata_json"])
    assert "error" not in saved["attempts"]["primary_0"]


@pytest.mark.parametrize("bug_type", BUG_TYPES)
def test_split_programming_bug_keeps_split_reservation_open(tmp_path, monkeypatch, bug_type):
    text = "Thiết bị thử ghi một tín hiệu ngắn rồi lưu kết quả đo vào bộ nhớ. " * 3
    pipeline, chapter, row = _edge_pipeline(tmp_path, [AudioQualityError("synthetic refusal")] * 4, text=text)
    monkeypatch.setattr(pipeline_module.time, "sleep", lambda _seconds: None)

    def broken(*_args, **_kwargs):
        raise bug_type("split bug")

    monkeypatch.setattr(pipeline, "_synthesize_split", broken)
    with pytest.raises(CriticalResourceStop):
        pipeline._process_single_segment(row, chapter)
    saved = json.loads(pipeline.db.artifact_by_key(pipeline._take_session_key(row))["metadata_json"])
    assert saved["state"] == "open" and "error" not in saved["attempts"]["primary_split"]
    assert pipeline.db.get_segment(row["id"])["status"] != "failed"


@pytest.mark.parametrize("bug_type", BUG_TYPES)
def test_candidate_programming_bug_does_not_advance_attempt(tmp_path, monkeypatch, bug_type):
    from tests.test_word_break_gate import seeded

    pipeline, chapter, row, _engine = seeded(tmp_path, monkeypatch, plan={})
    pipeline._process_single_segment(row, chapter)
    row = pipeline.db.get_segment(row["id"])
    candidate = pipeline._allocate_segment_candidate(row, 0, 2)

    def broken(*_args, **_kwargs):
        raise bug_type("candidate bug")

    monkeypatch.setattr(pipeline.tts, "synthesize_atomic", broken)
    with pytest.raises(CriticalResourceStop):
        pipeline._process_segment_candidate(row, candidate, chapter)
    current = pipeline.db.get_segment_candidate(candidate["id"])
    assert current["state"] == "generating" and current["tts_attempt"] == 0
    assert current["generation_seed"] == candidate["generation_seed"]


@pytest.mark.parametrize("bug_type", BUG_TYPES)
def test_tempo_rescue_programming_bug_never_records_a_failure(setup, monkeypatch, bug_type):
    pipeline, chapter, row = setup
    source = pipeline.paths.root / "source.wav"
    source.write_bytes(b"synthetic source bytes")
    checksum = pipeline_module.sha256_file(source)
    source_row = dict(id=1, wav_path=str(source), wav_sha256=checksum, signal_json="{}")
    candidate = dict(id=2, postprocess_source_candidate_id=1, postprocess_source_sha256=checksum,
                     wav_path=str(pipeline.paths.root / "tempo.wav"), generation_seed=7)
    monkeypatch.setattr(pipeline.db, "get_segment_candidate", lambda _id: source_row)
    monkeypatch.setattr(pipeline, "_require_segment_candidate_pronunciation_delivery", lambda *_: ("locked", "Đèn thử.", []))
    monkeypatch.setattr(pipeline.db, "mark_segment_candidate_tts_failed",
                        lambda *_a, **_k: pytest.fail("a bug must not become a candidate failure"))

    def broken(*_args):
        raise bug_type("tempo bug")

    monkeypatch.setattr(pipeline_module, "tempo_stretch_wav_atomic", broken)
    with pytest.raises(CriticalResourceStop):
        pipeline._process_tempo_rescue_candidate(row, candidate, chapter)


def test_cli_validates_stored_root_without_resolving_unsafe_path(setup, bad_path, monkeypatch):
    from abook.cli import validate_project

    pipeline, _chapter, _row = setup
    value, outside = bad_path
    with pipeline.db.transaction() as conn:
        conn.execute("UPDATE book SET project_root=?", (value,))
    with monkeypatch.context() as guarded:
        guard_paths(guarded, outside)
        result = validate_project(pipeline.paths.root)
    assert result["checks"]["project_root"] is False


def test_segmentation_refuses_unsafe_sources_before_io(setup, bad_path, monkeypatch):
    pipeline, chapter, _row = setup
    value, outside = bad_path
    with monkeypatch.context() as guarded:
        guard_paths(guarded, outside)
        with pytest.raises(book_paths.UnsafeBookPath):
            load_and_segment_chapter({**dict(chapter), "input_path": value}, max_chars=200,
                                     project_root=pipeline.paths.root)


def test_audio_locator_never_probes_unsafe_stored_paths(setup, bad_path, monkeypatch):
    from abook.webui import store

    pipeline, _chapter, _row = setup
    value, outside = bad_path
    with monkeypatch.context() as guarded:
        guard_paths(guarded, outside)
        assert store.AudioLocator(pipeline.paths.root).find(value) is None


def test_locked_model_settings_never_probe_or_hash_unsafe_paths(setup, bad_path, monkeypatch):
    from abook.quality_policy import external_file_hash
    from abook.runtime_contract import relocated_model_path

    pipeline, _chapter, _row = setup
    value, outside = bad_path
    with monkeypatch.context() as guarded:
        guard_paths(guarded, outside)
        with pytest.raises(book_paths.UnsafeBookPath):
            relocated_model_path(value, pipeline.paths.root)
        assert external_file_hash(value, trusted_root=pipeline.paths.root) == "MISSING"


def test_continuation_link_cannot_resolve_network_or_leave_library(setup, bad_path, monkeypatch):
    pipeline, _chapter, _row = setup
    value, outside = bad_path
    (pipeline.paths.root / continuation.LINK_FILE).write_text(json.dumps({"previous": value}), encoding="utf-8")
    with monkeypatch.context() as guarded:
        guard_paths(guarded, outside)
        assert continuation.previous_path(pipeline.paths.root) is None


def test_audio_locator_and_work_items_skip_links_to_external_files(tmp_path):
    from abook.webui import store, work_items
    from tests.test_secfix_book_paths import test_a_link_inside_the_book_folder_that_points_outside_is_refused

    # Reuse the platform-specific junction setup; its containment assertion remains useful here.
    test_a_link_inside_the_book_folder_that_points_outside_is_refused(tmp_path)
    outside = tmp_path / "ngoai" / "source.txt"
    outside.write_text("Synthetic source.", encoding="utf-8")
    project = tmp_path / "sach"
    linked = project / "lien_ket" / "source.txt"
    assert store.AudioLocator(project).find(str(linked)) is None
    assert work_items._folded_book([str(linked)], project) == ""
