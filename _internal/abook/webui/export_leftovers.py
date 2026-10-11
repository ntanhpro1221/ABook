"""Dọn dấu vết của lượt gói dự án (`.abookproj`) bị cắt ngang: đóng app khi việc đang gói quá 3 giây (`export_jobs.shutdown`) hay máy tắt
đột ngột thì file tạm `.<tên>.abookproj.<8 hex>.part` nằm lại cạnh nơi lưu, và thư mục tạm `abookproj-*` nằm lại trong thư mục tạm
của hệ thống. Lần mở app sau dọn chúng.

Chỉ đụng đúng hai mẫu tên của chính `projectfile.py`, và chỉ khi đã cũ (`MIN_AGE`: một app khác đang gói thì file của nó còn mới) -
file người dùng, file `.abookproj` thật, thư mục lạ cùng chỗ không bao giờ bị xoá. Nơi cần dọn: các thư mục xuất app đã ghi nhớ
(`ExportFolders`, qua các lần mở app) cùng thư mục "Đã xuất" mặc định của thư viện."""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import threading
import time
from collections.abc import Iterable
from pathlib import Path

log = logging.getLogger(__name__)

PART = re.compile(r"^\..+\.abookproj\.[0-9a-f]{8}\.part$")  # projectfile._seal: f".{out.name}.{secrets.token_hex(4)}.part"
SCRATCH = re.compile(r"^abookproj-[a-z0-9_]{8}$")  # projectfile.pack: tempfile.TemporaryDirectory(prefix="abookproj-")
MIN_AGE = 600.0
KEEP = 20


class ExportFolders:
    """Các thư mục người dùng đã chọn để xuất `.abookproj`, nhớ qua các lần mở app (mới nhất trước, tối đa `KEEP`)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def recent(self) -> list[Path]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return [Path(item) for item in data if isinstance(item, str)] if isinstance(data, list) else []

    def remember(self, folder: Path) -> None:
        """Ghi nhớ trước khi gói (lúc chết giữa chừng thì lần mở sau còn biết chỗ dọn). Lỗi ghi không được làm hỏng lượt xuất."""
        text = str(folder)
        with self._lock:
            kept = [text] + [str(item) for item in self.recent() if str(item) != text]
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.path.with_name(self.path.name + ".tmp")
                temporary.write_bytes(json.dumps(kept[:KEEP], ensure_ascii=False).encode("utf-8"))
                os.replace(temporary, self.path)
            except OSError:
                log.warning("Không ghi nhớ được thư mục xuất %s", folder, exc_info=True)


def _newest(path: Path) -> float:
    """Lúc sửa gần nhất của thư mục hoặc mục con trực tiếp của nó (thư mục tạm đang dùng thì có file mới)."""
    newest = path.stat().st_mtime
    try:
        for child in path.iterdir():
            newest = max(newest, child.stat().st_mtime)
    except OSError:
        pass
    return newest


def sweep(folders: Iterable[Path], scratch_root: Path | None, *, now: float | None = None, min_age: float = MIN_AGE) -> list[Path]:
    """Xoá file `.part` và thư mục `abookproj-*` sót lại cũ hơn `min_age` giây; trả những gì đã xoá. Lỗi từng mục (đang bị khoá, mất quyền) bỏ qua."""
    now = time.time() if now is None else now
    removed: list[Path] = []
    for folder in dict.fromkeys(folders):
        try:
            names = [entry for entry in folder.iterdir() if PART.match(entry.name) and entry.is_file()]
        except OSError:
            continue  # thư mục đã dời / ổ rời không cắm
        for entry in names:
            try:
                if now - entry.stat().st_mtime >= min_age:
                    entry.unlink()
                    removed.append(entry)
            except OSError:
                log.debug("Không dọn được %s", entry, exc_info=True)
    if scratch_root is not None:
        try:
            scratches = [entry for entry in scratch_root.iterdir() if SCRATCH.match(entry.name) and entry.is_dir()]
        except OSError:
            scratches = []
        for entry in scratches:
            try:
                if now - _newest(entry) >= min_age:
                    shutil.rmtree(entry)
                    removed.append(entry)
            except OSError:
                log.debug("Không dọn được %s", entry, exc_info=True)
    return removed


# ---- rác của các việc khác bị tắt ngang (soát a28 lỗi 12) ---------------------------------------------------------------------------
# Nhập / mở / xuất sách và tải nhạc đều ghi ra tên tạm rồi mới đổi sang tên thật; app bị tắt ngang thì tên tạm nằm lại mãi (một cuốn TXT
# 11 MB, một file sách 34 MB...). Chỉ đúng mẫu tên của chính app, và chỉ khi đã cũ hơn `CRASH_AGE` - một việc còn chạy thì có file mới.
CRASH_AGE = 3600.0
BOOKFILE_PART = re.compile(r"^\..+\.abook\.[0-9a-f]{8}\.part$")  # bookfile.pack: f".{out.name}.{secrets.token_hex(4)}.part"
M4B_SCRATCH = re.compile(r"^\.m4b-[a-z0-9_]{8}$")  # export.m4b_from_files: TemporaryDirectory(prefix=".m4b-", dir=nơi lưu)
STAGING = re.compile(r"^\..+\.[0-9a-f]{8}\.part$")  # bookfile / projectfile extract, open_into: thư mục tạm trong thư viện
RETIRED = re.compile(r"^\.(?P<name>.+)\.[0-9a-f]{8}\.old$")  # bookfile / projectfile extract: bản cũ chờ xoá sau khi thay
TEMP_SCRATCH = re.compile(r"^abook-(?:text|wishes)-[a-z0-9_]{8}$")  # textbook / book_wishes: TemporaryDirectory trong %TEMP%
MUSIC_PART = re.compile(r"^.+\.[0-9a-f]{8}\.part$")  # server: bài nhạc đang tải f"{target.stem}.{secrets.token_hex(4)}.part"


def _age(path: Path, now: float) -> float:
    return now - (_newest(path) if path.is_dir() else path.stat().st_mtime)


def _drop(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _entries(folder: Path, pattern: re.Pattern[str]) -> list[Path]:
    try:
        return [entry for entry in folder.iterdir() if pattern.match(entry.name)]
    except OSError:
        return []  # thư mục đã dời / ổ rời không cắm


def sweep_crashed(export_folders: Iterable[Path], library_folders: Iterable[Path], scratch_root: Path | None, music_files: Path | None,
                  *, now: float | None = None, min_age: float = CRASH_AGE) -> list[Path]:
    """Dọn tên tạm của nhập / mở / xuất sách và tải nhạc bị tắt ngang, cũ hơn `min_age` giây. Bản cũ `.<tên>.<hex>.old` mà bản chính không còn
    (tắt ngang đúng giữa hai lần đổi tên) thì được ĐỔI TÊN LẠI thành `<tên>` - đó là cuốn sách của người dùng, không phải rác. Trả những gì đã
    xoá / trả lại. Lỗi từng mục bỏ qua."""
    now = time.time() if now is None else now
    found: list[Path] = []
    restored: list[Path] = []
    for folder in dict.fromkeys(export_folders):
        found += _entries(folder, BOOKFILE_PART) + _entries(folder, M4B_SCRATCH)
    for folder in dict.fromkeys(library_folders):
        found += _entries(folder, STAGING)
        for retired in _entries(folder, RETIRED):
            original = folder / RETIRED.match(retired.name)["name"]  # type: ignore[index] - _entries chỉ trả tên khớp
            try:
                if original.exists():
                    found.append(retired)
                elif _age(retired, now) >= min_age:
                    os.replace(retired, original)
                    restored.append(original)
            except OSError:
                log.debug("Không trả lại được %s", retired, exc_info=True)
    if scratch_root is not None:
        found += [entry for entry in _entries(scratch_root, TEMP_SCRATCH) if entry.is_dir()]
    if music_files is not None:
        found += [entry for entry in _entries(music_files, MUSIC_PART) if entry.is_file()]
    removed: list[Path] = []
    for entry in found:
        try:
            if _age(entry, now) >= min_age:
                _drop(entry)
                removed.append(entry)
        except OSError:
            log.debug("Không dọn được %s", entry, exc_info=True)
    return removed + restored
