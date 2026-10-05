"""Lời dẫn tên kèm kính ngữ Nhật ("Yuzuki-chan bước vào...") gán câu thoại cho "Yuzuki", không đẻ ra "Yuzuki-chan".

Tên chép nguyên từ câu kể thành một nhân vật mới chưa rõ giới, đè tên đúng của model, rồi lọt vào danh sách "Nhân vật đã
biết" của mọi lô sau.
"""
from __future__ import annotations

from abook.analysis import _original_neighbor_context, _validate
from abook.character_registry import strip_japanese_honorific


def row(stable_id: str, seq: int, text: str, hint: str) -> dict[str, object]:
    return {"stable_id": stable_id, "chapter_id": 1, "seq": seq, "paragraph_index": 5, "text": text,
            "kind_hint": hint}


def item(seg_id: str, kind: str, speaker: str, gender: str) -> dict[str, object]:
    return {"id": seg_id, "kind": kind, "speaker": speaker, "gender": gender, "age": "young",
            "emotion": "neutral", "intensity": 1, "confidence": 0.9}


CHAPTER = [
    row("a", 1, "Cuối cùng thì, nó cũng trở nên,", "narration"),
    row("b", 2, "“nó thấy dễ chịu lắm.”", "dialogue"),
    row("c", 3, "Yuzuki-chan sắp bước vào một thế giới lạ… tại tôi.", "narration"),
]


def analyse(speaker: str, gender: str) -> dict[str, object]:
    payload = {"segments": [
        item("a", "narration", "NARRATOR", "unknown"),
        item("b", "dialogue", speaker, gender),
        item("c", "narration", "NARRATOR", "unknown"),
    ]}
    return _validate(CHAPTER, payload, original_context=_original_neighbor_context(CHAPTER))["b"]


def test_the_models_name_and_gender_stay_when_the_tag_only_adds_an_honorific() -> None:
    line = analyse("Yuzuki", "female")
    assert (line["speaker"], line["gender"]) == ("Yuzuki", "female")


def test_a_wrong_speaker_is_replaced_by_the_bare_name() -> None:
    assert analyse("Ren", "male")["speaker"] == "Yuzuki"


def test_the_registry_still_exports_the_shared_helper() -> None:
    assert strip_japanese_honorific("Yuzuki-chan") == "Yuzuki"
