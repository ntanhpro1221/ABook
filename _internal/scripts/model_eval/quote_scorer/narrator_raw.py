"""N7b TỪ VĂN BẢN THÔ: đoán người kể "tôi" của một truyện LÚC NHẬP SÁCH - không LLM, không sổ nhân vật, không gold.

    D:/Novels/LLM_Train/.venv/Scripts/python.exe scripts/model_eval/quote_scorer/narrator_raw.py \
        "D:/Novels/Ebook Reader/Corpus/Young Master's PoV Woke Up As A Villain In A Game One Day" [--chapters 40]

Dòng prompt "người kể xưng 'tôi' là SAMAEL" đưa LoRA từ 34,0% lên 89,4% người nói ở truyện ngôi thứ nhất (27-09) - nhưng
dòng ấy phải có NGAY lúc phân tích, trước khi app biết tên ai. Nên ứng viên lấy từ chính văn bản: cụm VIẾT HOA không đứng
đầu câu (trong tiếng Việt gần như luôn là tên riêng), 1-3 chữ. Người kể = tên hay được gọi trong ngoặc thoại mà gần như
không xuất hiện trong lời kể (người kể không tự gọi tên mình), chỉ khi lời kể có nhiều "tôi" (bỏ "mình" phản thân).
Tách đoạn bằng chính `text_processing.segment_chapter_text` của app.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2]))

from build_vi import NARRATOR_I  # noqa: E402

from ebook_reader.io_utils import decode_text_bytes  # noqa: E402
from ebook_reader.text_processing import segment_chapter_text  # noqa: E402

UPPER = "A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ"
WORD = rf"[{UPPER}][\w'-]*"
# Cụm viết hoa 1-3 chữ KHÔNG đứng đầu câu/đoạn (sau chữ thường hoặc dấu phẩy) - tên riêng, không phải chữ đầu câu.
NAME = re.compile(rf"(?<=[\w,;]\s)({WORD}(?:\s{WORD}){{0,2}})")


def names_in(text: str) -> list[str]:
    return [match.group(1) for match in NAME.finditer(text)]


def guess(chapters: list[list[tuple[str, str]]], min_rate: float = 0.30, min_dialogue: int = 5,
          min_ratio: float = 3.0) -> tuple[str | None, float, list[tuple[str, int, int]]]:
    """(người kể, tỉ lệ lời kể có 'tôi', top ứng viên (tên, lần trong thoại, lần trong lời kể))."""
    narration = [text for rows in chapters for text, kind in rows if kind != "dialogue"]
    rate = sum(bool(NARRATOR_I.search(text)) for text in narration) / max(1, len(narration))
    in_dialogue, in_narration = Counter(), Counter()
    for rows in chapters:
        for text, kind in rows:
            (in_dialogue if kind == "dialogue" else in_narration).update(names_in(text))
    # Tên dài gộp tên ngắn nằm trong nó ("Samael Grandtiford" đếm cho "Samael" nếu tên ngắn là ứng viên chính)
    scored = [(name, in_dialogue[name], in_narration[name]) for name in in_dialogue if in_dialogue[name] >= min_dialogue]
    scored.sort(key=lambda item: (-(item[1] + 1) / (item[2] + 1), -item[1]))
    top = scored[:5]
    if rate < min_rate or not top or (top[0][1] + 1) / (top[0][2] + 1) < min_ratio:
        return None, rate, top
    return top[0][0], rate, top


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folders", type=Path, nargs="+")
    parser.add_argument("--chapters", type=int, default=40, help="số chương đầu truyện dùng để đoán")
    args = parser.parse_args()
    for folder in args.folders:
        files = sorted((path for path in folder.glob("*.txt") if path.stem.isdigit()), key=lambda path: int(path.stem))
        chapters = []
        for index, path in enumerate(files[:args.chapters], 1):
            rows = segment_chapter_text(index, decode_text_bytes(path.read_bytes()))
            chapters.append([(str(row["text"]), str(row["kind_hint"])) for row in rows])
        narrator, rate, top = guess(chapters)
        print(f"{folder.name[:40]:40s} 'tôi' {rate:4.0%} -> {narrator or '(không đoán)'} | "
              + ", ".join(f"{name} {d}/{n}" for name, d, n in top[:4]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
