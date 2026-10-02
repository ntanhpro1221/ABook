"""Tên người nói viết không như sách ("HOANG CAI", "KHỐNG MINH") hiện trong danh sách nhân vật theo chữ của sách.

Model 4B tinh chỉnh rơi dấu cả chương, hay đặt sai dấu, với tên chưa gặp (Tam quốc Hồi 50-52, 27-09). Giọng không sai
vì thế; sai là chữ chủ sách đọc trong Studio - nên lượt này chỉ đổi chữ hiển thị, và chỉ khi sách không để chỗ nào phải
đoán.
"""
from __future__ import annotations

from abook.character_registry import canonical_speaker_names, restore_source_marks

BOOK = (
    "Rồi Hoàng Cái nói với Chu Du. Du cười. Rồi Huyền-đức hỏi Hoàng Cái về Đông Ngô, và Khổng Minh im lặng.\n"
    "Mình đi đâu? Ông Minh gật đầu. Rồi Vân và Văn cùng tới. Rồi Tháo thao thao bất tuyệt.\n"
)


def test_a_name_without_marks_takes_the_one_spelling_of_the_book() -> None:
    assert restore_source_marks(["HOANG CAI", "HUYEN-DUC", "DONG NGO"], BOOK) == {
        "HOANG CAI": "HOÀNG CÁI", "HUYEN-DUC": "HUYỀN-ĐỨC", "DONG NGO": "ĐÔNG NGÔ"}


def test_a_name_with_wrong_marks_takes_the_book_spelling() -> None:
    assert restore_source_marks(["KHỐNG MINH"], BOOK) == {"KHỐNG MINH": "KHỔNG MINH"}


def test_a_label_in_mixed_case_takes_the_book_exactly() -> None:
    assert restore_source_marks(["Hoang Cai"], BOOK) == {"Hoang Cai": "Hoàng Cái"}


def test_a_name_the_book_writes_that_way_stays() -> None:
    # "Minh" là tên không dấu; "Mình" đầu câu là đại từ - không được biến MINH thành MÌNH
    assert restore_source_marks(["MINH", "DU", "CHU DU", "HOÀNG CÁI"], BOOK) == {}


def test_two_spellings_are_not_guessed() -> None:
    assert restore_source_marks(["VAN"], BOOK) == {}


def test_only_words_written_as_names_count() -> None:
    # "thao thao" viết thường không phải tên; "Tháo" viết hoa giữa câu là tên
    assert restore_source_marks(["THAO"], BOOK) == {"THAO": "THÁO"}
    # chữ hoa đầu câu không nói gì về tên một chữ: "Văn chương" không biến VAN thành VĂN
    assert restore_source_marks(["VAN"], "Văn chương của hắn hay. Văn nói gì?") == {}
    assert restore_source_marks(["HOANG CAI"], "") == {}


def test_the_naming_passes_show_the_book_spelling() -> None:
    names = canonical_speaker_names({"HOANG CAI": 9, "CHU DU": 4, "DU": 12}, BOOK)
    assert names == {"HOANG CAI": "HOÀNG CÁI", "CHU DU": "CHU DU", "DU": "CHU DU"}
