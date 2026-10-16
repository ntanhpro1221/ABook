"""Kiểm tương đương của học sinh q06 cho "Nghe ngay": `ChapterStudent` trong tiến trình này so với `StudioChapterStudent` (tiến trình con serve của
Python Studio), cùng gói, cùng chương, hai bộ nhớ đệm trắng. Phải ra các mục (dV / dE / dT / chapterV) Y HỆT, rồi plan nhạc đầy đủ
(`music_nnscene.build_chapter`) của những chương ấy cũng y hệt. Chạy trên CPU, 2 luồng, không GPU.

    runtime/.venv/Scripts/python.exe scripts/music_nnstudio_check.py [--package <gói q06>] [--studio-python <python>] [--chapters 3]

Chữ chương và danh mục bài lấy của tests/test_music_nnscene.py (sách bịa, danh mục bịa); chỉ để so hai đường, không đo chất lượng."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"  # trước khi torch được nạp, ở cả hai bên
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abook.webui import music_nnscene, music_scene_student, music_scenes  # noqa: E402
from tests.test_music_nnscene import chapter_text, lookup, near  # noqa: E402

THREADS = 2
DEFAULT_PACKAGE = Path("D:/Novels/LLM_Train/music/pkg_scene_q06")


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def largest_gap(left: list[dict[str, Any]] | None, right: list[dict[str, Any]] | None) -> str:
    if left is None or right is None:
        return "none" if left is None and right is None else "one side None"
    if len(left) != len(right):
        return "length differs"
    gap = max((abs(a[key] - b[key]) for a, b in zip(left, right) for key in ("dV", "dE", "dT", "chapterV") if key in a and key in b), default=0.0)
    return f"{gap:.1e}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", default=str(DEFAULT_PACKAGE))
    parser.add_argument("--studio-python", default=sys.executable)
    parser.add_argument("--chapters", type=int, default=3)
    arguments = parser.parse_args()
    package = Path(arguments.package)
    if not music_scene_student._complete(package):
        print(f"No complete q06 package at {package}")
        return 2
    music_scene_student.configure(package)
    temporary = Path(tempfile.mkdtemp(prefix="nnstudio_"))
    order = list(range(1, arguments.chapters + 1))
    texts = {cid: chapter_text(1, cid) for cid in order}
    scripts = {cid: music_nnscene.chapter_script(cid, f"Chuong {cid}", texts[cid])[0] for cid in order}
    local = music_scene_student.ChapterStudent(package, temporary / "local.npz", log=lambda _line: None, threads=THREADS)
    studio = music_scene_student.StudioChapterStudent(
        arguments.studio_python, ROOT, {"PYTHONPATH": str(ROOT), "CUDA_VISIBLE_DEVICES": "-1"}, package, temporary / "studio.npz", threads=THREADS)
    failures = 0
    try:
        print(f"{'chapter':>7} {'scenes':>6} {'local s':>8} {'studio s':>9} {'items':>10} {'max gap':>8}")
        for cid in order:
            base = music_scenes.book_scenes([scripts[cid]])
            started = time.perf_counter()
            a = local.chapter(scripts[cid], base)
            middle = time.perf_counter()
            b = studio.chapter(scripts[cid], base)
            finished = time.perf_counter()
            same = a is not None and a == b
            failures += 0 if same else 1
            print(f"{cid:>7} {len(base):>6} {middle - started:>8.1f} {finished - middle:>9.1f} {'IDENTICAL' if same else 'DIFFERENT':>10} {largest_gap(a, b):>8}")
        # Plan đầy đủ lần lượt từng chương ở hai đường (cùng lịch sử bài vừa dùng).
        records: dict[str, list[dict[str, Any]]] = {}
        for name, worker in (("local", local), ("studio", studio)):
            book = music_nnscene.SceneBook(temporary / f"scene_{name}", {"book": "1", "catalog": "r1", "student": "q06"})
            records[name] = [music_nnscene.build_chapter(
                book, order, cid, f"Chuong {cid}", texts[cid], None, sha_of=lambda c: music_nnscene.text_sha(texts[c], None), near=near, lookup=lookup,
                catalog_revision="r1", taxonomy=None, book_key="nnstudio-check",
                student=lambda script, base, worker=worker: worker.chapter(script, base)) for cid in order]
        for cid, a, b in zip(order, records["local"], records["studio"]):
            same = canonical(a) == canonical(b)
            failures += 0 if same else 1
            print(f"plan chapter {cid}: {'IDENTICAL' if same else 'DIFFERENT'} ({len(a['scenes'])} scenes, student scenes "
                  f"{sum(1 for scene in a['scenes'] if scene.get('moodSource') == 'student')})")
        print("RESULT:", "all identical" if not failures else f"{failures} difference(s)")
    finally:
        local.close()
        studio.close()
        shutil.rmtree(temporary, ignore_errors=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
