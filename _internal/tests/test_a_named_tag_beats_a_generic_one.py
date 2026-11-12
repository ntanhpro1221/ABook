"""Lời dẫn có tên thì nhãn chung phải im; lời dẫn riêng thắng khoá theo đoạn (đáp án chuẩn TMA 418:37, 426:22, 436:61)."""
from __future__ import annotations

from abook.analysis import _generic_speaker_attribution, _validate


def _row(seq: int, kind_hint: str, text: str, paragraph: int = 3) -> dict:
    return {"stable_id": f"s{seq}", "kind_hint": kind_hint, "text": text, "chapter_id": 1, "seq": seq,
            "paragraph_index": paragraph}


def _item(seq: int, kind: str, speaker: str, gender: str = "male") -> dict:
    return {"id": f"s{seq}", "kind": kind, "speaker": speaker, "gender": gender, "age": "adult",
            "emotion": "neutral", "intensity": 0, "pace": "normal", "volume": "normal", "confidence": 0.9}


def test_a_named_tag_is_not_given_to_a_generic_label() -> None:
    for text in (
        'Bên quầy in có hai người đàn ông cùng một người phụ nữ, James đưa cho Lucien tập phiếu rồi nói:',
        'Người đàn ông trung niên đeo tạp dề chấm mực, Salgueiro, cau mày nói:',
        'Chưa từng chọn được món quà cho cô gái ở quầy bên, Lucien nói như tự giễu:',
    ):
        assert _generic_speaker_attribution(text, prefer_last=True) is None, text


def test_an_anonymous_tag_still_gets_its_generic_label() -> None:
    assert _generic_speaker_attribution("Một người phụ nữ trung niên bước tới nói:", prefer_last=True) == "người phụ nữ"
    # A sigh is an action, not a speech tag.
    assert _generic_speaker_attribution("Người đàn ông lặng lẽ thở dài:", prefer_last=True) is None


def test_the_model_keeps_the_named_speaker() -> None:
    group = [
        _row(0, "narration", 'Người đàn ông trung niên đeo tạp dề chấm mực, Salgueiro, cau mày nói:'),
        _row(1, "dialogue", '“Chúng ta đánh dấu từng lô bằng màu mực nào đây?”'),
    ]
    result = _validate(group, {"segments": [_item(0, "narration", "NARRATOR"), _item(1, "dialogue", "Salgueiro")]})
    assert result["s1"]["speaker"].casefold() == "salgueiro"


def test_an_interruption_in_the_same_paragraph_keeps_its_own_speaker() -> None:
    group = [
        _row(0, "dialogue", "“Việc này…”"),
        _row(1, "narration", 'Raventi đang định đọc bảng kê, Florencia cầm tấm phiếu và cắt ngang:'),
        _row(2, "dialogue", '“Oliver đã xem bản vẽ và đặt thêm hai cuộn giấy can cho cậu đấy.”'),
    ]
    payload = {"segments": [
        _item(0, "dialogue", "Raventi"), _item(1, "narration", "NARRATOR"), _item(2, "dialogue", "Florencia", "female"),
    ]}
    result = _validate(group, payload)
    assert result["s0"]["speaker"].casefold() == "raventi"
    assert result["s2"]["speaker"].casefold() == "florencia"
