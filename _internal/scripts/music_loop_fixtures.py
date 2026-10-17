"""Sinh bộ ví dụ DÙNG CHUNG cho mô hình lặp có điểm vòng (Corpus/research/music/PLAN_loop.md §10): `tests/fixtures/music_loop/` và ca
`tests/fixtures/music_timeline/loop_points.json`. Python (`music_mix.loop_bounds` / `loop_position` / `loop_schedule` / `music_timeline`) là
nguồn sự thật; trình phát máy tính (musicBed.test.ts) và điện thoại (MusicLoopTest.kt, MusicTimelineTest.kt) đọc đúng các file này và phải
ra cùng số (lệch <= 1 ms).

    with_points.json     bài có đoạn kết + điểm vòng hợp lệ
    without_points.json  bài không có điểm vòng; `legacy` = số của mã 0.4.89 (tính bằng mã cũ trước khi sửa, giữ nguyên khi sinh lại)
    invalid_points.json  điểm vòng không hợp lệ (`invalidVariants`): như không có, `legacy` như trên

Mỗi file: `track` (bài), `bounds` (vòng lặp), `ts` -> `positions` (chỗ trong bài sau t giây kể từ lúc vào từ A), `cues` = mỗi độ dài mốc:
`opens` (lúc mở phần tử lặp của mốc thường) và `tail` {opens, seconds} (mốc `tail`: lúc mở phần tử, lúc nhạc hết ở E của vòng cuối).
Sinh lại (chỉ khi cố ý đổi luật):  runtime/.venv/Scripts/python.exe scripts/music_loop_fixtures.py
Chỉ kiểm file trên đĩa còn khớp mã:  ... scripts/music_loop_fixtures.py --check
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abook.webui import music_mix

OUT = ROOT / "tests" / "fixtures" / "music_loop"
TIMELINE = ROOT / "tests" / "fixtures" / "music_timeline" / "loop_points.json"

TS = [0, 10.25, 100, 157.249, 157.25, 157.251, 200, 303.5, 303.51, 450.125, 1000.3, 3600.7]
BASE = {"seconds": 200, "audibleStart": 1.5, "audibleEnd": 190.25}
# Độ dài mốc: mốc `tail` dài từ chỗ bài hết ở vòng cuối tới dưới nửa chu kỳ sau đó (như music_select canh), để dòng thời gian
# của mốc ấy kết đúng ở E.
CASES: dict[str, dict[str, Any]] = {
    "with_points": {
        "description": "Bài có đoạn kết, điểm vòng hợp lệ: vòng đầu từ A; phần tử lặp mở ở loopEnd - X, phát từ loopStart; vòng cuối "
                       "của mốc tail chơi qua loopEnd tới E.",
        "track": {**BASE, "loopStart": 12.5, "loopEnd": 160.75},
        "lengths": [188.75, 340, 540, 700],
    },
    "without_points": {
        "description": "Bài không có điểm vòng: lặp E - X -> A như 0.4.89; legacy = số của mã 0.4.89.",
        "track": dict(BASE),
        "lengths": [188.75, 400, 600, 800],
    },
    "invalid_points": {
        "description": "Điểm vòng không hợp lệ (loopEnd - X vượt E, chu kỳ dưới loopMinPeriodSeconds, loopStart trước A, ngược, "
                       "thiếu một trường): như không có điểm vòng; legacy = số của mã 0.4.89.",
        "track": {**BASE, "loopStart": 12.5, "loopEnd": 195},
        "invalidVariants": [{"loopStart": 12.5, "loopEnd": 195}, {"loopStart": 100, "loopEnd": 111},
                            {"loopStart": 1.0, "loopEnd": 160.75}, {"loopStart": 160, "loopEnd": 150}, {"loopStart": 12.5}],
        "lengths": [188.75, 400, 600, 800],
    },
}


def bounds_json(bounds: music_mix.LoopBounds) -> dict[str, Any]:
    return {"start": bounds.start, "end": bounds.end, "period": bounds.period, "crossfade": bounds.crossfade,
            "loopStart": bounds.loop_start, "loopEnd": bounds.loop_end}


def loop_case(spec: dict[str, Any], legacy: Any) -> dict[str, Any]:
    track = spec["track"]
    bounds = music_mix.track_loop_bounds(track, track["seconds"])
    for variant in spec.get("invalidVariants", []):
        assert music_mix.track_loop_bounds({**BASE, **variant}, BASE["seconds"]) == music_mix.track_loop_bounds(BASE, BASE["seconds"])
    cues = []
    for length in spec["lengths"]:
        opens, _ = music_mix.loop_schedule(bounds, length)
        tail_opens, tail_end = music_mix.loop_schedule(bounds, length, tail=True)
        cues.append({"seconds": length, "opens": opens, "tail": {"opens": tail_opens, "seconds": tail_end}})
    out = {"description": spec["description"], "track": track, "bounds": bounds_json(bounds)}
    if "invalidVariants" in spec:
        out["invalidVariants"] = spec["invalidVariants"]
    out.update(ts=TS, positions=[music_mix.loop_position(bounds, t) for t in TS], cues=cues)
    if legacy is not None:
        out["legacy"] = legacy
    return out


def timeline_case() -> dict[str, Any]:
    """Một chương có bài điểm vòng: mốc tail kết ở E của vòng thứ hai rồi bài anh em vào; sau đó bài ấy mở lại thành mốc thường dài
    (ba phần tử lặp từ loopStart) và mờ ra cuối mốc."""
    tracks = {"a": CASES["with_points"]["track"], "b": {"seconds": 120, "audibleStart": 0, "audibleEnd": 115}}
    cues = [{"start": 0, "end": 335, "track": "a", "gainDb": -12, "tail": True},
            {"start": 335, "end": 520, "track": "b", "gainDb": -14, "sibling": True},
            {"start": 520, "end": 1000, "track": "a", "gainDb": -10}]
    return {"description": "Bài a có điểm vòng: mốc tail chơi qua loopEnd tới E của vòng 2 (335 s) rồi b vào; a mở lại ở 520, ba "
                           "phần tử lặp từ loopStart, mờ ra ở 1000.",
            "chapterSeconds": 1200, "tracks": tracks, "cues": cues,
            "timeline": music_mix.music_timeline(cues, 1200, tracks)}


def dump(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> int:
    check = "--check" in sys.argv[1:]
    files: dict[Path, bytes] = {}
    for name, spec in CASES.items():
        path = OUT / f"{name}.json"
        legacy = json.loads(path.read_bytes()).get("legacy") if path.is_file() else None
        assert name == "with_points" or legacy is not None, f"{path}: thiếu `legacy` (số của mã 0.4.89)"
        files[path] = dump(loop_case(spec, legacy))
    files[TIMELINE] = dump(timeline_case())
    stale = [path for path, data in files.items() if not path.is_file() or path.read_bytes() != data]
    if check:
        for path in stale:
            print(f"lệch mã: {path.relative_to(ROOT)}")
        return 1 if stale else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for path in stale:
        path.write_bytes(files[path])
        print(f"ghi {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
