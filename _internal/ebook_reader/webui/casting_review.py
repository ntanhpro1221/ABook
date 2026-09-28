"""Tab "Kịch bản" của Studio: duyệt phân vai từng câu (docs/STUDIO_REVIEW.md, mục 3 "Ai nói câu này").

Hộp "Việc cần anh" chỉ đưa ra chỗ máy nghi; tab này cho người nghe đọc CẢ chương như một kịch bản - câu nào của ai - và
đổi người nói của bất kỳ câu thoại hay nội tâm nào. Sửa bằng đúng đường ghi đè của thẻ "Ai nói câu này" (POST /speaker ->
overrides.json -> dây chuyền áp ở ranh giới chương, câu đã thu thì thu lại), nên không có đường ghi thứ hai, và mọi luật
của đường ấy vẫn đúng: chỉ gán cho người đã có giọng, câu đổi chữ thì yêu cầu tự rơi. Mỗi lần sửa cũng là một nhãn kiểu
gold cho vòng học (nguyên tắc 7).

Chỗ máy nghi dùng CHUNG tín hiệu với hộp việc (work_items.py): bộ chấm thứ hai bất đồng, hai câu liền nhau cùng người,
câu mở đầu bằng lời gọi chính người nói. SQLite mở chỉ đọc như mọi phần của webui.
"""
from __future__ import annotations

from collections import Counter
from contextlib import closing
from pathlib import Path
from typing import Any

from ..listener_overrides import (
    NARRATOR, NO_VOICE, NOT_SPEECH, SPEECH_KINDS, UNNAMED, read_overrides, speaker_requests, speaker_target,
)
from . import store
from .reviews import speaker_label
from .work_items import calls_themselves, confident_doubts, merged_turns

# Người có tên trong cả cuốn đưa vào ô "người khác": sách dài có hàng trăm vai, ô tìm lọc tại chỗ.
OTHERS = 300
# Gợi ý cho câu "liền nhau cùng người": người khác gần nhất vừa nói trước cặp ấy, trong chừng này câu.
LOOKBACK = 6
# Vì sao một yêu cầu đã ghi sẽ không được dây chuyền áp (câu đổi chữ thì yêu cầu tự rơi, không hiện).
REFUSED = {
    NO_VOICE: "Người này chưa có giọng trong sách - dây chuyền sẽ bỏ qua yêu cầu này.",
    NOT_SPEECH: "Câu này giờ là lời kể, không có người nói để đổi.",
}


def label(raw: str) -> str:
    if raw == NARRATOR:
        return "Người kể"
    if raw == UNNAMED or raw == "UNKNOWN" or raw.startswith("ANONYMOUS"):
        return "Vai phụ không tên"
    return speaker_label(raw)


def choice_value(raw: str) -> str:
    """Giá trị gửi cho POST /speaker để giữ đúng người đang nói câu ấy (xác nhận = một nhãn cho vòng học): nhóm vô danh
    mang nhãn UNKNOWN trong SQLite nhưng yêu cầu gọi nó là UNNAMED."""
    return UNNAMED if raw == "UNKNOWN" or raw.startswith("ANONYMOUS") else raw


def _is_person(raw: str) -> bool:
    return bool(raw) and raw != NARRATOR and raw != "UNKNOWN" and not raw.startswith("ANONYMOUS")


def _hints(connection: Any, project_root: Path, rows: list[Any], chapter_id: int | None) -> dict[str, dict[str, Any]]:
    """stable_id -> vì sao máy nghi người nói của câu ấy. Một câu nhiều tín hiệu thì giữ tín hiệu mạnh nhất: bộ chấm thứ hai
    (đo được) > hai câu liền nhau cùng người (38/42 sai) > lời gọi."""
    hints: dict[str, dict[str, Any]] = {}
    speech = [row for row in rows if str(row["kind"]) != "narration"]
    for row in speech:
        if calls_themselves(row):
            name = label(str(row["speaker"]))
            hints[str(row["stable_id"])] = {
                "kind": "vocative",
                "note": f"Câu mở đầu bằng lời gọi {name} - người được gọi thường là người nghe, không phải người nói.",
            }
    order = {str(row["stable_id"]): index for index, row in enumerate(speech)}
    for first, second in merged_turns(connection, chapter_id):
        name = label(str(second["speaker"]))
        hint: dict[str, Any] = {
            "kind": "turn",
            "note": f"Câu liền trước cũng của {name}, đoạn này không có lời dẫn - thường là người kia đáp lại.",
        }
        # Đối đáp đi xen kẽ: người khác gần nhất vừa nói trước cặp này là ứng viên tự nhiên nhất.
        start = order.get(str(first["stable_id"]))
        if start is not None:
            for row in reversed(speech[max(0, start - LOOKBACK):start]):
                other = str(row["speaker"])
                if _is_person(other) and other.casefold() != str(second["speaker"]).casefold():
                    hint["suggest"] = other
                    break
        hints[str(second["stable_id"])] = hint
    for row, doubt, certainty in confident_doubts(project_root, {str(row["stable_id"]): row for row in speech}):
        choice = str(doubt.get("choice") or "")
        hints[str(row["stable_id"])] = {
            "kind": "speaker",
            "note": f"Bộ chấm thứ hai chắc {round(certainty * 100)}% là {label(choice)}.",
            "suggest": choice,
        }
    return hints


def _wish(connection: Any, row: Any, wish: dict[str, str] | None) -> dict[str, Any] | None:
    """Yêu cầu của người nghe cho câu này và nó đang ở đâu: chờ ranh giới chương, đã áp, hay dây chuyền sẽ từ chối (hỏi
    bằng đúng phép dây chuyền dùng - `speaker_target`). Câu đã đổi chữ thì yêu cầu tự rơi: không có gì để hiện."""
    if wish is None or wish["text_sha256"] != str(row["text_sha256"] or ""):
        return None
    value = wish["speaker"]
    view: dict[str, Any] = {"value": value, "label": label(value)}
    target, problem = speaker_target(
        connection, stable_id=str(row["stable_id"]), text_sha256=wish["text_sha256"], speaker=value
    )
    if target is None:
        return {**view, "state": "refused", "reason": REFUSED.get(str(problem), "Dây chuyền sẽ không áp được yêu cầu này.")}
    return {**view, "state": "applied" if str(target["speaker"]) == str(row["speaker"]) else "pending"}


def casting_chapters(project_root: Path) -> dict[str, Any]:
    """Mục lục của tab: mỗi chương có bao nhiêu câu thoại, bao nhiêu chỗ máy nghi, bao nhiêu câu người nghe đã quyết."""
    with closing(store.connect(project_root)) as connection:
        names = store.chapter_names(connection)
        counts = {
            int(row["chapter_id"]): int(row["lines"])
            for row in connection.execute("SELECT chapter_id, COUNT(*) AS lines FROM segments GROUP BY chapter_id")
        }
        speech = connection.execute(
            "SELECT id, stable_id, chapter_id, seq, text, text_sha256, speaker, kind FROM segments"
            " WHERE kind != 'narration' ORDER BY chapter_id, seq"
        ).fetchall()
        hints = _hints(connection, project_root, speech, None)
        cast_ready = connection.execute(
            "SELECT 1 FROM segments WHERE voice_profile_id IS NOT NULL LIMIT 1"
        ).fetchone() is not None
    wishes = {entry["stable_id"] for entry in speaker_requests(read_overrides(project_root))}
    per_chapter = {chapter_id: {"speech": 0, "hints": 0, "decided": 0} for chapter_id in counts}
    for row in speech:
        entry = per_chapter[int(row["chapter_id"])]
        entry["speech"] += 1
        entry["hints"] += str(row["stable_id"]) in hints
        entry["decided"] += str(row["stable_id"]) in wishes
    chapters = [
        {
            "chapterId": chapter_id,
            "index": int(names.get(chapter_id, {}).get("index", chapter_id)),
            "title": str(names.get(chapter_id, {}).get("full") or ""),
            "lines": counts[chapter_id],
            **per_chapter[chapter_id],
        }
        for chapter_id in counts
    ]
    chapters.sort(key=lambda chapter: (chapter["index"], chapter["chapterId"]))
    return {"castReady": cast_ready, "chapters": chapters}


def casting_chapter(project_root: Path, chapter_id: int) -> dict[str, Any] | None:
    """Một chương như kịch bản: mọi câu theo thứ tự, người nói, gợi ý máy nghi, yêu cầu của người nghe; dàn người nói của
    chương (chọn nhanh) và những người có tên khác trong cuốn (ô tìm)."""
    with closing(store.connect(project_root)) as connection:
        if connection.execute("SELECT 1 FROM chapters WHERE id = ?", (chapter_id,)).fetchone() is None:
            return None
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(segments)")}
        extra = [column for column in ("paragraph_index", "wav_path") if column in columns]
        rows = connection.execute(
            "SELECT id, stable_id, chapter_id, seq, text, text_sha256, speaker, kind"
            + "".join(f", {column}" for column in extra)
            + " FROM segments WHERE chapter_id = ? ORDER BY seq",
            (chapter_id,),
        ).fetchall()
        hints = _hints(connection, project_root, rows, chapter_id)
        wishes = {entry["stable_id"]: entry for entry in speaker_requests(read_overrides(project_root))}
        decided = {str(row["stable_id"]): _wish(connection, row, wishes.get(str(row["stable_id"]))) for row in rows}
        # Chỉ người ĐÃ CÓ giọng mới gán được (speaker_target): trước bước phân vai thì chưa ai có.
        voiced = Counter(
            str(row["speaker"])
            for row in connection.execute(
                "SELECT speaker FROM segments WHERE kind != 'narration' AND voice_profile_id IS NOT NULL"
            )
        )
        order = [
            int(row["chapter_id"])
            for row in connection.execute(
                "SELECT DISTINCT s.chapter_id FROM segments s JOIN chapters c ON c.id = s.chapter_id"
                " ORDER BY c.chapter_index, s.chapter_id"
            )
        ]
        chapter_name = store.chapter_names(connection).get(chapter_id, {})
    here = Counter(str(row["speaker"]) for row in rows if str(row["kind"]) in SPEECH_KINDS)
    cast = [
        {"value": raw, "label": label(raw), "lines": count}
        for raw, count in sorted(here.items(), key=lambda item: (-item[1], label(item[0]).casefold()))
        if _is_person(raw) and raw in voiced
    ]
    # Vai phụ cục bộ của chương khác không phải người của cảnh này: ô tìm chỉ có người có tên.
    others = [
        {"value": raw, "label": label(raw), "lines": count}
        for raw, count in sorted(voiced.items(), key=lambda item: (-item[1], label(item[0]).casefold()))
        if _is_person(raw) and not raw.startswith("NPC_LOCAL") and raw not in here
    ][:OTHERS]
    voices = store.read_settings(project_root).get("voices")
    first_person = str((voices if isinstance(voices, dict) else {}).get("first_person_identity") or "")
    position = order.index(chapter_id) if chapter_id in order else -1
    lines = []
    for row in rows:
        raw = str(row["speaker"] or "")
        kind = str(row["kind"] or "narration")
        stable_id = str(row["stable_id"])
        paragraph = row["paragraph_index"] if "paragraph_index" in extra else None
        lines.append({
            "segmentId": int(row["id"]),
            "stableId": stable_id,
            "textSha256": str(row["text_sha256"] or ""),
            "seq": int(row["seq"]),
            "paragraph": int(paragraph) if paragraph is not None else None,
            "text": str(row["text"]),
            "kind": kind,
            "speaker": raw,
            "current": choice_value(raw),
            "label": label(raw),
            "editable": kind in SPEECH_KINDS and bool(row["text_sha256"]),
            "hasAudio": bool(row["wav_path"]) if "wav_path" in extra else False,
            "hint": hints.get(stable_id),
            "wish": decided.get(stable_id),
        })
    return {
        "chapterId": chapter_id,
        "index": int(chapter_name.get("index", chapter_id)),
        "title": str(chapter_name.get("full") or ""),
        "previous": order[position - 1] if position > 0 else None,
        "next": order[position + 1] if 0 <= position < len(order) - 1 else None,
        "castReady": bool(voiced),
        "firstPerson": {"value": first_person, "label": label(first_person)} if first_person else None,
        "cast": cast,
        "others": others,
        "lines": lines,
    }
