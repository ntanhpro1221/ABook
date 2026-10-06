"""Dòng mở bằng gạch ở chương viết thoại trong ngoặc kép: lời kể thì là lời kể, lời nói thì vẫn là thoại.

Hai thầy gán nhãn a2w4 (06-10) cùng trả lời "lời kể" cho một dòng "-Hoặc không, vì hắn đã nhảy tránh..." mà bộ tách đoạn
khoá thoại chỉ vì dấu gạch đầu dòng; đáp án gold cũng ghi lời kể cho những dòng như thế (evil_lord 02:57). Chương viết
thoại bằng gạch (Tắt đèn, Tam quốc) và dòng gạch có dấu hiệu lời nói thì giữ nguyên. Văn bản dưới đây là câu tự viết.
"""
from __future__ import annotations

from abook.text_processing import segment_chapter_text

QUOTED_TALK = [
    "“Anh đến muộn rồi đấy.”",
    "“Xin lỗi, đường đông quá.”",
    "“Lần sau nhớ đi sớm hơn.”",
    "“Ừ, anh biết rồi.”",
    "“Thôi, vào đi kẻo lạnh.”",
    "“Trong nhà có ai không?”",
    "“Chỉ có mẹ em thôi.”",
    "“Vậy anh chào bác một câu.”",
    "“Bác đang ngủ, để mai hẵng chào.”",
    "“Được, mai anh qua.”",
]


def hint_of(line: str, talk: list[str] = QUOTED_TALK) -> str:
    text = "\n\n".join(["Trời đã tối hẳn khi Minh tới cổng.", *talk[:5], line, *talk[5:]])
    rows = segment_chapter_text(1, text)
    return next(str(row["kind_hint"]) for row in rows if str(row["text"]) == line)


def test_a_dash_led_aside_in_the_narration_is_narration() -> None:
    assert hint_of("-Hoặc không, vì hắn đã nhảy lùi lại tránh nhát chém.") == "narration"
    assert hint_of("— Lan đã đứng chờ sẵn ở cổng làng.") == "narration"


def test_a_dash_led_line_continuing_the_sentence_is_narration() -> None:
    assert hint_of("-bởi vì cả làng không còn ai ở lại.") == "narration"


def test_a_dash_led_line_that_speaks_stays_dialogue() -> None:
    assert hint_of("- Ngươi định đi đâu giờ này?") == "dialogue"
    assert hint_of("- Ta sẽ chờ ở đây đến sáng.") == "dialogue"
    assert hint_of("- Tôi đã nói với cậu rồi.") == "dialogue"
    assert hint_of("- Đợi đã.") == "dialogue"
    assert hint_of("-Rầm!") == "dialogue"
    assert hint_of("- Hắn đã đi thật rồi.") == "dialogue"


def test_a_chapter_that_writes_its_dialogue_with_dashes_keeps_every_dash_turn() -> None:
    dash_talk = [f"- Câu thứ {number} của cuộc nói chuyện." for number in range(1, 11)]
    assert hint_of("-Hoặc không, vì hắn đã nhảy lùi lại tránh nhát chém.", dash_talk) == "dialogue"


def test_a_chapter_with_several_dash_lines_keeps_them_dialogue() -> None:
    talk = QUOTED_TALK[:5] + ["- Một.", "- Hai.", "- Ba."] + QUOTED_TALK[5:]
    assert hint_of("-Hoặc không, vì hắn đã nhảy lùi lại tránh nhát chém.", talk) == "dialogue"


def test_too_few_quoted_lines_to_know_the_chapter_keeps_the_dash_turn() -> None:
    assert hint_of("-Hoặc không, vì hắn đã nhảy lùi lại tránh nhát chém.", QUOTED_TALK[:4]) == "dialogue"
