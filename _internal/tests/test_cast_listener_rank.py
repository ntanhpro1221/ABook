"""Casting takes voices in the listener's order, and falls back to the arbitrary one only past it.

Nothing used to rank adult voices by quality: the most-speaking character always took the first unused
natural Northern preset in `CAST_ORDER`, which is alphabetical. `voice_rank.json` is the listener's ear;
`CAST_ORDER` only separates voices nobody has ranked.
"""

from __future__ import annotations

import json

import pytest

from abook import voice_catalog
from abook.character_registry import PresetAllocator
from abook.voice_catalog import LAST_RESORT_PRESETS, casting_presets

NARRATOR = "Phạm Tuyên"


def _rank(monkeypatch: pytest.MonkeyPatch, *, male=(), female=(), child_male=(), child_female=()) -> None:
    monkeypatch.setattr(
        voice_catalog,
        "VOICE_RANK",
        {
            "adult": {"male": tuple(male), "female": tuple(female)},
            "child": {"male": tuple(child_male), "female": tuple(child_female)},
        },
    )


def _picks(gender: str, count: int, *, age: str = "adult", narrator: str = NARRATOR) -> list[str]:
    """Casting order is line-count order, so the n-th call is the n-th most-speaking character."""
    allocator = PresetAllocator(narrator, 2)
    return [
        str(allocator.choose(gender, npc=False, age=age, who=f"P{index}")[0]["name"])
        for index in range(count)
    ]


def test_the_shipped_file_loads_and_names_only_real_presets() -> None:
    data = json.loads(voice_catalog.VOICE_RANK_PATH.read_text(encoding="utf-8"))
    assert set(data) == {"adult", "child"}
    assert voice_catalog.load_voice_rank()["child"]["female"][0] == "Ngọc Linh"


def test_a_name_the_catalog_does_not_know_fails_loudly(tmp_path) -> None:
    path = tmp_path / "voice_rank.json"
    path.write_bytes(
        json.dumps({"adult": {"male": ["Không Có"], "female": []}, "child": {"male": [], "female": []}}).encode()
    )
    with pytest.raises(ValueError, match="Không Có"):
        voice_catalog.load_voice_rank(path)


def test_a_preset_listed_twice_fails_loudly(tmp_path) -> None:
    path = tmp_path / "voice_rank.json"
    path.write_bytes(
        json.dumps(
            {"adult": {"male": ["Đức Trí", "Đức Trí"], "female": []}, "child": {"male": [], "female": []}}
        ).encode()
    )
    with pytest.raises(ValueError, match="twice"):
        voice_catalog.load_voice_rank(path)


def test_the_most_speaking_male_takes_the_best_ranked_voice_then_the_next(monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = _picks("male", 8)
    _rank(monkeypatch, male=("Đức Trí", "Quốc Tuấn"))
    picks = _picks("male", 8)
    assert picks[:2] == ["Đức Trí", "Quốc Tuấn"]
    # Past the ranked voices the old order carries on, untouched.
    assert picks[2:] == [name for name in baseline if name not in {"Đức Trí", "Quốc Tuấn"}][:6]
    assert len(set(picks)) == len(picks)


def test_the_most_speaking_female_takes_the_best_ranked_voice_then_the_next(monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = _picks("female", 6)
    _rank(monkeypatch, female=("Quỳnh Anh", "Kim Thanh"))
    picks = _picks("female", 6)
    assert picks[:2] == ["Quỳnh Anh", "Kim Thanh"]
    assert picks[2:] == [name for name in baseline if name not in {"Quỳnh Anh", "Kim Thanh"}][:4]


def test_variety_still_comes_before_the_ranking(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two characters never share a voice while an unused one exists, however well it is ranked."""
    _rank(monkeypatch, male=("Đức Trí",))
    picks = _picks("male", 5)
    assert picks.count("Đức Trí") == 1


def test_the_narrator_voice_is_never_given_to_a_character(monkeypatch: pytest.MonkeyPatch) -> None:
    _rank(monkeypatch, male=(NARRATOR, "Quốc Tuấn"), female=("Ngọc Linh",))
    assert NARRATOR not in _picks("male", 12)
    assert _picks("male", 1)[0] == "Quốc Tuấn"
    assert "Ngọc Linh" not in _picks("female", 12, narrator="Ngọc Linh")


def test_the_child_list_decides_among_presets_that_reach_the_child_pitch(monkeypatch: pytest.MonkeyPatch) -> None:
    _rank(monkeypatch, child_female=("Trúc Ly", "Đoan Trang", "Ngọc Linh"))
    assert _picks("female", 3, age="child") == ["Trúc Ly", "Đoan Trang", "Ngọc Linh"]
    _rank(monkeypatch, child_female=("Ngọc Linh", "Đoan Trang", "Trúc Ly"))
    assert _picks("female", 3, age="child") == ["Ngọc Linh", "Đoan Trang", "Trúc Ly"]


def test_the_shipped_child_data_is_the_old_hard_coded_preference() -> None:
    assert _picks("female", 1, age="child") == ["Ngọc Linh"]
    assert _picks("male", 1, age="child", narrator="Đức Trí") == ["Phạm Tuyên"]


def test_empty_adult_lists_leave_casting_exactly_as_it_was(monkeypatch: pytest.MonkeyPatch) -> None:
    """Until the listener ranks adults the change is neutral: the old order, voice for voice."""
    _rank(monkeypatch)
    assert _picks("male", 6) == ["Adam bựa", "Hải Đăng", "Quốc Tuấn", "Xuân Vĩnh", "Adam", "Thiền Tâm Đức"]
    assert _picks("female", 6) == ["Ngọc Huyền", "Trúc Ly", "Đoan Trang", "Ngọc Linh", "Quỳnh Anh", "Kim Thanh"]


@pytest.mark.parametrize("gender", ["male", "female"])
def test_no_arbitrary_order_sits_ahead_of_the_listeners_ranking(monkeypatch: pytest.MonkeyPatch, gender: str) -> None:
    """Rank the whole pool back to front of the arbitrary order; every pick must follow the ranking.

    A tie-break by name, region, style or `CAST_ORDER` placed ahead of `listener_rank` would put one of
    these voices out of place. Last-resort voices are demoted on purpose, before the ranking.
    """
    pool = [
        str(preset["name"])
        for preset in casting_presets(gender)
        if preset["name"] != NARRATOR and preset["name"] not in LAST_RESORT_PRESETS
    ]
    ranking = tuple(reversed(pool))
    _rank(monkeypatch, **{gender: ranking})
    assert _picks(gender, len(ranking)) == list(ranking)
