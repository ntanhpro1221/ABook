"""Trộn nhạc nền: MỘT nguồn hằng số cho ba bên và dòng thời gian thuần của một chương (Corpus/research/music/MIX_QA.md 7.1, 7.2).

`assets/music_mix.json` là file DUY NHẤT chứa các mức mờ, ngưỡng lặp, độ to giọng: máy chủ đọc ở đây lúc nạp module (`MIX` -
music_plan, music_select lấy hằng số từ đó), trình phát web gói nó vào bundle (ui/src/listen/musicBed.ts), Android đọc nó như
asset (MusicBed.kt). Đổi một con số thì chỉ đổi file ấy.

Mô hình lặp chung (lô 2 mix-loop, MIX_QA 3.2 + 9) - ba bên theo đúng: mỗi bài có A = `audibleStart`, E = `audibleEnd` (giây; thiếu
thì 0 và độ dài thật), X = `loopCrossfadeSeconds`. Bài có đoạn kết soạn sẵn mang thêm điểm vòng `loopStart` / `loopEnd` của danh
mục (Corpus/research/music/PLAN_loop.md §10; hợp lệ khi A <= loopStart < loopEnd - X <= E và chu kỳ >= `loopMinPeriodSeconds`,
không thì như không có): lặp nối giữa bài thay vì "kết bài -> đầu bài". Không có điểm vòng thì loopStart = A, loopEnd = E.
- Vào bài: phát từ A + lệch.
- Lặp: E - A >= 3X thì tới loopEnd - X một phần tử MỚI phát từ loopStart, mờ chéo X giây với phần tử cũ (cũ dừng khi mờ xong);
  chu kỳ P = loopEnd - loopStart - X. Bài quá ngắn thì lặp thường cả file như cũ.
- Tua (`loop_position`, t = giây - đầu mốc): t < loopEnd - X - A thì A + t; sau đó loopStart + ((t - (loopStart - A)) mod P).
- Vòng cuối của mốc `tail` (music_plan.chapter_cues): không mở phần tử lặp mới, bài chơi QUA loopEnd tới E là hết (đoạn kết soạn
  sẵn là cái kết; vòng cuối dài E - loopStart); mốc kế bắt đầu đúng ở cuối mốc thì vào sớm ngay lúc ấy. Lịch mở phần tử và chỗ
  hết vòng cuối: `loop_schedule`.
- Nối bài anh em: bài cũ mờ ra trong min(siblingFadeSeconds, E - vị trí) - không bao giờ bị cắt khi còn kêu.
"""
from __future__ import annotations

import json
import math
from collections.abc import Iterable
from itertools import pairwise
from pathlib import Path
from typing import Any, NamedTuple

MIX_FILE = Path(__file__).resolve().parent / "assets" / "music_mix.json"


def _constant(value: Any) -> Any:
    """Số -> float (sai kiểu thì văng ngay lúc nạp); bảng (`truePeakFir` của bản xuất kèm nhạc, music_render) -> các hàng float."""
    if isinstance(value, list):
        return [[float(item) for item in row] for row in value]
    return float(value)


MIX: dict[str, Any] = {key: _constant(value) for key, value in json.loads(MIX_FILE.read_text(encoding="utf-8")).items()}
LOOP_CROSSFADE_SECONDS = MIX["loopCrossfadeSeconds"]
LOOP_MIN_PERIOD_SECONDS = MIX["loopMinPeriodSeconds"]
LOOP_KEYS = ("loopStart", "loopEnd")  # điểm vòng của bài trong danh mục (giây trong bài), đi theo bài như audibleStart / audibleEnd
_EPS = 1e-6


def number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


class LoopBounds(NamedTuple):
    """Vòng lặp của một bài (giây trong bài): vào từ `start` (A), hết ở `end` (E), chu kỳ `period`; `crossfade` False = lặp thường
    cả file. Phần tử lặp mở ở `loop_end` - X và phát từ `loop_start` (không có điểm vòng: A và E)."""
    start: float
    end: float
    period: float
    crossfade: bool
    loop_start: float
    loop_end: float


def loop_bounds(seconds: Any, audible_start: Any = None, audible_end: Any = None, loop_start: Any = None,
                loop_end: Any = None) -> LoopBounds:
    """Vòng lặp của một bài dài `seconds` (độ dài thật; thiếu = chưa biết). Bài quá ngắn (E - A < 3X) lặp thường cả file:
    (0, độ dài, độ dài, False). Chưa biết độ dài lẫn E: (0, vô cùng, vô cùng, False) - bài coi như không bao giờ hết. Điểm vòng
    (`loop_start`, `loop_end`) chỉ dùng khi hợp lệ với A, E đã tính (docstring module)."""
    total = number(seconds)
    total = total if total is not None and total > 0 else None
    start, end = number(audible_start), number(audible_end)
    start = start if start is not None and start >= 0 else 0.0
    end = end if end is not None and end > 0 else total
    if end is None:
        return LoopBounds(0.0, math.inf, math.inf, False, 0.0, math.inf)
    if total is not None:
        end = min(end, total)
    if end - start < 3 * LOOP_CROSSFADE_SECONDS:
        whole = total if total is not None else end
        return LoopBounds(0.0, whole, whole, False, 0.0, whole)
    restart, out = number(loop_start), number(loop_end)
    if out is not None and total is not None and out - LOOP_CROSSFADE_SECONDS <= end:
        out = min(out, total)
    if (restart is not None and out is not None and start <= restart < out - LOOP_CROSSFADE_SECONDS <= end
            and out - restart - LOOP_CROSSFADE_SECONDS >= LOOP_MIN_PERIOD_SECONDS):
        return LoopBounds(start, end, out - restart - LOOP_CROSSFADE_SECONDS, True, restart, out)
    return LoopBounds(start, end, end - start - LOOP_CROSSFADE_SECONDS, True, start, end)


def track_loop_bounds(info: dict[str, Any] | None, seconds: Any) -> LoopBounds:
    """`loop_bounds` của bài mang thông tin `info` (audibleStart / audibleEnd / loopStart / loopEnd), độ dài thật `seconds`."""
    info = info or {}
    return loop_bounds(seconds, info.get("audibleStart"), info.get("audibleEnd"), info.get("loopStart"), info.get("loopEnd"))


def loop_position(bounds: LoopBounds, t: float) -> float:
    """Chỗ trong bài (giây) sau `t` >= 0 giây kể từ lúc bài vào từ A (tua, vào giữa mốc). Không có điểm vòng thì đúng A + (t mod P)
    như trước (loop_start - A = 0)."""
    if not math.isfinite(bounds.period):
        return bounds.start + t
    if bounds.crossfade and t < bounds.loop_end - LOOP_CROSSFADE_SECONDS - bounds.start:
        return bounds.start + t
    return bounds.loop_start + ((t - (bounds.loop_start - bounds.start)) % bounds.period)


def loop_schedule(bounds: LoopBounds, length: float, tail: bool = False) -> tuple[list[float], float]:
    """(lúc mở các phần tử lặp, lúc nhạc hết) của một mốc dài `length` giây mà bài vào từ A ở giây 0. Lượt j hết tự nhiên (tới E)
    ở (E - A) + j·P và mở phần tử kế ở đó - (E - loopEnd + X). Mốc thường: mọi phần tử mở trước `length`, nhạc hết ở `length`.
    Mốc `tail`: vòng cuối = lượt đầu tiên mà phần còn lại của mốc hơn chỗ bài hết chưa tới nửa chu kỳ (như `finalLoop` của trình
    phát); không mở phần tử sau nó, nhạc hết ở E của vòng ấy. Lặp thường cả file không mở phần tử nào."""
    natural = bounds.end - bounds.start
    lead = bounds.end - bounds.loop_end + LOOP_CROSSFADE_SECONDS  # từ lúc mở phần tử kế tới lúc lượt đang kêu tới E
    opens: list[float] = []
    if tail:
        while math.isfinite(natural) and length - natural >= bounds.period / 2:
            if bounds.crossfade:
                opens.append(natural - lead)
            natural += bounds.period
        return opens, natural
    while bounds.crossfade and natural - lead < length:
        opens.append(natural - lead)
        natural += bounds.period
    return opens, length


def _step_db(cue: dict[str, Any], seconds: float) -> float:
    """Mức bước (dB) của mốc tại giây `seconds`: bước cuối cùng đã tới, chưa tới bước nào thì 0 (musicBed.ts `stepDbAt`)."""
    db = 0.0
    for step in sorted(cue.get("steps") or [], key=lambda step: float(step["at"])):
        if seconds < float(step["at"]):
            break
        db = float(step["db"])
    return db


def _level(cue: dict[str, Any], seconds: float) -> float:
    """Biên độ đích (tuyến tính) của mốc tại giây `seconds`: gainDb + bước, <= 0 dB như trình phát."""
    return 10 ** (min(0.0, float(cue.get("gainDb") or 0.0) + _step_db(cue, seconds)) / 20)


class _Element:
    """Một phần tử đang kêu: bài `track` vào lúc `begin` ở vị trí `position` (giây trong bài); `points` = đường biên độ
    [(giây chương, biên độ tuyến tính)], nội suy tuyến tính, sau điểm cuối giữ nguyên."""

    def __init__(self, track: str, cue: int, enter: str, begin: float, position: float,
                 bounds: LoopBounds) -> None:
        self.track, self.cue, self.enter, self.begin, self.position, self.bounds = track, cue, enter, begin, position, bounds
        self.points: list[tuple[float, float]] = []
        self.to: float | None = None

    def at(self, seconds: float) -> float:
        """Vị trí trong bài ở giây `seconds` của chương."""
        return self.position + seconds - self.begin

    def amplitude(self, seconds: float) -> float:
        points = self.points
        if not points or seconds <= points[0][0]:
            return points[0][1] if points else 0.0
        for (t0, a0), (t1, a1) in pairwise(points):
            if seconds <= t1:
                return a0 + (a1 - a0) * (seconds - t0) / (t1 - t0) if t1 > t0 else a1
        return points[-1][1]

    def ramp(self, seconds: float, target: float, length: float) -> None:
        """Từ giây `seconds` trượt tuyến tính tới biên độ `target` trong `length` giây; đường dự tính sau đó bị thay."""
        now = self.amplitude(seconds)
        self.points = [point for point in self.points if point[0] < seconds - _EPS] + [(seconds, now), (seconds + length, target)]

    def shape(self) -> dict[str, Any]:
        out: dict[str, Any] = {"track": self.track, "cue": self.cue, "enter": self.enter, "from": round(self.begin, 3),
                               "to": round(self.to if self.to is not None else math.inf, 3), "position": round(self.position, 3),
                               "gain": [[round(t, 3), round(20 * math.log10(a), 2) if a > 1e-9 else None] for t, a in self.points]}
        if not self.bounds.crossfade:
            out["loop"] = True  # lặp thường cả file (bài quá ngắn để mờ chéo)
        return out


def music_timeline(cues: Iterable[dict[str, Any]], chapter_seconds: float | None,
                   tracks: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Dòng thời gian nhạc của một chương theo "mô hình lặp chung" (docstring module) - hàm thuần, không âm thanh: bản xuất dùng
    trực tiếp, hai trình phát theo cùng quy tắc (test chéo bằng tests/fixtures/music_timeline).

    `cues`: mốc của chương ({start, end, track, gainDb, steps?, sibling?, tail?} - như music_plan.chapter_cues / package, `track` là
    khoá vào `tracks`); `chapter_seconds`: độ dài chương (mốc cuối kẹp như `clamp_to_chapter`); `tracks`: {track: {seconds (độ dài
    thật), audibleStart, audibleEnd, loopStart?, loopEnd?}}. Ra: các phần tử theo thứ tự vào - {track, cue (chỉ số mốc), enter ("start" đầu mốc, "loop"
    phần tử lặp, "early" vào sớm), from, to (giây chương), position (giây trong bài lúc `from`), gain [[giây, dB hay None = câm]]
    (nội suy tuyến tính theo biên độ), loop (chỉ có khi lặp thường cả file)}."""
    from .music_plan import clamp_to_chapter  # music_plan nạp module này: nhập muộn, tránh vòng

    fade, sibling_fade, ramp, crossfade = (MIX["fadeSeconds"], MIX["siblingFadeSeconds"], MIX["stepRampSeconds"],
                                           LOOP_CROSSFADE_SECONDS)
    cues = clamp_to_chapter(sorted((dict(cue) for cue in cues), key=lambda cue: float(cue["start"])), chapter_seconds)
    out: list[_Element] = []
    current: _Element | None = None  # phần tử còn kêu ở cuối mốc trước (chơi tiếp sang mốc kề cùng bài)
    ended: _Element | None = None    # phần tử của mốc trước đã chơi tới E trước khi mốc ấy hết (vòng cuối)
    for index, cue in enumerate(cues):
        start, end = float(cue["start"]), float(cue["end"])
        info = tracks.get(cue["track"]) or {}
        bounds = track_loop_bounds(info, info.get("seconds"))
        first, last, period, crossfading = bounds.start, bounds.end, bounds.period, bounds.crossfade
        if current is not None and current.track == cue["track"]:
            element = current  # cùng bài sang mốc kề: chơi tiếp, mức theo mốc mới
            if abs(element.amplitude(start) - _level(cue, start)) > 1e-9:
                element.ramp(start, _level(cue, start), ramp)
        else:
            previous = cues[index - 1] if index else None
            early = (ended is not None and previous is not None and previous.get("tail") and ended.track != cue["track"]
                     and abs(float(previous["end"]) - start) < _EPS and ended.to is not None and ended.to < start - _EPS)
            begin = ended.to if early else start
            element = _Element(cue["track"], index, "early" if early else "start", begin, first, bounds)
            element.points = [(begin, 0.0), (begin + (sibling_fade if cue.get("sibling") else fade), _level(cue, max(begin, start)))]
            out.append(element)
        current, ended = None, None
        steps = sorted(float(step["at"]) for step in cue.get("steps") or [] if start < float(step["at"]) < end)
        while True:
            if crossfading:
                # Vòng cuối (lô 1 `finalLoop`, tính theo E): phần còn lại của mốc hơn phần còn lại của bài chưa tới nửa chu kỳ.
                natural = element.begin + (last - element.position)
                final = bool(cue.get("tail")) and end - natural < period / 2
            else:  # lặp thường cả file: chỉ mốc `tail` có vòng cuối
                final = bool(cue.get("tail"))
                natural = _final_pass(element, period, end) if final else math.inf
            spawn = element.begin + (bounds.loop_end - crossfade - element.position) if crossfading and not final else math.inf
            stop = min(spawn, natural if final else math.inf, end)
            while steps and steps[0] < stop:
                at = steps.pop(0)
                element.ramp(at, _level(cue, at), ramp)
            if spawn < end and spawn <= stop:
                element.ramp(spawn, 0.0, crossfade)
                element.to = spawn + crossfade
                element = _Element(cue["track"], index, "loop", spawn, bounds.loop_start, bounds)
                element.points = [(spawn, 0.0), (spawn + crossfade, _level(cue, spawn))]
                out.append(element)
                continue
            if final and natural <= end + _EPS:
                element.points = [point for point in element.points if point[0] < natural - _EPS] + [(natural, element.amplitude(natural))]
                element.to, ended = natural, element  # chơi tới E là hết: không mờ, phần sau E đã im
                break
            following = cues[index + 1] if index + 1 < len(cues) else None
            following = following if following is not None and abs(float(following["start"]) - end) < _EPS else None
            if following is not None and following["track"] == element.track:
                current = element
                break
            length = fade
            if following is not None and following.get("sibling"):
                length = max(_EPS, min(sibling_fade, last - element.at(end)))  # MIX_QA 3.5: hết phần còn lại thật của bài
            element.ramp(end, 0.0, length)
            element.to = end + length
            break
    return [element.shape() for element in out]


def _final_pass(element: _Element, period: float, end: float) -> float:
    """Lặp thường, mốc `tail`: hết vòng nào cách hết mốc dưới nửa vòng thì đó là vòng cuối (lô 1 `finalLoop`)."""
    natural = element.begin + (period - element.position)
    while math.isfinite(period) and end - natural >= period / 2:
        natural += period
    return natural
