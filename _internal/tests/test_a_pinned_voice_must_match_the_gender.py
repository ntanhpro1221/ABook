"""A pinned voice survives unless its preset is the wrong gender for the person; a female preset fits any child.

This file used to hold a second rule, "a voice carrying the child pitch is dropped for a pinned adult". Children are no
longer pitch-shifted (05-11), so no voice carries that pitch and the rule is gone; what is left is the gender rule.
"""
from __future__ import annotations

from abook.character_registry import _drop_pins_that_contradict_a_person


class _Events:
    def __init__(self) -> None:
        self.rows: list[tuple] = []

    def event(self, level: str, code: str, message: str, detail: dict) -> None:
        self.rows.append((level, code, message, detail))


def test_a_pinned_man_loses_a_womans_voice() -> None:
    events = _Events()
    logs: list[str] = []
    kept = _drop_pins_that_contradict_a_person(
        events,
        {"IVAN": "vieneu@3.8.3/Ngọc Linh"},
        {"IVAN": "male"},
        {"IVAN": "adult"},
        logs.append,
    )
    assert kept == {}
    assert events.rows and events.rows[0][1] == "CASTING_PIN_CONTRADICTS_A_PERSON"


def test_a_pinned_child_keeps_a_female_preset_even_as_a_boy() -> None:
    """Chủ sách 05-11: "trẻ con thì dùng giọng của nữ đi" - cả bé trai."""
    events = _Events()
    kept = _drop_pins_that_contradict_a_person(
        events,
        {"EVERAN": "vieneu@3.8.3/Ngọc Linh"},
        {"EVERAN": "male"},
        {"EVERAN": "child"},
        lambda line: None,
    )
    assert kept == {"EVERAN": "vieneu@3.8.3/Ngọc Linh"}
    assert events.rows == []


def test_a_pinned_boy_keeps_a_male_preset_someone_chose() -> None:
    kept = _drop_pins_that_contradict_a_person(
        _Events(),
        {"EVERAN": "vieneu@3.8.3/Thái Sơn"},
        {"EVERAN": "male"},
        {"EVERAN": "child"},
        lambda line: None,
    )
    assert kept == {"EVERAN": "vieneu@3.8.3/Thái Sơn"}


def test_a_pinned_girl_loses_a_male_preset() -> None:
    logs: list[str] = []
    kept = _drop_pins_that_contradict_a_person(
        _Events(),
        {"MIA": "vieneu@3.8.3/Thái Sơn"},
        {"MIA": "female"},
        {"MIA": "child"},
        logs.append,
    )
    assert kept == {}
    assert logs


def test_an_adult_voice_for_a_pinned_adult_is_untouched() -> None:
    kept = _drop_pins_that_contradict_a_person(
        _Events(),
        {"NATASHA": "vieneu@3.8.3/Ngọc Linh"},
        {"NATASHA": "female"},
        {"NATASHA": "adult"},
        lambda line: None,
    )
    assert kept == {"NATASHA": "vieneu@3.8.3/Ngọc Linh"}


def test_nobody_pinned_an_age_so_nothing_is_dropped() -> None:
    kept = _drop_pins_that_contradict_a_person(
        _Events(),
        {"AI": "vieneu@3.8.3/Ngọc Linh"},
        {},
        {},
        lambda line: None,
    )
    assert kept == {"AI": "vieneu@3.8.3/Ngọc Linh"}, "không ai ghim thì không kết tội"
