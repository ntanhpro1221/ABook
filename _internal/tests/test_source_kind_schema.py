"""Quote hints stay advisory; independent semantic constraints still share one schema rule."""

from __future__ import annotations

import pytest

from abook.analysis import (
    ALLOWED_KINDS,
    _allowed_kinds_by_id,
    _output_schema_for_batch,
    _source_kind_transition_rule,
)


def _row(stable_id: str, kind_hint: str) -> dict[str, str]:
    return {"stable_id": stable_id, "kind_hint": kind_hint, "text": "Một câu."}


def _branch(schema: dict, stable_id: str) -> dict:
    items = schema["properties"]["segments"]["items"]
    return next(
        branch
        for branch in items["oneOf"]
        if branch["properties"]["id"]["enum"] == [stable_id]
    )


def test_a_dialogue_hint_does_not_lock_kind():
    assert _allowed_kinds_by_id([_row("a", "dialogue")]) == {}


def test_a_thought_hint_does_not_lock_kind():
    assert _allowed_kinds_by_id([_row("a", "thought")]) == {}


def test_a_narration_hint_allows_actual_speech():
    assert _allowed_kinds_by_id([_row("a", "narration")]) == {}


def test_the_allowed_set_comes_from_the_rule_that_rejects_crossings() -> None:
    """Schema and check must not be able to disagree about where the boundary is."""
    for hint in ("dialogue", "thought", "narration"):
        row = _row("a", hint)
        derived = _allowed_kinds_by_id([row]).get("a", tuple(sorted(ALLOWED_KINDS)))
        for kind in ALLOWED_KINDS:
            rejected = _source_kind_transition_rule(row, kind) is not None
            assert rejected == (kind not in derived), (hint, kind)


def test_an_unrestricted_segment_is_left_alone():
    assert _allowed_kinds_by_id([_row("a", "narration")]) == {}


def test_the_schema_carries_the_constraint_per_segment() -> None:
    schema = _output_schema_for_batch(
        ["S000", "S001"],
        hard_kinds_by_id={"S000": ("dialogue",), "S001": ("narration", "thought")},
    )
    assert _branch(schema, "S000")["properties"]["kind"]["enum"] == ["dialogue"]
    assert _branch(schema, "S001")["properties"]["kind"]["enum"] == ["narration", "thought"]


def test_an_unconstrained_batch_keeps_the_flat_schema() -> None:
    """The branches cost 3.4x the schema size; they are only worth paying for a constraint."""
    schema = _output_schema_for_batch(["S000", "S001"])
    items = schema["properties"]["segments"]["items"]
    assert "oneOf" not in items
    assert items["properties"]["id"]["enum"] == ["S000", "S001"]


@pytest.mark.parametrize(
    "invalid",
    [
        {"S000": ()},
        {"S000": ("dialogue", "dialogue")},
        {"S000": ("shouting",)},
        {"S999": ("dialogue",)},
        {"S000": ["dialogue"]},
    ],
)
def test_an_invalid_constraint_is_refused_rather_than_shipped(invalid: dict) -> None:
    with pytest.raises(ValueError):
        _output_schema_for_batch(["S000", "S001"], hard_kinds_by_id=invalid)
