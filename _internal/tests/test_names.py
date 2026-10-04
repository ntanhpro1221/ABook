"""Tên Nhật / Hàn trong "Nghe ngay" đọc theo luật phiên âm (abook/readaloud/names.py + vieneu.spoken_tokens): từ tiếng Anh giữ nguyên, âm tiết Việt
giữ nguyên, tên romaji / RR đổi sang âm tiết Việt, gốc của cuốn tự đoán và người dùng ghi đè được, khoá bộ đệm clip theo cách đọc."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from abook import english_vi
from abook.readaloud import names, vieneu
from abook.readaloud.cache import clip_key
from abook.readaloud.service import ReadAloud
from abook.webui import word_timing
from tests.test_readaloud_vieneu import fake_voices  # noqa: F401 - fixture dùng chung

ROOT = Path(__file__).resolve().parents[1]
KOTLIN = ROOT / "mobile/android/app/src/main/java/vn/abook/player/readaloud/EnglishWords.kt"
FIXTURE = Path(__file__).parent / "fixtures" / "vieneu" / "android" / "text.json"


def _said(text: str, origin: str | None) -> list[str]:
    return vieneu.spoken_tokens(word_timing.tokens(text), origin)


# ---- danh sách từ tiếng Anh -----------------------------------------------------------------------------------------------------
def test_the_english_list_is_small_sorted_and_lowercase() -> None:
    words = names.english_words()
    text = names.ENGLISH_FILE.read_text(encoding="utf-8")
    assert text.split() == sorted(words) and all(re.fullmatch("[a-z]{2,}", word) for word in words)
    assert b"\r" not in names.ENGLISH_FILE.read_bytes()
    assert 5_000 < len(words) < 10_000 and names.ENGLISH_FILE.stat().st_size < 80_000


def test_english_names_stay_and_common_japanese_names_do_not() -> None:
    words = names.english_words()
    assert {"kate", "mike", "rose", "anne", "emma", "nina", "sara", "level", "okay", "mario", "jennifer", "smith"} <= words
    assert not {"hana", "rika", "mina", "kana", "nana", "sakura", "haruto", "yamato", "tanaka", "kenji"} & words


def test_the_kotlin_copy_of_the_list_is_the_same_words() -> None:
    chunks = re.findall(r'^        "([a-z ]+)"', KOTLIN.read_text(encoding="utf-8"), flags=re.M)
    assert " ".join(chunks).split(" ") == sorted(names.english_words())
    assert all(len(chunk.encode()) < 65_535 for chunk in chunks)


# ---- token nào được đọc theo luật --------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("token, reading", [
    ("Haruto", "Ha-ru-tô"), ("Yamato", "Gia-ma-tô"), ("Kyouko", "Ki-âu-cô"), ("Hana", "Ha-na"), ("Rika", "Ri-ca"), ("Sakura", "Xa-cu-ra"),
    ("Haruto-kun", "Ha-ru-tô-cun"), ("Tōkyō", "Tô-ki-ô"),
    # hậu tố gọi nối gạch vào tên, không tách thành hai chữ
    ("Jin-dono", "Gin-đô-nô"), ("Yuki-tan", "Giu-ki-tan"), ("Kou-nii", "Câu-ni"), ("Sora-nee", "Xô-ra-ne"), ("Tanaka-senpai", "Ta-na-ca-xen-pai"),
])
def test_a_japanese_name_in_a_japanese_book_is_read_by_the_rules(token: str, reading: str) -> None:
    assert _said(f"Rồi {token}.", "ja")[1] == f"{reading}."


@pytest.mark.parametrize("token", ["Kate", "Mike", "Rose", "Anne", "Emma", "Nina", "Sara", "Mario", "Level", "Okay", "Smith"])
def test_an_english_name_is_left_to_the_voice_even_in_a_japanese_book(token: str) -> None:
    assert _said(f"Rồi {token}.", "ja") == ["Rồi", f"{token}."]


@pytest.mark.parametrize("token", ["Hm", "Nn", "Haiz", "Goblin", "Elf", "Wizard", "Hoa", "Nam", "Mai", "Tôi", "Ôi", "Anh", "A", "Aa", "McDonald", "Spider-Man", "Haruto's", "Weisss"])
def test_vietnamese_syllables_shouts_capitals_and_odd_words_are_left_alone(token: str) -> None:
    assert _said(f"Rồi {token}.", "ja") == ["Rồi", f"{token}."]
    assert _said(f"Rồi {token}.", "ko") == ["Rồi", f"{token}."]


def test_names_stay_without_an_origin_and_punctuation_around_a_name_is_kept() -> None:
    toks = word_timing.tokens("“Haruto-kun,” Yamato! (Kyouko) Sakura… Hajime")
    # không gốc: chỉ hậu tố gọi nối gạch cho biết là tên Nhật (names.honorific_reading); tên trần để nguyên
    assert vieneu.spoken_tokens(toks) == ["“Ha-ru-tô-cun,”", "Yamato!", "(Kyouko)", "Sakura…", "Hajime"] == vieneu.spoken_tokens(toks, None) == vieneu.spoken_tokens(toks, "zz")
    assert vieneu.spoken_tokens(toks, "ja") == ["“Ha-ru-tô-cun,”", "Gia-ma-tô!", "(Ki-âu-cô)", "Xa-cu-ra…", "Ha-gi-me"]


def test_a_korean_book_reads_romanized_korean_names() -> None:
    assert _said("Seo-yeon gặp Ji-ho và Geun-hye.", "ko") == ["Xeo-gion", "gặp", "Gi-hô", "và", "Cưn-hê."]


def test_the_shown_words_and_their_count_never_change() -> None:
    text = "Haruto-kun, Kyouko-san đã đến. “Yamato!” Kate hỏi Mike, còn Rose và Hana thì cười. Seo-yeon cũng ở đó."
    for origin in (None, "ja", "ko"):
        toks, parts = vieneu.units(text, 256, origin)
        assert " ".join(unit.text(toks) for unit in parts) == text
        assert [i for unit in parts for i in range(unit.first, unit.last + 1)] == list(range(len(toks)))
    assert vieneu.units(text, 256, "ja")[1][0].pieces != vieneu.units(text, 256)[1][0].pieces


def test_a_roman_numeral_is_still_a_number_and_not_a_name() -> None:
    assert _said("Chương IV, Haruto.", "ja") == ["Chương", "bốn,", "Ha-ru-tô."]


# ---- gốc của cuốn --------------------------------------------------------------------------------------------------------------------
JA = "Haruto Yuki Sakura Kyouko Takeshi Hiroshi Akira Kenji Yamato Naoki Satoshi Ayaka".split()
WEST = "Alberu Eruhaben Henituse Harol Witira Cale Mirabelle Ruel Alon Gideon Damien Aurora".split()
KO = "Si-eun So-hye Hwi-min Seo-ram Deok-gu Kang-ho Ha-jin Joo-seon Min-jun Seo-yeon Ji-ho Geun-hye".split()


def _book(listed: list[str], rounds: int = 10) -> str:
    return " ".join(f"{name} nói." for _ in range(rounds) for name in listed)


def test_a_book_of_romaji_names_is_japanese_and_a_book_of_korean_names_is_korean() -> None:
    assert names.book_origin([_book(JA)]) == "ja"
    assert names.book_origin([_book(KO)]) == "ko"


@pytest.mark.parametrize("texts", [
    [_book(WEST)],
    [_book(WEST + JA[:3])],
    [_book(JA[:5], 40)],  # ít tên khác nhau
    [_book(JA, 1)],  # ít lần xuất hiện
    ["Hoa và Nam đi chợ với Mai. " * 80],
    ["Rose, Mike, Kate, Emma, Anne, Nina và Sara đi dạo. " * 80],
    [],
])
def test_a_book_with_other_names_has_no_origin(texts: list[str]) -> None:
    assert names.book_origin(texts) is None


def test_honorifics_beside_romaji_names_lower_the_share_needed() -> None:
    mixed = _book(WEST * 2 + JA, 4)
    assert names.book_origin([mixed]) is None, "tên Âu nhiều: tỉ lệ romaji thấp"
    honorific = " ".join(f"{name}-san nói." for name in JA[:4]) + " "
    assert names.book_origin([mixed + " " + honorific * 8]) == "ja"
    assert names.book_origin([mixed + " " + honorific * 2]) is None, "ít hậu tố"
    assert names.book_origin([mixed + " " + (" ".join(f"{name}-san nói." for name in WEST[:4]) + " ") * 8]) is None, "hậu tố đi với tên không phải romaji"
    assert names.book_origin([mixed + " " + (" ".join(f"{name}-dono nói." for name in JA[:2]) + " ") * 8]) is None, "chỉ 2 tên khác nhau"
    korean = _book(KO, 10) + " ".join(f"{name}-nim nói." for name in KO) * 10
    assert names.book_origin([korean]) == "ko", "-nim của Hàn không phải dấu hiệu Nhật"


def test_only_the_first_chapters_are_used() -> None:
    west, japanese = _book(WEST), _book(JA)
    assert names.SAMPLE_CHAPTERS == 40
    assert names.book_origin([west] * 40 + [japanese] * 200) is None
    assert names.book_origin([west] * 40 + [japanese] * 200, sample=None) == "ja"


def test_book_origins_remember_the_guess_and_the_users_override(tmp_path: Path) -> None:
    store = names.BookOrigins(tmp_path / "origins.json")
    calls: list[int] = []

    def texts() -> list[str]:
        calls.append(1)
        return [_book(JA)]

    assert store.get("b1") == {"guess": None, "override": None}
    assert store.origin("b1", texts) == "ja" and store.origin("b1", texts) == "ja"
    assert len(calls) == 1, "đoán một lần, nhớ"
    assert store.get("b1") == {"guess": "ja", "override": None}
    store.override("b1", "none")
    assert store.origin("b1", texts) is None
    store.override("b1", "ko")
    assert store.origin("b1", texts) == "ko"
    store.override("b1", None)
    assert store.origin("b1", texts) == "ja" and len(calls) == 1
    assert names.BookOrigins(tmp_path / "origins.json").get("b1")["guess"] == "ja", "còn sau khi mở lại"
    assert store.origin("b2", lambda: ["Hoa đi chợ."]) is None and store.get("b2")["guess"] == "none"
    with pytest.raises(ValueError):
        store.override("b1", "zh")
    assert b"\r" not in (tmp_path / "origins.json").read_bytes()


def test_a_guess_made_by_an_older_rule_is_made_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = names.BookOrigins(tmp_path / "origins.json")
    assert store.origin("b", lambda: [_book(JA)]) == "ja"
    monkeypatch.setattr(names, "RULE_VERSION", names.RULE_VERSION + 1)
    assert store.origin("b", lambda: ["Hoa đi chợ."]) is None


# ---- khoá bộ đệm clip ------------------------------------------------------------------------------------------------------------
def test_the_clip_key_only_changes_for_text_the_origin_changes(fake_voices, tmp_path: Path) -> None:  # noqa: F811
    provider, engines = fake_voices
    assert clip_key("p", "v", "t") == clip_key("p", "v", "t", "")
    assert clip_key("p", "v", "t", "ja") != clip_key("p", "v", "t")
    assert provider.reading_tag("Haruto đến.", "ja") == "ja" and provider.reading_tag("Haruto đến.", None) == ""
    assert provider.reading_tag("Kate đến.", "ja") == "" and provider.reading_tag("Hoa đến.", "ko") == ""
    service = ReadAloud(tmp_path / "cache", [provider])
    voice = "vieneu:turbo/Thường"
    plain = service.clip(voice, "Haruto đến cùng Kate và Mike.")
    named = service.clip(voice, "Haruto đến cùng Kate và Mike.", origin="ja")
    assert plain["file"] != named["file"]
    assert "ha-ru-tô" in " ".join(engines["turbo"].calls) and "haruto" in " ".join(engines["turbo"].calls)
    count = len(engines["turbo"].calls)
    assert service.clip(voice, "Haruto đến cùng Kate và Mike.", origin="ja") == named and len(engines["turbo"].calls) == count
    same = service.clip(voice, "Kate và Mike đến.")
    assert service.clip(voice, "Kate và Mike đến.", origin="ja") == same, "đoạn không có tên nào đổi dùng chung clip"
    assert service.clip(voice, "Haruto đến cùng Kate và Mike.", cached_only=True) == plain


# ---- bộ ví dụ dùng chung với Kotlin (scripts/vieneu_android_fixtures.py) -------------------------------------------------------------
def test_the_shared_origin_cases_match() -> None:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["origins"]
    assert len(cases) >= 13 and {case["origin"] for case in cases} == {"ja", "ko", None}
    for case in cases:
        texts, sample = case["texts"], case.get("sample") or names.SAMPLE_CHAPTERS
        keys = ("total", "names", "ja_names", "ko_names", "honorific", "honorific_names")
        shares = names.origin_shares(*names.scan_names(texts[:sample]))
        assert names.book_origin(texts, sample=sample) == case["origin"]
        assert {key: shares[key] for key in keys} == {key: case[key] for key in keys}


# ---- máy chủ -------------------------------------------------------------------------------------------------------------------------
def test_the_server_takes_the_origin_from_the_request_or_from_the_book(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from abook.webui import packages, server

    texts = {1: _book(JA), 2: "Chương hai."}
    monkeypatch.setattr(packages, "is_package", lambda _path: True)
    monkeypatch.setattr(packages, "edited_manifest", lambda _path: {"chapters": [{"id": 1}, {"id": 2}, {"id": "x"}]})
    monkeypatch.setattr(packages, "chapter_text", lambda _path, chapter: texts.get(chapter))

    def listenable(book: str) -> Path:
        if book != "known":
            raise server.ApiError(404, "Không tìm thấy sách này trong thư viện")
        return tmp_path

    handler = SimpleNamespace(app=SimpleNamespace(readaloud=SimpleNamespace(origins=names.BookOrigins(tmp_path / "o.json")), _listenable=listenable))
    origin = lambda body: server.Handler._reading_origin(handler, body)  # noqa: E731
    assert origin({}) is None and origin({"bookId": ""}) is None and origin({"bookId": 3}) is None
    assert origin({"origin": "ja"}) == "ja" and origin({"origin": "none", "bookId": "known"}) is None and origin({"origin": "zz"}) is None
    assert origin({"bookId": "unknown"}) is None
    assert origin({"bookId": "known"}) == "ja"
    handler.app.readaloud.origins.override("known", "ko")
    assert origin({"bookId": "known"}) == "ko" and origin({"bookId": "known", "origin": "ja"}) == "ja"


# ---- giọng không nói được âm Anh (Supertonic): từ Anh Việt hoá, tên Nhật / Hàn theo gốc cuốn ----------------------------------------------------
def _said_en(text: str, origin: str | None = None, speaks_english: bool = False) -> list[str]:
    return vieneu.spoken_tokens(word_timing.tokens(text), origin, speaks_english)


def test_a_voice_that_speaks_english_keeps_english_words_exactly_as_before() -> None:
    text = "Tôi gặp Rose và Mike. Anh ấy mở laptop, dùng skill Fireball cho Haruto-kun, Kyouko."
    toks = word_timing.tokens(text)
    for origin in (None, "ja", "ko"):
        assert vieneu.spoken_tokens(toks, origin, True) == vieneu.spoken_tokens(toks, origin) == names.spoken_names(toks, origin, True)
        assert vieneu.spoken_tokens(toks, origin) == vieneu.spoken_tokens(toks, origin, True)
    assert [a for a, b in zip(names.spoken_names(toks, None, True), toks) if a != b] == ["Ha-ru-tô-cun,"], "không gốc, nói được Anh: chỉ tên có hậu tố gọi Nhật đổi"


def test_english_words_and_names_become_syllables_for_a_voice_that_cannot_say_them() -> None:
    words = ["laptop", "Facebook", "email", "Jennifer", "Rose"]
    said = _said_en("Anh ấy mở laptop, vào Facebook rồi gửi email cho Jennifer và Rose.")
    assert said[3] == english_vi.vietnamized_english("laptop") + "," and said[5] == english_vi.vietnamized_english("Facebook")
    assert said[8] == english_vi.vietnamized_english("email") and said[10] == english_vi.vietnamized_english("Jennifer")
    assert said[12] == english_vi.vietnamized_english("Rose") + "." and not set(words) & set(said), "chữ Anh không còn trong chữ đem đọc"
    assert [said[i] for i in (0, 1, 2, 4, 6, 7, 9, 11)] == ["Anh", "ấy", "mở", "vào", "rồi", "gửi", "cho", "và"], "chữ Việt không đổi"
    # ca chủ sách chốt (english_vi.OWNER): đứng trên mọi luật
    assert _said_en("Mike, Kate và Pete đến.") == ["Mi-ke,", "Ca-tê", "và", "Pi-tờ", "đến."]
    assert _said_en("Dùng skill, level và Boss.") == ["Dùng", "xờ-kiu,", "le-vồ", "và", "Bót."]


@pytest.mark.parametrize("token", ["Hoa", "Nam", "ba", "con", "may", "Tôi", "Hà-Nội", "10kg", "x", "A"])
def test_vietnamese_syllables_and_odd_words_are_left_to_the_voice(token: str) -> None:
    assert _said_en(f"Rồi {token} đến.") == ["Rồi", token, "đến."]


def test_a_unit_after_a_number_is_left_to_the_text_normalizer() -> None:
    assert _said_en("Nặng 10 kg, cao 5 m.") == ["Nặng", "10", "kg,", "cao", "5", "m."]


def test_punctuation_is_kept_and_the_shown_words_and_their_count_never_change() -> None:
    assert _said_en("“Rose,” Mike! (laptop)") == [f"“{english_vi.vietnamized_english('Rose')},”", "Mi-ke!", f"({english_vi.vietnamized_english('laptop')})"]
    text = "Rose gặp Mike ở quán. Haruto-kun, Kyouko-san đến. Anh mở laptop rồi gửi email cho Jennifer!"
    for origin in (None, "ja", "ko"):
        toks, parts = vieneu.units(text, 256, origin, False)
        assert " ".join(unit.text(toks) for unit in parts) == text
        assert [i for unit in parts for i in range(unit.first, unit.last + 1)] == list(range(len(toks)))


def test_japanese_names_follow_the_book_origin_and_the_english_rule_takes_the_rest() -> None:
    assert _said_en("Kyouko và Haruto gặp Rose.", "ja") == ["Ki-âu-cô", "và", "Ha-ru-tô", "gặp", english_vi.vietnamized_english("Rose") + "."]
    assert _said_en("Kyouko và Haruto gặp Rose.", None)[0] != "Ki-âu-cô", "không gốc: đi đường chữ Anh, không phải luật romaji"
    assert vieneu.spoken_tokens(word_timing.tokens("Kyouko gặp Rose."), "ja") == ["Ki-âu-cô", "gặp", "Rose."], "giọng nói được Anh: tên Anh để nguyên"


def test_the_reading_tag_changes_only_when_the_reading_does() -> None:
    text = "Rose gặp Haruto."
    assert vieneu.reading_tag(text, "ja") == "ja" and vieneu.reading_tag(text, None) == "", "VieNeu: y như trước"
    assert vieneu.reading_tag("Rose gặp Mike.", "ja") == "" and vieneu.reading_tag("Rose gặp Mike.", None) == ""
    assert vieneu.reading_tag(text, "ja", False) == f"ja+en{names.ENGLISH_READING}"
    assert vieneu.reading_tag("Rose gặp Mike.", "ja", False) == vieneu.reading_tag("Rose gặp Mike.", None, False) == f"en{names.ENGLISH_READING}"
    assert vieneu.reading_tag("Tôi về nhà.", "ja", False) == "", "không từ nước ngoài nào: dùng chung clip cũ"
    assert vieneu.reading_tag("Haruto đến.", "ja", False) == "ja"


def test_every_provider_says_whether_its_voice_speaks_english() -> None:
    from abook.readaloud import azure, fpt, google, supertonic, viettel
    from abook.readaloud.service import DeviceProvider, EdgeProvider

    assert vieneu.VieneuProvider.speaks_english and EdgeProvider.speaks_english, "đo 04-10: đọc chữ Anh để nguyên tốt"
    assert azure.AzureProvider.speaks_english and google.GoogleProvider.speaks_english
    # chưa đo / chưa quyết: giữ cách đọc cũ (chữ Anh để nguyên) tới khi phép đo nói khác
    assert supertonic.SupertonicProvider.speaks_english and fpt.FptProvider.speaks_english
    assert viettel.ViettelProvider.speaks_english and DeviceProvider.speaks_english
