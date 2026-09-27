"""Cửa sổ KHÔNG NHÃN từ các chương sản xuất của một truyện - cho tự học theo từng cuốn (N4', ANALYSIS_RESEARCH.md).

    D:/Novels/LLM_Train/.venv/Scripts/python.exe scripts/model_eval/quote_scorer/build_unlabeled.py \
        --projects "D:/Novels/Audiobooks/book2/_versions/*/*/project.sqlite3" --gold-book throne_of_magical_arcana \
        --out D:/Novels/LLM_Train/data/unlabeled_tma_para_cast.jsonl --layout paragraph --cast --max-chapters 200

App phân tích CẢ cuốn trước khi đọc, nên bộ chấm có thể tự học trên chính cuốn đang làm: chấm mọi câu, giữ câu nó chắc
(sau hiệu chỉnh: tin cậy >= 0,8 đúng 93-100% trên test 27-09) làm nhãn tạm, học thêm, chấm lại. Script này dựng phần
"mọi câu" đúng định dạng build_vi.py (cùng dàn trang, cùng danh sách nhân vật chương, bí danh từ bảng characters của
project). Mọi câu thoại (kind dialogue sau pha phân tích) vào "quotes" với "speaker": null và "unlabeled": true - KHÔNG
được đưa thẳng vào huấn luyện; pseudo_label.py thay bằng nhãn tạm cho câu đủ chắc và bỏ các câu còn lại.
Chương có trong gold của truyện bị bỏ (để phép đo trên gold không bị lọt).
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from build_vi import GOLD_ROOT, aliases_for, chapter_cast, join_segments, mention_spans, windows_for, with_cast  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--projects", required=True, help="glob tới các project.sqlite3 của truyện")
    parser.add_argument("--gold-book", required=True, help="thư mục gold của truyện (các chương ấy bị bỏ)")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--layout", choices=("line", "paragraph"), default="paragraph")
    parser.add_argument("--cast", action="store_true")
    parser.add_argument("--max-chapters", type=int, default=0, help="0 = tất cả; chọn các chương GẦN gold nhất trước")
    parser.add_argument("--tokenizer", default="jhu-clsp/mmBERT-base")
    parser.add_argument("--budget", type=int, default=1024)
    args = parser.parse_args()

    from transformers import AutoTokenizer  # noqa: PLC0415

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)

    def count_tokens(text: str) -> int:
        return len(tokenizer(text, add_special_tokens=False)["input_ids"])

    gold_numbers = {int(path.stem) for path in (GOLD_ROOT / args.gold_book).glob("*.txt") if path.stem.isdigit()}
    center = sum(gold_numbers) / max(1, len(gold_numbers))
    # chương -> (project, id chương) - chương có ở nhiều project (đúc lại) thì lấy project mới nhất theo tên
    where: dict[int, tuple[str, int, str]] = {}
    for database in sorted(glob.glob(args.projects)):
        connection = sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True)
        for chapter_id, title in connection.execute("SELECT id, title FROM chapters"):
            number = re.search(r"\d+", str(title))
            if number and int(number.group()) not in gold_numbers:
                pending = connection.execute("SELECT COUNT(*) FROM segments WHERE chapter_id = ? AND status = 'pending'",
                                             (chapter_id,)).fetchone()[0]
                if pending == 0:  # chỉ chương đã phân tích xong (kind đã chốt)
                    where[int(number.group())] = (database, int(chapter_id), str(title))
        connection.close()
    chosen = sorted(where, key=lambda number: (abs(number - center), number))
    if args.max_chapters:
        chosen = chosen[:args.max_chapters]
    stats: Counter = Counter()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as writer:
        for number in sorted(chosen):
            database, chapter_id, title = where[number]
            connection = sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True)
            display = {str(c): str(d or c) for c, d in connection.execute("SELECT canonical_name, display_name FROM characters")}
            aliases = aliases_for(set(display), display)
            rows = connection.execute("SELECT seq, text, kind, paragraph_index FROM segments WHERE chapter_id = ? ORDER BY seq",
                                      (chapter_id,)).fetchall()
            connection.close()
            segments = [(int(seq), str(text)) for seq, text, _, _ in rows]
            paragraph_of = {int(seq): int(paragraph) for seq, _, _, paragraph in rows}
            quotes = {int(seq): ("D", "?") for seq, _, kind, _ in rows if kind == "dialogue"}
            cast = chapter_cast(segments, aliases, None) if args.cast else []
            stats["chương"] += 1
            for lo, hi, seqs in windows_for(segments, quotes, args.budget, count_tokens):
                text, offsets = join_segments(segments[lo:hi + 1], paragraph_of if args.layout == "paragraph" else None)
                mentions = mention_spans(text, aliases)
                if args.cast:
                    text, offsets, mentions = with_cast(text, offsets, mentions, cast, display)
                items = [{"start": offsets[seq][0], "end": offsets[seq][1], "speaker": None, "unlabeled": True, "kind": "D",
                          "book": args.gold_book, "chapter": title, "seq": seq} for seq in seqs]
                stats["câu thoại"] += len(items)
                stats["cửa sổ"] += 1
                writer.write(json.dumps({"text": text, "quotes": items, "mentions": mentions}, ensure_ascii=False) + "\n")
    print(f"{dict(stats)}; chương {min(chosen)}-{max(chosen)} (gold quanh {center:.0f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
