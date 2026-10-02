"""Xuất sách ra một thư mục MP3 nghe được bằng MỌI trình phát (điện thoại, xe hơi, Voice, Smart AudioBook Player...).

MP3 chương do dây chuyền ghi mang tag của nội bộ sản xuất: album là tên project của lô ("lo16"), title là tên file
nguồn ("645"). Mở bằng trình phát khác thì thấy sách "lo16" với các chương "645", "646" (thử 26-09 trên Voice). Code
ghi MP3 nằm trong các file bị khoá của dây chuyền, nên sửa ở đây: chép nguyên luồng âm thanh (không mã hoá lại - nhanh,
không mất chất lượng) sang thư mục mới với tag đúng - tên sách, tên chương thật, giọng kể, số thứ tự, ảnh bìa - kèm
danh sách phát `.m3u8`. File chưa xong ghi ra `.part` rồi mới đổi tên, như mọi file âm thanh khác của dự án.
"""
from __future__ import annotations

import base64
import os
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .. import continuation
from ..io_utils import ffmpeg_executable, run_hidden
from . import covers, listen_view, store

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(text: str, limit: int = 120) -> str:
    """Tên file hợp lệ trên Windows, giữ nguyên chữ tiếng Việt."""
    cleaned = _UNSAFE.sub(" ", text).strip().strip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:limit].rstrip() or "Sach"


def _cover_file(folder: Path, cover: str | None) -> Path | None:
    """Ảnh bìa gửi từ giao diện (data URL PNG do trình duyệt vẽ, cùng kiểu bìa trong app)."""
    match = re.fullmatch(r"data:image/png;base64,([A-Za-z0-9+/=]+)", cover or "")
    if not match:
        return None
    data = base64.b64decode(match.group(1))
    if not data.startswith(b"\x89PNG") or len(data) > 4 * 1024 * 1024:
        return None
    path = folder / "cover.png"
    path.write_bytes(data)
    return path


def _real_cover(project_root: Path, folder: Path) -> Path | None:
    """Ảnh bìa thật người dùng đã đặt (covers.py) thắng bìa tự vẽ mà giao diện gửi kèm."""
    source = covers.cover_file(project_root)
    if source is None:
        return None
    target = folder / covers.COVER_FILE
    shutil.copyfile(source, target)
    return target


def _listenable(project_root: Path) -> list[dict[str, Any]]:
    """Các chương đã nghe được - đúng những chương mọi kiểu xuất lấy."""
    return [chapter for chapter in listen_view.chapters(project_root) if chapter["available"]]


def export_book(project_root: Path, target_root: Path, *, cover: str | None = None,
                folder_name: str | None = None) -> dict[str, Any]:
    """`folder_name`: tên thư mục thay cho tên sách - bản xuất cả bộ đặt mỗi phần vào "Phần N - ..."."""
    summary = store.summarize(project_root)
    title = summary["title"] or project_root.name
    narrator = summary["settings"]["narrator"] or ""
    chapters = _listenable(project_root)
    if not chapters:
        raise ValueError("Sách chưa có chương nào nghe được để xuất")
    folder = target_root / safe_name(folder_name or title)
    folder.mkdir(parents=True, exist_ok=True)
    cover_path = _real_cover(project_root, folder) or _cover_file(folder, cover)
    ffmpeg = ffmpeg_executable()
    total = len(chapters)
    width = max(2, len(str(total)))
    playlist = ["#EXTM3U", f"#PLAYLIST:{title}"]
    written: list[str] = []
    for number, chapter in enumerate(chapters, start=1):
        source = store.chapter_audio_path(project_root, chapter["id"])
        if source is None:
            continue
        name = f"{number:0{width}d} - {safe_name(chapter['fullTitle'], 90)}.mp3"
        final = folder / name
        partial = folder / f"{name}.part"
        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source)]
        if cover_path:
            command += ["-i", str(cover_path), "-map", "0:a", "-map", "1:v", "-c:v", "copy",
                        "-disposition:v", "attached_pic", "-metadata:s:v", "title=Album cover",
                        "-metadata:s:v", "comment=Cover (front)"]
        else:
            command += ["-map", "0:a"]
        command += [
            "-c:a", "copy", "-map_metadata", "-1", "-id3v2_version", "3", "-write_id3v1", "1",
            "-metadata", f"title={chapter['fullTitle']}",
            "-metadata", f"album={title}",
            "-metadata", f"artist={narrator}",
            "-metadata", f"album_artist={narrator}",
            "-metadata", f"track={number}/{total}",
            "-metadata", "genre=Audiobook",
            "-f", "mp3", str(partial),
        ]
        run_hidden(command, timeout=300)
        os.replace(partial, final)
        written.append(name)
        playlist += [f"#EXTINF:{int(round(chapter['duration']))},{chapter['fullTitle']}", name]
    (folder / f"{safe_name(title)}.m3u8").write_text("\n".join(playlist) + "\n", encoding="utf-8")
    return {"folder": str(folder), "files": len(written), "chaptersTotal": summary["chapters"]["total"]}


def _title_of(project: Path) -> str:
    return store.summarize(project)["title"] or project.name


def series_split(parts: list[Path]) -> tuple[list[tuple[int, Path]], list[dict[str, Any]]]:
    """Các phần của bộ chia làm hai: phần có chương nghe được [(số phần, dự án)] và phần chưa có chương nào [{part, title}].
    Số phần là vị trí trong bộ, không đếm lại sau khi bỏ qua - "Phần 3" vẫn là phần 3. Mọi kiểu xuất cả bộ dùng chung."""
    listed: list[tuple[int, Path]] = []
    skipped: list[dict[str, Any]] = []
    for number, project in enumerate(parts, start=1):
        if _listenable(project):
            listed.append((number, project))
        else:
            skipped.append({"part": number, "title": _title_of(project)})
    if not listed:
        raise ValueError("Chưa phần nào của bộ có chương nghe được để xuất")
    return listed, skipped


def audio_bytes(projects: list[Path]) -> int:
    """Tổng cỡ audio các chương nghe được - ước lượng cỡ file `.abook` (audio chiếm gần hết) trước khi xuất."""
    total = 0
    for project in projects:
        for chapter in _listenable(project):
            path = store.chapter_audio_path(project, chapter["id"])
            if path is not None:
                total += path.stat().st_size
    return total


def export_series(parts: list[Path], target_root: Path,
                  export_part: Callable[[Path, Path, str], dict[str, Any]]) -> dict[str, Any]:
    """Xuất cả bộ ("Làm tiếp cuốn này" chia một truyện thành nhiều dự án): một thư mục cho bộ, mỗi phần xuất bằng đúng đường
    xuất một phần. `export_part(dự án, thư mục bộ, "Phần N - tên")` làm một phần và trả kết quả của nó (MP3: thư mục
    con theo nhãn; .abook: một file mang nhãn). Chỉ chương đã xong như xuất một phần; phần chưa có chương nào bị bỏ qua và
    được kể tên - người dùng thấy bộ thiếu phần nào thay vì nghĩ là xuất sót."""
    listed, skipped = series_split(parts)
    folder = target_root / safe_name(continuation.base_title(_title_of(parts[0])))
    done = [{"part": number, "title": _title_of(project),
             **export_part(project, folder, f"Phần {number} - {continuation.base_title(_title_of(project))}")}
            for number, project in listed]
    return {"folder": str(folder), "parts": done, "skipped": skipped, "partsTotal": len(parts)}


def export_series_file(parts: list[Path], target_root: Path,
                       pack: Callable[[list[tuple[int, Path]], Path], Path]) -> dict[str, Any]:
    """Cả bộ trong MỘT file `.abook` (phiên bản 3, bookfile.pack_series) nằm thẳng trong `target_root`, tên theo tên bộ.
    `pack(các phần, đường file)` ghi file và trả đường dẫn. Kết quả cùng hình dạng với `export_series` (parts, skipped,
    partsTotal) cộng `file` + `size`: giao diện phân biệt "một file" với "mỗi phần một file" bằng chỗ có `file`."""
    from .bookfile import default_name

    listed, skipped = series_split(parts)
    path = pack(listed, target_root / default_name(continuation.base_title(_title_of(parts[0]))))
    return {"folder": str(path.parent), "file": str(path), "size": path.stat().st_size,
            "parts": [{"part": number, "title": _title_of(project)} for number, project in listed],
            "skipped": skipped, "partsTotal": len(parts)}
