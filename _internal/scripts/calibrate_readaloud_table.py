"""Đo Turbo/Nano của Nghe ngay bằng cùng câu và meter với bảng Studio."""
import hashlib
import argparse
import io
import json
import os
from pathlib import Path
import sys
import time

for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from calibrate_voice_table import SEEDS, sentences, dump


def main(folder, models=None):
    import numpy as np
    import soundfile as sf
    from abook.readaloud import vieneu as v, loudness

    models = models or folder.parent / "models" / "readaloud"
    installed = v.Installed(models / "voices", (models / "turbo", models / "turbo"), models / "nano", False)
    provider = v.VieneuProvider(lambda: installed)
    variants = {}
    folder.mkdir(parents=True, exist_ok=True)
    for tier in ("turbo", "nano"):
        for name, preset in provider.presets(tier, installed).items():
            if name == "Mai Anh":
                continue
            key = f"vieneu:{tier}/{name}"
            engine = f"readaloud-{tier}"
            token = hashlib.sha256(f"{engine}:{name}".encode()).hexdigest()[:16]
            variants[key] = dict(engine=engine, preset=name, record=dict(r=1.0))
            dest = folder / "raw" / token
            dest.mkdir(parents=True, exist_ok=True)
            for i, text in enumerate(sentences()):
                for seed in SEEDS:
                    path = dest / f"{i:02d}_{seed}.wav"
                    if path.exists():
                        continue
                    v.seed_of = lambda *args, _seed=seed: _seed
                    started = time.perf_counter()
                    wave, rate, *_ = provider._speak(tier, name, installed, preset, text)
                    assert np.isfinite(wave).all() and len(wave) >= .2 * rate, (key, i, seed)
                    # Cùng clip 16-bit và bước bù câu ngắn của service, trước gain lúc phát.
                    clip = loudness.lift_wav(key, v.wav_bytes(wave, rate))
                    wave, rate = sf.read(io.BytesIO(clip), dtype="float32")
                    sf.write(path, wave, rate, subtype="FLOAT")
                    print("READALOUD", key, i, seed, round(time.perf_counter() - started, 3), flush=True)
        provider.forget()
    dump(folder / "protocol.json", dict(variants=variants, seeds=SEEDS, stage="clip_before_playback_gain",
         sentence_sha256=[hashlib.sha256(t.encode()).hexdigest() for t in sentences()]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--models", type=Path)
    args = parser.parse_args()
    main(args.folder, args.models)
