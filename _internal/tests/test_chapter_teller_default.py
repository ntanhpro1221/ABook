"""Chapter presentation regressions on invented sentences, without speech models."""
import json

import pytest

from abook import narrator_sections, teller_voice, voice_integrity
from abook.character_registry import assert_voice_stability
from abook.database import ProjectDB
from abook.webui import teller_mode
from tests.test_chapter_teller_voice import rows
from tests.test_teller_voice import _book, _settings


@pytest.mark.parametrize('kind', ['narration', 'dialogue', 'thought'])
@pytest.mark.parametrize('section', [False, True])
@pytest.mark.parametrize('recorded', [False, True])
def test_default_local_teller_voices_unrecorded_narrator_kinds_and_preserves_takes(tmp_path, kind, section, recorded):
    settings = _settings('Bao', {} if section else {'2': 'Mai'})
    paths, db, settings = _book(tmp_path, settings=settings)
    if section:
        narrator_sections.decide(paths.root, 2, 2, 2, accepted=True, narrator='Mai', source='owner')
    with db.transaction() as con:
        con.execute("UPDATE segments SET kind=?,gender='unknown' WHERE stable_id='c2s2'", (kind,))
        if recorded:
            con.execute("UPDATE segments SET status='verified',wav_path='before.wav',wav_sha256='before' WHERE stable_id='c2s2'")
    before = rows(db)
    teller_voice.ensure(paths.root, db, settings)
    after = rows(db)
    expected = before['c2s2'] if recorded else before['c1s1']
    assert after['c2s2']['voice_profile_id'] == expected['voice_profile_id']
    if recorded:
        assert after['c2s2'] == before['c2s2']
    else:
        assert after['c2s2']['wav_sha256'] is None
        assert after['c2s2']['status'] == 'analyzed'
    for sid in before:
        assert (after[sid]['speaker'], after[sid]['canonical_character_id']) == (before[sid]['speaker'], before[sid]['canonical_character_id'])
        if sid == 'c2s1' and section:
            assert after[sid]['voice_profile_id'] == before['c1s0']['voice_profile_id']
        elif sid not in ('c2s2', 'c1s3'):
            assert after[sid] == before[sid]
    reopened = ProjectDB(paths.db)
    assert teller_voice.ensure(paths.root, reopened, settings) == {}
    assert rows(reopened) == after
    assert_voice_stability(reopened)
    issues = voice_integrity.audit(paths.root, chapter_ids={1, 2})['issues']
    assert bool([i for i in issues if i['code'] == 'VOICE_OWNER_MISMATCH']) is recorded
    # Removing the local decision restores the original profile after reopen.
    settings['voices']['first_person_chapters'] = {}
    if section:
        narrator_sections.decide(paths.root, 2, 2, 2, accepted=False, narrator='Mai', source='owner')
    teller_voice.ensure(paths.root, reopened, settings)
    assert rows(reopened)['c2s2']['voice_profile_id'] == before['c2s2']['voice_profile_id']


@pytest.mark.parametrize('wish', ['text', 'narrator', 'named', 'preset'])
def test_text_or_narrator_owner_wishes_keep_chapter_voice_but_named_choices_win(tmp_path, wish):
    paths, db, settings = _book(tmp_path, settings=_settings('Bao', {'2': 'Mai'}))
    overrides = {
        'text': {'lines': {'c2s2': {'spoken': 'Một câu đã sửa.'}}},
        'narrator': {'speakers': {'c2s2': {'speaker': 'NARRATOR'}}},
        'named': {'speakers': {'c2s2': {'speaker': 'BAO'}}},
        'preset': {'voices': {'NARRATOR': {'preset': settings['voices']['narrator_voice']}}},
    }[wish]
    (paths.root / 'overrides.json').write_text(json.dumps(overrides), encoding='utf-8')
    before = rows(db)
    teller_voice.ensure(paths.root, db, settings)
    expected = before['c1s1'] if wish in ('text', 'narrator') else before['c2s2']
    assert rows(db)['c2s2']['voice_profile_id'] == expected['voice_profile_id']


def test_default_chapter_profile_is_not_the_explicit_switch_and_its_price_is_correct(tmp_path):
    paths, db, settings = _book(tmp_path, settings=_settings('Bao', {'2': 'Mai'}))
    paths.settings.write_text(json.dumps(settings), encoding='utf-8')
    teller_voice.ensure(paths.root, db, settings)
    view = teller_mode.view(paths.root)
    assert view['mode'] == 'narrator' and not view['applied']
    assert view['plan']['direction'] == 'on'
    assert view['plan']['lines'] == 3
    teller_voice.set_mode(paths.root, 'teller')
    teller_voice.ensure(paths.root, db, settings)
    assert teller_mode.view(paths.root)['plan']['lines'] == 3
    teller_voice.set_mode(paths.root, 'narrator')
    teller_voice.ensure(paths.root, db, settings)
    assert rows(db)['c2s2']['voice_profile_id'] == rows(db)['c1s1']['voice_profile_id']
    assert teller_voice.ensure(paths.root, db, settings) == {}


def test_default_chapter_profile_and_provenance_roll_back_together(tmp_path, monkeypatch):
    paths, db, settings = _book(tmp_path, settings=_settings('Bao', {'2': 'Mai'}))
    before = rows(db)
    with monkeypatch.context() as patch:
        patch.setattr(teller_voice, '_move_lines', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('interrupted')))
        with pytest.raises(RuntimeError, match='interrupted'):
            teller_voice.ensure(paths.root, db, settings)
    reopened = ProjectDB(paths.db)
    assert rows(reopened) == before
    with reopened.connect() as con:
        assert con.execute('SELECT COUNT(*) FROM chapter_teller_lines').fetchone()[0] == 0
    teller_voice.ensure(paths.root, reopened, settings)
    assert rows(reopened)['c2s2']['voice_profile_id'] == before['c1s1']['voice_profile_id']
