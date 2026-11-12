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
    group = [_row(0, "dialogue", '“Hóa ra dưới khay tem còn một ngăn đựng mực nữa.”'), _row(1, "narration", narration)]
    result = _validate(group, {"segments": [_item(0, "dialogue", model_says), _item(1, "narration", "NARRATOR")]})
    return str(result["s0"]["speaker"]).casefold()


def test_a_vietnamese_word_opening_the_sentence_is_not_a_name() -> None:
    for text in ('Lo lắng phu nhân Tess làm đổ lọ mực, ông vội nói.', "Tay trái của Lucien nắm chặt.",
                 'Y chỉ vào cuộn giấy sát chiếc cân rồi nói.', 'Cho rằng màu tem vẫn chưa khớp, hắn nói.',
                 'Mất cả hộp mực, Beyer ngồi bệt bên quầy.', "Xung quanh bàn là mấy thùng giấy chưa dán nhãn."):
        assert _leading_proper_name(text) is None, text
    assert _leading_proper_name("Victor giải thích thêm một lần nữa.") == "Victor"
    assert _leading_proper_name('Ray nói, chuyển sang hỏi giá giấy can.') == "Ray"


def test_someone_who_had_not_spoken_yet_does_not_take_the_line() -> None:
    assert _names_someone_who_had_not_spoken('Lucien còn chưa kịp lấy cuộn giấy, một giọng nói vang qua bộ đàm.', "Lucien")
    assert _names_someone_who_had_not_spoken('Lucien chưa kịp mở hộp, Jacob đã nói tiếp.', "Lucien")
    assert _names_someone_who_had_not_spoken('Fernando còn chưa kịp đọc số phiếu, Antec đã kêu lên.', "Fernando")
    # Bị ngắt khi đang nói: người được nêu tên CHÍNH là người vừa nói.
    assert not _names_someone_who_had_not_spoken('Lucien chưa kịp nói hết bảng kê, Natasha đã cắt ngang.', "Lucien")
    assert not _names_someone_who_had_not_spoken('Dieppe còn chưa kịp dứt lời đọc số phiếu, tiếng còi tàu vang lên.', "Dieppe")
    assert not _names_someone_who_had_not_spoken('Lucien còn chưa kịp nói thêm về hộp màu, Alferris đã chộp lấy.', "Lucien")
    assert not _names_someone_who_had_not_spoken('Fernando lặp lại giá giấy, nhưng chưa kịp đọc hết.', "Fernando")


def test_the_model_keeps_the_line_when_the_named_person_had_not_spoken() -> None:
    narration = 'Lucien còn chưa kịp mở hộp mực, một giọng nói trầm vang qua bộ đàm ở quầy vé.'
    assert _speaker_of_the_quote(narration, "Beyer") == "beyer"


def test_only_a_real_speech_verb_takes_the_line():
    assert _speaker_of_the_quote('Tavin nói, giọng chậm rãi.','Mira')=='tavin'
    assert _speaker_of_the_quote('Tavin nhìn ra sân, rồi cầm ô.','Mira')=='mira'
