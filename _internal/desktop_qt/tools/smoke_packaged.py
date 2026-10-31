"""Start the packaged app the way an installed copy starts: from a folder with no source tree above it.

smoke_dist.py starts dist/ABookDesk.exe in place, where Backend finds the source tree and its runtime Python. Here dist/
(with resources/python + resources/app from scripts/build_windows_qt.ps1) is copied to a temporary folder first, so the
host can only come from resources/. The app runs with ABOOK_SMOKE_EXIT=host: 0 once the first frame is drawn AND the host
is Ready, 5 when the host failed. The host must have run from the copy's resources/python.
Then the copy runs again with ABOOK_SMOKE_EXIT=play (smoke_play.py): the Library holds one book whose chapter is a real
440 Hz mp3, it plays through the host + Media Foundation + mixer of the package into a WAV (ABOOK_AUDIO_SINK), and the
WAV must hold that tone. Negative check: the same with a chapter of random bytes must NOT pass.

smoke_packaged.py <dist> [--seconds 120]
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
import smoke_play  # noqa: E402
from smoke_dist import report, run  # noqa: E402


def play(app: Path, work: Path, chapter: bytes, seconds: float):
    """Run the copy `app` with ABOOK_SMOKE_EXIT=play on a Library holding only the test book with `chapter`;
    return (exit code, log, what the sink heard as mono)."""
    root = work / "profile"
    root.mkdir(parents=True)
    smoke_play.library(work / "library", chapter)
    (root / "prefs.json").write_text(json.dumps({"libraryRoot": str(work / "library")}), encoding="utf-8")
    sink = work / "sink.wav"
    code, text, _children = run(app / "ABookDesk.exe", seconds, smoke="play", root=root,
                                extra={"ABOOK_AUDIO_SINK": str(sink), "ABOOK_MUTE": "0"})
    return code, text, smoke_play.read_sink(sink)


def smoke_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if "SMOKE_" in line]


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

        broken = smoke_play.selftest()
        if broken:
            print("SMOKE_FAIL the sound check misjudges its own test signals:", ", ".join(broken))
            return 1
        tone = smoke_play.tone_mp3()
        code, text, heard = play(app, copy / "play", tone, args.seconds)
        for line in smoke_lines(text):
            print("SMOKE_PLAY", line)
        why = smoke_play.verdict(heard)
        if code != 0 or why or "SMOKE_PLAYED" not in text:
            print(f"SMOKE_FAIL the packaged app did not play the Library book (exit {code}; {why or 'sound ok'})")
            return 1
        seconds, frequency = smoke_play.heard(heard)
        # Negative check: a chapter of random bytes (its hash matches, so it imports) must not pass, or the run above proves nothing.
        bad_code, bad_text, bad_heard = play(app, copy / "play-broken", os.urandom(len(tone)), 30)
        for line in smoke_lines(bad_text):
            print("SMOKE_PLAY_BROKEN", line)
        bad_why = smoke_play.verdict(bad_heard)
        if bad_code == 0 or bad_why is None:
            print(f"SMOKE_FAIL a broken chapter passed too (exit {bad_code}; {bad_why or 'sound ok'}) - the play check proves nothing")
            return 1
        print(f"SMOKE_OK packaged Library book played: {seconds:.1f} s at {frequency:.0f} Hz heard; broken chapter: exit {bad_code}, "
              f"{bad_why}")
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
