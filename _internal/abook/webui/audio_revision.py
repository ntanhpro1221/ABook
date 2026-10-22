"""Dấu nội dung dùng chung cho đồng bộ, nhập và bản xuất."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections import Counter, OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

# Băm cả file audio mỗi lần điện thoại hỏi thư viện là hàng GB đọc lại: nhớ dấu theo (đường tuyệt đối, cỡ, mtime_ns). File đổi cỡ hay
# mtime thì khoá khác -> băm lại. Máy chủ đa luồng: khoá chỉ giữ lúc đọc/ghi bảng, KHÔNG giữ lúc băm (hai luồng cùng băm một file thì
# chỉ tốn công, kết quả như nhau).
_CACHE_LIMIT = 4096
_CACHE: "OrderedDict[tuple[str, int, int], str]" = OrderedDict()
_CACHE_LOCK = threading.Lock()
# File mới ghi trong vài giây vừa qua chưa được nhớ: đồng hồ file thô (có hệ 1-2 giây, Windows vài chục ms) có thể cho hai lần ghi cùng
# cỡ trùng mtime - giống "racily clean" của git. Qua ngưỡng này mới tin (cỡ, mtime) là đủ phân biệt bản thu.
_SETTLE_NS = 3_000_000_000


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
    stat = path.stat()
    key = (os.path.abspath(path), stat.st_size, stat.st_mtime_ns)
    with _CACHE_LOCK:
        known = _CACHE.get(key)
        if known is not None:
            _CACHE.move_to_end(key)
            return {"size": stat.st_size, "sha256": known}
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
            _CACHE[key] = result
            _CACHE.move_to_end(key)
            while len(_CACHE) > _CACHE_LIMIT:
                _CACHE.popitem(last=False)
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
