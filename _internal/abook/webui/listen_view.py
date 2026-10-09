"""Sách nhìn từ phía NGƯỜI NGHE - cùng hình dạng với `book.json` của gói sách mà trình phát Android đọc.

Phía sản xuất (store.py) nói về câu, lô, giai đoạn; phía nghe chỉ cần: tên, người đọc, chương nào nghe được và
dài bao nhiêu, đã nghe tới đâu. Máy tính dựng hình dạng này từ project đang sản xuất (chương nào xong là nghe được
chương đó); điện thoại đọc nó từ gói đã tải về. Giao diện Nghe dùng chung một mã cho cả hai.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import covers, store
from .listening import book_progress

FORMAT = "abook-book/1"  # không ai đọc trường này, mã phiên bản gói không tính nó


_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}


def chapters(project_root: Path) -> list[dict[str, Any]]:
    """Danh sách chương cho người nghe, đệm theo lần ghi cuối của DB - thư viện hỏi lại mỗi vài giây."""
    stamp = store.touched(project_root)
    cached = _CACHE.get(str(project_root))
    if cached and cached[0] == stamp:
        return cached[1]
    result = _chapters(project_root)
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
        })
    return out


def book(project_root: Path, book_id: str, summary: dict[str, Any], state: dict[str, Any],
         *, with_chapters: bool = True) -> dict[str, Any]:
    items = chapters(project_root)
    available = [chapter for chapter in items if chapter["available"]]
    complete = summary["phase"] == "done" and len(available) == len(items)
    # Nhật ký đêm không đi theo danh sách/sách (có thể dài vài trăm mốc): thẻ "Tối qua" hỏi riêng.
    state = {key: value for key, value in state.items() if key not in ("night", "sessions")}
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
    result["series"] = _series(project_root)
    if with_chapters:
        result["chapters"] = items
    return result


def _series(project_root: Path) -> dict[str, Any] | None:
    from .. import continuation
    from .library import book_id

    place = continuation.series_of(project_root)
    return {"root": book_id(place[0]), "part": place[1]} if place else None
