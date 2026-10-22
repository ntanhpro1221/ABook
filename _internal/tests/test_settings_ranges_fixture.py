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
            assert key in ("shakeAction", "shakeSensitivity"), f"{key} không có ở Python mà cũng không phải khoá riêng của điện thoại"


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
