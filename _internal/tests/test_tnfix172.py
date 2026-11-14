"""Authored cross-platform TN rules and counterexamples; source text stays intact."""
import json
from pathlib import Path

import pytest

from abook.readaloud import vieneu
from abook.webui.word_timing import tokens
from scripts.tn_benchmark import SpeechBoundaries, normalize

CASES = json.loads((Path(__file__).parent/'fixtures/readaloud/tnfix172/cases.json').read_text(encoding='utf-8'))


@pytest.fixture(scope='module')
def speech_boundaries():
    with SpeechBoundaries() as boundaries:
        yield boundaries


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['id'])
def test_spoken_tnfix172_shared_with_android(case, speech_boundaries):
    shown, parts = vieneu.units(case['text'], 256, case.get('origin'), direct_english=True)
    assert shown == tokens(case['text'])
    instant = ' '.join(piece for part in parts for piece in part.pieces if piece)
    assert normalize(instant) == normalize(case['spoken'])
    outputs, _ = speech_boundaries.read(case)
    assert normalize(outputs['studio']) == normalize(case.get('studio', case['spoken']))


def test_spoken_tnfix172_listener_reading_wins():
    for text, surface in [('Giá USD 47.', 'USD'), ('Mở https://example.org/c.', 'https://example.org/c')]:
        result = vieneu.spoken_tokens(tokens(text), readings={surface:'cách đọc riêng'}, direct_english=True)
        assert 'cách-đọc-riêng' in ' '.join(result)
