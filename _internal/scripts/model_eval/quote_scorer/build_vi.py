"""Dựng dữ liệu cho BỘ CHẤM ỨNG VIÊN người nói (ANALYSIS_RESEARCH.md, E3) từ đáp án chuẩn tiếng Việt.

    D:/Novels/LLM_Train/.venv/Scripts/python.exe scripts/model_eval/quote_scorer/build_vi.py \
        --replay D:/Novels/Audiobooks/_model_eval_gold/replay_21_09_base --out D:/Novels/LLM_Train/data/quote_vi

Theo "Fast and Accurate Quotation Attribution in Literary Texts" (arXiv 2608.02359): thay vì để LLM VIẾT tên người
nói, một bộ mã hoá đọc một cửa sổ văn bản MỘT lần rồi CHẤM ĐIỂM từng chỗ nhắc nhân vật (ứng viên) cho từng câu thoại
trong cửa sổ. Mỗi dòng JSONL ra là một cửa sổ:

    {"text": ..., "quotes": [{"start", "end", "speaker" (thực thể, hoặc null = người kể / NPC không tên / không ai
     trong danh sách), "kind" "D"|"T", "book", "chapter", "seq"}], "mentions": [{"start", "end", "entities": [...]}]}

Văn bản cửa sổ = các đoạn (segments) của project phát lại gold nối bằng xuống dòng; ứng viên = mọi chỗ khớp bí danh
của nhân vật (tên chuẩn bỏ gạch dưới, từng phần tên >= 3 chữ, display_name) - chưa có đồng tham chiếu ("hắn", "cô
gái"), đúng biến thể "Aliases" của bài báo. Train/dev/test tách theo CHƯƠNG, cùng SPLIT với build_training_set.py.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from build_training_set import SPLIT  # noqa: E402

GOLD_ROOT = HERE.parent / "gold"
NULL_SPEAKERS = ("NARRATOR", "NPC", "?")


def gold_quotes(path: Path) -> dict[int, tuple[str, str]]:
    """seq -> (loại, người nói đầu tiên) cho các đoạn thoại/nội tâm của một chương gold."""
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 3 and parts[1][:1] in "DT":
            rows[int(parts[0])] = (parts[1][:1], parts[2].split(",")[0])
    return rows


def entity_of(label: str) -> str | None:
    return None if label.startswith(NULL_SPEAKERS) else label


def aliases_for(entities: set[str], display: dict[str, str]) -> dict[str, set[str]]:
    """bí danh (chữ thường) -> các thực thể có thể là; tên ngắn trùng nhau thì trỏ tới nhiều thực thể."""
    table: dict[str, set[str]] = {}
    for entity in entities:
        names = {entity.replace("_", " ")}
        if display.get(entity):
            names.add(display[entity].replace("_", " "))
        for name in list(names):
            names.update(part for part in name.split() if len(part) >= 3)
        for name in names:
            table.setdefault(name.lower(), set()).add(entity)
    return table


def mention_spans(text: str, aliases: dict[str, set[str]]) -> list[dict]:
    if not aliases:
        return []
    ordered = sorted(aliases, key=len, reverse=True)  # "alva bullard" trước "alva"
    pattern = re.compile(r"(?<!\w)(" + "|".join(re.escape(name) for name in ordered) + r")(?!\w)", re.IGNORECASE)
    return [{"start": m.start(), "end": m.end(), "entities": sorted(aliases[m.group(0).lower()])}
            for m in pattern.finditer(text)]


def split_of(book: str, chapter: str) -> str:
    for name, books in SPLIT.items():
        if chapter in books.get(book, set()):
            return name
    return "train"


def windows_for(segments: list[tuple[int, str]], quotes: dict[int, tuple[str, str]], budget: int,
                count_tokens) -> list[tuple[int, int, list[int]]]:
    """Cửa sổ (đoạn đầu, đoạn cuối, các câu thoại gán cho cửa sổ): mỗi câu thoại vào đúng MỘT cửa sổ, cửa sổ dựng
    quanh nó với ngữ cảnh hai phía gần cân nhau, gom các câu liền kề vào chung cửa sổ khi còn chỗ."""
    lengths = [count_tokens(text) + 1 for _, text in segments]
    index_of = {seq: i for i, (seq, _) in enumerate(segments)}
    pending = sorted(index_of[seq] for seq in quotes if seq in index_of)
    out = []
    while pending:
        center = pending[0]
        lo = hi = center
        used = lengths[center]
        while True:
            grew = False
            for side in ("hi", "lo") if (center - lo) > (hi - center) else ("lo", "hi"):
                if side == "lo" and lo > 0 and used + lengths[lo - 1] <= budget:
                    lo -= 1
                    used += lengths[lo]
                    grew = True
                if side == "hi" and hi + 1 < len(segments) and used + lengths[hi + 1] <= budget:
                    hi += 1
                    used += lengths[hi]
                    grew = True
            if not grew:
                break
        # Câu thoại trong nửa đầu-giữa cửa sổ (còn >= 1/4 ngữ cảnh phía sau) được gán luôn vào cửa sổ này.
        limit = hi - max(1, (hi - lo) // 4)
        taken = [index for index in pending if lo <= index <= max(center, limit)]
        out.append((lo, hi, [segments[index][0] for index in taken]))
        pending = [index for index in pending if index not in taken]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--replay", type=Path, required=True, help="thư mục phát lại gold (mỗi truyện một project)")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tokenizer", default="jhu-clsp/mmBERT-base")
    parser.add_argument("--budget", type=int, default=1024, help="token mỗi cửa sổ")
    args = parser.parse_args()

    from transformers import AutoTokenizer  # noqa: PLC0415

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)

    def count_tokens(text: str) -> int:
        return len(tokenizer(text, add_special_tokens=False)["input_ids"])

    args.out.mkdir(parents=True, exist_ok=True)
    writers = {name: (args.out / f"{name}.jsonl").open("w", encoding="utf-8") for name in ("train", "dev", "test")}
    stats: Counter = Counter()
    for database in sorted(args.replay.rglob("project.sqlite3")):
        book = database.relative_to(args.replay).parts[0]
        connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
        display = {str(c): str(d or c) for c, d in connection.execute("SELECT canonical_name, display_name FROM characters")}
        chapters = connection.execute("SELECT id, title FROM chapters ORDER BY chapter_index").fetchall()
        golds = {title: gold_quotes(GOLD_ROOT / book / f"{title}.txt") for _, title in chapters
                 if (GOLD_ROOT / book / f"{title}.txt").is_file()}
        entities = {entity for quotes in golds.values() for _, label in quotes.values()
                    if (entity := entity_of(label))} | set(display)
        aliases = aliases_for(entities, display)
        for chapter_id, title in chapters:
            quotes = golds.get(title)
            if not quotes:
                continue
            split = split_of(book, title)
            segments = [(int(seq), str(text)) for seq, text in connection.execute(
                "SELECT seq, text FROM segments WHERE chapter_id = ? ORDER BY seq", (chapter_id,))]
            for lo, hi, seqs in windows_for(segments, quotes, args.budget, count_tokens):
                offsets, parts, cursor = {}, [], 0
                for seq, text in segments[lo:hi + 1]:
                    offsets[seq] = (cursor, cursor + len(text))
                    parts.append(text)
                    cursor += len(text) + 1
                text = "\n".join(parts)
                mentions = mention_spans(text, aliases)
                rows = []
                for seq in seqs:
                    kind, label = quotes[seq]
                    speaker = entity_of(label)
                    covered = speaker is not None and any(speaker in m["entities"] for m in mentions)
                    stats[(split, "quotes")] += 1
                    stats[(split, "null")] += speaker is None
                    stats[(split, "covered")] += covered
                    stats[(split, "named")] += speaker is not None
                    rows.append({"start": offsets[seq][0], "end": offsets[seq][1], "speaker": speaker, "kind": kind,
                                 "book": book, "chapter": title, "seq": seq})
                writers[split].write(json.dumps({"text": text, "quotes": rows, "mentions": mentions},
                                                ensure_ascii=False) + "\n")
                stats[(split, "windows")] += 1
    for writer in writers.values():
        writer.close()
    for split in ("train", "dev", "test"):
        named = stats[(split, "named")] or 1
        print(f"{split:5}: {stats[(split, 'windows')]:4} cửa sổ, {stats[(split, 'quotes')]:5} câu (không tên/người kể "
              f"{stats[(split, 'null')]}), người nói có trong ứng viên {stats[(split, 'covered')]}/{stats[(split, 'named')]} "
              f"= {stats[(split, 'covered')] / named:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
