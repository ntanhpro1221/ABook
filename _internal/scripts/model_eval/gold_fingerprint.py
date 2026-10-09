r"""Ghi dấu chữ `.seqtext` cho một chương đáp án, từ project mà đáp án được gắn nhãn trên đó.

    python scripts/model_eval/gold_fingerprint.py <project> <gold_dir> --chapter 042
    python scripts/model_eval/gold_fingerprint.py <project> <gold_dir> --chapter 042 --variant a40231f3   # cách tách khác
    (gold_dir: đường dẫn, hoặc chỉ tên truyện trong scripts/model_eval/gold/)

Đáp án khoá theo seq, không mang chữ; dấu chữ là `seq<TAB>băm` cho MỌI đoạn của chương (không chỉ đoạn có nhãn) để
score_models.aligned_gold phát hiện parser tách chương khác. `--variant` ghi vào `_variants/<nhãn>/` - chỗ đặt đáp án gắn nhãn
trên một cách tách khác (cùng chương: `<chương>.txt` + `<chương>.seqtext`). Không ghi đè nếu không có --force.
Mã thoát: 0 đã ghi; 1 file đã có; 2 project không có chương ấy.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from score_models import GOLD_ROOT, read_segment_texts, write_seqtext  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project", type=Path)
    parser.add_argument("gold_dir", type=Path)
    parser.add_argument("--chapter", required=True, help="tên chương như khoá của đáp án (tên file .txt không có đuôi)")
    parser.add_argument("--variant", help="nhãn biến thể: ghi vào _variants/<nhãn>/ thay vì cạnh đáp án chính")
    parser.add_argument("--force", action="store_true", help="ghi đè dấu chữ đã có")
    args = parser.parse_args(argv)

    gold_dir = args.gold_dir if args.gold_dir.is_dir() or not (GOLD_ROOT / args.gold_dir).is_dir() else GOLD_ROOT / args.gold_dir
    texts = read_segment_texts(args.project, {args.chapter}).get(args.chapter)
    if not texts:
        print(f"project {args.project} không có đoạn nào của chương {args.chapter}", file=sys.stderr)
        return 2
    target_dir = gold_dir / "_variants" / args.variant if args.variant else gold_dir
    target = target_dir / f"{args.chapter}.seqtext"
    if target.exists() and not args.force:
        print(f"{target} đã có - thêm --force để ghi đè", file=sys.stderr)
        return 1
    target_dir.mkdir(parents=True, exist_ok=True)
    label = f"{gold_dir.name}/{args.variant}/{args.chapter}" if args.variant else f"{gold_dir.name}/{args.chapter}"
    write_seqtext(target, texts, [
        f"dấu chữ gold {label}: seq<TAB>sha1(chữ chuẩn hoá NFC + gộp khoảng trắng)[:12]",
        f"project {args.project} | {date.today().isoformat()} | {len(texts)} đoạn",
    ])
    print(f"đã ghi {target} ({len(texts)} đoạn)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
