"""N1 - che dấu hiệu: biến câu thoại TƯỜNG MINH của các chương chưa gán nhãn thành câu NGẦM biết chắc đáp án.

    D:/Novels/LLM_Train/.venv/Scripts/python.exe scripts/model_eval/quote_scorer/build_cue_masked.py \
        --projects "D:/Novels/Audiobooks/book2/_versions/*/*/project.sqlite3" --out D:/Novels/LLM_Train/data/quote_vi_cue

Ý tưởng riêng của project (ANALYSIS_RESEARCH.md): chỉ 7,5% câu thoại truyện dịch có thẻ "<Tên> nói" (đo trên gold
27-09) và luật đọc thẻ đúng 95,5% - còn lại là câu ngầm/đại từ, loại khó nhất. Lấy câu có thẻ, XOÁ đoạn lời kể chứa
thẻ (chỉ khi đoạn ấy ngắn, gần như chỉ có thẻ), là được một câu ngầm trong đúng thể loại, đúng ngôn ngữ, có nhãn -
hàng nghìn câu từ các chương sản xuất mà không cần làm thêm gold.

Chương có trong đáp án chuẩn (mọi truyện) bị BỎ HẲN, để tập test (build_training_set.SPLIT) không lọt vào huấn luyện.
Mỗi dòng ra cùng dạng với build_vi.py; chỉ câu đã che nằm trong "quotes" (câu khác trong cửa sổ không có nhãn).
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

from build_vi import GOLD_ROOT, aliases_for, join_segments, mention_spans, windows_for  # noqa: E402
from cues import explicit_labels  # noqa: E402

MAX_TAG_CHARS = 60  # đoạn chứa thẻ dài hơn thì trong đó còn nội dung khác - không xoá được sạch


def gold_chapter_numbers() -> set[int]:
    numbers = set()
    for path in GOLD_ROOT.glob("*/*.txt"):
        if path.stem.isdigit():
            numbers.add(int(path.stem))
    return numbers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--projects", required=True, help="glob tới các project.sqlite3 (chương chưa gán nhãn)")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tokenizer", default="jhu-clsp/mmBERT-base")
    parser.add_argument("--budget", type=int, default=1024)
    parser.add_argument("--layout", choices=("line", "paragraph"), default="line", help="như build_vi.py (N8)")
    args = parser.parse_args()

    from transformers import AutoTokenizer  # noqa: PLC0415

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)

    def count_tokens(text: str) -> int:
        return len(tokenizer(text, add_special_tokens=False)["input_ids"])

    skip = gold_chapter_numbers()
    args.out.mkdir(parents=True, exist_ok=True)
    stats: Counter = Counter()
    seen_chapters: set[str] = set()
    with (args.out / "train.jsonl").open("w", encoding="utf-8") as writer:
        for database in sorted(glob.glob(args.projects)):
            connection = sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True)
            display = {str(c): str(d or c) for c, d in connection.execute("SELECT canonical_name, display_name FROM characters")}
            aliases = aliases_for(set(display), display)
            for chapter_id, title in connection.execute("SELECT id, title FROM chapters ORDER BY chapter_index").fetchall():
                number = re.search(r"\d+", str(title))
                if number and int(number.group()) in skip:
                    stats["chương gold bỏ qua"] += 1
                    continue
                if str(title) in seen_chapters:
                    continue  # cùng chương có trong nhiều project (đúc lại): lấy một lần
                seen_chapters.add(str(title))
                segments = [(int(seq), str(text), str(kind or "")) for seq, text, kind in connection.execute(
                    "SELECT seq, text, kind FROM segments WHERE chapter_id = ? ORDER BY seq", (chapter_id,))]
                paragraph_of = dict(connection.execute(
                    "SELECT seq, paragraph_index FROM segments WHERE chapter_id = ?", (chapter_id,)).fetchall())
                labels = explicit_labels(segments, aliases)
                stats["chương"] += 1
                for quote_seq, (entity, tag_seq) in labels.items():
                    tag_text = next(text for seq, text, _ in segments if seq == tag_seq)
                    if len(tag_text) > MAX_TAG_CHARS:
                        stats["thẻ dài, bỏ"] += 1
                        continue
                    masked = [(seq, text) for seq, text, _ in segments if seq != tag_seq]
                    quotes = {quote_seq: ("D", entity)}
                    for lo, hi, seqs in windows_for(masked, quotes, args.budget, count_tokens):
                        text, offsets = join_segments(masked[lo:hi + 1],
                                                      paragraph_of if args.layout == "paragraph" else None)
                        mentions = mention_spans(text, aliases)
                        covered = any(entity in mention["entities"] for mention in mentions)
                        stats["câu che"] += 1
                        stats["người nói còn trong ứng viên"] += covered
                        writer.write(json.dumps({"text": text, "mentions": mentions, "quotes": [{
                            "start": offsets[quote_seq][0], "end": offsets[quote_seq][1], "speaker": entity, "kind": "D",
                            "book": "cue_masked", "chapter": str(title), "seq": quote_seq}]}, ensure_ascii=False) + "\n")
    print(dict(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
