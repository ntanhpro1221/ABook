"""Start the packaged app once on a never-switched desktop and fail if Main.qml does not load.

QML tests run against stub ABook singletons, so a type that only the real app registers can
break Main.qml (exit 3 from objectCreationFailed) while every test passes. build.bat runs
this after windeployqt. With ABOOK_SMOKE_EXIT=1 the app quits after its first frame: 0 when
the engine reported no warning, 4 when it did. The app gets its own empty LOCALAPPDATA/APPDATA,
never the user's.

smoke_dist.py <dist/ABookDesk.exe> [--seconds 60]
"""
import argparse
import ctypes
import os
import re
import sys
import tempfile
from ctypes import wintypes as wt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from windows_process import create_suspended  # noqa: E402

# A QML engine error that leaves part of the window dead even when Main itself loads.
FATAL = re.compile(r"is not a type|is not installed|ReferenceError|TypeError|Cannot assign|"
                   r"Type \S+ unavailable|module \S+ plugin|failed to load component|Component is not ready")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--seconds", type=float, default=60)
    args = ap.parse_args()
    exe = args.exe.resolve()
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.CreateDesktopW.restype = wt.HANDLE
    user.CreateDesktopW.argtypes = [wt.LPCWSTR, wt.LPCWSTR, ctypes.c_void_p, wt.DWORD, wt.DWORD, ctypes.c_void_p]
    user.CloseDesktop.argtypes = [wt.HANDLE]
    nt = ctypes.WinDLL("ntdll")
    nt.NtResumeProcess.argtypes = [wt.HANDLE]
    nt.NtResumeProcess.restype = wt.LONG
    with tempfile.TemporaryDirectory(prefix="abook-smoke-") as tmp:
        root = Path(tmp)
        for name in ("local", "roaming", "temp"):
            (root / name).mkdir()
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("QT_", "QML", "ABOOK_"))}
        env.update(LOCALAPPDATA=str(root / "local"), APPDATA=str(root / "roaming"), TEMP=str(root / "temp"),
                   TMP=str(root / "temp"), ABOOK_PREFERENCES=str(root / "prefs.json"), ABOOK_MUTE="1", ABOOK_SMOKE_EXIT="1",
                   QT_FORCE_STDERR_LOGGING="1")
        name = f"ABookSmoke-{os.getpid()}"
        desk = user.CreateDesktopW(name, None, None, 0, 0x10000000, None)
        if not desk:
            raise ctypes.WinError(ctypes.get_last_error())
        log_path = root / "app.log"
        try:
            with log_path.open("wb") as log:
                process = create_suspended([str(exe), "-qwindowgeometry", "1280x800+0+0"], env=env,
                                           cwd=str(exe.parent), log=log, desktop=name, show=4)
            if nt.NtResumeProcess(wt.HANDLE(int(process._handle))) != 0:
                process.kill()
                raise RuntimeError("cannot resume the smoke process")
            try:
                code = process.wait(args.seconds)
            except Exception:
                code = None
            if code is None:
                process.kill()
                process.wait(10)
            text = log_path.read_text(encoding="utf-8", errors="replace")
        finally:
            user.CloseDesktop(desk)
    fatal = [line for line in text.splitlines() if FATAL.search(line)]
    for line in text.splitlines():
        if line.startswith("qrc:/"):
            print("SMOKE_QML", line)
    if code is None:
        print(f"SMOKE_FAIL no first frame within {args.seconds:g} s")
        return 1
    if code != 0:
        print(f"SMOKE_FAIL app exited with {code} (3 = Main.qml did not load, 4 = QML warnings)")
        return 1
    if fatal:
        print(f"SMOKE_FAIL {len(fatal)} QML error line(s)")
        return 1
    print("SMOKE_OK Main.qml loaded and drew its first frame without QML warnings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
