"""Sách nhập từ file (`.abook` / `.abookproj`, nút "Thêm sách") chia sẻ cho máy đã ghép - điện thoại và máy tính khác.

Dự án Studio vốn đã đi qua cổng đồng bộ (sync.py `manifest`, `resolve_file`). Cuốn nhập từ file thì không có dự án phía sau, nhưng
`book.json` của nó cùng định dạng với bản `sync.manifest` dựng - nên ở đây chỉ việc đọc gói (packages.py, kèm lớp sửa của người nghe:
tên sách, tên chương, tên nhân vật, bìa, nhạc) và trả đúng hình dạng ấy; máy kia nghe cuốn này y như cuốn của một dự án.

Chỉ cuốn dưới `Sách đã nhập/` được chia sẻ (library.imported_packages), không cuốn ảo của máy khác (`Trên máy khác/`): máy A mà soi
lại bản soi của B thì B thấy sách của chính mình hai lần, rồi lại soi tiếp.

Phần sửa từ máy kia gửi lên một cuốn nhập từ file cũng không cần Studio: nó nhập vào chính lớp sửa của cuốn (book_edits.adopt, bản đến sau
thắng) - tên, bìa, nhạc áp ngay; ý muốn chờ Studio (cách đọc, giọng...) nằm trong lớp sửa ấy và đi theo cuốn khi lưu thành file.
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from . import book_edits, covers, edits_inbox, listen_view, music_plan, packages


_WHAT = {"title": "Tên sách", "cover": "Ảnh bìa", "character": "Tên nhân vật", "chapter": "Tên chương", "reading": "Cách đọc",
         "music": "Nhạc nền", "wish": "Việc chờ Studio"}


def _cover_meta(path: Path, book: dict[str, Any]) -> dict[str, Any] | None:
    """Màu và phiên bản của bìa người nghe thấy (đã qua lớp sửa); sách không bìa, hay đã bỏ bìa: None."""
    cover = book.get("cover")
    if not isinstance(cover, dict) or book_edits.cover_file(path) is None:
        return None
    return {key: cover[key] for key in ("color", "width", "height", "version") if key in cover}


def library_entry(path: Path, key: str, state: dict[str, Any]) -> dict[str, Any]:
    """Một dòng của `/sync/v1/library` (cùng khoá với dự án - sync.SyncApp.library_view)."""
    view = packages.listen(path, key, state, with_chapters=False)
    entry = {name: view[name] for name in ("id", "title", "narrator", "duration", "chaptersTotal", "chaptersAvailable",
                                           "complete", "updatedAt")}
    entry["series"] = None
    if view.get("author"):
        entry["author"] = view["author"]  # tìm và sắp theo tác giả ở máy kia cần nó; dự án Studio không có tác giả nên không mang khoá
    meta = _cover_meta(path, packages.edited_manifest(path))
    entry["cover"] = {"color": meta.get("color", ""), "version": meta.get("version", 0)} if meta else None
    return entry


def _chapter(path: Path, chapter: dict[str, Any]) -> dict[str, Any]:
    """Một chương của book.json như `sync.manifest` dựng: `file` / `size` theo file CÓ trên đĩa, `script` / `text` chỉ khi file có."""
    item = {name: value for name, value in chapter.items() if name != "skip"}  # dòng bỏ khỏi phần đọc là sở thích của người nghe ở máy này
    audio = packages.chapter_file(path, chapter.get("id"))
    item["available"] = audio is not None
    item["size"] = audio.stat().st_size if audio is not None else 0
    if audio is not None:
        item["file"] = chapter["file"]
    elif chapter.get("text"):
        item.pop("file", None)  # chương chỉ-chữ không mang khoá `file` (sync.text_layer)
    else:
        item["file"] = None
    for name in ("script", "text"):
        if name in item and not packages.has(path, item[name]):
            item.pop(name)
    if item.get("state") == packages.TEXT_STATE and "text" not in item:
        item.pop("state")
    return item


def manifest(path: Path, key: str) -> dict[str, Any]:
    """`book.json` của cuốn nhập từ file như máy đã ghép đọc: hình dạng của `sync.manifest`, dựng từ lớp sách cộng lớp sửa."""
    book = packages.edited_manifest(path)
    edits = book_edits.load(path)
    view = packages.listen(path, key, {}, with_chapters=False)
    chapters = [_chapter(path, chapter) for chapter in book.get("chapters") or [] if isinstance(chapter, dict)]
    samples = [name for name in book.get("samples") or [] if isinstance(name, str) and packages.has(path, name)]
    meta = _cover_meta(path, book)
    music = copy.deepcopy(book.get("music")) if isinstance(book.get("music"), dict) else None
    for name, info in (music.get("tracks") or {}).items() if music and isinstance(music.get("tracks"), dict) else ():
        file = packages.music_file(path, name)
        if file is not None and isinstance(info, dict):
            info["size"] = file.stat().st_size  # cỡ từng file bài để bên tải kiểm (như sync.manifest)
    # Phiên bản đổi khi lớp sách (phiên bản lúc đóng gói), danh sách file có thật, hay lớp sửa đổi: máy đã tải thấy "có cập nhật".
    version = hashlib.sha256(json.dumps(
        [book.get("version"), [(chapter["id"], chapter["size"]) for chapter in chapters],
         hashlib.sha256(book_edits.dump(edits)).hexdigest() if not book_edits.is_empty(edits) else ""],
        sort_keys=True).encode()).hexdigest()[:16]
    return {
        "format": listen_view.FORMAT,
        "id": key,
        "title": view["title"],
        **({"author": view["author"]} if view.get("author") else {}),
        "narrator": view["narrator"],
        "duration": view["duration"],
        "chaptersTotal": view["chaptersTotal"],
        "chaptersAvailable": sum(1 for chapter in chapters if chapter["available"]),
        "complete": view["complete"],
        "series": None,
        "version": version,
        "chapters": chapters,
        "cast": "cast.json",
        "samples": samples,
        "cover": {**meta, "file": covers.COVER_FILE} if meta else None,
        **({"music": music} if music else {}),
    }


def _shared_cast(path: Path) -> bytes:
    """`cast.json` như người nghe thấy (tên nhân vật đã đổi), không dấu "đang chờ đổi giọng" - ý muốn ấy là của máy này, chưa thành giọng nào."""
    cast = copy.deepcopy(packages.cast(path))
    if isinstance(cast, dict):
        for kind in ("characters", "extras", "carried"):
            for person in cast.get(kind) or []:
                if isinstance(person, dict) and "pendingVoice" in person:
                    person["pendingVoice"] = None  # như cast.json của dự án: khoá có, không đang chờ gì
    return json.dumps(cast, ensure_ascii=False).encode("utf-8")


def resolve_file(path: Path, relative: str) -> Path | bytes | None:
    """File của gói mà máy đã ghép xin: chỉ tên có trong `manifest` vừa dựng (không có tên nào ngoài đó, kể cả file có trên đĩa); chữ đọc theo và
    dàn nhân vật là bản đã qua lớp sửa."""
    if relative == "cast.json":
        return _shared_cast(path)
    if relative == covers.COVER_FILE:
        return book_edits.cover_file(path)
    if music_plan.TRACK_FILE.fullmatch(relative):
        return packages.music_file(path, relative)
    book = packages.edited_manifest(path)
    if relative in (book.get("samples") or []):
        return packages.sample_file(path, int(relative.split("/")[1].split(".")[0]))
    for chapter in book.get("chapters") or []:
        if not isinstance(chapter, dict) or not isinstance(chapter.get("id"), int):
            continue
        if chapter.get("file") == relative:
            return packages.chapter_file(path, chapter["id"])
        if chapter.get("script") == relative:
            script = packages.script(path, chapter["id"])
            return json.dumps(script, ensure_ascii=False).encode("utf-8") if script else None
        if chapter.get("text") == relative:
            text = packages.chapter_text(path, chapter["id"])
            return text.encode("utf-8") if text and text.strip() else None
    return None


def receive_edits(path: Path, device: dict[str, Any], package: Path) -> dict[str, Any]:
    """Phần sửa máy đã ghép gửi lên một cuốn nhập từ file (gói zip - edits_inbox.read_package kiểm): nhập vào lớp sửa của cuốn, bản gửi tới
    thắng khi hai bên cùng đặt một khoá (xung đột được báo). Không có dự án để áp: ý muốn chờ Studio (`waiting`) nằm trong lớp sửa, đi theo cuốn khi
    lưu thành file. Cùng hình dạng trả lời với `edits_inbox.receive`."""
    edits, cover, tracks = edits_inbox.read_package(package)
    scratch = Path(tempfile.mkdtemp(prefix=".edits_in_", dir=path))
    try:
        if tracks:
            edits_inbox.extract(package, tracks, scratch)
        report = book_edits.adopt(path, edits, cover,
                                  lambda name, _target: book_edits.place(path, name, scratch / name.rpartition("/")[2]),
                                  incoming_wins=True)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    conflicts = [edits_inbox.conflict(item["kind"], item["key"], _WHAT[item["kind"]],
                                      f"{_WHAT[item['kind']]}: đã có bản riêng trên máy tính này, đã thay bằng bản từ {device['name']}",
                                      item["lost"], item["kept"]) for item in report["clashes"]]
    return {"applied": book_edits.count_applied(edits), "skipped": 0, "music": False, "requests": 0,
            "waiting": book_edits.count_wishes(edits), "skippedWishes": 0, "conflicts": conflicts}
