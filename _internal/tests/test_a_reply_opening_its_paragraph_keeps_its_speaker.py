"""Câu thoại ngắn mở đầu đoạn văn ở mép trái lô, lời dẫn nối bằng dấu phẩy, vẫn là câu của người nói.

“Ừ”, cô ấy đáp lại... đứng đầu lô: lô không thấy đoạn trước nên cụm trích chỉ còn một phía, và phía ấy mở bằng dấu phẩy -
trông y như thuật ngữ giữa câu kể. Đoạn liền trước (ngoài lô) thuộc đoạn văn khác thì cụm trích mở đầu đoạn văn, không
nằm giữa câu nào.
"""
from __future__ import annotations

from abook.analysis import (
    _is_quoted_inside_a_sentence,
    _original_neighbor_context,
    _validate,
)


def row(stable_id: str, seq: int, paragraph: int, text: str, hint: str) -> dict[str, object]:
    return {
        "stable_id": stable_id,
        "chapter_id": 1,
        "seq": seq,
        "paragraph_index": paragraph,
        "text": text,
        "kind_hint": hint,
    }


def item(seg_id: str, kind: str, speaker: str) -> dict[str, object]:
    return {"id": seg_id, "kind": kind, "speaker": speaker, "gender": "female", "age": "young",
            "emotion": "neutral", "intensity": 1, "confidence": 0.9}


CHAPTER = [
    row("a", 1, 7, "“Vậy mình về phòng rồi nói nhé”", "dialogue"),
    row("b", 2, 8, "“Ừ”", "dialogue"),
    row("c", 3, 8, ", cô ấy đáp lại rồi đi thẳng về phòng tôi.", "narration"),
]


def test_a_reply_at_the_start_of_the_batch_keeps_its_speaker() -> None:
    group = CHAPTER[1:]
    payload = {"segments": [item("b", "dialogue", "Mai"), item("c", "narration", "NARRATOR")]}
    result = _validate(group, payload, original_context=_original_neighbor_context(CHAPTER))
    assert result["b"]["kind"] == "dialogue"
    assert result["b"]["speaker"] == "Mai"


def test_without_the_outside_neighbour_the_old_edge_rule_still_applies() -> None:
    group = CHAPTER[1:]
    result = {"b": {"kind": "dialogue", "speaker": "Mai"}, "c": {"kind": "narration", "speaker": "NARRATOR"}}
    assert _is_quoted_inside_a_sentence(group, 0, result)


def test_a_term_whose_sentence_began_before_the_batch_is_still_the_narrators() -> None:
    chapter = [
        row("a", 1, 8, "Cậu ấy không chịu gọi nó là", "narration"),
        row("b", 2, 8, "“bí kíp”", "dialogue"),
        row("c", 3, 8, "mà cứ gọi là sổ tay.", "narration"),
    ]
    result = {"b": {"kind": "dialogue", "speaker": "Mai"}, "c": {"kind": "narration", "speaker": "NARRATOR"}}
    assert _is_quoted_inside_a_sentence(chapter[1:], 0, result, _original_neighbor_context(chapter))
