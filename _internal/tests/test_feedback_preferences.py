"""Âm thanh chạm và Nền đọc (Cài đặt > Giao diện) lưu như các cài đặt khác: mặc định bật / tự động, máy chủ chỉ nhận đúng giá trị hợp lệ."""
from __future__ import annotations

from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung


def test_touch_sounds_and_reading_surface_default_and_only_accept_their_values(studio) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    prefs = app.preferences.get()
    assert prefs["touchSounds"] is True and prefs["readingSurface"] == "auto"
    for broken in ("yes", 0, None):
        status, data = _call(server, "PUT", "/api/preferences", {"touchSounds": broken, "readingSurface": broken})
        assert status == 200 and data["touchSounds"] is True and data["readingSurface"] == "auto", broken
    status, data = _call(server, "PUT", "/api/preferences", {"touchSounds": False, "readingSurface": "ivory"})
    assert status == 200 and data["touchSounds"] is False and data["readingSurface"] == "ivory"
    assert app.preferences.get()["readingSurface"] == "ivory", "lưu lại cho lần mở sau"
