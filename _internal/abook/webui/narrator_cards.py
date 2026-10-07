"""Thẻ "người kể của đoạn khác" của hộp "Việc cần duyệt" (abook/narrator_sections.py là bộ phát hiện + nơi lưu quyết định).

Đề xuất tính từ chữ nguồn của chương và các câu đã chia (không model, không GPU) - có ngay sau khi chia câu, không cần chờ
phân tích, và KHÔNG chặn gì: chưa trả lời = không áp. Chỉ sách có người kể "tôi" (`voices.first_person_identity` hay
`first_person_chapters`) mới có thẻ; sách khác không bị đụng tới.

Quyết định ghi vào `narrator_sections.json` cạnh sổ dự án (không phải settings - settings khoá theo băm). Dây chuyền đọc lại ở
mỗi lô phân tích CHƯA chạy; lô đã chạy xong thì không phân tích lại (như `first_person_chapters`, chỉ đổi được khi làm lại sách).
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
from typing import Any

from .. import narrator_sections
from . import store

# Kết quả phát hiện theo (chương, tệp nguồn, người kể, số câu, cỡ câu, bỏ dòng ghi công): tính một chương mất vài chục ms, và
# hộp việc mở lại nhiều lần.
_CACHE: dict[tuple, list[dict[str, Any]]] = {}
_CACHE_MAX = 4000


def narrators(project_root: Path) -> tuple[str, dict[int, str]]:
    """(người kể cả cuốn, người kể theo chương) của sách - như analysis.OllamaBookAnalyzer đọc."""
    from ..analysis import FIRST_PERSON_PRONOUNS, first_person_chapters

    settings = store.read_settings(project_root)
    voices = settings.get("voices") if isinstance(settings.get("voices"), dict) else {}
    identity = str(voices.get("first_person_identity") or "").strip()
    return ("" if identity.casefold() in FIRST_PERSON_PRONOUNS else identity), first_person_chapters(settings)


def proposals(project_root: Path) -> list[dict[str, Any]]:
    """Mọi đoạn có vẻ không do người kể của sách kể: {chapter_id, chapter_index, narrator, from_seq, to_seq, r1, r3, words}."""
    identity, by_chapter = narrators(project_root)
    if not identity and not by_chapter:
        return []
    settings = store.read_settings(project_root)
    tts = settings.get("tts") if isinstance(settings.get("tts"), dict) else {}
    text = settings.get("text") if isinstance(settings.get("text"), dict) else {}
    max_chars = int(tts.get("max_segment_chars") or narrator_sections.MAX_CHARS)
    drop_credits = bool(text.get("drop_credit_lines"))
    found: list[dict[str, Any]] = []
    with closing(store.connect(project_root)) as connection:
        # Sổ tối thiểu (test, bản chụp cũ) có thể thiếu cột nguồn / gợi ý loại đoạn: không có gì để đề xuất.
        for table, needed in (("chapters", {"input_path", "chapter_index"}), ("segments", {"kind_hint", "seq", "text"})):
            if not needed <= {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}:
                return []
        chapters = connection.execute("SELECT id, chapter_index, input_path FROM chapters ORDER BY chapter_index").fetchall()
        for chapter in chapters:
            index = int(chapter["chapter_index"])
            narrator = by_chapter.get(index, identity)
            if not narrator or not chapter["input_path"]:
                continue
            rows = connection.execute(
                "SELECT seq, text, kind_hint FROM segments WHERE chapter_id=? ORDER BY seq", (int(chapter["id"]),)
            ).fetchall()
            if not rows:
                continue
            path = Path(str(chapter["input_path"]))
            try:
                stat = path.stat()
            except OSError:
                continue
            key = (str(project_root), index, stat.st_mtime_ns, stat.st_size, narrator, len(rows), max_chars, drop_credits)
            if key not in _CACHE:
                if len(_CACHE) > _CACHE_MAX:
                    _CACHE.clear()
                from ..io_utils import decode_text_bytes

                try:
                    raw = decode_text_bytes(path.read_bytes())
                except OSError:
                    continue
                _CACHE[key] = narrator_sections.detect(raw, rows, narrator, max_chars=max_chars, drop_credits=drop_credits)
            found += [{**item, "chapter_id": int(chapter["id"]), "chapter_index": index, "narrator": narrator}
                      for item in _CACHE[key]]
    return found


def decision_of(sections: dict[int, list[dict[str, Any]]], chapter_index: int, from_seq: int, to_seq: int) -> dict[str, Any] | None:
    for entry in sections.get(chapter_index, ()):
        if (entry["from_seq"], entry["to_seq"]) == (from_seq, to_seq):
            return entry
    return None


def progress(project_root: Path, chapter_id: int, from_seq: int, to_seq: int) -> tuple[int, int]:
    """(số câu của đoạn, số câu đã phân tích xong) - câu đã phân tích không bị phân tích lại khi người dùng đổi ý."""
    with closing(store.connect(project_root)) as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS total, COALESCE(SUM(status != 'pending'), 0) AS done FROM segments"
            " WHERE chapter_id=? AND seq BETWEEN ? AND ?", (chapter_id, from_seq, to_seq)).fetchone()
    return int(row["total"]), int(row["done"])


def applies_note(total: int, done: int) -> str:
    """Điều người dùng cần biết trước khi bấm: đoạn đã phân tích xong thì lựa chọn chỉ áp khi làm lại sách."""
    if not total or not done:
        return ""
    if done >= total:
        return "Chương này đã phân tích xong - đổi sẽ áp khi làm lại sách."
    return f"{done}/{total} câu của đoạn này đã phân tích xong - phần ấy chỉ đổi khi làm lại sách; phần còn lại áp ngay."


def decide(project_root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """Ghi quyết định của một đoạn (thân yêu cầu: chapterIndex, fromSeq, toSeq, và `action`: "accept" / "choose" kèm `narrator` /
    "keep" / "undo", hay `withdraw`: true). Trả về trạng thái đã ghi. ValueError khi đoạn không còn là một đề xuất của sách."""
    try:
        chapter_index, first, last = int(body["chapterIndex"]), int(body["fromSeq"]), int(body["toSeq"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Thiếu chương hoặc đoạn") from error
    # `withdraw`: cùng dạng "Hoàn tác" của mọi thẻ (decisions.undoAction) - thẻ hỏi lại như chưa bấm.
    action = "undo" if body.get("withdraw") else str(body.get("action") or "")
    if action not in ("accept", "choose", "keep", "undo"):
        raise ValueError("Lựa chọn không hợp lệ")
    if action != "undo" and not any((item["chapter_index"], item["from_seq"], item["to_seq"]) == (chapter_index, first, last)
                                    for item in proposals(project_root)):
        raise ValueError("Đoạn này không còn là một đề xuất (chữ nguồn đã khác?)")
    narrator = " ".join(str(body.get("narrator") or "").split())[:narrator_sections.MAX_NAME]
    if action == "choose":
        from ..character_registry import PRONOUNS, normalize_name

        if not narrator or normalize_name(narrator) in PRONOUNS:
            raise ValueError("Điền tên người kể (không phải đại từ như “tôi”)")
    if action == "undo":
        narrator_sections.forget(project_root, chapter_index, first, last)
        return {"action": "undo"}
    narrator_sections.decide(project_root, chapter_index, first, last, accepted=action != "keep",
                             narrator=narrator if action == "choose" else "", source="owner" if action == "choose" else "auto")
    return {"action": action, "narrator": narrator if action == "choose" else ""}
