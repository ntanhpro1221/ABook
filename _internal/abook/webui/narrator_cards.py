"""Thẻ "người kể của đoạn khác" của hộp "Việc cần duyệt" (abook/narrator_sections.py là bộ phát hiện + nơi lưu quyết định).

Đề xuất tính từ chữ nguồn của chương và các câu đã chia (không model, không GPU) - có ngay sau khi chia câu, không cần chờ
phân tích, và KHÔNG chặn gì: chưa trả lời = không áp. Chỉ sách có người kể "tôi" (`voices.first_person_identity` hay
`first_person_chapters`) mới có thẻ; sách khác không bị đụng tới.

Quyết định ghi vào `narrator_sections.json` cạnh sổ dự án (không phải settings - settings khoá theo băm). Dây chuyền đọc lại ở
mỗi lô phân tích CHƯA chạy; lô đã chạy xong thì không phân tích lại (như `first_person_chapters`, chỉ đổi được khi làm lại sách).
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from contextlib import closing
from pathlib import Path
from typing import Any

from .. import narrator_sections
from . import store

# Kết quả phát hiện theo (chương, tệp nguồn, người kể, số câu, cỡ câu, bỏ dòng ghi công): tính một chương mất vài chục ms, và
# hộp việc mở lại nhiều lần.
_CACHE: dict[tuple, list[dict[str, Any]]] = {}
_CACHE_MAX = 4000
# Đại từ người kể đếm trên chữ nguồn từng chương, theo (tệp, mtime, cỡ): cửa sổ của mỗi chương cộng số đếm của các chương quanh nó.
_COUNTS: dict[tuple, Counter[str]] = {}
# Cửa sổ đại từ: chương đang xét và tối đa ngần này chương mỗi bên cùng người kể (DCHECK_12-10 phụ lục 04:1x: không tính cả cuốn -
# cuốn thật có thể xưng "tôi" ở đa số chương mà vài chương liền nhau do người xưng "ta" kể).
PRONOUN_WINDOW = 2


def narrators(project_root: Path) -> tuple[str, dict[int, str]]:
    """(người kể cả cuốn, người kể theo chương) của sách - như analysis.OllamaBookAnalyzer đọc."""
    from ..analysis import FIRST_PERSON_PRONOUNS, first_person_chapters

    settings = store.read_settings(project_root)
    voices = settings.get("voices") if isinstance(settings.get("voices"), dict) else {}
    identity = str(voices.get("first_person_identity") or "").strip()
    return ("" if identity.casefold() in FIRST_PERSON_PRONOUNS else identity), first_person_chapters(settings)


def known_name(project_root: Path, connection: Any, name: str) -> str:
    """Tên trong dự án của người mà một dòng tiêu đề góc nhìn gọi tới: bí danh đã xác nhận (aliases.json), tên trong sổ nhân vật
    (tên gốc, tên hiển thị, bí danh) - đủ tên, hay một chữ của đúng MỘT tên trong sổ ("Saito" -> "SAITO AYANE"). Không khớp thì
    giữ nguyên chữ của tiêu đề."""
    from .. import aliases

    key = aliases.key(name)
    person = aliases.load(project_root).get(key)
    if person:
        return person
    tables = store._table_names(connection)
    known: list[tuple[str, str]] = []  # (cách viết, tên gốc)
    if "characters" in tables:
        for row in connection.execute("SELECT canonical_name, display_name FROM characters"):
            known += [(str(row["canonical_name"] or ""), str(row["canonical_name"] or "")),
                      (str(row["display_name"] or ""), str(row["canonical_name"] or ""))]
        if "character_aliases" in tables:
            known += [(str(row[1] or ""), str(row[0] or "")) for row in connection.execute(
                "SELECT c.canonical_name, a.alias FROM character_aliases a JOIN characters c ON c.id = a.character_id")]
    known = [(written, canonical) for written, canonical in known if written.strip() and canonical.strip()]
    exact = {canonical for written, canonical in known if aliases.key(written) == key}
    if len(exact) == 1:
        return exact.pop()
    if len(key.split()) == 1:
        partial = {canonical for written, canonical in known if key in aliases.key(written).split()}
        if len(partial) == 1:
            return partial.pop()
    return name


def proposals(project_root: Path) -> list[dict[str, Any]]:
    """Mọi đoạn có vẻ không do người kể của sách kể: {chapter_id, chapter_index, narrator, from_seq, to_seq, r1, r3, words}; đoạn
    mở bằng dòng tiêu đề góc nhìn có thêm `heading` (dòng ấy) và `suggested` (người kể nó gọi, theo tên trong dự án; "" = ngôi
    ba). Chỉ sách có người kể "tôi": dây chuyền (analysis._bind_narrator_sections) chỉ đọc quyết định ở những sách ấy, nên ở
    sách ngôi ba một lần nhận sẽ không đổi được gì."""
    identity, by_chapter = narrators(project_root)
    if not identity and not by_chapter:
        return []
    settings = store.read_settings(project_root)
    tts = settings.get("tts") if isinstance(settings.get("tts"), dict) else {}
    text = settings.get("text") if isinstance(settings.get("text"), dict) else {}
    max_chars = int(tts.get("max_segment_chars") or narrator_sections.MAX_CHARS)
    drop_credits = bool(text.get("drop_credit_lines"))
    drop_tail_credits = bool(text.get("drop_tail_credit_lines"))
    found: list[dict[str, Any]] = []
    with closing(store.connect(project_root)) as connection:
        # Sổ tối thiểu (test, bản chụp cũ) có thể thiếu cột nguồn / gợi ý loại đoạn: không có gì để đề xuất.
        for table, needed in (("chapters", {"input_path", "chapter_index"}), ("segments", {"kind_hint", "seq", "text"})):
            if not needed <= {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}:
                return []
        chapters = connection.execute("SELECT id, chapter_index, input_path FROM chapters ORDER BY chapter_index").fetchall()
        tellers = [by_chapter.get(int(chapter["chapter_index"]), identity) for chapter in chapters]
        for position, chapter in enumerate(chapters):
            index = int(chapter["chapter_index"])
            # Chương kể ngôi ba ("" theo chương) vẫn được xét: D im ở đó, nhưng dòng "Góc nhìn của X" vẫn là một đề xuất.
            narrator = tellers[position]
            if not chapter["input_path"]:
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
            pron = narrator_sections.PRON
            if narrator:
                window: Counter[str] = Counter()
                for other in range(max(0, position - PRONOUN_WINDOW), min(len(chapters), position + PRONOUN_WINDOW + 1)):
                    if tellers[other] == narrator and chapters[other]["input_path"]:
                        window.update(_pronoun_counts(Path(str(chapters[other]["input_path"]))))
                pron = narrator_sections.pronoun_pattern(window)
            key = (str(project_root), index, stat.st_mtime_ns, stat.st_size, narrator, len(rows), max_chars, drop_credits, drop_tail_credits,
                   pron.pattern)
            if key not in _CACHE:
                if len(_CACHE) > _CACHE_MAX:
                    _CACHE.clear()
                raw = _read(path)
                if raw is None:
                    continue
                _CACHE[key] = narrator_sections.detect(raw, rows, narrator, max_chars=max_chars, drop_credits=drop_credits,
                                                         drop_tail_credits=drop_tail_credits, pron=pron)
            for item in _CACHE[key]:
                if "heading" in item:
                    suggested = known_name(project_root, connection, item["suggested"]) if item["suggested"] else ""
                    if narrator_sections.same_narrator(suggested, narrator):
                        continue  # tên trong sổ hoá ra là người kể của sách
                    item = {**item, "suggested": suggested}
                found.append({**item, "chapter_id": int(chapter["id"]), "chapter_index": index, "narrator": narrator})
    return found


def _read(path: Path) -> str | None:
    from ..io_utils import decode_text_bytes

    try:
        return decode_text_bytes(path.read_bytes())
    except OSError:
        return None


def _pronoun_counts(path: Path) -> Counter[str]:
    """Đại từ người kể trên chữ nguồn một chương (narrator_sections.pronoun_counts), nhớ theo tệp; tệp không đọc được = không đếm."""
    try:
        stat = path.stat()
    except OSError:
        return Counter()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if key not in _COUNTS:
        if len(_COUNTS) > _CACHE_MAX:
            _COUNTS.clear()
        raw = _read(path)
        _COUNTS[key] = narrator_sections.pronoun_counts(raw) if raw is not None else Counter()
    return _COUNTS[key]


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
        return "Chương đã phân tích chỉ nhận thay đổi khi bạn tạo lại cuốn từ file truyện."
    return (f"{done}/{total} câu đã phân tích chỉ đổi khi phân tích lại; phần còn lại áp ngay.")


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
    proposal = None if action == "undo" else next(
        (item for item in proposals(project_root) if (item["chapter_index"], item["from_seq"], item["to_seq"]) == (chapter_index, first, last)),
        None)
    if action != "undo" and proposal is None:
        raise ValueError("Đoạn này không còn là một đề xuất (chữ nguồn đã khác?)")
    narrator = " ".join(str(body.get("narrator") or "").split())[:narrator_sections.MAX_NAME]
    if action == "accept" and proposal is not None and "heading" in proposal:
        # Nhận đề xuất của dòng tiêu đề góc nhìn: người kể là người dòng ấy gọi (máy đề xuất -> source "auto").
        narrator_sections.decide(project_root, chapter_index, first, last, accepted=True, narrator=proposal["suggested"], source="auto")
        return {"action": action, "narrator": proposal["suggested"]}
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


# Tên riêng gợi ý cho "Người kể là ai khác…": chữ viết hoa đứng GIỮA câu trong đoạn (chưa có sổ nhân vật thì đây là chỗ duy nhất
# thấy được ai có mặt), nối liền nếu viết hoa liên tiếp ("Thiên Biến"). Tối đa ba chữ một tên.
SUGGEST_NAMES = 4
_WORD = re.compile(r"[^\W\d_]+")


def section_names(texts: list[str], leave_out: set[str]) -> list[str]:
    """Tên riêng hay gặp nhất trong chữ của một đoạn, trừ `leave_out` (khoá casefold: người kể của sách) - nhiều lần nhất trước."""
    from ..character_registry import _opens_a_sentence

    counts: dict[str, int] = {}
    first_seen: dict[str, int] = {}
    for text in texts:
        text = unicodedata.normalize("NFC", text)
        run: list[str] = []
        previous_end = -1
        for match in _WORD.finditer(text):
            word = match.group(0)
            joined = bool(run) and text[previous_end:match.start()] == " "
            capital = word[0].isupper() and len(word) > 1
            if capital and joined and len(run) < 3:
                run.append(word)
            else:
                _flush(run, counts, first_seen)
                run = [word] if capital and not _opens_a_sentence(text, match.start()) else []
            previous_end = match.end()
        _flush(run, counts, first_seen)
    blocked = {item.casefold() for item in leave_out}
    ranked = sorted((name for name in counts if name.casefold() not in blocked
                     and not any(part.casefold() in blocked for part in name.split())),
                    key=lambda name: (-counts[name], first_seen[name]))
    return _without_overlaps(ranked, counts, first_seen)[:SUGGEST_NAMES]


def _overlap(first: str, second: str) -> bool:
    """Hai tên là mảnh của cùng một cụm tên: một tên nằm trọn trong tên kia, hay đuôi tên này khớp đầu tên kia từ hai chữ trở lên
    ("Thiên Biến Vạn" / "Biến Vạn Hóa"). Chỉ chung MỘT chữ ("Lâm Hạ" / "Hạ Vy") thì vẫn là hai người."""
    one, two = first.casefold().split(), second.casefold().split()
    if len(one) > len(two):
        one, two = two, one
    if any(two[start:start + len(one)] == one for start in range(len(two) - len(one) + 1)):
        return True
    for size in range(2, min(len(one), len(two)) + 1):
        if one[-size:] == two[:size] or two[-size:] == one[:size]:
            return True
    return False


def _without_overlaps(ranked: list[str], counts: dict[str, int], first_seen: dict[str, int]) -> list[str]:
    """Bỏ mảnh chồng lấn, giữ tên DÀI NHẤT không chồng: tên viết hoa liên tiếp bị cắt ở ba chữ nên một cụm dài sinh ra vài mảnh
    ("Thiên Biến Vạn", "Biến Vạn Hóa", "Hóa Krai Andrey"). Mảnh gặp trước (nhiều lần hơn) giữ chỗ; tên dài hơn nuốt mảnh nó chứa."""
    kept: list[str] = []
    for name in ranked:
        clashing = [other for other in kept if _overlap(name, other)]
        if not clashing:
            kept.append(name)
        elif all(len(name.split()) > len(other.split()) for other in clashing):
            kept = [other for other in kept if other not in clashing] + [name]
    return sorted(kept, key=lambda name: (-counts[name], first_seen[name]))


def _flush(run: list[str], counts: dict[str, int], first_seen: dict[str, int]) -> None:
    if run:
        name = " ".join(run)
        counts[name] = counts.get(name, 0) + 1
        first_seen.setdefault(name, len(first_seen))
