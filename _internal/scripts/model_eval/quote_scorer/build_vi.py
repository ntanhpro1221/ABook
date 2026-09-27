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
# Ngôi thứ nhất (N7, 27-09): truyện mạng/light novel hay kể bằng "tôi" - nhân vật kể KHÔNG BAO GIỜ được gọi tên
# trong lời kể, nên 118/138 câu có người nói nằm ngoài ứng viên là của chính người kể. PDNC (tiểu thuyết cổ điển,
# hầu hết ngôi thứ ba) không có chuyện này. "tôi/mình/tớ" TRONG LỜI KỂ (không phải trong thoại) = chỗ nhắc người kể.
FIRST_PERSON = re.compile(r"(?<!\w)(tôi|mình|tớ)(?!\w)", re.IGNORECASE)
FIRST_PERSON_CUE = re.compile(r"(?<!\w)(tôi|mình|tớ)\s+(?:\w+\s+){0,2}?(nói|hỏi|đáp|gọi|lên tiếng|thì thầm|hét|la|thốt|bảo|trả lời|"
                              r"lẩm bẩm|nhắc|cười|cất tiếng|mở lời|kêu|gắt|quát|thở dài|lầm bầm|càu nhàu|"
                              r"đáp lời|hỏi lại|nói tiếp|giải thích|xác nhận|phản bác|chen vào)(?!\w)", re.IGNORECASE)


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


def point_of_view(segments_by_chapter: dict, golds: dict) -> dict[str, str]:
    """Nhân vật "tôi" của một truyện: người nói gold gặp nhiều nhất ở câu thoại NGAY SAU lời kể có "tôi nói/hỏi/...".

    Khi chạy thật không có gold: đây sẽ là câu hỏi của Studio ("Truyện kể ngôi thứ nhất? 'Tôi' là ai?") hoặc lấy từ
    chính bộ chấm trên các câu tường minh - ở đây dùng gold để đo TRẦN của hướng này trước."""
    votes: dict[str, Counter] = {}
    for chapter, segments in segments_by_chapter.items():
        quotes = golds.get(chapter, {})
        votes[chapter] = Counter()
        for index, (seq, text, kind) in enumerate(segments):
            # Chỉ khi "tôi nói/hỏi..." là mệnh đề CUỐI của lời kể và câu thoại đứng NGAY SAU: "tôi hỏi. / <câu trả
            # lời của người kia>" từng làm Lucy, Sitri bị nhận là người kể (27-09).
            if kind == "dialogue":
                continue
            cues = list(FIRST_PERSON_CUE.finditer(text))
            if not cues:
                continue
            # Thẻ lời nói gắn với câu thoại nào tuỳ vị trí và dấu câu (quy ước truyện dịch):
            #   "tôi nói:" ở CUỐI lời kể, câu thoại ngay SAU      -> thẻ của câu sau;
            #   "tôi nói." ở ĐẦU lời kể, ngay sau một câu thoại  -> thẻ của câu TRƯỚC ("…," tôi nói.).
            # Lấy nhầm câu sau trong trường hợp thứ hai từng nhận người đối thoại làm người kể (Fuyutsuki, 27-09).
            target = None
            if text.rstrip().endswith(":") and len(text) - cues[-1].end() <= 12 and index + 1 < len(segments):
                target = segments[index + 1][0]
            elif cues[0].start() <= 15 and index > 0 and segments[index - 1][2] == "dialogue":
                target = segments[index - 1][0]
            label = quotes.get(target, (None, None))[1] if target is not None else None
            if label and entity_of(label):
                votes[chapter][entity_of(label)] += 1
    # Có truyện đổi người kể theo chương (Yamiyo no Hotaru: Tomobe / Kaede / Yuusei): "tôi" xác định theo CHƯƠNG, lấy
    # cả truyện làm dự phòng cho chương không có câu "tôi nói" nào.
    total = sum(votes.values(), Counter())
    ranked = total.most_common(2)
    # Thắng rõ: >= 3 phiếu và gấp đôi người thứ hai - không thì thà không đoán người kể.
    book = ranked[0][0] if ranked and ranked[0][1] >= 3 and (len(ranked) < 2 or ranked[0][1] >= 2 * ranked[1][1]) else None
    result = {}
    for chapter, counts in votes.items():
        best = counts.most_common(1)[0] if counts else (None, 0)
        result[chapter] = best[0] if best[1] >= 2 else book
    return {chapter: entity for chapter, entity in result.items() if entity}


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
    parser.add_argument("--no-pov", action="store_true", help="tắt ứng viên ngôi thứ nhất (để so với mốc)")
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
        segments_by_chapter = {
            title: [(int(seq), str(text), str(kind or "")) for seq, text, kind in connection.execute(
                "SELECT seq, text, kind FROM segments WHERE chapter_id = ? ORDER BY seq", (chapter_id,))]
            for chapter_id, title in chapters if title in golds}
        povs = {} if args.no_pov else point_of_view(segments_by_chapter, golds)
        if povs:
            print(f"  {book}: 'tôi' theo chương = {povs}")
        for chapter_id, title in chapters:
            quotes = golds.get(title)
            if not quotes:
                continue
            split = split_of(book, title)
            kinds = {seq: kind for seq, _, kind in segments_by_chapter[title]}
            pov = povs.get(title)
            segments = [(seq, text) for seq, text, _ in segments_by_chapter[title]]
            for lo, hi, seqs in windows_for(segments, quotes, args.budget, count_tokens):
                offsets, parts, cursor = {}, [], 0
                for seq, text in segments[lo:hi + 1]:
                    offsets[seq] = (cursor, cursor + len(text))
                    parts.append(text)
                    cursor += len(text) + 1
                text = "\n".join(parts)
                mentions = mention_spans(text, aliases)
                if pov:
                    for seq, (begin, finish) in offsets.items():
                        if kinds.get(seq) == "dialogue":
                            continue  # "tôi" trong ngoặc thoại là chính người đang nói, không phải người kể
                        for match in FIRST_PERSON.finditer(text, begin, finish):
                            mentions.append({"start": match.start(), "end": match.end(), "entities": [pov]})
                    mentions.sort(key=lambda mention: mention["start"])
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
