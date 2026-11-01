"""Run the LF build.bat through a CRLF execution copy for cmd.exe."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time
from hidden_suite import wait_for_machine
from guarded_process import run_guarded

root = Path(__file__).resolve().parents[1]
folder = root / "build/hidden-evidence"
folder.mkdir(parents=True, exist_ok=True)
label = sys.argv[1]
wait = wait_for_machine()
(folder / f"build-{label}-wait.json").write_text(json.dumps(wait, indent=2), encoding="utf-8", newline="\n")
print("BUILD machine-clear", {"seconds": wait["seconds"], "blocked_samples": len(wait["blocked_samples"])}, flush=True)
source = (root / "build.bat").read_text(encoding="utf-8")
source = source.replace("set HERE=%~dp0", "set HERE=" + str(root) + "\\")
if "--compile-only" in sys.argv:
    source = source.split("rem Player unit tests", 1)[0] + "\nexit /b 0\n"
bat = folder / "build-execution.bat"
bat.write_bytes(source.replace("\n", "\r\n").encode("utf-8"))
env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
# --package: build.bat package (dist\resources + packaged smoke, scripts/build_windows_qt.ps1); --installer: + NSIS installer
mode = ["installer"] if "--installer" in sys.argv else ["package"] if "--package" in sys.argv else []
# Guard ceiling per mode, about twice the measured time (`seconds` in build-<label>-audit.json). Cold tree, 01-11: compile +
# QtTests ~1150 s (WidthTests 677 s, the other suites ~77 s); the audio_sink gate of package / installer 385 s (2 runs + strength);
# installer builds before the gate ~1000 s. The old single 1200 s killed a package build inside the gate (prefetch4).
ceiling = 1200 if "--compile-only" in sys.argv else 3600 if mode else 2400
with (folder / f"build-{label}.log").open("wb") as log:
    command = ["cmd.exe", "/d", "/c", str(bat)] + mode
    started = time.monotonic()
    try:
        result = run_guarded(command, cwd=root, env=env, log=log, timeout=ceiling)
    except subprocess.TimeoutExpired:  # the guard killed the tree; the audit still says how far it got
        result = dict(exit_code=124, timed_out=True)
    result.update(seconds=round(time.monotonic() - started, 1), ceiling=ceiling)
(folder / f"build-{label}-audit.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
print("BUILD", result, flush=True)
raise SystemExit(result["exit_code"])
