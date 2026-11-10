"""Tên / từ bị hét viết HOA cả ("YUI!", "KAEL!") đọc như chính từ ấy, viết tắt thật ("NPC!", "USA!") vẫn đánh vần.
Bộ ví dụ dùng chung với Kotlin (`CapitalWordsTest`): tests/fixtures/readaloud/capitals/cases.json."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook.readaloud import abbreviations, japanese_policy, vieneu

CASES = json.loads((Path(__file__).parent / "fixtures/readaloud/capitals/cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES["spoken"], ids=lambda case: f"{case['text']}|{case['origin']}|{len(case.get('readings', {}))}")
def test_shared_capital_words(case):
    toks = case["text"].split()
    assert " ".join(vieneu.spoken_tokens(toks, case["origin"], readings=case.get("readings"), direct_english=True)) == case["said"]


@pytest.mark.parametrize("case", CASES["books"], ids=lambda case: case["note"][:24])
def test_shared_capital_names_of_a_book(case):
    assert japanese_policy.book_name_readings(case["texts"], case["characters"], case["origin"]) == case["readings"]


def test_a_shouted_name_is_never_spelled_and_a_listed_abbreviation_always_is():
    for name in ("YUI", "YUKI", "KASAI", "AKIRA", "SORA"):
        assert "<en>" not in vieneu.spoken_tokens([f"{name}!"], "ja", direct_english=True)[0], name
    for code in ("USA", "AGI", "DEX", "UFO", "CPU", "USB", "AOE"):
        for origin in ("ja", "en", None):
            assert vieneu.spoken_tokens([f"{code}!"], origin, direct_english=True) == [f"<en>{' '.join(code)}</en>!"], code


def test_only_a_reading_equal_to_the_capitalized_spelling_is_proof_and_never_a_sound():
    assert abbreviations.proves_name("KAEL", "Kael")
    assert not abbreviations.proves_name("KAEL", "Ca-en") and not abbreviations.proves_name("Kael", "Kael") and not abbreviations.proves_name("ĐI", "Đi")
    assert abbreviations.capital_words(["Rồi", "đến."], "ja") is None
