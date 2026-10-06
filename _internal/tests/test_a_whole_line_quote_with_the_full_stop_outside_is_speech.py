"""Cả dòng là câu trong ngoặc, dấu chấm đặt NGOÀI ngoặc (“...”.): vẫn là câu nói, không phải lời kể.

Hai thầy gán nhãn 06-10: một lời nói dài cả đoạn, kết thúc bằng ”. ngay sau lời dẫn "X nhìn Y một lúc rồi nói." bị bộ tách
đoạn khoá là lời kể - câu ấy sẽ đọc bằng giọng người kể. Văn bản là câu tự viết cùng cấu trúc.
"""
from __future__ import annotations

from abook.text_processing import segment_chapter_text


def kinds(text: str) -> list[tuple[str, str]]:
    return [(str(row["kind_hint"]), str(row["text"])) for row in segment_chapter_text(1, text)]


def test_a_whole_line_quote_with_the_full_stop_outside_is_dialogue() -> None:
    speech = "“Nói thật nhé, cậu còn trẻ lắm, ta cho cậu một cơ hội cuối, đưa túi tiền đây rồi đi đi”."
    assert kinds(f"Borak nhìn Kael một lúc rồi nói.\n\n{speech}") == [
        ("narration", "Borak nhìn Kael một lúc rồi nói."),
        ("dialogue", speech),
    ]


def test_a_whole_line_quote_with_the_full_stop_inside_is_still_dialogue() -> None:
    assert kinds("“Đi thôi, trời sắp tối rồi.”") == [("dialogue", "“Đi thôi, trời sắp tối rồi.”")]


def test_a_quoted_word_the_narrator_questions_stays_narration() -> None:
    # Dấu hỏi ngoài ngoặc: người kể ngẫm lại một chữ, không phải ai nói câu ấy.
    assert kinds("“Cơ hội vàng”?") == [("narration", "“Cơ hội vàng”?")]


def test_a_quote_inside_a_narration_sentence_stays_narration() -> None:
    line = "Cả làng gọi đó là “mùa gặt đỏ”."
    assert kinds(line) == [("narration", line)]
