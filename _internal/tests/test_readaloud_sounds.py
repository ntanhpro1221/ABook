"""Viết tắt TOÀN HOA, thán từ kéo dài và hậu tố gọi trong "Nghe ngay" (abook/readaloud/abbreviations.py, shouts.py, names.honorific_reading): biến đổi để đọc, chữ hiện không đổi,
số chữ không đổi, mọi giọng như nhau. Bản Kotlin y hệt (Abbreviations.kt, Shouts.kt, Names.kt) và đọc chung tests/fixtures/vieneu/android/text.json."""
from __future__ import annotations

import pytest

from abook.readaloud import abbreviations, names, shouts, vieneu
from abook.webui import word_timing


def _said(text: str, origin: str | None = None, speaks_english: bool = True) -> list[str]:
    toks = word_timing.tokens(text)
    said = vieneu.spoken_tokens(toks, origin, speaks_english)
    assert len(said) == len(toks)
    return said


# ---- viết tắt: tên chữ cái hệ a-bê-xê ----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("token, reading", [
    ("HP", "hát pê"), ("MP", "em pê"), ("NPC", "en pê xê"), ("EXP", "e ích pê"), ("SSR", "ét ét e-rờ"), ("GOTY", "giê ô tê i-dài"), ("QQ", "quy quy"),
    ("XL", "ích e-lờ"), ("BBQ", "bê bê quy"), ("ATSM", "a tê ét em"), ("WZ", "vê-kép dét"), ("JK", "gi ca"), ("AI", "a i"), ("ABC", "a bê xê"), ("USA", "u ét a"),
    ("RPG", "e-rờ pê giê"), ("VIT", "vê i tê"),
])
def test_an_abbreviation_is_read_by_its_letter_names(token: str, reading: str) -> None:
    assert _said(f"Rồi {token}.") == ["Rồi", f"{reading}."]
    assert _said(f"Rồi {token}.", "ja") == _said(f"Rồi {token}.", None, False) == ["Rồi", f"{reading}."], "mọi giọng, mọi gốc"


@pytest.mark.parametrize("token, reading", [("VIP", "víp"), ("ID", "ai-đi"), ("OK", "ô kê"), ("TV", "ti vi")])
def test_four_abbreviations_are_read_as_words(token: str, reading: str) -> None:
    assert _said(f"Rồi {token}.") == ["Rồi", f"{reading}."]


@pytest.mark.parametrize("token, lowered", [("LINE", "line"), ("MAX", "max"), ("YES", "yes"), ("TIP", "tip"), ("BAKA", "baka"), ("NO", "no"), ("WARNING", "warning")])
def test_a_capital_word_is_a_word_not_an_abbreviation(token: str, lowered: str) -> None:
    assert _said(f"Rồi {token}.") == ["Rồi", f"{lowered}."], "chữ thường: sea-g2p đọc chữ hoa cả thành từng chữ cái"


@pytest.mark.parametrize("token", ["Hp", "hp", "NPCs", "A", "H", "10KG", "A12-B", "TP.HCM", "PGS.TS", "KIRITO", "X-RAY", "SS2", "ĐH", "CÁC"])
def test_other_tokens_are_left_alone(token: str) -> None:
    assert _said(f"Rồi {token} đến.") == ["Rồi", token, "đến."]


def test_punctuation_around_an_abbreviation_is_kept_and_a_number_before_it_stops_it() -> None:
    assert _said("“HP,” (MP) NPC! 3MP LV5 5HP") == ["“hát pê,”", "(em pê)", "en pê xê!", "3MP", "level 5", "5HP"]


def test_a_shouted_sentence_is_not_a_row_of_abbreviations() -> None:
    assert _said("CÚT ĐI, AI ĐÓ") == ["CÚT", "ĐI,", "AI", "ĐÓ"]
    assert _said("ONII-CHAN LO LẮNG CHO CON KÌA") == ["ONII-CHAN", "LO", "LẮNG", "CHO", "CON", "KÌA"]
    assert _said("HP MP SP") == ["hát pê", "em pê", "ét pê"], "một dãy toàn viết tắt thì vẫn đọc"


def test_a_roman_numeral_is_still_a_number_before_an_abbreviation_is_tried() -> None:
    assert _said("Chương IV, HP.") == ["Chương", "bốn,", "hát pê."]
    assert abbreviations.spelled("IIII") == "i i i i" and abbreviations.spelled("XXX") == "ích ích ích"


# ---- thán từ Latin và tiếng kéo dài ----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("token, reading", [("Umm", "ừm"), ("Ugh", "ức"), ("Boom", "bùm"), ("Oh", "ô"), ("Hmm", "hừm"), ("UGH", "ức"), ("oh", "ô")])
def test_a_fixed_latin_interjection_is_read_as_a_vietnamese_sound(token: str, reading: str) -> None:
    assert _said(f"Rồi {token}, đến.") == ["Rồi", f"{reading},", "đến."]


@pytest.mark.parametrize("token, reading", [
    # nguyên âm đứng riêng: gốc, "…", nguyên âm một lần
    ("Aaaa", "a… a"), ("Haaa", "ha… a"), ("Uuu", "u… u"), ("Viiiiii", "vi… i"), ("Taaa", "ta… a"), ("oaaaa", "oa… a"), ("Eeee", "e… e"),
    # kéo nguyên âm mang thanh của âm gốc
    ("rồiiiii", "rồi… ì"), ("tớơơơơ", "tớ… ớ"), ("chứứứứ", "chứ… ứ"), ("quẹooo", "quẹo… ọ"), ("đâuuuu", "đâu… u"), ("màaaa", "mà… à"), ("nhaaa", "nha… a"), ("tooo", "to… o"),
    # phụ âm / "y": chỉ gốc và "…"
    ("Khônggg", "không…"), ("Emmmm", "em…"), ("Hầyyy", "hầy…"), ("rấtttt", "rất…"), ("hiếppppp", "hiếp…"), ("Oáppp", "oáp…"), ("Haizzz", "hai…"),
    # thán từ Latin: gốc trong bảng
    ("Hmmm", "hừm…"), ("Ummm", "ừm…"), ("Shhhh", "suỵt…"), ("Ahhhh", "a…"), ("Aaah", "a… a"), ("Oooh", "ô… ô"), ("Ughhh", "ức…"),
    # tiếng kêu Nhật: đọc bằng luật romaji
    ("Kyaaa", "ki-a… a"), ("Uwaaa", "u-oa… a"), ("Yaaa", "gia… a"),
    # toàn hoa cùng luật; "ー" sau nguyên âm là kéo
    ("AAAA", "a… a"), ("EMMMMMMM", "em…"), ("HMMM", "hừm…"), ("Aー", "a… a"), ("Haー", "ha… a"), ("Aーー", "a… a"),
])
def test_a_stretched_sound_is_the_sound_then_an_ellipsis_then_the_vowel(token: str, reading: str) -> None:
    assert _said(f"Rồi {token}, đến.") == ["Rồi", f"{reading},", "đến."]
    assert _said(f"Rồi {token}, đến.", "ja") == _said(f"Rồi {token}, đến.", "ko") == _said(f"Rồi {token}, đến.", None, False)


@pytest.mark.parametrize("core", ["Weisss", "wwww", "zzz", "kkkkk", "Onii-channnn", "XXX", "III", "Hmm,Aa", "Aa", "Haiz"])
def test_what_cannot_be_traced_to_a_sound_is_left_alone(core: str) -> None:
    assert shouts.stretch_reading(core) is None


def test_two_stretched_words_in_a_row_and_a_stretch_inside_quotes() -> None:
    assert _said("“Aaaa… Uuu!” ‘nhaaa’ (Hmmm)") == ["“a… a…", "u… u!”", "‘nha… a”", "(hừm…)"], "nháy đơn sau MỘT chữ cái sea-g2p đọc là phẩy: đổi sang ngoặc kép đóng"


def test_a_stretch_glued_to_the_next_word_is_read_before_the_break() -> None:
    assert _said("Ummm…Ý bạn; Haaa…..cuối; màaaa—nếu; Oáppp~....Hầy; -EH....nhìn") == [
        "ừm…Ý", "bạn;", "ha… a…..cuối;", "mà… à, nếu;", "oáp....Hầy;", "-ê....nhìn"]


def test_a_trailing_dash_of_a_stretch_is_dropped() -> None:
    assert _said("Xoạttt- *Viiiii*-") == ["xoạt…", "vi… i"]


def test_a_rank_is_not_a_stretch() -> None:
    assert _said("hạng AAA và AAA+++, rồi SSS") == ["hạng", "a a a", "và", "a a a+++,", "rồi", "ét ét ét"]


def test_a_stretched_roman_numeral_or_x_is_not_a_stretch() -> None:
    assert _said("Chương III, XXX.") == ["Chương", "ba,", "ba mươi."], "số La Mã nối tiếp số vừa đọc vẫn là số"
    assert _said("Ôi, XXX! III") == ["Ôi,", "ích ích ích!", "i i i"]


# ---- hậu tố gọi ---------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("token, reading", [
    ("Ariel-sama", "Ariel-xa-ma"), ("Mary-san", "Mary-xan"), ("Zeros-sensei", "Zeros-xen-xây"), ("Goblin-san", "Goblin-xan"), ("Noel-chan", "Noel-chan"),
    ("sĩ-sama", "sĩ-xa-ma"), ("thần-chan", "thần-chan"), ("diện-san", "diện-xan"), ("Bá-sama", "Bá-xa-ma"),
    # tên Nhật rõ đọc cả tên (không cần gốc của cuốn)
    ("Sora-sama", "Xô-ra-xa-ma"), ("Hinata-sama", "Hi-na-ta-xa-ma"), ("Haruto-kun", "Ha-ru-tô-cun"), ("Tanaka-senpai", "Ta-na-ca-xen-pai"),
    # tên Âu / từ Anh giữ nguyên chữ, chỉ hậu tố đổi
    ("Kate-san", "Kate-xan"), ("Ian-sama", "Ian-xa-ma"),
])
def test_an_honorific_suffix_is_read_with_any_book_origin(token: str, reading: str) -> None:
    for origin in (None, "ja"):
        assert _said(f"Rồi {token}.", origin) == ["Rồi", f"{reading}."], origin


def test_korean_terms_are_read_alone_and_after_a_name() -> None:
    assert _said("“Oppa, unnie! hyung noona”") == ["“óp-pa,", "un-ni!", "hi-ung", "nu-na”"]
    assert _said("Hyung-nim, Soleum-ssi, Minho-oppa") == ["hi-ung-nim,", "Soleum-xi,", "Minho-óp-pa"]


@pytest.mark.parametrize("token", ["san", "sama", "nim", "ssi", "tan", "nee", "nii", "Kun", "con-sans", "Ra-TAN", "DOT-SAMA"])
def test_a_suffix_word_alone_or_a_look_alike_is_left_alone(token: str) -> None:
    assert _said(f"Rồi {token} đến.")[1] == token


# ---- TN "Nghe ngay" lượt 3 (bộ thử Corpus/research/tn, gold_spec): tiếng cười, thán từ, nói lắp, Lv, từ mượn, đơn vị tiền ------------------------------
@pytest.mark.parametrize("token, reading", [("Haha", "ha ha"), ("hahaha", "ha ha ha"), ("HAHA", "ha ha"), ("Hehe", "hê hê"), ("Hihi", "hi hi"), ("fufu", "phu phu"),
                                             ("Hm", "hừm"), ("Huh", "hả"), ("Hic", "hích"), ("Ooh", "ô"), ("Urgh", "ức")])
def test_a_laugh_or_an_interjection_is_read_as_sounds(token: str, reading: str) -> None:
    assert _said(f"Rồi {token}, đến.") == ["Rồi", f"{reading},", "đến."]
    assert _said(f"Rồi {token}, đến.", "ja") == _said(f"Rồi {token}, đến.", "ko") == _said(f"Rồi {token}, đến.", None, False)


def test_a_word_stretched_in_several_places_is_collected_when_it_makes_one_syllable() -> None:
    assert shouts.stretch_reading("Cccchhhhàaaaaaoooo") == "chào… ò"
    assert shouts.stretch_reading("sssssáaaannnngggg") == "sáng…"
    assert shouts.stretch_reading("Bbbbbuuuuuôooiiii") is None, "gộp ra không phải âm tiết: giữ nguyên"


@pytest.mark.parametrize("text, said", [
    ("T-tôi không biết.", "tờ… tôi không biết."),
    ("“C-Chuyện đó", "“chờ… Chuyện đó"),
    ("Ng-ngài và K-Không và Đ-Điều", "ngờ… ngài và khờ… Không và đờ… Điều"),
    ("E-em muốn A-anh", "e… em muốn a… anh"),
    ("[Kh- Không phải", "[khờ… Không phải"),
    ("“……T-, tức là", "“……tờ, tức là"),
    ("Hà-Hà đến, X-quang, E-mail", "Hà-Hà đến, X-quang, E-mail"),  # âm tiết đầy đủ hay không phải phần đầu của chữ sau: không phải nói lắp
])
def test_a_stutter_is_read_as_the_sound_it_starts(text: str, said: str) -> None:
    assert " ".join(_said(text)) == said


def test_the_word_after_a_stutter_still_goes_through_the_name_rules() -> None:
    assert " ".join(_said("“T-Tsukinoki-senpai cho", "ja")) == "“tờ… Xu-ki-nô-ki-xen-pai cho"
    assert " ".join(_said("A-anime")) == "a… a-ni-me"


@pytest.mark.parametrize("text, said", [
    ("Lv 5, Lv.15] Lvl.1 LV5 và lv 40.", "level 5, level 15], level 1 level 5 và level 40."),
    ("Lv ơi, LVL. LV", "lờ vê ơi, lờ vê lờ. lờ vê"),  # chủ sách 04-10: không đi với số thì không chắc là cấp độ: đọc tên chữ cái
])
def test_lv_is_a_level_only_right_before_a_number(text: str, said: str) -> None:
    assert " ".join(_said(text)) == said


def test_lv_is_vietnamised_with_the_other_english_words_for_a_voice_that_cannot_say_english() -> None:
    assert _said("Lv 5", None, False) == [names.english_reading("level") or "level", "5"]


@pytest.mark.parametrize("token, reading", [
    ("sofa", "xô-pha"), ("Logic", "lô-gích"), ("video", "vi-đê-ô"), ("violin", "vi-ô-lông"), ("piano", "pi-a-nô"), ("sandal", "xăng-đan"), ("vali", "va-li"), ("robot", "rô-bốt"),
    ("gorilla", "gô-ri-la"), ("anime", "a-ni-me"), ("Ninja", "nin-gia"), ("manga", "man-ga"), ("bento", "ben-tô"), ("kimono", "ki-mô-nô"), ("sake", "xa-ke"),
    ("takoyaki", "ta-cô-gia-ki"), ("senpai", "xen-pai"), ("Umu", "u-mu"), ("tsukkomi", "xúc-cô-mi"),
])
def test_a_common_loanword_is_read_with_any_book_origin_and_any_voice(token: str, reading: str) -> None:
    for origin in (None, "ja", "ko"):
        assert _said(f"Rồi {token}.", origin)[1].lower() == f"{reading}."
    assert _said(f"Rồi {token}.", None, False)[1].lower() == f"{reading}."


def test_won_yen_and_kwan_are_units_only_after_a_number() -> None:
    assert _said("3 triệu won, 100 yen, 5 kwan, mười won") == ["3", "triệu", "guôn,", "100", "yên,", "5", "quan,", "mười", "guôn"]
    assert _said("Anh won, rồi yen.") == ["Anh", "won,", "rồi", "yen."]


def test_a_capital_o_starting_a_hyphenated_name_is_a_syllable_not_a_letter() -> None:
    assert _said("Otsuki-san, Okayama, Onii-sama", "ja") == ["o-xu-ki-xan,", "o-ca-gia-ma,", "o-ni-xa-ma"]


def test_a_parenthesised_abbreviation_glued_to_a_word_is_spelled() -> None:
    assert _said("đó.”(GM) xong") == ["đó.”(giê em)", "xong"]


def test_two_words_glued_by_an_ellipsis_or_a_dash_are_read_one_by_one() -> None:
    assert _said("rồi…Senpai.” Babi—người") == ["rồi…xen-pai.”", "Babi, người"]
    assert _said("Thế chiến II—thời kỳ") == ["Thế", "chiến", "hai, thời", "kỳ"]
