"""Thước F1 giọng (scripts/model_eval/voice_identity.py): người vô danh ĐÃ được đáp án soát là ai (`NPC*:<mô tả>`) là MỘT
người; chỉ `NPC*` trơn (đám đông, chưa soát) mới là "chưa biết ai cùng ai"."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "model_eval"))

from voice_identity import bcubed, gold_person  # noqa: E402


def test_gold_person_names_a_described_stranger_and_leaves_the_rest() -> None:
    assert gold_person(SimpleNamespace(speakers=(("NPC*", 1.0),), npc_label="Bà thầy bói")) == "NPC*:bà thầy bói"
    assert gold_person(SimpleNamespace(speakers=(("NPC*", 1.0),), npc_label="")) == "NPC*"
    assert gold_person(SimpleNamespace(speakers=(("KRAI", 1.0),), npc_label="")) == "KRAI"


def test_a_described_stranger_read_in_two_voices_is_a_split() -> None:
    """Nageki 62: bà thầy bói thành "Bà lão" và "Bà thầy bói" - người nghe nghe hai bà. Với `NPC*` trơn việc tách ấy
    không mất gì (không biết hai câu có cùng một người không); đã soát là một người thì mất độ phủ."""
    split = [("NPC*:bà thầy bói", "BÀ LÃO")] * 3 + [("NPC*:bà thầy bói", "BÀ THẦY BÓI")] * 3 + [("KRAI", "KRAI")] * 4
    unknown = [("NPC*" if gold.startswith("NPC*") else gold, voice) for gold, voice in split]
    assert bcubed(unknown)[1] == pytest.approx(1.0)
    assert bcubed(split)[1] == pytest.approx((6 * 0.5 + 4) / 10)


def test_one_intruding_line_costs_a_described_stranger_a_share_not_half() -> None:
    """Một câu của Krai lẫn vào giọng bà thầy bói: với `NPC*` trơn mỗi câu của bà chỉ còn độ chính xác 1/2 (câu vô danh không
    đỡ nhau); đã soát là một người thì 23/24 - đúng như B-cubed thường."""
    kept = [("NPC*:bà thầy bói", "BÀ THẦY BÓI")] * 23 + [("KRAI", "BÀ THẦY BÓI")] + [("KRAI", "KRAI")] * 12
    unknown = [("NPC*" if gold.startswith("NPC*") else gold, voice) for gold, voice in kept]
    expected = (23 * (23 / 24) + 1 * (1 / 24) + 12 * 1.0) / 36
    assert bcubed(kept)[0] == pytest.approx(expected)
    assert bcubed(unknown)[0] < bcubed(kept)[0]


def test_two_described_strangers_in_one_voice_are_a_merge() -> None:
    """LU 10: sếp và mẹ của Hayase là hai người - đọc chung một giọng là nhập."""
    merged = [("NPC*:sếp của hayase", "NGƯỜI LẠ")] * 4 + [("NPC*:mẹ hayase", "NGƯỜI LẠ")] * 4
    assert bcubed(merged)[0] == pytest.approx(0.5)
