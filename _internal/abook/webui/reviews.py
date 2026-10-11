"""Hàng chờ "Cần nghe lại" của Studio: những câu mà khâu tự kiểm tra không chắc, xếp theo mức đáng lo.

Đo trên lô 18 (26-09, 3.682 câu): 6 câu hỏng (`failed` - chương không xuất được), 22 câu Whisper "nghe" ra một câu
không thể có trong độ dài ấy (ảo giác quen thuộc: "Cảm ơn các bạn đã theo dõi..." cho một câu "Cái..."), 766 câu tên
riêng viết khác chính tả của Whisper - độ khớp trung bình 94%, gần hết là ổn. Nên hàng chờ không liệt kê phẳng: hỏng
trước, rồi chưa kiểm được, rồi tên riêng có độ khớp thấp; tên riêng khớp cao ẩn đi trừ khi xin xem.

Phán quyết của người nghe ("ổn" / "cần thu lại") lưu ở `reviews.json` trong thư mục dự án (đi theo dự án sang máy khác), KHÔNG
ghi vào SQLite của sách (đó là của dây chuyền). Các chương có câu "cần thu lại" là danh sách đúc lại cho ranh giới lô kế tiếp.
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
KINDS = ("failed", "unverified", "name-low", "text-low", "name", "text")
# Lệch ít (tên hay chữ thường): thường vẫn ổn - không vào hàng chờ trừ khi mở "cả câu lệch ít".
MINOR_KINDS = ("name", "text")
REASONS = {
    "failed": "Thu âm hỏng sau mọi lần thử - chương này chưa xuất được",
    "unverified": "Máy nghe lại không kiểm được (câu quá ngắn) - nên nghe bằng tai",
    "name-low": "Tên riêng đọc khác nhiều so với chữ viết",
    "name": "Tên riêng đọc hơi khác chữ viết - thường vẫn ổn",
    "text-low": "Máy nghe ra khác nhiều so với chữ viết",
    "text": "Máy nghe ra hơi khác chữ viết - thường vẫn ổn",
}
# Mã cảnh báo nói lệch nằm ở TÊN RIÊNG (asr.py: Whisper viết tên ngoại bằng chữ Latin dù đọc đúng). Mã khác (lệch chữ thường
# sau mọi lần sửa, nghe chưa tự nhiên...) không được gọi là "tên riêng" (soát UX a24: nhãn ấy gắn cả câu không có tên nào).
_NAME_CODES = ("ASR_LOCKED_NAME_ANCHOR_MISMATCH", "ASR_LOCKED_NAME_ANCHOR_REVIEW")


UNNAMED_LABEL = "Vai phụ không tên"


def speaker_label(raw: str) -> str:
    """Tên người nói cho người đọc: vai phụ cục bộ "NPC_LOCAL::c00006::r0b2…::người lùn" -> "người lùn"."""
    if not raw:
        return ""
    if raw.upper() == "NARRATOR":
        return "Người kể"
    # Nhãn dành riêng của máy ("UNKNOWN", "UNNAMED", "ANONYMOUS...") là người nói không tên - tab Kịch bản gọi họ thế; chữ
    # "Unknown" thô không bao giờ lên mặt người nghe (soát UX a8).
    if raw.upper() in ("UNKNOWN", "UNNAMED") or raw.upper().startswith("ANONYMOUS"):
        return UNNAMED_LABEL
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
    about_name = any(name_code in code.split("|") for name_code in _NAME_CODES)
    if similarity is not None and similarity < LOW_SIMILARITY:
        return "name-low" if about_name else "text-low"
    return "name" if about_name else "text"


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
    spans: dict[int, dict[int, tuple[float, float]]] = {}
    audio = store.AudioLocator(project_root)
    items = []
    for row in rows:
        similarity = float(row["asr_similarity"]) if row["asr_similarity"] is not None else None
        kind = _kind(str(row["status"]), str(row["warning_code"] or ""), similarity)
        chapter = names.get(int(row["chapter_id"]), {})
        playable = store.segment_audio(project_root, row["wav_path"], audio) is not None
        # WAV riêng của câu đã dọn sau khi ghép chương: nghe đúng đoạn ấy trong file chương (mốc như chế độ đọc theo).
        span = None
        if not playable and kind != "failed":
            if int(row["chapter_id"]) not in spans:
                spans[int(row["chapter_id"])] = store.chapter_spans(project_root, int(row["chapter_id"]))
            span = spans[int(row["chapter_id"])].get(int(row["id"]))
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
            "playable": playable,
            "chapterClip": {"start": span[0], "end": span[1]} if span else None,
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


REVIEWS_NAME = "reviews.json"


class Reviews:
    """Phán quyết "Cần nghe lại" theo `stable_id` của câu, nằm trong CHÍNH thư mục dự án (`reviews.json`) - đi theo dự án khi
    gói `.abookproj` (projectfile mang mọi file của thư mục), mở ở máy hay hồ sơ khác vẫn còn (soát UX a24, A8: trước nằm ở hồ
    sơ app, mở dự án ở máy khác thì mất cả ba phán quyết). Một khoá cho mọi lần đọc-sửa-ghi trong tiến trình này."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    @staticmethod
    def path(project_root: Path) -> Path:
        return Path(project_root) / REVIEWS_NAME

    def _read(self, project_root: Path) -> dict[str, Any]:
        try:
            data = json.loads(self.path(project_root).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def get(self, project_root: Path) -> dict[str, Any]:
        with self._lock:
            return self._read(project_root)

    def set(self, project_root: Path, stable_id: str, verdict: str | None, chapter_id: int) -> None:
        if verdict not in (None, "ok", "redo"):
            raise ValueError("verdict")
        with self._lock:
            entry = self._read(project_root)
            if verdict is None:
                if entry.pop(stable_id, None) is None:
                    return
            else:
                entry[stable_id] = {"verdict": verdict, "chapterId": int(chapter_id), "at": time.time()}
            path = self.path(project_root)
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(json.dumps(entry, ensure_ascii=False, indent=1).encode("utf-8"))
            os.replace(temporary, path)


def awaiting(item: dict[str, Any], verdicts: dict[str, Any]) -> bool:
    """Câu còn chờ người nghe ở "Cần nghe lại": đáng lo (không phải tên khớp cao), chưa chấm, chưa sửa chữ đem đọc. Hộp việc
    (thẻ "Bản thu lỗi", work_items.py) đếm đúng những câu này - soát UX a23: chấm hết mà thẻ vẫn "Chưa nghe"."""
    return (item["kind"] not in MINOR_KINDS and not (verdicts.get(item["stableId"]) or {}).get("verdict")
            and item["pendingSpoken"] is None)


def review_view(project_root: Path, verdicts: dict[str, Any], *, include_minor: bool) -> dict[str, Any]:
    items = review_items(project_root)
    counts = {kind: 0 for kind in KINDS}
    pending = 0
    for item in items:
        counts[item["kind"]] += 1
        item["verdict"] = (verdicts.get(item["stableId"]) or {}).get("verdict")
        if awaiting(item, verdicts):
            pending += 1
    redo = sorted({int(value["chapterId"]) for value in verdicts.values() if value.get("verdict") == "redo"})
    shown = items if include_minor else [item for item in items if item["kind"] not in MINOR_KINDS or item["verdict"]]
    return {"counts": counts, "pending": pending, "redoChapters": redo, "items": shown[:600]}
