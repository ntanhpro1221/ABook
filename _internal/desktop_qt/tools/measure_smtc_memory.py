"""Alternating off/on rounds through measure.py's mandatory suspended-launch guard.

Run with the owner's pinned python.exe -X utf8. Raw audits include commit and page maps.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import time
import measure


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=6)
    parser.add_argument("--exe", type=Path, default=measure.HERE / "dist/ABookDesk.exe")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--arms", default="off:0,on:1")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    fixture = Path("D:/Novels/native_desk_proto/deskqt_fixture_music")
    books = json.loads((fixture / "audio_books.json").read_bytes())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    audit = args.out.with_name(args.out.stem + "_audit")
    os.environ["ABOOK_BENCH_AUDIT_DIR"] = str(audit)
    base = {"ABOOK_PREFERENCES": str(fixture / "prefs.json"),
            "ABOOK_HOST_PYTHON": "D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe",
            "ABOOK_HOST_APP": str(measure.HERE.parent), "ABOOK_BENCH_SCENARIO": "player",
            "ABOOK_BENCH_BOOK": books["a"], "ABOOK_MUTE": "1", "PYTHONUTF8": "1",
            "ABOOK_BENCH_MEMORY_MAP": "1" if args.profile else "0"}
    result = {"exe": str(args.exe), "sha256": hashlib.sha256(args.exe.read_bytes()).hexdigest(),
              "rounds_requested": args.rounds, "profile": args.profile, "runs": []}
    if args.out.exists():
        if not args.resume:
            raise RuntimeError("Output exists; use --resume to preserve accepted samples")
        previous = json.loads(args.out.read_bytes())
        for field in ("exe", "sha256", "profile"):
            if previous.get(field) != result[field]:
                raise RuntimeError(f"Cannot mix different {field}")
        if previous["rounds_requested"] > args.rounds:
            raise RuntimeError("Cannot shorten an existing series")
        if "failure" in previous:
            raise RuntimeError("Previous run aborted; inspect its safety audit before a new series")
        result = previous
        result["rounds_requested"] = args.rounds
    completed = [(row["round"], row["arm"]) for row in result["runs"]]
    planned = [(n, arm.split(":")[0]) for n in range(1, args.rounds + 1) for arm in args.arms.split(",")]
    if completed != planned[:len(completed)]:
        raise RuntimeError("Existing samples are not an alternating prefix of the requested series")
    for round_no in range(1, args.rounds + 1):
        for arm in args.arms.split(","):
            label, value = arm.split(":")
            if (round_no, label) in completed:
                continue
            clean = fixture / "listening.clean.json"
            if clean.exists():
                (fixture / "listening.json").write_bytes(clean.read_bytes())
            journal = fixture / "listening.json.journal"
            if journal.exists():
                saved = fixture / "_journals"
                saved.mkdir(exist_ok=True)
                journal.replace(saved / f"smtc_memory_{time.time_ns()}_{label}.json")
            # launch() waits for foreign ABookDesk/measure.py/ramrun.py BEFORE EVERY RUN.
            got = measure.launch(args.exe, dict(base, ABOOK_SMTC=value))
            if not got.get("ok"):
                result["failure"] = got
                args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
                raise RuntimeError(f"Aborted, no automatic retry: {got}")
            bench = got["d"]
            events = {name: stamp + bench["epoch_offset_ms"] for stamp, name in bench["events"]}
            if "timeout" in events or not all(name in events for name in ("min_begin", "min_end", "restore_end")):
                raise RuntimeError("Incomplete scenario")
            begin, end = events["min_begin"], events["min_end"]
            tail = [m for t, m, _ in got["samples"] if end - 3000 <= t <= end]
            mem = [m for t, m in got["memory"] if end - 3000 <= t <= end]
            if len(tail) < 5 or len(mem) < 5 or any("error" in m for t, m in got["memory"] if begin + 5000 <= t <= end):
                raise RuntimeError("Missing or failed memory samples")
            steady = [m for t, m, _ in got["samples"] if begin + 5000 <= t <= end]
            row = {"round": round_no, "arm": label, "private_ws_mib": statistics.median(tail),
                   "commit_mib": statistics.median(m["private_commit_mib"] for m in mem),
                   "tail_ws_range": [min(tail), max(tail)], "steady_ws_range": [min(steady), max(steady)],
                   "threads": statistics.median(m["threads"] for m in mem),
                   "min_seconds": (end - begin) / 1000, "tail_samples": len(tail),
                   "foreground_events": got["foreground_events"], "offscreen": got["offscreen"]}
            result["runs"].append(row)
            args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(row), flush=True)
    print("COMPLETE", args.out, flush=True)


if __name__ == "__main__":
    main()
