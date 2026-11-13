"""Shared, self-authored vocal cases and display/anchor invariants."""
import json
from pathlib import Path

import pytest
from abook.readaloud import vieneu, shouts, cache
from abook.readaloud.studio_tn import studio_tn
from abook.webui.word_timing import tokens
from abook.quality_policy import QUALITY_IMPLEMENTATION_FILES

CASES = json.loads((Path(__file__).parent/'fixtures/readaloud/soundfix/cases.json').read_text('utf8'))['cases']


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['text'][:32])
def test_shared_vocal_routes_keep_display_and_unit_ownership(case):
    text = case['text']
    shown, parts = vieneu.units(text, 256, 'ja', readings=case.get('readings'), direct_english=True)
    assert shown == tokens(text)
    assert ' '.join(word for word in vieneu.spoken_tokens(shown, 'ja', readings=case.get('readings'), direct_english=True) if word) == case['said']
    assert ' '.join(piece for part in parts for piece in part.pieces) == case['said']
    assert [index for part in parts for index in range(part.first, part.last + 1)] == list(range(len(shown)))


def test_studio_offsets_and_explicit_readings_survive_note_boundaries():
    text = '_"S-sau[note12]đó tôi đến."_'
    said, offsets = studio_tn(text, 'ja', True, direct_english=True)
    assert said == '"sờ… sau đó tôi đến."'
    assert len(offsets) == len(text) + 1
    assert offsets == sorted(offsets)
    assert offsets[-1] == len(said)
    protected, _ = studio_tn(text, 'ja', True, [(0, len(text))], direct_english=True)
    assert protected == text


def test_shared_policy_is_in_quality_hash_and_cache_namespace():
    assert 'readaloud/sound_policy.json' in QUALITY_IMPLEMENTATION_FILES
    assert cache.CACHE_RULES == 19
    assert 'readaloud/phoneme_policy.py' in QUALITY_IMPLEMENTATION_FILES
    assert shouts.POLICY['version'] == 1


def test_long_laughter_is_bounded_and_names_and_units_are_guarded():
    said = shouts.stretch_reading('a' + 'ha' * 100)
    assert said.split()[0] == 'a'  # the opening vowel is not one of the bounded laugh syllables
    assert len(said.split()) == shouts.POLICY['max_laugh_syllables'] + 1
    assert len(shouts.stretch_reading('ha' * 100).split()) == shouts.POLICY['max_laugh_syllables']
    for raw in ('Weisss', 'www', 'MMM', 'III', 'SSS', 'UH'):
        assert shouts.stretch_reading(raw) is None


@pytest.mark.parametrize("word", ["Hee", "Hii", "Mee", "Ii", "Heh", "Hihi", "Hehe"])
def test_generated_sound_never_spells_an_english_word_unmeasured(word):
    """A generated syllable that spells an English word is said in English by sea-g2p."""
    from abook.readaloud import names, vieneu

    said = vieneu.spoken_tokens([word], "ja", direct_english=True)[0]
    for syllable in said.replace("…", "").replace("-", " ").split():
        low = syllable.casefold()
        assert low not in names.english_words() or low in shouts.POLICY["english_safe"], (word, said)
    assert said.casefold() not in shouts.POLICY["english_collisions"] or said == shouts.POLICY["english_collisions"][said.casefold()]


def test_collision_targets_are_vietnamese_and_measured_safe_readings_stay_vietnamese():
    pytest.importorskip("sea_g2p")
    from abook.readaloud import vieneu_engine

    assert "iː" not in vieneu_engine.phonemize(["hê"]) and "aɪ" not in vieneu_engine.phonemize(["hy"]) and "iː" not in vieneu_engine.phonemize(["mê"])
    for said in shouts.POLICY["english_safe"]:
        assert not {"ɑː", "aɪ", "iː"} & {said_phone for said_phone in ("ɑː", "aɪ", "iː") if said_phone in vieneu_engine.phonemize([said])}


@pytest.mark.parametrize("field", ["text", "listener_text"])
@pytest.mark.parametrize("pasted", ["Yuuki[note1] bước vào.", "Senpai[ note12 ]!", "Kyouko-chan[note3]", "Aaaah[note4]!"])
def test_reference_marks_are_never_said_on_the_studio_route(tmp_path, pasted, field):
    from abook.config import build_settings
    from abook.database import ProjectDB
    from abook.tts import TTSCoordinator

    tts = TTSCoordinator(build_settings(), ProjectDB(tmp_path / "project.sqlite3"), lambda _: None)
    row = {"text": "Câu gốc.", "listener_text": pasted} if field == "listener_text" else {"text": pasted}
    spoken, _ = tts.spoken_text_with_anchors(row)
    assert "note" not in spoken.lower()
