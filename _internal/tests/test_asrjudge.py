"""Conservative alias, regional name spelling and marked-stretch regressions."""
import unicodedata

import pytest

from abook import asr
from abook.config import build_settings
from abook.readaloud import shouts, vieneu, vieneu_engine
from abook.tts import TTSCoordinator


def adjudicate(spoken, heard, *, form="Ha-ru-mi", surface="Harumi", region="", alias=True):
    anchor = dict(surface=surface, spoken_form=form, spoken_start=spoken.index(form),
                  spoken_end=spoken.index(form) + len(form), asr_alias_only=alias)
    raw = asr.WhisperVerifier(build_settings(), lambda _: None)._evaluate_transcript(spoken, heard, 8)
    return asr.adjudicate_locked_name_anchors(spoken, raw, [anchor],
        min_similarity=.78, max_wer=.3, voice_region=region)


@pytest.mark.parametrize("word,heard", [("thổi", "thối"), ("lẳng", "lặng"), ("thể", "thế")])
def test_alias_accepts_only_tone_changes(word, heard):
    result = adjudicate(f"Ha-ru-mi nói rất {word} rồi.", f"Harumi nói rất {heard} rồi.")
    assert result['verdict'] == asr.ASR_PASS


@pytest.mark.parametrize("word,heard", [("thản", "thẳng"), ("sưởi", "sửa"), ("cúi", "cuối"), ("ghế", "đá")])
def test_alias_keeps_vowel_quality_codas_and_wrong_words(word, heard):
    result = adjudicate(f"Ha-ru-mi nói rất {word} rồi.", f"Harumi nói rất {heard} rồi.", region="Bắc")
    assert result['verdict'] == asr.ASR_MISMATCH


@pytest.mark.parametrize("region,passed", [("Bắc", True), ("Nam", False), ("Trung", False), ("", False)])
def test_ordinary_dialect_folding_uses_the_voice_region(region, passed):
    result = adjudicate("Ha-ru-mi cứ chần chừ rồi.", "Harumi cứ trần trừ rồi.", region=region)
    assert (result['verdict'] == asr.ASR_PASS) is passed


@pytest.mark.parametrize("form,surface,heard,region,passed", [
    ("Ri-ta", "Rita", "zita", "Nam", True),
    ("Ri-ta", "Rita", "zita", "Bắc", True),
    ("Ri-ta", "Rita", "dita", "Nam", False),
    ("Ri-ta", "Rita", "dita", "Bắc", True),
    ("Dô-na", "Dona", "yona", "Nam", True),
    ("Dô-na", "Dona", "yona", "Bắc", False),
    ("Sát-ta", "Shasta", "sata", "Nam", True),
    ("Pha-na", "Fana", "fana", "Nam", True),
    ("Oan", "Wan", "wan", "Nam", True),
    ("Ri-ta", "Rita", "zita", "", False),
    ("Ri-ta", "Rita", "zita", "Trung", False),
    ("Lu-si-en", "Lucien", "Lucy", "Nam", False),
    ("Lu-si-en", "Lucien", "Lusienne", "Bắc", False),
    ("Xa-men", "Samael", "Sam Min", "Nam", False),
    ("Mi-đô", "Midou", "Mido", "Nam", True),
    ("Rin-đô", "Rindou", "Jindo", "Bắc", True),
    ("i-ta-đa-ki-ma-xu", "Itadakimatsu", "Itadakimasu", "Bắc", True),
    ("Ra", "Raa", "đa", "Bắc", False),
    ("Đa", "Daa", "ra", "Bắc", False),
    ("Đa", "Daa", "gia", "Bắc", False),
])
def test_names_compare_exact_sounds_and_keep_region_boundaries(form, surface, heard, region, passed):
    spoken = f"Anh {form}."
    result = adjudicate(spoken, f"Anh {heard}.", form=form, surface=surface, region=region, alias=False)
    assert (result['verdict'] == asr.ASR_PASS) is passed


def test_regional_folding_never_changes_sentence_phonemes():
    original = asr._segmental_phonemes('zita')
    adjudicate('Anh Ri-ta.', 'Anh zita.', form='Ri-ta', surface='Rita', region='Nam')
    assert asr._segmental_phonemes('zita') == original


@pytest.mark.parametrize("preset,expected", [("Đức Trí", "Nam"), ("Ngọc Linh", "Bắc"), ("unknown", "")])
def test_effective_locked_profile_provides_region(preset, expected):
    co = object.__new__(TTSCoordinator)
    co._voice_profile_for_row = lambda row: {'engine':'vieneu', 'preset_name':preset}
    assert co.voice_region_for_row({}) == expected


def test_pipeline_passes_effective_region_to_direct_repeat_and_collapsed(tmp_path, monkeypatch):
    from tests.test_pipeline_mock import _asr_signal_pipeline, _asr_result
    from abook import pipeline as module

    pipeline, _chapter, row, _expected = _asr_signal_pipeline(tmp_path, repair_rounds=0)
    pipeline.tts.spoken_text_with_anchors = lambda _: (
        'Anh Ri-ta!', [dict(surface='Rita', spoken_form='Ri-ta', spoken_start=4, spoken_end=9)])
    pipeline.tts.voice_region_for_row = lambda _: 'Nam'
    seen = []
    def direct(*args, **kw):
        seen.append(('anchor', kw['voice_region'], kw.get('repeat_count', 1)))
        return dict(args[1])
    def collapsed(*args, **kw):
        seen.append(('collapsed', kw['voice_region'], kw['requested_repeat_count']))
        return None
    monkeypatch.setattr(module, 'adjudicate_locked_name_anchors', direct)
    monkeypatch.setattr(module, 'adjudicate_collapsed_repeated_short', collapsed)
    class Verifier:
        def verify(self, *args, **kw):
            return _asr_result(asr.ASR_MISMATCH, 'Anh zita', similarity=.5, wer=.5)
        verify_repeated_short = verify
        def can_verify_repeated_short(self, text):
            return True
    pipeline._decode_audio_candidate(dict(row), Verifier(), confirmation=False,
        repair_round=None, delivery_mode='primary')
    assert seen == [('anchor', 'Nam', 1), ('anchor', 'Nam', 3), ('collapsed', 'Nam', 3)]


@pytest.mark.parametrize("text,reading", [
    ("đââââââyy", "đây…"), ("Eeeê", "ê… ê"), ("Gìì", "gì… ì"),
    ("Gaààoo", "gào… ò"), ("Piiim", "pim… i"), ("Êii", "ê… i"),
    ("ớớ", "ớ… ớ"), ("ừừ", "ừ… ừ"), ("Ưư", "ư… ư"), ("hẵẵng", "hẵng…"), ("bậập", "bập…"),
])
def test_marked_stretches_are_readable_before_g2p(text, reading):
    assert shouts.stretch_reading(text) == reading
    assert shouts.stretch_reading(unicodedata.normalize('NFD', text)) == reading
    pieces = vieneu.spoken_tokens([text])
    assert pieces == [reading]
    phones = vieneu_engine.phonemize(pieces, source=text)
    assert phones == vieneu_engine.phonemize([reading], source=reading)


def test_stretch_transforms_voice_text_and_invalidates_clip_cache_only():
    source = 'Phi về đââââââyy!'
    shown, units = vieneu.units(source, 256, None)
    assert ' '.join(shown) == source
    assert 'đââ' not in ' '.join(piece for unit in units for piece in unit.pieces)
    assert 'shouts2' in vieneu.reading_tag(source, None)


@pytest.mark.parametrize("vowel", list("aăâeêioôơuưy"))
@pytest.mark.parametrize("tone", list("\u0300\u0301\u0303\u0309\u0323"))
def test_every_vietnamese_vowel_and_tone_collapses(vowel, tone):
    char = unicodedata.normalize('NFC', unicodedata.normalize('NFD', vowel) + tone)
    chars = shouts._letters(char * 4)
    assert shouts._runs(chars) == [(0, 4)]
    assert shouts._run_char(chars) == char
    # Short vowels need a coda; y needs an onset. Test legal syllables,
    # rather than asking the reader to invent a pronunciation for bare ă/â.
    core = 'b' + char * 4 + 'n' if vowel in 'ăâ' else 't' + char * 4 if vowel == 'y' else char * 4
    reading = shouts.stretch_reading(core)
    assert reading is not None
    assert char * 2 not in reading
    assert shouts.stretch_reading(char * 4) is not None


@pytest.mark.parametrize('text,expected', [('âââ', 'ơ… ơ'), ('ắắ', 'á… á'), ('ỳỳ', 'ì… ì')])
def test_bare_short_vowel_cries_use_a_readable_sustained_vowel(text, expected):
    assert shouts.stretch_reading(text) == expected


@pytest.mark.parametrize("word", ["cứu", "hưu", "lưu", "mưu", "bưu", "cừu", "tửu", "ưu", "hữu", "cựu",
                                 "soóc", "moóc", "goòng", "voọc", "boong", "xoong", "khuỷu", "hươu", "rượu"])
def test_real_syllables_are_never_stretched(word):
    for text in (word, word.title(), word.upper(), unicodedata.normalize('NFD', word)):
        assert shouts.stretch_reading(text) is None


def test_help_sentence_preserves_ordinary_words():
    from abook.readaloud.studio_tn import studio_tn
    assert studio_tn("Hãy cứu tôi với!", None, False)[0] == "Hãy cứu tôi với!"
    assert shouts._vowel_family('ứ') != shouts._vowel_family('ú')


@pytest.mark.parametrize("left,right", [("tay", "tai"), ("hay", "hai"), ("tuy", "tui"),
                                       ("ra", "đa"), ("giá", "đã"), ("da", "đa")])
@pytest.mark.parametrize("region", ["Bắc", "Nam", "Trung", ""])
def test_conservative_alias_does_not_merge_different_words(left, right, region):
    a, b = (asr._normalize_anchor_transcript(w) for w in (left, right))
    assert asr._ordinary_alias_key(a, region) != asr._ordinary_alias_key(b, region)
    if (left, right) != ('da', 'đa'):
        # Existing sentence-level d/đ normalization may already pass da/đa.
        # This task preserves old passes; the additional alias must stay distinct.
        result = adjudicate(f"Ha-ru-mi nói rất {left} rồi.", f"Harumi nói rất {right} rồi.", region=region)
        assert result['verdict'] == asr.ASR_MISMATCH


def test_name_folds_keep_syllabic_gi_and_initial_tr():
    assert asr._name_spelling_key('tri', 'Bắc') == 'chi'
    assert asr._name_spelling_key('hagicano', 'Bắc') == 'hadicano'
    assert asr._name_spelling_key('gi', 'Nam') == 'di'
    assert asr._name_phonemes('gi', '') == asr._name_phonemes('di', '')
    assert asr._ordinary_alias_key('lý', 'Bắc') == asr._ordinary_alias_key('lí', 'Bắc')
    assert asr._name_spelling_key('tay', 'Bắc') != asr._name_spelling_key('tai', 'Bắc')


def test_pipeline_persists_spelling_alias_evidence_without_changing_verdict(tmp_path):
    import json
    from tests.test_pipeline_mock import _asr_signal_pipeline, _asr_result

    pipeline, _chapter, row, expected = _asr_signal_pipeline(tmp_path, repair_rounds=0)
    alias_evidence = {'anchors': [{'surface': 'Rita', 'status': 'mismatch', 'voice_region': 'Nam'}]}
    result = _asr_result(asr.ASR_PASS, expected, similarity=1.0, wer=0.0)
    result['spelling_alias_evidence'] = alias_evidence
    evidence = pipeline._record_segment_asr_decode_evidence(dict(row), result, confirmation=False,
        context_mode='direct', selected=True, repair_round=None, delivery_mode='primary')
    assert evidence['verdict'] == asr.ASR_PASS
    assert evidence['spelling_alias_evidence'] == alias_evidence
    with pipeline.db.connect() as conn:
        stored = conn.execute("SELECT metrics_json FROM quality_checks WHERE stage='segment_asr_decode_v1' ORDER BY id DESC").fetchone()
    assert json.loads(stored[0])['spelling_alias_evidence'] == alias_evidence
