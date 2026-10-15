"""Bộ nhớ đệm clip trên đĩa: `<khoá>.mp3|wav` + `<khoá>.json` (độ dài, mốc từng chữ), khoá = sha256(phiên bản luật đọc | nhà cung cấp | giọng | chữ).

Clip ở tốc độ 1,0 (đổi tốc độ là việc của trình phát), nên mọi tốc độ dùng chung một clip. Đầy quá `limit` thì bỏ clip lâu không dùng nhất
(LRU theo thời gian truy cập: mỗi lần trúng đệm ghi lại mtime của file JSON). Ghi qua file tạm rồi đổi tên: máy chủ đọc không bao giờ thấy file dở.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path

from . import names

LIMIT_BYTES = 500 * 1024 * 1024
NAME = re.compile(r"[0-9a-f]{64}\.(mp3|wav)")
TYPES = {"mp3": "audio/mpeg", "wav": "audio/wav"}


# Luật đọc (chuẩn hoá chữ) nằm trong khoá: đổi luật thì clip làm trước (kể cả "Làm trước" đã ghim) KHÔNG còn trúng đệm - cách đọc mới được làm lại, không giữ cách đọc cũ.
# Khoá = phiên bản luật của các mô-đun có số riêng (`names.RULE_VERSION`) + số này; Android (ClipCache.kt `RULES`) tính CÙNG cách, từ `Names.RULE_VERSION` +
# `ClipCache.CACHE_RULES`. Một thay đổi luật đọc mà mô-đun của nó không có số riêng (romanization, shouts, vieneu units...) thì tăng số này, ở CẢ HAI nơi.
CACHE_RULES = 1


def rules_version() -> str:
    return f"{names.RULE_VERSION}.{CACHE_RULES}"


def clip_key(provider: str, voice: str, text: str, reading: str = "") -> str:
    """`reading`: dấu của cách đọc riêng của cuốn (gốc Nhật / Hàn làm tên đọc khác: `VieneuProvider.reading_tag`); rỗng thì không thêm gì sau chữ."""
    return hashlib.sha256((f"{rules_version()}|{provider}|{voice}|{text}" + (f"|{reading}" if reading else "")).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Cached:
    key: str
    file: str
    duration_ms: int
    words: list[list[int]]


class ClipCache:
    def __init__(self, folder: Path | str, limit: int = LIMIT_BYTES) -> None:
        self.folder = Path(folder)
        self.limit = limit
        self._lock = threading.RLock()
        self._size: int | None = None

    def get(self, key: str) -> Cached | None:
        meta = self.folder / f"{key}.json"
        try:
            data = json.loads(meta.read_bytes().decode("utf-8"))
            file = str(data["file"])
            if not NAME.fullmatch(file) or not (self.folder / file).is_file():
                return None
            os.utime(meta)  # trúng đệm = vừa dùng
            return Cached(key, file, int(data["duration_ms"]), [[int(a), int(b)] for a, b in data["words"]])
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def put(self, key: str, audio: bytes, ext: str, duration_ms: int, words: list[list[int]]) -> Cached:
        file = f"{key}.{ext}"
        with self._lock:
            self.folder.mkdir(parents=True, exist_ok=True)
            self._write(self.folder / file, audio)
            meta = json.dumps({"file": file, "duration_ms": duration_ms, "words": words}, separators=(",", ":")).encode("utf-8")
            self._write(self.folder / f"{key}.json", meta)
            if self._size is not None:
                self._size += len(audio) + len(meta)
            self.trim()
        return Cached(key, file, duration_ms, words)

    def path(self, file: str) -> Path | None:
        """Đường dẫn file audio theo tên (chỉ tên đúng dạng `<64 hex>.mp3|wav`)."""
        if not NAME.fullmatch(file):
            return None
        path = self.folder / file
        return path if path.is_file() else None

    @staticmethod
    def mime(file: str) -> str:
        return TYPES.get(file.rsplit(".", 1)[-1], "application/octet-stream")

    def usage(self, keys: "set[str] | frozenset[str]") -> tuple[int, set[str]]:
        """Byte của các clip trong `keys` còn nằm trong bộ đệm, và tập khoá còn lại (clip đã bị dọn khỏi đĩa thì không có)."""
        used, present = 0, set()
        for key in keys:
            size = sum(self._size_of(self.folder / f"{key}.{ext}") for ext in ("json", *TYPES))
            if size:
                used += size
                present.add(key)
        return used, present

    def remove(self, keys: "set[str] | frozenset[str]") -> int:
        """Xoá các clip trong `keys` khỏi bộ đệm; trả số byte giải phóng."""
        freed = 0
        with self._lock:
            for key in keys:
                for ext in ("json", *TYPES):
                    path = self.folder / f"{key}.{ext}"
                    size = self._size_of(path)
                    if not size:
                        continue
                    try:
                        path.unlink()
                    except OSError:
                        continue
                    freed += size
            if self._size is not None:
                self._size = max(0, self._size - freed)
        return freed

    @staticmethod
    def _size_of(path: Path) -> int:
        try:
            return path.stat().st_size
        except OSError:
            return 0

    def _write(self, path: Path, data: bytes) -> None:
        temp = path.with_name(path.name + ".part")
        temp.write_bytes(data)
        os.replace(temp, path)

    def size(self) -> int:
        with self._lock:
            if self._size is None:
                self._size = sum(entry.stat().st_size for entry in self._entries())
            return self._size

    def _entries(self) -> list[Path]:
        try:
            return [entry for entry in self.folder.iterdir() if entry.is_file() and not entry.name.endswith(".part")]
        except OSError:
            return []

    def trim(self) -> None:
        """Bỏ clip lâu không dùng nhất cho tới khi còn <= limit."""
        with self._lock:
            if self.size() <= self.limit:
                return
            clips = []
            for meta in self._entries():
                if meta.suffix != ".json":
                    continue
                try:
                    stamp = meta.stat().st_mtime
                    file = json.loads(meta.read_bytes().decode("utf-8"))["file"]
                except (OSError, ValueError, KeyError):
                    stamp, file = 0.0, ""
                clips.append((stamp, meta, self.folder / file if NAME.fullmatch(file) else None))
            clips.sort(key=lambda item: item[0])
            for _, meta, audio in clips:
                if self._size is not None and self._size <= self.limit:
                    break
                for path in (audio, meta):
                    if path is None:
                        continue
                    try:
                        size = path.stat().st_size
                        path.unlink()
                        self._size = (self._size or 0) - size
                    except OSError:
                        pass


class ClipBooks:
    """Cuốn nào đã làm ra clip nào ("bản đọc đã làm" của cuốn): khoá clip là băm nên bộ đệm tự nó không biết clip thuộc cuốn nào.
    Ghi nối thêm từng dòng JSON `[cuốn, khoá]` ở file cạnh thư mục bộ đệm (không nằm trong đó - bộ đệm tự dọn file lâu không dùng). Khoá của clip đã bị
    bộ đệm dọn thì bỏ ở lần hỏi kế; clip làm trước khi có file này không thuộc cuốn nào (chỉ có trong tổng)."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._books: dict[str, set[str]] | None = None

    def _load(self) -> dict[str, set[str]]:
        if self._books is None:
            books: dict[str, set[str]] = {}
            try:
                lines = self.path.read_bytes().decode("utf-8").splitlines()
            except OSError:
                lines = []
            for line in lines:
                try:
                    book, key = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if isinstance(book, str) and isinstance(key, str):
                    books.setdefault(book, set()).add(key)
            self._books = books
        return self._books

    def note(self, book: str, key: str) -> None:
        with self._lock:
            keys = self._load().setdefault(book, set())
            if key in keys:
                return
            keys.add(key)
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("ab") as handle:
                    handle.write(json.dumps([book, key], ensure_ascii=False).encode("utf-8") + b"\n")
            except OSError:
                pass  # chỉ là sổ ghi chú: mất dòng này thì clip chỉ không được tính cho cuốn

    def keys(self, book: str) -> set[str]:
        with self._lock:
            return set(self._load().get(book, ()))

    def forget(self, book: str, keys: "set[str] | frozenset[str]") -> None:
        """Bỏ `keys` khỏi sổ của `book` (đã xoá khỏi bộ đệm, hay đã bị dọn) và ghi lại file gọn."""
        with self._lock:
            books = self._load()
            if book in books:
                books[book] -= set(keys)
                if not books[book]:
                    del books[book]
            body = b"".join(json.dumps([name, key], ensure_ascii=False).encode("utf-8") + b"\n" for name, keys_ in books.items() for key in sorted(keys_))
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temp = self.path.with_name(self.path.name + ".part")
                temp.write_bytes(body)
                os.replace(temp, self.path)
            except OSError:
                pass
