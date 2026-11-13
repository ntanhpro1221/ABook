"""Nhãn chung + cụm mô tả ngoại hình ngắn ("người phụ nữ mặc váy xanh nói") là một luật chung, không phải từng khoá
chép tay trong GENERIC_SPEAKER_TRAITS. Mọi câu ở đây là câu tự viết."""
from __future__ import annotations

import pytest

from abook.analysis import (
    GENERIC_DESCRIPTOR_MAX_SYLLABLES,
    GENERIC_SPEAKER_TRAITS,
    _generic_speaker_attribution,
    _validate,
    local_speaker_label,
)


def _row(seq: int, kind_hint: str, text: str) -> dict:
    return {"stable_id": f"s{seq}", "kind_hint": kind_hint, "text": text, "chapter_id": 1, "seq": seq,
            "paragraph_index": 4}


def _item(seq: int, kind: str, speaker: str, confidence: float) -> dict:
    return {"id": f"s{seq}", "kind": kind, "speaker": speaker, "gender": "unknown", "age": "unknown",
            "emotion": "neutral", "intensity": 0, "pace": "normal", "volume": "normal", "confidence": confidence}


def test_no_hand_copied_descriptor_keys_remain() -> None:
    # Every key is a bare generic noun; descriptors come from the general rule.
    assert not [key for key in GENERIC_SPEAKER_TRAITS if any(
        word in key.split() for word in ("mặc", "đội", "đeo", "áo", "váy", "khoác", "choàng"))]


@pytest.mark.parametrize("tag,label,gender,age", [
    ("Người phụ nữ mặc váy xanh nói:", "người phụ nữ mặc váy xanh", "female", "adult"),
    ("Ông lão đội nón lá hỏi:", "ông lão đội nón lá", "male", "elderly"),
    ("Cô gái đeo kính tròn khẽ đáp:", "cô gái đeo kính tròn", "female", "young"),
    ("Cậu bé cầm cây sáo gỗ hỏi:", "cậu bé cầm cây sáo gỗ", "male", "child"),
    ("Bà lão có mái tóc bạc thì thầm:", "bà lão có mái tóc bạc", "female", "elderly"),
    ("Chàng trai đi giày vải cười nói:", "chàng trai đi giày vải", "male", "young"),
    # The old hand-written key, now caught by the rule in two different phrasings.
    ("0. Câu thử đã gỡ. 0.", "0. Câu thử đã gỡ. 0.", "0. Câu thử đã gỡ. 0.", "0. Câu thử đã gỡ. 0."),
    ("Người đàn ông áo choàng đen lên tiếng:", "người đàn ông áo choàng đen", "male", "adult"),
])
def test_a_described_generic_speaker_is_attributed_with_head_traits(tag, label, gender, age) -> None:
    assert _generic_speaker_attribution(tag, prefer_last=True) == label
    group = [_row(0, "narration", tag), _row(1, "dialogue", "“Ngày mai trời có mưa không?”")]
    result = _validate(group, {"segments": [_item(0, "narration", "NARRATOR", .9), _item(1, "dialogue", "UNKNOWN", .5)]})
    assert local_speaker_label(result["s1"]["speaker"]) == label
    assert (result["s1"]["gender"], result["s1"]["age"]) == (gender, age)


def test_two_different_outfits_are_two_speakers() -> None:
    blue = _generic_speaker_attribution("Người phụ nữ mặc váy xanh nói:", prefer_last=True)
    red = _generic_speaker_attribution("Người phụ nữ mặc váy đỏ nói:", prefer_last=True)
    assert blue and red and blue != red


def test_the_syllable_cap_is_inclusive() -> None:
    assert GENERIC_DESCRIPTOR_MAX_SYLLABLES == 6
    assert _generic_speaker_attribution("0. Câu thử đã gỡ. 0.", prefer_last=True) \
        == "0. Câu thử đã gỡ. 0."
    assert _generic_speaker_attribution("0. Câu thử đã gỡ. 0.", prefer_last=True) is None


@pytest.mark.parametrize("tag", [
    # Longer than the cap: a clause, not a label.
    "Người đàn ông mặc áo khoác đen dài chấm gót chân hỏi:",
    # A comma breaks the subject; what follows may have its own subject.
    "Người phụ nữ mặc váy xanh, tay cầm ô, nói:",
    "Ông lão đội nón lá, cháu ông, hỏi:",
    # A relative clause: the speaker is the pronoun ("anh ta"), not the woman. Pronouns and
    # conjunctions cut the phrase, so the whole tag is left to the model.
    "Người phụ nữ mặc áo mà anh ta nói:",
    "Cô gái cầm đèn rồi hắn hỏi:",
    # A capitalised word is a name: whose line it is stays ambiguous.
    "Người phụ nữ cầm thư Tavin nói:",
    # "có vẻ" is a manner adverb, not an appearance.
    "Người đàn ông có vẻ mệt nói:",
    # Movement, not footwear.
    "Người đàn ông đi tới nói:",
    # The described person is an object of someone else's verb.
    "Người đàn ông nhìn cô gái mặc áo đỏ nói:",
    "Tavin nhìn người phụ nữ mặc váy xanh rồi nói:",
])
def test_ambiguous_or_overlong_descriptions_are_not_attributed(tag) -> None:
    assert _generic_speaker_attribution(tag, prefer_last=True) is None


def test_existing_forms_are_unchanged() -> None:
    assert _generic_speaker_attribution("Một người phụ nữ trung niên bước tới nói:", prefer_last=True) == "người phụ nữ"
    assert _generic_speaker_attribution("Mấy cô gái khẽ hỏi:", prefer_last=True) == "cô gái"
    assert _generic_speaker_attribution("Mẹ của cô bé nói:", prefer_last=True) == "mẹ của cô bé"
    assert _generic_speaker_attribution("Em gái Tavin khẽ hỏi:", prefer_last=True) == "em gái tavin"
    assert _generic_speaker_attribution("Người đàn ông lặng lẽ thở dài:", prefer_last=True) is None
    assert _generic_speaker_attribution(
        "Người đàn ông trung niên đeo tạp dề, Salgueiro, cau mày nói:", prefer_last=True) is None
