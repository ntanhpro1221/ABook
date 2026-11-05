"""A child is cast from the female presets and read untouched.

The owner (05-11): "trẻ con thì dùng giọng của nữ đi, đừng bóp nữa, bóp đem đến âm thanh quá tệ". The age pitch
shift and the formant warp that used to carry a voice to a child are gone: a child, boy or girl, takes a female
preset ranked by the female character tiers, with age pitch 0 and formant 1.0. Teen and elderly are unchanged.
"""

from __future__ import annotations

import pytest

from abook import voice_catalog
from abook.character_registry import PresetAllocator
from abook.voice_catalog import (
    LAST_RESORT_PRESETS,
    VIENEU_PRESETS,
    age_pitch_semitones,
    casting_presets,
    formant_ratio_for_age,
    preset_age_reach,
    preset_by_name,
    preset_reaches_age_pitch,
    vocal_tract_target_cm,
)


def _child(gender: str, *, narrator: str = "Đức Trí") -> tuple[str, float, int]:
    preset, ratio, pitch = PresetAllocator(narrator, 2).choose(gender, npc=False, age="child", who="KID")
    return str(preset["name"]), float(ratio), int(pitch)


@pytest.mark.parametrize("gender", ["male", "female", "unknown"])
def test_a_child_gets_a_female_preset_with_no_pitch_shift_and_no_formant_warp(gender: str) -> None:
    name, ratio, pitch = _child(gender)
    assert preset_by_name(name)["gender"] == "female"
    assert pitch == 0
    assert ratio == 1.0


def test_the_first_child_takes_the_best_ranked_female_character_voice() -> None:
    assert _child("male")[0] == _child("female")[0] == "Ngọc Linh"


def test_children_follow_the_female_character_tiers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        voice_catalog,
        "VOICE_RANK",
        {
            "narrator": {"male": (), "female": ()},
            "character": {"male": (("Xuân Vĩnh",),), "female": (("Trúc Ly",), ("Quỳnh Anh",))},
        },
    )
    allocator = PresetAllocator("Đức Trí", 2)
    picks = [str(allocator.choose("male", npc=False, age="child", who=f"K{i}")[0]["name"]) for i in range(2)]
    assert picks == ["Trúc Ly", "Quỳnh Anh"]


def test_a_child_has_no_age_transform_at_all() -> None:
    assert vocal_tract_target_cm("child", "male") is None
    for preset in VIENEU_PRESETS:
        name, gender = str(preset["name"]), str(preset["gender"])
        assert age_pitch_semitones("child", gender, name) == 0
        assert formant_ratio_for_age(name, "child", gender) == 1.0
        assert preset_age_reach(name, "child", gender) == 0.0
        assert preset_reaches_age_pitch(name, "child", gender)


def test_teen_and_elderly_are_still_carried_toward_their_age() -> None:
    shifts = {age_pitch_semitones("teen", "male", str(p["name"])) for p in VIENEU_PRESETS if p["gender"] == "male"}
    assert shifts != {0}
    assert any(
        formant_ratio_for_age(str(p["name"]), "teen", str(p["gender"])) != 1.0 for p in VIENEU_PRESETS
    )
    assert any(age_pitch_semitones("elderly", "male", str(p["name"])) != 0 for p in VIENEU_PRESETS if p["gender"] == "male")


def test_several_children_and_female_leads_get_distinct_voices_while_any_are_free() -> None:
    """Tám preset nữ dùng được khi người kể là nam (bảy khi người kể là nữ)."""
    pool = len(casting_presets("female"))
    assert pool == 8
    allocator = PresetAllocator("Đức Trí", 2)
    ages = ["adult", "adult", "child", "adult", "child", "child", "adult", "child"]
    people = [f"P{index}" for index in range(len(ages))]
    for person in people:
        allocator.note_chapters(person, {1})
    picks = [
        allocator.choose("female", npc=False, age=age, who=person)
        for person, age in zip(people, ages, strict=True)
    ]
    names = [str(preset["name"]) for preset, _ratio, _pitch in picks]
    assert len(set(names)) == pool, names
    for (preset, ratio, pitch), age in zip(picks, ages, strict=True):
        if age == "child":
            assert (ratio, pitch) == (1.0, 0)
    assert LAST_RESORT_PRESETS.isdisjoint(names)


def test_a_child_is_never_warped_even_when_the_voices_run_out() -> None:
    allocator = PresetAllocator("Đức Trí", 2)
    for index in range(12):
        allocator.note_chapters(f"K{index}", {1})
    for index in range(12):
        _preset, ratio, pitch = allocator.choose("female", npc=False, age="child", who=f"K{index}")
        assert (ratio, pitch) == (1.0, 0)
