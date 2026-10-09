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
   Câu đáp án `NPC*` ("bất kỳ NPC cục bộ nào", GOLD_GUIDE) KHÔNG nói hai người vô danh là một hay hai - từ 29-09 chỉ chấm
   quan hệ đã biết: NPC* khác mọi người có tên (câu người lạ đọc bằng giọng nhân vật chính = NHẬP), còn giữa hai câu NPC*
   thì không tính. Trước đó mọi câu NPC* là MỘT cụm: model tách đúng ba người lạ bị phạt, model gộp bừa được thưởng (LU 10:
   10/39 câu nói là NPC*, Nageki 62: 25/83). `bcubed(..., anonymous_known=True)` cho cách cũ. Câu `NPC*:<mô tả>` (đáp án
   đã soát người vô danh ấy là ai, `gold_person`) là MỘT người, chấm như người có tên - chỉ NPC* trơn còn "chưa biết".

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

from score_models import (  # noqa: E402
    GOLD_ROOT, aligned_gold_multi, exit_on_gold_mismatch, load_gold, read_project, speaker_credit, speaker_key,
)

from abook import character_registry  # noqa: E402
from abook.character_registry import canonical_speaker_names, is_local_speaker  # noqa: E402


def source_text(projects: list[Path]) -> str:
    """Như `character_registry._source_text`: mọi .txt cùng thư mục với các chương của project, nguyên chữ."""
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
    return "\n".join(chunks)


def gold_person(entry) -> str:
    """Cụm đáp án của một câu: người nói ưu tiên; câu `NPC*:<mô tả>` (đáp án đã soát người vô danh ấy là ai - "bà thầy bói",
    "mẹ Kakeru") thành MỘT người như người có tên. `NPC*` trơn (đám đông, chưa soát) vẫn là "chưa biết là ai" - xem `bcubed`.
    Chấm người nói chặt không đổi: mô tả chỉ nói ai cùng ai (29-09 tối - Nageki 62: 25 câu của một bà thầy bói; model tách bà
    làm hai giọng không mất điểm, model giữ một giọng mà lẫn MỘT câu của Krai thì mất nửa độ chính xác của cả 25 câu)."""
    person = entry.speakers[0][0]
    return f"NPC*:{entry.npc_label.casefold()}" if person == "NPC*" and entry.npc_label else person


def voice_of(label: str, chapter: str, mapping: dict[str, str]) -> str:
    """Giọng người nghe nghe: nhân vật sau gom; NPC cục bộ riêng từng chương; vô danh chung một giọng."""
    if is_local_speaker(label):
        return f"{chapter}:{label}"
    if speaker_key(label) == "NPC*":
        return "NPC*"
    return speaker_key(mapping.get(label, label))


def bcubed(points: list[tuple[str, str]], *, anonymous_known: bool = False) -> tuple[float, float, float]:
    """(độ chính xác, độ phủ, F1) B-cubed; mỗi điểm là (cụm đáp án, cụm dự đoán).

    Điểm có đáp án `NPC*` là người vô danh chưa biết là ai: cặp NPC*-NPC* không tính (không phải cùng, không phải khác),
    cặp NPC*-có tên là khác người. Nên với câu NPC*: độ phủ = 1 (không biết ai cùng người với nó), độ chính xác = 1 /
    (1 + số câu có tên cùng giọng). Với câu có tên: như B-cubed thường, câu NPC* cùng giọng tính là khác người.
    `anonymous_known=True`: cách trước 29-09 - mọi câu NPC* là một người.
    """
    # Bảng gộp nhiều chương đặt tên điểm là (chương, người) - người là phần tử cuối. Chỉ `NPC*` TRƠN là chưa biết ai:
    # `NPC*:<mô tả>` (gold_person) là một người đã soát, chấm như người có tên.
    anonymous = {gold for gold, _ in points
                 if not anonymous_known and (gold[-1] if isinstance(gold, tuple) else gold) == "NPC*"}
    by_gold = Counter(gold for gold, _ in points)
    by_voice = Counter(voice for _, voice in points)
    named_by_voice = Counter(voice for gold, voice in points if gold not in anonymous)
    both = Counter(points)
    precision = sum(
        1 / (1 + named_by_voice[voice]) if gold in anonymous else both[(gold, voice)] / by_voice[voice]
        for gold, voice in points
    ) / len(points)
    recall = sum(
        1.0 if gold in anonymous else both[(gold, voice)] / by_gold[gold]
        for gold, voice in points
    ) / len(points)
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


@exit_on_gold_mismatch
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
    wanted_chapters = {chapter for chapter, _ in load_gold(GOLD_ROOT / gold_dir)}
    for model_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        projects = [found.parent for chapter in chapters
                    for found in [next((model_dir / chapter).rglob("project.sqlite3"), None)] if found]
        if not projects:
            continue
        # Đáp án gióng theo chữ của project từng chương của model này (cách tách có thể khác giữa các lượt đo).
        gold = aligned_gold_multi(GOLD_ROOT / gold_dir, projects, wanted_chapters)
        rows: dict[tuple[str, int], dict] = {}
        for project in projects:
            found, _meta = read_project(project, wanted_chapters)
            rows.update({(str(row["chapter"]), int(row["seq"])): row for row in found})
        # Chương đang phân tích dở: câu chưa tới lượt mang nhãn tạm (UNKNOWN) - chấm vào là đo nhầm một "hỏng cả chương"
        # (29-09: TMA 378 của 8B-v5 đọc ra 39/47 UNKNOWN giữa lúc đang đo). Bỏ chương ấy, nói ra.
        unfinished = sorted({key[0] for key, row in rows.items() if str(row.get("status") or "") == "pending"})
        if unfinished:
            print(f"{model_dir.name}: bỏ chương chưa phân tích xong {', '.join(unfinished)}")
            rows = {key: row for key, row in rows.items() if key[0] not in unfinished}
        labels = Counter(str(row["speaker"] or "") for row in rows.values())
        mapping = canonical_speaker_names(labels, source_text(projects))
        points, places, strict, shown = [], [], 0, 0
        split: dict[str, set[str]] = defaultdict(set)
        merged: dict[str, set[str]] = defaultdict(set)
        for key, entry in gold.items():
            if not entry.spoken or key not in rows:
                continue
            label = str(rows[key]["speaker"] or "")
            person, voice = gold_person(entry), voice_of(label, key[0], mapping)
            points.append((person, voice))
            places.append(key[0])
            strict += speaker_credit(entry, label) > 0
            shown += speaker_credit(entry, mapping.get(label, label)) > 0
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
        print(f"{model_dir.name:24s} {len(points):4d} câu | nhãn chặt {strict / len(points):6.1%} "
              f"-> sau gom {shown / len(points):6.1%} | "
              f"giọng B3 P {precision:6.1%} R {recall:6.1%} F1 {f1:6.1%} | "
              f"người >1 giọng {len(split_people)}/{len(split)} | giọng >1 người "
              f"{sum(len(people) > 1 for people in merged.values())}/{len(merged)} | F1 từng chương {per_chapter}")
        for person in split_people[:6]:
            counts = Counter(voice for gold_person, voice in points if gold_person == person)
            print(f"    tách {person}: " + ", ".join(f"{voice} {count}" for voice, count in counts.most_common(5)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
