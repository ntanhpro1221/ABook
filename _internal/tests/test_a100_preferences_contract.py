"""Tuỳ chọn hẹn giờ ngủ khi ĐỌC file (soát a100 V2): lịch đêm sai cấu trúc, số âm, sai kiểu không được lọt qua bước nạp - trình phát
(`scheduleWindow`) tách "HH:mm" và hẹn theo các số ấy. Trường sai về mặc định RIÊNG trường ấy, các trường còn lại giữ nguyên; bản hỏng
được giữ lại và báo. PUT /api/preferences dùng cùng bảng giá trị (library.SLEEP_CHOICES, clean_sleep_schedule)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook.webui import notices
from abook.webui.library import DEFAULT_PREFERENCES, Preferences

GOOD = {"from": "22:00", "to": "06:00", "minutes": 30}


def _load(tmp_path: Path, stored: dict) -> tuple[Preferences, Path]:
    path = tmp_path / "preferences.json"
    path.write_text(json.dumps(stored), encoding="utf-8", newline="\n")
    return Preferences(path), path


@pytest.mark.parametrize("schedule", [
    {},
    {"from": 12, "to": "06:00", "minutes": 30},
    {"from": {"bad": 1}, "to": "06:00", "minutes": 30},
    {"from": "22:00", "to": "6:00", "minutes": 30},
    {"from": "24:00", "to": "06:00", "minutes": 30},
    {"from": "22:00", "to": "06:00", "minutes": -10},
    {"from": "22:00", "to": "06:00", "minutes": 20},
    {"from": "22:00", "to": "06:00", "minutes": True},
    {"from": "22:00", "to": "06:00"},
    [GOOD],
    "22:00",
    5,
])
def test_a_malformed_night_schedule_falls_back_to_none_and_the_other_fields_stay(tmp_path: Path, schedule) -> None:
    prefs, path = _load(tmp_path, {"sleepSchedule": schedule, "theme": "dark", "sleepFadeSeconds": 60})
    data = prefs.get()
    assert data["sleepSchedule"] is None
    assert data["theme"] == "dark" and data["sleepFadeSeconds"] == 60
    assert list(tmp_path.glob("preferences.json.hong-*")), "bản hỏng phải được giữ lại"
    assert json.loads(path.read_text(encoding="utf-8")).get("sleepSchedule") is None  # bản sạch đã ghi lại


def test_a_valid_night_schedule_is_kept_untouched(tmp_path: Path) -> None:
    prefs, _ = _load(tmp_path, {"sleepSchedule": GOOD})
    assert prefs.get()["sleepSchedule"] == GOOD
    assert not list(tmp_path.glob("preferences.json.hong-*"))


@pytest.mark.parametrize("key,value", [
    ("sleepFadeSeconds", -30), ("sleepFadeSeconds", 45), ("sleepFadeSeconds", True),
    ("sleepExtendMinutes", -10), ("sleepExtendMinutes", 0), ("sleepExtendMinutes", "10"),
    ("safetyStopHours", -1), ("safetyStopHours", 4), ("safetyStopHours", None),
    ("playbackRate", 0), ("playbackRate", 9), ("volume", -1), ("volume", 2),
])
def test_out_of_range_or_wrong_type_numbers_fall_back_to_their_own_default(tmp_path: Path, key: str, value) -> None:
    prefs, _ = _load(tmp_path, {key: value, "theme": "light"})
    data = prefs.get()
    assert data[key] == DEFAULT_PREFERENCES[key]
    assert data["theme"] == "light"
    assert list(tmp_path.glob("preferences.json.hong-*"))


@pytest.mark.parametrize("stored", [
    {"sleepFadeSeconds": 10, "sleepExtendMinutes": 5, "safetyStopHours": 0, "playbackRate": 0.5, "volume": 0.0},
    {"sleepFadeSeconds": 60, "sleepExtendMinutes": 15, "safetyStopHours": 3, "playbackRate": 3.0, "volume": 1.0},
    {"sleepSchedule": None},
])
def test_every_choice_the_interface_offers_is_accepted(tmp_path: Path, stored: dict) -> None:
    prefs, _ = _load(tmp_path, stored)
    data = prefs.get()
    assert all(data[key] == value for key, value in stored.items())
    assert not list(tmp_path.glob("preferences.json.hong-*"))


def test_the_server_put_and_the_loader_share_one_contract(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from abook.webui.server import Handler

    prefs = Preferences(tmp_path / "preferences.json")

    class Request:
        app = SimpleNamespace(preferences=prefs, library=SimpleNamespace(root=tmp_path), voices=lambda: [])

        def __init__(self, body: dict) -> None:
            self.body = body

        def _body(self) -> dict:
            return self.body

        def _send_json(self, status, value) -> None:
            self.reply = value

    Handler.put_preferences(Request({"sleepSchedule": {**GOOD, "extra": 1}, "sleepFadeSeconds": 60, "safetyStopHours": True}), {})
    stored = Preferences(prefs.path).get()
    assert stored["sleepSchedule"] == GOOD
    assert stored["sleepFadeSeconds"] == 60
    assert stored["safetyStopHours"] == DEFAULT_PREFERENCES["safetyStopHours"]  # bool không phải mức
    Handler.put_preferences(Request({"sleepSchedule": {"from": 12, "to": "06:00", "minutes": 30}, "sleepExtendMinutes": -10}), {})
    again = Preferences(prefs.path).get()
    assert again["sleepSchedule"] == GOOD and again["sleepExtendMinutes"] == DEFAULT_PREFERENCES["sleepExtendMinutes"]
    Handler.put_preferences(Request({"sleepSchedule": None}), {})
    assert Preferences(prefs.path).get()["sleepSchedule"] is None


def test_the_listener_is_told_a_broken_setting_was_kept(tmp_path: Path) -> None:
    notices.NOTICES.clear()
    _load(tmp_path, {"sleepSchedule": {}})
    assert any("cài đặt" in str(item) for item in notices.NOTICES.all())
    notices.NOTICES.clear()


def test_auto_rewind_is_a_per_machine_switch_on_by_default(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from abook.webui.server import Handler

    assert Preferences(tmp_path / "preferences.json").get()["autoRewind"] is True
    prefs = Preferences(tmp_path / "other.json")

    class Request:
        app = SimpleNamespace(preferences=prefs, library=SimpleNamespace(root=tmp_path), voices=lambda: [])

        def __init__(self, body: dict) -> None:
            self.body = body

        def _body(self) -> dict:
            return self.body

        def _send_json(self, status, value) -> None:
            self.reply = value

    Handler.put_preferences(Request({"autoRewind": False}), {})
    assert Preferences(prefs.path).get()["autoRewind"] is False
    Handler.put_preferences(Request({"autoRewind": "yes"}), {})  # không phải bool: bỏ qua
    assert Preferences(prefs.path).get()["autoRewind"] is False
    (tmp_path / "x").mkdir()
    reloaded, _ = _load(tmp_path / "x", {"autoRewind": "no"})
    assert reloaded.get()["autoRewind"] is True  # sai kiểu trong file: về mặc định
