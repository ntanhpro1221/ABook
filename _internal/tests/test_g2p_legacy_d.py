"""Latin eth in Vietnamese is a D-stroke, including unaccented/NFD words."""
import unicodedata

import pytest

from abook.readaloud import vieneu, vieneu_engine


@pytest.mark.parametrize("eth_text,modern", [
    ("Ði", "Đi"), ("Ðang", "Đang"), ("Ðan", "Đan"),
    ("Ðinh Văn Ðông", "Đinh Văn Đông"),
    (unicodedata.normalize("NFD", "Ðông"), "Đông"),
])
def test_eth_vietnamese_has_exact_modern_phonemes(eth_text, modern):
    def phones(text):
        shown, parts = vieneu.units(text, 256, None, direct_english=True)
        return " ".join(vieneu_engine.phonemize(p.pieces, source=p.text(shown)) for p in parts)
    assert vieneu.spoken_tokens(eth_text.split(), direct_english=True) == modern.split()
    assert phones(eth_text) == phones(modern)
    assert "ɗ" in phones(eth_text)


def test_eth_in_a_foreign_word_is_not_rewritten():
    assert vieneu.spoken_tokens(["Ðavid"], direct_english=True) == ["Ðavid"]


def test_eth_tokens_are_part_of_the_public_gate():
    import json
    from pathlib import Path
    rows = json.loads((Path(__file__).parent / "data/g2pgate/tokens.json").read_text("utf8"))
    tokens = {row["token"] for row in rows}
    assert {"Ði", "Ðang", "Ðan", unicodedata.normalize("NFD", "Ðông")} <= tokens
