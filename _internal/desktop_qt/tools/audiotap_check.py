"""Đọc kết quả AudioTap (WAV + log + .gaps) và tự dò lỗi tiếng, không cần ai nghe.

  python audiotap_check.py script.json [--voice voice] [--snips DIR]

Phép dò:
- gaps: khung endpoint chạy mà không có dữ liệu (FileSinkDevice ghi).
- clicks: bước nhảy mẫu bất thường (sai phân bậc 2 vượt xa nền cục bộ), so với tỉ lệ cùng phép dò trên bản gốc giải mã.
- align: với giọng được chỉ định (chạy một mình), khớp phong bì 2 s của tiếng ra với bản gốc quanh vị trí app báo
  -> độ lệch "app nói đang ở X" so với "người nghe đang nghe Y", theo thời gian (lệch trôi = sai thời lượng).
- level: mức RMS tiếng ra so với đoạn nội dung gốc tương ứng, theo từng đoạn tốc độ.
- edges: biên độ quanh mỗi thao tác (pause/play/seek/rate): cắt cứng = nhảy từ mức nói xuống 0 trong < 1 ms.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

RATE = 48000
HOP = 480  # 10 ms


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def decode(path):
    raw = subprocess.run([ffmpeg_exe(), "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(RATE), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)


def mono(x):
    return x.mean(axis=1) if x.ndim == 2 else x


def envelope(x):
    m = mono(x)
    n = len(m) // HOP
    return np.sqrt((m[: n * HOP].reshape(n, HOP) ** 2).mean(axis=1) + 1e-12)


def click_hits(x, thresh=6.0):
    """Mẫu có sai phân bậc 2 vượt `thresh` lần mức 99,9 % của cửa sổ 50 ms quanh nó (bỏ đoạn gần im lặng)."""
    m = mono(x).astype(np.float64)
    d2 = np.abs(np.diff(m, 2))
    win = RATE // 20
    n = len(d2) // win
    hits = []
    for i in range(n):
        seg = d2[i * win:(i + 1) * win]
        lo = max(0, i - 2) * win
        hi = min(len(d2), (i + 3) * win)
        ref = np.percentile(d2[lo:hi], 99.9)
        peak = seg.max()
        if peak > 0.02 and peak > thresh * max(ref * 0.5, 1e-4) and peak > 4 * np.percentile(d2[lo:hi], 99):
            hits.append(i * win + int(seg.argmax()) + 1)
    return hits


def interp_position(samples, voice, frame):
    fr = np.array([s["frame"] for s in samples], dtype=np.float64)
    pos = np.array([s[voice] for s in samples], dtype=np.float64)
    i = np.searchsorted(fr, frame)
    if i <= 0 or i >= len(fr):
        return None
    # Chỉ nội suy trong một đoạn liền (không qua seek/pause): hai mẫu kề nhau phải tiến đều.
    f0, f1, p0, p1 = fr[i - 1], fr[i], pos[i - 1], pos[i]
    if f1 <= f0 or not (0 <= p1 - p0 <= 3 * (f1 - f0) / RATE):
        return None
    return p0 + (p1 - p0) * (frame - f0) / (f1 - f0)


def speed_at(marks, voice, frame):
    speed = 1.0
    for m in marks:
        if m["voice"] == voice and m["op"] == "rate" and m["frame"] <= frame:
            speed = m["value"]
    return speed


def align(out_env, ref_env, at_frame, pos, speed, span=2.0, search=0.5):
    """Tìm vị trí gốc khớp nhất cho cửa sổ tiếng ra [at, at+span) (phong bì 10 ms, co giãn theo tốc độ)."""
    a = at_frame // HOP
    w = int(span * 100)
    seg = out_env[a:a + w]
    if len(seg) < w or seg.max() < 1e-3:
        return None
    seg = np.log(seg + 1e-4)
    seg = seg - seg.mean()
    best = None
    for off in np.arange(-search, search + 1e-9, 0.002):
        start = (pos + off) * 100
        idx = start + np.arange(w) * speed
        if idx[0] < 0 or idx[-1] + 1 >= len(ref_env):
            continue
        ref = np.interp(idx, np.arange(len(ref_env)), ref_env)
        ref = np.log(ref + 1e-4)
        ref = ref - ref.mean()
        c = float(seg @ ref / (np.linalg.norm(seg) * np.linalg.norm(ref) + 1e-12))
        if best is None or c > best[1]:
            best = (off, c)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--voice", help="giọng chạy một mình để khớp với bản gốc")
    ap.add_argument("--snips", help="thư mục ghi đoạn wav 0,6 s quanh chỗ nghi")
    ap.add_argument("--json", help="ghi kết quả máy đọc")
    args = ap.parse_args()
    script = json.loads(Path(args.script).read_text(encoding="utf-8"))
    log = json.loads(Path(script["log"]).read_text(encoding="utf-8"))
    out, rate = sf.read(script["out"], dtype="float32")
    assert rate == RATE, rate
    report = {"seconds": len(out) / RATE}

    gaps_path = Path(script["out"] + ".gaps")
    gaps = [tuple(map(int, l.split())) for l in gaps_path.read_text().split("\n") if l.strip()] if gaps_path.exists() else []
    report["gaps"] = [{"at": a / RATE, "ms": f * 1000 / RATE} for a, f in gaps]

    marks = [m for m in log["marks"]]
    stops_path = Path(script["out"] + ".stops")
    stops = [tuple(map(int, l.split())) for l in stops_path.read_text().split("\n") if l.strip()] if stops_path.exists() else []
    m_out = mono(out)
    holes = []
    for a, f in stops:
        prior = [m for m in marks if m["frame"] <= a + RATE // 100]
        m = prior[-1] if prior else None
        # Bước vào và ra khỏi lỗ: biên độ ngay trước Stop và ngay sau Start (lỗ dài 0 vẫn là một mối ghép).
        into = float(np.abs(m_out[max(0, a - 1):a]).max()) if a else 0.0
        out_of = float(np.abs(m_out[a + f:a + f + 1]).max()) if a + f < len(m_out) else 0.0
        holes.append({"at": a / RATE, "ms": round(f * 1000 / RATE, 2), "after": f'{m["voice"]}:{m["op"]}' if m else None,
                      "step_in": round(into, 4), "step_out": round(out_of, 4),
                      "rms_before": round(float(np.sqrt((m_out[max(0, a - 480):a] ** 2).mean())) if a else 0.0, 4)})
    report["stops"] = holes
    out_hits = click_hits(out)
    near = []
    for h in out_hits:
        m = min(marks, key=lambda m: abs(m["frame"] - h)) if marks else None
        near.append({"at": h / RATE, "mark": f'{m["voice"]}:{m["op"]}' if m else None,
                     "from_mark_ms": (h - m["frame"]) * 1000 / RATE if m else None})
    report["clicks"] = near

    peak = float(np.abs(out).max())
    report["peak"] = peak
    report["clipped"] = int((np.abs(out) >= 0.999).sum())

    edges = []
    for m in marks:
        f = m["frame"]
        if f < RATE // 10 or f + RATE // 10 > len(out):
            continue
        before = float(np.sqrt((mono(out[f - 2400:f]) ** 2).mean()))
        # Tìm khoảng chuyển trong 200 ms sau mốc: bước lớn nhất của mẫu so với mức trước đó.
        win = mono(out[f - 480:f + 9600]).astype(np.float64)
        step = float(np.abs(np.diff(win)).max())
        edges.append({"mark": f'{m["voice"]}:{m["op"]}', "at": f / RATE, "rms_before": before, "max_step": step})
    report["edges"] = edges

    if args.voice:
        voice = args.voice
        ref = decode(script["voices"][voice]["file"])
        ref_hits = click_hits(ref)
        report["ref_click_rate_per_min"] = len(ref_hits) / (len(ref) / RATE / 60)
        out_env, ref_env = envelope(out), envelope(ref)
        rows = []
        samples = log["samples"]
        for t in np.arange(0.5, len(out) / RATE - 2.5, 0.5):
            f = int(t * RATE)
            pos = interp_position(samples, voice, f)
            # Cửa sổ 2 s không được vắt qua thao tác nào của giọng này.
            if pos is None or any(m["voice"] == voice and f - RATE // 5 <= m["frame"] <= f + 2 * RATE + RATE // 5 for m in marks):
                continue
            sp = speed_at(marks, voice, f)
            r = align(out_env, ref_env, f, pos, sp)
            if r is None:
                continue
            seg = out[f:f + 2 * RATE]
            src = ref[int(pos * RATE):int((pos + 2 * sp) * RATE)]
            lvl = 20 * np.log10((np.sqrt((seg ** 2).mean()) + 1e-9) / (np.sqrt((src ** 2).mean()) + 1e-9))
            rows.append({"t": round(float(t), 2), "pos": round(float(pos), 3), "speed": sp,
                         "offset_ms": round(r[0] * 1000, 1), "corr": round(r[1], 3), "level_db": round(float(lvl), 2)})
        report["align"] = rows
        good = [r for r in rows if r["corr"] > 0.8]
        if good:
            offs = np.array([r["offset_ms"] for r in good])
            report["align_summary"] = {"windows": len(rows), "matched": len(good), "offset_median_ms": float(np.median(offs)),
                                       "offset_min_ms": float(offs.min()), "offset_max_ms": float(offs.max())}
            by_speed = {}
            for r in good:
                by_speed.setdefault(r["speed"], []).append(r["level_db"])
            report["level_by_speed_db"] = {str(k): round(float(np.median(v)), 2) for k, v in by_speed.items()}

    if args.snips:
        d = Path(args.snips)
        d.mkdir(parents=True, exist_ok=True)
        for i, c in enumerate(report["clicks"]):
            f = int(c["at"] * RATE)
            sf.write(d / f"click_{i:02d}_{c['at']:.2f}s.wav", out[max(0, f - RATE * 3 // 10):f + RATE * 3 // 10], RATE, subtype="PCM_16")

    text = json.dumps(report, ensure_ascii=False, indent=1)
    if args.json:
        Path(args.json).write_text(text, encoding="utf-8")
    summary = {k: v for k, v in report.items() if k not in ("align", "edges")}
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("edges:")
    for e in report["edges"]:
        print(f'  {e["at"]:7.3f} {e["mark"]:14s} rms_before={e["rms_before"]:.4f} max_step={e["max_step"]:.4f}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
