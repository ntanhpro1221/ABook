"""Synthetic boundary cases for the approved TN fixes; no source-book sentences."""
import pytest

from abook.readaloud.studio_tn import studio_tn
from abook.readaloud.vieneu import integer_reading


@pytest.mark.parametrize(("source", "expected"), [
    ("Quỹ có 2.070.000.000.", "Quỹ có hai tỷ không trăm bảy mươi triệu."),
    ("Giá 3,000 đồng.", "Giá ba nghìn đồng."),
    ("Đo 2.5kg.", "Đo 2,5kg."),
    ("Alex 1. Morgan 3. Taylor 5.", "Alex một. Morgan ba. Taylor năm."),
    ("Giá 1,25 đồng.", "Giá 1,25 đồng."),
    ("Mã v1.2 và 12:30.", "Mã v1.2 và 12:30."),
])
def test_number_boundaries(source, expected):
    assert studio_tn(source, None, True, direct_english=True)[0] == expected


def test_unbounded_integer_and_leading_zeroes():
    assert integer_reading("1000000000000000000") == "một tỷ tỷ"
    assert integer_reading("007") == "không không bảy"


def test_explicit_readings_keep_number_ownership():
    source = "Giá 300."
    assert studio_tn(source, None, True, [(4, 7)], direct_english=True)[0] == source


@pytest.mark.parametrize(("source", "expected"), [
    ("Mẫu T-virus và G-virus.", "Mẫu tê vi-rút và giê vi-rút."),
    ("Thử B-robot.", "Thử bê rô-bốt."),
    ("Xem livestream rồi gặp boss.", "Xem lai-xtrim rồi gặp bót."),
    ("Mặc vest ở bar.", "Mặc vét ở ba."),
])
def test_loanwords_and_letter_compounds(source, expected):
    assert studio_tn(source, None, True, direct_english=True)[0] == expected


@pytest.mark.parametrize("word", ["Emm", "Emmmm", "emmmmm", "Ừmmm", "ừmm"])
def test_nasal_hesitation(word):
    assert studio_tn(f"{word}, chờ đã.", None, True, direct_english=True)[0] == "ừm, chờ đã."


@pytest.mark.parametrize("word", ["cứu", "hưu", "lưu", "mưu", "bưu", "cừu", "hữu", "cựu", "ưu", "soóc", "moóc", "goòng", "voọc", "em"])
def test_real_words_are_never_stretched(word):
    from abook.readaloud.shouts import stretch_reading

    assert stretch_reading(word) is None
    assert studio_tn(f"Từ {word} này.", None, True)[0] == f"Từ {word} này."


@pytest.mark.parametrize(("code", "said"), [("M2", "em hai"), ("M60", "em sáu mươi"), ("M500", "em năm trăm"), ("MP9", "em pê chín"), ("M82A1", "em tám mươi hai a một")])
def test_uppercase_model_codes(code, said):
    assert studio_tn(f"Thử {code} nhé.", None, True, direct_english=True)[0] == f"Thử {said} nhé."
