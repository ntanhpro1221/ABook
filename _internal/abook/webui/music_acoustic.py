"""Âm học cho bộ phân tích nhạc của tôi (music_student.py): ~42 đặc trưng cổ điển (Juslin & Lindström 2010, MIRtoolbox của
Eerola, Gabrielsson) đo bằng librosa + numpy, không model. Mỗi bài: ba cửa sổ 30 s ở 20%, 50%, 80% độ dài (bài ngắn: cửa sổ
nào vừa thì lấy, ít nhất một), mono 22050 Hz giải mã bằng ffmpeg; mỗi đặc trưng là trung bình qua các cửa sổ, riêng nhịp, độ to
và trọng tâm phổ có thêm `_sd` (độ lệch chuẩn GIỮA các cửa sổ).

ĐÂY LÀ BẢN CHÉP ĐÚNG SỐ của `LLM_Train/music/acoustic_features2.py` (đặc trưng mà đầu "trò" đã học trên đó): sửa một công thức là
đầu trò lệch. Chỉ `windows` đổi chỗ cắt; giải mã (ffmpeg của app, tần số tuỳ ý - CLAP cần 48 kHz) nằm ở `music_mel.decode`, dùng chung với đường ONNX.

Định nghĩa không hiển nhiên:
- pulse_clarity = đỉnh cao nhất của tự tương quan (đã chuẩn hoá theo độ trễ 0) của đường khởi âm trong độ trễ 0,25-2 s.
- tempo_stability = 1 - CV các khoảng cách phách (beat_track), kẹp 0..1; dưới 4 phách thì bỏ cửa sổ ấy khỏi trung bình.
- mode = tương quan tốt nhất với 12 điệu trưởng - tốt nhất với 12 điệu thứ (Krumhansl-Kessler), dương = trưởng;
  key_clarity = tương quan tốt nhất trong cả 24 điệu.
- roughness: Plomp-Levelt (tham số Sethares) trên 8 đỉnh phổ mạnh nhất mỗi khung, không phụ thuộc độ to.
- speech_band_ratio: tỉ lệ năng lượng 300-3000 Hz (app ghi vào `loudness.speechBand`).
"""
from __future__ import annotations

import warnings

import librosa
import numpy as np

warnings.filterwarnings("ignore")
RATE = 22050
HOP = 512
NFFT = 2048
WIN = 30 * RATE
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])  # Krumhansl-Kessler
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
KEYS_MAJOR = np.array([np.roll(MAJOR, k) for k in range(12)])
KEYS_MINOR = np.array([np.roll(MINOR, k) for k in range(12)])
FREQS = librosa.fft_frequencies(sr=RATE, n_fft=NFFT)
PEAK_BAND = (FREQS >= 50) & (FREQS <= 5000)
IDX_PAIRS = np.triu_indices(8, 1)


def windows(y: np.ndarray) -> list[np.ndarray]:
    n = len(y)
    if n < RATE * 2:
        return []
    if n <= WIN:
        return [y]
    starts = sorted({min(max(int(n * f) - WIN // 2, 0), n - WIN) for f in (0.2, 0.5, 0.8)})
    return [y[s:s + WIN] for s in starts]


def sethares(freq: np.ndarray, amp: np.ndarray) -> float:
    """Độ chối tai Plomp-Levelt trung bình qua khung; freq, amp: (8, T)."""
    fa, fb = freq[IDX_PAIRS[0]], freq[IDX_PAIRS[1]]
    weight = amp[IDX_PAIRS[0]] * amp[IDX_PAIRS[1]]
    s = 0.24 / (0.0207 * np.minimum(fa, fb) + 18.96)
    df = np.abs(fa - fb)
    pair = np.exp(-3.5 * s * df) - np.exp(-5.75 * s * df)
    total = weight.sum(0)
    ok = total > 1e-12
    return float(np.mean((weight * pair).sum(0)[ok] / total[ok])) if ok.any() else float("nan")


def window_features(y: np.ndarray) -> dict:
    y = y.astype(np.float32)
    S = np.abs(librosa.stft(y, n_fft=NFFT, hop_length=HOP))
    P = S ** 2
    total = P.sum() + 1e-12
    out: dict = {}
    # --- độ to / động học
    rms = librosa.feature.rms(S=S, frame_length=NFFT)[0]
    rms_db = 20 * np.log10(rms + 1e-6)
    t = np.arange(len(rms_db)) * HOP / RATE
    out["rms_db"] = float(rms_db.mean())
    out["dynamic_range_db"] = float(np.percentile(rms_db, 95) - np.percentile(rms_db, 5))
    out["crescendo"] = float(np.polyfit(t, rms_db, 1)[0] * 10)
    out["loudness_sd"] = float(rms_db.std())
    # --- nhịp, khởi âm
    mel_pow = librosa.feature.melspectrogram(S=P, sr=RATE, n_mels=128)
    mel_db = librosa.power_to_db(mel_pow)
    onset = librosa.onset.onset_strength(S=mel_db, sr=RATE, hop_length=HOP)
    tempo, beats = librosa.beat.beat_track(onset_envelope=onset, sr=RATE, hop_length=HOP)
    out["tempo"] = float(np.atleast_1d(tempo)[0])
    ibi = np.diff(beats) * HOP / RATE
    out["tempo_stability"] = float(np.clip(1 - ibi.std() / ibi.mean(), 0, 1)) if len(beats) >= 4 and ibi.mean() > 0 else float("nan")
    ac = librosa.autocorrelate(onset - onset.mean())
    ac = ac / (ac[0] + 1e-12)
    lo, hi = int(0.25 * RATE / HOP), int(2 * RATE / HOP)
    out["pulse_clarity"] = float(ac[lo:hi + 1].max())
    peaks = librosa.onset.onset_detect(onset_envelope=onset, sr=RATE, hop_length=HOP)
    out["onset_rate"] = len(peaks) / (len(y) / RATE)
    slope = np.diff(onset, prepend=onset[0])
    out["attack_sharpness"] = float(np.mean([slope[max(f - 2, 0):f + 2].max() for f in peaks]) / (onset.mean() + 1e-9)) if len(peaks) else 0.0
    if len(peaks) >= 2:
        legato = [rms_db[a:min(a + 4, b)].max() - rms_db[a:b + 1].min() <= 6 for a, b in zip(peaks[:-1], peaks[1:])]  # noqa: RUF007 - bản chép đúng
        out["legato_ratio"] = float(np.mean(legato))
    else:
        out["legato_ratio"] = float("nan")
    # --- tông, điệu, âm vực (một CQT dùng chung)
    C = np.abs(librosa.cqt(y, sr=RATE, hop_length=HOP, fmin=librosa.note_to_hz("C1"), n_bins=84, bins_per_octave=12))
    chroma = librosa.feature.chroma_cqt(C=C, sr=RATE, bins_per_octave=12)
    mean_chroma = chroma.mean(1)
    cm = mean_chroma - mean_chroma.mean()
    corr = lambda keys: (keys - keys.mean(1, keepdims=True)) @ cm / (np.linalg.norm(keys - keys.mean(1, keepdims=True), axis=1) * np.linalg.norm(cm) + 1e-12)
    cmaj, cmin = corr(KEYS_MAJOR).max(), corr(KEYS_MINOR).max()
    out["key_clarity"] = float(max(cmaj, cmin))
    out["mode"] = float(cmaj - cmin)
    top = C.max(0)
    keep = top >= 0.01 * top.max()
    midi = 24 + C.argmax(0)
    out["pitch_mean"] = float(np.average(midi, weights=top + 1e-12))
    out["pitch_range"] = float(np.percentile(midi[keep], 90) - np.percentile(midi[keep], 10))
    p = mean_chroma / (mean_chroma.sum() + 1e-12)
    out["chroma_entropy"] = float(-(p * np.log2(p + 1e-12)).sum() / np.log2(12))
    blocks = chroma.shape[1] // 21
    if blocks >= 2:
        coarse = chroma[:, :blocks * 21].reshape(12, blocks, 21).mean(2)
        tonnetz = librosa.feature.tonnetz(chroma=coarse, sr=RATE)
        out["harmonic_change"] = float(np.linalg.norm(np.diff(tonnetz, axis=1), axis=0).mean())
    else:
        out["harmonic_change"] = float("nan")
    # --- âm sắc, đăng ký phổ
    centroid = librosa.feature.spectral_centroid(S=S, sr=RATE)[0]
    out["centroid_hz"] = float(np.median(centroid))
    out["rolloff_hz"] = float(np.median(librosa.feature.spectral_rolloff(S=S, sr=RATE, roll_percent=0.85)[0]))
    out["flatness"] = float(np.median(librosa.feature.spectral_flatness(S=S)[0]))
    out["brightness"] = float(P[FREQS > 1500].sum() / total)
    out["speech_band_ratio"] = float(P[(FREQS >= 300) & (FREQS <= 3000)].sum() / total)
    out["spectral_contrast"] = float(librosa.feature.spectral_contrast(S=S, sr=RATE).mean())
    for i, v in enumerate(librosa.feature.mfcc(S=mel_db, n_mfcc=13).mean(1), 1):
        out[f"mfcc{i}"] = float(v)
    # --- mật độ
    H, Pc = librosa.decompose.hpss(np.sqrt(mel_pow))  # HPSS trên phổ mel (128 dải) cho nhanh ~8 lần
    out["percussive_ratio"] = float((Pc ** 2).sum() / ((H ** 2).sum() + (Pc ** 2).sum() + 1e-12))
    Sn = S / (np.linalg.norm(S, axis=0, keepdims=True) + 1e-12)
    out["spectral_flux"] = float(np.sqrt((np.maximum(np.diff(Sn, axis=1), 0) ** 2).sum(0)).mean())
    # --- đỉnh phổ: độ chối tai + số đỉnh (polyphony)
    inner = S[1:-1]
    is_peak = (inner > S[:-2]) & (inner >= S[2:])
    band = PEAK_BAND[1:-1][:, None]
    Sp = np.where(is_peak & band, inner, 0.0)
    fmax = S.max(0) + 1e-12
    out["polyphony"] = float(((Sp >= 0.01 * fmax) & (Sp > 0)).sum(0).mean())
    top8 = np.argpartition(-Sp, 7, axis=0)[:8]
    cols = np.arange(Sp.shape[1])[None, :]
    amp = Sp[top8, cols]
    a, b, c = S[top8, cols], S[top8 + 1, cols], S[top8 + 2, cols]  # bin top8+1 ở S = đỉnh (inner lệch 1)
    delta = np.clip(0.5 * (a - c) / (a - 2 * b + c - 1e-12), -0.5, 0.5)
    freq = (top8 + 1 + delta) * RATE / NFFT
    out["roughness"] = sethares(freq, amp / fmax[None, :])
    return out


def aggregate(per_window: list[dict]) -> dict:
    keys = per_window[0].keys()
    res = {}
    for k in keys:
        v = np.array([w[k] for w in per_window], dtype=float)
        res[k] = None if np.isnan(v).all() else round(float(np.nanmean(v)), 4)
        if k in ("tempo", "rms_db", "centroid_hz"):
            res[k + "_sd"] = round(float(np.std(v)), 4)
    return res


def features(y: np.ndarray) -> dict | None:
    """Đặc trưng của cả bài đã giải mã ở RATE Hz (aggregate qua các cửa sổ); None khi bài ngắn hơn 2 giây."""
    parts = windows(y)
    return aggregate([window_features(w) for w in parts]) if parts else None
