"""Cắt khúc đầu của Supertonic (supertonic.cut, livejoin2): đoạn <= 300 ký tự vốn là MỘT khúc nên không có gì để phát luồng; khúc đầu dài hơn 120 ký tự được cắt ở ranh
câu / ranh vế. Bảng ca dùng chung với điện thoại (tests/fixtures/supertonic/opening_cut.json, SupertonicOpeningCutTest.kt)."""
from __future__ import annotations

import json
from pathlib import Path

from abook.readaloud import local_stream, supertonic, vieneu
from abook.readaloud.supertonic import SupertonicProvider

FIXTURE = Path(__file__).parent / "fixtures" / "supertonic" / "opening_cut.json"


def test_every_shared_case_is_cut_the_same_way():
    cases = json.loads(FIXTURE.read_bytes().decode("utf-8"))["cases"]
    assert len(cases) >= 8
    for case in cases:
        toks, parts = supertonic.cut(case["text"], case["origin"])
        assert [{"text": unit.text(toks), "pieces": unit.pieces} for unit in parts] == case["units"], case["name"]


def test_only_the_first_unit_is_cut_and_every_word_is_in_exactly_one_unit():
    for case in json.loads(FIXTURE.read_bytes().decode("utf-8"))["cases"]:
        toks, plain = vieneu.units(case["text"], supertonic.MAX_CHARS, case["origin"], True, None)
        _, parts = supertonic.cut(case["text"], case["origin"])
        assert parts[0].first == 0 and parts[-1].last == len(toks) - 1, case["name"]
        assert all(a.last + 1 == b.first for a, b in zip(parts, parts[1:])), case["name"]
        if len(parts) == len(plain):  # không cắt
            assert [(u.first, u.last, u.pieces) for u in parts] == [(u.first, u.last, u.pieces) for u in plain], case["name"]
        else:
            assert len(parts) == len(plain) + 1, case["name"]
            assert [(u.first, u.last) for u in parts[2:]] == [(u.first, u.last) for u in plain[1:]], case["name"]


def test_the_rule_in_numbers():
    text = ("Mưa đã tạnh. Trời sáng dần lên. Những giọt nước còn đọng trên lá lấp lánh như những hạt ngọc. "
            "Con đường làng vắng lặng, chỉ có tiếng chim hót vọng lại từ phía bên kia đồi chè xanh ngắt. Họ lại lên đường.")
    toks, parts = supertonic.cut(text)
    head = len(parts[0].text(toks))
    assert len(parts) == 2 and supertonic.OPENING_MIN <= head <= supertonic.OPENING_MAX
    assert len(parts[1].text(toks)) >= supertonic.OPENING_TAIL
    assert parts[0].text(toks).endswith(".")  # ranh câu, không cắt giữa từ
    assert supertonic.cut("")[1] == []


def test_the_desktop_plan_for_a_stream_is_the_same_cut():
    provider = SupertonicProvider(lambda: None)
    text = json.loads(FIXTURE.read_bytes().decode("utf-8"))["cases"][1]["text"]
    toks, parts = local_stream.plan(provider, "F1", text, None, None)
    assert len(parts) == 2 and [(u.first, u.last) for u in parts] == [(u.first, u.last) for u in supertonic.cut(text)[1]]


def test_the_clip_key_carries_the_cut(monkeypatch):
    from abook.webui import supertonic_module

    assert supertonic_module.model_mark("other:x", "") == ""
    for tier in ("", "fast5"):
        supertonic_module._core._marks.clear()
        before = supertonic_module.model_mark("supertonic:F1", tier)
        monkeypatch.setattr(supertonic_module, "OPENING_CUT", supertonic.OPENING_CUT + 1)
        supertonic_module._core._marks.clear()
        assert supertonic_module.model_mark("supertonic:F1", tier) != before, tier
        monkeypatch.undo()
    supertonic_module._core._marks.clear()
