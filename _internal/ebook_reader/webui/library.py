"""Thư viện sách và tuỳ chọn của người dùng.

Thư viện = các thư mục sách nằm TRỰC TIẾP trong thư mục thư viện, cộng những sách người dùng tự mở ở nơi khác
("gần đây"). Server chỉ đọc sách nằm trong tập ấy.

Mã sách (`book_id`) là HMAC của đường dẫn với khoá bí mật của máy này (`book_ids.key` cạnh tuỳ chọn): cùng thư mục thì
cùng mã, mà mã không giải ngược ra đường dẫn - bản dựng trước 0.4.0 dùng chính đường dẫn mã hoá base64, lộ tên tài khoản
Windows qua link `#/book/<mã>`, ảnh chụp màn hình, nghe từ xa (docs/BOOK_IDS.md). Mã kiểu cũ vẫn được nhận
(`Library.resolve`, `canonical`) - link cũ, điện thoại chưa đổi khoá; dữ liệu lưu theo mã cũ được đổi khoá một lần lúc
mở app (`legacy_ids`, server.App).

Tuỳ chọn và vị trí nghe dở lưu ở `%LOCALAPPDATA%/ABook/preferences.json` - ghi atomic. (Tên cũ của thư mục là
"Ebook Reader": lần đầu mở với tên mới, các file của app được chuyển sang - `preferences_path`.)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any

from ..listener_overrides import overrides_path
from . import store

DEFAULT_PREFERENCES: dict[str, Any] = {
    "libraryRoot": "",
    "recents": [],
    "theme": "system",
    "positions": {},
    "playbackRate": 1.0,
    "volume": 0.9,
    "syncEnabled": False,
    # Studio từ xa (remote_studio.py): thiết bị đã ghép được điều khiển sản xuất. Tắt mặc định, tách khỏi quyền nghe.
    "remoteStudio": False,
    # Hẹn giờ ngủ: nhỏ dần bao lâu trước khi tắt, và mỗi lần "nghe thêm" cộng bao nhiêu phút.
    "sleepFadeSeconds": 30,
    "sleepExtendMinutes": 10,
    # Lưới an toàn ngủ quên: phát liên tục chừng này giờ không ai chạm máy thì tự dừng (0 = tắt).
    "safetyStopHours": 2,
    # Lịch đêm tự hẹn giờ: {"from": "22:00", "to": "06:00", "minutes": 30} hoặc None.
    "sleepSchedule": None,
}
MAX_RECENTS = 30


APP_DATA_FOLDER = "ABook"
LEGACY_APP_DATA_FOLDERS = ("Ebook Reader",)
# File của app nằm cạnh preferences.json (tuỳ chọn, dữ liệu nghe, máy đã ghép, phán quyết nghe lại, dấu vân tay audio).
APP_DATA_FILES = ("preferences.json", "listening.json", "devices.json", "reviews.json", "fingerprints.json")


def preferences_path() -> Path:
    override = os.environ.get("EBOOK_READER_PREFERENCES")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return Path.home() / ".ebook_reader" / "preferences.json"
    root = Path(base) / APP_DATA_FOLDER
    _move_legacy_app_data(Path(base), root)
    return root / "preferences.json"


def _move_legacy_app_data(base: Path, root: Path) -> None:
    """Thư mục dữ liệu mang tên cũ của app: chuyển các file của app sang thư mục tên mới, một lần - khi thư mục mới
    chưa có tuỳ chọn nào. Chỉ chuyển file của app (không đụng bộ nhớ đệm của trình duyệt nhúng)."""
    if (root / "preferences.json").exists():
        return
    for name in LEGACY_APP_DATA_FOLDERS:
        legacy = base / name
        files = [legacy / file for file in APP_DATA_FILES if (legacy / file).is_file()]
        if not files:
            continue
        root.mkdir(parents=True, exist_ok=True)
        for file in files:
            if (root / file.name).exists():
                continue  # thư mục mới đã có bản của nó: không đè
            try:
                os.replace(file, root / file.name)
            except OSError:
                continue  # file đang bị giữ: lần sau thử lại, app vẫn mở với tuỳ chọn mặc định
        return


def _legacy_output_folder() -> str:
    """Thư mục "Nơi lưu" của giao diện cũ (QSettings), để người dùng cũ mở app mới thấy ngay sách của mình."""
    try:
        from PySide6.QtCore import QSettings

        value = QSettings("OpenAI", "EbookReader").value("output", "", str)
        return str(value or "")
    except Exception:  # noqa: BLE001 - không có Qt hoặc registry lỗi: dùng mặc định
        return ""


ID_KEY_FILE = "book_ids.key"
ID_PATTERN = re.compile(r"[0-9a-f]{24}")  # 96 bit đầu của HMAC-SHA256, hex
_ID_KEYS: dict[str, bytes] = {}
_ID_LOCK = threading.Lock()


def _id_key() -> bytes:
    """Khoá bí mật của mã sách trên máy này: 32 byte ngẫu nhiên, tạo lần đầu cần tới, nằm cạnh preferences.json - đi
    cùng dữ liệu nghe nó đánh khoá (sao lưu / chép thư mục dữ liệu thì mã giữ nguyên). Tạo bằng O_EXCL: hai tiến trình
    cùng mở lần đầu thì một bên tạo, bên kia đọc lại khoá ấy. Không ghi được thư mục (ổ chỉ đọc): khoá suy từ đường dẫn
    thư mục dữ liệu - vẫn ổn định giữa các lần mở, chỉ kém bí mật."""
    path = preferences_path().with_name(ID_KEY_FILE)
    with _ID_LOCK:
        cached = _ID_KEYS.get(str(path))
        if cached is not None:
            return cached
        key = _read_or_create_key(path)
        _ID_KEYS[str(path)] = key
        return key


def _read_or_create_key(path: Path) -> bytes:
    for _attempt in range(20):
        try:
            key = bytes.fromhex(path.read_text(encoding="ascii").strip())
            if len(key) >= 16:
                return key
        except (OSError, ValueError):
            pass
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            time.sleep(0.05)  # tiến trình kia vừa tạo, chưa ghi xong: đọc lại
            continue
        except OSError:
            break
        key = secrets.token_bytes(32)
        with os.fdopen(handle, "w", encoding="ascii") as file:
            file.write(key.hex())
        return key
    return hashlib.sha256(b"abook-book-ids:" + str(path.parent).encode("utf-8")).digest()


def book_id(path: Path) -> str:
    """Mã sách của thư mục `path` trên máy này: cùng thư mục (không phân biệt hoa thường, dạng viết) thì cùng mã."""
    return hmac.new(_id_key(), _key(Path(path).resolve()).encode("utf-8"), hashlib.sha256).hexdigest()[:24]


def legacy_book_id(path: Path) -> str:
    """Mã sách kiểu cũ (đường dẫn mã hoá base64) - chỉ để nhận ra và đổi khoá dữ liệu cũ, không cấp ra nữa."""
    return base64.urlsafe_b64encode(str(path).encode("utf-8")).decode("ascii").rstrip("=")


def _decode_id(value: str) -> Path | None:
    """Đường dẫn trong một mã KIỂU CŨ; mã mới hay chuỗi lạ: None."""
    if ID_PATTERN.fullmatch(value):
        return None
    try:
        padded = value + "=" * (-len(value) % 4)
        text = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeError):
        return None
    # đường dẫn tuyệt đối (C:\..., \máy\..., /...): "open" hay mã rác giải ra được vẫn không phải mã sách
    return Path(text) if text and ("\\" in text or "/" in text) and Path(text).is_absolute() else None


def legacy_ids(keys: Any) -> dict[str, str]:
    """{mã cũ: mã mới} cho những khoá kiểu cũ trong `keys` - để đổi khoá dữ liệu lưu theo mã kiểu cũ (thư mục đã mất vẫn
    đổi: mã mới chỉ phụ thuộc đường dẫn)."""
    found: dict[str, str] = {}
    for key in keys:
        path = _decode_id(str(key)) if isinstance(key, str) else None
        if path is not None:
            found[key] = book_id(path)
    return found


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


class Preferences:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or preferences_path()
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        data = json.loads(json.dumps(DEFAULT_PREFERENCES))
        try:
            data.update(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
        if not data.get("libraryRoot"):
            data["libraryRoot"] = _legacy_output_folder() or str(Path.home() / "Audiobooks")
        return data

    def get(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._data))

    def update(self, changes: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            for key, value in changes.items():
                if key in DEFAULT_PREFERENCES:
                    self._data[key] = value
            self._save()
            return json.loads(json.dumps(self._data))

    def remember_position(self, book: str, chapter_id: int, seconds: float, duration: float) -> None:
        with self._lock:
            positions = self._data.setdefault("positions", {})
            positions[book] = {"chapterId": int(chapter_id), "seconds": round(float(seconds), 1),
                               "duration": round(float(duration), 1), "at": time.time()}
            self._save()

    def rename_positions(self, renamed: dict[str, str]) -> None:
        """Đổi khoá chỗ nghe dở ({mã cũ: mã mới}, `legacy_ids`); hai khoá về cùng một cuốn: chỗ ghi sau thắng."""
        with self._lock:
            positions = self._data.get("positions")
            if not isinstance(positions, dict) or not any(old in positions for old in renamed):
                return
            for old, new in renamed.items():
                if old == new or old not in positions:
                    continue
                moved = positions.pop(old)
                current = positions.get(new)
                if not isinstance(current, dict) or float((moved or {}).get("at") or 0) > float(current.get("at") or 0):
                    positions[new] = moved
            self._save()

    def add_recent(self, path: Path) -> None:
        with self._lock:
            recents = [item for item in self._data.get("recents", []) if _key(Path(item)) != _key(path)]
            self._data["recents"] = [str(path), *recents][:MAX_RECENTS]
            self._save()

    def forget_recent(self, path: Path) -> None:
        with self._lock:
            recents = [item for item in self._data.get("recents", []) if _key(Path(item)) != _key(path)]
            if recents != self._data.get("recents", []):
                self._data["recents"] = recents
                self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporary, self.path)


class Library:
    def __init__(self, preferences: Preferences) -> None:
        self.preferences = preferences
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = threading.Lock()

    @property
    def root(self) -> Path:
        return Path(self.preferences.get()["libraryRoot"]).expanduser()

    def projects(self) -> list[Path]:
        found: dict[str, Path] = {}
        root = self.root
        try:
            children = sorted(root.iterdir()) if root.is_dir() else []
        except OSError:
            children = []
        for child in children:
            if child.is_dir() and store.is_project(child):
                found.setdefault(_key(child), child.resolve())
        for item in self.preferences.get().get("recents", []):
            path = Path(item)
            if store.is_project(path):
                found.setdefault(_key(path), path.resolve())
        return list(found.values())

    def forget(self, project: Path) -> None:
        """Dự án đã bị xoá: bỏ khỏi danh sách gần đây và bộ đệm tóm tắt."""
        self.preferences.forget_recent(project)
        with self._lock:
            self._cache.pop(_key(project), None)

    def resolve(self, value: str) -> Path | None:
        """Dự án mang mã `value` (mã mới, hay mã kiểu cũ của cùng thư mục); ngoài thư viện: None."""
        return self._find(value, self.projects())

    @staticmethod
    def _find(value: str, allowed: list[Path]) -> Path | None:
        if ID_PATTERN.fullmatch(value):
            return next((path for path in allowed if book_id(path) == value), None)
        path = _decode_id(value)
        if path is None:
            return None
        return {_key(item): item for item in allowed}.get(_key(path))

    def canonical(self, value: str) -> str:
        """Mã hiện hành của cuốn mang mã `value`: mã kiểu cũ của một cuốn trong thư viện -> mã mới; còn lại giữ nguyên.
        Mọi chỗ dùng mã làm KHOÁ (dữ liệu nghe, phán quyết, hàng đợi) nhận mã qua đây."""
        if ID_PATTERN.fullmatch(value):
            return value
        path = self.resolve_listenable(value)
        return book_id(path) if path is not None else value

    def packages(self) -> list[Path]:
        """Cuốn mở từ file `.abook` (webui/packages.py) - nghe được, không phải dự án của Studio."""
        from . import packages  # packages -> listening -> library: nhập lúc gọi, không lúc nạp module

        return packages.folders(self.root)

    def resolve_listenable(self, value: str) -> Path | None:
        """Như `resolve`, cho phía Nghe: dự án hoặc cuốn đã nhập từ file."""
        project = self.resolve(value)
        if project is not None:
            return project
        return self._find(value, self.packages())

    def summary(self, project: Path, *, running: bool, starting: bool = False) -> dict[str, Any]:
        # Cả mốc của overrides.json (yêu cầu mới của người nghe đổi "pendingChanges") và tên đặt lại - không chạm DB.
        stamp = (store.touched(project), _mtime(overrides_path(project)), _mtime(project / store.RUN_MARKER),
                 _mtime(project / store.TITLE_FILE))
        key = _key(project)
        with self._lock:
            cached = self._cache.get(key)
        if cached and cached[0] == stamp and not running and not cached[1].get("running") and not starting:
            result = dict(cached[1])
        else:
            result = store.summarize(project, running=running)
            with self._lock:
                self._cache[key] = (stamp, result)
            result = dict(result)
        result["id"] = book_id(project)
        result["starting"] = starting
        position = self.preferences.get().get("positions", {}).get(result["id"])
        result["position"] = position
        return result
