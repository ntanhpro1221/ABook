"""Các ĐOẠN của một chương và không khí của từng đoạn - nền cho nhạc nền (chủ sách 01-10: nhạc là một lớp riêng của cuốn
sách, như phụ đề của video; máy tự gắn, người dùng sửa nếu muốn).

Không cần model: mỗi câu đã có cảm xúc, cường độ, nhịp, âm lượng (bộ phân tích gán lúc làm sách, có sẵn trong mọi `.abook`).
Mỗi cảm xúc là một điểm trên hai trục của mô hình tròn cảm xúc (Russell 1980): VALENCE vui (+) / buồn (-), AROUSAL dồn dập (+) /
êm (-). Đoạn = một khúc liền nhau cùng không khí:

1. Ranh giới CỨNG từ chữ: đầu chương, dòng ngăn cảnh (`***`, `* * *`, `---`...), câu mở bằng mốc nhảy thời gian ("Sáng hôm
   sau", "Ba ngày sau"...).
2. Trong khúc giữa hai ranh giới cứng: không khí trượt (trung bình theo thời lượng đọc, cửa sổ ~45 giây) đổi XA khỏi không khí
   của đoạn đang mở và GIỮ đủ lâu thì cắt đoạn mới - một câu kêu lên giữa cảnh bình yên không đổi nhạc.
3. Đoạn ngắn hơn MIN_SCENE_SECONDS gộp vào đoạn kề gần không khí nhất.

Câu kể trung tính (phần lớn văn bản) nặng ít hơn: nó không nói lên không khí, chỉ là nền. `confidence` = phần trọng số đến
từ câu CÓ cảm xúc - thấp thì đoạn không có không khí rõ (chọn nhạc nhẹ hay để im lặng là việc của bước chọn nhạc).
"""
from __future__ import annotations

import math
import re
from typing import Any, Iterable

# (valence, arousal) trên [-1, 1]. Đặt theo mô hình tròn cảm xúc; "sarcastic" và "whispering" là cách nói hơn là cảm xúc -
# gần trung tính, chỉ kéo arousal.
EMOTION_VA: dict[str, tuple[float, float]] = {
    "neutral": (0.0, 0.0),
    "happy": (0.8, 0.45),
    "excited": (0.6, 0.85),
    "tender": (0.65, -0.4),
    "surprised": (0.1, 0.7),
    "sarcastic": (-0.2, 0.2),
    "angry": (-0.65, 0.8),
    "afraid": (-0.7, 0.7),
    "sad": (-0.75, -0.35),
    "tired": (-0.3, -0.7),
    "whispering": (0.0, -0.5),
}
PACE_AROUSAL = {"slow": -0.2, "normal": 0.0, "fast": 0.2}
VOLUME_AROUSAL = {"soft": -0.15, "normal": 0.0, "loud": 0.15}
NEUTRAL_WEIGHT = 0.35          # câu trung tính đóng góp ít vào không khí
SMOOTH_SECONDS = 45.0          # cửa sổ không khí trượt
SHIFT_DISTANCE = 0.5           # khoảng cách (trên mặt phẳng VA) coi là "đổi không khí"
SHIFT_HOLD_SECONDS = 40.0      # ... và phải giữ chừng ấy giây
MIN_SCENE_SECONDS = 60.0
UNTIMED_SECONDS_PER_CHAR = 0.065  # chương chưa có audio: ước thời lượng đọc theo số ký tự (~15 ký tự/giây)

SEPARATOR = re.compile(r"^\s*(?:[*~#=_\-·•oO0]\s*){3,}\s*$")
TIME_JUMP = re.compile(
    r"^\W*(?:(?:sáng|trưa|chiều|tối|đêm)\s+(?:hôm\s+)?sau|hôm\s+sau|ngày\s+(?:hôm\s+)?sau|sáng\s+sớm\s+hôm\s+sau|"
    r"(?:mấy|vài|ba|bốn|năm|sáu|bảy|mười|một|hai|\d+)\s+(?:ngày|tuần|tháng|năm|canh\s+giờ)\s+sau|"
    r"(?:the\s+)?next\s+(?:morning|day)|(?:a\s+few|several|\d+)\s+(?:days|weeks|months|years)\s+later)",
    re.IGNORECASE,
)


def line_point(segment: dict[str, Any]) -> tuple[float, float, float, bool]:
    """(valence, arousal, trọng số theo cường độ, có cảm xúc hay không) của một câu."""
    emotion = str(segment.get("emotion") or "neutral")
    valence, arousal = EMOTION_VA.get(emotion, (0.0, 0.0))
    try:
        intensity = max(0, min(3, int(segment.get("intensity") or 0)))
    except (TypeError, ValueError):
        intensity = 0
    scale = 0.4 + 0.2 * intensity  # cường độ 0..3 -> kéo điểm từ 40% tới 100% về phía cảm xúc
    valence, arousal = valence * scale, arousal * scale
    arousal += PACE_AROUSAL.get(str(segment.get("pace") or "normal"), 0.0)
    arousal += VOLUME_AROUSAL.get(str(segment.get("volume") or "normal"), 0.0)
    affective = emotion != "neutral"
    weight = (0.5 + intensity / 3.0) * (1.0 if affective else NEUTRAL_WEIGHT)
    return max(-1.0, min(1.0, valence)), max(-1.0, min(1.0, arousal)), weight, affective


def _durations(segments: list[dict[str, Any]]) -> list[float]:
    timed = all(segment.get("start") is not None and segment.get("end") is not None for segment in segments)
    if timed:
        return [max(0.05, float(segment["end"]) - float(segment["start"])) for segment in segments]
    return [max(0.3, len(str(segment.get("text") or "")) * UNTIMED_SECONDS_PER_CHAR) for segment in segments]


def hard_break(segment: dict[str, Any]) -> str | None:
    text = str(segment.get("text") or "")
    if segment.get("kind") == "heading":
        return "heading"
    if SEPARATOR.match(text):
        return "separator"
    if TIME_JUMP.match(text):
        return "time_jump"
    return None


class _Accumulator:
    def __init__(self) -> None:
        self.valence = self.arousal = self.weight = self.affective = self.seconds = 0.0

    def add(self, valence: float, arousal: float, weight: float, affective: bool, seconds: float) -> None:
        w = weight * seconds
        self.valence += valence * w
        self.arousal += arousal * w
        self.weight += w
        self.affective += w if affective else 0.0
        self.seconds += seconds

    def merge(self, other: "_Accumulator") -> None:
        self.valence += other.valence
        self.arousal += other.arousal
        self.weight += other.weight
        self.affective += other.affective
        self.seconds += other.seconds

    def point(self) -> tuple[float, float]:
        if not self.weight:
            return 0.0, 0.0
        return self.valence / self.weight, self.arousal / self.weight


def chapter_scenes(script: dict[str, Any]) -> list[dict[str, Any]]:
    """Các đoạn của một chương (`store.chapter_script` / `scripts/<n>.json` của `.abook`)."""
    segments = [segment for segment in script.get("segments") or [] if isinstance(segment, dict)]
    if not segments:
        return []
    seconds = _durations(segments)
    points = [line_point(segment) for segment in segments]
    timeline = []
    clock = 0.0
    for segment, length in zip(segments, seconds):
        start = float(segment["start"]) if segment.get("start") is not None else clock
        timeline.append(start)
        clock = start + length

    # Không khí trượt: trung bình có trọng số các câu trong SMOOTH_SECONDS trước đó.
    smooth: list[tuple[float, float]] = []
    window: list[int] = []
    for index in range(len(segments)):
        window.append(index)
        while window and timeline[index] - timeline[window[0]] > SMOOTH_SECONDS:
            window.pop(0)
        acc = _Accumulator()
        for j in window:
            acc.add(*points[j], seconds[j])
        smooth.append(acc.point())

    scenes: list[dict[str, Any]] = []

    def open_scene(index: int, reason: str) -> dict[str, Any]:
        return {"first": index, "last": index, "reason": reason, "acc": _Accumulator()}

    current = open_scene(0, "chapter_start")
    pending_shift: int | None = None
    for index in range(len(segments)):
        reason = hard_break(segments[index]) if index else None
        if reason and current["acc"].seconds > 0:
            scenes.append(current)
            current = open_scene(index, reason)
            pending_shift = None
        elif current["acc"].seconds >= MIN_SCENE_SECONDS:
            here = current["acc"].point()
            moved = math.dist(here, smooth[index]) >= SHIFT_DISTANCE
            if moved and pending_shift is None:
                pending_shift = index
            elif not moved:
                pending_shift = None
            if pending_shift is not None and timeline[index] - timeline[pending_shift] >= SHIFT_HOLD_SECONDS:
                # Cắt ở chỗ không khí BẮT ĐẦU đổi, không ở chỗ phát hiện: các câu từ đó thuộc đoạn mới.
                tail = _Accumulator()
                for j in range(pending_shift, index):
                    tail.add(*points[j], seconds[j])
                head = _Accumulator()
                for j in range(current["first"], pending_shift):
                    head.add(*points[j], seconds[j])
                current["acc"], current["last"] = head, pending_shift - 1
                scenes.append(current)
                current = open_scene(pending_shift, "mood_shift")
                current["acc"] = tail
                pending_shift = None
        current["acc"].add(*points[index], seconds[index])
        current["last"] = index
    scenes.append(current)
    scenes = _merge_short(scenes)
    return [_view(scene, segments, timeline, seconds, script) for scene in scenes]


def _merge_short(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Đoạn ngắn hơn MIN_SCENE_SECONDS gộp vào đoạn kề có không khí gần nhất (ranh giới cứng cũng nhường: một dòng `***`
    trước hai câu cuối chương không đáng một bản nhạc riêng)."""
    merged = list(scenes)
    changed = True
    while changed and len(merged) > 1:
        changed = False
        for index, scene in enumerate(merged):
            if scene["acc"].seconds >= MIN_SCENE_SECONDS:
                continue
            neighbours = [j for j in (index - 1, index + 1) if 0 <= j < len(merged)]
            target = min(neighbours, key=lambda j: math.dist(merged[j]["acc"].point(), scene["acc"].point()))
            keep, drop = (merged[target], scene) if target < index else (scene, merged[target])
            keep["acc"].merge(drop["acc"])
            keep["first"], keep["last"] = min(keep["first"], drop["first"]), max(keep["last"], drop["last"])
            merged.remove(drop)
            changed = True
            break
    return merged


def _view(scene: dict[str, Any], segments: list[dict[str, Any]], timeline: list[float], seconds: list[float],
          script: dict[str, Any]) -> dict[str, Any]:
    first, last = scene["first"], scene["last"]
    valence, arousal = scene["acc"].point()
    weight = scene["acc"].weight
    return {
        "chapterId": script.get("chapterId"),
        "firstSegment": segments[first].get("id"),
        "lastSegment": segments[last].get("id"),
        "start": round(timeline[first], 3),
        "end": round(timeline[last] + seconds[last], 3),
        "valence": round(valence, 3),
        "arousal": round(arousal, 3),
        "confidence": round(scene["acc"].affective / weight, 3) if weight else 0.0,
        "reason": scene["reason"],
        "lines": last - first + 1,
    }


def book_scenes(scripts: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Các đoạn của cả cuốn, theo thứ tự chương."""
    return [scene for script in scripts for scene in chapter_scenes(script)]
