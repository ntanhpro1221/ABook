"""Trình phát trên các máy đã ghép - mạng trạm bước 4 (chủ sách 27-09: điều khiển hai chiều, mọi cặp máy).

Máy tính khác và điện thoại chia sẻ thư viện (cùng `computers.json`, remote_books.py) trả trình phát của chúng ở
`GET /sync/v1/player`. Giao diện hỏi `/api/remote` 1,5-5 giây một lần; hỏi thẳng từng máy trong lượt ấy thì một máy tắt
làm cả thanh điều khiển đứng chờ. Nên một luồng nền hỏi thay, và chỉ khi có người đang xem (giao diện hỏi trong 15 giây
qua): máy đang có sách 1,5 giây một lần, máy rảnh 5 giây, máy không trả lời 20 giây. `view()` đọc bản chụp, không bao giờ
đợi mạng; vị trí nội suy ở giao diện theo `age` như với điện thoại.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from . import remote_books
from .sync import _presence, _text

WANTED_SECONDS = 15.0
BUSY_SECONDS = 1.5
IDLE_SECONDS = 5.0
DOWN_SECONDS = 20.0


class PeerPlayers:
    def __init__(self, computers: remote_books.Computers,
                 fetch: Callable[[dict[str, Any]], dict[str, Any]] = remote_books.player) -> None:
        self.computers = computers
        self.fetch = fetch
        self._lock = threading.Lock()
        self._seen: dict[str, dict[str, Any]] = {}  # máy -> {"at": lúc hỏi, "reply": trả lời | None, "due": lúc hỏi lại}
        self._busy: set[str] = set()
        self._wanted = 0.0
        self._thread: threading.Thread | None = None
        self._wake = threading.Event()

    def view(self) -> list[dict[str, Any]]:
        """Máy đã ghép đang trả lời, kèm trình phát của nó (có thể chưa nạp sách - vẫn nhận "Phát trên máy này")."""
        now = time.time()
        with self._lock:
            self._wanted = now
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._loop, name="peer-players", daemon=True)
                self._thread.start()
            seen = dict(self._seen)
        players = []
        for computer in self.computers.list():
            entry = seen.get(computer["id"])
            reply = entry["reply"] if entry else None
            if not isinstance(reply, dict):
                continue
            presence = _presence({**reply, "state": reply.get("state") if isinstance(reply.get("state"), dict) else {}})
            age = float(reply.get("age") or 0) if isinstance(reply.get("age"), (int, float)) else 0.0
            players.append({**presence, "device": computer["id"], "via": "peer",
                            "name": _text(reply.get("name")) or str(computer.get("name") or ""),
                            "kind": "phone" if reply.get("kind") == "phone" else "computer",
                            "age": round(max(0.0, age) + now - entry["at"], 2)})
        return players

    def poke(self, computer: str) -> None:
        """Vừa gửi lệnh cho máy này: hỏi lại ngay để nút dưới tay người bấm thấy kết quả sau một lượt mạng."""
        with self._lock:
            if computer in self._seen:
                self._seen[computer]["due"] = 0.0
        self._wake.set()

    def _loop(self) -> None:
        listed, keys = 0.0, []
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="peer-player") as pool:
            while time.time() - self._wanted < WANTED_SECONDS:
                now = time.time()
                if now - listed > 2:  # computers.json đọc lại 2 giây một lần, không phải mỗi vòng 0,25 giây
                    listed, keys = now, [computer["id"] for computer in self.computers.list()]
                for key in keys:
                    with self._lock:
                        entry = self._seen.get(key)
                        if key in self._busy or (entry is not None and entry["due"] > now):
                            continue
                        self._busy.add(key)
                    pool.submit(self._poll, key)
                self._wake.wait(0.25)
                self._wake.clear()

    def _poll(self, key: str) -> None:
        try:
            entry = self.computers.get(key)
            reply: dict[str, Any] | None = None
            if entry is not None:
                try:
                    reply = self.fetch(entry)
                except (remote_books.RemoteError, ValueError, KeyError):
                    reply = None
            now = time.time()
            state = reply.get("state") if isinstance(reply, dict) else None
            delay = DOWN_SECONDS if reply is None else BUSY_SECONDS if isinstance(state, dict) and state.get("bookId") else IDLE_SECONDS
            with self._lock:
                self._seen[key] = {"at": now, "reply": reply, "due": now + delay}
        finally:
            with self._lock:
                self._busy.discard(key)
