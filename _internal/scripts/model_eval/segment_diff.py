"""Bộ tách đoạn đổi thì số thứ tự đoạn (seq) của đáp án chuẩn lệch theo: chương nào đổi, đổi ở đâu, và chuyển đáp án sang
cách tách mới theo văn bản.

    python scripts/model_eval/segment_diff.py --old D:/Novels/ABook/_internal --new D:/Novels/ABook_disc/_internal
    python scripts/model_eval/segment_diff.py --old ... --new ... --migrate      # ghi gold/*.txt theo cách tách mới

Mỗi mã (`--old`, `--new`) tách mọi chương có đáp án bằng CHÍNH `text_processing` của nó (tiến trình con riêng - hai bản
cùng tên module không nạp chung một tiến trình được), cùng `max_chars` 340 của project đo. So hai dãy đoạn (văn bản + loại
bộ tách khoá) bằng difflib. `--migrate`: đoạn không đổi giữ nguyên nhãn (đánh số lại); đoạn cũ bị tách thành thoại + lời
dẫn (“Được,” Liz gật đầu.) thì phần thoại lấy người nói từ nhãn cũ theo quy tắc 10 ("N NARRATOR,LIZ~" -> "D LIZ,..."),
phần lời dẫn thành "N"; chỗ không suy được ghi "?" để người gán điền, và in ra.
"""
from __future__ import annotations

import argparse
import difflib
import json

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLD = HERE / "gold"
sys.path.insert(0, str(HERE))
from replay_all import BOOKS, CORPUS  # noqa: E402

PRODUCTION_SOURCE = Path("D:/Novels/ABook/Text_Tmp")
# Kho truyện là repo riêng, chỉ nằm ở checkout chính - worktree không có.
if not CORPUS.is_dir():
    CORPUS = Path("D:/Novels/ABook/Corpus")
MAX_CHARS = 340
SEGMENT_SCRIPT = r"""
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from ebook_reader.text_processing import decode_text_bytes, segment_chapter_text
out = {}
for path in json.loads(sys.stdin.read()):
    text = decode_text_bytes(Path(path).read_bytes())
    rows = segment_chapter_text(1, text, max_chars=int(sys.argv[2]))
    out[path] = [[row["kind_hint"], row["text"]] for row in rows]
print(json.dumps(out, ensure_ascii=False))
"""


def gold_files() -> list[tuple[Path, Path]]:
    pairs = []
    for folder in sorted(path for path in GOLD.iterdir() if path.is_dir()):
        book = BOOKS.get(folder.name, "")
        if book == "":
            continue
        root = PRODUCTION_SOURCE if book is None else CORPUS / book
        for gold in sorted(folder.glob("*.txt")):
            source = root / gold.name
            if source.is_file():
                pairs.append((gold, source))
    return pairs


def segments(code_root: str, sources: list[Path]) -> dict[str, list[list[str]]]:
    done = subprocess.run([sys.executable, "-c", SEGMENT_SCRIPT, code_root, str(MAX_CHARS)],
                          input=json.dumps([str(path) for path in sources]), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=True)
    return json.loads(done.stdout)


def gold_lines(path: Path) -> tuple[list[str], dict[int, str]]:
    header, labels = [], {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            header.append(line)
            continue
        seq, _, rest = line.partition(" ")
        labels[int(seq)] = rest
    return header, labels


def split_label(old: str, kind: str) -> str:
    """Nhãn cho phần THOẠI tách ra từ một đoạn cũ khoá N: người nói ~ của nhãn cũ (quy tắc 10) thành người nói đủ."""
    parts = old.split(" ")
    if len(parts) < 2:
        return f"{kind} ?"
    names = (" ".join(parts[1:-5]) if len(parts) >= 7 else parts[1]).split(",")
    speakers = [name for name in names if name.endswith("~") and name.rstrip("~") not in ("NARRATOR", "UNKNOWN", "NPC*")]
    if not speakers:
        return f"{kind} ?"
    main = speakers[0].rstrip("~")
    tail = " ".join(parts[-5:]) if len(parts) >= 7 else "neutral 0-1 normal normal u"
    return f"{kind} {main} {tail}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--old", required=True)
    parser.add_argument("--new", required=True)
    parser.add_argument("--migrate", action="store_true")
    args = parser.parse_args()
    pairs = gold_files()
    sources = [source for _gold, source in pairs]
    old, new = segments(args.old, sources), segments(args.new, sources)
    changed = 0
    for gold, source in pairs:
        before, after = old[str(source)], new[str(source)]
        if before == after:
            continue
        changed += 1
        header, labels = gold_lines(gold)
        print(f"== {gold.parent.name}/{gold.name}: {len(before)} -> {len(after)} đoạn")
        matcher = difflib.SequenceMatcher(a=[text for _k, text in before], b=[text for _k, text in after], autojunk=False)
        out: dict[int, str] = {}
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for offset in range(i2 - i1):
                    old_kind, new_kind = before[i1 + offset][0], after[j1 + offset][0]
                    label = labels.get(i1 + offset, "N")
                    if old_kind != new_kind:
                        print(f"   [{i1 + offset}->{j1 + offset}] loại {old_kind}->{new_kind}: {after[j1 + offset][1][:70]}")
                        label = f"{split_label(label, new_kind[0].upper())}"
                    out[j1 + offset] = label
                continue
            olds = [f"[{i}] {before[i][0][:1].upper()} {labels.get(i, 'N')[:60]} | {before[i][1][:60]}" for i in range(i1, i2)]
            print(f"   {tag}: " + " || ".join(olds))
            source_label = labels.get(i1, "N") if i2 > i1 else "N"
            for j in range(j1, j2):
                kind, text = after[j]
                letter = {"dialogue": "D", "narration": "N", "thought": "T"}.get(kind, kind[:1].upper())
                out[j] = split_label(source_label, letter) if letter in ("D", "T") else "N"
                print(f"      -> [{j}] {out[j][:60]} | {text[:70]}")
        if args.migrate:
            body = [f"{seq} {out.get(seq, 'N')}" for seq in range(len(after))]
            gold.write_bytes(("\n".join(header + body) + "\n").encode("utf-8"))
    print(f"{changed}/{len(pairs)} chương đáp án đổi cách tách")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
