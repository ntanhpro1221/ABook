"""Bench bundle for the phone's VieNeu runtime (Kotlin port, docs/LISTEN_ANYTHING.md "VieNeu module").

Runs on the desktop (runtime venv). For 5 fixed Vietnamese sentences it records everything the phone needs to repeat the
synthesis WITHOUT the Python-only parts (G2P, tokenizer, RNG) and what the desktop produced from the same ONNX graphs:

  <out>/models/turbo_int8/   VieNeu-TTS-v3-Turbo onnx_int8 graphs + vieneu_v3_heads.npz (the phone reads the npz in place)
  <out>/models/codec/        MOSS audio tokenizer decode graph (Turbo's vocoder)
  <out>/models/nano/         VieNeu-TTS-v3-Nano graphs + constants.npz
  <out>/bundle/              manifest.json (phonemes, ids, sampling params, desktop timings) + one raw file per tensor:
                             voice, uniform random streams (Turbo sampling), Nano start noise, desktop codes and audio

Sampling is made deterministic and RNG-independent on purpose: the engine's numpy `choice` is replaced by an inverse-CDF
draw over a recorded stream of uniforms, so the Kotlin loop makes the same draws. Everything in the draw (top-k, softmax,
nucleus cut, cdf) is float64 after the float32 penalty/temperature step, so both sides can reproduce it exactly.

    runtime/.venv/Scripts/python.exe scripts/vieneu_phone_bench_export.py --out D:/tmp/vneu_bench
Then: scripts/vieneu_phone_bench.sh push|run (see the header of that file).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import numpy as np

SENTENCES = [
    "Trời hôm nay đẹp quá.",
    "Cô gái đứng bên cửa sổ, lặng lẽ nhìn mưa rơi.",
    "Chiếc thuyền nhỏ trôi chậm giữa dòng sông, mang theo những mùa hè đã xa.",
    "Anh ấy mở cuốn sổ cũ, đọc lại từng dòng chữ mà mẹ đã viết cho mình từ nhiều năm trước.",
    "Khi ánh đèn trong phòng vụt tắt, cả ngôi nhà chìm vào bóng tối, chỉ còn tiếng đồng hồ gõ nhịp đều đặn như một nhịp tim đang chờ đợi.",
]
SAMPLING = dict(temperature=0.8, top_k=25, top_p=0.95, repetition_penalty=1.2, repetition_window=64)
NANO = dict(steps=16, cfg=3.0, sway=0.0, speed=1.0)
TURBO_SEED, NANO_SEED = 1000, 2000
FIRST_CHUNK_FRAMES = 4          # onnx_runtime_lite._STREAM_LEADIN_FRAMES


def _snapshot(repo: str, patterns: list[str]) -> Path:
    from huggingface_hub import snapshot_download
    return Path(snapshot_download(repo, allow_patterns=patterns, local_files_only=True))


class Timed:
    """Session proxy: accumulates seconds spent inside run()."""

    def __init__(self, session):
        self._s = session
        self.seconds = 0.0
        self.calls = 0
        self.first_inputs = None

    def run(self, names, feed, *a, **k):
        if self.first_inputs is None:
            self.first_inputs = feed
        t = time.perf_counter()
        out = self._s.run(names, feed, *a, **k)
        self.seconds += time.perf_counter() - t
        self.calls += 1
        return out

    def __getattr__(self, name):
        return getattr(self._s, name)


def _det_sample(state):
    """Replacement for OnnxV3LiteEngine._sample: same maths, inverse-CDF draw from state['u'] (float64)."""
    def sample(logits, temperature, top_k, top_p, rep_pen, prev):
        logits = logits.astype(np.float32)
        if prev:
            idx = np.fromiter(prev, dtype=np.int64, count=len(prev))
            sel = logits[idx]
            logits = logits.copy()
            logits[idx] = np.where(sel < 0, sel * np.float32(rep_pen), sel / np.float32(rep_pen))
        logits = logits / np.float32(temperature)
        order = np.argsort(-logits, kind="stable")[: int(top_k)]
        cs = logits[order].astype(np.float64)
        e = np.exp(cs - cs.max())
        p = e / e.sum()
        keep = (np.cumsum(p) - p) < top_p
        p = p * keep
        p = p / p.sum()
        cdf = np.cumsum(p)
        u = state["u"][state["n"]]
        state["n"] += 1
        return int(order[min(int(np.searchsorted(cdf, u, side="right")), len(order) - 1)])
    return sample


def write_sampler_fixture(path: Path, cases: int = 24) -> None:
    """Random logits + repetition history + uniform -> the code `_det_sample` picks: the JVM test of the Kotlin sampler replays them."""
    import base64
    rng = np.random.default_rng(7)
    out = []
    for k in range(cases):
        logits = (rng.standard_normal(1024) * rng.choice([0.5, 2.0, 4.0])).astype(np.float32)
        logits[rng.integers(0, 1024, size=3)] += rng.choice([4.0, 8.0])           # a few clear favourites, so the nucleus cut bites
        logits[rng.integers(0, 1024, size=8)] = np.float32(0.0)                    # exact ties
        history = sorted({int(x) for x in rng.integers(0, 1024, size=int(rng.integers(0, 64)))} | set(np.argsort(-logits)[:3].tolist() if k % 2 else []))
        u = float(rng.random())
        state = {"u": [u], "n": 0}
        code = _det_sample(state)(logits.copy(), 0.8, 25, 0.95, 1.2, history)
        out.append({"logits": base64.b64encode(logits.astype("<f4").tobytes()).decode(), "history": history, "u": u, "code": code})
    path.write_bytes(json.dumps({"temperature": 0.8, "top_k": 25, "top_p": 0.95, "repetition_penalty": 1.2, "cases": out}).encode())


def _write(path: Path, array, dtype) -> dict:
    a = np.ascontiguousarray(np.asarray(array, dtype=dtype))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(a.tobytes())      # raw little-endian, LF-agnostic
    return {"file": path.name, "dtype": np.dtype(dtype).name, "shape": list(a.shape)}


def _copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def export_models(out: Path, turbo_dir: Path, codec_dir: Path, nano_dir: Path, tag: str, with_nano: bool) -> None:
    t = out / "models" / f"turbo_{tag}"
    for name in ["vieneu_prefill.onnx", "vieneu_decode_step.onnx", "vieneu_acoustic_cached.onnx", "vieneu_backbone_shared.data",
                 "config.json", "tokenizer.json", "vieneu_v3_heads.npz"]:
        _copy(turbo_dir / name, t / name)
    for name in ["moss_audio_tokenizer_decode_full.onnx", "moss_audio_tokenizer_decode_shared.data"]:
        _copy(codec_dir / name, out / "models" / "codec" / name)
    if not with_nano:
        return
    n = out / "models" / "nano"
    for name in ["text_encoder.onnx", "duration_predictor.onnx", "vector_estimator.onnx", "codec_decoder.onnx", "config.json", "constants.npz"]:
        _copy(nano_dir / name, n / name)


def run_turbo(turbo_dir: Path, codec_dir: Path, voice: dict, threads: int, record: bool, bundle: Path | None):
    from vieneu._v3_turbo_engine.onnx_runtime_lite import OnnxV3LiteEngine
    from vieneu_utils.core_utils import max_expected_frames
    from vieneu_utils.phonemize_text import phonemize_text_with_emotions
    import vieneu._v3_turbo_engine.onnx_runtime_lite as lite

    t0 = time.perf_counter()
    eng = OnnxV3LiteEngine(onnx_dir=str(turbo_dir), codec_dir=str(codec_dir), threads=threads)
    load_s = time.perf_counter() - t0
    eng.babble_retries = 0                         # retries are a rare extra cost; the bench measures one pass
    sess = {n: Timed(getattr(eng, n)) for n in ["sess_pre", "sess_dec", "sess_ac", "sess_codec_dec"]}
    for n, s in sess.items():
        setattr(eng, n, s)
    st = {"u": None, "n": 0}
    eng._sample = _det_sample(st)
    frames_seen = {}
    real_decode = eng._decode_codes

    def decode(codes):
        frames_seen["codes"] = np.asarray(codes)
        return real_decode(codes)
    eng._decode_codes = decode
    ac_stamps: list[float] = []
    real_ac = eng._acoustic_frame

    def ac(*a, **k):
        r = real_ac(*a, **k)
        ac_stamps.append(time.perf_counter())
        return r
    eng._acoustic_frame = ac

    rows = []
    manifest_sentences = []
    for i, text in enumerate(SENTENCES):
        ph = phonemize_text_with_emotions(text)
        cap = min(300, max_expected_frames(ph))
        st["u"] = np.random.default_rng(TURBO_SEED + i).random(cap * eng.n_vq)
        st["n"] = 0
        ac_stamps.clear()
        for s in sess.values():
            s.seconds = 0.0
            s.calls = 0
        start = time.perf_counter()
        wav = eng.infer(phonemes=ph, speaker_emb=voice["speaker_emb"], ref_codes=voice["codes"],
                        temperature=SAMPLING["temperature"], top_k=SAMPLING["top_k"], top_p=SAMPLING["top_p"],
                        repetition_penalty=SAMPLING["repetition_penalty"], repetition_window=SAMPLING["repetition_window"],
                        max_new_frames=300, frame_cap=True)
        total = time.perf_counter() - start
        codes = frames_seen["codes"]
        # first audio = everything up to the 4th frame + decoding those 4 frames (the streaming path's first chunk)
        n4 = min(FIRST_CHUNK_FRAMES, len(codes))
        tc = time.perf_counter()
        real_decode(codes[:n4])
        first = (ac_stamps[n4 - 1] - start) + (time.perf_counter() - tc)
        audio_s = len(wav) / eng.SAMPLE_RATE
        # the loop's non-ORT remainder: embeddings, heads matmuls, sampling
        ort_s = sum(s.seconds for s in sess.values())
        rows.append({
            "i": i, "total_s": total, "audio_s": audio_s, "rtf": total / audio_s, "frames": int(len(codes)),
            "first_audio_s": first, "prefill_s": sess["sess_pre"].seconds, "decode_step_s": sess["sess_dec"].seconds,
            "acoustic_s": sess["sess_ac"].seconds, "codec_s": sess["sess_codec_dec"].seconds,
            "heads_and_sampling_s": total - ort_s, "max_frames": cap,
        })
        if record and bundle is not None:
            manifest_sentences.append({"u_draws": st["n"], "max_new_frames": cap, "frames": int(len(codes)),
                                       "audio_samples": int(len(wav)), "ph": ph})
            _write(bundle / f"turbo_uniforms_{i}.f64", st["u"], "<f8")
            _write(bundle / f"turbo_codes_{i}.i32", codes, "<i4")
            _write(bundle / f"turbo_audio_{i}.f32", wav, "<f4")
    return {"threads": threads, "load_s": load_s, "sentences": rows}, manifest_sentences, eng


def run_nano(nano_dir: Path, voice: dict, threads: int, record: bool, bundle: Path | None):
    import vieneu.v3nano as v3nano
    from vieneu_utils.phonemize_text import phonemize_text_with_emotions

    v3nano._trim_and_fade = lambda w, sr: w            # compare raw model output (the edge trim is post-processing)
    t0 = time.perf_counter()
    eng = v3nano.OnnxV3NanoEngine(local_dir=str(nano_dir), threads=threads)
    load_s = time.perf_counter() - t0
    names = ["s_text", "s_dur", "s_ve", "s_dec"]
    sess = {n: Timed(getattr(eng, n)) for n in names}
    for n, s in sess.items():
        setattr(eng, n, s)
    rows, meta = [], []
    for i, text in enumerate(SENTENCES):
        ph = phonemize_text_with_emotions(text)
        for s in sess.values():
            s.seconds, s.calls, s.first_inputs = 0.0, 0, None
        start = time.perf_counter()
        wav = eng.infer(ph, voice["speaker_emb"], voice["style"], seed=NANO_SEED + i, **NANO)
        total = time.perf_counter() - start
        audio_s = len(wav) / eng.SAMPLE_RATE
        noise = sess["s_ve"].first_inputs["x"]
        rows.append({"i": i, "total_s": total, "audio_s": audio_s, "rtf": total / audio_s, "first_audio_s": total,
                     "text_dur_s": sess["s_text"].seconds + sess["s_dur"].seconds, "vector_estimator_s": sess["s_ve"].seconds,
                     "decoder_s": sess["s_dec"].seconds, "ve_calls": sess["s_ve"].calls, "frames": int(noise.shape[2])})
        if record and bundle is not None:
            ids = eng.encode_phones(ph)
            meta.append({"ph": ph, "ids": ids[0].tolist(), "flow_frames": int(noise.shape[2]), "audio_samples": int(len(wav))})
            _write(bundle / f"nano_noise_{i}.f32", noise, "<f4")
            _write(bundle / f"nano_audio_{i}.f32", wav, "<f4")
    return {"threads": threads, "load_s": load_s, "sentences": rows}, meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--threads", default="1,2,4,8")
    ap.add_argument("--turbo-subfolder", default="onnx_int8", help="onnx_int8 (what the phone ships) or onnx_update (fp32: a reference check, "
                    "int8 kernels differ between CPUs so only fp32 repeats the desktop's codes exactly)")
    ap.add_argument("--only-turbo", action="store_true")
    ap.add_argument("--sampler-fixture", help="write the sampler test cases to this json and exit")
    args = ap.parse_args()
    if args.sampler_fixture:
        write_sampler_fixture(Path(args.sampler_fixture))
        return 0
    if not args.out:
        ap.error("--out is required")
    out = Path(args.out)
    threads = [int(x) for x in args.threads.split(",")]

    import vieneu
    assets = Path(vieneu.__file__).parent / "assets"
    tag = "int8" if args.turbo_subfolder == "onnx_int8" else "fp32"
    turbo_dir = _snapshot("pnnbao-ump/VieNeu-TTS-v3-Turbo", [f"{args.turbo_subfolder}/*"]) / args.turbo_subfolder
    nano_dir = _snapshot("pnnbao-ump/VieNeu-TTS-v3-Nano", ["*"])
    codec_dir = _snapshot("OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX", ["moss_audio_tokenizer_decode_*", "codec_browser_onnx_meta.json"])

    tv = json.loads((assets / "voices_v3_turbo.json").read_text(encoding="utf-8"))
    nv = json.loads((assets / "voices_v3_nano.json").read_text(encoding="utf-8"))
    tname, nname = tv["default_voice"], nv["default_voice"]
    tvoice = {"speaker_emb": np.asarray(tv["presets"][tname]["speaker_emb"], np.float32),
              "codes": np.asarray(tv["presets"][tname]["codes"], np.int64)}
    nvoice = {"speaker_emb": np.asarray(nv["presets"][nname]["speaker_emb"], np.float32),
              "style": np.asarray(nv["presets"][nname]["style"], np.float32)}

    # a sentence must be ONE chunk, or the app would synthesize several pieces and the bench would not match it
    from vieneu_utils.phonemize_text import normalize_to_chunks_v3_with_gaps
    for s in SENTENCES:
        assert len(normalize_to_chunks_v3_with_gaps(s, max_chars=140)[0]) == 1, s

    export_models(out, turbo_dir, codec_dir, nano_dir, tag, not args.only_turbo)
    bundle = out / ("bundle" if tag == "int8" else f"bundle_{tag}")
    bundle.mkdir(parents=True, exist_ok=True)
    manifest = {"version": 1, "sentences": SENTENCES, "sampling": SAMPLING, "nano": NANO, "seeds": {"turbo": TURBO_SEED, "nano": NANO_SEED},
                "first_chunk_frames": FIRST_CHUNK_FRAMES, "turbo_voice": tname, "nano_voice": nname, "files": {}}
    manifest["files"]["turbo_speaker_emb"] = _write(bundle / "turbo_speaker_emb.f32", tvoice["speaker_emb"], "<f4")
    manifest["files"]["turbo_ref_codes"] = _write(bundle / "turbo_ref_codes.i32", tvoice["codes"], "<i4")
    manifest["files"]["nano_speaker_emb"] = _write(bundle / "nano_speaker_emb.f32", nvoice["speaker_emb"], "<f4")
    manifest["files"]["nano_style"] = _write(bundle / "nano_style.f32", nvoice["style"], "<f4")

    # token ids of the Turbo prompt (tokenizer.json is not ported yet; the phone takes the ids as given)
    from tokenizers import Tokenizer
    tok = Tokenizer.from_file(str(turbo_dir / "tokenizer.json"))
    cfg = json.loads((turbo_dir / "config.json").read_text(encoding="utf-8"))
    from vieneu_utils.phonemize_text import phonemize_text_with_emotions
    turbo_ids = []
    for s in SENTENCES:
        ids = tok.encode(phonemize_text_with_emotions(s), add_special_tokens=False).ids
        turbo_ids.append([int(cfg["default_style_token_id"]), int(cfg["text_prompt_start_token_id"])] + ids + [int(cfg["text_prompt_end_token_id"])])

    desktop = {"python_onnxruntime": __import__("onnxruntime").__version__, "cpu_count": os.cpu_count(), "turbo": [], "nano": []}
    first = True
    for n in threads:
        r, sents, _ = run_turbo(turbo_dir, codec_dir, tvoice, n, record=first, bundle=bundle)
        desktop["turbo"].append(r)
        if first:
            manifest["turbo"] = [dict(s, text_ids=turbo_ids[i]) for i, s in enumerate(sents)]
        line = f"threads={n}: turbo RTF " + " ".join(f"{x['rtf']:.2f}" for x in desktop["turbo"][-1]["sentences"])
        if not args.only_turbo:
            r, meta = run_nano(nano_dir, nvoice, n, record=first, bundle=bundle)
            desktop["nano"].append(r)
            if first:
                manifest["nano_sentences"] = meta
            line += " | nano RTF " + " ".join(f"{x['rtf']:.2f}" for x in desktop["nano"][-1]["sentences"])
        first = False
        print(line, flush=True)
    manifest["desktop"] = desktop
    (bundle / "manifest.json").write_bytes(json.dumps(manifest, ensure_ascii=False, indent=1).encode("utf-8"))
    print("bundle written to", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
