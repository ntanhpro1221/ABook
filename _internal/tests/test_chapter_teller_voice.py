"""Narration voice opt-in preserves identity and supports atomic undo; CPU only."""
from pathlib import Path
import pytest
from abook import teller_voice, narrator_sections
from abook.database import ProjectDB
from abook.character_registry import assert_voice_stability
from tests.test_teller_voice import _book, _settings

def rows(db):
    return {r['stable_id']:dict(r) for r in db.list_segments()}

@pytest.mark.parametrize('identity,chapters', [('Mai',{}),('Bao',{'2':'Mai'}),('',{'2':'Mai'}),('Mai',{'2':''})])
@pytest.mark.parametrize('recorded', [False,True])
def test_chapter_and_section_tellers_do_not_automatically_change_voices(tmp_path,identity,chapters,recorded):
    paths, db, settings = _book(tmp_path, settings=_settings(identity,chapters),recorded=recorded)
    narrator_sections.decide(paths.root,1,0,4,accepted=True,narrator='Bao',source='owner')
    before=rows(db)
    teller_voice.ensure(paths.root,db,settings)
    teller_voice.ensure(paths.root,ProjectDB(paths.db),settings)
    assert rows(db)==before

def test_explicit_chapter_voice_changes_presentation_and_undo_restores_profiles(tmp_path):
    paths,db,settings=_book(tmp_path,settings=_settings('Bao',{'2':'Mai'}))
    before=rows(db)
    teller_voice.set_mode(paths.root,'teller')
    teller_voice.ensure(paths.root,db,settings)
    after=rows(db)
    for sid, row in after.items():
        assert (row['speaker'],row['canonical_character_id']) == (before[sid]['speaker'],before[sid]['canonical_character_id'])
        if row['kind']=='thought':
            assert row==before[sid]
    assert after['c2s2']['voice_profile_id']==before['c1s1']['voice_profile_id']
    assert_voice_stability(db)
    db=ProjectDB(paths.db)
    assert teller_voice.ensure(paths.root,db,settings)=={}
    teller_voice.set_mode(paths.root,'narrator')
    teller_voice.ensure(paths.root,db,settings)
    for sid,row in rows(db).items():
        for field in ('speaker','canonical_character_id','voice_profile_id'):
            assert row[field]==before[sid][field]
    assert_voice_stability(db)

@pytest.mark.parametrize('fail_at',[1,2,3])
def test_profile_change_and_provenance_roll_back_together(tmp_path,monkeypatch,fail_at):
    paths,db,settings=_book(tmp_path)
    before=rows(db)
    teller_voice.set_mode(paths.root,'teller')
    original=teller_voice._move_lines
    count=0
    def interrupted(*args,**kwargs):
        nonlocal count
        count+=1
        result=original(*args,**kwargs)
        if count==fail_at:
            raise RuntimeError('interrupted transaction')
        return result
    monkeypatch.setattr(teller_voice,'_move_lines',interrupted)
    with pytest.raises(RuntimeError,match='interrupted'):
        teller_voice.ensure(paths.root,db,settings)
    assert rows(db)==before
    with db.connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM chapter_teller_lines').fetchone()[0]==0
    monkeypatch.undo()
    teller_voice.ensure(paths.root,ProjectDB(paths.db),settings)
    assert rows(db)['c1s0']['voice_profile_id']==before['c1s1']['voice_profile_id']


def test_committed_voice_change_is_undoable_after_a_sidecar_failure(tmp_path,monkeypatch):
    paths,db,settings=_book(tmp_path)
    before=rows(db)
    teller_voice.set_mode(paths.root,'teller')
    def interrupted(*args,**kwargs):
        raise RuntimeError('sidecar write interrupted')
    monkeypatch.setattr(teller_voice,'_save',interrupted)
    with pytest.raises(RuntimeError,match='sidecar'):
        teller_voice.ensure(paths.root,db,settings)
    assert rows(db)['c1s0']['voice_profile_id']==before['c1s1']['voice_profile_id']
    monkeypatch.undo()
    teller_voice.set_mode(paths.root,'narrator')
    teller_voice.ensure(paths.root,ProjectDB(paths.db),settings)
    for sid,row in rows(db).items():
        for field in ('speaker','canonical_character_id','voice_profile_id'):
            assert row[field]==before[sid][field]
