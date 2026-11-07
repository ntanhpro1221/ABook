"""Synthetic voice ownership and recorded-provenance checks; no speech models."""
import json

import pytest

from abook import teller_voice, voice_integrity
from abook.analysis import _repair_in_sentence_quote_speakers
from abook.database import ProjectDB
from abook.webui import bookfile
from tests.test_chapter_teller_voice import rows
from tests.test_teller_voice import _book, _settings


def chapter_book(tmp_path, *, recorded=False):
    paths, db, settings = _book(tmp_path, settings=_settings("Bao", {"2": "Mai"}), recorded=recorded)
    teller_voice.set_mode(paths.root, "teller")
    return paths, db, settings


def ready(tmp_path):
    paths, db, settings = chapter_book(tmp_path, recorded=True)
    teller_voice.ensure(paths.root, db, settings)
    with db.transaction() as conn:
        for row in conn.execute('SELECT * FROM segments').fetchall():
            conn.execute("UPDATE segments SET status='verified',wav_path='take.wav',wav_sha256=?,signal_json=? WHERE id=?",
                         (f"wav-{row['stable_id']}", json.dumps({'voice_profile_id': row['voice_profile_id']}), row['id']))
    return paths, db, settings


def codes(paths, **kwargs):
    return {i['code'] for i in voice_integrity.audit(paths.root, **kwargs)['issues']}


def test_valid_book_audit_is_read_only(tmp_path):
    paths, db, _ = ready(tmp_path)
    before = rows(db)
    files = {p.relative_to(paths.root): p.read_bytes() for p in paths.root.rglob('*') if p.is_file()}
    report = voice_integrity.audit(paths.root)
    assert report['status'] == 'pass' and report['checked'] == len(before)
    assert rows(db) == before
    assert {p.relative_to(paths.root): p.read_bytes() for p in paths.root.rglob('*') if p.is_file()} == files


@pytest.mark.parametrize('kind', ['narration', 'dialogue', 'thought'])
def test_narrator_owner_is_checked_regardless_of_kind(tmp_path, kind):
    paths, db, _ = ready(tmp_path)
    with db.transaction() as conn:
        base = conn.execute("SELECT id FROM voice_profiles WHERE voice_key='narrator'").fetchone()[0]
        conn.execute('UPDATE segments SET kind=?,voice_profile_id=?,signal_json=? WHERE stable_id=?',
                     (kind, base, json.dumps({'voice_profile_id': base}), 'c2s2'))
    report = voice_integrity.audit(paths.root)
    mismatch = next(i for i in report['issues'] if i['code'] == 'VOICE_OWNER_MISMATCH')
    assert mismatch['stable_id'] == 'c2s2'
    assert mismatch['voice_current'] != mismatch['voice_correct']


def test_named_female_cast_to_male_is_blocked_even_if_signal_agrees(tmp_path):
    paths, db, _ = ready(tmp_path)
    before = rows(db)['c1s1']
    with db.transaction() as conn:
        base = conn.execute("SELECT id FROM voice_profiles WHERE voice_key='narrator'").fetchone()[0]
        key = conn.execute('SELECT voice_key FROM voice_profiles WHERE id=?', (before['voice_profile_id'],)).fetchone()[0]
        conn.execute('UPDATE characters SET locked_voice_key=? WHERE id=?', (key, before['canonical_character_id']))
        conn.execute('UPDATE segments SET voice_profile_id=?,signal_json=? WHERE stable_id=?',
                     (base, json.dumps({'voice_profile_id': base}), 'c1s1'))
    assert {'VOICE_OWNER_MISMATCH', 'VOICE_GENDER_MISMATCH'} <= codes(paths)


@pytest.mark.parametrize('signal', [None, {'voice_profile_id': 999},
                                    {'split_parts': 'invalid'}, {'parts': ['invalid']},
                                    {'split_parts': [{'voice_profile_id': 999}]},
                                    {'parts': [{'split_parts': [{'voice_profile_id': 999}]}]}])
def test_stale_or_mixed_short_piece_provenance_is_blocked(tmp_path, signal):
    paths, db, _ = ready(tmp_path)
    row = rows(db)['c2s2']
    if signal is not None and 'voice_profile_id' not in signal:
        signal = {'voice_profile_id': row['voice_profile_id'], **signal}
    with db.transaction() as conn:
        conn.execute('UPDATE segments SET signal_json=? WHERE stable_id=?', (json.dumps(signal), 'c2s2'))
    assert 'RECORDED_VOICE_MISMATCH' in codes(paths)


def test_retaken_row_cannot_certify_its_old_chapter_audio(tmp_path):
    paths, db, _ = ready(tmp_path)
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET status='analyzed',wav_sha256=NULL,signal_json=NULL WHERE stable_id='c2s2'")
    assert 'RECORDING_VOICE_UNPROVEN' in codes(paths, chapter_ids={2})


def test_ambiguous_narrator_gender_requires_attribution_review(tmp_path):
    paths, db, _ = ready(tmp_path)
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET kind='dialogue',gender='male' WHERE stable_id='c2s2'")
    assert 'SPEAKER_GENDER_CONFLICT' in codes(paths)


@pytest.mark.parametrize('status,checksum,expected', [('pass', 'match', set()),
    ('review', 'match', {'ACOUSTIC_VOICE_REVIEW'}), ('fail', 'match', {'ACOUSTIC_VOICE_REVIEW'}),
    ('pass', 'old', {'ACOUSTIC_EVIDENCE_INVALID'})])
def test_optional_acoustic_evidence_is_bound_to_the_take(tmp_path, status, checksum, expected):
    paths, db, _ = ready(tmp_path)
    def probe(row, profile):
        return {'status': status, 'wav_sha256': row['wav_sha256'] if checksum == 'match' else 'old',
                'expected_profile_id': profile['id']}
    assert codes(paths, acoustic_probe=probe) == expected


def test_acoustic_pass_for_a_different_expected_voice_is_rejected(tmp_path):
    paths, db, _ = ready(tmp_path)
    def probe(row, profile):
        return {'status': 'pass', 'wav_sha256': row['wav_sha256'], 'expected_profile_id': -1}
    assert codes(paths, acoustic_probe=probe) == {'ACOUSTIC_EVIDENCE_INVALID'}


def test_a_text_edit_wish_does_not_exempt_an_incorrect_chapter_voice(tmp_path):
    paths, db, _ = ready(tmp_path)
    with db.transaction() as conn:
        base = conn.execute("SELECT id FROM voice_profiles WHERE voice_key='narrator'").fetchone()[0]
        conn.execute('UPDATE segments SET voice_profile_id=?,signal_json=? WHERE stable_id=?',
                     (base, json.dumps({'voice_profile_id': base}), 'c2s2'))
    (paths.root / 'overrides.json').write_text(json.dumps({'lines': {'c2s2': {'spoken': 'Lời đọc đã sửa'}}}), encoding='utf-8')
    assert 'VOICE_OWNER_MISMATCH' in codes(paths)


@pytest.mark.parametrize('series', [False, True])
def test_export_blocks_before_word_alignment_or_publication(tmp_path, monkeypatch, series):
    paths, db, _ = ready(tmp_path)
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET signal_json='{}' WHERE stable_id='c2s2'")
    monkeypatch.setattr(bookfile.store, 'chapter_audio_paths', lambda _: {2: tmp_path / 'unused.mp3'})
    def forbidden(*args, **kwargs):
        pytest.fail('Word alignment ran before the voice gate')
    monkeypatch.setattr(bookfile, '_packaged_book', forbidden)
    out = tmp_path / 'book.abook'
    with pytest.raises(bookfile.BookFileError, match='c2s2'):
        bookfile.pack_series([paths.root], out) if series else bookfile.pack(paths.root, out)
    assert not out.exists()


@pytest.mark.parametrize('kind', ['dialogue', 'thought'])
def test_quoted_narrator_reset_reopen_and_undo(tmp_path, kind):
    paths, db, settings = chapter_book(tmp_path, recorded=True)
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET kind=?,status='verified',wav_path='old.wav',wav_sha256='old' WHERE stable_id='c2s2'", (kind,))
    before = rows(db)['c2s2']
    teller_voice.ensure(paths.root, db, settings)
    db = ProjectDB(paths.db)
    changed = rows(db)['c2s2']
    assert changed['voice_profile_id'] != before['voice_profile_id']
    assert changed['status'] == 'analyzed' and changed['wav_path'] is None
    assert 'chapterNarrator' not in teller_voice.ensure(paths.root, db, settings)
    settings['voices']['first_person_chapters'] = {'2': 'Bao'}
    teller_voice.ensure(paths.root, db, settings)
    assert rows(db)['c2s2']['voice_profile_id'] == rows(db)['c1s3']['voice_profile_id']
    teller_voice.set_mode(paths.root, 'narrator')
    teller_voice.ensure(paths.root, db, settings)
    after = rows(db)['c2s2']
    assert (after['speaker'], after['canonical_character_id'], after['voice_profile_id']) == (
        before['speaker'], before['canonical_character_id'], before['voice_profile_id'])


def test_quoted_narrator_reset_failure_rolls_back_after_reopen(tmp_path, monkeypatch):
    paths, db, settings = chapter_book(tmp_path, recorded=True)
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET kind='dialogue',status='verified',wav_path='old.wav' WHERE stable_id='c2s2'")
    before = rows(db)
    with monkeypatch.context() as patch:
        patch.setattr(db, '_reset_segment_pending_conn', lambda *a: (_ for _ in ()).throw(RuntimeError('crash')))
        with pytest.raises(RuntimeError, match='crash'):
            teller_voice.ensure(paths.root, db, settings)
    reopened = ProjectDB(paths.db)
    assert rows(reopened) == before
    with reopened.connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM chapter_teller_lines').fetchone()[0] == 0
    assert teller_voice.ensure(paths.root, reopened, settings)['teller']['redo'] == 1


@pytest.mark.parametrize('speaker,gender', [('MAI', 'female'), ('BAO', 'male'), ('NPC_LOCAL::speaker', 'female')])
def test_inline_reported_words_cannot_erase_a_named_or_local_speaker(speaker, gender):
    group = [dict(stable_id='a', chapter_id=1, paragraph_index=1, text='Người ấy khẽ nói'),
             dict(stable_id='b', chapter_id=1, paragraph_index=1, text='“đợi thêm một chút”'),
             dict(stable_id='c', chapter_id=1, paragraph_index=1, text='rồi tiếp tục đi.')]
    result = {'a': {'kind': 'narration', 'speaker': 'NARRATOR'},
              'b': {'kind': 'dialogue', 'speaker': speaker, 'gender': gender},
              'c': {'kind': 'narration', 'speaker': 'NARRATOR'}}
    _repair_in_sentence_quote_speakers(group, result)
    assert result['b'] == {'kind': 'dialogue', 'speaker': speaker, 'gender': gender}


@pytest.mark.parametrize('kind,quote', [('dialogue', '“bản đồ sao”'), ('thought', '‘bản đồ sao’')])
@pytest.mark.parametrize('speaker', ['MAI', 'NPC_LOCAL::speaker', 'UNKNOWN', ''])
def test_inline_nominal_fragment_resolves_named_local_and_unknown_owners(kind, quote, speaker):
    group = [dict(stable_id='a', chapter_id=1, paragraph_index=1, text='Mai nhớ tới'),
             dict(stable_id='b', chapter_id=1, paragraph_index=1, text=quote),
             dict(stable_id='c', chapter_id=1, paragraph_index=1, text=', một món quà nhỏ.')]
    result = {'a': {'kind': 'narration', 'speaker': 'NARRATOR'},
              'b': {'kind': kind, 'speaker': speaker, 'gender': 'female'},
              'c': {'kind': 'narration', 'speaker': 'NARRATOR'}}
    _repair_in_sentence_quote_speakers(group, result)
    assert result['b']['speaker'] == 'NARRATOR'
    assert result['b']['kind'] == kind
    assert result['b']['gender'] == 'female'


def test_teller_presentation_preserves_named_thoughts_in_the_export_gate(tmp_path):
    paths, db, _ = ready(tmp_path)
    thought = rows(db)['c2s0']
    assert thought['speaker'] == 'MAI'
    assert thought['voice_profile_id'] == rows(db)['c1s1']['voice_profile_id']
    assert codes(paths) == set()


@pytest.mark.parametrize('missing_profile', [False, True])
def test_unattributed_thought_falls_back_to_the_chapter_teller(tmp_path, missing_profile):
    paths, db, settings = chapter_book(tmp_path, recorded=True)
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET kind='thought',speaker='UNKNOWN',canonical_character_id=NULL WHERE stable_id='c2s2'")
        if missing_profile:
            conn.execute("UPDATE segments SET voice_profile_id=NULL WHERE stable_id='c2s2'")
    original = rows(db)['c2s2']
    female = rows(db)['c1s1']['voice_profile_id']
    teller_voice.ensure(paths.root, db, settings)
    reopened = ProjectDB(paths.db)
    assert rows(reopened)['c2s2']['voice_profile_id'] == female
    assert rows(reopened)['c2s2']['speaker'] == 'UNKNOWN'
    assert rows(reopened)['c2s2']['canonical_character_id'] is None
    assert teller_voice.ensure(paths.root, reopened, settings) == {}
    with reopened.connect() as conn:
        assert teller_voice.mode_plan(conn, paths.root, teller_voice.tellers_of(paths.root, settings, conn))['direction'] == 'off'
    teller_voice.set_mode(paths.root, 'narrator')
    teller_voice.ensure(paths.root, reopened, settings)
    assert rows(reopened)['c2s2']['speaker'] == 'UNKNOWN'
    assert rows(reopened)['c2s2']['canonical_character_id'] is None
    assert rows(reopened)['c2s2']['voice_profile_id'] == female
    # Removing the local teller restores even an originally missing profile.
    settings['voices']['first_person_chapters'] = {}
    teller_voice.ensure(paths.root, reopened, settings)
    assert rows(reopened)['c2s2']['voice_profile_id'] == original['voice_profile_id']


@pytest.mark.parametrize('kind', ['dialogue', 'thought'])
def test_teller_mode_includes_quoted_narrator_lines_and_restores_them(tmp_path, kind):
    paths, db, settings = _book(tmp_path, settings=_settings('Bao'), recorded=True)
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET kind=? WHERE stable_id='c1s0'", (kind,))
    original = rows(db)['c1s0']
    own = rows(db)['c1s3']['voice_profile_id']
    teller_voice.set_mode(paths.root, 'teller')
    teller_voice.ensure(paths.root, db, settings)
    assert rows(ProjectDB(paths.db))['c1s0']['voice_profile_id'] == own
    teller_voice.set_mode(paths.root, 'narrator')
    teller_voice.ensure(paths.root, db, settings)
    after = rows(ProjectDB(paths.db))['c1s0']
    assert after['speaker'] == original['speaker']
    assert after['voice_profile_id'] == original['voice_profile_id']


def test_an_intermediate_listening_layer_remains_available_for_project_backup(tmp_path, monkeypatch):
    paths, db, _ = ready(tmp_path)
    def final_gate(*args, **kwargs):
        pytest.fail('An intermediate backup layer ran the final publication gate')
    monkeypatch.setattr(bookfile, '_require_voice_integrity', final_gate)
    monkeypatch.setattr(bookfile, '_packaged_book', lambda _: {'chapters': [], 'samples': []})
    monkeypatch.setattr(bookfile.store, 'recorded_cast', lambda _: {})
    monkeypatch.setattr(bookfile, '_add_chapters', lambda *a, **kw: None)
    monkeypatch.setattr(bookfile, '_add_texts', lambda *a, **kw: None)
    monkeypatch.setattr(bookfile.covers, 'cover_file', lambda _: None)
    book, _ = bookfile.listening_layer(paths.root)
    assert book['chapters'] == []


def test_a_same_gender_optional_engine_narrator_uses_the_catalog_gender(tmp_path):
    paths, db, _ = ready(tmp_path)
    with db.transaction() as conn:
        base = conn.execute("SELECT id FROM voice_profiles WHERE voice_key='narrator'").fetchone()[0]
        conn.execute("UPDATE voice_profiles SET preset_name='F1',engine='supertonic' WHERE id=?", (base,))
        conn.execute("UPDATE segments SET voice_profile_id=?,signal_json=? WHERE speaker='NARRATOR'",
                     (base, json.dumps({'voice_profile_id': base})))
    teller_voice.set_mode(paths.root, 'narrator')
    assert codes(paths, chapter_ids={2}) == set()
