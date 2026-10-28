"""Serial, resumable owner-safe evidence collection after the guarded final build.

Run with the owner's pinned Python -X utf8. No audio is ever sent to a device by VoiceRender.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from guarded_process import run_guarded
from hidden_suite import wait_for_machine
from voice_ab import prepare_fixture

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/voicemix-evidence"


def note(message):
    print(message, flush=True)
    with (ROOT / "PROGRESS.md").open("a", encoding="utf-8", newline="\n") as stream:
        stream.write("- " + message + "\n")


def call(script, *args):
    log = OUT / ("validation-" + script + ".log")
    print("START", script, args, flush=True)
    with log.open("wb") as stream:
        code = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "tools" / script), *args], stdout=stream, stderr=subprocess.STDOUT,
                              creationflags=subprocess.CREATE_NO_WINDOW).returncode
    print(log.read_text(encoding="utf-8", errors="replace")[-2400:], flush=True)
    if code: raise RuntimeError(f"{script}: {code}; {log}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", help="full guarded build label; omit to continue already-built measurements")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--offline-only", action="store_true", help="build/signal checks while AC-only playback measurements are blocked")
    ap.add_argument("--playback-only", action="store_true", help="collect current scheduling evidence without repeating unchanged offline decoder renders")
    ap.add_argument("--abc", action="store_true", help="include the preserved local event/30 ms build")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.build:
        call("build_hidden.py", args.build)
        note(f"Voice final full guarded build {args.build}: exit 0; see build/hidden-evidence/build-{args.build}.log and -audit.json.")
    fixture = prepare_fixture()
    hidden = ROOT / "build/hidden-evidence/voicemix.json"
    exe_hash = hashlib.sha256((ROOT / "dist/ABookDesk.exe").read_bytes()).hexdigest()
    saved = json.loads(hidden.read_bytes()) if args.resume and hidden.exists() else []
    if not args.offline_only:
        if not saved or not all(r.get("clock_pass") and r.get("exe_sha256") == exe_hash for r in saved):
            call("hidden_suite.py", "--label", "voicemix", "--rounds", "1", "--offscreen", "--require-mixer", "--fixture-source", str(fixture))
            note("Voice hidden 120 s check passed; raw evidence build/hidden-evidence/voicemix.json.")
        call("voice_ab.py", "--rounds", "4", *(["--resume"] if args.resume else []), *(["--abc"] if args.abc else []))
        note("Voice A/B four alternating rounds complete: build/voicemix-evidence/ab.json, raw-*-*.json; ABOOK_MUTE=1, AC, no foreground events.")
    if args.playback_only:
        return
    wait = wait_for_machine()
    book = next(p for p in (fixture / "library").rglob("book.json") if json.loads(p.read_bytes()).get("title") == "Chuyện Thử Nghe")
    data = json.loads(book.read_bytes())
    music = book.parent / next(iter(data["music"]["tracks"]))
    qt = Path("D:/Novels/native_desk_proto/qt611/6.10.3/msvc2022_64")
    env = dict(os.environ, ABOOK_MUTE="1", QT_QPA_PLATFORM="offscreen", PATH=str(qt / "bin") + os.pathsep + os.environ["PATH"])
    with (OUT / "offline-render.log").open("wb") as stream:
        result = run_guarded([str(ROOT / "build/VoiceRender.exe"), "D:/Novels/Audiobooks/book2/_book/001.mp3", str(music), str(OUT / "chapter")],
                             cwd=ROOT, env=env, log=stream, timeout=300)
    (OUT / "offline-render-audit.json").write_text(json.dumps(dict(result, machine_wait=wait), indent=2), encoding="utf-8", newline="\n")
    if result["exit_code"]: raise RuntimeError(result)
    note("Offline chapter PCM rendered at 1x/1.5x with music crossfades, plus SourceReader reference. This is signal evidence, NOT an MFMediaEngine/WASAPI loopback capture. See build/voicemix-evidence/chapter.json.")
    call("analyze_voice.py")
    note("Offline signal analysis completed: build/voicemix-evidence/signal.json.")


if __name__ == "__main__": main()
