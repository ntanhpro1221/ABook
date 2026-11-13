"""Lớp "chữ hoa" tiếng Việt phải đúng là chữ hoa: dải điểm mã `À-Ỹ` chứa cả à, đ, ă, ơ, ạ... nên "đứng" từng bị coi là tên
riêng. Mọi câu ở đây là câu tự viết."""
from __future__ import annotations

import re
import unicodedata

import pytest

from abook.analysis import _generic_speaker_attribution
from abook.name_snap import CAPITALIZED_RUN
from abook.text_processing import VIETNAMESE_UPPERCASE_CLASS

_VOWELS = "aăâeêioôơuưy"
_TONES = ("", "̀", "́", "̉", "̃", "̣")
_LOWER = {unicodedata.normalize("NFC", vowel + tone) for vowel in _VOWELS for tone in _TONES} | set("bcdđghklmnpqrstvx")


def test_the_class_holds_every_vietnamese_capital_and_no_small_letter() -> None:
    upper = re.compile(rf"{VIETNAMESE_UPPERCASE_CLASS}\Z")
    for letter in sorted(_LOWER):
        assert not upper.match(letter), letter
        assert upper.match(letter.upper()), letter.upper()


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
