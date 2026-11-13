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


@pytest.mark.parametrize("region", ["", "Bắc", "Nam", "Trung"])
@pytest.mark.parametrize("alias", [False, True])
@pytest.mark.parametrize("repeat_count", [1, asr.SHORT_CONTEXT_REPEAT_COUNT])
@pytest.mark.parametrize("ordinary,heard", [
    ("đến đây rồi", "dến dây rồi"),
    ("đi đâu", "di đâu"),
    ("di dâu", "đi đâu"),
])
def test_name_sentence_keeps_legacy_d_stroke_pass(region, alias, repeat_count, ordinary, heard):
    # Synthetic sentences, including the review's transliterated-name scenario.
    spoken = f"Ha-ru-mi {ordinary}."
    transcript = " ".join([f"Harumi {heard}."] * repeat_count)
    anchor = dict(surface="Harumi", spoken_form="Ha-ru-mi", spoken_start=0,
                  spoken_end=len("Ha-ru-mi"), asr_alias_only=alias)
    raw = asr.WhisperVerifier(build_settings(), lambda _: None)._evaluate_transcript(
        " ".join([spoken] * repeat_count), transcript, 8 * repeat_count)
    result = asr.adjudicate_locked_name_anchors(
        spoken, raw, [anchor], repeat_count=repeat_count,
        min_similarity=.78, max_wer=.3, voice_region=region)
    assert result['verdict'] == asr.ASR_PASS
    metrics = result[asr.LOCKED_NAME_ANCHOR_METRICS_KEY]
    assert metrics['canonical_similarity'] == 1.0
    assert metrics['canonical_cer'] == metrics['canonical_wer'] == 0.0
    assert metrics['ordinary_exact_match_count'] == len(ordinary.split()) * repeat_count
    assert metrics['matched_occurrence_count'] == repeat_count


@pytest.mark.parametrize("fold_tone", [False, True])
@pytest.mark.parametrize("alias_region", [None, "", "Bắc", "Nam", "Trung"])
def test_canonical_metrics_fold_d_stroke_on_every_sentence_path(fold_tone, alias_region):
    # Exercise the metric boundary even if its caller retains name spelling.
    units = [dict(kind="token", token=word) for word in ["đến", "đây"]]
    operations = [dict(kind="substitute_token") for _ in units]
    assert asr._canonical_locked_name_metrics(
        units, operations, ["dến", "dây"], 0,
        fold_tone=fold_tone, ordinary_alias_region=alias_region) == (1.0, 0.0, 0.0)


@pytest.mark.parametrize("region", ["", "Bắc", "Nam", "Trung"])
def test_name_comparison_still_keeps_d_stroke(region):
    assert asr._normalize_anchor_transcript("Đa") == "đa"
    assert asr._name_spelling_key("Đa", region) != asr._name_spelling_key("ra", region)
    forms = asr._locked_name_anchor_forms(dict(spoken_form="Đa", surface="Daa"), region)
    assert any(tokens == ("đa",) for _, tokens, _ in forms)
    assert not asr._regional_syllables_match(("Đa",), "ra", region)
    result = adjudicate("Anh Đa.", "Anh ra.", form="Đa", surface="Daa",
                        region=region, alias=False)
    assert result['verdict'] == asr.ASR_MISMATCH


def test_sentence_stroke_and_regional_aliases_can_coexist_without_chaining():
    result = adjudicate("Ha-ru-mi đến đây cứ chần chừ.",
                        "Harumi dến dây cứ trần trừ.", region="Bắc")
    assert result['verdict'] == asr.ASR_PASS
    # A stroke folded to d cannot then acquire the regional d/gi/r merger.
    for spoken, heard in [("ra", "đa"), ("đa", "ra"), ("giá", "đã"), ("đã", "giá")]:
        result = adjudicate(f"Ha-ru-mi nói {spoken} rồi.",
                            f"Harumi nói {heard} rồi.", region="Bắc")
        assert result['verdict'] == asr.ASR_MISMATCH


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
    # Romaji "Yona" is read by the app's Japanese rule as Giô-na (o -> ô).
    ("Dô-na", "Dona", "yona", "Nam", True),
    ("Dô-na", "Dona", "yôna", "Nam", True),
    ("Dô-na", "Dona", "yona", "Bắc", True),
    ("Dô-na", "Dona", "yuna", "Bắc", False),
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
    ("Rin-đô", "Rindou", "Jindu", "Bắc", False),
    ("Rin-đô", "Rindou", "Jinđô", "Bắc", True),
    ("i-ta-đa-ki-ma-xu", "Itadakimatsu", "Itadakimasu", "Bắc", True),
    ("Ra", "Raa", "đa", "Bắc", False),
    ("Đa", "Daa", "ra", "Bắc", False),
    # The original integ168 component comparison already folded đ to d.
    ("Đa", "Daa", "gia", "Bắc", True),
])
def test_names_compare_exact_sounds_and_keep_region_boundaries(form, surface, heard, region, passed):
    spoken = f"Anh {form}."
    result = adjudicate(spoken, f"Anh {heard}.", form=form, surface=surface, region=region, alias=False)
    assert (result['verdict'] == asr.ASR_PASS) is passed


def test_regional_folding_never_changes_sentence_phonemes():
    original = asr._segmental_phonemes('zita')
    adjudicate('Anh Ri-ta.', 'Anh zita.', form='Ri-ta', surface='Rita', region='Nam')
    assert asr._segmental_phonemes('zita') == original


@pytest.mark.parametrize("left,right", [
    ("rư", "du"), ("rơ", "do"), ("râ", "da"), ("rê", "de"),
    ("riê", "di"), ("ră", "da"), ("rô", "do"),
])
@pytest.mark.parametrize("region", ["Bắc", "Nam", "Trung", ""])
def test_additional_name_paths_keep_vowel_quality(left, right, region):
    assert asr._name_spelling_key(left, region) != asr._name_spelling_key(right, region)
    assert asr._name_phonemes(left, region) != asr._name_phonemes(right, region)
    # Neither the token path nor the joined/component fallback may lose the
    # vowel mark before applying a regional consonant merger.
    for heard in (f"ha {right}", f"ha{right}"):
        result = adjudicate(f"Ha-{left}.", heard, form=f"Ha-{left}",
                            surface="Unrelated", region=region, alias=False)
        assert result['verdict'] == asr.ASR_MISMATCH


def test_haru_does_not_gain_a_northern_vowel_merger():
    result = adjudicate('“Ha-rư.”', 'Há dù', form='Ha-rư', surface='Haru',
                        region='Bắc', alias=False)
    assert result['verdict'] == asr.ASR_MISMATCH
    evidence = result[asr.LOCKED_NAME_ANCHOR_METRICS_KEY]
    assert evidence['anchors'][0]['matched'] is False


@pytest.mark.parametrize("heard", ["Ruki", "Zuki", "Ru ki", "Zu ki"])
def test_yuki_northern_consonant_alias_keeps_the_same_vowel(heard):
    result = adjudicate('“Giu-ki!”', heard, form='Giu-ki', surface='Yuki', region='Bắc')
    assert result['verdict'] == asr.ASR_PASS


def test_rita_vrataski_accepts_tone_and_northern_initials():
    form = 'Ri-ta vờ-ra-ta-xờ-ki'
    result = adjudicate(f'Không. Tôi còn lâu mới bằng được {form}.',
                        'Không. Tôi còn lâu mới bằng được di ta vở ra ta sở kì.',
                        form=form, surface='Rita Vrataski', region='Bắc', alias=False)
    assert result['verdict'] == asr.ASR_PASS


def test_rita_vrataski_southern_keeps_the_same_o_horn_vowel():
    # Stripping every mark turned "sờ" into "so" (English /soʊ/) against
    # "xờ" -> "xo" (/sɔ/). Retaining ơ on both sides compares the same vowel.
    assert asr._anchor_component_sounds_right(
        ('vờ', 'ra', 'ta', 'xờ', 'ki'), 'Vrataski', 'vờratasờkỳ', voice_region='Nam')
    assert not asr._anchor_component_sounds_right(
        ('vờ', 'ra', 'ta', 'xờ', 'ki'), 'Vrataski', 'voratasoky', voice_region='Nam')
    form = 'Ri-ta vờ-ra-ta-xờ-ki'
    result = adjudicate(f'0. Câu thử đã gỡ. 0.',
                        '0. Câu thử đã gỡ. 0.',
                        form=form, surface='Rita Vrataski', region='Nam', alias=False)
    assert result['verdict'] == asr.ASR_PASS


def test_component_regional_comparison_ignores_punctuation_without_losing_vowels():
    result = adjudicate('Anh xa-mu-rai!', 'Anh Samu Zai!', form='xa-mu-rai!',
                        surface='samurai!', region='Nam', alias=False)
    assert result['verdict'] == asr.ASR_PASS


@pytest.mark.parametrize("word", ['rứ', 'rớ', 'rấ', 'rế', 'riế', 'rắ', 'rố'])
def test_regional_name_tone_removal_preserves_nfc_and_nfd_vowels(word):
    expected = asr._name_phonemes(word, 'Bắc')
    assert asr._name_phonemes(unicodedata.normalize('NFD', word), 'Bắc') == expected
    assert asr._name_phonemes(word.upper(), 'Bắc') == expected


def test_component_transliteration_still_accepts_mizuki():
    result = adjudicate('Mi-dư-ki.', 'Mizuki', form='Mi-dư-ki', surface='Mizuki',
                        region='Bắc', alias=False)
    assert result['verdict'] == asr.ASR_PASS
    assert asr._anchor_component_sounds_right(('Mi', 'dư', 'ki'), 'Mizuki', 'mizuki', 'Bắc')


@pytest.mark.parametrize("form,surface,heard", [
    ('An-đê-ra-ban', 'Alderaban', 'Ande ra bàn'),
    ('Phư-di-ê-đa', 'Fujieda', 'Phư Di Eda'),
])
def test_original_component_d_stroke_and_diacritic_equivalence_survives(form, surface, heard):
    result = adjudicate(f'Anh {form}.', f'Anh {heard}.', form=form,
                        surface=surface, region='Bắc', alias=False)
    assert result['verdict'] == asr.ASR_PASS


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


@pytest.mark.parametrize("spoken,form,surface,heard,region", [
    ('Bạn của cậu à, Giô-si-cun?', 'Giô-si-cun', 'Yoshi-kun', 'Bạn của cậu A, Joshi Kun.', 'Bắc'),
    ('Mừng cậu trở lại, Giô-xu-ke.', 'Giô-xu-ke', 'Yosuke', 'Mừng cậu trở lại! Josuke!', 'Bắc'),
    ('Giô-xu-ke?', 'Giô-xu-ke', 'Yosuke', 'Zosuke', 'Bắc'),
    ('Cuối cùng, chỉ còn lại Hi-nô-ha-ra.', 'Hi-nô-ha-ra', 'Hinohara', 'Cuối cùng, chỉ còn lại Hino Haza.', 'Nam'),
    ('Đây là cách mà mình đã gặp Rin-đô.', 'Rin-đô', 'Rindou', 'Đây là cách mà mình đã gặp Jindo.', 'Bắc'),
    ('Bạn của cậu à, Giô-si-cun?', 'Giô-si-cun', 'Yoshi-kun', 'Bạn của cậu à, Joshi Kun.', ''),
])
def test_romaji_read_by_the_japanese_rule_matches_the_transliteration(spoken, form, surface, heard, region):
    result = adjudicate(spoken, heard, form=form, surface=surface, region=region, alias=False)
    assert result['verdict'] == asr.ASR_PASS


@pytest.mark.parametrize("form,heard,region", [
    ('Giô-si', 'Jushi', 'Bắc'),          # Giu-si: u is not ô
    ('Giô-si-cun', 'Joshi Kan', 'Bắc'),  # Can
    ('Hi-nô-ha-ra', 'Hina Haza', 'Nam'),
    ('Ha-rư', 'Hadu', 'Bắc'),
    ('Giô-si-e', 'Josie', 'Nam'),        # no Japanese reading: stays as before
])
def test_romaji_with_a_different_vowel_still_fails(form, heard, region):
    result = adjudicate(f'Anh {form} đến.', f'Anh {heard} đến.', form=form, surface='Unrelated',
                        region=region, alias=False)
    assert result['verdict'] != asr.ASR_PASS


@pytest.mark.parametrize("heard", ['Há dù', 'Há du', 'ha du'])
def test_vietnamese_tokens_never_take_the_romaji_path(heard):
    # Marked or bare-syllable Vietnamese tokens keep asrjudge2's strict vowels.
    assert not all(asr._romaji_token(token) for token in heard.split())
    assert not asr._romaji_component_sounds_right(('Ha', 'rư'), heard.split(), 'Bắc')
    result = adjudicate('“Ha-rư.”', heard, form='Ha-rư', surface='Haru', region='Bắc', alias=False)
    assert result['verdict'] == asr.ASR_MISMATCH


def test_romaji_path_needs_a_hyphenated_transliteration():
    assert asr._romaji_component_sounds_right(('Giô', 'si'), ['joshi'], 'Bắc')
    assert not asr._romaji_component_sounds_right(('Cun',), ['kun'], 'Bắc')
    assert not asr._romaji_component_sounds_right(('Giô', 'si'), ['jóshi'], 'Bắc')
    # The app reads romaji u as u, never ư (Haru -> Ha-ru).
    assert not asr._romaji_component_sounds_right(('Ha', 'rư'), ['haru'], 'Bắc')
    # Per syllable: Fuze -> Phu-de cannot stand for Phu-gi-e.
    assert not asr._romaji_component_sounds_right(('Phu', 'gi', 'e'), ['fuze'], 'Bắc')
    assert asr._romaji_component_sounds_right(('Phu', 'ghi', 'e'), ['fugie'], 'Bắc')


@pytest.mark.parametrize("heard", ['Fuze', 'fuze', 'Fu ze'])
@pytest.mark.parametrize("region", ['Bắc', 'Nam'])
def test_joined_regional_spelling_cannot_drop_a_syllable(heard, region):
    # Joined, gi+e reads as the one syllable "gie": Fuze would stand for Phu-gi-e.
    assert not asr._regional_syllables_match(('Phu', 'gi', 'e'), heard.replace(' ', '').lower(), region)
    result = adjudicate('Anh Phu-gi-e đến.', f'Anh {heard} đến.', form='Phu-gi-e', surface='Fugie',
                        region=region, alias=False)
    assert result['verdict'] != asr.ASR_PASS


def test_shizai_does_not_stand_for_xi_gi_ai():
    # nhung:465: joined keys made Shizai (Xi-dai) equal Xi-gi-ai (Xi-di-ai).
    assert not asr._regional_syllables_match(('Xi', 'gi', 'ai'), 'shizai', 'Bắc')
    result = adjudicate('Của Xi-gi-ai và.', 'Của Shizai và.', form='Xi-gi-ai', surface='CGI',
                        region='Bắc', alias=False)
    assert result['verdict'] != asr.ASR_PASS


def test_glued_regional_spelling_is_cut_per_syllable():
    assert asr._regional_syllables_match(('Sát', 'ta'), 'sata', 'Nam')  # shared boundary consonant
    assert asr._regional_syllables_match(('Phu', 'gi', 'e'), 'fugie', 'Bắc')
    # One glued romaji token still reads per syllable: Hinohaza (Nam z as r).
    result = adjudicate('Cuối cùng, chỉ còn lại Hi-nô-ha-ra.', 'Cuối cùng, chỉ còn lại Hinohaza.',
                        form='Hi-nô-ha-ra', surface='Hinohara', region='Nam', alias=False)
    assert result['verdict'] == asr.ASR_PASS
