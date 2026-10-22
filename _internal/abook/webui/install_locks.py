"""Serialize each destination across optional modules and host processes."""
from contextlib import contextmanager
from pathlib import Path
import threading
import os
import time

_guard = threading.Lock()
_locks: dict[Path, threading.RLock] = {}


@contextmanager
def destination_lock(path: Path):
    key = path.resolve()
    with _guard:
        lock = _locks.setdefault(key, threading.RLock())
    with lock:
        key.parent.mkdir(parents=True, exist_ok=True)
        with key.with_suffix(key.suffix + ".lock").open("a+b") as handle:
            deadline = time.monotonic() + 600
            while True:
                try:
                    if os.name == "nt":
                        import msvcrt
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Gói đang được tải ở cửa sổ khác. Bạn hãy chờ rồi thử lại.")
                    time.sleep(0.1)
            try:
                yield
            finally:
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
