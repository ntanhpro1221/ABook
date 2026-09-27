"""Người nói: sai vì NHẬN SAI NGƯỜI hay chỉ vì VIẾT SAI TÊN? (cổng Tam quốc 27-09, docs/ANALYSIS_RESEARCH.md)

    python name_form.py <root lượt đo> <thư mục gold> <chương> [<chương> ...]
    python name_form.py D:/Novels/Audiobooks/_model_eval_v2/27-09-tamquoc tam_quoc_dien_nghia 050 051 052

Với từng model dưới <root>: độ đúng người nói trên câu THOẠI (đúng trục `score_models`), chấm chặt và chấm bỏ qua
dấu/gạch nối/hoa thường. Khoảng cách giữa hai con số là phần mất chỉ vì chính tả tên - trong dây chuyền thật, một tên
viết khác (`HOANG CAI` thay "Hoàng Cái") thành nhân vật mới, giọng khác. Kèm số câu UNKNOWN/NPC.
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from score_models import GOLD_ROOT, load_gold, read_project, speaker_credit


def fold(name: str) -> str:
    """Bỏ dấu (kể cả đ), gạch nối, hoa thường: "Hoàng Cái" == "HOANG CAI" == "hoàng-cái"."""
    text = unicodedata.normalize("NFD", name.replace("đ", "d").replace("Đ", "D"))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.upper().replace("-", " ").split())


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    root, gold_dir, chapters = Path(argv[0]), argv[1], tuple(argv[2:])
    gold = load_gold(GOLD_ROOT / gold_dir)
    wanted_chapters = {chapter for chapter, _ in gold}
    for model_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        rows: dict[tuple[str, int], dict] = {}
        for chapter in chapters:
            project = next((model_dir / chapter).rglob("project.sqlite3"), None)
            if project is None:
                continue
            found, _meta = read_project(project.parent, wanted_chapters)
            rows.update({(str(row["chapter"]), int(row["seq"])): row for row in found})
        total = strict = folded = unknown = 0
        for key, entry in gold.items():
            if not entry.spoken or key not in rows:
                continue
            total += 1
            given = str(rows[key]["speaker"] or "")
            if speaker_credit(entry, given) > 0:
                strict += 1
                folded += 1
            elif any(fold(option) == fold(given) for option, _ in entry.speakers):
                folded += 1
            if given.upper().startswith(("UNKNOWN", "NPC")):
                unknown += 1
        if total:
            print(f"{model_dir.name:24s} {total:4d} câu thoại | chặt {strict / total:6.1%} | bỏ qua dấu {folded / total:6.1%}"
                  f" | UNKNOWN/NPC {unknown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
