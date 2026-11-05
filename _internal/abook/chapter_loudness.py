"""Đích master chương giữ độ lệch đã áp lên câu, neo theo trung bình toàn sách."""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from typing import Any

from .audio_io import segment_offsets_db
from .voice_balance import constants_for_profile

ALGORITHM = "speech_weighted_applied_offsets_v1"


def level_source_signature(rows: list[Any], profiles: list[Any], settings: dict[str, Any]) -> str:
    """Khóa hiệu chỉnh với nguồn gốc, không parse lại signal cho mỗi chương."""
    fields = ('chapter_id', 'stable_id', 'wav_sha256', 'wav_duration', 'signal_json',
              'voice_profile_id', 'volume', 'emotion', 'intensity', 'speaker')
    payload = [sorted((tuple(dict(r).get(k) for k in fields) for r in rows), key=lambda r: str(r[:2])),
               sorted((dict(p) for p in profiles), key=lambda p: p['id']), settings['audio']]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def chapter_level_plan(rows: list[Any], profiles: list[Any], settings: dict[str, Any],
                       corrections: dict[str, Any] | None = None) -> dict[int, dict[str, Any]]:
    """Tính bằng số giây có tiếng, bỏ break và lặng đo được, kể cả câu tách phần.

    ref_lufs là neo mức THÔ, không phải offset tương đối. Giữ o_db + cảm xúc + volume
    + người kể, trừ phần hạ thực do trần đỉnh. Chương chưa thu chưa có trọng số;
    đường ống chốt lại mọi đích sau khi đã có WAV cả sách.
    """
    voices = {int(p["id"]): p for p in profiles}
    corrections = corrections or {}
    from .voice_balance import voice_key_for_profile
    groups: dict[int, list[tuple[float, float, str, str]]] = defaultdict(list)
    for item in rows:
        row = dict(item)
        if not row.get("wav_duration") or not row.get("wav_sha256"):
            continue
        signal = json.loads(row.get("signal_json") or "{}")
        parts = signal.get("split_parts") or [signal]
        entries = []
        for part in parts:
            duration = part.get("level_speech_seconds")
            offset = part.get("applied_level_offset_db")
            if duration is None or offset is None:
                # Các bản thu tự có nhịp (vocalization) vẫn mang offset của giọng đã khoá.
                duration = max(0.0, float(row["wav_duration"])-float(signal.get("measured_silence_seconds", 0)))
                offset = constants_for_profile(voices[int(row["voice_profile_id"])]).o_db + segment_offsets_db(row, settings)
                offset -= float(signal.get("peak_limited_db", 0))
                entries = [(duration, offset)]
                break
            entries.append((float(duration), float(offset)))
        seconds = math.fsum(d for d, _ in entries)
        if seconds <= 0:
            continue
        offset = math.fsum(d*o for d, o in entries)/seconds
        profile = voices.get(int(row.get("voice_profile_id") or 0))
        key = voice_key_for_profile(profile) if profile is not None else ""
        offset += float(corrections.get("voices", {}).get(key, 0.0))
        if not math.isfinite(seconds) or not math.isfinite(offset):
            raise ValueError("Non-finite chapter level evidence")
        groups[int(row["chapter_id"])].append((seconds, offset, str(row["stable_id"]), str(row["wav_sha256"])))
    total = math.fsum(d for group in groups.values() for d, _, _, _ in group)
    book_mean = math.fsum(d*o for group in groups.values() for d, o, _, _ in group)/total if total else 0.0
    result = {}
    for chapter_id, entries in sorted(groups.items()):
        duration = math.fsum(e[0] for e in entries)
        mean = math.fsum(e[0]*e[1] for e in entries)/duration
        target = float(settings["audio"]["loudness_lufs"])+mean-book_mean
        residual = float(corrections.get("chapters", {}).get(str(chapter_id), 0.0))
        target += residual
        signature = hashlib.sha256(json.dumps(
            [ALGORITHM, target, sorted(entries), corrections.get("history", [])], ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode()).hexdigest()
        result[chapter_id] = {"algorithm": ALGORITHM, "target_lufs": target,
            "speech_seconds": duration, "chapter_offset_db": mean, "book_offset_db": book_mean,
            "signature": signature}
    return result
