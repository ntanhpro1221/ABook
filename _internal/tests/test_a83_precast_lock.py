"""Soát a83 B14: precast.set_wait / announce / release đọc-sửa-ghi cùng một file - chạy chồng nhau không được nuốt nhau."""
from __future__ import annotations

import threading
import time
from pathlib import Path

from abook.webui import precast


def test_announce_and_set_wait_do_not_swallow_each_other(monkeypatch, tmp_path: Path) -> None:
    real = precast._write

    def slow(root, record):
        if threading.current_thread().name == "announcer":
            time.sleep(0.3)
        return real(root, record)

    monkeypatch.setattr(precast, "_write", slow)
    thread = threading.Thread(target=lambda: precast.announce(tmp_path, now=123.0), name="announcer")
    thread.start()
    time.sleep(0.1)
    precast.set_wait(tmp_path, True)
    thread.join()
    record = precast.read(tmp_path)
    assert record["wait"] is True and record["announcedAt"] == 123.0
