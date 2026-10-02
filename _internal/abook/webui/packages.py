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
from .. import continuation
from .fingerprints import Fingerprints, base_name
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
    """Các cuốn đã nhập dưới `<thư viện>/Sách đã nhập/` (bỏ thư mục tạm của lần giải nén đang dở: tên bắt đầu bằng "."),
    và các cuốn ảo của máy tính khác dưới `<thư viện>/Trên máy khác/<máy>/` (remote_books.py)."""
    from .remote_books import REMOTE_FOLDER

    root = Path(library_root).expanduser()
    candidates: list[Path] = []
    try:
        imported = root / IMPORTED_FOLDER
        candidates += sorted(imported.iterdir()) if imported.is_dir() else []
        remote = root / REMOTE_FOLDER
        for computer in sorted(remote.iterdir()) if remote.is_dir() else []:
            candidates += sorted(computer.iterdir()) if computer.is_dir() else []
    except OSError:
        return []
    return [child.resolve() for child in candidates if child.is_dir() and not child.name.startswith(".") and is_package(child)]


def chapter_prints(book: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Cỡ + mã băm audio từng chương, ghi trong gói lúc xuất (như `BookFile.chapter_prints`)."""
    files = (book.get("package") or {}).get("files") or {}
    return {name: {"size": meta.get("size"), "sha256": meta.get("sha256")}
            for name, meta in files.items() if name.startswith("chapters/") and isinstance(meta, dict)}


def _prints_by_file(prints: dict[str, dict[str, Any]]) -> set[tuple[str, Any, Any]]:
    """Chương theo (tên file, cỡ, mã băm), không kể thư mục phần: cuốn nhập từ file một phần và file cả bộ đặt cùng một
    audio ở hai đường dẫn khác nhau mà vẫn là một lần sản xuất."""
    return {(base_name(name), meta.get("size"), meta.get("sha256")) for name, meta in prints.items()}


def _inside(root: Path, relative: Any) -> Path | None:
    """Đường dẫn trong gói - tên lấy từ `book.json`, nên không cho nó trỏ ra ngoài thư mục của cuốn."""
    if not isinstance(relative, str) or not relative:
        return None
    root = Path(root).resolve()
    candidate = (root / relative).resolve()
    return candidate if candidate.is_file() and candidate.is_relative_to(root) else None


def _file(path: Path, relative: Any) -> Path | None:
    """File trong gói; sách của máy tính khác thì tải về lần đầu cần tới (remote_books.fetch) rồi dùng như file đã có."""
    found = _inside(path, relative)
    if found is not None or not isinstance(relative, str):
        return found
    from .remote_books import fetch, remote_of

    book = manifest(path)
    if remote_of(book) is None:
        return None
    fetch(path, relative, book)
    return _inside(path, relative)


def music_file(path: Path, name: str) -> Path | None:
    """File nhạc nền mang theo trong gói (music/<sha1>.mp3, chỉ tên có trong mục `music` của book.json)."""
    from .music_plan import TRACK_FILE

    music = manifest(path).get("music")
    tracks = music.get("tracks") if isinstance(music, dict) else None
    if not TRACK_FILE.fullmatch(name) or not isinstance(tracks, dict) or name not in tracks:
        return None
    return _file(path, name)


def _remote(path: Path) -> bool:
    from .remote_books import remote_of

    return remote_of(manifest(path)) is not None


def _chapter(book: dict[str, Any], chapter_id: int) -> dict[str, Any] | None:
    return next((chapter for chapter in book.get("chapters") or []
                 if isinstance(chapter, dict) and chapter.get("id") == chapter_id), None)


def chapter_file(path: Path, chapter_id: int) -> Path | None:
    chapter = _chapter(manifest(path), chapter_id)
    return _file(path, chapter.get("file")) if chapter and chapter.get("available") else None


def sample_file(path: Path, sample_id: int) -> Path | None:
    name = f"samples/{int(sample_id)}.wav"
    return _file(path, name) if name in (manifest(path).get("samples") or []) else None


def script(path: Path, chapter_id: int) -> Any | None:
    chapter = _chapter(manifest(path), chapter_id)
    file = _file(path, chapter.get("script")) if chapter else None
    return json.loads(file.read_text(encoding="utf-8")) if file else None


def cast(path: Path) -> Any:
    file = _file(path, manifest(path).get("cast") or "cast.json")
    return json.loads(file.read_text(encoding="utf-8")) if file else {"characters": [], "extras": []}


def listen(path: Path, book_id: str, state: dict[str, Any], *, with_chapters: bool = True) -> dict[str, Any]:
    """Cùng hình dạng với `listen_view.book` của một dự án - giao diện Nghe không phân biệt hai loại."""
    book = manifest(path)
    remote = _remote(path)
    items = []
    for chapter in book.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        # Sách của máy tính khác: chương máy kia có là nghe được - file tải về lúc bấm nghe.
        available = bool(chapter.get("available")) and (remote or _inside(path, chapter.get("file")) is not None)
        items.append({
            "id": chapter.get("id"),
            "index": chapter.get("index"),
            "title": chapter.get("title") or "",
            "subtitle": chapter.get("subtitle") or "",
            "fullTitle": chapter.get("fullTitle") or chapter.get("title") or "",
            "duration": round(float(chapter.get("duration") or 0), 1) if available else 0.0,
            "available": available,
            "part": chapter.get("part") if isinstance(chapter.get("part"), int) else None,
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
        "remote": _remote_view(book) if remote else None,
        "updatedAt": (Path(path) / MANIFEST).stat().st_mtime,
        "state": state,
        "progress": book_progress(state, available, complete=complete),
        "cover": covers.cover_view(Path(path), book_id),
        "lastChapterTitle": next((chapter["fullTitle"] for chapter in items
                                  if chapter["id"] == (state.get("last") or {}).get("chapterId")), ""),
        # Cả bộ trong một file (bookfile.pack_series): các phần theo thứ tự; sách một phần thì rỗng.
        "parts": _parts(book),
    }
    if with_chapters:
        result["chapters"] = items
    return result


def _parts(book: dict[str, Any]) -> list[dict[str, Any]]:
    """Mục `parts` của book.json, chỉ giữ những gì giao diện dùng (số phần, tên, mã chương đầu/cuối, thời lượng, người đọc)."""
    out = []
    for part in book.get("parts") or []:
        span = part.get("chapters") if isinstance(part, dict) else None
        if not isinstance(span, list) or len(span) != 2 or not isinstance(part.get("part"), int):
            continue
        out.append({"part": part["part"], "title": str(part.get("title") or ""), "chapters": span,
                    "duration": float(part.get("duration") or 0), "narrator": str(part.get("narrator") or "")})
    return out


def _remote_view(book: dict[str, Any]) -> dict[str, Any]:
    from .remote_books import computer_name, remote_of

    # `device`: máy đã ghép giữ cuốn này - "Phát trên <máy ấy>" chỉ hiện với đúng máy phát được nó.
    return {"computer": computer_name(book), "device": (remote_of(book) or {}).get("computer", "")}


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
        # File cả bộ chung chương với nhiều dự án (mỗi phần một dự án): mở phần đầu của bộ.
        mine = [project for project in projects if fingerprints.shares_a_chapter(project, prints)]
        if mine:
            return Path(min(mine, key=continuation.part_number)), "project"
        imported = Path(library_root).expanduser() / IMPORTED_FOLDER
        wanted = _prints_by_file(prints)
        for existing in folders(library_root):
            theirs = chapter_prints(manifest(existing))
            if wanted & _prints_by_file(theirs):
                if len(prints) <= len(theirs):
                    return existing, "existing"
                target = opened.extract(imported, existing.name)
                _write_cover_meta(target, opened.book)
                return target.resolve(), "updated"
        target = opened.extract(imported, _folder_name(str(opened.book.get("title") or ""), opened.content_key))
        _write_cover_meta(target, opened.book)
        return target.resolve(), "new"
