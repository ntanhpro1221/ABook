"""Bốn cổng (TMA, YMP ngôi thứ nhất, Tam quốc, Tắt đèn): người nói chặt, cảm xúc (eval_models.json) và F1 giọng B-cubed.

    python gates_table.py v3=28-09-lora3 v6=29-09-lora6 [v7=29-09-lora7]

Mỗi đối số <nhãn>=<tiền tố>: cổng TMA ở <tiền tố>, ba cổng kia ở <tiền tố>-ymp-pov / -tamquoc / -tatden. v3 đo YMP bằng
bộ tách cũ; bản đo lại bằng bộ tách mới là 28-09-lora3-newsplit-ymp - dùng nó nếu có (cùng cách tách với v5 trở đi).
LƯU Ý: v4/v5 đã HỌC chương cổng Tam quốc/Tắt đèn (data_v4/v5) - số hai cổng ấy của v4/v5 vô giá trị.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "D:/Novels/ABook/_internal/scripts/model_eval")
sys.path.insert(0, "D:/Novels/ABook/_internal")
from score_models import GOLD_ROOT, load_gold, read_project  # noqa: E402
from voice_identity import bcubed, source_text, voice_of  # noqa: E402

from abook.character_registry import canonical_speaker_names  # noqa: E402

EVAL = Path("D:/Novels/Audiobooks/_model_eval_v2")
GATES = [("TMA", "", "throne_of_magical_arcana", ("351", "363", "378", "381")),
         ("YMP", "-ymp-pov", "young_masters_pov", ("248",)),
         ("Tam quốc", "-tamquoc", "tam_quoc_dien_nghia", ("050", "051", "052")),
         ("Tắt đèn", "-tatden", "tat_den_ngo_tat_to", ("020", "021", "024"))]


def gate(root: Path, gold_dir: str, chapters: tuple[str, ...]) -> str:
    summary = root / "eval_models.json"
    if not summary.is_file():
        return "-"
    entry = next((e for e in json.loads(summary.read_text(encoding="utf-8")) if e.get("chapters_ok") == e.get("chapters")), None)
    if entry is None:
        return "dở"
    gold = load_gold(GOLD_ROOT / gold_dir)
    projects = [found.parent for model in root.iterdir() if model.is_dir() for chapter in chapters
                for found in [next((model / chapter).rglob("project.sqlite3"), None)] if found]
    rows = {}
    for project in projects:
        with contextlib.redirect_stdout(io.StringIO()):
            found, _meta = read_project(project, set(chapters))
        rows.update({(str(row["chapter"]), int(row["seq"])): row for row in found})
    mapping = canonical_speaker_names(Counter(str(row["speaker"] or "") for row in rows.values()), source_text(projects))
    points = [(entry_.speakers[0][0], voice_of(str(rows[key]["speaker"] or ""), key[0], mapping))
              for key, entry_ in gold.items() if entry_.spoken and key in rows]
    f1 = bcubed(points)[2] if points else 0.0
    rates = entry["rates"]
    return f"chặt {rates['speaker']:.1f} · F1 {f1:.1%} · cảm xúc {rates['emotion']:.1f}"


def main(argv: list[str]) -> int:
    runs = [spec.partition("=") for spec in argv]
    print("| cổng | " + " | ".join(label for label, _, _ in runs) + " |")
    print("|---|" + "---|" * len(runs))
    for name, suffix, gold_dir, chapters in GATES:
        cells = []
        for label, _, prefix in runs:
            root = EVAL / f"{prefix}{suffix}"
            if label == "v3" and suffix == "-ymp-pov" and (EVAL / "28-09-lora3-newsplit-ymp").is_dir():
                root = EVAL / "28-09-lora3-newsplit-ymp"
            cells.append(gate(root, gold_dir, chapters))
        print(f"| {name} | " + " | ".join(cells) + " |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
