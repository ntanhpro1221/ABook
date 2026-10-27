"""Run the LF build.bat through a CRLF execution copy for cmd.exe."""
from pathlib import Path
import json
import os
import subprocess
import sys
from hidden_suite import wait_for_machine

root = Path(__file__).resolve().parents[1]
folder = root / "build/hidden-evidence"
folder.mkdir(parents=True, exist_ok=True)
label = sys.argv[1]
wait = wait_for_machine()
(folder / f"build-{label}-wait.json").write_text(json.dumps(wait, indent=2), encoding="utf-8", newline="\n")
print("BUILD machine-clear", wait, flush=True)
source = (root / "build.bat").read_text(encoding="utf-8")
source = source.replace("set HERE=%~dp0", "set HERE=" + str(root) + "\\")
if "--compile-only" in sys.argv:
    source = source.split("rem Player unit tests", 1)[0] + "\nexit /b 0\n"
bat = folder / "build-execution.bat"
bat.write_bytes(source.replace("\n", "\r\n").encode("utf-8"))
env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
with (folder / f"build-{label}.log").open("wb") as log:
    result = subprocess.run(["cmd.exe", "/d", "/c", str(bat)], env=env, stdout=log, stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW)
print("BUILD exit", result.returncode, flush=True)
raise SystemExit(result.returncode)
