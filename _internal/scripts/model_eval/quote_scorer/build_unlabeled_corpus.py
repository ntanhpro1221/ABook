"""Cửa sổ KHÔNG NHÃN cho mọi truyện có gold, lấy thẳng từ Corpus/ bằng bộ tách đoạn của app - cho tự học theo cuốn (N4').

    D:/Novels/LLM_Train/.venv/Scripts/python.exe scripts/model_eval/quote_scorer/build_unlabeled_corpus.py \
        --out D:/Novels/LLM_Train/data/unlabeled [--chapters 40]

Chỉ TMA có project sản xuất (build_unlabeled.py đọc loại đoạn LLM đã chốt); 9 truyện kia chỉ có .txt trong Corpus/. Ở đây
tách đoạn bằng chính `text_processing.segment_chapter_text` của app (luật, không LLM - loại đoạn là `kind_hint` theo dấu
ngoặc), rồi dựng cửa sổ y như build_vi.py: dàn trang paragraph, dòng danh sách nhân vật chương, khớp tên viết hoa, người kể
"tôi" tự suy (N7b). Bí danh = tên nhân vật trong gold của truyện - thứ khi chạy thật sổ nhân vật của app cung cấp.
Chương có gold bị bỏ; lấy `--chapters` chương GẦN các chương gold nhất. Mỗi truyện một tệp `<truyện>_para_cast.jsonl`.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[2]))  # _internal: gói abook

from build_vi import (  # noqa: E402
    GOLD_ROOT, aliases_for, chapter_cast, entity_of, gold_speakers, join_segments, mention_spans, point_of_view_auto,
    windows_for, with_cast,
)
from replay_all import BOOKS, CORPUS  # noqa: E402

from abook.io_utils import decode_text_bytes  # noqa: E402
from abook.text_processing import segment_chapter_text  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--chapters", type=int, default=40)
    parser.add_argument("--tokenizer", default="jhu-clsp/mmBERT-base")
    parser.add_argument("--budget", type=int, default=1024)
    args = parser.parse_args()

    from transformers import AutoTokenizer  # noqa: PLC0415

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)

    def count_tokens(text: str) -> int:
        return len(tokenizer(text, add_special_tokens=False)["input_ids"])

    args.out.mkdir(parents=True, exist_ok=True)
    for book, folder in BOOKS.items():
        if folder is None:
            continue  # TMA: build_unlabeled.py từ project sản xuất
        gold_files = sorted((GOLD_ROOT / book).glob("*.txt"))
        gold_numbers = {int(path.stem) for path in gold_files if path.stem.isdigit()}
        entities = {entity for path in gold_files for _, (_, options) in gold_speakers(path).items()
                    for option in options if (entity := entity_of(option.rstrip("~")))}
        aliases = aliases_for(entities, {})
        sources = [path for path in sorted((CORPUS / folder).glob("*.txt"))
                   if path.stem.isdigit() and int(path.stem) not in gold_numbers]
        center = sum(gold_numbers) / max(1, len(gold_numbers))
        chosen = sorted(sorted(sources, key=lambda path: (abs(int(path.stem) - center), int(path.stem)))[:args.chapters],
                        key=lambda path: int(path.stem))
        segments_by_chapter = {}
        for index, path in enumerate(chosen, 1):
            rows = segment_chapter_text(index, decode_text_bytes(path.read_bytes()))
            segments_by_chapter[path.stem] = [(int(row["seq"]), str(row["text"]), str(row["kind_hint"]),
                                               int(row["paragraph_index"])) for row in rows]
        povs = point_of_view_auto({chapter: [(seq, text, kind) for seq, text, kind, _ in rows]
                                   for chapter, rows in segments_by_chapter.items()}, aliases)
        stats: Counter = Counter()
        with (args.out / f"{book}_para_cast.jsonl").open("w", encoding="utf-8") as writer:
            for chapter, rows in segments_by_chapter.items():
                segments = [(seq, text) for seq, text, _, _ in rows]
                kinds = {seq: kind for seq, _, kind, _ in rows}
                paragraph_of = {seq: paragraph for seq, _, _, paragraph in rows}
                quotes = {seq: ("D", "?") for seq, kind in kinds.items() if kind == "dialogue"}
                pov = povs.get(chapter)
                cast = chapter_cast(segments, aliases, pov, True)
                for lo, hi, seqs in windows_for(segments, quotes, args.budget, count_tokens):
                    text, offsets = join_segments(segments[lo:hi + 1], paragraph_of)
                    mentions = mention_spans(text, aliases, True)
                    if pov:
                        from build_vi import FIRST_PERSON  # noqa: PLC0415
                        for seq, (begin, finish) in offsets.items():
                            if kinds.get(seq) == "dialogue":
                                continue
                            for match in FIRST_PERSON.finditer(text, begin, finish):
                                mentions.append({"start": match.start(), "end": match.end(), "entities": [pov]})
                        mentions.sort(key=lambda mention: mention["start"])
                    text, offsets, mentions = with_cast(text, offsets, mentions, cast, {})
                    items = [{"start": offsets[seq][0], "end": offsets[seq][1], "speaker": None, "unlabeled": True,
                              "kind": "D", "book": book, "chapter": chapter, "seq": seq} for seq in seqs]
                    stats["câu thoại"] += len(items)
                    stats["cửa sổ"] += 1
                    writer.write(json.dumps({"text": text, "quotes": items, "mentions": mentions}, ensure_ascii=False) + "\n")
        print(f"  {book}: {len(chosen)} chương, {dict(stats)}, người kể {sorted(set(povs.values())) or '-'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
