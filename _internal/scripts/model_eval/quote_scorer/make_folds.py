"""Chia MỌI cửa sổ gold (train + dev + test) thành K phần theo CHƯƠNG, cho kiểm chứng chéo bộ chấm.

    D:/Novels/LLM_Train/.venv/Scripts/python.exe scripts/model_eval/quote_scorer/make_folds.py \
        D:/Novels/LLM_Train/data/quote_vi_para_cast [--folds 5]

Vì sao (27-09): tập test cố định chỉ 185 câu của 2 truyện - bộ chấm hơn LLM 6 điểm mà McNemar vẫn p = 0,18, và một
lượt so cấu hình (dàn trang theo paragraph) lệch 33 điểm chỉ ở MỘT chương ngôi thứ nhất. Kiểm chứng chéo cho mỗi câu
gold một dự đoán từ mô hình chưa thấy chương của nó: ~1.900 câu, cả 10 truyện. Chương là đơn vị chia (các câu trong
một chương không độc lập), gán tham lam chương lớn trước vào phần đang ít câu nhất -> các phần cân nhau và mỗi truyện
nhiều chương rải khắp các phần. Ghi `fold0.jsonl` ... `fold{K-1}.jsonl` cạnh train/dev/test, cùng `folds.json`.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("data", type=Path)
    parser.add_argument("--folds", type=int, default=5)
    args = parser.parse_args()

    windows = []
    for name in ("train", "dev", "test"):
        windows += [json.loads(line) for line in (args.data / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
                    if line.strip()]
    by_chapter: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for window in windows:
        chapters = {(quote["book"], str(quote["chapter"])) for quote in window["quotes"]}
        assert len(chapters) == 1, chapters
        by_chapter[chapters.pop()].append(window)
    size = {key: sum(len(window["quotes"]) for window in group) for key, group in by_chapter.items()}
    load = [0] * args.folds
    assignment: dict[str, int] = {}
    for key in sorted(size, key=lambda key: (-size[key], key)):
        fold = min(range(args.folds), key=lambda index: (load[index], index))
        assignment["/".join(key)] = fold
        load[fold] += size[key]
    for fold in range(args.folds):
        with (args.data / f"fold{fold}.jsonl").open("w", encoding="utf-8") as handle:
            for key, group in sorted(by_chapter.items()):
                if assignment["/".join(key)] == fold:
                    handle.writelines(json.dumps(window, ensure_ascii=False) + "\n" for window in group)
        books = sorted({key.split("/")[0] for key, value in assignment.items() if value == fold})
        print(f"fold{fold}: {load[fold]} câu, {sum(v == fold for v in assignment.values())} chương, {len(books)} truyện")
    (args.data / "folds.json").write_text(json.dumps(assignment, ensure_ascii=False, indent=1, sort_keys=True),
                                          encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
