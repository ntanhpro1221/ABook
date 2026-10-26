"""Đo app Qt: khởi động nguội, RAM riêng khi nghỉ, nhịp khung khi cuộn lưới thư viện - cùng cách đo với measure_ra.py của đợt thử.

  python -X utf8 measure.py [--exe dist/ABookDesk.exe] [--fixture D:/Novels/native_desk_proto/deskqt_fixture] [--runs 5] [--attempts 12] [--topmost] [--scenario library|player]

Mỗi lượt: chạy app với ABOOK_BENCH (app tự ghi mốc + từng khung frameSwapped bằng đồng hồ steady của chính nó, rồi thoát), trong lúc đó
launcher lấy mẫu RAM riêng của tiến trình giao diện (QueryWorkingSet: trang trong working set không có bit Shared) mỗi 250 ms, và nhìn
cửa sổ: lượt nào cửa sổ bị che / thu nhỏ ở giữa lúc đo thì BỎ (Qt Quick ngừng vẽ khi bị che nên số đo vô nghĩa), đo lại cho đủ số lượt.
--topmost: đặt cửa sổ luôn trên cùng (không lấy tiêu điểm) để lượt không bị che bởi cửa sổ khác của máy.
Kết quả: JSON ghi vào <fixture>/../results (hoặc --out) + bảng tóm tắt in ra. Thư viện thử là bản dựng riêng, không phải thư viện của người dùng.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)
u32 = ctypes.windll.user32
k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]


def private_mb(h) -> float:
    """RAM riêng = trang trong working set không chia sẻ (cùng cách đo với measure.py của đợt thử)."""
    n = 1 << 17
    while True:
        buf = (ctypes.c_size_t * n)()
        if psapi.QueryWorkingSet(h, buf, ctypes.sizeof(buf)):
            break
        n *= 2
    cnt = buf[0]
    return sum(1 for i in range(1, cnt + 1) if not (buf[i] & 0x100)) * 4096 / 1048576


def cpu_ms(h) -> float:
    """CPU (nhân + người dùng) tiến trình đã dùng, mili giây."""
    c, e, k, u = wt.FILETIME(), wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
    if not k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)):
        return float("nan")
    ticks = lambda f: (f.dwHighDateTime << 32) | f.dwLowDateTime
    return (ticks(k) + ticks(u)) / 10000.0


def pct(v: list[float], q: float) -> float:
    v = sorted(v)
    if not v:
        return float("nan")
    k = (len(v) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def window_of(pid: int):
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, _l):
        q = wt.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(q))
        if q.value == pid and u32.IsWindowVisible(h):
            r = wt.RECT()
            u32.GetClientRect(h, ctypes.byref(r))
            if r.right > 400:
                found.append(h)
        return True

    u32.EnumWindows(cb, 0)
    return found[0] if found else None


def winstate(pid: int) -> dict:
    h = window_of(pid)
    out = {"window": bool(h)}
    if h:
        r = wt.RECT()
        u32.GetWindowRect(h, ctypes.byref(r))
        top = u32.WindowFromPoint(wt.POINT((r.left + r.right) // 2, (r.top + r.bottom) // 2))
        out["top_at_center"] = bool(top) and u32.GetAncestor(top, 2) == h
        out["iconic"] = bool(u32.IsIconic(h))
    fg = u32.GetForegroundWindow()
    q = wt.DWORD()
    u32.GetWindowThreadProcessId(fg, ctypes.byref(q))
    out["fg_is_us"] = q.value == pid
    return out


def refresh_hz() -> int:
    class DM(ctypes.Structure):
        _fields_ = [("name", ctypes.c_wchar * 32), ("spec", wt.WORD), ("drv", wt.WORD), ("size", wt.WORD), ("drvx", wt.WORD), ("fields", wt.DWORD),
                    ("pos", ctypes.c_long * 2), ("orient", wt.DWORD), ("fout", wt.DWORD), ("color", ctypes.c_short), ("dup", ctypes.c_short),
                    ("yres", ctypes.c_short), ("tt", ctypes.c_short), ("coll", ctypes.c_short), ("form", ctypes.c_wchar * 32), ("log", wt.WORD),
                    ("bpp", wt.DWORD), ("w", wt.DWORD), ("h", wt.DWORD), ("flags", wt.DWORD), ("hz", wt.DWORD), ("rest", ctypes.c_byte * 32)]

    dm = DM()
    dm.size = ctypes.sizeof(DM)
    u32.EnumDisplaySettingsW(None, -1, ctypes.byref(dm))
    return int(dm.hz)


def host_tree_private_mb(parent_pid: int) -> float:
    """RAM riêng của host Python (con của app) - để báo riêng, không tính vào ngân sách giao diện."""
    try:
        import psutil
    except ImportError:
        return float("nan")
    total = 0.0
    try:
        for c in psutil.Process(parent_pid).children(recursive=True):
            h = k32.OpenProcess(0x0410, False, c.pid)
            if h:
                total += private_mb(h)
                k32.CloseHandle(h)
    except Exception:
        return float("nan")
    return total


def launch(exe: Path, env_extra: dict, topmost: bool) -> dict:
    """Chạy app một lượt, lấy mẫu RAM riêng + CPU mỗi 250 ms và trạng thái cửa sổ; trả về mọi thứ thô cho phần phân tích."""
    out = Path(tempfile.gettempdir()) / f"abookdesk_bench_{os.getpid()}.json"
    if out.exists():
        out.unlink()
    env = dict(os.environ)
    env.update(env_extra)
    env["ABOOK_BENCH"] = str(out)
    wall0 = time.time()
    p = subprocess.Popen([str(exe)], env=env, cwd=str(exe.parent))
    h = k32.OpenProcess(0x0410, False, p.pid)
    samples: list[tuple[float, float, float]] = []   # (epoch ms, MB riêng, CPU ms của tiến trình)
    states: list[tuple[float, dict]] = []
    stop = threading.Event()

    def sampler():
        placed = False
        while not stop.is_set():
            try:
                samples.append((time.time() * 1000, private_mb(h), cpu_ms(h)))
            except Exception:
                pass
            if topmost and not placed:
                w = window_of(p.pid)
                if w:
                    u32.SetWindowPos(w, ctypes.c_void_p(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)   # HWND_TOPMOST: c_void_p, int trần bị cắt 32 bit
                    placed = True
            states.append((time.time() * 1000, winstate(p.pid)))
            stop.wait(0.25)

    th = threading.Thread(target=sampler, daemon=True)
    th.start()
    host_mb = float("nan")
    deadline = time.time() + 120
    while not out.exists() and time.time() < deadline and p.poll() is None:
        time.sleep(0.2)
        if time.time() - wall0 > 8 and host_mb != host_mb:       # một lần lúc app đã nghỉ
            host_mb = host_tree_private_mb(p.pid)
    time.sleep(0.4)
    stop.set()
    th.join(2)
    try:
        p.wait(8)
    except subprocess.TimeoutExpired:
        p.kill()
    if not out.exists():
        return {"ok": False, "why": "app không ghi file đo"}
    d = json.loads(out.read_bytes())
    return {"ok": True, "d": d, "samples": samples, "states": states, "host_mb": host_mb}


def one_run(exe: Path, env_extra: dict, topmost: bool) -> dict:
    got = launch(exe, env_extra, topmost)
    if not got["ok"]:
        return got
    d, samples, states, host_mb = got["d"], got["samples"], got["states"], got["host_mb"]
    off = d["epoch_offset_ms"]
    ev = {}
    for t, name in d["events"]:
        ev.setdefault(name, t + off)          # epoch ms
    start = d["process_start_epoch_ms"]
    need = ["first_frame", "idle_begin", "scroll_begin", "scroll_end"]
    if any(k not in ev for k in need):
        return {"ok": False, "why": "thiếu mốc " + ",".join(k for k in need if k not in ev), "events": sorted(ev)}
    frames = [f + off for f in d["frames"]]
    s0, s1 = ev["scroll_begin"], ev["scroll_end"]
    inwin = [f for f in frames if s0 <= f <= s1]
    iv = [inwin[i] - inwin[i - 1] for i in range(1, len(inwin))]
    idle = [m for t, m, _c in samples if ev["idle_begin"] + 1500 <= t <= ev["scroll_begin"]]
    after = [m for t, m, _c in samples if t >= ev["scroll_end"]]
    # che / thu nhỏ trong lúc đo (từ khung đầu đến hết cuộn) -> bỏ lượt
    bad = [s for t, s in states if ev["first_frame"] <= t <= s1 and (not s.get("window") or s.get("iconic") or not s.get("top_at_center"))]
    fg_lost = sum(1 for t, s in states if ev["first_frame"] <= t <= s1 and not s.get("fg_is_us"))
    r = {
        "ok": True,
        "covered": bool(bad),
        "fg_lost_samples": fg_lost,
        "cold_first_frame_ms": ev["first_frame"] - start,
        "cold_host_ready_ms": ev.get("host_ready", float("nan")) - start,
        "cold_library_loaded_ms": ev.get("library_loaded", float("nan")) - start,
        "cold_first_cover_ms": ev.get("first_cover", float("nan")) - start,
        "cold_qml_loaded_ms": ev.get("qml_loaded", float("nan")) - start,
        "private_idle_mb": statistics.median(idle) if idle else float("nan"),
        "private_after_scroll_mb": max(after) if after else float("nan"),
        "private_peak_mb": max(m for _, m, _c in samples) if samples else float("nan"),
        "host_private_mb": host_mb,
        "frames": len(inwin),
        "frame_p50": pct(iv, .5), "frame_p95": pct(iv, .95), "frame_p99": pct(iv, .99), "frame_max": max(iv) if iv else float("nan"),
        # p50 > 11 ms = Windows hạ tần số quét xuống 60 Hz giữa lượt (làm mới động): p99 <= 12 ms không còn đo được -> bỏ lượt
        "low_refresh": pct(iv, .5) > 11.0,
        "gpu": subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip(),
        "frames_over_16_7": sum(1 for x in iv if x > 16.7),
        "frames_over_12": sum(1 for x in iv if x > 12.0),
    }
    return r


def windows(ev_all: list[tuple[float, str]], begin: str, end: str) -> list[tuple[float, float]]:
    """Mọi cặp (begin, end) liên tiếp theo thời gian (kịch bản player lặp mở / đóng 5 lần)."""
    out, cur = [], None
    for t, name in sorted(ev_all):
        if name == begin:
            cur = t
        elif name == end and cur is not None:
            out.append((cur, t))
            cur = None
    return out


def gaps(frames: list[float], spans: list[tuple[float, float]]) -> list[float]:
    """Khoảng cách giữa hai khung liên tiếp cùng nằm trong một khoảng đo."""
    iv: list[float] = []
    for a, b in spans:
        inside = [f for f in frames if a <= f <= b]
        iv += [inside[i] - inside[i - 1] for i in range(1, len(inside))]
    return iv


def worst_gap(frames: list[float], anim: list[float], evs: list[tuple[float, str]], span: tuple[float, float]) -> dict:
    """Khung trễ nhất trong một khoảng: ở đâu, nhịp luồng giao diện (afterAnimating) có trễ theo không, mốc nào ngay trước nó."""
    inside = [f for f in frames if span[0] <= f <= span[1]]
    if len(inside) < 2:
        return {}
    i = max(range(1, len(inside)), key=lambda k: inside[k] - inside[k - 1])
    a, b = inside[i - 1], inside[i]
    ticks = [t for t in anim if a - 50 <= t <= b + 50]
    gui = max((ticks[k] - ticks[k - 1] for k in range(1, len(ticks))), default=float("nan"))
    near = [(round(t - a, 1), n) for t, n in evs if a - 1500 <= t <= b + 100 and not n.startswith("count:")]
    return {"at_ms": round(a - span[0], 1), "gap_ms": round(b - a, 1), "gui_gap_ms": round(gui, 1) if gui == gui else None,
            "gui_ticks": len(ticks), "events": near}


def player_run(exe: Path, env_extra: dict, topmost: bool) -> dict:
    """Kịch bản "player" (BenchScenario.qml): RAM nghỉ khi có sách, khung lúc biến hình, khung khi chữ chạy theo giọng, RAM + CPU khi thu nhỏ vẫn phát."""
    got = launch(exe, env_extra, topmost)
    if not got["ok"]:
        return got
    d, samples, states = got["d"], got["samples"], got["states"]
    off = d["epoch_offset_ms"]
    evs = [(t + off, n) for t, n in d["events"]]
    ev: dict[str, float] = {}
    counts: dict[str, list[int]] = {}
    for t, n in evs:
        if n.startswith("count:"):
            _, tag, *vals = n.split(":")
            counts[tag] = [int(v) for v in vals]
        else:
            ev.setdefault(n, t)
    need = ["first_frame", "idle_begin", "idle_end", "follow_begin", "follow_end", "min_begin", "min_end", "done"]
    if any(k not in ev for k in need):
        return {"ok": False, "why": "thiếu mốc " + ",".join(k for k in need if k not in ev), "events": sorted(ev)}
    frames = [f + off for f in d["frames"]]
    start = d["process_start_epoch_ms"]
    morph = windows(evs, "morph_begin", "morph_end")
    unmorph = windows(evs, "unmorph_begin", "unmorph_end")
    follow = [(ev["follow_begin"], ev["follow_end"])]
    iv_m, iv_u, iv_f = gaps(frames, morph), gaps(frames, unmorph), gaps(frames, follow)
    worst = worst_gap(frames, [f + off for f in d.get("anim", [])], evs, follow[0])
    idle = [m for t, m, _c in samples if ev["idle_begin"] + 1500 <= t <= ev["idle_end"]]
    follow_ram = [m for t, m, _c in samples if follow[0][0] <= t <= follow[0][1]]
    mins = [(t, m, c) for t, m, c in samples if ev["min_begin"] + 1500 <= t <= ev["min_end"]]
    cpu_pct = float("nan")
    if len(mins) >= 2 and mins[-1][0] > mins[0][0]:
        cpu_pct = (mins[-1][2] - mins[0][2]) / (mins[-1][0] - mins[0][0]) * 100.0      # % của MỘT nhân
    # che / thu nhỏ ngoài ý muốn trong các khoảng đo khung (khoảng thu nhỏ là chủ ý)
    spans = morph + unmorph + follow
    bad = [(round(t - ev["idle_begin"]), s) for t, s in states if any(a <= t <= b for a, b in spans) and s.get("window") and (s.get("iconic") or not s.get("top_at_center"))]      # không thấy cửa sổ trong một mẫu (đang đổi cỡ) không tính là bị che
    marks = {k: round(v - ev["idle_begin"]) for k, v in ev.items() if k.endswith("_begin") or k.endswith("_end")}
    fb, fe = counts.get("follow_begin"), counts.get("follow_end")
    mb, me = counts.get("min_begin"), counts.get("min_end")
    delta = lambda a, b: [y - x for x, y in zip(a, b)] if a and b else None
    return {
        "ok": True,
        "covered": bool(bad),
        "bad_sample": (bad[0], marks) if bad else None,
        "cold_first_frame_ms": ev["first_frame"] - start,
        "private_idle_loaded_mb": statistics.median(idle) if idle else float("nan"),
        "private_follow_mb": max(follow_ram) if follow_ram else float("nan"),
        "private_min_playing_mb": max(m for _, m, _c in mins) if mins else float("nan"),
        "cpu_min_playing_pct_of_core": cpu_pct,
        "morph_frames": len(iv_m), "morph_p50": pct(iv_m, .5), "morph_p99": pct(iv_m, .99), "morph_max": max(iv_m) if iv_m else float("nan"),
        "unmorph_frames": len(iv_u), "unmorph_p99": pct(iv_u, .99), "unmorph_max": max(iv_u) if iv_u else float("nan"),
        "follow_frames": len(iv_f), "follow_p50": pct(iv_f, .5), "follow_p99": pct(iv_f, .99), "follow_max": max(iv_f) if iv_f else float("nan"),
        "follow_over_12": sum(1 for x in iv_f if x > 12.0),
        "follow_worst": worst,
        "low_refresh": pct(iv_f, .5) > 11.0,
        # bộ đếm: (nhịp đồng hồ, ảnh chụp đổi, lần tính câu của ReadAlong, lần đổi câu / chữ) - hiệu giữa hai mốc
        "follow_secs": (ev["follow_end"] - ev["follow_begin"]) / 1000.0,
        "follow_counters_delta": delta(fb, fe),
        "min_secs": (ev["min_end"] - ev["min_begin"]) / 1000.0,
        "min_counters_delta": delta(mb, me),
    }


def player_main(a, exe: Path, fixture: Path, env: dict) -> int:
    books = json.loads((fixture / "audio_books.json").read_bytes())
    env = dict(env, ABOOK_BENCH_SCENARIO="player", ABOOK_BENCH_BOOK=books["a"], ABOOK_MUTE="1")
    print(f"màn hình {refresh_hz()} Hz; exe {exe}; thư viện thử {fixture}; cuốn nghe thử {books['a']}")
    good: list[dict] = []
    dropped = 0
    for attempt in range(a.attempts):
        if len(good) >= a.runs:
            break
        clean = fixture / "listening.clean.json"        # lượt trước đã lưu chỗ nghe vào thư viện thử: mỗi lượt bắt đầu từ trạng thái chưa nghe
        if clean.exists():
            (fixture / "listening.json").write_bytes(clean.read_bytes())
        r = player_run(exe, env, a.topmost)
        if not r.get("ok"):
            print(f"lượt {attempt + 1}: lỗi - {r.get('why')}")
            dropped += 1
            continue
        if r["covered"] or r["low_refresh"]:
            print(f"lượt {attempt + 1}: {'cửa sổ bị che ' + str(r['bad_sample']) if r['covered'] else 'tần số quét tụt'} -> bỏ")
            dropped += 1
            continue
        good.append(r)
        print(f"lượt {attempt + 1}: nghỉ có sách {r['private_idle_loaded_mb']:.1f} MB | biến hình p99 {r['morph_p99']:.1f} max {r['morph_max']:.1f} ms ({r['morph_frames']} khung; "
              f"đóng p99 {r['unmorph_p99']:.1f}) | chữ chạy p50 {r['follow_p50']:.1f} p99 {r['follow_p99']:.1f} max {r['follow_max']:.1f} ms "
              f"({r['follow_frames']} khung, >12ms {r['follow_over_12']}) RAM {r['private_follow_mb']:.1f} | thu nhỏ phát: RAM {r['private_min_playing_mb']:.1f} MB "
              f"CPU {r['cpu_min_playing_pct_of_core']:.2f} % | đếm lúc chữ chạy (nhịp, ảnh chụp, tính, đổi) {r['follow_counters_delta']} trong {r['follow_secs']:.0f} s; "
              f"thu nhỏ {r['min_counters_delta']}\n    khựng lớn nhất {r['follow_worst']}")
        time.sleep(1.0)
    res = {"scenario": "player", "hz": refresh_hz(), "runs": good, "dropped": dropped}
    if good:
        med = lambda k: statistics.median(r[k] for r in good)
        worst = lambda k: max(r[k] for r in good)
        res["summary"] = {
            "cold_first_frame_ms_median": med("cold_first_frame_ms"),
            "private_idle_loaded_mb_median": med("private_idle_loaded_mb"), "private_idle_loaded_mb_worst": worst("private_idle_loaded_mb"),
            "private_min_playing_mb_worst": worst("private_min_playing_mb"), "cpu_min_playing_pct_worst": worst("cpu_min_playing_pct_of_core"),
            "morph_p99_ms_median": med("morph_p99"), "morph_p99_ms_worst": worst("morph_p99"), "unmorph_p99_ms_worst": worst("unmorph_p99"),
            "follow_p99_ms_median": med("follow_p99"), "follow_p99_ms_worst": worst("follow_p99"), "follow_max_ms_worst": worst("follow_max"),
        }
        print("tóm tắt:", json.dumps(res["summary"], indent=1))
    out = Path(a.out) if a.out else fixture.parent / "results" / "deskqt_measure_player.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes((json.dumps(res, indent=1) + "\n").encode("utf-8"))
    print("đã ghi", out)
    return 0 if good else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=str(HERE / "dist" / "ABookDesk.exe"))
    ap.add_argument("--fixture", default="D:/Novels/native_desk_proto/deskqt_fixture")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--attempts", type=int, default=12)
    ap.add_argument("--topmost", action="store_true")
    ap.add_argument("--scenario", choices=["library", "player"], default="library",
                    help="library: cuộn lưới; player: thanh phát + Đang nghe (thư viện thử phải có audio_books.json)")
    ap.add_argument("--out", default="")
    ap.add_argument("--python", default="D:/Novels/ABook/_internal/runtime/.venv/Scripts/pythonw.exe")
    a = ap.parse_args()
    exe = Path(a.exe).resolve()
    fixture = Path(a.fixture).resolve()
    env = {
        "ABOOK_PREFERENCES": str(fixture / "prefs.json"),
        "ABOOK_HOST_PYTHON": a.python,
        "ABOOK_HOST_APP": str(HERE.parent),
    }
    if a.scenario == "player":
        return player_main(a, exe, fixture, env)
    print(f"màn hình {refresh_hz()} Hz; exe {exe}; thư viện thử {fixture}")
    good: list[dict] = []
    dropped = 0
    for attempt in range(a.attempts):
        if len(good) >= a.runs:
            break
        r = one_run(exe, env, a.topmost)
        if not r.get("ok"):
            print(f"lượt {attempt + 1}: lỗi - {r.get('why')}")
            dropped += 1
            continue
        if r["covered"]:
            print(f"lượt {attempt + 1}: cửa sổ bị che -> bỏ")
            dropped += 1
            continue
        if r["low_refresh"]:
            print(f"lượt {attempt + 1}: tần số quét tụt về ~60 Hz (khung p50 {r['frame_p50']:.1f} ms) -> bỏ")
            dropped += 1
            continue
        good.append(r)
        print(f"lượt {attempt + 1}: nguội {r['cold_first_frame_ms']:.0f} ms (thư viện {r['cold_library_loaded_ms']:.0f}, bìa đầu {r['cold_first_cover_ms']:.0f}) "
              f"RAM nghỉ {r['private_idle_mb']:.1f} MB (sau cuộn {r['private_after_scroll_mb']:.1f}, host Python {r['host_private_mb']:.0f}) "
              f"khung p50 {r['frame_p50']:.1f} p99 {r['frame_p99']:.1f} max {r['frame_max']:.1f} ms (>12ms: {r['frames_over_12']}/{r['frames']}) "
              f"tiêu điểm mất {r['fg_lost_samples']}")
        time.sleep(1.0)
    res = {"hz": refresh_hz(), "runs": good, "dropped": dropped}
    if good:
        med = lambda k: statistics.median(r[k] for r in good)
        worst = lambda k: max(r[k] for r in good)
        res["summary"] = {
            "cold_first_frame_ms_median": med("cold_first_frame_ms"), "cold_first_frame_ms_worst": worst("cold_first_frame_ms"),
            "private_idle_mb_median": med("private_idle_mb"), "private_idle_mb_worst": worst("private_idle_mb"),
            "private_after_scroll_mb_worst": worst("private_after_scroll_mb"),
            "frame_p99_ms_median": med("frame_p99"), "frame_p99_ms_worst": worst("frame_p99"), "frame_max_ms_worst": worst("frame_max"),
        }
        print("tóm tắt:", json.dumps(res["summary"], indent=1))
    out = Path(a.out) if a.out else fixture.parent / "results" / "deskqt_measure.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes((json.dumps(res, indent=1) + "\n").encode("utf-8"))
    print("đã ghi", out)
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
