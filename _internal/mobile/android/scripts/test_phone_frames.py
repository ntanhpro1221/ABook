"""Kiểm thử phần an toàn của phone_frames.py bằng bản dumpsys THẬT (cắt gọn, trong fixtures/): máy ảo API 36 khi có màn hình ảo scrcpy, và OPPO (Android 12, ColorOS).

    D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe -X utf8 -m pytest -rf _internal/mobile/android/scripts/test_phone_frames.py
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phone_frames as pf  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
APP = "com.ngdtuanh.abook.dev2"
SETTINGS = "com.android.settings"
VIRTUAL = 2  # số hiệu màn hình ảo trong các bản chụp


def fx(name):
    with open(os.path.join(HERE, "fixtures", name), encoding="utf-8") as f:
        return f.read()


def emu(case):
    return fx(f"emu36_{case}_activities.txt"), fx(f"emu36_{case}_windows.txt")


def test_app_on_top_and_focused_on_the_virtual_display_is_fine():
    assert pf.verdict(APP, VIRTUAL, *emu("ok")) is None


def test_another_app_on_the_same_virtual_display_is_refused():
    why = pf.verdict(APP, VIRTUAL, *emu("settings_on_virtual"))
    assert why and SETTINGS in why and f"màn hình {VIRTUAL}" in why


def test_our_app_only_on_the_real_display_does_not_count_for_the_virtual_one():
    acts, wins = emu("app_on_real_only")
    why = pf.verdict(APP, VIRTUAL, acts, wins)
    assert why and SETTINGS in why
    # ... và ngược lại: màn hình 0 đang có app của ta thì hợp lệ khi đo trên màn hình 0.
    assert pf.verdict(APP, 0, acts, wins) is None


def test_the_real_display_without_our_app_is_refused_when_measuring_display_0():
    why = pf.verdict(APP, 0, *emu("ok"))
    assert why and "launcher" in why.lower()


def test_a_display_that_does_not_exist_is_refused():
    assert pf.verdict(APP, 7, *emu("ok")) == "không thấy màn hình 7"


def test_focus_in_another_window_is_refused():
    acts, wins = emu("ok")
    lines = wins.splitlines()
    for i, ln in enumerate(lines):
        if "mCurrentFocus=Window" in ln and APP in ln:
            lines[i] = ln.replace(APP + "/vn.abook.player.ui.NativeActivity", "com.android.systemui/.RecentsActivity")
    why = pf.verdict(APP, VIRTUAL, acts, "\n".join(lines) + "\n")
    assert why and "tiêu điểm" in why and "systemui" in why


def test_no_focus_at_all_is_refused():
    acts, wins = emu("ok")
    lines = ["  mCurrentFocus=null" if "mCurrentFocus=Window" in ln and APP in ln else ln for ln in wins.splitlines()]
    why = pf.verdict(APP, VIRTUAL, acts, "\n".join(lines) + "\n")
    assert why and "không ai" in why


@pytest.mark.parametrize("mode", ["freeform", "pinned", "multi-window"])
def test_a_window_that_is_not_fullscreen_is_refused(mode):
    acts, wins = emu("ok")
    why = pf.verdict(APP, VIRTUAL, acts.replace("mode=fullscreen", f"mode={mode}"), wins)
    assert why and mode in why


def test_a_task_that_is_not_visible_is_refused():
    acts, wins = emu("ok")
    why = pf.verdict(APP, VIRTUAL, acts.replace("visible=true", "visible=false"), wins)
    assert why and "không hiện" in why


def test_oppo_android_12_format_mResumedActivity():
    acts, wins = fx("oppo12_settings_activities.txt"), fx("oppo12_settings_windows.txt")
    assert pf.verdict(SETTINGS, 0, acts, wins) is None
    why = pf.verdict(APP, 0, acts, wins)
    assert why and SETTINGS in why


def test_oppo_format_without_the_measured_app_on_top_is_refused_whatever_the_display_number():
    acts, wins = fx("oppo12_settings_activities.txt"), fx("oppo12_settings_windows.txt")
    assert pf.verdict(APP, 3, acts, wins) == "không thấy màn hình 3"


def test_section_returns_none_for_a_missing_display():
    acts, _ = emu("ok")
    assert pf.section(acts, pf.ACTIVITY_DISPLAY, 9) is None
    assert pf.section(acts, pf.ACTIVITY_DISPLAY, VIRTUAL) is not None


def test_virtual_display_period_is_read_from_that_display_not_the_real_one():
    dump = fx("emu36_display.txt")
    assert pf.display_hz(dump, VIRTUAL) == 60.0
    assert pf.display_hz(dump, 0) == pytest.approx(60.0, abs=0.01)
    assert pf.display_hz(dump, 9) is None
    # Màn hình ảo chạy 120 Hz trong khi màn hình thật 60 Hz: P theo màn hình ảo.
    faked = dump.replace('"scrcpy", displayId 2', '"scrcpy", displayId 2').replace("renderFrameRate 60.0,", "renderFrameRate 120.0,")
    assert pf.display_hz(faked, VIRTUAL) == 120.0
    assert pf.display_hz(faked, 0) == pytest.approx(60.0, abs=0.01)


class FakePhone(pf.Phone):
    """Phone không nối máy: `shell` trả bản chụp dumpsys định sẵn và ghi lại mọi lệnh."""

    def __init__(self, display, activities, windows, package=APP):
        self.package, self.display, self.sent = package, display, 0
        self.w, self.h = 1080, 2400
        self.activities, self.windows, self.log = activities, windows, []

    def shell(self, cmd):
        self.log.append(cmd)
        if cmd == "dumpsys activity activities":
            return self.activities
        if cmd == "dumpsys window displays":
            return self.windows
        return ""

    def inputs(self):
        return [c for c in self.log if c.startswith("input")]


def test_guard_stops_before_sending_the_input(monkeypatch):
    monkeypatch.setattr(pf.time, "sleep", lambda s: None)
    phone = FakePhone(VIRTUAL, *emu("settings_on_virtual"))
    with pytest.raises(pf.Unsafe):
        phone.tap((0.5, 0.5))
    with pytest.raises(pf.Unsafe):
        phone.back()
    with pytest.raises(pf.Unsafe):
        phone.swipe(0.5, 0.8, 0.5, 0.2, 100)
    assert phone.inputs() == [] and phone.sent == 0


def test_guard_lets_input_through_to_the_measured_display_only(monkeypatch):
    monkeypatch.setattr(pf.time, "sleep", lambda s: None)
    phone = FakePhone(VIRTUAL, *emu("ok"))
    phone.tap((0.5, 0.5))
    phone.back()
    phone.swipe(0.5, 0.8, 0.5, 0.2, 100)
    assert phone.sent == 3
    assert phone.inputs() == [f"input -d {VIRTUAL} tap 540 1200", f"input -d {VIRTUAL} keyevent KEYCODE_BACK", f"input -d {VIRTUAL} swipe 540 1920 540 480 100"]


def test_waking_never_touches_the_real_display_when_measuring_another_one(monkeypatch):
    monkeypatch.setattr(pf.time, "sleep", lambda s: None)
    phone = FakePhone(VIRTUAL, *emu("ok"))
    phone.wake_if_asleep()
    phone.awake()
    phone.nap(0.0)
    assert phone.log == []
