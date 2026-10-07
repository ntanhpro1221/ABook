"""Bộ ví dụ DÙNG CHUNG cho bộ phân tích nhạc "trò" trên điện thoại (MusicStudent*.kt, docs/MUSIC_IMPORT.md "Giai đoạn B"): bản
Kotlin phải ra ĐÚNG những con số mà bản Python (webui/music_student.py, music_mel.py, đường onnx) ra cho cùng đầu vào.

    fixtures/music_student/stereo_44k.mp3   12 giây, stereo 44,1 kHz (ba cửa sổ 10 giây): nhạc tổng hợp, không phải nhạc của ai
    fixtures/music_student/mono_22k.mp3     5 giây, mono 22,05 kHz (một cửa sổ ngắn, repeatpad)
    fixtures/music_student/student_head_A.npz, vox_head.npz, preprocessor_config.json   bản sao ghim ở music_student.REVISION (53 KB + 7 KB): test đọc npz thật
    fixtures/music_student/golden.json      windows (n -> điểm bắt đầu), mel (tín hiệu tổng hợp xác định: vài khung + tổng),
                                            head (vector nhúng 512 chiều -> kết quả của đầu), tracks (kết quả đầy đủ của
                                            music_student.analyze trên mp3 qua ffmpeg + onnxruntime: để so với máy Android)

Sinh lại (chỉ khi cố ý đổi hành vi):
    runtime/.venv/Scripts/python.exe -m tests.music_student_goldens --model-dir <thư mục có clap_audio_fp16.onnx, student_head_A.npz,
                                                                      vox_head.npz, preprocessor_config.json>
(thêm --rebuild-audio để tổng hợp lại hai file mp3 - mp3 do ffmpeg mã hoá nên cần ffmpeg có libmp3lame).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

FIXTURES = Path(__file__).parent / "fixtures" / "music_student"
TRACKS = {"stereo_44k.mp3": (44_100, 2, 12.0), "mono_22k.mp3": (22_050, 1, 5.0)}
WINDOW_SIZES = [1, 100_000, 143_999, 144_000, 150_000, 479_999, 480_000, 480_001, 960_000, 1_200_000, 1_323_000, 5_000_001]
MEL_FRAMES = [0, 1, 2, 3, 250, 499, 500, 501, 750, 998, 999, 1000]
SHORT_SAMPLES = 150_000


def synth(rate: int, channels: int, seconds: float) -> np.ndarray:
    """Nhạc tổng hợp xác định (hợp âm đổi mỗi 2 giây, vài hoà âm, run biên độ, chút nhiễu): (mẫu, kênh) float32."""
    rng = np.random.RandomState(11)
    t = np.arange(int(rate * seconds)) / rate
    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (196.0, 246.94, 293.66), (164.81, 207.65, 246.94)]
    out = np.zeros((len(t), channels))
    for beat in range(int(np.ceil(seconds / 2.0))):
        start = beat * 2.0
        gate = np.clip((t - start) * 4, 0, 1) * np.clip((start + 2.4 - t) * 3, 0, 1)
        for voice_index, hz in enumerate(chords[beat % len(chords)]):
            voice = sum(np.sin(2 * np.pi * hz * k * t + k) / k**1.3 for k in (1, 2, 3, 4)) * gate
            voice = voice * (0.8 + 0.2 * np.sin(2 * np.pi * 5.3 * t))
            pan = voice_index / 2.0
            for c in range(channels):
                out[:, c] += voice * ((pan if c == 0 else 1.0 - pan) if channels > 1 else 1.0)
    out += rng.normal(0, 0.01, out.shape)  # nền ồn như thu âm thật: nếu không, mp3 để dải mel cao ở sàn -100 dB và số đầu ra nhạy với sai số 1e-5
    return (out / np.abs(out).max() * 0.6).astype(np.float32)


def encode(path: Path, samples: np.ndarray, rate: int) -> None:
    from abook.io_utils import ffmpeg_executable

    subprocess.run([ffmpeg_executable(), "-y", "-v", "error", "-f", "f32le", "-ar", str(rate), "-ac", str(samples.shape[1]), "-i", "-",
                    "-c:a", "libmp3lame", "-b:a", "192k", "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:a", "+bitexact", str(path)],
                   input=samples.astype("<f4").tobytes(), check=True)


def lcg_signal(count: int) -> np.ndarray:
    """Tín hiệu kiểm mel mà Kotlin dựng lại BẰNG SỐ NGUYÊN (không sin/cos): răng cưa + nhiễu trắng 32 bit, float32.
    x[i] = ((i * 2654435761) mod 2^32 >> 8) / 2^24 - 0.5, nhân 0,25, cộng ((i mod 100) / 100 - 0.5) * 0,5."""
    i = np.arange(count, dtype=np.uint64)
    noise = (((i * np.uint64(2_654_435_761)) & np.uint64(0xFFFFFFFF)) >> np.uint64(8)).astype(np.float64) / float(1 << 24) - 0.5
    saw = ((np.arange(count) % 100) / 100.0 - 0.5) * 0.5
    return (noise * 0.25 + saw).astype(np.float32)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, default=Path(os.environ.get("ABOOK_MUSIC_STUDENT_DIR", "")) if os.environ.get("ABOOK_MUSIC_STUDENT_DIR") else None)
    parser.add_argument("--rebuild-audio", action="store_true")
    args = parser.parse_args()
    if args.model_dir is None or not (args.model_dir / "student_head_A.npz").is_file():
        print("cần --model-dir có gói model của đường onnx", file=sys.stderr)
        return 2
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    os.environ["ABOOK_MUSIC_STUDENT_DIR"] = str(args.model_dir)
    os.environ["ABOOK_MUSIC_STUDENT_BACKEND"] = "onnx"
    from abook.webui import music_mel, music_student

    FIXTURES.mkdir(parents=True, exist_ok=True)
    if args.rebuild_audio:
        for name, (rate, channels, seconds) in TRACKS.items():
            encode(FIXTURES / name, synth(rate, channels, seconds), rate)
    for name in ("student_head_A.npz", "vox_head.npz", "preprocessor_config.json"):
        shutil.copyfile(args.model_dir / name, FIXTURES / name)

    golden: dict = {"windows": [], "mel": {}, "head": {}, "tracks": {}}
    for n in WINDOW_SIZES:
        windows = music_student._clap_windows(np.zeros(n, dtype=np.float32))
        golden["windows"].append({"n": n, "count": len(windows), "starts": sorted({min(max(int(n * f) - 240_000, 0), n - 480_000) for f in (0.2, 0.5, 0.8)}) if n > 480_000 else [0]})
    # mel: cửa sổ đủ 480000 mẫu và cửa sổ ngắn (repeatpad, lặp 3 lần + 0)
    for label, count in (("full", 480_000), ("short", SHORT_SAMPLES)):
        mel = music_mel.log_mel(lcg_signal(count))
        golden["mel"][label] = {"samples": count, "frames": MEL_FRAMES, "rows": [[float(v) for v in mel[f]] for f in MEL_FRAMES],
                                "sum": float(mel.astype(np.float64).sum()), "sumSquares": float((mel.astype(np.float64) ** 2).sum())}
    student = music_student._load()
    assert student is not None and student.backend == "onnx", "không nạp được đường onnx"
    for name in TRACKS:
        samples = music_mel.decode(FIXTURES / name, music_student.CLAP_RATE)
        clips = music_student._clap_windows(samples)
        embedding = student.embed(clips)
        golden["head"][name] = {"embedding": [float(v) for v in embedding], "result": student.predict(embedding)}
        starts = [] if not len(clips) else sorted({min(max(int(len(samples) * f) - 240_000, 0), len(samples) - 480_000) for f in (0.2, 0.5, 0.8)}) if len(samples) > 480_000 else [0]
        golden["tracks"][name] = {"samples": int(len(samples)), "starts": starts, "result": music_student.analyze(FIXTURES / name)}
    # kiểm: kết quả của analyze() trùng predict(embed()) (cùng đường)
    for name, entry in golden["tracks"].items():
        assert entry["result"] == golden["head"][name]["result"], name
    (FIXTURES / "golden.json").write_bytes((json.dumps(golden, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print("wrote", FIXTURES / "golden.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
