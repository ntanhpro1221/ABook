"""Dựng file `.abook` / `.abookproj` tay (độc hay lành) cho soát a81: mở file của người lạ phải từ chối rõ hoặc nhận trọn."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import struct
import zipfile
from pathlib import Path
from typing import Any, Callable

from abook.webui.library import Preferences
from abook.webui.listening import Listening
from abook.webui.actions import FakeRunner
from abook.webui.server import App

MIME = "application/vnd.ngdtuanh.abook+zip"
PROJECT_MIME = "application/vnd.ngdtuanh.abookproj+zip"


def sha(data: bytes) -> dict[str, Any]:
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def build(path: Path, entries: dict[str, bytes], book: dict[str, Any] | None = None, *, version: int = 1,
          raw_book: bytes | str | None = None, manifest: bool = True, deflate: tuple[str, ...] = (),
          omit_from_files: tuple[str, ...] = ()) -> Path:
    """Một file sách: `entries` là ruột (chapters/..., cast.json...), `book` là book.json (chưa có `package`). `manifest=False`: không có
    manifest.json (Readium). `deflate`: các mục nén DEFLATE (mặc định STORED)."""
    book = dict(book if book is not None else {"title": "T", "chapters": [], "chaptersTotal": 0})
    book["package"] = {"format": "abook", "version": version, "createdAt": "2026-01-01T00:00:00+00:00", "producer": "x",
                       "files": {name: sha(data) for name, data in entries.items() if name not in omit_from_files}}
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(zipfile.ZipInfo("mimetype"), MIME)
        archive.writestr("book.json", raw_book if raw_book is not None else json.dumps(book))
        if manifest:
            archive.writestr("manifest.json", "{}")
        for name, data in entries.items():
            archive.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED if name in deflate else zipfile.ZIP_STORED)
    return path


def simple_book(chapters: int = 1, title: str = "Sách thử") -> tuple[dict[str, Any], dict[str, bytes]]:
    entries: dict[str, bytes] = {}
    items = []
    for number in range(1, chapters + 1):
        entries[f"chapters/{number:03d}.mp3"] = b"ID3" + bytes([number]) * 100
        items.append({"id": number, "index": number, "title": f"Chương {number}", "file": f"chapters/{number:03d}.mp3",
                      "available": True, "duration": 1.0})
    book = {"title": title, "narrator": "A", "chaptersTotal": chapters, "chaptersAvailable": chapters, "complete": True,
            "duration": float(chapters), "chapters": items, "cast": "cast.json", "samples": [], "cover": None}
    entries["cast.json"] = json.dumps({"narrator": {"voice": "", "lines": 0, "seconds": 0}, "characters": [], "extras": []}).encode()
    return book, entries


def patch_header(source: Path, target: Path, name: str, *, method: int | None = None, flags: int | None = None) -> Path:
    """Sửa phương pháp nén / cờ của mục `name` trong cả header cục bộ lẫn thư mục trung tâm."""
    data = bytearray(source.read_bytes())
    for signature in (b"PK\x03\x04", b"PK\x01\x02"):
        local = signature == b"PK\x03\x04"
        position = 0
        while True:
            position = data.find(signature, position)
            if position < 0:
                break
            length = struct.unpack_from("<H", data, position + (26 if local else 28))[0]
            offset = position + (30 if local else 46)
            if bytes(data[offset:offset + length]) == name.encode():
                if method is not None:
                    struct.pack_into("<H", data, position + (8 if local else 10), method)
                if flags is not None:
                    struct.pack_into("<H", data, position + (6 if local else 8), flags)
            position += 4
    target.write_bytes(bytes(data))
    return target


def build_project(path: Path, entries: dict[str, bytes], *, workshop: str = "present", title: str = "Dự án thử",
                  files_extra: dict[str, Any] | None = None, version: int = 3) -> Path:
    files = {name: sha(data) for name, data in entries.items()}
    files.update(files_extra or {})
    manifest = {"format": "abookproj", "version": version, "createdAt": "2026-01-01T00:00:00+00:00", "producer": "x",
                "title": title, "workshop": workshop, "projectRoot": "C:/Users/friend/ABook/proj", "sources": [],
                "missingSources": [], "aliases": {}, "files": files}
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(zipfile.ZipInfo("mimetype"), PROJECT_MIME)
        archive.writestr("project.json", json.dumps(manifest))
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def sqlite_bytes(path: Path, user_version: int | None = None) -> bytes:
    from abook.database import ProjectDB

    ProjectDB(path)
    if user_version is not None:
        connection = sqlite3.connect(path)
        connection.execute(f"PRAGMA user_version={user_version}")
        connection.commit()
        connection.close()
    return path.read_bytes()


def app_in(tmp_path: Path, library_root: Path) -> App:
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(library_root)})
    return App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "listening.json"))


Mutate = Callable[[dict[str, Any]], None]


def build_pending_project(path: Path, entries: dict[str, bytes], book: dict[str, Any] | None = None, *,
                          deflate: tuple[str, ...] = (), extra: dict[str, bytes] | None = None) -> Path:
    """`.abookproj` chưa có xưởng (`workshop: pending`): chỉ phần nghe `entries` + book.json. `deflate`: các mục nén DEFLATE."""
    if book is None:
        book, _ = simple_book(1)
    book = dict(book)
    book["package"] = {"format": "abook", "version": 5, "createdAt": "2026-01-01T00:00:00+00:00", "producer": "x",
                       "files": {name: sha(data) for name, data in entries.items()}}
    raw = json.dumps(book).encode("utf-8")
    everything = {**entries, **(extra or {}), "book.json": raw}
    manifest = {"format": "abookproj", "version": 3, "createdAt": "2026-01-01T00:00:00+00:00", "producer": "x", "title": "Dự án thử",
                "workshop": "pending", "projectRoot": "C:/Users/friend/ABook/proj", "sources": [], "missingSources": [],
                "aliases": {}, "files": {name: sha(data) for name, data in everything.items()}}
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(zipfile.ZipInfo("mimetype"), PROJECT_MIME)
        archive.writestr("project.json", json.dumps(manifest))
        for name, data in everything.items():
            archive.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED if name in deflate else zipfile.ZIP_STORED)
    return path


CASES = Path(__file__).parent / "fixtures" / "book_files" / "cases.json"


def golden_cases() -> list[dict[str, Any]]:
    """Bộ file sách DÙNG CHUNG với JVM (BookFileGoldenTest): cùng một file, cùng một phán quyết ở cả hai nền."""
    return json.loads(CASES.read_text(encoding="utf-8"))["cases"]


def build_golden(path: Path, case: dict[str, Any]) -> Path:
    entries = {name: bytes(data["zeros"]) if isinstance(data, dict) else data.encode("utf-8") for name, data in case["entries"].items()}
    return build(path, entries, case["book"], version=case.get("version", 1), manifest=case.get("manifest", True),
                 deflate=tuple(case.get("deflate", ())), omit_from_files=tuple(case.get("omitFromFiles", ())))
