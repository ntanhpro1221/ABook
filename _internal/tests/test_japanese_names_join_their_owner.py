"""LN Nhật: tên viết HỌ TRƯỚC ("Onizuki Hina") và kính ngữ đứng SAU tên ("Hina-sama") - một người, một giọng.

Bản dịch Việt của light novel Nhật giữ thứ tự tên Nhật, nên như tên Việt, chữ CUỐI là tên gọi: model ghi "HINA" ở câu này,
"ONIZUKI HINA" ở câu kia, và trước luật này Hina có hai giọng (luật tên gọi chỉ mở cho tên Việt/Hán Việt, vì tên Âu thì chữ
cuối là họ chung của cả nhà). Bộ đo LN 28-09 (docs/ANALYSIS_RESEARCH.md): chủ sách đọc LN Nhật/Hàn.
"""
from __future__ import annotations

from abook.character_registry import (
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


def test_a_title_before_the_name_is_not_a_second_person() -> None:
    counts = {"GIÁO SƯ GLAST": 10, "Glast": 4, "CÔNG CHÚA MURINA": 2, "MURINA": 3, "TIỂU THƯ HINA": 1, "ED": 20}
    mapping = canonical_speaker_names(counts, "")
    assert mapping["GIÁO SƯ GLAST"] == mapping["Glast"]
    assert mapping["CÔNG CHÚA MURINA"] == mapping["MURINA"] == "MURINA"
    assert mapping["TIỂU THƯ HINA"] == "TIỂU THƯ HINA", "không có nhãn HINA trơn nào để gom về - giữ nguyên"


def test_an_english_title_the_model_wrote_is_not_a_second_person() -> None:
    """01-10: sách viết "giáo sư Glast", LoRA v8 gán "Professor Glast" - dịch chức danh khi viết nhãn."""
    counts = {"Professor Glast": 34, "Glast": 4, "Lady Lucia": 2, "LUCIA": 9, "Sir Lancelot": 1, "Master": 3, "ED": 20}
    mapping = canonical_speaker_names(counts, "")
    assert mapping["Professor Glast"] == mapping["Glast"]
    assert mapping["Lady Lucia"] == mapping["LUCIA"]
    assert mapping["Sir Lancelot"] == "Sir Lancelot", "không có nhãn Lancelot trơn nào để gom về - giữ nguyên"
    assert mapping["Master"] == "Master", "chỉ có chức danh thì không có tên để gom"


BOTH_ORDERS = "\n".join([
    "Yakishio Remon chạy tới.", "Cậu nhìn Yakishio Remon.", "Yakishio Remon cười.", "Remon Yakishio, cô ấy là vậy.", "Gọi là Remon Yakishio.",
    "Kasagi Shizuka gật đầu.", "Kasagi Shizuka mỉm cười.",
])


def test_a_book_writing_one_name_in_both_orders_is_still_one_person() -> None:
    """08-10, Make Heroine 017a: sách viết cả "Yakishio Remon" lẫn "Remon Yakishio" - trước đây là hai tên đủ, "REMON" và
    "YAKISHIO" mỗi nhãn khớp hai "người" nên không gom, và cô có hai giọng (B9: 21 câu)."""
    mapping = canonical_speaker_names({"Remon": 32, "Yakishio": 26, "Shizuka Kasagi": 4, "SHIZUKA": 20}, BOTH_ORDERS)
    assert mapping["Remon"] == mapping["Yakishio"] == "YAKISHIO REMON"
    assert mapping["Shizuka Kasagi"] == mapping["SHIZUKA"] == "KASAGI SHIZUKA", "nhãn đảo thứ tự tên đủ của sách"


def test_a_reversed_label_joins_the_name_the_model_already_wrote() -> None:
    mapping = canonical_speaker_names({"Remon Yakishio": 3, "Yakishio Remon": 9, "Yurika Kasagi": 2}, BOTH_ORDERS)
    assert mapping["Remon Yakishio"] == "Yakishio Remon"
    assert mapping["Yurika Kasagi"] == "Yurika Kasagi", "sách không viết tên đủ ấy ở thứ tự nào - giữ nguyên"


TITLES = "\n".join([
    "Tướng quân Niên Phi bước vào.", "Thầy Vương lên tiếng.", "Chị Dậu ngồi xuống.", "Tiểu thư Bạch Dạ cười.",
])


def test_a_vietnamese_title_before_a_name_the_book_writes_joins_that_name() -> None:
    counts = {"TƯỚNG QUÂN NIÊN PHI": 4, "NIÊN PHI": 6, "Tiểu thư Bạch Dạ": 2, "Bạch Dạ": 5, "Thầy Vương": 3, "Vương": 2,
              "CHỊ DẬU": 8, "DẬU": 3, "Hoàng tử Vân Phi": 2, "Vân Phi": 4, "Bác sĩ Lee": 2, "Lee": 3}
    mapping = canonical_speaker_names(counts, TITLES)
    assert mapping["TƯỚNG QUÂN NIÊN PHI"] == mapping["NIÊN PHI"]
    assert mapping["Tiểu thư Bạch Dạ"] == mapping["Bạch Dạ"]
    assert mapping["Bác sĩ Lee"] == mapping["Lee"], "\"bác sĩ\" là chức danh, không phải \"bác\" + \"sĩ Lee\""
    assert mapping["Thầy Vương"] == "Thầy Vương", "một âm tiết sau chức danh có thể chỉ là họ"
    assert mapping["CHỊ DẬU"] == "CHỊ DẬU" and mapping["DẬU"] == "DẬU", "chị Dậu là vợ anh Dậu"
    assert mapping["Hoàng tử Vân Phi"] == "Hoàng tử Vân Phi", "sách không viết \"hoàng tử Vân Phi\" - không có bằng chứng"
    assert canonical_speaker_names({"TƯỚNG QUÂN NIÊN PHI": 4, "NIÊN PHI": 6}, "")["TƯỚNG QUÂN NIÊN PHI"] \
        == "TƯỚNG QUÂN NIÊN PHI", "không có nguồn thì luật tên có dấu tắt"
