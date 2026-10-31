"""Run TrayProbe (tools/tray_probe.cpp) against the real Explorer and record what the Win32 tray code actually gets back.

`shell` runs on the owner's desktop because Shell_NotifyIcon finds the taskbar by window lookup, and window lookup is per desktop;
the icon is hidden from NIM_ADD on (NIF_STATE + NIS_HIDDEN forced by the probe), no window is ever shown. `menu` draws a real popup
menu, so it runs only on a never-switched desktop (guarded_process.run_guarded). HKCU\\Control Panel\\NotifyIconSettings is read
before and after (read only) to show what Explorer records about the probe.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import winreg

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from guarded_process import run_guarded  # noqa: E402

SETTINGS = r"Control Panel\NotifyIconSettings"


def notify_icon_settings():
    entries = {}
    try:
        root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, SETTINGS)
    except OSError:
        return entries
    with root:
        for i in range(winreg.QueryInfoKey(root)[0]):
            name = winreg.EnumKey(root, i)
            values = {}
            with winreg.OpenKey(root, name) as key:
                for j in range(winreg.QueryInfoKey(key)[1]):
                    value, data, _kind = winreg.EnumValue(key, j)
                    values[value] = data.hex() if isinstance(data, bytes) else data
            entries[name] = values
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=HERE.parent / "build" / "TrayProbe.exe")
    parser.add_argument("--qt-bin", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PATH=f"{args.qt_bin};{os.environ['PATH']}")
    before = notify_icon_settings()
    shell = subprocess.run([str(args.exe), "shell", str(args.out / "shell.json")], env=env, cwd=args.out,
                           creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True, text=True, timeout=120)
    after = notify_icon_settings()
    guarded = {}
    for mode in ("menu", "menu-plain"):
        with open(args.out / f"{mode}.log", "w", encoding="utf-8") as log:
            guarded[mode] = run_guarded([str(args.exe), mode, str(args.out / mode)], cwd=args.out, env=env, log=log, timeout=120)
    ours = str(args.exe).lower()
    report = {
        "shell_exit": shell.returncode, "shell_stderr": shell.stderr[-2000:],
        "menu_guard": guarded,
        "notify_icon_settings": {
            "before": len(before), "after": len(after),
            "added": {k: v for k, v in after.items() if k not in before},
            "probe_entries": {k: v for k, v in after.items() if str(v.get("ExecutablePath", "")).lower() == ours},
            "abook_entries": {k: v for k, v in after.items() if "abook" in str(v.get("ExecutablePath", "")).lower()},
        },
    }
    (args.out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"shell_exit": shell.returncode, "menu_exit": [g["exit_code"] for g in guarded.values()],
                      "settings_added": len(report["notify_icon_settings"]["added"])}))


if __name__ == "__main__":
    main()
