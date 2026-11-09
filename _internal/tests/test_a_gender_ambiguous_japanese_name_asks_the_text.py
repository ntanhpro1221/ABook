"""A gender-ambiguous Japanese given name: the text decides even when the model votes as one.

sugaru_v5mac read YUGAMI MIZUHO female in 551 of 551 segments and CHIHIRO AMAGAI female in 265
of 275; both are the male narrators of their books. The model was reading the name.
"""
from __future__ import annotations

from abook.character_registry import (
    GENDER_AMBIGUOUS_GIVEN_NAMES,
    has_gender_ambiguous_given_name,
    resolve_gender,
)


def row(speaker: str, gender: str, text: str = "") -> dict[str, str]:
    return {"speaker": speaker, "gender": gender, "text": text}


MALE_TEXT = "Anh Yugami Mizuho gật đầu. Cậu Mizuho, anh ấy, chàng trai Mizuho, ông bố của Mizuho gọi cậu ta."


def test_a_unanimous_female_vote_on_mizuho_loses_to_male_text() -> None:
    ident = [row("YUGAMI MIZUHO", "female") for _ in range(6)]
    gender, why = resolve_gender(ident, [*ident, row("NARRATOR", "unknown", MALE_TEXT)])
    assert gender == "male", why
    assert why.startswith("text_ambiguous_name:")


def test_a_two_to_one_margin_is_enough_on_such_a_name() -> None:
    # Chihiro: 28 male words to 11 - below the 3:1 a split vote needs, above the 2:1 this class needs.
    ident = [row("CHIHIRO", "female") for _ in range(5)]
    text = "Anh Chihiro, cậu ấy, chàng Chihiro, anh ta, cậu Chihiro, anh Chihiro. Cô Chihiro, chị Chihiro."
    gender, why = resolve_gender(ident, [*ident, row("NARRATOR", "unknown", text)])
    assert gender == "male", why


def test_without_decisive_text_the_vote_still_stands() -> None:
    ident = [row("AOI", "female") for _ in range(4)]
    assert resolve_gender(ident, ident) == ("female", "model")


def test_a_different_ambiguous_name_can_resolve_to_female() -> None:
    ident = [row("AOI", "male") for _ in range(6)]
    text = row("NARRATOR", "unknown", "Cô Aoi gặp chị Aoi, bà Aoi, nàng Aoi và cô gái Aoi.")
    gender, why = resolve_gender(ident, [*ident, text])
    assert gender == "female", why
    assert why.startswith("text_ambiguous_name:")


def test_a_few_gendered_words_do_not_overrule_a_unanimous_vote() -> None:
    ident = [row("AOI", "female") for _ in range(6)]
    text = row("NARRATOR", "unknown", "Anh Aoi gọi cậu Aoi.")
    assert resolve_gender(ident, [*ident, text]) == ("female", "model")


def test_an_ordinary_name_keeps_the_unanimous_vote() -> None:
    ident = [row("MILINA", "female") for _ in range(4)]
    text = row("NARRATOR", "unknown", "Ngài Neeshka, ông Evans, anh ấy, cậu ta, ông ấy quay sang Milina.")
    assert resolve_gender(ident, [*ident, text]) == ("female", "model")


def test_the_listener_still_outranks_the_text() -> None:
    ident = [row("YUGAMI MIZUHO", "female")]
    text = row("NARRATOR", "unknown", MALE_TEXT)
    assert resolve_gender(ident, [*ident, text], {"YUGAMI MIZUHO": "female"}) == ("female", "listener")


def test_the_class_is_matched_by_word_not_by_substring() -> None:
    assert has_gender_ambiguous_given_name({"YUGAMI MIZUHO"})
    assert has_gender_ambiguous_given_name({"Chihiro Amagai"})
    assert not has_gender_ambiguous_given_name({"JUNICHIRO"})
    assert not has_gender_ambiguous_given_name({"RENATA"})
    assert {"mizuho", "chihiro"} <= GENDER_AMBIGUOUS_GIVEN_NAMES
