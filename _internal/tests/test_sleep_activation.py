"""Automatic sleep requires a chosen setting, including after loading preferences."""
import json

import pytest

from abook.webui.library import Preferences
from abook.webui.sync import remote_command


@pytest.mark.parametrize("stored", [{}, {"theme": "dark"}, {"safetyStopHours": "bad"}])
def test_unselected_or_invalid_safety_does_not_enable_sleep(tmp_path, stored):
    path = tmp_path / "preferences.json"
    path.write_text(json.dumps(stored), encoding="utf-8")
    settings = Preferences(path).get()
    assert settings["safetyStopHours"] == 0
    assert settings["sleepSchedule"] is None


@pytest.mark.parametrize("hours", [0, 1, 2, 3])
def test_saved_explicit_safety_choice_is_preserved(tmp_path, hours):
    path = tmp_path / "preferences.json"
    path.write_text(json.dumps({"safetyStopHours": hours}), encoding="utf-8")
    assert Preferences(path).get()["safetyStopHours"] == hours


@pytest.mark.parametrize("action", ["sleep", "setSleep", "extendSleep", "SLEEP_PLUS"])
def test_station_cannot_arm_the_phone_timer(action):
    with pytest.raises(ValueError):
        remote_command({"action": action, "minutes": 30})


def test_cast_timer_stays_an_explicit_supported_command():
    assert remote_command({"action": "sleep", "minutes": 30}, cast=True) == {"action": "sleep", "minutes": 30}
