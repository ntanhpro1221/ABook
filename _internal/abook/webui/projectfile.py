"""Một dự án Studio trong MỘT file `.abookproj`: chuyển sang máy khác, sao lưu, làm tiếp ở chỗ khác.

`.abook` là sách đã xong để nghe (bookfile.py); `.abookproj` là cả xưởng làm ra nó - sổ dự án, audio đã thu, ứng viên,
nguồn chương, bìa. Mở file là có lại đúng dự án ấy trong thư viện Studio.

`.abook` về mặt logic là TẬP CON của `.abookproj` (chủ sách 02-10): file dự án mang luôn phần NGHE của sách - các chương đã
xong, chữ có tag, dàn nhân vật, câu mẫu, bìa, nhạc nền - nên chỗ nào đọc được `.abook` (điện thoại) thì đọc được phần nghe
của `.abookproj`, không phải xuất thêm một file. Phần nghe là `book.json` đúng như của file `.abook`
(bookfile.listening_layer dựng), chỉ khác: audio chương KHÔNG chép hai lần - `book.json` trỏ thẳng tới mục
`project/output/chapters/<tên>.mp3` đã có trong gói. Máy tính mở file dự án luôn là mở dự án (mở ra là nghe, sửa ở một chỗ).

Hình dạng - một gói ZIP:

    mimetype                 MIMETYPE, mục ĐẦU TIÊN, không nén (như .abook, EPUB)
    project.json             mô tả: phiên bản định dạng, ai làm ra, tên sách, thư mục gốc cũ, nguồn chương, cỡ + mã băm
                             từng file (kể cả phần nghe)
    cover.jpg                bìa, nếu có (bản sao để Explorer hiện thumbnail mà không phải đọc cả dự án)
    project/<đường dẫn>      mọi file của thư mục dự án; `project.sqlite3` là bản chụp nhất quán (SQLite backup), không
                             kèm `-wal`/`-shm`, nhật ký, khoá worker, file `.part` dở hay file `.abook` đã xuất
    sources/<n>_<tên>        nguồn chương nằm NGOÀI thư mục dự án
    book.json                phần nghe (phiên bản 2): như `book.json` của file `.abook`; mục `package.files` liệt kê cỡ + mã
                             băm các file nghe được. Chỉ có khi dự án đã có chương xong lúc đóng gói
    cast.json, scripts/<chương>.json, samples/<câu>.wav, music/<sha1>.mp3
                             như trong file `.abook`; nhạc nền lấy từ bộ đệm của máy (tải khi cần)

Sổ dự án ghi đường dẫn tuyệt đối (chương nguồn, MP3, WAV). Mở ở chỗ mới thì các cột đường dẫn THƯỜNG được viết lại:
gốc dự án cũ -> gốc mới, mỗi nguồn cũ -> chỗ của nó trong `sources/` của dự án mới. Cài đặt đã khoá theo sách
(`settings_json`) và mọi JSON có mã băm thì KHÔNG đụng: đổi chúng là đổi quyển sách (AGENTS.md). Cài đặt ấy có đường
dẫn tới model của Studio - máy khác cài Studio ở chỗ khác thì làm tiếp phần thu âm sẽ báo thiếu model thay vì chạy
sai; nghe, xem kịch bản, xuất sách vẫn được.

Đóng gói chỉ khi dự án không chạy: worker đang ghi thì không có bản chụp nào vừa đúng sổ vừa đúng file.

    python -m abook.webui.projectfile pack <thư mục dự án> [-o file]
    python -m abook.webui.projectfile verify <file>
    python -m abook.webui.projectfile open <file> <thư viện>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import sqlite3
import sys
import tempfile
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from typing import Any, Callable, Self

from . import bookfile, covers, store

EXTENSION = ".abookproj"
MIMETYPE = "application/vnd.ngdtuanh.abookproj+zip"
FORMAT = "abookproj"
# 1 = dự án thuần; 2 = thêm phần nghe (`book.json` + cast/scripts/samples/music). Đọc được cả hai, mới hơn thì từ chối.
FORMAT_VERSION = 2
MANIFEST = "project.json"
MAX_ENTRIES = 1_000_000
MAX_JSON_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024**3
_SKIP_NAMES = {".worker.lock", store.DB_NAME + "-wal", store.DB_NAME + "-shm", store.DB_NAME + "-journal"}
_SKIP_DIRS = {"logs", "__pycache__"}
_SKIP_SUFFIXES = (".part", ".tmp", ".abook", EXTENSION)
_STORED = (".mp3", ".wav", ".jpg", ".png", ".flac", ".ogg", ".opus", ".m4a", ".zip")
_PATH_COLUMNS = {"project_root", "input_path", "output_mp3", "path"}
_PART = re.compile(r"[^\x00-\x1f<>:\"|?*\\/]+")
# Audio chương trong gói: chỗ nó nằm trong thư mục dự án (store.chapter_mp3) - `book.json` của phần nghe trỏ tới đây.
_CHAPTER_AUDIO = re.compile(r"project/output/chapters/[^\x00-\x1f<>:\"|?*\\/]+\.mp3")
_CHUNK = 1024 * 1024


class ProjectFileError(Exception):
    """File không mở hay không gói được như một dự án. Câu chữ để người dùng đọc."""


def default_name(title: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", str(title)).strip(" .") or "Dự án sách nói"
    return " ".join(name.split())[:150] + EXTENSION


def _project_files(project_root: Path) -> list[tuple[str, Path]]:
    """(tên mục, file) của mọi file cần mang theo, trừ sổ dự án (chụp riêng)."""
    found = []
    for folder, dirs, files in os.walk(project_root):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS and not d.startswith("."))
        for name in sorted(files):
            path = Path(folder) / name
            relative = path.relative_to(project_root).as_posix()
            if relative == store.DB_NAME or name in _SKIP_NAMES or name.lower().endswith(_SKIP_SUFFIXES):
                continue
            found.append((f"project/{relative}", path))
    return found


def _sources(database: Path, project_root: Path) -> dict[str, str]:
    """Nguồn chương nằm ngoài thư mục dự án: {đường dẫn cũ: tên mục}."""
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT chapter_index, input_path FROM chapters ORDER BY chapter_index, id").fetchall()
    finally:
        connection.close()
    mapping: dict[str, str] = {}
    for index, value in rows:
        if not value or value in mapping or not _absolute(value) or _under(value, str(project_root)) is not None:
            continue
        name = _PART.fullmatch(PureWindowsPath(value).name) and PureWindowsPath(value).name or "chuong.txt"
        mapping[value] = f"sources/{int(index or 0):05d}_{name}"
    return mapping


def _listening_book(project_root: Path, files: dict[str, Path | bytes],
                    music_track: Callable[[str], Path | None] | None) -> dict[str, Any] | None:
    """Phần nghe của dự án (`book.json` chưa có `package`; các file đi cùng vào `files`), hay None nếu chưa có chương nào
    xong - dự án mới bắt đầu vẫn sao lưu được, chỉ chưa có gì để nghe. Audio chương không chép lại: `book.json` trỏ tới mục
    `project/output/chapters/...` đã có trong `files`."""
    audio = {path.resolve(): name for name, path in files.items()
             if isinstance(path, Path) and _CHAPTER_AUDIO.fullmatch(name)}
    book, layer = bookfile.listening_layer(project_root, music_track, audio_entry=lambda path: audio.get(path.resolve()))
    if not any(chapter.get("file") for chapter in book["chapters"]):
        return None
    files.update(layer)
    return book


def _listening_name(name: str) -> bool:
    """Mục của gói thuộc phần nghe: file như trong `.abook`, hay audio chương nằm trong thư mục dự án."""
    return bookfile.LISTENING_ENTRY.fullmatch(name) is not None or _CHAPTER_AUDIO.fullmatch(name) is not None


def _snapshot(database: Path, target: Path) -> None:
    """Bản chụp nhất quán của sổ dự án (kể cả phần còn trong `-wal`), như một file SQLite thường."""
    source = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    try:
        sink = sqlite3.connect(target)
        try:
            source.backup(sink)
            sink.execute("PRAGMA journal_mode=DELETE")
        finally:
            sink.close()
    finally:
        source.close()


def pack(project_root: Path, out: Path | None = None, *, running: bool = False, producer: str = "ABook",
         music_track: Callable[[str], Path | None] | None = None) -> Path:
    """Gói một dự án thành một file; ghi file tạm cạnh đích rồi thay nguyên tử. Trả đường dẫn file.

    `music_track(link)` -> file một bài nhạc nền (bộ đệm của máy, tải khi cần): có thì phần nghe mang cả nhạc nền
    (bookfile.listening_layer); bài không lấy được thì bỏ khỏi gói, chỗ ấy im lặng - như file `.abook`."""
    project_root = Path(project_root).resolve()
    if not store.is_project(project_root):
        raise ProjectFileError("Thư mục này không phải dự án Studio.")
    if running:
        raise ProjectFileError("Dự án đang chạy. Đóng gói khi nó đã chạy xong hoặc đã dừng.")
    title = store.summarize(project_root, running=False).get("title") or project_root.name
    out = Path(out) if out is not None else project_root.parent / default_name(title)
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_name(f".{out.name}.{secrets.token_hex(4)}.part")
    with tempfile.TemporaryDirectory(prefix="abookproj-") as scratch:
        database = Path(scratch) / store.DB_NAME
        _snapshot(project_root / store.DB_NAME, database)
        files: dict[str, Path | bytes] = {f"project/{store.DB_NAME}": database}
        files.update(_project_files(project_root))
        sources = _sources(database, project_root)
        # Nguồn đã bị dời hay xoá thì vẫn gói (sao lưu không được hỏng vì nó), ghi lại để báo: nghe, xem, xuất vẫn được,
        # chỉ việc phải đọc lại nguồn (làm tiếp phân tích, thu lại chương) mới cần chép nguồn vào.
        missing = [old for old in sources if not Path(old).is_file()]
        sources = {old: entry for old, entry in sources.items() if old not in missing}
        files.update({entry: Path(old) for old, entry in sources.items()})
        cover = covers.cover_file(project_root)
        if cover is not None:
            files[covers.COVER_FILE] = cover
        book = _listening_book(project_root, files, music_track)
        described = {name: bookfile.describe(source) for name, source in sorted(files.items())}
        if book is not None:
            book["package"] = {
                "format": bookfile.FORMAT,
                "version": bookfile.package_version(book),
                "createdAt": datetime.now(UTC).isoformat(timespec="seconds"),
                "producer": producer,
                "files": {name: meta for name, meta in described.items() if _listening_name(name)},
            }
            files[bookfile.MANIFEST] = bookfile.json_bytes(book)
            described[bookfile.MANIFEST] = bookfile.describe(files[bookfile.MANIFEST])
        manifest = {
            "format": FORMAT,
            "version": FORMAT_VERSION,
            "createdAt": datetime.now(UTC).isoformat(timespec="seconds"),
            "producer": producer,
            "title": title,
            "projectRoot": str(project_root),
            "sources": [{"path": old, "entry": entry} for old, entry in sources.items()],
            "missingSources": missing,
            "files": dict(sorted(described.items())),
        }
        try:
            with zipfile.ZipFile(temporary, "w", allowZip64=True) as archive:
                archive.writestr(_entry("mimetype", stored=True), MIMETYPE)
                archive.writestr(_entry(MANIFEST), json.dumps(manifest, ensure_ascii=False, indent=1).encode("utf-8"))
                bookfile.write_entries(archive, files, order=_order, stored_suffixes=_STORED)
            with temporary.open("rb+") as handle:
                os.fsync(handle.fileno())
            os.replace(temporary, out)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    return out


class ProjectFile:
    """Một file dự án đã mở và đã kiểm hình dạng (mã băm: `verify()`; `open_into()` tự kiểm)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        try:
            self._zip = zipfile.ZipFile(self.path)
        except (zipfile.BadZipFile, OSError) as exc:
            raise ProjectFileError("Đây không phải file dự án ABook (không mở được gói).") from exc
        try:
            self.manifest = self._validate()
        except BaseException:
            self._zip.close()
            raise

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._zip.close()

    @property
    def title(self) -> str:
        return str(self.manifest.get("title") or "Dự án sách nói")

    @property
    def missing_sources(self) -> list[str]:
        value = self.manifest.get("missingSources")
        return [str(item) for item in value] if isinstance(value, list) else []

    @property
    def listenable(self) -> bool:
        """Gói có phần nghe (dự án đã có chương xong lúc đóng gói) - điện thoại nhập được."""
        return bookfile.MANIFEST in self.manifest["files"]

    @property
    def size(self) -> int:
        return sum(meta["size"] for meta in self.manifest["files"].values())

    def verify(self) -> None:
        """Mọi file đúng cỡ và mã băm ghi trong `project.json`."""
        for name, expected in self.manifest["files"].items():
            digest = hashlib.sha256()
            size = 0
            with self._zip.open(name) as handle:
                while chunk := handle.read(_CHUNK):
                    digest.update(chunk)
                    size += len(chunk)
            if size != expected["size"] or digest.hexdigest() != expected["sha256"]:
                raise ProjectFileError(f"File dự án bị hỏng hoặc bị sửa ({name}). Hãy chép lại file từ nguồn.")

    def open_into(self, library: Path) -> tuple[Path, dict[str, Any]]:
        """Kiểm, giải nén vào một thư mục MỚI trong `library` (không bao giờ đè dự án đang có), viết lại đường dẫn
        trong sổ dự án. Thư mục tạm rồi đổi tên: hỏng giữa chừng không để lại nửa dự án. Trả (thư mục, báo cáo)."""
        library = Path(library)
        library.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(library).free < self.size * 1.05 + 64 * 1024**2:
            raise ProjectFileError("Ổ đĩa của thư viện không đủ chỗ cho dự án này.")
        self.verify()
        target = _free_folder(library, default_name(self.title)[: -len(EXTENSION)])
        staging = library / f".{target.name}.{secrets.token_hex(4)}.part"
        try:
            for name in self.manifest["files"]:
                if name.startswith("project/"):
                    destination = staging.joinpath(*name.split("/")[1:])
                elif name.startswith("sources/"):
                    destination = staging.joinpath(*name.split("/"))
                else:
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                with self._zip.open(name) as source, destination.open("wb") as sink:
                    shutil.copyfileobj(source, sink, _CHUNK)
            sources = {item["path"]: str(target.joinpath(*item["entry"].split("/")))
                       for item in self.manifest["sources"]}
            report = relocate(staging / store.DB_NAME, str(self.manifest["projectRoot"]), str(target), sources)
            os.replace(staging, target)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return target, report

    def copy_music(self, into: Path) -> int:
        """Chép các bài nhạc nền của gói vào bộ đệm nhạc của máy (`into/<sha1>.mp3`, bài đã có thì giữ): dự án mở ra phát
        lại nhạc ngay cả khi máy này không có mạng. Gọi sau `open_into` (đã kiểm mã băm). Trả số bài vừa chép."""
        copied = 0
        for name in self.manifest["files"]:
            if not name.startswith("music/"):
                continue
            target = Path(into) / name.split("/", 1)[1]
            if target.is_file():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            staging = target.with_name(f".{target.name}.{secrets.token_hex(4)}.part")
            try:
                with self._zip.open(name) as source, staging.open("wb") as sink:
                    shutil.copyfileobj(source, sink, _CHUNK)
                os.replace(staging, target)
            finally:
                staging.unlink(missing_ok=True)
            copied += 1
        return copied

    def _validate(self) -> dict[str, Any]:
        infos = self._zip.infolist()
        if not infos or infos[0].filename != "mimetype" or infos[0].compress_type != zipfile.ZIP_STORED:
            raise ProjectFileError("Đây không phải file dự án ABook.")
        if self._zip.read("mimetype").decode("ascii", "replace").strip() != MIMETYPE:
            raise ProjectFileError("Đây không phải file dự án ABook.")
        if len(infos) > MAX_ENTRIES:
            raise ProjectFileError("File dự án có quá nhiều mục.")
        names: set[str] = set()
        total = 0
        for info in infos:
            name = info.filename
            if name in names or info.is_dir():
                raise ProjectFileError(f"Gói có mục trùng hay thư mục lạ: {name!r}.")
            if name not in ("mimetype", MANIFEST, bookfile.MANIFEST) and not (
                    _listening_name(name) or _safe_entry(name)):
                raise ProjectFileError(f"Gói có mục lạ: {name!r}.")
            names.add(name)
            total += info.file_size
        if total > MAX_TOTAL_BYTES:
            raise ProjectFileError("File dự án quá lớn.")
        if MANIFEST not in names:
            raise ProjectFileError("File dự án thiếu phần mô tả (project.json).")
        if self._zip.getinfo(MANIFEST).file_size > MAX_JSON_BYTES:
            raise ProjectFileError("project.json quá lớn.")
        try:
            manifest = json.loads(self._zip.read(MANIFEST).decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ProjectFileError("project.json hỏng.") from exc
        if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
            raise ProjectFileError("Đây không phải file dự án ABook.")
        version = manifest.get("version")
        if not isinstance(version, int) or version < 1:
            raise ProjectFileError("File dự án có phiên bản định dạng không hợp lệ.")
        if version > FORMAT_VERSION:
            raise ProjectFileError("Dự án này được gói bằng bản app mới hơn. Hãy cập nhật app để mở.")
        files = manifest.get("files")
        content = names - {"mimetype", MANIFEST}
        if not isinstance(files, dict) or set(files) != content:
            raise ProjectFileError("Danh sách file trong dự án không khớp nội dung gói.")
        for name, meta in files.items():
            if (not isinstance(meta, dict) or self._zip.getinfo(name).file_size != meta.get("size")
                    or not isinstance(meta.get("sha256"), str)):
                raise ProjectFileError(f"Mô tả file {name!r} không khớp gói.")
        if f"project/{store.DB_NAME}" not in content or f"project/{store.SETTINGS_NAME}" not in content:
            raise ProjectFileError("File dự án thiếu sổ dự án hay cài đặt sách.")
        sources = manifest.get("sources")
        if not isinstance(sources, list) or not isinstance(manifest.get("projectRoot"), str) or any(
                not isinstance(item, dict) or not isinstance(item.get("path"), str)
                or item.get("entry") not in content or not str(item.get("entry")).startswith("sources/")
                for item in sources):
            raise ProjectFileError("Mô tả nguồn chương trong dự án không hợp lệ.")
        if bookfile.MANIFEST in content:
            self._check_listening(manifest, content)
        return manifest

    def _check_listening(self, manifest: dict[str, Any], content: set[str]) -> None:
        """Phần nghe (`book.json`) khớp phần còn lại của gói: mọi file nó kể có trong gói với đúng cỡ + mã băm ghi ở
        `project.json`, mọi file nghe được trong gói đều được kể, và chương nào cũng trỏ tới audio có thật."""
        if self._zip.getinfo(bookfile.MANIFEST).file_size > MAX_JSON_BYTES:
            raise ProjectFileError("book.json quá lớn.")
        try:
            book = json.loads(self._zip.read(bookfile.MANIFEST).decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ProjectFileError("book.json hỏng.") from exc
        package = book.get("package") if isinstance(book, dict) else None
        listed = package.get("files") if isinstance(package, dict) else None
        if not isinstance(listed, dict) or package.get("format") != bookfile.FORMAT:
            raise ProjectFileError("Phần nghe của dự án (book.json) không hợp lệ.")
        listening = {name for name in content if _listening_name(name)}
        if set(listed) != listening or any(
                not isinstance(meta, dict) or meta != manifest["files"][name] for name, meta in listed.items()):
            raise ProjectFileError("Phần nghe của dự án không khớp nội dung gói.")
        for chapter in book.get("chapters") or []:
            reference = chapter.get("file") if isinstance(chapter, dict) else None
            if reference and reference not in listed:
                raise ProjectFileError("Phần nghe của dự án thiếu audio của một chương.")


def relocate(database: Path, old_root: str, new_root: str, sources: dict[str, str]) -> dict[str, Any]:
    """Viết lại các cột đường dẫn thường của sổ dự án: nguồn cũ -> nguồn mới, gốc cũ -> gốc mới. Không đụng JSON.
    Trả số ô đã đổi và số đường dẫn tuyệt đối còn trỏ ra ngoài (đường dẫn tới model, file nằm chỗ lạ)."""
    changed = 0
    outside = 0
    connection = sqlite3.connect(database)
    try:
        with connection:
            row = connection.execute("SELECT project_root FROM book LIMIT 1").fetchone() if _has_column(
                connection, "book", "project_root") else None
            roots = [value for value in {old_root, row[0] if row and row[0] else old_root} if value]
            tables = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            for table in tables:
                columns = [r[1] for r in connection.execute(f'PRAGMA table_info("{table}")')]
                for column in columns:
                    if column not in _PATH_COLUMNS and not column.endswith("_path"):
                        continue
                    updates = []
                    for rowid, value in connection.execute(f'SELECT rowid, "{column}" FROM "{table}"'):
                        if not isinstance(value, str) or not value:
                            continue
                        moved = sources.get(value) if column == "input_path" else None
                        if moved is None:
                            for root in roots:
                                rest = _under(value, root)
                                if rest is not None:
                                    moved = str(Path(new_root).joinpath(*rest)) if rest else new_root
                                    break
                        if moved is not None and moved != value:
                            updates.append((moved, rowid))
                        elif moved is None and _absolute(value):
                            outside += 1
                    connection.executemany(f'UPDATE "{table}" SET "{column}" = ? WHERE rowid = ?', updates)
                    changed += len(updates)
    finally:
        connection.close()
    return {"changed": changed, "outside": outside}


def _has_column(connection: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in connection.execute(f'PRAGMA table_info("{table}")'))


def _absolute(value: str) -> bool:
    return PureWindowsPath(value).is_absolute() or value.startswith("/")


def _under(value: str, root: str) -> list[str] | None:
    """Các phần của `value` sau `root` nếu nằm trong `root` (so như Windows: không phân biệt hoa thường, / hay \\)."""
    path = PureWindowsPath(value)
    base = PureWindowsPath(root)
    if not path.is_absolute() or not base.is_absolute():
        return None
    parts = [part.lower() for part in path.parts]
    prefix = [part.lower() for part in base.parts]
    if parts[: len(prefix)] != prefix:
        return None
    return list(path.parts[len(prefix):])


def _safe_entry(name: str) -> bool:
    parts = name.split("/")
    return (len(parts) >= 2 and parts[0] in ("project", "sources") and all(_PART.fullmatch(part) for part in parts[1:])
            and not any(part in (".", "..") for part in parts) and (parts[0] != "sources" or len(parts) == 2))


def _free_folder(library: Path, name: str) -> Path:
    name = name.strip(" .") or "Dự án sách nói"
    candidate = library / name
    number = 2
    while candidate.exists():
        candidate = library / f"{name} ({number})"
        number += 1
    return candidate


def _order(name: str) -> tuple[int, str]:
    """Mô tả, bìa, sổ dự án và chữ trước; audio sau cùng."""
    if name in (covers.COVER_FILE, bookfile.MANIFEST):
        return 0, name
    if name == f"project/{store.DB_NAME}":
        return 1, name
    if name.lower().endswith(_STORED):
        return 3, name
    return 2, name


def _entry(name: str, *, stored: bool = False) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=time.localtime()[:6])
    info.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
    return info


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    pack_command = commands.add_parser("pack", help="gói một dự án thành một file")
    pack_command.add_argument("project", type=Path)
    pack_command.add_argument("-o", "--out", type=Path, default=None)
    commands.add_parser("verify").add_argument("file", type=Path)
    open_command = commands.add_parser("open", help="mở một file dự án vào thư viện")
    open_command.add_argument("file", type=Path)
    open_command.add_argument("library", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "pack":
            packed = pack(args.project, args.out)
            with ProjectFile(packed) as project:
                for missing in project.missing_sources:
                    print(f"thiếu nguồn (không gói): {missing}", file=sys.stderr)
            print(packed)
            return 0
        with ProjectFile(args.file) as project:
            if args.command == "verify":
                project.verify()
                print(f"{project.title} · {len(project.manifest['files'])} file · {project.size} byte · mã băm khớp"
                      f"{f' · thiếu {len(project.missing_sources)} nguồn' if project.missing_sources else ''}")
            else:
                target, report = project.open_into(args.library)
                print(f"{target} · đổi {report['changed']} đường dẫn · {report['outside']} đường dẫn trỏ ra ngoài")
        return 0
    except ProjectFileError as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
