"""Cụm trích giữa câu kể trả về NGƯỜI KỂ; câu thoại thật thì không bị chạm."""
from __future__ import annotations

from abook.analysis import _repair_in_sentence_quote_speakers
from abook.database import IN_SENTENCE_QUOTE_NARRATOR_NOTE


def row(stable_id: str, paragraph: int, text: str) -> dict[str, object]:
    return {"stable_id": stable_id, "chapter_id": 1, "paragraph_index": paragraph, "text": text}


def data(kind: str, speaker: str) -> dict[str, object]:
    return {"kind": kind, "speaker": speaker, "personality_hint": "", "notes": ""}


def test_a_term_between_two_halves_of_a_sentence_goes_back_to_the_narrator() -> None:
    group = [
        row("a", 3, "Lucien không thể bảo rằng nếu là"),
        row("b", 3, "“Khoa Học”"),
        row("c", 3, "thì đòi hỏi phải tạo ra từ mới."),
    ]
    result = {"a": data("narration", "NARRATOR"), "b": data("dialogue", "LUCIEN"),
              "c": data("narration", "NARRATOR")}
    _repair_in_sentence_quote_speakers(group, result)
    assert result["b"]["speaker"] == "NARRATOR"
    assert IN_SENTENCE_QUOTE_NARRATOR_NOTE in result["b"]["_host_note_markers"]


def test_a_real_line_keeps_its_speaker() -> None:
    group = [
        row("a", 3, "Lucien mỉm cười nói:"),
        row("b", 3, "“Tôi đã tìm ra lời giải.”"),
        row("c", 4, "Cả phòng lặng đi."),
    ]
    result = {"a": data("narration", "NARRATOR"), "b": data("dialogue", "LUCIEN"),
              "c": data("narration", "NARRATOR")}
    _repair_in_sentence_quote_speakers(group, result)
    assert result["b"]["speaker"] == "LUCIEN"
    assert "_host_note_markers" not in result["b"]


def test_a_whole_utterance_quoted_mid_sentence_keeps_its_speaker() -> None:
    # Hai thầy gán nhãn 05-10: câu nói có dấu phẩy giữa câu kể vẫn là lời của người nói, không phải thuật ngữ.
    group = [
        row("a", 7, "Minh nói"),
        row("b", 7, "“Bố mẹ tớ đến xem rồi, nên nhà tớ sẽ ăn cùng nhau”"),
        row("c", 7, "và vì vậy chúng tôi ăn riêng."),
    ]
    result = {"a": data("narration", "NARRATOR"), "b": data("dialogue", "MINH"),
              "c": data("narration", "NARRATOR")}
    _repair_in_sentence_quote_speakers(group, result)
    assert result["b"]["speaker"] == "MINH"
    assert "_host_note_markers" not in result["b"]


def test_a_term_in_another_paragraph_is_not_touched() -> None:
    group = [
        row("a", 3, "Lucien không thể bảo rằng nếu là"),
        row("b", 4, "“Khoa Học”"),
        row("c", 5, "thì đòi hỏi phải tạo ra từ mới."),
    ]
    result = {"a": data("narration", "NARRATOR"), "b": data("dialogue", "LUCIEN"),
              "c": data("narration", "NARRATOR")}
    _repair_in_sentence_quote_speakers(group, result)
    assert result["b"]["speaker"] == "LUCIEN"
