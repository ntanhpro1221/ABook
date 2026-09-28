"""LN Nhật: tên viết HỌ TRƯỚC ("Onizuki Hina") và kính ngữ đứng SAU tên ("Hina-sama") - một người, một giọng.

Bản dịch Việt của light novel Nhật giữ thứ tự tên Nhật, nên như tên Việt, chữ CUỐI là tên gọi: model ghi "HINA" ở câu này,
"ONIZUKI HINA" ở câu kia, và trước luật này Hina có hai giọng (luật tên gọi chỉ mở cho tên Việt/Hán Việt, vì tên Âu thì chữ
cuối là họ chung của cả nhà). Bộ đo LN 28-09 (docs/ANALYSIS_RESEARCH.md): chủ sách đọc LN Nhật/Hàn.
"""
from __future__ import annotations

from ebook_reader.character_registry import (
    canonical_speaker_names,
    merge_given_names,
    strip_japanese_honorific,
)


def reps(*names: str) -> dict[str, str]:
    return {name.casefold(): name for name in names}


def test_a_japanese_given_name_joins_the_family_first_full_name() -> None:
    assert merge_given_names(reps("HINA", "ONIZUKI HINA", "YOSHIHITO", "KUCHINASHI YOSHIHITO")) == {
        "hina": "ONIZUKI HINA", "yoshihito": "KUCHINASHI YOSHIHITO"}


def test_siblings_keep_their_own_given_names_and_the_family_name_alone_is_not_guessed() -> None:
    merged = merge_given_names(reps("AOI", "ONIZUKI AOI", "HINA", "ONIZUKI HINA", "ONIZUKI"))
    assert merged == {"aoi": "ONIZUKI AOI", "hina": "ONIZUKI HINA"}


def test_european_and_korean_names_stay_apart() -> None:
    # chữ cuối tên Âu là họ; tên Hàn không phải chuỗi âm tiết romaji
    assert merge_given_names(reps("GREY", "JANE GREY", "EVANS", "LUCIEN EVANS", "DOKJA", "KIM DOKJA")) == {}


def test_a_japanese_honorific_after_the_name_is_not_a_second_person() -> None:
    assert strip_japanese_honorific("HINA-SAMA") == "HINA"
    assert strip_japanese_honorific("Kazuma-san") == "Kazuma"
    assert strip_japanese_honorific("KAORU SENSEI") == "KAORU"
    assert strip_japanese_honorific("SENSEI") == "SENSEI", "chỉ có kính ngữ thì không có tên để giữ"
    assert strip_japanese_honorific("SUSAN") == "SUSAN", "kính ngữ phải tách bằng gạch nối hay dấu cách"


def test_the_pipeline_reads_all_three_forms_as_one_voice() -> None:
    counts = {"HINA": 6, "HINA-SAMA": 2, "ONIZUKI HINA": 3, "TOMOBE": 9}
    mapping = canonical_speaker_names(counts, "")
    assert {mapping["HINA"], mapping["HINA-SAMA"], mapping["ONIZUKI HINA"]} == {"ONIZUKI HINA"}
    assert mapping["TOMOBE"] == "TOMOBE"


BOOK = "\n".join([
    "Kuchinashi Yoshihito thở dài.", "Kuromitsu Kirako cười.", "Cậu là Kuchinashi Yoshihito mà.",
    "Onizuki Hina bước vào.", "Onizuki Aoi gật đầu.", "Onizuki Hina mỉm cười.", "Onizuki Aoi đi ra.",
    "Kuromitsu Kirako lại cười.", "Jane Grey lên tiếng.", "Jane Grey im lặng.",
])


def test_a_family_name_or_given_name_label_joins_the_full_name_the_book_writes() -> None:
    counts = {"Kuchinashi": 8, "Yoshihito": 12, "KIRAKO": 5, "HINA": 4, "AOI": 3, "ONIZUKI": 2, "GREY": 6}
    mapping = canonical_speaker_names(counts, BOOK)
    assert mapping["Kuchinashi"] == mapping["Yoshihito"] == "KUCHINASHI YOSHIHITO", "họ và tên gọi là một người"
    assert mapping["KIRAKO"] == "KUROMITSU KIRAKO"
    assert mapping["HINA"] == "ONIZUKI HINA" and mapping["AOI"] == "ONIZUKI AOI"
    assert mapping["ONIZUKI"] == "ONIZUKI", "họ chung của hai người trong sách - không đoán"
    assert mapping["GREY"] == "GREY", "tên Âu: chữ cuối là họ, không nối"


def test_a_pair_seen_once_is_not_a_name() -> None:
    mapping = canonical_speaker_names({"HINA": 3}, "Onizuki Hina bước vào.")
    assert mapping["HINA"] == "HINA"
