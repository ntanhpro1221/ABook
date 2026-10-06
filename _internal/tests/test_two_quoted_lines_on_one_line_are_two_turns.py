"""Hai câu trong ngoặc liền nhau trên một dòng là hai lượt thoại; liệt kê hay dẫn lời bằng dấu phẩy, hai chấm thì vẫn một.

Hai thầy gán nhãn 06-10: một dòng nguồn chứa câu của người này rồi câu đáp của người kia ("...nữa." "Cô chắc chứ?") bị gộp
thành một đoạn, câu đáp đọc bằng giọng người nói trước. Văn bản là câu tự viết cùng cấu trúc.
"""
from __future__ import annotations

from abook.text_processing import segment_chapter_text


def pieces(text: str) -> list[tuple[str, str]]:
    return [(str(row["kind_hint"]), str(row["text"])) for row in segment_chapter_text(1, text)]


def test_two_straight_quoted_lines_side_by_side_are_two_turns() -> None:
    assert pieces('"Ta đi đây, ngươi khỏi lo nữa." "Cô chắc chứ?"') == [
        ("dialogue", '"Ta đi đây, ngươi khỏi lo nữa."'),
        ("dialogue", '"Cô chắc chứ?"'),
    ]


def test_two_curly_quoted_lines_with_a_full_stop_between_are_two_turns() -> None:
    assert pieces("“Cảm ơn nhé, Tom.”. “Chuyện nhỏ thôi, thưa ngài.”") == [
        ("dialogue", "“Cảm ơn nhé, Tom.”."),
        ("dialogue", "“Chuyện nhỏ thôi, thưa ngài.”"),
    ]


def test_quoted_lines_listed_with_commas_stay_one_segment() -> None:
    line = "“Sao lại thế?”, “Ai cho phép?”, “Đi đâu vậy?”"
    assert pieces(line) == [("dialogue", line)]


def test_a_quoted_term_leading_into_speech_with_a_colon_stays_one_segment() -> None:
    line = "“Bình tĩnh nào!”: “Ta muốn nghĩ bao lâu thì nghĩ bấy lâu.”"
    assert pieces(line) == [("dialogue", line)]
