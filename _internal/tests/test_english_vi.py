"""Luật Việt hoá từ / tên tiếng Anh (abook/english_vi.py, docs/READING_FOREIGN_NAMES.md mục 1 và 4).

Bốn lớp kiểm:
  - phán quyết chủ sách (cố định): đầu ra phải khớp; luật (tắt bảng ghi đè) cũng phải ra trừ ca riêng Kate / Pete / slime;
  - mọi dạng CÓ NGUỒN (tests/english_vi_evidence.py): khớp, hoặc không khớp kèm lý do;
  - từng dòng luật, bằng ca nhỏ tự dựng; chạy thử trên ~300 từ tiếng Anh thật;
  - bộ ví dụ dùng chung với Kotlin (tests/fixtures/english_vi/cases.json) và từ điển gọn (assets/english_phones.txt.gz) là bản sinh mới nhất.
"""
from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path

import pytest

from abook.vietnamese_syllable import valid_spoken_form, valid_syllable
from abook.english_vi import (
    OPEN_CHOICES,
    PHONES_PATH,
    load_phones,
    vietnamized_english,
    vietnamized_english_flags,
)
from tests import english_vi_evidence as evidence

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "english_vi" / "cases.json"
# Mọi phán quyết chủ sách (04-10, bốn lần): (chữ, các dạng chủ sách cho là đúng; dạng thứ hai là cách đọc khác cũng được)
OWNER = [(token, sources) for token, sources, kind in evidence.SOURCED if kind == "owner"] + [("VIP", ("víp",)), ("ID", ("ai-đi",))]
# ca riêng: chỉ bảng ghi đè ra được, luật không suy rộng (vòng 9: từ Washington trở đi)
FIXED_ONLY = {"Kate", "Pete", "guild", "time", "Thomas", "great", "Gate", "higher", "Laplace", "Walt", "Dalton", "days", "VIP", "ID",
              "Washington", "Damien", "Darius", "Violet", "Forthorthe", "Judge", "Max", "Mikhail", "Blanche", "Reine", "Wolf", "Walker",
              "Undead", "Hilde", "oldest", "card", "wind", "world", "monster", "brother", "Charlie", "Anne", "Louise", "April"}
# Chủ sách viết những dạng mà bộ kiểm âm tiết (đúng chính tả) không nhận; không nới bộ kiểm, nên chưa có cách đọc (hỏi lại chủ sách)
TALLY = {"owner": [120, 156], "official": [2, 4], "textbook": [8, 32], "press": [0, 2], "community": [6, 18]}


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _matches(token: str, sources: tuple[str, ...]) -> bool:
    found = vietnamized_english(token, overrides=False)
    return found is not None and found.casefold() in {source.casefold() for source in sources}


# ---- chủ sách ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("token,forms", OWNER)
def test_owner_rulings_hold(token, forms):
    assert vietnamized_english(token) in forms


@pytest.mark.parametrize("token,forms", [(token, forms) for token, forms in OWNER if token not in FIXED_ONLY])
def test_the_rules_alone_reach_the_owner_forms(token, forms):
    assert vietnamized_english(token, overrides=False) in forms


# ---- dạng có nguồn -----------------------------------------------------------------------------------------------------

def test_every_sourced_form_matches_or_is_explained():
    matched, unexplained, stale = [], [], []
    for token, sources, _kind in evidence.SOURCED:
        reading = vietnamized_english(token, overrides=False)
        if _matches(token, sources):
            matched.append(token)
            assert token not in evidence.EXPLAINED, f"{token} khớp nhưng vẫn ghi là không khớp"
        elif token not in evidence.EXPLAINED:
            unexplained.append((token, reading, sources))
        elif evidence.EXPLAINED[token][0] != (reading or ""):
            stale.append((token, reading, evidence.EXPLAINED[token][0]))
    assert not unexplained, f"không khớp mà chưa có lý do: {unexplained}"
    assert not stale, f"cách đọc đổi mà lý do còn viết cho cách đọc cũ: {stale}"
    assert len(matched) + len(evidence.EXPLAINED) == len(evidence.SOURCED)


def test_tally_of_sourced_forms_by_kind():
    tally: dict[str, list[int]] = {}
    for token, sources, kind in evidence.SOURCED:
        entry = tally.setdefault(kind, [0, 0])
        entry[0] += _matches(token, sources)
        entry[1] += 1
    # (khớp đủ thanh, tổng). Chủ sách: TALLY_OWNER, phần còn lại là ca riêng (bảng ghi đè, xem FIXED_ONLY); dạng của nguồn đã thành ca
    # chủ sách khi chủ sách chốt (Tô-mát, Bốt-tơn, Rốc-ki, Đan-tơn, Oa-xinh-tơn, Xờ-cót-lừn, Xếch-xơ-pia). Cộng đồng chỉ để xem.
    assert tally == TALLY


# ---- từng dòng luật ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("token,reading", [
    # -əl cuối -> ồ, thanh huyền; l sau ai / ao / oi -> "ồ" không phụ âm đầu; l cuối sau i -> u (chủ sách); l khép khác -> n (Men-bơn)
    ("table", "tây-bồ"), ("Daniel", "Đa-ni-ồ"), ("smile", "xờ-mai-ồ"), ("oil", "oi-ồ"), ("bill", "biu"), ("Melbourne", "Men-bơn"),
    # schwa + n / m giữ phụ âm cuối, thanh ngang (chủ sách: Oa-sinh-tơn, Ê-đi-xơn đúng); schwa theo chữ viết
    ("Washington", "Oa-xinh-tơn"), ("Philadelphia", "Phi-la-đen-phi-a"), ("Dallas", "Đa-lát"),
    # cụm phụ âm đầu -> Cờ- thanh huyền (chủ sách: xờ-kiu, bờ-lếch); giữa từ ơ ngang; t + r giữ tr; t đầu từ giữ t
    ("spell", "xờ-peo"), ("star", "xờ-ta"), ("Brian", "Bờ-rai-an"), ("trust", "trắt"), ("Detroit", "Đi-troi"), ("Tyler", "Tai-lờ"),
    # phụ âm tắc nhân đôi sau nguyên âm nhấn chính (máp-pồ)
    ("happy", "háp-pi"), ("ticket", "tích-két"),
    # /eɪ/: mở ây, khép p -> a, khép c -> êch, khép mũi ê; ai + m -> am; ai / ao / oi + phụ âm khác không khép; /æŋk/ -> anh
    ("day", "đây"), ("name", "nêm"), ("make", "mếch"), ("crime", "cờ-ram"), ("five", "phai"), ("town", "tao"), ("Yorktown", "I-oóc-tao"),
    ("rank", "ranh"), ("thank", "thanh"),
    # w / y bán âm, qu, ng không mở âm tiết, r của ơ trước nguyên âm
    ("William", "Guy-li-am"), ("queen", "quin"), ("you", "iu"), ("Hemingway", "He-minh-uây"), ("Colorado", "Co-lơ-ra-đô"),
    # phụ âm cuối hữu thanh / xát -> tắc + sắc (Bớt, Tô-mát); r cuối bỏ; cụm cuối giữ một
    ("Bird", "Bớt"), ("bad", "bát"), ("love", "lắp"), ("York", "I-oóc"), ("first", "phớt"),
    # tên ngắn một phụ âm đầu + tắc + e câm theo mặt chữ, chỉ với tên viết hoa
    ("Coke", "Co-ke"), ("Nate", "Na-te"), ("Shake", "Sa-ke"), ("Lace", "La-xe"), ("Cale", "Ca-le"),
    # /eɪ/ + t -> êt, /eɪ/ + s cuối -> ây; /aɪər/ -> ai; /ɔːl/ -> ôn; từ ghép không có trong từ điển đọc từng phần
    ("gate", "ghết"), ("fire", "phai"), ("call", "côn"), ("sandworm", "xan-u-ơm"), ("water", "guốt-tờ"), ("Walter", "Guôn-tờ"), ("Warrior", "Goa-ri-ơ"),
    # tên ngắn e câm: âm mũi theo âm vị (Dane), g + e cứng (Page); tắc + l / r giữa từ -> Cờ huyền; w đầu từ -> gu
    ("Dane", "Đên"), ("Page", "Pa-ghe"), ("tablet", "táp-lét"), ("Andrew", "An-riu"),
    # -land lừn chỉ sau phụ âm chặn + l (địa danh); tên người giữ lan. Từ mượn đã vào từ điển tiếng Việt: taxi -> tắc-xi
    ("England", "Inh-gơ-lừn"), ("Iceland", "Ai-xơ-lừn"), ("Roland", "Rô-lừn"), ("Garland", "Ga-lừn"), ("taxi", "tắc-xi"),
    # l cuối sau e -> eo; tắc + r sau nguyên âm nhấn khép; dh -> d; AO + s + t -> ô
    ("bell", "beo"), ("cobra", "cốp-ra"), ("this", "dít"), ("Austin", "Ô-tin"),
    # đường chính tả (không có trong từ điển)
    ("Encrid", "En-cờ-rít"), ("Lancel", "Lan-xồ"), ("Calian", "Ca-li-an"), ("Litana", "Li-ta-na"),
    # nối gạch
    ("Jean-Paul", "Gin Pau"),
])
def test_reading_follows_the_convention(token, reading):
    assert vietnamized_english(token) == reading


@pytest.mark.parametrize("token", ["MARY", "iPhone", "McDonald", "O'Brien", "Ko1", "", "Jean Paul", "Vĩnh"])
def test_unsure_is_none(token):
    assert vietnamized_english(token) is None


def test_without_a_dictionary_the_spelling_route_reads():
    assert vietnamized_english_flags("Washington", {}, overrides=False) == ("Goa-sinh-ton", ("via:spelling",))
    assert vietnamized_english_flags("Washington", overrides=False) == ("Goa-sinh-tơn", ("via:phonemes",))
    assert vietnamized_english_flags("España", {}) == ("Ét-pa-nha", ("via:spelling",))  # ñ -> nh
    assert vietnamized_english("Encrid", {}) == vietnamized_english("Encrid")
    assert vietnamized_english("tank", {}, overrides=False) == "tanh"


def test_analogy_points_are_flagged_and_settled_points_are_not():
    assert vietnamized_english_flags("rank") == ("ranh", ("via:phonemes", "analogy:ank"))  # theo tank -> tanh
    # w đầu từ -> g + âm đệm đã là luật (vòng 9 chủ sách chốt Will, William, Wendy, Weiss, west, Wood, water): không cờ analogy
    assert vietnamized_english_flags("Walter") == ("Guôn-tờ", ("via:phonemes",))
    assert vietnamized_english("sandworm") == "xan-u-ơm"  # w ở nửa sau từ ghép giữ u
    for word in ("Master", "Blake", "Lyle", "Tom", "Tyler", "Zeke", "late", "Grace", "Rose", "fireball", "Cage", "Luce", "Jane", "Laplace"):  # chủ sách đã chốt: không cờ
        assert not [flag for flag in vietnamized_english_flags(word, overrides=False)[1] if not flag.startswith("via:")], word
    assert vietnamized_english_flags("Mike") == ("Mi-ke", ("via:override",))
    assert vietnamized_english_flags("Mike", overrides=False) == ("Mi-ke", ("via:face",))
    assert OPEN_CHOICES == {}


def test_the_vowels_without_a_rhyme_are_rewritten_not_waved_through():
    """ơc / ơch và o + ch không phải vần tiếng Việt: ɜːr + c -> âc (Kirk cấc), o + ch cuối -> óc (George gióc); bộ kiểm không nới."""
    for form in ("cớc", "bớc", "gióch"):
        assert not valid_spoken_form(form), form
    assert vietnamized_english("Kirk", overrides=False) == "Cấc" and vietnamized_english("Burke", overrides=False) == "Bấc"
    assert vietnamized_english("George", overrides=False) == "Gióc"
    assert vietnamized_english("Hamburg", overrides=False) == "Ham-bơ"  # ɜːr trước g câm: vẫn ơ


def test_the_labialised_g_forms_pass_the_syllable_checker():
    for syllable in ("guy", "guyu", "guây", "guốt", "goét", "goen"):  # guen không nhận: oe viết goen, cùng âm
        assert valid_syllable(syllable), syllable


def test_the_trial_words_all_read_with_and_without_a_dictionary():
    cases = [case for case in json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"] if case["group"] == "trial"]
    assert len(cases) == 300
    assert all(case["reading"] is not None and case["reading_nodict"] is not None for case in cases)


# ---- dữ liệu sinh ra ---------------------------------------------------------------------------------------------------

def test_shared_fixture_matches_python():
    wrong = []
    for case in json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]:
        for options, reading_key, flags_key in (({}, "reading", "flags"), ({"dictionary": {}}, "reading_nodict", "flags_nodict")):
            found = vietnamized_english_flags(case["token"], **options)
            got = (None, []) if found is None else (found[0], list(found[1]))
            if got != (case[reading_key], case[flags_key]):
                wrong.append((case["token"], reading_key, got, case[reading_key]))
    assert not wrong, wrong[:10]


def test_shared_fixture_is_the_latest_build():
    assert FIXTURE.read_bytes() == _load_script("build_english_vi_fixture").cases_bytes(), \
        "chạy lại scripts/build_english_vi_fixture.py"


def test_compact_dictionary_is_the_latest_build():
    built = _load_script("build_english_phones").phones_bytes()
    assert PHONES_PATH.read_bytes() == built, "chạy lại scripts/build_english_phones.py"
    entries = load_phones(PHONES_PATH)
    assert entries["maple"] == "M EY1 P AH0 L"
    assert len(entries) > 100_000
    assert len(gzip.decompress(built)) > 2 * len(built)
