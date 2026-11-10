"""Đo `music_library.select` trên một kho cỡ danh mục thật (2.387 bài): mỗi kiểu lọc / tìm phải dưới 50 ms.

Đo giờ nằm ở đây chứ không ở bộ test: số mili-giây phụ thuộc tải máy (tests/test_test_flakiness.py chỉ cho bớt chỗ đo giờ trong test).
Phần đúng/sai của bộ lọc do bảng ca chung tests/fixtures/music_library/cases.json lo.

    python -X utf8 scripts/bench_music_library.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from abook.webui import music_library  # noqa: E402

LIMIT_MS = 50.0


def catalogue(size: int = 2387):
    emotions = ["peacefulness", "joy", "power", "sadness"]
    tracks = {f"https://x/{index}": {"title": f"Bài số {index} Đêm", "creator": f"Người {index % 50}", "bpm": 60 + index % 120,
                                     "duration": 30 + index % 600, "style": ["piano", "ambient", "dark"][index % 3],
                                     "emotions": {name: ((index * 7 + offset * 13) % 100) / 100 for offset, name in enumerate(emotions)}}
              for index in range(size)}
    playlists = {"p": [f"https://x/{index}" for index in range(0, size, 7)]}
    return tracks, playlists


def main() -> int:
    tracks, playlists = catalogue()
    filters = ({}, {"q": "dem 12"}, {"emotion": "joy"}, {"playlist": "p", "tempo": "fast"}, {"style": "piano", "length": "long", "q": "nguoi"})
    for each in filters:  # ấm máy
        music_library.select(tracks, each, playlists, [])
    worst = 0.0
    for each in filters:
        started = time.perf_counter()
        music_library.select(tracks, each, playlists, [])
        ms = (time.perf_counter() - started) * 1000
        worst = max(worst, ms)
        print(f"music_library.select {len(tracks)} bài, {each}: {ms:.2f} ms")
    print(f"chậm nhất: {worst:.2f} ms (trần {LIMIT_MS:.0f} ms)")
    return 0 if worst < LIMIT_MS else 1


if __name__ == "__main__":
    raise SystemExit(main())
