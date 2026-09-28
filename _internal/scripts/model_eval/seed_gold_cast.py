r"""Gieo "nhân vật đã biết" vào project đo một chương giữa truyện, từ đáp án của các chương TRƯỚC nó.

    python scripts/model_eval/seed_gold_cast.py <project> --gold yamiyo_no_hotaru --chapter 141

Bộ đo `--book` tạo project trống cho mỗi chương (make_eval_project không gieo), nên prompt mở đầu bằng "(Chưa có nhân
vật đã biết)". Lúc làm sách thật, tới chương 141 sổ đã có mọi người nói từ 140 chương trước (tới 80 người, `_known_summary`,
kèm số lần gặp và giới) - thước LN đo model trong một điều kiện sản xuất không bao giờ gặp ở giữa truyện.

Đo 29-09 (scratchpad cast_absent.py): 133/722 câu có tên trong bộ LN có người nói mà tên KHÔNG có trong chính chương ấy,
nhưng 130 câu là của người kể "tôi" (TOMOBE, KAKERU, KRAI) mà prompt đã nêu qua `--first-person`; chỉ 3 câu thật sự vắng
tên. Nên phép thử này KHÔNG nhắm câu "không thể đoán": nó hỏi model dùng một sổ nhân vật thật (tên, số lần, giới) tốt
hay tệ - đo 21-09 trên cuốn 2 cho thấy số đếm kéo model về người nổi tiếng (cơ chế thật, lợi ròng ~0 với qwen3:8b).

Gieo từ đáp án các chương có số NHỎ hơn chương đo (sách thật không biết tương lai): mỗi người nói có tên, số câu, giới
theo đa số - cùng những gì `port_casting.py` mang sang lô sau, và cùng bộ lọc `_known_summary` dùng (bỏ người kể, vai
phụ, người không rõ giới). Tên chuẩn là khoá đáp án (chữ HOA) như `canonical_name` của sổ sản xuất.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (ROOT, HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from score_models import GOLD_ROOT, load_gold  # noqa: E402

GENDER = {"m": "male", "f": "female"}
KNOWN_MAX = 80  # _known_summary: most_common(80)


def _number(chapter: str) -> int | None:
    return int(chapter) if chapter.isdigit() else None


def gold_cast(gold_book: str, chapter: str) -> list[dict]:
    """Người nói có tên của các chương đáp án TRƯỚC `chapter`: [{name, lines, gender}], nhiều câu nhất trước."""
    limit = _number(chapter)
    lines: Counter[str] = Counter()
    genders: dict[str, Counter[str]] = defaultdict(Counter)
    for (other, _seq), row in load_gold(GOLD_ROOT / gold_book).items():
        number = _number(other)
        if limit is None or number is None or number >= limit or not row.spoken or not row.speakers:
            continue
        speaker = row.speakers[0][0]
        if speaker in ("NARRATOR", "NPC*") or speaker.startswith(("NPC", "ANONYMOUS")):
            continue
        lines[speaker] += 1
        if row.gender in GENDER:
            genders[speaker][GENDER[row.gender]] += 1
    cast = []
    for name, count in lines.most_common():
        if not genders[name]:
            continue  # _known_summary chỉ đưa người đã rõ giới
        cast.append({"name": name, "lines": count, "gender": genders[name].most_common(1)[0][0]})
    return cast[:KNOWN_MAX]


def seed(project_root: Path, gold_book: str, chapter: str) -> list[dict]:
    from ebook_reader.database import ProjectDB
    from ebook_reader.models import ProjectPaths

    cast = gold_cast(gold_book, chapter)
    database = ProjectDB(ProjectPaths.build(project_root).db)
    for person in cast:
        database.upsert_character(
            canonical_name=person["name"],
            display_name=person["name"].title(),
            gender=person["gender"],
            age="adult",
            personality="",
            mentions=person["lines"],
            importance="main",
            confidence=1.0,
        )
    return cast


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project", type=Path)
    parser.add_argument("--gold", required=True, help="thư mục đáp án trong gold/")
    parser.add_argument("--chapter", required=True, help="chương đang đo - chỉ gieo từ các chương trước nó")
    args = parser.parse_args(argv)
    cast = seed(args.project, args.gold, args.chapter)
    print(f"gieo {len(cast)} người: " + ", ".join(f"{person['name']} {person['lines']}" for person in cast[:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
