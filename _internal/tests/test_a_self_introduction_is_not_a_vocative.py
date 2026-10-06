"""Tên đầu câu + thân phận/dòng dõi rồi hết câu là người nói tự giới thiệu, không phải gọi người có tên ấy.

Hai thầy gán nhãn 06-10: đáp lại "Tên ta là ...", nhân vật nói "“<tên>, con trai của <tên cha>. Bắt đầu nào.”"; host coi tên
đầu câu là người được gọi và đổi người nói thành "người gọi <tên>".
"""
from __future__ import annotations

from abook.analysis import _repair_addressee_speakers, _speaker_is_directly_addressed


def test_name_and_lineage_is_a_self_introduction() -> None:
    assert not _speaker_is_directly_addressed("“Borak, con trai của Gerud. Vào trận đi.”", "Borak")


def test_name_and_rank_in_a_house_is_a_self_introduction() -> None:
    assert not _speaker_is_directly_addressed("“Edan, một kỵ sĩ của nhà Valmont.”", "Edan")


def test_a_name_followed_by_speech_is_still_a_vocative() -> None:
    assert _speaker_is_directly_addressed("“Borak, mau lùi lại!”", "Borak")


def test_a_lineage_phrase_that_runs_on_with_a_comma_is_still_a_vocative() -> None:
    assert _speaker_is_directly_addressed("“Borak, con trai của Gerud, ngươi dám trốn sao?”", "Borak")


def test_the_repair_keeps_the_speaker_of_a_self_introduction() -> None:
    group = [{"stable_id": "a", "chapter_id": 1, "paragraph_index": 3, "seq": 3,
              "text": "“Borak, con trai của Gerud. Vào trận đi.”"}]
    result = {"a": {"kind": "dialogue", "speaker": "Borak", "personality_hint": "", "notes": ""}}
    _repair_addressee_speakers(group, result, "b0000")
    assert result["a"]["speaker"] == "Borak"
    assert "_host_note_markers" not in result["a"]
