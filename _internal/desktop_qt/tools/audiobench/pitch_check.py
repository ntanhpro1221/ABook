"""Cao độ giữa các tốc độ (D1 bước 1): đọc các WAV bắt qua loopback, trả F0 trung vị (Hz) của đoạn có tiếng.
Giữ cao độ = F0 ở 1,5x / 2x / 3x gần F0 ở 1x (lệch < 3 %). Không giữ = F0 nhân theo tốc độ.
  python -X utf8 pitch_check.py <wav>...
"""
import sys

import numpy as np
import soundfile as sf


def median_f0(path: str) -> dict:
    data, rate = sf.read(path, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    peak = float(np.max(np.abs(data))) or 1.0
    data = data / peak
    frame, hop = int(0.04 * rate), int(0.02 * rate)
    lo, hi = int(rate / 300), int(rate / 70)
    rms_all = np.sqrt(np.mean(data ** 2))
    values = []
    for start in range(0, len(data) - frame, hop):
        x = data[start:start + frame]
        if np.sqrt(np.mean(x ** 2)) < 0.5 * rms_all:
            continue
        x = x - x.mean()
        spec = np.fft.rfft(x, 2 * frame)
        ac = np.fft.irfft(spec * np.conj(spec))[:frame]
        if ac[0] <= 0:
            continue
        ac = ac / ac[0]
        lag = lo + int(np.argmax(ac[lo:hi]))
        if ac[lag] > 0.5:
            values.append(rate / lag)
    return {"file": path, "peak": peak, "voiced_frames": len(values), "f0_median": float(np.median(values)) if values else None,
            "f0_p25": float(np.percentile(values, 25)) if values else None, "f0_p75": float(np.percentile(values, 75)) if values else None}


if __name__ == "__main__":
    for item in sys.argv[1:]:
        print(median_f0(item))
