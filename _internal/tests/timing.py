"""Hạn chờ theo giờ thật của test - một chỗ duy nhất, nhân với hệ số máy tải.

Test khẳng định "xong trong N giây" hay chờ tới hạn `now + N` đậu trên máy rảnh và hỏng khi máy bận (nhiều bản build,
trình quét, pytest song song cùng chạy), dù mã không sai. Mọi hạn như thế đi qua đây:

    from tests.timing import assert_between, assert_within, scaled

    deadline = time.monotonic() + scaled(5)        # hạn chờ một điều kiện: chỉ là chốt chặn treo, không phải thời gian mong đợi
    assert_within(2.0, started, blocked=20)        # "phải xong ngay, không chờ cổng 20 giây"
    assert_between(1.4, 5, started)                # đã chờ thật (cận dưới giữ nguyên) mà không treo

`ABOOK_TEST_TIME_SCALE` (mặc định 5) là hệ số nhân; máy chậm hơn nữa thì đặt cao hơn. Cận DƯỚI ("đã chờ ít nhất 1,4 giây")
không bao giờ nhân: nó chứng minh có chờ thật, và máy chậm chỉ làm nó dễ đậu hơn.

`blocked=` là thời gian mà hành vi SAI sẽ mất (cổng chờ 20 giây, hạn cũ 30 giây): hạn nhân hệ số bị chặn ở 80% con số ấy, để
nới hạn không biến thành test không bắt được lỗi nó canh. Test đo hiệu năng thật (bắt buộc đúng ngưỡng cố định) không dùng
module này mà mang marker `perf` (bỏ khỏi cổng thường, chạy bằng `pytest -m perf`).

Máy dò `scripts/flaky_patterns.py` (luật elapsed-bound, fixed-deadline) cấm ngưỡng giờ thật cứng ngoài module này.
"""
from __future__ import annotations

import os
import time

SCALE = max(1.0, float(os.environ.get("ABOOK_TEST_TIME_SCALE", "5")))


def scaled(seconds: float) -> float:
    """Hạn `seconds` nhân hệ số máy tải."""
    return seconds * SCALE


def _upper(limit: float, blocked: float | None) -> float:
    bound = scaled(limit)
    if blocked is not None:
        bound = min(bound, 0.8 * blocked)
    return max(limit, bound)


def assert_within(limit: float, since: float, *, blocked: float | None = None, clock=time.monotonic, message: str = "") -> float:
    """Khẳng định đã trôi qua không quá `limit` giây (đã nhân hệ số) kể từ `since`; trả số giây thật."""
    took = clock() - since
    bound = _upper(limit, blocked)
    assert took < bound, message or f"mất {took:.2f} giây, hạn {limit} giây (nhân hệ số: {bound:.1f})"
    return took


def assert_between(low: float, limit: float, since: float, *, blocked: float | None = None, clock=time.monotonic) -> float:
    """Như assert_within, thêm cận dưới `low` giữ nguyên (đã chờ thật)."""
    took = clock() - since
    bound = _upper(limit, blocked)
    assert low < took < bound, f"mất {took:.2f} giây, phải trong ({low}, {limit}) (nhân hệ số: {bound:.1f})"
    return took


def assert_took_within(took: float, limit: float, *, blocked: float | None = None, message: str = "") -> None:
    """Như assert_within khi số giây đã đo sẵn."""
    bound = _upper(limit, blocked)
    assert took < bound, message or f"mất {took:.2f} giây, hạn {limit} giây (nhân hệ số: {bound:.1f})"
