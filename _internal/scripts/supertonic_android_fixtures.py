"""Shared fixture for the phone's Supertonic voice (tests/fixtures/readaloud/supertonic/supertonic.json, read by the JVM test
SupertonicParityTest and on the emulator / a phone by SupertonicBenchTest#parity): what the DESKTOP path (abook/readaloud/supertonic.py + vieneu.py)
gives for the same input, i.e. the model's INPUTS piece by piece - cleaned text, character ids, chunk speed, units + seeds + normalised text of a
paragraph, the start noise (numpy's legacy RandomState), the loudness raise, the ten voice styles (shape + SHA-256 of their float32 bytes) - and
one chunk of audio (length, RMS, every 200th sample) to compare the phone's output with.

    runtime/.venv/Scripts/python.exe scripts/supertonic_android_fixtures.py <model folder>

<model folder> holds onnx/ + voice_styles/ as the "Giọng Supertonic" module downloads them. Needs sea-g2p (the runtime venv has it).
tests/test_supertonic_android.py recomputes the parts that need no model and fails when the fixture is stale.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np

from abook.readaloud import supertonic as st
from abook.readaloud import vieneu

OUT = ROOT / "tests" / "fixtures" / "readaloud" / "supertonic" / "supertonic.json"
VOICE = "F1"

# Written for this fixture (no book text): the characters clean() rewrites or drops, and chunk lengths around the speed ramp.
CLEAN = [
    "Xin chào",
    "Anh ấy nói: “Đi thôi!” rồi bước ra — không ngoái lại…",
    "Cô ấy cười 😊 và vẫy tay 👋🏻.",
    "[Ghi chú] Hệ thống | cấp_độ #3 → mở khoá ← quay lại",
    "Gửi thư tới a@b.vn , nhé ?",
    "Ôi '' trời ``đất'' ơi",
    "Khoảng trắng lạ　ở\tđây và\u0085kia\x1c",
    "Tim ♥ sao ☆ © bản quyền \\ gạch",
    "Chữ tổ hợp: ế và ế",
    "<en>Hello</en> world",
    "Câu không có dấu cuối nhưng có ngoặc)",
    "😊",
    "",
]
SPEED = ["Về rồi?", "Sao cô biết?", "Một hai ba bốn", "Một hai ba bốn năm sáu bảy tám", "Một hai ba bốn năm sáu bảy tám chín mười mười một",
         "Một hai ba bốn năm sáu bảy tám chín mười mười một mười hai mười ba", "cấp_độ ② và Ⅻ cùng ２ chữ số 3"]
PARAGRAPHS = [
    ("Ngày 12/03/2025, lúc 7h30, anh ấy trả 1.500.000đ cho 3 cuốn sách. Rồi đi!", None),
    ("Haruto nhìn Sakura-san và nói: “HP của tôi còn 25%.” Cô ấy gật đầu. Về rồi?", "ja"),
    ("Con đường dẫn lên núi quanh co và dốc đứng, đoàn người đi chậm, thỉnh thoảng dừng lại để nghỉ chân và uống nước, người dẫn đường kể rằng "
     "ngày xưa nơi đây từng có một ngôi làng nhỏ, nhưng sau trận lũ lớn năm 1998 dân làng đã dời đi hết, chỉ còn lại mấy bức tường đá phủ đầy rêu "
     "xanh, và mỗi mùa xuân người ta lại thấy hoa dại mọc kín lối đi cũ, như thể ngôi làng chưa bao giờ biến mất khỏi trí nhớ của núi rừng nơi này.", None),
]
RNG = [(0, 64), (12345, 144 * 3), (4294967295, 145)]
LOUDER = [[0.0, 0.1, -0.2, 0.05], [0.5, -0.95, 0.2], [0.0, 0.0], []]


def _floats(values) -> list[float]:
    return [float(x) for x in np.asarray(values, dtype=np.float32)]


def _sha(values) -> str:
    return hashlib.sha256(np.ascontiguousarray(values, dtype="<f4").tobytes()).hexdigest()


def text_fixture() -> dict:
    """Parts that need no model files (pytest recomputes them)."""
    paragraphs = []
    for text, origin in PARAGRAPHS:
        _toks, parts = vieneu.units(text, st.MAX_CHARS, origin, st.SupertonicProvider.speaks_english)
        units = []
        for unit in parts:
            spoken = st.normalize_pieces(unit.pieces)
            units.append({"first": unit.first, "last": unit.last, "pieces": unit.pieces, "seed": vieneu.seed_of(st.PREFIX, VOICE, " ".join(unit.pieces)),
                          "normalized": spoken, "speed": st.speed_for(spoken), "cleaned": st.clean(spoken),
                          "pause": "sentence" if spoken.rstrip()[-1:] in ".!?" else "minor"})
        paragraphs.append({"text": text, "origin": origin, "voice": VOICE, "units": units})
    rng = []
    for seed, count in RNG:
        noise = np.random.RandomState(seed).standard_normal((1, count)).astype(np.float32).reshape(-1)
        rng.append({"seed": seed, "count": count, "head": _floats(noise[:16]), "sha256": _sha(noise)})
    return {
        "clean": [{"text": text, "cleaned": st.clean(text)} for text in CLEAN],
        "speed": [{"text": text, "speed": st.speed_for(text)} for text in SPEED],
        "paragraphs": paragraphs,
        "rng": rng,
        "louder": [{"wave": _floats(wave), "out": _floats(st.louder(np.asarray(wave, dtype=np.float32)))} for wave in LOUDER],
    }


def model_fixture(model: Path, text: dict) -> dict:
    """Parts that need the model: character ids (with the slice of the indexer they use), the voice styles, one chunk of audio."""
    engine = st.SupertonicEngine(model, threads=4)
    cleaned = [case["cleaned"] for case in text["clean"]] + [unit["cleaned"] for paragraph in text["paragraphs"] for unit in paragraph["units"]]
    points = sorted({ord(char) for item in cleaned for char in f"<{st.LANGUAGE}>{item}</{st.LANGUAGE}>"})
    indexer = {str(point): int(engine.indexer[point]) if point < engine.indexer.size else -1 for point in points}
    ids = [{"cleaned": item, "ids": [int(x) for x in engine.ids(item)]} for item in dict.fromkeys(cleaned)]
    styles = {}
    for name in st.NAMES:
        ttl, dp = engine.style(name)
        styles[name] = {"style_ttl": {"dims": list(ttl.shape), "sha256": _sha(ttl)}, "style_dp": {"dims": list(dp.shape), "sha256": _sha(dp)}}
    unit = text["paragraphs"][1]["units"][-1]
    wave = engine.infer(unit["normalized"], VOICE, np.random.RandomState(unit["seed"]), unit["speed"])
    audio = {"voice": VOICE, "text": unit["normalized"], "seed": unit["seed"], "speed": unit["speed"], "sampleRate": engine.SAMPLE_RATE,
             "samples": int(wave.size), "rms": float(np.sqrt(np.mean(wave.astype(np.float64) ** 2))), "every": 200, "decimated": _floats(wave[::200])}
    return {"indexer": indexer, "ids": ids, "styles": styles, "audio": audio}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("model", type=Path)
    args = ap.parse_args()
    text = text_fixture()
    fixture = {"about": "Generated by scripts/supertonic_android_fixtures.py - do not edit by hand.", **text, **model_fixture(args.model, text)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes((json.dumps(fixture, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
