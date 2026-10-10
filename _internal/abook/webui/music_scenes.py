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
# Mức chương cho valence / tension (`apply_chapter_level`): hằng số ĐÓNG BĂNG của docs/MUSIC_RESEARCH.md 07-10 "CL" / "CL-APPLY"
# (`LLM_Train/music/chapter_level.py::FIXED`): (hệ số, hằng) của L_V (V = C0 hc) và L_T (T = P0 hc), và k giữ hình P0 trong chương.
# Không làm tròn, không chỉnh - muốn đổi phải đo lại theo nghiên cứu.
CHAPTER_LEVEL_V = (1.876, 0.068)
CHAPTER_LEVEL_T = (1.066, -0.490)
CHAPTER_LEVEL_SHAPE = 0.5
# Mức T của chương khi KHÔNG đủ P0 cho cả chương, dùng ở đường "student" (`apply_student`): L_T = a * TB(tension đường nhãn) + b.
# M3 10-10 (Corpus/research/music/PLAN_m3_q06_level.md; LLM_Train/music/m3_q06_level.log); học trên 42 chương 4+5+5b+6.
CHAPTER_LEVEL_T_LABELS = (4.022, -0.056)
# Hệ số hình của học sinh trong chương (đo ở M3: k = 1; CL của P0 giữ 0.5).
STUDENT_SHAPE = 1.0

SEPARATOR = re.compile(r"^\s*(?:[*~#=_\-·•oO0]\s*){3,}\s*$")
TIME_JUMP = re.compile(
    r"^\W*(?:(?:sáng|trưa|chiều|tối|đêm)\s+(?:hôm\s+)?sau|hôm\s+sau|ngày\s+(?:hôm\s+)?sau|sáng\s+sớm\s+hôm\s+sau|"
    r"(?:mấy|vài|ba|bốn|năm|sáu|bảy|mười|một|hai|\d+)\s+(?:ngày|tuần|tháng|năm|canh\s+giờ)\s+sau|"
    r"(?:the\s+)?next\s+(?:morning|day)|(?:a\s+few|several|\d+)\s+(?:days|weeks|months|years)\s+later)",
    re.IGNORECASE,
)
# Dấu hiệu đổi cảnh trong chữ (CUE - docs/MUSIC_RESEARCH.md 06-10, `seg_scenes.cue_kind` của nghiên cứu): dòng chỉ ký hiệu,
# tiêu đề phụ ("Góc nhìn của...", "[Yuki POV]", "— Phần hai —"). Thành cờ `sceneBreak` như dòng ngăn cảnh của sách
# (chapter_scenes) - ranh giới CÓ LÝ DO, chỗ duy nhất nhạc được đổi bài. Dòng thời gian / nơi chốn ("Trong khi đó") vẫn được
# `cue_kind` nhận ra nhưng `cue_bounds` bỏ qua (xem ở đó).
CUE_SYMBOLS = re.compile(r"^\s*(?:(?:[*~#=_\-·•◇◆○●♦※✦＊]\s*){1,}|o\s*O\s*o)\s*$")
CUE_SUBHEAD = re.compile(r"^\s*(?:góc nhìn|pov\b|phần\b|interlude|side\b|phía\b)", re.IGNORECASE)
# Ngoặc [..], 「..」, 【..】 mặc định là CHỮ TRONG TRUYỆN (bảng hệ thống, thực đơn, tiêu đề diễn đàn, thần giao cách cảm), không phải
# đổi cảnh: đo trên 82 chương (docs/MUSIC_RESEARCH.md 07-10 BRACKET, LLM-NT) ngoặc kiểu ấy sai nhiều hơn trúng. Chỉ dạng bao gạch
# ("-o0o-", "— Phần hai —") hay ngoặc nói góc nhìn mới (`bracket_is_subhead`) là tiêu đề phụ.
CUE_BRACKETED = re.compile(r"^\s*(?:【[^】]*】|\[[^\]]*\]|「[^」]*」|[—–-]{1,2}\s*[^—–-]{1,40}\s*[—–-]{1,2})\s*$")
CUE_BRACKET_POV = re.compile(r"\bPOV\b|góc nhìn|side", re.IGNORECASE)  # y regex đã đóng băng (cue_bracket.keep_bracket): "side" không \b
CUE_SUBHEAD_WORDS = 10
# Dòng bao gạch còn là lời thoại / lời dẫn thoại kiểu Việt ("– Lizz nói –", "– Đừng lại gần. –") và thông báo trong truyện: chỉ
# là tiêu đề phụ khi bên trong là hoa văn ("o0o", "0● 0"), từ tiêu đề ("Phần hai"), số, hay TÊN 1-3 từ viết hoa ("—Nanato—").
# Câu thường mở bằng "Phía sau…", "Phần lớn…" cũng không phải tiêu đề (`subhead_words`). Đo trên 3 tập chữ thật
# (docs/MUSIC_RESEARCH.md 10-10 CUE-DASH): bỏ 71/75 dòng nhận nhầm, không bỏ dòng thật nào.
CUE_DECOR = re.compile(r"^[oO0\W\d_]*$")
CUE_HEAD_WORD = re.compile(r"^(?:phần|chương|hồi|quyển|tập|ngoại\s+truyện|phiên\s+ngoại|chapter|part|interlude|prologue|"
                           r"epilogue|mở\s+đầu|vĩ\s+thanh|kết)\b", re.IGNORECASE)
CUE_NUMERAL = re.compile(r"^(?:\d+|[ivxlcdm]+)\.?$", re.IGNORECASE)
CUE_NAME_PUNCT = re.compile(r"[.!?…,;:*\"“”]")
CUE_PLAIN_END = re.compile(r"[.!?…,;:\"”'’)]\s*$")
CUE_PART_NUMBERS = frozenset({"một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín", "mười", "cuối", "kết", "đầu"})
CUE_TIME_PLACE = re.compile(
    r"^\W*(?:trong\s+khi\s+đó|cùng\s+lúc\s+(?:đó|ấy)|lúc\s+(?:ấy|đó)\s+ở|(?:vài|mấy|một|hai|ba)\s+(?:giờ|tiếng|phút)\s+sau|"
    r"(?:sáng|trưa|chiều|tối|đêm)\s+(?:hôm|ngày)\s+(?:ấy|đó)|ngày\s+hôm\s+đó|quay\s+lại|trở\s+lại\s+với|(?:ở|tại)\s+một\s+nơi\s+khác)",
    re.IGNORECASE)


def bracket_is_subhead(text: str) -> bool:
    """Câu dạng ngoặc (`CUE_BRACKETED`) chỉ là tiêu đề phụ khi bên trong nói góc nhìn (POV / góc nhìn / side; luật đóng băng
    `LLM_Train/music/cue_bracket.py::keep_bracket`), hoặc khi bao bằng gạch mà bên trong là hoa văn, từ tiêu đề, số hay tên
    (CUE-DASH, `LLM_Train/music/cue_dash.py`): "-o0o-", "— Phần hai —", "—Nanato—"; không phải "– Lizz nói –"."""
    text = text.strip()
    inner = re.sub(r"^\s*[\[【「(—–-]+\s*|\s*[\]】」)—–-]+\s*$", "", text)
    if CUE_BRACKET_POV.search(inner):
        return True
    words = inner.split()
    name = 1 <= len(words) <= 3 and not CUE_NAME_PUNCT.search(inner) and all(word[:1].isupper() for word in words)
    return text[:1] in "-–—" and bool(CUE_DECOR.match(inner) or CUE_HEAD_WORD.match(inner) or CUE_NUMERAL.match(inner) or name)


def subhead_words(text: str) -> bool:
    """Câu mở bằng từ tiêu đề phụ (`CUE_SUBHEAD`) có thật là tiêu đề: không kết bằng dấu câu văn (trừ ":" ở câu <= 4 chữ như
    "Phần 4:"), và "phần" phải có số đứng sau ("Phần hai", "Phần 3"). "Phần thưởng:", "Phía sau lưng hắn…" là câu thường."""
    if CUE_PLAIN_END.search(text) and not (text.endswith(":") and len(text.split()) <= 4):
        return False
    words = text.rstrip(":").split()
    if words and words[0].lower() == "phần":
        return 2 <= len(words) <= 4 and (words[1].lower() in CUE_PART_NUMBERS or bool(CUE_NUMERAL.match(words[1])))
    return True


def cue_kind(segment: dict[str, Any]) -> str | None:
    """Loại dấu hiệu đổi cảnh của một câu: "heading", "separator", "subhead", "time_place", hay None."""
    text = str(segment.get("text") or "").strip()
    if segment.get("kind") == "heading":
        return "heading"
    if CUE_SYMBOLS.match(text):
        return "separator"
    if len(text.split()) <= CUE_SUBHEAD_WORDS and (
            (CUE_SUBHEAD.match(text) and subhead_words(text)) or (CUE_BRACKETED.match(text) and bracket_is_subhead(text))):
        return "subhead"
    if TIME_JUMP.match(text) or CUE_TIME_PLACE.match(text):
        return "time_place"
    return None


def cue_bounds(segments: list[dict[str, Any]]) -> dict[Any, str]:
    """{id câu BẮT ĐẦU cảnh mới: loại dấu hiệu}. Dòng ký hiệu thì cảnh mới bắt đầu ở câu SAU nó; tiêu đề, tiêu đề phụ thì ở
    chính câu ấy. Câu đầu chương không tính (đầu chương đã là ranh giới)."""
    out: dict[Any, str] = {}
    for index, segment in enumerate(segments[1:], 1):
        kind = cue_kind(segment)
        if kind in ("separator", "heading", "subhead"):
            if index + 1 < len(segments):
                out.setdefault(segments[index + 1].get("id") if kind == "separator" else segment.get("id"), kind)
        # "time_place" (dòng thời gian / nơi chốn mở câu) KHÔNG còn là ranh giới: P .17 trúng đổi nơi/thời gian thật (MUSIC_RESEARCH
        # 07-10 BRACKET). Câu "Sáng hôm sau…" (TIME_JUMP) vẫn ngắt ở `hard_break`.
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
                   boundaries: Mapping[str, Mapping[Any, str]] | None = None,
                   student: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Các đoạn của một chương (`store.chapter_script` / `scripts/<n>.json` của `.abook`). `moods`: kết quả LLM đọc cả
    đoạn (`music_moods.load()["scenes"]`) - chỉ đổi valence / tension của đoạn, KHÔNG bao giờ đổi ranh giới đoạn.
    `boundaries`: ranh giới có lý do tính sẵn của chương này theo nguồn, {"llm": {id câu bắt đầu cảnh: loại}} - vào thành cờ
    `sceneBreak` như dấu hiệu đổi cảnh (`with_scene_breaks`). `student`: hình dạng không khí trong chương do học sinh đoán
    (`music_scene_student.load()["scenes"]`) - đoạn lấy hình từ đó (`apply_student`), cũng không đổi ranh giới."""
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
    views = [_view(scene, segments, timeline, seconds, script, spans) for scene in scenes]
    return apply_student(views, student) or apply_chapter_level(views)


def apply_chapter_level(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mức chương cho valence / tension của các đoạn của MỘT chương (docs/MUSIC_RESEARCH.md 07-10 "CL" và "CL-APPLY"; mã đã
    đóng băng `LLM_Train/music/chapter_level.py::FIXED` + `cl_apply.py`). LLM đọc từng đoạn (P0) chấm sai MỨC (T cao hơn đáp án
    chừng .5, V lệch theo chương) và phóng đại dao động giữa các đoạn, mà đáp án chủ yếu đổi theo chương: ước mức cả chương rồi
    giữ một nửa hình dạng của P0 trong chương thì MAE giảm 44% (.419 -> .234 ở bộ 7). Với TB(x) = trung bình trọng số d = end - start:

        L_V = clip(1.876 * TB(labelValence) + 0.068)      L_T = clip(1.066 * TB(pT) - 0.490)
        valence = clip(L_V + 0.5 * (pV - TB(pV)))         tension = clip(L_T + 0.5 * (pT - TB(pT)))

    pV / pT: valence / tension LLM của đoạn (đã về [-1, 1]); giữ lại ở `llmValence` / `llmTension`. Chỉ áp khi MỌI đoạn đã
    có LLM đọc (`moodSource == "llm"`) - có đoạn còn ở đường nhãn thì trả nguyên (đường ấy chưa đo). Đoạn được áp mang
    `moodSource` = "chapter"; arousal, sd, emotions, confidence không đổi. Thuần hàm: không sửa đoạn đưa vào."""
    weights = [max(0.0, float(scene["end"]) - float(scene["start"])) for scene in scenes]
    total = sum(weights)
    if not scenes or total <= 0 or any(scene.get("moodSource") != "llm" for scene in scenes):
        return scenes

    def mean(values: list[float]) -> float:
        return sum(w * v for w, v in zip(weights, values)) / total

    def clip(value: float) -> float:
        return max(-1.0, min(1.0, value))

    llm_valence = [float(scene["valence"]) for scene in scenes]
    llm_tension = [float(scene["tension"]) for scene in scenes]
    mean_valence, mean_tension = mean(llm_valence), mean(llm_tension)
    level_v = clip(CHAPTER_LEVEL_V[0] * mean([float(scene["labelValence"]) for scene in scenes]) + CHAPTER_LEVEL_V[1])
    level_t = clip(CHAPTER_LEVEL_T[0] * mean_tension + CHAPTER_LEVEL_T[1])
    return [dict(scene, moodSource="chapter", llmValence=round(pv, 3), llmTension=round(pt, 3),
                 valence=round(clip(level_v + CHAPTER_LEVEL_SHAPE * (pv - mean_valence)), 3),
                 tension=round(clip(level_t + CHAPTER_LEVEL_SHAPE * (pt - mean_tension)), 3))
            for scene, pv, pt in zip(scenes, llm_valence, llm_tension)]


def apply_student(scenes: list[dict[str, Any]], items: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    """Đường "student" (music_scene_student.py; SPEC_app_q06.md mục 1 + PLAN_m3_q06_level.md + PLAN_lv_q06.md): mức chương như CL (mức V thì ưu tiên
    đầu mức chương của học sinh), HÌNH trong chương do học sinh đoán. `scenes`: các đoạn của MỘT chương ngay từ `_view` (chưa qua
    `apply_chapter_level`); `items`: độ lệch thô của học sinh, mỗi đoạn một mục khớp chapterId + id câu đầu / cuối (dV, dE, dT; và `chapterV`
    khi gói có đầu mức chương). Với w = end - start, TB(x) = trung bình theo w:

        L_V = clip(chapterV)                                                nếu mục có `chapterV` (LV-Q06 10-10: bộ 7 MAE_V .262 -> .155)
        L_V = clip(1.876 * TB(labelValence) + 0.068)                        nếu không (gói cũ chưa có đầu mức chương: như CL, từ nhãn câu)
        L_T = clip(1.066 * TB(pT) - 0.490)                                  nếu MỌI đoạn đã có P0 (moodSource "llm"); pT = tension P0
        L_T = clip(4.022 * TB(labelTension) - 0.056)                        nếu không (M3: nhãn đủ thay P0 ở mức chương hơi kém)
        valence = clip(L_V + k * (dV - TB(dV)))   tension = clip(L_T + k * (dT - TB(dT)))     k = 1 (CL của P0 dùng 0.5)
        arousal = clip(TB(arousal) + k * (dE - TB(dE)))      mức E vẫn là TB nhãn câu của chương (CL-E 07-10: không cần sửa mức);
                                                             hình E từ học sinh (Q06-E 10-10, Corpus PLAN_q06_e.md: r E trong
                                                             chương bộ 7 .391 so với .141 của nhãn câu)

    Chương một đoạn: độ lệch 0 nên đoạn = mức chương. sd, emotions, confidence giữ nguyên.
    Đoạn mang `moodSource` = "student", `studentValence` / `studentArousal` / `studentTension` = dV / dE / dT thô, `levelSource` = {"V": "student" |
    "labels", "T": "p0" | "labels"} (mức V / T của chương lấy từ đâu, cho giao diện / ghi chép), và `llmValence` / `llmTension` khi chính đoạn ấy đã có P0.
    Trả None (caller dùng `apply_chapter_level`, đường hôm nay) khi không có mục cho MỌI đoạn của chương. Thuần hàm: không sửa đoạn đưa vào."""
    weights = [max(0.0, float(scene["end"]) - float(scene["start"])) for scene in scenes]
    total = sum(weights)
    if not scenes or not items or total <= 0:
        return None
    by_key = {(item.get("chapterId"), item.get("firstSegment"), item.get("lastSegment")): item for item in items if isinstance(item, dict)}
    try:
        matched = [by_key[(scene.get("chapterId"), scene.get("firstSegment"), scene.get("lastSegment"))] for scene in scenes]
        deviations = [(float(item["dV"]), float(item["dE"]), float(item["dT"])) for item in matched]
    except (KeyError, TypeError, ValueError):
        return None
    chapter_v = _chapter_level_v(matched)

    def mean(values: list[float]) -> float:
        return sum(w * v for w, v in zip(weights, values)) / total

    def clip(value: float) -> float:
        return max(-1.0, min(1.0, value))

    if chapter_v is not None:
        level_v = clip(chapter_v)
    else:
        level_v = clip(CHAPTER_LEVEL_V[0] * mean([float(scene["labelValence"]) for scene in scenes]) + CHAPTER_LEVEL_V[1])
    p0 = all(scene.get("moodSource") == "llm" for scene in scenes)
    if p0:
        level_t = clip(CHAPTER_LEVEL_T[0] * mean([float(scene["tension"]) for scene in scenes]) + CHAPTER_LEVEL_T[1])
    else:
        level_t = clip(CHAPTER_LEVEL_T_LABELS[0] * mean([float(scene["labelTension"]) for scene in scenes]) + CHAPTER_LEVEL_T_LABELS[1])
    level_source = {"V": "labels" if chapter_v is None else "student", "T": "p0" if p0 else "labels"}
    level_e = mean([float(scene["arousal"]) for scene in scenes])
    mean_dv, mean_de, mean_dt = (mean([dev[axis] for dev in deviations]) for axis in range(3))
    out = []
    for scene, (dv, de, dt) in zip(scenes, deviations):
        fields = {"moodSource": "student", "levelSource": dict(level_source),
                  "studentValence": round(dv, 3), "studentArousal": round(de, 3), "studentTension": round(dt, 3),
                  "valence": round(clip(level_v + STUDENT_SHAPE * (dv - mean_dv)), 3),
                  "arousal": round(clip(level_e + STUDENT_SHAPE * (de - mean_de)), 3),
                  "tension": round(clip(level_t + STUDENT_SHAPE * (dt - mean_dt)), 3)}
        if scene.get("moodSource") == "llm":
            fields.update(llmValence=round(float(scene["valence"]), 3), llmTension=round(float(scene["tension"]), 3))
        out.append(dict(scene, **fields))
    return out


def _chapter_level_v(items: list[dict[str, Any]]) -> float | None:
    """Mức V của chương do đầu mức chương của học sinh đoán (`chapterV` của các mục, cùng giá trị ở mọi đoạn); None nếu mục nào thiếu hay hỏng
    (gói cũ chưa có đầu mức chương) - khi ấy mức V về nhãn câu."""
    try:
        levels = [float(item["chapterV"]) for item in items]
    except (KeyError, TypeError, ValueError):
        return None
    return levels[0] if levels and all(math.isfinite(level) for level in levels) else None


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
    label_tension = tension  # như label_valence: nền của mức T khi chương chưa đủ P0 (`apply_student`)
    mood_source = "labels"
    overlaps = [(sum(seconds[max(first, a):min(last, b) + 1]), v, t) for a, b, v, t in spans if a <= last and b >= first]
    total = sum(w for w, _v, _t in overlaps)
    label_valence = valence  # đường nhãn câu, TRƯỚC khi LLM ghi đè: nền của mức chương (`apply_chapter_level`)
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
        "labelValence": round(label_valence, 3),
        "labelTension": round(label_tension, 3),
    }


def book_scenes(scripts: Iterable[dict[str, Any]], moods: list[dict[str, Any]] | None = None,
                boundaries: Mapping[Any, Mapping[str, Mapping[Any, str]]] | None = None,
                student: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Các đoạn của cả cuốn, theo thứ tự chương. `moods`, `student`: xem `chapter_scenes`; `boundaries`: {chapterId: ranh giới theo
    nguồn của chương ấy} (xem `chapter_scenes`)."""
    return [scene for script in scripts
            for scene in chapter_scenes(script, moods, (boundaries or {}).get(script.get("chapterId")), student)]
