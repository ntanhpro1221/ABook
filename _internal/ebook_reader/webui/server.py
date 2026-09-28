"""Server HTTP cục bộ cho giao diện: JSON API + audio (có Range để tua) + frontend đã build.

Chỉ nghe trên 127.0.0.1. Mọi `/api` và `/media` cần mã phiên (header `X-Ebook-Token` hoặc `?t=`), và `Host`
phải là chính server - không thì một trang web bất kỳ trong trình duyệt của người dùng gọi được
`127.0.0.1:<cổng>` (hoặc qua DNS rebinding) để đọc sách hay bấm "Bắt đầu" thay họ.
"""
from __future__ import annotations

import base64
import binascii
import json
import mimetypes
import re
import secrets
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import parse_qs, unquote, urlsplit

from .. import listener_overrides
from . import actions, bookfile, cover_search, covers, listen_view, packages, store
from .fingerprints import Fingerprints
from .library import Library, Preferences, book_id
from .listening import RECORD_ID, Listening
from . import remote_books
from .remote_studio import REMOTE_HEADER, StudioGate
from .reviews import Reviews, review_view
from .casting_review import casting_chapter, casting_chapters
from .voice_picker import voice_choices
from .work_items import work_items
from .sync import Devices, ExclusiveHTTPServer, Remote, SyncApp, SyncServer, local_addresses, remote_command, SYNC_PORT

STATIC_DIR = Path(__file__).resolve().parent / "static"
MISSING_UI_PAGE = (
    "<!doctype html><html lang='vi'><meta charset='utf-8'><title>ABook</title>"
    "<body style='font-family:system-ui,sans-serif;background:#0e1115;color:#e8eaed;padding:48px;line-height:1.6'>"
    "<h1 style='font-size:22px'>Chưa dựng giao diện của ABook</h1>"
    "<p>Chạy <code>npm run build</code> trong thư mục <code>_internal\\ui</code> rồi mở lại ABook.</p>"
    "<p>Trong lúc chờ, giao diện cũ vẫn mở được: <code>app.py --classic</code>.</p></body></html>"
)
ASSET_DIR = Path(__file__).resolve().parents[1] / "assets"
VOICE_PREVIEW_DIR = ASSET_DIR / "voice_previews"
CHUNK = 256 * 1024
MAX_BODY = 1024 * 1024
TYPES = {
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
}


class Dialogs(Protocol):
    def pick_folder(self, title: str, start: str) -> str | None: ...
    def pick_files(self, title: str, start: str) -> list[str]: ...
    def pick_book_file(self, title: str, start: str) -> str | None: ...


# Câu chữ cho người đọc của các mã từ chối. listener_overrides.py giữ mã (file khoá chất lượng), câu chữ ở đây để sửa
# chữ không đổi hash chất lượng.
PRONUNCIATION_PROBLEMS = {
    listener_overrides.MULTI_WORD: "Chỉ sửa được cách đọc của MỘT từ - cách đọc lưu theo từng từ.",
    listener_overrides.NOT_VIETNAMESE: "Cách đọc phải là các âm tiết tiếng Việt nối bằng gạch nối, ví dụ Hên-khơ.",
}
LINE_PROBLEMS = {
    listener_overrides.UNKNOWN_LINE: "Không còn câu này trong sách.",
    listener_overrides.SOURCE_CHANGED: "Chữ của câu này đã đổi - tải lại chương.",
    listener_overrides.BAD_KIND: "Loại đoạn phải là lời kể, lời thoại hay nội tâm.",
    listener_overrides.BAD_EMOTION: "Cảm xúc này không có trong bộ giọng.",
    listener_overrides.NOT_SPEECH: "Lời kể không có người nói - đổi thành lời thoại trước.",
    listener_overrides.NO_VOICE: "Người này chưa có giọng trong sách (chưa nói câu nào) - chưa gán được.",
}

VOICE_PROBLEMS = {
    listener_overrides.UNKNOWN_CHARACTER: "Không có nhân vật này trong sách.",
    listener_overrides.NOT_A_CHARACTER: "Giọng người kể chọn khi tạo sách, không đổi ở đây.",
    listener_overrides.NO_VOICE: "Nhân vật này chưa có giọng (chưa qua bước phân vai) - chưa đổi được.",
    listener_overrides.UNKNOWN_PRESET: "Giọng này không dùng cho nhân vật được (không có, hay là giọng người kể).",
    listener_overrides.BAD_GENDER: "Giới phải là nam hoặc nữ.",
}

SPEAKER_PROBLEMS = {
    listener_overrides.UNKNOWN_LINE: "Không còn câu này trong sách.",
    listener_overrides.SOURCE_CHANGED: "Chữ của câu này đã đổi từ lúc máy chấm - tải lại danh sách việc.",
    listener_overrides.NOT_SPEECH: "Câu này là lời kể, không có người nói để đổi.",
    listener_overrides.NO_VOICE: "Người này chưa có giọng trong sách (chưa nói câu nào) - chưa gán được.",
}


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _held_record(body: dict[str, Any]) -> str | None:
    """Hồ sơ nghe mà trình phát đang phát (nó ghi vào đúng hồ sơ ấy, xem `Listening._held`); không có thì None."""
    record = body.get("record")
    return record if isinstance(record, str) and RECORD_ID.fullmatch(record) else None


class App:
    def __init__(
        self,
        *,
        preferences: Preferences,
        runner: actions.Runner,
        token: str | None,
        dialogs: Dialogs | None = None,
        read_only: bool = False,
        static_dir: Path = STATIC_DIR,
        version: str = "",
        listening: Listening | None = None,
    ) -> None:
        self.preferences = preferences
        self.listening = listening or Listening(preferences.path.with_name("listening.json"))
        self.fingerprints = Fingerprints(self.listening.path.with_name("fingerprints.json"))
        self.devices = Devices(preferences.path.with_name("devices.json"))
        self.remote = Remote()
        self.sync_server: SyncServer | None = None
        self.sync_host = "0.0.0.0"
        self.sync_port = SYNC_PORT
        self.sync_error = ""
        self.library = Library(preferences)
        self.jobs = actions.Jobs(runner)
        self.runner = runner
        self.token = token
        self.dialogs = dialogs
        self.read_only = read_only
        self.static_dir = static_dir
        self.version = version
        self.reviews = Reviews(preferences.path.with_name("reviews.json"))
        # Thư mục đã xuất trong phiên này - chỉ những thư mục này được mở bằng "Mở thư mục" sau khi xuất.
        self.exports: set[str] = set()
        # Hàng đợi sản xuất: hai cuốn chạy cùng lúc tranh nhau GPU (phân tích cần ~6,2 GB trên card 8 GB), nên cuốn
        # thứ hai xếp hàng và tự bắt đầu khi cuốn đang chạy xong. Hàng đợi sống cùng app (đóng app là bỏ hàng).
        self.queue: list[str] = []
        self._queue_lock = threading.RLock()  # summary() lấy lại khoá này từ trong start/stop
        self._queue_thread: threading.Thread | None = None
        # Cổng của chính máy chủ giao diện này (Server đặt) - Studio từ xa chuyển tiếp API về đây. 0: chưa chạy.
        self.local_port = 0
        # Máy tính khác đã ghép (remote_books.py): thư viện của chúng hiện thành sách "Trên máy khác".
        self.computers = remote_books.Computers(preferences.path.with_name("computers.json"))
        remote_books.configure(self.computers)
        self._remote_refreshed = 0.0
        self._remote_lock = threading.Lock()
        self._state_synced: dict[str, float] = {}
        # App Windows đóng gói (webui/host.py): vỏ Tauri báo có bản mới (`update`), nhận lệnh cài qua `shell`; Studio
        # (thư viện + model làm sách) tải thêm khi cần (`studio`, webui/studio_setup.py). Bản dev: cả ba là None.
        self.update: dict[str, Any] | None = None
        self.shell: Callable[[dict[str, Any]], None] | None = None
        self.studio: Any = None

    # ---- sách ------------------------------------------------------------------------------------------

    def _book(self, value: str) -> Path:
        path = self.library.resolve(value)
        if path is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Không tìm thấy sách này trong thư viện")
        return path

    def _listenable(self, value: str) -> Path:
        """Phía Nghe: dự án hoặc cuốn mở từ file `.abook` (webui/packages.py). Studio vẫn chỉ dùng `_book`."""
        path = self.library.resolve_listenable(value)
        if path is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Không tìm thấy sách này trong thư viện")
        return path

    def install_update(self) -> dict[str, Any]:
        """Người dùng bấm "Cập nhật": vỏ tải gói đã ký, dừng server này, chạy bộ cài rồi mở lại app (docs/PACKAGING.md)."""
        if self.shell is None or not self.update:
            raise ApiError(HTTPStatus.CONFLICT, "Không có bản mới để cài")
        self.shell({"install_update": True})
        return {"installing": str(self.update.get("version") or "")}

    def open_book_file(self, path: str = "") -> dict[str, Any]:
        """Mở một file `.abook`: chọn bằng hộp thoại của cửa sổ app, hoặc đường dẫn có sẵn (bấm đúp file trong
        Explorer - desktop.py chuyển tới). Trả mã cuốn trong thư viện và cách mở (`packages.import_file`)."""
        self._mutating()
        if not path:
            if self.dialogs is None:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Mở file sách trong cửa sổ app ABook")
            path = self.dialogs.pick_book_file("Mở file sách", str(Path.home())) or ""
            if not path:
                return {"id": None}
        if not Path(path).is_file():
            raise ApiError(HTTPStatus.NOT_FOUND, "Không tìm thấy file sách này - có thể nó đã bị chuyển hay xoá")
        try:
            target, how = packages.import_file(Path(path), self.library.root, self.library.projects(), self.fingerprints)
        except bookfile.BookFileError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error
        return {"id": book_id(target), "how": how}

    def summary(self, path: Path) -> dict[str, Any]:
        running = self.runner.running(path)
        result = self.library.summary(path, running=running, starting=self.jobs.starting(path))
        result["startError"] = self.jobs.error(path)
        result["cover"] = covers.cover_view(path, result["id"])
        result.pop("position", None)
        with self._queue_lock:
            result["queuePosition"] = self.queue.index(result["id"]) + 1 if result["id"] in self.queue else None
        return result

    def _busy_elsewhere(self, path: Path) -> Path | None:
        for other in self.library.projects():
            if other != path and (self.runner.running(other) or self.jobs.starting(other)):
                return other
        return None

    def _drain_queue(self) -> None:
        while True:
            time.sleep(15)
            with self._queue_lock:
                if not self.queue:
                    self._queue_thread = None
                    return
                head = self.queue[0]
            path = self.library.resolve(head)
            if path is None:
                with self._queue_lock:
                    self.queue.remove(head)
                continue
            if self._busy_elsewhere(path) is None:
                with self._queue_lock:
                    if self.queue and self.queue[0] == head:
                        self.queue.pop(0)
                self.jobs.start(path)

    def library_view(self) -> dict[str, Any]:
        books = []
        for path in self.library.projects():
            try:
                books.append(self.summary(path))
            except Exception as exc:  # noqa: BLE001 - một sách hỏng không được làm mất cả thư viện
                books.append({"id": book_id(path), "path": str(path), "title": path.name, "broken": str(exc)})
        books.sort(key=lambda book: book.get("updatedAt") or 0, reverse=True)
        return {"root": str(self.library.root), "books": books}

    def book_view(self, value: str) -> dict[str, Any]:
        path = self._book(value)
        return {"book": self.summary(path), "chapters": store.chapters(path)}

    def _mutating(self) -> None:
        if self.read_only:
            raise ApiError(HTTPStatus.FORBIDDEN, "Giao diện đang ở chế độ chỉ xem")

    def start(self, value: str, *, now: bool = False) -> dict[str, Any]:
        self._mutating()
        path = self._book(value)
        if self.runner.running(path):
            return self.summary(path)
        if not now and self._busy_elsewhere(path) is not None:
            with self._queue_lock:
                if value not in self.queue:
                    self.queue.append(value)
                if self._queue_thread is None:
                    self._queue_thread = threading.Thread(target=self._drain_queue, name="production-queue", daemon=True)
                    self._queue_thread.start()
            return self.summary(path)
        with self._queue_lock:
            if value in self.queue:
                self.queue.remove(value)
        self.jobs.start(path)
        return self.summary(path)

    def stop(self, value: str) -> dict[str, Any]:
        self._mutating()
        path = self._book(value)
        with self._queue_lock:
            queued = value in self.queue
            if queued:
                # Đang xếp hàng: "Dừng" nghĩa là bỏ khỏi hàng, không có gì để dừng.
                self.queue.remove(value)
        if queued:
            return self.summary(path)  # ngoài khoá: summary() cũng lấy khoá này (Lock không vào lại được)
        self.jobs.stop(path)
        return self.summary(path)

    def create(self, body: dict[str, Any]) -> dict[str, Any]:
        self._mutating()
        paths = [str(item) for item in body.get("paths", [])]
        root = actions.create_book(
            self.library.root, paths, str(body.get("title", "")), str(body.get("profile", "high_quality")),
            str(body.get("narrator", "")), str(body.get("firstPerson", "")),
            settings_overrides=self.studio.settings_overrides() if self.studio is not None else None,
        )
        self.preferences.add_recent(root)
        if body.get("start"):
            # Qua hàng đợi như nút "Bắt đầu": cuốn đang chạy thì cuốn mới xếp hàng, không tranh GPU (soát 28-09 - trước
            # đây "Tạo + bắt đầu ngay" chạy song song với cuốn đang sản xuất).
            self.start(book_id(root))
        return {"id": book_id(root)}

    def open_existing(self, body: dict[str, Any]) -> dict[str, Any]:
        path = Path(str(body.get("path", ""))).expanduser()
        if not store.is_project(path):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thư mục này không phải một sách của ABook")
        self.preferences.add_recent(path.resolve())
        return {"id": book_id(path.resolve())}

    # ---- đồng bộ điện thoại ------------------------------------------------------------------------------

    def sync_view(self) -> dict[str, Any]:
        running = self.sync_server is not None
        return {
            "enabled": running,
            "wanted": bool(self.preferences.get().get("syncEnabled")),
            "error": self.sync_error,
            "name": socket_name(),
            "port": self.sync_server.port if running else self.sync_port,
            "addresses": local_addresses() if self.sync_host == "0.0.0.0" else [self.sync_host],
            "pairing": self.devices.pairing() if running else None,
            "pairingBlocked": running and self.devices.blocked,
            "devices": sorted(self.devices.list(), key=lambda device: -float(device.get("lastSeen") or 0)),
            # Studio từ xa (remote_studio.py): công tắc riêng, tách khỏi quyền nghe của điện thoại.
            "remoteStudio": bool(self.preferences.get().get("remoteStudio")),
        }

    def set_remote_studio(self, enabled: bool) -> dict[str, Any]:
        """Cho / thôi cho thiết bị đã ghép điều khiển sản xuất. Cổng đồng bộ đọc lại công tắc mỗi yêu cầu: tắt là đóng
        ngay, kể cả với trang Studio đang mở trên điện thoại."""
        self.preferences.update({"remoteStudio": enabled})
        return self.sync_view()

    def set_sync(self, enabled: bool) -> dict[str, Any]:
        """Bật/tắt đồng bộ. Tuỳ chọn lưu Ý MUỐN của người dùng, không lưu kết quả: cổng bận một lần lúc khởi
        động không được tự tắt đồng bộ vĩnh viễn - lần mở sau thử lại."""
        if enabled and self.sync_server is None:
            try:
                studio = StudioGate(allowed=lambda: bool(self.preferences.get().get("remoteStudio")),
                                    port=lambda: self.local_port, token=self.token, static_dir=self.static_dir)
                app = SyncApp(self.library, self.listening, self.devices, socket_name(), self.remote, studio=studio)
                self.sync_server = SyncServer(app, host=self.sync_host, port=self.sync_port).start()
                self.sync_error = ""
            except OSError as error:
                self.sync_error = f"Không mở được cổng đồng bộ {self.sync_port}: {error.strerror or error}"
        elif not enabled:
            self.sync_error = ""
            self.devices.cancel_pairing()
            self._stop_sync()
        if self.preferences.get().get("syncEnabled") != enabled:
            self.preferences.update({"syncEnabled": enabled})
        return self.sync_view()

    def _stop_sync(self) -> None:
        # Trả lời ngay các lần "hỏi dài" đang treo, rồi mới tắt máy chủ - không để luồng nào đợi 25 giây vô ích.
        self.remote.reset()
        if self.sync_server is not None:
            self.sync_server.stop()
            self.sync_server = None

    def close(self) -> None:
        """App đóng: tắt cổng đồng bộ nhưng giữ nguyên lựa chọn của người dùng cho lần mở sau."""
        self._stop_sync()

    def remote_view(self) -> dict[str, Any]:
        """Điện thoại đang có sách trên trình phát (PLAYER_RESEARCH #12), kèm những gì máy tính biết về cuốn ấy: có
        trong thư viện không (để "Nghe trên máy tính") và ảnh bìa. Giao diện hỏi mỗi 1,5 giây nên ở đây không mở SQLite."""
        phones = []
        for phone in self.remote.view() if self.sync_server is not None else []:
            path = self.library.resolve(phone["bookId"]) if phone["bookId"] else None
            phone["known"] = path is not None
            phone["cover"] = covers.cover_view(path, phone["bookId"]) if path is not None else None
            phones.append(phone)
        return {"phones": phones}

    def remote_send(self, device: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            command = remote_command(body)
        except ValueError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error
        try:
            return {"id": self.remote.send(device, command)["id"]}
        except LookupError as error:
            raise ApiError(HTTPStatus.CONFLICT, "Điện thoại không còn kết nối - mở app trên điện thoại rồi thử lại") from error

    # ---- nghe ------------------------------------------------------------------------------------------

    def refresh_remote(self, *, wait: bool = False) -> None:
        """Hỏi lại thư viện của các máy tính khác: chạy nền, tối đa mỗi phút một lần (thư viện được hỏi mỗi vài giây);
        `wait` - ngay và đợi xong (vừa ghép, người dùng bấm làm mới)."""
        if not self.computers.list():
            return
        def run() -> None:
            try:
                remote_books.refresh(self.library.root, self.computers)
            finally:
                self._remote_lock.release()
        if wait:
            self._remote_lock.acquire()
            self._remote_refreshed = time.time()
            run()
            return
        if time.time() - self._remote_refreshed < 60 or not self._remote_lock.acquire(blocking=False):
            return
        self._remote_refreshed = time.time()
        threading.Thread(target=run, name="remote-books", daemon=True).start()

    def sync_remote_state(self, value: str, *, wait: bool) -> None:
        """Chỗ nghe của một cuốn "Trên máy khác", hai chiều: gửi bản của máy này, gộp bản máy kia trả về (theo mốc thời gian
        từng phần, như điện thoại với máy tính). Mở sách: đợi, trần 1,5 giây (máy kia tắt thì trang không đứng chờ). Đang
        nghe / đánh dấu: chạy nền, tối đa mỗi 30 giây một lần - mọi phần mang mốc thời gian, gửi muộn vẫn gộp đúng."""
        path = self.library.resolve_listenable(value)
        if path is None or not packages.is_package(path):
            return
        book = packages.manifest(path)
        if remote_books.remote_of(book) is None:
            return
        now = time.time()
        if not wait and now - self._state_synced.get(value, 0.0) < 30:
            return
        self._state_synced[value] = now

        def run() -> None:
            reply = remote_books.exchange_state(book, self.listening.get(value), timeout=1.5 if wait else 4)
            if reply is not None:
                self.listening.merge(value, {key: item for key, item in reply.items() if key not in ("night", "sessions")})
        if wait:
            run()
        else:
            threading.Thread(target=run, name="remote-state", daemon=True).start()

    def computers_view(self) -> dict[str, Any]:
        return {"name": socket_name(), "computers": self.computers.list()}

    def pair_computer(self, address: str, code: str) -> dict[str, Any]:
        self._mutating()
        try:
            self.computers.pair(address, code, socket_name())
        except remote_books.RemoteError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error
        self.refresh_remote(wait=True)
        return self.computers_view()

    def forget_computer(self, computer: str) -> dict[str, Any]:
        self._mutating()
        self.computers.forget(computer, self.library.root)
        return self.computers_view()

    def listen_library(self) -> list[dict[str, Any]]:
        """Sách nghe được: mọi sách đã có ít nhất một chương xong - đang sản xuất cũng nghe được phần đã xong. Sách vừa
        tạo, đang làm mà chưa có chương nào, cũng có mặt (chưa nghe được) - người mới tạo sách hỏi "sách của tôi đâu?"."""
        self.refresh_remote()
        books = []
        for path in self.library.projects():
            try:
                summary = self.summary(path)
            except Exception:  # noqa: BLE001 - sách hỏng thì phía Studio báo; phía Nghe bỏ qua
                continue
            producing = bool(summary.get("running") or summary.get("starting"))
            if summary.get("chapters", {}).get("completed", 0) <= 0 and not producing:
                continue
            view = listen_view.book(path, summary["id"], summary, self.listening.get(summary["id"]), with_chapters=False)
            view["eta"] = summary.get("eta")
            books.append(view)
        for path in self.library.packages():
            value = book_id(path)
            try:
                books.append(packages.listen(path, value, self.listening.get(value), with_chapters=False))
            except (OSError, ValueError):  # gói hỏng: bỏ qua, như sách hỏng
                continue
        books.sort(key=lambda item: ((item["state"].get("last") or {}).get("at") or 0, item.get("updatedAt") or 0),
                   reverse=True)
        return books

    def listen_book(self, value: str) -> dict[str, Any]:
        path = self._listenable(value)
        self.sync_remote_state(value, wait=True)
        if packages.is_package(path):
            view = packages.listen(path, value, self.listening.get(value))
        else:
            view = listen_view.book(path, value, self.summary(path), self.listening.get(value))
        view["records"] = self.listening.records(value)  # hồ sơ nghe gắn với cuốn này (webui/listening.py)
        return view

    def voices(self) -> list[dict[str, Any]]:
        from ..voice_catalog import DEFAULT_NARRATOR_BY_GENDER, VOICE_PREVIEW_FILENAMES, narrator_presets

        defaults = set(DEFAULT_NARRATOR_BY_GENDER.values())
        return [
            {
                "name": preset["name"],
                "gender": {"male": "Nam", "female": "Nữ"}.get(preset["gender"], ""),
                "region": preset["region"],
                "style": {"tu_nhien": "Tự nhiên", "doc_truyen": "Kể chuyện"}.get(preset["style"], preset["style"]),
                "recommended": preset["name"] in defaults,
                "preview": bool(VOICE_PREVIEW_FILENAMES.get(preset["name"])),
            }
            for preset in narrator_presets()
        ]

    def voice_file(self, name: str) -> Path | None:
        from ..voice_catalog import VOICE_PREVIEW_FILENAMES

        filename = VOICE_PREVIEW_FILENAMES.get(name)
        path = VOICE_PREVIEW_DIR / filename if filename else None
        return path if path and path.is_file() else None


# ---- HTTP ------------------------------------------------------------------------------------------------

Route = tuple[str, re.Pattern[str], Callable[..., Any]]


class Handler(BaseHTTPRequestHandler):
    server_version = "EbookReader"
    protocol_version = "HTTP/1.1"
    app: App
    port: int

    # Không in log ra stderr: server sống trong pythonw, không có console.
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    # ---- khung chung -----------------------------------------------------------------------------------

    def _allowed_host(self) -> bool:
        host = (self.headers.get("Host") or "").lower()
        return host in {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}

    def _authorized(self, query: dict[str, list[str]]) -> bool:
        token = self.app.token
        if token is None:
            return True
        supplied = self.headers.get("X-Ebook-Token") or (query.get("t") or [""])[0]
        return secrets.compare_digest(supplied, token)

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self, limit: int = MAX_BODY) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length > limit:
            raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Yêu cầu quá lớn")
        if not length:
            return {}
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, "JSON không hợp lệ") from exc
        return data if isinstance(data, dict) else {}

    def _send_file(self, path: Path, *, cache: bool = False) -> None:
        size = path.stat().st_size
        content_type = TYPES.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        start, end = 0, size - 1
        status = HTTPStatus.OK
        match = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range") or "")
        if match and size:
            first, last = match.groups()
            if first:
                start = int(first)
                end = min(int(last), size - 1) if last else size - 1
            elif last:
                start = max(0, size - int(last))
            if start > end or start >= size:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            status = HTTPStatus.PARTIAL_CONTENT
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Cache-Control", "public, max-age=31536000, immutable" if cache else "no-cache")
        self.end_headers()
        if self.command == "HEAD":
            return
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = handle.read(min(CHUNK, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _remote(self) -> bool:
        """Yêu cầu do Studio từ xa chuyển tới (remote_studio.forward gắn header): thiết bị ở xa không được chỉ đường
        dẫn tuỳ ý trên máy này - kể cả đường UNC, thứ khiến Windows tự nối SMB tới máy khác (soát bảo mật 28-09)."""
        return self.headers.get(REMOTE_HEADER) == "1"

    def _source_paths(self, raw: Any) -> list[str]:
        paths = [str(item) for item in (raw or [])]
        if self._remote():
            uploads = Path(self.app.preferences.get()["libraryRoot"]) / actions.UPLOAD_FOLDER
            if not all(actions.inside_folder(path, uploads) for path in paths):
                raise ApiError(HTTPStatus.FORBIDDEN, "Từ xa chỉ dùng được các chương đã gửi lên máy tính")
        return paths

    def _target(self, body: dict[str, Any]) -> str:
        """Nơi xuất: từ xa luôn là thư mục mặc định trong thư viện, không bao giờ một đường do thiết bị ở xa chỉ."""
        return "" if self._remote() else str(body.get("target") or "").strip()

    def _static(self, path_text: str) -> None:
        root = self.app.static_dir
        relative = unquote(path_text).lstrip("/") or "index.html"
        if "\\" in relative or ":" in relative:
            relative = "index.html"  # `\\máy\share` thành đường UNC: Windows nối SMB trước khi `relative_to` kịp chặn
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            candidate = root / "index.html"
        if not candidate.is_file():
            candidate = root / "index.html"
        if not candidate.is_file():
            # Cửa sổ app (desktop.py) mở thẳng trang này: nói cách sửa bằng trang đọc được, không phải JSON thô.
            body = MISSING_UI_PAGE.encode("utf-8")
            self.send_response(HTTPStatus.SERVICE_UNAVAILABLE)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._send_file(candidate, cache="/assets/" in candidate.as_posix())

    # ---- định tuyến ------------------------------------------------------------------------------------

    def _dispatch(self, method: str) -> None:
        parts = urlsplit(self.path)
        query = parse_qs(parts.query)
        try:
            if not self._allowed_host():
                raise ApiError(HTTPStatus.FORBIDDEN, "Host không hợp lệ")
            path = parts.path
            if not (path.startswith("/api/") or path.startswith("/media/")):
                if method not in ("GET", "HEAD"):
                    raise ApiError(HTTPStatus.METHOD_NOT_ALLOWED, "Không hỗ trợ")
                self._static(path)
                return
            if not self._authorized(query):
                raise ApiError(HTTPStatus.UNAUTHORIZED, "Thiếu mã phiên")
            for verb, pattern, handler in ROUTES:
                if verb != method and not (verb == "GET" and method == "HEAD"):
                    continue
                match = pattern.fullmatch(path)
                if match:
                    handler(self, query, *[unquote(group) for group in match.groups()])
                    return
            raise ApiError(HTTPStatus.NOT_FOUND, "Không có đường dẫn này")
        except ApiError as error:
            self._send_json(error.status, {"error": error.message})
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            return
        except FileNotFoundError as error:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": f"Không thấy file: {error}"})
        except ValueError as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except Exception as error:  # noqa: BLE001 - lỗi bất kỳ vẫn phải về thành JSON cho giao diện
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"{type(error).__name__}: {error}"})

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

    def do_HEAD(self) -> None:  # noqa: N802
        self._dispatch("HEAD")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def do_PUT(self) -> None:  # noqa: N802
        self._dispatch("PUT")

    def do_DELETE(self) -> None:  # noqa: N802
        self._dispatch("DELETE")

    # ---- các đường dẫn ---------------------------------------------------------------------------------

    def get_app(self, _query: dict[str, list[str]]) -> None:
        prefs = self.app.preferences.get()
        self._send_json(HTTPStatus.OK, {
            "version": self.app.version,
            "readOnly": self.app.read_only,
            "dialogs": self.app.dialogs is not None,
            # App Windows đóng gói: bản mới vỏ tìm thấy ({version, notes}), hay None; Studio đã cài chưa (None: bản dev,
            # Studio chính là runtime cạnh mã nguồn).
            "update": self.app.update,
            "studio": None if self.app.studio is None else {"installed": self.app.studio.installed(),
                                                             "outdated": bool(self.app.studio.outdated())},
            "libraryRoot": prefs["libraryRoot"],
            "theme": prefs["theme"],
            "playbackRate": prefs["playbackRate"],
            "volume": prefs["volume"],
            "sleepFadeSeconds": prefs.get("sleepFadeSeconds", 30),
            "sleepExtendMinutes": prefs.get("sleepExtendMinutes", 10),
            "safetyStopHours": prefs.get("safetyStopHours", 2),
            "sleepSchedule": prefs.get("sleepSchedule"),
        })

    def get_library(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.library_view())

    def get_book(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.book_view(value))

    def get_cast(self, _query: dict[str, list[str]], value: str) -> None:
        path = self.app._listenable(value)
        self._send_json(HTTPStatus.OK, packages.cast(path) if packages.is_package(path) else store.cast(path))

    def get_activity(self, query: dict[str, list[str]], value: str) -> None:
        technical = (query.get("technical") or ["0"])[0] == "1"
        self._send_json(HTTPStatus.OK, store.activity(self.app._book(value), technical=technical))

    def get_script(self, _query: dict[str, list[str]], value: str, chapter: str) -> None:
        path = self.app._listenable(value)
        script = (packages.script(path, int(chapter)) if packages.is_package(path)
                  else store.chapter_script(path, int(chapter)))
        if script is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Không có chương này")
        self._send_json(HTTPStatus.OK, script)

    def post_start(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.ACCEPTED, self.app.start(value))

    def post_stop(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.ACCEPTED, self.app.stop(value))

    def post_reveal(self, _query: dict[str, list[str]], value: str) -> None:
        actions.reveal(self.app._book(value))
        self._send_json(HTTPStatus.OK, {"ok": True})

    def post_export(self, _query: dict[str, list[str]], value: str) -> None:
        from .export import export_book

        project = self.app._book(value)
        body = self._body()
        target = self._target(body)
        root = Path(target) if target else Path(self.app.preferences.get()["libraryRoot"]) / "Đã xuất"
        try:
            result = export_book(project, root, cover=body.get("cover"))
        except ValueError as error:
            raise ApiError(HTTPStatus.CONFLICT, str(error)) from error
        self.app.exports.add(result["folder"])
        self._send_json(HTTPStatus.OK, result)

    def post_bookfile(self, _query: dict[str, list[str]], value: str) -> None:
        # Một cuốn trong một file (bookfile.py) - mở bằng app ở máy khác, gửi cho người khác.
        project = self.app._book(value)
        target = self._target(self._body())
        root = Path(target) if target else Path(self.app.preferences.get()["libraryRoot"]) / "Đã xuất"
        try:
            path = bookfile.pack(project, root / bookfile.default_name(store.summarize(project)["title"] or project.name))
        except bookfile.BookFileError as error:
            raise ApiError(HTTPStatus.CONFLICT, str(error)) from error
        self.app.exports.add(str(path.parent))
        self._send_json(HTTPStatus.OK, {"file": str(path), "folder": str(path.parent), "size": path.stat().st_size})

    def get_review(self, query: dict[str, list[str]], value: str) -> None:
        project = self.app._book(value)
        verdicts = self.app.reviews.get(value)
        self._send_json(HTTPStatus.OK, review_view(project, verdicts, include_minor=query.get("all") == ["1"]))

    def get_work(self, _query: dict[str, list[str]], value: str) -> None:
        # "Việc cần anh" (docs/STUDIO_REVIEW.md): chỗ máy nghi ngờ, xếp theo lợi trên mỗi lần bấm.
        self._send_json(HTTPStatus.OK, work_items(self.app._book(value)))

    def get_casting(self, _query: dict[str, list[str]], value: str) -> None:
        # Tab "Kịch bản" (casting_review.py): chương nào bao nhiêu câu thoại, bao nhiêu chỗ máy nghi, bao nhiêu câu đã quyết.
        self._send_json(HTTPStatus.OK, casting_chapters(self.app._book(value)))

    def get_casting_chapter(self, _query: dict[str, list[str]], value: str, chapter: str) -> None:
        view = casting_chapter(self.app._book(value), int(chapter))
        if view is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Không có chương này")
        self._send_json(HTTPStatus.OK, view)

    def post_pronunciation(self, _query: dict[str, list[str]], value: str) -> None:
        # Sửa cách đọc một tên. Giao diện KHÔNG ghi SQLite của sách: nó ghi mong muốn vào overrides.json, dây chuyền áp
        # ở ranh giới chương kế tiếp (hoặc lần chạy tới) và thu lại mọi câu đã thu có tên ấy - listener_overrides.py.
        self.app._mutating()
        path = self.app._book(value)
        body = self._body()
        surface = str(body.get("surface", "")).strip()[:80]
        spoken = " ".join(str(body.get("spokenForm", "")).split())[:120]
        if not surface or not spoken:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu tên hoặc cách đọc")
        problem = listener_overrides.pronunciation_problem(surface, spoken)
        if problem is not None:
            raise ApiError(HTTPStatus.BAD_REQUEST, PRONUNCIATION_PROBLEMS.get(problem, "Cách đọc này không dùng được"))
        listener_overrides.request_pronunciation(path, surface, spoken, now=time.time())
        self._send_json(HTTPStatus.OK, {"surface": surface, "spokenForm": spoken})

    def post_speaker(self, _query: dict[str, list[str]], value: str) -> None:
        # "Ai nói câu này": như cách đọc tên - ghi mong muốn vào overrides.json, dây chuyền áp ở ranh giới chương. Hỏi
        # SQLite (chỉ đọc) ngay bây giờ để từ chối tại chỗ những gì dây chuyền chắc chắn sẽ từ chối: câu đã đổi chữ, câu
        # không phải lời nói, người chưa có giọng.
        self.app._mutating()
        path = self.app._book(value)
        body = self._body()
        speaker = str(body.get("speaker", "")).strip()[:200]
        # Một câu ("Ai nói câu này") hay cả nhóm câu của một vai phụ; cả nhóm được nhận hoặc cả nhóm bị từ chối.
        raw_lines = body.get("lines") if isinstance(body.get("lines"), list) else [body]
        lines = [(str(line.get("stableId", "")).strip()[:120], str(line.get("textSha256", "")).strip()[:64])
                 for line in raw_lines[:2000] if isinstance(line, dict)]
        if not speaker or not lines or not all(stable_id and text_sha256 for stable_id, text_sha256 in lines):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu câu hoặc người nói")
        for stable_id, text_sha256 in lines:
            problem = store.speaker_request_problem(path, stable_id, text_sha256, speaker)
            if problem is not None:
                raise ApiError(HTTPStatus.BAD_REQUEST, SPEAKER_PROBLEMS.get(problem, "Không đổi được người nói câu này"))
        listener_overrides.request_speakers(path, lines, speaker, now=time.time())
        self._send_json(HTTPStatus.OK, {"lines": len(lines), "speaker": speaker})

    def get_voice_choices(self, query: dict[str, list[str]], value: str) -> None:
        # Màn "Đổi giọng" của một nhân vật (voice_picker.py): mọi giọng dùng được, giọng máy gợi ý, ai đang dùng giọng nào.
        view = voice_choices(self.app._book(value), (query.get("character") or [""])[0][:200])
        if view is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Nhân vật này chưa có giọng trong sách")
        self._send_json(HTTPStatus.OK, view)

    def post_line(self, _query: dict[str, list[str]], value: str) -> None:
        # Cách đọc một câu (tab Kịch bản): loại đoạn, cảm xúc, cường độ - và người nói khi câu từ lời kể thành lời thoại.
        # Như người nói: ghi mong muốn vào overrides.json, dây chuyền áp ở ranh giới chương; từ chối tại chỗ những gì dây
        # chuyền chắc chắn sẽ từ chối.
        self.app._mutating()
        path = self.app._book(value)
        body = self._body()
        stable_id = str(body.get("stableId", "")).strip()[:120]
        text_sha256 = str(body.get("textSha256", "")).strip()[:64]
        kind = str(body.get("kind") or "").strip()[:20]
        emotion = str(body.get("emotion") or "").strip()[:20]
        speaker = str(body.get("speaker") or "").strip()[:200]
        raw = body.get("intensity")
        intensity = int(raw) if isinstance(raw, (int, float)) and not isinstance(raw, bool) else None
        if not stable_id or not text_sha256 or not (kind or emotion or intensity is not None or speaker):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu câu hoặc thay đổi")
        problem = store.line_request_problem(path, stable_id, text_sha256, kind=kind, emotion=emotion,
                                             intensity=intensity, speaker=speaker)
        if problem is not None:
            raise ApiError(HTTPStatus.BAD_REQUEST, LINE_PROBLEMS.get(problem, "Không đổi được cách đọc câu này"))
        listener_overrides.request_line(path, stable_id, text_sha256, kind=kind, emotion=emotion, intensity=intensity,
                                        speaker=speaker, now=time.time())
        self._send_json(HTTPStatus.OK, {"stableId": stable_id, "kind": kind, "emotion": emotion, "intensity": intensity})

    def post_voice(self, _query: dict[str, list[str]], value: str) -> None:
        # Giọng / giới của MỘT nhân vật (thẻ "Nam hay nữ", "Chung giọng"): như người nói - ghi mong muốn vào overrides.json,
        # dây chuyền áp ở ranh giới chương; hỏi SQLite chỉ đọc bằng đúng phép dây chuyền dùng để từ chối tại chỗ.
        self.app._mutating()
        path = self.app._book(value)
        body = self._body()
        character = str(body.get("character", "")).strip()[:200]
        preset = str(body.get("preset", "") or "").strip()[:120]
        gender = str(body.get("gender", "") or "").strip()[:10]
        avoid = str(body.get("avoid", "") or "").strip()[:200]
        if not character:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu nhân vật")
        problem = store.voice_request_problem(path, character, preset=preset, gender=gender, avoid=avoid)
        if problem is not None:
            raise ApiError(HTTPStatus.BAD_REQUEST, VOICE_PROBLEMS.get(problem, "Không đổi được giọng nhân vật này"))
        listener_overrides.request_voice(path, character, preset=preset, gender=gender, avoid=avoid, now=time.time())
        self._send_json(HTTPStatus.OK, {"character": character, "preset": preset, "gender": gender, "avoid": avoid})

    def post_review(self, _query: dict[str, list[str]], value: str) -> None:
        self.app._book(value)
        body = self._body()
        verdict = body.get("verdict")
        if verdict not in (None, "ok", "redo"):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Phán quyết không hợp lệ")
        self.app.reviews.set(value, str(body.get("stableId", ""))[:80], verdict, int(body.get("chapterId", 0)))
        self._send_json(HTTPStatus.OK, {"ok": True})

    def put_cover(self, _query: dict[str, list[str]], value: str) -> None:
        self.app._mutating()
        path = self.app._book(value)
        # Ảnh chụp điện thoại vài MB thành data URL còn to hơn 1/3: trần riêng cho đúng yêu cầu này.
        body = self._body(limit=covers.MAX_UPLOAD_BYTES * 4 // 3 + 4096)
        try:
            if body.get("url"):
                # Ảnh chọn từ kết quả "Tìm bìa trên mạng": máy chủ tự tải, chỉ từ các nguồn đã cho phép.
                covers.save_cover_bytes(path, cover_search.download_image(str(body["url"])))
            else:
                covers.save_cover(path, str(body.get("image", "")))
        except covers.CoverError as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(exc)) from exc
        self._send_json(HTTPStatus.OK, {"cover": covers.cover_view(path, value)})

    def get_cover_search(self, query: dict[str, list[str]], value: str) -> None:
        self.app._book(value)
        self._send_json(HTTPStatus.OK, cover_search.search((query.get("q") or [""])[0]))

    def delete_cover(self, _query: dict[str, list[str]], value: str) -> None:
        self.app._mutating()
        covers.remove_cover(self.app._book(value))
        self._send_json(HTTPStatus.OK, {"cover": None})

    def media_cover(self, _query: dict[str, list[str]], value: str) -> None:
        path = covers.cover_file(self.app._listenable(value))
        if path is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Sách này chưa có ảnh bìa")
        self._send_file(path, cache=True)

    def post_reveal_export(self, _query: dict[str, list[str]]) -> None:
        folder = str(self._body().get("folder", ""))
        if folder not in self.app.exports:
            raise ApiError(HTTPStatus.FORBIDDEN, "Không mở được thư mục này")
        actions.reveal(Path(folder))
        self._send_json(HTTPStatus.OK, {"ok": True})

    def get_sync(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.sync_view())

    def post_sync(self, _query: dict[str, list[str]]) -> None:
        self._mutating_guard()
        self._send_json(HTTPStatus.OK, self.app.set_sync(bool(self._body().get("enabled"))))

    def post_sync_studio(self, _query: dict[str, list[str]]) -> None:
        # Chỉ trên chính máy này: remote_studio.ALLOWED không có đường /api/sync nào.
        self._mutating_guard()
        self._send_json(HTTPStatus.OK, self.app.set_remote_studio(bool(self._body().get("enabled"))))

    def post_sync_pairing(self, _query: dict[str, list[str]]) -> None:
        self._mutating_guard()
        if self.app.sync_server is None:
            raise ApiError(HTTPStatus.CONFLICT, "Bật đồng bộ trước rồi mới ghép điện thoại")
        self.app.devices.start_pairing()
        self._send_json(HTTPStatus.OK, self.app.sync_view())

    def delete_sync_pairing(self, _query: dict[str, list[str]]) -> None:
        self.app.devices.cancel_pairing()
        self._send_json(HTTPStatus.OK, self.app.sync_view())

    def delete_sync_device(self, _query: dict[str, list[str]], device: str) -> None:
        self._mutating_guard()
        self.app.devices.revoke(device)
        self.app.remote.forget(device)
        self._send_json(HTTPStatus.OK, self.app.sync_view())

    def post_sync_device_studio(self, _query: dict[str, list[str]], device: str) -> None:
        # Quyền Studio từ xa theo TỪNG thiết bị (soát 28-09). Chỉ trên chính máy này - không nằm trong ALLOWED.
        self._mutating_guard()
        if not self.app.devices.set_studio(device, bool(self._body().get("enabled"))):
            raise ApiError(HTTPStatus.NOT_FOUND, "Không có thiết bị này")
        self._send_json(HTTPStatus.OK, self.app.sync_view())

    def get_remote(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.remote_view())

    def post_remote(self, _query: dict[str, list[str]], device: str) -> None:
        self._mutating_guard()
        self._send_json(HTTPStatus.OK, self.app.remote_send(device, self._body()))

    def _mutating_guard(self) -> None:
        if self.app.read_only:
            raise ApiError(HTTPStatus.FORBIDDEN, "Giao diện đang ở chế độ chỉ xem")

    def get_computers(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.computers_view())

    def post_computers(self, _query: dict[str, list[str]]) -> None:
        # Ghép với máy tính khác bằng địa chỉ + mã 6 số đang hiện trên máy ấy (cùng mã điện thoại dùng).
        body = self._body()
        self._send_json(HTTPStatus.OK, self.app.pair_computer(str(body.get("address") or ""), str(body.get("code") or "")))

    def post_computers_refresh(self, _query: dict[str, list[str]]) -> None:
        self.app.refresh_remote(wait=True)
        self._send_json(HTTPStatus.OK, self.app.computers_view())

    def delete_computer(self, _query: dict[str, list[str]], computer: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.forget_computer(computer))

    def get_listen_library(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.listen_library())

    def post_open_book_file(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.open_book_file(str(self._body().get("path") or "")))

    def get_listen_book(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.listen_book(value))

    def post_progress(self, _query: dict[str, list[str]], value: str) -> None:
        self.app._listenable(value)
        self.app.sync_remote_state(value, wait=False)
        body = self._body()
        state = self.app.listening.progress(
            value, int(body.get("chapterId", 0)), float(body.get("seconds", 0)), float(body.get("duration", 0)),
            record=_held_record(body),
        )
        self._send_json(HTTPStatus.OK, state)

    def post_chapter_done(self, _query: dict[str, list[str]], value: str, chapter: str) -> None:
        self.app._listenable(value)
        self.app.sync_remote_state(value, wait=False)
        state = self.app.listening.set_chapter_done(value, int(chapter), bool(self._body().get("done", True)))
        self._send_json(HTTPStatus.OK, state)

    def post_finished(self, _query: dict[str, list[str]], value: str) -> None:
        self.app._listenable(value)
        self.app.sync_remote_state(value, wait=False)
        self._send_json(HTTPStatus.OK, self.app.listening.set_finished(value, bool(self._body().get("finished", True))))

    def post_rate(self, _query: dict[str, list[str]], value: str) -> None:
        self.app._listenable(value)
        self.app.listening.set_rate(value, float(self._body().get("rate", 1.0)))
        self._send_json(HTTPStatus.OK, {"ok": True})

    def post_bookmark(self, _query: dict[str, list[str]], value: str) -> None:
        self.app._listenable(value)
        self.app.sync_remote_state(value, wait=False)
        body = self._body()
        mark = self.app.listening.add_bookmark(
            value, int(body.get("chapterId", 0)), float(body.get("seconds", 0)), str(body.get("note", "")),
            record=_held_record(body),
        )
        self._send_json(HTTPStatus.CREATED, mark)

    def put_bookmark(self, _query: dict[str, list[str]], value: str, mark: str) -> None:
        self.app._listenable(value)
        self.app.sync_remote_state(value, wait=False)
        self.app.listening.update_bookmark(value, mark, str(self._body().get("note", "")))
        self._send_json(HTTPStatus.OK, {"ok": True})

    def delete_bookmark(self, _query: dict[str, list[str]], value: str, mark: str) -> None:
        self.app._listenable(value)
        self.app.sync_remote_state(value, wait=False)
        self.app.listening.delete_bookmark(value, mark)
        self._send_json(HTTPStatus.OK, {"ok": True})

    def post_bookmark_restore(self, _query: dict[str, list[str]], value: str) -> None:
        self.app._listenable(value)
        self.app.sync_remote_state(value, wait=False)
        body = self._body()
        if not re.fullmatch(r"[0-9a-f]{6,40}", str(body.get("id", ""))):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Dấu trang không hợp lệ")
        self._send_json(HTTPStatus.OK, self.app.listening.restore_bookmark(value, body))

    # ---- hồ sơ nghe: độc lập với sách, app giữ liên kết (webui/listening.py) ----------------------------------------

    def _own_record(self, value: str, record: str) -> None:
        self.app._listenable(value)
        if self.app.listening.book_of(record) != value:
            raise ApiError(HTTPStatus.NOT_FOUND, "Không có hồ sơ nghe này")

    def get_records(self, _query: dict[str, list[str]], value: str) -> None:
        self.app._listenable(value)
        self._send_json(HTTPStatus.OK, {"records": self.app.listening.records(value)})

    def post_record(self, _query: dict[str, list[str]], value: str) -> None:
        self.app._listenable(value)
        self.app.listening.create_record(value, str(self._body().get("name", "")))
        self._send_json(HTTPStatus.CREATED, {"records": self.app.listening.records(value)})

    def post_record_activate(self, _query: dict[str, list[str]], value: str, record: str) -> None:
        self._own_record(value, record)
        self.app.listening.activate(value, record)
        self._send_json(HTTPStatus.OK, {"records": self.app.listening.records(value)})

    def put_record(self, _query: dict[str, list[str]], value: str, record: str) -> None:
        self._own_record(value, record)
        if not self.app.listening.rename_record(record, str(self._body().get("name", ""))):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Tên hồ sơ không được để trống")
        self._send_json(HTTPStatus.OK, {"records": self.app.listening.records(value)})

    def post_record_move(self, _query: dict[str, list[str]], value: str, record: str) -> None:
        self._own_record(value, record)
        target = str(self._body().get("book", ""))
        self.app._listenable(target)
        self.app.listening.move_record(record, target)
        self._send_json(HTTPStatus.OK, {"records": self.app.listening.records(value)})

    def delete_record(self, _query: dict[str, list[str]], value: str, record: str) -> None:
        self._own_record(value, record)
        self.app.listening.delete_record(record)
        self._send_json(HTTPStatus.OK, {"records": self.app.listening.records(value)})

    def get_sessions(self, _query: dict[str, list[str]], value: str) -> None:
        self.app._listenable(value)
        self._send_json(HTTPStatus.OK, self.app.listening.sessions(value))

    def post_session(self, _query: dict[str, list[str]], value: str) -> None:
        self.app._listenable(value)
        body = self._body()
        self.app.listening.add_session(value, body, record=_held_record(body))
        self._send_json(HTTPStatus.OK, {"ok": True})

    def post_reading(self, _query: dict[str, list[str]], value: str) -> None:
        self.app._listenable(value)
        body = self._body()
        self.app.listening.set_reading(value, int(body.get("chapterId", 0)), int(body.get("index", 0)))
        self._send_json(HTTPStatus.OK, {"ok": True})

    def post_night(self, _query: dict[str, list[str]], value: str) -> None:
        self.app._listenable(value)
        self.app.listening.save_night(value, self._body())
        self._send_json(HTTPStatus.OK, {"ok": True})

    def get_night(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.listening.latest_night())

    def post_night_dismiss(self, _query: dict[str, list[str]]) -> None:
        body = self._body()
        self.app.listening.dismiss_night(str(body.get("bookId", "")), str(body.get("id", "")))
        self._send_json(HTTPStatus.OK, {"ok": True})

    def post_open(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.open_existing(self._body()))

    def post_create(self, _query: dict[str, list[str]]) -> None:
        body = self._body()
        self._source_paths(body.get("paths"))
        self._send_json(HTTPStatus.CREATED, self.app.create(body))

    def post_scan(self, _query: dict[str, list[str]]) -> None:
        body = self._body()
        self._send_json(HTTPStatus.OK, actions.scan_inputs(self._source_paths(body.get("paths"))))

    def post_source_upload(self, _query: dict[str, list[str]]) -> None:
        # Studio từ xa: điện thoại không có đường dẫn nào trên máy này để gõ - nó gửi từng chương TXT, rồi trình tạo sách
        # đi tiếp như khi chọn thư mục. Byte giữ nguyên (base64): dây chuyền tự nhận bảng mã như với file trên máy.
        self.app._mutating()
        body = self._body(limit=actions.MAX_SOURCE_UPLOAD * 4 // 3 + 4096)
        try:
            data = base64.b64decode(str(body.get("data", "")), validate=True)
        except (ValueError, binascii.Error) as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Dữ liệu file không hợp lệ") from error
        folder = actions.upload_source(Path(self.app.preferences.get()["libraryRoot"]), str(body.get("folder", "")),
                                       str(body.get("name", "")), data)
        self._send_json(HTTPStatus.OK, {"folder": str(folder)})

    def post_first_person(self, _query: dict[str, list[str]]) -> None:
        body = self._body()
        self._send_json(HTTPStatus.OK, actions.first_person_hint(self._source_paths(body.get("paths"))))

    def get_voices(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.voices())

    def get_preferences(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.preferences.get())

    def put_preferences(self, _query: dict[str, list[str]]) -> None:
        body = self._body()
        allowed = {key: body[key] for key in ("theme", "libraryRoot", "playbackRate", "volume") if key in body}
        # Hai tuỳ chọn hẹn giờ ngủ chỉ nhận đúng các mức giao diện đưa ra.
        if body.get("sleepFadeSeconds") in (10, 30, 60):
            allowed["sleepFadeSeconds"] = body["sleepFadeSeconds"]
        if body.get("sleepExtendMinutes") in (5, 10, 15):
            allowed["sleepExtendMinutes"] = body["sleepExtendMinutes"]
        if body.get("safetyStopHours") in (0, 1, 2, 3):
            allowed["safetyStopHours"] = body["safetyStopHours"]
        if "sleepSchedule" in body:
            schedule = body["sleepSchedule"]
            clock = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
            if schedule is None:
                allowed["sleepSchedule"] = None
            elif (isinstance(schedule, dict) and clock.fullmatch(str(schedule.get("from", "")))
                  and clock.fullmatch(str(schedule.get("to", ""))) and schedule.get("minutes") in (15, 30, 45, 60)):
                allowed["sleepSchedule"] = {"from": schedule["from"], "to": schedule["to"], "minutes": schedule["minutes"]}
        self._send_json(HTTPStatus.OK, self.app.preferences.update(allowed))

    def post_app_update(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.install_update())

    def _studio_setup(self) -> Any:
        if self.app.studio is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Bản này không cài Studio từ trong app (Studio là runtime cạnh mã nguồn)")
        return self.app.studio

    def get_studio_setup(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self._studio_setup().status())

    def post_studio_setup(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self._studio_setup().start())

    def post_studio_setup_cancel(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self._studio_setup().cancel())

    def delete_studio_setup(self, _query: dict[str, list[str]]) -> None:
        setup = self._studio_setup()
        busy = self.app._busy_elsewhere(Path())
        if busy is not None:
            raise ApiError(HTTPStatus.CONFLICT, f"Đang làm cuốn \"{busy.name}\" - dừng cuốn ấy trước khi gỡ Studio")
        self._send_json(HTTPStatus.OK, setup.remove())

    def post_pick_folder(self, _query: dict[str, list[str]]) -> None:
        if self.app.dialogs is None:
            raise ApiError(HTTPStatus.NOT_IMPLEMENTED, "Không có hộp thoại chọn thư mục ở chế độ này")
        body = self._body()
        path = self.app.dialogs.pick_folder(str(body.get("title", "Chọn thư mục")), str(body.get("start", "")))
        self._send_json(HTTPStatus.OK, {"path": path})

    def post_pick_files(self, _query: dict[str, list[str]]) -> None:
        if self.app.dialogs is None:
            raise ApiError(HTTPStatus.NOT_IMPLEMENTED, "Không có hộp thoại chọn file ở chế độ này")
        body = self._body()
        paths = self.app.dialogs.pick_files(str(body.get("title", "Chọn file TXT")), str(body.get("start", "")))
        self._send_json(HTTPStatus.OK, {"paths": paths})

    def media_voice(self, _query: dict[str, list[str]], name: str) -> None:
        path = self.app.voice_file(name)
        if path is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Không có bản nghe thử cho giọng này")
        self._send_file(path, cache=True)

    def media_chapter(self, _query: dict[str, list[str]], value: str, chapter: str) -> None:
        book = self.app._listenable(value)
        path = (packages.chapter_file(book, int(chapter)) if packages.is_package(book)
                else store.chapter_audio_path(book, int(chapter)))
        if path is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Chương này chưa nghe được")
        self._send_file(path)

    def media_sample(self, _query: dict[str, list[str]], value: str, segment: str) -> None:
        book = self.app._listenable(value)
        path = (packages.sample_file(book, int(segment)) if packages.is_package(book)
                else store.sample_audio_path(book, int(segment)))
        if path is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Không có câu mẫu")
        self._send_file(path)


BOOK = r"/api/books/([A-Za-z0-9_-]+)"
LISTEN = r"/api/listen/books/([A-Za-z0-9_-]+)"
ROUTES: list[Route] = [
    ("GET", re.compile(r"/api/app"), Handler.get_app),
    ("POST", re.compile(r"/api/app/update"), Handler.post_app_update),
    ("GET", re.compile(r"/api/studio/setup"), Handler.get_studio_setup),
    ("POST", re.compile(r"/api/studio/setup"), Handler.post_studio_setup),
    ("POST", re.compile(r"/api/studio/setup/cancel"), Handler.post_studio_setup_cancel),
    ("DELETE", re.compile(r"/api/studio/setup"), Handler.delete_studio_setup),
    ("GET", re.compile(r"/api/library"), Handler.get_library),
    ("GET", re.compile(r"/api/voices"), Handler.get_voices),
    ("GET", re.compile(r"/api/preferences"), Handler.get_preferences),
    ("PUT", re.compile(r"/api/preferences"), Handler.put_preferences),
    ("POST", re.compile(r"/api/scan"), Handler.post_scan),
    ("POST", re.compile(r"/api/sources/upload"), Handler.post_source_upload),
    ("POST", re.compile(r"/api/first-person"), Handler.post_first_person),
    ("POST", re.compile(r"/api/books"), Handler.post_create),
    ("POST", re.compile(r"/api/books/open"), Handler.post_open),
    ("POST", re.compile(r"/api/dialog/folder"), Handler.post_pick_folder),
    ("POST", re.compile(r"/api/dialog/files"), Handler.post_pick_files),
    ("GET", re.compile(BOOK), Handler.get_book),
    ("GET", re.compile(BOOK + r"/cast"), Handler.get_cast),
    ("GET", re.compile(BOOK + r"/activity"), Handler.get_activity),
    ("GET", re.compile(BOOK + r"/chapters/(\d+)/script"), Handler.get_script),
    ("POST", re.compile(BOOK + r"/start"), Handler.post_start),
    ("POST", re.compile(BOOK + r"/stop"), Handler.post_stop),
    ("POST", re.compile(BOOK + r"/reveal"), Handler.post_reveal),
    ("POST", re.compile(BOOK + r"/export"), Handler.post_export),
    ("GET", re.compile(BOOK + r"/review"), Handler.get_review),
    ("GET", re.compile(BOOK + r"/work"), Handler.get_work),
    ("GET", re.compile(BOOK + r"/casting"), Handler.get_casting),
    ("GET", re.compile(BOOK + r"/casting/(\d+)"), Handler.get_casting_chapter),
    ("POST", re.compile(BOOK + r"/review"), Handler.post_review),
    ("POST", re.compile(BOOK + r"/pronunciation"), Handler.post_pronunciation),
    ("POST", re.compile(BOOK + r"/bookfile"), Handler.post_bookfile),
    ("POST", re.compile(BOOK + r"/speaker"), Handler.post_speaker),
    ("POST", re.compile(BOOK + r"/voice"), Handler.post_voice),
    ("POST", re.compile(BOOK + r"/line"), Handler.post_line),
    ("GET", re.compile(BOOK + r"/voices"), Handler.get_voice_choices),
    ("GET", re.compile(BOOK + r"/cover/search"), Handler.get_cover_search),
    ("PUT", re.compile(BOOK + r"/cover"), Handler.put_cover),
    ("DELETE", re.compile(BOOK + r"/cover"), Handler.delete_cover),
    ("POST", re.compile(r"/api/reveal-export"), Handler.post_reveal_export),
    ("GET", re.compile(r"/api/sync"), Handler.get_sync),
    ("POST", re.compile(r"/api/sync"), Handler.post_sync),
    ("POST", re.compile(r"/api/sync/pairing"), Handler.post_sync_pairing),
    ("POST", re.compile(r"/api/sync/studio"), Handler.post_sync_studio),
    ("GET", re.compile(r"/api/remote"), Handler.get_remote),
    ("POST", re.compile(r"/api/remote/([0-9a-f]{12})"), Handler.post_remote),
    ("DELETE", re.compile(r"/api/sync/pairing"), Handler.delete_sync_pairing),
    ("DELETE", re.compile(r"/api/sync/devices/([0-9a-f]+)"), Handler.delete_sync_device),
    ("POST", re.compile(r"/api/sync/devices/([0-9a-f]+)/studio"), Handler.post_sync_device_studio),
    ("GET", re.compile(r"/api/computers"), Handler.get_computers),
    ("POST", re.compile(r"/api/computers"), Handler.post_computers),
    ("POST", re.compile(r"/api/computers/refresh"), Handler.post_computers_refresh),
    ("DELETE", re.compile(r"/api/computers/([0-9a-f]{12})"), Handler.delete_computer),
    ("GET", re.compile(r"/api/listen/library"), Handler.get_listen_library),
    ("POST", re.compile(r"/api/listen/open-book-file"), Handler.post_open_book_file),
    ("GET", re.compile(LISTEN), Handler.get_listen_book),
    ("POST", re.compile(LISTEN + r"/progress"), Handler.post_progress),
    ("POST", re.compile(LISTEN + r"/chapters/(\d+)/done"), Handler.post_chapter_done),
    ("POST", re.compile(LISTEN + r"/finished"), Handler.post_finished),
    ("POST", re.compile(LISTEN + r"/rate"), Handler.post_rate),
    ("POST", re.compile(LISTEN + r"/bookmarks"), Handler.post_bookmark),
    ("PUT", re.compile(LISTEN + r"/bookmarks/([0-9a-f]+)"), Handler.put_bookmark),
    ("DELETE", re.compile(LISTEN + r"/bookmarks/([0-9a-f]+)"), Handler.delete_bookmark),
    ("POST", re.compile(LISTEN + r"/bookmarks/restore"), Handler.post_bookmark_restore),
    ("GET", re.compile(LISTEN + r"/records"), Handler.get_records),
    ("POST", re.compile(LISTEN + r"/records"), Handler.post_record),
    ("POST", re.compile(LISTEN + r"/records/(r-[0-9a-f]{16})/activate"), Handler.post_record_activate),
    ("PUT", re.compile(LISTEN + r"/records/(r-[0-9a-f]{16})"), Handler.put_record),
    ("POST", re.compile(LISTEN + r"/records/(r-[0-9a-f]{16})/move"), Handler.post_record_move),
    ("DELETE", re.compile(LISTEN + r"/records/(r-[0-9a-f]{16})"), Handler.delete_record),
    ("POST", re.compile(LISTEN + r"/night"), Handler.post_night),
    ("POST", re.compile(LISTEN + r"/reading"), Handler.post_reading),
    ("GET", re.compile(LISTEN + r"/sessions"), Handler.get_sessions),
    ("POST", re.compile(LISTEN + r"/sessions"), Handler.post_session),
    ("GET", re.compile(r"/api/listen/night"), Handler.get_night),
    ("POST", re.compile(r"/api/listen/night/dismiss"), Handler.post_night_dismiss),
    ("GET", re.compile(r"/media/voices/([^/]+)"), Handler.media_voice),
    ("GET", re.compile(r"/media/books/([A-Za-z0-9_-]+)/chapters/(\d+)"), Handler.media_chapter),
    ("GET", re.compile(r"/media/books/([A-Za-z0-9_-]+)/samples/(\d+)"), Handler.media_sample),
    ("GET", re.compile(r"/media/books/([A-Za-z0-9_-]+)/cover"), Handler.media_cover),
]


class Server:
    """Server chạy trên một luồng nền; `url` là địa chỉ để cửa sổ (hoặc trình duyệt khi phát triển) mở."""

    def __init__(self, app: App, *, port: int = 0) -> None:
        handler = type("BoundHandler", (Handler,), {"app": app})
        self.httpd = ExclusiveHTTPServer(("127.0.0.1", port), handler)
        handler.port = self.httpd.server_address[1]
        self.app = app
        self.port = int(self.httpd.server_address[1])
        app.local_port = self.port
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        suffix = f"?t={self.app.token}" if self.app.token else ""
        return f"http://127.0.0.1:{self.port}/{suffix}"

    def start(self) -> "Server":
        self._thread = threading.Thread(target=self.httpd.serve_forever, name="webui", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def new_token() -> str:
    return secrets.token_urlsafe(24)



def socket_name() -> str:
    """Tên máy hiện trên điện thoại khi tìm thấy nó."""
    import socket

    return socket.gethostname() or "Máy tính"

