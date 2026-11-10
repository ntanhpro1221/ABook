"""Plugin pytest giả ổ đĩa THẬT của máy chạy test: `-p real_disk_plugin` với ABOOK_TEST_REAL_DISK_GB=<số GB trống>.

Nạp trước conftest, nên với bộ test nó đúng là "máy này còn ngần ấy chỗ": mọi `shutil.disk_usage` / `psutil.disk_usage`
chưa được fixture `_roomy_disk` (tests/conftest.py) che sẽ thấy số này. tests/test_disk_independent.py dùng nó để chạy lại
các bài cài Studio trên một máy còn 1 GB và một máy còn 100 GB.
"""
from __future__ import annotations

import os
import shutil
from collections import namedtuple

import psutil

_TOTAL = 1024 * 1024**3
_FREE = int(float(os.environ["ABOOK_TEST_REAL_DISK_GB"]) * 1024**3)
_ShutilUsage = namedtuple("usage", "total used free")
_PsutilUsage = namedtuple("sdiskusage", "total used free percent")

shutil.disk_usage = lambda _path: _ShutilUsage(_TOTAL, _TOTAL - _FREE, _FREE)
psutil.disk_usage = lambda _path: _PsutilUsage(_TOTAL, _TOTAL - _FREE, _FREE, round(100 * (_TOTAL - _FREE) / _TOTAL, 1))
