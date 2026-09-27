"""Đo CHẶT hệ kết hợp bộ chấm + LLM - thước đo đúng cho quyết định app (ANALYSIS_RESEARCH.md, đính chính 27-09).

    D:/Novels/LLM_Train/.venv/Scripts/python.exe scripts/model_eval/quote_scorer/combine_eval.py \
        "tự học=D:/Novels/LLM_Train/runs/st/m_bal@last" \
        --llm "lora27-4b:latest=D:/Novels/Audiobooks/_model_eval_v2/27-09-lora" "qwen3:8b=D:/.../21-09"

Bộ chấm không đặt được nhãn người kể/NPC (lựa chọn "không ai" của nó gộp NARRATOR, NPC*, UNKNOWN), mà trong app mỗi câu
phải thành MỘT giọng cụ thể và cách chấm chính thức (score_models) coi NARRATOR và NPC* là hai giọng khác nhau. Nên đơn vị
đo là hệ kết hợp: bộ chấm quyết người nói CÓ TÊN khi độ tin cậy (nhiệt độ T) >= θ, còn lại lấy đúng nhãn của LLM. θ chọn
bằng kiểm chứng chéo bỏ-một-chương (chọn trên các chương kia, đo trên chương bị bỏ). Chấm chặt: nhãn phải là người nói đủ
điểm (không có chuyện "không ai" dễ dãi). Hệ bộ chấm dùng cú pháp của compare_predictions (glob / fold+fold / @epoch).
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from compare_predictions import llm_rows, load_seed, mcnemar, official_gold  # noqa: E402

GRID = (0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.01)  # 1,01 = không bao giờ tin bộ chấm (LLM một mình)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scorers", nargs="+", help="tên=lần_chạy (như compare_predictions)")
    parser.add_argument("--llm", nargs="+", required=True, help="tên model=thư mục gốc eval_models[@truyện] (lặp tên để gộp gốc)")
    parser.add_argument("--temperature", type=float, default=6.0)
    args = parser.parse_args()

    from score_models import speaker_key  # noqa: PLC0415

    accepted = official_gold()

    def strict(label, key) -> bool:
        return label is not None and speaker_key(label) in accepted[key]

    def choice(row) -> tuple[str | None, float]:
        options = {**row["probs"], None: row["p_null"]}
        scaled = {name: math.log(max(1e-12, p)) / args.temperature for name, p in options.items()}
        top = max(scaled.values())
        total = sum(math.exp(value - top) for value in scaled.values())
        best = max(scaled, key=scaled.get)
        return best, math.exp(scaled[best] - top) / total

    for spec in args.scorers:
        name, _, runs = spec.partition("=")
        scorer = load_seed(runs, "test")
        llms: dict[str, dict] = {}
        for llm_spec in args.llm:
            model, _, where = llm_spec.partition("=")
            root, _, book = where.partition("@")
            llms.setdefault(model, {}).update(llm_rows(model, Path(root), book or "throne_of_magical_arcana", scorer))
        for model, rows in llms.items():
            keys = [key for key in rows if key in accepted and scorer[key].get("p_null") is not None]

            def combined(threshold: float, key) -> bool:
                label, confidence = choice(scorer[key])
                if label is not None and confidence >= threshold:
                    return strict(label, key)
                return strict(rows[key]["predicted"], key)

            chosen, right = [], 0
            for chapter in sorted({(key[0], key[1]) for key in keys}):
                train = [key for key in keys if (key[0], key[1]) != chapter]
                test = [key for key in keys if (key[0], key[1]) == chapter]
                threshold = max(GRID, key=lambda t: (sum(combined(t, key) for key in train), -t))
                chosen.append(threshold)
                right += sum(combined(threshold, key) for key in test)
            alone = sum(strict(rows[key]["predicted"], key) for key in keys)
            # Theo cặp: hệ kết hợp (ngưỡng CV của từng chương) vs LLM một mình, trên cùng câu
            per_key = {}
            for chapter, threshold in zip(sorted({(key[0], key[1]) for key in keys}), chosen):
                for key in keys:
                    if (key[0], key[1]) == chapter:
                        per_key[key] = combined(threshold, key)
            only_combined = sum(per_key[key] and not strict(rows[key]["predicted"], key) for key in keys)
            only_llm = sum(strict(rows[key]["predicted"], key) and not per_key[key] for key in keys)
            print(f"{name} + {model}: n={len(keys)}  {model} một mình {alone / len(keys):.1%}  ->  kết hợp {right / len(keys):.1%}"
                  f"  (chỉ kết hợp đúng {only_combined}, chỉ LLM đúng {only_llm}, p McNemar {mcnemar(only_combined, only_llm):.4f};"
                  f" θ theo chương {chosen})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
