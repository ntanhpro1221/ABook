"""Mốc thời gian từng CHỮ của sách nói, để app sáng đúng chữ đang đọc (chủ sách 03-10: "như Edge đọc to"; docs/LISTEN_ANYTHING.md
"Read-along view", "Word timings - measured 03-10").

Làm lúc đóng gói sách (bookfile.py) trên máy có Studio, NGOÀI dây chuyền khoá: mỗi câu đã biết chữ và biết khoảng thời gian của nó
trong MP3 chương (`store.chapter_script`), nên chỉ cần căn lại chữ ấy vào đúng khoảng audio đó:
- Căn CTC: wav2vec2 tiếng Việt (`dragonSwing/wav2vec2-base-vietnamese`, Apache-2.0) xuất ONNX int8 chạy bằng onnxruntime trên CPU; chữ được
  đọc thành âm tiết (số đọc ra chữ, chữ ngoại ngữ ánh xạ sang chữ cái của model), căn Viterbi ép đúng chuỗi ấy (bản numpy của
  `torchaudio.functional.forced_align`), rồi ánh xạ ngược về các "chữ hiện" = các đơn vị cách nhau bằng khoảng trắng. Một chữ kết thúc
  đúng chỗ chữ sau bắt đầu. Đo 03-10 trên 1.696 chữ của Edge TTS: 99% đầu chữ lệch dưới 100 ms (trung vị 15 ms); 1,3 giây CPU cho mỗi
  phút audio (4 luồng).
- Dự phòng khi model chưa có, hay căn tệ (độ tin cậy thấp / không đủ khung): chia thời gian câu theo âm tiết, KÈM dò chỗ ngắt bằng năng
  lượng (không bao giờ chia mà không dò ngắt: không dò chỉ 56% đầu chữ lệch dưới 100 ms, có dò 93%).

Kết quả là `words: [[bắt đầu_ms, kết thúc_ms], ...]` trong từng câu của `scripts/<n>.json`, MỘT cặp cho mỗi chữ hiện (`tokens(text)`), tính từ đầu
MP3 chương (cùng đồng hồ với `start`/`end` của câu). Người đọc chỉ dùng khi số cặp bằng số chữ hiện; thiếu `words` thì sáng cả câu như cũ.

Bộ nhớ đệm theo dự án, `word_timings/<chương>.json`: mã SHA-256 của audio chương (kèm cỡ + mốc sửa để hỏi nhanh) và, mỗi câu, SHA-256 của chữ +
khoảng thời gian + cách căn. Đóng gói lại thì không căn lại gì; audio chương làm lại thì căn lại cả chương; chữ một câu đổi thì chỉ câu ấy.
`store.chapter_script` đọc bộ nhớ đệm (rẻ, không cần numpy) nên Studio, đồng bộ điện thoại và đóng gói đều thấy `words`.

Chạy ở đâu: trong tiến trình này nếu có numpy + ffmpeg (máy dev, tiến trình dây chuyền của Studio); app Windows đóng gói (Python nhúng, không
numpy) giao cho Python của Studio (`python -m abook.webui.word_timing align ...`). Không có cả hai thì thôi - sách vẫn đóng gói, không `words`.
Model: ABOOK_WORD_ALIGN_DIR, hay `<ABOOK_RUNTIME>/models/wordalign` (Studio, bước "wordalign" của studio_setup.py), hay `runtime/models/wordalign` cạnh
mã khi chạy từ mã nguồn. ABOOK_WORD_TIMING=0 tắt hẳn (bộ kiểm).

    python -m abook.webui.word_timing align <thư mục dự án> [--chapter N ...] [--pack [-o file]]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any, Callable, Sequence

from .. import io_utils

ENV_DIR = "ABOOK_WORD_ALIGN_DIR"
ENV_SWITCH = "ABOOK_WORD_TIMING"  # "0" = không bao giờ căn chữ
ENV_RUNTIME = "ABOOK_RUNTIME"
CACHE_FOLDER = "word_timings"
# Đổi khi cách căn đổi (hằng số, chuẩn hoá chữ, ngưỡng): bộ nhớ đệm cũ coi như chưa căn.
VERSION = 1
SAMPLE_RATE = 16_000
FRAME = 0.02  # wav2vec2: bước 320 mẫu ở 16 kHz
HOP = 0.01  # khung năng lượng của đường dự phòng
MARGIN = 0.25  # giây lấy thêm hai bên khoảng của câu (mốc câu là co giãn tuyến tính theo độ dài MP3: lệch tới ~0,15 s trên 13 phút)
MAX_LINE_SECONDS = 90.0  # câu dài hơn thế không đưa cho model (attention bậc hai): dùng đường dự phòng
MIN_CONFIDENCE = 0.7  # trung bình xác suất của khung được gán chữ: câu đúng chữ ≥ 0,94, chữ không khớp giọng đọc 0,35-0,52, thừa chữ 0,65 (đo 03-10)
MAX_AUDIO_SECONDS = 4 * 3600
CTC, SPREAD = "ctc", "spread"
MODEL_FILES = ("wav2vec2-vi-int8.onnx", "vocab.json", "preprocessor_config.json")  # = studio_setup.WORD_ALIGN_FILES

PUNCT_END = set(",.!?:;…")
STRIP = "\"'“”‘’()[]«»—–-…,.!?:;"
FOREIGN_MAP = {"f": "ph", "j": "gi", "w": "u", "z": "d"}  # chỉ khi từ điển model thiếu chữ cái ấy
_TOKEN = re.compile(r"\S+")


# ---- chữ -> âm tiết (không cần numpy) -------------------------------------------------------------------------------------
def tokens(text: str) -> list[str]:
    """Các "chữ hiện": đơn vị cách nhau bằng khoảng trắng, đúng như người đọc tách câu (ui/src/listen/words.ts `splitTokens`)."""
    return _TOKEN.findall(text)


def text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def phrases(toks: Sequence[str]) -> list[list[int]]:
    """Cắt danh sách chữ ở chữ kết thúc bằng dấu ngắt. Trả danh sách các nhóm chỉ số."""
    out: list[list[int]] = []
    current: list[int] = []
    for index, token in enumerate(toks):
        current.append(index)
        core = token.rstrip("\"'”’)")
        if core and core[-1] in PUNCT_END:
            out.append(current)
            current = []
    if current:
        out.append(current)
    return out


_DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]


def _read_three(value: int, full: bool) -> list[str]:
    hundreds, tens, units = value // 100, (value // 10) % 10, value % 10
    words: list[str] = []
    if full or hundreds:
        words += [_DIGITS[hundreds], "trăm"]
    if tens == 0:
        if units and (full or hundreds):
            words += ["linh", _DIGITS[units]]
        elif units:
            words += [_DIGITS[units]]
    elif tens == 1:
        words += ["mười"]
        if units == 5:
            words += ["lăm"]
        elif units:
            words += [_DIGITS[units]]
    else:
        words += [_DIGITS[tens], "mươi"]
        if units == 1:
            words += ["mốt"]
        elif units == 4:
            words += ["tư"]
        elif units == 5:
            words += ["lăm"]
        elif units:
            words += [_DIGITS[units]]
    return words


def read_number(text: str) -> list[str]:
    """Số đọc ra âm tiết ("2.500.000" -> hai triệu năm trăm nghìn); dấu chấm ngăn nhóm ba chữ số."""
    value = int(text.replace(".", ""))
    if value == 0:
        return ["không"]
    units = ["", "nghìn", "triệu", "tỷ"]
    groups: list[int] = []
    while value:
        groups.append(value % 1000)
        value //= 1000
    words: list[str] = []
    for position in range(len(groups) - 1, -1, -1):
        group = groups[position]
        if group == 0:
            continue
        words += _read_three(group, full=position < len(groups) - 1)
        if position < len(units) and units[position]:
            words.append(units[position])
    return words


def spoken_syllables(token: str) -> list[str]:
    """Chữ hiện được đọc ra sao: danh sách âm tiết (chữ thường, chỉ chữ cái). Số đọc thành chữ; "6:30" hay "12/10" tách ở dấu thành hai số."""
    core = token.strip(STRIP).lower()
    if not core:
        return []
    if re.fullmatch(r"\d+(\.\d{3})*", core):
        return read_number(core)
    out: list[str] = []
    for part in re.split(r"[\W_]+", core):
        if part.isdigit():
            out += read_number(part)
        elif part:
            out.append(part)
    return out


def syllable_count(token: str) -> int:
    """Ước lượng số âm tiết khi đọc: số đã đọc ra; âm tiết có dấu = 1; từ ASCII thuần (tên ngoại) = số cụm nguyên âm."""
    spoken = spoken_syllables(token)
    if not spoken:
        return 0
    if len(spoken) > 1:
        return len(spoken)
    word = spoken[0]
    if re.fullmatch(r"[a-z]+", word):
        return max(1, len(re.findall(r"[aeiouy]+", word)))
    return 1


def _letters(syllable: str, vocab: dict[str, int]) -> list[str]:
    out: list[str] = []
    for char in unicodedata.normalize("NFC", syllable):
        if char in vocab:
            out.append(char)
        elif char in FOREIGN_MAP and all(c in vocab for c in FOREIGN_MAP[char]):
            out += list(FOREIGN_MAP[char])
        else:
            base = unicodedata.normalize("NFD", char)
            if all(c in vocab for c in base):
                out += list(base)
            elif base[0] in vocab:
                out.append(base[0])
    return out


def targets(toks: Sequence[str], vocab: dict[str, int]) -> tuple[list[int], list[int]]:
    """Chuỗi nhãn CTC của cả câu: chữ cái của từng âm tiết, các âm tiết cách nhau bằng `|`. Trả (nhãn, chữ hiện sở hữu từng nhãn; -1 cho `|`)."""
    ids: list[int] = []
    owner: list[int] = []
    for index, token in enumerate(toks):
        for syllable in spoken_syllables(token):
            letters = _letters(syllable, vocab)
            if not letters:
                continue
            if ids:
                ids.append(vocab["|"])
                owner.append(-1)
            for letter in letters:
                ids.append(vocab[letter])
                owner.append(index)
    return ids, owner


def finish(found: Sequence[Sequence[float] | None], line_end: float | None = None) -> list[list[int]]:
    """Mốc theo giây của từng chữ hiện (None: chữ không có âm nào, vd dấu "—") -> `[[bắt đầu_ms, kết thúc_ms], ...]`.
    Chữ không có âm đứng yên chỗ chữ trước kết thúc; đầu chữ không lùi; một chữ kết thúc đúng chỗ chữ sau bắt đầu, chữ cuối giữ
    điểm cuối của chính nó."""
    count = len(found)
    first = next((item for item in found if item is not None), None)
    if count == 0:
        return []
    if first is None:
        base = round((0.0 if line_end is None else line_end) * 1000)
        return [[base, base] for _ in range(count)]
    starts: list[float] = []
    ends: list[float] = []
    previous_end = float(first[0])
    for item in found:
        if item is None:
            starts.append(previous_end)
            ends.append(previous_end)
        else:
            starts.append(float(item[0]))
            ends.append(float(item[1]))
            previous_end = float(item[1])
    floor = starts[0]
    for i, start in enumerate(starts):
        floor = max(floor, start)
        starts[i] = floor
    result: list[list[int]] = []
    for i in range(count):
        end = starts[i + 1] if i + 1 < count else max(ends[i], starts[i])
        result.append([round(starts[i] * 1000), max(round(end * 1000), round(starts[i] * 1000))])
    return result


# ---- model + căn CTC ---------------------------------------------------------------------------------------------------------
_studio: Callable[[], Any] | None = None
_lock = threading.RLock()
_aligner: tuple[str, Any] | None = None


def configure(studio: Callable[[], Any] | None) -> None:
    """server.py: `lambda: app.studio` (StudioSetup hay None). App đóng gói không có numpy nên giao việc cho Python của Studio."""
    global _studio
    _studio = studio


def enabled() -> bool:
    return os.environ.get(ENV_SWITCH, "1") != "0"


def _complete(folder: Path) -> bool:
    return all((folder / name).is_file() for name in MODEL_FILES)


def model_dir() -> Path | None:
    """Thư mục model dùng được trên máy này, hay None."""
    candidates: list[Path] = []
    if os.environ.get(ENV_DIR):
        candidates.append(Path(os.environ[ENV_DIR]))
    if os.environ.get(ENV_RUNTIME):
        candidates.append(Path(os.environ[ENV_RUNTIME]) / "models" / "wordalign")
    studio = _studio() if _studio is not None else None
    if studio is not None and getattr(studio, "word_align", None) is not None:
        candidates.append(Path(studio.word_align))
    candidates.append(Path(__file__).resolve().parents[2] / "runtime" / "models" / "wordalign")
    return next((folder for folder in candidates if _complete(folder)), None)


def in_process() -> bool:
    """Căn được ngay trong tiến trình này: có numpy và ffmpeg (onnxruntime chỉ cần cho đường CTC)."""
    return importlib.util.find_spec("numpy") is not None and io_utils.ffmpeg_available()


def _numpy() -> Any:
    import numpy

    return numpy


class Aligner:
    """wav2vec2 CTC (ONNX) + từ điển ký tự. Một phiên onnxruntime dùng chung; mỗi lần chạy một câu."""

    def __init__(self, folder: Path, threads: int | None = None) -> None:
        import onnxruntime

        self.vocab: dict[str, int] = json.loads((folder / "vocab.json").read_text(encoding="utf-8"))
        config = json.loads((folder / "preprocessor_config.json").read_text(encoding="utf-8"))
        if not config.get("do_normalize") or config.get("sampling_rate") != SAMPLE_RATE or self.vocab.get("<pad>") != 0 or "|" not in self.vocab:
            raise ValueError("model căn chữ không phải loại word_timing đã chép cứng (blank = <pad> = 0, dấu cách |, chuẩn hoá, 16 kHz)")
        self.blank = self.vocab["<pad>"]
        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = threads or max(1, min(8, (os.cpu_count() or 2) // 2))  # nửa số lõi logic, tối đa 8: máy vẫn dùng được trong lúc căn
        options.inter_op_num_threads = 1
        self.session = onnxruntime.InferenceSession(str(folder / MODEL_FILES[0]), options, providers=["CPUExecutionProvider"])

    def emissions(self, wave: Any) -> Any:
        """log-softmax [khung, lớp] của một đoạn audio 16 kHz."""
        np = _numpy()
        x = np.asarray(wave, dtype=np.float32)
        x = (x - x.mean()) / np.sqrt(x.var() + 1e-7)
        logits = self.session.run(None, {"audio": x[None]})[0][0]
        logits = logits - logits.max(-1, keepdims=True)
        return logits - np.log(np.exp(logits).sum(-1, keepdims=True))

    def align(self, wave: Any, text: str, offset: float = 0.0) -> tuple[list[list[float] | None], float] | None:
        """Mốc (giây, tính từ đầu chương nhờ `offset`) của từng chữ hiện + độ tin cậy; None nếu không căn được."""
        toks = tokens(text)
        ids, owner = targets(toks, self.vocab)
        if not ids:
            return None
        emission = self.emissions(wave)
        path = forced_align(emission, ids, self.blank)
        if path is None:
            return None
        frames, confidence = path
        found: list[list[float] | None] = [None] * len(toks)
        first: dict[int, int] = {}
        last: dict[int, int] = {}
        for frame, target in enumerate(frames):
            if target < 0:
                continue
            first.setdefault(target, frame)
            last[target] = frame
        for target, start in first.items():
            index = owner[target]
            if index < 0:
                continue
            span = [start * FRAME + offset, (last[target] + 1) * FRAME + offset]
            if found[index] is None:
                found[index] = span
            else:
                found[index][0] = min(found[index][0], span[0])  # type: ignore[index]
                found[index][1] = max(found[index][1], span[1])  # type: ignore[index]
        return found, confidence


def forced_align(emission: Any, ids: Sequence[int], blank: int = 0) -> tuple[list[int], float] | None:
    """Căn Viterbi CTC: (nhãn nào chiếm từng khung, -1 = trống), trung bình xác suất của các khung có nhãn). None khi không đủ khung cho
    chuỗi nhãn (kể cả khung trống bắt buộc giữa hai nhãn trùng nhau). Cùng kết quả `torchaudio.functional.forced_align` trên cùng log-prob."""
    np = _numpy()
    frames, count = emission.shape[0], len(ids)
    need = count + sum(1 for k in range(1, count) if ids[k] == ids[k - 1])
    if count == 0 or frames < need:
        return None
    extended = np.full(2 * count + 1, blank, dtype=np.int64)
    extended[1::2] = ids
    states = len(extended)
    emit = emission[:, extended]  # [khung, trạng thái]
    skip = np.zeros(states, dtype=bool)
    skip[2:] = (extended[2:] != blank) & (extended[2:] != extended[:-2])
    floor = -1e30
    score = np.full(states, floor, dtype=np.float64)
    score[0], score[1] = emit[0, 0], emit[0, 1]
    came = np.zeros((frames, states), dtype=np.int8)
    rows = np.arange(states)
    for t in range(1, frames):
        stay = score
        one = np.concatenate(([floor], score[:-1]))
        two = np.where(skip, np.concatenate(([floor, floor], score[:-2])), floor)
        stacked = np.stack((stay, one, two))
        step = stacked.argmax(0)
        score = stacked[step, rows] + emit[t]
        came[t] = step
    state = states - 1 if score[states - 1] >= score[states - 2] else states - 2
    labelled: list[int] = [-1] * frames
    probability = 0.0
    used = 0
    for t in range(frames - 1, -1, -1):
        if state % 2 == 1:
            labelled[t] = (state - 1) // 2
            probability += float(np.exp(emit[t, state]))
            used += 1
        state -= int(came[t, state])
    return labelled, probability / used if used else 0.0


# ---- đường dự phòng: chia theo âm tiết + dò ngắt bằng năng lượng ----------------------------------------------------------
def _frame_db(wave: Any) -> Any:
    np = _numpy()
    hop = int(SAMPLE_RATE * HOP)
    window = hop * 2
    count = max(1, 1 + (len(wave) - window) // hop)
    index = np.minimum(np.arange(window)[None, :] + hop * np.arange(count)[:, None], len(wave) - 1)
    rms = np.sqrt((wave[index] ** 2).mean(1) + 1e-12)
    return 20 * np.log10(rms + 1e-9)


def _trim(db: Any, relative: float = 40.0) -> tuple[int, int]:
    np = _numpy()
    threshold = max(db.max() - relative, -60)
    voiced = np.where(db > threshold)[0]
    return (0, len(db)) if len(voiced) == 0 else (int(voiced[0]), int(voiced[-1]) + 1)


def _pauses(db: Any, first: int, last: int, relative: float = 35.0, shortest: float = 0.12) -> list[tuple[float, float]]:
    np = _numpy()
    segment = db[first:last]
    low = segment <= max(segment.max() - relative, -60)
    out: list[tuple[float, float]] = []
    index = 0
    while index < len(low):
        if low[index]:
            end = index
            while end < len(low) and low[end]:
                end += 1
            if (end - index) * HOP >= shortest:
                out.append(((first + index) * HOP, (first + end) * HOP))
            index = end
        else:
            index += 1
    return out


def _spread(span: tuple[float, float], members: Sequence[int], weight: Sequence[float]) -> dict[int, tuple[float, float]]:
    start, end = span
    sizes = [weight[i] for i in members]
    total = sum(sizes) or 1.0
    done = 0.0
    out: dict[int, tuple[float, float]] = {}
    for index, size in zip(members, sizes):
        out[index] = (start + (end - start) * done / total, start + (end - start) * (done + size) / total)
        done += size
    return out


def spread_words(wave: Any, text: str, offset: float = 0.0) -> list[list[float] | None]:
    """Đường dự phòng: chia thời gian có tiếng của câu theo âm tiết, nhưng neo các chỗ ngắt (dấu câu) vào khoảng lặng thật dò bằng năng lượng
    (khớp tuần tự bằng quy hoạch động giữa chỗ ngắt dự kiến và các khoảng lặng ≥ 120 ms). Tính từ `offset` giây."""
    np = _numpy()
    toks = tokens(text)
    if not toks or len(wave) < int(SAMPLE_RATE * HOP * 3):
        return [None] * len(toks)
    weight = [float(syllable_count(token)) for token in toks]
    groups = phrases(toks)
    db = _frame_db(np.asarray(wave, dtype=np.float32))
    first, last = _trim(db)
    begin, finish_at = first * HOP, last * HOP
    estimate: list[list[float] | None] = [None] * len(toks)
    if len(groups) > 1:
        silences = _pauses(db, first, last)
        total = sum(weight) or 1.0
        cumulative = np.cumsum([sum(weight[i] for i in group) for group in groups])[:-1] / total
        expected = begin + (finish_at - begin) * cumulative
        middles = [(a + b) / 2 for a, b in silences]
        breaks, pauses = len(expected), len(middles)
        tolerance = 0.3 * (finish_at - begin) + 1e-6
        best = np.zeros((breaks + 1, pauses + 1))
        move: dict[tuple[int, int], str] = {}
        for k in range(breaks + 1):
            for j in range(pauses + 1):
                if k == 0 and j == 0:
                    continue
                options: list[tuple[float, str]] = []
                if k > 0:
                    options.append((best[k - 1][j], "skip-break"))
                if j > 0:
                    options.append((best[k][j - 1], "skip-pause"))
                if k > 0 and j > 0:
                    gain = 1.0 - abs(middles[j - 1] - expected[k - 1]) / tolerance
                    if gain > 0:
                        options.append((best[k - 1][j - 1] + gain + 0.5 * (silences[j - 1][1] - silences[j - 1][0]), "match"))
                score, choice = max(options, key=lambda item: item[0])
                best[k][j] = score
                move[(k, j)] = choice
        k, j, matched = breaks, pauses, {}
        while k > 0 or j > 0:
            choice = move[(k, j)]
            if choice == "match":
                matched[k - 1] = silences[j - 1]
                k, j = k - 1, j - 1
            elif choice == "skip-break":
                k -= 1
            else:
                j -= 1
        members: list[int] = []
        cursor = begin
        for number, group in enumerate(groups):
            members += group
            if number < breaks and number in matched:
                quiet_start, quiet_end = matched[number]
                for index, span in _spread((cursor, quiet_start), members, weight).items():
                    estimate[index] = [span[0] + offset, span[1] + offset]
                members, cursor = [], quiet_end
        for index, span in _spread((cursor, finish_at), members, weight).items():
            estimate[index] = [span[0] + offset, span[1] + offset]
        return _drop_silent(estimate, toks)
    for index, span in _spread((begin, finish_at), list(range(len(toks))), weight).items():
        estimate[index] = [span[0] + offset, span[1] + offset]
    return _drop_silent(estimate, toks)


def _drop_silent(estimate: list[list[float] | None], toks: Sequence[str]) -> list[list[float] | None]:
    """Chữ không đọc ra âm nào (dấu "—", "...") không giữ thời gian riêng: `finish` cho nó đứng yên chỗ chữ trước kết thúc."""
    return [None if not spoken_syllables(token) else span for token, span in zip(toks, estimate)]


# ---- audio ------------------------------------------------------------------------------------------------------------------
def decode(path: Path) -> Any:
    """Cả chương thành float32 mono 16 kHz bằng ffmpeg của app (music_mel.decode cắt ở 30 phút đầu; chương dài hơn vẫn phải căn đủ).
    Không đọc được thì mảng rỗng."""
    np = _numpy()
    try:
        raw = subprocess.run(
            [io_utils.ffmpeg_executable(), "-v", "error", "-nostdin", "-threads", "1", "-i", str(path), "-ac", "1", "-ar", str(SAMPLE_RATE),
             "-t", str(MAX_AUDIO_SECONDS), "-f", "s16le", "-"],
            capture_output=True, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0).stdout
    except (OSError, subprocess.SubprocessError):
        return np.zeros(0, dtype=np.float32)
    return np.frombuffer(raw[: len(raw) // 2 * 2], dtype=np.int16).astype(np.float32) / 32768.0


def line_words(wave: Any, text: str, offset: float, aligner: Aligner | None) -> tuple[list[list[int]], str, float]:
    """Mốc từng chữ của MỘT câu: `wave` là đoạn audio quanh câu (bắt đầu ở `offset` giây trong chương). Trả (words, cách căn, độ tin cậy)."""
    toks = tokens(text)
    if aligner is not None and 0 < len(wave) <= MAX_LINE_SECONDS * SAMPLE_RATE:
        try:
            aligned = aligner.align(wave, text, offset)
        except Exception:  # noqa: BLE001 - model hỏng/không nạp được một câu thì câu ấy dùng đường dự phòng
            aligned = None
        if aligned is not None and aligned[1] >= MIN_CONFIDENCE:
            return finish(aligned[0]), CTC, aligned[1]
    return finish(spread_words(wave, text, offset)), SPREAD, 0.0


def get_aligner() -> Aligner | None:
    """Bộ căn dùng chung (nạp một lần, nạp lại khi thư mục model đổi); None nếu thiếu model hay onnxruntime."""
    global _aligner
    folder = model_dir()
    if folder is None:
        return None
    with _lock:
        if _aligner is not None and _aligner[0] == str(folder):
            return _aligner[1]
        try:
            if importlib.util.find_spec("onnxruntime") is None:
                return None
            loaded = Aligner(folder)
        except Exception:  # noqa: BLE001 - model hỏng: coi như chưa có, đường dự phòng vẫn chạy
            return None
        _aligner = (str(folder), loaded)
        return loaded


def reset() -> None:
    global _aligner
    with _lock:
        _aligner = None


# ---- bộ nhớ đệm ---------------------------------------------------------------------------------------------------------------
def cache_file(project_root: Path, chapter_id: int) -> Path:
    return Path(project_root) / CACHE_FOLDER / f"{int(chapter_id)}.json"


def _load(project_root: Path, chapter_id: int) -> dict[str, Any]:
    try:
        data = json.loads(cache_file(project_root, chapter_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) and data.get("version") == VERSION and isinstance(data.get("lines"), dict) else {}


def _save(project_root: Path, chapter_id: int, data: dict[str, Any]) -> None:
    io_utils.atomic_write_bytes(cache_file(project_root, chapter_id), json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), fsync=False)


def _milliseconds(segment: dict[str, Any]) -> list[int] | None:
    start, end = segment.get("start"), segment.get("end")
    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
        return None
    return [round(start * 1000), round(end * 1000)]


def _valid(entry: Any, segment: dict[str, Any]) -> bool:
    return (isinstance(entry, dict) and entry.get("textSha256") == text_sha(str(segment.get("text", "")))
            and entry.get("span") == _milliseconds(segment) and isinstance(entry.get("words"), list)
            and len(entry["words"]) == len(tokens(str(segment.get("text", "")))))


def attach(project_root: Path, chapter_id: int, segments: Sequence[dict[str, Any]], audio: Path | None) -> int:
    """Thêm `words` đã căn vào các câu của một chương (store.chapter_script): chỉ câu mà chữ + khoảng thời gian còn khớp bộ nhớ đệm, và chỉ khi audio
    chương vẫn là file đã căn (cỡ + mốc sửa). Rẻ, không cần numpy. Trả số câu có `words`."""
    if audio is None:
        return 0
    cache = _load(project_root, chapter_id)
    stamp = cache.get("audio") if cache else None
    try:
        stat = audio.stat()
    except OSError:
        return 0
    if not isinstance(stamp, dict) or stamp.get("size") != stat.st_size or stamp.get("mtimeNs") != stat.st_mtime_ns:
        return 0
    lines = cache["lines"]
    count = 0
    for segment in segments:
        entry = lines.get(str(segment.get("id")))
        if _valid(entry, segment):
            segment["words"] = entry["words"]
            count += 1
    return count


def stamp(project_root: Path) -> str:
    """Dấu hiệu "mốc chữ của sách này đã đổi" cho đồng bộ điện thoại (sync.manifest, library_view): băm tên + cỡ + mốc sửa của các file bộ nhớ đệm
    (chỉ `stat`, không đọc file - danh sách thư viện được hỏi liên tục). Rỗng khi sách chưa căn chữ nào, nên sách chưa căn giữ nguyên
    phiên bản gói như trước và điện thoại không tải lại gì."""
    folder = Path(project_root) / CACHE_FOLDER
    parts: list[list[Any]] = []
    try:
        for file in sorted(folder.glob("*.json")):
            info = file.stat()
            parts.append([file.name, info.st_size, info.st_mtime_ns])
    except OSError:
        return ""
    return hashlib.sha256(json.dumps(parts).encode("utf-8")).hexdigest()[:12] if parts else ""


_hashes: dict[tuple[str, int, int], str] = {}


def audio_sha256(path: Path) -> str:
    stat = path.stat()
    key = (str(path), stat.st_size, stat.st_mtime_ns)
    if key not in _hashes:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1 << 20):
                digest.update(chunk)
        _hashes[key] = digest.hexdigest()
    return _hashes[key]


def coverage(project_root: Path) -> dict[str, int]:
    """{"lines": số câu có audio, "words": số câu đã có `words`} của cả dự án - cho nút "Căn từ cho sách đã làm"."""
    from . import store

    total = done = 0
    for chapter in store.chapters(project_root):
        if not chapter.get("playable"):
            continue
        script = store.chapter_script(project_root, int(chapter["id"]))
        if not script or not script.get("timed"):
            continue
        total += len(script["segments"])
        done += sum(1 for segment in script["segments"] if "words" in segment)
    return {"lines": total, "words": done}


# ---- căn một chương / cả dự án ------------------------------------------------------------------------------------------------
Progress = Callable[[int, int], None]


def align_chapter(project_root: Path, chapter_id: int, *, aligner: Any = ..., progress: Progress | None = None,
                  cancelled: Callable[[], bool] = lambda: False) -> dict[str, Any]:
    """Căn (lại) những câu của một chương chưa có mốc hợp lệ trong bộ nhớ đệm. Trả thống kê: lines, cached, ctc, spread, seconds (audio đã căn)."""
    from . import store

    stats: dict[str, Any] = {"chapter": int(chapter_id), "lines": 0, "cached": 0, "ctc": 0, "spread": 0, "seconds": 0.0, "skipped": ""}
    audio = store.chapter_audio_path(project_root, chapter_id)
    script = store.chapter_script(project_root, chapter_id)
    if audio is None or not script or not script.get("timed"):
        stats["skipped"] = "chưa có audio"
        return stats
    segments = [segment for segment in script["segments"] if _milliseconds(segment) is not None]
    stats["lines"] = len(segments)
    sha = audio_sha256(audio)
    stat = audio.stat()
    cache = _load(project_root, chapter_id)
    if (cache.get("audio") or {}).get("sha256") != sha:
        cache = {}
    helper = get_aligner() if aligner is ... else aligner
    lines: dict[str, Any] = cache.get("lines") or {}
    todo = []
    for position, segment in enumerate(segments):
        entry = lines.get(str(segment["id"]))
        # Câu căn dự phòng được căn lại khi đã có model; câu CTC thì giữ.
        if _valid(entry, segment) and (entry.get("method") == CTC or helper is None):
            stats["cached"] += 1
        else:
            todo.append(position)
    stamp = {"sha256": sha, "size": stat.st_size, "mtimeNs": stat.st_mtime_ns}
    if not todo:
        if cache.get("audio") != stamp:  # cùng nội dung, khác mốc sửa (chép dự án sang chỗ khác): ghi mốc mới
            _save(project_root, chapter_id, {"version": VERSION, "audio": stamp, "lines": lines})
        return stats
    wave = decode(audio)
    total = len(wave) / SAMPLE_RATE
    if total <= 0:
        stats["skipped"] = "không giải mã được audio"
        return stats
    begin = time.perf_counter()
    for number, index in enumerate(todo):
        if cancelled():
            break
        segment = segments[index]
        start, end = float(segment["start"]), float(segment["end"])
        before = start - float(segments[index - 1]["end"]) if index > 0 else 2 * MARGIN
        after = float(segments[index + 1]["start"]) - end if index + 1 < len(segments) else 2 * MARGIN
        a = max(0.0, start - min(MARGIN, max(0.0, before) / 2))
        b = min(total, end + min(MARGIN, max(0.0, after) / 2))
        text = str(segment["text"])
        words, method, confidence = line_words(wave[int(a * SAMPLE_RATE): int(b * SAMPLE_RATE)], text, a, helper)
        lines[str(segment["id"])] = {"textSha256": text_sha(text), "span": _milliseconds(segment), "method": method,
                                     "confidence": round(confidence, 3), "words": words}
        stats[method] += 1
        stats["seconds"] += end - start
        if progress is not None:
            progress(number + 1, len(todo))
        if (number + 1) % 200 == 0:
            _save(project_root, chapter_id, {"version": VERSION, "audio": stamp, "lines": lines})
    stats["elapsed"] = round(time.perf_counter() - begin, 2)
    _save(project_root, chapter_id, {"version": VERSION, "audio": stamp, "lines": lines})
    return stats


def prepare(project_root: Path, chapter_ids: Sequence[int] | None = None, *, progress: Progress | None = None,
            cancelled: Callable[[], bool] = lambda: False) -> dict[str, Any]:
    """Căn mọi câu còn thiếu mốc của các chương (mặc định: mọi chương nghe được) rồi để bộ nhớ đệm cho `attach`. Không bao giờ ném lỗi ra ngoài
    (đóng gói sách phải xong dù không căn được): `error` trong kết quả nói vì sao. `mode`: "process" (ngay đây), "studio" (Python của
    Studio), "off" (tắt / không có cách nào)."""
    summary: dict[str, Any] = {"mode": "off", "chapters": 0, "lines": 0, "cached": 0, "ctc": 0, "spread": 0, "seconds": 0.0, "error": ""}
    if not enabled():
        return summary
    try:
        ids = list(chapter_ids) if chapter_ids is not None else _playable(project_root)
        if in_process():
            summary["mode"] = "process"
            helper = get_aligner()
            for chapter_id in ids:
                if cancelled():
                    break
                stats = align_chapter(project_root, chapter_id, aligner=helper, progress=progress, cancelled=cancelled)
                summary["chapters"] += 1
                for key in ("lines", "cached", "ctc", "spread", "seconds"):
                    summary[key] += stats[key]
            return summary
        studio = _studio() if _studio is not None else None
        if studio is not None and studio.installed() and not studio.outdated():
            summary["mode"] = "studio"
            summary.update(_run_in_studio(studio, project_root, ids, progress, cancelled))
        else:
            summary["error"] = "máy này chưa có Studio nên chưa căn được từng chữ"
    except Exception as error:  # noqa: BLE001 - xem docstring
        summary["error"] = f"{type(error).__name__}: {error}"
    return summary


def _playable(project_root: Path) -> list[int]:
    from . import store

    return [int(chapter["id"]) for chapter in store.chapters(project_root) if chapter.get("playable")]


def _run_in_studio(studio: Any, project_root: Path, ids: Sequence[int], progress: Progress | None,
                   cancelled: Callable[[], bool]) -> dict[str, Any]:
    """Python của Studio chạy `align` (có numpy + onnxruntime); đọc tiến độ từ các dòng JSON nó in."""
    command = [str(studio.python), "-m", "abook.webui.word_timing", "align", str(project_root), "--json"]
    for chapter_id in ids:
        command += ["--chapter", str(chapter_id)]
    environment = {**os.environ, **studio.environment()}
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                               env=environment, cwd=str(studio.app_root),
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
    result: dict[str, Any] = {}
    tail: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        if cancelled():
            process.kill()
            break
        try:
            message = json.loads(line)
        except ValueError:
            tail = (tail + [line.strip()])[-3:]
            continue
        if "progress" in message and progress is not None:
            progress(int(message["progress"][0]), int(message["progress"][1]))
        elif "summary" in message:
            result = message["summary"]
    code = process.wait()
    if code != 0 and not result:
        return {"error": "Python của Studio không căn được: " + " | ".join(tail)[-300:]}
    return {key: result.get(key, 0) for key in ("chapters", "lines", "cached", "ctc", "spread", "seconds")}


# ---- việc nền "Căn từ cho sách đã làm" ----------------------------------------------------------------------------------------
class Job:
    """Một lượt "Căn từ cho sách đã làm" mỗi dự án: căn mọi chương rồi đóng lại file sách của dự án kèm `words`. Giao diện hỏi `status`."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict[str, dict[str, Any]] = {}
        self._cancel: dict[str, threading.Event] = {}

    def status(self, project_root: Path) -> dict[str, Any]:
        with self._lock:
            state = dict(self._state.get(str(project_root)) or {"state": "idle"})
        # Đang chạy thì giao diện hỏi mỗi giây: chỉ trả tiến độ, đếm câu (đọc mọi chương) để lúc rảnh.
        return state if state["state"] == "running" else {**state, **coverage(project_root)}

    def start(self, project_root: Path, repack: Callable[[], Path | None] | None = None) -> dict[str, Any]:
        key = str(project_root)
        with self._lock:
            if (self._state.get(key) or {}).get("state") == "running":
                return self.status(project_root)
            cancel = self._cancel[key] = threading.Event()
            self._state[key] = {"state": "running", "done": 0, "total": 0, "error": "", "file": ""}

        def update(**changes: Any) -> None:
            with self._lock:
                self._state[key] = {**self._state[key], **changes}

        def work() -> None:
            try:
                summary = prepare(project_root, progress=lambda done, total: update(done=done, total=total), cancelled=cancel.is_set)
                if summary["error"]:
                    update(state="error", error=summary["error"])
                    return
                file = repack() if repack is not None and not cancel.is_set() else None
                update(state="done", file=str(file) if file else "", **{k: summary[k] for k in ("ctc", "spread", "cached")})
            except Exception as error:  # noqa: BLE001 - lỗi lạ phải tới được người dùng, không giết luồng im lặng
                update(state="error", error=f"{type(error).__name__}: {error}")

        threading.Thread(target=work, name="word-timing", daemon=True).start()
        return self.status(project_root)

    def cancel(self, project_root: Path) -> None:
        event = self._cancel.get(str(project_root))
        if event is not None:
            event.set()


# ---- dòng lệnh ---------------------------------------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Căn từng chữ của sách nói vào audio chương.")
    commands = parser.add_subparsers(dest="command", required=True)
    align = commands.add_parser("align", help="căn các câu còn thiếu mốc chữ rồi ghi bộ nhớ đệm")
    align.add_argument("project", type=Path)
    align.add_argument("--chapter", type=int, action="append", help="chỉ chương này (nhắc lại được)")
    align.add_argument("--json", action="store_true", help="in tiến độ và kết quả dạng từng dòng JSON (Studio gọi)")
    align.add_argument("--pack", action="store_true", help="căn xong thì đóng lại file .abook")
    align.add_argument("-o", "--out", type=Path)
    args = parser.parse_args(argv)
    if not in_process():
        print("Cần numpy và ffmpeg để căn chữ.", file=sys.stderr)
        return 2
    last = [0.0]

    def progress(done: int, total: int) -> None:
        if args.json and (time.monotonic() - last[0] > 0.5 or done == total):
            last[0] = time.monotonic()
            print(json.dumps({"progress": [done, total]}), flush=True)

    ids = args.chapter or _playable(args.project)
    summary = {"chapters": 0, "lines": 0, "cached": 0, "ctc": 0, "spread": 0, "seconds": 0.0}
    helper = get_aligner()
    if helper is None and not args.json:
        print("Chưa có model (hay onnxruntime): căn bằng đường dự phòng (chia theo âm tiết + dò ngắt).", file=sys.stderr)
    for chapter_id in ids:
        stats = align_chapter(args.project, chapter_id, aligner=helper, progress=progress)
        summary["chapters"] += 1
        for key in ("lines", "cached", "ctc", "spread", "seconds"):
            summary[key] += stats[key]
        if not args.json:
            print(f"chương {chapter_id}: {stats['lines']} câu, đã có {stats['cached']}, CTC {stats['ctc']}, dự phòng {stats['spread']}"
                  + (f" ({stats['skipped']})" if stats["skipped"] else ""))
    if args.json:
        print(json.dumps({"summary": summary}), flush=True)
    if args.pack:
        from . import bookfile

        print(bookfile.pack(args.project, args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
