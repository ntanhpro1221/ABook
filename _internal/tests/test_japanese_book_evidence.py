"""Book evidence and presentation boundaries, using invented romaji names."""
from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path

import pytest

from abook.readaloud import english_policy, japanese_policy as jp, names, vieneu
from abook.studio_names import planned_reading, rule_reading


@pytest.mark.parametrize("case", json.loads((Path(__file__).parent / "fixtures/readaloud/japanese_fallback/book_evidence.json").read_text(encoding="utf-8")))
def test_shared_book_evidence(case):
    assert jp.reading(case["token"], case["origin"]) == case["reading"]
    if "spoken" in case:
        assert vieneu.spoken_tokens([case["token"]], case["origin"], direct_english=True) == [case["spoken"]]


@pytest.mark.parametrize("case", json.loads((Path(__file__).parent / "fixtures/readaloud/japanese_fallback/book_names.json").read_text(encoding="utf-8")))
def test_shared_book_name_readings(case):
    assert jp.book_name_readings(case["texts"], case["characters"]) == case["readings"]


def test_a_proven_name_reads_one_way_everywhere_and_a_listener_reading_still_wins():
    found = jp.book_name_readings(["Mira-san vẫy tay."])
    said = vieneu.spoken_tokens("Mira gọi MIRA và Mira-san.".split(), "ja", readings=found, direct_english=True)
    assert said[4] == "Mi-ra-xan."
    assert said[0] == said[2] == "Mi-ra"
    mine = vieneu.spoken_tokens(["Mira"], "ja", readings={**found, "Mira": "Đan"}, direct_english=True)
    assert mine == ["Đan"]


def test_book_name_scan_is_order_independent():
    texts = ["Yui và Aoi. YUI! AOI!", "Mira-san"]
    assert jp.book_name_readings(texts) == jp.book_name_readings(list(reversed(texts)))


@pytest.mark.parametrize("word", ["Nopi", "NOPIKA", "Nopi-kunn", "NOPI-CHAAAN"])
def test_known_book_reads_short_names_and_uppercase(word):
    assert jp.reading(word, "ja") is not None
    assert jp.reading(word, None) is None
    assert jp.reading(word, "ko") is None
    assert english_policy.reading(word, "ja") is None
    assert vieneu.spoken_tokens([word], "ja", direct_english=True) != [word]
    assert planned_reading(word, "ja", direct_english=True)[1] == "rule_romanization"


@pytest.mark.parametrize("word", ["_Nopi_", "~Nopi~", "Nopi[note27]", "chữ「Nopi」to", "Nopi・Nopika", "(NOPIKA)"])
def test_presentation_is_only_removed_for_recognition(word):
    original = word
    assert jp.reading(word, "ja") is not None
    assert jp.reading(word, None) is None
    assert vieneu.spoken_tokens([word], "ja", direct_english=True) != [word]
    assert word == original


@pytest.mark.parametrize("word", ["Reuse", "Reusable", "Camera", "Tina", "Nam", "HOA", "NASA", "AAAH", "Nopikk", "Nopikkka"])
def test_general_lexicon_vietnamese_and_invalid_romaji_abstain(word):
    assert jp.reading(word, "ja") is None


def test_local_word_evidence_cannot_promote_book_origin():
    assert rule_reading("Nopika, Nopi", None) is None
    assert rule_reading("Nopika, Nopi", "ja") is None  # punctuation is not a name component
    assert jp.reading("Nopi", None) is None
    assert jp.reading("Nopi", "ja") == "Nô-pi"
    assert planned_reading("Nopika Nopi", None, direct_english=True)[1] == "rule_romanization"


def test_lexical_asset_is_generated_from_general_sources():
    root = Path(__file__).resolve().parents[1]
    path = root / "scripts/build_japanese_lexicon.py"
    import sys
    monkey_path = str(path.parent)
    sys.path.insert(0, monkey_path)
    try:
        spec = importlib.util.spec_from_file_location("lexicon_builder", path)
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        try:
            expected = builder.words()
        except SystemExit:
            pytest.skip("BERT vocabulary cache is unavailable")
    finally:
        sys.path.remove(monkey_path)
    assert builder.LIMIT == jp.POLICY["routing"]["lexicon_bert_max_id"]
    assert jp.lexical_guard() == frozenset(expected)
    assert len(expected) > 16_000
    assert gzip.decompress(builder.TARGET.read_bytes()).decode("utf-8").splitlines() == expected


def test_lexical_asset_is_in_both_pipeline_fingerprints():
    from abook.quality_policy import ANALYSIS_CASTING_IMPLEMENTATION_FILES, QUALITY_IMPLEMENTATION_FILES

    assert "readaloud/japanese_lexicon.txt.gz" in QUALITY_IMPLEMENTATION_FILES
    assert "readaloud/japanese_lexicon.txt.gz" in ANALYSIS_CASTING_IMPLEMENTATION_FILES


@pytest.mark.parametrize("case", json.loads((Path(__file__).parent / "fixtures/readaloud/japanese_fallback/ownership.json").read_text(encoding="utf-8")))
def test_reading_ownership_and_independent_name_evidence(case):
    text = case["text"]
    toks = text.split()
    assert " ".join(vieneu.spoken_tokens(toks, case["origin"], direct_english=True)) == case["said"]
    _, units = vieneu.units(text, 256, case["origin"], direct_english=True)
    assert " ".join(piece for unit in units for piece in unit.pieces) == case["said"]
    # A listener's explicit choice still wins over every automatic stage.
    first = names.split_token(toks[0])[1]
    assert "đã-chọn" in vieneu.spoken_tokens(toks, case["origin"], readings={first: "đã chọn"}, direct_english=True)[0]
