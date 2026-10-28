"""Four alternating A/B pairs, owner-safe and machine-serialized before EVERY run.

Uses the exact same embedded player scenario in both binaries (20 s minimized).
Stores raw samples as well as per-round figures; never changes the owner's library/settings.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import argparse
import re
import uuid
import measure
from hidden_suite import wait_for_machine
from measure_mini import fixture_at, reset

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/idlecpu-evidence"


class SharedMachineBusy(RuntimeError):
    pass


def prepare_fixture():
    fixture = fixture_at(OUT / "fixture", Path("D:/Novels/native_desk_proto/deskqt_fixture_mp3"))
    source = Path("D:/Novels/Audiobooks/book2/_book/001.mp3")
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    for path in (fixture / "library").rglob("book.json"):
        data = json.loads(path.read_bytes())
        if data.get("title") != "Chuyện Thử Nghe": continue
        for chapter in data["chapters"]:
            target = path.parent / chapter["file"]
            if hashlib.sha256(target.read_bytes()).hexdigest() != sha: shutil.copyfile(source, target)
            chapter.update(duration=750.96, size=source.stat().st_size, sha256=sha)
            for cue in data.get("music", {}).get("chapters", {}).get(str(chapter["id"]), []): cue["end"] = 750.96
            data.get("package", {}).get("files", {})[chapter["file"]] = dict(size=source.stat().st_size, sha256=sha)
        data["duration"] = sum(ch["duration"] for ch in data["chapters"])
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8", newline="\n")
    (OUT / "chapter-input.json").write_text(json.dumps(dict(source=str(source), sha256=sha, bytes=source.stat().st_size, rate=48000, channels=1), indent=2), encoding="utf-8", newline="\n")
    # Both immutable benchmark binaries open the saved chapter. Pin that state to chapter 1.
    base = fixture / "_base/listening.json"
    listening = json.loads(base.read_bytes())
    for record in listening["records"].values():
        state = record.get("state", {})
        state["chapters"] = {}
        if "last" in state:
            state["last"].update(chapterId=1, seconds=0)
    base.write_text(json.dumps(listening, ensure_ascii=False), encoding="utf-8", newline="\n")
    return fixture


def summarize_threads(got, begin, end):
    series = [(t, entries) for t, entries in got["thread_samples"] if begin <= t <= end]
    if len(series) < 20: raise RuntimeError("Missing thread samples")
    first, last = series[0], series[-1]
    dt = (last[0] - first[0]) / 1000
    old = {x["id"]: x for x in first[1]}
    rows = []
    for x in last[1]:
        if x["id"] not in old: continue
        prev = old[x["id"]]
        rows.append(dict(id=x["id"], name=x["name"], cpu_core_pct=(x["cpu_s"] - prev["cpu_s"]) / dt * 100,
            cycles_core_pct=(x["cycles"] - prev["cycles"]) / (measure._TSC_MHZ * 1e6 * dt) * 100,
            scheduler_dispatches_s=(x["context_switches"] - prev["context_switches"]) / dt,
            identity={k: v for k, v in x.items() if k not in {"cpu_s", "cycles", "context_switches"}}))
    return sorted(rows, key=lambda x: x["cycles_core_pct"], reverse=True)


def run(rounds, resume=False, abc=False, probe=False, native=False):
    OUT.mkdir(parents=True, exist_ok=True)
    fixture = prepare_fixture()
    books = json.loads((fixture / "audio_books.json").read_bytes())
    qt = Path("D:/Novels/native_desk_proto/qt611/6.10.3/msvc2022_64")
    local = OUT / "ab-local"
    local.mkdir(exist_ok=True)
    env = {"ABOOK_PREFERENCES": str(fixture / "prefs.json"), "ABOOK_HOST_PYTHON": "D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe",
           "ABOOK_HOST_APP": str(ROOT.parent), "ABOOK_BENCH_SCENARIO": "player", "ABOOK_BENCH_BOOK": books["a"],
           "ABOOK_MUTE": "1", "ABOOK_AUDIO_TRACE": "1", "ABOOK_IDLE_AUDIT": "1", "ABOOK_SMTC": "1", "LOCALAPPDATA": str(local),
           "QT_SCALE_FACTOR": "1", "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
           "ABOOK_BENCH_HIDDEN_DESKTOP": "1", "QT_QPA_FONTDIR": str(ROOT / "fonts"),
           "QT_QPA_PLATFORM_PLUGIN_PATH": str(qt / "plugins/platforms"), "PATH": str(qt / "bin") + os.pathsep + os.environ["PATH"]}
    if native:
        env.update(QT_QPA_PLATFORM="windows", QT_QUICK_BACKEND="rhi")
    rows = json.loads((OUT / "ab.json").read_bytes()) if resume and (OUT / "ab.json").exists() else []
    for round in range(1, rounds + 1):
        variants = [("A", OUT / "baseline/ABookDesk.exe"), ("B", ROOT / "dist/ABookDesk.exe")]
        if probe == "A": variants = variants[:1]
        if probe == "B":
            variants = [("B", ROOT / "build/ABookDesk.exe")]
            env["ABOOK_IDLE_AUDIT"] = "1"
        if abc: variants.append(("C", OUT / "event30/ABookDesk.exe"))
        if round % 2 == 0: variants.reverse()
        for label, exe in variants:
            previous = next((r for r in rows if r["round"] == round and r["label"] == label), None)
            if previous:
                if previous["exe_sha256"] != hashlib.sha256(exe.read_bytes()).hexdigest(): raise RuntimeError("Cannot resume A/B after a binary change")
                print("KEEP", round, label, flush=True)
                continue
            wait = wait_for_machine()
            reset(fixture)
            (fixture / "listening.json.journal").write_bytes(b"")
            run_local = local / f"{round}-{label}-{uuid.uuid4().hex[:8]}"
            run_local.mkdir()
            env["LOCALAPPDATA"] = str(run_local) # no progress outbox or UI settings may leak from A to B
            print("START", round, label, "machine-clear", wait["seconds"], flush=True)
            got = measure.launch(exe.resolve(), env, True, timeout_seconds=100)
            got.update(round=round, label=label, machine_wait=wait, local_appdata=str(run_local), exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest())
            (OUT / f"raw-{round}-{label}.json").write_text(json.dumps(got, indent=1), encoding="utf-8", newline="\n")
            if got.get("app_log"):
                shutil.copyfile(got["app_log"], OUT / f"{round}-{label}.app.log")
            if not got.get("ok") or got["exit_code"] or got["forced_termination"] or got["foreground_events"]:
                raise RuntimeError(got.get("why", "Unclean run"))
            if got.get("shared_busy"):
                excluded = OUT / "excluded" / f"{round}-{label}-{uuid.uuid4().hex[:8]}"
                excluded.mkdir(parents=True)
                shutil.copyfile(OUT / f"raw-{round}-{label}.json", excluded / "raw.json")
                shutil.copyfile(OUT / f"{round}-{label}.app.log", excluded / "app.log")
                raise SharedMachineBusy("Shared machine became busy; retain raw attempt but exclude this round")
            if not got.get("power_samples") or any(ac != 1 for _t, ac in got["power_samples"]): raise RuntimeError("AC lost during measurement")
            ev = {name: t + got["d"]["epoch_offset_ms"] for t, name in got["d"]["events"]}
            begin, end = ev["min_begin"] + 5000, ev["min_end"]
            samples = [(t, p, c) for t, p, c in got["samples"] if begin <= t <= end]
            memory = [(t, p, w, c) for t, p, w, c in got["memory_samples"] if begin <= t <= end]
            if len(memory) < 20 or len(samples) < 20: raise RuntimeError("Insufficient steady samples")
            row = dict(round=round, label=label, steady_s=(memory[-1][0] - memory[0][0]) / 1000,
                cpu_core_pct=(memory[-1][3] - memory[0][3]) / (memory[-1][0] - memory[0][0]) * 100000,
                cycles_core_pct=(samples[-1][2] - samples[0][2]) / (samples[-1][0] - samples[0][0]) * 100,
                private_commit_mb=statistics.median(x[1] for x in memory), working_set_mb=statistics.median(x[2] for x in memory),
                private_working_set_mb=statistics.median(x[1] for x in samples), foreground_events=got["foreground_events"],
                exe_sha256=got["exe_sha256"], mixer_events=[n for _t, n in got["d"]["events"] if n.startswith("mix_")])
            row["battery_status_at_launch"] = got["battery_status_at_launch"]
            row["battery_status_at_end"] = got["battery_status_at_end"]
            row["machine_wait_s"] = got["machine_wait"]["seconds"]
            row["threads"] = summarize_threads(got, begin, end)
            trace = Path(got["app_log"]).read_text(encoding="utf-8", errors="replace")
            wakes = [(int(t), int(n), int(tid)) for t, n, tid in re.findall(r"mix_wakes epoch_ms=(\d+) count=(\d+) thread=(\d+)", trace) if begin <= int(t) <= end]
            row["render_wakes_s"] = (wakes[-1][1] - wakes[0][1]) / ((wakes[-1][0] - wakes[0][0]) / 1000) if len(wakes) > 1 else None
            row["render_thread_id"] = wakes[0][2] if wakes else None
            reader = [(int(t), int(n), int(tid)) for t, n, tid in re.findall(r"reader_wakes epoch_ms=(\d+) count=(\d+) thread=(\d+)", trace) if begin <= int(t) <= end]
            row["reader_wakes_s"] = (reader[-1][1] - reader[0][1]) / ((reader[-1][0] - reader[0][0]) / 1000) if len(reader) > 1 else None
            main_wakes = [int(n) for n in re.findall(r"idle_main_dispatcher_wakes=(\d+)", trace)]
            row["main_dispatcher_iterations_s"] = max(main_wakes) / ((ev["restore_begin"] - ev["min_begin"]) / 1000) if main_wakes else None
            row["main_timer_events"] = re.findall(r"idle_timer (.+) count=(\d+)", trace)
            row["chapter_source"] = "chapter 1, saved-state fixture reset to 0 s"
            if "mix_playing" not in row["mixer_events"] or "mix_failed" in row["mixer_events"]:
                raise RuntimeError("Music did not play through the mixer")
            rows.append(row)
            (OUT / "ab.json").write_text(json.dumps(rows, indent=2), encoding="utf-8", newline="\n")
            print("RESULT", {k: v for k, v in row.items() if k not in {"threads", "mixer_events"}}, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--setup-only", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--abc", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--probe-b", action="store_true")
    ap.add_argument("--evidence", type=Path, help="separate diagnostic folder; never mix with the final A/B rows")
    ap.add_argument("--network-trace", action="store_true", help="diagnostic only; enables verbose Qt network categories")
    ap.add_argument("--native", action="store_true", help="diagnostic on the never-switched desktop, x=-10000 and foreground guard")
    args = ap.parse_args()
    if args.evidence: OUT = args.evidence.resolve()
    if args.network_trace:
        os.environ["QT_LOGGING_RULES"] = "qt.network.*.debug=true"
        os.environ["QT_MESSAGE_PATTERN"] = "qtclock=%{time yyyy-MM-ddTHH:mm:ss.zzz} tid=%{threadid} %{category} %{message}"
    if args.setup_only: print(prepare_fixture())
    else:
        while True:
            try:
                run(args.rounds, args.resume, args.abc, "B" if args.probe_b else "A" if args.probe else False, args.native)
                break
            except SharedMachineBusy as exc:
                print("REQUEUE", str(exc), flush=True)
                args.resume = True
