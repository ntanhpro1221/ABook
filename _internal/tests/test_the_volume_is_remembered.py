"""Âm lượng nhớ qua các lần mở app (soát UX 29-09: đặt 15% rồi mở lại thành 90% - app nghe trước khi ngủ mà lần sau phát to
đột ngột): giao diện lưu vào tuỳ chọn, và máy chủ chỉ nhận một SỐ trong khoảng hợp lệ - trình phát nạp lại nó lúc mở app."""
from __future__ import annotations

from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung


def test_a_volume_is_kept_and_a_broken_one_is_not(studio) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    status, data = _call(server, "PUT", "/api/preferences", {"volume": 0.15, "playbackRate": 1.5})
    assert status == 200 and data["volume"] == 0.15 and data["playbackRate"] == 1.5
    for broken in ("loud", 5, -1, True, None):
        _call(server, "PUT", "/api/preferences", {"volume": broken, "playbackRate": broken})
    assert (app.preferences.get()["volume"], app.preferences.get()["playbackRate"]) == (0.15, 1.5)
    status, data = _call(server, "GET", "/api/app")
    assert status == 200 and data["volume"] == 0.15, "lần mở sau trình phát nạp đúng mức đã lưu"
