"""Nhãn tạm cho tự học theo cuốn (N4'): giữ phần câu bộ chấm CHẮC nhất, gán đúng lựa chọn của nó, bỏ các câu còn lại.

    D:/Novels/LLM_Train/.venv/Scripts/python.exe scripts/model_eval/quote_scorer/pseudo_label.py \
        --windows D:/Novels/LLM_Train/data/unlabeled/tma_para_cast.jsonl \
        --predictions D:/Novels/LLM_Train/runs/st/pred0/predictions.jsonl --keep 0.5 --out D:/.../pseudo0.jsonl \
        [--rank margin] [--balance]

Xếp câu theo độ chắc rồi giữ `--keep` phần đầu. Đo 27-09 trên test: nửa câu chắc nhất đúng ~94%. Câu không giữ bị bỏ
khỏi "quotes" (văn bản vẫn còn nguyên - chỉ là không có nhãn để học). Nhãn "không ai" (người kể/NPC) giữ như mọi nhãn.

Hai bài học vòng đầu (27-09 14:0x, TMA làm truyện mới):
- `--rank prob` (mặc định cũ): xác suất lớn nhất BÃO HOÀ - cả nửa trên đều >= 1,0000, nên cắt ở 50% là chọn tuỳ ý giữa
  các câu "chắc như nhau". `--rank margin` xếp theo log p(nhất) - log p(nhì), còn phân biệt được khi p đã bằng 1.
- Chọn chung một ngưỡng thì 2.220/2.220 nhãn tạm là câu CÓ TÊN (người kể/NPC luôn kém chắc hơn): học thêm làm độ đúng
  "không ai" tụt 34,5% -> 26,1%. `--balance` giữ `--keep` phần chắc nhất TRONG TỪNG LỚP dự đoán (có tên / không ai).
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--windows", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--keep", type=float, default=0.5, help="phần câu chắc nhất được giữ (0-1)")
    parser.add_argument("--rank", choices=("prob", "margin"), default="prob")
    parser.add_argument("--balance", action="store_true", help="giữ --keep phần chắc nhất trong TỪNG lớp (có tên / không ai)")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    choice: dict[tuple[str, int], tuple[float, str | None]] = {}
    for line in args.predictions.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("p_null") is None:
            continue
        options = {**row["probs"], None: row["p_null"]}
        ranked = sorted(options.items(), key=lambda item: -item[1])
        label, best = ranked[0]
        second = ranked[1][1] if len(ranked) > 1 else 0.0
        score = best if args.rank == "prob" else math.log(max(best, 1e-12)) - math.log(max(second, 1e-12))
        choice[(str(row["chapter"]), int(row["seq"]))] = (score, label)

    def cutoff(values: list[float]) -> float:
        ordered = sorted(values, reverse=True)
        return ordered[max(0, int(len(ordered) * args.keep) - 1)] if ordered else math.inf

    if args.balance:
        by_class = {named: cutoff([score for score, label in choice.values() if (label is not None) == named])
                    for named in (True, False)}
        threshold = {key: by_class[label is not None] for key, (_, label) in choice.items()}
    else:
        common = cutoff([score for score, _ in choice.values()])
        threshold = {key: common for key in choice}

    kept: Counter = Counter()
    windows_out = 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as writer:
        for line in args.windows.read_text(encoding="utf-8").splitlines():
            window = json.loads(line)
            quotes = []
            for quote in window["quotes"]:
                key = (str(quote["chapter"]), int(quote["seq"]))
                if key not in choice:
                    continue
                score, label = choice[key]
                if score < threshold[key]:
                    continue
                quote = {name: value for name, value in quote.items() if name != "unlabeled"} | {
                    "speaker": label, "pseudo": round(score, 4)}
                quotes.append(quote)
                kept["không ai" if label is None else "có tên"] += 1
            if quotes:
                writer.write(json.dumps({**window, "quotes": quotes}, ensure_ascii=False) + "\n")
                windows_out += 1
    total = sum(kept.values())
    print(f"giữ {total}/{len(choice)} câu ({total / max(1, len(choice)):.0%}, xếp theo {args.rank}"
          f"{', cân từng lớp' if args.balance else ''}) trong {windows_out} cửa sổ: {dict(kept)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
