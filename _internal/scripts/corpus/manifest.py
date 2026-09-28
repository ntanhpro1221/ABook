r"""Bảng kê kho truyện `D:/Novels/ABook/Corpus/` -> `Corpus/manifest.json`.

    python scripts/corpus/manifest.py            # quét lại, ghi bảng kê
    python scripts/corpus/manifest.py --check    # so kho với bảng kê đã ghi (file mất / đổi nội dung)

Mỗi truyện: số chương, số từ (tách theo khoảng trắng), sha256 từng file. Bảng kê để biết chắc cái đang có
là cái đã gom, và để các tập train/dev/test chỉ đích danh chương theo mã băm.

Kho là một repo RIÊNG TƯ, `ntanhpro1221/ABook-Corpus`, clone vào đúng `Corpus/` (repo chính bỏ qua thư mục
này). Chủ sách chốt 19-09: dữ liệu phải được đẩy lên, laptop hỏng thì không mất công gom và làm đáp án. 27-09:
repo chính công khai mà truyện còn bản quyền - một thông báo DMCA khoá cả repo, kéo theo trang tải APK và bộ cập
nhật của app - nên kho sang repo riêng tư, còn lịch sử repo chính được viết lại cho sạch.

Nguồn từng truyện ghi ở `SOURCES` (lúc gom) hoặc trong `metadata.json` cạnh truyện (tải từ Hako).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT.parent / "Corpus"
MANIFEST = CORPUS / "manifest.json"

# Nguồn lúc gom 19-09 (docs/LLM_EVAL.md, mục "Kho dữ liệu").
SOURCES = {
    "Young Master's PoV Woke Up As A Villain In A Game One Day": "cuốn 1 của dự án (Ebook Reader/Text), kể ngôi thứ nhất (SAMAEL)",
    "Throne of Magical Arcana": "cuốn 2 của dự án (Ebook Reader/Text_Tmp)",
    "Nise Seiken Monogatari": "D:/Novels/Tools/Text Nise Seiken Monogatari",
    "Two Childhood Friends Who Have the Strongest Power Kick Each Other in the Dungeon With All Their Might": "D:/Novels/Tools",
    "Đã bảo là cùng nhau tự sát, cớ sao lại thành sống chung": "D:/Novels/Tools",
    "Yamiyo no Hotaru": "Thùng rác C: (C:/Users/NGDtuanh/Novels/Tools/Text, xoá 04-04-2026)",
    "Hướng dẫn sinh tồn trong học viện": "Thùng rác D: (D:/Novels/Tools/Text, xoá 22-08-2026)",
    "Nageki no Bourei wa Intai Shitai": "Thùng rác D: (Text_Tmp Nageki no Bourei wa Intai Shitai, xoá 13-09-2026)",
    "Năng lực bá đạo của tôi trong game tử thần là những thiếu nữ xinh đẹp": "Thùng rác D: (xoá 25-07-2026)",
    "Love Unseen Beneath the Clear Night Sky": "Thùng rác D: (D:/Novels/Tools/Text, xoá 01-08-2026)",
    "Tam quốc diễn nghĩa (Phan Kế Bính)": "vi.wikisource, hồi 45-54 (bản dịch 1909, hết bản quyền), 27-09",
    "Tắt đèn (Ngô Tất Tố)": "vi.wikisource, đủ 27 chương (1937-1939, hết bản quyền), 28-09",
}


def scan(corpus: Path = CORPUS) -> dict:
    books = {}
    # `_survey/` (khảo sát Hako) và `.git/` không phải truyện.
    for folder in sorted(path for path in corpus.iterdir() if path.is_dir() and path.name[:1] not in "._"):
        chapters = sorted(folder.glob("*.txt"))
        words = 0
        files = {}
        for chapter in chapters:
            data = chapter.read_bytes()
            files[chapter.name] = hashlib.sha256(data).hexdigest()
            words += len(data.decode("utf-8", errors="replace").split())
        metadata = folder / "metadata.json"
        source = SOURCES.get(folder.name, "")
        if metadata.is_file():
            meta = json.loads(metadata.read_text(encoding="utf-8"))
            source = source or f"hako {meta.get('path', '')}"
        books[folder.name] = {"chapters": len(chapters), "words": words, "source": source, "sha256": files}
    return books


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    books = scan()
    if args.check:
        recorded = json.loads(MANIFEST.read_text(encoding="utf-8"))
        problems = 0
        for name, book in recorded.items():
            now = books.get(name)
            if now is None:
                print(f"MẤT CẢ TRUYỆN: {name}")
                problems += 1
                continue
            for chapter, digest in book["sha256"].items():
                if now["sha256"].get(chapter) != digest:
                    print(f"{name}/{chapter}: {'mất' if chapter not in now['sha256'] else 'đổi nội dung'}")
                    problems += 1
        print(f"{len(recorded)} truyện trong bảng kê, {problems} vấn đề")
        return 1 if problems else 0
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(books, ensure_ascii=False, indent=1), encoding="utf-8")
    for name, book in books.items():
        print(f"{book['chapters']:>5} ch {book['words']:>10,} từ  {name}")
    print(f"tổng {sum(b['chapters'] for b in books.values()):,} chương, {sum(b['words'] for b in books.values()):,} từ -> {MANIFEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
