"""Bộ nhớ đệm clip trên đĩa: `<khoá>.mp3|wav` + `<khoá>.json` (độ dài, mốc từng chữ), khoá = sha256(nhà cung cấp | giọng | chữ).

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

LIMIT_BYTES = 500 * 1024 * 1024
NAME = re.compile(r"[0-9a-f]{64}\.(mp3|wav)")
TYPES = {"mp3": "audio/mpeg", "wav": "audio/wav"}


def clip_key(provider: str, voice: str, text: str) -> str:
    return hashlib.sha256(f"{provider}|{voice}|{text}".encode("utf-8")).hexdigest()


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
