"""Tab "Kịch bản" của Studio: duyệt phân vai từng câu (docs/STUDIO_REVIEW.md, mục 3 "Ai nói câu này").

Hộp "Việc cần duyệt" chỉ đưa ra chỗ máy nghi; tab này cho người nghe đọc CẢ chương như một kịch bản - câu nào của ai - và
đổi người nói của bất kỳ câu thoại hay nội tâm nào. Sửa bằng đúng đường ghi đè của thẻ "Ai nói câu này" (POST /speaker ->
overrides.json -> dây chuyền áp ở ranh giới chương, câu đã thu thì thu lại), nên không có đường ghi thứ hai, và mọi luật
của đường ấy vẫn đúng: chỉ gán cho người đã có giọng, câu đổi chữ thì yêu cầu tự rơi. Mỗi lần sửa cũng là một nhãn kiểu
gold cho vòng học (nguyên tắc 7).

Chỗ máy nghi dùng CHUNG tín hiệu với hộp việc (work_items.py, gọi lại đúng hàm của nó): hai câu liền nhau cùng người, câu
mở đầu bằng lời gọi chính người nói, xưng hô lệch khỏi người đang được gán (address_cues), và câu model kém chắc ai nói
(speaker_logprobs: p_first thấp). SQLite mở chỉ đọc như mọi phần của webui.
"""
from __future__ import annotations

from collections import Counter
from contextlib import closing
from pathlib import Path
from typing import Any

from ..listener_overrides import (
    NARRATOR, OVERRIDES_FILE, NO_VOICE, NOT_SPEECH, SPEECH_KINDS, UNNAMED, line_requests, line_target, read_overrides, retake_requests,
    speaker_requests, speaker_target,
)
from . import store
from .reviews import speaker_label
from .address_cues import _same_person, address_doubts
from .work_items import first_person_lookup, merged_turns, self_addressed, unsure_speaker_lines
from .. import speaker_logprobs

# Người có tên trong cả cuốn đưa vào ô "người khác": sách dài có hàng trăm vai, ô tìm lọc tại chỗ.
OTHERS = 300
# Gợi ý cho câu "liền nhau cùng người": người khác gần nhất vừa nói trước cặp ấy, trong chừng này câu.
LOOKBACK = 6
# Vì sao một yêu cầu đã ghi sẽ không được dây chuyền áp (câu đổi chữ thì yêu cầu tự rơi, không hiện).
REFUSED = {
    NO_VOICE: "Người này chưa có giọng trong sách - dây chuyền sẽ bỏ qua yêu cầu này.",
    NOT_SPEECH: "Câu này giờ là lời kể, không có người nói để đổi.",
}


def display_names(connection: Any) -> dict[str, str]:
    """canonical_name -> display_name của sổ nhân vật: tên như tab Nhân vật viết ("Người Khách"), không phải khoá sổ ("người khách")."""
    try:
        return {str(row["canonical_name"]): str(row["display_name"] or "")
                for row in connection.execute("SELECT canonical_name, display_name FROM characters")}
    except Exception:  # sách chưa qua bước phân tích nào: chưa có bảng nhân vật
        return {}


def label(raw: str, display: dict[str, str] | None = None) -> str:
    """Tên người nói cho người đọc. `display` (display_names): cùng cách viết với tab Nhân vật - hai tab gọi một người bằng hai
    kiểu chữ hoa là lỗi (soát UX a8, mục 20)."""
    named = display.get(raw) if display and _is_person(raw) and not raw.startswith("NPC_LOCAL") else None
    return speaker_label(named or raw)


def choice_value(raw: str) -> str:
    """Giá trị gửi cho POST /speaker để giữ đúng người đang nói câu ấy (xác nhận = một nhãn cho vòng học): nhóm vô danh
    mang nhãn UNKNOWN trong SQLite nhưng yêu cầu gọi nó là UNNAMED."""
    return UNNAMED if raw == "UNKNOWN" or raw.startswith("ANONYMOUS") else raw


def _is_person(raw: str) -> bool:
    return bool(raw) and raw != NARRATOR and raw != "UNKNOWN" and not raw.startswith("ANONYMOUS")


def _hints(connection: Any, rows: list[Any], chapter_id: int | None,
           display: dict[str, str] | None = None, project_root: Path | None = None) -> dict[str, dict[str, Any]]:
    """stable_id -> vì sao máy nghi người nói của câu ấy. Một câu nhiều tín hiệu thì giữ tín hiệu mạnh nhất: hai câu liền
    nhau cùng người (38/42 sai) > lời gọi > xưng hô lệch > model kém chắc. `project_root`: cần cho hai tín hiệu cuối (đọc người
    kể "tôi" của sách và số đo logprob); không có thì chỉ hai tín hiệu đầu."""
    hints: dict[str, dict[str, Any]] = {}
    speech = [row for row in rows if str(row["kind"]) != "narration"]
    if project_root is not None:
        _weak_hints(connection, speech, chapter_id, display, project_root, hints)
    calling = self_addressed(connection, chapter_id)
    for row in speech:
        if int(row["id"]) in calling:
            name = label(str(row["speaker"]), display)
            hints[str(row["stable_id"])] = {
                "kind": "vocative",
                "note": f"Câu này gọi tên {name} - người được gọi thường là người nghe, không phải người nói.",
            }
    order = {str(row["stable_id"]): index for index, row in enumerate(speech)}
    for first, second in merged_turns(connection, chapter_id):
        name = label(str(second["speaker"]), display)
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
    return hints


def _weak_hints(connection: Any, speech: list[Any], chapter_id: int | None, display: dict[str, str] | None,
                project_root: Path, hints: dict[str, dict[str, Any]]) -> None:
    """Hai tín hiệu của hộp việc mà tab này từng thiếu (soát UX a13 #2): xưng hô (thẻ 0b) và p_first thấp (thẻ 0c2) - cùng hàm,
    cùng ngưỡng, cùng ngân sách "20% câu kém chắc nhất của cả cuốn". Xưng hô chỉ xét trên các câu của `speech` (một chương khi
    mở chương; hồ sơ xưng hô vốn dựng theo chương)."""
    chapter_index = {int(row[0]): int(row[1] or 0) for row in connection.execute("SELECT id, chapter_index FROM chapters")}
    book_narrator, chapter_narrators, narrator_of, by_section = first_person_lookup(project_root, chapter_index)
    carded: set[str] = set()
    for row, suggested, _cue in address_doubts(speech, narrator_of, by_section) if (book_narrator or chapter_narrators) else []:
        stable_id = str(row["stable_id"])
        carded.add(stable_id)
        hints[stable_id] = {
            "kind": "address",
            "note": f"Xưng hô trong câu giống {label(suggested, display)} hơn {label(str(row['speaker']), display)}.",
            "suggest": suggested,
        }
    confidences = speaker_logprobs.read_confidences(project_root)
    if not confidences:
        return
    # Ngân sách tính trên cả cuốn: mở một chương thì vẫn hỏi cùng những câu như hộp việc.
    spoken = speech if chapter_id is None else connection.execute(
        "SELECT id, stable_id, chapter_id, seq, speaker, kind FROM segments WHERE kind != 'narration' ORDER BY chapter_id, seq"
    ).fetchall()
    unsure, budget = unsure_speaker_lines(spoken, confidences, carded)
    shown = {str(row["stable_id"]) for row in speech}
    for row, found in unsure[:budget]:
        stable_id = str(row["stable_id"])
        if stable_id in shown and stable_id not in hints:
            hints[stable_id] = {
                "kind": "unsure",
                "note": f"Máy chỉ chắc ~{round(float(found['p_first']) * 100)}% câu này là của {label(str(row['speaker']), display)}.",
            }


def _wish(connection: Any, row: Any, wish: dict[str, str] | None, as_kind: str = "",
          display: dict[str, str] | None = None) -> dict[str, Any] | None:
    """Yêu cầu của người nghe cho câu này và nó đang ở đâu: chờ ranh giới chương, đã áp, hay dây chuyền sẽ từ chối (hỏi
    bằng đúng phép dây chuyền dùng - `speaker_target`). Câu đã đổi chữ thì yêu cầu tự rơi: không có gì để hiện."""
    if wish is None or wish["text_sha256"] != str(row["text_sha256"] or ""):
        return None
    value = wish["speaker"]
    view: dict[str, Any] = {"value": value, "label": label(value, display)}
    # `as_kind`: câu đang chờ đổi từ lời kể thành lời thoại (yêu cầu `lines`) - xét như dây chuyền sẽ xét sau bước ấy.
    target, problem = speaker_target(
        connection, stable_id=str(row["stable_id"]), text_sha256=wish["text_sha256"], speaker=value, as_kind=as_kind
    )
    if target is None:
        return {**view, "state": "refused", "reason": REFUSED.get(str(problem), "Dây chuyền sẽ không áp được yêu cầu này.")}
    return {**view, "state": "applied" if str(target["speaker"]) == str(row["speaker"]) else "pending"}


def _value(row: Any, key: str) -> Any:
    """Cột có thể chưa có ở sách cũ (chưa qua lượt nâng cấp của dây chuyền): None."""
    return row[key] if key in row.keys() else None


def _line_wish(connection: Any, row: Any, wish: dict[str, Any] | None) -> dict[str, Any] | None:
    """Yêu cầu sửa cách đọc câu này và nó đang ở đâu (chờ / đã áp / không áp được) - hỏi bằng `line_target`."""
    if wish is None or wish["text_sha256"] != str(row["text_sha256"] or ""):
        return None
    view = {"kind": wish["kind"], "emotion": wish["emotion"], "intensity": wish["intensity"]}
    if wish.get("spoken") is not None:
        view["spoken"] = wish["spoken"]
    target, problem = line_target(connection, stable_id=str(row["stable_id"]), text_sha256=wish["text_sha256"],
                                  kind=wish["kind"], emotion=wish["emotion"], intensity=wish["intensity"],
                                  spoken=wish.get("spoken"))
    if target is None:
        return {**view, "state": "refused", "reason": REFUSED.get(str(problem), "Dây chuyền sẽ không áp được yêu cầu này.")}
    applied = (str(row["kind"]) == target["kind"] and str(row["emotion"] or "neutral") == target["emotion"]
               and int(row["intensity"] or 0) == target["intensity"]
               and (_value(row, "listener_text") or None) == target["listener_text"])
    return {**view, "state": "applied" if applied else "pending"}


def _retake(row: Any, request: dict[str, Any] | None) -> str | None:
    """Câu đã xin thu lại mà dây chuyền chưa thu ("pending"): cùng phép thử `apply_listener_retake` - yêu cầu phải mới hơn lần thu
    lại theo yêu cầu gần nhất của câu, và chữ câu không đổi từ lúc xin. Sách chưa nâng cấp (không có cột) coi như chưa thu lần nào."""
    if request is None or request["text_sha256"] != str(row["text_sha256"] or ""):
        return None
    return "pending" if float(_value(row, "listener_retake_at") or 0) < request["requested_at"] else None


def casting_stamp(project_root: Path) -> int:
    """Lần ghi yêu cầu cuối của người nghe (mốc sửa của overrides.json; 0 = chưa ai sửa gì). Giao diện hỏi nhẹ mỗi vài giây: đổi nghĩa là
    một cửa sổ khác vừa sửa, nên chương đang xem phải tải lại (soát UX a23 B19) - rẻ hơn nhiều so với tải lại cả chương để so."""
    try:
        return (Path(project_root) / OVERRIDES_FILE).stat().st_mtime_ns
    except OSError:
        return 0


def casting_chapters(project_root: Path) -> dict[str, Any]:
    """Mục lục của tab: mỗi chương có bao nhiêu câu thoại, bao nhiêu chỗ máy nghi, bao nhiêu câu người nghe đã quyết."""
    with closing(store.connect(project_root)) as connection:
        names = store.chapter_names(connection, project_root)
        counts = {
            int(row["chapter_id"]): int(row["lines"])
            for row in connection.execute("SELECT chapter_id, COUNT(*) AS lines FROM segments GROUP BY chapter_id")
        }
        speech = connection.execute(
            "SELECT id, stable_id, chapter_id, seq, text, text_sha256, speaker, kind FROM segments"
            " WHERE kind != 'narration' ORDER BY chapter_id, seq"
        ).fetchall()
        hints = _hints(connection, speech, None, display_names(connection), project_root)
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
        extra = [column for column in ("paragraph_index", "wav_path", "emotion", "intensity", "listener_text", "listener_retake_at")
                 if column in columns]
        rows = connection.execute(
            "SELECT id, stable_id, chapter_id, seq, text, text_sha256, speaker, kind"
            + "".join(f", {column}" for column in extra)
            + " FROM segments WHERE chapter_id = ? ORDER BY seq",
            (chapter_id,),
        ).fetchall()
        display = display_names(connection)
        hints = _hints(connection, rows, chapter_id, display, project_root)
        overrides = read_overrides(project_root)
        wishes = {entry["stable_id"]: entry for entry in speaker_requests(overrides)}
        line_wishes = {entry["stable_id"]: entry for entry in line_requests(overrides)}
        retakes = {entry["stable_id"]: entry for entry in retake_requests(overrides)}
        decided = {
            str(row["stable_id"]): _wish(
                connection, row, wishes.get(str(row["stable_id"])),
                as_kind=str((line_wishes.get(str(row["stable_id"])) or {}).get("kind") or ""), display=display,
            )
            for row in rows
        }
        delivery = (
            {str(row["stable_id"]): _line_wish(connection, row, line_wishes.get(str(row["stable_id"]))) for row in rows}
            if "emotion" in extra else {}
        )
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
        chapter_name = store.chapter_names(connection, project_root).get(chapter_id, {})
    here = Counter(str(row["speaker"]) for row in rows if str(row["kind"]) in SPEECH_KINDS)
    cast = [
        {"value": raw, "label": label(raw, display), "lines": count}
        for raw, count in sorted(here.items(), key=lambda item: (-item[1], label(item[0], display).casefold()))
        if _is_person(raw) and raw in voiced
    ]
    # Vai phụ cục bộ của chương khác không phải người của cảnh này: ô tìm chỉ có người có tên.
    others = [
        {"value": raw, "label": label(raw, display), "lines": count}
        for raw, count in sorted(voiced.items(), key=lambda item: (-item[1], label(item[0], display).casefold()))
        if _is_person(raw) and not raw.startswith("NPC_LOCAL") and raw not in here
    ][:OTHERS]
    voices = store.read_settings(project_root).get("voices")
    voices = voices if isinstance(voices, dict) else {}
    first_person = str(voices.get("first_person_identity") or "")
    # Người kể "tôi" CỦA CHƯƠNG NÀY: first_person_chapters (theo số chương) đè người kể cả cuốn, rỗng = chương kể ngôi ba. Chip
    # của người ấy trong chương: tên người dùng gõ ("Krai") có thể khác cách sổ nhân vật viết ("KRAI ANDREY"). Máy gán nhầm
    # câu của người khác cho người kể nhiều nhất - 8B-v5 trên bộ LN: 97/276 câu gán cho người kể là sai (ANALYSIS_RESEARCH).
    by_chapter = voices.get("first_person_chapters") if isinstance(voices.get("first_person_chapters"), dict) else {}
    index_key = str(chapter_name.get("index", chapter_id))
    if index_key in by_chapter:
        first_person = str(by_chapter[index_key] or "").strip()
    narrator_chip = next((person["value"] for person in cast if _same_person(person["value"], first_person)), None)
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
            "label": label(raw, display),
            "editable": kind in SPEECH_KINDS and bool(row["text_sha256"]),
            "hasAudio": bool(row["wav_path"]) if "wav_path" in extra else False,
            "hint": hints.get(stable_id),
            "wish": decided.get(stable_id),
            "emotion": str(row["emotion"] or "neutral") if "emotion" in extra else None,
            "intensity": int(row["intensity"] or 0) if "intensity" in extra else None,
            "lineWish": delivery.get(stable_id),
            # Chữ người nghe sửa đang được đọc thay câu gốc (đã áp); None = đọc đúng chữ sách.
            "spoken": _value(row, "listener_text") or None,
            # Người nghe đã xin thu lại câu này, chờ dây chuyền thu ("pending"); None = không có yêu cầu nào đang chờ.
            "retake": _retake(row, retakes.get(stable_id)),
        })
    return {
        "chapterId": chapter_id,
        "index": int(chapter_name.get("index", chapter_id)),
        "title": str(chapter_name.get("full") or ""),
        "previous": order[position - 1] if position > 0 else None,
        "next": order[position + 1] if 0 <= position < len(order) - 1 else None,
        "castReady": bool(voiced),
        "firstPerson": {"value": first_person, "label": label(first_person, display), "chip": narrator_chip} if first_person else None,
        "cast": cast,
        "others": others,
        "lines": lines,
    }
