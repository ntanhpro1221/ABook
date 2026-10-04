"""Bộ kiểm âm tiết tiếng Việt chặt (abook/vietnamese_syllable.py): chính tả, vần, thanh.

  - bộ ví dụ dùng chung với Kotlin (tests/fixtures/vietnamese_syllable/cases.json): đúng phải qua, sai phải trượt;
  - văn bản Việt có sẵn trong repo công khai (passage.txt: Truyện Kiều, hết bản quyền; fixture nhập sách): MỌI âm tiết phải qua;
  - ba ca bộ cũ (analysis._valid_vietnamese_spoken_form) để lọt: Gen, Mêch, Ain, Got - bộ này chặn, bộ cũ vẫn nhận (đó là lý do có bộ này);
  - mọi cách đọc máy sinh ra (romanization, english_vi: bảng ghi đè, bộ ví dụ dùng chung) đều qua bộ kiểm;
  - kho truyện hết bản quyền trong Corpus (nếu máy có): tỉ lệ âm tiết bị từ chối chỉ là lỗi gõ / OCR.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path

import pytest

from abook.vietnamese_syllable import valid_spoken_form, valid_syllable

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
CASES = json.loads((FIXTURES / "vietnamese_syllable" / "cases.json").read_text(encoding="utf-8"))
WORD = re.compile(r"[^\W\d_]+")


def _words(text: str) -> list[str]:
    return WORD.findall(unicodedata.normalize("NFC", text))


@pytest.mark.parametrize("syllable", CASES["valid"])
def test_a_real_syllable_passes(syllable):
    assert valid_syllable(syllable), syllable


@pytest.mark.parametrize("syllable", CASES["invalid"])
def test_a_wrong_syllable_fails(syllable):
    assert not valid_syllable(syllable), syllable


@pytest.mark.parametrize("text", CASES["spoken_valid"])
def test_a_spoken_form_of_real_syllables_passes(text):
    assert valid_spoken_form(text), text


@pytest.mark.parametrize("text", CASES["spoken_invalid"])
def test_a_spoken_form_with_a_wrong_piece_fails(text):
    assert not valid_spoken_form(text), text


def test_every_syllable_of_the_public_vietnamese_text_passes():
    rejected = sorted({word for word in _words((FIXTURES / "vietnamese_syllable" / "passage.txt").read_text(encoding="utf-8")) if not valid_syllable(word)})
    assert not rejected, f"âm tiết Việt thật bị từ chối: {rejected}"
    whole = _words((FIXTURES / "import" / "whole.txt").read_text(encoding="utf-8"))
    assert len(whole) > 50
    assert not [word for word in whole if not valid_syllable(word)]


def test_what_the_old_check_let_through_is_stopped_here():
    from abook.analysis import _valid_vietnamese_spoken_form

    # g + e viết gh; p / t / c / ch chỉ đi với thanh sắc hay nặng; ai không nhận phụ âm cuối
    for wrong, right in (("Gen", "Ghen"), ("Mêch", "Mếch"), ("Got", "Gót"), ("Ain", "Ai-nơ"), ("Xớc", "Xơ-cơ")):
        assert _valid_vietnamese_spoken_form("", wrong), f"bộ cũ không còn nhận {wrong}: sửa lại ví dụ"
        assert not valid_spoken_form(wrong), wrong
        assert valid_spoken_form(right), right


def test_a_tone_sits_on_a_vowel_only():
    assert not valid_syllable("mañ")  # ñ là n + dấu ngã, không phải thanh
    assert valid_syllable("mãn")


def test_the_two_forms_of_a_precomposed_and_decomposed_syllable_agree():
    for word in ("nguyễn", "Việt", "quýt", "huỳnh"):
        assert valid_syllable(unicodedata.normalize("NFC", word)) == valid_syllable(unicodedata.normalize("NFD", word)) is True


def test_a_stop_coda_needs_a_rising_or_heavy_tone():
    for coda in ("c", "ch", "p", "t"):
        nucleus = "ê" if coda == "ch" else "a"
        assert not valid_syllable("m" + nucleus + coda)
        assert not valid_syllable("m" + {"a": "à", "ê": "ề"}[nucleus] + coda)
        assert valid_syllable("m" + {"a": "á", "ê": "ế"}[nucleus] + coda)
        assert valid_syllable("m" + {"a": "ạ", "ê": "ệ"}[nucleus] + coda)


def test_every_machine_made_reading_passes():
    from abook.english_vi import ACRONYMS, OVERRIDES

    for token, reading in list(OVERRIDES.items()) + list(ACRONYMS.items()):
        assert valid_spoken_form(reading), f"{token}: {reading}"
    shared = json.loads((FIXTURES / "english_vi" / "cases.json").read_text(encoding="utf-8"))["cases"]
    wrong = [(case["token"], case[key]) for case in shared for key in ("reading", "reading_nodict") if case.get(key) and not valid_spoken_form(case[key])]
    assert not wrong, wrong
    wrong = [(case["token"], case["reading"]) for case in json.loads((FIXTURES / "romanization" / "cases.json").read_text(encoding="utf-8"))["cases"]
             if case.get("reading") and not valid_spoken_form(case["reading"])]
    assert not wrong, wrong


CORPUS = Path(os.environ.get("ABOOK_CORPUS", "D:/Novels/ABook/Corpus"))
OLD_BOOKS = ("Một chữ tình (Hồ Biểu Chánh)", "Nửa chừng xuân (Khái Hưng)", "Tắt đèn (Ngô Tất Tố)")


@pytest.mark.skipif(not all((CORPUS / book).is_dir() for book in OLD_BOOKS), reason="máy không có kho truyện hết bản quyền (Corpus)")
def test_the_public_domain_novels_are_almost_all_accepted():
    counts: dict[str, int] = {}
    for book in OLD_BOOKS:
        for chapter in sorted((CORPUS / book).glob("*.txt")):
            for word in _words(chapter.read_text(encoding="utf-8")):
                counts[word.lower()] = counts.get(word.lower(), 0) + 1
    # token có dấu tiếng Việt (thanh hay â ê ô ă ơ ư đ), không lẫn chữ Hán, chữ lạ: là tiếng Việt chắc chắn
    vietnamese = {word: n for word, n in counts.items() if re.fullmatch(r"[a-zà-ỹ]+", word) and re.search(r"[à-ỹ]", word)}
    rejected = {word: n for word, n in vietnamese.items() if not valid_syllable(word)}
    total = sum(vietnamese.values())
    assert total > 100_000
    # còn lại là lỗi gõ / OCR của bản số hoá (môt, gưong, tuơi, nuớc, đưòng...), không phải vần thật
    assert sum(rejected.values()) / total < 0.002, sorted(rejected.items(), key=lambda item: -item[1])[:30]
