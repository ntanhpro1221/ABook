"""Đo bảng trên câu trung tính cố định; không đọc sách hay sửa audio sách."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import shutil

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HOME", str(Path.home() / ".cache" / "huggingface"))
os.environ.setdefault("HF_HUB_CACHE", str(Path.home() / ".cache" / "huggingface" / "hub"))
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SEEDS = (730001, 730002)


def sentences() -> list[str]:
    # Bộ cũ cần Corpus ngoài repo và WAV đã mất. Bộ này dựng được chỉ từ repo,
    # giữ nguyên cho mọi máy/giọng; mười câu cuối là mẫu thao tác trung tính.
    from measure_vieneu_loudness import SENTENCES

    objects = ("chiếc cốc", "quyển vở", "cây bút", "tờ giấy", "chiếc hộp")
    actions = ("đặt", "giữ")
    return list(SENTENCES) + [f"Bạn {action} {item} trên bàn rồi kiểm tra lại một lần." for action in actions for item in objects]


def combinations():
    from abook import voice_balance as vb
    result = {}
    for key in vb.castable_keys():
        engine = key.partition("@")[0]
        name = key.partition("/")[2]
        result[key] = dict(engine=engine, preset=name, record=copy.deepcopy(vb.load_table()["voices"][key]))
    return dict(sorted(result.items()))


def configure_local_engines(folder: Path):
    """Chỉ trỏ bộ đo vào model đã kiểm băm, không đổi cấu hình Studio."""
    from abook.webui import zerotts_module as z, supertonic_module as s
    from abook.readaloud.supertonic import Installed

    z.locate = lambda: z.Installed(folder / "zerotts" / "lib", Path.home() / ".cache/huggingface/hub/models--zeroweight-ai--ZeroTTS/snapshots" / z.SOURCE_REVISION)
    s.locate = lambda: Installed(folder / "supertonic")


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def synthesize(folder: Path, *, models: Path | None = None, reuse: Path | None = None):
    import numpy as np
    import soundfile as sf
    from abook.config import DEFAULT_SETTINGS
    from abook.tts import ENGINE_ADAPTERS
    from abook import voice_balance as vb

    folder.mkdir(parents=True, exist_ok=True)
    variants = combinations()
    text = sentences()
    sentence_hashes = [hashlib.sha256(t.encode()).hexdigest() for t in text]
    if reuse is not None:
        previous = json.loads((reuse / "protocol.json").read_text(encoding="utf8"))
        if previous["sentence_sha256"] != sentence_hashes or previous["seeds"] != list(SEEDS):
            raise ValueError("Bộ câu hoặc seed của bản thô không khớp protocol")
    for variant in variants.values():
        token = hashlib.sha256(f"{variant['engine']}:{variant['preset']}".encode()).hexdigest()[:16]
        dest = folder / "raw" / token
        source = reuse / "raw" / token if reuse is not None else dest
        expected = [f"{i:02d}_{seed}.wav" for i in range(40) for seed in SEEDS]
        if source != dest and all((source / name).is_file() for name in expected):
            variant["raw"] = str(source.resolve())
        else:
            dest.mkdir(parents=True, exist_ok=True)
            if source != dest:
                for name in expected:
                    if (source / name).is_file() and not (dest / name).exists():
                        shutil.copyfile(source / name, dest / name)
            variant["raw"] = str(dest.resolve())
    dump(folder / "protocol.json", dict(seeds=SEEDS, sentence_sha256=sentence_hashes,
         generator="scripts/calibrate_voice_table.py:sentences", variants=variants))
    presets = sorted({(v["engine"], v["preset"]) for v in variants.values()}, key=lambda x: (x[0] != "vieneu", x))
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    settings["tts"]["batch_size"] = 1
    configure_local_engines(models if models is not None else folder / "models")
    def raw_dir(engine, name):
        return Path(next(v["raw"] for v in variants.values() if v["engine"] == engine and v["preset"] == name))
    failures = {}
    for engine_name in dict.fromkeys(x[0] for x in presets):
        if all(len(list(raw_dir(e, n).glob("*.wav"))) == 80 for e, n in presets if e == engine_name):
            continue
        engine = ENGINE_ADAPTERS[engine_name](settings, lambda m: print(m, flush=True))
        try:
            engine.load()
        except Exception as exc:
            failures[engine_name] = repr(exc)
            dump(folder / "unavailable.json", failures)
            print("UNAVAILABLE", engine_name, repr(exc), flush=True)
            continue
        print("ENGINE", engine_name, "device", getattr(getattr(engine.tts, "engine", None), "device", None), flush=True)
        for _, name in [p for p in presets if p[0] == engine_name]:
            token = hashlib.sha256(f"{engine_name}:{name}".encode()).hexdigest()[:16]
            dest = raw_dir(engine_name, name)
            dest.mkdir(parents=True, exist_ok=True)
            record = next(v["record"] for v in variants.values() if v["engine"] == engine_name and v["preset"] == name)
            for i, sentence in enumerate(text):
                for seed in SEEDS:
                    path = dest / f"{i:02d}_{seed}.wav"
                    if path.exists():
                        continue
                    start = time.perf_counter()
                    row = dict(text=sentence, speaker="CALIBRATION", kind="dialogue", emotion="neutral", intensity=0, volume="normal", pace="normal")
                    profile = dict(preset_name=name, engine=engine_name, voice_key=token)
                    wave = engine.generate_one(row, profile, seed, speed=record.get("engine_speed"))
                    if not np.isfinite(wave).all() or len(wave) < .2 * engine.sample_rate:
                        raise ValueError(f"invalid calibration take: {name}/{i}/{seed}")
                    sf.write(path, wave, engine.sample_rate, subtype="FLOAT")
                    print("RAW", engine_name, name, i, seed, round(time.perf_counter() - start, 2), flush=True)
        engine.unload()
    dump(folder / "unavailable.json", failures)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--models", type=Path, help="Thư mục model của bộ đo đã kiểm băm")
    parser.add_argument("--reuse", type=Path, help="Protocol và bản thô cùng câu/seed, chỉ thu phần còn thiếu")
    args = parser.parse_args()
    synthesize(args.folder, models=args.models, reuse=args.reuse)
