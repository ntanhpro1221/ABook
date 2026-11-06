"""A+ chapter exceptions reuse the thinker's locked character voice; CPU only."""
import json
from pathlib import Path

import pytest

from abook import cli, teller_voice
from abook import narrator_sections
from abook.config import build_settings
from abook.database import ProjectDB
from abook.tts import TTSCoordinator
from test_teller_voice import _book, _settings


def rows(db):
    with db.connect() as conn:
        return {r["stable_id"]: dict(r) for r in conn.execute("SELECT * FROM segments")}


def chapter_book(tmp_path, **kwargs):
    return _book(tmp_path, settings=_settings("Bao", {"2": "Mai"}), **kwargs)


def test_chapter_narration_and_own_thought_share_character_voice_and_reopen(tmp_path):
    paths, db, settings = chapter_book(tmp_path, recorded=True)
    before = rows(db)
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET status='verified',wav_path='take.wav' WHERE stable_id IN ('c2s0','c2s2')")
    result = teller_voice.ensure(paths.root, db, settings)
    assert result["chapterNarrator"] == {"lines": 2, "redo": 1}
    db = ProjectDB(paths.db)  # Reopen: no schema additions or sidecar replay needed.
    after = rows(db)
    own_voice = before["c1s1"]["voice_profile_id"]
    for sid in ("c2s0", "c2s2"):
        assert after[sid]["voice_profile_id"] == own_voice
        assert after[sid]["speaker"] == "NARRATOR"
    assert after["c2s2"]["status"] == "analyzed" and not after["c2s2"]["wav_path"]
    assert after["c2s0"]["status"] == "verified"  # Already in her own voice: no retake.
    for sid in before.keys() - {"c2s0", "c2s2"}:
        assert after[sid] == before[sid]
    assert "chapterNarrator" not in teller_voice.ensure(paths.root, db, settings)
    tts = object.__new__(TTSCoordinator)
    tts.db = db
    tts.spoken_text_with_anchors = lambda row, **kw: (row["text"], [])
    tts.spoken_text = lambda row, **kw: row["text"]
    assert tts._voice_profile_for_row(after["c2s0"])["id"] == own_voice
    assert tts._spoken_row(after["c2s0"])["voice_profile_id"] == own_voice


@pytest.mark.parametrize("same_gender,identity", [(True, "Bao"), (False, "")])
def test_same_gender_and_third_person_no_chapter_changes(tmp_path, same_gender, identity):
    settings = _settings(identity, {"2": "Mai"} if same_gender else {})
    paths, db, settings = _book(tmp_path, settings=settings, mai_gender="male" if same_gender else "female", recorded=True)
    before = rows(db)
    assert "chapterNarrator" not in teller_voice.ensure(paths.root, db, settings)
    assert rows(db) == before


@pytest.mark.parametrize("preset", ["Thái Sơn", None])
def test_deliberate_global_override_rebinds_chapter_profiles_and_survives_reopen(tmp_path, preset):
    paths, db, settings = chapter_book(tmp_path, recorded=True)
    teller_voice.ensure(paths.root, db, settings)
    with db.connect() as conn:
        base = dict(conn.execute("SELECT * FROM voice_profiles WHERE voice_key='narrator'").fetchone())
    preset = preset or base["preset_name"]  # Choosing the current base voice is deliberate too.
    result = db.apply_listener_voice(character="NARRATOR", voices=settings["voices"], preset=preset)
    assert result and "problem" not in result
    db = ProjectDB(paths.db)
    for sid in ("c2s0", "c2s2"):
        assert rows(db)[sid]["voice_profile_id"] == base["id"]
    assert "chapterNarrator" not in teller_voice.ensure(paths.root, db, settings)
    assert rows(db)["c2s2"]["voice_profile_id"] == base["id"]


def test_missing_auto_flag_is_not_a_deliberate_override(tmp_path):
    paths, db, settings = chapter_book(tmp_path, recorded=True, narrator_auto=False)
    assert teller_voice.ensure(paths.root, db, settings)["chapterNarrator"]["lines"] == 2


def test_unrecorded_thought_only_teller_keeps_her_own_profile(tmp_path):
    paths, db, settings = chapter_book(tmp_path)
    own = rows(db)["c2s0"]["voice_profile_id"]
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET canonical_character_id=(SELECT id FROM characters WHERE canonical_name='BAO'),"
                     " speaker='BAO',voice_profile_id=(SELECT voice_profile_id FROM segments WHERE stable_id='c2s1')"
                     " WHERE stable_id IN ('c1s1','c1s2')")
        profiles = conn.execute("SELECT COUNT(*) FROM voice_profiles").fetchone()[0]
    teller_voice.ensure(paths.root, db, settings)
    assert rows(db)["c2s0"]["voice_profile_id"] == own
    assert rows(db)["c2s2"]["voice_profile_id"] == own
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM voice_profiles").fetchone()[0] == profiles


@pytest.mark.parametrize("whole_book", [False, True])
def test_cast_lists_the_chapter_exception(tmp_path, whole_book):
    from abook.webui.store import _cast
    paths, db, settings = _book(tmp_path, recorded=True) if whole_book else chapter_book(tmp_path, recorded=True)
    (paths.root / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    teller_voice.ensure(paths.root, db, settings)
    voice = db.voice_profile(rows(db)["c2s2"]["voice_profile_id"])["preset_name"]
    narrator = _cast(paths.root)["narrator"]
    assert narrator["chapterVoices"] == [f"Chương {i}: {voice}" for i in ([1, 2] if whole_book else [2])]
    assert narrator["profile"]["preset"] == narrator["voice"] == settings["voices"]["narrator_voice"]


def test_explicit_narrator_wish_prevents_chapter_assignment(tmp_path):
    paths, db, settings = chapter_book(tmp_path, recorded=True)
    (paths.root / "overrides.json").write_text(json.dumps({"voices": {"NARRATOR": {"preset": "Thái Sơn"}}}), encoding="utf-8")
    assert "chapterNarrator" not in teller_voice.ensure(paths.root, db, settings)


def test_chapter_reset_failure_rolls_back_and_can_retry_after_reopen(tmp_path, monkeypatch):
    paths, db, settings = chapter_book(tmp_path, recorded=True)
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET status='verified',wav_path='take.wav' WHERE stable_id='c2s2'")
    before = rows(db)
    def crash(*args):
        raise RuntimeError("crash before commit")
    with monkeypatch.context() as m:
        m.setattr(db, "_reset_segment_pending_conn", crash)
        with pytest.raises(RuntimeError, match="crash before commit"):
            teller_voice.ensure(paths.root, db, settings)
    db = ProjectDB(paths.db)
    assert rows(db) == before
    assert teller_voice.ensure(paths.root, db, settings)["chapterNarrator"]["redo"] == 1


@pytest.mark.parametrize("next_narrator", [None, "Bao", ""])
def test_section_voice_and_original_thinker_are_restored_after_undo_or_same_gender_choice(tmp_path, next_narrator):
    paths, db, settings = _book(tmp_path, settings=_settings("Bao"), recorded=True)
    before = rows(db)
    narrator_sections.decide(paths.root, 2, 0, 2, accepted=True, narrator="Mai", source="owner")
    teller_voice.ensure(paths.root, db, settings)
    assert rows(db)["c2s2"]["voice_profile_id"] == before["c1s1"]["voice_profile_id"]
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET status='verified',wav_path='new.wav',wav_duration=1 WHERE stable_id='c2s2'")
    if next_narrator is None:
        narrator_sections.forget(paths.root, 2, 0, 2)
    else:
        narrator_sections.decide(paths.root, 2, 0, 2, accepted=True, narrator=next_narrator, source="owner")
    db = ProjectDB(paths.db)
    teller_voice.ensure(paths.root, db, settings)
    after = rows(db)
    for sid in ("c2s0", "c2s2"):
        for field in ("speaker", "canonical_character_id", "voice_profile_id"):
            assert after[sid][field] == before[sid][field], (sid, field)
    assert after["c2s2"]["status"] == "analyzed" and after["c2s2"]["wav_path"] is None
    assert "chapterNarrator" not in teller_voice.ensure(paths.root, db, settings)


def test_section_undo_keeps_a_listener_line_choice(tmp_path):
    from abook.listener_overrides import request_speaker
    paths, db, settings = _book(tmp_path, settings=_settings("Bao"), recorded=True)
    narrator_sections.decide(paths.root, 2, 0, 2, accepted=True, narrator="Mai", source="owner")
    teller_voice.ensure(paths.root, db, settings)
    request_speaker(paths.root, "c2s2", "sha-c2s2", "MAI", now=10)
    db.apply_listener_speaker(stable_id="c2s2", text_sha256="sha-c2s2", speaker="MAI")
    chosen = rows(db)["c2s2"]
    narrator_sections.forget(paths.root, 2, 0, 2)
    teller_voice.ensure(paths.root, ProjectDB(paths.db), settings)
    assert rows(db)["c2s2"] == chosen


def test_section_undo_failure_rolls_back_provenance_and_can_retry_after_reopen(tmp_path, monkeypatch):
    paths, db, settings = _book(tmp_path, settings=_settings("Bao"), recorded=True)
    narrator_sections.decide(paths.root, 2, 0, 2, accepted=True, narrator="Mai", source="owner")
    teller_voice.ensure(paths.root, db, settings)
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET status='verified',wav_path='take.wav' WHERE stable_id='c2s2'")
        provenance = [tuple(r) for r in conn.execute("SELECT * FROM chapter_teller_lines ORDER BY segment_id")]
    before = rows(db)
    narrator_sections.forget(paths.root, 2, 0, 2)
    def crash(*args):
        raise RuntimeError("crash during undo")
    with monkeypatch.context() as m:
        m.setattr(db, "_reset_segment_pending_conn", crash)
        with pytest.raises(RuntimeError, match="crash during undo"):
            teller_voice.ensure(paths.root, db, settings)
    db = ProjectDB(paths.db)
    assert rows(db) == before
    with db.connect() as conn:
        assert [tuple(r) for r in conn.execute("SELECT * FROM chapter_teller_lines ORDER BY segment_id")] == provenance
    assert teller_voice.ensure(paths.root, db, settings)["chapterNarrator"]["redo"] == 1
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM chapter_teller_lines").fetchone()[0] == 0


def test_global_override_failure_rolls_back_profile_and_rows(tmp_path, monkeypatch):
    paths, db, settings = chapter_book(tmp_path, recorded=True)
    teller_voice.ensure(paths.root, db, settings)
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET status='verified',wav_path='take.wav' WHERE stable_id='c2s2'")
    before = rows(db)
    with db.connect() as conn:
        profiles = [tuple(r) for r in conn.execute("SELECT * FROM voice_profiles ORDER BY id")]
    def crash(*args):
        raise RuntimeError("crash before commit")
    with monkeypatch.context() as m:
        m.setattr(db, "_reset_segment_pending_conn", crash)
        with pytest.raises(RuntimeError, match="crash before commit"):
            db.apply_listener_voice(character="NARRATOR", voices=settings["voices"], preset="Thái Sơn")
    db = ProjectDB(paths.db)
    assert rows(db) == before
    with db.connect() as conn:
        assert [tuple(r) for r in conn.execute("SELECT * FROM voice_profiles ORDER BY id")] == profiles
    assert db.apply_listener_voice(character="NARRATOR", voices=settings["voices"], preset="Thái Sơn")["reset_segments"] == 1


@pytest.mark.parametrize("explicit", [False, True])
def test_cli_settings_file_marks_auto_only_without_explicit_voice(tmp_path, capsys, explicit):
    source = tmp_path / "001.txt"
    source.write_text("A short story.", encoding="utf-8")
    config = build_settings()
    config["voices"]["first_person_identity"] = "Mai"
    if explicit:
        config["voices"]["narrator_voice"] = "Thái Sơn"
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps(config), encoding="utf-8")
    output = tmp_path / "out"
    assert cli.main(["create", "--files", str(source), "--output-root", str(output), "--title", "T", "--settings-file", str(settings_file), "--json"]) == 0
    project = next(output.rglob("project.sqlite3")).parent
    assert teller_voice.read(project)["narratorAuto"] is not explicit
