"""Synthetic regression cases for voice TN, ASR spelling aliases and take edges."""
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from abook import asr
from abook.audio_io import AudioQualityError, signal_metrics, validate_audio_array
from abook.config import build_settings
from abook.database import ProjectDB
from abook.readaloud.studio_tn import separate_digit_quotes, studio_tn
from abook.tts import TTSCoordinator


@pytest.mark.parametrize("mark", list('“”\"‘’\'′″‴‵‶‷⁗＂＇「」『』〝〞〟ʹʺʻʼʽʾʿˈˊˋˮ`´«»'))
def test_digit_quotes_removed_on_both_sides(mark):
    source = f'{mark}420000{mark}'
    voice, mapping = studio_tn(source, None, True)
    assert voice.strip() == '420000'
    assert mapping[-1] == len(voice)
    assert source == f'{mark}420000{mark}'


def test_quotes_around_words_and_ordinary_numbers_are_preserved():
    assert separate_digit_quotes('“bốn” 42 và 1998') == '“bốn” 42 và 1998'


@pytest.mark.parametrize('expected,heard', [
    ('Giá 420,000 đồng', 'Giá bốn trăm hai mươi nghìn đồng'),
    ('Giá 420.000 đồng', 'Giá 420 000 đồng'),
    ('Giá 420\u202f000 đồng', 'Giá 420000 đồng'),
    ('Giá 420,000.', 'Giá bốn trăm hai mươi nghìn.'),
    ('Giá 420.000, đủ rồi.', 'Giá bốn trăm hai mươi nghìn, đủ rồi.'),
])
def test_grouped_numbers_match_words_on_both_sides(expected, heard):
    assert asr.transcript_metrics(expected, heard) == (1.0, 0.0)
    assert asr.transcript_metrics(heard, expected) == (1.0, 0.0)


def test_decimals_and_digit_identifiers_are_not_thousands():
    assert asr.normalize_transcript('3,14') != asr.normalize_transcript('314')
    assert asr.normalize_transcript('1,2345') != asr.normalize_transcript('12345')
    assert asr.normalize_transcript('007') == '007'
    assert asr.normalize_transcript('12a') == '12a'


def test_optional_alias_keeps_voice_tn_and_punctuation_offsets(tmp_path):
    db, c, v = _coordinator(tmp_path)
    db.upsert_pronunciation(surface='Harumi', normalized_surface='harumi',
                            spoken_form='Mai-cồ', source='analysis', confidence=1, locked=True)
    from abook.readaloud.studio_tn import studio_tn
    source = 'Harumi, đã tới.'
    spoken, anchors = c.spoken_text_with_anchors({'text': source})
    assert spoken == studio_tn('Mai-cồ, đã tới.', None, False)[0]
    assert len(anchors) == 1
    anchor = anchors[0]
    assert spoken[anchor['spoken_start']:anchor['spoken_end']] == anchor['spoken_form']
    assert anchor['matched_surface'] == 'Harumi'


def _coordinator(tmp_path):
    db = ProjectDB(tmp_path / 'project.sqlite3')
    settings = build_settings()
    settings['asr'].update(min_similarity=.78, max_wer=.3, min_words=1)
    c = TTSCoordinator(settings, db, lambda _: None)
    c._book_origin = (None,)
    c._row_speaks_english = lambda _: False
    return db, c, asr.WhisperVerifier(settings, lambda _: None)


def _score(c, v, source, heard):
    spoken, anchors = c.spoken_text_with_anchors({'text': source})
    raw = v._evaluate_transcript(spoken, heard, 5)
    return asr.adjudicate_locked_name_anchors(
        spoken, raw, anchors, min_similarity=.78, max_wer=.3,
    )


@pytest.mark.parametrize('heard', ['Tôi gặp Harumi.', 'Tôi gặp Ha-ru-mi.', 'Tôi gặp Harumi.', 'Tôi gặp ha ru mi.'])
def test_locked_analysis_name_accepts_source_and_joined_reading(tmp_path, heard):
    db, c, v = _coordinator(tmp_path)
    db.upsert_pronunciation(surface='Harumi', normalized_surface='harumi',
                            spoken_form='Ha-ru-mi', source='analysis', confidence=1, locked=True)
    result = _score(c, v, 'Tôi gặp Harumi.', heard)
    assert result['verdict'] == asr.ASR_PASS


def test_automatic_english_transliteration_accepts_mixed_source_spellings(tmp_path):
    _db, c, v = _coordinator(tmp_path)
    spoken, anchors = c.spoken_text_with_anchors({'text': 'Please open the window.'})
    assert anchors and spoken != 'Please open the window.'
    assert _score(c, v, 'Please open the window.', 'please open the window')['verdict'] == asr.ASR_PASS


def test_name_alias_does_not_forgive_an_ordinary_wrong_word(tmp_path):
    db, c, v = _coordinator(tmp_path)
    db.upsert_pronunciation(surface='Harumi', normalized_surface='harumi',
                            spoken_form='Ha-ru-mi', source='listener_choice', confidence=1, locked=True)
    assert _score(c, v, 'Harumi nói rất thản nhiên.', 'Harumi nói rất thẳng nhiên.')['verdict'] == asr.ASR_MISMATCH


def test_initial_consonant_difference_uses_existing_anchor_review_rules(tmp_path):
    db, c, v = _coordinator(tmp_path)
    db.upsert_pronunciation(surface='Harumi', normalized_surface='harumi',
                            spoken_form='Ha-ru-mi', source='analysis', confidence=1, locked=True)
    result = _score(c, v, 'Harumi đã ngồi ở trên ghế.', 'Jarumi đã ngồi ở trên ghế.')
    assert result['verdict'] == asr.ASR_MISMATCH
    assert result['locked_name_review_eligible'] is True
    assert result[asr.LOCKED_NAME_ANCHOR_METRICS_KEY]['passed'] is False
    wrong = _score(c, v, 'Harumi đã ngồi ở trên ghế.', 'Jarumi đã ngồi ở trên đá.')
    assert wrong['verdict'] == asr.ASR_MISMATCH
    assert wrong['locked_name_review_eligible'] is False


def test_new_aliases_do_not_demote_an_existing_pass(tmp_path):
    db, c, v = _coordinator(tmp_path)
    db.upsert_pronunciation(surface='Harumi', normalized_surface='harumi',
                            spoken_form='Ha-ru-mi', source='analysis', confidence=1, locked=True)
    source = 'Harumi đã mang theo một chiếc hộp nhỏ để chúng tôi cùng xem.'
    spoken, _ = c.spoken_text_with_anchors({'text': source})
    heard = spoken.replace('Ha-ru-mi', 'Xa-ru-mi')
    assert v._evaluate_transcript(spoken, heard, 5)['verdict'] == asr.ASR_PASS
    assert _score(c, v, source, heard)['verdict'] == asr.ASR_PASS


@pytest.mark.parametrize('end,code', [(False, 'TTS_ACTIVE_ONSET'), (True, 'TTS_ACTIVE_OFFSET')])
def test_active_take_edge_rejected_even_with_zero_boundary_sample(end, code):
    settings = build_settings()
    sr = settings['tts']['sample_rate']
    t = np.arange(sr, dtype=np.float32) / sr
    audio = .12 * np.sin(2*np.pi*230*t)
    audio[:sr//20] = 0
    audio[-sr//20:] = 0
    if end:
        audio[-sr//200:] = .22
        audio[-1] = 0
    else:
        audio[:sr//200] = .22
        audio[0] = 0
    with pytest.raises(AudioQualityError, match=code):
        validate_audio_array(audio, 'Một câu thử.', settings, sr)
    assert signal_metrics(audio,sr)['offset_rms' if end else 'onset_rms'] > .05


def test_quiet_take_edges_pass():
    settings = build_settings()
    sr = settings['tts']['sample_rate']
    t = np.arange(sr,dtype=np.float32)/sr
    audio = .12*np.sin(2*np.pi*230*t)
    audio[:sr//20] = 0
    audio[-sr//20:] = 0
    validate_audio_array(audio, 'Một câu thử.', settings, sr)


def test_active_edge_uses_existing_pipeline_seed_retry(tmp_path, monkeypatch):
    from abook.pipeline import BookPipeline

    p = object.__new__(BookPipeline)
    p.settings = build_settings()
    p.settings['tts']['max_retries'] = 2
    p.quality_policy_hash = 'synthetic-policy'
    p.log = lambda _: None
    p._wait_pause_or_stop = lambda: None
    p._chunk_path = lambda _: tmp_path / 'take.wav'
    p._reset_tts_failure_streak = lambda: None
    committed = []
    p.db = SimpleNamespace(mark_generating=lambda *a, **k: None,
                           mark_signal_passed=lambda *a, **k: committed.append(k))
    salts = []
    def synthesize(row, output, *, seed_salt, **kwargs):
        salts.append(seed_salt)
        sr = p.settings['tts']['sample_rate']
        t = np.arange(sr,dtype=np.float32)/sr
        audio = .12*np.sin(2*np.pi*230*t)
        audio[:sr//20] = 0
        audio[-sr//20:] = 0
        if len(salts) == 1:
            audio[:sr//200] = .22
        _, metrics = validate_audio_array(audio, row['text'], p.settings, sr)
        return 'synthetic-checksum', metrics, len(salts)
    p.tts = SimpleNamespace(generation_seed=lambda *a: 17, synthesize_atomic=synthesize)
    # Bài này chỉ kiểm vòng seed; checkpoint giữ bản thu có bài tích hợp dùng SQLite/WAV thật.
    p._keep_usable_take = lambda *a: None
    p._accept_retained_take = lambda row: committed.append({'generation_seed': len(salts)})
    monkeypatch.setattr('abook.pipeline.time.sleep', lambda _: None)
    p._process_single_segment({'id': 1, 'stable_id': 'synthetic', 'text': 'Một câu thử.'}, {})
    assert salts == ['primary_0', 'primary_1']
    assert len(committed) == 1 and committed[0]['generation_seed'] == 2


@pytest.mark.parametrize('quoted', ['“420000”', '420000"', '1998′', '420000❞', '420000〃'])
def test_real_cpu_phonemizer_matches_the_unquoted_number(quoted):
    p = pytest.importorskip('vieneu_utils.phonemize_text')
    from abook.readaloud import vieneu

    digits = ''.join(c for c in quoted if c.isdigit())
    voice, _ = studio_tn(quoted, None, True)
    assert p.phonemize_text(voice) == p.phonemize_text(digits)
    heard_now = ' '.join(vieneu.spoken_tokens([quoted]))
    assert p.phonemize_text(heard_now) == p.phonemize_text(digits)


def test_real_phonemizer_counted_thousands_are_kept_after_quote_fix():
    p = pytest.importorskip('vieneu_utils.phonemize_text')
    source = '“420,000” đồng'
    voice, _ = studio_tn(source, None, True)
    assert p.phonemize_text(voice) == p.phonemize_text('420000 đồng')
    assert p.phonemize_text('420,000 đồng') != p.phonemize_text(voice)


def test_unqualified_single_group_number_keeps_its_separator():
    # A single group without counting context is intentionally ambiguous.
    voice, mapping = studio_tn('"420,000"', None, True)
    assert voice.strip() == '420,000'
    assert mapping[-1] == len(voice)
