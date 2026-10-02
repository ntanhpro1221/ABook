"""Bảng so các lượt đo trên bộ LN: F1 giọng (B-cubed, thước chính), người nói chặt, cảm xúc - từng chương và GỘP (vi mô,
theo câu), cho từng tiền tố gốc đo.

    python ln_table.py 28-09-ln-qwen3-8b 28-09-ln-turns-qwen3-8b 28-09-ln-lora3 ...

Chạy bằng venv của app, trong _internal của cây mã muốn dùng cho các lượt gom tên (mặc định main).
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import os

# ABOOK_ROOT: cây mã cho các lượt gom tên + đáp án (mặc định main đang đóng băng cho hàng GPU).
ROOT = Path(os.environ.get("ABOOK_ROOT", "D:/Novels/ABook/_internal"))
sys.path.insert(0, str(ROOT / "scripts" / "model_eval"))
sys.path.insert(0, str(ROOT))

from score_models import GOLD_ROOT, load_gold, read_project, speaker_credit  # noqa: E402
from voice_identity import bcubed, source_text, voice_of  # noqa: E402
try:
    from voice_identity import gold_person  # noqa: E402  (29-09 tối: NPC*:<mô tả> là một người)
except ImportError:
    def gold_person(entry):  # noqa: D103 - cây mã cũ chưa có
        return entry.speakers[0][0]

from abook.character_registry import canonical_speaker_names  # noqa: E402

EVAL = Path("D:/Novels/Audiobooks/_model_eval_v2")
CHAPTERS = [("tcf", "two_childhood_friends", "042"), ("nise", "nise_seiken", "132"), ("hdst", "huong_dan_sinh_ton", "062"),
            ("yamiyo", "yamiyo_no_hotaru", "141"), ("nageki", "nageki_no_bourei", "65"), ("lu", "love_unseen", "07")]


def chapter_points(root: Path, gold_dir: str, chapter: str):
    # Chỉ lượt đo ĐÃ XONG (eval_models.json ghi đủ chương): project đang phân tích dở có câu chưa có người nói.
    import json

    summary = root / "eval_models.json"
    if not summary.is_file() or not any(entry.get("chapters_ok") == entry.get("chapters") and entry.get("chapters")
                                        for entry in json.loads(summary.read_text(encoding="utf-8"))):
        return None
    gold = load_gold(GOLD_ROOT / gold_dir)
    model_dirs = [path for path in root.iterdir() if path.is_dir()] if root.is_dir() else []
    for model_dir in model_dirs:
        project = next((model_dir / chapter).rglob("project.sqlite3"), None)
        if project is None:
            continue
        rows_list, _meta = read_project(project.parent, {chapter})
        rows = {(str(row["chapter"]), int(row["seq"])): row for row in rows_list}
        mapping = canonical_speaker_names(Counter(str(row["speaker"] or "") for row in rows.values()),
                                          source_text([project.parent]))
        points, strict, emotion, lines = [], 0, 0, 0
        for key, entry in gold.items():
            if key[0] != chapter or key not in rows:
                continue
            lines += 1
            emotion += str(rows[key]["emotion"] or "") in entry.emotions
            if not entry.spoken:
                continue
            label = str(rows[key]["speaker"] or "")
            points.append((gold_person(entry), voice_of(label, key[0], mapping)))
            strict += speaker_credit(entry, label) >= 1.0
        return model_dir.name, points, strict, emotion, lines
    return None


def main(prefixes: list[str]) -> int:
    import contextlib
    import io

    header = "| lượt đo | " + " | ".join(name for name, _, _ in CHAPTERS) + " | GỘP F1 giọng | người nói chặt | cảm xúc |"
    print(header)
    print("|" + "---|" * (len(CHAPTERS) + 4))
    for prefix in prefixes:
        cells, all_points, strict_sum, spoken_sum, emotion_sum, line_sum = [], [], 0, 0, 0, 0
        model = ""
        for name, gold_dir, chapter in CHAPTERS:
            with contextlib.redirect_stdout(io.StringIO()):  # các lượt gom tên in nhật ký
                found = chapter_points(EVAL / f"{prefix}-{name}", gold_dir, chapter)
            if not found or not found[1]:
                cells.append("-")
                continue
            model, points, strict, emotion, lines = found
            cells.append(f"{bcubed(points)[2]:.1%}")
            all_points += [((name, person), (name, voice)) for person, voice in points]
            strict_sum += strict
            spoken_sum += len(points)
            emotion_sum += emotion
            line_sum += lines
        total = f"{bcubed(all_points)[2]:.1%}" if all_points else "-"
        strict_rate = f"{strict_sum / spoken_sum:.1%}" if spoken_sum else "-"
        emotion_rate = f"{emotion_sum / line_sum:.1%}" if line_sum else "-"
        print(f"| {prefix} ({model}) | " + " | ".join(cells) + f" | {total} ({spoken_sum} câu) | {strict_rate} | {emotion_rate} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
