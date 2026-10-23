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
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class Notices:
    """Các dòng báo của phiên này (mới nhất sau cùng, không trùng)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: list[dict[str, Any]] = []

    def add(self, text: str, *, kind: str = "warning", preserved_file: str | None = None) -> None:
        with self._lock:
            if any(item["text"] == text for item in self._items):
                return
            self._items.append({"id": f"n{len(self._items) + 1}-{int(time.time())}", "text": text,
                                "kind": kind, "at": int(time.time() * 1000),
                                **({"preservedFile": preserved_file} if preserved_file else {})})
        log.warning("%s", text)

    def all(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._items]

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def diagnostics(self) -> dict[str, Any]:
        """Recovery metadata only: never include the original notice/profile text."""
        rows = self.all()
        return {"savingBlocked": any(row["kind"] == "saving-blocked" for row in rows),
                "notices": [{key: row[key] for key in ("kind", "at", "preservedFile") if key in row}
                            for row in rows[-200:]]}


NOTICES = Notices()


def keep_broken(path: Path, what: str, *, then: str = "app dùng mặc định", copy_only: bool = False) -> Path | None:
    """Đổi tên file hỏng thành `<tên>.hong-<giờ>` và báo một dòng; trả tên mới (None: không đổi tên được - vẫn báo)."""
    kept = path.with_name(f"{path.name}.hong-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}")
    try:
        if copy_only:
            with path.open("rb") as source, kept.open("xb") as target:
                import shutil
                shutil.copyfileobj(source, target)
                target.flush()
                os.fsync(target.fileno())
        else:
            os.replace(path, kept)
    except OSError:
        log.warning("Không giữ được bản hỏng của %s", path, exc_info=True)
        NOTICES.add(f"{what} bị hỏng nên {then}. Chưa giữ được bản cũ ({path.name}) - đừng xoá nó nếu cần lấy lại.", kind="saving-blocked")
        return None
    NOTICES.add(f"{what} bị hỏng nên {then}. Bản cũ được giữ lại ở {kept.name}, cùng thư mục với {path.name}.",
                kind="recovered", preserved_file=kept.name)
    return kept


class Unreadable(OSError):
    """File trạng thái CÓ trên đĩa mà không đọc được (chương trình khác giữ - diệt virus, sao lưu, đồng bộ; quyền; ổ lỗi). Người gọi KHÔNG được
    coi như file trống rồi ghi đè: dùng mặc định trong bộ nhớ, không ghi, đọc lại ở lần sửa kế."""


READ_ATTEMPTS = 15
READ_PAUSE_SECONDS = 0.2


def unreadable(what: str) -> None:
    NOTICES.add(f"{what} đang bị một chương trình khác giữ nên chưa đọc được - app tạm dùng mặc định và chưa lưu thay đổi vào đó cho tới "
                "khi đọc được (thường chỉ vài giây).", kind="saving-blocked")


def read_json(path: Path, what: str, valid: Callable[[Any], bool] = lambda _data: True) -> Any:
    """Nội dung JSON của `path`; chưa có file: None. Có mà hỏng (cắt nửa, rỗng, sai hình dạng theo `valid`): giữ bản hỏng (`keep_broken`)
    rồi None. Có mà không đọc được: thử lại vài giây rồi `Unreadable` (+ báo) - trước đây trả None và lần ghi kế ĐÈ file thật bằng mặc định."""
    for attempt in range(READ_ATTEMPTS):
        try:
            raw = path.read_bytes()
            break
        except FileNotFoundError:
            return None
        except OSError as error:
            if attempt == READ_ATTEMPTS - 1:
                log.warning("Không đọc được %s", path, exc_info=True)
                unreadable(what)
                raise Unreadable(f"không đọc được {path.name}") from error
            time.sleep(READ_PAUSE_SECONDS)
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError:  # gồm UnicodeDecodeError, JSONDecodeError
        if keep_broken(path, what) is None:
            raise Unreadable(f"Chưa giữ được bản cũ của {path.name}. Bạn hãy thử lại.")
        return None
    if not valid(data):
        if keep_broken(path, what) is None:
            raise Unreadable(f"Chưa giữ được bản cũ của {path.name}. Bạn hãy thử lại.")
        return None
    return data
