"""Nhạc nền cho sách nghe bằng "Nghe ngay" (docs/LISTEN_ANYTHING.md mục 4): sách chỉ có chữ không qua phân tích nên không có không
khí từng cảnh để chọn bài - người nghe chọn một DANH SÁCH PHÁT cho cả cuốn.

Lựa chọn nằm ở lớp sửa của người nghe (`edits.json`, `music.playlist` - book_edits.py) nên đi theo sách và đồng bộ như mọi sửa khác:
- mã một danh sách phát của danh mục (mục `playlists` của mục lục, dựng bằng LLM_Train/music/playlists.py - 12 danh sách cố
  định, mỗi danh sách là các link theo thứ tự đã trộn sẵn);
- `MINE` = "Nhạc của tôi" của máy đang phát (music_local.py), theo thứ tự trong kho;
- không có = tắt (mặc định của sách chỉ có chữ).

Trình phát chơi các bài nối nhau theo đúng thứ tự, qua mọi chương (không bắt đầu lại mỗi chương), chuyển mờ và nằm dưới giọng theo
đúng công thức Pha 4 (`music_plan.cue_gain_db`; giọng "Nghe ngay" được cân về -20 LUFS lúc phát như giọng Studio). Bản Kotlin:
Playlists.kt.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Iterable

MINE = "mine"
_ID = re.compile(r"[a-z0-9_]{1,40}")
TEXT_MAX = 200


def _text(value: Any) -> str:
    return " ".join(str(value).split())[:TEXT_MAX] if isinstance(value, str) else ""


def catalogue_playlists(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Mục `playlists` của mục lục danh mục, chỉ giữ mục đúng hình dạng: {id, name, description, minutes, tracks}. Mã lạ, trùng
    mã hay không có bài nào thì bỏ; link chỉ nhận https:// (máy chủ chỉ tải bài có trong danh mục, music_track_file)."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in manifest.get("playlists") or []:
        if not isinstance(item, dict):
            continue
        playlist_id = item.get("id")
        if not isinstance(playlist_id, str) or not _ID.fullmatch(playlist_id) or playlist_id == MINE or playlist_id in seen:
            continue
        links = [link for link in item.get("tracks") or [] if isinstance(link, str) and link.startswith("https://")]
        if not links:
            continue
        seen.add(playlist_id)
        minutes = item.get("minutes")
        out.append({"id": playlist_id, "name": _text(item.get("name")) or playlist_id, "description": _text(item.get("description")),
                    "minutes": int(minutes) if isinstance(minutes, (int, float)) and not isinstance(minutes, bool) and minutes > 0 else 0,
                    "tracks": list(dict.fromkeys(links))})
    return out


def summaries(playlists: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Danh sách phát cho menu chọn (không kèm link): {id, name, description, minutes, count}."""
    return [{"id": item["id"], "name": item["name"], "description": item["description"], "minutes": item["minutes"],
             "count": len(item["tracks"])} for item in playlists]


def links_of(playlists: Iterable[dict[str, Any]], playlist_id: str) -> list[str]:
    """Các link của danh sách `playlist_id`, đúng thứ tự trộn sẵn; danh mục không (còn) có danh sách ấy thì rỗng."""
    return next((list(item["tracks"]) for item in playlists if item["id"] == playlist_id), [])


def queue(links: Iterable[str], tracks: dict[str, dict[str, Any]],
          available: Callable[[str], bool] | None = None) -> list[dict[str, Any]]:
    """Hàng bài để phát: [{link, duration}] theo đúng thứ tự `links`, bỏ bài máy này không dùng được (`available`) - danh sách
    vẫn chạy với các bài còn lại. `duration` (giây) lấy từ thông tin bài (`tracks[link]`); không biết thì None (trình phát dùng
    độ dài thật của file). Độ khuếch đại từng bài gắn sau bằng `music_plan.apply_gain`, cùng chỗ với nhạc theo cảnh."""
    out: list[dict[str, Any]] = []
    for link in links:
        if available is not None and not available(link):
            continue
        duration = (tracks.get(link) or {}).get("duration")
        ok = isinstance(duration, (int, float)) and not isinstance(duration, bool) and duration > 0
        out.append({"link": link, "duration": float(duration) if ok else None})
    return out
