"""Một người, một giọng: chấm người nói theo CỤM, như người nghe nghe - không theo chữ trên nhãn.

    python voice_identity.py <root lượt đo> <thư mục gold> <chương> [<chương> ...] [--without-given-names]
    python voice_identity.py D:/Novels/Audiobooks/_model_eval_v2/27-09-tamquoc tam_quoc_dien_nghia 050 051 052
    python voice_identity.py --gold-check

Người nghe không đọc nhãn: `HOANG CAI` hay `Hoàng Cái` là MỘT giọng nếu dây chuyền gom chúng làm một nhân vật. Cái
họ nghe ra là (a) một người bị đọc bằng hai giọng (tách) và (b) hai người chung một giọng (nhập). Nên:

1. Nhãn người nói của từng model đi qua ĐÚNG các lượt gom tên của dây chuyền trước khi khoá giọng
   (`character_registry.canonical_speaker_names`, gọi thẳng, không chép lại), gộp CẢ các chương đo như một cuốn -
   dây chuyền thật phân tích cả cuốn trong một project. `--without-given-names` tắt lượt tên gọi để so trước/sau.
2. Mỗi câu thoại/nội tâm có đáp án là một điểm; cụm dự đoán = nhân vật sau gom (NPC cục bộ: mỗi nhãn một cụm trong
   chương của nó; NPC*/đại từ: một cụm "vô danh" chung), cụm đáp án = người nói ưu tiên của đáp án.
3. B-cubed (Bagga & Baldwin 1998, thước đo chuẩn của đồng tham chiếu): độ chính xác = phần câu cùng giọng với câu này
   mà đúng là cùng người (thấp = NHẬP); độ phủ = phần câu cùng người với câu này mà được cùng giọng (thấp = TÁCH).

Kèm độ đúng nhãn chặt (`score_models`) trên cùng các câu để thấy khoảng cách giữa "sai chữ" và "sai giọng".
`--gold-check`: phần PHÁ - chạy các lượt gom trên chính nhãn đáp án của từng truyện; gom hai người làm một là lỗi.
Đo 27-09 (ANALYSIS_RESEARCH.md, "Một người một giọng").
"""
from __future__ import annotations

import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (HERE, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from score_models import GOLD_ROOT, load_gold, read_project, speaker_credit, speaker_key  # noqa: E402

from ebook_reader import character_registry  # noqa: E402
from ebook_reader.character_registry import canonical_speaker_names, fold_for_source_search, is_local_speaker  # noqa: E402


def source_text(projects: list[Path]) -> str:
    """Như `_folded_source_text`: mọi .txt cùng thư mục với các chương của project, bỏ dấu, chữ thường."""
    folders: set[Path] = set()
    for project in projects:
        connection = sqlite3.connect(f"file:{project / 'project.sqlite3'}?mode=ro", uri=True)
        try:
            for (input_path,) in connection.execute("SELECT input_path FROM chapters"):
                if input_path and Path(str(input_path)).parent.is_dir():
                    folders.add(Path(str(input_path)).parent)
        finally:
            connection.close()
    chunks = [path.read_text(encoding="utf-8", errors="replace")
              for folder in sorted(folders) for path in sorted(folder.glob("*.txt"))]
    return fold_for_source_search("\n".join(chunks))


def voice_of(label: str, chapter: str, mapping: dict[str, str]) -> str:
    """Giọng người nghe nghe: nhân vật sau gom; NPC cục bộ riêng từng chương; vô danh chung một giọng."""
    if is_local_speaker(label):
        return f"{chapter}:{label}"
    if speaker_key(label) == "NPC*":
        return "NPC*"
    return speaker_key(mapping.get(label, label))


def bcubed(points: list[tuple[str, str]]) -> tuple[float, float, float]:
    """(độ chính xác, độ phủ, F1) B-cubed; mỗi điểm là (cụm đáp án, cụm dự đoán)."""
    by_gold = Counter(gold for gold, _ in points)
    by_voice = Counter(voice for _, voice in points)
    both = Counter(points)
    precision = sum(both[point] / by_voice[point[1]] for point in points) / len(points)
    recall = sum(both[point] / by_gold[point[0]] for point in points) / len(points)
    return precision, recall, 2 * precision * recall / (precision + recall)


def gold_check() -> int:
    broken = 0
    for directory in sorted(path for path in GOLD_ROOT.iterdir() if path.is_dir()):
        gold = load_gold(directory)
        labels = Counter(entry.speakers[0][0] for entry in gold.values() if entry.spoken)
        mapping = canonical_speaker_names(labels, "")
        people_by_voice: dict[str, set[str]] = defaultdict(set)
        for label in labels:
            people_by_voice[voice_of(label, "", mapping)].add(speaker_key(label))
        merged = {voice: people for voice, people in people_by_voice.items() if len(people) > 1 and voice != "NPC*"}
        broken += len(merged)
        print(f"{directory.name:28s} {len(labels):3d} người | nhập làm một: "
              + ("; ".join(f"{voice} <- {', '.join(sorted(people))}" for voice, people in merged.items()) or "không"))
    return 1 if broken else 0


def main(argv: list[str]) -> int:
    if "--without-given-names" in argv:
        character_registry.merge_given_names = lambda _representatives: {}
        argv = [arg for arg in argv if arg != "--without-given-names"]
    if argv == ["--gold-check"]:
        return gold_check()
    if len(argv) < 3:
        print(__doc__)
        return 2
    root, gold_dir, chapters = Path(argv[0]), argv[1], tuple(argv[2:])
    gold = load_gold(GOLD_ROOT / gold_dir)
    wanted_chapters = {chapter for chapter, _ in gold}
    for model_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        projects = [found.parent for chapter in chapters
                    for found in [next((model_dir / chapter).rglob("project.sqlite3"), None)] if found]
        if not projects:
            continue
        rows: dict[tuple[str, int], dict] = {}
        for project in projects:
            found, _meta = read_project(project, wanted_chapters)
            rows.update({(str(row["chapter"]), int(row["seq"])): row for row in found})
        labels = Counter(str(row["speaker"] or "") for row in rows.values())
        mapping = canonical_speaker_names(labels, source_text(projects))
        points, places, strict = [], [], 0
        split: dict[str, set[str]] = defaultdict(set)
        merged: dict[str, set[str]] = defaultdict(set)
        for key, entry in gold.items():
            if not entry.spoken or key not in rows:
                continue
            label = str(rows[key]["speaker"] or "")
            person, voice = entry.speakers[0][0], voice_of(label, key[0], mapping)
            points.append((person, voice))
            places.append(key[0])
            strict += speaker_credit(entry, label) > 0
            split[person].add(voice)
            merged[voice].add(person)
        if not points:
            continue
        precision, recall, f1 = bcubed(points)
        split_people = sorted((person for person, voices in split.items() if len(voices) > 1),
                              key=lambda person: -len(split[person]))
        per_chapter = " ".join(
            f"{chapter}:{bcubed([point for point, where in zip(points, places) if where == chapter])[2]:.1%}"
            for chapter in chapters if chapter in places
        )
        print(f"{model_dir.name:24s} {len(points):4d} câu | nhãn chặt {strict / len(points):6.1%} | "
              f"giọng B3 P {precision:6.1%} R {recall:6.1%} F1 {f1:6.1%} | "
              f"người >1 giọng {len(split_people)}/{len(split)} | giọng >1 người "
              f"{sum(len(people) > 1 for people in merged.values())}/{len(merged)} | F1 từng chương {per_chapter}")
        for person in split_people[:6]:
            counts = Counter(voice for gold_person, voice in points if gold_person == person)
            print(f"    tách {person}: " + ", ".join(f"{voice} {count}" for voice, count in counts.most_common(5)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
