"""B (tuỳ chọn, mặc định tắt): người kể "tôi" tự kể chuyện - câu lời kể của đoạn do họ kể đọc bằng giọng của chính họ.
Bật khi sách đã có bản thu thì chỉ những câu đổi giọng bị thu lại; tắt trả về đúng như trước (`applied["teller"]`)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from abook import narrator_sections, teller_voice
from abook.character_registry import assert_voice_stability
from abook.config import build_settings
from abook.database import LISTENER_REDO, ProjectDB
from abook.voice_catalog import casting_presets
from tests.test_teller_voice import _book, _events, _settings, _speakers


def _rows(db: ProjectDB) -> list[tuple]:
    with db.connect() as conn:
        return [tuple(row) for row in conn.execute(
            "SELECT stable_id, speaker, canonical_character_id, voice_profile_id, status FROM segments ORDER BY stable_id")]


def _record_everything(db: ProjectDB) -> None:
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET status='verified', wav_path='take.wav', wav_sha256='sha'")
        conn.execute("UPDATE chapters SET status='completed'")


def _profile_of(db: ProjectDB, stable_id: str) -> tuple[int, int, str]:
    with db.connect() as conn:
        row = conn.execute("SELECT canonical_character_id, voice_profile_id, speaker FROM segments WHERE stable_id=?", (stable_id,)).fetchone()
    return int(row[0]), int(row[1]), str(row[2])


def test_the_switch_is_off_by_default_and_a_book_stays_as_it_was(tmp_path: Path) -> None:
    paths, db, settings = _book(tmp_path)
    assert teller_voice.read(paths.root)["mode"] == "narrator"

    teller_voice.ensure(paths.root, db, settings)

    assert _speakers(db)["c1s0"] == "NARRATOR" and _speakers(db)["c2s2"] == "NARRATOR"


def test_explicit_teller_voice_preserves_identity_and_thoughts(tmp_path):
    paths,db,settings=_book(tmp_path)
    before=_rows(db)
    teller_voice.set_mode(paths.root,'teller')
    result=teller_voice.ensure(paths.root,db,settings)
    assert result['teller']['narration']==3
    assert _speakers(db)['c1s0']=='NARRATOR'
    assert _profile_of(db,'c1s0')[1]==_profile_of(db,'c1s1')[1]
    assert [(r[0],r[1],r[2]) for r in _rows(db)]==[(r[0],r[1],r[2]) for r in before]
    assert_voice_stability(db)


def test_applying_twice_changes_nothing_more(tmp_path: Path) -> None:
    paths, db, settings = _book(tmp_path)
    teller_voice.set_mode(paths.root, "teller")
    teller_voice.ensure(paths.root, db, settings)
    before = (_rows(db), teller_voice.read(paths.root))

    assert teller_voice.ensure(paths.root, db, settings) == {}

    assert (_rows(db), teller_voice.read(paths.root)) == before


def test_turning_it_off_restores_the_original_profiles_and_preserves_thoughts(tmp_path):
    paths,db,settings=_book(tmp_path)
    before=_rows(db)
    teller_voice.set_mode(paths.root,'teller')
    teller_voice.ensure(paths.root,db,settings)
    teller_voice.set_mode(paths.root,'narrator')
    teller_voice.ensure(paths.root,db,settings)
    assert _rows(db)==before
    assert teller_voice.ensure(paths.root,db,settings)=={}


def test_turning_it_on_after_recording_resets_only_the_lines_whose_voice_changes_and_says_the_price_first(tmp_path: Path) -> None:
    paths, db, settings = _book(tmp_path)
    _record_everything(db)
    teller_voice.set_mode(paths.root, "teller")
    with db.connect() as conn:
        plan = teller_voice.mode_plan(conn, paths.root, teller_voice.tellers_of(paths.root, settings, conn))
    assert plan == {"direction": "on", "lines": 3, "recorded": 3, "tellers": ["Mai"]}

    result = teller_voice.ensure(paths.root, db, settings)

    assert result["teller"]["redo"] == 3
    statuses = {row[0]: row[4] for row in _rows(db)}
    assert {statuses[i] for i in ("c1s0", "c1s4", "c2s2")} == {"analyzed"}
    assert {statuses[i] for i in ("c1s1", "c1s2", "c1s3", "c2s0", "c2s1")} == {"verified"}, "câu không đổi giọng giữ bản thu"
    with db.connect() as conn:
        chapters = conn.execute("SELECT status, last_error FROM chapters").fetchall()
    assert {row[0] for row in chapters} == {"warning"} and all(str(row[1]).startswith(LISTENER_REDO) for row in chapters)

    teller_voice.set_mode(paths.root, "narrator")
    with db.connect() as conn:
        assert teller_voice.mode_plan(conn, paths.root, teller_voice.tellers_of(paths.root, settings, conn))["direction"] == "off"
    teller_voice.ensure(paths.root, db, settings)
    assert _speakers(db)["c1s0"] == "NARRATOR"


def test_explicit_section_voice_uses_the_tellers_profile_and_keeps_identity(tmp_path):
    paths,db,settings=_book(tmp_path)
    narrator_sections.decide(paths.root,1,0,0,accepted=True,narrator='',source='owner')
    narrator_sections.decide(paths.root,1,4,4,accepted=True,narrator='Bao',source='owner')
    before=_rows(db)
    teller_voice.set_mode(paths.root,'teller')
    teller_voice.ensure(paths.root,db,settings)
    assert _profile_of(db,'c1s4')[1]==_profile_of(db,'c1s3')[1]
    assert _profile_of(db,'c2s2')[1]==_profile_of(db,'c1s1')[1]
    assert _rows(db)[0]==before[0]
    assert _speakers(db)['c1s4']=='NARRATOR'


def test_a_teller_without_a_voice_of_their_own_is_left_alone(tmp_path: Path) -> None:
    paths, db, settings = _book(tmp_path, settings=_settings(identity="Lan"))
    teller_voice.set_mode(paths.root, "teller")

    teller_voice.ensure(paths.root, db, settings)

    assert _speakers(db)["c1s0"] == "NARRATOR" and _speakers(db)["c2s2"] == "NARRATOR"


def test_teller_profile_retargets_on_the_next_worker_check(tmp_path):
    paths,db,settings=_book(tmp_path)
    teller_voice.set_mode(paths.root,'teller')
    teller_voice.ensure(paths.root,db,settings)
    with db.connect() as conn:
        taken={r[0] for r in conn.execute('SELECT preset_name FROM voice_profiles')}
    other=next(p['name'] for p in casting_presets('female') if p['name'] not in taken)
    db.apply_listener_voice(character='Mai',voices=build_settings()['voices'],preset=other)
    teller_voice.ensure(paths.root,db,settings)
    assert _profile_of(db,'c1s0')[1]==_profile_of(db,'c1s1')[1]==_profile_of(db,'c2s2')[1]
    assert _speakers(db)['c1s0']=='NARRATOR'


def test_a_failed_voice_change_leaves_no_partial_profile_or_origin(tmp_path,monkeypatch):
    paths,db,settings=_book(tmp_path)
    before=_rows(db)
    teller_voice.set_mode(paths.root,'teller')
    def interrupted(*args,**kwargs):
        raise RuntimeError('interrupted')
    monkeypatch.setattr(teller_voice,'_move_lines',interrupted)
    with pytest.raises(RuntimeError,match='interrupted'):
        teller_voice.ensure(paths.root,db,settings)
    assert _rows(db)==before
    with db.connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM chapter_teller_lines').fetchone()[0]==0
    monkeypatch.undo()
    teller_voice.ensure(paths.root,db,settings)
    teller_voice.set_mode(paths.root,'narrator')
    teller_voice.ensure(paths.root,db,settings)
    assert _rows(db)==before


def test_a_third_person_book_ignores_the_switch(tmp_path: Path) -> None:
    paths, db, settings = _book(tmp_path, settings=_settings(identity=""))
    teller_voice.set_mode(paths.root, "teller")

    assert teller_voice.ensure(paths.root, db, settings) == {"skipped": "third_person"}
    assert _speakers(db)["c1s0"] == "NARRATOR"


def test_the_sidecar_keeps_the_studios_mode_when_the_worker_saves_its_part(tmp_path: Path) -> None:
    teller_voice.set_mode(tmp_path, "teller")
    teller_voice._save(tmp_path, applied={"thoughts": {"s": "MAI"}})

    record = teller_voice.read(tmp_path)

    assert record["mode"] == "teller" and record["applied"] == {"thoughts": {"s": "MAI"}}
    with pytest.raises(ValueError):
        teller_voice.set_mode(tmp_path, "robot")
