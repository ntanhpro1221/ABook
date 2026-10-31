"""Tai kiểm tiếng của app máy tính (ABOOK_AUDIO_SINK).

App chạy trên bàn làm việc ẩn, bộ trộn ghi đúng những khung đáng lẽ ra WASAPI vào WAV theo nhịp đồng hồ thật. Kịch bản bench
"audio" (qml/BenchScenario.qml) phát cuốn thử có nhạc: phát, dừng, tua, đổi nhạc giữa chương (mờ chéo), hạ / nâng mức nhạc,
bốn tốc độ, tua xa, lùi, hết chương tự sang chương sau, bấm chương sau. Rồi soi file:

  lỗ      chu kỳ engine kéo mà thiếu dữ liệu / luồng đang dừng (.gaps/.stops), chuỗi số 0 tuyệt đối, giọng mất hẳn so với nguồn
  tách    bậc nhảy mẫu-mẫu (sai phân bậc hai vượt xa nền quanh nó) mà nguồn ở cùng chỗ không có
  trôi    vị trí app báo so với đồng hồ (độ dốc từng đoạn) và tiếng nghe thấy so với vị trí app báo (khớp dạng sóng với nguồn)
  mức     tiếng ra so với nguồn ở cùng đoạn nội dung, theo từng tốc độ
  rò      còn tiếng sau lúc dừng

  python -X utf8 tools/audio_sink.py run <label> [--exe dist/ABookDesk.exe]
  python -X utf8 tools/audio_sink.py analyze <thư_mục_lượt>
  python -X utf8 tools/audio_sink.py selftest      (build.bat: bộ dò bắt được lỗi cấy vào và im với tiếng sạch)

Bằng chứng (WAV, đoạn trích quanh chỗ nghi) nằm trong build/audiosink-evidence/<label>/ - không bao giờ commit.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
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
DROPOUT_DB = 30.0       # tiếng ra thấp hơn nguồn chừng này dB trong 20 ms khi nguồn có tiếng = giọng mất
LEVEL_TOL_DB = 1.0      # mức ở mỗi tốc độ lệch mức ở tốc độ 1 quá chừng này = lỗi
DRIFT_TOL = 0.002       # vị trí chạy lệch tốc độ quá 0,2 %
OFFSET_SPREAD_MS = 30.0 # tiếng nghe thấy lệch vị trí app báo: dao động quá chừng này trong một đoạn = trôi / giật
LEAK_PEAK = 1e-3        # sau lúc dừng 60 ms còn đỉnh lớn hơn thế = rò
TREND_TOL_MS = 10.0     # tiếng nghe thấy trôi khỏi vị trí app báo quá 10 ms (thời gian người nghe) mỗi 10 s
TREND_SPAN_S = 10.0     # ... chỉ đo trên đoạn dài ít nhất chừng này (đoạn ngắn: Sonic + vùng nắn ±50 ms làm dốc giả)
OFFSET_MEDIAN_MS = 40.0 # tiếng nghe thấy đi trước / sau vị trí app báo quá chừng này = đọc-theo lệch thấy được (tua mất khối: 171)
MATCH_SCORE = 0.9      # khớp dạng sóng dưới mức này là khớp nhầm chu kỳ cao độ khác, bỏ
DROPOUT_SLACK_S = 0.06  # mất giọng: so với chỗ nguồn im nhất trong ±chừng này (giây người nghe) quanh vị trí báo


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


def analyze(run_dir, source_path=None):
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "run.json").read_bytes()) if (run_dir / "run.json").exists() else {}
    sink_path = run_dir / "sink.wav"
    x, rate = read_wav(sink_path)
    mono = x.mean(axis=1)
    epoch_ms, clock_rate = Path(str(sink_path) + ".clock").read_text().split()
    epoch_ms, clock_rate = float(epoch_ms), int(clock_rate)
    assert clock_rate == rate
    bench = json.loads((run_dir / "bench.json").read_bytes())
    marks = parse_marks(bench["events"], epoch_ms, rate)
    events = [m for m in marks if m["tag"] != "tick"]
    ticks = [m for m in marks if m["tag"] == "tick"]
    source = decode(source_path or meta["source"], rate)
    snippets = run_dir / "snippets"
    snippets.mkdir(exist_ok=True)
    findings = []

    def snip(kind, frame, note):
        name = f"{kind}_{frame / rate:08.3f}s.wav"
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

    def position_at(f):
        for a, b in pairs:
            if a["frame"] <= f <= b["frame"]:
                return a["position"] + (b["position"] - a["position"]) * (f - a["frame"]) / (b["frame"] - a["frame"])
        return None

    # 1. Lỗ do thiết bị thấy: engine kéo mà thiếu / luồng đang dừng
    for kind, path in (("hole_gap", ".gaps"), ("hole_stop", ".stops")):
        for at, n in read_pairs(str(sink_path) + path):
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
    source_clicks = np.array(clicks(source, rate), dtype=np.int64)
    for f in clicks(mono, rate):
        if not in_sound(f):
            continue
        p = position_at(f)
        if p is not None and len(source_clicks) and np.min(np.abs(source_clicks - int(p * rate))) < 0.05 * rate:
            continue
        snip("click", f, "")
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

    # 6. Trôi vị trí: độ dốc vị trí theo đồng hồ tiếng ra so với tốc độ đặt
    drift = []
    for s in segments:
        t = np.array([m["frame"] for m in s["ticks"]], dtype=np.float64) / rate
        p = np.array([m["position"] for m in s["ticks"]])
        slope = float(np.polyfit(t, p, 1)[0])
        speed = rate_of[s["tag"]]
        drift.append(dict(segment=s["tag"], speed=speed, slope=round(slope, 5), error=round(slope / speed - 1, 5)))
        if abs(slope / speed - 1) > DRIFT_TOL:
            snip("drift", s["frames"][0], f"{s['tag']}: vị trí chạy {slope:.4f} giây/giây, tốc độ {speed}")
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
    report = dict(sink=str(sink_path), seconds=round(len(mono) / rate, 2), events=[(e["tag"], round(e["frame"] / rate, 3), e["chapter"], e["position"]) for e in events],
                  counts=counts, findings=findings, drift=drift, offsets=offsets, levels=levels, ok=not findings)
    (run_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    return report


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


# ---------- tự kiểm hai phía ----------

def selftest():
    """Bộ dò im với tiếng sạch giống giọng + nhạc, và bắt được từng lỗi cấy vào. Không cần app hay file ngoài."""
    rng = np.random.default_rng(7)
    rate, n = RATE, RATE * 12
    t = np.arange(n) / rate
    f0 = 140 + 40 * np.sin(2 * np.pi * 0.7 * t)
    phase = 2 * np.pi * np.cumsum(f0) / rate
    voiced = sum(np.sin(k * phase) / k for k in range(1, 12))
    syllables = np.clip(np.sin(2 * np.pi * 3.7 * t), 0, None) ** 0.5 * (0.6 + 0.4 * np.sin(2 * np.pi * 0.31 * t) ** 2)
    noise = np.convolve(rng.standard_normal(n), np.ones(8) / 8, mode="same")
    speech = (0.18 * voiced * syllables + 0.01 * noise * syllables).astype(np.float32)
    music = (0.02 * (np.sin(2 * np.pi * 220 * t) + 0.7 * np.sin(2 * np.pi * 277.2 * t + 1) + 0.5 * np.sin(2 * np.pi * 329.6 * t + 2))).astype(np.float32)
    clean = speech + music
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
    print(json.dumps(dict(selftest="audio_sink", failures=failures), ensure_ascii=False))
    return not failures


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("label"); r.add_argument("--exe", type=Path, default=ROOT / "dist/ABookDesk.exe")
    a = sub.add_parser("analyze"); a.add_argument("dir", type=Path); a.add_argument("--source", type=Path)
    sub.add_parser("selftest")
    args = ap.parse_args()
    if args.cmd == "selftest":
        sys.exit(0 if selftest() else 1)
    report = run(args.label, args.exe) if args.cmd == "run" else analyze(args.dir, args.source)
    print(json.dumps({k: report[k] for k in ("seconds", "counts", "drift", "offsets", "levels", "ok")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
