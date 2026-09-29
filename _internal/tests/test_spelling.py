"""Phụ âm đầu viết lại theo chính tả tiếng Việt cho lời gợi ý khi một cách đọc bị từ chối (webui/spelling.py)."""

from __future__ import annotations

import pytest

from ebook_reader.listener_overrides import pronunciation_problem
from ebook_reader.webui.spelling import respelled, respelling_note


@pytest.mark.parametrize(
    ("typed", "fixed"),
    [
        ("Hên-kơ", "Hên-cơ"),  # k trước ơ -> c (soát UX 29-09: "Hên-kơ" cho Hailkes bị từ chối)
        ("Ka-ra", "Ca-ra"),
        ("Ngê", "Nghê"),  # ng trước ê -> ngh
        ("Nghà-ra", "Ngà-ra"),  # ngh trước a (dấu thanh không che nguyên âm gốc) -> ng
        ("Ci-ra", "Ki-ra"),  # c trước i -> k
        ("Ghô-ra", "Gô-ra"),
        ("Ge-ra", "Ghe-ra"),
    ],
)
def test_the_initial_consonant_is_respelled_before_the_vowel_it_meets(typed: str, fixed: str) -> None:
    assert respelled(typed) == fixed


@pytest.mark.parametrize("typed", ["Gi-a", "Khan", "Chi", "Kên", "Kỳ", "Hên-khơ", "Nhi"])
def test_valid_initials_and_digraphs_are_left_alone(typed: str) -> None:
    """"gi", "kh", "ch", "nh" là phụ âm đầu riêng: không đọc "gi" thành "g" + "i"."""
    assert respelled(typed) == typed


def test_the_note_names_the_syllable_and_the_suggestion_passes_the_same_check() -> None:
    fixed = respelled("Hên-kơ-xơ")
    assert fixed == "Hên-cơ-xơ"
    assert respelling_note("Hên-kơ-xơ", fixed) == "Tiếng Việt viết “cơ”, không viết “kơ”."
    assert pronunciation_problem("Hailkes", "Hên-kơ-xơ") is not None
    assert pronunciation_problem("Hailkes", fixed) is None


def test_nothing_to_respell_gives_no_note() -> None:
    assert respelled("Xờ-taiu") == "Xờ-taiu"
    assert respelling_note("Xờ-taiu", "Xờ-taiu") == ""
