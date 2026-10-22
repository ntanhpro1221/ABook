"""Soát a79 lỗi 11, nửa ở file khoá: `word_timing.tokens` và `readings` đếm "chữ hiện" như JavaScript (mapping.TOKEN), không như `\\S+`
của Python - cùng fixture chung với mapping/spread/google và điện thoại."""

from __future__ import annotations

import json
from pathlib import Path

from abook.readaloud import mapping, readings
from abook.webui import word_timing

FIXTURE = Path(__file__).parent / "fixtures" / "readaloud" / "js_space_is_the_word_boundary.json"


def test_word_timing_counts_words_like_the_reader() -> None:
    case = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(word_timing.tokens(case["text"])) == len(case["words"])
    assert word_timing.tokens(case["text"]) == mapping.TOKEN.findall(case["text"])


def test_python_only_spaces_do_not_split_and_bom_does() -> None:
    for char in "\u0085\u001c\u001d\u001e\u001f":
        assert word_timing.tokens(f"a{char}b c") == [f"a{char}b", "c"]
    assert word_timing.tokens("a﻿b") == ["a", "b"]


def test_readings_walk_the_same_words() -> None:
    assert readings._TOKEN is mapping.TOKEN
