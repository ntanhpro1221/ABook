"""Loanwords with a settled Vietnamese reading are read that way by every voice (owner verdict 10-11, "quán net" -> nét).

The table lives in english_policy.json ("loanwords"); Kotlin reads the same file and the same cases
(LoanwordsTest.kt). English runs and proper names keep their own route.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook.readaloud import english_policy, names, vieneu
from abook.vietnamese_syllable import valid_spoken_form
from abook.webui.word_timing import tokens

FIXTURE = Path(__file__).parent / "fixtures/readaloud/loanwords/cases.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["text"])
def test_shared_loanword_cases(case):
    toks = tokens(case["text"])
    assert " ".join(vieneu.spoken_tokens(toks, case["origin"], direct_english=True)) == case["direct"]
    assert " ".join(vieneu.spoken_tokens(toks, case["origin"])) == case["plain"]
    _, units = vieneu.units(case["text"], 256, case["origin"], direct_english=True)
    assert " ".join(piece for unit in units for piece in unit.pieces) == case["direct"]


def test_every_loanword_reading_is_a_valid_vietnamese_spoken_form():
    assert names.LOANWORDS == english_policy.POLICY["loanwords"]
    bad = {word: said for word, said in names.LOANWORDS.items() if not valid_spoken_form(said)}
    assert not bad
    assert names.LOANWORD_CAPITALS <= set(names.LOANWORDS)
    assert names.LOANWORD_NAMES <= set(names.LOANWORDS) and not names.LOANWORD_NAMES & names.LOANWORD_CAPITALS


def test_no_loanword_is_also_an_abbreviation():
    """Capitals written for emphasis ("BAN", "GAME") are read as the loanword; that is only safe while no table word is also a listed abbreviation (OK, TV...)."""
    policy = english_policy.POLICY
    listed = {word.casefold() for key in ("acronyms", "preserve_acronyms", "spoken_abbreviations", "vietnamese_abbreviations", "contextual_abbreviations",
                                          "case_sensitive_abbreviations", "contextual_letter_names") for word in policy[key]}
    assert not listed & set(names.LOANWORDS)


def test_capitals_for_emphasis_keep_the_vietnamese_reading_before_the_abbreviation_rule():
    said = vieneu.spoken_tokens(tokens("Hắn bị admin BAN nick, mở APP chơi GAME."), None, False)
    assert said == ["Hắn", "bị", "át-min", "ban", "ních,", "mở", "áp", "chơi", "ghêm."]
    assert vieneu.spoken_tokens(tokens("GAME OVER"), None) == ["game", "over"]


@pytest.mark.parametrize("origin", [None, "ja", "ko"])
def test_a_voice_that_cannot_say_english_gets_the_same_loanword_reading(origin):
    said = vieneu.spoken_tokens(tokens("Ra quán net chơi game online."), origin, False)
    assert said == ["Ra", "quán", "nét", "chơi", "ghêm", "ôn-lai."]


def test_a_capitalised_loanword_starts_a_sentence_or_is_a_name():
    toks = tokens("Net là thứ hắn sống cùng. Hôm qua tôi gặp Net.")
    said = vieneu.spoken_tokens(toks, None)
    assert said[0] == "nét" and said[-1] == "Net."
