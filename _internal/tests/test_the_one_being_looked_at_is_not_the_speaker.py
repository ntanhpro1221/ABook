"""Luật "tên ngay trước 'nói:' là người nói" im khi tên là người NGHE hay mẩu tên bị cắt (cuốn 2: ~29 câu)."""
from __future__ import annotations

from ebook_reader.analysis import _trailing_speech_attribution


def test_the_listener_named_before_the_speech_verb_is_not_the_speaker() -> None:
    for text in (
        <removed>
        <removed>
        <removed>
        <removed>
        <removed>
        <removed>
        <removed>
        <removed>
    ):
        assert _trailing_speech_attribution(text) is None, text


def test_a_name_cut_short_by_its_accents_is_not_a_name() -> None:
    <removed>
    <removed>


def test_the_subject_still_takes_the_line() -> None:
    assert _trailing_speech_attribution("Lucien nói:") == "Lucien"
    assert _trailing_speech_attribution("Rồi Lucien nói:") == "Lucien"
    assert _trailing_speech_attribution("Sau đó, Lucien hỏi:") == "Lucien"
    <removed>
    <removed>
    <removed>
    <removed>
