"""Tạm dừng tạo sách khi máy tính xách tay rút sạc (supervisor của `background_runner` hỏi mỗi vài giây).

Trên pin, card đồ hoạ bị hạ công suất (máy chủ sách 29-09: 15 W, việc GPU chậm ~15 lần) - làm tiếp chỉ hao pin mà không ra
việc. Tạm dừng dùng đúng cơ chế `pause_requested` của dây chuyền: tiến trình vẫn sống, dừng ở checkpoint kế tiếp và làm
tiếp ĐÚNG chỗ ấy khi cắm sạc lại - khác với "Dừng" (lần chạy sau đọc lại trạng thái, giữa pha phân tích là ra một quyển
sách khác: AGENTS.md). Pin cạn thì Windows ngủ đông, tiến trình đang tạm dừng sống qua được.

Rút sạc một chốc (cắm lại dây, đổi ổ điện) không đáng dừng: chỉ tạm dừng sau `GRACE_SECONDS` chạy pin liên tục; cắm lại là
làm tiếp ngay. Người dùng tắt được ở Cài đặt (`pauseOnBattery` trong preferences.json của app), hay bấm "Tiếp tục" để làm
tiếp trên pin một lần (hết hiệu lực khi máy lại thấy sạc).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import psutil

GRACE_SECONDS = 60.0
PREFERENCE_KEY = "pauseOnBattery"


def on_battery() -> bool | None:
    """True khi máy đang chạy pin, False khi đang cắm sạc hay không có pin (máy bàn), None khi không biết."""
    return _windows_on_battery() if os.name == "nt" else _psutil_on_battery()


def _psutil_on_battery() -> bool | None:
    try:
        battery = psutil.sensors_battery()
    except Exception:  # noqa: BLE001 - driver pin lạ không được làm hỏng việc tạo sách
        return None
    if battery is None:
        return False
    if battery.power_plugged is None:
        return None
    return not battery.power_plugged


def _windows_on_battery() -> bool | None:
    """GetSystemPowerStatus: ACLineStatus 0 = chạy pin, 1 = cắm sạc, 255 = không biết. psutil gộp 255 vào "chạy pin"
    (power_plugged = ACLineStatus == 1) - máy báo "không biết" sẽ tạm dừng sau 60 giây mọi lượt (soát QA 29-09)."""
    import ctypes
    from ctypes import wintypes

    class Status(ctypes.Structure):
        _fields_ = [("ACLineStatus", wintypes.BYTE), ("BatteryFlag", wintypes.BYTE),
                    ("BatteryLifePercent", wintypes.BYTE), ("SystemStatusFlag", wintypes.BYTE),
                    ("BatteryLifeTime", wintypes.DWORD), ("BatteryFullLifeTime", wintypes.DWORD)]

    status = Status()
    try:
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            return None
    except (AttributeError, OSError):
        return None
    return _from_status(status.ACLineStatus & 0xFF, status.BatteryFlag & 0xFF)


def _from_status(line: int, flag: int) -> bool | None:
    if flag != 0xFF and flag & 128:  # không có pin (máy bàn)
        return False
    return {0: True, 1: False}.get(line)


def _preferences_path() -> Path:
    # Cùng chỗ với webui.library.preferences_path (không nhập webui vào supervisor: chỉ cần đọc một khoá).
    override = os.environ.get("EBOOK_READER_PREFERENCES")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return Path.home() / ".ebook_reader" / "preferences.json"
    return Path(base) / "ABook" / "preferences.json"


_last_setting: bool | None = None


def pause_on_battery_enabled() -> bool:
    """Tuỳ chọn của app; thiếu file hay khoá (CLI, máy chưa mở app) thì bật. Đọc lỗi thoáng qua (file đang được ghi đè)
    thì giữ giá trị đọc được lần trước - không để người đã tắt tuỳ chọn thấy sách khựng vài giây (soát QA 29-09)."""
    global _last_setting
    path = _preferences_path()
    if not path.exists():
        _last_setting = True
        return True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True if _last_setting is None else _last_setting
    value = data.get(PREFERENCE_KEY, True) if isinstance(data, dict) else True
    _last_setting = value is not False
    return _last_setting


class BatteryWatch:
    """Nhớ từ lúc nào máy chạy pin; `wants_pause` sau `grace` giây liên tục. Thời gian là đồng hồ đơn điệu của người gọi."""

    def __init__(self, grace: float | None = None) -> None:
        self.grace = GRACE_SECONDS if grace is None else grace
        self.since: float | None = None
        # Lần cuối thấy sạc (đồng hồ tường): yêu cầu "làm tiếp trên pin" chỉ có hiệu lực cho lần rút sạc sau nó.
        self.last_plugged_wall: float | None = None

    def update(self, battery: bool | None, now: float, wall: float) -> bool:
        if battery is None:
            # Không đọc được: giữ nguyên nhận định cũ (một lần đọc lỗi không được làm sách chạy tiếp trên pin).
            return self.since is not None and now - self.since >= self.grace
        if not battery:
            self.since = None
            self.last_plugged_wall = wall
            return False
        if self.since is None:
            self.since = now
        return now - self.since >= self.grace
