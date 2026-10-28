"""Native Qt/driver/network diagnostic; never mix these costs into A/B timings.

The app remains on the never-switched desktop at x=-10000 with the pre-resume
foreground guard. Thread-pool ETW is optional and never requests elevation.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from hidden_suite import wait_for_machine

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/idlecpu-evidence/native"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    wait = wait_for_machine()
    name = f"ABookIdle-{os.getpid()}-{time.time_ns()}"
    command = ["logman", "create", "trace", name, "-o", str(OUT / "threadpool.etl"),
               "-p", "{C861D0E2-A2C1-4D36-9F9C-970BAB943A12}", "0xffffffffffffffff", "5", "-max", "64", "-ets"]
    def call(args):
        got = subprocess.run(args, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return dict(command=args, exit_code=got.returncode, stdout=got.stdout, stderr=got.stderr)
    trace = call(command)
    trace["machine_wait"] = wait
    (OUT / "etw.json").write_text(json.dumps(trace, indent=2), encoding="utf-8", newline="\n")
    print("ETW", trace["exit_code"], trace["stdout"].strip(), flush=True)
    env = dict(os.environ, ABOOK_CAPTURE_MODULES="1")
    try:
        code = subprocess.call(["D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe", "-X", "utf8", str(ROOT / "tools/idle_ab.py"),
            "--rounds", "1", "--probe-b", "--native", "--network-trace", "--evidence", str(OUT)],
            env=env, creationflags=subprocess.CREATE_NO_WINDOW)
    finally:
        if trace["exit_code"] == 0:
            trace["stop"] = call(["logman", "stop", name, "-ets"])
            (OUT / "etw.json").write_text(json.dumps(trace, indent=2), encoding="utf-8", newline="\n")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
