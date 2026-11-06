"""Condition polling that yields even when the sleep-counting fixture disables sleep.

The timeout is a deadlock guard, never the expected duration of the operation.
Use Events/latches instead when the operation exposes a completion signal.
"""
import threading
import time


def wait_until(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    wake = threading.Event()
    while True:
        if predicate():
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        wake.wait(min(0.01, remaining))
