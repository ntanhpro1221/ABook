"""Khoá cài Studio giữa các tiến trình (soát a92 V2).

Trạng thái "đang cài" của `StudioSetup` chỉ nằm ở luồng trong RAM của host: host chết (đóng app, Windows tắt máy) mà tiến
trình con của lượt cài (`uv pip install`...) vẫn chạy thì lần mở sau không thấy gì, bấm Cài tiếp là hai lượt cài vào cùng
một thư mục. File khoá nằm trong thư mục Studio: ai đang cài (pid + thời điểm bắt đầu của host) và tiến trình con đang chạy
của lượt ấy. Khoá của tiến trình đã chết, hay mã pid bị máy dùng lại cho tiến trình khác (so thời điểm bắt đầu), là khoá chết.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import psutil

LOCK_FILE = "install.lock"
# Hai lần đọc thời điểm bắt đầu của cùng một tiến trình lệch nhau cỡ phần nghìn giây; pid bị dùng lại cho tiến trình khác thì lệch hàng giây trở lên.
SAME_PROCESS_SECONDS = 1.5


def process_started(pid: int) -> float | None:
    """Thời điểm tiến trình `pid` bắt đầu; None khi nó không còn."""
    try:
        process = psutil.Process(pid)
        if process.status() == psutil.STATUS_ZOMBIE:
            return None
        return process.create_time()
    except psutil.Error:
        return None


def is_same_process(pid: int, started: float) -> bool:
    """Đúng tiến trình đã ghi (còn sống và cùng thời điểm bắt đầu), không phải một tiến trình khác mang lại mã ấy."""
    actual = process_started(pid)
    return actual is not None and abs(actual - started) <= SAME_PROCESS_SECONDS


def kill_tree(process: psutil.Process) -> list[int]:
    """Giết `process` cùng mọi tiến trình con cháu của nó (con trước), trả mã những tiến trình đã giết. Chỉ đi xuống từ nó."""
    killed: list[int] = []
    try:
        victims = [*process.children(recursive=True), process]
    except psutil.Error:
        return killed
    for victim in victims:
        try:
            victim.kill()
            killed.append(victim.pid)
        except psutil.Error:
            continue
    psutil.wait_procs(victims, timeout=5)
    return killed


class InstallLock:
    """Khoá của MỘT lượt cài trong `folder`. `acquire` trả None khi lượt này giữ được khoá, hay mô tả lượt khác còn sống."""

    def __init__(self, folder: Path) -> None:
        self.path = folder / LOCK_FILE
        self._held = False

    def _read(self) -> dict[str, Any] | None:
        for _ in range(20):  # Windows: người khác đang thay file đúng lúc ta đọc
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else None
            except PermissionError:
                time.sleep(0.05)
            except (OSError, ValueError):
                return None
        return None

    @staticmethod
    def _live(data: dict[str, Any]) -> dict[str, Any] | None:
        """Mô tả lượt cài của khoá `data` nếu còn sống (host của nó hay tiến trình con đang chạy), None nếu là khoá chết."""
        try:
            host = int(data.get("pid") or 0)
            started = float(data.get("started") or 0)
        except (TypeError, ValueError):
            return None
        child = data.get("child") if isinstance(data.get("child"), dict) else None
        host_alive = host > 0 and is_same_process(host, started)
        child_pid, child_started = (int(child.get("pid") or 0), float(child.get("started") or 0)) if child else (0, 0.0)
        child_alive = child_pid > 0 and is_same_process(child_pid, child_started)
        if not host_alive and not child_alive:
            return None
        return {"pid": host if host_alive else child_pid, "since": float(data.get("since") or 0), "what": str(data.get("what") or ""),
                "orphan": not host_alive, "childPid": child_pid if child_alive else 0}

    def holder(self) -> dict[str, Any] | None:
        """Lượt cài KHÁC còn sống (không phải lượt này), hay None."""
        data = self._read()
        if data is None:
            return None
        if self._held or (int(data.get("pid") or 0) == os.getpid() and is_same_process(os.getpid(), float(data.get("started") or 0))):
            return None  # của chính tiến trình này
        return self._live(data)

    def _create(self, temporary: Path, content: str) -> None:
        """Tạo file khoá, thất bại (FileExistsError) nếu đã có. os.link: nguyên tử, có đủ nội dung ngay khi xuất hiện; ổ không hỗ trợ link thì O_EXCL."""
        try:
            os.link(temporary, self.path)
        except FileExistsError:
            raise
        except OSError:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)

    def acquire(self, what: str) -> dict[str, Any] | None:
        me = process_started(os.getpid()) or time.time()
        content = json.dumps({"pid": os.getpid(), "started": me, "since": time.time(), "what": what, "child": None}, ensure_ascii=False)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
        temporary.write_text(content, encoding="utf-8")
        try:
            for _ in range(2):
                try:
                    self._create(temporary, content)
                    self._held = True
                    return None
                except FileExistsError:
                    other = self.holder()
                    if other is not None:
                        return other
                    self.path.unlink(missing_ok=True)  # khoá chết (hay của chính ta từ lượt trước): lấy lại
            return self.holder()
        finally:
            temporary.unlink(missing_ok=True)

    def _write(self, **changes: Any) -> None:
        data = self._read() or {}
        data.update(changes)
        temporary = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        for attempt in range(20):
            try:
                os.replace(temporary, self.path)
                return
            except PermissionError:
                if attempt == 19:
                    temporary.unlink(missing_ok=True)
                    raise
                time.sleep(0.05)

    def note_child(self, pid: int | None) -> None:
        """Ghi tiến trình con đang chạy của lượt này (hay xoá khi nó xong): host chết thì lần mở sau còn biết nó."""
        if not self._held:
            return
        started = process_started(pid) if pid else None
        try:
            self._write(child={"pid": pid, "started": started} if pid and started else None)
        except OSError:
            pass  # không ghi được thì lượt cài vẫn chạy; chỉ mất khả năng nhận ra tiến trình mồ côi

    def release(self) -> None:
        if self._held:
            self._held = False
            self.path.unlink(missing_ok=True)

    def stop_leftover(self) -> list[int]:
        """Dừng tiến trình con mồ côi của lượt cài cũ (chỉ cây tiến trình ấy) và dọn khoá nếu host của lượt ấy đã chết.
        Host còn sống là app khác đang cài: không đụng, người dùng đóng nó đi."""
        other = self.holder()
        if other is None or not other["orphan"]:
            return []
        killed: list[int] = []
        if other["childPid"]:
            try:
                killed = kill_tree(psutil.Process(other["childPid"]))
            except psutil.Error:
                killed = []
        self.path.unlink(missing_ok=True)
        return killed
