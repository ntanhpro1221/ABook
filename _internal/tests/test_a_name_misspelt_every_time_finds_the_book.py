"""Tên người nói viết sai MỌI lần ("GAST" cho Glast) trỏ về tên riêng của sách, không thành một nhân vật lạ giọng riêng.

LoRA v5 (29-09) không viết đúng "Glast" lần nào trong HDST 062 - 21 câu của người thầy thành nhân vật "GAST", và
`fold_to_source_spelling` không có nhãn đúng nào để gom về. `snap_to_source_names` tìm trong chính văn bản sách.
"""
from __future__ import annotations

from abook.character_registry import (
    canonical_speaker_names,
    fold_for_source_search,
    snap_to_source_names,
)

BOOK = (
    "Đêm muộn, Giáo sư Glast ngồi tựa gốc cây. Tôi nhìn Glast rất lâu. Yennica hỏi Glast một câu.\n"
    "Rồi Krai Andrey bước vào, và Krai Andrey cười. Ai cũng biết Krai Andrey. Lúc ấy Lương Tử nói với Lương Tử.\n"
    "Gạt nước mắt đi. Gạt đi. Gạt hết đi.\n"
)


def snap(names: list[str], book: str = BOOK) -> dict[str, str]:
    return snap_to_source_names(names, book, fold_for_source_search(book))


def test_a_name_misspelt_every_time_takes_the_book_name() -> None:
    assert snap(["GAST"]) == {"GAST": "GLAST"}
    assert snap(["Gast"]) == {"Gast": "Glast"}


def test_one_wrong_word_of_a_full_name_is_replaced_when_the_book_has_the_whole_name() -> None:
    assert snap(["Krai Andrei"]) == {"Krai Andrei": "Krai Andrey"}
    assert snap(["KRAI ANDREI"]) == {"KRAI ANDREI": "KRAI ANDREY"}
    # "Andrey" có trong sách nhưng "Zed Andrey" thì không: không bịa ra một người sách không có
    assert snap(["Zed Andrei"]) == {}


def test_names_the_book_has_are_left_alone() -> None:
    assert snap(["GLAST", "Yennica", "KRAI ANDREY"]) == {}


def test_vietnamese_names_are_never_snapped() -> None:
    # lệch một ký tự ở tên Việt / Hán Việt đã là họ khác
    assert snap(["TƯƠNG TỬ"]) == {}


def test_two_candidates_are_not_guessed() -> None:
    book = BOOK + "Rồi Gleast đến. Gặp Gleast lần nữa, và Gleast đi.\n"
    assert snap(["GAST"], book) == {"GAST": "GLAST"}  # "Gleast" cách GAST hai ký tự: vẫn một đích
    assert snap(["GLEST"], book) == {}  # cách một ký tự với cả "Glast" lẫn "Gleast"


def test_capitals_that_only_open_sentences_are_not_names() -> None:
    # "Trong" viết hoa ba lần nhưng lần nào cũng đầu câu - là giới từ, không phải tên
    book = "Trong phòng tối. Trong nhà sáng. Trong vườn im.\n"
    assert snap(["TRONGS"], book) == {}
    assert snap(["TRONGS"], book + "Hắn gặp Trong ở chợ, rồi gọi Trong, rồi chờ Trong.\n") == {"TRONGS": "TRONG"}
    # viết hoa giữa câu mà chưa đủ ba lần thì chưa chắc là tên
    assert snap(["TRONGS"], book + "Hắn gặp Trong ở chợ.\n") == {}


def test_nothing_without_the_book() -> None:
    assert snap_to_source_names(["GAST"], "", "") == {}


def test_the_naming_passes_read_the_teacher_in_his_own_voice() -> None:
    names = canonical_speaker_names({"GAST": 21, "ED ROSTAILER": 30, "YENNICA": 5}, BOOK)
    assert names["GAST"] == "GLAST"
    assert names["YENNICA"] == "YENNICA"
