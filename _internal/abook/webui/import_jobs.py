"""Sổ các lượt thêm sách của máy chủ (file sách `.abook` / `.abookproj`, EPUB / DOCX / PDF / TXT): việc của máy chủ, không của màn "Thêm sách".

Màn "Thêm sách" (Qt `AddBook.qml`, web `AddBook.tsx`) chỉ là MỘT người xem: đóng màn giữa chừng thì lượt vẫn chạy tới xong, và thư viện tự làm mới nhờ
người xem ở cấp app (Qt `Api.qml` `importJobs`, web `useImportJobs`) thấy `revision` đổi - không nhờ lời gọi lại của màn đã đóng. Cùng vai với
`BookImports` / `ImportJobs` của điện thoại.

Sổ ghi ra đĩa (`import_jobs.json` cạnh `preferences.json`): app thoát giữa lượt thì lần mở sau lượt ấy hiện là "interrupted" (kèm nút Thử lại ở
giao diện), không bao giờ im lặng biến mất. Nhập luôn giải vào thư mục tạm `.<tên>.<hex>.part` rồi mới đổi tên (bookfile `_extract`), nên lượt dở
không để nửa cuốn trong thư viện; thư mục tạm của lượt dở được dọn lúc mở lại (`sweep_parts`).
"""
from __future__ import annotations

import contextlib
import json
import re
import shutil
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

FILE_NAME = "import_jobs.json"
KEEP = 20  # lượt đã xong / lỗi giữ lại (mới nhất), như ImportJobs.KEEP của điện thoại
RUNNING, DONE, FAILED, INTERRUPTED = "running", "done", "failed", "interrupted"


class ImportJobs:
    """`begin` / `finish` / `fail` từ luồng làm việc; `view` cho giao diện. Mọi thay đổi tăng `revision` (người xem so số này để biết có gì mới)."""

    def __init__(self, journal: Path | None = None, clock: Callable[[], float] = time.time) -> None:
        self._lock = threading.RLock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._journal = journal
        self._clock = clock
        self.revision = 0
        self.interrupted: list[dict[str, Any]] = []  # lượt dở của lần chạy trước (để dọn thư mục tạm)
        self._load()

    def _load(self) -> None:
        if self._journal is None:
            return
        try:
            rows = json.loads(self._journal.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(rows, list):
            return
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not isinstance(row.get("params"), dict):
                continue
            if row.get("state") == RUNNING:
                row = {**row, "state": INTERRUPTED, "ended": row.get("started")}
                self.interrupted.append(row)
            self._jobs[row["id"]] = row
        if self.interrupted:
            self._save()

    def _save(self) -> None:
        if self._journal is None:
            return
        from ..io_utils import atomic_write_json
        with contextlib.suppress(OSError):
            atomic_write_json(self._journal, list(self._jobs.values()), fsync=False)

    def _changed(self) -> None:
        ended = [key for key, job in self._jobs.items() if job["state"] != RUNNING]
        for key in ended[:max(0, len(ended) - KEEP)]:
            del self._jobs[key]
        self.revision += 1
        self._save()

    def begin(self, kind: str, name: str, params: dict[str, Any]) -> str:
        with self._lock:
            job_id = uuid.uuid4().hex[:12]
            self._jobs[job_id] = {"id": job_id, "kind": kind, "name": name, "params": params, "state": RUNNING,
                                  "started": self._clock(), "ended": None, "result": None, "problem": ""}
            self._changed()
            return job_id

    def finish(self, job_id: str, result: dict[str, Any]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.update(state=DONE, ended=self._clock(), result={key: result.get(key) for key in ("id", "how") if key in result})
                self._changed()

    def fail(self, job_id: str, problem: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.update(state=FAILED, ended=self._clock(), problem=problem)
                self._changed()

    def run(self, kind: str, name: str, params: dict[str, Any], work: Callable[[], dict[str, Any]],
            problem: Callable[[Exception], str], *, job_id: str | None = None) -> dict[str, Any]:
        """Chạy `work` như một lượt (luồng gọi): xong ghi kết quả, lỗi ghi lời của lỗi (`problem`) rồi ném tiếp cho người gọi."""
        job_id = job_id or self.begin(kind, name, params)
        try:
            result = work()
        except Exception as error:
            self.fail(job_id, problem(error))
            raise
        self.finish(job_id, result)
        return result

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job is not None else None

    def dismiss(self, job_id: str) -> bool:
        """Bỏ một lượt đã xong / lỗi / dở khỏi sổ (người dùng đóng hàng). Lượt đang chạy thì không bỏ."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job["state"] == RUNNING:
                return False
            del self._jobs[job_id]
            self._changed()
            return True

    def view(self) -> dict[str, Any]:
        """Cho giao diện: không gửi `params` (đường dẫn, lựa chọn chương) - chỉ những gì một hàng cần."""
        with self._lock:
            rows = [{key: job[key] for key in ("id", "kind", "name", "state", "problem", "result", "started", "ended")}
                    for job in self._jobs.values()]
            return {"revision": self.revision, "jobs": rows}


def sweep_parts(library: Path, interrupted: list[dict[str, Any]]) -> int:
    """Lượt dở của lần chạy trước có thể để lại thư mục tạm `.<tên>.<hex>.part` (bookfile `_extract`): không bao giờ là sách trong thư viện, nhưng chiếm
    chỗ. Lúc mở app chưa có lượt nào chạy, nên mọi thư mục tạm sinh ra từ lúc lượt dở sớm nhất bắt đầu là của nó."""
    if not interrupted:
        return 0
    since = min(float(job.get("started") or 0) for job in interrupted) - 5
    removed = 0
    with contextlib.suppress(OSError):
        for entry in Path(library).iterdir():
            if (re.fullmatch(r"\..+\.[0-9a-f]{8}\.part", entry.name) and not entry.is_symlink() and entry.is_dir()
                    and entry.stat().st_mtime >= since):
                shutil.rmtree(entry)
                removed += 1
    return removed
