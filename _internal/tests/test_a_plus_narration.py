"""The owner's A+, B and chapter verdicts, with invented text and CPU-only DBs."""
import json

import pytest

from abook import narrator_sections, teller_voice, voice_integrity
from abook.character_registry import assert_voice_stability, voice_profile_spec
from abook.database import ProjectDB
from abook.voice_catalog import VOICE_RANK, narrator_presets, preset_by_name
from tests.test_chapter_teller_voice import rows
from tests.test_teller_voice import _book, _events, _identities, _profiles, _settings


def test_female_narrator_ranking_matches_the_owner_and_mai_anh_is_unavailable():
    assert VOICE_RANK['narrator']['female'] == (
        ('Đoan Trang',), ('Ngọc Linh',), ('Kim Thanh', 'Mỹ Duyên', 'Quỳnh Anh', 'Thục Đoan'))
    names = [p['name'] for p in narrator_presets('female')]
    assert names[:2] == ['Đoan Trang', 'Ngọc Linh']
    assert 'Mai Anh' not in names


def test_alignment_skips_a_top_voice_held_even_by_a_silent_pinned_character(tmp_path):
    paths, db, settings = _book(tmp_path)
    profile = voice_profile_spec(preset_by_name('Đoan Trang'))
    db.upsert_voice_profile(profile)
    with db.transaction() as conn:
        conn.execute("INSERT INTO characters(canonical_name,display_name,gender,age,personality,importance,mention_count,confidence,locked,locked_voice_key,created_at,updated_at)"
                     " VALUES('LAN','Lan','female','adult','','minor',0,1,1,?,0,0)", (profile['voice_key'],))
    before = rows(db)
    teller_voice.ensure(paths.root, db, settings)
    with db.connect() as conn:
        assert conn.execute("SELECT preset_name FROM voice_profiles WHERE voice_key='narrator'").fetchone()[0] == 'Ngọc Linh'
    assert rows(db)['c1s1'] == before['c1s1']


@pytest.mark.parametrize('source', ['wish', 'event'])
def test_explicit_narrator_choice_suppresses_global_alignment(tmp_path, source):
    paths, db, settings = _book(tmp_path)
    if source == 'wish':
        (paths.root / 'overrides.json').write_text(json.dumps({'voices': {'NARRATOR': {'preset': 'Đức Trí'}}}), encoding='utf-8')
    else:
        db.event('info', 'VOICE_SET_BY_LISTENER', 'chosen', {'character': 'NARRATOR'})
    teller_voice.ensure(paths.root, db, settings)
    assert _events(db, 'NARRATOR_ALIGNED_TO_TELLER') == 0
    assert _profiles(db)['c1s2'] == _profiles(db)['c1s0']


def test_chapter_exception_compares_against_the_aligned_female_base(tmp_path):
    paths, db, settings = _book(tmp_path)
    # Two Mai chapters vs a Bao section: female book base, male local exception.
    narrator_sections.decide(paths.root, 1, 0, 4, accepted=True, narrator='Bao', source='owner')
    before = rows(db)
    teller_voice.ensure(paths.root, db, settings)
    after = rows(db)
    assert teller_voice.read(paths.root)['applied']['narrator']['to'] == 'Đoan Trang'
    assert after['c1s0']['voice_profile_id'] == after['c1s4']['voice_profile_id'] == before['c1s3']['voice_profile_id']
    assert after['c1s3']['voice_profile_id'] == before['c1s3']['voice_profile_id']
    assert after['c1s2']['voice_profile_id'] == before['c1s2']['voice_profile_id']
    assert after['c2s0']['voice_profile_id'] == after['c2s2']['voice_profile_id'] == before['c1s0']['voice_profile_id']
    assert_voice_stability(db)


def test_a_plus_b_and_back_restore_profiles_after_reopen_and_price_thoughts(tmp_path):
    paths, db, settings = _book(tmp_path)
    identities = _identities(db)
    teller_voice.ensure(paths.root, db, settings)
    baseline = _profiles(db)
    with db.connect() as conn:
        plan = teller_voice.mode_plan(conn, paths.root, teller_voice.tellers_of(paths.root, settings, conn))
    assert plan['lines'] == 5 and plan['recorded'] == 0
    teller_voice.set_mode(paths.root, 'teller')
    teller_voice.ensure(paths.root, ProjectDB(paths.db), settings)
    current = _profiles(db)
    assert current['c1s0'] == current['c1s1'] == current['c1s2'] == current['c2s0']
    assert current['c1s3'] != current['c1s0']
    teller_voice.set_mode(paths.root, 'narrator')
    teller_voice.ensure(paths.root, ProjectDB(paths.db), settings)
    assert _profiles(db) == baseline and _identities(db) == identities
    assert teller_voice.ensure(paths.root, db, settings) == {}


def test_thought_only_teller_can_switch_to_b_without_losing_the_original_voice(tmp_path):
    paths, db, settings = _book(tmp_path)
    with db.transaction() as conn:
        conn.execute("DELETE FROM segments WHERE stable_id='c1s1'")
    original = _profiles(db)['c1s2']
    teller_voice.ensure(paths.root, db, settings)
    assert _profiles(db)['c1s2'] != original
    teller_voice.set_mode(paths.root, 'teller')
    teller_voice.ensure(paths.root, ProjectDB(paths.db), settings)
    assert _profiles(db)['c1s0'] == _profiles(db)['c1s2'] == original


def test_removing_first_person_identity_restores_thought_profile_from_sqlite(tmp_path):
    paths, db, settings = _book(tmp_path)
    original = _profiles(db)
    teller_voice.ensure(paths.root, db, settings)
    settings['voices']['first_person_identity'] = ''
    teller_voice.ensure(paths.root, ProjectDB(paths.db), settings)
    assert _profiles(db) == original


def test_own_thought_profile_and_provenance_roll_back_on_failure(tmp_path, monkeypatch):
    paths, db, settings = _book(tmp_path, narrator_auto=False)
    before = rows(db)
    move = teller_voice._move_lines
    def crash(*args, **kwargs):
        move(*args, **kwargs)
        raise RuntimeError('thought transaction interrupted')
    with monkeypatch.context() as patch:
        patch.setattr(teller_voice, '_move_lines', crash)
        with pytest.raises(RuntimeError, match='thought transaction'):
            teller_voice.ensure(paths.root, db, settings)
    assert rows(ProjectDB(paths.db)) == before
    with db.connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM chapter_teller_lines').fetchone()[0] == 0
    teller_voice.ensure(paths.root, db, settings)
    assert _profiles(db)['c1s2'] == _profiles(db)['c1s0']


def test_voice_integrity_accepts_a_plus_thought_identity_and_detects_profile_tampering(tmp_path):
    paths, db, settings = _book(tmp_path)
    before = _profiles(db)
    teller_voice.ensure(paths.root, db, settings)
    with db.transaction() as conn:
        for row in conn.execute('SELECT * FROM segments').fetchall():
            conn.execute("UPDATE segments SET status='verified',wav_path='take.wav',wav_sha256=?,signal_json=? WHERE id=?",
                         (row['stable_id'], json.dumps({'voice_profile_id': row['voice_profile_id']}), row['id']))
    assert voice_integrity.audit(paths.root)['status'] == 'pass'
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET voice_profile_id=?,signal_json=? WHERE stable_id='c1s2'",
                     (before['c1s2'], json.dumps({'voice_profile_id': before['c1s2']})))
    assert any(i['stable_id'] == 'c1s2' and i['code'] == 'VOICE_OWNER_MISMATCH'
               for i in voice_integrity.audit(paths.root)['issues'])


@pytest.mark.parametrize('column,value', [('wav_path', 'take.wav'), ('wav_sha256', 'recorded-sha'), ('status', 'signal_passed')])
def test_any_recording_evidence_freezes_the_shared_narrator_profile(tmp_path, column, value):
    paths, db, settings = _book(tmp_path)
    with db.transaction() as conn:
        conn.execute(f"UPDATE segments SET {column}=? WHERE stable_id='c1s2'", (value,))
        before = dict(conn.execute("SELECT * FROM segments WHERE stable_id='c1s2'").fetchone())
    teller_voice.ensure(paths.root, db, settings)
    with db.connect() as conn:
        assert dict(conn.execute("SELECT * FROM segments WHERE stable_id='c1s2'").fetchone()) == before
    assert _events(db, 'NARRATOR_ALIGNED_TO_TELLER') == 0


@pytest.mark.parametrize('first_person', [False, True])
def test_read_only_audit_without_presentation_evidence_does_not_create_a_table(tmp_path, first_person):
    import hashlib
    import sqlite3
    from tests.test_webui_listen_and_sync import make_project

    project = make_project(tmp_path)
    if first_person:
        with sqlite3.connect(project / 'project.sqlite3') as conn:
            conn.execute('UPDATE book SET settings_json=?',
                         (json.dumps({'voices': {'first_person_identity': 'LUCIEN'}}),))
    path = project / 'project.sqlite3'
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    assert voice_integrity.audit(project, chapter_ids={1})['status'] == 'pass'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    with sqlite3.connect(path) as conn:
        assert not teller_voice.has_presentation_table(conn)


def test_listener_can_select_the_base_preset_to_undo_a_chapter_exception_after_a_plus(tmp_path):
    from abook.listener_overrides import _narrator_target, character_presets

    paths, db, settings = _book(tmp_path)
    narrator_sections.decide(paths.root, 1, 0, 4, accepted=True, narrator='Bao', source='owner')
    teller_voice.ensure(paths.root, db, settings)
    with db.connect() as conn:
        base = conn.execute("SELECT preset_name FROM voice_profiles WHERE voice_key='narrator'").fetchone()[0]
        assert base not in character_presets(conn)
        target, problem = _narrator_target(conn, preset=base, gender='', avoid='')
        assert problem is None and target['profile'] is not None
    before = _identities(db)
    result = db.apply_listener_voice(character='NARRATOR', voices=settings['voices'], preset=base)
    assert result is not None and 'problem' not in result
    teller_voice.ensure(paths.root, ProjectDB(paths.db), settings)
    profiles = _profiles(db)
    assert profiles['c1s0'] == profiles['c2s2']
    assert _identities(db) == before


def test_thought_only_actor_still_holds_the_original_voice_for_listener_narrator_choices(tmp_path):
    from abook.listener_overrides import _narrator_target, character_presets, VOICE_TAKEN

    paths, db, settings = _book(tmp_path)
    with db.transaction() as conn:
        original = conn.execute("SELECT v.preset_name FROM segments s JOIN voice_profiles v ON v.id=s.voice_profile_id WHERE s.stable_id='c1s2'").fetchone()[0]
        conn.execute("DELETE FROM segments WHERE stable_id='c1s1'")
    teller_voice.ensure(paths.root, db, settings)
    with db.connect() as conn:
        assert character_presets(conn)[original] == ['MAI']
        target, problem = _narrator_target(conn, preset=original, gender='', avoid='')
        assert target is None and problem == VOICE_TAKEN
