"""Lời báo lúc mở app, và file trạng thái hỏng thì GIỮ LẠI chứ không đè (soát a28).

Một file trạng thái của người dùng (tuỳ chọn, hồ sơ nghe, thiết bị đã ghép, khoá mã sách...) đọc lỗi thì trước đây app im lặng dùng mặc
định và lần ghi kế ĐÈ lên - chỗ nghe, dấu trang, cài đặt mất hẳn. Giờ: đổi tên bản hỏng thành `<tên>.hong-<YYYYmmdd-HHMMSS>` cạnh đó, ghi
một dòng vào `NOTICES` (cái gì, đã giữ bản cũ ở đâu), rồi mới dùng mặc định. Giao diện lấy các dòng ấy qua `/api/app` (`notices`) và báo
một lần lúc mở.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class Notices:
    """Các dòng báo của phiên này (mới nhất sau cùng, không trùng)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: list[dict[str, Any]] = []

    def add(self, text: str) -> None:
        with self._lock:
            if any(item["text"] == text for item in self._items):
                return
            self._items.append({"id": f"n{len(self._items) + 1}-{int(time.time())}", "text": text})
        log.warning("%s", text)

    def all(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._items]

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


NOTICES = Notices()


def keep_broken(path: Path, what: str, *, then: str = "app dùng mặc định") -> Path | None:
    """Đổi tên file hỏng thành `<tên>.hong-<giờ>` và báo một dòng; trả tên mới (None: không đổi tên được - vẫn báo)."""
    kept = path.with_name(f"{path.name}.hong-{time.strftime('%Y%m%d-%H%M%S')}")
    try:
        os.replace(path, kept)
    except OSError:
        log.warning("Không giữ được bản hỏng của %s", path, exc_info=True)
        NOTICES.add(f"{what} bị hỏng nên {then}. Chưa giữ được bản cũ ({path.name}) - đừng xoá nó nếu cần lấy lại.")
        return None
    NOTICES.add(f"{what} bị hỏng nên {then}. Bản cũ được giữ lại ở {kept.name}, cùng thư mục với {path.name}.")
    return kept


def read_json(path: Path, what: str, valid: Callable[[Any], bool] = lambda _data: True) -> Any:
    """Nội dung JSON của `path`; chưa có file hay không đọc được (quyền, ổ rời): None. Có mà hỏng (cắt nửa, rỗng, sai hình dạng theo
    `valid`): giữ bản hỏng (`keep_broken`) rồi None."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError:
        log.warning("Không đọc được %s", path, exc_info=True)
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError:  # gồm UnicodeDecodeError, JSONDecodeError
        keep_broken(path, what)
        return None
    if not valid(data):
        keep_broken(path, what)
        return None
    return data
