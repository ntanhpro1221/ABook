"""Luật đọc romaji Nhật / RR Hàn thành âm tiết Việt (abook/romanization.py, docs/READING_FOREIGN_NAMES.md mục 1-3).

Ba lớp kiểm:
  - mọi dạng CÓ NGUỒN (tests/romanization_evidence.py): khớp, hoặc không khớp kèm lý do là một dòng quy ước đã [Chọn] khác nguồn;
  - từng dòng luật, bằng ca nhỏ tự dựng;
  - bộ ví dụ dùng chung với Kotlin (tests/fixtures/romanization/cases.json): bản Python phải ra đúng file, và file phải là bản sinh mới nhất.
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from abook.analysis import _valid_vietnamese_spoken_form
from abook.romanization import OPEN_CHOICES, romanized_reading, romanized_reading_flags
from tests import romanization_evidence as evidence

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "romanization" / "cases.json"


def _cases() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


def _matches(token: str, origin: str, sources: tuple[str, ...]) -> bool:
    found = romanized_reading(token, origin)
    return found is not None and found.casefold() in {source.casefold() for source in sources}


# ---- dạng có nguồn -----------------------------------------------------------------------------------------------------

def test_every_sourced_form_matches_or_is_explained_by_a_chosen_rule():
    matched, unexplained, stale = [], [], []
    for token, origin, sources, _kind in evidence.SOURCED:
        reading = romanized_reading(token, origin)
        if _matches(token, origin, sources):
            matched.append(token)
            assert token not in evidence.EXPLAINED, f"{token} khớp nhưng vẫn ghi là không khớp"
        elif token not in evidence.EXPLAINED:
            unexplained.append((token, reading, sources))
        elif evidence.EXPLAINED[token][0] != (reading or ""):
            stale.append((token, reading, evidence.EXPLAINED[token][0]))
    assert not unexplained, f"không khớp mà chưa có lý do: {unexplained}"
    assert not stale, f"cách đọc đổi mà lý do còn viết cho cách đọc cũ: {stale}"
    assert len(matched) + len(evidence.EXPLAINED) == len(evidence.SOURCED)
    # 82 / 139: 36 / 91 dạng có nguồn + 56 ca của chủ sách (04-10, sáu lần; ca của chủ sách thay dạng SGK cùng chữ: Yamato, Osaka); 64 còn lại đều do luật của
    # chủ sách, điểm đã quét hay nguồn tự lệch (EXPLAINED)
    assert len(matched) == 82


def test_tally_of_sourced_forms_by_kind():
    tally: dict[tuple[str, str], list[int]] = {}
    for token, origin, sources, kind in evidence.SOURCED:
        entry = tally.setdefault((kind, origin), [0, 0])
        entry[0] += _matches(token, origin, sources)
        entry[1] += 1
    # (khớp, tổng). Dạng "community" (Doraemon cũ) chỉ để xem, không là chuẩn.
    assert tally == {("owner", "ja"): [37, 37], ("owner", "ko"): [19, 19], ("textbook", "ja"): [20, 44], ("official", "ja"): [3, 11], ("community", "ja"): [0, 8],
                     ("official", "ko"): [3, 20]}


# ---- từng dòng luật ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("token,origin,reading", [
    # chủ sách 04-10 (đứng trên mọi nguồn): u Nhật -> u ở mọi chỗ, hậu tố nối gạch thành một chuỗi
    # lần 2: y + nguyên âm -> gi (đầu và giữa từ), ei -> ây, e Nhật -> e (ge -> ghe, ke -> ke)
    ("Yamato", "ja", "Gia-ma-tô"), ("Ayaka", "ja", "A-gia-ca"), ("Yuki", "ja", "Giu-ki"), ("Mayu", "ja", "May-u"), ("Yoshida", "ja", "Giô-si-đa"),
    ("Rei", "ja", "Rây"), ("Hajime", "ja", "Ha-gi-me"), ("Sanae", "ja", "Xa-na-e"), ("Kōbe", "ja", "Cô-be"), ("Edo", "ja", "E-đô"),
    ("Ge", "ja", "Ghe"), ("Keita", "ja", "Cây-ta"), ("Seiya", "ja", "Xây-a"),
    # ou viết ra -> âu (kyou / ryou tách i-âu; shou chou jou giữ âm vòm, có cờ analogy); ō, ô, oo vẫn -> ô
    ("Kyouko", "ja", "Ki-âu-cô"), ("Ryouma", "ja", "Ri-âu-ma"), ("Kouki", "ja", "Câu-ki"), ("Satou", "ja", "Xa-tâu"),
    ("Kyôto", "ja", "Ki-ô-tô"), ("Tooru", "ja", "Tô-ru"),
    ("Haruto-kun", "ja", "Ha-ru-tô-cun"), ("Fukushima", "ja", "Phu-cu-si-ma"), ("Suzu", "ja", "Xu-du"), ("Gugu", "ja", "Gu-gu"),
    ("Tsuru", "ja", "Xu-ru"), ("Kuro", "ja", "Cu-rô"), ("Fumio", "ja", "Phu-mi-ô"), ("Masakazu", "ja", "Ma-xa-ca-du"),
    # mục 1.2: thanh ngang; khép p / t / c / ch thì sắc (phụ âm đôi khép âm tiết trước)
    ("Sapporo", "ja", "Xáp-pô-rô"), ("Hokkaido", "ja", "Hốc-cai-đô"), ("Matcha", "ja", "Mát-cha"), ("Kenta", "ja", "Ken-ta"),
    # mục 1.4: s -> x, sh -> s
    ("Osaka", "ja", "O-xa-ca"), ("Hiroshima", "ja", "Hi-rô-si-ma"), ("Shimoda", "ja", "Si-mô-đa"),
    # mục 2: iu / u sau âm vòm, chu, tsu -> chu, ji -> gi, wa -> oa
    ("Kyuushuu", "ja", "Ki-u-su"), ("Chuubu", "ja", "Chu-bu"), ("Tsubasa", "ja", "Xu-ba-xa"),
    ("Kawasaki", "ja", "Ca-oa-xa-ki"),
    # nguyên âm dài không kéo dài; ei -> ây (chủ sách); ai giữ; n âm tiết khép
    ("Koutarou", "ja", "Câu-ta-râu"), ("Tōkyō", "ja", "Tô-ki-ô"), ("Reiji", "ja", "Rây-gi"), ("Saitama", "ja", "Xai-ta-ma"),
    ("Sendai", "ja", "Xen-đai"), ("Shinzō", "ja", "Sin-dô"),
    # c / k / g theo chính tả
    ("Kenji", "ja", "Ken-gi"), ("Ginko", "ja", "Ghin-cô"),
    # hậu tố: nối gạch vào tên thành một chuỗi (chủ sách 04-10), hậu tố giữ chữ thường
    ("Subaru-kun", "ja", "Xu-ba-ru-cun"), ("Tanaka-senpai", "ja", "Ta-na-ca-xen-pai"), ("Sato-sensei", "ja", "Xa-tô-xen-xây"),
    ("Aiko-san", "ja", "Ai-cô-xan"), ("Rin-chan", "ja", "Rin-chan"), ("Ojou-sama", "ja", "O-giâu-xa-ma"), ("Hiiragi-chan", "ja", "Hi-ra-ghi-chan"),
    ("senpai", "ja", "xen-pai"),
    # chủ sách 04-10 lần 4 (Nhật): ee -> e, ii -> i, aa -> a; g + i -> ghi, ji -> gi; tsu -> xu; yu sau phụ âm tách; shu -> su; o không phụ âm đầu -> o; ao cuối gộp
    ("Onee-san", "ja", "O-ne-xan"), ("Onii-chan", "ja", "O-ni-chan"), ("Hiiragi", "ja", "Hi-ra-ghi"), ("Ryuu", "ja", "Ri-u"), ("Kyuuji", "ja", "Ki-u-gi"),
    ("Aoi", "ja", "A-o-i"), ("Kaori", "ja", "Ca-o-ri"), ("Nao", "ja", "Nao"), ("Naoki", "ja", "Na-o-ki"), ("Okaa-san", "ja", "O-ca-xan"),
    ("Ojii-san", "ja", "O-gi-xan"), ("Onigiri", "ja", "O-ni-gi-ri"), ("Tomoe", "ja", "Tô-mô-e"), ("Matsuyama", "ja", "Ma-xu-gia-ma"),
    ("Jin-dono", "ja", "Gin-đô-nô"), ("Natsuki", "ja", "Na-xu-ki"), ("Kyūshū", "ja", "Ki-u-su"),
    # chủ sách 04-10 lần 4 (Hàn): bật hơi như thường, s -> x, j -> gi, y + nguyên âm -> gi, eo -> eo / e-o + coda, yu / yeo tách i-, wo -> uô, w đầu từ -> gu, oi
    ("Kang", "ko", "Cang"), ("Taehyun", "ko", "Te-hi-un"), ("Choi", "ko", "Choi"), ("Yoon", "ko", "Giun"), ("Hyung", "ko", "Hi-ung"), ("Seojun", "ko", "Xeo-giun"),
    ("Jeong", "ko", "Gie-ong"), ("Won", "ko", "Guôn"), ("Suwon", "ko", "Xu-guôn"), ("Busan", "ko", "Bu-xan"), ("Jin", "ko", "Gin"), ("Yuna", "ko", "Giu-na"),
    ("Kim Jong-un", "ko", "Kim Giông-un"), ("Kwon", "ko", "Quôn"),
    # chủ sách 04-10 lần 5: o sau i / u là ô, sau a / e và đầu từ là o; Maaya ca cố định; Hàn: gye -> ghi, eo + u -> e-un, Myung -> mung, b đầu từ -> b, tên nối gạch
    ("Fukuoka", "ja", "Phu-cu-ô-ca"), ("Naoki", "ja", "Na-o-ki"), ("Maaya", "ja", "May-a"), ("Ayaka", "ja", "A-gia-ca"), ("Suneo", "ja", "Xu-ne-o"),
    # lần 5 bổ sung: ya cuối từ sau nguyên âm -> y là bán âm cuối của âm tiết trước + a riêng (ya giữa / đầu từ vẫn gia); Hàn: yu sau phụ âm i-u, yeo sau phụ âm mất y
    ("Maya", "ja", "May-a"), ("Kaya", "ja", "Cay-a"), ("Kyung", "ko", "Ki-ung"), ("Byung", "ko", "Bi-ung"), ("Gyeong", "ko", "Ghe-ong"), ("Pyeong", "ko", "Pe-ong"),
    ("Cheonggyecheon", "ko", "Che-ong-ghi-che-on"), ("Park", "ko", "Pắc"), ("Bak", "ko", "Bắc"), ("Taehyung", "ko", "Te-hi-ung"), ("Geun-hye", "ko", "Cưn-hê"),
    # tiếng Hàn: g / d / b đầu từ vô thanh, giữa hai âm hữu thanh thì hữu thanh; k t p cuối -> c t p + sắc; l cuối -> n
    ("Geun", "ko", "Cưn"), ("Dae", "ko", "Te"), ("Changdeok", "ko", "Chang-đe-óc"), ("Park", "ko", "Pắc"), ("Seoul", "ko", "Xe-un"),
    ("Hanbit", "ko", "Han-bít"), ("Hallasan", "ko", "Han-la-xan"), ("Jeju", "ko", "Giê-giu"), ("Daegu", "ko", "Te-gu"),
    # tên người Hàn: mỗi âm tiết RR một bộ phận cách nhau dấu cách khi viết nối gạch
    ("Park Geun-hye", "ko", "Pắc Cưn-hê"), ("Kim Dae-jung", "ko", "Kim Te-giung"), ("Lee Myung-bak", "ko", "Li Mung-bắc"),
])
def test_reading_follows_the_convention(token, origin, reading):
    assert romanized_reading(token, origin) == reading


@pytest.mark.parametrize("token,origin", [
    ("Cale", "ja"), ("Lily", "ja"), ("Ah", "ja"), ("IZUMO", "ja"), ("iPhone", "ja"), ("Ko1", "ja"), ("Tuka", "ja"), ("Kaz", "ja"), ("", "ja"),
    ("Ka-", "ja"), ("Cale", "ko"), ("Hmm", "ko"), ("PARK", "ko"),
    ("Hajime", None), ("Seoul", None),                # không biết gốc thì không đoán
    ("Yongin", "ko"), ("Hangang", "ko"), ("Jiwoo", "ko"),  # yong-in / yon-gin không phân được; Jiwoo không là RR
])
def test_unsure_is_none(token, origin):
    assert romanized_reading(token, origin) is None


def test_ou_before_a_palatal_is_flagged_as_an_analogy():
    assert romanized_reading_flags("Shouta", "ja") == ("Sâu-ta", ("analogy:ou_vom",))
    assert romanized_reading_flags("Chouji", "ja") == ("Châu-gi", ("analogy:ou_vom",))
    assert romanized_reading_flags("Jouji", "ja") == ("Giâu-gi", ("analogy:ou_vom",))
    assert romanized_reading_flags("Kyouko", "ja") == ("Ki-âu-cô", ())  # kyou / ryou do chính chủ sách chốt


def test_open_choices_are_flagged_not_silent():
    # ya Nhật đã chốt gi (chủ sách, không cờ); yo / yu theo ya có cờ analogy; kyo đã có nguồn (Ki-ô-tô): không mở
    assert romanized_reading_flags("Yamato", "ja") == ("Gia-ma-tô", ())
    assert romanized_reading_flags("Yokohama", "ja") == ("Giô-cô-ha-ma", ("analogy:y_gi",))
    assert romanized_reading_flags("Yuki", "ja") == ("Giu-ki", ("analogy:y_gi",))
    assert romanized_reading_flags("Kyoko", "ja") == ("Ki-ô-cô", ())
    # k bật hơi và wo của Hàn đã chốt (không cờ); oe / wi / ui / we / wae còn mở
    assert romanized_reading_flags("Taehyung", "ko")[1] == ()
    assert romanized_reading_flags("Kwon", "ko")[1] == ()
    assert romanized_reading_flags("Suwon", "ko")[1] == ("analogy:ko_w_gu",)
    assert romanized_reading_flags("Hoe", "ko")[1] == ("open:ko_rare_vowels",)
    assert romanized_reading_flags("Naoki", "ja")[1] == ("analogy:ao_split",)
    assert romanized_reading_flags("Seiya", "ja")[1] == ()
    assert romanized_reading_flags("Mayu", "ja")[1] == ("analogy:y_final",)
    assert romanized_reading_flags("Kouya", "ja")[1] == ("open:y_after_vowel_pair",)
    assert romanized_reading_flags("Gyeong", "ko")[1] == ("analogy:ko_yeo",)
    assert romanized_reading_flags("Seoul", "ko")[1] == ("analogy:ko_eo_u",)
    assert set(OPEN_CHOICES) == {"ko_rare_vowels", "y_after_vowel_pair"}


def test_a_reading_is_the_same_whatever_the_capitalisation_of_the_input():
    assert romanized_reading("osaka", "ja") == "o-xa-ca"
    assert romanized_reading("Osaka", "ja") == "O-xa-ca"
    assert romanized_reading("OSAKA", "ja") is None  # toàn hoa là chữ viết tắt, việc của luật khác


# ---- bộ ví dụ dùng chung với Kotlin ------------------------------------------------------------------------------------

def test_the_shared_fixture_is_what_the_python_rule_says():
    cases = _cases()
    assert len(cases) > 300
    wrong = []
    for case in cases:
        found = romanized_reading_flags(case["token"], case["origin"])
        reading = None if found is None else found[0]
        flags = [] if found is None else list(found[1])
        if (reading, flags) != (case["reading"], case["flags"]):
            wrong.append((case["token"], case["origin"], reading, flags, case["reading"], case["flags"]))
    assert not wrong, wrong[:10]


def test_the_shared_fixture_is_the_latest_generated_one():
    spec = importlib.util.spec_from_file_location("build_romanization_fixture", ROOT / "scripts" / "build_romanization_fixture.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert FIXTURE.read_bytes() == module.cases_bytes(), "chạy lại scripts/build_romanization_fixture.py"
    assert b"\r" not in FIXTURE.read_bytes()


def test_every_syllable_of_every_reading_is_a_valid_vietnamese_syllable():
    checked = 0
    for case in _cases():
        if case["reading"] is None:
            continue
        for syllable in re.split(r"[ -]", case["reading"]):
            assert _valid_vietnamese_spoken_form("", syllable), (case["token"], case["reading"], syllable)
            checked += 1
    assert checked > 800
