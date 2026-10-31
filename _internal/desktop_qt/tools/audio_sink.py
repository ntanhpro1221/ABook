"""Tai kiểm tiếng của app máy tính (ABOOK_AUDIO_SINK).

App chạy trên bàn làm việc ẩn, bộ trộn ghi đúng những khung đáng lẽ ra WASAPI vào WAV theo nhịp đồng hồ thật. Kịch bản bench
"audio" (qml/BenchScenario.qml) phát cuốn thử có nhạc: phát, dừng, tua, đổi nhạc giữa chương (mờ chéo), hạ / nâng mức nhạc,
bốn tốc độ, tua xa, lùi, hết chương tự sang chương sau, bấm chương sau. Rồi soi file:

  lỗ      chu kỳ engine kéo mà thiếu dữ liệu / luồng đang dừng (.gaps/.stops), chuỗi số 0 tuyệt đối, giọng mất hẳn so với nguồn
  tách    bậc nhảy mẫu-mẫu (sai phân bậc hai vượt xa nền quanh nó) mà nguồn ở cùng chỗ không có
  trôi    vị trí app báo so với đồng hồ (sai số tích luỹ từng đoạn) và tiếng nghe thấy so với vị trí app báo (khớp dạng sóng)
  mức     tiếng ra so với nguồn ở cùng đoạn nội dung, theo từng tốc độ
  rò      còn tiếng sau lúc dừng
  đột im  đang có tiếng mà tắt phụt (> -45 dB xuống < -70 dB trong 20 ms) không do thao tác nào, ở chỗ nguồn không tự tắt
          (01-11: hết chương tự sang chương sau, nhạc dừng cùng giọng - 0.4.152 rơi -30 -> -91 dB trong 6 ms)

  python -X utf8 tools/audio_sink.py run <label> [--exe dist/ABookDesk.exe]
  python -X utf8 tools/audio_sink.py analyze <thư_mục_lượt>
  python -X utf8 tools/audio_sink.py selftest      (build.bat: bộ dò bắt được lỗi cấy vào và im với tiếng sạch)
  python -X utf8 tools/audio_sink.py strength <thư_mục_lượt>   (lượt xanh, lỗi cấy vào chính nó đỏ)
  python -X utf8 tools/audio_sink.py gate <exe> [--runs 2]     (build.bat package / installer: cổng phát hành)

Bằng chứng (WAV, đoạn trích quanh chỗ nghi) nằm trong build/audiosink-evidence/<label>/ - không bao giờ commit.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/audiosink-evidence"
RATE = 48000
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

# Ngưỡng
SETTLE_S = 0.6          # sau một thao tác, chờ chừng này mới coi là phát ổn định (đo trôi / mức)
ZERO_RUN_S = 0.002      # chuỗi số 0 tuyệt đối dài hơn thế giữa lúc phát = lỗ
CLICK_RATIO = 14.0      # |sai phân bậc hai| gấp chừng này nền RMS quanh nó (bỏ chính nó) ...
CLICK_FLOOR = 0.02      # ... và lớn hơn chừng này (đỉnh 1,0) mới là tiếng tách
CLICK_FLOOR_SONIC = 0.03  # ... ở đoạn tốc độ khác 1 (Sonic chạy) thì chừng này: chỗ nối mờ chéo của Sonic tự làm gãy độ dốc
                          # tới 0,0205 ở nơi nguồn chỉ 0,005 (01-11 lượt 5, 93,446 s; Sonic offline cùng mã: 0,011 nơi nguồn 0,004)
DROPOUT_DB = 30.0       # tiếng ra thấp hơn nguồn chừng này dB trong 20 ms khi nguồn có tiếng = giọng mất
LEVEL_TOL_DB = 1.0      # mức ở mỗi tốc độ lệch mức ở tốc độ 1 quá chừng này = lỗi
# Trôi vị trí: vị trí app báo = con trỏ nghe của bộ trộn = khung đã ra theo padding của thiết bị, mà padding chỉ đổi theo
# chu kỳ engine (10 ms). Nên vị trí luôn trễ sự thật 0..1 chu kỳ, pha đổi chậm theo nhịp thức của luồng trộn: răng cưa ≤ 10 ms
# (đo 01-11, 5 lượt x 15 đoạn: tối đa 10,8 ms, tiếng ra vẫn đúng đồng hồ). Đoạn 4,5 s vì thế có dốc giả tới 0,24 %.
# Trôi thật thì cộng dồn: sai số tích luỹ trong đoạn (thời gian người nghe) vượt chừng này mới là trôi.
DRIFT_MS = 15.0
CLICK_SOURCE_S = 0.05   # tiếng tách mà nguồn cũng có trong chừng này giây NGƯỜI NGHE quanh vị trí báo thì là của nguồn
CLICK_COPY = 0.5        # ... tức nguồn trong cửa sổ ấy có gai (|sai phân bậc hai|) ít nhất bằng chừng này lần gai tiếng ra
OFFSET_SPREAD_MS = 30.0 # tiếng nghe thấy lệch vị trí app báo: dao động quá chừng này trong một đoạn = trôi / giật
LEAK_PEAK = 1e-3        # sau lúc dừng 60 ms còn đỉnh lớn hơn thế = rò
TREND_TOL_MS = 10.0     # tiếng nghe thấy trôi khỏi vị trí app báo quá 10 ms (thời gian người nghe) mỗi 10 s
TREND_SPAN_S = 10.0     # ... chỉ đo trên đoạn dài ít nhất chừng này (đoạn ngắn: Sonic + vùng nắn ±50 ms làm dốc giả)
OFFSET_MEDIAN_MS = 40.0 # tiếng nghe thấy đi trước / sau vị trí app báo quá chừng này = đọc-theo lệch thấy được (tua mất khối: 171)
MATCH_SCORE = 0.9      # khớp dạng sóng dưới mức này là khớp nhầm chu kỳ cao độ khác, bỏ
DROPOUT_SLACK_S = 0.06  # mất giọng: so với chỗ nguồn im nhất trong ±chừng này (giây người nghe) quanh vị trí báo
CUT_FROM_DB = -45.0     # đột im: bao 5 ms đang trên mức này (nhạc dưới giọng ở cuốn thử ~ -36 dB) ...
CUT_TO_DB = -70.0       # ... rồi trong CUT_WITHIN_S xuống dưới mức này
CUT_WITHIN_S = 0.02
CUT_ACTION_S = 0.5      # sau một thao tác (dừng, tua, sang chương, đổi tốc độ...) chừng này giây thì im phụt là do người dùng


# ---------- đọc ----------

def read_wav(path):
    raw = Path(path).read_bytes()
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError(f"{path}: không phải WAV")
    fmt = int.from_bytes(raw[20:22], "little")
    channels = int.from_bytes(raw[22:24], "little")
    rate = int.from_bytes(raw[24:28], "little")
    bits = int.from_bytes(raw[34:36], "little")
    data = raw[44:]
    if fmt == 3 and bits == 32:
        x = np.frombuffer(data[: len(data) // (4 * channels) * 4 * channels], dtype="<f4")
    elif fmt == 1 and bits == 16:
        x = np.frombuffer(data[: len(data) // (2 * channels) * 2 * channels], dtype="<i2").astype(np.float32) / 32768
    else:
        raise ValueError(f"{path}: định dạng {fmt}/{bits} chưa hỗ trợ")
    return x.reshape(-1, channels), rate


def write_wav16(path, mono, rate):
    pcm = (np.clip(mono, -1, 1) * 32767).astype("<i2").tobytes()
    head = b"RIFF" + (36 + len(pcm)).to_bytes(4, "little") + b"WAVEfmt " + (16).to_bytes(4, "little")
    head += (1).to_bytes(2, "little") + (1).to_bytes(2, "little") + rate.to_bytes(4, "little") + (rate * 2).to_bytes(4, "little")
    head += (2).to_bytes(2, "little") + (16).to_bytes(2, "little") + b"data" + len(pcm).to_bytes(4, "little")
    Path(path).write_bytes(head + pcm)


def decode(path, rate=RATE):
    """Nguồn chương -> mono float32 ở `rate` (ffmpeg)."""
    out = subprocess.run([FFMPEG, "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(rate), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype="<f4").copy()


def read_pairs(path):
    p = Path(path)
    if not p.exists():
        return []
    return [tuple(int(v) for v in line.split()) for line in p.read_text().splitlines() if line.strip()]


# ---------- bộ dò (thuần số, selftest dùng chung) ----------

def zero_runs(mono, min_len):
    """[(đầu, dài)] các chuỗi số 0 tuyệt đối dài >= min_len."""
    z = np.concatenate(([False], mono == 0.0, [False]))
    edges = np.flatnonzero(np.diff(z.astype(np.int8)))
    starts, ends = edges[::2], edges[1::2]
    keep = (ends - starts) >= min_len
    return list(zip(starts[keep].tolist(), (ends - starts)[keep].tolist()))


def clicks(mono, rate, ratio=CLICK_RATIO, floor=CLICK_FLOOR):
    """Chỗ có bậc nhảy: |sai phân bậc hai| vượt `ratio` lần RMS của nó trong 5 ms hai bên (bỏ 0,25 ms giữa)."""
    d = np.zeros_like(mono)
    d[2:] = mono[2:] - 2 * mono[1:-1] + mono[:-2]
    e = d.astype(np.float64) ** 2
    c = np.concatenate(([0.0], np.cumsum(e)))
    w, g = int(rate * 0.005), max(2, int(rate * 0.00025))
    n = len(d)
    i = np.arange(n)
    lo_a, lo_b = np.clip(i - w, 0, n), np.clip(i - g, 0, n)
    hi_a, hi_b = np.clip(i + g + 1, 0, n), np.clip(i + w + 1, 0, n)
    energy = (c[lo_b] - c[lo_a]) + (c[hi_b] - c[hi_a])
    count = np.maximum((lo_b - lo_a) + (hi_b - hi_a), 1)
    bed = np.sqrt(energy / count)
    hit = (np.abs(d) > floor) & (np.abs(d) > ratio * np.maximum(bed, 1e-6))
    out, last = [], -rate
    for k in np.flatnonzero(hit).tolist():
        if k - last > rate * 0.01:
            out.append(k)
        last = k
    return out


def rms_db(x):
    return 10 * np.log10(np.mean(np.asarray(x, dtype=np.float64) ** 2) + 1e-20)


def frame_db(mono, hop):
    n = len(mono) // hop
    v = mono[: n * hop].astype(np.float64).reshape(n, hop)
    return 10 * np.log10(np.mean(v * v, axis=1) + 1e-20)


def match_offset(sink, source, at_sink, at_source, rate, win_s=0.04, search_s=0.25):
    """Tìm chỗ trong nguồn (quanh at_source, ±search_s) giống nhất cửa sổ win_s của tiếng ra tại at_sink.
    Trả (lệch_giây, tương_quan) - lệch dương: tiếng nghe thấy đi trước vị trí dự kiến."""
    w, s = int(win_s * rate), int(search_s * rate)
    a = sink[at_sink: at_sink + w].astype(np.float64)
    lo = at_source - s
    if at_sink < 0 or at_sink + w > len(sink) or lo < 0 or at_source + s + w > len(source):
        return None, 0.0
    b = source[lo: at_source + s + w].astype(np.float64)
    a = a - a.mean()
    na = np.sqrt((a * a).sum())
    if na < 1e-4:
        return None, 0.0
    n = len(b) + w
    size = 1 << (n - 1).bit_length()
    corr = np.fft.irfft(np.fft.rfft(b, size) * np.conj(np.fft.rfft(a, size)), size)[: len(b) - w + 1]
    c = np.concatenate(([0.0], np.cumsum(b)))
    c2 = np.concatenate(([0.0], np.cumsum(b * b)))
    seg_sum = c[w:] - c[:-w]
    seg_e = (c2[w:] - c2[:-w]) - seg_sum * seg_sum / w
    score = corr / (na * np.sqrt(np.maximum(seg_e, 1e-12)))
    k = int(np.argmax(score))
    return (k - s) / rate, float(score[k])


# ---------- phân tích một lượt ----------

def parse_marks(events, epoch_ms, rate):
    marks = []
    for t, name in events:
        if not name.startswith("audio:"):
            continue
        tag, chapter, position, playing = name[len("audio:"):].rsplit(":", 3)
        marks.append(dict(tag=tag, ms=t, frame=int(round((t - epoch_ms) * rate / 1000)), chapter=int(chapter),
                          position=float(position), playing=int(playing)))
    return marks


def load(run_dir, source_path=None):
    """Một lượt trên đĩa -> dữ liệu cho check(): tiếng ra (mono), mốc bench, lỗ thiết bị thấy, nguồn chương."""
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "run.json").read_bytes()) if (run_dir / "run.json").exists() else {}
    sink_path = run_dir / "sink.wav"
    x, rate = read_wav(sink_path)
    epoch_ms, clock_rate = Path(str(sink_path) + ".clock").read_text().split()
    assert int(clock_rate) == rate
    bench = json.loads((run_dir / "bench.json").read_bytes())
    return dict(sink=str(sink_path), rate=rate, mono=x.mean(axis=1), marks=parse_marks(bench["events"], float(epoch_ms), rate),
                gaps=read_pairs(str(sink_path) + ".gaps"), stops=read_pairs(str(sink_path) + ".stops"),
                source=decode(source_path or meta["source"], rate))


def analyze(run_dir, source_path=None):
    run_dir = Path(run_dir)
    report = check(load(run_dir, source_path), run_dir / "snippets")
    (run_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    return report


def check(data, snippets=None):
    """Soi một lượt đã nạp. snippets: thư mục ghi đoạn trích quanh chỗ nghi (None = không ghi, như khi kiểm lực)."""
    rate, mono, source, marks = data["rate"], data["mono"], data["source"], data["marks"]
    events = [m for m in marks if m["tag"] != "tick"]
    ticks = [m for m in marks if m["tag"] == "tick"]
    if snippets is not None:
        snippets.mkdir(exist_ok=True)
    findings = []

    def snip(kind, frame, note):
        name = f"{kind}_{frame / rate:08.3f}s.wav"
        if snippets is not None:
            a, b = max(0, frame - rate // 2), min(len(mono), frame + rate // 2)
            write_wav16(snippets / name, mono[a:b], rate)
        findings.append(dict(kind=kind, t=round(frame / rate, 3), note=note, snippet=name))

    # Khoảng phải có tiếng: từ "play" (+ khởi động) tới "stop", bỏ [pause, resume]; khoảng phải im: [pause, resume], [stop, ...]
    by_tag = {}
    for m in events:
        by_tag.setdefault(m["tag"], m)
    start = next((t["frame"] for t in ticks if t["playing"] and t["frame"] > by_tag["play"]["frame"]), by_tag["play"]["frame"])
    sound = [(start, by_tag["pause"]["frame"]), (by_tag["resume"]["frame"] + int(0.3 * rate), by_tag["stop"]["frame"])]
    quiet = [(by_tag["pause"]["frame"] + int(0.06 * rate), by_tag["resume"]["frame"]),
             (by_tag["stop"]["frame"] + int(0.06 * rate), len(mono))]

    def in_sound(f):
        return any(a <= f < b for a, b in sound)

    # Vị trí nội dung (giây nguồn) theo khung tiếng ra: nội suy giữa hai tick liền nhau cùng chương, đang phát, không thao tác xen giữa.
    def steady(a, b):
        return (a["playing"] and b["playing"] and a["chapter"] == b["chapter"] and 0 < b["frame"] - a["frame"] < rate
                and not any(a["frame"] - SETTLE_S * rate < e["frame"] <= b["frame"] for e in events))
    pairs = [(a, b) for a, b in zip(ticks, ticks[1:]) if steady(a, b)]

    def pair_at(f):
        return next(((a, b) for a, b in pairs if a["frame"] <= f <= b["frame"]), None)

    def position_at(f):
        ab = pair_at(f)
        if ab is None:
            return None
        a, b = ab
        return a["position"] + (b["position"] - a["position"]) * (f - a["frame"]) / (b["frame"] - a["frame"])

    # 1. Lỗ do thiết bị thấy: engine kéo mà thiếu / luồng đang dừng
    for kind, found in (("hole_gap", data["gaps"]), ("hole_stop", data["stops"])):
        for at, n in found:
            if in_sound(at) or in_sound(at + n - 1):
                snip(kind, at, f"{n} khung ({n * 1000 / rate:.1f} ms)")
    # 2. Chuỗi số 0 giữa lúc phát, trừ chỗ nguồn cũng im tuyệt đối (giữa hai câu TTS, nhạc chưa vào)
    def source_near(f):
        p = position_at(f)
        if p is None:
            near = min(pairs, key=lambda ab: min(abs(ab[0]["frame"] - f), abs(ab[1]["frame"] - f)), default=None)
            if near is None or min(abs(near[0]["frame"] - f), abs(near[1]["frame"] - f)) > rate:
                return None
            a, b = near
            speed = (b["position"] - a["position"]) * rate / (b["frame"] - a["frame"])
            p = a["position"] + (f - a["frame"]) / rate * speed
        j = int(p * rate)
        return source[max(0, j - rate // 20): j + rate // 20]
    for at, n in zero_runs(mono, int(ZERO_RUN_S * rate)):
        if not in_sound(at):
            continue
        near = source_near(at + n // 2)
        if near is not None and len(near) and rms_db(near) < -60:
            continue
        snip("hole_zero", at, f"{n} khung số 0 ({n * 1000 / rate:.1f} ms)")
    # 3. Giọng mất hẳn so với nguồn (20 ms), chỉ ở đoạn phát ổn định
    # Vị trí báo lệch tiếng thật vài chục ms (Sonic, vùng nắn trôi): chỉ là mất giọng khi cả lân cận nguồn đều có tiếng.
    hop = int(0.02 * rate)
    sink_db = frame_db(mono, hop)
    source_db = frame_db(source, hop)
    for a, b in pairs:
        speed = max(0.5, (b["position"] - a["position"]) * rate / (b["frame"] - a["frame"]))
        for k in range(a["frame"] // hop + 1, b["frame"] // hop):
            p = position_at(k * hop)
            if p is None:
                continue
            lo = int((p - DROPOUT_SLACK_S * speed) * rate) // hop
            hi = int((p + (0.02 + DROPOUT_SLACK_S) * speed) * rate) // hop + 1
            if lo < 0 or hi > len(source_db):
                continue
            src = float(source_db[lo:hi].min())
            if src > -40 and sink_db[k] < src - DROPOUT_DB:
                snip("dropout", k * hop, f"ra {sink_db[k]:.1f} dB, nguồn {src:.1f} dB")
    # 4. Tiếng tách: có ở tiếng ra mà nguồn cùng chỗ không có
    # Dung sai tính theo thời gian người nghe: ở x3 tiếng nghe lệch vị trí báo ~22 ms = ~66 ms nguồn, nên tiếng bật phụ âm
    # của bản ghi (Sonic chép nguyên chu kỳ chứa nó) nằm ngoài 0,05 s nguồn (01-11: 103,85 s, 4/5 lượt).
    # "Nguồn cũng có" so độ nhọn tuyệt đối, không so tỉ số với nền: Sonic chép gai của nguồn nhưng bỏ bớt chu kỳ quanh nó, nên
    # gai dưới tỉ số 14 ở nguồn thành trên 14 ở tiếng ra (Sonic offline, 6000 s nghe ở 0,75-3x: mọi gai vượt sàn đều như thế).
    # Ở đoạn Sonic chạy, gãy độ dốc do chính chỗ nối của nó (tới CLICK_FLOOR_SONIC) cũng không phải tiếng tách.
    source_d2 = np.zeros_like(source)
    source_d2[2:] = np.abs(source[2:] - 2 * source[1:-1] + source[:-2])
    excused = []
    for f in clicks(mono, rate):
        if not in_sound(f):
            continue
        ab = pair_at(f)
        if ab is not None:
            a, b = ab
            pace = (b["position"] - a["position"]) * rate / (b["frame"] - a["frame"])
            speed = max(1.0, pace)
            kink = abs(float(mono[f] - 2 * mono[f - 1] + mono[f - 2]))
            if abs(pace - 1) > 0.01 and kink <= CLICK_FLOOR_SONIC:
                excused.append(dict(t=round(f / rate, 3), sonic=round(kink, 4)))
                continue
            p, w = int(position_at(f) * rate), int(CLICK_SOURCE_S * speed * rate)
            lo, hi = max(0, p - w), max(0, p + w)
            if hi > lo and lo < len(source_d2) and float(source_d2[lo:hi].max()) >= CLICK_COPY * kink:
                excused.append(dict(t=round(f / rate, 3), source=round((lo + int(np.argmax(source_d2[lo:hi]))) / rate, 3)))
                continue
        snip("click", f, "")
    # 4b. Đột im: tiếng ra tắt phụt giữa lúc phát mà không do thao tác nào. Nguồn giọng tự tắt phụt ở cùng chỗ (TTS cắt cứng
    # cuối câu, khi không có nhạc) thì là của nguồn. Không suy được vị trí (xa mọi tick hơn 1 s) thì không tha.
    cut_hop = int(0.005 * rate)
    cut_db, source_cut_db = frame_db(mono, cut_hop), frame_db(source, cut_hop)
    reach = int(CUT_WITHIN_S * rate) // cut_hop
    actions = [e["frame"] for e in events]
    last_cut = -rate
    for k in np.flatnonzero(cut_db[:-reach] > CUT_FROM_DB).tolist():
        f = k * cut_hop
        if f - last_cut < CUT_ACTION_S * rate or cut_db[k + 1: k + 1 + reach].min() >= CUT_TO_DB or not in_sound(f):
            continue
        if any(a - (reach + 1) * cut_hop <= f <= a + CUT_ACTION_S * rate for a in actions):  # khung đứng trước chỗ rơi: sớm hơn thao tác tới 20 ms
            continue
        near = min(pairs, key=lambda ab: min(abs(ab[0]["frame"] - f), abs(ab[1]["frame"] - f)), default=None)
        if near is not None and min(abs(near[0]["frame"] - f), abs(near[1]["frame"] - f)) <= rate:
            a, b = near
            pace = max(0.5, (b["position"] - a["position"]) * rate / (b["frame"] - a["frame"]))
            j = int((a["position"] + (f - a["frame"]) / rate * pace) * rate) // cut_hop
            w = int((DROPOUT_SLACK_S * pace) * rate) // cut_hop + reach
            if 0 <= j - w and j + w < len(source_cut_db) and source_cut_db[j - w: j + 1].max() > CUT_FROM_DB and source_cut_db[j: j + w + 1].min() < CUT_TO_DB:
                continue
        last_cut = f
        f = (k + 1 + int(np.argmax(cut_db[k + 1: k + 1 + reach] < CUT_TO_DB))) * cut_hop  # báo đúng khung đã im
        snip("cut", f, f"{cut_db[k]:.1f} dB -> {cut_db[k + 1: k + 1 + reach].min():.1f} dB trong {CUT_WITHIN_S * 1000:.0f} ms, không thao tác nào")
    # 5. Rò tiếng lúc phải im
    for a, b in quiet:
        if b - a > 0:
            peak = float(np.max(np.abs(mono[a:b]))) if b > a else 0.0
            if peak > LEAK_PEAK:
                f = a + int(np.argmax(np.abs(mono[a:b])))
                snip("leak", f, f"đỉnh {peak:.4f}")

    # Đoạn theo thao tác: từ thao tác này tới thao tác kế
    segments = []
    for e, nxt in zip(events, events[1:]):
        inside = [t for t in ticks if e["frame"] + SETTLE_S * rate <= t["frame"] < nxt["frame"] and t["playing"]]
        if len(inside) >= 8 and len({t["chapter"] for t in inside}) == 1:
            segments.append(dict(tag=e["tag"], ticks=inside, frames=(inside[0]["frame"], inside[-1]["frame"])))
    rate_of = {}
    current = 1.0
    for e in events:
        if e["tag"].startswith("rate:"):
            current = float(e["tag"].split(":")[1])
        rate_of[e["tag"]] = current

    # 6. Trôi vị trí: sai số tích luỹ của vị trí báo so với đồng hồ tiếng ra x tốc độ đặt, trong từng đoạn (DRIFT_MS)
    drift = []
    for s in segments:
        t = np.array([m["frame"] for m in s["ticks"]], dtype=np.float64) / rate
        p = np.array([m["position"] for m in s["ticks"]])
        speed = rate_of[s["tag"]]
        slope = float(np.polyfit(t, p, 1)[0])
        lag = p / speed - t
        spread = float(lag.max() - lag.min()) * 1000
        drift.append(dict(segment=s["tag"], speed=speed, slope=round(slope, 5), error=round(slope / speed - 1, 5), spread_ms=round(spread, 1)))
        if spread > DRIFT_MS:
            snip("drift", s["frames"][0], f"{s['tag']}: vị trí lệch đồng hồ tích luỹ {spread:.1f} ms (dốc {slope:.4f} giây/giây, tốc độ {speed})")
    # 7. Tiếng nghe thấy so với vị trí app báo: khớp dạng sóng với nguồn ở từng tick
    # Sonic chép nguyên từng chu kỳ cao độ: ở tốc độ cao cửa sổ ngắn lại (~2 chu kỳ) mới khớp được một đoạn nguồn liền.
    # Lệch đổi về thời gian người nghe (giây nguồn / tốc độ).
    offsets = []
    for s in segments:
        got, speed = [], rate_of[s["tag"]]
        for m in s["ticks"]:
            off, score = match_offset(mono, source, m["frame"], int(round(m["position"] * rate)), rate, win_s=max(0.012, 0.04 / speed))
            if off is not None and score > MATCH_SCORE:
                got.append((m["frame"] / rate, off * 1000 / speed))
        if len(got) >= 5:
            t, g = np.array(got).T
            trend = float(np.polyfit(t, g, 1)[0]) * 10 if t[-1] - t[0] >= TREND_SPAN_S else None
            offsets.append(dict(segment=s["tag"], speed=speed, matched=len(got), of=len(s["ticks"]),
                                median_ms=round(float(np.median(g)), 1), spread_ms=round(float(np.percentile(g, 95) - np.percentile(g, 5)), 1),
                                trend_ms_per_10s=None if trend is None else round(trend, 1)))
            if trend is not None and abs(trend) > TREND_TOL_MS:
                snip("drift_audio", s["frames"][0], f"{s['tag']}: tiếng nghe thấy trôi {trend:+.1f} ms mỗi 10 s so với vị trí app báo")
            if abs(offsets[-1]["median_ms"]) > OFFSET_MEDIAN_MS:
                snip("offset", s["frames"][0], f"{s['tag']}: tiếng nghe thấy lệch vị trí app báo {offsets[-1]['median_ms']:+.1f} ms")
            if offsets[-1]["spread_ms"] > OFFSET_SPREAD_MS:
                snip("offset", s["frames"][0], f"{s['tag']}: lệch tiếng/vị trí dao động {offsets[-1]['spread_ms']} ms")
    # 8. Mức theo tốc độ: tiếng ra so với nguồn cùng đoạn nội dung
    levels = []
    for s in segments:
        a, b = s["frames"]
        p0, p1 = s["ticks"][0]["position"], s["ticks"][-1]["position"]
        if p1 - p0 < 2:
            continue
        gain = rms_db(mono[a:b]) - rms_db(source[int(p0 * rate): int(p1 * rate)])
        levels.append(dict(segment=s["tag"], speed=rate_of[s["tag"]], gain_db=round(gain, 2)))
    ref = [l["gain_db"] for l in levels if l["speed"] == 1.0]
    if ref:
        base = float(np.median(ref))
        for l in levels:
            l["vs_speed1_db"] = round(l["gain_db"] - base, 2)
            if abs(l["vs_speed1_db"]) > LEVEL_TOL_DB:
                findings.append(dict(kind="level", t=None, note=f"{l['segment']}: {l['vs_speed1_db']:+.2f} dB so với tốc độ 1"))

    counts = {}
    for f in findings:
        counts[f["kind"]] = counts.get(f["kind"], 0) + 1
    return dict(sink=data["sink"], seconds=round(len(mono) / rate, 2), events=[(e["tag"], round(e["frame"] / rate, 3), e["chapter"], e["position"]) for e in events],
                counts=counts, findings=findings, excused=excused, drift=drift, offsets=offsets, levels=levels, segments=[(s["tag"], s["frames"]) for s in segments],
                ok=not findings)


# ---------- chạy app ----------

def prepare(stage):
    """Bản sao riêng của cuốn thử (chương = book2/001.mp3, 750,96 s); chương 1 đổi nhạc ở giây 30 để có mờ chéo."""
    import idle_ab
    idle_ab.OUT = stage
    fixture = idle_ab.prepare_fixture()
    for path in (fixture / "library").rglob("book.json"):
        data = json.loads(path.read_bytes())
        if data.get("title") != "Chuyện Thử Nghe":
            continue
        music = data["music"]
        first = next(iter(music["tracks"]))
        second = next((f"music/{p.name}" for p in (path.parent / "music").iterdir() if f"music/{p.name}" != first), None)
        if second is None:
            raise RuntimeError("cuốn thử thiếu bản nhạc thứ hai")
        music["tracks"].setdefault(second, dict(music["tracks"][first], title="Nhạc thử thứ hai"))
        end = data["chapters"][0]["duration"]
        music["chapters"]["1"] = [dict(track=first, start=0, end=30), dict(track=second, start=30, end=end)]
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8", newline="\n")
    return fixture


def run(label, exe):
    import measure
    from measure_mini import reset
    stage = OUT / label
    if (stage / "report.json").exists():
        raise SystemExit(f"{stage} đã có kết quả; chọn nhãn khác")
    stage.mkdir(parents=True, exist_ok=True)
    fixture = prepare(stage)
    books = json.loads((fixture / "audio_books.json").read_bytes())
    source = json.loads((stage / "chapter-input.json").read_bytes())["source"]
    qt = Path("D:/Novels/native_desk_proto/qt611/6.10.3/msvc2022_64")
    local = stage / "local"
    local.mkdir(exist_ok=True)
    sink = stage / "sink.wav"
    env = dict(ABOOK_PREFERENCES=str(fixture / "prefs.json"), ABOOK_HOST_PYTHON="D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe",
               ABOOK_HOST_APP=str(ROOT.parent), ABOOK_BENCH_SCENARIO="audio", ABOOK_BENCH_BOOK=books["a"], ABOOK_AUDIO_SINK=str(sink),
               ABOOK_SMTC="1", LOCALAPPDATA=str(local), QT_SCALE_FACTOR="1", QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
               ABOOK_BENCH_HIDDEN_DESKTOP="1", QT_QPA_FONTDIR=str(ROOT / "fonts"), QT_QPA_PLATFORM_PLUGIN_PATH=str(qt / "plugins/platforms"),
               PATH=str(qt / "bin") + os.pathsep + os.environ["PATH"])
    reset(fixture)
    (fixture / "listening.json.journal").write_bytes(b"")
    got = measure.launch(Path(exe).resolve(), env, True, timeout_seconds=260, require_ac=False)
    if got.get("app_log"):
        shutil.copyfile(got["app_log"], stage / "app.log")
    if not got.get("ok"):
        (stage / "run.json").write_text(json.dumps(dict(ok=False, why=got.get("why")), ensure_ascii=False), encoding="utf-8")
        raise SystemExit(f"app không chạy xong: {got.get('why')}")
    (stage / "bench.json").write_text(json.dumps(got["d"]), encoding="utf-8")
    (stage / "run.json").write_text(json.dumps(dict(ok=True, exe=str(exe), source=source, exit_code=got.get("exit_code"),
                                                    forced=got.get("forced_termination")), ensure_ascii=False), encoding="utf-8")
    return analyze(stage)


# ---------- kiểm lực trên lượt thật: lỗi cấy vào chính lượt ấy phải đỏ ----------

STRENGTH_DRIFTS = (0.003, -0.003, 0.005, -0.005)
STRENGTH_STEP = 0.05
STRENGTH_CUT_S = 0.3


def strength(data, base=None):
    """Lượt phải xanh, và từng lỗi cấy vào nó phải đỏ đúng loại, đúng chỗ:
    - trôi ±0,3 % / ±0,5 % từ giữa đoạn: ở mọi đoạn mà phần cấy (thời gian người nghe) vượt DRIFT_MS + răng cưa sạch của
      chính đoạn ấy, tức là chắc chắn phải thấy; phải có ít nhất một đoạn như thế;
    - bậc 0,05 kéo 10 ms giữa một đoạn tốc độ >= 2,5 và một đoạn tốc độ 1, xa tiếng tách của nguồn và chỗ nguồn nhọn;
    - đột im: 0,3 s số 0 giữa một đoạn tốc độ 1, chỗ tiếng ra đang có tiếng và nguồn không tự tắt.
    Trả (ok, kết quả từng phép)."""
    rate = data["rate"]
    base = base or check(data)
    results = [dict(case="sạch", ok=base["ok"], counts=base["counts"])]
    segments = [dict(tag=tag, first=f0, last=f1, **d) for (tag, (f0, f1)), d in zip(base["segments"], base["drift"])]
    for frac in STRENGTH_DRIFTS:
        must = [s for s in segments if abs(frac) * (s["last"] - s["first"]) / rate / 2 * 1000 > DRIFT_MS + s["spread_ms"]]
        if not must:
            results.append(dict(case=f"trôi {frac:+.1%}", ok=False, note="không đoạn nào đủ dài để chắc chắn thấy"))
            continue
        for s in must:
            mid = (s["first"] + s["last"]) / 2
            marks = [dict(m, position=m["position"] + frac * s["speed"] * (m["frame"] - mid) / rate)
                     if m["tag"] == "tick" and mid < m["frame"] <= s["last"] else m for m in data["marks"]]
            got = check(dict(data, marks=marks))
            hit = any(f["kind"] == "drift" and f["t"] == round(s["first"] / rate, 3) for f in got["findings"])
            results.append(dict(case=f"trôi {frac:+.1%} {s['tag']}", ok=hit))
    source = data["source"]
    source_clicks = np.array(clicks(source, rate) or [-10 ** 9], dtype=np.int64)
    sink_clicks = np.array(clicks(data["mono"], rate) or [-10 ** 9], dtype=np.int64)
    source_d2 = np.zeros_like(source)
    source_d2[2:] = np.abs(source[2:] - 2 * source[1:-1] + source[:-2])
    for name, fast in (("x>=2,5", True), ("x1", False)):
        pick = [s for s in segments if (s["speed"] >= 2.5) == fast and (fast or s["speed"] == 1.0)]
        at = None
        for s in sorted(pick, key=lambda s: s["first"] - s["last"]):
            ticks = [m for m in data["marks"] if m["tag"] == "tick" and s["first"] <= m["frame"] <= s["last"]]
            for a, b in zip(ticks, ticks[1:]):
                f = (a["frame"] + b["frame"]) // 2
                p = int((a["position"] + b["position"]) / 2 * rate)
                w = int(CLICK_SOURCE_S * s["speed"] * rate)
                if (np.min(np.abs(source_clicks - p)) > 0.3 * s["speed"] * rate and np.min(np.abs(sink_clicks - f)) > 0.05 * rate
                        and source_d2[max(0, p - w):p + w].max() < CLICK_COPY * STRENGTH_STEP / 2):
                    at = f
                    break
            if at is not None:
                break
        if at is None:
            results.append(dict(case=f"tách {name}", ok=False, note="không tìm được chỗ cấy"))
            continue
        mono = data["mono"].copy()
        mono[at: at + rate // 100] += STRENGTH_STEP
        got = check(dict(data, mono=mono))
        results.append(dict(case=f"tách {name} @{at / rate:.3f}s",
                            ok=any(f["kind"] == "click" and abs(f["t"] * rate - at) < 0.001 * rate for f in got["findings"])))
    hop = int(0.005 * rate)
    sink_db, source_db = frame_db(data["mono"], hop), frame_db(source, hop)
    at = None
    for s in sorted((s for s in segments if s["speed"] == 1.0), key=lambda s: s["first"] - s["last"]):
        ticks = [m for m in data["marks"] if m["tag"] == "tick" and s["first"] <= m["frame"] <= s["last"]]
        for a, b in zip(ticks, ticks[1:]):
            f = (a["frame"] + b["frame"]) // 2 // hop * hop
            p = int((a["position"] + b["position"]) / 2 * rate)
            if sink_db[f // hop - 1] > CUT_FROM_DB + 3 and source_db[(p - int(0.1 * rate)) // hop: (p + int(STRENGTH_CUT_S * rate)) // hop].min() > CUT_TO_DB:
                at = f
                break
        if at is not None:
            break
    if at is None:
        results.append(dict(case="đột im", ok=False, note="không tìm được chỗ cấy"))
    else:
        mono = data["mono"].copy()
        mono[at: at + int(STRENGTH_CUT_S * rate)] = 0
        got = check(dict(data, mono=mono))
        results.append(dict(case=f"đột im @{at / rate:.3f}s", ok=any(f["kind"] == "cut" and abs(f["t"] * rate - at) < 0.02 * rate for f in got["findings"])))
    return all(r["ok"] for r in results), results


def gate(exe, runs):
    """Cổng phát hành: `runs` lượt liền trên exe đều xanh, và lượt đầu qua kiểm lực. Xanh thì xoá bằng chứng (WAV lớn)."""
    stamp = time.strftime("gate-%Y%m%d-%H%M%S")
    labels = [f"{stamp}-{i + 1}" for i in range(runs)]
    reports = [run(label, exe) for label in labels]
    ok, results = strength(load(OUT / labels[0]), reports[0])
    summary = dict(gate="audio_sink", exe=str(exe), runs=[dict(label=l, ok=r["ok"], counts=r["counts"], excused=r["excused"]) for l, r in zip(labels, reports)],
                   strength=results, ok=ok and all(r["ok"] for r in reports))
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    if summary["ok"]:
        for label in labels:
            stage = (OUT / label).resolve()
            assert stage.parent == OUT.resolve()
            shutil.rmtree(stage)
    else:
        (OUT / f"{stamp}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    return summary["ok"]


# ---------- tự kiểm hai phía ----------

def voice_and_music(n, rate=RATE, seed=7):
    """Tiếng giả giống giọng (cao độ trượt, âm tiết 3,7 Hz) + nhạc nền ba nốt: không số 0 tuyệt đối, không bậc nhảy."""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / rate
    f0 = 140 + 40 * np.sin(2 * np.pi * 0.7 * t)
    phase = 2 * np.pi * np.cumsum(f0) / rate
    voiced = sum(np.sin(k * phase) / k for k in range(1, 12))
    syllables = np.clip(np.sin(2 * np.pi * 3.7 * t), 0, None) ** 0.5 * (0.6 + 0.4 * np.sin(2 * np.pi * 0.31 * t) ** 2)
    noise = np.convolve(rng.standard_normal(n), np.ones(8) / 8, mode="same")
    speech = (0.18 * voiced * syllables + 0.01 * noise * syllables).astype(np.float32)
    music = (0.02 * (np.sin(2 * np.pi * 220 * t) + 0.7 * np.sin(2 * np.pi * 277.2 * t + 1) + 0.5 * np.sin(2 * np.pi * 329.6 * t + 2))).astype(np.float32)
    return speech + music, music


def synthetic_run(speed=1.0, saw_ms=10.0, drift=0.0, lead_ms=0.0, source_step_at=None, source_quiet_at=None, rate=RATE):
    """Một lượt giả cho check() theo hình kịch bản: play 0,5 s, pause 2 s, resume 2,5 s, rate:1 3 s, rate:<speed> 25,5 s,
    stop 48 s. Tiếng ra là nguồn đọc theo vị trí thật (như Sonic chép nguyên mẫu), đi trước vị trí báo lead_ms (người nghe).
    Tick 0,25 s báo vị trí trễ răng cưa 0..saw_ms (chu kỳ 2,5 s, như con trỏ nghe theo padding). drift: trôi thêm từ giữa
    đoạn cuối. source_step_at: bậc 0,05 trong nguồn ở giây nguồn ấy (tiếng bật của bản ghi). source_quiet_at: nguồn im tuyệt đối
    0,3 s từ giây nguồn ấy (TTS cắt cứng cuối câu, không nhạc)."""
    play, pause, resume, normal, change, stop, end = 0.5, 2.0, 2.5, 3.0, 25.5, 48.0, 49.0
    middle = (change + stop) / 2

    def local(t):
        return speed if t >= change else 1.0

    def truth(t):
        if t < pause:
            return t - play
        if t < resume:
            return pause - play
        if t < change:
            return pause - play + t - resume
        p = pause - play + change - resume + speed * (t - change)
        return p + (speed * drift * (t - middle) if t > middle else 0.0)

    # Tiếng ra kiểu Sonic: từng khúc 25 ms (tick rơi đầu khúc) chép nguyên từ nguồn ở vị trí thật, nối mờ 5 ms (ở x3 bỏ 2/3 nguồn giữa các khúc)
    hop, ramp = rate // 40, rate // 200
    starts = np.array([int(round((truth(j * hop / rate) + lead_ms / 1000 * local(j * hop / rate)) * rate)) for j in range(int(end * rate) // hop)])
    source, _ = voice_and_music(int((truth(end) + 1) * rate), rate)
    if source_step_at is not None:  # đặt bậc giữa một khúc được chép, như chu kỳ chứa tiếng bật mà Sonic giữ lại
        j = int(np.argmin(np.abs(starts - source_step_at * rate)))
        source[starts[j] + ramp + hop // 2:] += STRENGTH_STEP
    if source_quiet_at is not None:
        source[int(source_quiet_at * rate): int((source_quiet_at + STRENGTH_CUT_S) * rate)] = 0
    window = np.ones(hop + ramp, np.float32)
    window[:ramp], window[hop:] = np.linspace(0, 1, ramp), np.linspace(1, 0, ramp)
    mono = np.zeros(len(starts) * hop + ramp, np.float32)
    for j, at in enumerate(starts):
        mono[j * hop: j * hop + hop + ramp] += source[max(0, at): max(0, at) + hop + ramp] * window
    t = np.arange(len(mono)) / rate
    mono[~(((t >= play) & (t < pause)) | ((t >= resume) & (t < stop)))] = 0
    marks = []

    def mark(tag, when, on):
        lag = saw_ms / 1000 * ((when / 2.5) % 1.0) if on else 0.0
        marks.append(dict(tag=tag, ms=when * 1000, frame=int(round(when * rate)), chapter=1,
                          position=round(truth(when) - local(when) * lag, 3), playing=int(on)))
    for tag, when in (("play", play), ("pause", pause), ("resume", resume), ("rate:1", normal), (f"rate:{speed:g}", change), ("stop", stop)):
        mark(tag, when, tag not in ("pause", "stop"))
    for k in range(int(play / 0.25) + 1, int(end / 0.25)):
        when = k * 0.25 + 0.006  # sau mép mờ đầu khúc
        mark("tick", when, bool(play <= when < pause or resume <= when < stop))
    marks.sort(key=lambda m: m["frame"])
    return dict(sink="synthetic", rate=rate, mono=mono, marks=marks, gaps=[], stops=[], source=source)


def selftest():
    """Bộ dò im với tiếng sạch giống giọng + nhạc, và bắt được từng lỗi cấy vào. Không cần app hay file ngoài."""
    rate, n = RATE, RATE * 12
    clean, music = voice_and_music(n, rate)
    failures = []

    def expect(name, ok):
        if not ok:
            failures.append(name)

    expect("sạch: không tách", clicks(clean, rate) == [])
    expect("sạch: không chuỗi số 0", zero_runs(clean, int(ZERO_RUN_S * rate)) == [])
    # Tách: bậc nhảy 0,05 (một mẫu dịch chỗ), và hai đoạn nối lệch pha (như trộn lại sai chỗ)
    step = clean.copy(); step[3 * rate:] += 0.05
    expect("tách: bậc 0,05", any(abs(k - 3 * rate) < 5 for k in clicks(step, rate)))
    splice = np.concatenate((clean[: 5 * rate], clean[5 * rate + 173:]))
    expect("tách: nối lệch 173 mẫu", any(abs(k - 5 * rate) < 5 for k in clicks(splice, rate)))
    # Mờ 5 ms (như tua / trộn lại đúng cách) thì KHÔNG phải tách
    ramp = clean.copy(); w = int(0.005 * rate)
    ramp[6 * rate: 6 * rate + w] *= np.linspace(1, 0, w, dtype=np.float32)
    ramp[6 * rate + w: 6 * rate + 2 * w] *= np.linspace(0, 1, w, dtype=np.float32)
    expect("mờ 5 ms: không tách", clicks(ramp, rate) == [])
    # Lỗ: một chu kỳ 10 ms im lặng giữa câu
    hole = clean.copy(); hole[7 * rate: 7 * rate + 480] = 0
    runs = zero_runs(hole, int(ZERO_RUN_S * rate))
    expect("lỗ: 480 khung số 0", any(a == 7 * rate and m == 480 for a, m in runs))
    expect("lỗ: mép lỗ là tiếng tách", any(abs(k - 7 * rate) < 5 or abs(k - 7 * rate - 480) < 5 for k in clicks(hole, rate)))
    # Khớp dạng sóng: tiếng ra trễ 25 ms so với nguồn -> lệch -25 ms; trễ đổi giữa chừng -> hai giá trị khác nhau
    late = np.concatenate((np.zeros(int(0.025 * rate), np.float32), clean))[: n]
    off, score = match_offset(late, clean, 4 * rate, 4 * rate, rate)
    expect("khớp: trễ 25 ms", off is not None and abs(off * 1000 + 25) < 0.5 and score > 0.9)
    off, score = match_offset(clean, clean, 4 * rate, 4 * rate, rate)
    expect("khớp: trùng khít", off is not None and abs(off) < 1e-9 and score > 0.99)
    # Giọng mất: 20 ms im (có nhạc) thấp hơn nguồn > DROPOUT_DB thì phải thấy; nhạc nền còn thì frame_db vẫn thấp hơn nguồn
    gone = clean.copy(); gone[8 * rate: 8 * rate + 960] = music[8 * rate: 8 * rate + 960] * 0.001
    k = 8 * rate // 960
    expect("mất giọng: 20 ms", frame_db(gone, 960)[k] < frame_db(clean, 960)[k] - DROPOUT_DB)
    # Lượt giả qua check(): răng cưa 10 ms của con trỏ nghe không phải trôi, trôi thật từ giữa đoạn là trôi
    def kinds(data):
        return {f["kind"] for f in check(data)["findings"]}
    for speed in (1.0, 3.0):
        expect(f"lượt giả x{speed:g}: sạch", kinds(synthetic_run(speed)) == set())
    for frac in STRENGTH_DRIFTS:
        expect(f"lượt giả: trôi {frac:+.1%}", "drift" in kinds(synthetic_run(1.0, drift=frac)))
    # Tiếng bật của nguồn, tiếng nghe đi trước vị trí báo 22 ms: ở x3 là 66 ms nguồn mà vẫn là của nguồn; 66 ms ở x1 thì không
    fast = synthetic_run(3.0, lead_ms=22, source_step_at=60.0)
    expect("tách nguồn x3: tiếng ra có tách", any(abs(k - 37.3 * rate) < 0.1 * rate for k in clicks(fast["mono"], rate)))
    expect("tách nguồn x3 lệch 22 ms: không tách", "click" not in kinds(fast))
    expect("tách nguồn x1 lệch 66 ms: tách", "click" in kinds(synthetic_run(1.0, lead_ms=66, source_step_at=15.0)))
    # Đột im: 0,3 s số 0 giữa lúc phát là đột im; nguồn tự im (tiếng ra chép theo) thì không; ngay sau thao tác (dừng) thì không
    cut = synthetic_run(1.0)
    cut["mono"] = cut["mono"].copy(); cut["mono"][10 * rate: 10 * rate + int(STRENGTH_CUT_S * rate)] = 0
    expect("đột im: 0,3 s số 0 giữa lúc phát", any(f["kind"] == "cut" and abs(f["t"] - 10) < 0.02 for f in check(cut)["findings"]))
    expect("đột im: nguồn tự im thì không", "cut" not in kinds(synthetic_run(1.0, source_quiet_at=12.0)))
    ok, results = strength(synthetic_run(3.0))
    expect("kiểm lực trên lượt giả: " + ", ".join(r["case"] for r in results if not r["ok"]), ok)
    # ... và kiểm lực phải đỏ khi máy dò bị nới (ngưỡng trôi to vô hạn): cổng không bao giờ xanh với bộ dò câm
    global DRIFT_MS, CUT_TO_DB
    saved, DRIFT_MS = DRIFT_MS, 1e9
    try:
        expect("kiểm lực đỏ khi máy dò trôi câm", not strength(synthetic_run(3.0))[0])
    finally:
        DRIFT_MS = saved
    saved, CUT_TO_DB = CUT_TO_DB, -1e9
    try:
        expect("kiểm lực đỏ khi máy dò đột im câm", not strength(synthetic_run(3.0))[0])
    finally:
        CUT_TO_DB = saved
    print(json.dumps(dict(selftest="audio_sink", failures=failures), ensure_ascii=False))
    return not failures


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("label"); r.add_argument("--exe", type=Path, default=ROOT / "dist/ABookDesk.exe")
    a = sub.add_parser("analyze"); a.add_argument("dir", type=Path); a.add_argument("--source", type=Path)
    sub.add_parser("selftest")
    st = sub.add_parser("strength"); st.add_argument("dir", type=Path); st.add_argument("--source", type=Path)
    g = sub.add_parser("gate"); g.add_argument("exe", type=Path); g.add_argument("--runs", type=int, default=2)
    args = ap.parse_args()
    if args.cmd == "selftest":
        sys.exit(0 if selftest() else 1)
    if args.cmd == "gate":
        sys.exit(0 if gate(args.exe, args.runs) else 1)
    if args.cmd == "strength":
        ok, results = strength(load(args.dir, args.source))
        print(json.dumps(dict(strength=results, ok=ok), ensure_ascii=False, indent=1))
        sys.exit(0 if ok else 1)
    report = run(args.label, args.exe) if args.cmd == "run" else analyze(args.dir, args.source)
    print(json.dumps({k: report[k] for k in ("seconds", "counts", "drift", "offsets", "levels", "ok")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
