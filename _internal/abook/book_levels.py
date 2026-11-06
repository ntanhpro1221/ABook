"""Đo mức nghe trên MP3 cuối, chỉ cảnh báo; bản thu và bằng chứng QA câu bất biến."""
from __future__ import annotations

import hashlib
import io
import json
import math
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from ._vendor.zwicker.loudness_zwst import loudness_zwst

METER = "active_ISO532_1_stationary_v1"
VOICE_SPREAD_PHON = 1.5
CHAPTER_DELTA_PHON = 1.0
MIN_LINES = 12


def balance_limits(result: dict[str, Any]) -> tuple[float, float]:
    """Độ trải giọng và độ lệch chương lớn nhất, giữ riêng hai điều kiện PASS."""
    return (float(result.get("voice_spread_phon") or 0),
            max((abs(r["delta_phon"]) for r in result.get("chapters", {}).values()), default=0))


def balance_satisfied(result: dict[str, Any]) -> bool:
    voice, chapter = balance_limits(result)
    coverage = result.get("coverage", {})
    return (bool(result.get("voices") and result.get("chapters"))
            and coverage.get("measured_chapters") == coverage.get("total_chapters")
            and voice <= 1.5 and chapter <= 1.0)


def active_audio(audio: np.ndarray, rate: int) -> np.ndarray:
    """Giữ khung 20 ms trên đỉnh RMS −30 dB, tối đa 8 giây có tiếng."""
    n = max(1, round(.02 * rate))
    x = np.asarray(audio, dtype=np.float64).reshape(-1)
    if len(x) < n:
        return np.empty(0)
    frames = x[:len(x)//n*n].reshape(-1, n)
    energy = np.mean(frames*frames, axis=1)
    return frames[energy > max(1e-12, float(energy.max())*.001)].reshape(-1)[:8*rate]


def perceived_level(audio: np.ndarray, rate: int) -> float | None:
    """Phon stationary với neo phát lại cố định như phép đo dev; không phải SPL tại tai."""
    x = active_audio(audio, rate)
    if len(x) < rate:
        return None
    if rate != 48000:
        divisor = math.gcd(rate, 48000)
        x = resample_poly(x, 48000//divisor, rate//divisor)
    sones = float(loudness_zwst(x*10**((60+25-94)/20), 48000)[0])
    return float(40+10*np.log2(max(sones, 1e-3)))


def _summary(values: list[float]) -> dict[str, Any]:
    a = np.asarray(values)
    means = a[np.random.default_rng(7).integers(0, len(a), (2000, len(a)))].mean(axis=1)
    return {"n": len(a), "mean_phon": float(a.mean()),
            "ci95_phon": np.percentile(means, [2.5, 97.5]).tolist()}


def measure_finished_book(
    chapters: list[dict[str, Any]],
    open_audio: Callable[[Any], Any] = lambda path: sf.SoundFile(path),
    *, seed: str = "fit-v1", exclude: set[str] | None = None,
) -> dict[str, Any]:
    """Đọc các MP3 + mốc câu cuối. Mỗi giọng 60 câu, mỗi chương 40 câu; chọn bằng SHA256.

    `segments`: voice, stable_id, start, end. Không trả chữ hay âm thanh.
    Khoảng tin cậy bootstrap theo câu, chưa tính tương quan giữa câu cùng chương.
    """
    voices: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    per_chapter: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    known_voices = {str(g['voice']) for chapter in chapters for g in chapter['segments'] if g.get('voice')}
    for index, chapter in enumerate(chapters):
        for segment in chapter["segments"]:
            if str(segment["stable_id"]) in (exclude or set()):
                continue
            if not segment.get("voice"):
                continue
            start, end = float(segment["start"]), float(segment["end"])
            if not (math.isfinite(start) and math.isfinite(end) and start >= 0 and end-start >= 1.5):
                continue
            voices[str(segment["voice"])].append((index, segment))
            per_chapter[str(chapter["id"])].append((index, segment))
    def pick(rows, limit):
        return sorted(rows, key=lambda r: hashlib.sha256(
            f"{seed}:{r[0]}:{r[1]['stable_id']}".encode()).digest())[:limit]
    selected: dict[tuple[int, str], tuple[dict[str, Any], list[tuple[str, str]]]] = {}
    for scope, groups, limit in (("voices", voices, 60), ("chapters", per_chapter, 40)):
        for group, rows in sorted(groups.items()):
            for index, segment in pick(rows, limit):
                token = (index, str(segment["stable_id"]))
                selected.setdefault(token, (segment, []))[1].append((scope, group))
    values: dict[str, dict[str, list[float]]] = {"voices": defaultdict(list), "chapters": defaultdict(list)}
    measured_ids = []
    for index, chapter in enumerate(chapters):
        items = [(s, groups) for (i, _), (s, groups) in selected.items() if i == index]
        if not items:
            continue
        with open_audio(chapter["file"]) as audio:
            rate = audio.samplerate
            for segment, groups in items:
                a, b = int(float(segment["start"])*rate), int(float(segment["end"])*rate)
                if b > len(audio) + round(.1*rate):
                    raise ValueError("Mốc câu vượt MP3 cuối")
                audio.seek(a)
                # Đọc tối đa 30 giây; meter chỉ giữ 8 giây có tiếng.
                x = audio.read(min(b-a, 30*rate), dtype="float64", always_2d=True).mean(axis=1)
                level = perceived_level(x, rate)
                if level is not None:
                    measured_ids.append(str(segment["stable_id"]))
                    for scope, group in groups:
                        values[scope][group].append(level)
    result: dict[str, Any] = {"meter": METER, "unit": "phon (fixed playback reference)",
        "thresholds": {"voice_spread_phon": VOICE_SPREAD_PHON, "chapter_delta_phon": CHAPTER_DELTA_PHON},
        "ci_method": "sentence bootstrap, seed=7, 2000; within-chapter dependence not modelled"}
    result["sample_seed"] = seed
    result["measured_ids"] = sorted(set(measured_ids))
    result["insufficient_voices"] = {k: len(values["voices"].get(k, [])) for k in sorted(known_voices)
                                     if len(values["voices"].get(k, [])) < MIN_LINES}
    result["sparse_voices"] = {k: _summary(xs) for k, xs in sorted(values["voices"].items())
                              if 0 < len(xs) < MIN_LINES}
    for scope, groups in values.items():
        result[scope] = {k: _summary(v) for k, v in sorted(groups.items()) if len(v) >= MIN_LINES}
    v = [r["mean_phon"] for r in result["voices"].values()]
    fitted = [x for k, xs in values["voices"].items() if len(xs) >= MIN_LINES for x in xs]
    result["book_mean_phon"] = float(np.mean(fitted)) if fitted else None
    c = [r["mean_phon"] for r in result["chapters"].values()]
    result["voice_spread_phon"] = max(v)-min(v) if len(v) >= 2 else None
    # CI của độ trải dùng cùng phép lấy mẫu câu, không giả làm CI theo sách độc lập.
    for scope, label in (("voices", "voice_spread_ci95_phon"), ("chapters", "chapter_range_ci95_phon")):
        rng = np.random.default_rng(19)
        samples = []
        for group, xs in sorted(values[scope].items()):
            if len(xs) >= MIN_LINES:
                a = np.asarray(xs)
                samples.append(a[rng.integers(0, len(a), (2000, len(a)))].mean(axis=1))
        result[label] = np.percentile(np.ptp(samples, axis=0), [2.5, 97.5]).tolist() if len(samples) >= 2 else None
    result["chapter_range_phon"] = max(c)-min(c) if c else None
    result["coverage"] = {"measured_chapters": len(c), "total_chapters": len(chapters)}
    ref = float(np.median(c)) if c else None
    for row in result["chapters"].values():
        row["delta_phon"] = row["mean_phon"]-ref
    flags = []
    if len(v) >= 2 and max(v)-min(v) > VOICE_SPREAD_PHON:
        flags.append("VOICE_LEVEL_SPREAD")
    if len(c) >= 2 and any(abs(x-ref) > CHAPTER_DELTA_PHON for x in c):
        flags.append("CHAPTER_LEVEL_DELTA")
    sufficient = len(v) >= 2 and len(c) == len(chapters)
    result.update(flags=flags, verdict="warning" if flags else "pass" if sufficient else "insufficient_data")
    return result


def measure_package(path: Path, *, seed: str = "fit-v1", exclude: set[str] | None = None) -> dict[str, Any]:
    """Gói chỉ mở đọc, audio giải mã trong RAM; không giải nén chữ/audio ra đĩa."""
    with zipfile.ZipFile(path) as archive:
        book = json.loads(archive.read("book.json"))
        cast = json.loads(archive.read("cast.json"))
        def key(v):
            return v if isinstance(v, str) else str(v.get("preset") or v.get("key") or "")
        narrator = key(cast["narrator"]["voice"])
        mapping = {r["name"]: key(r["voice"]) for r in cast["characters"]+cast["extras"]}
        mapping.update({"NARRATOR": narrator, "": narrator})
        chapters = []
        for ch in book["chapters"]:
            segments = []
            for g in json.loads(archive.read(ch["script"]))["segments"]:
                segments.append({"voice": mapping.get(g["speaker"], narrator if g["kind"] in ("narration", "heading") else None),
                    "stable_id": g["stableId"], "start": g["start"], "end": g["end"]})
            chapters.append({"id": ch["index"], "file": ch["file"], "segments": segments})
        return measure_finished_book(chapters, lambda name: sf.SoundFile(io.BytesIO(archive.read(name))), seed=seed, exclude=exclude)
