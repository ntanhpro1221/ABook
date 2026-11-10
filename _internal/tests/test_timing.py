"""tests/timing.py: hệ số máy tải nhân cận trên, không bao giờ nhân cận dưới, và không nới quá thời gian của hành vi sai."""
import pytest

from tests import timing


@pytest.fixture
def scale5(monkeypatch):
    monkeypatch.setattr(timing, "SCALE", 5.0)


def test_scaled_multiplies_and_the_default_is_wide_enough_for_a_loaded_machine():
    assert timing.SCALE >= 1.0
    assert timing.scaled(2) == 2 * timing.SCALE


def test_within_accepts_a_slow_run_inside_the_scaled_limit_and_rejects_beyond_it(scale5):
    timing.assert_within(2.0, 0.0, clock=lambda: 9.9)  # 9,9 s < 2 x 5
    with pytest.raises(AssertionError):
        timing.assert_within(2.0, 0.0, clock=lambda: 10.0)


def test_blocked_caps_the_scaled_limit_so_the_wrong_behaviour_still_fails(scale5):
    # hành vi sai mất 10 s: hạn 3 x 5 = 15 s sẽ để nó lọt, nên bị chặn ở 8 s
    with pytest.raises(AssertionError):
        timing.assert_within(3.0, 0.0, blocked=10, clock=lambda: 9.0)
    timing.assert_within(3.0, 0.0, blocked=10, clock=lambda: 7.9)


def test_the_limit_is_never_below_what_was_asked(scale5):
    timing.assert_within(5.0, 0.0, blocked=1, clock=lambda: 4.9)  # blocked quá nhỏ thì hạn gốc vẫn là sàn


def test_between_keeps_the_lower_bound_unscaled(scale5):
    timing.assert_between(1.4, 5, 0.0, clock=lambda: 20.0)
    with pytest.raises(AssertionError):
        timing.assert_between(1.4, 5, 0.0, clock=lambda: 1.0)
    with pytest.raises(AssertionError):
        timing.assert_between(1.4, 5, 0.0, clock=lambda: 25.0)


def test_took_within_takes_a_measured_duration(scale5):
    timing.assert_took_within(9.9, 2)
    with pytest.raises(AssertionError):
        timing.assert_took_within(10.0, 2)
