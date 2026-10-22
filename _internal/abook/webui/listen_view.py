"""Sách nhìn từ phía NGƯỜI NGHE - cùng hình dạng với `book.json` của gói sách mà trình phát Android đọc.

Phía sản xuất (store.py) nói về câu, lô, giai đoạn; phía nghe chỉ cần: tên, người đọc, chương nào nghe được và
dài bao nhiêu, đã nghe tới đâu. Máy tính dựng hình dạng này từ project đang sản xuất (chương nào xong là nghe được
chương đó); điện thoại đọc nó từ gói đã tải về. Giao diện Nghe dùng chung một mã cho cả hai.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import covers, store, word_timing
from .listening import HEAVY_KEYS, book_progress

FORMAT = "abook-book/1"  # không ai đọc trường này, mã phiên bản gói không tính nó


def metadata_version(book: dict[str, Any]) -> str:
    """Dấu phiên bản của PHẦN MÔ TẢ cuốn (tên, tác giả, người đọc, liên kết bộ, tên từng chương) - không đụng audio / bìa / chữ. Gói sách
    (`book.json`) và dòng thư viện `/sync/v1/library` cùng mang nó: máy đã tải thấy dấu khác thì lấy lại phần mô tả mà giữ nguyên audio
    (điện thoại: LibraryPlugin.refreshMetadata), và đổi riêng tên sách không còn lặng lẽ để bản đã tải mang tên cũ (soát a97 V1)."""
    import hashlib
    import json

    series = book.get("series")
    chapters = [[chapter.get("id"), chapter.get("title") or "", chapter.get("subtitle") or "", chapter.get("fullTitle") or ""]
                for chapter in book.get("chapters") or [] if isinstance(chapter, dict)]
    return hashlib.sha256(json.dumps([book.get("title") or "", book.get("author") or "", book.get("narrator") or "",
                                      [series.get("root"), series.get("part")] if isinstance(series, dict) else None, chapters],
                                     ensure_ascii=False).encode()).hexdigest()[:16]


_CACHE: dict[str, tuple[tuple, list[dict[str, Any]]]] = {}


def on_shelf(summary: dict[str, Any], producing: bool) -> bool:
    """Dự án có mặt ở Thư viện nghe: đã có ít nhất một chương xong, hay đang làm (chưa có chương nào - "sắp có"). Cùng một luật cho
    Thư viện của chính máy này và danh sách máy đã ghép thấy (/sync/v1/library) - dự án chưa làm không thành "sách chữ" ở máy kia
    (soát a27 lỗi 13)."""
    return summary.get("chapters", {}).get("completed", 0) > 0 or producing


def chapters(project_root: Path) -> list[dict[str, Any]]:
    """Danh sách chương cho người nghe, đệm theo lần ghi cuối của DB - thư viện hỏi lại mỗi vài giây. Tên chương người nghe đặt lại nằm ở file
    riêng cạnh sổ (store.CHAPTER_TITLES_FILE), không đổi sổ: dấu của nó cũng thuộc chữ ký, không thì đổi tên xong trang vẫn trả tên cũ."""
    words = word_timing.stamp(project_root)
    stamp = (*store.db_signature(project_root, store.CHAPTER_TITLES_FILE), words)
    cached = _CACHE.get(str(project_root))
    if cached and cached[0] == stamp:
        return cached[1]
    result = _chapters(project_root)
    for chapter in result:
        chapter["wordsVersion"] = words
    _CACHE[str(project_root)] = (stamp, result)
    return result


def _chapters(project_root: Path) -> list[dict[str, Any]]:
    # Thời lượng lấy từ DB (tổng câu + khoảng lặng), không đo file MP3: lệch 0,14 s trên 13 phút (store.py), còn
    # đo MP3 cho mọi chương của mọi sách thì một thư viện 79 lô mất ~30 s. Trình phát tự biết độ dài thật khi phát.
    out = []
    for chapter in store.chapters(project_root):
        duration = chapter["seconds"] if chapter["playable"] else 0.0
        out.append({
            "id": chapter["id"],
            "index": chapter["index"],
            "title": chapter["displayTitle"],
            "subtitle": chapter["subtitle"],
            "fullTitle": chapter["fullTitle"],
            "duration": round(float(duration), 1),
            "available": bool(chapter["playable"]),
            "audioVersion": str(chapter["completedAt"] or ""),
        })
    return out


def book(project_root: Path, book_id: str, summary: dict[str, Any], state: dict[str, Any],
         *, with_chapters: bool = True) -> dict[str, Any]:
    items = chapters(project_root)
    available = [chapter for chapter in items if chapter["available"]]
    complete = summary["phase"] == "done" and len(available) == len(items)
    # Nhật ký đêm không đi theo danh sách/sách (có thể dài vài trăm mốc): thẻ "Tối qua" hỏi riêng.
    state = {key: value for key, value in state.items() if key not in HEAVY_KEYS}
    result: dict[str, Any] = {
        "format": FORMAT,
        "id": book_id,
        "title": summary["title"],
        "narrator": summary["settings"]["narrator"],
        "duration": round(sum(chapter["duration"] for chapter in available), 1),
        "chaptersTotal": len(items),
        "chaptersAvailable": len(available),
        "complete": complete,
        "producing": bool(summary.get("running") or summary.get("starting")),
        "paused": not complete and not (summary.get("running") or summary.get("starting")),
        # Đang làm nhưng bấm "Tạm dừng" hay máy chạy pin (tiến trình vẫn sống): thẻ "đang làm" nói đúng là đang tạm dừng
        # (soát UX 30-09: thẻ ghi "Đang làm · đang chuẩn bị").
        "pauseReason": summary.get("paused") if summary.get("running") else None,
        "updatedAt": summary.get("updatedAt"),
        "addedAt": summary.get("createdAt"),  # "Mới thêm" ở thư viện
        "state": state,
        "progress": book_progress(state, available, complete=complete),
        # Thẻ "Đang nghe dở" nói rõ chương nào, kể cả khi danh sách không kèm chương.
        "cover": covers.cover_view(project_root, book_id),
        "lastChapterTitle": next((chapter["fullTitle"] for chapter in items
                                  if chapter["id"] == (state.get("last") or {}).get("chapterId")), ""),
    }
    # Phần nối tiếp của "Làm tiếp cuốn này": phần đầu + thứ tự phần theo continues.json - thư viện gom các phần theo chuỗi,
    # không theo tên (soát UX 29-09, N10). Phần đầu không mang gì: giao diện nhận ra nó là sách mà các phần khác trỏ về.
    result["series"] = series(project_root)
    if with_chapters:
        result["chapters"] = items
    return result


def series(project_root: Path) -> dict[str, Any] | None:
    from .. import continuation
    from .library import book_id

    place = continuation.series_of(project_root)
    return {"root": book_id(place[0]), "part": place[1]} if place else None
