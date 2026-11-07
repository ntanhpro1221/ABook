"""Khoá "một đoạn văn một người nói" không nuốt cụm trích nằm giữa một câu kể (đáp án chuẩn TMA 419:24, 26)."""
from __future__ import annotations

from abook.analysis import _validate


def _row(seq: int, kind_hint: str, text: str) -> dict:
    return {"stable_id": f"s{seq}", "kind_hint": kind_hint, "text": text, "chapter_id": 1, "seq": seq,
            "paragraph_index": 13}


def _item(seq: int, kind: str, speaker: str, gender: str = "unknown") -> dict:
    return {"id": f"s{seq}", "kind": kind, "speaker": speaker, "gender": gender, "age": "unknown",
            "emotion": "neutral", "intensity": 0, "pace": "normal", "volume": "normal", "confidence": 0.9}


def test_a_term_quoted_inside_a_sentence_keeps_its_own_reading() -> None:
    group = [
        <removed>
        _row(1, "narration", "Arthur không hiểu"),
        _row(2, "dialogue", "“dây chuyền lắp ráp”"),
        _row(3, "narration", "hay"),
        _row(4, "dialogue", "“tiêu chuẩn hóa”"),
        <removed>
    ]
    payload = {"segments": [
        _item(0, "dialogue", "Arthur", "male"), _item(1, "narration", "NARRATOR"),
        _item(2, "dialogue", "NARRATOR"), _item(3, "narration", "NARRATOR"),
        _item(4, "dialogue", "NARRATOR"), _item(5, "narration", "NARRATOR"),
    ]}
    result = _validate(group, payload)
    assert result["s0"]["speaker"].casefold() == "arthur"
    assert result["s2"]["speaker"].casefold() != "arthur"
    assert result["s4"]["speaker"].casefold() != "arthur"


def test_a_term_at_the_edge_of_an_analysis_batch_is_still_seen() -> None:
    # 419:26 là đoạn cuối lô của nó: không thấy câu kể phía sau.
    group = [
        <removed>
        _row(1, "narration", "Arthur không hiểu"),
        _row(2, "dialogue", "“dây chuyền lắp ráp”"),
        _row(3, "narration", "hay"),
        _row(4, "dialogue", "“tiêu chuẩn hóa”"),
    ]
    payload = {"segments": [
        _item(0, "dialogue", "Arthur", "male"), _item(1, "narration", "NARRATOR"),
        _item(2, "dialogue", "NARRATOR"), _item(3, "narration", "NARRATOR"), _item(4, "dialogue", "NARRATOR"),
    ]}
    result = _validate(group, payload)
    assert result["s4"]["speaker"].casefold() != "arthur"


def test_a_later_tag_does_not_propagate_backward_over_another_tag():
    from tests.test_analysis_required import _castrule_batch
    rows,payload=_castrule_batch([('“Giữ đèn nhé.”','dialogue','Mira'),('cô nói, rồi nhìn Tavin.','narration','NARRATOR'),('“Tôi cầm ô.”','dialogue','Tavin'),('Tavin nói.','narration','NARRATOR')])
    assert _validate(rows,payload)['r0']['speaker']=='Mira'


def test_a_confident_following_turn_is_independent():
    from tests.test_analysis_required import _castrule_batch
    rows,payload=_castrule_batch([('“Tôi giữ đèn.”','dialogue','Mira'),('Mira nói.','narration','NARRATOR'),('“Tôi cầm ô.”','dialogue','Tavin')])
    assert _validate(rows,payload)['r2']['speaker']=='Tavin'


def test_embedded_nominal_fragment_corrects_a_model_assigned_name():
    from tests.test_analysis_required import _castrule_batch
    from abook.analysis import _original_neighbor_context
    rows, payload = _castrule_batch([
        ('Mira nhắc về', 'narration', 'NARRATOR'),
        ('“bản đồ gió”', 'dialogue', 'Tavin'),
        (', một vật dụng đã thất lạc.', 'narration', 'NARRATOR'),
    ])
    assert _validate(rows, payload)['r1']['speaker'] == 'NARRATOR'
    context = _original_neighbor_context(rows)
    assert _validate([rows[1]], {'segments': [payload['segments'][1]]},
                     original_context=context)['r1']['speaker'] == 'NARRATOR'


def test_a_single_quoted_fragment_preserves_the_accepted_thinker():
    from tests.test_analysis_required import _castrule_batch
    rows, payload = _castrule_batch([
        ('Tôi gọi tấm bản đồ ấy là', 'narration', 'NARRATOR'),
        ('‘đường về nhà’', 'thought', 'Tavin'),
        (', vì nó dẫn qua thung lũng.', 'narration', 'NARRATOR'),
    ])
    result = _validate(rows, payload)
    assert result['r1']['speaker'] == 'Tavin'
    assert result['r1']['kind'] == 'thought'
