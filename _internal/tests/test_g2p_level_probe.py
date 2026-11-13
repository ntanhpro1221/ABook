"""Exact phoneme requirements: normalization must not hide stress/tone damage."""
import pytest

from abook.readaloud.phoneme_policy import _level_probe, restore_generated_syllables
from abook.readaloud.vieneu_engine import _sea


@pytest.mark.parametrize("word,phone", [("đâu", "ɗˈə1w"), ("kêu", "kˈe1w"), ("giêng", "zˈiɛ1ŋ"), ("cai", "kˈaːj")])
def test_native_vietnamese_level_and_stress_are_preserved(word, phone):
    convert = _sea().g2p.convert
    assert convert(word) == phone
    assert _level_probe(word, convert) == phone


def test_katou_keeps_exact_native_level_marker():
    convert = _sea().g2p.convert
    actual = restore_generated_syllables("ca-tâu", "ca tâu", convert("ca tâu"), convert, "Katou")
    assert actual.split()[-1] == "t̪ˈə1w"


def test_probe_still_recovers_an_english_misclassification():
    convert = _sea().g2p.convert
    assert _level_probe("ten", convert) == "t̪ˈɛn"
