"""Server HTTP cục bộ cho giao diện: JSON API + audio (có Range để tua) + frontend đã build.

Chỉ nghe trên 127.0.0.1. Mọi `/api` và `/media` cần mã phiên (header `X-Ebook-Token` hoặc `?t=`), và `Host`
phải là chính server - không thì một trang web bất kỳ trong trình duyệt của người dùng gọi được
`127.0.0.1:<cổng>` (hoặc qua DNS rebinding) để đọc sách hay bấm "Bắt đầu" thay họ.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import mimetypes
import os
import re
import secrets
import shutil
import threading
import time
import urllib.request
from contextlib import closing
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import parse_qs, quote, unquote, urlsplit

from .. import aliases, bracket_rule, continuation, listener_overrides
from . import (actions, bookfile, cover_search, covers, humanize, listen_view, music_catalog, music_plan, packages,
               projectfile, remote_config, shared_readings, store)
from .fingerprints import Fingerprints
from .library import Library, Preferences, book_id, legacy_ids
from .listening import RECORD_ID, Listening
from . import bluetooth, remote_books, spelling
from .remote_studio import REMOTE_HEADER, StudioGate
from .reviews import Reviews, review_view
from .casting_review import casting_chapter, casting_chapters
from .name_readings import name_readings
from .voice_picker import voice_choices
from .work_items import work_items
from .cast import CastError, CastPlayers
from .cast import search as cast_search
from .peer_players import PeerPlayers
from .sync import (LOCAL_PLAYER, SYNC_PORT, Devices, ExclusiveHTTPServer, Remote, SyncApp, SyncServer, local_addresses,
                   remote_command)

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
    listener_overrides.BAD_TEXT: "Chữ đem đọc phải có chữ cái, không ký tự lạ, và không dài quá bốn lần câu gốc.",
}

VOICE_PROBLEMS = {
    listener_overrides.UNKNOWN_CHARACTER: "Không có nhân vật này trong sách.",
    listener_overrides.NOT_A_CHARACTER: "Giọng người kể chọn khi tạo sách, không đổi ở đây.",
    listener_overrides.NO_VOICE: "Nhân vật này chưa có giọng (chưa qua bước phân vai) - chưa đổi được.",
    listener_overrides.UNKNOWN_PRESET: "Giọng này không dùng cho nhân vật được (không có, hay là giọng người kể).",
    listener_overrides.BAD_GENDER: "Giới phải là nam hoặc nữ.",
}
# "Hoàn tác" tới sau khi dây chuyền đã đưa quyết định vào sách (ranh giới chương rơi đúng mấy giây ấy).
WITHDRAW_APPLIED = {
    "speakers": "Máy vừa đưa quyết định này vào sách nên không hoàn tác được nữa - muốn đổi lại, chọn người nói cho câu"
                " ở tab Kịch bản.",
    "pronunciations": "Máy vừa đưa cách đọc này vào sách nên không hoàn tác được nữa.",
    "voices": "Máy vừa đưa quyết định này vào sách nên không hoàn tác được nữa - muốn đổi lại, đổi giọng ở tab Nhân vật.",
}

SPEAKER_PROBLEMS = {
    listener_overrides.UNKNOWN_LINE: "Không còn câu này trong sách.",
    listener_overrides.SOURCE_CHANGED: "Chữ của câu này đã đổi từ lúc máy chấm - tải lại danh sách việc.",
    listener_overrides.NOT_SPEECH: "Câu này là lời kể, không có người nói để đổi.",
    listener_overrides.NO_VOICE: "Người này chưa có giọng trong sách (chưa nói câu nào) - chưa gán được.",
}


class ApiError(Exception):
    """`extra`: trường gửi kèm lời báo lỗi để giao diện làm được gì đó với nó (`suggestion` của một cách đọc bị từ chối)."""

    def __init__(self, status: int, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.extra = extra


def _held_record(body: dict[str, Any]) -> str | None:
    """Hồ sơ nghe mà trình phát đang phát (nó ghi vào đúng hồ sơ ấy, xem `Listening._held`); không có thì None."""
    record = body.get("record")
    return record if isinstance(record, str) and RECORD_ID.fullmatch(record) else None


def index_part(chain: list[Path], project: Path) -> int:
    """Số phần của `project` trong chuỗi (phần đầu = 1)."""
    return chain.index(project) + 1


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
        self.shared_readings = shared_readings.SharedReadings(preferences.path.with_name(shared_readings.FILE_NAME))
        self.remote = Remote()
        # Trình phát trong giao diện CHÍNH máy này: giao diện báo lên (`report_player`), máy đã ghép xem và điều khiển nó
        # qua cổng đồng bộ (sync.py, /sync/v1/player) - mạng trạm bước 4.
        self.player = Remote()
        self.sync_server: SyncServer | None = None
        # Cổng đồng bộ qua Bluetooth (webui/bluetooth.py): bật/tắt cùng cổng Wi-Fi, mang đúng giao thức ấy.
        self.bluetooth: bluetooth.BluetoothServer | None = None
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
        # Nhạc nền (webui/music_*.py): địa chỉ danh mục lấy từ cấu hình từ xa có chữ ký (remote_config.py), không ghi cứng.
        self.remote_config = remote_config.RemoteConfig(preferences.path.with_name("remote"))
        self.music_dir = preferences.path.with_name("music")
        self._music_catalog: music_catalog.MusicCatalog | None = None
        self._music_lock = threading.Lock()
        if not read_only:
            self._adopt_new_book_ids()
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
        self.peer_players = PeerPlayers(self.computers)
        # Loa / TV trong mạng nhà (DLNA, webui/cast.py): hiện trong danh sách máy như điện thoại, máy này phục vụ audio.
        # ABOOK_CAST_DISCOVERY=0 tắt việc tìm (bài thử - tests/conftest.py - không gửi multicast ra mạng người chạy).
        self.cast = CastPlayers(self._cast_book, self._cast_audio, self._cast_save, cover=self._cast_cover,
                                find=lambda: cast_search() if os.environ.get("ABOOK_CAST_DISCOVERY") != "0" else [])
        self._remote_refreshed = 0.0
        self._remote_lock = threading.Lock()
        self._state_synced: dict[str, float] = {}
        # App Windows đóng gói (webui/host.py): vỏ Tauri báo có bản mới (`update`), nhận lệnh cài qua `shell`; Studio
        # (thư viện + model làm sách) tải thêm khi cần (`studio`, webui/studio_setup.py). Bản dev: cả ba là None.
        self.update: dict[str, Any] | None = None
        self.shell: Callable[[dict[str, Any]], None] | None = None
        self.studio: Any = None

    def _adopt_new_book_ids(self) -> None:
        """Dữ liệu lưu theo mã sách kiểu cũ (đường dẫn base64 - docs/BOOK_IDS.md): đổi khoá sang mã mới, một
        lần. Hồ sơ nghe giữ nguyên mã (điện thoại gộp theo mã hồ sơ). Sao lưu từng file trước lần ghi đầu
        (`*.pre-ids.bak`)."""
        positions = self.preferences.get().get("positions")
        renamed = legacy_ids([*self.listening.books(), *(positions if isinstance(positions, dict) else {}),
                              *self.reviews.books()])
        if not renamed:
            return
        for file in (self.listening.path, self.preferences.path, self.reviews.path):
            backup = file.with_name(file.name + ".pre-ids.bak")
            try:
                if file.is_file() and not backup.exists():
                    shutil.copy2(file, backup)
            except OSError:
                pass  # không sao lưu được vẫn đổi: mỗi file ghi nguyên tử, mã cũ vẫn được nhận
        self.listening.rename_books(renamed)
        self.preferences.rename_positions(renamed)
        self.reviews.rename_books(renamed)

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
        if path.lower().endswith(projectfile.EXTENSION):
            return self.open_project_file(Path(path))
        try:
            target, how = packages.import_file(Path(path), self.library.root, self.library.projects(), self.fingerprints)
        except bookfile.BookFileError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error
        return {"id": book_id(target), "how": how}

    def open_project_file(self, path: Path) -> dict[str, Any]:
        """Mở một file `.abookproj` (projectfile.py): giải nén thành một dự án MỚI trong thư viện, mở ở Studio."""
        try:
            with projectfile.ProjectFile(path) as opened:
                target, report = opened.open_into(self.library.root)
                missing = len(opened.missing_sources)
        except projectfile.ProjectFileError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error
        self.library.preferences.add_recent(target)
        return {"id": book_id(target), "how": "studio", "missingSources": missing, "outside": report["outside"]}

    def summary(self, path: Path) -> dict[str, Any]:
        running = self.runner.running(path)
        result = self.library.summary(path, running=running, starting=self.jobs.starting(path))
        result["startError"] = self.jobs.error(path)
        # Tạm dừng mà tiến trình vẫn sống (power_source): "battery" / "listener". Dây chuyền chỉ đứng ở checkpoint kế -
        # tới đó sổ vẫn ghi pha đang làm, nên "đang tạm dừng" khác "đã tạm dừng".
        result["paused"] = self.runner.pause_reason(path) if running else None
        result["canPause"] = bool(running and self.runner.can_pause(path))
        # Phần nối tiếp của "Làm tiếp cuốn này": danh sách Dự án gom theo chuỗi, không theo tên (soát UX 29-09, N10).
        place = continuation.series_of(path)
        result["series"] = {"root": book_id(place[0]), "part": place[1]} if place else None
        if result["paused"]:
            result["statusLabel"] = humanize.pause_label(result["paused"], reached=result.get("status") == "paused")
            result["eta"] = None
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
                self._launch(path)

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
        self._launch(path)
        return self.summary(path)

    def _launch(self, path: Path) -> None:
        """Khởi động lượt chạy và ghi mốc (store.mark_run_started) - mốc lấy TRƯỚC khi khởi động: yêu cầu ghi trong lúc
        khởi động vẫn tính là đang chờ; khởi động hỏng thì không ghi gì."""
        started_at = time.time()
        self.jobs.start(path)
        store.mark_run_started(path, started_at)

    def pause(self, value: str, paused: bool) -> dict[str, Any]:
        """"Tạm dừng" / "Tiếp tục" cuốn đang chạy: tiến trình vẫn sống, dây chuyền đứng ở checkpoint kế rồi làm tiếp đúng
        chỗ ấy - an toàn cả giữa pha phân tích, nơi "Dừng" rồi chạy lại là ra một quyển sách khác. "Tiếp tục" lúc máy
        đang chạy pin = làm tiếp trên pin tới lần cắm sạc kế (background_runner._pause_reason)."""
        self._mutating()
        path = self._book(value)
        if not self.runner.running(path):
            raise ApiError(HTTPStatus.CONFLICT, "Sách này không đang chạy")
        try:
            self.runner.pause(path, paused)
        except RuntimeError as error:
            raise ApiError(HTTPStatus.CONFLICT, str(error)) from error
        # Supervisor đọc yêu cầu ở vòng kế (tới 0,25 giây): trả trạng thái SẼ có, không phải trạng thái vừa đọc.
        result = self.summary(path)
        result["paused"] = "listener" if paused else None
        if paused:
            result["statusLabel"] = humanize.pause_label("listener", reached=result.get("status") == "paused")
            result["eta"] = None
        return result

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

    def existing_projects(self, digests: list[str]) -> list[dict[str, Any]]:
        """Dự án đã làm từ chính những file vừa chọn - so NỘI DUNG (SHA-256), không so đường dẫn: truyện chép sang thư
        mục khác vẫn là một. Báo khi trùng từ nửa số file vừa chọn, hay từ nửa số chương của dự án cũ (chọn lại cả thư mục
        đã thêm chương mới). Soát UX 29-09: tạo lại cùng truyện không có lời nào, người dùng có hai dự án mà không biết."""
        wanted = {digest for digest in digests if digest}
        found: list[dict[str, Any]] = []
        if not wanted:
            return found
        for path in self.library.projects():
            try:
                have = store.source_digests(path)
            except Exception:  # noqa: BLE001 - một dự án hỏng không được chặn việc tạo sách
                continue
            shared = len(wanted & have)
            if shared and (shared * 2 >= len(wanted) or shared * 2 >= len(have)):
                try:
                    summary = self.summary(path)
                except Exception:  # noqa: BLE001
                    continue
                found.append({"id": summary["id"], "title": summary["title"], "statusLabel": summary["statusLabel"],
                              "shared": shared, "chapters": len(have)})
        found.sort(key=lambda item: -item["shared"])
        return found[:3]

    def rename(self, value: str, title: str) -> dict[str, Any]:
        """Đặt lại tên sách hiện trong thư viện, trên điện thoại và trong file xuất (store.TITLE_FILE) - thư mục dự án và
        sổ của dây chuyền giữ nguyên, nên đổi được cả lúc sách đang chạy."""
        self._mutating()
        path = self._book(value)
        cleaned = store.clean_title(title)
        if not cleaned:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Tên sách không được để trống")
        try:
            store.set_display_title(path, cleaned)
        except OSError as error:
            raise ApiError(HTTPStatus.CONFLICT, f"Không ghi được tên mới: {error}") from error
        return self.summary(path)

    def delete(self, value: str) -> dict[str, Any]:
        """Xoá một dự án: chuyển CẢ thư mục dự án vào Thùng rác (khôi phục được). File truyện gốc người dùng chọn lúc tạo
        nằm ngoài thư mục ấy, không bị đụng tới. Sách đang chạy phải dừng trước; đang xếp hàng thì bỏ khỏi hàng."""
        self._mutating()
        path = self._book(value)
        if self.runner.running(path) or self.jobs.starting(path):
            raise ApiError(HTTPStatus.CONFLICT, "Sách đang chạy - dừng sách rồi mới xoá được")
        resolved = path.resolve()
        if resolved == Path(resolved.anchor) or resolved == self.library.root.resolve() or not store.is_project(resolved):
            raise ApiError(HTTPStatus.CONFLICT, "Thư mục này không phải một dự án sách - không xoá")
        with self._queue_lock:
            if value in self.queue:
                self.queue.remove(value)
        try:
            actions.move_to_recycle_bin(resolved)
        except OSError as error:
            raise ApiError(
                HTTPStatus.CONFLICT,
                "Không chuyển được vào Thùng rác - có thể một file trong dự án đang mở (đang nghe cuốn này, hay thư mục"
                f" đang mở trong cửa sổ khác). Đóng rồi thử lại. ({error})",
            ) from error
        self.library.forget(path)
        return {"ok": True, "title": path.name}

    def remove_imported(self, value: str) -> dict[str, Any]:
        """Bỏ một cuốn NHẬP TỪ FILE `.abook` khỏi thư viện: thư mục đã giải nén vào Thùng rác. File `.abook` gốc không bị
        đụng - mở lại là nhập lại. Dự án của Studio xoá trong Studio; sách của máy khác thôi hiện khi gỡ máy ấy."""
        from .remote_books import REMOTE_FOLDER

        self._mutating()
        path = self._listenable(value).resolve()
        root = self.library.root.resolve()
        if store.is_project(path):
            raise ApiError(HTTPStatus.CONFLICT, "Đây là dự án của Studio - xoá ở trang dự án trong Studio (nút …)")
        if path.parent.parent == (root / REMOTE_FOLDER).resolve():
            raise ApiError(HTTPStatus.CONFLICT,
                           "Sách này nằm trên máy tính khác - muốn thôi hiện thì gỡ máy ấy ở Cài đặt → Máy tính khác")
        if path.parent != (root / packages.IMPORTED_FOLDER).resolve() or not packages.is_package(path):
            raise ApiError(HTTPStatus.CONFLICT, "Cuốn này không phải sách đã nhập từ file")
        try:
            actions.move_to_recycle_bin(path)
        except OSError as error:
            raise ApiError(
                HTTPStatus.CONFLICT,
                f"Không chuyển được vào Thùng rác - có thể một chương đang mở (đang nghe cuốn này). Thử lại. ({error})",
            ) from error
        return {"ok": True}

    def analysis_models(self) -> dict[str, Any]:
        """Model đọc hiểu truyện chọn được cho MỘT cuốn (trình tạo sách): các model có trong Ollama mà dây chuyền sẽ gọi -
        Ollama riêng của Studio trong app đóng gói, Ollama của máy khi chạy từ mã nguồn - cùng model mặc định của app. Hỏi
        HTTP /api/tags (không gọi CLI `ollama`: khi máy chủ tắt nó tự mở app khay); Ollama tắt thì danh sách rỗng."""
        import urllib.request

        from ..config import build_settings

        analysis = build_settings()["analysis"]
        default = str(analysis.get("model", ""))
        base = str((self.studio.settings_overrides().get("analysis") or {}).get("base_url") if self.studio is not None
                   else analysis.get("base_url", ""))
        models: list[dict[str, Any]] = []
        reachable = True
        try:
            with urllib.request.urlopen(f"{base.rstrip('/')}/api/tags", timeout=3) as reply:
                data = json.loads(reply.read().decode("utf-8"))
        except (OSError, ValueError):
            data, reachable = {}, False
        for item in data.get("models", []) if isinstance(data, dict) else []:
            name = str(item.get("name", ""))
            details = item.get("details") if isinstance(item.get("details"), dict) else {}
            if not name or "embed" in name.casefold() or "bert" in str(details.get("family", "")).casefold():
                continue
            models.append({"name": name, "size": int(item.get("size") or 0),
                           "parameters": str(details.get("parameter_size", "")),
                           "quantization": str(details.get("quantization_level", ""))})
        bare = lambda name: name[:-len(":latest")] if name.endswith(":latest") else name  # noqa: E731
        models.sort(key=lambda model: (bare(model["name"]) != bare(default), model["name"].casefold()))
        return {"default": default, "models": models, "reachable": reachable}

    def _analysis_overrides(self, chosen: str) -> dict[str, Any] | None:
        """Cài đặt riêng của cuốn mới: Ollama riêng của Studio (app đóng gói) và model đọc hiểu người dùng chọn (nếu khác
        mặc định) - model ấy phải có trong Ollama, không thì dây chuyền hỏng ngay bước đầu."""
        overrides = dict(self.studio.settings_overrides()) if self.studio is not None else {}
        chosen = chosen.strip()
        if chosen:
            listed = self.analysis_models()
            names = {model["name"] for model in listed["models"]}
            if chosen != listed["default"] and chosen not in names:
                raise ApiError(HTTPStatus.BAD_REQUEST, f"Model “{chosen}” không có trong Ollama của máy này")
            overrides["analysis"] = {**(overrides.get("analysis") or {}), "model": chosen}
        return overrides or None

    def create(self, body: dict[str, Any]) -> dict[str, Any]:
        self._mutating()
        paths = [str(item) for item in body.get("paths", [])]
        # "Làm tiếp cuốn này": phần mới gieo từ phần trước (continuation.py) - tìm phần trước TRƯỚC khi tạo, để id sai
        # không để lại một dự án mồ côi.
        previous = self._book(str(body["seedFrom"])) if body.get("seedFrom") else None
        # "Sửa thiết lập" của sách chưa bắt đầu: cuốn cũ được thay - kiểm TRƯỚC khi tạo, như phần trước ở trên.
        replaces = str(body.get("replaces") or "")
        replaced = self._book(replaces) if replaces else None
        if replaced is not None and (self.runner.running(replaced) or self.jobs.starting(replaced)
                                     or not store.not_started(replaced)):
            raise ApiError(HTTPStatus.CONFLICT, "Sách cũ đã bắt đầu chạy - không làm lại được nữa. Tạo sách mới hay dùng "
                                                "“Làm tiếp cuốn này”.")
        root = actions.create_book(
            self.library.root, paths, str(body.get("title", "")), str(body.get("profile", "high_quality")),
            humanize.voice_key(str(body.get("narrator", ""))), str(body.get("firstPerson", "")),
            settings_overrides=self._analysis_overrides(str(body.get("analysisModel", "") or "")),
            first_person_chapters={str(key): str(value) for key, value in body["firstPersonChapters"].items()}
            if isinstance(body.get("firstPersonChapters"), dict) else None,
            drop_credit_lines=body["dropCreditLines"] if isinstance(body.get("dropCreditLines"), bool) else None,
        )
        self.preferences.add_recent(root)
        replace_error = ""
        unchanged = replaced is not None and root.resolve() == replaced.resolve()
        if unchanged:
            # Cùng tên, cùng chương, cùng thiết lập: dây chuyền mở lại ĐÚNG cuốn cũ (project.create_or_open_project) - không
            # có gì để thay, và tuyệt đối không bỏ chính nó vào Thùng rác (soát 01-10: lần thử đầu đã làm vậy).
            replaced = None
        if replaced is not None:
            # Bìa đã chọn cho cuốn cũ đi theo; cuốn cũ vào Thùng rác (khôi phục được). Không bỏ được thì cuốn mới vẫn còn,
            # lời báo nói rõ.
            for name in (covers.COVER_FILE, covers.META_FILE):
                if (replaced / name).is_file() and not (root / name).exists():
                    shutil.copy2(replaced / name, root / name)
            try:
                self.delete(replaces)
            except ApiError as error:
                replace_error = error.message
        if previous is not None:
            # Giữa lúc tạo và lúc chạy - sau khi chạy là quá muộn (đổi cách đọc tên làm trôi chữ dưới audio đã có).
            try:
                continuation.seed(previous, root)
            except continuation.ContinuationError as error:
                raise ApiError(HTTPStatus.CONFLICT,
                               f"Đã tạo sách nhưng không mang được gì từ phần trước: {error}") from error
        # Cách đọc dùng chung: mục nào có trong truyện thì sách mới nhận luôn, như người dùng sửa từng tên (trước khi chạy -
        # chưa có câu nào phải thu lại).
        shared = shared_readings.apply(root, shared_readings.present(self.shared_readings.entries(),
                                                                      shared_readings.file_texts(paths)))
        if body.get("start"):
            # Qua hàng đợi như nút "Bắt đầu": cuốn đang chạy thì cuốn mới xếp hàng, không tranh GPU (soát 28-09 - trước
            # đây "Tạo + bắt đầu ngay" chạy song song với cuốn đang sản xuất).
            self.start(book_id(root))
        # Đang có cuốn khác chạy thì cuốn mới vào hàng chờ: lời báo nói đúng thế, không "Đang khởi động" (soát UX a6 01-10).
        with self._queue_lock:
            queued = self.queue.index(book_id(root)) + 1 if book_id(root) in self.queue else 0
        return {"id": book_id(root), "sharedReadings": shared, "queued": queued,
                **({"replaceError": replace_error} if replace_error else {}),
                **({"unchanged": True} if unchanged else {})}

    def shared_readings_view(self) -> dict[str, Any]:
        return {"entries": self.shared_readings.entries()}

    def put_shared_reading(self, body: dict[str, Any], source: str = "") -> dict[str, Any]:
        surface = " ".join(str(body.get("surface", "")).split())[:80]
        if body.get("remove"):
            return {"removed": self.shared_readings.remove(surface)}
        spoken = " ".join(str(body.get("spokenForm", "")).split())[:120]
        if not surface or not spoken:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu từ hoặc cách đọc")
        try:
            return self.shared_readings.put(surface, spoken, source=source)
        except ValueError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, PRONUNCIATION_PROBLEMS.get(str(error), "Cách đọc này không dùng được")) from error

    def book_shared_readings(self, value: str, *, apply: bool) -> dict[str, Any]:
        """Mục của từ điển chung có trong cuốn này mà cuốn đang đọc khác; `apply` thì ghi chúng thành yêu cầu cách đọc."""
        path = self._book(value)
        waiting = shared_readings.differing(path, self.shared_readings.entries(), shared_readings.book_texts(path))
        if not apply:
            return {"entries": waiting}
        self._mutating()
        return {"applied": shared_readings.apply(path, waiting)}

    def _pinned_model(self, plan: dict[str, Any]) -> None:
        """Model đọc hiểu đã ghim của cuốn cũ: bỏ đi nếu là mặc định của app, chuyển sang `analysisModelMissing` nếu Ollama
        không còn model ấy (trình tạo nói ra thay vì hỏng lúc tạo)."""
        if not plan.get("analysisModel"):
            return
        try:
            listed = self.analysis_models()
        except Exception:  # noqa: BLE001 - Ollama tắt: giữ tên, bước tạo sách tự kiểm lại
            return
        if plan["analysisModel"] == listed["default"]:
            plan["analysisModel"] = ""
        elif plan["analysisModel"] not in {model["name"] for model in listed["models"]}:
            plan["analysisModelMissing"], plan["analysisModel"] = plan["analysisModel"], ""

    # ---- nhạc nền ------------------------------------------------------------------------------------------------
    def music_catalog(self) -> music_catalog.MusicCatalog:
        with self._music_lock:
            if self._music_catalog is None:
                self._music_catalog = music_catalog.MusicCatalog(self.music_dir / "catalog",
                                                                 self.remote_config.music_catalogs()[0])
            return self._music_catalog

    def music_view(self, value: str) -> dict[str, Any]:
        """Rãnh nhạc của cuốn + lựa chọn của người dùng. Chưa có thì dựng (cần danh mục: lần đầu cần mạng)."""
        path = self._book(value)
        plan = music_plan.read_plan(path)
        error = ""
        if plan is None:
            try:
                plan = self.music_rebuild(value)
            except music_catalog.CatalogError as exc:
                error = str(exc)
        return {"plan": plan, "overrides": music_plan.read_overrides(path), "error": error,
                "taxonomy": self._music_taxonomy()}

    def _music_taxonomy(self) -> dict[str, Any]:
        """Bảng phong cách / thể loại / nhãn GEMS từ danh mục (đổi được không cần cập nhật app); mất mạng thì rỗng."""
        try:
            catalog = self.music_catalog()
            taxonomy = catalog.manifest().get("taxonomy")
            if not taxonomy:  # bản đệm từ trước khi danh mục có bảng phân loại: đọc lại một lần
                taxonomy = catalog.manifest(refresh=True).get("taxonomy")
            return dict(taxonomy or {})
        except music_catalog.CatalogError:
            return {}

    def music_rebuild(self, value: str) -> dict[str, Any]:
        path = self._book(value)
        catalog = self.music_catalog()
        # Dựng lại = muốn dữ liệu mới nhất: đọc lại mục lục (nhỏ) thay vì bản đệm 24 giờ.
        manifest = catalog.manifest(refresh=True)
        return music_plan.build(path, lambda v, a: catalog.near(v, a, radius=1), catalog.lookup,
                                catalog_revision=str(manifest.get("revision") or ""), book_key=value,
                                taxonomy=manifest.get("taxonomy"))

    def music_update(self, value: str, body: dict[str, Any]) -> dict[str, Any]:
        """Người dùng sửa (bật/tắt, phong cách, âm lượng, ghim, im lặng, bỏ bài): lưu lựa chọn rồi dựng lại rãnh nhạc.
        Mất mạng thì lựa chọn vẫn được lưu, rãnh nhạc dựng lại lần sau."""
        self._mutating()
        path = self._book(value)
        music_plan.write_overrides(path, body)
        return self.music_view(value) if music_plan.read_plan(path) is None else self._music_after_change(value)

    def _music_after_change(self, value: str) -> dict[str, Any]:
        path = self._book(value)
        error = ""
        try:
            self.music_rebuild(value)
        except music_catalog.CatalogError as exc:
            error = str(exc)
        return {"plan": music_plan.read_plan(path), "overrides": music_plan.read_overrides(path), "error": error,
                "taxonomy": self._music_taxonomy()}

    def music_cues(self, value: str, chapter_id: int) -> dict[str, Any]:
        """Nhạc của một chương cho trình phát: mốc thời gian + đường lấy file qua máy này (đệm, tua được)."""
        path = self._book(value)
        plan = music_plan.read_plan(path)
        if plan is None:
            return {"cues": [], "levelDb": music_plan.DEFAULT_LEVEL_DB}
        cues = [dict(cue, src="/api/music/track?link=" + quote(cue["link"], safe=""))
                for cue in music_plan.chapter_cues(plan, chapter_id)]
        return {"cues": cues, "levelDb": plan.get("levelDb", music_plan.DEFAULT_LEVEL_DB)}

    def music_track_file(self, link: str) -> Path:
        """File nhạc của một bài trong danh mục: tải một lần từ nguồn gốc vào bộ nhớ đệm, lần sau dùng lại. Chỉ bài CÓ
        trong danh mục - máy chủ này không thành chỗ tải hộ link tuỳ ý."""
        if not link.startswith("https://"):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Link nhạc không hợp lệ")
        target = self.music_dir / "files" / (hashlib.sha1(link.encode("utf-8")).hexdigest() + ".mp3")
        if target.is_file():
            return target
        try:
            known = self.music_catalog().lookup([link])
        except music_catalog.CatalogError as exc:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, str(exc)) from exc
        if link not in known:
            raise ApiError(HTTPStatus.NOT_FOUND, "Bài này không có trong danh mục nhạc nền")
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_suffix(".part")
        try:
            request = urllib.request.Request(link, headers={"User-Agent": music_catalog.USER_AGENT})
            with urllib.request.urlopen(request, timeout=60) as response, part.open("wb") as sink:
                shutil.copyfileobj(response, sink, 1 << 16)
            os.replace(part, target)
        except OSError as exc:
            part.unlink(missing_ok=True)
            raise ApiError(HTTPStatus.BAD_GATEWAY, "Không tải được bài nhạc từ nguồn - kiểm tra mạng") from exc
        return target

    def redo(self, value: str) -> dict[str, Any]:
        """"Sửa thiết lập" (store.redo_plan): lựa chọn lúc tạo của một cuốn chưa bắt đầu, và phần trước nếu nó là phần
        nối tiếp - để cuốn làm lại vẫn mang dàn nhân vật của phần trước."""
        path = self._book(value)
        plan = store.redo_plan(path)
        plan["started"] = plan["started"] or self.runner.running(path) or self.jobs.starting(path)
        previous = continuation.previous_project(path)
        plan["seedFrom"] = book_id(previous) if previous is not None and store.is_project(previous) else ""
        self._pinned_model(plan)
        return plan

    def continuation(self, value: str) -> dict[str, Any]:
        """"Làm tiếp cuốn này": chương kế tiếp, cài đặt và thứ sẽ mang theo - trình tạo sách điền sẵn từ đây. Tính từ phần
        MỚI NHẤT của cuốn (bấm ở phần 1 khi đã có phần 2 thì nối sau phần 2); `sourceId` là phần ấy - gieo từ nó."""
        clicked = self._book(value).resolve()
        latest = continuation.latest_part(clicked, self.library.projects())
        plan = store.continuation_plan(latest)
        plan["sourceId"] = book_id(latest)
        self._pinned_model(plan)
        if latest != clicked:
            # Bấm ở phần cũ khi cuốn đã có phần sau (soát UX a6 01-10, B1): phần mới nối sau phần MỚI NHẤT - nói ra, không thì
            # người dùng tưởng máy bỏ qua một phần ("Phần 1" -> "Phần 3").
            def title(project: Path) -> str:
                try:
                    return str(store.summarize(project)["title"])
                except (OSError, ValueError, KeyError):
                    return project.name

            plan["clickedTitle"], plan["latestTitle"] = title(clicked), title(latest)
        return plan

    def parts(self, value: str) -> list[dict[str, Any]]:
        """Các phần của cuốn mà sách này thuộc về (chuỗi dài nhất qua nó, phần đầu trước) - trang dự án chỉ sang phần kia
        (soát UX 29-09: phần 1 không nói đã có phần 2, phần 2 không nói nối tiếp cuốn nào). Một phần lẻ thì rỗng."""
        here = self._book(value).resolve()
        chain = continuation.chain_of(continuation.latest_part(here, self.library.projects()))
        if here not in chain:
            chain = continuation.chain_of(here)
        if len(chain) < 2:
            return []
        out = []
        for project in chain:
            try:
                title = str(store.summarize(project)["title"])
            except (OSError, ValueError, KeyError):
                title = project.name
            out.append({"id": book_id(project), "title": title, "part": index_part(chain, project),
                        "current": project == here})
        return out

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
            "bluetooth": self.bluetooth.view() if self.bluetooth is not None else None,
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
                app = SyncApp(self.library, self.listening, self.devices, socket_name(), self.remote, studio=studio,
                              routes=self.routes,
                              player=self.player, cast=self.cast)
                self.sync_server = SyncServer(app, host=self.sync_host, port=self.sync_port).start()
                self.sync_error = ""
                if self.sync_host == "0.0.0.0":  # máy chủ thật (không phải bài thử chỉ nghe 127.0.0.1)
                    try:
                        self.bluetooth = bluetooth.BluetoothServer(self.sync_server.port, socket_name()).start()
                    except Exception:  # noqa: BLE001 - Bluetooth không bao giờ được làm hỏng đồng bộ qua Wi-Fi
                        self.bluetooth = None
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
        self.player.reset()
        if self.bluetooth is not None:
            self.bluetooth.stop()
            self.bluetooth = None
        if self.sync_server is not None:
            self.sync_server.stop()
            self.sync_server = None

    def close(self) -> None:
        """App đóng: tắt cổng đồng bộ nhưng giữ nguyên lựa chọn của người dùng cho lần mở sau."""
        self._stop_sync()
        self.cast.close()

    def routes(self) -> dict[str, Any]:
        """Các đường tới máy này cho thiết bị vừa ghép: địa chỉ LAN + cổng đồng bộ, và địa chỉ Bluetooth khi cổng
        Bluetooth đang nghe - điện thoại dùng Wi-Fi khi được, Bluetooth khi không (tự chọn đường)."""
        lan = local_addresses() if self.sync_host == "0.0.0.0" else [self.sync_host]
        port = self.sync_server.port if self.sync_server is not None else self.sync_port
        bluetooth = getattr(self, "bluetooth", None)
        address = str(bluetooth.view().get("address") or "") if bluetooth is not None and bluetooth.view().get("running") else ""
        return {"lan": [host for host in lan if host not in ("127.0.0.1", "0.0.0.0")], "port": int(port), "bluetooth": address}

    def remote_view(self) -> dict[str, Any]:
        """Máy khác đang có sách trên trình phát (PLAYER_RESEARCH #12), kèm những gì máy này biết về cuốn ấy: có trong
        thư viện không (để "Nghe trên máy này") và ảnh bìa. Hai nguồn: điện thoại báo lên cổng đồng bộ (`via` remote), và
        máy đã ghép ở "Máy tính khác" - máy tính hay điện thoại chia sẻ thư viện - do PeerPlayers hỏi nền (`via` peer; sách
        của chúng ở máy này là cuốn ảo, `localBookId`). Giao diện hỏi mỗi 1,5 giây nên ở đây không mở SQLite, không đợi mạng."""
        phones = []
        for phone in self.remote.view() if self.sync_server is not None else []:
            path = self.library.resolve(phone["bookId"]) if phone["bookId"] else None
            phone["known"] = path is not None
            # điện thoại chưa đổi khoá báo mã kiểu cũ: giao diện luôn nhận mã hiện hành của cuốn
            phone["localBookId"] = book_id(path) if path is not None else None
            phone["cover"] = covers.cover_view(path, phone["localBookId"]) if path is not None else None
            phones.append({**phone, "kind": "phone", "via": "remote"})
        # Điện thoại vừa báo lên đây vừa chia sẻ thư viện: một thanh là đủ. Nhận ra nó bằng tên VÀ đúng cuốn, đúng chương
        # đang phát - hai điện thoại cùng đời máy (cùng tên) đang nghe hai thứ khác nhau thì vẫn là hai thanh.
        reporting = {(phone["name"], phone["bookId"], phone["chapterId"]) for phone in phones}
        for peer in self.peer_players.view():
            if (peer["name"], peer["bookId"], peer["chapterId"]) in reporting:
                continue
            path = remote_books.local_book(self.library.root, peer["device"], peer["bookId"]) if peer["bookId"] else None
            local = book_id(path) if path is not None else None
            if path is None and peer["bookId"] and (own := self.library.resolve(peer["bookId"])) is not None:
                path, local = own, book_id(own)  # máy kia đang nghe thẳng sách của CHÍNH máy này
            peer["known"] = local is not None
            peer["localBookId"] = local
            peer["cover"] = covers.cover_view(path, local) if path is not None and local is not None else None
            phones.append(peer)
        for device in self.cast.view():
            path = self.library.resolve_listenable(device["bookId"]) if device["bookId"] else None
            device["known"] = path is not None
            device["localBookId"] = device["bookId"] if path is not None else None
            device["cover"] = covers.cover_view(path, device["bookId"]) if path is not None else None
            phones.append(device)
        return {"phones": phones}

    def remote_send(self, device: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            command = remote_command(body)
        except ValueError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error
        if self.cast.owns(device):
            try:
                return self.cast.send(device, command)
            except CastError as error:
                raise ApiError(HTTPStatus.CONFLICT, str(error)) from error
        entry = self.computers.get(device)
        if entry is None or any(phone["device"] == device for phone in self.remote.view()):
            try:
                return {"id": self.remote.send(device, command)["id"]}
            except LookupError as error:
                raise ApiError(HTTPStatus.CONFLICT, "Máy kia không còn kết nối - mở ABook trên máy ấy rồi thử lại") from error
        if command["action"] == "load":
            # "Phát trên <máy kia>": giao diện gửi mã cuốn của MÁY NÀY; máy kia chỉ phát được sách của chính nó.
            path = self.library.resolve_listenable(command["bookId"])
            remote = remote_books.remote_of(packages.manifest(path)) if path is not None and packages.is_package(path) else None
            if remote is None or remote["computer"] != device:
                raise ApiError(HTTPStatus.CONFLICT, f"{entry['name']} không có cuốn này")
            command["bookId"] = remote["book"]
        try:
            reply = remote_books.player_command(entry, command)
        except remote_books.RemoteError as error:
            raise ApiError(HTTPStatus.CONFLICT, str(error)) from error
        finally:
            self.peer_players.poke(device)
        if reply.get("ok") is False:
            raise ApiError(HTTPStatus.CONFLICT, f"{entry['name']}: {reply.get('message') or 'không làm được lệnh này'}")
        return {"id": str(reply.get("id") or "")}

    # Loa / TV (webui/cast.py) dùng đúng đường của trình phát trong app: sách nghe được, file chương, chỗ nghe, bìa.
    def _cast_book(self, value: str) -> dict[str, Any]:
        try:
            return self.listen_book(value)
        except ApiError as error:
            raise CastError(error.message) from None

    def _cast_audio(self, value: str, chapter: int) -> Path | None:
        book = self.library.resolve_listenable(value)
        if book is None:
            return None
        return packages.chapter_file(book, chapter) if packages.is_package(book) else store.chapter_audio_path(book, chapter)

    def _cast_save(self, value: str, chapter: int, seconds: float, duration: float) -> None:
        self.listening.progress(value, chapter, seconds, duration)
        self.sync_remote_state(value, wait=False)

    def _cast_cover(self, value: str) -> Path | None:
        book = self.library.resolve_listenable(value)
        return covers.cover_file(book) if book is not None else None

    def report_player(self, body: dict[str, Any]) -> dict[str, Any]:
        """Giao diện máy này báo trình phát của nó và treo tới `wait` giây chờ lệnh từ máy đã ghép (như điện thoại báo
        máy tính, sync.Remote). Đồng bộ tắt thì không ai gửi lệnh được: trả ngay `idle`, giao diện thưa lại."""
        if self.sync_server is None:
            return {"commands": [], "idle": True}
        commands = self.player.report(LOCAL_PLAYER, socket_name(), body, body.get("wait", 0))
        return {"commands": [{key: value for key, value in command.items() if key != "at"} for command in commands]}

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

    def discover_computers(self) -> dict[str, Any]:
        """Máy tính ABook khác đang bật kết nối trong mạng (cùng cách điện thoại tìm máy tính) - để khỏi gõ địa chỉ."""
        paired = {(entry.get("host"), int(entry.get("port") or 0)) for entry in self.computers.list()}
        own_port = self.sync_port if self.sync_server is not None else None
        found = remote_books.discover(exclude_port=own_port)
        return {"found": [{**item, "paired": (item["host"], item["port"]) in paired} for item in found]}

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
                "name": humanize.voice_label(preset["name"]),
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

    def _source_paths(self, raw: Any, seed_from: Any = None) -> list[str]:
        paths = [str(item) for item in (raw or [])]
        if self._remote():
            uploads = Path(self.app.preferences.get()["libraryRoot"]) / actions.UPLOAD_FOLDER
            # "Làm tiếp cuốn này" từ xa: chương kế tiếp do CHÍNH máy này tính từ dự án phần trước - thiết bị chỉ chọn trong
            # danh sách ấy. So nguyên chuỗi, không `resolve()` chuỗi thiết bị gửi (đường UNC làm Windows tự nối SMB).
            following = ({str(path) for path in continuation.next_chapters(self.app._book(str(seed_from)))}
                         if seed_from else set())
            if not all(path in following or actions.inside_folder(path, uploads) for path in paths):
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
                    groups = [unquote(group) for group in match.groups()]
                    if groups and pattern.pattern.startswith(BOOK_ROUTES):
                        # mã kiểu cũ (link cũ, điện thoại chưa đổi khoá) -> mã hiện hành: mọi handler dùng mã làm khoá
                        # dữ liệu nghe, phán quyết, hàng đợi nhận đúng một mã cho mỗi cuốn
                        groups[0] = self.app.library.canonical(groups[0])
                    handler(self, query, *groups)
                    return
            raise ApiError(HTTPStatus.NOT_FOUND, "Không có đường dẫn này")
        except ApiError as error:
            self._send_json(error.status, {"error": error.message, **error.extra})
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

    def get_pending_changes(self, _query: dict[str, list[str]], value: str) -> None:
        # Hộp xem trước của nút "Áp dụng N thay đổi": từng thay đổi, số câu / chương thu lại, thời gian ước (store.pending_details).
        project = self.app._book(value)
        with closing(store.connect(project)) as connection:
            row = connection.execute("SELECT updated_at FROM book WHERE id=1").fetchone()
        since = store.changes_since(project, float(row["updated_at"] or 0) if row is not None else 0.0)
        self._send_json(HTTPStatus.OK, store.pending_details(project, since))

    def post_pending_withdraw(self, _query: dict[str, list[str]], value: str) -> None:
        # Bỏ một thay đổi khỏi hộp "Áp dụng N thay đổi" trước khi áp (soát UX a6 01-10: muốn bỏ một mục thì phải đi tìm lại
        # đúng thẻ / đúng câu ở ba tab khác nhau). Chỉ khi sách KHÔNG chạy: đang chạy thì dây chuyền có thể đang áp chính
        # yêu cầu ấy ở ranh giới chương. Yêu cầu từng thay một yêu cầu cũ thì yêu cầu cũ trở lại (withdraw_requests).
        self.app._mutating()
        path = self.app._book(value)
        if self.app.runner.running(path) or self.app.jobs.starting(path):
            raise ApiError(HTTPStatus.CONFLICT, "Sách đang chạy - máy có thể đang áp chính thay đổi này. Tạm dừng hẳn rồi bỏ.")
        body = self._body()
        section, key = str(body.get("section") or ""), str(body.get("key") or "")
        try:
            requested_at = float(body.get("requestedAt") or 0)
        except (TypeError, ValueError):
            requested_at = 0.0
        if section not in ("pronunciations", "speakers", "lines", "voices", "retakes") or not key or requested_at <= 0:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu thay đổi cần bỏ")
        group = ([str(item) for item in body.get("keys") or [] if isinstance(item, str)][:5000]
                 if section in store.BY_CLICK else [])
        mine = listener_overrides.requests_made_at(listener_overrides.read_overrides(path), section, group or [key], requested_at)
        if not mine:
            raise ApiError(HTTPStatus.CONFLICT, "Thay đổi này vừa được thay bằng một lựa chọn sau - mở lại hộp để xem.")
        if section == "retakes":
            # "Thu lại cả chương" là một nhóm: bỏ cả nhóm - chỉ những câu còn đúng lần bấm ấy.
            for stable_id in mine:
                listener_overrides.cancel_retake(path, stable_id)
        else:
            listener_overrides.withdraw_requests(path, section, list(mine), requested_at)
            if section == "speakers":
                # "Gộp vào…" ghi cả bí danh cùng mốc ấy: bỏ lần gộp là bỏ luôn bí danh.
                aliases.remove_added_at(path, requested_at)
        self._send_json(HTTPStatus.OK, {"withdrawn": len(mine)})

    def post_merge_character(self, _query: dict[str, list[str]], value: str) -> None:
        # Tab Nhân vật: "Gộp vào…" (soát UX a6 01-10: máy tách một người thành hai - "Lucien" và "Giáo sư Lucien" - mà Studio
        # chỉ sửa được từng câu). Đi đúng đường có sẵn: mọi câu nói của người này thành câu của người kia (overrides.json
        # `speakers`, một lần ghi, một mốc) + bí danh cấp TÊN (aliases.json) để phần sau của cuốn tự hiểu. Bỏ trong hộp
        # "Áp dụng" là bỏ cả hai.
        self.app._mutating()
        path = self.app._book(value)
        body = self._body()
        source = str(body.get("from", "")).strip()[:200]
        target = str(body.get("into", "")).strip()[:200]
        if not source or not target or aliases.key(source) == aliases.key(target):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Chọn hai người khác nhau")
        with closing(store.connect(path)) as connection:
            rows = connection.execute(
                "SELECT stable_id, text_sha256, speaker FROM segments WHERE kind IN ('dialogue', 'thought')"
                " AND stable_id IS NOT NULL AND text_sha256 IS NOT NULL ORDER BY chapter_id, seq"
            ).fetchall()
        lines = [(str(row["stable_id"]), str(row["text_sha256"])) for row in rows
                 if aliases.key(str(row["speaker"] or "")) == aliases.key(source)]
        if not lines:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Người này không còn câu nói nào để gộp")
        problem = store.speaker_request_problem(path, lines[0][0], lines[0][1], target, "")
        if problem is not None:
            raise ApiError(HTTPStatus.BAD_REQUEST, SPEAKER_PROBLEMS.get(problem, "Không gộp được vào người này"))
        now = time.time()
        listener_overrides.request_speakers(path, lines, target, now=now)
        aliases.add(path, source, target, now=now)
        self._send_json(HTTPStatus.OK, {"lines": len(lines), "requestedAt": now})

    def post_chapter_retake(self, _query: dict[str, list[str]], value: str, chapter: str) -> None:
        # Menu "…" của một chương: thu lại MỌI câu đã thu của chương bằng hạt giống mới (soát UX a5/a6 01-10: cả chương nghe
        # không ổn thì phải bấm "Cần thu lại" từng câu). Cùng đường với "Cần thu lại" một câu (overrides.json `retakes`),
        # cùng một mốc thời gian để hộp "Áp dụng" coi là một thay đổi; dây chuyền áp ở ranh giới như mọi yêu cầu.
        self.app._mutating()
        path = self.app._book(value)
        with closing(store.connect(path)) as connection:
            rows = connection.execute(
                "SELECT stable_id, text_sha256 FROM segments WHERE chapter_id=? AND wav_path IS NOT NULL AND wav_path != ''"
                " AND stable_id IS NOT NULL AND text_sha256 IS NOT NULL ORDER BY seq",
                (int(chapter),),
            ).fetchall()
        if not rows:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Chương này chưa có câu nào đã thu để thu lại.")
        now = time.time()
        for row in rows:
            listener_overrides.request_retake(path, str(row["stable_id"]), str(row["text_sha256"]), now=now)
        self._send_json(HTTPStatus.OK, {"lines": len(rows), "requestedAt": now})

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

    def post_pause(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.ACCEPTED, self.app.pause(value, self._body().get("paused") is not False))

    def delete_listen_book(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.remove_imported(value))

    def put_title(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.rename(value, str(self._body().get("title") or "")))

    def delete_book(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.delete(value))

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

    def post_projectfile(self, _query: dict[str, list[str]], value: str) -> None:
        # Cả dự án trong một file (projectfile.py) - chuyển máy, sao lưu, làm tiếp ở chỗ khác.
        project = self.app._book(value)
        target = self._target(self._body())
        root = Path(target) if target else Path(self.app.preferences.get()["libraryRoot"]) / "Đã xuất"
        title = store.summarize(project)["title"] or project.name
        try:
            path = projectfile.pack(project, root / projectfile.default_name(title),
                                    running=self.app.runner.running(project))
            with projectfile.ProjectFile(path) as packed:
                missing = packed.missing_sources
        except projectfile.ProjectFileError as error:
            raise ApiError(HTTPStatus.CONFLICT, str(error)) from error
        self.app.exports.add(str(path.parent))
        self._send_json(HTTPStatus.OK, {"file": str(path), "folder": str(path.parent), "size": path.stat().st_size,
                                        "missingSources": missing})

    def get_review(self, query: dict[str, list[str]], value: str) -> None:
        project = self.app._book(value)
        verdicts = self.app.reviews.get(value)
        self._send_json(HTTPStatus.OK, review_view(project, verdicts, include_minor=query.get("all") == ["1"]))

    def get_work(self, _query: dict[str, list[str]], value: str) -> None:
        # "Việc cần duyệt" (docs/STUDIO_REVIEW.md): chỗ máy nghi ngờ, xếp theo lợi trên mỗi lần bấm.
        self._send_json(HTTPStatus.OK, work_items(self.app._book(value)))

    def get_music(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.music_view(value))

    def put_music(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.music_update(value, self._body()))

    def post_music_rebuild(self, _query: dict[str, list[str]], value: str) -> None:
        try:
            self.app.music_rebuild(value)
        except music_catalog.CatalogError as error:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, str(error)) from error
        self._send_json(HTTPStatus.OK, self.app.music_view(value))

    def get_music_cues(self, _query: dict[str, list[str]], value: str, chapter: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.music_cues(value, int(chapter)))

    def get_music_track(self, query: dict[str, list[str]]) -> None:
        self._send_file(self.app.music_track_file((query.get("link") or [""])[0]), cache=True)

    def get_redo(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.redo(value))

    def get_continuation(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.continuation(value))

    def get_parts(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, {"parts": self.app.parts(value)})

    def get_name_readings(self, _query: dict[str, list[str]], value: str) -> None:
        # Tab Nhân vật, mục "Cách đọc tên" (name_readings.py): mọi cách đọc của cuốn, kể cả cách máy chắc và cách đã ghim.
        self._send_json(HTTPStatus.OK, name_readings(self.app._book(value)))

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
        if body.get("withdraw"):
            # Cách đọc chỉ sửa được trên thẻ, mà thẻ biến mất khi cách đọc đã vào sách: đã áp thì hoàn tác bằng cách xin
            # lại cách đọc cũ (`previous`, cách máy đọc lúc bấm) - câu có từ ấy được đọc lại như trước.
            previous = " ".join(str(body.get("previous", "") or "").split())[:120]
            usable = bool(previous) and listener_overrides.pronunciation_problem(surface, previous) is None
            # Lần sửa ấy cũng đưa cách đọc vào từ điển chung ("Dùng cho mọi sách"): hoàn tác gỡ luôn mục ấy - nếu nó vẫn là
            # đúng cách đọc ấy (soát UX 01-10: hoàn tác xong, sách khác vẫn được mời dùng cách đọc vừa bỏ).
            shared = " ".join(str(body.get("shared", "") or "").split())
            if shared and any(entry["surface"].casefold() == surface.casefold() and entry["spokenForm"] == shared
                              for entry in self.app.shared_readings.entries()):
                self.app.shared_readings.remove(surface)
            self._withdraw(path, "pronunciations", [listener_overrides.surface_key(surface)] if surface else [], body,
                           restore=(lambda now: listener_overrides.request_pronunciation(path, surface, previous, now=now))
                           if usable else None)
            return
        spoken = " ".join(str(body.get("spokenForm", "")).split())[:120]
        if not surface or not spoken:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu tên hoặc cách đọc")
        problem = listener_overrides.pronunciation_problem(surface, spoken)
        if problem is not None:
            # Gõ theo tai mà sai chính tả ("Hên-kơ"): nói đúng âm tiết sai và mời dùng bản sửa - bản sửa qua đúng phép kiểm
            # vừa từ chối thì mới mời (soát UX 29-09: câu báo chung không chỉ chỗ sửa).
            fixed = spelling.respelled(spoken)
            if problem == listener_overrides.NOT_VIETNAMESE and fixed != spoken and \
                    listener_overrides.pronunciation_problem(surface, fixed) is None:
                raise ApiError(HTTPStatus.BAD_REQUEST, f"{spelling.respelling_note(spoken, fixed)} Viết: “{fixed}”.",
                               suggestion=fixed)
            raise ApiError(HTTPStatus.BAD_REQUEST, PRONUNCIATION_PROBLEMS.get(problem, "Cách đọc này không dùng được"))
        now = time.time()
        listener_overrides.request_pronunciation(path, surface, spoken, now=now)
        if body.get("everywhere") is True:
            # "Dùng cho mọi sách": cùng cách đọc vào từ điển chung - sách mới có từ này tự nhận nó.
            self.app.put_shared_reading({"surface": surface, "spokenForm": spoken}, source=store.summarize(path)["title"])
        self._send_json(HTTPStatus.OK, {"surface": surface, "spokenForm": spoken, "requestedAt": now})

    def _withdraw(self, path: Path, section: str, keys: list[str], body: dict[str, Any], *,
                  restore: Callable[[float], None] | None = None) -> None:
        # "Hoàn tác" trên thông báo sau một quyết định trong hộp việc: bỏ yêu cầu của ĐÚNG lần bấm ấy (`requestedAt` do
        # lần bấm trả về) khi dây chuyền chưa đưa nó vào sách - thẻ hỏi lại như chưa bấm. Đã vào sách thì bỏ yêu cầu cũng
        # không đổi lại được gì: xin lại giá trị cũ nếu có cách (`restore`), không thì nói thật và giữ yêu cầu. "Giữ
        # nguyên" (`keep`) không đổi gì trong sách, áp hay chưa cũng bỏ được.
        try:
            requested_at = float(body.get("requestedAt") or 0)
        except (TypeError, ValueError):
            requested_at = 0.0
        if not keys or requested_at <= 0:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu quyết định cần hoàn tác")
        mine = listener_overrides.requests_made_at(listener_overrides.read_overrides(path), section, keys, requested_at)
        if not mine:
            raise ApiError(HTTPStatus.CONFLICT, "Quyết định này đã được thay bằng một lựa chọn sau - không còn gì để hoàn tác.")
        if not body.get("keep") and store.already_applied(path, section, mine):
            if restore is None:
                raise ApiError(HTTPStatus.CONFLICT, WITHDRAW_APPLIED[section])
            restore(time.time())
            self._send_json(HTTPStatus.OK, {"undone": len(mine), "restored": True})
            return
        removed = listener_overrides.withdraw_requests(path, section, list(mine), requested_at)
        self._send_json(HTTPStatus.OK, {"undone": len(removed), "restored": False})

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
        if body.get("withdraw"):
            self._withdraw(path, "speakers", [stable_id for stable_id, _sha in lines if stable_id], body)
            return
        if not speaker or not lines or not all(stable_id and text_sha256 for stable_id, text_sha256 in lines):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu câu hoặc người nói")
        # "Người mới…": người nghe tạo người nói chưa có trong sách (tên + giới) - dây chuyền cấp giọng như bước phân vai.
        new_gender = str(body.get("newGender", "")).strip()
        if new_gender and new_gender not in listener_overrides.NEW_CHARACTER_GENDERS:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Giới của người mới không hợp lệ")
        for stable_id, text_sha256 in lines:
            problem = store.speaker_request_problem(path, stable_id, text_sha256, speaker, new_gender)
            if problem is not None:
                raise ApiError(HTTPStatus.BAD_REQUEST, SPEAKER_PROBLEMS.get(problem, "Không đổi được người nói câu này"))
        now = time.time()
        listener_overrides.request_speakers(path, lines, speaker, now=now, new_gender=new_gender)
        # Thẻ "Một người hai tên": ngoài các câu này, ghi luôn cấp TÊN (aliases.py) - phần sau của cuốn tự hiểu.
        alias = str(body.get("alias", "") or "").strip()[:200]
        remembered = bool(alias) and aliases.add(path, alias, speaker)
        # Thẻ 『』 với phạm vi "Cả cuốn": quy ước của cuốn (bracket_rule.py) - các phần sau tự áp trước khi phân vai.
        if body.get("bracketRule"):
            remembered = bracket_rule.save(path, speaker) or remembered
        self._send_json(HTTPStatus.OK, {"lines": len(lines), "speaker": speaker, "new": bool(new_gender),
                                        "alias": remembered, "requestedAt": now})

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
        # Chữ đem đọc (STUDIO_REVIEW mục 7): None = không đụng, "" = trả về chữ của sách.
        spoken = str(body["spoken"])[:2200] if isinstance(body.get("spoken"), str) else None
        if not stable_id or not text_sha256 or not (kind or emotion or intensity is not None or speaker or spoken is not None):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu câu hoặc thay đổi")
        problem = store.line_request_problem(path, stable_id, text_sha256, kind=kind, emotion=emotion,
                                             intensity=intensity, speaker=speaker, spoken=spoken)
        if problem is not None:
            raise ApiError(HTTPStatus.BAD_REQUEST, LINE_PROBLEMS.get(problem, "Không đổi được cách đọc câu này"))
        listener_overrides.request_line(path, stable_id, text_sha256, kind=kind, emotion=emotion, intensity=intensity,
                                        speaker=speaker, spoken=spoken, now=time.time())
        self._send_json(HTTPStatus.OK, {"stableId": stable_id, "kind": kind, "emotion": emotion, "intensity": intensity,
                                        "spoken": spoken})

    def post_voice(self, _query: dict[str, list[str]], value: str) -> None:
        # Giọng / giới của MỘT nhân vật (thẻ "Nam hay nữ", "Chung giọng"): như người nói - ghi mong muốn vào overrides.json,
        # dây chuyền áp ở ranh giới chương; hỏi SQLite chỉ đọc bằng đúng phép dây chuyền dùng để từ chối tại chỗ.
        self.app._mutating()
        path = self.app._book(value)
        body = self._body()
        character = str(body.get("character", "")).strip()[:200]
        if body.get("withdraw"):
            self._withdraw(path, "voices", [listener_overrides.character_key(character)] if character else [], body)
            return
        preset = humanize.voice_key(str(body.get("preset", "") or "").strip()[:120])
        gender = str(body.get("gender", "") or "").strip()[:10]
        avoid = str(body.get("avoid", "") or "").strip()[:200]
        if not character:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu nhân vật")
        problem = store.voice_request_problem(path, character, preset=preset, gender=gender, avoid=avoid)
        if problem is not None:
            raise ApiError(HTTPStatus.BAD_REQUEST, VOICE_PROBLEMS.get(problem, "Không đổi được giọng nhân vật này"))
        now = time.time()
        listener_overrides.request_voice(path, character, preset=preset, gender=gender, avoid=avoid, now=now)
        self._send_json(HTTPStatus.OK, {"character": character, "preset": humanize.voice_label(preset), "gender": gender,
                                        "avoid": avoid, "requestedAt": now})

    def post_review(self, _query: dict[str, list[str]], value: str) -> None:
        self.app._mutating()  # ghi reviews.json và (Cần thu lại) overrides.json - như mọi yêu cầu sửa khác
        body = self._body()
        verdict = body.get("verdict")
        if verdict not in (None, "ok", "redo"):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Phán quyết không hợp lệ")
        stable_id = str(body.get("stableId", ""))[:80]
        project = self.app._book(value)
        self.app.reviews.set(value, stable_id, verdict, int(body.get("chapterId", 0)))
        # "Cần thu lại" là một yêu cầu cho dây chuyền (overrides.json `retakes`: thu bằng hạt giống mới ở lần chạy tới -
        # sách đã xong: nút "Áp dụng thay đổi"); đổi ý thì bỏ yêu cầu chưa áp.
        text_sha256 = store.segment_text_sha256(project, stable_id)
        if verdict == "redo" and text_sha256:
            listener_overrides.request_retake(project, stable_id, text_sha256, now=time.time())
        elif verdict != "redo":
            listener_overrides.cancel_retake(project, stable_id)
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

    def post_player_report(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.report_player(self._body()))

    def post_cast_scan(self, _query: dict[str, list[str]]) -> None:
        self.app.cast.scan()
        self._send_json(HTTPStatus.OK, {"scanning": True})

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

    def get_computers_discover(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.discover_computers())

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
        target = self.app.library.canonical(str(self._body().get("book", "")))
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
        book = self.app.library.canonical(str(body.get("bookId", "")))
        self.app.listening.dismiss_night(book, str(body.get("id", "")))
        self._send_json(HTTPStatus.OK, {"ok": True})

    def post_open(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.open_existing(self._body()))

    def post_create(self, _query: dict[str, list[str]]) -> None:
        body = self._body()
        self._source_paths(body.get("paths"), body.get("seedFrom"))
        if body.get("replaces") and self._remote():
            # Thay = bỏ cuốn cũ vào Thùng rác: như xoá, chỉ từ chính máy này.
            raise ApiError(HTTPStatus.FORBIDDEN, "Sửa thiết lập (làm lại sách) chỉ làm được trên máy tính")
        self._send_json(HTTPStatus.CREATED, self.app.create(body))

    def post_scan(self, _query: dict[str, list[str]]) -> None:
        body = self._body()
        # EPUB tách vào thư viện (như "Nguồn tải lên"), không ghi cạnh file của người dùng.
        result = actions.scan_inputs(self._source_paths(body.get("paths"), body.get("seedFrom")),
                                     epub_root=self.app.library.root / "Nguồn EPUB")
        result["existing"] = self.app.existing_projects([str(row.get("sha256") or "") for row in result["files"]])
        self._send_json(HTTPStatus.OK, result)

    def post_source_split(self, _query: dict[str, list[str]]) -> None:
        # Người dùng bấm "Tách thành N chương" (đề xuất của bước 1): các chương ghi vào thư mục mới trong thư viện, file
        # gốc giữ nguyên. Từ xa: nguồn phải là file đã gửi lên, và kết quả cũng nằm trong "Nguồn tải lên" để quét tiếp được.
        from . import txt_split

        self.app._mutating()
        body = self._body()
        paths = self._source_paths([str(body.get("path") or "")])
        source = Path(paths[0].strip().strip('"').strip("'").strip()).expanduser()
        if not source.is_file() or source.suffix.casefold() != ".txt":
            raise ApiError(HTTPStatus.BAD_REQUEST, "Chỉ tách được một file .txt có sẵn trên máy này")
        library = Path(self.app.preferences.get()["libraryRoot"])
        root = library / (actions.UPLOAD_FOLDER if self._remote() else actions.SPLIT_FOLDER)
        try:
            folder = txt_split.split(source, root)
        except (OSError, ValueError) as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, f"Không tách được: {error}") from error
        self._send_json(HTTPStatus.OK, {"folder": str(folder)})

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
        self._send_json(HTTPStatus.OK, actions.first_person_hint(self._source_paths(body.get("paths"), body.get("seedFrom"))))

    def get_voices(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.voices())

    def get_preferences(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.preferences.get())

    def get_analysis_models(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.analysis_models())

    def get_shared_readings(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.shared_readings_view())

    def post_shared_readings(self, _query: dict[str, list[str]]) -> None:
        self.app._mutating()
        self._send_json(HTTPStatus.OK, self.app.put_shared_reading(self._body()))

    def get_book_shared_readings(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.book_shared_readings(value, apply=False))

    def post_book_shared_readings(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.book_shared_readings(value, apply=True))

    def put_preferences(self, _query: dict[str, list[str]]) -> None:
        body = self._body()
        allowed = {key: body[key] for key in ("theme", "libraryRoot") if key in body}
        # Tốc độ và âm lượng là SỐ trong khoảng giao diện đưa ra (player.SPEEDS 0,75-3; âm lượng 0-1): trình phát nạp lại
        # chúng lúc mở app, và một giá trị hỏng (chuỗi, 5) từng được lưu nguyên.
        for key, low, high in (("playbackRate", 0.5, 3.0), ("volume", 0.0, 1.0)):
            value = body.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and low <= float(value) <= high:
                allowed[key] = float(value)
        # Hai tuỳ chọn hẹn giờ ngủ chỉ nhận đúng các mức giao diện đưa ra.
        if body.get("sleepFadeSeconds") in (10, 30, 60):
            allowed["sleepFadeSeconds"] = body["sleepFadeSeconds"]
        if body.get("sleepExtendMinutes") in (5, 10, 15):
            allowed["sleepExtendMinutes"] = body["sleepExtendMinutes"]
        if body.get("safetyStopHours") in (0, 1, 2, 3):
            allowed["safetyStopHours"] = body["safetyStopHours"]
        # Supervisor đọc thẳng khoá này (power_source.pause_on_battery_enabled) - chỉ nhận đúng True/False.
        if isinstance(body.get("pauseOnBattery"), bool):
            allowed["pauseOnBattery"] = body["pauseOnBattery"]
        # Mặc định của trình tạo sách: chất lượng là một trong ba mức; giọng kể là tên giọng có thật ("" = máy đề xuất).
        if body.get("newBookProfile") in ("fast", "balanced", "high_quality"):
            allowed["newBookProfile"] = body["newBookProfile"]
        if isinstance(body.get("newBookNarrator"), str):
            narrator = body["newBookNarrator"].strip()[:80]
            if not narrator or narrator in {voice["name"] for voice in self.app.voices()}:
                allowed["newBookNarrator"] = narrator
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
        path = self.app.voice_file(humanize.voice_key(name))
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
BOOK_ROUTES = (BOOK, LISTEN, r"/media/books/")
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
    ("POST", re.compile(r"/api/sources/split"), Handler.post_source_split),
    ("POST", re.compile(r"/api/first-person"), Handler.post_first_person),
    ("POST", re.compile(r"/api/books"), Handler.post_create),
    ("POST", re.compile(r"/api/books/open"), Handler.post_open),
    ("POST", re.compile(r"/api/dialog/folder"), Handler.post_pick_folder),
    ("POST", re.compile(r"/api/dialog/files"), Handler.post_pick_files),
    ("GET", re.compile(BOOK), Handler.get_book),
    ("GET", re.compile(BOOK + r"/cast"), Handler.get_cast),
    ("GET", re.compile(BOOK + r"/activity"), Handler.get_activity),
    ("GET", re.compile(BOOK + r"/pending-changes"), Handler.get_pending_changes),
    ("POST", re.compile(BOOK + r"/pending-changes/withdraw"), Handler.post_pending_withdraw),
    ("POST", re.compile(BOOK + r"/chapters/(\d+)/retake"), Handler.post_chapter_retake),
    ("POST", re.compile(BOOK + r"/characters/merge"), Handler.post_merge_character),
    ("GET", re.compile(BOOK + r"/chapters/(\d+)/script"), Handler.get_script),
    ("POST", re.compile(BOOK + r"/start"), Handler.post_start),
    ("POST", re.compile(BOOK + r"/stop"), Handler.post_stop),
    ("POST", re.compile(BOOK + r"/pause"), Handler.post_pause),
    ("POST", re.compile(BOOK + r"/reveal"), Handler.post_reveal),
    # Chỉ trên máy này: Studio từ xa (remote_studio.ALLOWED) không có hai đường này.
    ("PUT", re.compile(BOOK + r"/title"), Handler.put_title),
    ("DELETE", re.compile(BOOK), Handler.delete_book),
    ("POST", re.compile(BOOK + r"/export"), Handler.post_export),
    ("GET", re.compile(BOOK + r"/review"), Handler.get_review),
    ("GET", re.compile(BOOK + r"/work"), Handler.get_work),
    ("GET", re.compile(BOOK + r"/casting"), Handler.get_casting),
    ("GET", re.compile(BOOK + r"/continuation"), Handler.get_continuation),
    ("GET", re.compile(BOOK + r"/redo"), Handler.get_redo),
    ("GET", re.compile(BOOK + r"/music"), Handler.get_music),
    ("PUT", re.compile(BOOK + r"/music"), Handler.put_music),
    ("POST", re.compile(BOOK + r"/music/rebuild"), Handler.post_music_rebuild),
    ("GET", re.compile(BOOK + r"/music/chapters/(\d+)"), Handler.get_music_cues),
    ("GET", re.compile(r"/api/music/track"), Handler.get_music_track),
    ("GET", re.compile(BOOK + r"/parts"), Handler.get_parts),
    ("GET", re.compile(BOOK + r"/pronunciations"), Handler.get_name_readings),
    ("GET", re.compile(BOOK + r"/casting/(\d+)"), Handler.get_casting_chapter),
    ("POST", re.compile(BOOK + r"/review"), Handler.post_review),
    ("POST", re.compile(BOOK + r"/pronunciation"), Handler.post_pronunciation),
    ("GET", re.compile(BOOK + r"/shared-readings"), Handler.get_book_shared_readings),
    ("POST", re.compile(BOOK + r"/shared-readings"), Handler.post_book_shared_readings),
    ("GET", re.compile(r"/api/readings"), Handler.get_shared_readings),
    ("GET", re.compile(r"/api/analysis-models"), Handler.get_analysis_models),
    ("POST", re.compile(r"/api/readings"), Handler.post_shared_readings),
    ("POST", re.compile(BOOK + r"/bookfile"), Handler.post_bookfile),
    ("POST", re.compile(BOOK + r"/projectfile"), Handler.post_projectfile),
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
    ("POST", re.compile(r"/api/player/report"), Handler.post_player_report),
    ("POST", re.compile(r"/api/remote/([0-9a-f]{12})"), Handler.post_remote),
    ("POST", re.compile(r"/api/cast/scan"), Handler.post_cast_scan),
    ("DELETE", re.compile(r"/api/sync/pairing"), Handler.delete_sync_pairing),
    ("DELETE", re.compile(r"/api/sync/devices/([0-9a-f]+)"), Handler.delete_sync_device),
    ("POST", re.compile(r"/api/sync/devices/([0-9a-f]+)/studio"), Handler.post_sync_device_studio),
    ("GET", re.compile(r"/api/computers"), Handler.get_computers),
    ("POST", re.compile(r"/api/computers"), Handler.post_computers),
    ("POST", re.compile(r"/api/computers/refresh"), Handler.post_computers_refresh),
    ("GET", re.compile(r"/api/computers/discover"), Handler.get_computers_discover),
    ("DELETE", re.compile(r"/api/computers/([0-9a-f]{12})"), Handler.delete_computer),
    ("GET", re.compile(r"/api/listen/library"), Handler.get_listen_library),
    ("POST", re.compile(r"/api/listen/open-book-file"), Handler.post_open_book_file),
    ("GET", re.compile(LISTEN), Handler.get_listen_book),
    # Chỉ trên máy này (remote_studio không có): bỏ một cuốn nhập từ file .abook khỏi thư viện.
    ("DELETE", re.compile(LISTEN), Handler.delete_listen_book),
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

