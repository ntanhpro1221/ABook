"""Đo app Qt: khởi động nguội, RAM riêng khi nghỉ, nhịp khung khi cuộn lưới thư viện - cùng cách đo với measure_ra.py của đợt thử.

  python -X utf8 measure.py [--exe dist/ABookDesk.exe] [--fixture D:/Novels/native_desk_proto/deskqt_fixture] [--runs 5] [--attempts 12] [--topmost]

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


def one_run(exe: Path, env_extra: dict, topmost: bool) -> dict:
    out = Path(tempfile.gettempdir()) / f"abookdesk_bench_{os.getpid()}.json"
    if out.exists():
        out.unlink()
    env = dict(os.environ)
    env.update(env_extra)
    env["ABOOK_BENCH"] = str(out)
    wall0 = time.time()
    p = subprocess.Popen([str(exe)], env=env, cwd=str(exe.parent))
    h = k32.OpenProcess(0x0410, False, p.pid)
    samples: list[tuple[float, float]] = []   # (epoch ms, MB riêng)
    states: list[tuple[float, dict]] = []
    stop = threading.Event()

    def sampler():
        placed = False
        while not stop.is_set():
            try:
                samples.append((time.time() * 1000, private_mb(h)))
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
    deadline = time.time() + 60
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
    idle = [m for t, m in samples if ev["idle_begin"] + 1500 <= t <= ev["scroll_begin"]]
    after = [m for t, m in samples if t >= ev["scroll_end"]]
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
        "private_peak_mb": max(m for _, m in samples) if samples else float("nan"),
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=str(HERE / "dist" / "ABookDesk.exe"))
    ap.add_argument("--fixture", default="D:/Novels/native_desk_proto/deskqt_fixture")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--attempts", type=int, default=12)
    ap.add_argument("--topmost", action="store_true")
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
