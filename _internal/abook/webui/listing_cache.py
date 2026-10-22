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


def stamps(directory: Path, current: tuple) -> dict[str, int]:
    """{đường dẫn thư mục con (mọi tầng có trong chữ ký `current` của `directory`): mốc sửa} - để dựng lại danh sách chỉ phải xét lại
    những thư mục đã đổi (`settled`, packages._packages_in)."""
    found: dict[str, int] = {}
    base = str(Path(directory))
    for name, mtime, children in current:
        path = os.path.join(base, name)  # chuỗi như str(Path(directory) / name), không dựng Path cho từng cuốn
        found[path] = int(mtime)
        if children:
            found.update(stamps(Path(path), children))
    return found


def settled(mtime_ns: int) -> bool:
    """Mốc sửa đã cũ hơn RACY_SECONDS: điều suy từ thư mục có mốc này nhớ được (xem `cached`)."""
    return mtime_ns <= time.time_ns() - int(RACY_SECONDS * 1e9)


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


def quiet(current: tuple) -> bool:
    """Chữ ký `current` không có mục nào mới sửa trong RACY_SECONDS giây: kết quả tính từ nó nhớ được (xem `cached`)."""
    return _newest(current) <= time.time_ns() - int(RACY_SECONDS * 1e9)


def cached(key: Any, current: tuple, build: Callable[[], Any]) -> Any:
    """`build()` được nhớ dưới `key` tới khi chữ ký `current` đổi hay hết tuổi. Kết quả trả về là bản dùng chung: người gọi không được sửa nó.
    Thư mục mới sửa trong RACY_SECONDS giây thì không nhớ: mốc sửa chỉ nhích theo nhịp đồng hồ hệ thống (vài chục mili giây, ổ thô 2 giây), nên
    file thêm vào ngay sau lần liệt kê trước có thể để nguyên mốc, và chữ ký sẽ không báo gì.
    Cùng `key` thì mỗi lúc chỉ một lượt `build()`: yêu cầu đến giữa chừng chờ rồi dùng kết quả ấy - mở tab Kịch bản bắn cùng lúc mấy yêu cầu
    cần cùng một phép tính, tính song song chỉ tranh nhau GIL (soát a29: 4-5 giây thay vì 1)."""
    entry = _fresh(key, current)
    if entry is not None:
        return entry[2]
    with _LOCK:
        gate = _BUILDING.setdefault(key, threading.Lock())
    with gate:
        entry = _fresh(key, current)  # lượt vừa xong trong lúc chờ
        if entry is not None:
            return entry[2]
        now = time.monotonic()
        value = build()
        if not quiet(current):
            return value
        with _LOCK:
            if len(_ENTRIES) > 256:
                _ENTRIES.clear()
            _ENTRIES[key] = (now, current, value)
    return value


_BUILDING: dict[Any, threading.Lock] = {}


def _fresh(key: Any, current: tuple) -> tuple[float, Any, Any] | None:
    with _LOCK:
        entry = _ENTRIES.get(key)
    if entry is not None and entry[1] == current and time.monotonic() - entry[0] < MAX_AGE_SECONDS:
        return entry
    return None


def files_signature(*paths: Path) -> tuple:
    """Chữ ký của vài file cho `cached` (cùng dạng `signature`: tên kèm cỡ, mốc sửa): file chưa có thì không có mục - sinh ra hay mất đi
    cũng đổi chữ ký. Sổ SQLite của dự án: file chính VÀ `-wal` (ghi vào `-wal` trước, file chính đổi khi checkpoint)."""
    found = []
    for path in paths:
        try:
            info = os.stat(path)
        except OSError:
            continue
        found.append((f"{Path(path).name}:{info.st_size}", info.st_mtime_ns, ()))
    return tuple(found)


def forget(key: Any) -> None:
    """Bỏ mục đã nhớ dưới `key` (người gọi biết nó đã cũ vì lý do chữ ký không thấy)."""
    with _LOCK:
        _ENTRIES.pop(key, None)
