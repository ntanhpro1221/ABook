"""Chỗ chờ trước Thùng rác: xoá một sách / dự án trên máy tính được "Hoàn tác" trong ~30 giây.

Thùng rác của Windows khôi phục từ app thì phải qua COM, nên xoá không đi thẳng vào đó. Xoá = đổi tên (`os.replace`, cùng ổ nên
tức thì, không chép byte nào) cả thư mục sang `<thư viện>/.trash-pending/<mã>/<tên gốc>` kèm `meta.json` (đường gốc, loại, lúc
xoá). Thư viện thấy sách biến mất ngay; "Hoàn tác" chỉ là đổi tên ngược lại. Hết `UNDO_SECONDS` (và lúc app mở / đóng) bộ dọn
chuyển thư mục vào Thùng rác đúng như trước đây.

Luật giữ cho chỗ này an toàn:
- Không bao giờ xoá hẳn: dọn không được (file khoá, ổ không có Thùng rác) thì để nguyên chỗ chờ, lần sau dọn tiếp.
- Trước khi gọi Thùng rác, thư mục được đổi tên NGƯỢC về đường gốc: Thùng rác ghi nhớ đường gốc để "Khôi phục" đưa nó về đúng
  chỗ cũ, không về trong `.trash-pending` (nơi lần dọn sau lại gom nó đi). Đường gốc đã bị chiếm (mở lại đúng file .abook trong
  hạn: tên cũ được cấp lại cho cuốn mới) thì đi qua một tên anh em còn trống cạnh đó ("<tên> (đã xoá)") - Windows khôi phục về
  tên ấy, không đè cuốn mới.
- Hai bước "đổi tên ra ngoài" và "gọi Thùng rác" có thể đứt giữa chừng (Thùng rác lỗi mà đổi tên ngược cũng lỗi, hay app chết):
  meta ghi `phase: recycling` + đường đang dùng + mã nhận dạng thư mục TRƯỚC khi đổi tên ra, nên lần dọn sau thấy dấu ấy thì
  tiếp tục đưa vào Thùng rác chứ không bỏ meta (cuốn đã xoá không được sống lại). Thư mục ở đường đó đã bị thay bằng cuốn khác
  (mã nhận dạng khác) thì không đụng tới. Trong khoảng đứt ấy thư viện vẫn có thể thấy cuốn ở đường đó cho tới lần dọn kế
  (lúc mở app dọn ngay); không lọc riêng vì đòi thư viện biết chỗ chờ - chi phí lớn hơn lợi.
- Người dùng bấm "Không" ở hộp "xoá hẳn" của Windows (thư mục quá lớn so với Thùng rác) thì coi như chưa xoá: cuốn ở lại chỗ cũ,
  không hỏi lặp. Hộp ấy cũng không hiện lúc đóng app (`ask=False`: cuốn nào Thùng rác không nhận thì để lần mở sau).
- `.trash-pending` nằm trong thư mục thư viện nhưng không phải dự án hay sách nhập: thư viện chỉ quét thư mục con có sổ dự án
  (store.is_project) hay nằm trong "Sách đã nhập", nên không bao giờ thấy nó như một cuốn sách.
"""
from __future__ import annotations

import json
import logging
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Callable

from . import actions

log = logging.getLogger(__name__)

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
        self._roots: dict[str, Path] = {}  # mã -> thư viện lúc xoá (đổi thư viện giữa hạn thì hoàn tác / dọn vẫn tìm đúng chỗ)

    def root_of(self, token: str, default: Path) -> Path:
        with self._lock:
            return self._roots.get(token, default)

    def roots(self) -> list[Path]:
        """Các thư viện còn cuốn nằm chờ do phiên này đặt vào (đổi thư viện giữa hạn thì thư viện cũ vẫn phải được dọn)."""
        with self._lock:
            return list(dict.fromkeys(self._roots.values()))

    def fits(self, root: Path, path: Path) -> bool:
        """Đổi tên được từ `path` vào chỗ chờ của `root` không: thư viện còn đó và cùng ổ (khác ổ thì đổi tên là CHÉP - không
        tức thì, không hoàn tác gọn được) và Thùng rác của ổ nhận cuốn này mà Windows không hỏi "xoá hẳn". Không thì nơi gọi
        chuyển thẳng vào Thùng rác như cũ: nếu có hộp hỏi thì hiện NGAY lúc người dùng bấm xoá, không bật bất ngờ ở lần dọn nền."""
        return root.is_dir() and _drive(root) == _drive(path) and FOLDER not in path.parts and actions.recycle_bin_accepts(path)

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
                self._roots[token] = root
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
            self._roots.pop(token, None)
            self._tidy(folder)
        self._tidy_base(root / FOLDER)
        return meta

    def sweep(self, root: Path, *, everything: bool = False, ask: bool = True) -> int:
        """Chuyển vào Thùng rác những mã đã quá `UNDO_SECONDS` (`everything`: mọi mã, lúc app mở / đóng). Trả số mã còn lại - dọn
        không được thì còn, lần sau thử tiếp; không bao giờ văng. `ask=False` (lúc đóng app, không được chờ ai bấm): cuốn mà
        Thùng rác không nhận trọn thì để lại, không gọi Thùng rác - Windows sẽ hiện hộp hỏi."""
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
                if meta is None or not self._recycle(folder, meta, ask):
                    left += 1
            if not folder.is_dir():
                self._roots.pop(folder.name, None)
        self._tidy_base(base)
        return left

    # ------------------------------------------------------------------------------------------------------------------

    def _recycle(self, folder: Path, meta: dict[str, Any], ask: bool) -> bool:
        item = folder / meta["name"]
        original = Path(meta["original"])
        target = Path(meta["via"]) if meta.get("phase") == "recycling" and isinstance(meta.get("via"), str) else None
        if target is not None and not item.is_dir():
            # Lần dọn trước đã đổi tên ra `target` mà chưa xong: tiếp tục, trừ khi ở đó đã là một thư mục khác.
            if target.is_dir() and _same_folder(target, meta.get("id")):
                return self._finish(folder, item, target, original, meta, ask)
            self._tidy(folder)  # không còn: đã vào Thùng rác (hay người dùng tự xoá)
            return True
        if not item.is_dir():
            self._tidy(folder)  # chỉ còn meta (thư mục đã đi tiếp ở lần dọn dở trước)
            return True
        if not ask and not actions.recycle_bin_accepts(item):
            return False
        target = _free_sibling(original)
        if target is None:
            return False
        self._write_meta(folder, {**meta, "phase": "recycling", "via": str(target), "id": _folder_id(item)})
        try:
            os.replace(item, target)  # về đường gốc (hay tên anh em còn trống) để Thùng rác ghi nhớ chỗ cũ (xem đầu file)
        except OSError:
            self._write_meta(folder, meta)
            return False
        return self._finish(folder, item, target, original, meta, ask=True)

    def _finish(self, folder: Path, item: Path, target: Path, original: Path, meta: dict[str, Any], ask: bool) -> bool:
        """Thư mục đã ở `target`: gọi Thùng rác. Lỗi thì đổi tên ngược về chỗ chờ (thư viện không được thấy lại cuốn đã xoá);
        ngược cũng lỗi thì meta giữ dấu `recycling` để lần sau tiếp tục - không bỏ meta."""
        if not ask and not actions.recycle_bin_accepts(target):
            return False
        try:
            actions.move_to_recycle_bin(target)
        except actions.RecycleCancelled:
            log.info("Người dùng không cho xoá %s - giữ lại, coi như chưa xoá", target)
            if target != original and not original.exists():
                try:
                    os.replace(target, original)
                except OSError:
                    pass
            self._tidy(folder)
            return True
        except OSError:
            try:
                os.replace(target, item)
            except OSError:
                return False
            self._write_meta(folder, meta)
            return False
        self._tidy(folder)
        return True

    @staticmethod
    def _write_meta(folder: Path, meta: dict[str, Any]) -> None:
        """Ghi lại meta; `meta` không có `phase` thì là bản gốc (bỏ dấu đang dọn)."""
        try:
            (folder / META).write_bytes(json.dumps(meta, ensure_ascii=False).encode("utf-8"))
        except OSError:
            pass

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


def _free_sibling(original: Path) -> Path | None:
    """Đường để đưa cuốn vào Thùng rác: chính đường gốc nếu còn trống, không thì "<tên> (đã xoá)" cạnh nó (rồi "(đã xoá 2)"...).
    None khi thư mục chứa đã mất."""
    if not original.parent.is_dir():
        return None
    if not original.exists():
        return original
    for number in range(1, 1000):
        candidate = original.with_name(f"{original.name} (đã xoá)" if number == 1 else f"{original.name} (đã xoá {number})")
        if not candidate.exists():
            return candidate
    return None


def _folder_id(path: Path) -> list[int] | None:
    """Mã nhận dạng thư mục (ổ + file index): đổi tên thì giữ nguyên, thư mục khác cùng tên thì khác. None khi hệ thống không có."""
    try:
        stat = path.stat()
    except OSError:
        return None
    return [stat.st_dev, stat.st_ino] if stat.st_ino else None


def _same_folder(path: Path, expected: Any) -> bool:
    return not expected or _folder_id(path) == list(expected)
