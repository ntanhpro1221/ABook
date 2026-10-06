"""Câu kể ngay sau một câu thoại thiếu dấu đóng: model trả lời người kể thì app lưu người kể.

Hai thầy gán nhãn 06-10 trả lời NARRATOR cho "X, cô hầu bàn, đặt hai ly bia..." và "X trả lời với cái trán rỉ máu." ngay
sau một câu thoại không có ”; app lưu tên người nói câu trước. Lỗi nằm ở bộ tách đoạn cũ: nó khoá câu kể ấy là thoại nối
tiếp, nên `_validate` bỏ câu trả lời lời kể (ranh giới thoại thuộc bộ tách đoạn) và `_repair_continued_dialogue_speakers`
chép người nói câu trước. Từ khi ngoặc thiếu dấu đóng được đóng ở cuối đoạn của nó (`_fresh_quote_opening`), câu kể ấy
là lời kể từ bộ tách đoạn, và câu trả lời của model đi thẳng vào. Văn bản là câu tự viết cùng cấu trúc.
"""
from __future__ import annotations

from abook.analysis import _validate
from abook.text_processing import segment_chapter_text


def analysed(text: str, speakers: dict[str, str]) -> list[tuple[str, str, str]]:
    rows = [dict(row, chapter_id=1) for row in segment_chapter_text(1, text)]
    payload = {
        "segments": [
            {
                "id": row["stable_id"],
                "kind": row["kind_hint"],
                "speaker": speakers.get(str(row["text"]), "NARRATOR"),
                "emotion": "neutral",
            }
            for row in rows
        ]
    }
    result = _validate(rows, payload)
    return [(str(row["text"]), result[row["stable_id"]]["kind"], result[row["stable_id"]]["speaker"]) for row in rows]


def test_a_named_action_after_an_unclosed_line_is_the_narrators() -> None:
    opened = "“Thật mà, chú Bảo, dạo này chú ít ghé nên không nghe đấy thôi."
    narration = "Thu, cô chủ quán, đặt hai cốc trà lên bàn. Lúc ấy, Bảo phá lên cười."
    reply = "“Thế à? Vậy kể ta nghe xem nào.”"
    stored = analysed(f"{opened}\n\n{narration}\n\n{reply}", {opened: "Thu", reply: "Bảo"})

    assert stored == [(opened, "dialogue", "Thu"), (narration, "narration", "NARRATOR"), (reply, "dialogue", "Bảo")]


def test_a_named_speech_tag_after_an_unclosed_question_is_the_narrators() -> None:
    opened = "“Ơ… à, phải, phải rồi! Chắc anh đang giận lắm nhỉ?"
    narration = "Khải trả lời, tay vẫn ôm trán."
    reply = "“Tôi biết, phải không? Vậy bạn bè nên nói gì lúc này?”"
    stored = analysed(f"{opened}\n\n{narration}\n\n{reply}", {opened: "Khải", reply: "Gã áo choàng"})

    assert stored[1] == (narration, "narration", "NARRATOR")
    assert stored[0][2] == "Khải"
