"""OS input evidence for the local listener. Unsupported/failed probes return unknown."""
from __future__ import annotations

import ctypes
import sys


def windows_idle_ms(user32, kernel32) -> int | None:
    class LastInputInfo(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint32), ("dwTime", ctypes.c_uint32)]

    value = LastInputInfo()
    value.cbSize = ctypes.sizeof(value)
    if not user32.GetLastInputInfo(ctypes.byref(value)):
        return None
    # Both are DWORD uptime counters. Subtract modulo 2**32 across the 49.7-day wrap.
    return (int(kernel32.GetTickCount()) - value.dwTime) & 0xFFFFFFFF


def system_idle_ms() -> int | None:
    if sys.platform != "win32":
        return None
    try:
        return windows_idle_ms(ctypes.windll.user32, ctypes.windll.kernel32)
    except (AttributeError, OSError):
        return None
