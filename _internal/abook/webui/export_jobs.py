"""Xuất file sách (`.abook`) thành việc nền có trạng thái: bấm là có ngay một mã, đóng gói chạy trong luồng của máy chủ,
giao diện hỏi trạng thái - tải lại trang giữa chừng hay sau khi xong vẫn hỏi lại được. Bản ghi sống trong bộ nhớ (hết khi
máy chủ khởi động lại), mỗi cuốn nhớ lần xuất gần nhất. "Xuất M4B" dùng cùng lớp, bản ghi riêng (server.py `m4b_jobs`); "Xuất sách nói" của sách
Nghe ngay (listen_export.py) cũng vậy và dùng thêm tiến độ (`update`) và huỷ (`cancel`)."""
from __future__ import annotations

import threading
import time
import uuid
import json
from pathlib import Path
from typing import Any, Callable

from . import humanize

Clock = Callable[[], float]

_HISTORY_LOCK = threading.RLock()
HISTORY = "export_history.json"


def audio_snapshot(project: Path) -> dict[str, str]:
    from . import audio_revision, store
    paths = store.chapter_audio_paths(project)
    digests = {path: audio_revision.describe(path)["sha256"] for path in set(paths.values()) if path.is_file()}
    return {str(key): digests[path] for key, path in paths.items() if path in digests}


def _history(project: Path) -> list[dict[str, Any]]:
    try:
        return json.loads((project / HISTORY).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []


def remember_export(project: Path, kind: str, target: str, chapters: dict[str, str]) -> None:
    from ..io_utils import atomic_write_json
    with _HISTORY_LOCK:
        records = [item for item in _history(project) if item["target"] != target]
        records.append({"kind": kind, "target": target, "chapters": chapters, "createdAt": time.time()})
        atomic_write_json(project / HISTORY, records)


def export_history(project: Path) -> list[dict[str, Any]]:
    with _HISTORY_LOCK:
        records = _history(project)
        if not records:
            return []
        current = audio_snapshot(project)
        return [{**item, "changed": [int(key) for key, digest in item["chapters"].items() if current.get(key) != digest]}
                for item in records]


class Cancelled(Exception):
    """Việc nền ném khi người dùng bấm Huỷ và nó dừng ở chỗ an toàn kế tiếp: lượt xuất kết thúc ở trạng thái "cancelled" (không phải lỗi)."""


def join_until(threads: list[threading.Thread], deadline: float) -> None:
    """Chờ các luồng xong, tới mốc `deadline` (time.monotonic) là thôi."""
    for thread in threads:
        thread.join(max(0.0, deadline - time.monotonic()))


class BookFileJobs:
    """Mỗi cuốn một bản ghi: `state` idle | running | done | error | cancelled. `work()` trả kết quả của `post_bookfile` (file, folder, size,
    hoặc parts...) và ném `Exception` có lời cho người dùng khi hỏng."""

    def __init__(self, clock: Clock = time.time) -> None:
        self._lock = threading.Lock()
        self._state: dict[str, dict[str, Any]] = {}
        self._stops: dict[str, threading.Event] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._clock = clock

    def status(self, key: str) -> dict[str, Any]:
        with self._lock:
            state = dict(self._state.get(key) or {"state": "idle"})
        if state["state"] == "running":
            state["elapsed"] = max(0.0, self._clock() - state["startedAt"])
        elif state["state"] != "idle":
            # Giao diện không so đồng hồ của máy xem với máy chủ: "xong cách đây bao lâu" tính sẵn ở đây.
            state["finishedAgo"] = max(0.0, self._clock() - state["finishedAt"])
        return state

    def running(self) -> list[tuple[str, dict[str, Any]]]:
        """Các cuốn đang có lượt xuất chạy: [(key, trạng thái)]. Giao diện vừa mở (hay tải lại ở trang khác) hỏi để hiện lại tiến độ."""
        with self._lock:
            keys = [key for key, state in self._state.items() if state.get("state") == "running"]
        return [(key, self.status(key)) for key in keys]

    def update(self, key: str, **fields: Any) -> None:
        """Việc đang chạy ghi tiến độ vào bản ghi của nó (giao diện thấy ở lần hỏi kế). Việc đã xong / không có thì bỏ qua."""
        with self._lock:
            if (self._state.get(key) or {}).get("state") == "running":
                self._state[key] = {**self._state[key], **fields}

    def cancel(self, key: str) -> bool:
        """Bảo việc đang chạy của cuốn `key` dừng (nó dừng ở chỗ an toàn kế tiếp - `cancelled()`). True nếu có việc đang chạy."""
        with self._lock:
            running = (self._state.get(key) or {}).get("state") == "running"
            stop = self._stops.get(key)
        if running and stop is not None:
            stop.set()
        return running

    def shutdown(self, timeout: float = 3.0) -> None:
        """App đóng: bảo mọi việc đang chạy dừng ở chỗ an toàn kế tiếp rồi chờ chúng dọn xong (file tạm), tổng cộng không quá `timeout` giây
        - đóng app không được treo vì một lượt xuất. Việc không có chỗ dừng trong ngần ấy giây thì bỏ lại (luồng nền chết cùng tiến trình)."""
        join_until(self.stop_all(), time.monotonic() + timeout)

    def stop_all(self) -> list[threading.Thread]:
        """Bảo mọi việc đang chạy dừng ở chỗ an toàn kế tiếp, KHÔNG chờ; trả luồng của chúng để chờ (`join_until`). App đóng bảo mọi
        loại việc dừng cùng lúc rồi chờ chung một hạn (server `App.close`)."""
        with self._lock:
            running = [key for key, state in self._state.items() if state.get("state") == "running"]
            stops = [self._stops[key] for key in running if key in self._stops]
            threads = [self._threads[key] for key in running if key in self._threads and self._threads[key].ident is not None]
        for stop in stops:
            stop.set()
        return threads

    def cancelled(self, key: str) -> bool:
        """Việc đang chạy của `key` đã bị bảo dừng? (Lượt đã xong / đã huỷ thì không: cờ cũ không được dừng lượt đồng bộ sau đó.)"""
        with self._lock:
            stop = self._stops.get(key)
            running = (self._state.get(key) or {}).get("state") == "running"
        return running and stop is not None and stop.is_set()

    def start(self, key: str, work: Callable[[], dict[str, Any]], *, on_done: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
        """Bắt đầu một lượt xuất cho cuốn `key`; đang có lượt chạy thì trả lượt ấy (không đóng gói hai lần cùng lúc)."""
        def finish(**changes: Any) -> None:
            with self._lock:
                self._state[key] = {**self._state[key], **changes, "finishedAt": self._clock()}

        def run() -> None:
            try:
                result = work()
                if on_done is not None:
                    on_done(result)
            except Cancelled:
                finish(state="cancelled")
                return
            except OSError as error:
                # Thư mục xuất chỉ đọc, ổ đầy: lời người dùng (humanize.write_error), không "[WinError 5] Access is denied: '...'".
                finish(state="error", error=humanize.write_error(error) if humanize.is_write_problem(error) else str(error) or type(error).__name__)
                return
            except Exception as error:  # noqa: BLE001 - lỗi lạ phải tới được người dùng, không giết luồng im lặng
                finish(state="error", error=str(error) or type(error).__name__)
                return
            finish(state="done", result=result)

        with self._lock:
            if (self._state.get(key) or {}).get("state") != "running":
                job_id = uuid.uuid4().hex[:12]
                self._state[key] = {"state": "running", "id": job_id, "startedAt": self._clock()}
                self._stops[key] = threading.Event()
                # Luồng được ghi nhận VÀ chạy trong cùng một lần giữ khoá: `shutdown` (đóng app) không bao giờ thấy luồng chưa start để join (RuntimeError).
                thread = self._threads[key] = threading.Thread(target=run, name="bookfile-export", daemon=True)
                thread.start()
        return self.status(key)
