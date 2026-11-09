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
    assert cache.CACHE_RULES == 14
    assert 'readaloud/phoneme_policy.py' in QUALITY_IMPLEMENTATION_FILES
    assert shouts.POLICY['version'] == 1


def test_long_laughter_is_bounded_and_names_and_units_are_guarded():
    said = shouts.stretch_reading('a' + 'ha' * 100)
    assert len(said.split()) == shouts.POLICY['max_laugh_syllables']
    for raw in ('Weisss', 'www', 'MMM', 'III', 'SSS', 'UH'):
        assert shouts.stretch_reading(raw) is None
