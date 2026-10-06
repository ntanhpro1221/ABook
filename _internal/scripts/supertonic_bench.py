"""Speed of the Supertonic voice on this computer's CPU, on the same three paragraphs the phone bench reads (tests/fixtures/readaloud/supertonic/supertonic_bench.json,
androidTest SupertonicBench.kt) - the reference column of docs/research/SUPERTONIC_PHONE.md.

    runtime/.venv/Scripts/python.exe scripts/supertonic_bench.py <model folder> [--threads 4,8] [--passes 2] [--audio <folder>]

<model folder> holds onnx/ and voice_styles/ as the "Giọng Supertonic" module downloads them (supertonic_module.FILES). Each paragraph is one chunk read
exactly as the app reads it (`SupertonicEngine.infer`, seed `seed_of("supertonic", voice, text)`, speed `speed_for`), without the sea-g2p normaliser
(the paragraphs have no numbers). Per thread count: load time, then pass 0 (cold: the first run of a fresh engine) and `--passes` warm passes;
RTF = compute seconds / audio seconds. `--audio` writes each paragraph's audio as raw float32 (`p<i>.f32`) to compare with the phone's.
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "readaloud" / "supertonic" / "supertonic_bench.json"


def main() -> int:
    import numpy as np
    import onnxruntime

    from abook.readaloud.supertonic import PREFIX, SupertonicEngine, speed_for
    from abook.readaloud.vieneu import seed_of

    ap = argparse.ArgumentParser()
    ap.add_argument("model", type=Path)
    ap.add_argument("--threads", default="4,8")
    ap.add_argument("--passes", type=int, default=2)
    ap.add_argument("--audio", type=Path)
    args = ap.parse_args()
    bench = json.loads(FIXTURE.read_bytes().decode("utf-8"))
    voice, paragraphs = bench["voice"], bench["paragraphs"]
    print(f"cpu: {platform.processor()}  onnxruntime {onnxruntime.__version__}  numpy {np.__version__}")
    for threads in (int(x) for x in args.threads.split(",")):
        began = time.perf_counter()
        engine = SupertonicEngine(args.model, threads=threads)
        engine.style(voice)
        load = time.perf_counter() - began
        rows: list[list[float]] = []
        seconds: list[float] = []
        for run in range(args.passes + 1):
            row = []
            for index, text in enumerate(paragraphs):
                rng = np.random.RandomState(seed_of(PREFIX, voice, text))
                start = time.perf_counter()
                wave = engine.infer(text, voice, rng, speed_for(text))
                spent = time.perf_counter() - start
                audio = wave.size / engine.SAMPLE_RATE
                row.append(spent / audio)
                if run == 0:
                    seconds.append(audio)
                    if args.audio:
                        args.audio.mkdir(parents=True, exist_ok=True)
                        (args.audio / f"p{index}.f32").write_bytes(wave.astype("<f4").tobytes())
            rows.append(row)
        warm = [statistics.median(rows[run][i] for run in range(1, len(rows))) for i in range(len(paragraphs))] if len(rows) > 1 else []
        print(json.dumps({"threads": threads, "loadMs": round(load * 1000), "audioSeconds": [round(x, 2) for x in seconds],
                          "coldRtf": [round(x, 3) for x in rows[0]], "warmRtf": [round(x, 3) for x in warm],
                          "warmRtfMedian": round(statistics.median(warm), 3) if warm else None}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
