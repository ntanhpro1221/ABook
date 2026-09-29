"""Bộ đo LN: bao nhiêu câu có người nói mà tên KHÔNG có trong chính chương ấy (model chỉ đoán được nếu biết dàn nhân vật từ
chương trước) - và tên ấy có ở các chương TRƯỚC của truyện không (lúc làm sách thật, sổ "nhân vật đã biết" đã có nó).

Bộ đo --book tạo project trống cho mỗi chương (không gieo), nên phần này là chỗ bộ đo khác sản xuất."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ABOOK = Path("D:/Novels/ABook/_internal")
sys.path.insert(0, str(ABOOK))
sys.path.insert(0, str(ABOOK / "scripts" / "model_eval"))
from ebook_reader.character_registry import fold_for_source_search  # noqa: E402
from replay_all import BOOKS  # noqa: E402
from score_models import GOLD_ROOT, load_gold  # noqa: E402

CORPUS = Path("D:/Novels/ABook/Corpus")
LN = [("two_childhood_friends", "042"), ("nise_seiken", "132"), ("huong_dan_sinh_ton", "062"),
      ("yamiyo_no_hotaru", "141"), ("nageki_no_bourei", "65"), ("love_unseen", "07"),
      ("yamiyo_no_hotaru", "225"), ("nageki_no_bourei", "62"), ("two_childhood_friends", "060"),
      ("nise_seiken", "086"), ("huong_dan_sinh_ton", "130"), ("love_unseen", "10")]
SKIP = {"NARRATOR", "NPC*"}


def chapter_files(book: str) -> dict[int, Path]:
    folder = CORPUS / str(BOOKS[book])
    return {int(path.stem): path for path in folder.glob("*.txt") if path.stem.isdigit()}


def forms(name: str) -> set[str]:
    text = fold_for_source_search(name).strip()
    words = text.split()
    return {text} | ({word for word in (words[0], words[-1]) if len(word) >= 3} if len(words) > 1 else set())


def present(name: str, folded: str) -> bool:
    return any(f" {form} " in f" {folded} " or f" {form}," in f" {folded}" for form in forms(name))


def main() -> None:
    total = Counter()
    for book, chapter in LN:
        gold = load_gold(GOLD_ROOT / book)
        rows = [row for (ch, _seq), row in sorted(gold.items(), key=lambda item: item[0][1]) if ch == chapter and row.spoken]
        files = chapter_files(book)
        number = int(chapter)
        here = fold_for_source_search(files[number].read_text(encoding="utf-8", errors="replace"))
        before = fold_for_source_search("\n".join(files[n].read_text(encoding="utf-8", errors="replace")
                                                  for n in sorted(files) if n < number))
        counts = Counter()
        absent_names = Counter()
        for row in rows:
            speaker = row.speakers[0][0] if row.speakers else ""
            if not speaker or speaker in SKIP:
                counts["bỏ (người kể/NPC)"] += 1
                continue
            counts["câu có tên"] += 1
            if present(speaker, here):
                continue
            counts["tên VẮNG khỏi chương"] += 1
            absent_names[speaker] += 1
            if present(speaker, before):
                counts["... nhưng có ở chương trước"] += 1
        total.update(counts)
        names = ", ".join(f"{name} {count}" for name, count in absent_names.most_common(4))
        print(f"{book[:18]:18} {chapter:>4}: {dict(counts)}  [{names}]")
    print("TỔNG:", dict(total))


if __name__ == "__main__":
    main()
