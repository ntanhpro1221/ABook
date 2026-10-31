"""Bộ cập nhật của bản Qt (desktop_qt): host làm thay vỏ việc mà plugin updater của Tauri làm ở shell/src-tauri/src/main.rs.

Vỏ Qt chạy host với `--self-update`. `App.shell` khi ấy là `Updater.handle`: `{"check_update"}` / `{"install_update"}` của
server.py tới đây thay vì về vỏ. Mở app: kiểm một lần, im lặng khi mất mạng.
- Bản mới: báo như vỏ Tauri báo (`found`, tức `{"update": ...}` của host.py).
- Bấm "Cập nhật": tải gói vào thư mục tạm, kiểm chữ ký minisign (minisign_verify.file_ok, đòi đúng `version:` của
  latest.json), rồi nhờ vỏ `{"run_installer": path, "args": [...]}`. Vỏ dừng host, chạy bộ cài passive, thoát.
- Câu báo, hạn chờ và nơi ghi nhật ký giống vỏ Tauri, để hai bản nói cùng một lời.

Nơi hỏi và khoá công khai: `plugins.updater` của tauri.conf.json. Bản đóng gói không mang file ấy: build_windows_qt.ps1
chép đúng hai trường ấy vào resources/app/updater.json. Không bao giờ lấy khoá từ mạng.

Chặn trước khi tải (Lead 31-10):
- Chỉ https cho nơi hỏi và gói; http chỉ khi máy chủ là 127.0.0.1 / localhost (test, ABOOK_UPDATE_URL).
- Tên gói là `ABook_<x.y.z>_x64-setup.exe` với đúng số của latest.json. Không lấy tên thô từ URL, nên tên lạ (`..\\x.exe`,
  `%2e%2e`) không bao giờ thành đường ghi.
- Gói ghi vào %TEMP%\\ABook-update dựng mới mỗi lần.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .minisign_verify import file_ok

CHECK_TIMEOUT = 30.0  # giây: hỏi trang phát hành quá chừng này là coi như không có mạng
STALL = 60.0  # giây: đang tải gói mà không thêm byte nào chừng này là đứt mạng (không hạn cho cả lần tải)
PLATFORM = "windows-x86_64"
INSTALLER_ARGS = ["/P", "/UPDATE", "/R"]  # passive, giữ lựa chọn lối tắt, mở lại app khi xong (installer/abook.nsi)

NETWORK = "Chưa lấy được bản mới - mạng chập chờn hoặc không tới được trang phát hành. Bạn kiểm tra mạng rồi thử lại."
STALLED = "Đường tải bản mới đứng yên quá lâu. Bạn kiểm tra mạng rồi bấm Cập nhật lần nữa."
SIGNATURE = "Gói tải về không khớp chữ ký của ABook nên bạn chưa nên cài nó. Bạn thử lại sau ít phút."
INSTALL = "Chưa cài được bản mới. Bạn đóng rồi mở lại ABook, rồi thử lại."
PACKAGE = "Trang phát hành ghi một gói lạ nên ABook không tải nó. Bạn thử lại sau ít phút."

PACKAGE_NAME = re.compile(r"ABook_(\d+\.\d+\.\d+)_x64-setup\.exe")
LOCAL_HOSTS = {"127.0.0.1", "localhost"}

CHECKED_EVENT = "abook-update-checked"
FAILED_EVENT = "abook-update-failed"

_INTERNAL = Path(__file__).resolve().parents[2]


def config(app_root: Path = _INTERNAL) -> dict[str, Any]:
    """`{"endpoints": [...], "pubkey": ...}`: resources/app/updater.json của bản đóng gói, hay tauri.conf.json của cây mã."""
    packaged = app_root / "updater.json"
    if packaged.is_file():
        return json.loads(packaged.read_text(encoding="utf-8"))
    tauri = json.loads((app_root / "shell/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    return {key: tauri["plugins"]["updater"][key] for key in ("endpoints", "pubkey")}


def _version(text: str) -> tuple[tuple[int, ...], int, str] | None:
    """Khoá so sánh semver gọn: lõi số, bản trước phát hành (`-rc1`) đứng trước bản chính."""
    match = re.fullmatch(r"v?(\d+(?:\.\d+)*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?", text.strip())
    if not match:
        return None
    core = tuple(int(part) for part in match.group(1).split("."))
    core += (0,) * (3 - len(core))
    return core, 0 if match.group(2) else 1, match.group(2) or ""


def newer(candidate: str, current: str) -> bool:
    a, b = _version(candidate), _version(current)
    return a is not None and b is not None and a > b


def allowed_url(url: str) -> bool:
    """https, hay http tới chính máy này (máy chủ giả của test)."""
    parts = urllib.parse.urlsplit(url)
    return bool(parts.hostname) and (parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in LOCAL_HOSTS))


def package_name(url: str, version: str) -> str | None:
    """Tên file gói khi phần cuối đường dẫn của `url` đúng là `ABook_<version>_x64-setup.exe`; không thì None."""
    last = urllib.parse.unquote(urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1])
    match = PACKAGE_NAME.fullmatch(last)
    return last if match and match.group(1) == version else None


def _log(line: str) -> None:
    """Một dòng vào %LOCALAPPDATA%\\ABook\\logs\\host.log, như log_line của vỏ Tauri (trang chỉ nói gọn)."""
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return
    folder = Path(base) / "ABook" / "logs"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / "host.log").open("a", encoding="utf-8") as file:
            file.write(f"[updater] {line}\n")
    except OSError:
        pass


class Updater:
    """`send`: ống tới vỏ (host.Channel.send). `found(update)`: báo host có bản mới (`{"version", "notes"}`)."""

    def __init__(self, version: str, send: Callable[[dict[str, Any]], None], found: Callable[[dict[str, Any]], None],
                 settings: dict[str, Any] | None = None, folder: Path | None = None, log: Callable[[str], None] = _log,
                 check_timeout: float = CHECK_TIMEOUT, stall: float = STALL) -> None:
        settings = settings if settings is not None else config()
        override = os.environ.get("ABOOK_UPDATE_URL")
        self.endpoints = [override] if override else list(settings.get("endpoints") or [])
        self.pubkey = str(settings.get("pubkey") or "")
        self.version = version
        self.send = send
        self.found = found
        self.folder = folder or Path(tempfile.gettempdir()) / "ABook-update"
        self.log = log
        self.check_timeout = check_timeout
        self.stall = stall
        self._pending: dict[str, Any] | None = None
        self._lock = threading.Lock()
        self._installing = False

    def handle(self, message: dict[str, Any]) -> None:
        """Thay `App.shell`: hai yêu cầu của server.py chạy ở luồng nền; thứ khác (nếu có) vẫn về vỏ."""
        if message.get("check_update"):
            self.start(manual=True)
        elif message.get("install_update"):
            threading.Thread(target=self.install, name="update-install", daemon=True).start()
        else:
            self.send(message)

    def start(self, manual: bool = False) -> threading.Thread:
        thread = threading.Thread(target=self.check, args=(manual,), name="update-check", daemon=True)
        thread.start()
        return thread

    def _event(self, name: str, detail: Any) -> None:
        self.send({"event": name, "detail": detail})

    def check(self, manual: bool = False) -> None:
        """Hỏi latest.json. `manual`: kết quả nào cũng báo trang (`found` / `latest` / `failed` + câu), để nút không đứng im."""
        report = (lambda detail: self._event(CHECKED_EVENT, detail)) if manual else (lambda detail: None)
        try:
            release = self._latest()
        except Exception as error:  # noqa: BLE001 - mạng, JSON hỏng, thiếu trường: cùng một câu cho người dùng
            self.log(f"kiểm bản mới hỏng: {error!r}")
            return report({"state": "failed", "message": NETWORK})
        if release is None:
            return report({"state": "latest"})
        with self._lock:
            self._pending = release
        self.found({"version": release["version"], "notes": release["notes"]})
        report({"state": "found"})

    def _latest(self) -> dict[str, Any] | None:
        last: Exception | None = None
        for endpoint in self.endpoints:
            if not allowed_url(endpoint):
                last = ValueError(f"nơi hỏi không phải https: {endpoint}")
                continue
            try:
                with urllib.request.urlopen(endpoint, timeout=self.check_timeout) as response:
                    manifest = json.loads(response.read().decode("utf-8"))
            except Exception as error:  # noqa: BLE001 - thử nơi kế, như plugin của Tauri
                last = error
                continue
            version = str(manifest["version"])
            if not newer(version, self.version):
                return None
            platform = manifest["platforms"][PLATFORM]
            return {"version": version.lstrip("v"), "notes": str(manifest.get("notes") or ""),
                    "url": str(platform["url"]), "signature": str(platform["signature"])}
        raise last or RuntimeError("không có nơi hỏi bản mới")

    def install(self) -> None:
        """Tải gói, kiểm chữ ký, nhờ vỏ chạy bộ cài. Hỏng: trang được báo (`abook-update-failed`), bấm lại được."""
        with self._lock:
            release = self._pending
            if release is None or self._installing:
                return
            self._installing = True
        try:
            url = release["url"]
            name = package_name(url, release["version"])
            if name is None or not allowed_url(url):
                self.log(f"tải bản mới: gói lạ, không tải ({url!r}, bản {release['version']})")
                return self._event(FAILED_EVENT, PACKAGE)
            target = self.folder / name
            try:
                self._fresh_folder()
                self._download(url, target)
            except TimeoutError as error:
                self.log(f"tải bản mới: đứng yên quá lâu, bỏ ({error!r})")
                return self._event(FAILED_EVENT, STALLED)
            except Exception as error:  # noqa: BLE001 - mạng đứt / trả lỗi: thử lại được; ghi đĩa hỏng: câu của bước cài
                self.log(f"tải bản mới hỏng: {error!r}")
                return self._event(FAILED_EVENT, INSTALL if _disk(error) else NETWORK)
            if not file_ok(target, release["signature"], self.pubkey, version=release["version"]):
                self.log(f"tải bản mới: chữ ký không khớp ({target.name})")
                _discard(target)
                return self._event(FAILED_EVENT, SIGNATURE)
            self.send({"run_installer": str(target), "args": INSTALLER_ARGS})
        finally:
            with self._lock:
                self._installing = False

    def _fresh_folder(self) -> None:
        """Thư mục tải rỗng, dựng lại mỗi lần: gói cũ / tải dở không bao giờ được dùng lại. Thư mục là liên kết (junction) thì
        từ chối: xoá cây theo liên kết là xoá chỗ khác."""
        if os.path.lexists(self.folder):
            if _reparse(self.folder):
                raise OSError(0, "thư mục tải là liên kết", str(self.folder))
            shutil.rmtree(self.folder)
        self.folder.mkdir(parents=True)

    def _download(self, url: str, target: Path) -> None:
        """Tải vào `<target>.part` rồi đổi tên. Hạn của socket là `stall`: mỗi lần đọc chờ quá chừng ấy là đứt. Ít byte hơn
        Content-Length (đứt giữa chừng) là hỏng, không đổi tên."""
        part = target.with_name(target.name + ".part")
        try:
            with urllib.request.urlopen(url, timeout=self.stall) as response, part.open("wb") as file:
                started = time.monotonic()
                expected = response.headers.get("Content-Length")
                while True:
                    chunk = response.read(1 << 20)
                    if not chunk:
                        break
                    file.write(chunk)
            size = part.stat().st_size
            if expected is not None and size != int(expected):
                raise ConnectionError(f"gói tải dở: {size} / {expected} byte")
            self.log(f"tải bản mới xong: {size} byte trong {time.monotonic() - started:.1f} s")
            os.replace(part, target)
        finally:
            _discard(part)


def _disk(error: Exception) -> bool:
    """Lỗi ghi file tạm (đầy đĩa, bị khoá), khác lỗi mạng (URLError, đứt kết nối, hết hạn - cũng là OSError)."""
    return (isinstance(error, OSError) and not isinstance(error, (urllib.error.URLError, ConnectionError, TimeoutError))
            and getattr(error, "filename", None) is not None)


def _reparse(path: Path) -> bool:
    """Liên kết tượng trưng hay junction (os.path.isjunction chỉ có từ 3.12)."""
    return os.path.islink(path) or bool(getattr(os.lstat(path), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _discard(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass
