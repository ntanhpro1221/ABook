"""Reproduce final minimized-playback tables from retained evidence; launches nothing."""
import hashlib
import json
from pathlib import Path
import re
import statistics
import struct

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/idlecpu-evidence"


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.write_text(value, encoding="utf-8", newline="\n")


def enrich(threads, raw, exe):
    # Early samples can predate the module loader. Recover modules from another
    # thread with the SAME recorded start in this process, never another run.
    known = {x["start_address"]: x for _, entries in raw["thread_samples"]
             for x in entries if x.get("module") and x.get("start_address")}
    main = raw["thread_samples"][0][1][0]
    pe = exe.read_bytes()
    entry = struct.unpack_from("<I", pe, struct.unpack_from("<I", pe, 0x3c)[0] + 40)[0]
    # Validate the recorded primary thread start against the PE entry point.
    image_base = int(main["start_address"], 16) - entry
    assert image_base > 0 and image_base % 65536 == 0
    result = []
    for thread in threads:
        t = dict(thread)
        ident = dict(t["identity"])
        other = known.get(ident.get("start_address"), {})
        for key in ("module", "module_offset", "symbol", "symbol_offset"):
            if key not in ident and key in other:
                ident[key] = other[key]
        if t["id"] == main["id"]:
            t["name"] = t["name"] or "main (baseline unnamed)"
            if not ident.get("module"):
                ident.update(module=str(exe.resolve()), module_offset=hex(entry),
                             module_mapping="primary-thread PE entry-point inference; 64-KiB base aligned")
        t["identity"] = ident
        result.append(t)
    return result


def symbol(ident, symbols):
    key = (Path(ident.get("module", "")).name.lower(), ident.get("module_offset"))
    s = symbols.get(key)
    if not s:
        return "unavailable"
    if s.get("exact"):
        return s["symbol"]
    if s.get("symbol"):
        return "unavailable; nearest export " + s["symbol"] + "+" + s["displacement"]
    return "unavailable (DbgHelp error " + str(s.get("error")) + ")"


def cause(t):
    name, module = t["name"], Path(t["identity"].get("module", "")).name.lower()
    if "audio decode" in name:
        return "condition-variable predicate: low ring, source-ready, or control; no periodic wait"
    if "audio render" in name:
        return "narration WASAPI event/control; music-only mixer uses padding-based deadline"
    if "cover decode" in name:
        return "cover job queue / Qt pool idle-expiry timeout; no steady decode CPU observed"
    if "main" in name:
        return "socket completions, queued audio/control events, 5-s progress persistence, Qt housekeeping"
    if "NetworkAccessManager" in name:
        return "HTTP socket/completion/timeout events; bookmarks every 10 s and ranged audio reads remain; exact dispatch split unmeasured"
    if module == "nvwgf2umx.dll":
        return "NVIDIA internal worker; recurring scheduling observed, private callback/wait cause unavailable"
    if module == "ntdll.dll":
        return "Windows pool callback dispatch; specific callback unavailable (ETW access denied)"
    if module == "mswsock.dll":
        return "Winsock asynchronous socket notifications"
    if module == "winmm.dll":
        return "Windows multimedia timer service; no steady dispatch observed"
    if module == "crypt32.dll":
        return "crypt32 ILS wait worker; internal event/completion, not app polling"
    if module == "combase.dll":
        return "COM RPC worker; incoming RPC/completion"
    if "QSGRenderThread" in name:
        return "Qt scene-graph render requests; no steady dispatch in native probe"
    if "PixmapReader" in name:
        return "Qt image request queue; no steady dispatch observed"
    if "QQmlThread" in name or "pooled" in name:
        return "Qt queued job/event; no steady dispatch observed"
    return "internal queued event; exact wake cause unavailable"


def include_transient_threads(row, raw, begin, end):
    samples = [(at, entries) for at, entries in raw["thread_samples"] if begin <= at <= end]
    dt = (samples[-1][0] - samples[0][0]) / 1000
    initial = {t["id"]: t for t in samples[0][1]}
    final = {t["id"]: t for t in samples[-1][1]}
    seen = {t["id"]: t for _, ts in samples for t in ts}
    already = {t["id"] for t in row["threads"]}
    # Recover the SAME run's cycle normalization from an existing stable row.
    hz = next((final[t["id"]]["cycles"] - initial[t["id"]]["cycles"]) / dt / (t["cycles_core_pct"] / 100)
              for t in row["threads"] if t["cycles_core_pct"] > 0)
    for tid in sorted(seen.keys() - already):
        last = seen[tid]
        old = initial.get(tid, dict(cpu_s=0, cycles=0, context_switches=0))
        note = "partial lifetime; lower bound through last sample" if tid not in final else "created during steady window"
        row["threads"].append(dict(id=tid, name=last["name"],
            cpu_core_pct=(last["cpu_s"] - old["cpu_s"]) / dt * 100,
            cycles_core_pct=(last["cycles"] - old["cycles"]) / dt / hz * 100,
            scheduler_dispatches_s=(last["context_switches"] - old["context_switches"]) / dt,
            coverage=note, identity={k: v for k, v in last.items() if k not in {"cpu_s", "cycles", "context_switches"}}))
    row["threads"].sort(key=lambda x: x["cycles_core_pct"], reverse=True)


def table(title, rows, metrics, symbols):
    lines = ["## " + title, "", "CPU is time / wall time, percent of ONE core. Dispatch/s includes preemption; it is not a wake counter.", "",
             "| TID | Name / owner | CPU % | Cycles/TSC % | Dispatch/s | Counted waits/s | Win32 start | Module + RVA | DbgHelp symbol | What runs it |",
             "|---|---|---:|---:|---:|---:|---|---|---|---|"]
    for t in rows:
        i = t["identity"]
        module = Path(i.get("module", "unknown")).name + "+" + i.get("module_offset", "unknown")
        label = t["name"] or Path(i.get("module", "unknown")).name + " worker"
        if t.get("coverage"):
            label += " (" + t["coverage"] + ")"
        wake = "unmeasured"
        if "audio render" in label and metrics.get("render_wakes_s") is not None:
            wake = f'{metrics["render_wakes_s"]:.3f}'
        elif "audio decode" in label and metrics.get("reader_wakes_s") is not None:
            wake = f'{metrics["reader_wakes_s"]:.3f}'
        elif "main" in label and metrics.get("main_dispatcher_iterations_s") is not None:
            wake = f'{metrics["main_dispatcher_iterations_s"]:.3f} dispatcher iterations'
        cells = [t["id"], label, f'{t["cpu_core_pct"]:.6f}', f'{t["cycles_core_pct"]:.6f}',
                 f'{t["scheduler_dispatches_s"]:.3f}', wake, i.get("start_address", "unknown"), module,
                 symbol(i, symbols), cause(t)]
        lines.append("| " + " | ".join(str(x).replace("|", "\\|") for x in cells) + " |")
    return "\n".join(lines) + "\n\n"


def timer_inventory():
    notes = {
        "AdvancedStorage.qml": "UI storage polling gated by UiActivity; refresh on resume.",
        "AdvancedUpdate.qml": "One-shot timeout for an actual update request; host update result is event-driven.",
        "CaptionButton.qml": "Hover latch polling stops on hidden visibility (latched cleared).",
        "CoverView.qml": "One-shot image-size debounce; no periodic poll.",
        "EditBookMyMusic.qml": "One-shot row purge; analysis/download polling gated by UiActivity, reload on resume.",
        "Main.qml": "One-shot delayed NowPlaying unload; main and mini visual shells invisible while minimized/hidden.",
        "MyMusicSettings.qml": "One-shot row removal after transition.",
        "MyMusicModule.qml": "Busy download polling gated by UiActivity, refresh on resume.",
        "OtherComputersRow.qml": "One-shot removal of an absent peer row.",
        "PhoneSyncDevice.qml": "One-shot removal of an absent device row.",
        "Scrollbar.qml": "One-shot recent-scroll expiry, restarted only by contentY change.",
        "OtherComputers.qml": "Wake/status and relative-time polling gated by UiActivity; load/time refresh on resume.",
        "PhoneSync.qml": "Sync status, pairing countdown and relative-time timers gated by UiActivity; load/time refresh on resume.",
        "ReadAlongView.qml": "One-shot placement debounce. ReadAlong ticker stops when view inactive; no hidden follow scroll.",
        "Interactive.qml": "One-shot tooltip delay stops on hidden visibility.",
        "SettingsVoice.qml": "One-shot preview-end UI state; skeleton animation gated by Nav.uiVisible.",
        "Sidebar.qml": "One-shot hover open/close; no autonomous periodic timer.",
        "StudioScreen.qml": "Peer recovery UI polling gated by UiActivity; ask once on resume.",
        "StudioSettings.qml": "One-shot confirmation disarm; running-status polling gated by UiActivity, load on resume.",
        "WindowMode.qml": "Zero-delay geometry event coalescer; no periodic timer.",
        "Toast.qml": "Notice lifetime, may restart while hovered. No steady hidden callback in measured scenario.",
        "VoiceModule.qml": "Voice-job progress polling gated by UiActivity; refresh on resume.",
    }
    text = "# Timer and animation audit of final source\n\n"
    text += "One-shots already pending when a window hides may finish once. Audio fades, sleep enforcement, persistent bookmarks and request deadlines remain functional work. This inventory is a source audit; the benchmark does not exercise every page/job/error combination.\n\n"
    text += "| QML source and line | Hidden behavior |\n|---|---|\n"
    for path in sorted((ROOT / "qml").glob("*.qml")):
        if path.name == "BenchScenario.qml":
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\bTimer\s*\{", line):
                assert path.name in notes, f"Unclassified timer {path}:{n}"
                text += f"| {path.name}:{n} | {notes[path.name]} |\n"
    text += "\nC++: PlayerClock 250-ms display timer is suspended with synchronous refresh on restore. Player persistence/safety timer changes 1 s to 5 s hidden; a configured sleep timer retains 100 ms for audible fades. Notice expiry and fresh-state timeout are one-shots; shutdown's bounded nested-loop poll runs only on shutdown. Music sync is a single-shot cue/step/rate/loop/prewarm deadline; 250-ms cadence remains only while audio buffering/fade/tail state requires it. MusicBed fade timer and loop ticket control audible transitions. ReadAlong ticker is inactive hidden; reload coalescer and delayed script drop are one-shots. Main library refresh is a 1.5-s one-shot, stopped/deferred while hidden and fetched once on restore. MusicWindowActivity coalesces window state events with a zero-delay singleShot. Platform has a 2-s hide working-set trim one-shot. Backend has only a host-stop grace singleShot, no polling heartbeat.\n\n"
    text += "SMTC subscribes to book/chapter/load/play/rate/seek/duration changes, with no timer or positionChanged subscription. The OS advances the timeline. Tray tooltip/menu depend on book/chapter/play/control changes, without position or a timer; tray creation is disabled on the isolated benchmark desktop, so actual native tray CPU is not included. QNAM has no application keep-alive ping here; socket timeouts/idle connection cleanup and actual requests still dispatch. Backend stdout/socket events are event-driven.\n\n"
    text += "Infinite busy/skeleton/pulse/rotation animations in BookCell, Button, ConnectionChip, CoverSearch, DevicesSkeleton, EditBookSkeleton, ImportSkeleton, PlayButton and SettingsVoice are gated by Nav.uiVisible (plus their existing conditions). Theme shared motion durations become zero while hidden; its generator has the same rule. Finite transitions can settle once on hide; no periodic UI position/read-along count increase was observed. Native Qt/D3D retains internal timer/driver work; public-event suppression and graphics-release experiments were rejected and are not shipped.\n\n"
    text += "## C++ timer call-site inventory\n\n"
    for path in sorted((ROOT / "src").glob("*")):
        if path.suffix not in {".cpp", ".h"} or path.name == "idleaudit.h":
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\bQTimer\s+\w+|QTimer::singleShot|\.setInterval\(|\bstartTimer\(", line):
                text += f"- `{path.name}:{n}`: `{line.strip()}`\n"
    write(OUT / "timer-audit.md", text)


def main():
    timer_inventory()
    rows = read(OUT / "stage1/ab.json")
    native = read(OUT / "native/ab.json")[0]
    hidden = read(OUT / "hidden/idlecpu-quiet.json")[0]
    assert len(rows) == 8 and {(r["round"], r["label"]) for r in rows} == {(n, v) for n in range(1, 5) for v in "AB"}
    binaries = {"A": OUT / "baseline/ABookDesk.exe", "B": OUT / "stage1/ABookDesk.exe"}
    hashes = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in binaries.items()}
    for row in rows:
        raw = read(OUT / f'stage1/raw-{row["round"]}-{row["label"]}.json')
        assert raw["ok"] and raw["exit_code"] == 0 and not raw["forced_termination"]
        assert not raw["shared_busy"] and not raw["foreground_events"]
        assert raw["battery_status_at_launch"] == raw["battery_status_at_end"] == [2]
        assert {p[1] for p in raw["power_samples"]} == {1}
        assert row["exe_sha256"] == hashes[row["label"]]
        ev = dict((name, time) for time, name in raw["d"]["events"])
        begin = ev["min_begin"] + 5000 + raw["d"]["epoch_offset_ms"]
        end = ev["min_end"] + raw["d"]["epoch_offset_ms"]
        include_transient_threads(row, raw, begin, end)
        row["threads"] = enrich(row["threads"], raw, binaries[row["label"]])
    assert hidden["clock_pass"] and hidden["mixer_pass"] and not hidden["shared_busy"] and not hidden["foreground_events"]
    assert hidden["exe_sha256"] == native["exe_sha256"] == hashes["B"]
    native_raw = read(OUT / "native/raw-1-B.json")
    native_ev = dict((name, time + native_raw["d"]["epoch_offset_ms"]) for time, name in native_raw["d"]["events"])
    include_transient_threads(native, native_raw, native_ev["min_begin"] + 5000, native_ev["min_end"])
    native["threads"] = enrich(native["threads"], native_raw, binaries["B"])
    hidden_ev = dict((name, time + hidden["d"]["epoch_offset_ms"]) for time, name in hidden["d"]["events"])
    long_row = dict(threads=read(OUT / "hidden/thread-summary.json"))
    include_transient_threads(long_row, hidden, hidden_ev["hide_begin"] + 5000, hidden_ev["hide_end"])
    long_threads = enrich(long_row["threads"], hidden, binaries["B"])
    combined = rows + [native, {"threads": long_threads}]
    write(OUT / "threads-final.json", json.dumps(combined, indent=2) + "\n")
    # First invocation also produces symbol input; run idle_symbols.py on it,
    # then rerun this script to fill the public-PDB column.
    symbol_file = OUT / "symbols-final.json"
    symbols = {(Path(s["module"]).name.lower(), s["module_offset"]): s for s in read(symbol_file)} if symbol_file.exists() else {}
    text = "# All captured threads: final build53520f and baseline da5a1d4b\n\n"
    text += "Original raw identities are retained. Missing early main mappings are inferred from the PE entry point after validating 64-KiB image-base alignment. Missing same-start mappings use only the same process. Private Qt/NVIDIA symbols are not invented from distant exports.\n\n"
    for row in rows:
        text += table(f'Round {row["round"]} {row["label"]}', row["threads"], row, symbols)
    text += table("Long clean hidden run (114.799-s steady slice)", long_threads, {}, symbols)
    text += table(f'Native D3D diagnostic only (7.337-s sparse slice; {len(native["threads"])} threads)', native["threads"], native, symbols)
    write(OUT / "thread-tables.md", text)
    ev = dict((name, time) for time, name in hidden["d"]["events"])
    begin, end = ev["hide_begin"] + 5000 + hidden["d"]["epoch_offset_ms"], ev["hide_end"] + hidden["d"]["epoch_offset_ms"]
    mem = [s for s in hidden["memory_samples"] if begin <= s[0] <= end]
    long_metrics = dict(steady_s=(mem[-1][0] - mem[0][0]) / 1000,
                        cpu_core_pct=(mem[-1][3] - mem[0][3]) / (mem[-1][0] - mem[0][0]) * 100000,
                        private_commit_mb=statistics.median(s[1] for s in mem), working_set_mb=statistics.median(s[2] for s in mem))
    keys = ["cpu_core_pct", "cycles_core_pct", "private_commit_mb", "working_set_mb", "private_working_set_mb"]
    summary = dict(hashes=hashes, medians={v: {k: statistics.median(x[k] for x in rows if x["label"] == v) for k in keys} for v in "AB"}, hidden=long_metrics,
                   thread_counts=[len(x["threads"]) for x in combined], target_core_pct=0.15, target_met=False)
    write(OUT / "audit-summary.json", json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
