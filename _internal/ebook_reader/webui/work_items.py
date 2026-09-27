"""Hộp "Việc cần anh" của Studio (docs/STUDIO_REVIEW.md), bước 1: CHỈ ĐỌC.

Dựng danh sách chỗ máy nghi ngờ từ SQLite của sách (mở chỉ đọc như mọi phần của webui), mỗi việc tự giải thích và xếp
theo LỢI TRÊN MỖI LẦN BẤM: `số câu bị ảnh hưởng x khả năng máy sai x độ chói tai`. Không việc nào chặn dây chuyền - máy
đã tự quyết và đang chạy tiếp; bước sau mới cho sửa (ghi đè áp ở ranh giới an toàn).

Độ tin cậy do LLM tự báo KHÔNG dùng để xếp: đo trên Tập 18, câu thoại trung bình 0,91 và chỉ 14/1.157 câu dưới 0,8 - nó
quá tự tin. Các tín hiệu ở đây là tín hiệu có cấu trúc, kiểm được bằng mắt.
"""
from __future__ import annotations

import re
import json
from collections import defaultdict
from contextlib import closing
from pathlib import Path
from typing import Any

from . import store
from .reviews import review_items, speaker_label

# Độ chói tai khi máy sai ở khía cạnh ấy (1 = người nghe nhận ra ngay: giọng sai người, sai giới).
SEVERITY = {
    "speaker": 1.0,
    "gender": 1.0,
    "vocative": 0.9,
    "alias": 0.8,
    "shared-voice": 0.6,
    "pronunciation": 0.5,
    "unnamed": 0.3,
    "audio": 0.9,
}
EXAMPLES = 3
LEADING = re.compile(r"^[\s\-–—“”\"'‘’«»]+")


def _is_named(speaker: str) -> bool:
    return bool(speaker) and speaker != "NARRATOR" and not speaker.startswith("NPC_LOCAL")


def _example(row: Any, names: dict[int, dict[str, Any]]) -> dict[str, Any]:
    chapter = names.get(int(row["chapter_id"]), {})
    return {
        "segmentId": int(row["id"]),
        "chapterId": int(row["chapter_id"]),
        "chapterTitle": chapter.get("full") or chapter.get("title") or "",
        "seq": int(row["seq"]),
        "text": str(row["text"]),
        "speaker": speaker_label(str(row["speaker"])),
    }


def _tokens(name: str) -> list[str]:
    return [token for token in re.split(r"[\s\-]+", name.upper()) if token]


def work_items(project_root: Path) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    with closing(store.connect(project_root)) as connection:
        names = store.chapter_names(connection)
        spoken = connection.execute(
            "SELECT id, stable_id, chapter_id, seq, text, speaker, kind, voice_profile_id, canonical_character_id FROM segments"
            " WHERE kind != 'narration' ORDER BY chapter_id, seq"
        ).fetchall()
        characters = {
            int(row["id"]): row
            for row in connection.execute("SELECT id, canonical_name, display_name, gender, locked FROM characters")
        }
        pronunciations = connection.execute(
            "SELECT surface, spoken_form, confidence, locked FROM pronunciations WHERE confidence < 0.9"
        ).fetchall() if "pronunciations" in store._table_names(connection) else []
        # Cách đọc một tên sai là sai ở MỌI câu có tên ấy: đếm số câu một lượt (phiên âm lưu theo từng từ - AGENTS.md).
        word_segments: dict[str, int] = defaultdict(int)
        if pronunciations:
            for (text,) in connection.execute("SELECT text FROM segments"):
                for word in set(re.findall(r"\w+", str(text))):
                    word_segments[word] += 1
    lines_by_speaker: dict[str, list[Any]] = defaultdict(list)
    for row in spoken:
        lines_by_speaker[str(row["speaker"])].append(row)

    # 0. Ai nói câu này: bộ chấm ứng viên (doubt.json, scripts/model_eval/quote_scorer/doubt_for_book.py) CHẮC về một người
    #    có tên khác nhãn LLM. Đây là tín hiệu xếp hạng tốt nhất đã đo (review_curve.py: duyệt 20% câu theo nó 74,8 -> 84,6%,
    #    theo tin cậy LLM tự báo chỉ 79,7% = ngẫu nhiên). Bộ chấm không đổi nhãn nào - chỉ chỉ chỗ cho người nghe lại.
    doubt_path = project_root / "doubt.json"
    if doubt_path.is_file():
        try:
            doubts = json.loads(doubt_path.read_text(encoding="utf-8")).get("segments", {})
        except (OSError, ValueError):
            doubts = {}
        by_stable = {str(row["stable_id"]): row for row in spoken}
        for stable_id, doubt in doubts.items():
            row = by_stable.get(stable_id)
            if row is None or str(row["speaker"]) != doubt.get("llm") or not doubt.get("disagree"):
                continue  # câu đổi nhãn sau lần chấm, hay bộ chấm đồng ý
            certainty = float(doubt.get("certainty") or 0)
            if certainty < 0.5:
                continue
            choice = speaker_label(str(doubt.get("choice") or ""))
            options = [speaker_label(str(name)) for name, _ in doubt.get("top", []) if name] + ["Người kể", "Vai phụ không tên"]
            items.append({
                "kind": "speaker",
                "key": f"speaker:{stable_id}",
                "title": f"Ai nói câu này - {speaker_label(str(row['speaker']))} hay {choice}?",
                "problem": f"Máy đọc (LLM) gán cho {speaker_label(str(row['speaker']))}; bộ chấm thứ hai chắc"
                           f" {round(certainty * 100)}% là {choice}.",
                "affected": 1,
                "doubt": round(certainty, 3),
                "options": list(dict.fromkeys(options)),
                "current": speaker_label(str(row["speaker"])),
                "examples": [_example(row, names)],
            })

    # 1. Chưa rõ nam hay nữ mà có lời: giọng sai giới là lỗi người nghe nhận ra ngay.
    for character_id, character in characters.items():
        if character["gender"] not in ("unknown", "") or character["locked"]:
            continue
        rows = [row for row in spoken if row["canonical_character_id"] == character_id]
        if not rows:
            continue
        items.append({
            "kind": "gender",
            "key": f"gender:{character['canonical_name']}",
            "title": f"{speaker_label(character['canonical_name'])} là nam hay nữ?",
            "problem": "Truyện chưa cho máy đủ dấu hiệu về giới của nhân vật này; máy đang đọc bằng giọng trung tính.",
            "affected": len(rows),
            "doubt": 0.5,
            "options": ["Nam", "Nữ", "Để máy quyết"],
            "current": "Chưa rõ",
            "examples": [_example(row, names) for row in rows[:EXAMPLES]],
        })

    # 2. Người nói lại chính là người được GỌI ở đầu câu ("Lucien, ..." mà nhãn là LUCIEN): gần như chắc là sai.
    for row in spoken:
        speaker = str(row["speaker"])
        if not _is_named(speaker):
            continue
        name = speaker_label(speaker)
        text = LEADING.sub("", str(row["text"]))
        if name and text.upper().startswith(name.upper() + ","):
            items.append({
                "kind": "vocative",
                "key": f"vocative:{row['id']}",
                "title": f"Câu mở đầu bằng lời gọi \"{name}\" lại gán cho chính {name}",
                "problem": "Tên đứng đầu câu và có dấu phẩy thường là người NGHE, không phải người nói.",
                "affected": 1,
                "doubt": 0.7,
                "options": ["Chọn người nói khác", "Giữ nguyên"],
                "current": name,
                "examples": [_example(row, names)],
            })

    # 3. Nghi là MỘT người mang hai tên (bí danh): tên này nằm trọn trong tên kia, cùng giới.
    named = {speaker: rows for speaker, rows in lines_by_speaker.items() if _is_named(speaker)}
    by_character = {str(character["canonical_name"]).upper(): character for character in characters.values()}
    speakers = sorted(named, key=lambda speaker: -len(named[speaker]))
    for index, longer in enumerate(speakers):
        long_tokens = _tokens(speaker_label(longer))
        for shorter in speakers[index + 1:]:
            short_tokens = _tokens(speaker_label(shorter))
            if not short_tokens or len(short_tokens) >= len(long_tokens):
                continue
            if short_tokens != long_tokens[-len(short_tokens):] and short_tokens != long_tokens[:len(short_tokens)]:
                continue
            a, b = by_character.get(longer.upper()), by_character.get(shorter.upper())
            if a is not None and b is not None and "unknown" not in (a["gender"], b["gender"]) and a["gender"] != b["gender"]:
                continue
            items.append({
                "kind": "alias",
                "key": f"alias:{longer}|{shorter}",
                "title": f"\"{speaker_label(shorter)}\" và \"{speaker_label(longer)}\" là một người?",
                "problem": "Hai tên này đang là hai nhân vật với hai giọng khác nhau, nhưng tên ngắn nằm trọn trong tên dài.",
                "affected": min(len(named[longer]), len(named[shorter])),
                "doubt": 0.6,
                "options": [f"Gộp vào {speaker_label(longer)}", "Hai người khác nhau"],
                "current": "Hai người khác nhau",
                "examples": [_example(row, names) for row in (named[shorter][:2] + named[longer][:1])],
            })

    # 4. Hai nhân vật có tên dùng CHUNG một giọng và cùng nói trong một chương: người nghe không phân biệt được.
    voice_chapters: dict[tuple[int, int], set[str]] = defaultdict(set)
    for row in spoken:
        if _is_named(str(row["speaker"])) and row["voice_profile_id"] is not None:
            voice_chapters[(int(row["voice_profile_id"]), int(row["chapter_id"]))].add(str(row["speaker"]))
    clashes: dict[frozenset[str], set[int]] = defaultdict(set)
    for (voice, chapter_id), people in voice_chapters.items():
        if len(people) > 1:
            clashes[frozenset(people)].add(chapter_id)
    for people, chapter_ids in clashes.items():
        rows = [row for row in spoken if str(row["speaker"]) in people and int(row["chapter_id"]) in chapter_ids]
        labels = sorted(speaker_label(person) for person in people)
        items.append({
            "kind": "shared-voice",
            "key": "shared-voice:" + "|".join(sorted(people)),
            "title": f"{', '.join(labels)} dùng chung một giọng trong cùng chương",
            "problem": f"Cùng nói trong {len(chapter_ids)} chương mà một giọng - nghe không biết ai đang nói.",
            "affected": len(rows),
            "doubt": 0.8,
            "options": [f"Đổi giọng {label}" for label in labels] + ["Giữ nguyên"],
            "current": "Chung giọng",
            "examples": [_example(row, names) for row in rows[:EXAMPLES]],
        })

    # 5. Người nói không tên (vai phụ cục bộ): có thể là một nhân vật có tên trong chương.
    for speaker, rows in lines_by_speaker.items():
        if not speaker.startswith("NPC_LOCAL"):
            continue
        items.append({
            "kind": "unnamed",
            "key": f"unnamed:{speaker}",
            "title": f"\"{speaker_label(speaker)}\" là ai?",
            "problem": "Máy để người này là vai phụ không tên (giọng riêng trong chương). Nếu thật ra là nhân vật có tên thì"
                       " nên dùng giọng của nhân vật ấy.",
            "affected": len(rows),
            "doubt": 0.4,
            "options": ["Là một nhân vật có tên", "Đúng là vai phụ"],
            "current": "Vai phụ không tên",
            "examples": [_example(row, names) for row in rows[:EXAMPLES]],
        })

    # 6. Cách đọc tên riêng máy chưa chắc.
    for row in pronunciations:
        occurrences = word_segments.get(str(row["surface"]), 0)
        if occurrences == 0:
            continue
        items.append({
            "kind": "pronunciation",
            "key": f"pronunciation:{row['surface']}",
            "title": f"Đọc \"{row['surface']}\" là \"{row['spoken_form']}\"?",
            "problem": f"Máy chỉ chắc {round(float(row['confidence']) * 100)}% về cách đọc tên này; tên có trong"
                       f" {occurrences} câu.",
            "affected": occurrences,
            "doubt": round(1 - float(row["confidence"]), 2),
            "options": ["Đúng rồi", "Đọc cách khác"],
            "current": str(row["spoken_form"]),
            "examples": [],
        })

    # 7. Bản thu lỗi (hàng chờ "Cần nghe lại"), gom theo chương.
    audio_by_chapter: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for entry in review_items(project_root):
        if entry.get("kind") in ("failed", "unverified", "name-low"):
            audio_by_chapter[int(entry["chapterId"])].append(entry)
    for chapter_id, entries in audio_by_chapter.items():
        items.append({
            "kind": "audio",
            "key": f"audio:{chapter_id}",
            "title": f"{len(entries)} câu thu âm cần nghe lại - {entries[0].get('chapterTitle', '')}",
            "problem": "Khâu tự kiểm tra không chắc các câu này (xem tab Cần nghe lại).",
            "affected": len(entries),
            "doubt": 0.5,
            "options": ["Nghe và chấm ở tab Cần nghe lại"],
            "current": "Chưa nghe",
            "examples": [],
        })

    for item in items:
        item["score"] = round(item["affected"] * item["doubt"] * SEVERITY[item["kind"]], 3)
    items.sort(key=lambda item: -item["score"])
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        counts[item["kind"]] += 1
    return {"items": items, "counts": dict(counts)}
