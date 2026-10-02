"""Người gác pin (scripts/power_guard.py): các bậc theo THỜI GIAN CÒN LẠI ước từ tốc độ tụt thật, không theo một con số % -
chủ sách 29-09: "không phải cứ thấy pin tụt chút là tắt trong khi on battery vẫn chạy được lâu"."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from power_guard import Reading, State, decide, remaining_minutes  # noqa: E402


def run(readings: list[Reading]) -> tuple[State, list[list[str]]]:
    state = State()
    return state, [decide(state, reading) for reading in readings]


def test_a_short_unplug_does_nothing_and_leaves_no_trace() -> None:
    """Rút nhầm rồi cắm lại trong 40 giây: không tạm dừng gì, không báo gì."""
    state, actions = run([Reading(0, False, 90, None), Reading(20, False, 90, None), Reading(40, True, 90, None)])
    assert actions == [[], [], ["ac_back"]]
    assert state.unplugged_at is None


def test_a_minute_on_battery_pauses_the_gpu_jobs_and_power_back_resumes_them() -> None:
    state, actions = run([Reading(0, False, 90, None), Reading(60, False, 90, None), Reading(80, True, 90, None)])
    assert actions[1] == ["pause"]
    assert actions[2] == ["resume", "ac_back"]


def test_a_healthy_battery_is_never_shut_down_for_a_small_drop() -> None:
    """Máy nghỉ GPU tụt 1% mỗi 3 phút: 80% còn ~4 giờ - hai giờ đồng hồ chỉ có tạm dừng + "chạy pin đã lâu"."""
    readings = [Reading(t, False, 80 - t // 180, None) for t in range(0, 7200, 20)]
    state, actions = run(readings)
    flat = [action for step in actions for action in step]
    assert flat == ["pause", "long"]
    assert not state.stopped


def test_the_shutdown_waits_for_the_estimate_to_run_low_twice() -> None:
    """Tụt 1%/phút: cảnh báo khi còn <= 25 phút, đóng việc + hẹn tắt khi còn <= 12 phút ở HAI lần đo liền."""
    readings = [Reading(t, False, 60 - t // 60, None) for t in range(0, 3600, 20)]
    state, actions = run(readings)
    warn_at = next(i for i, step in enumerate(actions) if "warn" in step)
    stop_at = next(i for i, step in enumerate(actions) if "stop" in step)
    assert 20 <= readings[warn_at].percent <= 26
    assert actions[stop_at] == ["stop", "shutdown"]
    assert 9 <= readings[stop_at].percent <= 13
    assert sum("shutdown" in step for step in actions) == 1, "đã hẹn tắt thì không hẹn lại"


def test_one_low_reading_is_not_enough() -> None:
    """Ước lượng của Windows nhảy xuống 5 phút MỘT lần (tải đột biến) rồi trở lại: không đóng việc."""
    readings = [Reading(0, False, 70, 7200), Reading(20, False, 70, 300), Reading(40, False, 70, 7000),
                Reading(60, False, 70, 7000)]
    state, actions = run(readings)
    assert "stop" not in [action for step in actions for action in step]
    assert state.low_polls == 0


def test_a_declined_shutdown_is_not_asked_again_in_that_battery_run() -> None:
    state = State()
    for t in range(0, 200, 20):
        decide(state, Reading(t, False, 7, None))
    assert state.stopped and state.shutdown_pending
    state.shutdown_pending, state.declined = False, True  # chủ sách bấm "Không tắt máy"
    later = [decide(state, Reading(t, False, 5, None)) for t in range(200, 400, 20)]
    assert "shutdown" not in [action for step in later for action in step]
    assert decide(state, Reading(400, True, 5, None)) == ["ac_back"], "đã đóng việc thì không có gì để chạy tiếp"


def test_power_back_while_a_shutdown_is_pending_aborts_it() -> None:
    state = State()
    for t in range(0, 200, 20):
        decide(state, Reading(t, False, 6, None))
    assert decide(state, Reading(200, True, 6, None)) == ["abort", "ac_back"]


def test_the_estimate_is_the_more_careful_of_windows_and_the_measured_rate() -> None:
    state = State(samples=[(0, 50), (300, 45)])
    assert remaining_minutes(state, Reading(300, False, 45, None)) == 45  # 1%/phút
    assert remaining_minutes(state, Reading(300, False, 45, 20 * 60)) == 20  # Windows bi quan hơn thì theo Windows
    assert remaining_minutes(State(samples=[(0, 50), (60, 49)]), Reading(60, False, 49, None)) is None, \
        "một phút số liệu, % nhảy từng 1: chưa đủ để ước"


def test_the_guard_leaves_ollama_alone_while_an_app_book_runs() -> None:
    """Sách của app tự tạm dừng khi rút sạc, ở ranh giới lô; treo máy chủ Ollama giữa lô thì yêu cầu đang bay hết hạn chờ
    và phần phân tích chạy khác lượt liền mạch (soát QA 29-09)."""
    from power_guard import suspend_servers

    job = "bash gpu_queue_29_09v7.sh"
    app = "C:/ABook/Studio/runtime/pythonw.exe -m abook.background_runner supervise --project-root D:/sach"
    assert suspend_servers([job, "ollama.exe serve"]) is True
    assert suspend_servers([job, app, "ollama.exe serve"]) is False
