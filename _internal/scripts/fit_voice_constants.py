"""Khớp gain ISO stationary trên bộ trung tính; sách chỉ dùng ở lượt kiểm độc lập."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import math
import os
from pathlib import Path
import sys
import time

for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import soundfile as sf
from scipy.optimize import brentq
from scipy.signal import resample_poly

from abook import audio_io, tts
from abook.book_levels import active_audio, perceived_level
from abook._vendor.zwicker.noct_spectrum import noct_spectrum
from abook._vendor.zwicker.amp2db import amp2db
from abook._vendor.zwicker._main_loudness import _main_loudness
from abook._vendor.zwicker._calc_slopes import _calc_slopes
from abook._vendor.zwicker.loudness_zwst import loudness_zwst
from calibrate_voice_table import dump, SEEDS
import json

TARGET_PHON = 73.0
CHAPTER_GAIN_DB = 5.0


def spectrum(x, rate):
    x = active_audio(x, rate)
    if len(x) < .2 * rate:
        raise ValueError("take has less than 0.2 active seconds")
    if rate != 48000:
        d = math.gcd(rate, 48000)
        x = resample_poly(x, 48000 // d, rate // d)
    spec, _ = noct_spectrum(x * 10 ** ((60 + 25 - 94) / 20), 48000, fmin=24, fmax=12600)
    return amp2db(spec, ref=2e-5)


def calibration_level(x, rate):
    result = perceived_level(x, rate)
    if result is not None:
        return result
    # Câu kiểm cố định có câu ngắn. Vẫn cùng meter, không áp cửa đủ 1 giây
    # của bộ chọn câu sách; không lặp waveform hay thêm im lặng để đủ cửa.
    x = active_audio(x, rate)
    if rate != 48000:
        d = math.gcd(rate, 48000)
        x = resample_poly(x, 48000 // d, rate // d)
    n = float(loudness_zwst(x * 10 ** ((60 + 25 - 94) / 20), 48000)[0])
    return float(40 + 10 * np.log2(max(n, 1e-3)))


def phon(spec, gain):
    n, _ = _calc_slopes(_main_loudness(spec + gain, "free"))
    return 40 + 10 * np.log2(np.maximum(n, 1e-3))


def informational(x, rate):
    # Thang phụ chỉ để báo cáo, tuyệt đối không tham gia khớp gain.
    import pyloudnorm as pyln

    x = active_audio(x, rate)
    rms = 10 * np.log10(max(float(np.mean(x * x)), 1e-20))
    k = x.copy()
    for filt in pyln.Meter(rate)._filters.values():
        k = filt.apply_filter(k)
    kval = 10 * np.log10(max(float(np.mean(k * k)), 1e-20))
    f = np.fft.rfftfreq(len(x), 1 / rate)
    f2 = f * f
    a = 12194 ** 2 * f2 * f2 / np.maximum((f2 + 20.6 ** 2) * np.sqrt((f2 + 107.7 ** 2) * (f2 + 737.9 ** 2)) * (f2 + 12194 ** 2), 1e-20)
    power = abs(np.fft.rfft(x)) ** 2
    # Parseval: nhân đôi năng lượng trừ DC và Nyquist.
    weights = np.full(len(power), 2.0)
    weights[0] = 1
    if len(x) % 2 == 0:
        weights[-1] = 1
    aval = 10 * np.log10(max(float(np.sum(power * weights * (a * 10 ** (2 / 20)) ** 2) / len(x) ** 2), 1e-20))
    return [rms, kval, aval]


def fit_group(folder_string, group):
    folder = Path(folder_string)
    first = group[0][1]
    engine, name = first["engine"], first["preset"]
    token = hashlib.sha256(f"{engine}:{name}".encode()).hexdigest()[:16]
    raw = Path(first.get("raw", folder / "raw" / token))
    # Chỉ áp tempo đã khoá của preset lên bản thô.
    takes = []
    hashes = []
    start = time.perf_counter()
    for i in range(40):
        for seed in SEEDS:
            path = raw / f"{i:02d}_{seed}.wav"
            hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
            x, rate = sf.read(path, dtype="float32")
            x = tts.apply_speed_change(x, rate, first["record"]["r"])
            takes.append((x, rate))
    result = {}
    priority = set(json.loads((folder / "priority_keys.json").read_text(encoding="utf8"))) if (folder / "priority_keys.json").exists() else set()
    group = sorted(group, key=lambda pair: pair[0] not in priority)
    for key, variant in group:
        output = folder / "keys" / (hashlib.sha256(key.encode()).hexdigest() + ".json")
        if output.exists():
            continue
        waves = takes
        spec = np.stack([spectrum(x, rate) for x, rate in waves], axis=1)
        gain = float(brentq(lambda g: float(np.mean(phon(spec, g))) - TARGET_PHON, -25, 25, xtol=1e-7))
        # Bootstrap theo CÂU; hai seed của một câu luôn đi cùng nhau.
        grid = gain + np.linspace(-3, 3, 25)
        curve = np.stack([phon(spec, g).reshape(40, 2).mean(axis=1) for g in grid], axis=1)
        picks = np.random.default_rng(20261106).integers(0, 40, (2000, 40))
        bootstrap_curves = curve[picks].mean(axis=1)
        roots = [float(np.interp(TARGET_PHON, row, grid)) for row in bootstrap_curves]
        if min(roots) <= grid[0] or max(roots) >= grid[-1]:
            raise ValueError(f"bootstrap root outside gain grid: {key}")
        # Đo lại trên waveform đã nhân gain, qua meter công bố đầy đủ.
        verified = [calibration_level(x * 10 ** (gain / 20), rate) for x, rate in waves]
        if any(v is None for v in verified):
            raise ValueError(f"invalid verification take: {key}")
        if abs(float(np.mean(verified)) - TARGET_PHON) > .002:
            raise ValueError(f"spectral solve and waveform meter disagree: {key}")
        final_phon = phon(spec, gain + CHAPTER_GAIN_DB).tolist()
        info = np.mean([informational(x * 10 ** ((gain + CHAPTER_GAIN_DB) / 20), rate) for x, rate in waves], axis=0)
        lufs = float(np.mean([audio_io.integrated_loudness_lufs(x, rate) for x, rate in waves]))
        row = dict(key=key, engine=engine, preset=name, raw=str(raw.resolve()),
                   n_sentences=40, n_takes=80, gain_db=gain, gain_ci95_db=np.percentile(roots, [2.5, 97.5]).tolist(),
                   target_phon=TARGET_PHON, verified_mean_phon=float(np.mean(verified)),
                   predicted_final_phon=float(np.mean(final_phon)), predicted_sentence_phon=np.asarray(final_phon).reshape(40, 2).mean(axis=1).tolist(),
                   informational_final_rms_k_a_db=info.tolist(), ref_lufs=lufs, o_db=gain+25+lufs,
                   raw_sha256=hashes, record=variant["record"])
        output.parent.mkdir(exist_ok=True)
        dump(output, row)
        result[key] = gain
        print("KEY", key, round(gain, 4), flush=True)
    return dict(engine=engine, preset=name, keys=len(result), seconds=time.perf_counter() - start)


def fit_preset(folder_string, group):
    return fit_group(folder_string, group)


def main(folder, workers, priority_only=False):
    variants = json.loads((folder / "protocol.json").read_text(encoding="utf8"))["variants"]
    groups = {}
    priority = set(json.loads((folder / "priority_keys.json").read_text(encoding="utf8"))) if priority_only else None
    for key, variant in variants.items():
        if priority is not None and key not in priority:
            continue
        token = hashlib.sha256(f"{variant['engine']}:{variant['preset']}".encode()).hexdigest()[:16]
        if len(list(Path(variant.get("raw", folder / "raw" / token)).glob("*.wav"))) != 80:
            continue
        groups.setdefault((variant["engine"], variant["preset"]), []).append((key, variant))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fit_preset, str(folder), group) for group in groups.values()]
        failures = []
        for future in as_completed(futures):
            try:
                print(future.result(), flush=True)
            except Exception as exc:
                import traceback
                traceback.print_exc()
                failures.append(repr(exc))
        dump(folder / "fit_failures.json", failures)
        if failures:
            raise RuntimeError(f"{len(failures)} calibration groups failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--priority-only", action="store_true")
    args = parser.parse_args()
    main(args.folder, args.workers, args.priority_only)
