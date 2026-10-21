"""Reconcile checkpoints survive a speaker-pass crash through BookPipeline.run."""
from pathlib import Path

import pytest

from abook import pipeline as pipeline_module
from abook.analysis import OllamaBookAnalyzer
from abook.database import ProjectDB
from test_speaker_pass_pipeline import (
    Crash, FakeOllama, LABELS, _Analyzer, _Stop, _pipeline,
    make_pass, make_project, pass_settings, speakers,
)


@pytest.mark.parametrize("failure", ["unavailable", "request"])
def test_unreachable_model_reconciliation_is_retried_before_the_speaker_pass(tmp_path: Path, monkeypatch, failure: str) -> None:
    pipeline = _pipeline(monkeypatch, finalized=False, pending=True)
    pipeline.db = make_project(tmp_path / "p")
    pipeline.settings = pass_settings()
    pipeline.settings["analysis"]["local_identity_reconcile"] = "loose"
    monkeypatch.delenv("ABOOK_LOCAL_IDENTITY_RECONCILE", raising=False)
    with pipeline.db.transaction() as conn:
        conn.execute("UPDATE segments SET speaker='Lan' WHERE stable_id='c1s1'")
    analyzer = OllamaBookAnalyzer(pipeline.settings, pipeline.db, pipeline.log)
    available = [False]
    asked = []
    monkeypatch.setattr(analyzer, "analyze_all", lambda *a, **kw: None)
    monkeypatch.setattr(analyzer, "ensure_available", lambda: failure == "request" or available[0])
    monkeypatch.setattr(analyzer, "unload", lambda: None)
    monkeypatch.setattr(analyzer, "reconcile_name_pronunciations", lambda **kw: 0)

    def request(*a, **kw):
        asked.append(1)
        if not available[0]:
            raise RuntimeError("offline")
        return {"identities": []}

    monkeypatch.setattr(analyzer, "_stream_json_response", request)
    monkeypatch.setattr(pipeline_module, "OllamaBookAnalyzer", lambda *a, **kw: analyzer)
    passed = []
    pipeline._run_speaker_pass = lambda _analyzer: passed.append(1)
    if failure == "request":
        # A failed request is not retried on resume: the seeded question would fail the same way
        # every time and the book would never move on. The chapter keeps its local labels.
        with pytest.raises(_Stop):
            pipeline.run(recovery_already_run=True)
        assert asked and passed == [1]
        assert ProjectDB(pipeline.db.path).speaker_pass_is_reconciled()
        return
    with pytest.raises(RuntimeError, match="hoà giải"):
        pipeline.run(recovery_already_run=True)
    assert not ProjectDB(pipeline.db.path).speaker_pass_is_reconciled()
    assert not passed and not pipeline.db.casting_is_finalized()
    available[0] = True
    with pytest.raises(_Stop):
        pipeline.run(recovery_already_run=True)
    assert asked and passed == [1]
    assert ProjectDB(pipeline.db.path).speaker_pass_is_reconciled()


def test_local_reconciliation_without_candidates_completes_without_a_model(tmp_path: Path, monkeypatch) -> None:
    pipeline = _pipeline(monkeypatch, finalized=False, pending=False)
    pipeline.db = make_project(tmp_path / "p")
    with pipeline.db.transaction() as conn:
        conn.execute("UPDATE segments SET speaker='UNKNOWN' WHERE speaker NOT LIKE 'NPC_LOCAL::%' AND speaker!='NARRATOR'")
    pipeline.settings = pass_settings()
    pipeline.settings["analysis"]["local_identity_reconcile"] = "loose"
    monkeypatch.delenv("ABOOK_LOCAL_IDENTITY_RECONCILE", raising=False)
    analyzer = OllamaBookAnalyzer(pipeline.settings, pipeline.db, pipeline.log)
    monkeypatch.setattr(analyzer, "ensure_available", lambda: pytest.fail("không có ứng viên: không cần model"))
    monkeypatch.setattr(_Analyzer, "reconcile_local_speaker_identities", lambda self, **kw: analyzer.reconcile_local_speaker_identities(**kw))
    pipeline._run_speaker_pass = lambda _analyzer: None
    with pytest.raises(_Stop):
        pipeline.run(recovery_already_run=True)
    assert ProjectDB(pipeline.db.path).speaker_pass_is_reconciled()


@pytest.mark.parametrize("fail_after", [0, 5])
def test_pipeline_resume_does_not_reconcile_committed_pass_labels(tmp_path: Path, monkeypatch, fail_after: int) -> None:
    calls = []
    labels = {**LABELS, "“Ai đó?”": "NPC_LOCAL:cậu bé"}

    def configure(root: Path, ollama: FakeOllama):
        pipeline = _pipeline(monkeypatch, finalized=False, pending=True)
        pipeline.db = make_project(root)
        pipeline.settings = pass_settings()
        pass_ = make_pass(pipeline.db, ollama, monkeypatch)
        monkeypatch.setattr(pipeline_module, "SpeakerPass", lambda *_args: pass_)

        def reconcile(self, **_kw):
            calls.append("local")
            with pipeline.db.transaction() as conn:
                conn.execute("UPDATE segments SET speaker='Iven' WHERE speaker LIKE 'NPC_LOCAL::%cậu bé'")
            return 0

        def names(self, **_kw):
            calls.append("names")

        monkeypatch.setattr(_Analyzer, "reconcile_local_speaker_identities", reconcile)
        monkeypatch.setattr(_Analyzer, "reconcile_name_pronunciations", names)
        return pipeline

    uninterrupted = configure(tmp_path / "whole", FakeOllama(labels))
    with pytest.raises(_Stop):
        uninterrupted.run(recovery_already_run=True)
    expected = speakers(uninterrupted.db)
    calls.clear()

    first = FakeOllama(labels)
    first.fail_after = fail_after
    interrupted = configure(tmp_path / "resume", first)
    with pytest.raises(Crash):
        interrupted.run(recovery_already_run=True)
    assert len(interrupted.db.speaker_pass_done_chapters()) == (1 if fail_after else 0)
    second = FakeOllama(labels)
    resumed = configure(tmp_path / "resume", second)
    with pytest.raises(_Stop):
        resumed.run(recovery_already_run=True)

    assert speakers(resumed.db) == expected
    assert calls == ["local", "names"]
    assert len(second.prompts) == (2 if fail_after else 6)


@pytest.mark.parametrize("checkpoint", ["none", "lock", "chapter"])
def test_old_databases_preserve_the_pre_pass_checkpoint_on_reopen(tmp_path: Path, checkpoint: str) -> None:
    db = make_project(tmp_path / "p")
    if checkpoint == "lock":
        db.lock_speaker_pass(model_name="speaker", model_digest="digest", analysis_model="analysis",
                             tokenizer_sha256="tokenizer", algorithm="pq")
    elif checkpoint == "chapter":
        db.commit_speaker_pass_chapter(int(db.list_chapters()[-1]["id"]), [], {}, seconds=0)
    with db.transaction() as conn:
        conn.execute("ALTER TABLE book DROP COLUMN speaker_pass_reconciled")
    reopened = ProjectDB(db.path)
    assert reopened.speaker_pass_is_reconciled() == (checkpoint != "none")
    reopened.mark_speaker_pass_reconciled()
    assert ProjectDB(db.path).speaker_pass_is_reconciled()
