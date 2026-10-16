"""NN-lite: học sinh nhỏ (2 MB, chỉ chữ) cho nhạc nền THEO CẢNH của "Nghe ngay" khi máy KHÔNG có gói q06 (Corpus research/music/SPEC_nnlite_app.md;
điện thoại có bản Kotlin `NnLite.kt` cùng đọc cùng file). Thay mục học sinh `None` của đường N0 (music_nnscene.py) bằng mục `dV / dE / dT / chapterV / chapterP` tính
từ chữ cảnh rồi đi đúng đường NN-V (`music_scenes.apply_student` + sàn `WEAK_MOOD` ở `music_nnscene.chapter_scenes`). Đo trên bộ vàng 18 (60 chương): sai rõ
37,8 % (N0) -> 17,4 % (NN-lite); q06 14,7 %.

File `assets/nnlite.bin` (little-endian; tạo bằng LLM_Train/music/nnlite_ref.py export) - chỉ trọng số trên ô băm, không chữ, không danh sách từ:
  magic "NNL1" | u32 B (ô băm) | u32 n_out (= 4) | u32 n_dense (= 4)
  Wh B x 4 fp16 (hàng = ô băm: pV, pE, pT, q) | Wd 4 x 4 f32 | b 4 | dmu 4 | dsd 4 | ymu 4 | ysd 4 | c 3 | c_c 1 (f32)
Sai magic / hình / cỡ thì coi như không có model: `model()` trả None (một dòng log) và nhạc đi đường N0. Sau khi đọc mọi phép tính là float64.

Chữ cảnh -> đặc trưng định nghĩa theo ĐIỂM MÃ (code point), không theo đơn vị UTF-16 - bản Kotlin duyệt `codePoints()` và phải ra GIỐNG HỆT (token, ô băm tuyệt
đối; đặc trưng sai < 1e-12): bộ ví dụ tests/fixtures/music/nnlite/*.json.
1. `normalize`: NFC rồi `lower()` (ánh xạ đầy đủ, theo ngữ cảnh: "İ" -> "i" + U+0307, sigma cuối từ -> "ς"); không NFC lại.
2. `tokens`: điểm mã loại Lu Ll Lt Lm Lo Mn Mc Nd Nl No liền nhau = một token WORD; điểm mã trong PUNCT = token một điểm mã (và cắt WORD dở); mọi điểm mã khác chỉ cắt.
3. `features`: mục băm "1|" + t (unigram) và "2|" + t[i] + " " + t[i+1] (bigram) trên CẢ dãy token; FNV-1a 32 bit trên byte UTF-8; ô = băm % B; đếm theo ô (va chạm
   thì cộng), giá trị = log1p(đếm) rồi chia chuẩn L2; ô tăng dần.
4. `dense` (chữ đã NFC, chưa hạ chữ): tỉ lệ dòng mở bằng DIALOG, "!" và "?" trên số token WORD, log1p(số token WORD) / 10.
5. `weight` = max(1, số mẩu `split()`) - y hệt trọng số của `ChapterStudent` (khoảng trắng = `str.isspace`: cũng là thứ `str.strip` / `str.split` dùng).

Ranh cảnh LB (Corpus research/music/SPEC_lb_app.md; sai rõ bộ 20: 16,7 -> 11,1 %): cũng từ model này, thuần Python (không numpy) - chia chương thành khối >= 150 chữ, mỗi khối một hồ sơ
(pV, pE, pT)/ysd, quy hoạch động tìm chỗ hồ sơ đổi (`Model.scene_bounds`). `scene_bounds(script)` là nguồn ranh "lite" của `music_nnscene.chapter_scenes`; bản Kotlin
(`NnLite.sceneBounds`) ra y hệt trên bộ ví dụ tests/fixtures/music/nnlite/lb_fixture.json."""
from __future__ import annotations

import hashlib
import logging
import math
import struct
import threading
import unicodedata
from pathlib import Path
from typing import Any

from . import music_moods

log = logging.getLogger(__name__)

MODEL_FILE = Path(__file__).resolve().parent / "assets" / "nnlite.bin"
MAGIC = b"NNL1"
N_OUT = 4
N_DENSE = 4
WORD_CATEGORIES = frozenset({"Lu", "Ll", "Lt", "Lm", "Lo", "Mn", "Mc", "Nd", "Nl", "No"})
PUNCT = frozenset("!?…\"“”«»—–-~")
DIALOG = frozenset("\"“«-–—")
FNV_OFFSET, FNV_PRIME = 2166136261, 16777619
LB_LAMBDA, LB_BLOCK_WORDS, LB_MIN_BLOCKS = 2.0, 150, 2  # phạt mỗi ranh, chữ tối thiểu một khối, khối tối thiểu một đoạn (SPEC_lb_app mục 2)
LB_SOURCE, LB_REASON = "lite", "mood_shift"  # tên nguồn ranh trong `music_scenes.with_scene_breaks` và lý do của đoạn mới


# ---- chữ -> đặc trưng ---------------------------------------------------------------------------------------------------------------
def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower()


def tokens(norm: str) -> list[str]:
    out: list[str] = []
    current: list[str] = []
    for char in norm:
        if unicodedata.category(char) in WORD_CATEGORIES:
            current.append(char)
            continue
        if current:
            out.append("".join(current))
            current = []
        if char in PUNCT:
            out.append(char)
    if current:
        out.append("".join(current))
    return out


def fnv1a(entry: str) -> int:
    value = FNV_OFFSET
    for byte in entry.encode("utf-8"):
        value = ((value ^ byte) * FNV_PRIME) & 0xFFFFFFFF
    return value


def entries(words: list[str]) -> list[str]:
    return [f"1|{word}" for word in words] + [f"2|{a} {b}" for a, b in zip(words, words[1:])]


def features(text: str, buckets: int) -> dict[int, float]:
    """{ô băm: giá trị}, ô tăng dần; cảnh không token -> rỗng."""
    counts: dict[int, int] = {}
    for entry in entries(tokens(normalize(text))):
        slot = fnv1a(entry) % buckets
        counts[slot] = counts.get(slot, 0) + 1
    values = {slot: math.log1p(count) for slot, count in counts.items()}
    norm = math.sqrt(sum(value * value for value in values.values()))
    return {slot: value / norm for slot, value in sorted(values.items())} if norm > 0 else {}


def dense(text: str) -> list[float]:
    nfc = unicodedata.normalize("NFC", text)
    lines = [line for line in (part.strip() for part in nfc.split("\n")) if line]
    words = sum(1 for word in tokens(nfc.lower()) if word not in PUNCT)
    first = sum(1 for line in lines if line[0] in DIALOG) / len(lines) if lines else 0.0
    return [first, nfc.count("!") / max(1, words), nfc.count("?") / max(1, words), math.log1p(words) / 10]


def weight(text: str) -> int:
    return max(1, len(text.split()))


# ---- ranh cảnh LB ------------------------------------------------------------------------------------------------------------------
def blocks(segments: list[dict[str, Any]], block_words: int = LB_BLOCK_WORDS) -> list[tuple[int, int]]:
    """Khối (vị trí câu đầu, câu cuối) của chương: cộng số chữ `split()` theo câu, đủ `block_words` thì đóng khối ở câu ấy; phần dư cuối < một nửa và đã có khối thì gộp vào khối trước."""
    out: list[tuple[int, int]] = []
    start = count = 0
    for index, segment in enumerate(segments):
        count += len(str(segment.get("text") or "").split())
        if count >= block_words:
            out.append((start, index))
            start, count = index + 1, 0
    if start < len(segments):
        if out and count < block_words / 2:
            out[-1] = (out[-1][0], len(segments) - 1)
        else:
            out.append((start, len(segments) - 1))
    return out


def partition(profile: list[list[float]], lam: float = LB_LAMBDA, min_blocks: int = LB_MIN_BLOCKS) -> list[int]:
    """Chỉ số khối MỞ mỗi đoạn (trừ đoạn đầu): cực tiểu Σ SSE(đoạn) + lam·(số đoạn − 1), mỗi đoạn >= `min_blocks` khối; dưới 2·`min_blocks` khối thì không ranh.
    SSE qua tổng tiền tố; duyệt j tăng rồi i tăng, chỉ thay khi nhỏ hơn hẳn (hoà giữ i nhỏ)."""
    n = len(profile)
    if n < 2 * min_blocks:
        return []
    prefix, prefix2 = [[0.0, 0.0, 0.0]], [0.0]
    for row in profile:
        prefix.append([prefix[-1][axis] + row[axis] for axis in range(3)])
        prefix2.append(prefix2[-1] + sum(value * value for value in row))
    inf = float("inf")
    best, back = [inf] * (n + 1), [0] * (n + 1)
    best[0] = -lam
    for j in range(min_blocks, n + 1):
        for i in range(0, j - min_blocks + 1):
            if best[i] < inf:
                s = [prefix[j][axis] - prefix[i][axis] for axis in range(3)]
                value = best[i] + lam + (prefix2[j] - prefix2[i] - (s[0] * s[0] + s[1] * s[1] + s[2] * s[2]) / (j - i))
                if value < best[j]:
                    best[j], back[j] = value, i
    cuts: list[int] = []
    j = n
    while j > 0:
        j = back[j]
        if j > 0:
            cuts.append(j)
    return sorted(cuts)


# ---- model --------------------------------------------------------------------------------------------------------------------------
class Model:
    """Trọng số NN-lite đọc từ `nnlite.bin`; ném `ValueError` khi file sai (dùng `model()` để có None + log thay vì lỗi)."""

    def __init__(self, raw: bytes) -> None:
        if raw[:4] != MAGIC or len(raw) < 16:
            raise ValueError("không phải file NN-lite")
        self.buckets, n_out, n_dense = struct.unpack_from("<III", raw, 4)
        if n_out != N_OUT or n_dense != N_DENSE:
            raise ValueError("hình model lạ")
        offset = 16 + self.buckets * N_OUT * 2
        tail = N_DENSE * N_OUT + 5 * N_OUT + 3 + 1
        if self.buckets <= 0 or offset + tail * 4 != len(raw):
            raise ValueError("cỡ file sai")
        self._raw = raw  # hàng k của Wh (4 fp16) đọc khi cần: không numpy, bản cài chỉ-nghe không có nó
        rest = [float(x) for x in struct.unpack_from(f"<{tail}f", raw, offset)]
        self.wd = [rest[row * N_OUT:(row + 1) * N_OUT] for row in range(N_DENSE)]
        rest = rest[N_DENSE * N_OUT:]
        self.b, self.dmu, self.dsd, self.ymu, self.ysd = (rest[index * 4:(index + 1) * 4] for index in range(5))
        self.c, self.c_c = rest[20:23], rest[23]

    def _row(self, bucket: int) -> tuple[float, ...]:
        return struct.unpack_from(f"<{N_OUT}e", self._raw, 16 + bucket * N_OUT * 2)

    def scene(self, text: str) -> list[float]:
        """(pV, pE, pT, q) thang thầy của chữ một cảnh."""
        z = list(self.b)
        for bucket, value in features(text, self.buckets).items():
            for out, weight_ in enumerate(self._row(bucket)):
                z[out] += value * weight_
        for row, value in enumerate(dense(text)):
            scaled = (value - self.dmu[row]) / self.dsd[row]
            for out in range(N_OUT):
                z[out] += scaled * self.wd[row][out]
        return [z[out] * self.ysd[out] + self.ymu[out] for out in range(N_OUT)]

    def chapter(self, texts: list[str]) -> list[dict[str, float]]:
        """Mục học sinh của MỘT chương theo thứ tự cảnh: dV, dE, dT căn giữa theo trọng số `weight` rồi cộng `c` (chương một cảnh: 0), và chapterV (cùng giá trị ở
        mọi cảnh), và chapterP = (pV, pE, pT, q) THÔ của chương (trung bình theo `weight`, chưa cộng `c_c`; LVJ, `music_scenes.apply_student`)."""
        if not texts:
            return []
        y = [self.scene(text) for text in texts]
        w = [float(weight(text)) for text in texts]
        total = sum(w)
        chapter_p = [sum(wi * yi[axis] for wi, yi in zip(w, y)) / total for axis in range(4)]
        level = chapter_p[3] + self.c_c
        if len(texts) < 2:
            return [{"dV": 0.0, "dE": 0.0, "dT": 0.0, "chapterV": level, "chapterP": chapter_p}]
        mean = chapter_p[:3]
        return [{"dV": yi[0] - mean[0] + self.c[0], "dE": yi[1] - mean[1] + self.c[1], "dT": yi[2] - mean[2] + self.c[2], "chapterV": level,
                 "chapterP": list(chapter_p)} for yi in y]

    def block_profile(self, segments: list[dict[str, Any]], spans: list[tuple[int, int]]) -> list[list[float]]:
        """Hồ sơ từng khối: (pV, pE, pT) của chữ khối chia độ lệch chuẩn đích `ysd`."""
        return [[value / sd for value, sd in zip(self.scene(music_moods.scene_text(segments, first, last))[:3], self.ysd[:3])] for first, last in spans]

    def scene_bounds(self, segments: list[dict[str, Any]]) -> list[Any]:
        """`id` của câu đầu mỗi khối mở đoạn mới (trừ đoạn đầu): chỗ hồ sơ V / E / T của chương đổi (LB)."""
        spans = blocks(segments)
        return [segments[spans[cut][0]].get("id") for cut in partition(self.block_profile(segments, spans))]

    def chapter_items(self, script: dict[str, Any], scenes: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        """Mục (`chapterId`, `firstSegment`, `lastSegment`, `dV`, `dE`, `dT`, `chapterV`, `chapterP`) của từng đoạn `scenes` (của `music_scenes.book_scenes([script], None, None, None)`)
        của chương `script`, cùng khuôn với `ChapterStudent.chapter`. None: đoạn không khớp câu của chương."""
        texts = music_moods.scene_texts(script, scenes)
        if texts is None:
            return None
        return [{"chapterId": scene["chapterId"], "firstSegment": scene["firstSegment"], "lastSegment": scene["lastSegment"], **item}
                for scene, item in zip(scenes, self.chapter(texts))]

    def items(self, scripts: list[dict[str, Any]], scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """`chapter_items` cho cả cuốn (`scenes` = đoạn của mọi chương); chương không dùng được thì bỏ qua (đoạn ấy đi đường N0)."""
        out: list[dict[str, Any]] = []
        for script in scripts:
            mine = [scene for scene in scenes if scene.get("chapterId") == script.get("chapterId")]
            out += self.chapter_items(script, mine) or []
        return out


_lock = threading.Lock()
_loaded: tuple[Path, Model | None, str] | None = None


def model() -> Model | None:
    """Model đã nạp (một lần cho cả tiến trình), None khi file thiếu / hỏng (một dòng log): nhạc đi đường N0."""
    global _loaded
    with _lock:
        if _loaded is None or _loaded[0] != MODEL_FILE:
            try:
                raw = MODEL_FILE.read_bytes()
                _loaded = (MODEL_FILE, Model(raw), hashlib.sha256(raw).hexdigest()[:12])
            except (OSError, ValueError) as error:
                log.warning("NN-lite không nạp được (%s): nhạc theo cảnh chạy đường N0", error)
                _loaded = (MODEL_FILE, None, "")
        return _loaded[1]


def sha() -> str:
    """Mã băm ngắn của file model đã nạp ("" khi không có model): một phần khoá đệm plan nhạc (đổi model thì dựng lại)."""
    model()
    return _loaded[2] if _loaded is not None else ""


def student_items(script: dict[str, Any], scenes: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """Chỗ cắm `music_nnscene.StudentItems`: mục NN-lite của chương, None khi không có model hay chương không dùng được."""
    loaded = model()
    return None if loaded is None else loaded.chapter_items(script, scenes)


def scene_bounds(script: dict[str, Any]) -> dict[Any, str]:
    """Chỗ cắm `music_nnscene.SceneBounds`: {id câu mở cảnh mới: "mood_shift"} của chương theo LB; rỗng khi không có model hay chương ngắn (dưới 4 khối)."""
    loaded = model()
    if loaded is None:
        return {}
    segments = [segment for segment in script.get("segments") or [] if isinstance(segment, dict)]
    return {sid: LB_REASON for sid in loaded.scene_bounds(segments)}
