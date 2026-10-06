"""Các ĐOẠN của một chương và không khí của từng đoạn - nền cho nhạc nền (chủ sách 01-10: nhạc là một lớp riêng của cuốn
sách, như phụ đề của video; máy tự gắn, người dùng sửa nếu muốn).

Không cần model: mỗi câu đã có cảm xúc, cường độ, nhịp, âm lượng (bộ phân tích gán lúc làm sách, có sẵn trong mọi `.abook`).
Mỗi cảm xúc là một điểm trên hai trục của mô hình tròn cảm xúc (Russell 1980): VALENCE vui (+) / buồn (-), AROUSAL dồn dập (+) /
êm (-). Đoạn = một khúc liền nhau cùng không khí:

1. Ranh giới CỨNG từ chữ: đầu chương, dòng ngăn cảnh (`***`, `* * *`, `---`...), câu mở bằng mốc nhảy thời gian ("Sáng hôm
   sau", "Ba ngày sau"...), dấu hiệu đổi cảnh (`cue_kind`: tiêu đề phụ, dòng thời gian / nơi chốn).
2. Trong khúc giữa hai ranh giới cứng: không khí trượt (trung bình theo thời lượng đọc, cửa sổ ~45 giây) đổi XA khỏi không khí
   của đoạn đang mở và GIỮ đủ lâu thì cắt đoạn mới - một câu kêu lên giữa cảnh bình yên không đổi nhạc.
3. Đoạn ngắn hơn MIN_SCENE_SECONDS gộp vào đoạn kề gần không khí nhất.

Câu kể trung tính (phần lớn văn bản) nặng ít hơn: nó không nói lên không khí, chỉ là nền. `confidence` = phần trọng số đến
từ câu CÓ cảm xúc - thấp thì đoạn không có không khí rõ (chọn nhạc nhẹ hay để im lặng là việc của bước chọn nhạc).
"""
from __future__ import annotations

import math
import re
from typing import Any, Callable, Iterable, Mapping

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
# Trục thứ ba (căng thẳng - Schimmack & Grob 2000; MUSIC_SELECTION_MODEL.md): "dồn dập vì hào hứng" và "dồn dập vì sợ" khác
# nhau ở đây.
EMOTION_TENSION: dict[str, float] = {
    "neutral": 0.0, "happy": -0.4, "excited": 0.1, "tender": -0.6, "surprised": 0.5, "sarcastic": 0.3,
    "angry": 0.75, "afraid": 0.85, "sad": 0.1, "tired": -0.3, "whispering": 0.3,
}
# 13 cảm xúc nhạc (Lớp 2 của docs/MUSIC_THEORY.md: GEMS-9 + 4 lớp truyện cần), mỗi cái một cường độ độc lập 0..1 - không
# ép cộng bằng 1, để cảnh buồn-mà-ấm giữ được cả `sadness` lẫn `tenderness`.
EMOTION_CLASSES = ("peacefulness", "tenderness", "nostalgia", "sadness", "joy", "playful", "power", "wonder", "tension",
                   "fear", "anger", "mystery", "moved")
# Đường nhãn câu: nhãn cảm xúc của câu -> các lớp nó góp vào. Đây chỉ là ĐƯỜNG CƠ SỞ (baseline theo nhãn) cho tới khi đường
# LLM (đọc cả đoạn, ghi thẳng 13 cường độ) vào; số là giá trị khởi đầu từ MUSIC_THEORY.md, sẽ học (E4, Bradley-Terry).
LINE_EMOTIONS: dict[str, dict[str, float]] = {
    "happy": {"joy": 1.0},
    "excited": {"joy": 0.6, "power": 0.6},
    "tender": {"tenderness": 1.0},
    "surprised": {"wonder": 0.5, "tension": 0.4},
    "sarcastic": {"playful": 0.7},
    "angry": {"anger": 1.0, "tension": 0.4},
    "afraid": {"fear": 1.0, "tension": 0.6},
    "sad": {"sadness": 1.0, "nostalgia": 0.3},
    "tired": {"sadness": 0.3, "peacefulness": 0.3},
    "whispering": {"mystery": 0.6, "tension": 0.3},
    "neutral": {"peacefulness": 0.15},
}
EMOTION_SCALE = 0.25           # cường độ lớp = 1 - exp(-phần của đoạn / EMOTION_SCALE); giá trị khởi đầu, sẽ học
PACE_AROUSAL = {"slow": -0.2, "normal": 0.0, "fast": 0.2}
VOLUME_AROUSAL = {"soft": -0.15, "normal": 0.0, "loud": 0.15}
NEUTRAL_WEIGHT = 0.35          # câu trung tính đóng góp ít vào không khí
SMOOTH_SECONDS = 45.0          # cửa sổ không khí trượt
SHIFT_DISTANCE = 0.5           # khoảng cách (trên mặt phẳng VA) coi là "đổi không khí"
SHIFT_HOLD_SECONDS = 40.0      # ... và phải giữ chừng ấy giây
MIN_SCENE_SECONDS = 60.0
MAX_SCENE_SECONDS = 180.0       # đoạn dài hơn thì chia đều (_split_long)
UNTIMED_SECONDS_PER_CHAR = 0.065  # chương chưa có audio: ước thời lượng đọc theo số ký tự (~15 ký tự/giây)

SEPARATOR = re.compile(r"^\s*(?:[*~#=_\-·•oO0]\s*){3,}\s*$")
TIME_JUMP = re.compile(
    r"^\W*(?:(?:sáng|trưa|chiều|tối|đêm)\s+(?:hôm\s+)?sau|hôm\s+sau|ngày\s+(?:hôm\s+)?sau|sáng\s+sớm\s+hôm\s+sau|"
    r"(?:mấy|vài|ba|bốn|năm|sáu|bảy|mười|một|hai|\d+)\s+(?:ngày|tuần|tháng|năm|canh\s+giờ)\s+sau|"
    r"(?:the\s+)?next\s+(?:morning|day)|(?:a\s+few|several|\d+)\s+(?:days|weeks|months|years)\s+later)",
    re.IGNORECASE,
)
# Dấu hiệu đổi cảnh trong chữ (CUE - docs/MUSIC_RESEARCH.md 06-10, `seg_scenes.cue_kind` của nghiên cứu): dòng chỉ ký hiệu,
# tiêu đề phụ ("Góc nhìn của...", "【...】"), dòng thời gian / nơi chốn ("Trong khi đó", "Vài giờ sau"). Thành cờ `sceneBreak`
# như dòng ngăn cảnh của sách (chapter_scenes) - ranh giới CÓ LÝ DO, chỗ duy nhất nhạc được đổi bài.
CUE_SYMBOLS = re.compile(r"^\s*(?:(?:[*~#=_\-·•◇◆○●♦※✦＊]\s*){1,}|o\s*O\s*o)\s*$")
CUE_SUBHEAD = re.compile(r"^\s*(?:góc nhìn|pov\b|phần\b|interlude|side\b|phía\b)", re.IGNORECASE)
CUE_BRACKETED = re.compile(r"^\s*(?:【[^】]*】|\[[^\]]*\]|「[^」]*」|[—–-]{1,2}\s*[^—–-]{1,40}\s*[—–-]{1,2})\s*$")
CUE_SUBHEAD_WORDS = 10
CUE_TIME_PLACE = re.compile(
    r"^\W*(?:trong\s+khi\s+đó|cùng\s+lúc\s+(?:đó|ấy)|lúc\s+(?:ấy|đó)\s+ở|(?:vài|mấy|một|hai|ba)\s+(?:giờ|tiếng|phút)\s+sau|"
    r"(?:sáng|trưa|chiều|tối|đêm)\s+(?:hôm|ngày)\s+(?:ấy|đó)|ngày\s+hôm\s+đó|quay\s+lại|trở\s+lại\s+với|(?:ở|tại)\s+một\s+nơi\s+khác)",
    re.IGNORECASE)


def cue_kind(segment: dict[str, Any]) -> str | None:
    """Loại dấu hiệu đổi cảnh của một câu: "heading", "separator", "subhead", "time_place", hay None."""
    text = str(segment.get("text") or "").strip()
    if segment.get("kind") == "heading":
        return "heading"
    if CUE_SYMBOLS.match(text):
        return "separator"
    if len(text.split()) <= CUE_SUBHEAD_WORDS and (CUE_SUBHEAD.match(text) or CUE_BRACKETED.match(text)):
        return "subhead"
    if TIME_JUMP.match(text) or CUE_TIME_PLACE.match(text):
        return "time_place"
    return None


def cue_bounds(segments: list[dict[str, Any]]) -> dict[Any, str]:
    """{id câu BẮT ĐẦU cảnh mới: loại dấu hiệu}. Dòng ký hiệu thì cảnh mới bắt đầu ở câu SAU nó; tiêu đề, tiêu đề phụ, dòng
    thời gian / nơi chốn thì ở chính câu ấy. Câu đầu chương không tính (đầu chương đã là ranh giới)."""
    out: dict[Any, str] = {}
    for index, segment in enumerate(segments[1:], 1):
        kind = cue_kind(segment)
        if kind in ("separator", "heading", "subhead"):
            if index + 1 < len(segments):
                out.setdefault(segments[index + 1].get("id") if kind == "separator" else segment.get("id"), kind)
        elif kind:
            out.setdefault(segment.get("id"), kind)
    return out


# Các NGUỒN ranh giới có lý do ngoài dòng ngăn cảnh của sách (cột `segments.scene_break`), theo thứ tự ưu tiên: tên nguồn ->
# hàm (các câu của chương) -> {id câu BẮT ĐẦU cảnh mới: loại}. Nguồn nào cũng thành cùng một cờ `sceneBreak` (`with_scene_breaks`),
# kèm `sceneSource` = tên nguồn. Ranh giới tính sẵn ngoài chương (LLM chia cảnh, "llm") không nằm ở đây mà vào qua tham số
# `boundaries` của `chapter_scenes` / `book_scenes` - cùng hình {id: loại}, cùng cờ.
BOUNDARY_SOURCES: dict[str, Callable[[list[dict[str, Any]]], Mapping[Any, str]]] = {"cue": cue_bounds}


def with_scene_breaks(segments: list[dict[str, Any]],
                      boundaries: Mapping[str, Mapping[Any, str]] | None = None) -> list[dict[str, Any]]:
    """Các câu, câu đứng ngay trước một ranh giới có lý do mang cờ `sceneBreak` - đúng chỗ cờ của dòng ngăn cảnh - kèm
    `sceneSource` (nguồn: "cue", "llm"...) và `sceneCue` (loại, thành lý do của đoạn mới). Nguồn: `BOUNDARY_SOURCES` rồi
    `boundaries` ({nguồn: {id câu bắt đầu cảnh: loại}}); hai nguồn cùng chỗ thì nguồn trước thắng. Câu gốc không bị sửa: câu
    được gắn cờ là bản sao; câu đã có cờ từ dòng ngăn cảnh của sách giữ nguyên."""
    sources = [(name, find(segments)) for name, find in BOUNDARY_SOURCES.items()]
    sources += list((boundaries or {}).items())
    out = list(segments)
    for index, segment in enumerate(segments[:-1]):
        following = segments[index + 1].get("id")
        found = next(((name, starts[following]) for name, starts in sources if following in starts), None)
        if found and not segment.get("sceneBreak"):
            out[index] = dict(segment, sceneBreak=True, sceneSource=found[0], sceneCue=str(found[1] or found[0]))
    return out


def line_tension(segment: dict[str, Any]) -> float:
    try:
        intensity = max(0, min(3, int(segment.get("intensity") or 0)))
    except (TypeError, ValueError):
        intensity = 0
    return EMOTION_TENSION.get(str(segment.get("emotion") or "neutral"), 0.0) * (0.4 + 0.2 * intensity)


def line_emotions(segment: dict[str, Any]) -> dict[str, float]:
    """Phần góp của một câu vào từng lớp trong 13 cảm xúc (chưa nhân thời lượng): ánh xạ nhãn x (0,4 + 0,2 x cường độ)."""
    try:
        intensity = max(0, min(3, int(segment.get("intensity") or 0)))
    except (TypeError, ValueError):
        intensity = 0
    scale = 0.4 + 0.2 * intensity
    return {name: share * scale for name, share in LINE_EMOTIONS.get(str(segment.get("emotion") or "neutral"), {}).items()}


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


def hard_break(segment: dict[str, Any], previous: dict[str, Any] | None = None) -> str | None:
    """Lý do đoạn nhạc mới phải bắt đầu ở `segment`. `previous`: câu ngay trước nó - dòng ngăn cảnh ("***", "◆") không có chữ
    nên không thành câu, mà đánh dấu câu đứng trước (`sceneBreak`, từ cột `segments.scene_break`). Ranh giới từ nguồn khác
    (`with_scene_breaks`: dấu hiệu đổi cảnh, LLM) cũng là cờ ấy, kèm `sceneSource` và loại `sceneCue` làm lý do."""
    text = str(segment.get("text") or "")
    flagged = previous is not None and bool(previous.get("sceneBreak"))
    if segment.get("kind") == "heading":
        return "heading"
    if (flagged and not previous.get("sceneSource")) or SEPARATOR.match(text):
        return "separator"
    if TIME_JUMP.match(text):
        return "time_jump"
    if flagged:
        return str(previous["sceneCue"])
    return None


class _Accumulator:
    """Tổng có trọng số (trọng số câu x giây) của các câu trong một đoạn: trung bình và độ lệch chuẩn của V/E/T, và tổng
    cường độ x giây của 13 cảm xúc. Chỉ giữ TỔNG (và tổng bình phương) nên `merge` đúng như thêm từng câu vào một chỗ."""

    def __init__(self) -> None:
        self.valence = self.arousal = self.tension = self.weight = self.affective = self.seconds = 0.0
        self.valence2 = self.arousal2 = self.tension2 = 0.0
        self.emotions: dict[str, float] = {}

    def add(self, valence: float, arousal: float, weight: float, affective: bool, seconds: float,
            tension: float = 0.0, emotions: dict[str, float] | None = None) -> None:
        w = weight * seconds
        self.valence += valence * w
        self.arousal += arousal * w
        self.tension += tension * w
        self.valence2 += valence * valence * w
        self.arousal2 += arousal * arousal * w
        self.tension2 += tension * tension * w
        self.weight += w
        self.affective += w if affective else 0.0
        self.seconds += seconds
        for name, share in (emotions or {}).items():
            self.emotions[name] = self.emotions.get(name, 0.0) + share * seconds

    def add_line(self, segment: dict[str, Any], seconds: float, point: tuple[float, float, float, bool] | None = None) -> None:
        """Thêm một câu đủ cả V/E/T và 13 cảm xúc (`point` = `line_point(segment)` nếu đã tính)."""
        self.add(*(point or line_point(segment)), seconds, tension=line_tension(segment), emotions=line_emotions(segment))

    def merge(self, other: "_Accumulator") -> None:
        for name in ("valence", "arousal", "tension", "valence2", "arousal2", "tension2", "weight", "affective", "seconds"):
            setattr(self, name, getattr(self, name) + getattr(other, name))
        for name, total in other.emotions.items():
            self.emotions[name] = self.emotions.get(name, 0.0) + total

    def point(self) -> tuple[float, float]:
        if not self.weight:
            return 0.0, 0.0
        return self.valence / self.weight, self.arousal / self.weight

    def mean_tension(self) -> float:
        return self.tension / self.weight if self.weight else 0.0

    def sd(self) -> dict[str, float]:
        """Độ lệch chuẩn có trọng số của các điểm câu trong đoạn, cùng trọng số với trung bình."""
        out = {}
        for name, total, squares in (("valence", self.valence, self.valence2), ("arousal", self.arousal, self.arousal2),
                                     ("tension", self.tension, self.tension2)):
            mean = total / self.weight if self.weight else 0.0
            out[name] = math.sqrt(max(0.0, squares / self.weight - mean * mean)) if self.weight else 0.0
        return out

    def emotion_intensities(self) -> dict[str, float]:
        """13 cường độ độc lập 0..1: 1 - exp(-phần của đoạn / EMOTION_SCALE). Không chuẩn hoá giữa các lớp."""
        seconds = self.seconds or 1.0
        return {name: round(1.0 - math.exp(-(self.emotions.get(name, 0.0) / seconds) / EMOTION_SCALE), 3)
                for name in EMOTION_CLASSES}


def chapter_scenes(script: dict[str, Any], moods: list[dict[str, Any]] | None = None,
                   boundaries: Mapping[str, Mapping[Any, str]] | None = None) -> list[dict[str, Any]]:
    """Các đoạn của một chương (`store.chapter_script` / `scripts/<n>.json` của `.abook`). `moods`: kết quả LLM đọc cả
    đoạn (`music_moods.load()["scenes"]`) - chỉ đổi valence / tension của đoạn, KHÔNG bao giờ đổi ranh giới đoạn.
    `boundaries`: ranh giới có lý do tính sẵn của chương này theo nguồn, {"llm": {id câu bắt đầu cảnh: loại}} - vào thành cờ
    `sceneBreak` như dấu hiệu đổi cảnh (`with_scene_breaks`)."""
    segments = [segment for segment in script.get("segments") or [] if isinstance(segment, dict)]
    if not segments:
        return []
    segments = with_scene_breaks(segments, boundaries)
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
        reason = hard_break(segments[index], segments[index - 1]) if index else None
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
                    tail.add_line(segments[j], seconds[j], points[j])
                head = _Accumulator()
                for j in range(current["first"], pending_shift):
                    head.add_line(segments[j], seconds[j], points[j])
                current["acc"], current["last"] = head, pending_shift - 1
                scenes.append(current)
                current = open_scene(pending_shift, "mood_shift")
                current["acc"] = tail
                pending_shift = None
        current["acc"].add_line(segments[index], seconds[index], points[index])
        current["last"] = index
    scenes.append(current)
    scenes = _split_long(_merge_short(scenes), segments, seconds)
    spans = _mood_spans(moods, script.get("chapterId"), segments)
    return [_view(scene, segments, timeline, seconds, script, spans) for scene in scenes]


def _mood_spans(moods: list[dict[str, Any]] | None, chapter_id: Any,
                segments: list[dict[str, Any]]) -> list[tuple[int, int, float, float]]:
    """Kết quả LLM của chương này đổi sang (vị trí câu đầu, vị trí câu cuối, V, T). So theo VỊ TRÍ trong chương, không theo
    id (id câu không chắc liên tục); mục có id không còn trong chương (sách đã đổi) bị bỏ."""
    position = {segment.get("id"): index for index, segment in enumerate(segments)}
    spans = []
    for mood in moods or []:
        first, last = position.get(mood.get("firstSegment")), position.get(mood.get("lastSegment"))
        if mood.get("chapterId") != chapter_id or first is None or last is None or first > last:
            continue
        try:
            spans.append((first, last, float(mood["V"]), float(mood["T"])))
        except (KeyError, TypeError, ValueError):
            continue
    return spans


def _split_long(scenes: list[dict[str, Any]], segments: list[dict[str, Any]], seconds: list[float]) -> list[dict[str, Any]]:
    """Đoạn dài hơn MAX_SCENE_SECONDS chia đều theo thời lượng, cắt ở ranh giới câu. Đo trên 13 chương có đáp án cảnh
    (docs/MUSIC_RESEARCH.md, 02-10): một bài cho cả chương bỏ lỡ gần hết thay đổi không khí trong chương (r vui-buồn với
    đáp án 0,15-0,43); chia khúc ~3 phút nâng lên 0,39-0,76 ở cả hai bộ kiểm giữ riêng - ổn định hơn mọi cách chọn chỗ
    cắt khéo hơn đã thử (TextTiling, LLM)."""
    out: list[dict[str, Any]] = []
    for scene in scenes:
        first, last = scene["first"], scene["last"]
        total = sum(seconds[first:last + 1])
        parts = math.ceil(total / MAX_SCENE_SECONDS)
        if parts <= 1:
            out.append(scene)
            continue
        target = total / parts
        start, clock = first, 0.0
        for index in range(first, last + 1):
            clock += seconds[index]
            if clock >= target and index < last:
                piece = {"first": start, "last": index, "reason": scene["reason"] if start == first else "length",
                         "acc": _Accumulator()}
                for j in range(start, index + 1):
                    piece["acc"].add_line(segments[j], seconds[j])
                out.append(piece)
                start, clock = index + 1, 0.0
        if start <= last:
            piece = {"first": start, "last": last, "reason": scene["reason"] if start == first else "length",
                     "acc": _Accumulator()}
            for j in range(start, last + 1):
                piece["acc"].add_line(segments[j], seconds[j])
            out.append(piece)
    return out


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
          script: dict[str, Any], spans: list[tuple[int, int, float, float]] = ()) -> dict[str, Any]:
    """Một đoạn cho bên ngoài. `valence`/`arousal`/`tension` là trung bình, `sd` là độ lệch chuẩn của các câu trong đoạn
    (đoạn càng lẫn lộn càng khoan dung với bài lệch), `emotions` là 13 cường độ độc lập; ở đường nhãn câu chúng suy từ nhãn.
    `spans` (`_mood_spans`): LLM đã đọc đoạn này thì `valence` / `tension` lấy từ LLM (V, T trên [-2, 2] -> [-1, 1], trung
    bình theo giây của phần chồng lên đoạn), `moodSource` = "llm"; còn lại ("labels") giữ đường nhãn."""
    first, last = scene["first"], scene["last"]
    acc = scene["acc"]
    valence, arousal = acc.point()
    tension = acc.mean_tension()
    weight = acc.weight
    mood_source = "labels"
    overlaps = [(sum(seconds[max(first, a):min(last, b) + 1]), v, t) for a, b, v, t in spans if a <= last and b >= first]
    total = sum(w for w, _v, _t in overlaps)
    if total > 0:
        valence = sum(w * v / 2 for w, v, _t in overlaps) / total
        tension = sum(w * t / 2 for w, _v, t in overlaps) / total
        mood_source = "llm"
    return {
        "chapterId": script.get("chapterId"),
        "firstSegment": segments[first].get("id"),
        "lastSegment": segments[last].get("id"),
        "start": round(timeline[first], 3),
        "end": round(timeline[last] + seconds[last], 3),
        "valence": round(valence, 3),
        "arousal": round(arousal, 3),
        "tension": round(tension, 3),
        "sd": {axis: round(value, 3) for axis, value in acc.sd().items()},
        "emotions": acc.emotion_intensities(),
        "confidence": round(acc.affective / weight, 3) if weight else 0.0,
        "reason": scene["reason"],
        "lines": last - first + 1,
        "moodSource": mood_source,
    }


def book_scenes(scripts: Iterable[dict[str, Any]], moods: list[dict[str, Any]] | None = None,
                boundaries: Mapping[Any, Mapping[str, Mapping[Any, str]]] | None = None) -> list[dict[str, Any]]:
    """Các đoạn của cả cuốn, theo thứ tự chương. `moods`: xem `chapter_scenes`; `boundaries`: {chapterId: ranh giới theo
    nguồn của chương ấy} (xem `chapter_scenes`)."""
    return [scene for script in scripts
            for scene in chapter_scenes(script, moods, (boundaries or {}).get(script.get("chapterId")))]
