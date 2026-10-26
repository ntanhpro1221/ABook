"""Dựng sách NGHE ĐƯỢC thử (có audio thật, mốc câu, mốc chữ) để đo và thử bộ phát - không đụng thư viện của người dùng.

Audio là giọng tổng hợp của Windows (SAPI, đọc ra FILE, không phát ra loa) ghép từng câu, nên mốc câu và mốc chữ khớp từng mẫu. Chữ truyện
là văn bản giả (xếp ngẫu nhiên từ một bộ từ, không lấy từ truyện nào). Mỗi chương là MP3 mono như dây chuyền xuất (48 kHz, 192 kbps).

  python -X utf8 make_audio_fixture.py <out> [--into-existing]
Không có --into-existing: tạo <out>/prefs.json + <out>/library mới. Có: thêm vào thư viện của <out> (vd deskqt_fixture, 200 cuốn chữ).
Sau đó: ABOOK_PREFERENCES=<out>/prefs.json.  Cuốn A có chỗ nghe dở (chương 2, giây 40) để app mở lên là nạp sẵn nó ở trạng thái dừng.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
INTERNAL = HERE.parents[1]
sys.path.insert(0, str(INTERNAL))
sys.path.insert(0, str(HERE))
from make_fixture import Host, cover_jpeg, WORDS  # noqa: E402

RATE = 48000
SENTENCE_GAP = 0.35
PARAGRAPH_GAP = 0.9


def ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def sentence(rng: random.Random, dialogue: bool) -> str:
    n = rng.choice([5, 7, 8, 9, 11, 13])
    words = [rng.choice(WORDS) for _ in range(n)]
    words[0] = words[0].capitalize()
    text = " ".join(words)
    if dialogue:
        return "“" + text + rng.choice([".", "!", "?"]) + "”"
    return text + "."


def make_script(rng: random.Random, chapter: int, title: str, sentences: int) -> list[dict]:
    """[{paragraph, text, kind, speaker}] - đoạn đầu là tiêu đề."""
    out = [{"paragraph": 0, "text": f"Chương {chapter} - {title}", "kind": "heading", "speaker": ""}]
    paragraph = 1
    while len(out) < sentences:
        for _ in range(rng.choice([2, 3, 3, 4, 5])):
            dialogue = rng.random() < 0.25
            out.append({"paragraph": paragraph, "text": sentence(rng, dialogue), "kind": "dialogue" if dialogue else "narration",
                        "speaker": rng.choice(["Lan", "Minh"]) if dialogue else ""})
            if len(out) >= sentences:
                break
        paragraph += 1
    return out


SAPI = r"""
param([string]$jobs)
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice('Microsoft David Desktop')
$s.Rate = 1
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(24000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$list = Get-Content -Raw -Encoding UTF8 $jobs | ConvertFrom-Json
foreach ($j in $list) {
  if (Test-Path $j.path) { continue }
  $s.SetOutputToWaveFile($j.path, $fmt)
  $s.Speak($j.text)
  $s.SetOutputToNull()
}
"""


def synthesize(jobs: list[tuple[str, Path]], workdir: Path) -> None:
    todo = [{"text": text, "path": str(path)} for text, path in jobs if not path.exists()]
    if not todo:
        return
    workdir.mkdir(parents=True, exist_ok=True)
    jobs_file = workdir / "jobs.json"
    jobs_file.write_bytes(json.dumps(todo, ensure_ascii=False).encode("utf-8"))
    script = workdir / "sapi.ps1"
    script.write_bytes(SAPI.encode("utf-8-sig"))
    subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), str(jobs_file)], check=True)


def load_wav(path: Path) -> np.ndarray:
    data, rate = sf.read(str(path), dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if rate != RATE:
        from scipy.signal import resample_poly
        data = resample_poly(data, RATE // 1000, rate // 1000).astype("float32")
    return data


def trimmed(data: np.ndarray) -> np.ndarray:
    """Bỏ lặng đầu / đuôi của câu SAPI (còn ~30 ms) để mốc sát tiếng."""
    loud = np.flatnonzero(np.abs(data) > 0.01)
    if not len(loud):
        return data
    return data[max(0, loud[0] - 400): loud[-1] + 400]


def encode_mp3(samples: np.ndarray, out: Path) -> None:
    raw = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
    subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-f", "s16le", "-ar", str(RATE), "-ac", "1", "-i", "-",
                    "-codec:a", "libmp3lame", "-b:a", "192k", str(out)], input=raw, check=True)


def sha256(path_or_bytes) -> dict:
    data = path_or_bytes.read_bytes() if isinstance(path_or_bytes, Path) else path_or_bytes
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def build_book(root: Path, key: str, title: str, chapters: list[tuple[str, int]], *, words: bool, timed: bool, seed: int, work: Path) -> Path:
    rng = random.Random(seed)
    files: dict[str, bytes | Path] = {}
    book_chapters = []
    jobs: list[tuple[str, Path]] = []
    plans = []
    for number, (chapter_title, count) in enumerate(chapters, start=1):
        lines = make_script(rng, number, chapter_title, count)
        paths = [work / "sapi" / f"{key}_{number}_{i}.wav" for i in range(len(lines))]
        jobs += [(line["text"], path) for line, path in zip(lines, paths)]
        plans.append((number, chapter_title, lines, paths))
    synthesize(jobs, work / "sapi")
    for number, chapter_title, lines, paths in plans:
        pieces: list[np.ndarray] = []
        segments = []
        clock = 0.0
        previous_paragraph = None
        for index, (line, path) in enumerate(zip(lines, paths)):
            speech = trimmed(load_wav(path))
            if index:
                gap = PARAGRAPH_GAP if line["paragraph"] != previous_paragraph else SENTENCE_GAP
                pieces.append(np.zeros(int(gap * RATE), dtype="float32"))
                clock += gap
            previous_paragraph = line["paragraph"]
            length = len(speech) / RATE
            segment = {
                "id": number * 1000 + index + 1, "seq": index + 1, "paragraph": line["paragraph"], "text": line["text"], "kind": line["kind"],
                "speaker": line["speaker"], "start": round(clock, 3) if timed else None, "end": round(clock + length, 3) if timed else None,
                "status": "verified",
            }
            if words and timed:
                tokens = line["text"].split()
                weights = np.array([max(1, len(t)) for t in tokens], dtype=float)
                edges = np.concatenate([[0], np.cumsum(weights / weights.sum())]) * length + clock
                segment["words"] = [[int(edges[i] * 1000), int(edges[i + 1] * 1000)] for i in range(len(tokens))]
            segments.append(segment)
            pieces.append(speech)
            clock += length
        mp3 = work / f"{key}_{number}.mp3"
        encode_mp3(np.concatenate(pieces), mp3)
        script = {"chapterId": number, "title": f"Chương {number} · {chapter_title}", "timed": timed, "duration": round(clock, 3), "segments": segments}
        script_bytes = json.dumps(script, ensure_ascii=False, indent=1).encode("utf-8")
        files[f"chapters/{number:05d}_{number}.mp3"] = mp3
        files[f"scripts/{number}.json"] = script_bytes
        book_chapters.append({
            "id": number, "index": number, "title": f"Chương {number}", "subtitle": chapter_title, "fullTitle": f"Chương {number} · {chapter_title}",
            "duration": round(clock, 1), "available": True, "file": f"chapters/{number:05d}_{number}.mp3", "size": mp3.stat().st_size,
            "script": f"scripts/{number}.json",
        })
    cast = {"narrator": {"voice": "Đức Trí", "lines": sum(len(p[2]) for p in plans), "seconds": 1.0}, "characters": [], "extras": []}
    files["cast.json"] = json.dumps(cast, ensure_ascii=False, indent=1).encode("utf-8")
    rngc = random.Random(seed + 1)
    files["cover.jpg"] = cover_jpeg(seed % 97, title, rngc)
    book = {
        "format": "abook-book/1", "title": title, "narrator": "Giọng thử", "duration": round(sum(c["duration"] for c in book_chapters), 1),
        "chaptersTotal": len(book_chapters), "chaptersAvailable": len(book_chapters), "complete": True,
        "version": hashlib.sha1(f"{key}{seed}".encode()).hexdigest()[:16], "chapters": book_chapters, "cast": "cast.json", "samples": [],
        "cover": {"version": 1, "color": "#9b562f", "width": 600, "height": 900, "file": "cover.jpg"},
    }
    sys.path.insert(0, str(INTERNAL))
    from abook.webui import bookfile
    out = work / f"{title}.abook"
    bookfile.seal(book, files, out, producer="ABook", version=bookfile.package_version(book))
    return out


BOOKS = [
    # khoá, tên, [(tên chương, số câu)], có mốc chữ, có mốc câu, hạt giống
    ("a", "Chuyện Thử Nghe", [("Mở đầu", 30), ("Con đường", 40), ("Bến sông", 60), ("Đêm dài", 150)], True, True, 11),
    ("b", "Sách Không Mốc", [("Một", 12), ("Hai", 14)], False, False, 22),
    ("c", "Giọng Cũ", [("Đầu", 25), ("Cuối", 25)], False, True, 33),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--into-existing", action="store_true")
    args = ap.parse_args()
    out = Path(args.out).resolve()
    prefs = out / "prefs.json"
    if not args.into_existing:
        (out / "library").mkdir(parents=True, exist_ok=True)
        prefs.write_bytes(json.dumps({"libraryRoot": str(out / "library")}).encode("utf-8"))
    work = out / "audio_src"
    host = Host(prefs)
    ids = {}
    try:
        for key, title, chapters, words, timed, seed in BOOKS:
            file = build_book(out, key, title, chapters, words=words, timed=timed, seed=seed, work=work)
            opened = host.call("POST", "/api/listen/open-book-file", {"path": str(file)})
            ids[key] = opened["id"]
            print(key, title, opened, flush=True)
        # Cuốn A đã nghe dở: chương 2, giây 40 - app mở lên nạp sẵn chỗ này.
        session = "fixture-session"
        host.call("POST", f"/api/listen/books/{ids['a']}/progress/session", {"sessionId": session})
        host.call("POST", f"/api/listen/books/{ids['a']}/progress", {"chapterId": 2, "seconds": 40.0, "duration": 100.0, "sessionId": session, "revision": 1})
        (out / "audio_books.json").write_bytes(json.dumps(ids).encode("utf-8"))
    finally:
        host.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
