"""Nhãn tạm cho tự học theo cuốn (N4'): giữ phần câu bộ chấm CHẮC nhất, gán đúng lựa chọn của nó, bỏ các câu còn lại.

    D:/Novels/LLM_Train/.venv/Scripts/python.exe scripts/model_eval/quote_scorer/pseudo_label.py \
        --windows D:/Novels/LLM_Train/data/unlabeled/tma_para_cast.jsonl \
        --predictions D:/Novels/LLM_Train/runs/st/pred0/predictions.jsonl --keep 0.5 --out D:/.../pseudo0.jsonl

Xếp theo xác suất lớn nhất của câu (thứ tự không đổi theo nhiệt độ, nên không cần hiệu chỉnh) rồi giữ `--keep` phần
đầu. Đo 27-09 trên test: nửa câu chắc nhất đúng ~94%. Câu không giữ bị bỏ khỏi "quotes" (văn bản vẫn còn nguyên - chỉ
là không có nhãn để học). Nhãn "không ai" (người kể/NPC) được giữ như mọi nhãn khác.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--windows", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--keep", type=float, default=0.5, help="phần câu chắc nhất được giữ (0-1)")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    choice: dict[tuple[str, int], tuple[float, str | None]] = {}
    for line in args.predictions.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("p_null") is None:
            continue
        options = {**row["probs"], None: row["p_null"]}
        label = max(options, key=lambda name: options[name])
        choice[(str(row["chapter"]), int(row["seq"]))] = (options[label], label)
    ranked = sorted(choice.values(), key=lambda value: -value[0])
    cutoff = ranked[max(0, int(len(ranked) * args.keep) - 1)][0] if ranked else 1.0
    kept: Counter = Counter()
    windows_out = 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as writer:
        for line in args.windows.read_text(encoding="utf-8").splitlines():
            window = json.loads(line)
            quotes = []
            for quote in window["quotes"]:
                confidence, label = choice.get((str(quote["chapter"]), int(quote["seq"])), (0.0, None))
                if confidence < cutoff:
                    continue
                quote = {key: value for key, value in quote.items() if key != "unlabeled"} | {"speaker": label,
                                                                                            "pseudo": round(confidence, 4)}
                quotes.append(quote)
                kept["không ai" if label is None else "có tên"] += 1
            if quotes:
                writer.write(json.dumps({**window, "quotes": quotes}, ensure_ascii=False) + "\n")
                windows_out += 1
    total = sum(kept.values())
    print(f"giữ {total}/{len(choice)} câu ({total / max(1, len(choice)):.0%}, xác suất >= {cutoff:.4f}) trong {windows_out} "
          f"cửa sổ: {dict(kept)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
