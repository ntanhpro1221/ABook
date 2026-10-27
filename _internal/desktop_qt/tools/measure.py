"""Đo app Qt: khởi động nguội, RAM riêng khi nghỉ, nhịp khung khi cuộn lưới thư viện - cùng cách đo với measure_ra.py của đợt thử.

  measure.py [--exe dist/ABookDesk.exe] [--fixture D:/Novels/native_desk_proto/deskqt_fixture] [--runs 5] [--attempts 12] [--scenario library|player]

Mỗi lượt: chạy app với ABOOK_BENCH (app tự ghi mốc + từng khung frameSwapped bằng đồng hồ steady của chính nó, rồi thoát), trong lúc đó
launcher lấy mẫu RAM riêng của tiến trình giao diện (QueryWorkingSet: trang trong working set không có bit Shared) mỗi 250 ms, và nhìn
cửa sổ nằm ở (-10000,-10000), không nhận tiêu điểm. Có kiểm cả sự kiện foreground lẫn GetForegroundWindow: app chiếm tiêu điểm thì lượt đo HỎNG.
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
dwm = ctypes.WinDLL("dwmapi")
dwm.DwmGetWindowAttribute.argtypes = [wt.HWND, wt.DWORD, ctypes.c_void_p, wt.DWORD]
u32.GetForegroundWindow.restype = wt.HWND
u32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]


def private_mb(h) -> float:
    """RAM riêng = trang trong working set không chia sẻ (cùng cách đo với measure.py của đợt thử)."""
    n = 1 << 17
    while n <= 1 << 23:
        buf = (ctypes.c_size_t * n)()
        if psapi.QueryWorkingSet(h, buf, ctypes.sizeof(buf)):
            break
        # Tiến trình vừa thoát: lỗi handle không phải thiếu bộ đệm, không nhân đôi RAM vô hạn.
        error = ctypes.get_last_error()
        if error != 24 or n >= 1 << 23:  # ERROR_BAD_LENGTH
            raise OSError(error, "QueryWorkingSet")
        n *= 2
    else:
        raise RuntimeError("Working set lớn hơn giới hạn bộ đo")
    cnt = buf[0]
    return sum(1 for i in range(1, cnt + 1) if not (buf[i] & 0x100)) * 4096 / 1048576


def tsc_mhz() -> float:
    """Tần số TSC (bất biến) ~ xung danh định của CPU, đọc từ registry."""
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
        return float(winreg.QueryValueEx(key, "~MHz")[0])


_TSC_MHZ = tsc_mhz()


def cpu_ms(h) -> float:
    """CPU tiến trình đã dùng, mili giây: chu kỳ (QueryProcessCycleTime, đếm theo TSC) chia tần số TSC.
    GetProcessTimes chỉ nhảy theo nhịp 15,6 ms nên sai cả chục phần trăm khi tiến trình gần như ngủ."""
    cycles = ctypes.c_uint64()
    if not k32.QueryProcessCycleTime(h, ctypes.byref(cycles)):
        return float("nan")
    return cycles.value / (_TSC_MHZ * 1000.0)


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
        out["rect"] = [r.left, r.top, r.right, r.bottom]
        top = u32.WindowFromPoint(wt.POINT((r.left + r.right) // 2, (r.top + r.bottom) // 2))
        out["top_at_center"] = bool(top) and u32.GetAncestor(top, 2) == h
        out["iconic"] = bool(u32.IsIconic(h))
    fg = u32.GetForegroundWindow()
    q = wt.DWORD()
    u32.GetWindowThreadProcessId(fg, ctypes.byref(q))
    out["fg_is_us"] = q.value == pid
    return out


def cloak_states(pid: int) -> list[dict]:
    result = []
    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def inspect(hwnd, _param):
        owner = wt.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            cloak = wt.DWORD()
            hr = dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloak), ctypes.sizeof(cloak))
            rect = wt.RECT()
            u32.GetWindowRect(hwnd, ctypes.byref(rect))
            result.append({"hwnd": int(hwnd), "visible": bool(u32.IsWindowVisible(hwnd)),
                           "cloaked": cloak.value if hr == 0 else None,
                           "rect": [rect.left, rect.top, rect.right, rect.bottom]})
        return True
    u32.EnumWindows(inspect, 0)
    return result


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


def launch(exe: Path, env_extra: dict, offscreen: bool = True, timeout_seconds: float = 120) -> dict:
    """Chạy app một lượt, lấy mẫu RAM riêng + CPU mỗi 250 ms và trạng thái cửa sổ; trả về mọi thứ thô cho phần phân tích."""
    out = Path(tempfile.gettempdir()) / f"abookdesk_bench_{os.getpid()}.json"
    if not offscreen:
        raise ValueError("Chỉ cho phép đo ngoài màn hình")
    if out.exists():
        subprocess.run(["node", "-e", "require('fs').rmSync(process.argv[1], {force:true})", str(out.resolve())], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    env = dict(os.environ)
    env.update(env_extra)
    env["ABOOK_BENCH"] = str(out)
    env["QT_FORCE_STDERR_LOGGING"] = "1"
    platform = env.get("QT_QPA_PLATFORM", "windows").split(":")[0]
    candidates = [exe.parent / "platforms"]
    if env.get("QT_QPA_PLATFORM_PLUGIN_PATH"):
        candidates.insert(0, Path(env["QT_QPA_PLATFORM_PLUGIN_PATH"]))
    candidates += [Path(p) / "platforms" for p in env.get("QT_PLUGIN_PATH", "").split(os.pathsep) if p]
    plugins = next((p for p in candidates if (p / f"q{platform}.dll").is_file()), None)
    if plugins is None:
        return {"ok": False, "why": f"Không có plugin {platform}; từ chối chạy để tránh hộp lỗi Qt"}
    env["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(plugins.resolve())
    wall0 = time.time()
    env["QT_FORCE_STDERR_LOGGING"] = "1"
    env["QT_ASSUME_STDERR_HAS_CONSOLE"] = "1"
    desktop = None
    startup = subprocess.STARTUPINFO()
    if env.get("QT_QPA_PLATFORM") == "offscreen" or env.get("ABOOK_BENCH_HIDDEN_DESKTOP") == "1":
        # Lớp chắn thứ hai: cả hộp lỗi trước lúc Qt nạp cũng không thể lên desktop của chủ sách.
        u32.CreateDesktopW.restype = wt.HANDLE
        u32.CreateDesktopW.argtypes = [wt.LPCWSTR, wt.LPCWSTR, ctypes.c_void_p, wt.DWORD, wt.DWORD, ctypes.c_void_p]
        u32.CloseDesktop.argtypes = [wt.HANDLE]
        desktop_name = f"ABookBench-{os.getpid()}"
        desktop = u32.CreateDesktopW(desktop_name, None, None, 0, 0x10000000, None)
        if not desktop:
            raise ctypes.WinError()
        startup.lpDesktop = "winsta0\\" + desktop_name
    app_log = out.with_suffix(".app.log").open("wb")
    command = [str(exe)]
    if env.get("ABOOK_BENCH_HIDDEN_DESKTOP") == "1":
        command += ["-qwindowgeometry", "1920x1080-20000-20000"]
    startup.dwFlags = subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 4  # SW_SHOWNOACTIVATE
    previous_error_mode = k32.SetErrorMode(0x0001 | 0x0002 | 0x8000)
    try:
        p = subprocess.Popen(command, env=env, cwd=str(exe.parent), stdout=app_log, stderr=subprocess.STDOUT,
                             creationflags=0x00000004 | subprocess.CREATE_NO_WINDOW, startupinfo=startup)
    finally:
        k32.SetErrorMode(previous_error_mode)
    h = k32.OpenProcess(0x0410, False, p.pid)
    samples: list[tuple[float, float, float]] = []   # (epoch ms, MB riêng, CPU ms của tiến trình)
    states: list[tuple[float, dict]] = []
    stop = threading.Event()

    host: list[tuple[float, float]] = []      # (epoch ms, CPU ms của mọi tiến trình con - host Python)
    kids: dict[int, int] = {}
    foreground = []
    cloak_errors = []
    cloaked_windows = set()
    require_cloak = env.get("ABOOK_BENCH_CLOAK") == "1"
    guard_ready = threading.Event()
    guard_error = []

    def focus_guard():
        callback_type = ctypes.WINFUNCTYPE(None, wt.HANDLE, wt.DWORD, wt.HWND, wt.LONG, wt.LONG, wt.DWORD, wt.DWORD)
        def inspect(hwnd):
            q = wt.DWORD()
            u32.GetWindowThreadProcessId(hwnd, ctypes.byref(q))
            if q.value == p.pid:
                foreground.append(time.time() * 1000)
                p.kill()
        @callback_type
        def changed(_hook, _event, hwnd, _obj, _child, _tid, _when):
            inspect(hwnd)
        u32.SetWinEventHook.restype = wt.HANDLE
        u32.SetWinEventHook.argtypes = [wt.DWORD, wt.DWORD, wt.HMODULE, callback_type, wt.DWORD, wt.DWORD, wt.DWORD]
        hook = u32.SetWinEventHook(3, 3, None, changed, 0, 0, 0)
        if not hook:
            guard_error.append("Không cài được bộ gác foreground")
        guard_ready.set()
        message = wt.MSG()
        while not stop.is_set():
            while u32.PeekMessageW(ctypes.byref(message), None, 0, 0, 1):
                u32.TranslateMessage(ctypes.byref(message))
                u32.DispatchMessageW(ctypes.byref(message))
            inspect(u32.GetForegroundWindow())
            stop.wait(0.01)
        if hook:
            u32.UnhookWinEvent.argtypes = [wt.HANDLE]
            u32.UnhookWinEvent(hook)

    guard_thread = threading.Thread(target=focus_guard, daemon=True)
    guard_thread.start()
    guard_ready.wait(5)
    if not guard_ready.is_set() or guard_error:
        p.kill()
        stop.set()
        guard_thread.join(2)
        return {"ok": False, "why": str(guard_error or "Bộ gác foreground không lên")}
    # Popen đóng handle luồng chính; NtResumeProcess chỉ dùng cho tiến trình vừa tạo của phép đo.
    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtResumeProcess.argtypes = [wt.HANDLE]
    ntdll.NtResumeProcess.restype = wt.LONG
    if ntdll.NtResumeProcess(wt.HANDLE(int(p._handle))) != 0:
        p.kill()
        stop.set()
        guard_thread.join(2)
        return {"ok": False, "why": "Không khởi động được app dưới bộ gác foreground"}

    def host_cpu_ms() -> float:
        try:
            import psutil
            for c in psutil.Process(p.pid).children(recursive=True):
                if c.pid not in kids:
                    kids[c.pid] = k32.OpenProcess(0x0410, False, c.pid)
        except Exception:
            pass
        return sum(cpu_ms(k) for k in kids.values() if k)       # tiến trình con đã thoát vẫn đọc được qua handle giữ lại

    def sampler():
        while not stop.is_set():
            try:
                samples.append((time.time() * 1000, private_mb(h), cpu_ms(h)))
                host.append((time.time() * 1000, host_cpu_ms()))
            except Exception:
                pass
            state = winstate(p.pid)
            if require_cloak:
                state["windows"] = cloak_states(p.pid)
                for window in state["windows"]:
                    if window["visible"] or window["cloaked"]:
                        cloaked_windows.add(window["hwnd"])
                    if window["hwnd"] in cloaked_windows and not window["cloaked"]:
                        cloak_errors.append(window)
                        p.kill()  # Cloak mất: kết thúc ngay, không chờ vòng lấy mẫu sau.
            states.append((time.time() * 1000, state))
            stop.wait(0.25)

    th = threading.Thread(target=sampler, daemon=True)
    th.start()
    host_mb = float("nan")
    deadline = time.time() + timeout_seconds
    while not out.exists() and time.time() < deadline and p.poll() is None and not foreground:
        time.sleep(0.2)
        if time.time() - wall0 > 8 and host_mb != host_mb:       # một lần lúc app đã nghỉ
            host_mb = host_tree_private_mb(p.pid)
    time.sleep(0.4)
    if foreground:
        import psutil
        try:
            for child in reversed(psutil.Process(p.pid).children(recursive=True)):
                child.kill()
        except psutil.NoSuchProcess:
            pass
        p.kill()
    forced_termination = False
    try:
        p.wait(8)
    except subprocess.TimeoutExpired:
        forced_termination = True
        # Chỉ thu hồi cây do lượt đo này tạo, không để host riêng sống sót sau app bị kẹt.
        import psutil
        for child in reversed(psutil.Process(p.pid).children(recursive=True)):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        p.kill()
        p.wait(5)
    stop.set()
    th.join(2)
    guard_thread.join(2)
    app_log.close()
    if desktop:
        u32.CloseDesktop(desktop)
    for handle in [h, *kids.values()]:
        if handle:
            k32.CloseHandle(handle)
    audit = os.environ.get("ABOOK_BENCH_AUDIT_DIR")
    if audit:
        folder = Path(audit)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{int(wall0 * 1000)}_{p.pid}.json").write_text(json.dumps({
            "foreground_events": foreground, "offscreen": True,
            "require_cloak": require_cloak, "cloak_errors": cloak_errors,
            "states": states, "samples": samples, "host_cpu": host, "child_pids": list(kids),
            "bench": json.loads(out.read_bytes()) if out.exists() else {}, "app_log": out.with_suffix(".app.log").read_text(encoding="utf-8", errors="replace"),
        }, indent=1), encoding="utf-8")
    if foreground or any(s.get("fg_is_us") for _t, s in states):
        return {"ok": False, "why": "OWNER RULE: app đã thành foreground", "foreground_events": foreground}
    if require_cloak and (cloak_errors or not cloaked_windows):
        return {"ok": False, "why": "OWNER RULE: DWM cloak mất hoặc không có mẫu xác nhận", "cloak_errors": cloak_errors}
    escaped = [s for _t, s in states if s.get("rect") and not s.get("iconic") and (s["rect"][2] >= 0 or s["rect"][3] >= 0)]
    if escaped and not require_cloak:
        return {"ok": False, "why": "OWNER RULE: cửa sổ đã rời vị trí ngoài màn hình", "escaped": escaped}
    if not out.exists():
        return {"ok": False, "why": "app không ghi file đo"}
    d = json.loads(out.read_bytes())
    return {"ok": True, "d": d, "samples": samples, "states": states, "host_mb": host_mb, "host_cpu": host, "foreground_events": 0, "offscreen": True, "app_log": str(out.with_suffix(".app.log")),
            "exit_code": p.returncode, "forced_termination": forced_termination}


def one_run(exe: Path, env_extra: dict, offscreen: bool = True) -> dict:
    got = launch(exe, env_extra, offscreen)
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
    bad = [s for t, s in states if ev["first_frame"] <= t <= s1 and s.get("iconic")]
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


def player_run(exe: Path, env_extra: dict, offscreen: bool = True) -> dict:
    """Kịch bản "player" (BenchScenario.qml): RAM nghỉ khi có sách, khung lúc biến hình, khung khi chữ chạy theo giọng, RAM + CPU khi thu nhỏ vẫn phát."""
    got = launch(exe, env_extra, offscreen)
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
    need = ["idle_begin", "idle_end", "follow_begin", "follow_end", "min_begin", "min_end", "done"]
    if any(k not in ev for k in need):
        return {"ok": False, "why": "thiếu mốc " + ",".join(k for k in need if k not in ev), "events": sorted(ev)}
    frames = [f + off for f in d["frames"]]
    start = d["process_start_epoch_ms"]
    morph = windows(evs, "morph_begin", "morph_end")
    unmorph = windows(evs, "unmorph_begin", "unmorph_end")
    follow = [(ev["follow_begin"], ev["follow_end"])]
    iv_m, iv_u, iv_f = gaps(frames, morph), gaps(frames, unmorph), gaps(frames, follow)
    idle = [m for t, m, _c in samples if ev["idle_begin"] + 1500 <= t <= ev["idle_end"]]
    idle_cpu = [(t, c) for t, _m, c in samples if ev["idle_begin"] + 1500 <= t <= ev["idle_end"]]
    follow_ram = [m for t, m, _c in samples if follow[0][0] <= t <= follow[0][1]]
    mins = [(t, m, c) for t, m, c in samples if ev["min_begin"] + 1500 <= t <= ev["min_end"]]
    settled = [m for t, m, _c in mins if t >= ev["min_end"] - 3000]       # 3 s cuối: sau khi app trả working set lúc thu nhỏ (2 s)
    restore = None
    if "restore_begin" in ev and "restore_end" in ev:      # mở lại sau thu nhỏ: khung đầu (ms từ lệnh mở) + khoảng cách khung lớn nhất
        rf = [f for f in frames if ev["restore_begin"] <= f <= ev["restore_end"]]
        restore = (rf[0] - ev["restore_begin"] if rf else float("nan"), max((b - a for a, b in zip(rf, rf[1:])), default=float("nan")))
    cpu_pct = float("nan")
    rate = lambda pts: (pts[-1][1] - pts[0][1]) / (pts[-1][0] - pts[0][0]) * 100.0 if len(pts) >= 2 and pts[-1][0] > pts[0][0] else float("nan")   # % của MỘT nhân
    host_min = [(t, c) for t, c in got["host_cpu"] if ev["min_begin"] + 1500 <= t <= ev["min_end"]]
    host_idle = [(t, c) for t, c in got["host_cpu"] if ev["idle_begin"] + 1500 <= t <= ev["idle_end"]]
    # trạng thái ổn định khi thu nhỏ: bỏ 5 s đầu (trả working set ở giây 2 + lỗi trang kéo về sau đó là chi phí một lần)
    steady = [(t, c) for t, _m, c in samples if ev["min_begin"] + 5000 <= t <= ev["min_end"]]
    host_steady = [(t, c) for t, c in got["host_cpu"] if ev["min_begin"] + 5000 <= t <= ev["min_end"]]
    if len(mins) >= 2 and mins[-1][0] > mins[0][0]:
        cpu_pct = (mins[-1][2] - mins[0][2]) / (mins[-1][0] - mins[0][0]) * 100.0      # % của MỘT nhân
    # che / thu nhỏ ngoài ý muốn trong các khoảng đo khung (khoảng thu nhỏ là chủ ý)
    spans = morph + unmorph + follow
    bad = [(round(t - ev["idle_begin"]), s) for t, s in states if any(a <= t <= b for a, b in spans) and s.get("iconic")]
    marks = {k: round(v - ev["idle_begin"]) for k, v in ev.items() if k.endswith("_begin") or k.endswith("_end")}
    fb, fe = counts.get("follow_begin"), counts.get("follow_end")
    mb, me = counts.get("min_begin"), counts.get("min_end")
    delta = lambda a, b: [y - x for x, y in zip(a, b)] if a and b else None
    return {
        "ok": True,
        "offscreen": True,
        "foreground_events": got["foreground_events"],
        "rendered_frames": len(frames),
        "covered": bool(bad),
        "bad_sample": (bad[0], marks) if bad else None,
        "cold_first_frame_ms": ev.get("first_frame", float("nan")) - start,
        "private_idle_loaded_mb": statistics.median(idle) if idle else float("nan"),
        "private_follow_mb": max(follow_ram) if follow_ram else float("nan"),
        "private_min_playing_mb": max(m for _, m, _c in mins) if mins else float("nan"),
        "private_min_settled_mb": statistics.median(settled) if settled else float("nan"),
        "restore_first_ms": restore[0] if restore else float("nan"),
        "restore_max_gap_ms": restore[1] if restore else float("nan"),
        "cpu_min_playing_pct_of_core": cpu_pct,
        "cpu_min_steady_pct_of_core": rate(steady),
        "host_cpu_min_steady_pct_of_core": rate(host_steady),
        "cpu_idle_loaded_pct_of_core": rate(idle_cpu),
        "host_cpu_min_playing_pct_of_core": rate(host_min),
        "host_cpu_idle_loaded_pct_of_core": rate(host_idle),
        "morph_frames": len(iv_m), "morph_p50": pct(iv_m, .5), "morph_p99": pct(iv_m, .99), "morph_max": max(iv_m) if iv_m else float("nan"),
        "unmorph_frames": len(iv_u), "unmorph_p99": pct(iv_u, .99), "unmorph_max": max(iv_u) if iv_u else float("nan"),
        "follow_frames": len(iv_f), "follow_p50": pct(iv_f, .5), "follow_p99": pct(iv_f, .99), "follow_max": max(iv_f) if iv_f else float("nan"),
        "follow_over_12": sum(1 for x in iv_f if x > 12.0),
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
        r = player_run(exe, env)
        if not r.get("ok"):
            print(f"lượt {attempt + 1}: lỗi - {r.get('why')}")
            dropped += 1
            continue
        if r["covered"] or (r["low_refresh"] and not a.allow_low_refresh):
            print(f"lượt {attempt + 1}: {'cửa sổ bị che ' + str(r['bad_sample']) if r['covered'] else 'tần số quét tụt'} -> bỏ")
            dropped += 1
            continue
        good.append(r)
        print(f"lượt {attempt + 1}: nghỉ có sách {r['private_idle_loaded_mb']:.1f} MB | biến hình p99 {r['morph_p99']:.1f} max {r['morph_max']:.1f} ms ({r['morph_frames']} khung; "
              f"đóng p99 {r['unmorph_p99']:.1f}) | chữ chạy p50 {r['follow_p50']:.1f} p99 {r['follow_p99']:.1f} max {r['follow_max']:.1f} ms "
              f"({r['follow_frames']} khung, >12ms {r['follow_over_12']}) RAM {r['private_follow_mb']:.1f} | thu nhỏ phát: RAM {r['private_min_playing_mb']:.1f} -> {r['private_min_settled_mb']:.1f} MB "
              f"CPU {r['cpu_min_playing_pct_of_core']:.2f} % (ổn định {r['cpu_min_steady_pct_of_core']:.2f} %; nghỉ hiện {r['cpu_idle_loaded_pct_of_core']:.2f} %) | đếm lúc chữ chạy (nhịp, ảnh chụp, tính, đổi) {r['follow_counters_delta']} trong {r['follow_secs']:.0f} s; "
              f"thu nhỏ {r['min_counters_delta']} | mở lại: khung đầu {r['restore_first_ms']:.0f} ms, khoảng lớn nhất {r['restore_max_gap_ms']:.1f} ms")
        time.sleep(1.0)
    res = {"scenario": "player", "hz": refresh_hz(), "runs": good, "dropped": dropped}
    if good:
        med = lambda k: statistics.median(r[k] for r in good)
        worst = lambda k: max(r[k] for r in good)
        res["summary"] = {
            "cold_first_frame_ms_median": med("cold_first_frame_ms"),
            "private_idle_loaded_mb_median": med("private_idle_loaded_mb"), "private_idle_loaded_mb_worst": worst("private_idle_loaded_mb"),
            "private_min_playing_mb_worst": worst("private_min_playing_mb"), "private_min_settled_mb_worst": worst("private_min_settled_mb"),
            "restore_first_ms_worst": worst("restore_first_ms"), "restore_max_gap_ms_worst": worst("restore_max_gap_ms"),
            "cpu_min_playing_pct_worst": worst("cpu_min_playing_pct_of_core"),
            "cpu_min_steady_pct_median": med("cpu_min_steady_pct_of_core"), "cpu_idle_loaded_pct_median": med("cpu_idle_loaded_pct_of_core"),
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
    ap.add_argument("--allow-low-refresh", action="store_true",
                    help="keep RAM samples on a 60 Hz display; frame results remain labelled low_refresh")
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
        r = one_run(exe, env)
        if not r.get("ok"):
            print(f"lượt {attempt + 1}: lỗi - {r.get('why')}")
            dropped += 1
            continue
        if r["covered"]:
            print(f"lượt {attempt + 1}: cửa sổ bị che -> bỏ")
            dropped += 1
            continue
        if r["low_refresh"] and not a.allow_low_refresh:
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
