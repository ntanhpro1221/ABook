"""Hằng số tốc độ mỗi giọng: nhanh hơn thật, giữ cao độ, và mặc định không đổi gì.

Vì sao có: bốn giọng kiểu đọc truyện của VieNeu 3.8.1 đọc 10,9-12,7 kt/s, dưới sàn 12,5 của cổng
nhịp - Đức Trí, người dẫn chuyện chủ sách chọn, ngoài băng 23/25 câu. Cao độ gốc không chữa được vì
`apply_pitch_variant` giữ nguyên độ dài câu. Hệ số nằm trong bảng `voice_balance` (tempo = x * r_v).
"""
from __future__ import annotations

import numpy as np
import pytest
import pyworld

from abook.audio_io import integrated_loudness_lufs
from abook.tts import WORLD_MIN_SECONDS, WSOLA_FRAME_SECONDS, apply_speed_change
from abook import voice_balance
from abook.voice_catalog import SPEED_FACTOR_MAX, SPEED_FACTOR_MIN

RATE = 24_000


def voiced(seconds: float = 1.2, f0: float = 150.0) -> np.ndarray:
    t = np.arange(int(RATE * seconds)) / RATE
    tone = sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 8))
    envelope = 0.6 + 0.4 * np.sin(2 * np.pi * 3.0 * t)
    return (0.2 * tone * envelope).astype(np.float32)


def median_f0(audio: np.ndarray) -> float:
    f0, _ = pyworld.harvest(audio.astype(np.float64), RATE, f0_floor=55.0, f0_ceil=600.0)
    return float(np.median(f0[f0 > 0]))


@pytest.mark.parametrize("speed", [0.76, 0.89, 1.20, 1.27, 1.35])
def test_a_speed_factor_sets_the_length_to_exactly_one_over_it(speed: float) -> None:
    audio = voiced()
    faster = apply_speed_change(audio, RATE, speed)
    assert faster.size == round(audio.size / speed)


@pytest.mark.parametrize("speed", [0.89, 1.30])
def test_a_speed_factor_keeps_the_pitch(speed: float) -> None:
    audio = voiced(f0=150.0)
    faster = apply_speed_change(audio, RATE, speed)
    assert median_f0(faster) == pytest.approx(median_f0(audio), rel=0.01)


@pytest.mark.parametrize("speed", [0.89, 1.30])
def test_stretching_keeps_the_loudness(speed: float) -> None:
    # Tương quan chuẩn hoá: giọng thật 04-10 lệch -0,21..+0,03 dB. Bản tương quan thô trước đó nghiêng về
    # đoạn to và nâng +0,4..0,6 dB; bảng cân bằng vẫn đo độ to SAU bước này, test chặn việc quay lại.
    audio = voiced(seconds=3.0)
    before = integrated_loudness_lufs(audio, RATE)
    after = integrated_loudness_lufs(apply_speed_change(audio, RATE, speed), RATE)
    assert abs(after - before) < 0.3


def test_a_take_shorter_than_one_frame_still_gets_its_length() -> None:
    # Giữa WORLD_MIN_SECONDS (đi qua nguyên vẹn) và một khung WSOLA: vẫn co giãn, không văng.
    audio = voiced(seconds=WSOLA_FRAME_SECONDS / 2)
    assert audio.size >= WORLD_MIN_SECONDS * RATE
    faster = apply_speed_change(audio, RATE, 1.30)
    assert faster.size == round(audio.size / 1.30)
    assert np.all(np.isfinite(faster))


@pytest.mark.parametrize("speed", [0.89, 1.30])
def test_it_keeps_the_pitch_of_the_reference_wsola_and_the_loudness_better(speed: float) -> None:
    # audiotsm là phụ thuộc DEV, không đóng vào app: chỉ dùng để đối chiếu bản viết tay. Dạng sóng
    # lệch pha nên không so từng mẫu; độ dài cũng không - audiotsm bỏ phần đuôi chưa đủ khung (ngắn hơn
    # 1/r chừng 2 %), bản của app cắt đúng 1/r. audiotsm chọn chỗ nối bằng tương quan THÔ (nghiêng về
    # đoạn to) nên to hơn bản gốc; bản của app (chuẩn hoá) phải giữ độ to sát bản gốc hơn nó.
    audiotsm = pytest.importorskip("audiotsm")
    from audiotsm.io.array import ArrayReader, ArrayWriter

    audio = voiced(seconds=3.0)
    writer = ArrayWriter(channels=1)
    frame = int(WSOLA_FRAME_SECONDS * RATE)
    audiotsm.wsola(channels=1, speed=speed, frame_length=frame, synthesis_hop=frame // 2).run(
        ArrayReader(audio.reshape(1, -1)), writer
    )
    reference = writer.data.reshape(-1).astype(np.float32)
    ours = apply_speed_change(audio, RATE, speed)
    assert median_f0(ours) == pytest.approx(median_f0(reference), rel=0.01)
    source = integrated_loudness_lufs(audio, RATE)
    assert abs(integrated_loudness_lufs(ours, RATE) - source) < abs(integrated_loudness_lufs(reference, RATE) - source)


def test_no_factor_means_no_change_at_all() -> None:
    audio = voiced()
    assert np.array_equal(apply_speed_change(audio, RATE, 1.0), audio)


def test_a_factor_outside_the_range_is_refused() -> None:
    with pytest.raises(ValueError):
        apply_speed_change(voiced(), RATE, SPEED_FACTOR_MAX + 0.1)
    with pytest.raises(ValueError):
        apply_speed_change(voiced(), RATE, SPEED_FACTOR_MIN - 0.1)


def test_the_range_now_reaches_the_slow_tempi_the_shared_knob_asks_for() -> None:
    # x ~ 0,85 nhân r ~ 0,89 là 0,76: sàn cũ 0,80 từ chối nó.
    assert SPEED_FACTOR_MIN == 0.70
    assert apply_speed_change(voiced(), RATE, 0.76).size > voiced().size


def test_every_tabulated_tempo_is_inside_the_range() -> None:
    table = voice_balance.load_table()
    for key, record in table["voices"].items():
        assert SPEED_FACTOR_MIN <= table["x"] * record["r"] <= SPEED_FACTOR_MAX, key


def test_the_speed_step_runs_after_pitch_and_skips_the_laugh() -> None:
    # Hàm cao độ cắt/đệm về độ dài gốc, nên tốc độ PHẢI chạy sau nó; và tiếng cười "ha" có bất
    # biến số mẫu thô nên không được đổi tốc độ. Soi thẳng mã, vì dựng cả engine TTS cho một thứ
    # tự hai dòng là quá nặng.
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "abook" / "tts.py").read_text(encoding="utf-8")
    pitch_at = source.index("pitched_audio = apply_pitch_variant(\n                        audio,\n                        self.vieneu.sample_rate,\n                        pitch_steps,\n                    )")
    speed_at = source.index("audio = apply_speed_change(audio, self.vieneu.sample_rate, speed_factor)")
    assert pitch_at < speed_at
    assert "vocalization_delivery_profile != HA_VOCALIZATION_DELIVERY_PROFILE" in source[pitch_at:speed_at]
