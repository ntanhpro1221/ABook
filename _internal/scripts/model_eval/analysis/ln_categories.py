"""Người nói đúng theo LOẠI câu trên bộ LN (cơ sở + mở rộng): biết model mới hơn/kém ở đâu, dữ liệu nhắm lỗi có tác dụng không.

    python ln_categories.py v3=28-09-ln-lora3n,29-09-lnx-lora3 v6=29-09-ln-lora6,29-09-lnx-lora6

Loại (một câu có thể thuộc nhiều loại): 『』 (câu mở bằng 『), tôi nói (người nói đáp án là người kể "tôi" của chương),
vô danh (đáp án NPC*), đối đáp liền (câu trước VÀ câu sau đều là lời nói - giữa chuỗi đối đáp không lời dẫn), có lời dẫn
(câu kể liền trước/sau nêu tên người nói), còn lại. Mỗi ô: số câu, % đúng chặt (tín dụng đủ), % đúng sau lượt gom tên của
dây chuyền (nhãn sau `canonical_speaker_names`, như người nghe nghe tên).
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ln_table import EVAL  # noqa: E402
from lnx_table import BASE, EXT  # noqa: E402

sys.path.insert(0, "D:/Novels/ABook/_internal/scripts/model_eval")
sys.path.insert(0, "D:/Novels/ABook/_internal")
from score_models import GOLD_ROOT, load_gold, read_project, speaker_credit  # noqa: E402
from voice_identity import source_text  # noqa: E402

from abook.character_registry import canonical_speaker_names  # noqa: E402

FIRST_PERSON = {"hdst": "ED ROSTAILER", "yamiyo": "TOMOBE", "nageki": "KRAI ANDREY", "lu": "KAKERU SORANO",
                "yamiyo225": "TOMOBE", "nageki62": "KRAI ANDREY", "hdst130": "ED ROSTAILER", "lu10": "YUUKO HAYASE"}
CATEGORIES = ("『』", "tôi nói", "vô danh", "đối đáp liền", "có lời dẫn", "còn lại", "TẤT CẢ")


def finished(root: Path) -> bool:
    summary = root / "eval_models.json"
    return summary.is_file() and any(entry.get("chapters_ok") == entry.get("chapters") and entry.get("chapters")
                                     for entry in json.loads(summary.read_text(encoding="utf-8")))


def categories(name: str, chapter: str, seq: int, entry, gold, texts: dict[int, str]) -> list[str]:
    found = []
    text = texts.get(seq, "").lstrip()
    person = entry.speakers[0][0]
    if text.startswith("『"):
        found.append("『』")
    narrator = FIRST_PERSON.get(name, "")
    if narrator and set(person.split()) & set(narrator.split()):
        found.append("tôi nói")
    if person.startswith("NPC"):
        found.append("vô danh")
    before, after = gold.get((chapter, seq - 1)), gold.get((chapter, seq + 1))
    if before is not None and after is not None and before.spoken and after.spoken:
        found.append("đối đáp liền")
    words = {word.casefold() for word in person.split() if len(word) > 1}
    for other in (seq - 1, seq + 1):
        neighbour = gold.get((chapter, other))
        if neighbour is not None and not neighbour.spoken and words & {w.casefold().strip(".,!?…:;\"“”") for w in texts.get(other, "").split()}:
            found.append("có lời dẫn")
            break
    return found or ["còn lại"]


def collect(spec: str) -> dict[str, list[int]]:
    """{loại: [số câu, đúng chặt, đúng sau gom]} gộp mọi chương đã đo xong."""
    base, _, ext = spec.partition("=")[2].partition(",")
    table: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for prefix, chapters in ((base, BASE), (ext, EXT)):
        if not prefix:
            continue
        for name, gold_dir, chapter in chapters:
            root = EVAL / f"{prefix}-{name}"
            if not finished(root):
                continue
            gold = load_gold(GOLD_ROOT / gold_dir)
            project = next((path for model in root.iterdir() if model.is_dir()
                            for path in [next((model / chapter).rglob("project.sqlite3"), None)] if path), None)
            if project is None:
                continue
            with contextlib.redirect_stdout(io.StringIO()):
                rows_list, _meta = read_project(project.parent, {chapter})
            rows = {int(row["seq"]): row for row in rows_list if str(row["chapter"]) == chapter}
            texts = {seq: str(row["text"] or "") for seq, row in rows.items()}
            mapping = canonical_speaker_names(Counter(str(row["speaker"] or "") for row in rows.values()),
                                              source_text([project.parent]))
            for (gold_chapter, seq), entry in gold.items():
                if gold_chapter != chapter or not entry.spoken or seq not in rows:
                    continue
                label = str(rows[seq]["speaker"] or "")
                strict = speaker_credit(entry, label) >= 1.0
                mapped = speaker_credit(entry, mapping.get(label, label)) >= 1.0
                for category in categories(name, chapter, seq, entry, gold, texts) + ["TẤT CẢ"]:
                    cell = table[category]
                    cell[0] += 1
                    cell[1] += strict
                    cell[2] += mapped
    return table


def main(argv: list[str]) -> int:
    runs = {spec.partition("=")[0]: collect(spec) for spec in argv}
    print("| loại | " + " | ".join(f"{label} (câu, chặt, sau gom)" for label in runs) + " |")
    print("|---|" + "---|" * len(runs))
    for category in CATEGORIES:
        cells = []
        for table in runs.values():
            count, strict, mapped = table.get(category, [0, 0, 0])
            cells.append(f"{count}, {strict / count:.1%}, {mapped / count:.1%}" if count else "-")
        print(f"| {category} | " + " | ".join(cells) + " |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
