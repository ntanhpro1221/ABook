"""Synthetic boundary cases for the approved TN fixes; no source-book sentences."""
import pytest

from abook.readaloud.studio_tn import studio_tn
from abook.readaloud.vieneu import integer_reading


@pytest.mark.parametrize(("source", "expected"), [
    ("Quỹ có 2.070.000.000.", "Quỹ có hai tỷ không trăm bảy mươi triệu."),
    ("Giá 3,000 đồng.", "Giá ba nghìn đồng."),
    ("Đo 2.5kg.", "Đo hai phẩy năm kg."),
    ("Alex 1. Morgan 3. Taylor 5.", "Alex một. Morgan ba. Taylor năm."),
    ("Giá 1,25 đồng.", "Giá 1,25 đồng."),
    ("Đo 0,357 giây.", "Đo 0,357 giây."),
    ("Đo 3,0005 giây.", "Đo 3,0005 giây."),
    ("Mã v1.2 và 12:30.", "Mã một chấm hai và 12:30."),
])
def test_number_boundaries(source, expected):
    assert studio_tn(source, None, True, direct_english=True)[0] == expected


def test_unbounded_integer_and_leading_zeroes():
    assert integer_reading("1000000000000000000") == "một tỷ tỷ"
    assert integer_reading("007") == "không không bảy"


def test_explicit_readings_keep_number_ownership():
    source = "Giá 300."
    assert studio_tn(source, None, True, [(4, 7)], direct_english=True)[0] == source


@pytest.mark.parametrize("source", ["ngày 12.05", "lúc 10.30", "phiên bản 1.10", "đo 1234.5000"])
def test_explicit_readings_keep_dotted_number_ownership(source):
    start = source.rfind(" ") + 1
    assert studio_tn(source, None, True, [(start, len(source))])[0] == source


@pytest.mark.parametrize(("source", "expected"), [
    ("Mẫu T-virus và G-virus.", "Mẫu tê vi-rút và giê vi-rút."),
    ("Thử B-robot.", "Thử bê rô-bốt."),
    ("Xem livestream rồi gặp boss.", "Xem lai-xờ-trim rồi gặp bót."),
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


@pytest.mark.parametrize(("code", "said"), [("M2", "em hai"), ("M60", "em sáu mươi"), ("M500", "em năm trăm"), ("MP9", "em pê chín"), ("M82A1", "em tám mươi hai a một"), ("SS2", "ét ét hai"),
                                           ("R18", "e-rờ mười tám"), ("L115A3", "e-lờ một trăm mười lăm a ba")])
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


@pytest.mark.parametrize("source", ["Cô nói “Ồ” rồi đi.", "Chữ “A” đây."])
def test_quotation_marks_after_a_lone_letter_stay(source):
    from abook.readaloud.studio_tn import separate_digit_quotes

    assert separate_digit_quotes(source) == source



@pytest.mark.parametrize(("source", "expected"), [
    ("Chỉ 0.0003% thôi.", "Chỉ không phẩy không không không ba% thôi."),
    ("Mất 0.006 giây.", "Mất không phẩy không không sáu giây."),
    ("Bản 0.0.2 nhé.", "Bản không chấm không chấm hai nhé."),
    ("Giá 4.200 đồng.", "Giá bốn nghìn hai trăm đồng."),
])
def test_a_leading_zero_group_is_a_decimal(source, expected):
    assert studio_tn(source, None, True, direct_english=True)[0] == expected


@pytest.mark.parametrize(("source", "direct", "plain"), [
    ("Lần thứ N rồi.", "Lần thứ <en>N</en> rồi.", "Lần thứ en rồi."),
    ("Nhắc N lần rồi.", "Nhắc <en>N</en> lần rồi.", "Nhắc en lần rồi."),
    ("Chọn lá N đi.", "Chọn lá N đi.", "Chọn lá N đi."),
    ("Thứ R lần này.", "Thứ R lần này.", "Thứ R lần này."),
])
def test_n_as_an_unspecified_count(source, direct, plain):
    assert studio_tn(source, None, True, direct_english=True)[0] == direct
    assert studio_tn(source, None, True)[0] == plain


@pytest.mark.parametrize(("source", "expected"), [
    ("Cậu là loli-con hả?", "Cậu là lô-li con hả?"),
    ("Đánh Boss Cuối Cùng đi.", "Đánh bót Cuối Cùng đi."),
    ("Gặp Boss Taylor ở đây.", "Gặp Boss Taylor ở đây."),
    ("Một bro-con thật sự.", "Một bro-con thật sự."),
    ("Trang web-based thôi.", "Trang web-based thôi."),
])
def test_loanwords_beside_vietnamese_words(source, expected):
    assert studio_tn(source, None, True, direct_english=True)[0] == expected


@pytest.mark.parametrize(("source", "expected"), [
    ("Sai số 30.0002 thôi.", "Sai số ba mươi phẩy không không không hai thôi."),
    ("Chiều dài 4321.765 nhé.", "Chiều dài bốn nghìn ba trăm hai mươi mốt phẩy bảy sáu năm nhé."),
    ("Hằng số 1.41421 đây.", "Hằng số một phẩy bốn một bốn hai một đây."),
    ("Ngày 21.9.2027 nhé.", "Ngày 21.9.2027 nhé."),
    ("Đi 7.400 km.", "Đi 7.400 km."),
    ("Giá 6.300 đồng.", "Giá sáu nghìn ba trăm đồng."),
])
def test_a_long_group_after_the_dot_is_a_decimal_not_a_date(source, expected):
    assert studio_tn(source, None, True, direct_english=True)[0] == expected


@pytest.mark.parametrize(("source", "expected"), [
    ("Đội P.Q.R.S đến.", "Đội <en>P Q R S</en> đến."),
    ("Đội PQRS đến.", "Đội <en>P Q R S</en> đến."),
    ("Họ về X.Y.Z rồi.", "Họ về <en>X Y zed</en> rồi."),
    ("Họ sống ở X.Y.Z.", "Họ sống ở <en>X Y zed</en>."),
    ("Họ về X.Y.Z. Rồi đi.", "Họ về <en>X Y zed</en>. Rồi đi."),
    ("Hệ B.C. mới chạy.", "Hệ <en>B C</en> mới chạy."),
    ("Một cú K.D., rồi ngã.", "Một cú <en>K D</en>, rồi ngã."),
    ("Nhóm (P.Q.R), đến.", "Nhóm (<en>P Q R</en>), đến."),
    ("Ví dụ v.v. thôi.", "Ví dụ vân vân. thôi."),
])
def test_dotted_initials_read_like_initials_without_dots(source, expected):
    assert studio_tn(source, None, True, direct_english=True)[0] == expected


def test_the_dot_of_initials_cuts_only_a_real_sentence():
    from abook.readaloud import vieneu

    _toks, units = vieneu.units("Hệ B.C. mới chạy. Họ về X.Y.Z. Rồi đi.", 256)
    assert [unit.pieces for unit in units] == [["Hệ bê xê mới chạy.", "Họ về ích i-dài dét.", "Rồi đi."]]
