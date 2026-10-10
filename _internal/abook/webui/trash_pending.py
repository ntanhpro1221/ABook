"""Chỗ chờ trước Thùng rác: xoá một sách / dự án trên máy tính được "Hoàn tác" trong ~30 giây.

Thùng rác của Windows khôi phục từ app thì phải qua COM, nên xoá không đi thẳng vào đó. Xoá = đổi tên (`os.replace`, cùng ổ nên
tức thì, không chép byte nào) cả thư mục sang `<thư viện>/.trash-pending/<mã>/<tên gốc>` kèm `meta.json` (đường gốc, loại, lúc
xoá). Thư viện thấy sách biến mất ngay; "Hoàn tác" chỉ là đổi tên ngược lại. Hết `UNDO_SECONDS` (và lúc app mở / đóng) bộ dọn
chuyển thư mục vào Thùng rác đúng như trước đây.

Luật giữ cho chỗ này an toàn:
- Không bao giờ xoá hẳn: dọn không được (file khoá, ổ không có Thùng rác) thì để nguyên chỗ chờ, lần sau dọn tiếp.
- Trước khi gọi Thùng rác, thư mục được đổi tên NGƯỢC về đường gốc: Thùng rác ghi nhớ đường gốc để "Khôi phục" đưa nó về đúng
  chỗ cũ, không về trong `.trash-pending` (nơi lần dọn sau lại gom nó đi). Đường gốc đã bị chiếm thì để nguyên, dọn lần sau.
- `.trash-pending` nằm trong thư mục thư viện nhưng không phải dự án hay sách nhập: thư viện chỉ quét thư mục con có sổ dự án
  (store.is_project) hay nằm trong "Sách đã nhập", nên không bao giờ thấy nó như một cuốn sách.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Callable

from . import actions

FOLDER = ".trash-pending"
META = "meta.json"
UNDO_SECONDS = 30
_TOKEN = re.compile(r"[0-9a-f]{32}")


class NotPending(LookupError):
    """Mã này không còn trong chỗ chờ (quá hạn đã vào Thùng rác, hoặc đã hoàn tác rồi)."""


class Occupied(FileExistsError):
    """Đường gốc đã có thư mục cùng tên - không đè lên được."""


def _drive(path: Path) -> str:
    return os.path.splitdrive(os.path.abspath(path))[0].lower()


class TrashPending:
    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self.clock = clock
        self._lock = threading.RLock()

    def fits(self, root: Path, path: Path) -> bool:
        """Đổi tên được từ `path` vào chỗ chờ của `root` không: thư viện còn đó và cùng ổ (khác ổ thì đổi tên là CHÉP - không
        tức thì, không hoàn tác gọn được; nơi gọi chuyển thẳng vào Thùng rác như cũ)."""
        return root.is_dir() and _drive(root) == _drive(path) and FOLDER not in path.parts

    def hold(self, root: Path, path: Path, kind: str, *, queued: bool = False) -> str:
        """Đưa thư mục `path` (đã resolve) vào chỗ chờ, trả mã hoàn tác. Lỗi (file đang mở, ổ không có Thùng rác) là OSError và
        thư mục còn nguyên chỗ cũ. Ổ không có Thùng rác báo NGAY ở đây - không đợi tới lúc hết hạn mới biết không dọn được."""
        actions.recycle_bin_available(path)
        token = secrets.token_hex(16)
        folder = root / FOLDER / token
        with self._lock:
            folder.mkdir(parents=True)
            try:
                meta = {"original": str(path), "name": path.name, "kind": kind, "deletedAt": self.clock(), "queued": queued}
                (folder / META).write_bytes(json.dumps(meta, ensure_ascii=False).encode("utf-8"))
                os.replace(path, folder / path.name)
            except OSError:
                self._tidy(folder)
                self._tidy_base(root / FOLDER)
                raise
        return token

    def restore(self, root: Path, token: str) -> dict[str, Any]:
        """Hoàn tác: thư mục về đúng đường gốc. Trả meta (original, name, kind, queued). `NotPending` khi mã lạ / hết hạn,
        `Occupied` khi đường gốc đã có thư mục cùng tên (thư mục vẫn nằm chờ), OSError khi đổi tên không được."""
        folder = self._folder(root, token)
        with self._lock:
            meta = self._meta(folder)
            if meta is None:
                raise NotPending(token)
            item = folder / meta["name"]
            original = Path(meta["original"])
            if not item.is_dir():
                raise NotPending(token)
            if original.exists():
                raise Occupied(str(original))
            original.parent.mkdir(parents=True, exist_ok=True)
            os.replace(item, original)
            self._tidy(folder)
        self._tidy_base(root / FOLDER)
        return meta

    def sweep(self, root: Path, *, everything: bool = False) -> int:
        """Chuyển vào Thùng rác những mã đã quá `UNDO_SECONDS` (`everything`: mọi mã, lúc app mở / đóng). Trả số mã còn lại - dọn
        không được thì còn, lần sau thử tiếp; không bao giờ văng."""
        base = root / FOLDER
        try:
            folders = sorted(child for child in base.iterdir() if child.is_dir() and _TOKEN.fullmatch(child.name))
        except OSError:
            return 0
        left = 0
        for folder in folders:
            with self._lock:
                if not folder.is_dir():
                    continue  # hoàn tác giữa chừng
                meta = self._meta(folder)
                if not everything and meta is not None and self.clock() - float(meta.get("deletedAt") or 0) < UNDO_SECONDS:
                    left += 1
                    continue
                if meta is None or not self._recycle(folder, meta):
                    left += 1
        self._tidy_base(base)
        return left

    # ------------------------------------------------------------------------------------------------------------------

    def _recycle(self, folder: Path, meta: dict[str, Any]) -> bool:
        item = folder / meta["name"]
        original = Path(meta["original"])
        if not item.is_dir():
            self._tidy(folder)  # chỉ còn meta (thư mục đã đi tiếp ở lần dọn dở trước)
            return True
        if original.exists() or not original.parent.is_dir():
            return False
        try:
            os.replace(item, original)  # về đường gốc để Thùng rác ghi nhớ chỗ cũ (xem đầu file)
        except OSError:
            return False
        try:
            actions.move_to_recycle_bin(original)
        except OSError:
            try:
                os.replace(original, item)  # thư viện không được thấy lại cuốn đã xoá
            except OSError:
                pass
            return False
        self._tidy(folder)
        return True

    @staticmethod
    def _folder(root: Path, token: str) -> Path:
        if not _TOKEN.fullmatch(token):
            raise NotPending(token)
        return root / FOLDER / token

    @staticmethod
    def _meta(folder: Path) -> dict[str, Any] | None:
        try:
            meta = json.loads((folder / META).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        name, original = meta.get("name"), meta.get("original")
        if not isinstance(name, str) or not isinstance(original, str) or not name or name != Path(original).name:
            return None
        if not Path(original).is_absolute():
            return None
        return meta

    @staticmethod
    def _tidy(folder: Path) -> None:
        """Bỏ meta.json và thư mục mã khi nó chỉ còn lại meta (không đụng nội dung sách: thư mục khác thì rmdir báo lỗi)."""
        try:
            if {child.name for child in folder.iterdir()} <= {META}:
                (folder / META).unlink(missing_ok=True)
                folder.rmdir()
        except OSError:
            pass

    @staticmethod
    def _tidy_base(base: Path) -> None:
        try:
            base.rmdir()  # rỗng thì bỏ, không thì thôi
        except OSError:
            pass
