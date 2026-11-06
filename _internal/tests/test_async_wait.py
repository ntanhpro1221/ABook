"""The common poller owns the deadline and yields independently of time.sleep."""
from types import SimpleNamespace

import pytest

from tests import async_wait


@pytest.fixture
def scheduler(monkeypatch):
    state = SimpleNamespace(now=0.0, waits=[])

    class Wake:
        def wait(self, seconds):
            state.waits.append(seconds)
            state.now += seconds

    monkeypatch.setattr(async_wait, "time", SimpleNamespace(monotonic=lambda: state.now))
    monkeypatch.setattr(async_wait, "threading", SimpleNamespace(Event=Wake))
    return state


def test_timeout_yields_and_clamps_the_last_wait(scheduler):
    assert async_wait.wait_until(lambda: False, timeout=0.025) is False
    assert scheduler.waits == pytest.approx([0.01, 0.01, 0.005])
    assert scheduler.now == pytest.approx(0.025)


def test_returns_the_observed_value_without_polling_again(scheduler):
    value = {"state": "done"}
    observations = iter([None, None, value])
    assert async_wait.wait_for(lambda: next(observations)) is value
    assert scheduler.waits == [0.01, 0.01]


def test_success_does_not_sleep_and_boolean_api_stays_boolean(scheduler):
    assert async_wait.wait_until(lambda: {"ready": True}) is True
    assert scheduler.waits == []


def test_preserves_the_callers_polling_interval(scheduler):
    assert async_wait.wait_for(lambda: False, timeout=0.012, interval=0.005) is False
    assert scheduler.waits == pytest.approx([0.005, 0.005, 0.002])


def test_does_not_swallow_predicate_errors(scheduler):
    def broken():
        raise RuntimeError("worker failed")

    with pytest.raises(RuntimeError, match="worker failed"):
        async_wait.wait_for(broken)
    assert scheduler.waits == []
