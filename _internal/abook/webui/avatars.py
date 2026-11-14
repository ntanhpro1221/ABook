"""Studio portrait jobs; bounded single remote request at a time, no local inference dependency."""
from __future__ import annotations

import base64
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from typing import Any

from .. import avatars
from . import store

_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="portrait")
_LOCK = threading.Lock()
_JOBS: dict[tuple[str, str], dict[str, Any]] = {}


def status(root: Path, name: str) -> dict[str, Any]:
    with _LOCK:
        job = dict(_JOBS.get((str(root), name), {}))
    return {"available": avatars.service_config(root) is not None, **job}


def person(root: Path, name: str) -> dict[str, Any]:
    with closing(store.connect(root)) as connection:
        row = connection.execute("SELECT canonical_name,display_name,gender,age FROM characters WHERE canonical_name=?", (name,)).fetchone()
    if row is None:
        raise ValueError("Nhân vật không có trong sách.")
    return dict(row)


def update(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    name = str(body.get("character") or "")
    record = person(root, name)
    action = body.get("action")
    if action in ("upload", "pattern"):
        data = base64.b64decode(str(body.get("data") or ""), validate=True) if action == "upload" else None
        return {"avatar": avatars.choose(root, name, data), "pending": False}
    if action != "generate":
        raise ValueError("Chọn ảnh, sinh lại hoặc dùng hoạ tiết.")
    with closing(store.connect(root)) as connection:
        if connection.execute("SELECT COUNT(*) FROM segments WHERE status='pending'").fetchone()[0]:
            raise ValueError("Bạn đợi phân tích xong rồi sinh ảnh.")
    if avatars.service_config(root) is None:
        raise ValueError("Bạn chưa cấu hình dịch vụ ảnh cho sách này.")
    key = (str(root), name)
    with _LOCK:
        if _JOBS.get(key, {}).get("pending"):
            return dict(_JOBS[key])
        if sum(bool(job.get("pending")) for job in _JOBS.values()) >= 32:
            raise ValueError("Đang có nhiều ảnh chờ sinh. Bạn thử lại sau.")
        _JOBS[key] = {"pending": True, "error": ""}
    def run() -> None:
        try:
            with closing(store.connect(root)) as connection:
                names = [str(row[0]) for row in connection.execute("SELECT display_name FROM characters")]
                chapter_ids = [row[0] for row in connection.execute("SELECT id FROM chapters ORDER BY id")]
            evidence = []
            for chapter in chapter_ids:
                evidence.extend(avatars.appearance(record["display_name"], store.chapter_source_text(root, chapter) or "", names))
                if len(evidence) >= 4:
                    break
            avatars.generate(root, record, evidence[:4], force=True)
            done = {"pending": False, "error": ""}
        except Exception:
            done = {"pending": False, "error": "Chưa sinh được ảnh. Bạn thử lại."}
        with _LOCK:
            _JOBS[key] = done
    _POOL.submit(run)
    return {"pending": True, "error": ""}
