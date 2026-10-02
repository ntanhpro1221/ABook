"""Dấu vân tay nội dung của một cuốn sách: mã băm audio từng chương, do APP tự tính.

Chủ sách, 27-09: sách và dữ liệu nghe là hai thứ độc lập, "hoàn toàn không biết đến mã"; mã chỉ là thứ app dùng để
liên kết một sách với dữ liệu nghe. Nên không file sách nào mang mã. Muốn biết cuốn mở từ file .abook và cuốn tải qua
Wi-Fi có phải CÙNG một lần sản xuất không, app so audio: hai bản có chung một chương audio giống hệt từng byte (cùng
tên, cùng cỡ, cùng mã băm) là cùng một lần sản xuất - kể cả khi bản sau đã thêm chương.

Băm MP3 tốn công (vài chục MB mỗi chương) nên chỉ băm khi cần (tên + cỡ đã khớp) và nhớ theo (đường dẫn, cỡ, mốc sửa)
trong kho của app, cạnh `listening.json` - không bao giờ ghi vào thư mục sách.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any

CHUNK = 1024 * 1024


def content_key(chapters: dict[str, str]) -> str:
    """Tên thư mục app đặt cho một cuốn mở từ file, suy từ nội dung (`{tên chương: sha256}`) - mở lại đúng file ấy thì
    trùng tên. Android dùng đúng công thức này (BookFileImport.contentKey)."""
    text = "\n".join(f"{name}:{chapters[name]}" for name in sorted(chapters))
    return "f-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def base_name(name: str) -> str:
    """Tên file của một mục `chapters/...` (bỏ thư mục phần của file cả bộ): `chapters/2/x.mp3` -> `x.mp3`."""
    return name.rsplit("/", 1)[-1]


class Fingerprints:
    """Mã băm file audio, nhớ theo (đường dẫn, cỡ, mốc sửa) - đổi file là băm lại."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            loaded = {}
        self._cache: dict[str, list[Any]] = loaded if isinstance(loaded, dict) else {}

    def sha256(self, file: Path) -> str:
        stat = file.stat()
        key = os.path.normcase(str(file.resolve()))
        with self._lock:
            known = self._cache.get(key)
            if isinstance(known, list) and known[:2] == [stat.st_size, stat.st_mtime_ns]:
                return str(known[2])
        digest = hashlib.sha256()
        with file.open("rb") as handle:
            while chunk := handle.read(CHUNK):
                digest.update(chunk)
        value = digest.hexdigest()
        with self._lock:
            self._cache[key] = [stat.st_size, stat.st_mtime_ns, value]
            self._save()
        return value

    def shares_a_chapter(self, project_root: Path, chapters: dict[str, dict[str, Any]]) -> bool:
        """Cuốn trên máy này có chung ít nhất một chương audio với `chapters` ({"chapters/x.mp3": {size, sha256}})?
        Chỉ băm file trùng tên và cỡ - thường là không băm gì cả. So theo TÊN FILE (không kể thư mục): file cả bộ
        đặt audio ở `chapters/<phần>/x.mp3`, còn dự án mỗi phần giữ `output/chapters/x.mp3`."""
        folder = Path(project_root) / "output" / "chapters"
        for name, described in chapters.items():
            if not name.startswith("chapters/") or not isinstance(described, dict):
                continue
            candidate = folder / base_name(name)
            try:
                if (candidate.is_file() and candidate.stat().st_size == int(described.get("size", -1))
                        and self.sha256(candidate) == described.get("sha256")):
                    return True
            except (OSError, ValueError, TypeError):
                continue
        return False

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._cache), encoding="utf-8")
        os.replace(temporary, self.path)
