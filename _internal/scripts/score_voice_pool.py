"""Máy chấm kho giọng: chấm mọi preset bằng audio sách đã thu, rồi xem máy có xếp đúng phán quyết cũ của chủ sách không.

    python scripts/score_voice_pool.py --out <thư mục nháp>/voice_scores.json [--per-voice 30] [--speechbrain-path <thư mục>]

Chủ sách KHÔNG nghe (bộ nhớ "owner-never-labels", "no-more-listen-rounds"): kho giọng đạt chỉ được mở rộng bằng số. Nhưng
số chỉ được tin khi chính nó xếp đúng những gì tai chủ sách đã phán (giọng có bậc trong `voice_rank.json` vs NEVER_AUTO +
Adam bựa) - nên script này in cả phép hiệu chỉnh ấy, và `machine_approved` chỉ được ghi khi phép ấy qua.

Nguồn audio: `segments.wav_path` của các project sách (chỉ đọc), lấy tất định tối đa `--per-voice` câu mỗi preset, rải
đều giữa các sách, 2-12 giây. Thêm bản nghe thử `assets/voice_previews` (cùng câu, cùng hạt giống cho mọi giọng).

Đo mỗi câu:
- UTMOSv2 (`perceptual_qa.UTMOSNaturalnessVerifier`, CPU, cùng cấu hình dây chuyền) - độ tự nhiên dự đoán;
- ECAPA (speechbrain/spkrec-ecapa-voxceleb, dựng tay từ checkpoint đã cache - speechbrain cài ngoài venv bằng
  `pip install --target <thư mục> --no-deps speechbrain hyperpyyaml ruamel.yaml`) - độ ổn định giọng qua các câu (cos tới
  tâm của chính nó) và độ khác biệt (cos tới tâm giọng gần nhất);
- WER của ASR lấy sẵn trong `segments.asr_wer` (dây chuyền đã chấm khi thu).
"""
from __future__ import annotations

import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import argparse
import hashlib
import json
import sqlite3
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from abook.voice_catalog import NEVER_AUTO, VIENEU_PRESETS, VOICE_PREVIEW_FILENAMES, VOICE_RANK  # noqa: E402

HAND18 = Path("D:/Novels/Audiobooks/hand18")
DEFAULT_PROJECTS = (
    HAND18 / "all-you-need-is-kill/all_you_need_is_kill_novel_70be1348f4/project.sqlite3",
    HAND18 / "hello-hello-and-hello/build_20261112_122943/hello_hello_and_hello_e4e4d173ba/project.sqlite3",
    HAND18 / "nhung-gi-em-de-lai-cho-toi/build_20261110_223946/"
             "nhung_gi_em_de_lai_cho_toi_voi_mot_nam_con_lai_cua_cuoc_doi_af223a1dc8/project.sqlite3",
    HAND18 / "noi-ma-hai-ta-da-goi-dien/build_20261107_142937/noi_ma_hai_ta_da_goi_dien_33e49f5810/project.sqlite3",
)
PREVIEW_ROOT = Path(__file__).resolve().parent.parent / "abook" / "assets" / "voice_previews"
UTMOS_CHECKPOINT = Path(os.environ.get("ABOOK_RUNTIME", "D:/Novels/ABook/_internal/runtime")) / "models/utmosv2/fold0_s42_best_model.pth"
MIN_SECONDS, MAX_SECONDS = 2.0, 12.0
# Phán quyết TỆ của chủ sách: NEVER_AUTO, và Adam bựa (15-11: "đó không phải giọng tốt").
OWNER_BAD = frozenset(NEVER_AUTO | {"Adam bựa"})


def owner_good() -> dict[str, int]:
    """{preset: bậc nhân vật tốt nhất của chủ sách} cho mọi preset có bậc."""
    out: dict[str, int] = {}
    for gender, tiers in VOICE_RANK["character"].items():
        for index, tier in enumerate(tiers):
            for name in tier:
                out[name] = min(out.get(name, index), index)
    return out


def collect_clips(projects: list[Path], per_voice: int) -> dict[str, list[dict[str, Any]]]:
    pools: dict[str, list[list[dict[str, Any]]]] = {}
    for book_index, path in enumerate(projects):
        if not path.is_file():
            continue
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        for row in conn.execute(
            "SELECT v.preset_name, s.stable_id, s.wav_path, s.wav_duration, s.asr_wer FROM segments s "
            "JOIN voice_profiles v ON v.id = s.voice_profile_id WHERE s.wav_path IS NOT NULL AND s.wav_path <> '' "
            "AND s.wav_duration BETWEEN ? AND ?", (MIN_SECONDS, MAX_SECONDS),
        ):
            if not Path(row["wav_path"]).is_file():
                continue
            per_book = pools.setdefault(str(row["preset_name"]), [])
            while len(per_book) <= book_index:
                per_book.append([])
            per_book[book_index].append({
                "book": path.parent.name, "stable_id": str(row["stable_id"]), "wav": str(row["wav_path"]),
                "seconds": float(row["wav_duration"]), "asr_wer": None if row["asr_wer"] is None else float(row["asr_wer"]),
            })
        conn.close()
    picked: dict[str, list[dict[str, Any]]] = {}
    for preset, books in sorted(pools.items()):
        queues = [sorted(clips, key=lambda c: hashlib.sha1(c["stable_id"].encode()).hexdigest()) for clips in books]
        chosen: list[dict[str, Any]] = []
        while len(chosen) < per_voice and any(queues):
            for queue in queues:
                if queue and len(chosen) < per_voice:
                    chosen.append(queue.pop(0))
        picked[preset] = chosen
    return picked


class Ecapa:
    def __init__(self, speechbrain_path: str) -> None:
        if speechbrain_path:
            sys.path.insert(0, speechbrain_path)
        import torch
        import torchaudio

        if not hasattr(torchaudio, "list_audio_backends"):
            torchaudio.list_audio_backends = lambda: ["soundfile"]  # torchaudio 2.9+ bỏ hàm speechbrain gọi lúc nạp
        from speechbrain.lobes.features import Fbank
        from speechbrain.lobes.models.ECAPA_TDNN import ECAPA_TDNN
        from speechbrain.processing.features import InputNormalization

        hub = Path.home() / ".cache/huggingface/hub/models--speechbrain--spkrec-ecapa-voxceleb/snapshots"
        snap = sorted(hub.iterdir())[0]
        self.torch = torch
        self.fbank = Fbank(n_mels=80)
        self.norm = InputNormalization(norm_type="sentence", std_norm=False)
        self.model = ECAPA_TDNN(80, channels=[1024, 1024, 1024, 1024, 3072], kernel_sizes=[5, 3, 3, 3, 1],
                                dilations=[1, 2, 3, 4, 1], attention_channels=128, lin_neurons=192)
        self.model.load_state_dict(torch.load(snap / "embedding_model.ckpt", map_location="cpu"))
        self.model.eval()
        self.emb_norm = InputNormalization(norm_type="global", std_norm=False)
        self.emb_norm._load(snap / "mean_var_norm_emb.ckpt")
        self.emb_norm.eval()

    def embed(self, wav: Path) -> np.ndarray:
        import librosa
        import soundfile as sf

        audio, rate = sf.read(str(wav), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        audio = librosa.resample(audio, orig_sr=rate, target_sr=16000)
        torch = self.torch
        with torch.no_grad():
            signal = torch.tensor(audio)[None]
            lengths = torch.ones(1)
            feats = self.norm(self.fbank(signal), lengths)
            emb = self.model(feats, lengths)
            emb = self.emb_norm(emb, torch.ones(1))
        vector = emb.squeeze().numpy().astype(np.float64)
        return vector / (np.linalg.norm(vector) or 1.0)


def utmos_scorer(threads: int) -> Any:
    from abook.config import build_settings
    from abook.perceptual_qa import UTMOSNaturalnessVerifier

    settings = build_settings()
    settings["perceptual_qa"] = {**settings["perceptual_qa"], "enabled": True, "device": "cpu", "failure_policy": "fail",
                                 "checkpoint_path": str(UTMOS_CHECKPOINT), "worker_threads": threads}
    verifier = UTMOSNaturalnessVerifier(settings, lambda message: print(message, flush=True))
    verifier.load()
    return verifier


def _auc(good: list[float], bad: list[float]) -> float:
    """P(một giọng tốt ngẫu nhiên > một giọng tệ ngẫu nhiên), hoà tính nửa."""
    pairs = [(g > b) + 0.5 * (g == b) for g in good for b in bad]
    return sum(pairs) / len(pairs) if pairs else float("nan")


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    """Số mỗi giọng + phép hiệu chỉnh với phán quyết chủ sách. Chiều mọi chỉ số: cao hơn = tốt hơn."""
    clips = data["clips"]
    good, bad = data["owner_good"], set(data["owner_bad"])
    by: dict[str, list[dict[str, Any]]] = {}
    for clip in clips:
        by.setdefault(clip["preset"], []).append(clip)
    centroids = {}
    for name, items in by.items():
        book = [c for c in items if c["book"] != "preview"]
        if len(book) >= 3:
            matrix = np.array([c["ecapa"] for c in book])
            mean = matrix.mean(axis=0)
            centroids[name] = mean / np.linalg.norm(mean)
    voices: dict[str, dict[str, Any]] = {}
    for name, items in sorted(by.items()):
        book = [c for c in items if c["book"] != "preview"]
        preview = [c for c in items if c["book"] == "preview"]
        wers = [c["asr_wer"] for c in book if c["asr_wer"] is not None]
        row: dict[str, Any] = {
            "verdict": "tốt (bậc %d)" % good[name] if name in good else "tệ" if name in bad else "chưa xếp",
            "n": len(book),
            "utmos_mean": statistics.fmean(c["utmos"] for c in book) if book else None,
            "utmos_p10": float(np.percentile([c["utmos"] for c in book], 10)) if book else None,
            "utmos_sd": statistics.pstdev(c["utmos"] for c in book) if len(book) > 1 else None,
            "utmos_preview": preview[0]["utmos"] if preview else None,
            "wer_mean": statistics.fmean(wers) if wers else None,
            "ok_rate": sum(w <= 0.10 for w in wers) / len(wers) if wers else None,
        }
        if name in centroids:
            matrix = np.array([c["ecapa"] for c in book])
            row["ecapa_stability"] = float((matrix @ centroids[name]).mean())
            others = {o: float(centroids[name] @ v) for o, v in centroids.items() if o != name}
            nearest = max(others, key=others.get)
            row["ecapa_nearest"] = nearest
            row["ecapa_distinct"] = 1.0 - others[nearest]
        voices[name] = row
    metrics = ("utmos_mean", "utmos_p10", "utmos_preview", "ok_rate", "ecapa_stability", "ecapa_distinct")
    calibration = {}
    for metric in metrics:
        g = [voices[n][metric] for n in good if n in voices and voices[n].get(metric) is not None]
        b = [voices[n][metric] for n in bad if n in voices and voices[n].get(metric) is not None]
        auc = _auc(g, b)
        calibration[metric] = {
            "auc": auc, "good_min": min(g) if g else None, "bad_max": max(b) if b else None,
            "separates": bool(g and b and min(g) > max(b)), "n_good": len(g), "n_bad": len(b),
        }
    return {"voices": voices, "calibration": calibration}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--summarize", action="store_true", help="Chỉ đọc --out đã có và in bảng + hiệu chỉnh")
    parser.add_argument("--per-voice", type=int, default=30)
    parser.add_argument("--speechbrain-path", default="")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--projects", nargs="*", default=[str(p) for p in DEFAULT_PROJECTS])
    args = parser.parse_args()
    out = Path(args.out)
    if args.summarize:
        print(json.dumps(summarize(json.loads(out.read_text(encoding="utf-8"))), ensure_ascii=False, indent=1))
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    clips = collect_clips([Path(p) for p in args.projects], args.per_voice)
    print({name: len(rows) for name, rows in clips.items()}, flush=True)
    utmos = utmos_scorer(args.threads)
    ecapa = Ecapa(args.speechbrain_path)
    started = time.time()
    rows: list[dict[str, Any]] = []
    presets = {str(p["name"]): p for p in VIENEU_PRESETS}
    for name in sorted(presets):
        items = list(clips.get(name, []))
        preview = VOICE_PREVIEW_FILENAMES.get(name)
        if preview and (PREVIEW_ROOT / preview).is_file():
            items.append({"book": "preview", "stable_id": preview, "wav": str(PREVIEW_ROOT / preview), "seconds": None, "asr_wer": None})
        for item in items:
            item["preset"] = name
            item["utmos"] = utmos._score(Path(item["wav"]))
            item["ecapa"] = ecapa.embed(Path(item["wav"])).round(6).tolist()
            rows.append(item)
        print(f"{name}: {len(items)} câu, {time.time() - started:.0f}s", flush=True)
        out.write_text(json.dumps({"clips": rows}, ensure_ascii=False), encoding="utf-8")
    out.write_text(json.dumps({"clips": rows, "owner_good": owner_good(), "owner_bad": sorted(OWNER_BAD),
                               "presets": presets}, ensure_ascii=False), encoding="utf-8")
    print("XONG", out, flush=True)


if __name__ == "__main__":
    main()
