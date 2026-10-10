"""Xuất file sách (`.abook`) thành việc nền có trạng thái: bấm là có ngay một mã, đóng gói chạy trong luồng của máy chủ,
giao diện hỏi trạng thái - tải lại trang giữa chừng hay sau khi xong vẫn hỏi lại được. Bản ghi sống trong bộ nhớ (hết khi
máy chủ khởi động lại), mỗi cuốn nhớ lần xuất gần nhất. "Xuất M4B" dùng cùng lớp, bản ghi riêng (server.py `m4b_jobs`); "Xuất sách nói" của sách
Nghe ngay (listen_export.py) cũng vậy và dùng thêm tiến độ (`update`) và huỷ (`cancel`)."""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Callable

Clock = Callable[[], float]


class Cancelled(Exception):
    """Việc nền ném khi người dùng bấm Huỷ và nó dừng ở chỗ an toàn kế tiếp: lượt xuất kết thúc ở trạng thái "cancelled" (không phải lỗi)."""


class BookFileJobs:
    """Mỗi cuốn một bản ghi: `state` idle | running | done | error | cancelled. `work()` trả kết quả của `post_bookfile` (file, folder, size,
    hoặc parts...) và ném `Exception` có lời cho người dùng khi hỏng."""

    def __init__(self, clock: Clock = time.time) -> None:
        self._lock = threading.Lock()
        self._state: dict[str, dict[str, Any]] = {}
        self._stops: dict[str, threading.Event] = {}
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

    def cancelled(self, key: str) -> bool:
        stop = self._stops.get(key)
        return stop is not None and stop.is_set()

    def start(self, key: str, work: Callable[[], dict[str, Any]], *, on_done: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
        """Bắt đầu một lượt xuất cho cuốn `key`; đang có lượt chạy thì trả lượt ấy (không đóng gói hai lần cùng lúc)."""
        with self._lock:
            if (self._state.get(key) or {}).get("state") == "running":
                running = True
            else:
                running = False
                job_id = uuid.uuid4().hex[:12]
                self._state[key] = {"state": "running", "id": job_id, "startedAt": self._clock()}
                self._stops[key] = threading.Event()
        if running:
            return self.status(key)

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
            except Exception as error:  # noqa: BLE001 - lỗi lạ phải tới được người dùng, không giết luồng im lặng
                finish(state="error", error=str(error) or type(error).__name__)
                return
            finish(state="done", result=result)

        threading.Thread(target=run, name="bookfile-export", daemon=True).start()
        return self.status(key)
