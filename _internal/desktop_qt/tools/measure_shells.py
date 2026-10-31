"""measure_shells.py <tools dir> <shells dir> [--rounds 3] [--seconds 40]: Qt vs Tauri on a never-switched desktop.

Every launch: fresh LOCALAPPDATA / APPDATA / USERPROFILE under shells/runs (never the owner's), native windows on a private
desktop created here, a foreground guard (any window of the tree becoming foreground kills the run and marks it invalid).
Per launch: first visible window (ms after resume), settled (first 2 s span after the window with tree CPU < 5 % of a core),
USS and private bytes of the tree split UI / host (python*), median of the samples between 25 s and the end.
Each round: Qt first-run, Qt second-run (same profile), Tauri first-run, Tauri second-run; rounds alternate the order.
Only processes whose exe lies inside <shells dir> are terminated; anything else of the tree is left to exit and reported.

--fresh-install: every first-run starts from a new copy of the layout (runs/<round>_<kind>_install), as right after an
install or update: files never opened before, so the antivirus scans them and the disk cache holds nothing of them. Without
it the same layout serves every round, and only the first round's first-run is really cold.
Also per launch, up to `settled`: CPU seconds of the UI process, the host (python*), other children (powershell, ...) and
of the antivirus (MsMpEng.exe, read only - its CPU over the same span, whatever it scanned).
"""
import argparse
import ctypes
import json
import os
import shutil
import statistics
import sys
import threading
import time
from ctypes import wintypes as wt
from pathlib import Path

import psutil

ap = argparse.ArgumentParser()
ap.add_argument("tools")
ap.add_argument("shells")
ap.add_argument("--rounds", type=int, default=3)
ap.add_argument("--seconds", type=float, default=40)
ap.add_argument("--kinds", default="qt,tauri")
ap.add_argument("--fresh-install", action="store_true")
args = ap.parse_args()
sys.path.insert(0, args.tools)
from windows_process import create_suspended  # noqa: E402
from private_profile import isolate  # noqa: E402

SHELLS = Path(args.shells).resolve()
EXES = {"qt": SHELLS / "qt/ABookDesk.exe", "tauri": SHELLS / "tauri/ABook.exe"}
user = ctypes.WinDLL("user32", use_last_error=True)
user.CreateDesktopW.restype = wt.HANDLE
user.CreateDesktopW.argtypes = [wt.LPCWSTR, wt.LPCWSTR, ctypes.c_void_p, wt.DWORD, wt.DWORD, ctypes.c_void_p]
user.CloseDesktop.argtypes = [wt.HANDLE]
user.GetForegroundWindow.restype = wt.HWND
user.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user.IsWindowVisible.argtypes = [wt.HWND]
user.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
ENUM = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user.EnumDesktopWindows.argtypes = [wt.HANDLE, ENUM, wt.LPARAM]
nt = ctypes.WinDLL("ntdll")
nt.NtResumeProcess.argtypes = [wt.HANDLE]


def inside(path) -> bool:
    try:
        return Path(path).resolve().is_relative_to(SHELLS)
    except (OSError, ValueError, TypeError):
        return False


def foreign_abook() -> list[str]:
    found = []
    for p in psutil.process_iter(["name", "exe"]):
        if (p.info["name"] or "").lower() in {"abook.exe", "abookdesk.exe"} and not inside(p.info["exe"]):
            found.append(f"{p.pid} {p.info['exe']}")
    return found


def tree(root: psutil.Process) -> list[psutil.Process]:
    try:
        return [root] + root.children(recursive=True)
    except psutil.NoSuchProcess:
        return []


def antivirus() -> psutil.Process | None:
    return next((p for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "msmpeng.exe"), None)


def cpu_of(process: psutil.Process | None) -> float:
    try:
        t = process.cpu_times()
        return t.user + t.system
    except (psutil.Error, AttributeError):
        return 0.0


def side_of(process: psutil.Process, root_pid: int) -> str:
    if process.pid == root_pid:
        return "ui"
    try:
        return "host" if process.name().lower().startswith("python") else "child"
    except psutil.Error:
        return "child"


def one(kind: str, profile: Path, seconds: float, exe: Path) -> dict:
    if kind == "tauri" and foreign_abook():
        return {"kind": kind, "skipped": "an ABook outside the test folder is running (single-instance would reach it)"}
    env = {k: v for k, v in os.environ.items() if k.upper() not in {"QT_QPA_PLATFORM"}}
    env.update(LOCALAPPDATA=str(profile / "local"), APPDATA=str(profile / "roaming"))
    for sub in ("local", "roaming"):
        (profile / sub).mkdir(parents=True, exist_ok=True)
    env = isolate(env)
    name = f"ABookShells-{os.getpid()}-{time.monotonic_ns()}"
    desk = user.CreateDesktopW(name, None, None, 0, 0x10000000, None)
    if not desk:
        raise ctypes.WinError(ctypes.get_last_error())
    log = open(profile / f"{kind}_stdout.log", "ab")
    av = antivirus()
    av_start = cpu_of(av)
    process = create_suspended([str(exe)], cwd=exe.parent, env=env, log=log, desktop=name, show=1)
    root = psutil.Process(process.pid)
    violations, stop = [], threading.Event()
    pids: set[int] = {process.pid}

    def guard():
        while not stop.is_set():
            hwnd = user.GetForegroundWindow()
            pid = wt.DWORD()
            user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in pids:
                violations.append(time.time())
                process.kill()
            stop.wait(0.01)

    threading.Thread(target=guard, daemon=True).start()
    if nt.NtResumeProcess(wt.HANDLE(int(process._handle))) != 0:
        raise RuntimeError("resume failed")
    start = time.perf_counter()
    first_window = settled = None
    cpu_hist: list[tuple[float, float]] = []
    # Highest CPU seen per process (a child that exits keeps what it used) and its side; summed at `settled`.
    seen: dict[int, tuple[str, float]] = {}
    at_settled: dict[str, float] = {}
    samples = []
    next_mem = 0.0
    while (now := time.perf_counter() - start) < seconds and process.poll() is None:
        procs = tree(root)
        pids.update(p.pid for p in procs)
        if first_window is None:
            hits = []

            @ENUM
            def each(hwnd, _):
                pid = wt.DWORD()
                user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                rect = wt.RECT()
                if pid.value in pids and user.IsWindowVisible(hwnd) and user.GetWindowRect(hwnd, ctypes.byref(rect)) \
                        and rect.right - rect.left > 300:
                    hits.append(hwnd)
                return True
            user.EnumDesktopWindows(desk, each, 0)
            if hits:
                first_window = now
        for p in procs:
            used = cpu_of(p)
            side = seen[p.pid][0] if p.pid in seen else side_of(p, process.pid)
            seen[p.pid] = (side, max(used, seen.get(p.pid, (side, 0.0))[1]))
        cpu = sum(used for _side, used in seen.values())
        cpu_hist.append((now, cpu))
        if first_window is not None and settled is None:
            old = [c for t, c in cpu_hist if now - t >= 2.0]
            if old and now - first_window >= 2.0 and (cpu - old[-1]) < 0.05 * 2.0:
                settled = now - 2.0
                for side in ("ui", "host", "child"):
                    at_settled[side] = round(sum(used for s, used in seen.values() if s == side), 2)
                at_settled["antivirus"] = round(cpu_of(av) - av_start, 2) if av else None
        if now >= next_mem:
            next_mem = now + 1.0
            row = {"t": round(now, 2), "ui_uss": 0, "host_uss": 0, "ui_private": 0, "host_private": 0, "n": len(procs)}
            for p in procs:
                try:
                    full = p.memory_full_info()
                    side = "host" if p.name().lower().startswith("python") else "ui"
                    row[f"{side}_uss"] += full.uss
                    row[f"{side}_private"] += full.private
                except psutil.Error:
                    pass
            samples.append(row)
        time.sleep(0.25)
    stop.set()
    exited_early = process.poll() is not None and not violations
    names = sorted({p.name() for p in tree(root) if p.is_running()})
    left = []
    for p in reversed(tree(root)):
        try:
            if inside(p.exe()):
                p.kill()
            else:
                left.append(p)
        except psutil.Error:
            pass
    process.wait(10)
    gone, alive = psutil.wait_procs(left, timeout=15)
    log.close()
    user.CloseDesktop(desk)
    late = [r for r in samples if r["t"] >= 25]

    def med(key):
        return round(statistics.median(r[key] for r in late) / 1e6, 1) if late else None
    return {"kind": kind, "first_window_ms": None if first_window is None else round(first_window * 1000),
            "settled_ms": None if settled is None else round(settled * 1000), "ui_uss_mb": med("ui_uss"),
            "host_uss_mb": med("host_uss"), "ui_private_mb": med("ui_private"), "host_private_mb": med("host_private"),
            "cpu_s_to_settled": at_settled, "processes": names, "exited_early": exited_early,
            "foreground_violations": len(violations), "left_running": [f"{p.pid} {p.name()}" for p in alive],
            "samples": samples}


runs = SHELLS / "runs" / time.strftime("%H%M%S")
results = []
for r in range(args.rounds):
    order = [k for k in (["qt", "tauri"] if r % 2 == 0 else ["tauri", "qt"]) if k in args.kinds.split(",")]
    for kind in order:
        profile = runs / f"r{r}_{kind}"
        exe = EXES[kind]
        if args.fresh_install:
            install = runs / f"r{r}_{kind}_install"
            shutil.copytree(exe.parent, install)
            exe = install / exe.name
        for launch in ("first", "second"):
            res = one(kind, profile, args.seconds, exe)
            res.update(round=r, launch=launch)
            results.append(res)
            print(json.dumps({k: v for k, v in res.items() if k != "samples"}, ensure_ascii=False), flush=True)
            time.sleep(3)
(runs / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
print("summary")
for kind in ("qt", "tauri"):
    for launch in ("first", "second"):
        rows = [x for x in results if x["kind"] == kind and x["launch"] == launch and not x.get("skipped")
                and not x["foreground_violations"]]
        if not rows:
            continue

        def m(key):
            vals = [x[key] for x in rows if x[key] is not None]
            return statistics.median(vals) if vals else None
        print(kind, launch, len(rows), "window", m("first_window_ms"), "settled", m("settled_ms"), "ui_uss", m("ui_uss_mb"),
              "host_uss", m("host_uss_mb"), "ui_private", m("ui_private_mb"), "host_private", m("host_private_mb"))
        for side in ("ui", "host", "child", "antivirus"):
            vals = [x["cpu_s_to_settled"].get(side) for x in rows if x["cpu_s_to_settled"].get(side) is not None]
            print(f"   cpu_s {side}", statistics.median(vals) if vals else None, vals)
