"""A roster pronunciation must affect only the adjudicated occurrence."""
import pytest

from abook.readaloud import vieneu, vieneu_engine
from abook.readaloud.phoneme_policy import Rulings, book_rulings, ruled_vietnamese_words


@pytest.mark.parametrize("text,name,want", [
    ("An nói: I want an apple.", "an", {0}),
    ("I can not do it, Can.", "can", {5}),
])
def test_roster_is_applied_only_at_its_occurrence(text, name, want):
    assert ruled_vietnamese_words(text, rulings=Rulings(names={name})) == want


@pytest.mark.parametrize("text,name,english_phone,vietnamese_phone", [
    ("An nói: I want an apple.", "an", "æn", "ˈaːn"),
    ("I can not do it, Can.", "can", "kˈæn", "kˈaːn"),
])
def test_real_frontend_preserves_english_and_vietnamese_occurrences(text, name, english_phone, vietnamese_phone):
    rulings = Rulings(names={name})
    with book_rulings(rulings):
        shown, parts = vieneu.units(text, 256, None, direct_english=True)
        phones = " ".join(vieneu_engine.phonemize(p.pieces, source=p.text(shown), rulings=rulings) for p in parts)
    assert english_phone in phones.split(), phones
    assert vietnamese_phone in phones.rstrip(".").split(), phones
