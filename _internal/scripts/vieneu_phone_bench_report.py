"""Table from a VieNeu phone bench run (results.jsonl of scripts/vieneu_phone_bench.sh) next to the desktop numbers of the export.

    runtime/.venv/Scripts/python.exe scripts/vieneu_phone_bench_report.py results.jsonl [--manifest <bench>/bundle/manifest.json]

Per configuration (model, ep, threads, codec threads): the median over the timed passes of RTF (compute seconds / audio seconds) per sentence,
then the median over sentences; first-audio latency (Turbo: prefill + 4 frames + their codec decode; Nano: the whole chunk), peak resident
memory, thermal readings, and the output's sanity (RMS, audio length against the desktop's for the same sentence). A sustain run
(`sustain` mode) is printed as RTF over time with the CPU clocks and battery temperature.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path


def _name(x: dict) -> str:
    name = f"{x['model']:5} {x.get('ep', 'cpu'):7} {x['threads']:>2}"
    if x.get("codecThreads") not in (None, x["threads"]):
        name += f" codec {x['codecThreads']}"
    if x.get("spin"):
        name += " spin"
    return name


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--manifest")
    args = ap.parse_args()
    lines = [json.loads(x) for x in Path(args.results).read_text(encoding="utf-8").splitlines() if x.strip()]
    start = next((x for x in lines if x.get("bench") in ("start", "sustain-start")), None)
    if start:
        d = start["device"]
        print(f"device: {d['manufacturer']} {d['model']}  SoC {d['soc']}  Android {d['android']}  {d['ramMB']} MB RAM  {d['cores']} cores "
              f"(max MHz {d.get('maxMHzPerCore', d['maxMHz'])})  cpuset {d.get('cpuset', '?')}  ORT providers {d.get('providers', '?')}")
    desktop = {}
    if args.manifest:
        m = json.loads(Path(args.manifest).read_text(encoding="utf-8"))["desktop"]
        for model in ("turbo", "nano"):
            for run in m.get(model, []):
                desktop[(model, run["threads"])] = statistics.median(s["rtf"] for s in run["sentences"])
    print(f"{'config':26} {'RTF med':>8} {'min':>6} {'max':>6} {'first s':>8} {'peak MB':>8} {'load s':>7} {'desk RTF':>9} {'len/desk':>9} {'rms':>6}  breakdown (s per audio s)")
    loads = {_name(x): x for x in lines if "loadMs" in x}
    for x in lines:
        if "error" in x:
            print(f"{_name(x):26} FAILED: {x['error'][:160]}")
            continue
        if "rows" not in x or not x["rows"]:
            continue
        rows = x["rows"]
        by_sentence: dict[int, list[dict]] = {}
        for r in rows:
            by_sentence.setdefault(r["sentence"], []).append(r)
        rtf = [statistics.median(r["rtf"] for r in rs) for rs in by_sentence.values()]
        first = [statistics.median(r["firstAudioS"] for r in rs) for rs in by_sentence.values()]
        audio = sum(statistics.median(r["audioS"] for r in rs) for rs in by_sentence.values())
        parts = {k: sum(statistics.median(r[k] for r in rs) for rs in by_sentence.values()) / audio for k in rows[0]
                 if k.endswith("S") and k not in ("audioS", "computeS", "firstAudioS", "desktopAudioS")}
        ratio = [r["audioS"] / r["desktopAudioS"] for r in rows if r.get("desktopAudioS")]
        rms = [r["rms"] for r in rows if "rms" in r]
        load = loads.get(_name(x), {}).get("loadMs", float("nan")) / 1000
        dk = desktop.get((x["model"], x["threads"]))
        print(f"{_name(x):26} {statistics.median(rtf):8.2f} {min(rtf):6.2f} {max(rtf):6.2f} {statistics.median(first):8.2f} {x['peakRssMB']:8d} {load:7.1f} "
              f"{'' if dk is None else format(dk, '.2f'):>9} {'' if not ratio else format(statistics.median(ratio), '.2f'):>9} "
              f"{'' if not rms else format(min(rms), '.3f'):>6}  " + " ".join(f"{k[:-1]}={v:.2f}" for k, v in parts.items()))
        tb, ta = x["thermalBefore"], x["thermalAfter"]
        print(f"{'':26} thermal: battery {tb.get('batteryTempDeciC')}->{ta.get('batteryTempDeciC')} (0.1 C), loadavg {tb['loadavg'].split()[0]}->"
              f"{ta['loadavg'].split()[0]}, cpu MHz after {ta['cpuMHz']}")
    sustain = [x for x in lines if "sustainRow" in x]
    if sustain:
        print(f"\nsustain {_name(sustain[0])}: t(s)  sentence  RTF  cpu MHz  battery (0.1 C)")
        for x in sustain:
            r = x["sustainRow"]
            print(f"  {r['atS']:6.1f}  {r['sentence']}  {r['rtf']:5.2f}  {r['thermal']['cpuMHz']}  {r['thermal']['batteryTempDeciC']}")
        half = len(sustain) // 2
        early = sum(x["sustainRow"]["computeS"] for x in sustain[:half]) / sum(x["sustainRow"]["audioS"] for x in sustain[:half])
        late = sum(x["sustainRow"]["computeS"] for x in sustain[half:]) / sum(x["sustainRow"]["audioS"] for x in sustain[half:])
        done = next((x for x in lines if x.get("bench") == "sustain-done"), {})
        print(f"  RTF first half {early:.2f}, second half {late:.2f}; peak RSS {done.get('peakRssMB', '?')} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
