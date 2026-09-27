"""Sách mở từ file `.abook` trên máy tính: giải nén vào thư viện, nghe như sách tự làm.

Chủ sách 27-09: một cuốn là một file, bấm đúp là ABook mở. Điện thoại đã mở được (BookFileImport.kt); ở máy tính file
được kiểm từng phần rồi giải nén (`bookfile.extract`) vào `<thư viện>/Sách đã nhập/`. `book.json` của gói mang sẵn
hình dạng phía nghe (`sync.manifest` dựng từ `listen_view`), nên thư viện chỉ việc đọc nó: không SQLite, không Studio.

Cùng một lần sản xuất không thành hai cuốn (dấu vân tay audio, `fingerprints.py`): file do chính máy này xuất ra - có
chung một chương audio với một dự án trong thư viện - mở ra đúng dự án ấy; mở lại một cuốn đã nhập thì về cuốn ấy, và
bản nào nhiều chương hơn thì giữ bản ấy (thay tại chỗ, nên dữ liệu nghe gắn với cuốn vẫn nguyên).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from . import covers, store
from .fingerprints import Fingerprints
from .listen_view import FORMAT
from .listening import book_progress

MANIFEST = "book.json"  # = bookfile.MANIFEST (bookfile nhập library, library nhập module này - nên không nhập ở đây)
IMPORTED_FOLDER = "Sách đã nhập"

_CACHE: dict[str, tuple[tuple[int, int], dict[str, Any]]] = {}


def manifest(path: Path) -> dict[str, Any]:
    """`book.json` của một cuốn đã nhập, đệm theo lần ghi - thư viện hỏi lại mỗi vài giây."""
    file = Path(path) / MANIFEST
    stat = file.stat()
    stamp = (stat.st_mtime_ns, stat.st_size)
    cached = _CACHE.get(str(file))
    if cached and cached[0] == stamp:
        return cached[1]
    data = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("book.json không phải một đối tượng")
    _CACHE[str(file)] = (stamp, data)
    return data


def is_package(path: Path) -> bool:
    """Thư mục là một cuốn đã nhập từ file: có `book.json` mang mục "package", và không phải dự án sản xuất."""
    path = Path(path)
    if not (path / MANIFEST).is_file() or store.is_project(path):
        return False
    try:
        return isinstance(manifest(path).get("package"), dict)
    except (OSError, ValueError):
        return False


def folders(library_root: Path) -> list[Path]:
    """Các cuốn đã nhập dưới `<thư viện>/Sách đã nhập/` (bỏ thư mục tạm của lần giải nén đang dở: tên bắt đầu bằng ".")."""
    imported = Path(library_root).expanduser() / IMPORTED_FOLDER
    try:
        children = sorted(imported.iterdir()) if imported.is_dir() else []
    except OSError:
        return []
    return [child.resolve() for child in children if child.is_dir() and not child.name.startswith(".") and is_package(child)]


def chapter_prints(book: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Cỡ + mã băm audio từng chương, ghi trong gói lúc xuất (như `BookFile.chapter_prints`)."""
    files = (book.get("package") or {}).get("files") or {}
    return {name: {"size": meta.get("size"), "sha256": meta.get("sha256")}
            for name, meta in files.items() if name.startswith("chapters/") and isinstance(meta, dict)}


def _inside(root: Path, relative: Any) -> Path | None:
    """Đường dẫn trong gói - tên lấy từ `book.json`, nên không cho nó trỏ ra ngoài thư mục của cuốn."""
    if not isinstance(relative, str) or not relative:
        return None
    root = Path(root).resolve()
    candidate = (root / relative).resolve()
    return candidate if candidate.is_file() and candidate.is_relative_to(root) else None


def _chapter(book: dict[str, Any], chapter_id: int) -> dict[str, Any] | None:
    return next((chapter for chapter in book.get("chapters") or []
                 if isinstance(chapter, dict) and chapter.get("id") == chapter_id), None)


def chapter_file(path: Path, chapter_id: int) -> Path | None:
    chapter = _chapter(manifest(path), chapter_id)
    return _inside(path, chapter.get("file")) if chapter and chapter.get("available") else None


def sample_file(path: Path, sample_id: int) -> Path | None:
    name = f"samples/{int(sample_id)}.wav"
    return _inside(path, name) if name in (manifest(path).get("samples") or []) else None


def script(path: Path, chapter_id: int) -> Any | None:
    chapter = _chapter(manifest(path), chapter_id)
    file = _inside(path, chapter.get("script")) if chapter else None
    return json.loads(file.read_text(encoding="utf-8")) if file else None


def cast(path: Path) -> Any:
    file = _inside(path, manifest(path).get("cast") or "cast.json")
    return json.loads(file.read_text(encoding="utf-8")) if file else {"characters": [], "extras": []}


def listen(path: Path, book_id: str, state: dict[str, Any], *, with_chapters: bool = True) -> dict[str, Any]:
    """Cùng hình dạng với `listen_view.book` của một dự án - giao diện Nghe không phân biệt hai loại."""
    book = manifest(path)
    items = []
    for chapter in book.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        available = bool(chapter.get("available")) and _inside(path, chapter.get("file")) is not None
        items.append({
            "id": chapter.get("id"),
            "index": chapter.get("index"),
            "title": chapter.get("title") or "",
            "subtitle": chapter.get("subtitle") or "",
            "fullTitle": chapter.get("fullTitle") or chapter.get("title") or "",
            "duration": round(float(chapter.get("duration") or 0), 1) if available else 0.0,
            "available": available,
        })
    available = [chapter for chapter in items if chapter["available"]]
    complete = bool(book.get("complete")) and len(available) == len(items)
    state = {key: value for key, value in state.items() if key not in ("night", "sessions")}
    result: dict[str, Any] = {
        "format": FORMAT,
        "id": book_id,
        "title": str(book.get("title") or Path(path).name),
        "narrator": str(book.get("narrator") or ""),
        "duration": round(sum(chapter["duration"] for chapter in available), 1),
        "chaptersTotal": max(int(book.get("chaptersTotal") or 0), len(items)),
        "chaptersAvailable": len(available),
        "complete": complete,
        "producing": False,
        "paused": False,
        "imported": True,
        "updatedAt": (Path(path) / MANIFEST).stat().st_mtime,
        "state": state,
        "progress": book_progress(state, available, complete=complete),
        "cover": covers.cover_view(Path(path), book_id),
        "lastChapterTitle": next((chapter["fullTitle"] for chapter in items
                                  if chapter["id"] == (state.get("last") or {}).get("chapterId")), ""),
    }
    if with_chapters:
        result["chapters"] = items
    return result


def _folder_name(title: str, key: str) -> str:
    """Tên thư mục đọc được trong Explorer: tên sách (bỏ ký tự Windows cấm) + 8 ký tự đầu của khoá nội dung."""
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", title or "").strip(" .")
    clean = " ".join(clean.split())[:60].rstrip(" .") or "Sách"
    return f"{clean} ({key.removeprefix('f-')[:8]})"


def _write_cover_meta(target: Path, book: dict[str, Any]) -> None:
    """Màu và cỡ bìa đi trong `book.json`; `covers.cover_meta` đọc chúng từ `cover.json` như ở dự án."""
    cover = book.get("cover")
    if isinstance(cover, dict) and (target / covers.COVER_FILE).is_file():
        meta = {key: cover[key] for key in ("color", "width", "height") if cover.get(key)}
        (target / covers.META_FILE).write_text(json.dumps(meta), encoding="utf-8")


def import_file(source: Path, library_root: Path, projects: Iterable[Path],
                fingerprints: Fingerprints) -> tuple[Path, str]:
    """Nhập một file `.abook`. Trả (thư mục cuốn trong thư viện, cách): "project" - file do chính máy này xuất, mở
    dự án ấy; "existing" - đã nhập rồi, bản đã có đủ chương bằng hoặc hơn; "updated" - đã nhập rồi, bản mới nhiều
    chương hơn nên thay tại chỗ; "new" - cuốn mới. File hỏng, bị sửa hay không phải sách: `bookfile.BookFileError`."""
    from . import bookfile

    with bookfile.BookFile(Path(source)) as opened:
        prints = opened.chapter_prints
        for project in projects:
            if fingerprints.shares_a_chapter(project, prints):
                return Path(project), "project"
        imported = Path(library_root).expanduser() / IMPORTED_FOLDER
        for existing in folders(library_root):
            theirs = chapter_prints(manifest(existing))
            if any(theirs.get(name) == meta for name, meta in prints.items()):
                if len(prints) <= len(theirs):
                    return existing, "existing"
                target = opened.extract(imported, existing.name)
                _write_cover_meta(target, opened.book)
                return target.resolve(), "updated"
        target = opened.extract(imported, _folder_name(str(opened.book.get("title") or ""), opened.content_key))
        _write_cover_meta(target, opened.book)
        return target.resolve(), "new"
