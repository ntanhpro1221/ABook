"""The desktop audiobook export cuts a text chapter into paragraphs with the Python port of the player's rule (abook/readaloud/paragraphs.py).

An exported chapter must hold the very paragraphs the player reads, or the clips already made while listening (cache key = voice + paragraph text)
do not match and the whole book is read again. Both ports read the shared examples tests/fixtures/text_paragraphs/cases.json and
tests/fixtures/scene_break/cases.json (textScript.test.ts runs the same files).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook.readaloud import paragraphs as px

FIXTURES = Path(__file__).parent / "fixtures"
TEXT_CASES = json.loads((FIXTURES / "text_paragraphs" / "cases.json").read_text(encoding="utf-8"))["cases"]
SCENE_CASES = json.loads((FIXTURES / "scene_break" / "cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", TEXT_CASES, ids=[case["name"] for case in TEXT_CASES])
def test_a_chapter_is_cut_into_the_paragraphs_the_player_reads(case: dict) -> None:
    assert px.paragraphs_of(px.without_lines(case["text"], case.get("skip"))) == case["paragraphs"]


@pytest.mark.parametrize("case", SCENE_CASES["paragraphs"], ids=[case["name"] for case in SCENE_CASES["paragraphs"]])
def test_scene_breaks_are_flagged_and_paused_like_the_player(case: dict) -> None:
    split = px.split_paragraphs(case["text"])
    assert [paragraph.text for paragraph in split] == case["paragraphs"]
    assert [paragraph.scene_break for paragraph in split] == case["breaks"]
    assert px.scene_break_gaps(split) == case["gapsMs"]


def test_an_unreadable_non_separator_line_does_not_cut_a_run_of_separators() -> None:
    items = [px.Paragraph(text, text == "***" or text == chr(0x25C6)) for text in ("A.", "***", "...", chr(0x25C6), "B.")]
    assert px.scene_break_gaps(items) == [0, px.SCENE_BREAK_MS, 0, 0, 0]


def test_the_js_whitespace_set_is_the_one_the_players_use() -> None:
    assert px.squeeze(chr(0xFEFF) + "  a" + chr(0xA0) + chr(0xA0) + "b " + chr(0x2003)) == "a b"
    # Python's own \s would treat U+0085 as a space; JavaScript (and so the player) does not
    assert px.squeeze("a" + chr(0x85) + "b") == "a" + chr(0x85) + "b"
    assert px.is_speakable("Ba") and px.is_speakable("12") and not px.is_speakable("* * *") and not px.is_speakable("…")
