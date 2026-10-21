"""Reconcile checkpoints survive a speaker-pass crash through BookPipeline.run."""
from pathlib import Path

import pytest

from abook import pipeline as pipeline_module
from abook.database import ProjectDB
from test_speaker_pass_pipeline import (
    Crash, FakeOllama, LABELS, _Analyzer, _Stop, _pipeline,
    make_pass, make_project, pass_settings, speakers,
)


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
