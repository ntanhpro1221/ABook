"""Ngoặc mở mà thiếu dấu đóng không được khoá các câu kể phía sau thành thoại / nội tâm.

Hai thầy gán nhãn 30 chương qua chính đường phân tích của app (05-10) cùng trả lời "lời kể" cho những đoạn mà bộ tách đoạn
đã khoá là nội tâm hay thoại: ‘…' đóng bằng dấu ' thẳng, “… thiếu ”, "… thiếu ". Ngoặc trôi tới tận dấu đóng của câu
thoại KẾ TIẾP, và mọi câu kể ở giữa đọc bằng giọng nhân vật. Văn bản dưới đây là câu tự viết cùng cấu trúc.
"""
from __future__ import annotations

from abook.text_processing import segment_chapter_text


def kinds(text: str, warnings: list[str] | None = None) -> list[str]:
    return [str(row["kind_hint"]) for row in segment_chapter_text(1, text, warnings=warnings)]


def test_a_straight_apostrophe_closes_a_curly_thought() -> None:
    text = (
        "Cuộc họp ấy được gọi là ‘bàn chuyện mùa đông'.\n\n"
        "Tôi gọi một ly trà rồi đi lên lầu.\n\n"
        "Quán đông kín chỗ.\n\n"
        "“Ơ, anh cũng đến à?”"
    )

    assert kinds(text) == ["narration", "thought", "narration", "narration", "dialogue"]


def test_an_apostrophe_inside_a_word_does_not_close_the_thought() -> None:
    rows = segment_chapter_text(1, "‘Hôm nay gặp Ma'at, cô ấy bảo I'm fine.’\n\nTôi về nhà.")

    assert [(row["kind_hint"], row["text"]) for row in rows] == [
        ("thought", "‘Hôm nay gặp Ma'at, cô ấy bảo I'm fine.’"),
        ("narration", "Tôi về nhà."),
    ]


def test_narration_between_an_unclosed_line_and_the_next_line_stays_narration() -> None:
    warnings: list[str] = []
    text = (
        "“Đừng nói thế trước mặt cậu ấy.\n\n"
        "Lan cản lại, nhưng mặt vẫn cười cười.\n\n"
        "“Ừ, xin lỗi nhé.”"
    )

    assert kinds(text, warnings) == ["dialogue", "narration", "dialogue"]
    assert len(warnings) == 1 and "paragraph 1" in warnings[0]


def test_a_quote_opened_mid_paragraph_shows_the_earlier_one_never_ran_on() -> None:
    text = (
        "“Đến đúng lúc lắm đấy!\n\n"
        "Nhìn Minh vừa lắc đầu “chậc chậc”, Hoa lay vai cô bạn thật mạnh.\n\n"
        "“Thôi nào, bình tĩnh đi.”"
    )

    assert kinds(text) == ["dialogue", "narration", "dialogue"]


def test_an_unclosed_straight_quote_does_not_swallow_narration() -> None:
    # Trước đây dấu " đầu dòng cuối bị coi là dấu ĐÓNG: hai câu kể thành thoại, câu thoại thật thành lời kể.
    text = (
        '"Tôi biết anh sẽ đến một mình.\n\n'
        "Quao, cậu ta quyết tâm thật đấy.\n\n"
        "Tôi định nói vậy nhưng thôi.\n\n"
        '"Tôi hiểu rồi.”'
    )

    assert kinds(text) == ["dialogue", "narration", "narration", "dialogue"]


def test_a_thought_word_ending_a_narration_line_does_not_close_an_open_quote() -> None:
    rows = segment_chapter_text(
        1,
        "“Ngài không nên tự mình ra tay.\n\n"
        "Thế là Minh bước ra can. Cô gái vẫn thì thầm, ‘ba’\n\n"
        "Tôi không hiểu cô ấy định làm gì.\n\n"
        "“Đi thôi.”",
    )

    by_text = {str(row["text"]): str(row["kind_hint"]) for row in rows}
    assert by_text["Thế là Minh bước ra can. Cô gái vẫn thì thầm,"] == "narration"
    assert by_text["‘ba’"] == "thought"
    assert by_text["Tôi không hiểu cô ấy định làm gì."] == "narration"
    assert by_text["“Đi thôi.”"] == "dialogue"


def test_a_speech_that_reopens_every_paragraph_is_still_one_speech() -> None:
    warnings: list[str] = []
    text = (
        "“Nghe này, ta chỉ nói một lần.\n\n"
        "“Sáng mai cả đoàn lên đường.\n\n"
        "“Ai đến muộn thì ở lại.”\n\n"
        "Cả phòng im lặng."
    )

    assert kinds(text, warnings) == ["dialogue", "dialogue", "dialogue", "narration"]
    assert warnings == []


def test_a_quote_nested_in_a_quote_keeps_the_whole_line_as_one_speech() -> None:
    line = "“Haha! “Cậu sẽ bị xử lý thích đáng” chứ gì? Cứ làm đi!”"
    rows = segment_chapter_text(1, f"{line}\n\nTôi mở cửa bước ra.")

    assert [(row["kind_hint"], row["text"]) for row in rows] == [
        ("dialogue", line),
        ("narration", "Tôi mở cửa bước ra."),
    ]
