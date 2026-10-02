r"""Lấy truyện hết bản quyền từ vi.wikisource về kho `Corpus/` - mỗi trang một chương `NNN.txt`.

    python scripts/corpus/wikisource.py "Tam quốc diễn nghĩa (Phan Kế Bính)" "Tam quốc diễn nghĩa/Hồi {n}" 1 120

Trang đổi hướng (`#đổi [[...]]`) được theo tới đích. Chữ ra theo lối kho đã có: mỗi đoạn văn, mỗi dòng thơ, mỗi dòng
tiêu đề là một đoạn cách nhau một dòng trống; khung đầu trang (`{{đầu đề}}`) bỏ; khung trình bày (`{{g|..}}`,
`{{biên trái|..}}`) chỉ giữ chữ bên trong; liên kết `[[a|b]]` -> `b`; chú thích `<ref>` bỏ. Chương đã có trong kho
KHÔNG bị ghi đè (mã băm của chương cũ nằm trong bảng kê `Corpus/manifest.json` và trong các tập train/test).
Kho là repo riêng tư; chỉ lấy sách hết bản quyền.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# Kho chung, không theo worktree: parents[3] trỏ <worktree>/Corpus nên chạy từ worktree khác bản chính là ghi sai chỗ
# (02-10). Cùng quy ước với model_eval/make_eval_project.py.
CORPUS = Path(os.environ.get("ABOOK_CORPUS", "D:/Novels/ABook/Corpus"))
RAW = "https://vi.wikisource.org/w/index.php?title={title}&action=raw"
REDIRECT = re.compile(r"^#(?:đổi|redirect)\s*\[\[([^\]]+)\]\]", re.IGNORECASE)
USER_AGENT = "ABook-corpus/1.0 (research; contact via github.com/ntanhpro1221)"


def fetch(title: str, hops: int = 3) -> str:
    url = RAW.format(title=urllib.parse.quote(title.replace(" ", "_")))
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=60) as response:
        text = response.read().decode("utf-8")
    found = REDIRECT.match(text.strip())
    if found and hops:
        return fetch(found.group(1).split("|")[0].strip(), hops - 1)
    return text


def to_text(wikitext: str) -> str:
    """Lối của kho: `{{SIC|chữ sách|chữ đúng}}` giữ CHỮ SÁCH (lỗi in cũng là nguồn); chú thích `<ref>` thành dấu "[k]"
    trong câu và đoạn "▲ ..." ở chỗ bảng chú thích (hay cuối chương)."""
    notes: list[str] = []

    def note(found: re.Match[str]) -> str:
        notes.append(" ".join(found.group(1).split()))
        return f"[{len(notes)}]"

    wikitext = re.sub(r"<ref[^>/]*/>", "", wikitext)
    wikitext = re.sub(r"<ref[^>]*>(.*?)</ref>", note, wikitext, flags=re.S)
    wikitext = re.sub(r"\{\{SIC\|([^|}]*)\|[^}]*\}\}", r"\1", wikitext)
    wikitext = re.sub(r"\[\[(?:Tập tin|Hình|File|Image):[^\]]*\]\]", "", wikitext, flags=re.IGNORECASE)  # ảnh minh hoạ
    paragraphs: list[str] = []
    skipping = 0
    notes_placed = False
    for raw in wikitext.splitlines():
        line = raw.strip()
        if skipping or line.startswith("{{đầu đề"):
            skipping += line.count("{{") - line.count("}}")
            continue
        if re.match(r"\{\{chú thích|<references", line):
            paragraphs.extend(f"▲ {text}" for text in notes)
            notes_placed = True
            continue
        # Khung trình bày mở dòng ("{{g|", "{{biên trái|2em|", "{{...|nhỏ|phải|"): tên khung và các tham số một chữ
        # đứng trước nội dung; dấu ":" đầu dòng là thụt lề.
        line = re.sub(r"^\{\{[^|{}]+\|(?:[^|{}\s]+\|)*", "", line).lstrip(":").strip()
        line = line.replace("}}", "")
        line = re.sub(r"</?poem>|'{2,3}|<br\s*/?>", "", line)
        line = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", line).strip()
        if line:
            paragraphs.append(line)
    if notes and not notes_placed:
        paragraphs.extend(f"▲ {text}" for text in notes)
    return "\n\n".join(paragraphs) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("book", help="thư mục truyện trong Corpus/")
    parser.add_argument("pattern", help='tên trang, {n} là số chương, vd "Tam quốc diễn nghĩa/Hồi {n}"')
    parser.add_argument("first", type=int)
    parser.add_argument("last", type=int)
    parser.add_argument("--check", type=int, default=None, help="chỉ so chương này với bản đã có trong kho, không ghi")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    folder = CORPUS / args.book
    if args.check is not None:
        mine = to_text(fetch(args.pattern.format(n=args.check)))
        stored = (folder / f"{args.check:03d}.txt").read_text(encoding="utf-8")
        print("KHỚP từng ký tự" if mine == stored else f"LỆCH: của ta {len(mine)} ký tự, kho {len(stored)}")
        return 0 if mine == stored else 1
    folder.mkdir(parents=True, exist_ok=True)
    written = kept = 0
    for number in range(args.first, args.last + 1):
        target = folder / f"{number:03d}.txt"
        if target.exists():
            kept += 1
            continue
        target.write_text(to_text(fetch(args.pattern.format(n=number))), encoding="utf-8")
        written += 1
        time.sleep(0.5)  # lịch sự với máy chủ của wikisource
    print(json.dumps({"ghi": written, "giữ nguyên": kept, "thư mục": str(folder)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
