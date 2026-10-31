"""Chạy ma trận đo lõi phát (D1 bước 1). Mọi lượt có ABOOK_MUTE=1 (âm lượng 0). Kết quả: một dòng JSON mỗi lượt vào <out>.
  python -X utf8 run_matrix.py <host.json> <out.jsonl> [--seconds 30] [--repeat 3]
"""
import argparse
import json
import os
import subprocess
from pathlib import Path

ROOT = Path("D:/Novels/native_desk_proto/audiobench")
ap = argparse.ArgumentParser()
ap.add_argument("host")
ap.add_argument("out")
ap.add_argument("--seconds", type=float, default=30)
ap.add_argument("--repeat", type=int, default=3)
ap.add_argument("--only", default="")
args = ap.parse_args()
info = json.loads(Path(args.host).read_text(encoding="utf-8"))
book = info["books"]["a"]


def url(chapter: int) -> str:
    return f"{info['base']}/media/books/{book}/chapters/{chapter}?t={info['token']}"


ENGINES = [("mf", ROOT / "mf" / "audiobench_mf.exe", {}),
           ("qt-ffmpeg", ROOT / "qt" / "audiobench_qt.exe", {"QT_MEDIA_BACKEND": "ffmpeg"}),
           ]
if os.environ.get("BENCH_QT_WINDOWS"):
    ENGINES.append(("qt-windows", ROOT / "qt" / "audiobench_qt.exe", {"QT_MEDIA_BACKEND": "windows"}))
out = Path(args.out)


def run(engine, exe, extra, mode, extra_args, label):
    env = dict(os.environ, ABOOK_MUTE="1", **extra)
    cmd = [str(exe), "--engine", "mf" if engine == "mf" else "qt", "--mode", mode, "--out", str(out), *extra_args]
    try:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
        line = (proc.stdout.strip().splitlines() or ['{"error":"no output"}'])[-1]
    except subprocess.TimeoutExpired:
        line = '{"error":"timeout"}'
    print(engine, label, line, flush=True)


for engine, exe, extra in ENGINES:
    if args.only and engine != args.only:
        continue
    for rate in (1.0, 1.5, 2.0, 3.0):
        for i in range(args.repeat):
            run(engine, exe, extra, "play", ["--url", url(4), "--start", "20", "--rate", str(rate), "--seconds", str(args.seconds), "--volume", "1.0"], f"play x{rate} #{i}")
    run(engine, exe, extra, "seek", ["--url", url(4), "--start", "5", "--targets", "300,12,420,200,60,380", "--volume", "1.0"], "seek")
    run(engine, exe, extra, "gap", ["--url", url(1), "--url2", url(2), "--start", "78", "--volume", "1.0"], "gap")
