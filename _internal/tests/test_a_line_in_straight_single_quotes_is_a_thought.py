"""Cả dòng bọc trong cặp ' thẳng là nội tâm, như ‘…’.

Model 06-10: một câu tự nhủ 'Chà, ...' bị bộ tách đoạn khoá là lời kể; trước 93733295 nó "đúng" chỉ vì dấu ‘ của câu
trước không đóng được và tràn nội tâm xuống mọi câu kể. Kho có 8.554 dòng dạng này ở 70 bộ. Văn bản là câu tự viết.
"""
from __future__ import annotations

from abook.text_processing import segment_chapter_text


def kinds(text: str) -> list[tuple[str, str]]:
    return [(str(row["kind_hint"]), str(row["text"])) for row in segment_chapter_text(1, text)]


def test_a_whole_line_in_straight_single_quotes_is_a_thought() -> None:
    thought = "'Thôi được, chắc mình phải luyện kiếm thêm vài tháng nữa.'"
    assert kinds(f"Bảng chỉ số chẳng nhích lên chút nào.\n\n{thought}\n\nTôi cất tấm thẻ vào túi.") == [
        ("narration", "Bảng chỉ số chẳng nhích lên chút nào."),
        ("thought", thought),
        ("narration", "Tôi cất tấm thẻ vào túi."),
    ]


def test_an_apostrophe_inside_the_thought_does_not_break_it() -> None:
    thought = "'Lại là cái tên Ma'ren ấy à.'"
    assert kinds(thought) == [("thought", thought)]


def test_a_curly_thought_closed_by_a_straight_quote_does_not_spill_into_the_next_lines() -> None:
    text = "‘Đúng là một cơ thể vô dụng.'\n\nNgười khác lên cấp nhanh gấp đôi.\n\n'Vậy thì cứ chăm chỉ thôi.'"
    assert kinds(text) == [
        ("thought", "‘Đúng là một cơ thể vô dụng.'"),
        ("narration", "Người khác lên cấp nhanh gấp đôi."),
        ("thought", "'Vậy thì cứ chăm chỉ thôi.'"),
    ]


def test_a_thought_broken_by_narration_is_not_one_whole_thought() -> None:
    line = "'Mưa à? Hừm,' tôi lẩm bẩm. 'Chắc đường lên núi trơn lắm.'"
    assert kinds(line) != [("thought", line)]


def test_a_straight_quote_mid_line_is_not_a_thought() -> None:
    line = "'Kẻ lang thang' là biệt danh cả làng đặt cho lão."
    assert kinds(line) == [("narration", line)]
