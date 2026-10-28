"""Guarded 120 s hidden-playback controls; all evidence stays in this worktree."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

import psutil
import measure
from measure_mini import fixture_at, reset

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "build/hidden-evidence"


def wait_for_machine():
    start = time.time()
    waits = []
    quiet_since = None
    last_notice = None
    ancestors = {p.pid for p in psutil.Process().parents()} | {os.getpid()}
    while True:
        busy = []
        for proc in psutil.process_iter(["pid", "name", "cmdline", "exe"]):
            if proc.pid in ancestors:
                continue
            info = proc.info
            args = info.get("cmdline") or []
            scripts = {Path(a).name.lower() for a in args if a.endswith(".py")}
            name = (info.get("name") or "").lower()
            if (name == "abookdesk.exe" or name.endswith("tests.exe") or
                name in {"cl.exe", "link.exe", "ninja.exe", "cmake.exe", "qmlcachegen.exe", "qmltyperegistrar.exe"} or
                scripts & {"measure.py", "ramrun.py", "measure_mini.py", "hidden_suite.py", "private_worker.py", "voice_ab.py", "voice_validate.py", "idle_ab.py", "idle_hidden.py", "idle2_stage.py", "idle2_profile.py", "build_hidden.py"} or
                any("measure" in s for s in scripts)):
                busy.append(info)
        if not busy:
            if quiet_since is None: quiet_since = time.time()
            if time.time() - quiet_since >= 30:
                return {"seconds": round(time.time() - start, 3), "quiet_seconds": 30, "blocked_samples": waits}
        else:
            quiet_since = None
            waits.append({"time": time.time(), "processes": busy})
            notice = [(p["pid"], p["exe"]) for p in busy]
            if notice != last_notice:
                print("WAIT shared machine:", [(pid, Path(exe).name if exe else None) for pid, exe in notice], flush=True)
                last_notice = notice
        time.sleep(5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--exe", type=Path, default=ROOT / "dist/ABookDesk.exe")
    ap.add_argument("--music-off", action="store_true")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--offscreen", action="store_true")
    ap.add_argument("--require-mixer", action="store_true", help="require real mixer ready/playing markers and no decode/device failure")
    ap.add_argument("--fixture-source", type=Path, default=Path("D:/Novels/native_desk_proto/deskqt_fixture_music"))
    ap.add_argument("--functional-only", action="store_true", help="allow battery for playback correctness only; CPU/RAM samples are not performance evidence")
    args = ap.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    fixture = fixture_at(EVIDENCE / ("fixture-music-off" if args.music_off else "fixture-music"), args.fixture_source)
    for path in (fixture / "library").rglob("edits.json"):
        data = json.loads(path.read_bytes())
        data.setdefault("music", {})["enabled"] = not args.music_off
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8", newline="\n")
    books = json.loads((fixture / "audio_books.json").read_bytes())
    qt = Path("D:/Novels/native_desk_proto/qt611/6.10.3/msvc2022_64")
    local = EVIDENCE / (args.label + "-local")
    local.mkdir(exist_ok=True)
    env = {"ABOOK_PREFERENCES": str(fixture / "prefs.json"),
           "ABOOK_HOST_PYTHON": "D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe",
           "ABOOK_HOST_APP": str(ROOT.parent), "ABOOK_BENCH_SCENARIO": "mini", "ABOOK_BENCH_BOOK": books["a"],
           "ABOOK_MUTE": "1", "ABOOK_AUDIO_TRACE": "1", "ABOOK_SMTC": "1",
           "LOCALAPPDATA": str(local), "QT_SCALE_FACTOR": "1", "ABOOK_BENCH_HIDDEN_DESKTOP": "1",
           "QT_QPA_PLATFORM": "offscreen" if args.offscreen else "windows",
           "QT_QUICK_BACKEND": "software" if args.offscreen else "rhi", "QT_QPA_FONTDIR": str(ROOT / "fonts"),
           "QT_QPA_PLATFORM_PLUGIN_PATH": str(qt / "plugins/platforms"),
           "PATH": str(qt / "bin") + os.pathsep + os.environ["PATH"]}
    rows = []
    for i in range(args.rounds):
        wait = wait_for_machine()
        reset(fixture)
        print("START", args.label, i+1, "machine-clear", wait["seconds"], flush=True)
        got = measure.launch(args.exe.resolve(), env, True, timeout_seconds=190, require_ac=not args.functional_only)
        got.update(label=args.label, run=i+1, machine_wait=wait, exe_sha256=hashlib.sha256(args.exe.read_bytes()).hexdigest())
        if got.get("app_log"):
            log = EVIDENCE / f"{args.label}-{i+1}.app.log"
            shutil.copyfile(got["app_log"], log)
            got["app_log"] = str(log)
        if got.get("ok"):
            events = {n: t for t,n in got["d"]["events"]}
            got["mixer_events"] = [n for _t,n in got["d"]["events"] if n.startswith("mix_")]
            audio = {}
            for n in events:
                if n.startswith("audio:"):
                    _,tag,chapter,position,playing = n.split(":")
                    audio[tag] = dict(chapter=int(chapter), position=float(position), playing=int(playing))
            got["audio"] = audio
            if "hide_end" in audio and "hide_begin" in audio:
                got["hidden_wall_s"] = (events["hide_end"]-events["hide_begin"])/1000
                got["hidden_media_s"] = audio["hide_end"]["position"]-audio["hide_begin"]["position"]
                got["starvation_warnings"] = Path(got["app_log"]).read_text(encoding="utf-8", errors="replace").count("mix_device_empty")
                got["clock_pass"] = (audio["hide_begin"]["chapter"] == audio["hide_end"]["chapter"]
                    and abs(got["hidden_media_s"] - got["hidden_wall_s"]) <= 0.1
                    and got["starvation_warnings"] == 0 and all(v["playing"] == 1 for v in audio.values()))
                if args.require_mixer:
                    got["mixer_pass"] = (any(n.startswith("mix_ready:") for n in got["mixer_events"])
                        and "mix_playing" in got["mixer_events"] and "mix_failed" not in got["mixer_events"])
                    got["clock_pass"] = got["clock_pass"] and got["mixer_pass"]
        rows.append(got)
        (EVIDENCE / f"{args.label}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8", newline="\n")
        print("RESULT", {k:got.get(k) for k in ("label","run","ok","hidden_wall_s","hidden_media_s","clock_pass","why")}, flush=True)
        if got.get("shared_busy"):
            raise RuntimeError("Shared machine became busy; retain raw evidence but do not accept this attempt")
        if not got.get("ok"):
            raise RuntimeError(got.get("why"))  # Never retry a foreground failure.
    assert all(row.get("clock_pass") for row in rows), "Hidden playback must stay within 0.1 s of wall time with zero starvation warnings"
    assert all(row.get("exit_code") == 0 and not row.get("forced_termination") and
               row.get("foreground_events") == 0 for row in rows), "Playback must exit normally under the foreground guard"


if __name__ == "__main__":
    main()
