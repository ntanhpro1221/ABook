"""Table from a VieNeu phone bench run (results.jsonl of scripts/vieneu_phone_bench.sh) next to the desktop numbers of the export.

    runtime/.venv/Scripts/python.exe scripts/vieneu_phone_bench_report.py results.jsonl [--manifest <bench>/bundle/manifest.json]

Per (model, threads): the median over the timed passes of RTF (compute seconds / audio seconds) per sentence, then the median over sentences;
first-audio latency (Turbo: prefill + 4 frames + their codec decode; Nano: the whole chunk), peak resident memory, thermal readings.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--manifest")
    args = ap.parse_args()
    lines = [json.loads(x) for x in Path(args.results).read_text(encoding="utf-8").splitlines() if x.strip()]
    start = next((x for x in lines if x.get("bench") == "start"), None)
    if start:
        d = start["device"]
        print(f"device: {d['manufacturer']} {d['model']}  SoC {d['soc']}  Android {d['android']}  {d['ramMB']} MB RAM  {d['cores']} cores ({d['coresAtMaxFreq']} at {d['maxMHz']} MHz)")
    desktop = {}
    if args.manifest:
        m = json.loads(Path(args.manifest).read_text(encoding="utf-8"))["desktop"]
        for model in ("turbo", "nano"):
            for run in m.get(model, []):
                desktop[(model, run["threads"])] = statistics.median(s["rtf"] for s in run["sentences"])
    print(f"{'model':6} {'thr':>3} {'RTF med':>8} {'RTF min':>8} {'RTF max':>8} {'first audio s':>14} {'peak RSS MB':>12} {'load s':>7} {'desktop RTF':>12}  breakdown (s per audio s)")
    loads = {(x["model"], x["threads"]): x for x in lines if "loadMs" in x}
    for x in lines:
        if "rows" not in x:
            continue
        rows = x["rows"]
        by_sentence: dict[int, list[dict]] = {}
        for r in rows:
            by_sentence.setdefault(r["sentence"], []).append(r)
        rtf = [statistics.median(r["rtf"] for r in rs) for rs in by_sentence.values()]
        first = [statistics.median(r["firstAudioS"] for r in rs) for rs in by_sentence.values()]
        audio = sum(statistics.median(r["audioS"] for r in rs) for rs in by_sentence.values())
        parts = {k: sum(statistics.median(r[k] for r in rs) for rs in by_sentence.values()) / audio for k in rows[0] if k.endswith("S") and k not in ("audioS", "computeS", "firstAudioS")}
        load = loads.get((x["model"], x["threads"]), {}).get("loadMs", float("nan")) / 1000
        dk = desktop.get((x["model"], x["threads"]))
        print(f"{x['model']:6} {x['threads']:>3} {statistics.median(rtf):8.2f} {min(rtf):8.2f} {max(rtf):8.2f} {statistics.median(first):14.2f} {x['peakRssMB']:12d} {load:7.1f} "
              f"{'' if dk is None else format(dk, '12.2f'):>12}  " + " ".join(f"{k[:-1]}={v:.2f}" for k, v in parts.items()))
        tb, ta = x["thermalBefore"], x["thermalAfter"]
        print(f"       thermal: battery {tb.get('batteryTempDeciC')}->{ta.get('batteryTempDeciC')} (0.1 C), loadavg {tb['loadavg'].split()[0]}->{ta['loadavg'].split()[0]}, "
              f"cpu MHz after {ta['cpuMHz']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
