"""The read-aloud players (web textScript.ts, Android Paragraphs.kt) port the scene-break line rule of text_processing.

All three read tests/fixtures/scene_break/cases.json. This is the Python side: the rule and its constants must agree with the
fixture, so a change to `is_scene_break_line` that is not ported fails here (and the fixture change then fails the TS / JVM tests).
"""
from __future__ import annotations

import json
from pathlib import Path

from abook import text_processing as tp

CASES = json.loads((Path(__file__).parent / "fixtures" / "scene_break" / "cases.json").read_text(encoding="utf-8"))


def test_the_constants_are_the_ones_the_players_port() -> None:
    assert CASES["ms"] == tp.SCENE_BREAK_MS
    assert set(CASES["ruleGlyphs"]) == set(tp.SCENE_BREAK_RULE_GLYPHS)
    assert set(CASES["aloneGlyphs"]) == set(tp.SCENE_BREAK_ALONE_GLYPHS)
    assert set(CASES["ornamentGlyphs"]) == set(tp.SCENE_BREAK_ORNAMENT_GLYPHS)
    assert CASES["minRuleGlyphs"] == tp.SCENE_BREAK_MIN_RULE_GLYPHS
    assert CASES["maxGlyphs"] == tp.SCENE_BREAK_MAX_GLYPHS


def test_the_shared_lines_are_classified_as_the_players_must() -> None:
    assert CASES["separators"] and CASES["notSeparators"]
    assert [line for line in CASES["separators"] if not tp.is_scene_break_line(line)] == []
    assert [line for line in CASES["separators"] if not tp.is_scene_break_line(line, alone=True)] == []
    assert [line for line in CASES["notSeparators"] if tp.is_scene_break_line(line)] == []
    assert [line for line in CASES["notSeparators"] if tp.is_scene_break_line(line, alone=True)] == []


def test_a_short_rule_is_a_break_only_when_it_stands_alone_as_a_paragraph() -> None:
    assert CASES["loneSeparators"]
    assert [line for line in CASES["loneSeparators"] if tp.is_scene_break_line(line)] == []
    assert [line for line in CASES["loneSeparators"] if not tp.is_scene_break_line(line, alone=True)] == []


def test_a_line_over_the_glyph_limit_is_not_a_break() -> None:
    assert tp.is_scene_break_line("*" * CASES["maxGlyphs"])
    assert not tp.is_scene_break_line("*" * (CASES["maxGlyphs"] + 1))
