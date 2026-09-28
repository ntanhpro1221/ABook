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
