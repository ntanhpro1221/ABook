"""Kết quả mở file nằm ở host tới khi trang đã nhận và ACK đúng sự kiện."""
from __future__ import annotations

import threading
import uuid
from typing import Any


class OpenedEvents:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, dict[str, Any]] = {}

    def publish(self, result: dict[str, Any]) -> dict[str, Any]:
        event = {**result, "eventId": uuid.uuid4().hex}
        with self._lock:
            self._pending[event["eventId"]] = event
        return event

    def pending(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._pending.values())

    def ack(self, event_id: str) -> None:
        with self._lock:
            self._pending.pop(event_id, None)
