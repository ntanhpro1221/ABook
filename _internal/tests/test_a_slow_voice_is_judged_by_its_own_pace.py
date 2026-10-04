"""Cổng nhịp: một sàn chung (`pace_floor_scale * x`) cho mọi giọng - và chỉ sàn, chỉ một chiều."""
from __future__ import annotations

import numpy as np
import pytest

from abook import voice_balance
from abook.audio_io import (
    VOICE_BALANCE_FIELD,
    pace_is_outlier,
    segment_duration_policy,
    spoken_speakable_chars,
    validate_audio_array,
)
from abook.config import build_settings

NORMAL = (12.5, 24.5)
RATE = 48_000
SLOW_VOICE_KEY = "vieneu@3.8.3/Đức Trí/f100"
FAST_VOICE_KEY = "vieneu@3.8.3/Phạm Tuyên/f100"
# Không dấu câu nên không có ngân sách nghỉ: nhịp = ký tự đọc được / thời lượng.
LINE = "Người kể chuyện đọc thật chậm rãi từng chữ một trong đêm dài"


def _tone(seconds: float) -> np.ndarray:
    count = int(round(RATE * seconds))
    return (0.3 * np.sin(np.linspace(0.0, 2 * np.pi * 180 * seconds, count))).astype(np.float32)


def test_the_floor_moves_with_the_scale() -> None:
    # 11 kt/s, 3,3 âm tiết/s: chậm theo băng chung, bình thường với sàn nhân 0,81.
    assert pace_is_outlier(11.0, 3.3, "normal", NORMAL)
    assert not pace_is_outlier(11.0, 3.3, "normal", NORMAL, floor_scale=0.81)


def test_the_ceiling_does_not() -> None:
    assert pace_is_outlier(26.0, 7.0, "normal", NORMAL, floor_scale=0.81)
    assert not pace_is_outlier(20.0, 6.0, "normal", NORMAL, floor_scale=0.81)


def test_the_gate_scale_is_the_shared_floor_times_x(monkeypatch) -> None:
    # Lý do sửa: trước đây sàn theo preset (PRESET_PACE_SCALE); giờ MỘT hệ số chung của bảng, nhân
    # thêm x, nên tempo chung đổi thì sàn đổi theo.
    assert voice_balance.pace_gate_scale() == pytest.approx(
        voice_balance.pace_floor_scale() * voice_balance.x()
    )
    table = dict(voice_balance.load_table(), x=0.85)
    monkeypatch.setattr(voice_balance, "load_table", lambda: table)
    assert voice_balance.pace_gate_scale() == pytest.approx(voice_balance.pace_floor_scale() * 0.85)


def test_every_voice_is_judged_by_the_same_floor() -> None:
    settings = build_settings("high_quality")
    scale = voice_balance.pace_gate_scale()
    audio = _tone(spoken_speakable_chars(LINE) / (12.5 * scale * 0.9))  # chậm hơn sàn đã nhân
    plain = {"pace": "normal", "kind": "narration", "text": LINE}
    results = [
        validate_audio_array(audio, LINE, settings, RATE, segment)[1]
        for segment in (
            plain,
            {**plain, VOICE_BALANCE_FIELD: SLOW_VOICE_KEY},
            {**plain, VOICE_BALANCE_FIELD: FAST_VOICE_KEY},
        )
    ]
    assert all(metrics["pace_scale"] == pytest.approx(scale) for metrics in results)
    assert len({metrics["pace_outlier"] for metrics in results}) == 1
    assert results[0]["pace_outlier"] == 1.0
    slower = _tone(spoken_speakable_chars(LINE) / (12.5 * scale * 1.2))
    assert validate_audio_array(slower, LINE, settings, RATE, plain)[1]["pace_outlier"] == 0.0


def test_a_database_row_without_the_field_is_judged_by_the_shared_floor() -> None:
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT 'normal' AS pace, 'narration' AS kind, ? AS text", (LINE,)).fetchone()
    settings = build_settings("high_quality")
    audio = _tone(spoken_speakable_chars(LINE) / 7.0)
    _, metrics = validate_audio_array(audio, LINE, settings, RATE, row)
    assert metrics["pace_outlier"] == 1.0
    segment_duration_policy(LINE, settings, row)


def test_a_slow_voice_gets_the_frames_its_raw_take_needs() -> None:
    # Ngân sách sinh chia sàn cổng cho r_v (x triệt tiêu): giọng chậm (r > 1) cần nhiều khung hơn giọng nhanh.
    settings = build_settings("high_quality")
    text = LINE + " " + LINE
    plain = {"pace": "normal", "kind": "narration", "text": text}
    fast = segment_duration_policy(text, settings, {**plain, VOICE_BALANCE_FIELD: FAST_VOICE_KEY})
    own = segment_duration_policy(text, settings, {**plain, VOICE_BALANCE_FIELD: SLOW_VOICE_KEY})
    assert voice_balance.constants_for_key(SLOW_VOICE_KEY).r > voice_balance.constants_for_key(FAST_VOICE_KEY).r
    assert own.generation_max_frames >= fast.generation_max_frames
    assert own.generation_ceiling_seconds < own.validation_max_seconds
    slow = voice_balance.constants_for_key(SLOW_VOICE_KEY)
    assert voice_balance.raw_pace_floor_scale(slow) == pytest.approx(voice_balance.pace_floor_scale() / slow.r)
