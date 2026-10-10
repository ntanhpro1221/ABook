"""Một dự án Studio trong MỘT file `.abookproj`: chuyển sang máy khác, sao lưu, làm tiếp ở chỗ khác.

`.abook` là sách đã xong để nghe (bookfile.py); `.abookproj` là cả xưởng làm ra nó - sổ dự án, audio đã thu, ứng viên,
nguồn chương, bìa. Mở file là có lại đúng dự án ấy trong thư viện Studio.

`.abook` về mặt logic là TẬP CON của `.abookproj` (chủ sách 02-10): file dự án mang luôn phần NGHE của sách - các chương đã
xong, chữ có tag, dàn nhân vật, câu mẫu, bìa, nhạc nền - nên chỗ nào đọc được `.abook` (điện thoại) thì đọc được phần nghe
của `.abookproj`, không phải xuất thêm một file. Phần nghe có đúng tên mục và `book.json` của file `.abook` (bookfile.
listening_layer dựng). Máy tính có Studio mở file dự án luôn là mở dự án (mở ra là nghe, sửa ở một chỗ).

Phiên bản 3 (03-10, docs/EDITING.md phase P3):

- Không byte nào nằm hai lần. Mục media (`.mp3`, `.wav`, `.jpg`...) trùng cỡ + mã băm với mục khác chỉ là BÍ DANH: `project.json`
  ghi `aliases: {bí danh: mục thật}`, bí danh không có trong gói, người đọc lấy byte của mục thật. Mục thật là mục của phần
  nghe (`chapters/x.mp3` chứ không phải `project/output/chapters/x.mp3`) nên người chỉ nghe không cần biết bí danh là gì.
- `views/work.json`, `casting.json`, `names.json`: bản chụp chỉ đọc của vài màn Studio (project_views.py), để điện thoại hay máy
  chưa cài Studio cho người ta xem mà không mở `project/project.sqlite3`.
- `project.json` có `workshop`: "present" (có `project/`) hay "pending" - cuốn chỉ có phần nghe, được lưu thành `.abookproj` từ
  một `.abook` (hay từ một dự án mà máy không có xưởng); máy có Studio mời "Dựng xưởng" (workshop.py). File pending không có
  `project/`, `sources/` thì tuỳ chọn.
- Phần nghe mang cả lớp sửa của người nghe (`edits.json`, `edits/cover.jpg`, bài nhạc đã ghim - book_edits.py) khi điện thoại hay
  máy không có xưởng sửa rồi lưu. Studio không bao giờ ghi chúng; mở file có chúng ở máy có dự án ấy thì phần sửa được cất chờ
  người dùng đồng ý áp vào dự án ("N thay đổi - áp vào dự án?"), không tạo dự án trùng.

Hình dạng - một gói ZIP:

    mimetype                 MIMETYPE, mục ĐẦU TIÊN, không nén (như .abook, EPUB)
    project.json             mô tả: phiên bản định dạng, ai làm ra, tên sách, workshop, thư mục gốc cũ, nguồn chương, bí danh,
                             cỡ + mã băm từng mục (kể cả bí danh)
    cover.jpg                bìa, nếu có (bản sao để Explorer hiện thumbnail mà không phải đọc cả dự án)
    project/<đường dẫn>      mọi file của thư mục dự án; `project.sqlite3` là bản chụp nhất quán (SQLite backup), không
                             kèm `-wal`/`-shm`, nhật ký, khoá worker, file `.part` dở hay file `.abook` đã xuất
    sources/<n>_<tên>        nguồn chương nằm NGOÀI thư mục dự án
    views/<tên>.json         bản chụp chỉ đọc (project_views.py)
    book.json                phần nghe: như `book.json` của file `.abook`; mục `package.files` liệt kê cỡ + mã băm các mục
                             nghe được. Chỉ có khi dự án đã có chương xong lúc đóng gói
    cast.json, chapters/<tên>.mp3, scripts/<chương>.json, samples/<câu>.wav, music/<sha1>.mp3, edits.json, edits/cover.jpg
                             như trong file `.abook`; nhạc nền lấy từ bộ đệm của máy (tải khi cần)

Sổ dự án ghi đường dẫn tuyệt đối (chương nguồn, MP3, WAV). Mở ở chỗ mới thì các cột đường dẫn THƯỜNG được viết lại:
gốc dự án cũ -> gốc mới, mỗi nguồn cũ -> chỗ của nó trong `sources/` của dự án mới. Cài đặt đã khoá theo sách
(`settings_json`) và mọi JSON có mã băm thì KHÔNG đụng: đổi chúng là đổi quyển sách (AGENTS.md). Cài đặt ấy có đường
dẫn tới model của Studio - máy khác cài Studio ở chỗ khác thì làm tiếp phần thu âm sẽ báo thiếu model thay vì chạy
sai; nghe, xem kịch bản, xuất sách vẫn được.

Đóng gói chỉ khi dự án không chạy: worker đang ghi thì không có bản chụp nào vừa đúng sổ vừa đúng file.

    python -m abook.webui.projectfile pack <thư mục dự án> [-o file]
    python -m abook.webui.projectfile repack <thư mục sách đã nhập> -o file
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

from . import book_edits, bookfile, covers, project_views, store
from .fingerprints import content_key, identity_prints

EXTENSION = ".abookproj"
MIMETYPE = "application/vnd.ngdtuanh.abookproj+zip"
FORMAT = "abookproj"
# 3 = bí danh (không lưu hai lần), views/, `workshop`, lớp sửa của người nghe. Chỉ đọc đúng phiên bản này: app chưa phát hành
# cho ai nên không giữ đường đọc cho định dạng cũ (chủ sách 03-10); mới hơn thì nhắc cập nhật app.
FORMAT_VERSION = 3
PRESENT = "present"
PENDING = "pending"
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
_VIEW = re.compile(r"views/(?:" + "|".join(project_views.VIEWS) + r")\.json")
_CHUNK = 1024 * 1024
# Báo tiến độ đóng gói: progress(pha, đã, tổng) - "prepare" | "listen" (chương) | "views" | "hash" (byte) | "write" (byte). Gọi ở mỗi điểm
# kiểm giữa hai file; ném `export_jobs.Cancelled` từ đó thì việc dừng, file tạm bị dọn, không có file mang tên thật. Không đổi một byte của file ra.
Progress = Callable[[str, int, int], None]


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
                    music_track: Callable[[str], Path | None] | None,
                    progress: Progress | None = None) -> dict[str, Any] | None:
    """Phần nghe của dự án (`book.json` chưa có `package`; các file đi cùng vào `files`), hay None nếu chưa có chương nào
    xong audio và cũng không chương nào còn chữ nguồn để đọc - dự án mới bắt đầu vẫn sao lưu được, chỉ chưa có gì để nghe.
    Chưa có audio nào mà còn chữ: phần nghe là sách chỉ-chữ (`bookfile.listening_layer`)."""
    book, layer = bookfile.listening_layer(project_root, music_track, progress)
    if not any(chapter.get("file") or chapter.get("text") for chapter in book["chapters"]):
        return None
    files.update(layer)
    return book


def listening_name(name: str) -> bool:
    """Mục của gói thuộc phần nghe: đúng tên mục của một file `.abook` (phiên bản mới nhất)."""
    return bookfile.LISTENING_ENTRY.fullmatch(name) is not None


def aliasable(name: str) -> bool:
    return name.lower().endswith(_STORED)


def aliases_for(described: dict[str, dict[str, Any]]) -> dict[str, str]:
    """{bí danh: mục thật}: mục media trùng cỡ + mã băm với mục khác thì chỉ MỘT mục (mục thật) nằm trong gói. Mục thật là mục
    của phần nghe nếu có (không thì mục đứng đầu theo tên) - để người chỉ nghe không phải lần theo bí danh. Cùng luật ở
    BookDocumentWriter.kt."""
    groups: dict[tuple[int, str], list[str]] = {}
    for name, meta in described.items():
        if aliasable(name) and meta["size"] > 0:
            groups.setdefault((meta["size"], meta["sha256"]), []).append(name)
    aliases: dict[str, str] = {}
    for names in groups.values():
        if len(names) > 1:
            keeper = min(names, key=lambda name: (not listening_name(name), name))
            aliases.update({name: keeper for name in names if name != keeper})
    return aliases


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
         music_track: Callable[[str], Path | None] | None = None, progress: Progress | None = None,
         verdicts: dict[str, Any] | None = None) -> Path:
    """Gói một dự án thành một file; ghi file tạm cạnh đích rồi thay nguyên tử. Trả đường dẫn file.

    `music_track(link)` -> file một bài nhạc nền (bộ đệm của máy, tải khi cần): có thì phần nghe mang cả nhạc nền
    (bookfile.listening_layer); bài không lấy được thì bỏ khỏi gói, chỗ ấy im lặng - như file `.abook`.
    `progress`: xem `Progress`. `verdicts`: phán quyết "Cần nghe lại" của máy này cho bản chụp "Việc cần duyệt" (project_views)."""
    def step(phase: str, done: int = 0, total: int = 0) -> None:
        if progress is not None:
            progress(phase, done, total)

    project_root = Path(project_root).resolve()
    if not store.is_project(project_root):
        raise ProjectFileError("Thư mục này không phải dự án Studio.")
    if running:
        raise ProjectFileError("Dự án đang chạy. Đóng gói khi nó đã chạy xong hoặc đã dừng.")
    step("prepare")
    title = store.summarize(project_root, running=False).get("title") or project_root.name
    out = Path(out) if out is not None else project_root.parent / default_name(title)
    out.parent.mkdir(parents=True, exist_ok=True)  # thư mục đích không ghi được thì hỏng NGAY, không sau vài phút băm
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
        step("prepare")
        book = _listening_book(project_root, files, music_track, progress)
        step("views")
        files.update(project_views.snapshot(project_root, None if progress is None else lambda: step("views"), verdicts))
        return _seal(out, files, book, producer=producer, title=title, workshop=PRESENT, project_root=str(project_root),
                     sources=[{"path": old, "entry": entry} for old, entry in sources.items()], missing=missing,
                     version=bookfile.package_version(book) if book is not None else 1, progress=progress)


def repack(folder: Path, out: Path, *, producer: str = "ABook") -> Path:
    """Đóng lại một cuốn ĐÃ NHẬP (thư mục trong thư viện: giải nén từ `.abook`, hay từ `.abookproj` mà máy không mở thành dự án)
    thành file `.abookproj`: lớp sách y nguyên cộng lớp sửa của người nghe (bookfile.book_layer - cùng hàm với `bookfile.repack`),
    `views/`, và phần xưởng nếu cuốn vốn đến từ một dự án (`project.json` + `project/` + `sources/` copy NGUYÊN BYTE, không mở
    sổ dự án). Cuốn không có xưởng (từ `.abook`) ra file `workshop: "pending"`: máy có Studio mời "Dựng xưởng"."""
    folder = Path(folder)
    try:
        book, files, known, edits = bookfile.book_layer(folder)
    except bookfile.BookFileError as exc:
        raise ProjectFileError(str(exc)) from exc
    kept = _kept_manifest(folder)
    sources: list[Any] = []
    missing: list[str] = []
    project_root = ""
    workshop = PENDING
    if kept is not None:
        workshop, project_root, sources, missing = kept["workshop"], kept["projectRoot"], kept["sources"], kept["missingSources"]
        for name, meta in kept["files"].items():
            if not name.startswith(("project/", "sources/")):
                continue
            path = folder.joinpath(*name.split("/"))
            if not path.is_file() and name in kept["aliases"]:
                path = folder.joinpath(*kept["aliases"][name].split("/"))  # bí danh: byte của mục thật, ở đâu đó trong thư mục
            if not path.is_file():
                raise ProjectFileError(f"Thư mục sách thiếu file {name}.")
            files[name], known[name] = path, meta
    for view in project_views.available(folder):
        files[project_views.entry(view)] = folder / project_views.entry(view)
    title = str(book_edits.apply_manifest(book, edits).get("title") or folder.name)
    return _seal(Path(out), files, book, producer=producer, title=title, workshop=workshop, project_root=project_root,
                 sources=sources, missing=missing, version=bookfile.layer_version(book, files, edits), known=known)


def restamp_word_timings(project_root: Path) -> int:
    """Mốc chữ sáng (word_timings/<chương>.json) tin audio chương bằng cỡ + mã băm + MỐC SỬA (word_timing.attach); giải nén
    ra chỗ mới thì mốc sửa của file audio là giờ giải nén, nên toàn bộ mốc chữ bị coi là của audio khác và mất (soát UX
    a20). Audio nào còn đúng cỡ + mã băm đã ghi thì ghi lại mốc sửa mới vào dấu - nội dung y hệt, chỉ khác mốc. Trả số chương
    đã ghi lại dấu. Việc phụ: lỗi nào cũng bỏ qua, dự án vẫn mở được (mốc chữ căn lại được)."""
    from . import word_timing

    done = 0
    try:
        files = sorted((Path(project_root) / word_timing.CACHE_FOLDER).glob("*.json"))
    except OSError:
        return 0
    for file in files:
        try:
            chapter_id = int(file.stem)
            data = json.loads(file.read_text(encoding="utf-8"))
            stamp = data["audio"]
            audio = store.chapter_audio_path(project_root, chapter_id)
            if audio is None or not isinstance(stamp, dict):
                continue
            info = audio.stat()
            if (stamp.get("size") != info.st_size or stamp.get("mtimeNs") == info.st_mtime_ns
                    or stamp.get("sha256") != word_timing.audio_sha256(audio)):
                continue
            data["audio"] = {**stamp, "mtimeNs": info.st_mtime_ns}
            temporary = file.with_name(file.name + ".part")
            temporary.write_bytes(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            os.replace(temporary, file)
            done += 1
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return done


def _kept_manifest(folder: Path) -> dict[str, Any] | None:
    """`project.json` mà `ProjectFile.extract` để lại trong thư mục một cuốn nhập từ `.abookproj` (None: cuốn từ file `.abook`)."""
    try:
        manifest = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(manifest, dict) or manifest.get("workshop") not in (PRESENT, PENDING):
        return None
    files, aliases, sources = manifest.get("files"), manifest.get("aliases"), manifest.get("sources")
    missing = manifest.get("missingSources")
    if (not isinstance(files, dict) or not isinstance(aliases, dict) or not isinstance(sources, list)
            or not isinstance(missing, list) or not isinstance(manifest.get("projectRoot"), str)):
        return None
    return {"workshop": manifest["workshop"], "projectRoot": manifest["projectRoot"], "sources": sources,
            "missingSources": missing, "files": files, "aliases": aliases}


def _described(files: dict[str, Path | bytes], known: dict[str, dict[str, Any]],
               progress: Progress | None = None) -> dict[str, dict[str, Any]]:
    """Cỡ + mã băm từng mục. Cùng một file trên đĩa (audio chương nằm ở `chapters/` lẫn `project/output/chapters/`) chỉ băm một lần.
    `progress("hash", byte đã băm, tổng byte)` trước mỗi file mới."""
    by_path: dict[str, dict[str, Any]] = {}
    out: dict[str, dict[str, Any]] = {}
    ordered = sorted(files.items())
    keys = {name: os.path.normcase(str(source.resolve())) for name, source in ordered if isinstance(source, Path)}
    total = done = 0
    if progress is not None:  # tổng byte các file trên đĩa (mỗi file một lần) để thanh tiến độ có mẫu số
        for key in set(keys.values()):
            total += Path(key).stat().st_size
    for name, source in ordered:
        if not isinstance(source, Path):
            out[name] = bookfile.describe(source)
            continue
        key = keys[name]
        if key not in by_path:
            if progress is not None:
                progress("hash", done, total)
            by_path[key] = bookfile.described(name, source, known, None if progress is None else (lambda inside, at=done: progress("hash", at + inside, total)))
            done += by_path[key]["size"]
        out[name] = by_path[key]
    if progress is not None:
        progress("hash", total, total)
    return out


def _seal(out: Path, files: dict[str, Path | bytes], book: dict[str, Any] | None, *, producer: str, title: str, workshop: str,
          project_root: str, sources: list[Any], missing: list[str], version: int,
          known: dict[str, dict[str, Any]] | None = None, progress: Progress | None = None) -> Path:
    """Ghi `book.package` và `project.json` rồi gói ZIP: file tạm cạnh đích, thay nguyên tử. Mục trùng byte thành bí danh.
    `progress`: xem `Progress` (pha "hash" rồi "write"); dừng giữa chừng thì file tạm bị xoá."""
    described = _described(files, known or {}, progress)
    aliases = aliases_for(described)
    created = datetime.now(UTC).isoformat(timespec="seconds")
    if book is not None:
        book["package"] = {
            "format": bookfile.FORMAT,
            "version": version,
            "createdAt": created,
            "producer": producer,
            "files": {name: meta for name, meta in described.items() if listening_name(name)},
        }
        files[bookfile.MANIFEST] = bookfile.json_bytes(book)
        described[bookfile.MANIFEST] = bookfile.describe(files[bookfile.MANIFEST])
    elif workshop == PENDING:
        raise ProjectFileError("Sách chưa có chương nào nghe được để lưu thành dự án.")
    manifest = {
        "format": FORMAT,
        "version": FORMAT_VERSION,
        "createdAt": created,
        "producer": producer,
        "title": title,
        "workshop": workshop,
        "projectRoot": project_root,
        "sources": sources,
        "missingSources": missing,
        "aliases": dict(sorted(aliases.items())),
        "files": dict(sorted(described.items())),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_name(f".{out.name}.{secrets.token_hex(4)}.part")
    try:
        with zipfile.ZipFile(temporary, "w", allowZip64=True) as archive:
            archive.writestr(_entry("mimetype", stored=True), MIMETYPE)
            archive.writestr(_entry(MANIFEST), json.dumps(manifest, ensure_ascii=False, indent=1).encode("utf-8"))
            stored = {name: source for name, source in files.items() if name not in aliases}
            total = sum(described[name]["size"] for name in stored)
            written = 0

            def before(name: str) -> None:
                nonlocal written
                if progress is not None:
                    progress("write", written, total)
                written += described[name]["size"]

            def during(name: str, inside: int) -> None:  # giữa một file audio lớn: báo + cho Huỷ
                progress("write", written - described[name]["size"] + inside, total)

            bookfile.write_entries(archive, stored, order=_order, stored_suffixes=_STORED, before=before,
                                   during=None if progress is None else during)
            if progress is not None:
                progress("write", total, total)
        with temporary.open("rb+") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, out)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return out


class _Resolved:
    """Gói như `zipfile.ZipFile` cho `book_edits.read_layer`: mục là bí danh thì đọc byte của mục thật."""

    def __init__(self, archive: zipfile.ZipFile, aliases: dict[str, str]) -> None:
        self._archive, self._aliases = archive, aliases

    def getinfo(self, name: str) -> zipfile.ZipInfo:
        return self._archive.getinfo(self._aliases.get(name, name))

    def read(self, name: str) -> bytes:
        return self._archive.read(self._aliases.get(name, name))

    def open(self, member: str | zipfile.ZipInfo) -> Any:
        return self._archive.open(member)


class ProjectFile:
    """Một file dự án đã mở và đã kiểm hình dạng (mã băm: `verify()`; `open_into()` / `extract()` tự kiểm)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.last_merge: dict[str, Any] | None = None
        self.book: dict[str, Any] | None = None
        self._edits: dict[str, Any] = book_edits.empty()
        self._cover: bytes | None = None
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
    def workshop(self) -> str:
        """`PRESENT` (có `project/`: mở được thành dự án) hay `PENDING` (chỉ có phần nghe: chờ "Dựng xưởng")."""
        return str(self.manifest["workshop"])

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

    @property
    def aliases(self) -> dict[str, str]:
        return self.manifest["aliases"]

    @property
    def views(self) -> list[str]:
        return [name for name in project_views.VIEWS if project_views.entry(name) in self.manifest["files"]]

    @property
    def chapter_prints(self) -> dict[str, dict[str, Any]]:
        """Cỡ + mã băm audio từng chương - app so với sách đã có để nhận ra cùng một lần sản xuất (như `BookFile.chapter_prints`)."""
        if self.book is None:
            return {}
        return identity_prints(self.book["package"]["files"])

    @property
    def content_key(self) -> str:
        """Tên thư mục app đặt cho cuốn này khi nhập thành sách - cùng công thức với `BookFile.content_key`, nên một cuốn mở
        từ `.abook` rồi từ `.abookproj` của chính nó là một cuốn."""
        return content_key({name: meta["sha256"] for name, meta in self.chapter_prints.items()})

    @property
    def edits(self) -> dict[str, Any]:
        """Lớp sửa của người nghe mà file mang theo (đã kiểm); rỗng khi file không có."""
        return self._edits

    def edits_cover(self) -> bytes | None:
        return self._cover

    def read(self, name: str) -> bytes:
        """Byte của một mục (bí danh thì của mục thật)."""
        if name not in self.manifest["files"] and name != MANIFEST:
            raise KeyError(name)
        return self._zip.read(self.aliases.get(name, name))

    def view(self, name: str) -> Any | None:
        """Một bản chụp (`views/<name>.json`) đã đọc, hay None khi file không có."""
        entry = project_views.entry(name)
        return json.loads(self.read(entry).decode("utf-8")) if entry in self.manifest["files"] else None

    def copy_member(self, name: str, target: Path) -> None:
        """Chép một mục của gói ra `target` (nguyên tử): bài nhạc người nghe đã ghim, khi nhập lại vào cuốn đã có."""
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(f".{target.name}.{secrets.token_hex(4)}.part")
        try:
            with self._zip.open(self.aliases.get(name, name)) as source, part.open("wb") as sink:
                shutil.copyfileobj(source, sink, _CHUNK)
            os.replace(part, target)
        finally:
            part.unlink(missing_ok=True)

    def verify(self) -> None:
        """Mọi mục thật đúng cỡ và mã băm ghi trong `project.json` (bí danh có cỡ + mã băm của mục thật - `_validate` đã kiểm)."""
        for name, expected in self.manifest["files"].items():
            if name in self.aliases:
                continue
            digest = hashlib.sha256()
            size = 0
            with self._zip.open(name) as handle:
                while chunk := handle.read(_CHUNK):
                    digest.update(chunk)
                    size += len(chunk)
            if size != expected["size"] or digest.hexdigest() != expected["sha256"]:
                raise ProjectFileError(f"File dự án bị hỏng hoặc bị sửa ({name}). Hãy chép lại file từ nguồn.")

    def _copy_checked(self, name: str, destination: Path) -> None:
        """Chép mục `name` (qua bí danh nếu cần) ra `destination`, kiểm cỡ + mã băm TRONG LÚC chép - một lần đọc."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        with self._zip.open(self.aliases.get(name, name)) as source, destination.open("wb") as sink:
            while chunk := source.read(_CHUNK):
                digest.update(chunk)
                sink.write(chunk)
                size += len(chunk)
        expected = self.manifest["files"][name]
        if size != expected["size"] or digest.hexdigest() != expected["sha256"]:
            raise ProjectFileError(f"File dự án bị hỏng hoặc bị sửa ({name}). Hãy chép lại file từ nguồn.")

    def open_into(self, library: Path) -> tuple[Path, dict[str, Any]]:
        """Kiểm, giải nén vào một thư mục MỚI trong `library` (không bao giờ đè dự án đang có), viết lại đường dẫn
        trong sổ dự án. Thư mục tạm rồi đổi tên: hỏng giữa chừng không để lại nửa dự án. Trả (thư mục, báo cáo)."""
        if self.workshop != PRESENT:
            raise ProjectFileError("File này chưa có xưởng - chỉ có phần nghe của sách. Hãy “Dựng xưởng” từ sách đã mở.")
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
                self._copy_checked(name, destination)
            sources = {item["path"]: str(target.joinpath(*item["entry"].split("/")))
                       for item in self.manifest["sources"]}
            report = relocate(staging / store.DB_NAME, str(self.manifest["projectRoot"]), str(target), sources)
            os.replace(staging, target)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        restamp_word_timings(target)
        return target, report

    def extract(self, library: Path, folder: str | None = None) -> Path:
        """Nhập file như MỘT CUỐN SÁCH (không mở thành dự án) vào `library/<folder>/`: phần nghe giải ra y như `BookFile.extract`
        (bí danh thành file thật), kèm `views/`, `project.json`, và - khi file có xưởng - `project/` + `sources/` NGUYÊN BYTE
        để lưu lại được (không mở sổ dự án). Dùng khi file chỉ chờ dựng xưởng (`workshop: "pending"`) hay máy không có Studio.
        Kiểm cỡ + mã băm trong lúc chép; thư mục tạm rồi đổi tên; thư mục đã có thì được thay nhưng phần sửa của người nghe
        trên máy này được hợp vào (bookfile.keep_local_edits). Báo cáo hợp ở `last_merge`."""
        library = Path(library)
        library.mkdir(parents=True, exist_ok=True)
        files = self.manifest["files"]
        names = [bookfile.MANIFEST, *sorted(name for name in files if name != bookfile.MANIFEST and (
            listening_name(name) or _VIEW.fullmatch(name)
            or (self.workshop == PRESENT and name.startswith(("project/", "sources/")) and name not in self.aliases)))]
        try:
            bookfile.ensure_room(library, sum(files[name]["size"] for name in names) + self._zip.getinfo(MANIFEST).file_size)
        except bookfile.BookFileError as exc:
            raise ProjectFileError(str(exc)) from exc
        name = folder or self.content_key
        target = library / name
        staging = library / f".{name}.{secrets.token_hex(4)}.part"
        try:
            for entry in names:
                self._copy_checked(entry, staging.joinpath(*entry.split("/")))
            (staging / MANIFEST).write_bytes(self._zip.read(MANIFEST))
            self.last_merge = bookfile.keep_local_edits(target, staging, self.edits) if target.exists() else None
            if target.exists():
                retired = library / f".{name}.{secrets.token_hex(4)}.old"
                os.replace(target, retired)
                os.replace(staging, target)
                shutil.rmtree(retired, ignore_errors=True)
            else:
                os.replace(staging, target)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return target

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
            self.copy_member(name, target)
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
                    listening_name(name) or _VIEW.fullmatch(name) or _safe_entry(name)):
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
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise ProjectFileError("File dự án có phiên bản định dạng không hợp lệ.")
        if version > FORMAT_VERSION:
            raise ProjectFileError("Dự án này được gói bằng bản app mới hơn. Hãy cập nhật app để mở.")
        if version < FORMAT_VERSION:
            raise ProjectFileError("Dự án này được gói bằng bản app cũ hơn, định dạng không còn được đọc. "
                                   "Hãy mở nó bằng bản app đã gói nó rồi gói lại.")
        content = names - {"mimetype", MANIFEST}
        aliases = manifest.get("aliases")
        files = manifest.get("files")
        if not isinstance(files, dict) or not isinstance(aliases, dict):
            raise ProjectFileError("Danh sách file trong dự án không khớp nội dung gói.")
        if manifest.get("workshop") not in (PRESENT, PENDING):
            raise ProjectFileError("File dự án không nói rõ có xưởng hay chưa.")
        self._check_aliases(files, aliases, content)
        if set(files) != content | set(aliases):
            raise ProjectFileError("Danh sách file trong dự án không khớp nội dung gói.")
        for name, meta in files.items():
            if (not isinstance(meta, dict) or not isinstance(meta.get("sha256"), str) or not isinstance(meta.get("size"), int)
                    or (name in content and self._zip.getinfo(name).file_size != meta["size"])):
                raise ProjectFileError(f"Mô tả file {name!r} không khớp gói.")
        sources = manifest.get("sources")
        if not isinstance(sources, list) or not isinstance(manifest.get("projectRoot"), str) or any(
                not isinstance(item, dict) or not isinstance(item.get("path"), str)
                or item.get("entry") not in files or not str(item.get("entry")).startswith("sources/")
                for item in sources):
            raise ProjectFileError("Mô tả nguồn chương trong dự án không hợp lệ.")
        if manifest["workshop"] == PRESENT:
            if f"project/{store.DB_NAME}" not in content or f"project/{store.SETTINGS_NAME}" not in content:
                raise ProjectFileError("File dự án thiếu sổ dự án hay cài đặt sách.")
        elif any(name.startswith("project/") for name in files):
            raise ProjectFileError("File dự án chưa có xưởng mà lại mang sổ dự án.")
        elif bookfile.MANIFEST not in content:
            raise ProjectFileError("File dự án chưa có xưởng mà cũng không có phần nghe nào.")
        self.manifest = manifest
        for name in files:
            if _VIEW.fullmatch(name) and self._view_problem(name):
                raise ProjectFileError(f"Bản chụp {name} hỏng.")
        if bookfile.MANIFEST in content:
            self._check_listening(manifest, content)
        return manifest

    def _check_aliases(self, files: dict[str, Any], aliases: dict[str, Any], content: set[str]) -> None:
        for alias, target in aliases.items():
            if (not isinstance(alias, str) or not isinstance(target, str) or alias in content or target not in content
                    or not aliasable(alias) or not aliasable(target) or not (_safe_entry(alias) or listening_name(alias))):
                raise ProjectFileError(f"Bí danh {alias!r} trong dự án không hợp lệ.")
            if not isinstance(files.get(alias), dict) or files.get(alias) != files.get(target):
                raise ProjectFileError(f"Bí danh {alias!r} không khớp mục thật của nó.")

    def _view_problem(self, name: str) -> bool:
        """Bản chụp quá lớn hay không phải JSON."""
        if self.manifest["files"][name]["size"] > project_views.MAX_BYTES:
            return True
        try:
            json.loads(self._zip.read(name).decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return True
        return False

    def _check_listening(self, manifest: dict[str, Any], content: set[str]) -> None:
        """Phần nghe (`book.json`) khớp phần còn lại của gói: mọi file nó kể có trong gói (kể cả bí danh) với đúng cỡ + mã băm
        ghi ở `project.json`, mọi file nghe được trong gói đều được kể, chương nào cũng trỏ tới audio có thật, và lớp sửa của
        người nghe (nếu có) qua cùng cổng kiểm với file `.abook`."""
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
        listening = {name for name in manifest["files"] if listening_name(name)}
        if set(listed) != listening or any(
                not isinstance(meta, dict) or meta != manifest["files"][name] for name, meta in listed.items()):
            raise ProjectFileError("Phần nghe của dự án không khớp nội dung gói.")
        for chapter in book.get("chapters") or []:
            reference = chapter.get("file") if isinstance(chapter, dict) else None
            if reference and reference not in listed:
                raise ProjectFileError("Phần nghe của dự án thiếu audio của một chương.")
            written = chapter.get("text") if isinstance(chapter, dict) else None
            if written and (not isinstance(written, str) or written not in listed):
                raise ProjectFileError("Phần nghe của dự án thiếu chữ của một chương.")
        self.book = book
        try:
            self._edits, self._cover = book_edits.read_layer(_Resolved(self._zip, manifest["aliases"]), listening)
        except book_edits.EditsError as exc:
            raise ProjectFileError(str(exc)) from exc


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
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    pack_command = commands.add_parser("pack", help="gói một dự án thành một file")
    pack_command.add_argument("project", type=Path)
    pack_command.add_argument("-o", "--out", type=Path, default=None)
    repack_command = commands.add_parser("repack", help="đóng lại một cuốn đã nhập thành file dự án")
    repack_command.add_argument("folder", type=Path)
    repack_command.add_argument("-o", "--out", type=Path, required=True)
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
        if args.command == "repack":
            print(repack(args.folder, args.out))
            return 0
        with ProjectFile(args.file) as project:
            if args.command == "verify":
                project.verify()
                print(f"{project.title} · {len(project.manifest['files'])} file ({len(project.aliases)} bí danh) · "
                      f"{project.size} byte · mã băm khớp"
                      f"{f' · thiếu {len(project.missing_sources)} nguồn' if project.missing_sources else ''}")
            else:
                target, report = project.open_into(args.library)
                print(f"{target} · đổi {report['changed']} đường dẫn · {report['outside']} đường dẫn trỏ ra ngoài")
        return 0
    except (ProjectFileError, bookfile.BookFileError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
