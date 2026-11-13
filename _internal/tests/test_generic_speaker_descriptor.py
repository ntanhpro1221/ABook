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
    ("Bà lão quàng áo choàng đen trả lời:", "bà lão quàng áo choàng đen", "female", "elderly"),
    ("Chàng trai áo choàng đen lên tiếng:", "chàng trai áo choàng đen", "male", "young"),
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
    assert _generic_speaker_attribution("Ông lão đeo chiếc kính gọng bạc mỏng hỏi:", prefer_last=True) \
        == "ông lão đeo chiếc kính gọng bạc mỏng"
    assert _generic_speaker_attribution("Ông lão đeo chiếc kính gọng bạc mỏng tang hỏi:", prefer_last=True) is None


@pytest.mark.parametrize("tag", [
    # Longer than the cap: a clause, not a label.
    "Cô bé cầm chiếc ô giấy vàng sờn mép hỏi:",
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


@pytest.mark.parametrize("preposition", ["có", "với"])
@pytest.mark.parametrize("appearance", [
    "mái tóc bạc", "đôi mắt xanh", "chiếc áo khoác tím", "tóc xoăn ngắn",
    "cặp kính gọng bạc", "một chiếc khăn len", "bộ râu rậm", "áo sơ mi trắng",
    "dáng người gầy gò", "dáng vẻ trang nghiêm", "thân hình cao lớn", "nước da hồng hào",
])
@pytest.mark.parametrize("after_quote", [False, True])
def test_possession_requires_an_appearance_noun_phrase(preposition, appearance, after_quote) -> None:
    label = f"cô gái {preposition} {appearance}"
    tag = f"Cô gái {preposition} {appearance} đáp:"
    assert _generic_speaker_attribution(tag, prefer_last=not after_quote) == label
    dialogue = _row(1, "dialogue", "“Mã ô số tám.”")
    narration = _row(0, "narration", tag)
    group = [dialogue, narration] if after_quote else [narration, dialogue]
    for seq, row in enumerate(group):
        row["seq"] = seq
    result = _validate(group, {"segments": [
        _item(0, "narration", "NARRATOR", .9), _item(1, "dialogue", "UNKNOWN", .5),
    ]})["s1"]
    assert local_speaker_label(result["speaker"]) == label
    assert (result["gender"], result["age"]) == ("female", "young")


@pytest.mark.parametrize("head", ["Cô gái", "Ông lão"])
@pytest.mark.parametrize("descriptor,verb", [
    ("có nghe khách", "nói"),
    ("có thấy khách", "hỏi"),
    ("có biết khách", "đáp"),
    ("có muốn khách", "trả lời"),
    ("có nhờ khách", "lên tiếng"),
    ("có để ý khách", "hỏi"),
    ("với giọng ai đó", "gọi"),
    ("với giọng khách", "nói"),
    ("với mong muốn khách", "đáp"),
    ("với sự đồng ý khách", "hỏi"),
    # A noun at the start is insufficient: the remainder can introduce a clause.
    ("có tóc khiến khách", "nói"),
    ("có đôi mắt thấy khách", "hỏi"),
    ("có áo giúp khách", "đáp"),
    ("với áo khoác nghe khách", "nói"),
    ("với khăn che mắt khách", "hỏi"),
    ("có mái tóc khách", "nói"),
    ("với chiếc áo của khách", "nói"),
])
def test_clauses_do_not_invent_a_speaker_or_casting_traits(head, descriptor, verb) -> None:
    tag = f"{head} {descriptor} {verb}:"
    assert _generic_speaker_attribution(tag, prefer_last=True) is None
    group = [_row(0, "narration", tag), _row(1, "dialogue", "“Mã ô số tám.”")]
    result = _validate(group, {"segments": [
        _item(0, "narration", "NARRATOR", .9), _item(1, "dialogue", "UNKNOWN", .5),
    ]})["s1"]
    assert (result["speaker"], result["gender"], result["age"]) == ("UNKNOWN", "unknown", "unknown")


@pytest.mark.parametrize("preposition", ["có", "với"])
def test_nominal_descriptors_keep_the_cap_and_case_guard(preposition) -> None:
    assert _generic_speaker_attribution(
        f"Cô gái {preposition} chiếc áo khoác tím nhạt đáp:", prefer_last=True,
    ) == f"cô gái {preposition} chiếc áo khoác tím nhạt"
    assert _generic_speaker_attribution(
        f"Cô gái {preposition} một chiếc áo khoác tím nhạt đáp:", prefer_last=True,
    ) is None
    assert _generic_speaker_attribution(
        f"Cô gái {preposition} chiếc áo Tavin đáp:", prefer_last=True,
    ) is None


@pytest.mark.parametrize("confidence", [.79, .8, .95])
def test_nominal_descriptors_respect_the_existing_identity_threshold(confidence) -> None:
    tag = "Cô gái với chiếc áo khoác tím đáp:"
    group = [_row(0, "narration", tag), _row(1, "dialogue", "“Mã ô số tám.”")]
    result = _validate(group, {"segments": [
        _item(0, "narration", "NARRATOR", .9), _item(1, "dialogue", "Tavin", confidence),
    ]})["s1"]
    if confidence < .8:
        assert local_speaker_label(result["speaker"]) == "cô gái với chiếc áo khoác tím"
        assert (result["gender"], result["age"]) == ("female", "young")
    else:
        assert (result["speaker"], result["gender"], result["age"]) == ("Tavin", "unknown", "unknown")
