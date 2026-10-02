"""Chấm một cuốn sách THẬT bằng bộ chấm ứng viên, ghi `doubt.json` cạnh sách cho hộp "Việc cần duyệt" (STUDIO_REVIEW.md).

    CUDA_VISIBLE_DEVICES=-1 D:/Novels/LLM_Train/.venv/Scripts/python.exe \
        scripts/model_eval/quote_scorer/doubt_for_book.py <thư mục sách> --scorer D:/Novels/LLM_Train/runs/scorer_prod_27_09

Bộ chấm KHÔNG đổi nhãn nào của dây chuyền - nó chỉ nói câu nào đáng để người nghe lại (review_curve.py 27-09: duyệt 20%
câu xếp theo bộ chấm 74,8 -> 84,6%, theo tin cậy LLM tự báo 79,7% = ngẫu nhiên). Mặc định chạy CPU: GPU thuộc hàng huấn
luyện/sản xuất (mọi việc GPU đi qua một hàng). Cửa sổ dựng y như build_unlabeled.py (dàn trang paragraph, danh sách nhân
vật chương, khớp tên phân biệt hoa thường), thêm câu nội tâm.

doubt.json: {"scorer": ..., "temperature": T, "segments": {stable_id: {"llm": nhãn LLM, "choice": người bộ chấm chọn hoặc
null (= không ai có tên), "certainty": tin cậy đã hiệu chỉnh, "top": [[tên, xác suất], ...], "disagree": bool}}}.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[2]))  # _internal: abook.character_registry

from build_vi import (
    aliases_for,
    chapter_cast,
    join_segments,
    mention_spans,
    windows_for,
    with_cast,
)


def name_aliases(display: dict[str, str], book_text: str, common: int = 3) -> dict[str, set[str]]:
    """aliases_for, bỏ những MẢNH tên là chữ thường dùng: "Lão" của LÃO QUẢN GIA, "Báo" của CHIM BÁO TỬ.

    Khớp phân biệt hoa thường vẫn bắt mọi chữ đầu câu, nên chỉ nhìn chữ hoa thì "Lão nói" là chỗ nhắc lão quản gia. Phép
    thử lấy từ chính sách: tên riêng gần như không bao giờ viết thường, còn một mảnh xuất hiện viết thường từ `common` lần
    trở lên là chữ thường dùng - bỏ mảnh ấy, giữ tên đầy đủ. Không cần từ điển, đúng cho mọi thể loại và mọi ngôn ngữ
    có chữ hoa."""
    lowercase = Counter(word for word in re.findall(r"\w+", book_text) if word.islower())
    table = aliases_for(set(display), display)
    full = {entity.replace("_", " ").lower() for entity in display} | {
        name.replace("_", " ").lower() for name in display.values()}
    return {alias: entities for alias, entities in table.items()
            if alias in full or lowercase[alias] < common}


def build_windows(project: Path, out: Path, tokenizer_name: str, budget: int
                  ) -> tuple[dict[tuple[str, int], dict], set[str]]:
    """Viết cửa sổ ra `out`; trả ((chương, seq) -> {stable_id, nhãn LLM, khoá}, dàn diễn viên)."""
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)

    def count_tokens(text: str) -> int:
        return len(tokenizer(text, add_special_tokens=False)["input_ids"])

    connection = sqlite3.connect((project / "project.sqlite3").resolve().as_uri() + "?mode=ro", uri=True)
    from abook.character_registry import PRONOUNS, canonical_key

    # Ứng viên = dàn diễn viên THẬT: người dây chuyền đã giao ít nhất một câu. Bảng `characters` của một lô gieo từ lô trước
    # tích cả rác (throne_18: 706 tên, có "HẮN TA", "CÔ", "Y", "NGHE") - lấy nó làm ứng viên thì "Hắn nói" đầu câu thành
    # chỗ nhắc "HẮN TA" và bộ chấm chọn nó 39 lần. Đại từ và vai phụ cục bộ cũng không phải ứng viên: dây chuyền đẩy chúng
    # về nhóm vô danh (build_registry_and_cast), nên bộ chấm chọn chúng là chỉ sai chỗ cho người duyệt.
    names = {canonical_key(str(c)): str(d or c) for c, d in
             connection.execute("SELECT canonical_name, display_name FROM characters")}
    display: dict[str, str] = {}
    for (speaker,) in connection.execute(
        "SELECT DISTINCT speaker FROM segments WHERE kind IN ('dialogue', 'thought') AND status != 'pending'"
    ):
        key = canonical_key(str(speaker or ""))
        if (key and key != "NARRATOR" and not key.startswith("NPC_LOCAL") and key.casefold() not in PRONOUNS
                and "UNKNOWN" not in key and "ANONYMOUS" not in key):
            display[key] = names.get(key, str(speaker))
    book_text = "\n".join(str(text) for (text,) in connection.execute("SELECT text FROM segments"))
    aliases = name_aliases(display, book_text)
    chapters = connection.execute("SELECT id, title FROM chapters ORDER BY chapter_index").fetchall()
    lookup: dict[tuple[str, int], dict] = {}
    with out.open("w", encoding="utf-8") as writer:
        for chapter_id, title in chapters:
            rows = connection.execute(
                "SELECT seq, text, kind, paragraph_index, stable_id, speaker, status FROM segments WHERE chapter_id = ?"
                " ORDER BY seq", (chapter_id,)
            ).fetchall()
            if any(status == "pending" for *_, status in rows):
                continue  # chương chưa phân tích xong: nhãn LLM chưa có để so
            segments = [(int(seq), str(text)) for seq, text, *_ in rows]
            paragraph_of = {int(seq): int(paragraph) for seq, _, _, paragraph, *_ in rows}
            quotes = {int(seq): ("D", "?") for seq, _, kind, *_ in rows if kind in ("dialogue", "thought")}
            for seq, _, kind, _, stable_id, speaker, _ in rows:
                if kind in ("dialogue", "thought"):
                    lookup[(str(title), int(seq))] = {"stable_id": str(stable_id), "llm": str(speaker),
                                                      "key": canonical_key(str(speaker or ""))}
            cast = chapter_cast(segments, aliases, None, True)
            for lo, hi, seqs in windows_for(segments, quotes, budget, count_tokens):
                text, offsets = join_segments(segments[lo:hi + 1], paragraph_of)
                mentions = mention_spans(text, aliases, True)
                text, offsets, mentions = with_cast(text, offsets, mentions, cast, display)
                items = [{"start": offsets[seq][0], "end": offsets[seq][1], "speaker": None, "unlabeled": True, "kind": "D",
                          "book": project.name, "chapter": str(title), "seq": seq} for seq in seqs]
                writer.write(json.dumps({"text": text, "quotes": items, "mentions": mentions}, ensure_ascii=False) + "\n")
    connection.close()
    return lookup, set(display)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project", type=Path)
    parser.add_argument("--scorer", type=Path, required=True, help="lần chạy có encoder/ + head.pt")
    parser.add_argument("--out", type=Path, default=None, help="mặc định <sách>/doubt.json")
    parser.add_argument("--temperature", type=float, default=6.0)
    parser.add_argument("--tokenizer", default="jhu-clsp/mmBERT-base")
    parser.add_argument("--budget", type=int, default=1024)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as scratch:
        scratch_dir = Path(scratch)
        windows = scratch_dir / "windows.jsonl"
        lookup, cast_keys = build_windows(args.project, windows, args.tokenizer, args.budget)
        # train_scorer cần --data (train/dev/test). Test = chính các cửa sổ: nó nhìn dữ liệu để biết có "xô danh sách nhân
        # vật" không (has_cast) - đưa bộ rỗng thì đầu ra khác kích thước và nạp head.pt đã học có danh sách sẽ hỏng.
        data = scratch_dir / "data"
        data.mkdir()
        for name in ("train", "dev"):
            (data / f"{name}.jsonl").write_text("", encoding="utf-8")
        (data / "test.jsonl").write_text(windows.read_text(encoding="utf-8"), encoding="utf-8")
        run = scratch_dir / "run"
        done = subprocess.run(
            [sys.executable, "-u", "-W", "ignore", str(HERE / "train_scorer.py"), "--data", str(data), "--out", str(run),
             "--init", str(args.scorer), "--predict-file", str(windows)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        predictions = run / "predictions.jsonl"
        if done.returncode != 0 or not predictions.is_file():
            print(done.stdout[-2000:], done.stderr[-2000:])
            return 1
        rows = [json.loads(line) for line in predictions.read_text(encoding="utf-8").splitlines() if line.strip()]

    segments = {}
    for row in rows:
        where = lookup.get((str(row["chapter"]), int(row["seq"])))
        if where is None:
            continue
        options = {**row["probs"], None: row["p_null"]}
        scaled = {name: math.log(max(1e-12, p)) / args.temperature for name, p in options.items()}
        top = max(scaled.values())
        total = sum(math.exp(value - top) for value in scaled.values())
        calibrated = sorted(((name, math.exp(value - top) / total) for name, value in scaled.items()), key=lambda x: -x[1])
        choice, certainty = calibrated[0]
        llm = where["llm"]
        # Nhãn LLM "có tên" = một người trong dàn diễn viên; NARRATOR, vai phụ cục bộ, "Hắn" thì không.
        named_llm = where["key"] in cast_keys
        segments[where["stable_id"]] = {
            "llm": llm,
            "choice": choice,
            "certainty": round(certainty, 4),
            "top": [[name, round(p, 4)] for name, p in calibrated[:3]],
            "disagree": bool(choice is not None and (not named_llm or choice != where["key"])),
        }
    out = args.out or (args.project / "doubt.json")
    out.write_text(json.dumps({"scorer": str(args.scorer), "temperature": args.temperature, "segments": segments},
                              ensure_ascii=False), encoding="utf-8")
    disagree = sum(entry["disagree"] for entry in segments.values())
    print(f"{len(segments)} câu thoại/nội tâm chấm xong, bất đồng với LLM {disagree}; ghi {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
