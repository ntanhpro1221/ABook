"""Danh sách sách trong thư viện, đệm theo mốc sửa của các thư mục.

Mỗi yêu cầu theo mã sách phải biết "mã này là thư mục nào" nên liệt kê cả thư viện: thư mục con, `book.json` / `project.sqlite3` của từng cuốn,
`resolve` từng đường. Thư viện 300 cuốn: ~140 ms mỗi yêu cầu, kể cả một tấm bìa (soát a21). Thêm / xoá / đổi tên / nhập một cuốn đổi tên hay
mốc sửa của thư mục con trực tiếp (và `book.json` / `project.sqlite3` mới sinh đổi mốc sửa thư mục chứa nó), nên danh sách đệm đúng chừng nào
chữ ký này không đổi. Thêm một mốc tuổi tối đa cho ổ có mốc sửa thô (exFAT: 2 giây một nấc) - sai thì chỉ sai tới hết tuổi ấy.
"""
from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

MAX_AGE_SECONDS = 30.0
RACY_SECONDS = 2.5
_LOCK = threading.Lock()
_ENTRIES: dict[Any, tuple[float, Any, Any]] = {}


def signature(directory: Path, depth: int = 1) -> tuple:
    """(tên, mốc sửa, chữ ký con) của các thư mục con của `directory`, sâu `depth` tầng; thư mục không có: ()."""
    found = []
    try:
        # `os.stat` chứ không phải `entry.stat()`: NTFS chép mốc sửa vào chỉ mục của thư mục cha chậm hơn thư mục thật.
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.is_dir():
                    found.append((entry.name, os.stat(entry.path).st_mtime_ns, signature(Path(entry.path), depth - 1) if depth > 1 else ()))
    except OSError:
        return ()
    return tuple(sorted(found))


_RESOLVED: dict[str, tuple[float, str]] = {}


def resolved(path: Path, key: Callable[[Path], str]) -> str:
    """`key(path.resolve())`, nhớ theo chuỗi đường dẫn tới hết tuổi: mã sách (library.book_id) phải `resolve` đường dẫn, mà tìm một cuốn theo mã thử
    mã của từng cuốn trong thư viện (300 lần `resolve` mỗi yêu cầu)."""
    text = str(path)
    now = time.monotonic()
    hit = _RESOLVED.get(text)
    if hit is not None and now - hit[0] < MAX_AGE_SECONDS:
        return hit[1]
    value = key(Path(path).resolve())
    if len(_RESOLVED) > 4096:
        _RESOLVED.clear()
    _RESOLVED[text] = (now, value)
    return value


def _newest(current: tuple) -> int:
    """Mốc sửa mới nhất (ns) trong một chữ ký."""
    return max((max(int(entry[1]), _newest(entry[2])) for entry in current), default=0)


def cached(key: Any, current: tuple, build: Callable[[], Any]) -> Any:
    """`build()` được nhớ dưới `key` tới khi chữ ký `current` đổi hay hết tuổi. Kết quả trả về là bản dùng chung: người gọi không được sửa nó.
    Thư mục mới sửa trong RACY_SECONDS giây thì không nhớ: mốc sửa chỉ nhích theo nhịp đồng hồ hệ thống (vài chục mili giây, ổ thô 2 giây), nên
    file thêm vào ngay sau lần liệt kê trước có thể để nguyên mốc, và chữ ký sẽ không báo gì."""
    now = time.monotonic()
    with _LOCK:
        entry = _ENTRIES.get(key)
    if entry is not None and entry[1] == current and now - entry[0] < MAX_AGE_SECONDS:
        return entry[2]
    value = build()
    if _newest(current) > time.time_ns() - int(RACY_SECONDS * 1e9):
        return value
    with _LOCK:
        if len(_ENTRIES) > 256:
            _ENTRIES.clear()
        _ENTRIES[key] = (now, current, value)
    return value
