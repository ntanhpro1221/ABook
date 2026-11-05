"""Casting takes voices in the listener's tiers, and falls back to the arbitrary order only past them.

Nothing used to rank adult voices by quality: the most-speaking character always took the first unused
natural Northern preset in `CAST_ORDER`, which is alphabetical. `voice_rank.json` is the listener's ear, per role
(narrator / character / child) and per gender, as a list of tiers; voices in one tier are equal to the listener, so a
tie falls through to the computed proxies and `CAST_ORDER`, which only separates voices nobody has ranked.
"""

from __future__ import annotations

import json

import pytest

from abook import config, voice_catalog
from abook.character_registry import PresetAllocator
from abook.voice_catalog import (
    DEFAULT_NARRATOR_BY_GENDER,
    LAST_RESORT_PRESETS,
    casting_presets,
    listener_rank,
    narrator_presets,
)

NARRATOR = "Phạm Tuyên"


def _rank(
    monkeypatch: pytest.MonkeyPatch,
    *,
    male=(),
    female=(),
    narrator_male=(),
    narrator_female=(),
) -> None:
    def tiers(rows) -> tuple[tuple[str, ...], ...]:
        return tuple(tuple(row) for row in rows)

    monkeypatch.setattr(
        voice_catalog,
        "VOICE_RANK",
        {
            "narrator": {"male": tiers(narrator_male), "female": tiers(narrator_female)},
            "character": {"male": tiers(male), "female": tiers(female)},
        },
    )


def _picks(gender: str, count: int, *, age: str = "adult", narrator: str = NARRATOR) -> list[str]:
    """Casting order is line-count order, so the n-th call is the n-th most-speaking character."""
    allocator = PresetAllocator(narrator, 2)
    return [
        str(allocator.choose(gender, npc=False, age=age, who=f"P{index}")[0]["name"])
        for index in range(count)
    ]


def _write(tmp_path, table: dict) -> object:
    path = tmp_path / "voice_rank.json"
    path.write_bytes(json.dumps(table).encode())
    return path


def _table(**roles) -> dict:
    base = {role: {"male": [], "female": []} for role in ("narrator", "character")}
    base.update(roles)
    return base


# --- the file ------------------------------------------------------------------------------------------------------


def test_the_shipped_file_loads_in_tiers_and_names_only_real_presets() -> None:
    data = json.loads(voice_catalog.VOICE_RANK_PATH.read_text(encoding="utf-8"))
    assert set(data) == {"narrator", "character"}
    table = voice_catalog.load_voice_rank()
    assert table["character"]["female"][0] == ("Đoan Trang",)


def test_the_shipped_file_is_the_owners_male_verdict() -> None:
    table = voice_catalog.load_voice_rank()
    assert table["character"]["male"][0] == ("Xuân Vĩnh",)
    assert set(table["narrator"]["male"][0]) == {"Đức Trí", "Thiền Tâm Đức"}
    assert [set(tier) for tier in table["narrator"]["male"]] == [
        {"Đức Trí", "Thiền Tâm Đức"},
        {"Phạm Tuyên", "Xuân Vĩnh"},
        {"Thái Sơn", "Adam"},
    ]
    assert [set(tier) for tier in table["character"]["male"]] == [
        {"Xuân Vĩnh"},
        {"Đức Trí", "Thiền Tâm Đức", "Phạm Tuyên"},
        {"Thái Sơn", "Adam"},
    ]


def test_a_name_the_catalog_does_not_know_fails_loudly(tmp_path) -> None:
    path = _write(tmp_path, _table(character={"male": [["Không Có"]], "female": []}))
    with pytest.raises(ValueError, match="Không Có"):
        voice_catalog.load_voice_rank(path)


def test_a_preset_listed_twice_in_a_role_fails_loudly(tmp_path) -> None:
    path = _write(tmp_path, _table(character={"male": [["Đức Trí"], ["Quốc Tuấn", "Đức Trí"]], "female": []}))
    with pytest.raises(ValueError, match="twice"):
        voice_catalog.load_voice_rank(path)


def test_an_empty_tier_fails_loudly(tmp_path) -> None:
    path = _write(tmp_path, _table(narrator={"male": [["Đức Trí"], []], "female": []}))
    with pytest.raises(ValueError, match="empty tier"):
        voice_catalog.load_voice_rank(path)


def test_the_same_preset_may_appear_in_different_roles(tmp_path) -> None:
    path = _write(
        tmp_path,
        _table(
            narrator={"male": [["Đức Trí"]], "female": []},
            character={"male": [["Đức Trí"]], "female": []},
        ),
    )
    assert voice_catalog.load_voice_rank(path)["narrator"]["male"] == (("Đức Trí",),)


# --- listener_rank ---------------------------------------------------------------------------------------------------


def test_listener_rank_is_the_tier_index_and_unranked_is_the_tier_count(monkeypatch: pytest.MonkeyPatch) -> None:
    _rank(monkeypatch, male=[["Xuân Vĩnh"], ["Đức Trí", "Phạm Tuyên"]], narrator_male=[["Đức Trí"]])
    assert listener_rank("Xuân Vĩnh", "male") == 0
    assert listener_rank("Đức Trí", "male") == listener_rank("Phạm Tuyên", "male") == 1
    assert listener_rank("Adam bựa", "male") == 2
    assert listener_rank("Đức Trí", "male", role="narrator") == 0
    assert listener_rank("Phạm Tuyên", "male", role="narrator") == 1
    assert listener_rank("Ngọc Huyền", "female") == 0  # no tiers: everything unranked equally


# --- casting ---------------------------------------------------------------------------------------------------------


def test_the_most_speaking_male_takes_the_best_tier_then_the_next(monkeypatch: pytest.MonkeyPatch) -> None:
    _rank(monkeypatch)  # the old order, with nothing ranked
    baseline = _picks("male", 8)
    _rank(monkeypatch, male=[["Đức Trí"], ["Quốc Tuấn"]])
    picks = _picks("male", 8)
    assert picks[:2] == ["Đức Trí", "Quốc Tuấn"]
    # Past the ranked voices the old order carries on, untouched.
    assert picks[2:] == [name for name in baseline if name not in {"Đức Trí", "Quốc Tuấn"}][:6]
    assert len(set(picks)) == len(picks)


def test_the_most_speaking_female_takes_the_best_tier_then_the_next(monkeypatch: pytest.MonkeyPatch) -> None:
    _rank(monkeypatch)  # the old order, with nothing ranked
    baseline = _picks("female", 6)
    _rank(monkeypatch, female=[["Quỳnh Anh"], ["Kim Thanh"]])
    picks = _picks("female", 6)
    assert picks[:2] == ["Quỳnh Anh", "Kim Thanh"]
    assert picks[2:] == [name for name in baseline if name not in {"Quỳnh Anh", "Kim Thanh"}][:4]


def test_voices_in_one_tier_are_equal_so_the_proxies_and_the_old_order_break_the_tie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _rank(monkeypatch)  # the old order, with nothing ranked
    baseline = list(dict.fromkeys(_picks("male", 11)))
    tier = ["Đức Trí", "Quốc Tuấn", "Hải Đăng"]
    _rank(monkeypatch, male=[tier])
    picks = _picks("male", 3)
    assert set(picks) == set(tier)
    assert picks == [name for name in baseline if name in tier]


def test_variety_still_comes_before_the_ranking(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two characters never share a voice while an unused one exists, however well it is ranked."""
    _rank(monkeypatch, male=[["Đức Trí"]])
    picks = _picks("male", 5)
    assert picks.count("Đức Trí") == 1


def test_the_narrator_voice_is_never_given_to_a_character(monkeypatch: pytest.MonkeyPatch) -> None:
    _rank(monkeypatch, male=[[NARRATOR], ["Quốc Tuấn"]], female=[["Ngọc Linh"]])
    assert NARRATOR not in _picks("male", 12)
    assert _picks("male", 1)[0] == "Quốc Tuấn"
    assert "Ngọc Linh" not in _picks("female", 12, narrator="Ngọc Linh")


def test_the_shipped_male_verdict_decides_who_the_characters_get() -> None:
    """Narrator Đức Trí: Xuân Vĩnh first, then Thiền Tâm Đức and Phạm Tuyên in some order, then the third tier."""
    picks = _picks("male", 5, narrator="Đức Trí")
    assert picks[0] == "Xuân Vĩnh"
    assert set(picks[1:3]) == {"Thiền Tâm Đức", "Phạm Tuyên"}
    assert set(picks[3:5]) == {"Thái Sơn", "Adam"}
    assert "Adam bựa" not in picks


def test_only_thanh_binh_is_still_a_last_resort() -> None:
    assert LAST_RESORT_PRESETS == {"Thanh Bình"}


def test_the_shipped_female_verdict_decides_who_the_characters_get() -> None:
    picks = _picks("female", 8, narrator="Mỹ Duyên")
    assert picks[:2] == ["Đoan Trang", "Ngọc Linh"]
    assert picks[2] == "Mai Anh"
    assert set(picks[3:6]) == {"Kim Thanh", "Quỳnh Anh", "Thục Đoan"}
    assert set(picks[6:8]) == {"Ngọc Huyền", "Trúc Ly"}


def test_the_cross_gender_fallback_uses_the_same_news_eligibility(monkeypatch) -> None:
    allocator = PresetAllocator(NARRATOR, 2)
    allocator.not_for_characters = frozenset(p["name"] for p in voice_catalog.VIENEU_PRESETS
                                            if p["name"] not in {"Mai Anh", "Thùy Dung", "Minh Đức", "Minh Triết"})
    assert allocator.choose("male", npc=False, age="adult", who="P")[0]["name"] == "Mai Anh"
    _rank(monkeypatch)
    allocator.not_for_characters -= {"Ngọc Linh"}
    assert allocator.choose("male", npc=True, age="adult", who="Q")[0]["name"] == "Ngọc Linh"


def test_empty_lists_leave_casting_exactly_as_it_was(monkeypatch: pytest.MonkeyPatch) -> None:
    """With nothing ranked the change is neutral: the old order, voice for voice."""
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
    ranking = [[name] for name in reversed(pool)]
    _rank(monkeypatch, **{gender: ranking})
    assert _picks(gender, len(ranking)) == [tier[0] for tier in ranking]


# --- the narrator ----------------------------------------------------------------------------------------------------


def test_the_default_narrator_is_in_the_top_narrator_tier() -> None:
    """Edit the default or the narrator tiers without the other and this fails."""
    table = voice_catalog.load_voice_rank()
    for gender in ("male", "female"):
        assert DEFAULT_NARRATOR_BY_GENDER[gender] in table["narrator"][gender][0]
        assert DEFAULT_NARRATOR_BY_GENDER[gender] in {preset["name"] for preset in narrator_presets(gender)}
    assert DEFAULT_NARRATOR_BY_GENDER["male"] == "Đức Trí"
    assert DEFAULT_NARRATOR_BY_GENDER["female"] == "Mai Anh"


def test_a_ranked_news_voice_narrates_and_is_cast_in_its_character_tier() -> None:
    """Metadata tin tức không phủ quyết phán quyết theo vai của chủ sách."""
    news = {str(p["name"]) for p in voice_catalog.VIENEU_PRESETS if p["style"] == voice_catalog.STYLE_NEWS}
    assert "Mai Anh" in news
    assert narrator_presets("female")[0]["name"] == "Mai Anh"
    assert config.build_settings(overrides={"voices": {"narrator_voice": "Mai Anh"}})["voices"]["narrator_gender"] == "female"
    assert _picks("female", 3) == ["Đoan Trang", "Ngọc Linh", "Mai Anh"]
    for name in news - {"Mai Anh"}:
        assert name not in {p["name"] for p in narrator_presets()}
        assert name not in {p["name"] for gender in ("male", "female") for p in casting_presets(gender)}
        with pytest.raises(ValueError, match="Unsupported narrator voice"):
            config.build_settings(overrides={"voices": {"narrator_voice": name}})


@pytest.mark.parametrize("role", ["narrator", "character"])
def test_a_news_voice_is_only_opened_for_the_role_ranked(monkeypatch, role) -> None:
    _rank(monkeypatch, **{"narrator_female" if role == "narrator" else "female": [["Mai Anh"]]})
    preset = voice_catalog.preset_by_name("Mai Anh")
    assert voice_catalog.preset_eligible(preset, role)
    assert not voice_catalog.preset_eligible(preset, "character" if role == "narrator" else "narrator")
    assert ("Mai Anh" in {p["name"] for p in narrator_presets("female")}) == (role == "narrator")
    assert ("Mai Anh" in {p["name"] for p in casting_presets("female")}) == (role == "character")


def test_new_projects_start_with_the_default_narrator() -> None:
    assert config.build_settings("balanced")["voices"]["narrator_voice"] == DEFAULT_NARRATOR_BY_GENDER["male"]


def test_the_narrator_list_follows_the_owners_tiers_after_the_default() -> None:
    names = [str(preset["name"]) for preset in narrator_presets("male")]
    assert names[0] == "Đức Trí"
    assert names[1] == "Thiền Tâm Đức"
    assert set(names[2:4]) == {"Phạm Tuyên", "Xuân Vĩnh"}
    assert set(names[4:6]) == {"Thái Sơn", "Adam"}
    women = [str(preset["name"]) for preset in narrator_presets("female")]
    assert women[:3] == ["Mai Anh", "Đoan Trang", "Ngọc Linh"]
    assert set(women[3:7]) == {"Kim Thanh", "Mỹ Duyên", "Quỳnh Anh", "Thục Đoan"}


def test_narrator_tiers_are_read_by_each_presets_own_gender(monkeypatch: pytest.MonkeyPatch) -> None:
    _rank(monkeypatch, narrator_female=[["Quỳnh Anh"]], narrator_male=[["Quốc Tuấn"]])
    everyone = [str(preset["name"]) for preset in narrator_presets()]
    rest = [name for name in everyone if name not in {DEFAULT_NARRATOR_BY_GENDER["male"], DEFAULT_NARRATOR_BY_GENDER["female"]}]
    assert set(rest[:2]) == {"Quỳnh Anh", "Quốc Tuấn"}
