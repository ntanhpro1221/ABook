"""Lớp chữ hoa / chữ thường tiếng Việt phải đúng cỡ chữ: dải `À-Ỹ` chứa cả à, đ, ă, ơ, ạ ("đứng" từng bị coi là tên riêng),
dải `à-ỹ` chứa cả Ạ, Ă, Đ, còn `[A-ZĐ]` thiếu "Ánh", "Ông". Danh sách dùng chung với Kotlin (VietnameseLettersTest.kt) ở
tests/fixtures/vietnamese_letters/letters.json. Mọi câu ở đây là câu tự viết."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pytest

from abook.analysis import SELF_INTRODUCTION_APPOSITIVE_PATTERN, SPEECH_ATTRIBUTION_PATTERN, _generic_speaker_attribution
from abook.name_snap import CAPITALIZED_RUN
from abook.vietnamese_letters import (
    VIETNAMESE_LOWERCASE_CLASS,
    VIETNAMESE_LOWERCASE_LETTERS,
    VIETNAMESE_UPPERCASE_CLASS,
    VIETNAMESE_UPPERCASE_LETTERS,
)

FIXTURE = Path(__file__).parent / "fixtures" / "vietnamese_letters" / "letters.json"
_VOWELS = "aăâeêioôơuưy"
_TONES = ("", chr(0x300), chr(0x301), chr(0x309), chr(0x303), chr(0x323))
_LOWER = {unicodedata.normalize("NFC", vowel + tone) for vowel in _VOWELS for tone in _TONES} | set("bcdđghklmnpqrstvx")


def test_the_letters_match_the_list_shared_with_kotlin() -> None:
    shared = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert shared == {"upper": VIETNAMESE_UPPERCASE_LETTERS, "lower": VIETNAMESE_LOWERCASE_LETTERS}
    assert VIETNAMESE_UPPERCASE_LETTERS.lower() == VIETNAMESE_LOWERCASE_LETTERS
    assert VIETNAMESE_LOWERCASE_LETTERS.upper() == VIETNAMESE_UPPERCASE_LETTERS


def test_each_class_holds_every_letter_of_its_case_and_none_of_the_other() -> None:
    upper = re.compile(rf"{VIETNAMESE_UPPERCASE_CLASS}\Z")
    lower = re.compile(rf"{VIETNAMESE_LOWERCASE_CLASS}\Z")
    for letter in sorted(_LOWER):
        assert lower.match(letter) and not upper.match(letter), letter
        assert upper.match(letter.upper()) and not lower.match(letter.upper()), letter.upper()


@pytest.mark.parametrize("tag,label", [
    ("Cô gái đứng hỏi:", "cô gái"),
    ("Người đàn ông ngồi khẽ nói:", "người đàn ông"),
    ("Em gái Tavin khẽ hỏi:", "em gái tavin"),
    ("Em gái Ánh hỏi:", "em gái ánh"),
    ("Em trai Đông Quân đáp:", "em trai đông quân"),
])
def test_a_lowercase_word_is_never_read_as_a_name_after_a_generic_label(tag, label) -> None:
    assert _generic_speaker_attribution(tag, prefer_last=True) == label


def test_a_lowercase_accented_word_does_not_open_a_capitalised_run() -> None:
    runs = [match.group(1) for match in CAPITALIZED_RUN.finditer("rồi đứng đợi Ánh Dương ở ăn quán Đào")]
    assert runs == ["Ánh Dương", "Đào"]


def test_the_words_between_a_name_and_its_speech_verb_are_lowercase() -> None:
    assert SPEECH_ATTRIBUTION_PATTERN.search("Tavin mỉm cười nói:").group("middle") == "mỉm cười "
    assert SPEECH_ATTRIBUTION_PATTERN.search("Tavin Ăn nói:") is None


def test_a_self_introduction_may_end_on_an_accented_name() -> None:
    assert SELF_INTRODUCTION_APPOSITIVE_PATTERN.match(" con gái của Ánh.")
    assert SELF_INTRODUCTION_APPOSITIVE_PATTERN.match(" con trai của Roxar.")
    assert not SELF_INTRODUCTION_APPOSITIVE_PATTERN.match(" Con gái của Ánh.")
