"""Start the packaged app the way an installed copy starts: from a folder with no source tree above it.

smoke_dist.py starts dist/ABookDesk.exe in place, where Backend finds the source tree and its runtime Python. Here dist/
(with resources/python + resources/app from scripts/build_windows_qt.ps1) is copied to a temporary folder first, so the
host can only come from resources/. The app runs with ABOOK_SMOKE_EXIT=host: 0 once the first frame is drawn AND the host
is Ready, 5 when the host failed. The host must have run from the copy's resources/python.

smoke_packaged.py <dist> [--seconds 120]
"""
import argparse
import shutil
import sys
import tempfile
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
from smoke_dist import report, run  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dist", type=Path)
    ap.add_argument("--seconds", type=float, default=120)
    args = ap.parse_args()
    dist = args.dist.resolve()
    for need in ("ABookDesk.exe", "resources/python/pythonw.exe", "resources/app/abook/webui/host.py"):
        if not (dist / need).is_file():
            print(f"SMOKE_FAIL {need} is missing from {dist} (scripts/build_windows_qt.ps1 builds resources/)")
            return 1
    copy = Path(tempfile.mkdtemp(prefix="abook-packaged-"))
    try:
        if any((parent / "abook/webui/host.py").is_file() for parent in copy.parents):
            print(f"SMOKE_FAIL {copy} lies under a source tree; the host would not come from resources/")
            return 1
        app = copy / "ABook"
        shutil.copytree(dist, app)
        code, text, children = run(app / "ABookDesk.exe", args.seconds, smoke="host")
        python = (app / "resources/python").resolve()
        hosts = sorted(c for c in children if Path(c).name.lower().startswith("python"))
        for line in text.splitlines():
            if line.startswith("SMOKE_HOST_FAILED") or "SMOKE_HOST_FAILED" in line:
                print("SMOKE_HOST", line)
        if code == 5:
            print("SMOKE_FAIL the host did not start from resources/")
            return 1
        result = report(code, text, args.seconds)
        if result:
            return result
        if not hosts or any(not Path(h).resolve().is_relative_to(python) for h in hosts):
            print(f"SMOKE_FAIL the host ran from {hosts or 'nowhere'}, not from {python}")
            return 1
        print(f"SMOKE_OK packaged host Ready from {python}")
        return 0
    finally:
        # The host exits when its pipe closes; anything still running from the copy is ours and only ours.
        left = []
        for process in psutil.process_iter(["exe"]):
            try:
                if process.info["exe"] and Path(process.info["exe"]).resolve().is_relative_to(copy.resolve()):
                    left.append(process)
            except (psutil.Error, OSError, ValueError):
                pass
        _gone, alive = psutil.wait_procs(left, timeout=10)
        for process in alive:
            process.kill()
        psutil.wait_procs(alive, timeout=5)
        shutil.rmtree(copy, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
