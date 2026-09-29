"""Câu 『』 (và đối đáp liền) trên bộ LN gốc: đáp án vs nhãn của hai lượt model - ai bị gán thành ai.

    python bracket_flip.py 28-09-ln-lora3n 29-09-ln-lora6
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "D:/Novels/ABook/_internal/scripts/model_eval")
sys.path.insert(0, "D:/Novels/ABook/_internal")
from score_models import GOLD_ROOT, load_gold, read_project  # noqa: E402

EVAL = Path("D:/Novels/Audiobooks/_model_eval_v2")
BASE = [("tcf", "two_childhood_friends", "042"), ("nise", "nise_seiken", "132"), ("hdst", "huong_dan_sinh_ton", "062"),
        ("yamiyo", "yamiyo_no_hotaru", "141"), ("nageki", "nageki_no_bourei", "65"), ("lu", "love_unseen", "07")]


def rows_of(prefix: str, short: str, chapter: str) -> dict[int, dict]:
    project = next((EVAL / f"{prefix}-{short}").rglob("project.sqlite3"), None)
    if project is None:
        return {}
    rows, _extra = read_project(project.parent, {chapter})
    return {int(row["seq"]): row for row in rows}


def main(a: str, b: str) -> None:
    for short, gold_dir, chapter in BASE:
        gold = {seq: row for (ch, seq), row in load_gold(GOLD_ROOT / gold_dir).items() if ch == chapter}
        ra, rb = rows_of(a, short, chapter), rows_of(b, short, chapter)
        flips: Counter = Counter()
        total = 0
        for seq, row in sorted(gold.items()):
            line = ra.get(seq) or rb.get(seq)
            if not row.spoken or line is None or not str(line["text"]).lstrip().startswith("『"):
                continue
            total += 1
            want = row.speakers[0][0] if row.speakers else ""
            got_a = str((ra.get(seq) or {}).get("speaker") or "?").upper()
            got_b = str((rb.get(seq) or {}).get("speaker") or "?").upper()
            flips[(want, got_a, got_b)] += 1
        if not total:
            continue
        print(f"{short}: {total} câu 『』")
        for (want, got_a, got_b), count in flips.most_common(8):
            print(f"   {count:3d}  đáp án {want:20.20} | {a[-6:]}: {got_a:24.24} | {b[-6:]}: {got_b:24.24}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
