"""PDNC (tiếng Anh) -> cửa sổ cùng dạng build_vi.py, để HỌC TRƯỚC bộ chấm rồi mới tinh chỉnh bằng gold tiếng Việt.

    D:/Novels/LLM_Train/.venv/Scripts/python.exe scripts/model_eval/quote_scorer/build_pdnc.py \
        --pdnc D:/Novels/LLM_Train/pdnc --out D:/Novels/LLM_Train/data/pdnc_windows

Vì sao (ANALYSIS_RESEARCH.md): gold tiếng Việt có ~1.600 câu huấn luyện; PDNC (Vishnubhotla và cs., LREC 2022) có
~37 nghìn câu gán người nói trong 28 tiểu thuyết Anh ngữ. Bộ mã hoá mmBERT đa ngữ, còn kỹ năng cần học - thẻ lời nói
gần câu, xuống đoạn là đổi lượt, hai người thay phiên, tên gọi trong câu là người NGHE - không phụ thuộc ngôn ngữ.

Cùng quy ước với dữ liệu tiếng Việt để kỹ năng chuyển sang được:
- dàn trang theo paragraph (N8): mỗi paragraph một dòng, xuống dòng cứng kiểu Gutenberg nối lại bằng dấu cách;
- mỗi câu con (sub-quotation, bị thẻ "said he" cắt đôi) là một câu thoại riêng, như bộ tách đoạn của app;
- ứng viên = mọi chỗ khớp bí danh (Aliases của PDNC, phân biệt hoa thường - "Hope" khác "hope"); truyện kể ngôi
  thứ nhất thì "I/me/my" trong lời kể là chỗ nhắc người kể (N7), người kể suy ra từ thẻ ngôi thứ nhất ("said I",
  "I answered") trong referringExpression của chính PDNC;
- người nói không khớp nhân vật nào thì bỏ câu (PDNC không có lớp người kể/NPC - lựa chọn "không ai" học ở gold).
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from build_vi import join_segments, windows_for  # noqa: E402

csv.field_size_limit(10**9)
FIRST_PERSON_TAG = re.compile(r"\b(I|me)\b", re.IGNORECASE)
FIRST_PERSON = re.compile(r"\b(I|me|my|myself)\b")
PARAGRAPH = re.compile(r"\S(?:.*?\S)?(?=\n\s*\n|\s*\Z)", re.DOTALL)


def parse_names(field: str) -> set[str]:
    try:
        value = ast.literal_eval(field)
    except (ValueError, SyntaxError):
        return {field} if field else set()
    return {str(name) for name in value} if isinstance(value, (set, list, tuple)) else {str(value)}


def characters(folder: Path) -> tuple[dict[str, set[str]], dict[str, str]]:
    """(bí danh -> các thực thể, tên bất kỳ -> thực thể duy nhất). Thực thể = Main Name (thêm ID nếu trùng)."""
    rows = list(csv.DictReader((folder / "character_info.csv").open(encoding="utf-8")))
    main_count = Counter(row["Main Name"] for row in rows)
    aliases: dict[str, set[str]] = {}
    for row in rows:
        entity = row["Main Name"] if main_count[row["Main Name"]] == 1 else f"{row['Main Name']} #{row['Character ID']}"
        for name in parse_names(row["Aliases"]) | {row["Main Name"]}:
            if name.strip():
                aliases.setdefault(name.strip(), set()).add(entity)
    unique = {name: next(iter(entities)) for name, entities in aliases.items() if len(entities) == 1}
    return aliases, unique


def mention_spans(text: str, aliases: dict[str, set[str]], narration: list[tuple[int, int]], narrator: str | None
                  ) -> list[dict]:
    ordered = sorted(aliases, key=len, reverse=True)
    pattern = re.compile(r"(?<!\w)(" + "|".join(re.escape(name) for name in ordered) + r")(?!\w)")
    mentions = [{"start": m.start(), "end": m.end(), "entities": sorted(aliases[m.group(0)])}
                for m in pattern.finditer(text)]
    if narrator:
        for begin, finish in narration:
            for match in FIRST_PERSON.finditer(text, begin, finish):
                mentions.append({"start": match.start(), "end": match.end(), "entities": [narrator]})
        mentions.sort(key=lambda mention: mention["start"])
    return mentions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdnc", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tokenizer", default="jhu-clsp/mmBERT-base")
    parser.add_argument("--budget", type=int, default=1024)
    args = parser.parse_args()

    from transformers import AutoTokenizer  # noqa: PLC0415

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)

    def count_tokens(text: str) -> int:
        return len(tokenizer(text, add_special_tokens=False)["input_ids"])

    person = {row["Folder Name"]: row["Narrative Person"] for row in
              csv.DictReader((args.pdnc / "PDNC-Novel-Index.csv").open(encoding="utf-8")) if row["Folder Name"]}
    args.out.mkdir(parents=True, exist_ok=True)
    stats: Counter = Counter()
    with (args.out / "train.jsonl").open("w", encoding="utf-8") as writer:
        for folder in sorted(path for path in (args.pdnc / "data").iterdir() if path.is_dir()):
            raw = (folder / "novel_text.txt").read_text(encoding="utf-8")
            aliases, unique = characters(folder)
            paragraphs = [(m.start(), m.end()) for m in PARAGRAPH.finditer(raw)]
            starts = [start for start, _ in paragraphs]

            def paragraph_at(offset: int) -> int:
                low, high = 0, len(starts) - 1
                while low < high:
                    middle = (low + high + 1) // 2
                    if starts[middle] <= offset:
                        low = middle
                    else:
                        high = middle - 1
                return low

            quotes_by_paragraph: dict[int, list[tuple[int, int, str]]] = {}
            first_person_votes: Counter = Counter()
            for row in csv.DictReader((folder / "quotation_info.csv").open(encoding="utf-8")):
                stats["câu PDNC"] += 1
                speaker = unique.get(row["speaker"].strip())
                if speaker is None:
                    stats["người nói không khớp nhân vật, bỏ"] += 1
                    continue
                if FIRST_PERSON_TAG.search(str(row["referringExpression"] or "")):
                    first_person_votes[speaker] += 1
                for start, end in ast.literal_eval(row["quoteByteSpans"]):
                    # Gồm cả dấu ngoặc như đoạn thoại tiếng Việt (“…”): hai đầu mút của câu là dấu ngoặc ở cả hai bộ dữ liệu.
                    start -= start > 0 and raw[start - 1] in "\"“'‘"
                    end += end < len(raw) and raw[end] in "\"”'’"
                    index = paragraph_at(start)
                    quotes_by_paragraph.setdefault(index, []).append((start, end, speaker))
                    stats["câu con"] += 1
            narrator = None
            if str(person.get(folder.name, "")).startswith("1") and first_person_votes:
                (top, count), *rest = first_person_votes.most_common(2) + [(None, 0)]
                if count >= 5 and count >= 2 * rest[0][1]:
                    narrator = top
            print(f"  {folder.name}: {len(paragraphs)} paragraph, {sum(map(len, quotes_by_paragraph.values()))} câu con"
                  + (f", người kể 'I' = {narrator}" if narrator else ""), flush=True)
            segments = [(index, re.sub(r"\s*\n\s*", " ", raw[start:end])) for index, (start, end) in enumerate(paragraphs)]
            for lo, hi, taken in windows_for(segments, quotes_by_paragraph, args.budget, count_tokens):
                text, offsets = join_segments(segments[lo:hi + 1])
                rows, narration, cursor = [], [], None

                def local(offset: int) -> int:
                    index = paragraph_at(offset)
                    if index not in offsets:  # câu dài tràn sang paragraph ngoài cửa sổ: cắt ở cuối cửa sổ
                        return len(text)
                    head = raw[paragraphs[index][0]:offset]
                    return min(offsets[index][1], offsets[index][0] + len(re.sub(r"\s*\n\s*", " ", head)))

                quote_spans = []
                for index in range(lo, hi + 1):
                    for start, end, speaker in quotes_by_paragraph.get(index, []):
                        quote_spans.append((local(start), local(end), speaker, index in taken))
                quote_spans.sort()
                cursor = 0
                for start, end, _, _ in quote_spans:
                    if start > cursor:
                        narration.append((cursor, start))
                    cursor = max(cursor, end)
                narration.append((cursor, len(text)))
                mentions = mention_spans(text, aliases, narration, narrator)
                for start, end, speaker, mine in quote_spans:
                    if not mine:
                        continue
                    covered = any(speaker in mention["entities"] for mention in mentions)
                    stats["câu con vào cửa sổ"] += 1
                    stats["người nói có trong ứng viên"] += covered
                    rows.append({"start": start, "end": end, "speaker": speaker, "kind": "D", "book": f"pdnc/{folder.name}",
                                 "chapter": folder.name, "seq": start})
                if rows:
                    writer.write(json.dumps({"text": text, "quotes": rows, "mentions": mentions}, ensure_ascii=False) + "\n")
                    stats["cửa sổ"] += 1
    print(dict(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
