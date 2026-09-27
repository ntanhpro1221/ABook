"""Duyệt k% câu khó nhất thì đúng thêm bao nhiêu? - chọn tín hiệu xếp hạng cho hộp "Việc cần anh" (STUDIO_REVIEW.md).

    D:/Novels/LLM_Train/.venv/Scripts/python.exe scripts/model_eval/quote_scorer/review_curve.py \
        D:/Novels/LLM_Train/runs/st/ctrl@last --llm "lora27-4b:latest=D:/Novels/Audiobooks/_model_eval_v2/27-09-lora"

Máy quyết nhãn (LLM một mình - cái app đang làm); người nghe lại k% câu thoại theo một thứ tự rồi sửa đúng. So các thứ tự:
bộ chấm (độ tin cậy đã hiệu chỉnh của lựa chọn tốt nhất, thấp trước; hoặc "bộ chấm không đồng ý với LLM" trước), độ tin
cậy LLM tự báo (thấp trước), ngẫu nhiên (trung bình 500 lần xáo), và trần (câu sai trước). Chấm chặt như combine_eval.
"""

from __future__ import annotations

import argparse
import math
import random
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from compare_predictions import load_seed, official_gold  # noqa: E402

SHARES = (0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50)


def llm_confidences(root: Path, name: str, book: str) -> dict[tuple[str, str, int], tuple[str, float]]:
    """(truyện, chương, seq) -> (nhãn người nói, độ tin cậy LLM tự báo), đọc thẳng SQLite của project eval."""
    from paired import collect  # noqa: PLC0415
    from score_models import speaker_key  # noqa: PLC0415

    out = {}
    for chapter, run in collect([root])[name].items():
        db = sqlite3.connect(f"file:{Path(run['project']) / 'project.sqlite3'}?mode=ro", uri=True)
        for seq, speaker, confidence in db.execute(
            "SELECT s.seq, s.speaker, s.confidence FROM segments s JOIN chapters c ON c.id = s.chapter_id"
        ):
            out[(book, chapter, int(seq))] = (speaker_key(speaker), float(confidence))
        db.close()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scorer", help="lần chạy bộ chấm (cú pháp compare_predictions)")
    parser.add_argument("--llm", required=True, help="tên model=thư mục gốc eval_models[@truyện]")
    parser.add_argument("--temperature", type=float, default=6.0)
    args = parser.parse_args()

    from score_models import speaker_key  # noqa: PLC0415

    accepted = official_gold()
    scorer = load_seed(args.scorer, "test")
    model, _, where = args.llm.partition("=")
    root, _, book = where.partition("@")
    llm = llm_confidences(Path(root), model, book or "throne_of_magical_arcana")

    def best(row) -> tuple[str | None, float]:
        options = {**row["probs"], None: row["p_null"]}
        scaled = {name: math.log(max(1e-12, p)) / args.temperature for name, p in options.items()}
        top = max(scaled.values())
        total = sum(math.exp(value - top) for value in scaled.values())
        choice = max(scaled, key=scaled.get)
        return choice, math.exp(scaled[choice] - top) / total

    rows = []
    for key, row in scorer.items():
        if key not in llm or key not in accepted:
            continue
        label, confidence = llm[key]
        choice, certainty = best(row)
        agrees = choice is not None and speaker_key(choice) == label
        rows.append({
            "correct": label in accepted[key],
            "llm_conf": confidence,
            "scorer_conf": certainty,
            # Bộ chấm chắc về một người có tên KHÁC nhãn LLM: dấu hiệu mạnh nhất rằng LLM sai.
            "disagree": 0.0 if agrees or choice is None else certainty,
        })
    total = len(rows)
    base = sum(row["correct"] for row in rows)
    orders = {
        "trần (câu sai trước)": sorted(rows, key=lambda row: row["correct"]),
        "bộ chấm: bất đồng chắc trước": sorted(rows, key=lambda row: (-row["disagree"], row["scorer_conf"])),
        "bộ chấm: tin cậy thấp trước": sorted(rows, key=lambda row: row["scorer_conf"]),
        "LLM tự báo: thấp trước": sorted(rows, key=lambda row: row["llm_conf"]),
    }
    print(f"{total} câu thoại/nội tâm, máy một mình đúng {base} ({base / total:.1%})\n")
    header = "".join(f"{share:>7.0%}" for share in SHARES)
    print(f"{'thứ tự duyệt':32}{header}")
    for name, ordered in orders.items():
        cells = []
        for share in SHARES:
            reviewed = round(share * total)
            fixed = sum(not row["correct"] for row in ordered[:reviewed])
            cells.append(f"{(base + fixed) / total:>7.1%}")
        print(f"{name:32}{''.join(cells)}")
    rng = random.Random(1234)
    sums = [0.0] * len(SHARES)
    for _ in range(500):
        shuffled = rows[:]
        rng.shuffle(shuffled)
        for index, share in enumerate(SHARES):
            reviewed = round(share * total)
            sums[index] += (base + sum(not row["correct"] for row in shuffled[:reviewed])) / total
    print(f"{'ngẫu nhiên (500 lần)':32}{''.join(f'{value / 500:>7.1%}' for value in sums)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
