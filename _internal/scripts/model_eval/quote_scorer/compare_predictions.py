"""So các lần chạy BỘ CHẤM (và LLM) THEO CẶP TỪNG CÂU trên cùng một tập - ANALYSIS_RESEARCH.md.

    D:/Novels/LLM_Train/.venv/Scripts/python.exe scripts/model_eval/quote_scorer/compare_predictions.py \
        base=D:/Novels/LLM_Train/runs/scorer_vi_base,D:/Novels/LLM_Train/runs/scorer_vi_base_s7 \
        para=D:/Novels/LLM_Train/runs/scorer_vi_para_s1234 \
        --llm qwen3:8b=D:/Novels/Audiobooks/_model_eval_v2/21-09 [--split test]

Mỗi hệ = một hoặc nhiều thư mục lần chạy (các seed) có `<split>_predictions.jsonl`. Nhiều seed thì báo trung bình ±
độ lệch của từng lần VÀ một ensemble (trung bình xác suất biên từng thực thể + "không ai", lấy lớn nhất) - ensemble
là thứ đem so. Hệ đầu tiên là mốc: với mỗi hệ khác, trên đúng những câu CẢ HAI có, đếm câu chỉ mốc đúng / chỉ hệ kia
đúng, và p McNemar chính xác (nhị thức hai phía trên các câu bất đồng).

LLM (`--llm tên=thư mục gốc eval_models[@truyện]`): đọc speaker từng đoạn trong các project đã chạy trọn (lần mới nhất
mỗi chương, như paired.py), chấm bằng CÙNG đáp án của tập bộ chấm: gold có tên thì phải đúng tên chuẩn; gold người kể/
NPC ("không ai") thì LLM phải nói người kể/NPC - cùng độ dễ dãi với lựa chọn "không ai" của bộ chấm.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

NULL_KEYS = {"NARRATOR", "NPC*", "NPC", "?", "UNKNOWN"}
Key = tuple[str, str, int]  # (truyện, chương, seq)


def load_rows(run: Path | str, split: str) -> dict[Key, dict]:
    """`thư mục` = mô hình tốt nhất trên dev; `thư mục@last` = epoch cuối; `thư mục@3` = epoch 3 (runs/<x>/epochs/)."""
    run, _, epoch = str(run).partition("@")
    run = Path(run)
    if epoch:
        files = {int(path.name.split("_")[0]): path for path in (run / "epochs").glob(f"*_{split}_predictions.jsonl")}
        if not files:
            raise SystemExit(f"{run} không có dự đoán từng epoch (chạy trước bản vá 27-09 11:26)")
        path = files[max(files)] if epoch == "last" else files[int(epoch)]
    else:
        path = run / f"{split}_predictions.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {(row["book"], str(row["chapter"]), int(row["seq"])): row for row in rows}


def load_seed(spec: str, split: str) -> dict[Key, dict]:
    """Một lần chạy = hợp các fold: `a@last+b@last` hoặc mẫu `D:/runs/cv_para_f*@last` (kiểm chứng chéo)."""
    rows: dict[Key, dict] = {}
    for part in spec.split("+"):
        path, _, epoch = part.partition("@")
        folders = sorted(glob.glob(path)) if any(char in path for char in "*?[") else [path]
        if not folders:
            raise SystemExit(f"không thấy thư mục nào khớp {path}")
        for folder in folders:
            rows.update(load_rows(folder + (f"@{epoch}" if epoch else ""), split))
    return rows


def ensemble(runs: list[dict[Key, dict]]) -> dict[Key, dict]:
    """Trung bình xác suất biên qua các seed; câu nào thiếu xác suất (bản ghi cũ) thì bỏ phiếu theo đa số."""
    out: dict[Key, dict] = {}
    for key in set.intersection(*(set(run) for run in runs)):
        rows = [run[key] for run in runs]
        gold = rows[0]["gold"]
        if all(row.get("p_null") is not None for row in rows):
            totals: dict[str | None, float] = defaultdict(float)
            for row in rows:
                totals[None] += row["p_null"] / len(rows)
                for name, p in row["probs"].items():
                    totals[name] += p / len(rows)
            predicted = max(totals, key=lambda name: totals[name])
            correct = (predicted is None) if gold is None else predicted == gold
        else:
            correct = sum(bool(row["correct"]) for row in rows) * 2 > len(rows)
        out[key] = {**rows[0], "correct": bool(correct)}
    return out


def mcnemar(only_a: int, only_b: int) -> float:
    n = only_a + only_b
    if n == 0:
        return 1.0
    k = min(only_a, only_b)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def llm_rows(name: str, root: Path, book: str, reference: dict[Key, dict]) -> dict[Key, dict]:
    from paired import collect  # noqa: PLC0415
    from score_models import read_project, speaker_key  # noqa: PLC0415

    found = collect([root])
    if name not in found:
        raise SystemExit(f"không thấy model {name} dưới {root} (có: {sorted(found)})")
    out: dict[Key, dict] = {}
    for chapter, run in found[name].items():
        rows, _meta = read_project(Path(run["project"]), {chapter})
        spoken = {int(row["seq"]): speaker_key(row["speaker"]) for row in rows}
        for key, row in reference.items():
            if key[0] != book or key[1] != chapter or key[2] not in spoken:
                continue
            said = spoken[key[2]]
            gold = row["gold"]
            correct = (said in NULL_KEYS) if gold is None else said == speaker_key(gold)
            out[key] = {**row, "predicted": said, "correct": correct}
    return out


def accuracy(rows: dict[Key, dict], keys) -> tuple[int, int]:
    keys = [key for key in keys if key in rows]
    return sum(rows[key]["correct"] for key in keys), len(keys)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("systems", nargs="+",
                        help="tên=lần_chạy[,lần_chạy...] (nhiều seed -> ensemble); lần chạy = thư_mục[@epoch], hoặc "
                             "fold+fold / mẫu glob (kiểm chứng chéo); hệ đầu tiên là mốc")
    parser.add_argument("--llm", nargs="*", default=[], help="tên model=thư mục gốc eval_models[@truyện]")
    parser.add_argument("--split", default="test")
    args = parser.parse_args()

    systems: dict[str, dict[Key, dict]] = {}
    for spec in args.systems:
        name, _, paths = spec.partition("=")
        runs = [load_seed(path, args.split) for path in paths.split(",")]
        if len(runs) > 1:
            each = [sum(row["correct"] for row in run.values()) / len(run) for run in runs]
            print(f"{name}: {len(runs)} seed, từng lần {statistics.mean(each):.1%} ± {statistics.stdev(each):.1%} "
                  f"({', '.join(f'{value:.1%}' for value in each)})")
        systems[name] = ensemble(runs) if len(runs) > 1 else runs[0]
    reference_name = next(iter(systems))
    reference = systems[reference_name]
    for spec in args.llm:
        name, _, where = spec.partition("=")
        root, _, book = where.partition("@")
        # cùng tên model ở nhiều gốc (vd TMA và YMP chạy riêng) -> gộp thành một hệ
        systems.setdefault(name, {}).update(llm_rows(name, Path(root), book or "throne_of_magical_arcana", reference))

    books = sorted({key[0] for key in reference})
    header = f"{'hệ':28s} {'tất cả':>14s} {'có tên':>14s} {'không ai':>12s} " + " ".join(f"{b[:10]:>12s}" for b in books)
    print(header)
    for name, rows in systems.items():
        keys = list(rows)
        cells = []
        for subset in (keys, [k for k in keys if rows[k]["gold"] is not None], [k for k in keys if rows[k]["gold"] is None]):
            right, total = accuracy(rows, subset)
            cells.append(f"{right:4d}/{total:<4d}{right / max(1, total):6.1%}")
        per_book = []
        for book in books:
            right, total = accuracy(rows, [k for k in keys if k[0] == book])
            per_book.append(f"{right / total:12.1%}" if total else f"{'-':>12s}")
        print(f"{name:28s} {cells[0]:>14s} {cells[1]:>14s} {cells[2]:>12s} " + " ".join(per_book))

    print(f"\ntheo cặp với mốc {reference_name} (chỉ những câu cả hai cùng có):")
    for name, rows in systems.items():
        if name == reference_name:
            continue
        shared = [key for key in rows if key in reference]
        both = sum(reference[k]["correct"] and rows[k]["correct"] for k in shared)
        only_ref = sum(reference[k]["correct"] and not rows[k]["correct"] for k in shared)
        only_other = sum(rows[k]["correct"] and not reference[k]["correct"] for k in shared)
        ref_acc = (both + only_ref) / max(1, len(shared))
        other_acc = (both + only_other) / max(1, len(shared))
        print(f"  {name:26s} n={len(shared):4d}  mốc {ref_acc:6.1%}  hệ này {other_acc:6.1%}  "
              f"chỉ mốc đúng {only_ref:3d}  chỉ hệ này đúng {only_other:3d}  p McNemar {mcnemar(only_ref, only_other):.4f}  "
              f"trần hợp hai {(both + only_ref + only_other) / max(1, len(shared)):6.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
