import json

import pytest

from abook.webui.library import Preferences
from abook.webui.sync import remote_command


@pytest.mark.parametrize("stored", [{}, {"theme": "dark"}, *({"safetyStopHours": value} for value in ("bad", 0, 1, 2, 3))])
def test_removed_settings_are_ignored_and_cannot_request_a_timer_after_three_hours(tmp_path, stored):
    from abook.webui.library import DEFAULT_PREFERENCES, SLEEP_RANGES
    from abook.webui import library
    from unittest.mock import patch

    path = tmp_path / "preferences.json"
    original = json.dumps(stored)
    path.write_text(original, encoding="utf-8")
    prefs = Preferences(path)
    assert path.read_text(encoding="utf-8") == original
    with patch.object(library.time, "time", return_value=3 * 3600):
        settings = prefs.get()
        assert settings["sleepSchedule"] is None
        assert "safetyStopHours" not in settings
        assert "safetyStopHours" not in DEFAULT_PREFERENCES
        assert "safetyStopHours" not in SLEEP_RANGES
        assert "safetyStopHours" not in prefs.update({"safetyStopHours": 1})
    assert not list(tmp_path.glob("*.hong-*"))


@pytest.mark.parametrize("action", ["sleep", "setSleep", "extendSleep", "SLEEP_PLUS"])
def test_station_cannot_arm_the_phone_timer(action):
    with pytest.raises(ValueError):
        remote_command({"action": action, "minutes": 30})


def test_cast_timer_stays_an_explicit_supported_command():
    assert remote_command({"action": "sleep", "minutes": 30}, cast=True) == {"action": "sleep", "minutes": 30}
