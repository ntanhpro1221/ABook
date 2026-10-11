"""Bộ dựng nhạc nền NGOẠI TUYẾN cho xuất sách nói "Kèm nhạc nền" (MP3/M4B) - máy tính và điện thoại theo ĐÚNG file này.

Chép nguyên thuật toán từ bản tham chiếu của Music (LLM_Train/music/mixqa/music_render.py, MUSIC_RENDER.md); bản Kotlin port 1-1,
kiểm bằng fixture tests/fixtures/music_render (tham số tín hiệu + kỳ vọng). Hằng số (trần, đệm, nhìn trước, nhả, bảng FIR) đọc từ
assets/music_mix.json qua `music_mix.MIX` - không chép số. Nơi dùng: music_export.py. Chỉ numpy, mọi phép tính float64.

Hai bước, đều là hàm thuần:

1. `render_bus(timeline, n, rate, channels, pcm)` - bus nhạc từ dòng thời gian của `music_timeline` (lô 2): mỗi phần tử
   {track, from, to, position, gain [[giây, dB|None]], loop?}:
   - mẫu chương `k` trong [round(from*rate), min(round(to*rate), n)) đọc mẫu bài `round(position*rate) + (k - round(from*rate))`;
     `loop` (bài quá ngắn để mờ chéo) -> lấy theo modulo độ dài file; không `loop` mà quá cuối file -> 0;
   - biên độ tại t = k / rate: điểm gain đổi sang biên độ `10 ** (dB / 20)` (None -> 0), nội suy TUYẾN TÍNH THEO BIÊN ĐỘ dạng
     `a_j + slope_j * (t - t_j)`, `slope_j = (a_{j+1} - a_j) / (t_{j+1} - t_j)`, j = (số điểm có t_i <= t) - 1; trước điểm đầu = a đầu,
     từ điểm cuối trở đi = a cuối (như `_Element.amplitude` của music_mix.py và như trình phát trượt `volume`);
   - cộng các phần tử theo thứ tự trong `timeline`.
2. `guard(voice, bus, rate, mix)` - CHẶN ĐỈNH CHỈ TRÊN BUS NHẠC: ra `voice + g * bus`, `g` một đường chung mọi kênh, giọng không bị
   nhân với gì cả (PHONE_EXPORT_MIX.md mục 4):
   - trần `c = 10 ** ((exportCeilingDbtp - exportGuardHeadroomDb) / 20)`;
   - nội suy x4 (BS.1770-4 phụ lục 2: 4 pha x 12 hệ số `truePeakFir` trong music_mix.json): pha p tại n + p/4 =
     sum_{j=-5..6} fir[p][j+5] * x[n+j] (ngoài mảng = 0), cho cả giọng V và bus M;
   - tại mỗi điểm: `allowed = max(c, |V|)` (giọng một mình đã vượt trần thì nhạc chỉ không được làm tệ hơn),
     g_pt = clip((allowed - sign(M) * V) / |M|, 0, 1) khi |M| > 0, không thì 1; `need[n]` = min theo pha và kênh, CHỈ cho n trong
     [0, số mẫu chương) - ngoài đó need = 1 (giọng/bus ngoài chương coi là 0 khi nội suy);
   - phủ chân bộ lọc: need2[n] = min(need[n-6 .. n+6]);
   - nhìn trước L = round(attackMs/1000*rate): a[n] = min_{j=0..L} 1 - (1 - need2[n+j]) * (1 - j/L) (dốc thẳng, chạm đúng need tại
     đỉnh);
   - nhả R = round(releaseMs/1000*rate): g[n] = min(a[n], g[n-1] + 1/R), g[-1] = 1.
   App chạy theo khối bằng `GuardStream` (ra chậm L + 12 mẫu); kết quả từng bit như tính cả mảng, mọi cỡ khối.
3. `to_int16(x)` = clip(rint(x * 32768), -32768, 32767) - rint = chẵn gần nhất ở cả hai bên (numpy rint / Kotlin Math.rint).
Mọi `round(giây * rate)` cũng là chẵn gần nhất (Python round / Kotlin Math.rint, KHÔNG Math.round): 44,1 kHz x mốc mili giây có
thể rơi đúng .5 mẫu (5 ms = 220,5).
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from .music_mix import MIX

# Hằng số của bộ chặn trong music_mix.json: exportCeilingDbtp (trần đỉnh thật sau mã hoá), exportGuardHeadroomDb (đệm cho mức vọt
# của bộ mã hoá AAC/MP3 - AAC ffmpeg vọt tới +0,54 dB nên 0,75: trần trước mã hoá -1,75 dBTP), exportGuardAttackMs, exportGuardReleaseMs,
# truePeakFir (bảng `design_fir`).
FIR_TAPS, FIR_PHASES, FIR_LEFT = 12, 4, 5   # pha p dùng x[n-5 .. n+6]


def design_fir(cutoff: float = 1.0, beta: float = 7.0) -> list[list[float]]:
    """Hệ số nội suy x4 (chạy MỘT lần để sinh bảng `truePeakFir` cho music_mix.json; app chỉ ĐỌC bảng, không tính lại):
    sinc cửa sổ Kaiser liên tục trên [-6, 6], tần số cắt `cutoff` x Nyquist gốc, mỗi pha chuẩn hoá tổng = 1 (DC giữ nguyên).
    cutoff 1,0: sai so với resample_poly x16 trong [-0,03; 0] dB với sin 1-21 kHz ở 48 kHz (0,9 thì tới -4,2 dB ở 21 kHz)."""
    out = []
    for p in range(FIR_PHASES):
        t = np.arange(-FIR_LEFT, FIR_TAPS - FIR_LEFT, dtype=np.float64) - p / FIR_PHASES   # khoảng cách mẫu tới điểm n + p/4
        w = np.i0(beta * np.sqrt(np.clip(1 - (t / 6.0) ** 2, 0, None))) / np.i0(beta)
        h = cutoff * np.sinc(cutoff * t) * w
        out.append([0.0 if abs(v) < 1e-12 else float(f"{v:.12g}") for v in h / h.sum()])  # pha 0 = đúng mẫu gốc
    return out


def amplitude_curve(points: Sequence[Sequence[Any]], t: np.ndarray) -> np.ndarray:
    """Biên độ tuyến tính tại các giây `t` (mô tả ở docstring module, bước 1)."""
    if not points:
        return np.zeros_like(t)
    tp = np.array([float(p[0]) for p in points], dtype=np.float64)
    ap = np.array([0.0 if p[1] is None else 10.0 ** (float(p[1]) / 20.0) for p in points], dtype=np.float64)
    j = np.searchsorted(tp, t, side="right") - 1
    out = np.empty_like(t)
    before, after = j < 0, j >= len(tp) - 1
    out[before] = ap[0]
    out[after] = ap[-1]
    mid = ~(before | after)
    jm = j[mid]
    span = tp[jm + 1] - tp[jm]
    slope = np.where(span > 0, (ap[jm + 1] - ap[jm]) / np.where(span > 0, span, 1.0), 0.0)
    out[mid] = np.where(span > 0, ap[jm] + slope * (t[mid] - tp[jm]), ap[jm + 1])
    return out


def render_bus(timeline: Sequence[dict[str, Any]], n: int, rate: int, channels: int,
               pcm: Callable[[str], np.ndarray | None], start: int = 0) -> tuple[np.ndarray, list[str]]:
    """Bus nhạc (n, channels) float64. `pcm(track)` -> mảng (khung, channels) ĐÃ ở `rate`/`channels` của chương, hay None khi bài
    không lấy được (phần tử ấy im; trả kèm danh sách bài thiếu để báo "N đoạn thiếu nhạc"). `start`: dựng đoạn mẫu chương
    [start, start + n) - app dựng theo khối như GuardStream; ghép các khối = dựng một lần (test kiểm)."""
    bus = np.zeros((n, channels), dtype=np.float64)
    missing = []
    for element in timeline:
        data = pcm(element["track"])
        if data is None or not len(data):
            missing.append(element["track"])
            continue
        k0 = round(float(element["from"]) * rate)
        to = float(element["to"])
        k1 = start + n if not math.isfinite(to) else min(round(to * rate), start + n)
        lo = max(k0, start)
        if k1 <= lo:
            continue
        k = np.arange(lo, k1, dtype=np.int64)
        src = round(float(element["position"]) * rate) + (k - k0)
        if element.get("loop"):
            src = np.mod(src, len(data))
            take = np.ones(len(k), dtype=bool)
        else:
            take = (src >= 0) & (src < len(data))
        amp = amplitude_curve(element["gain"], k.astype(np.float64) / rate)
        sel = np.flatnonzero(take)
        bus[k[sel] - start] += data[src[sel]].astype(np.float64) * amp[sel, None]
    return bus, missing


def interpolate(x: np.ndarray, fir: Sequence[Sequence[float]]) -> list[np.ndarray]:
    """4 pha nội suy của x (n, kênh): pha p = giá trị tại n + p/4."""
    n = len(x)
    pad = np.zeros((n + FIR_TAPS, x.shape[1]), dtype=np.float64)
    pad[FIR_LEFT:FIR_LEFT + n] = x
    out = []
    for p in range(FIR_PHASES):
        y = np.zeros_like(x, dtype=np.float64)
        for j in range(FIR_TAPS):       # j tương ứng x[n + j - 5]; cộng theo j tăng dần (cố định thứ tự cho Kotlin)
            y += fir[p][j] * pad[j:j + n]
        out.append(y)
    return out


SUPPORT = FIR_TAPS // 2   # need2 = min need trong +-6 mẫu (chân bộ lọc)


class GuardStream:
    """Bộ chặn theo KHỐI (chương 30 phút 48 kHz = 86 triệu mẫu: không giữ cả mảng). `feed(giọng, bus)` từng khối (khung, kênh)
    trả phần ra đã chốt; `finish()` trả phần còn lại. Ra chậm `L + 12` mẫu so với vào (nhìn trước L + chân lọc hai lần).
    Kết quả KHÔNG phụ thuộc cỡ khối, từng bit như tính cả mảng một lần (test_music_render.py kiểm).
    `gains` (nếu `keep_gains`) = g của mọi mẫu đã ra - chỉ để báo/kiểm."""

    def __init__(self, rate: int, channels: int, mix: dict[str, Any] | None = None, keep_gains: bool = False) -> None:
        mix = MIX if mix is None else mix  # fixture mang bộ hằng số riêng; app dùng music_mix.json
        self.c = 10.0 ** ((float(mix["exportCeilingDbtp"]) - float(mix["exportGuardHeadroomDb"])) / 20.0)
        self.fir = mix["truePeakFir"]
        self.attack = max(1, round(float(mix["exportGuardAttackMs"]) / 1000.0 * rate))
        self.step = 1.0 / max(1, round(float(mix["exportGuardReleaseMs"]) / 1000.0 * rate))
        self.channels = channels
        self.voice = np.zeros((0, channels), dtype=np.float64)
        self.bus = np.zeros((0, channels), dtype=np.float64)
        self.base = 0      # chỉ số tuyệt đối của self.voice[0]
        self.done = 0      # chỉ số tuyệt đối của mẫu ra kế tiếp
        self.prev = 1.0    # g của mẫu ra trước (nhả)
        self.gains: list[np.ndarray] | None = [] if keep_gains else None

    def feed(self, voice: np.ndarray, bus: np.ndarray) -> np.ndarray:
        self.voice = np.concatenate([self.voice, np.asarray(voice, dtype=np.float64)])
        self.bus = np.concatenate([self.bus, np.asarray(bus, dtype=np.float64)])
        return self._emit(final=False)

    def finish(self) -> np.ndarray:
        return self._emit(final=True)

    def _x(self, data: np.ndarray, lo: int, hi: int) -> np.ndarray:
        """data theo chỉ số tuyệt đối [lo, hi), ngoài phần đang giữ = 0 (trước đầu chương / sau cuối chương)."""
        out = np.zeros((hi - lo, self.channels), dtype=np.float64)
        a, b = max(lo, self.base), min(hi, self.base + len(data))
        if b > a:
            out[a - lo:b - lo] = data[a - self.base:b - self.base]
        return out

    def _need(self, lo: int, hi: int) -> np.ndarray:
        """need[k], k trong [lo, hi): g lớn nhất ở điểm nội suy giữa k và k+1 để |V + g M| <= max(c, |V|)."""
        xv, xm = self._x(self.voice, lo - FIR_LEFT, hi + FIR_TAPS - FIR_LEFT - 1), self._x(self.bus, lo - FIR_LEFT, hi + FIR_TAPS - FIR_LEFT - 1)
        need = np.ones(hi - lo, dtype=np.float64)
        width = hi - lo
        for p in range(FIR_PHASES):
            V = np.zeros((width, self.channels), dtype=np.float64)
            M = np.zeros((width, self.channels), dtype=np.float64)
            for j in range(FIR_TAPS):    # x[k + j - 5]; cộng theo j tăng dần (cố định thứ tự cho Kotlin)
                V += self.fir[p][j] * xv[j:j + width]
                M += self.fir[p][j] * xm[j:j + width]
            allowed = np.maximum(self.c, np.abs(V))
            absm = np.abs(M)
            with np.errstate(divide="ignore", invalid="ignore"):
                g = np.where(absm > 0, np.clip((allowed - np.sign(M) * V) / np.where(absm > 0, absm, 1.0), 0.0, 1.0), 1.0)
            need = np.minimum(need, g.min(axis=1))
        return need

    def _emit(self, final: bool) -> np.ndarray:
        end = self.base + len(self.voice)
        a, b = self.done, end if final else end - (self.attack + 2 * SUPPORT)
        if b <= a:
            return np.zeros((0, self.channels), dtype=np.float64)
        # need trên [a - 6, b + L + 6): đủ cho need2 trên [a, b + L), đủ cho nhìn trước của [a, b)
        lo, hi = a - SUPPORT, b + self.attack + SUPPORT
        need = self._need(lo, hi)
        # need chỉ có nghĩa ở mẫu của chương [0, n): ngoài đó = 1 (như tính cả mảng; n chỉ biết khi `finish`)
        need[: max(0, -lo)] = 1.0
        if final:
            need[max(0, end - lo):] = 1.0
        width = b + self.attack - a
        need2 = np.ones(width, dtype=np.float64)
        for k in np.flatnonzero(need < 1.0):
            kk = k + lo                                             # tuyệt đối
            s, e = max(a, kk - SUPPORT), min(b + self.attack, kk + SUPPORT + 1)
            if e > s:
                need2[s - a:e - a] = np.minimum(need2[s - a:e - a], need[k])
        attack_env = np.ones(b - a, dtype=np.float64)
        for k in np.flatnonzero(need2 < 1.0):                       # k tương đối với a
            s = max(0, k - self.attack)
            if s >= b - a:
                continue
            e = min(k + 1, b - a)
            j = k - np.arange(s, e)                                 # j = k - m >= 0
            ramp = 1.0 - (1.0 - need2[k]) * (1.0 - j / self.attack)
            attack_env[s:e] = np.minimum(attack_env[s:e], ramp)
        g = np.ones(b - a, dtype=np.float64)
        prev = self.prev
        active = np.flatnonzero(attack_env < 1.0)
        k = 0
        while k < b - a:
            if prev >= 1.0:                                         # đang không hạ: nhảy tới mẫu bị hạ kế
                i = int(np.searchsorted(active, k))
                if i >= len(active):
                    break
                k = int(active[i])
            prev = min(attack_env[k], prev + self.step)             # nhả: g[n] = min(a[n], g[n-1] + 1/R)
            g[k] = prev
            k += 1
        self.prev = prev if k >= b - a else 1.0
        out = self._x(self.voice, a, b) + g[:, None] * self._x(self.bus, a, b)
        if self.gains is not None:
            self.gains.append(g)
        self.done = b
        keep = max(self.base, b - (FIR_TAPS + SUPPORT))             # giữ đủ quá khứ cho nội suy + need2 của khối sau
        self.voice, self.bus = self.voice[keep - self.base:], self.bus[keep - self.base:]
        self.base = keep
        return out


def guard(voice: np.ndarray, bus: np.ndarray, rate: int, mix: dict[str, Any] | None = None, block: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(ra = voice + g * bus, g) cho cả chương - chạy GuardStream một khối (hay từng khối `block` mẫu)."""
    stream = GuardStream(rate, voice.shape[1], mix, keep_gains=True)
    step = block or max(1, len(voice))
    parts = [stream.feed(voice[i:i + step], bus[i:i + step]) for i in range(0, len(voice), step)] + [stream.finish()]
    return np.concatenate(parts), np.concatenate(stream.gains) if stream.gains else np.ones(0)


def to_int16(x: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(x * 32768.0), -32768, 32767).astype(np.int16)


def true_peak_db(x: np.ndarray, fir: Sequence[Sequence[float]]) -> float:
    """Đỉnh thật theo đúng nội suy của bộ chặn (để báo; đo độc lập thì dùng bộ đo khác, xem render_check.py)."""
    best = float(np.abs(x).max()) if len(x) else 0.0
    for y in interpolate(x, fir):
        best = max(best, float(np.abs(y).max()))
    return 20 * math.log10(best) if best > 0 else -math.inf


def guard_stats(g: np.ndarray, rate: int) -> dict[str, Any]:
    below = g < 1.0
    edges = np.diff(np.concatenate([[0], below.astype(np.int8), [0]]))
    starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    return {"spans": len(starts), "ms": round(float(below.sum()) * 1000.0 / rate, 1),
            "maxSpanMs": round(float((ends - starts).max()) * 1000.0 / rate, 1) if len(starts) else 0.0,
            "minGainDb": round(20 * math.log10(float(g.min())), 2) if g.min() > 0 else None}
