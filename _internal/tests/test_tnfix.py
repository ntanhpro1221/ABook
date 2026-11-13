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
    ("Đo 0,357 giây.", "Đo 0,357 giây."),
    ("Đo 3,0005 giây.", "Đo 3,0005 giây."),
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


@pytest.mark.parametrize(("source", "expected"), [
    ("Thẻ N yếu hơn thẻ R.", "Thẻ en yếu hơn thẻ a."),
    ("N, R, SR, SSR, UR.", "en, a, ét e-rờ, ét ét e-rờ, u e-rờ."),
    ("Thẻ R18 ở đây.", "Thẻ e-rờ mười tám ở đây."),
])
def test_rank_letters(source, expected):
    assert studio_tn(source, None, True)[0] == expected


def test_rank_letters_use_the_direct_english_route():
    assert studio_tn("Thẻ N và R.", None, True, direct_english=True)[0] == "Thẻ <en>N</en> và <en>R</en>."


@pytest.mark.parametrize("source", ["n'", "o’", "a′", "Rock n' Roll"])
def test_lone_letter_quotes_do_not_become_primes(source):
    from abook.readaloud.studio_tn import separate_digit_quotes

    result = separate_digit_quotes(source)
    assert len(result) == len(source)
    assert not any(c in result for c in "'’′")


@pytest.mark.parametrize("source", ["don't", "I'm", "O'Brien", "l'amour"])
def test_internal_apostrophes_are_lexical(source):
    from abook.readaloud.studio_tn import separate_digit_quotes

    assert separate_digit_quotes(source) == source


@pytest.mark.parametrize("dash", ["–", "—"])
@pytest.mark.parametrize("source", ["C{}Cái gì?", "Kh{}Không!", "T{} tôi đi.", "Ng{}ngài đâu?"])
def test_long_dash_stutters_read_like_hyphen_stutters(source, dash):
    assert studio_tn(source.format(dash), None, True)[0] == studio_tn(source.format("-"), None, True)[0]


@pytest.mark.parametrize("source", [
    "Ngày 01-10-2026 nhé.", "Gọi 090-123-4567 nhé.", "Phép 3 < 5 đúng.", "Xem [1] nhé.", "Nặng 10 kg.",
    "Mã 007 đây.", "Số 1234567 đây.", "Có 144 126 071 người.", "Giá $5 thôi.", "Tăng ×3 lần.", "Khoảng ~50 người.",
])
def test_only_a_standalone_count_becomes_words(source):
    assert studio_tn(source, None, True, direct_english=True)[0] == studio_tn(source, None, True)[0]
    said = studio_tn(source, None, True)[0]
    assert any(c.isdigit() for c in said), said


@pytest.mark.parametrize(("source", "expected"), [
    ("Có 3 người.", "Có ba người."),
    ("Mất 120 vàng.", "Mất một trăm hai mươi vàng."),
    ("Đủ 999999 điểm.", "Đủ chín trăm chín mươi chín nghìn chín trăm chín mươi chín điểm."),
])
def test_a_standalone_count_is_read_in_vietnamese(source, expected):
    assert studio_tn(source, None, True)[0] == expected



@pytest.mark.parametrize(("source", "phrase"), [
    ("Xếp thứ 1 nhé.", "thứ nhất"),
    ("Xếp thứ 4 nhé.", "thứ tư"),
    ("Diện tích 17 km² nhé.", "ki lô mét vuông"),
    ("Diện tích 2.000.000 km² nhé.", "ki lô mét vuông"),
    ("Thể tích 23 m³ nhé.", "mét khối"),
])
def test_ordinals_and_powered_units_keep_their_numeric_context(source, phrase):
    from abook.readaloud import vieneu_engine

    said = studio_tn(source, None, True, direct_english=True)[0]
    assert phrase in vieneu_engine.normalize([said])
