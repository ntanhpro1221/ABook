"""Bảng miền giá trị của các tuỳ chọn nghe (tests/fixtures/settings/ranges.json) khớp với bản Python (abook/webui/library.py). Hai bên kia đọc cùng file:
ui/src/listen/sleepRanges.test.ts (giao diện) và ListenPrefsRangesTest.kt (lõi Android)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from abook.webui import library
from abook.webui.library import DEFAULT_PREFERENCES

RANGES = json.loads((Path(__file__).parent / "fixtures" / "settings" / "ranges.json").read_text(encoding="utf-8"))


def test_the_choice_tables_match_the_shared_fixture() -> None:
    for key, spec in RANGES["choices"].items():
        if key in library.SLEEP_CHOICES:
            assert list(library.SLEEP_CHOICES[key]) == spec["values"], key
        elif key in library.CHOICES:
            assert list(library.CHOICES[key]) == spec["values"], key
        else:
            assert key == "shakeSensitivity", f"{key} không có ở Python mà cũng không phải khoá riêng của điện thoại"


def test_the_python_defaults_are_the_fixture_defaults() -> None:
    for key, spec in RANGES["choices"].items():
        if key in DEFAULT_PREFERENCES:
            assert DEFAULT_PREFERENCES[key] == spec["default"], key


def test_the_night_schedule_table_and_clock_match_the_fixture() -> None:
    assert list(library.SCHEDULE_MINUTES) == RANGES["schedule"]["minutes"]
    assert library._CLOCK.pattern == RANGES["schedule"]["clock"].replace("^", "").replace("$", "")
    for minutes in RANGES["schedule"]["minutes"]:
        assert library.clean_sleep_schedule({"from": "22:00", "to": "06:00", "minutes": minutes}) is not None
    assert library.clean_sleep_schedule({"from": "22:00", "to": "06:00", "minutes": max(RANGES["schedule"]["minutes"]) + 1}) is None
    assert re.fullmatch(RANGES["schedule"]["clock"], "23:59") and not re.fullmatch(RANGES["schedule"]["clock"], "24:00")


def test_the_music_level_range_is_one_source_and_clamps_at_both_ends(tmp_path: Path) -> None:
    from abook.webui import book_edits, music_mix, music_plan

    assert (music_plan.LEVEL_MIN_DB, music_plan.LEVEL_MAX_DB, music_plan.DEFAULT_LEVEL_DB, music_mix.MIX["levelStepDb"]) == (-40.0, -6.0, -20.0, 1.0)
    assert book_edits.LEVEL_RANGE == (music_plan.LEVEL_MIN_DB, music_plan.LEVEL_MAX_DB)
    for given, kept in RANGES["musicLevel"]["clamped"]:
        assert music_plan.clamp_level(float(given)) == kept, given
        assert music_plan.write_overrides(tmp_path, {"levelDb": given})["levelDb"] == kept, given
    for value, _label, _text in RANGES["musicLevel"]["labels"]:
        assert music_plan.LEVEL_MIN_DB <= value <= music_plan.LEVEL_MAX_DB
        assert music_plan.write_overrides(tmp_path, {"levelDb": value})["levelDb"] == value, "giữa miền thì giữ đúng số, kể cả nửa dB"
