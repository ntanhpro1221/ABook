"""The independent oracle must catch production probe mistakes."""
import pytest

from g2pgate_dictionary import vietnamese_phone
from abook.readaloud.phoneme_policy import _level_probe


def test_dictionary_oracle_retains_native_level_and_stress():
    assert vietnamese_phone("đâu") == "ɗˈə1w"
    assert vietnamese_phone("cai") == "kˈaːj"
    assert vietnamese_phone("ten") == "t̪ˈɛn"


@pytest.mark.parametrize("word", ["dat", "bach", "cap", "cat", "Cat"])
def test_invalid_level_tone_stops_have_no_probe_or_oracle(word):
    assert _level_probe(word, lambda _: pytest.fail("Invalid syllable must not reach G2P")) is None
    with pytest.raises(ValueError, match="level-tone Vietnamese stop"):
        vietnamese_phone(word)


def test_oracle_does_not_depend_on_the_production_probe(monkeypatch):
    import abook.readaloud.phoneme_policy as policy
    monkeypatch.setattr(policy, "_level_probe", lambda *_: "incorrect")
    assert vietnamese_phone("tâu") == "t̪ˈə1w"


def test_unattested_spelling_has_no_vietnamese_target():
    from g2pgate_policy import canonical_options

    # "mylene" is no Vietnamese syllable: only the English-head option remains,
    # never a target fabricated by tone-probing the spelling.
    assert canonical_options("Mylene-san", "mixed") == ["mˈaɪliːn sˈaːn"]
