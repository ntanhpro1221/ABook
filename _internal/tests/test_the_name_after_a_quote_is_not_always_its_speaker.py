"""Luật "tên đầu câu kể sau câu thoại là người nói" im khi tên là chữ Việt hoặc người ấy chưa nói (đáp án chuẩn 378, 407)."""
from __future__ import annotations

from abook.analysis import _leading_proper_name, _names_someone_who_had_not_spoken, _validate


def _row(seq: int, kind_hint: str, text: str) -> dict:
    return {"stable_id": f"s{seq}", "kind_hint": kind_hint, "text": text, "chapter_id": 1, "seq": seq,
            "paragraph_index": 7}


def _item(seq: int, kind: str, speaker: str, gender: str = "male") -> dict:
    return {"id": f"s{seq}", "kind": kind, "speaker": speaker, "gender": gender, "age": "adult",
            "emotion": "neutral", "intensity": 0, "pace": "normal", "volume": "normal", "confidence": 0.9}


def _speaker_of_the_quote(narration: str, model_says: str) -> str:
    <removed>
    result = _validate(group, {"segments": [_item(0, "dialogue", model_says), _item(1, "narration", "NARRATOR")]})
    return str(result["s0"]["speaker"]).casefold()


def test_a_vietnamese_word_opening_the_sentence_is_not_a_name() -> None:
    <removed>
                 <removed>
                 <removed>
        assert _leading_proper_name(text) is None, text
    assert _leading_proper_name("Victor giải thích thêm một lần nữa.") == "Victor"
    <removed>


def test_someone_who_had_not_spoken_yet_does_not_take_the_line() -> None:
    <removed>
    <removed>
    <removed>
    # Bị ngắt khi đang nói: người được nêu tên CHÍNH là người vừa nói.
    <removed>
    <removed>
    <removed>
    <removed>


def test_the_model_keeps_the_line_when_the_named_person_had_not_spoken() -> None:
    <removed>
    assert _speaker_of_the_quote(narration, "Beyer") == "beyer"


def test_the_named_person_still_takes_the_line_when_the_sentence_says_so() -> None:
    assert _speaker_of_the_quote("Lucien nói, giọng trầm xuống.", "Beyer") == "lucien"
    <removed>
