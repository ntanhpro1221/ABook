"""Condition polling that yields even when the sleep-counting fixture disables sleep.

The timeout is a deadlock guard, never the expected duration of the operation.
Use Events/latches instead when the operation exposes a completion signal.
"""
import threading
import time


def wait_for(predicate, timeout=5.0, interval=0.01):
    """Return the first truthy observation, or False on timeout; never poll twice for a result."""
    deadline = time.monotonic() + timeout
    wake = threading.Event()
    while True:
        value = predicate()
        if value:
            return value
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        wake.wait(min(interval, remaining))


def wait_until(predicate, timeout=5.0, interval=0.01):
    return bool(wait_for(predicate, timeout, interval))
