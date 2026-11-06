"""Xuất bảng từ số đo bộ trung tính; thiếu một khoá thì từ chối xuất."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def build(folder: Path):
    protocol = json.loads((folder / "protocol.json").read_text(encoding="utf8"))
    variants = protocol["variants"]
    measured = {row["key"]: row for p in (folder / "keys").glob("*.json") for row in [json.loads(p.read_text(encoding="utf8"))]}
    missing = set(variants) - set(measured)
    extra = set(measured) - set(variants)
    if missing or extra:
        raise ValueError(f"measurement coverage: missing={sorted(missing)}, extra={sorted(extra)}")
    voices = {}
    for key, variant in variants.items():
        row = measured[key]
        if row["engine"] != variant["engine"] or row["preset"] != variant["preset"] or row["n_sentences"] != 40 or row["n_takes"] != 80:
            raise ValueError(f"wrong calibration identity: {key}")
        if abs(row["verified_mean_phon"] - 73.0) > .002:
            raise ValueError(f"gain verification failed: {key}")
        base = variant["record"]
        values = np.asarray(row["predicted_sentence_phon"])
        means = values[np.random.default_rng(20261106).integers(0, 40, (2000, 40))].mean(axis=1)
        voices[key] = dict(r=base["r"], o_db=round(row["gain_db"] + 25 + row["ref_lufs"], 7),
                           ref_lufs=round(row["ref_lufs"], 7))
        if "engine_speed" in base:
            voices[key]["engine_speed"] = base["engine_speed"]
    return dict(version=2, engine_versions={"vieneu": "3.8.3", "zerotts": "0.1.5", "supertonic": "3-724fb5ab"},
                x=1.0, L_lufs=-25.0, chapter_gain_db=5.0, pace_floor_scale=.99, engine_pace_floor={"supertonic": .9},
                calibration=dict(meter="active_ISO532_1_stationary_v1", target_phon=73.0, sentences=40, seeds=protocol["seeds"],
                                 sentence_sha256=protocol["sentence_sha256"], bootstrap="2000 sentence resamples, paired seeds, seed=20261106",
                                 protocol_sha256=hashlib.sha256((folder / "protocol.json").read_bytes()).hexdigest()),
                voices=dict(sorted(voices.items())))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    table = build(args.folder)
    args.output.write_text(json.dumps(table, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf8", newline="\n")
    print(len(table["voices"]), "calibrated keys")
