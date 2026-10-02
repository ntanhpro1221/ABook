"""Hàng chờ "Cần nghe lại" của Studio: những câu mà khâu tự kiểm tra không chắc, xếp theo mức đáng lo.

Đo trên lô 18 (26-09, 3.682 câu): 6 câu hỏng (`failed` - chương không xuất được), 22 câu Whisper "nghe" ra một câu
không thể có trong độ dài ấy (ảo giác quen thuộc: "Cảm ơn các bạn đã theo dõi..." cho một câu "Cái..."), 766 câu tên
riêng viết khác chính tả của Whisper - độ khớp trung bình 94%, gần hết là ổn. Nên hàng chờ không liệt kê phẳng: hỏng
trước, rồi chưa kiểm được, rồi tên riêng có độ khớp thấp; tên riêng khớp cao ẩn đi trừ khi xin xem.

Phán quyết của người nghe ("ổn" / "cần thu lại") lưu ở file riêng cạnh tuỳ chọn, KHÔNG ghi vào SQLite của sách (đó là
của dây chuyền). Các chương có câu "cần thu lại" là danh sách đúc lại cho ranh giới lô kế tiếp.
"""
from __future__ import annotations

import json
import os
import threading
import time
from contextlib import closing
from pathlib import Path
from typing import Any

from . import store

LOW_SIMILARITY = 0.8
KINDS = ("failed", "unverified", "name-low", "name")
REASONS = {
    "failed": "Thu âm hỏng sau mọi lần thử - chương này chưa xuất được",
    "unverified": "Máy nghe lại không kiểm được (câu quá ngắn) - nên nghe bằng tai",
    "name-low": "Tên riêng đọc khác nhiều so với chữ viết",
    "name": "Tên riêng đọc hơi khác chữ viết - thường vẫn ổn",
}


def speaker_label(raw: str) -> str:
    """Tên người nói cho người đọc: vai phụ cục bộ "NPC_LOCAL::c00006::r0b2…::người lùn" -> "người lùn"."""
    if not raw:
        return ""
    if raw.upper() == "NARRATOR":
        return "Người kể"
    from .humanize import person_name

    return person_name(raw)


def _shown_transcript(kind: str, similarity: float | None, text: str, heard: str) -> str:
    """Chữ máy nghe ra, trừ khi đó là Whisper NGHE ẢO: câu dài bất khả trên thời lượng ("unverified") hay câu rất ngắn khớp
    gần 0% - soát UX 29-09: "Hãy subscribe cho kênh..." hiện trên thẻ làm người mới tưởng audio bị chèn quảng cáo."""
    if kind == "unverified" or (similarity is not None and similarity < 0.2 and len(text.split()) <= 4):
        return ""
    return heard


def _kind(status: str, code: str, similarity: float | None) -> str:
    if status == "failed":
        return "failed"
    if code == "ASR_TRANSCRIPT_TIMELINE_IMPOSSIBLE":
        return "unverified"
    if similarity is not None and similarity < LOW_SIMILARITY:
        return "name-low"
    return "name"


def review_items(project_root: Path) -> list[dict[str, Any]]:
    from ..listener_overrides import line_requests, read_overrides

    with closing(store.connect(project_root)) as connection:
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(segments)")}
        extra = [column for column in ("text_sha256", "listener_text") if column in columns]
        rows = connection.execute(
            "SELECT id, stable_id, chapter_id, seq, text, asr_text, asr_similarity, status, warning_code, speaker,"
            " wav_path" + "".join(f", {column}" for column in extra)
            + " FROM segments WHERE status IN ('warning', 'failed') ORDER BY chapter_id, seq"
        ).fetchall()
        names = store.chapter_names(connection, project_root)
    # Chữ đem đọc đang chờ áp (tab Kịch bản hay chính thẻ này): thẻ hiện nó thay vì mời sửa lại từ đầu.
    waiting = {entry["stable_id"]: entry for entry in line_requests(read_overrides(project_root))
               if isinstance(entry.get("spoken"), str)}
    items = []
    for row in rows:
        similarity = float(row["asr_similarity"]) if row["asr_similarity"] is not None else None
        kind = _kind(str(row["status"]), str(row["warning_code"] or ""), similarity)
        chapter = names.get(int(row["chapter_id"]), {})
        items.append({
            "segmentId": int(row["id"]),
            "stableId": str(row["stable_id"]),
            "chapterId": int(row["chapter_id"]),
            "chapterTitle": chapter.get("full") or f"Chương {row['chapter_id']}",
            "text": str(row["text"] or ""),
            "heard": _shown_transcript(kind, similarity, str(row["text"] or ""), str(row["asr_text"] or "")),
            "similarity": similarity,
            "speaker": speaker_label(str(row["speaker"] or "")),
            "kind": kind,
            "reason": REASONS[kind],
            "playable": store.segment_audio(project_root, row["wav_path"]) is not None,
            # Sửa "chữ đem đọc" ngay trên thẻ (soát UX a5/a6 01-10: câu tượng thanh "Tách tách tách" hỏng sau mọi lần thử chỉ
            # có nút "Thu lại" - thu lại y chữ thì hỏng y như cũ). Băm chữ đi kèm để yêu cầu tự rơi khi câu đổi chữ.
            "textSha256": str(row["text_sha256"] or "") if "text_sha256" in row.keys() else "",
            "spoken": (str(row["listener_text"] or "") if "listener_text" in row.keys() else "") or None,
            "pendingSpoken": _pending_spoken(waiting.get(str(row["stable_id"])), row),
        })
    items.sort(key=lambda item: (KINDS.index(item["kind"]), item["similarity"] if item["similarity"] is not None else 1.0))
    return items


def _pending_spoken(wish: dict[str, Any] | None, row: Any) -> str | None:
    """Chữ đem đọc người nghe đã ghi mà dây chuyền chưa áp ("" = trả về chữ sách); None khi không có hay câu đã đổi chữ."""
    if wish is None or "text_sha256" not in row.keys() or wish.get("text_sha256") != str(row["text_sha256"] or ""):
        return None
    spoken = str(wish.get("spoken"))
    applied = str(row["listener_text"] or "") if "listener_text" in row.keys() else ""
    return None if spoken == applied else spoken


def reviews_path() -> Path:
    from .library import preferences_path

    return preferences_path().with_name("reviews.json")


class Reviews:
    """Phán quyết theo `stable_id` của câu (bền qua các lần mở lại sách)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or reviews_path()
        self._lock = threading.Lock()
        try:
            self._data: dict[str, Any] = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._data = {}

    def get(self, book: str) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._data.get(book) or {}))

    def set(self, book: str, stable_id: str, verdict: str | None, chapter_id: int) -> None:
        if verdict not in (None, "ok", "redo"):
            raise ValueError("verdict")
        with self._lock:
            entry = self._data.setdefault(book, {})
            if verdict is None:
                entry.pop(stable_id, None)
            else:
                entry[stable_id] = {"verdict": verdict, "chapterId": int(chapter_id), "at": time.time()}
            self._save()

    def books(self) -> list[str]:
        with self._lock:
            return list(self._data)

    def rename_books(self, renamed: dict[str, str]) -> None:
        """Đổi khoá sách ({mã cũ: mã mới}, library.legacy_ids). Hai khoá về cùng một cuốn: phán quyết mới hơn thắng."""
        with self._lock:
            changed = False
            for old, new in renamed.items():
                if old == new or old not in self._data:
                    continue
                moved = self._data.pop(old) or {}
                target = self._data.setdefault(new, {})
                for stable_id, verdict in moved.items():
                    current = target.get(stable_id)
                    if current is None or float((verdict or {}).get("at") or 0) > float(current.get("at") or 0):
                        target[stable_id] = verdict
                changed = True
            if changed:
                self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporary, self.path)


def review_view(project_root: Path, verdicts: dict[str, Any], *, include_minor: bool) -> dict[str, Any]:
    items = review_items(project_root)
    counts = {kind: 0 for kind in KINDS}
    pending = 0
    for item in items:
        counts[item["kind"]] += 1
        item["verdict"] = (verdicts.get(item["stableId"]) or {}).get("verdict")
        if item["kind"] != "name" and not item["verdict"] and item["pendingSpoken"] is None:
            pending += 1
    redo = sorted({int(value["chapterId"]) for value in verdicts.values() if value.get("verdict") == "redo"})
    shown = items if include_minor else [item for item in items if item["kind"] != "name" or item["verdict"]]
    return {"counts": counts, "pending": pending, "redoChapters": redo, "items": shown[:600]}
