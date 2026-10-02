"""Giải mã ffmpeg + mel cho bộ phân tích nhạc (music_student.py; mel là của đường ONNX): bản numpy thuần của `ClapFeatureExtractor` (transformers) đúng cấu hình
của gói trò (laion/clap-htsat-unfused: truncation "rand_trunc", padding "repeatpad", không fusion). Chỉ numpy - không scipy / librosa /
torch, để bản app chỉ-nghe (Python nhúng, docs/PACKAGING.md) tự tính được. Lệch so với transformers tối đa 7,6e-6 dB trên 36 cửa sổ
thật (Corpus/research/music/onnx_student/README.md); sửa một hằng số là đầu trò lệch.

Cấu hình (preprocessor_config.json): 48 kHz, n_fft = fft_window_size 1024, hop 480, 64 dải mel, 50-14000 Hz, top_db null, cửa sổ 10 giây
(480000 mẫu). Một cửa sổ w (mono, float, <= 10 giây):
 1. ngắn hơn 480000 mẫu thì lặp lại nguyên số lần (repeatpad) rồi đệm 0 bên phải cho đủ 480000;
 2. đệm phản xạ 512 mẫu mỗi bên (mẫu rìa không lặp) -> 481024 mẫu;
 3. 1001 khung 1024 mẫu, bước 480, nhân cửa sổ Hann tuần hoàn (np.hanning(1025)[:1024]); rfft -> 513 bin; công suất = |X|^2;
 4. mel = max(1e-10, công suất @ ngân hàng lọc); ngân hàng lọc (513 x 64) tam giác, thang slaney, chuẩn hoá diện tích slaney;
 5. dB = 10 * log10(mel), tham chiếu 1,0, không kẹp top_db; ra [1001, 64] (thời gian trước, mel sau).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import numpy as np

from ..io_utils import ffmpeg_executable

SAMPLE_RATE = 48_000
N_FFT = 1024
HOP = 480
N_MELS = 64
F_MIN = 50.0
F_MAX = 14_000.0
MAX_SAMPLES = 480_000
MEL_FLOOR = 1e-10
MAX_SECONDS = 1800  # bài dài hơn thế chỉ nghe 30 phút đầu


def decode(path: Path, rate: int) -> np.ndarray:
    """Mono float32 ở `rate` Hz, tối đa MAX_SECONDS giây đầu, giải mã bằng ffmpeg của app. Không đọc được thì mảng rỗng."""
    try:
        raw = subprocess.run([ffmpeg_executable(), "-v", "error", "-nostdin", "-threads", "1", "-i", str(path), "-ac", "1",
                              "-ar", str(rate), "-t", str(MAX_SECONDS), "-f", "f32le", "-"], capture_output=True, check=False,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0).stdout
    except (OSError, subprocess.SubprocessError):
        return np.zeros(0, dtype=np.float32)
    return np.frombuffer(raw, dtype=np.float32)


def _hz_to_mel_slaney(freq: np.ndarray) -> np.ndarray:
    freq = np.asarray(freq, dtype=np.float64)
    mels = 3.0 * freq / 200.0
    log_region = freq >= 1000.0
    return np.where(log_region, 15.0 + np.log(np.maximum(freq, 1e-12) / 1000.0) * (27.0 / np.log(6.4)), mels)


def _mel_to_hz_slaney(mels: np.ndarray) -> np.ndarray:
    mels = np.asarray(mels, dtype=np.float64)
    freq = 200.0 * mels / 3.0
    log_region = mels >= 15.0
    return np.where(log_region, 1000.0 * np.exp((np.log(6.4) / 27.0) * (mels - 15.0)), freq)


def mel_filter_bank() -> np.ndarray:
    """(513, 64): ngân hàng lọc tam giác thang slaney, chuẩn hoá diện tích slaney (= mel_filters_slaney của transformers)."""
    n_bins = N_FFT // 2 + 1
    mel_freqs = np.linspace(_hz_to_mel_slaney(F_MIN), _hz_to_mel_slaney(F_MAX), N_MELS + 2)
    filter_freqs = _mel_to_hz_slaney(mel_freqs)
    fft_freqs = np.linspace(0, SAMPLE_RATE // 2, n_bins)
    slopes = filter_freqs[None, :] - fft_freqs[:, None]  # (513, 66)
    down = -slopes[:, :-2] / np.diff(filter_freqs)[:-1]
    up = slopes[:, 2:] / np.diff(filter_freqs)[1:]
    fbank = np.maximum(0.0, np.minimum(down, up))
    enorm = 2.0 / (filter_freqs[2:N_MELS + 2] - filter_freqs[:N_MELS])
    return fbank * enorm[None, :]


_FBANK = mel_filter_bank()
_WINDOW = np.hanning(N_FFT + 1)[:N_FFT]  # Hann tuần hoàn


def pad_window(wave: np.ndarray) -> np.ndarray:
    """repeatpad cho đủ đúng 10 giây (cửa sổ dài hơn không dùng tới - trò chỉ đưa vào cửa sổ <= 10 giây; nếu có thì cắt)."""
    wave = np.asarray(wave, dtype=np.float64)
    if wave.shape[0] > MAX_SAMPLES:
        return wave[:MAX_SAMPLES]
    if wave.shape[0] < MAX_SAMPLES:
        wave = np.tile(wave, int(MAX_SAMPLES / wave.shape[0]))
        wave = np.pad(wave, (0, MAX_SAMPLES - wave.shape[0]), mode="constant")
    return wave


def log_mel(wave: np.ndarray) -> np.ndarray:
    """Một cửa sổ -> float32 [1001, 64] log-mel (dB): đầu vào của tháp trừ hai trục lô / kênh."""
    wave = np.pad(pad_window(wave), (N_FFT // 2, N_FFT // 2), mode="reflect")
    n_frames = 1 + (wave.shape[0] - N_FFT) // HOP
    frames = np.lib.stride_tricks.as_strided(
        wave, shape=(n_frames, N_FFT), strides=(wave.strides[0] * HOP, wave.strides[0]), writeable=False)
    spec = np.fft.rfft(frames * _WINDOW[None, :], axis=1)
    power = spec.real ** 2 + spec.imag ** 2  # (khung, 513)
    mel = np.maximum(MEL_FLOOR, power @ _FBANK)  # (khung, 64)
    return (10.0 * np.log10(mel)).astype(np.float32)


def input_features(windows: list[np.ndarray]) -> np.ndarray:
    """Các cửa sổ -> float32 [n, 1, 1001, 64], đúng đầu vào của tháp ONNX."""
    return np.stack([log_mel(w) for w in windows])[:, None, :, :]


def check_config(preprocessor_config: Path) -> None:
    """Báo lỗi nếu preprocessor_config.json của gói không còn là cấu hình mà module này chép cứng."""
    config = json.loads(Path(preprocessor_config).read_text(encoding="utf-8"))
    expect = {"sampling_rate": SAMPLE_RATE, "n_fft": N_FFT, "fft_window_size": N_FFT, "hop_length": HOP, "feature_size": N_MELS,
              "frequency_min": F_MIN, "frequency_max": F_MAX, "nb_max_samples": MAX_SAMPLES, "padding": "repeatpad",
              "truncation": "rand_trunc", "top_db": None}
    for key, value in expect.items():
        if config.get(key) != value:
            raise ValueError(f"preprocessor_config {key}={config.get(key)!r}, music_mel chép cứng {value!r}")
