"""Dấu nội dung dùng chung cho đồng bộ, nhập và bản xuất."""
from __future__ import annotations

import atexit
import hashlib
import json
import os
import threading
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

# Băm cả file audio mỗi lần điện thoại hỏi thư viện là hàng GB đọc lại: nhớ dấu theo đường tuyệt đối -> (cỡ, mtime_ns, sha256). File đổi cỡ
# hay mtime thì băm lại và thay mục. Không có trần LRU (quét tuần tự thư viện lớn hơn trần sẽ đẩy hết mục ra trước khi tới lượt sau): mỗi
# file một mục vài trăm byte, mục của file không còn thì dọn lúc ghi (`_flush`). Bảng được lưu ra đĩa (`configure`) nên khởi động lại app
# không băm lại gì. Máy chủ đa luồng: khoá chỉ giữ lúc đọc/ghi bảng, KHÔNG giữ lúc băm (hai luồng cùng băm một file thì chỉ tốn công).
_MEMO: dict[str, tuple[int, int, str]] = {}
_CACHE_LOCK = threading.Lock()
_STORE: Path | None = None  # file lưu bảng (nằm cạnh tuỳ chọn của app); None = chỉ nhớ trong bộ nhớ
_FLUSH_SECONDS = 2.0
_timer: threading.Timer | None = None
_dirty = False
_atexit_hooked = False
# File mới ghi trong vài giây vừa qua chưa được nhớ: đồng hồ file thô (có hệ 1-2 giây, Windows vài chục ms) có thể cho hai lần ghi cùng
# cỡ trùng mtime - giống "racily clean" của git. Qua ngưỡng này mới tin (cỡ, mtime) là đủ phân biệt bản thu.
_SETTLE_NS = 3_000_000_000


def configure(store_path: Path | None) -> None:
    """App gọi lúc dựng: nạp bảng dấu đã lưu ở `store_path` (hỏng / thiếu thì bắt đầu rỗng, băm lại dần) và từ đó ghi lại khi có mục mới."""
    global _STORE, _dirty, _atexit_hooked
    _flush()  # bảng của lần cấu hình trước (tests dựng nhiều app) về đúng file của nó
    loaded: dict[str, tuple[int, int, str]] = {}
    if store_path is not None:
        try:
            raw = json.loads(Path(store_path).read_bytes().decode("utf-8"))
            for name, item in (raw.get("files") or {}).items():
                if isinstance(name, str) and isinstance(item, list) and len(item) == 3 and isinstance(item[0], int) and isinstance(item[1], int) \
                        and isinstance(item[2], str) and len(item[2]) == 64:
                    loaded[name] = (item[0], item[1], item[2])
        except (OSError, ValueError, AttributeError):
            loaded = {}
    with _CACHE_LOCK:
        _STORE = Path(store_path) if store_path is not None else None
        _MEMO.clear()
        _MEMO.update(loaded)
        _dirty = bool(loaded)  # lần ghi đầu dọn mục của file đã mất
    if store_path is not None:
        if not _atexit_hooked:
            atexit.register(_flush)
            _atexit_hooked = True
        if loaded:
            _schedule()


def _schedule() -> None:
    global _timer
    with _CACHE_LOCK:
        if _timer is not None or _STORE is None:
            return
        _timer = threading.Timer(_FLUSH_SECONDS, _flush)
        _timer.daemon = True
        _timer.start()


def _flush() -> None:
    """Ghi bảng ra đĩa (nếu đổi), bỏ mục của file đã bị xoá (thư mục của nó còn mà file không còn: ổ rút ra thì giữ mục)."""
    global _timer, _dirty
    with _CACHE_LOCK:
        _timer = None
        if not _dirty or _STORE is None:
            return
        target, snapshot = _STORE, dict(_MEMO)
        _dirty = False
    gone = [name for name in snapshot if not os.path.exists(name) and os.path.isdir(os.path.dirname(name))]
    for name in gone:
        del snapshot[name]
    with _CACHE_LOCK:
        for name in gone:
            _MEMO.pop(name, None)
    try:
        from ..io_utils import atomic_write_json
        atomic_write_json(target, {"v": 1, "files": {name: list(item) for name, item in snapshot.items()}}, fsync=False, compact=True)
    except OSError:
        with _CACHE_LOCK:
            _dirty = True  # lần sau thử lại


def source_fingerprint(project: Path) -> str:
    """Nhận cùng sách khi mọi chương đều thu lại; không mang đường dẫn của máy vào gói."""
    from . import store
    with store.connect(project) as connection:
        if "input_path" not in {row[1] for row in connection.execute("PRAGMA table_info(chapters)")}:
            return ""
        rows = list(connection.execute("SELECT chapter_index,input_path FROM chapters ORDER BY chapter_index"))
    values = []
    for index, raw in rows:
        if not raw:
            return ""
        path = Path(raw)
        if not path.is_absolute():
            path = project / path
        if not path.is_file():
            return ""
        values.append((index, describe(path)["sha256"]))
    return hashlib.sha256(json.dumps(values).encode()).hexdigest() if values else ""


def describe(path: Path) -> dict[str, Any]:
    global _dirty
    stat = path.stat()
    name = os.path.abspath(path)
    with _CACHE_LOCK:
        known = _MEMO.get(name)
    if known is not None and known[0] == stat.st_size and known[1] == stat.st_mtime_ns:
        return {"size": stat.st_size, "sha256": known[2]}
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    result = digest.hexdigest()
    # Chỉ nhớ khi file đứng yên suốt lúc băm và đã "nguội" (xem _SETTLE_NS).
    after = path.stat()
    if (after.st_size, after.st_mtime_ns) == (stat.st_size, stat.st_mtime_ns) == (size, stat.st_mtime_ns) and time.time_ns() - stat.st_mtime_ns > _SETTLE_NS:
        with _CACHE_LOCK:
            _MEMO[name] = (stat.st_size, stat.st_mtime_ns, result)
            _dirty = True
        _schedule()
    return {"size": size, "sha256": result}


def version(chapters: list[dict[str, Any]]) -> str:
    return hashlib.sha256(json.dumps([(c["id"], c.get("sha256", "")) for c in chapters], separators=(",", ":")).encode()).hexdigest()


def expected(book: dict[str, Any], relative: str) -> str:
    return next((c["sha256"] for c in book.get("chapters", []) if c.get("file") == relative), "")


def matches(path: Path, size: int | None, digest: str) -> bool:
    try:
        return path.is_file() and (size is None or path.stat().st_size == size) and (not digest or describe(path)["sha256"] == digest)
    except OSError:
        return False


def import_state(local: dict, incoming: dict, local_at: str, incoming_at: str) -> str:
    def entries(items: dict) -> Counter:
        return Counter((name.rsplit("/", 1)[-1], json.dumps(value, sort_keys=True)) for name, value in items.items())
    own, next_ = entries(local), entries(incoming)
    preserves = own <= next_
    if own == next_:
        return "existing"
    if len(incoming) < len(local):
        return "older"
    try:
        before, after = datetime.fromisoformat(local_at), datetime.fromisoformat(incoming_at)
        if before == after and len(incoming) > len(local) and preserves:
            return "updated"
        if before.tzinfo is None or after.tzinfo is None or before == after:
            return "conflict"
        return "older" if after < before else "updated"
    except (ValueError, TypeError):
        # Chưa rõ thứ tự nhưng chỉ thêm chương, mọi chương cũ giữ nguyên: an toàn để bổ sung.
        if preserves:
            return "updated"
        return "conflict"
