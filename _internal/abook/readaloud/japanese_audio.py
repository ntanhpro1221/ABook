"""Shorten model-generated low-energy gaps inside aligned automatic names.

No guessed word timings: absent or unreliable CTC alignment leaves audio intact.
Studio runs this after tempo and before signal/content QA on the final waveform.
"""
from __future__ import annotations

import math
import re
from typing import Any, Iterable

VERSION = "jp-name-audio1"
MIN_CONFIDENCE = 0.7
MIN_GAP_MS = 120
KEEP_GAP_MS = 80
WINDOW_MS = 10
HOP_MS = 5
FADE_MS = 5
ABSOLUTE_FLOOR_DBFS = -45
RELATIVE_FLOOR_DB = -30
MAX_SECONDS = 90
_WORD = re.compile(r"[^\W\d_]+_?(?:-[^\W\d_]+_?)+")


def word_spans(text: str, groups: Iterable[str]) -> list[tuple[int, int]]:
    chosen = {word.casefold() for word in groups}
    return [match.span() for match in _WORD.finditer(text) if match.group().casefold() in chosen]


def low_energy_runs(audio: Any, rate: int) -> tuple[list[tuple[int, int]], float]:
    """The frozen 10 ms RMS / 5 ms hop diagnostic, in source sample coordinates."""
    import numpy as np

    hop, window = round(rate * HOP_MS / 1000), round(rate * WINDOW_MS / 1000)
    envelope = np.array([np.sqrt(np.mean(audio[i:i + window] ** 2) + 1e-20)
                         for i in range(0, len(audio) - window + 1, hop)])
    if not envelope.size:
        return [], 10 ** (ABSOLUTE_FLOOR_DBFS / 20)
    threshold = max(10 ** (ABSOLUTE_FLOOR_DBFS / 20), float(envelope.max()) * 10 ** (RELATIVE_FLOOR_DB / 20))
    changes = np.diff(np.r_[False, envelope < threshold, False].astype(int))
    return [(int(a * hop), int(b * hop + window - hop))
            for a, b in zip(np.flatnonzero(changes == 1), np.flatnonzero(changes == -1))], threshold


def shorten(audio: Any, rate: int, ranges: Iterable[tuple[float, float]]) -> tuple[Any, dict]:
    """Edit only the quiet middle of runs wholly inside independently aligned words.

    Keep 80 ms including a 5 ms linear crossfade, preserving the low-energy edges
    and every sample outside the edit intervals. Consonant closures can be quiet
    too: this bounds their duration rather than deleting the whole closure.
    """
    import numpy as np

    wave = np.asarray(audio, dtype=np.float32).reshape(-1)
    if rate < 1000 or not np.isfinite(wave).all():
        raise ValueError("Japanese gap repair needs finite mono audio and a valid rate")
    selected = sorted(set((float(a), float(b)) for a, b in ranges))
    if any(not (math.isfinite(a) and math.isfinite(b) and 0 <= a < b <= len(wave) / rate + 1e-6) for a, b in selected):
        raise ValueError("Invalid aligned Japanese word range")
    if any(b > c for (_, b), (c, _) in zip(selected, selected[1:])):
        raise ValueError("Overlapping aligned Japanese words")
    runs, threshold = low_energy_runs(wave, rate)
    keep, fade = round(rate * KEEP_GAP_MS / 1000), round(rate * FADE_MS / 1000)
    edits = []
    for lo, hi in runs:
        if (hi - lo) * 1000 < MIN_GAP_MS * rate:
            continue
        owner = next((i for i, (a, b) in enumerate(selected) if lo / rate >= a and hi / rate <= b), None)
        if owner is None:
            continue
        remove = hi - lo - keep - fade
        start = lo + (hi - lo - remove) // 2
        end = start + remove
        if remove <= 0 or start - fade <= lo or end + fade >= hi:
            continue
        edits.append(dict(word=owner,run_start=lo,run_end=hi,start=start,end=end,fade=fade,removed_samples=remove + fade))
    out = wave
    for edit in reversed(edits):
        start, end, fade = edit['start'], edit['end'], edit['fade']
        ramp = np.linspace(0, 1, fade, dtype=np.float32)
        blend = out[start - fade:start] * (1 - ramp) + out[end:end + fade] * ramp
        out = np.concatenate((out[:start - fade], blend, out[end + fade:]))
    return out, dict(version=VERSION,edits=edits,threshold_dbfs=20 * math.log10(threshold),
                     original_samples=len(wave),final_samples=len(out),removed_ms=(len(wave)-len(out))*1000/rate)


def repair(audio: Any, rate: int, text: str, spans: Iterable[tuple[int, int]], aligner: Any) -> tuple[Any, dict]:
    """Align expanded syllables and repair only exact automatic word occurrences."""
    from ..webui.word_timing import spoken_syllables

    requested = sorted(set(spans))
    words = []
    for start, end in requested:
        if not (0 <= start < end <= len(text)):
            continue
        words.extend((start + m.start(), start + m.end()) for m in _WORD.finditer(text[start:end]))
    if not words:
        return audio, dict(version=VERSION,status="not_applicable",edits=[])
    if aligner is None:
        return audio, dict(version=VERSION,status="no_alignment_model",edits=[])
    if not audio.size or len(audio) / rate > MAX_SECONDS:
        return audio, dict(version=VERSION,status="alignment_duration_limit",edits=[])
    tokens, owners = [], []
    for match in re.finditer(r"[^\W_]+", text):
        for syllable in spoken_syllables(match.group()):
            tokens.append(syllable)
            owners.append(match.span())
    from scipy.signal import resample_poly

    divisor = math.gcd(rate, 16000)
    result = aligner.align(resample_poly(audio, 16000 // divisor, rate // divisor), " ".join(tokens))
    if result is None or not math.isfinite(result[1]) or result[1] < MIN_CONFIDENCE:
        return audio, dict(version=VERSION,status="unreliable_alignment",edits=[],confidence=result[1] if result else 0)
    aligned, confidence = result
    if len(aligned) != len(tokens):
        return audio, dict(version=VERSION,status="incomplete_alignment",edits=[],confidence=confidence)
    ranges = []
    for start, end in words:
        indices = [i for i, (a, b) in enumerate(owners) if a >= start and b <= end]
        if not indices or any(aligned[i] is None for i in indices):
            continue
        ranges.append((float(aligned[indices[0]][0]), float(aligned[indices[-1]][1])))
    out, evidence = shorten(audio, rate, ranges)
    return out, dict(evidence,status="repaired" if evidence['edits'] else "clear",confidence=confidence,name_ranges=ranges)


def repair_anchors(audio: Any, rate: int, text: str, anchors: Iterable[dict]) -> tuple[Any, dict]:
    from .japanese_delivery import anchor_spans
    from ..webui.word_timing import get_aligner

    spans = anchor_spans(text, anchors)
    return repair(audio, rate, text, spans, get_aligner() if spans else None)
