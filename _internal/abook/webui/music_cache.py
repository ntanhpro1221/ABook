"""Bộ đệm nhạc nền của máy (music_dir/files): bài tải từ danh mục (`<sha1 của link>.mp3`) và bài sách mang theo chép vào từ file `.abookproj`
(projectfile.copy_music). Nhạc theo cảnh bật sẵn và mỗi bài tải được tới MUSIC_TRACK_MAX_MB, nên thư mục này phình mãi nếu không có trần.

Trần CAP_BYTES; quá trần thì xoá bài LÂU KHÔNG NGHE nhất (giờ sửa file = lần nghe gần nhất, `touch`) cho tới khi còn LOW_WATER của trần - bài danh mục bị xoá
tải lại được khi cần. KHÔNG BAO GIỜ xoá:
  - bài sách mang theo (`own`: sổ files_owned.json cạnh thư mục, không đoán từ tên - hai loại bài trùng kiểu tên) - xoá là mất nhạc của cuốn ấy khi offline;
  - bài người dùng nhập vào "Nhạc của tôi" (music_local.LocalMusic, ở music_dir/mine/files - ngoài thư mục này; ở đây thêm một chốt nữa: file có tên = sha1 NỘI DUNG của
    chính nó là bài nhập / bài người nghe ghim, không phải bài tải theo link nên không bao giờ bị xoá);
  - bài người nghe ghim trong cuốn (`protected`: music_overrides.json của các dự án), bài đang kêu / vừa dùng cho chương đang nghe (nghe thì `touch`, dưới RECENT_SECONDS
    không xoá), bài vừa tải (`keep`), file đang mở (Windows không cho xoá).
Điện thoại có luật cùng ý (MusicCatalog.prune: 300 MB, theo giờ dùng, trừ bài đang kêu / sắp tới / vừa tải; nhạc nhập và nhạc sách nằm ngoài thư mục bài tải)."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Callable, Iterable

from ..io_utils import atomic_write_json
from . import music_plan

CAP_BYTES = 2 * 1024 ** 3  # ~300 bài 4-10 MB: hàng chục cuốn nghe liền, còn xa mới đầy ổ; điện thoại 300 MB vì bộ nhớ nhỏ hơn
LOW_WATER = 0.9  # dọn xuống 90% trần: không dọn lại ở mỗi bài mới tải
RECENT_SECONDS = 24 * 3600  # bài nghe trong ngày qua (đang kêu, chương đang nghe, vừa tải sẵn) không xoá dù đã quá trần
TOUCH_SECONDS = 600  # ghi lại lần nghe nhiều nhất mỗi 10 phút một bài (đỡ ghi đĩa ở mỗi lượt phát)
OWNED_VERSION = 1
_TRACK = re.compile(music_plan.TRACK_NAME)


class MusicCache:
    def __init__(self, folder: Path, owned_file: Path, *, cap_bytes: int = CAP_BYTES, clock: Callable[[], float] = time.time) -> None:
        self.folder = Path(folder)
        self.owned_file = Path(owned_file)
        self.cap_bytes = cap_bytes
        self.clock = clock
        self._lock = threading.RLock()
        self._owned: set[str] | None = None

    # -- bài sách mang theo -------------------------------------------------------------------------------------------------
    def owned(self) -> set[str]:
        with self._lock:
            if self._owned is None:
                try:
                    data = json.loads(self.owned_file.read_text(encoding="utf-8"))
                    names = data.get("owned") if isinstance(data, dict) and data.get("version") == OWNED_VERSION else None
                except (OSError, ValueError):
                    names = None
                self._owned = {name for name in names or [] if isinstance(name, str) and _TRACK.fullmatch(name)}
            return set(self._owned)

    def own(self, names: Iterable[str]) -> None:
        """Ghi tên file (trong thư mục này) của các bài sách mang theo vừa chép vào: từ nay không bao giờ bị dọn."""
        with self._lock:
            found = {name for name in names if _TRACK.fullmatch(name)}
            if found <= self.owned():
                return
            self._owned = self.owned() | found
            with contextlib.suppress(OSError):
                atomic_write_json(self.owned_file, {"version": OWNED_VERSION, "owned": sorted(self._owned)})

    # -- dùng ---------------------------------------------------------------------------------------------------------------
    def touch(self, path: Path | None) -> None:
        """Ghi nhận bài vừa được dùng (giờ sửa file = lần nghe gần nhất); file ngoài thư mục này hay mới ghi gần đây thì thôi."""
        if path is None:
            return
        with contextlib.suppress(OSError):
            path = Path(path)
            if path.parent != self.folder:
                return
            now = self.clock()
            if now - path.stat().st_mtime > TOUCH_SECONDS:
                os.utime(path, (now, now))

    # -- dọn ----------------------------------------------------------------------------------------------------------------
    def total_bytes(self) -> int:
        return sum(size for _path, size, _mtime in self._tracks())

    def _tracks(self) -> list[tuple[Path, int, float]]:
        found = []
        with contextlib.suppress(OSError):
            for path in self.folder.iterdir():
                if _TRACK.fullmatch(path.name):
                    with contextlib.suppress(OSError):
                        info = path.stat()
                        found.append((path, info.st_size, info.st_mtime))
        return found

    def prune(self, protected: Callable[[], set[str]] | None = None, keep: Iterable[Path] = ()) -> list[Path]:
        """Quá trần thì xoá bài lâu không nghe nhất cho tới LOW_WATER của trần. `protected`: tên file các bài người nghe ghim (hỏi lúc cần dọn, không mỗi lần gọi);
        `keep`: file không được xoá (bài vừa tải). Trả các file đã xoá."""
        with self._lock:
            tracks = self._tracks()
            total = sum(size for _path, size, _mtime in tracks)
            if total <= self.cap_bytes:
                return []
            exempt = self.owned() | set(protected() if protected is not None else ()) | {Path(path).name for path in keep}
            recent = self.clock() - RECENT_SECONDS
            removed = []
            for path, size, mtime in sorted(tracks, key=lambda item: item[2]):
                if total <= self.cap_bytes * LOW_WATER:
                    break
                if path.name in exempt or mtime >= recent or self._content_addressed(path):
                    continue
                try:
                    path.unlink()
                except OSError:
                    continue  # đang mở (Windows) hay không xoá được: để lại, dọn bài khác
                for leftover in (path.with_suffix(music_plan.LUFS_SIDECAR), path.with_suffix(music_plan.MEASURE_SIDECAR)):
                    with contextlib.suppress(OSError):
                        leftover.unlink(missing_ok=True)
                removed.append(path)
                total -= size
            return removed

    @staticmethod
    def _content_addressed(path: Path) -> bool:
        """Tên file = sha1 nội dung của chính nó: bài người dùng nhập / ghim (`local:<sha1 file>`), không phải bài tải theo link (tên = sha1 của link)."""
        digest = hashlib.sha1()
        try:
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1 << 20), b""):
                    digest.update(chunk)
        except OSError:
            return True  # đọc không được thì đừng xoá
        return digest.hexdigest() == path.stem
