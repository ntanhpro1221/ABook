"""Mục "Cách đọc tên" của tab Nhân vật: MỌI cách đọc của cuốn (bảng `pronunciations`), không chỉ chỗ máy kém tin.

Hộp việc chỉ hỏi cách đọc máy tự đoán dưới 0,9, và thẻ biến mất khi cách đọc đã ghim - nên một tên máy chắc mà đọc sai, hay
một cách đọc người nghe đã chọn rồi muốn đổi, không có chỗ nào sửa (soát 29-09). Ở đây mỗi tên một dòng: đọc thế nào, ai
quyết (máy đoán hay người nghe), bao nhiêu câu có tên ấy, một câu mẫu để nghe, và yêu cầu đang chờ áp. Sửa đi đúng đường
của thẻ: POST /pronunciation -> overrides.json, dây chuyền áp ở ranh giới chương (listener_overrides.py)."""
from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Any

from . import store
from .work_items import _example, _has_audio, _rerecord_cost

WORD = re.compile(r"\w+")


def name_readings(project_root: Path) -> dict[str, Any]:
    """{"items": [...], "unseen": N} xếp theo số câu có tên (nhiều trước). Đếm như TTS khớp (`tts._load_pronunciations`):
    nguyên từ, không phân biệt hoa thường. Câu mẫu ưu tiên câu đã thu, để nghe máy đang đọc tên ấy thế nào."""
    from ..database import LISTENER_PRONUNCIATION_SOURCE
    from ..listener_overrides import pronunciation_requests, read_overrides, surface_key

    wishes = {surface_key(entry["surface"]): entry for entry in pronunciation_requests(read_overrides(project_root))}
    if not (Path(project_root) / store.DB_NAME).is_file():
        return {"items": []}
    with closing(store.connect(project_root)) as connection:
        tables = store._table_names(connection)
        rows = connection.execute(
            "SELECT surface, normalized_surface, spoken_form, confidence, source FROM pronunciations"
        ).fetchall() if "pronunciations" in tables else []
        # Tên người nghe vừa thêm (chưa có dòng nào trong bảng) cũng là một dòng, đang chờ áp.
        surfaces = {str(row["normalized_surface"]): str(row["surface"]) for row in rows}
        surfaces.update({key: str(entry["surface"]) for key, entry in wishes.items() if key not in surfaces})
        # Khoá bảng là cả cụm đã chuẩn hoá; từ trong câu so bằng casefold - tên nhiều từ (hiếm) không bao giờ khớp một từ,
        # đúng như TTS chỉ ghi đè từng từ.
        lines: dict[str, int] = defaultdict(int)
        examples: dict[str, Any] = {}
        names = store.chapter_names(connection, project_root) if "segments" in tables else {}
        audio = store.AudioLocator(project_root)  # một bộ tìm WAV cho mọi câu mẫu (thư mục sách chỉ `resolve` một lần)
        # Chữ không phải một từ trơn ("TP.HCM", "km/h" - người nghe thêm cho bất kỳ chữ nào) không nằm trong tập từ của câu: khớp
        # bằng regex nguyên từ như TTS, chỉ cho vài chữ ấy.
        odd = {key: re.compile(r"(?<!\w)" + re.escape(key) + r"(?!\w)", re.IGNORECASE)
               for key in surfaces if not WORD.fullmatch(key)}
        for segment in connection.execute(
            "SELECT id, chapter_id, seq, text, speaker, wav_path FROM segments ORDER BY wav_path IS NULL, chapter_id, seq"
        ) if "segments" in tables else ():
            text = str(segment["text"] or "")
            hit = {word.casefold() for word in WORD.findall(text)} & surfaces.keys()
            hit |= {key for key, pattern in odd.items() if pattern.search(text)}
            for word in hit:
                lines[word] += 1
                examples.setdefault(word, segment)
        items: list[dict[str, Any]] = []
        known = {str(row["normalized_surface"]): row for row in rows}
        for key, surface in surfaces.items():
            row = known.get(key)
            spoken = str(row["spoken_form"]) if row is not None else ""
            wish = wishes.get(key)
            # Yêu cầu bằng đúng cách đang đọc (đã áp, hay "Đúng rồi, giữ") không đổi gì - không phải "chờ áp dụng" mà là
            # người nghe đã quyết, như `store._kept_as_is`.
            kept = wish is not None and wish["spoken_form"] == spoken
            by_listener = kept or (row is not None and str(row["source"]) == LISTENER_PRONUNCIATION_SOURCE)
            waiting = wish is not None and not kept
            items.append({
                "surface": surface,
                "spoken": spoken,
                "byListener": by_listener,
                "confidence": round(float(row["confidence"]), 2) if row is not None else None,
                "lines": lines.get(key, 0),
                "requested": wish["spoken_form"] if waiting else None,
                "example": _example(examples[key], names, project_root=audio) if key in examples else None,
            })
    # Bảng mang cả tên của những chương khác trong cuốn (hạt giống từ phần trước): tên máy đoán mà phần này không có câu nào
    # thì không đổi gì ở đây - chỉ đếm (lô 18: 997/1136 dòng).
    shown = [item for item in items if item["lines"] or item["byListener"] or item["requested"]]
    shown.sort(key=lambda item: (-item["lines"], item["surface"].casefold()))
    return {"items": shown, "unseen": len(items) - len(shown)}


CHAPTERS_SHOWN = 6


def reading_reach(project_root: Path, surface: str) -> dict[str, Any]:
    """Một cách đọc cho BẤT KỲ chữ nào ("TP.HCM", "km/h"), không chỉ tên nhân vật, sẽ chạm tới những câu nào: số câu có chữ ấy, bao
    nhiêu câu đã thu (phải thu lại - cách đếm của hộp chọn giọng), ở chương nào, một câu mẫu (ưu tiên câu đã thu).

    Khớp đúng như TTS (`tts._load_pronunciations`): nguyên từ, không phân biệt hoa thường, trên chữ máy sẽ đọc (`listener_text` nếu
    người nghe đã sửa câu). Trước khi tra cách đọc, dây chuyền đổi ký hiệu máy không nói được thành quãng nghỉ
    (`spoken_symbols_to_words`: "Mở/đóng" thành "Mở, đóng"; "km/h" thì giữ), nên chữ nào bị chữ ấy xé đôi thì cách đọc không bao giờ khớp: `blocked`
    đếm các câu đó, để giao diện nói thật thay vì hứa thu lại."""
    surface = " ".join(str(surface).split())
    if not surface or not (Path(project_root) / store.DB_NAME).is_file():
        return _reach(surface, [], {}, lambda row: False, lambda row: {})
    with closing(store.connect(project_root)) as connection:
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(segments)")}
        names = store.chapter_names(connection, project_root)
        audio = store.AudioLocator(project_root)
        fields = "id, chapter_id, seq, text, speaker, wav_path" + (", listener_text" if "listener_text" in columns else "")
        rows = [(str((row["listener_text"] if "listener_text" in columns else "") or row["text"] or ""), row)
                for row in connection.execute(f"SELECT {fields} FROM segments ORDER BY chapter_id, seq")]
        return _reach(surface, rows, names, lambda row: _has_audio(row, audio),
                      lambda row: _example(row, names, project_root=audio))


def package_reading_reach(folder: Path, surface: str) -> dict[str, Any]:
    """`reading_reach` của cuốn mở từ file `.abook` (không có xưởng - "Đọc từ này là…" ở trang đọc, máy tính và điện thoại): cùng
    hình dạng, cùng luật khớp, đếm trên chữ đọc theo của gói (đã qua lớp sửa). Câu "đã thu" là câu có mốc thời gian trong một
    chương có audio - chính những câu Studio sẽ thu lại khi nhận ý muốn. Bản Kotlin: LocalStudio.readingReach (`blocked` cũng do
    SpokenSymbols.toWords = `spoken_symbols_to_words`); hai bên đáp chung ca tests/fixtures/book_edits/contract/reading_reach.json."""
    from . import packages

    surface = " ".join(str(surface).split())
    chapters = [chapter for chapter in packages.edited_manifest(folder).get("chapters") or []
                if isinstance(chapter, dict) and isinstance(chapter.get("id"), int) and not isinstance(chapter.get("id"), bool)]
    names = {chapter["id"]: {"full": str(chapter.get("fullTitle") or chapter.get("title") or "")} for chapter in chapters}
    rows: list[tuple[str, dict[str, Any]]] = []
    for chapter in chapters if surface else []:
        script = packages.script(folder, chapter["id"])
        heard = bool(chapter.get("available") and chapter.get("file"))
        for seq, segment in enumerate((script.get("segments") if isinstance(script, dict) else None) or [], start=1):
            if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
                continue
            start = segment.get("start")
            timed = heard and isinstance(start, (int, float)) and not isinstance(start, bool)
            # Hàng như của dự án (`wav_path` khác rỗng = đã thu) để dùng chung cách tính giá và câu mẫu (work_items).
            rows.append((segment["text"], {"id": segment.get("id") if isinstance(segment.get("id"), int) else seq,
                                           "chapter_id": chapter["id"], "seq": seq, "text": segment["text"],
                                           "speaker": str(segment.get("speaker") or ""), "wav_path": chapter["file"] if timed else ""}))
    # Người nói trong chữ đọc theo đã là tên người nghe thấy - không đổi thêm.
    return _reach(surface, rows, names, lambda row: bool(row["wav_path"]),
                  lambda row: _example(row, names, label=lambda raw: raw))


def _reach(surface: str, rows: list[tuple[str, Any]], names: dict[int, dict[str, Any]], recorded: Callable[[Any], bool],
           example: Callable[[Any], dict[str, Any]]) -> dict[str, Any]:
    """Phần đếm chung của `reading_reach` / `package_reading_reach`: `rows` = [(chữ máy sẽ đọc, hàng)] theo thứ tự chương, câu."""
    from ..text_processing import spoken_symbols_to_words

    pattern = re.compile(r"(?<!\w)" + re.escape(surface) + r"(?!\w)", re.IGNORECASE)
    matched: list[Any] = []
    reached: list[Any] = []
    for said, row in rows if surface else []:
        if not pattern.search(said):
            continue
        matched.append(row)
        if pattern.search(spoken_symbols_to_words(said)):
            reached.append(row)
    audible = [row for row in reached if recorded(row)]
    audible_ids = {id(row) for row in audible}
    per_chapter: dict[int, list[int]] = {}
    for row in reached:
        counts = per_chapter.setdefault(int(row["chapter_id"]), [0, 0])
        counts[0] += 1
        counts[1] += int(id(row) in audible_ids)
    first = (audible or reached or [None])[0]
    return {
        "surface": surface,
        "lines": len(matched),
        "reached": len(reached),
        "recorded": len(audible),
        "blocked": len(matched) - len(reached),
        "cost": _rerecord_cost(audible),
        "chapters": [
            {"chapterId": chapter_id, "title": str(names.get(chapter_id, {}).get("full") or ""), "lines": counts[0],
             "recorded": counts[1]}
            for chapter_id, counts in list(per_chapter.items())[:CHAPTERS_SHOWN]
        ],
        "example": example(first) if first is not None else None,
    }
