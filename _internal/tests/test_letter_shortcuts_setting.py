"""Phím tắt một chữ cái tắt được (WCAG 2.1.4, soát a31): Cài đặt > Phím tắt lưu như các cài đặt khác - mặc định bật như trước, máy
chủ chỉ nhận đúng true/false."""
from __future__ import annotations

from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung


def test_letter_shortcuts_are_on_by_default_and_only_a_boolean_turns_them_off(studio) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    assert app.preferences.get()["letterShortcuts"] is True
    for broken in ("tắt", 0, None, [False]):
        status, data = _call(server, "PUT", "/api/preferences", {"letterShortcuts": broken})
        assert status == 200 and data["letterShortcuts"] is True, broken
    status, data = _call(server, "PUT", "/api/preferences", {"letterShortcuts": False})
    assert status == 200 and data["letterShortcuts"] is False
    assert app.preferences.get()["letterShortcuts"] is False, "lưu lại cho lần mở sau"
