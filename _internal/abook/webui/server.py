"""Server HTTP cục bộ cho giao diện: JSON API + audio (có Range để tua) + frontend đã build.

Chỉ nghe trên 127.0.0.1. Mọi `/api` và `/media` cần mã phiên (header `X-Ebook-Token` hoặc `?t=`), và `Host`
phải là chính server - không thì một trang web bất kỳ trong trình duyệt của người dùng gọi được
`127.0.0.1:<cổng>` (hoặc qua DNS rebinding) để đọc sách hay bấm "Bắt đầu" thay họ.
"""
from __future__ import annotations

import base64
import binascii
import contextlib
import hashlib
import json
import mimetypes
import os
import re
import secrets
import shutil
import socket
import sqlite3
import tempfile
import threading
import time
import urllib.error
import urllib.request
from contextlib import closing
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Protocol
from urllib.parse import parse_qs, quote, unquote, urlsplit

from .. import aliases, bracket_rule, continuation, importers, listener_overrides
from ..io_utils import atomic_write_json
from ..readaloud import azure as readaloud_azure
from ..readaloud import keys as readaloud_keys
from ..readaloud import service as readaloud
from ..readaloud.model import VoiceError
from ..voice_catalog import engine_voice
from . import (actions, book_edits, book_wishes, bookfile, cover_search, covers, edits_inbox, export_jobs, export_leftovers, ffmpeg_setup, humanize, listen_view,
               listen_export, music_catalog, music_local, music_module, music_moods, music_plan, music_playlist, music_scene_student, music_select, music_student, music_valence, packages, project_views,
               projectfile, reading_preview, remote_config, shared_readings, store, supertonic_module, textbook, trash_pending, vieneu_module, volumes, word_timing, workshop, zerotts_module)
from .fingerprints import Fingerprints
from .library import Library, Preferences, book_id, clean_book_templates, legacy_ids
from .listening import RECORD_ID, Listening
from . import bluetooth, precast, remote_books, spelling, tls
from .. import names as renames
from .remote_studio import REMOTE_HEADER, StudioGate
from .reviews import Reviews, review_view
from .casting_review import casting_chapter, casting_chapters, casting_stamp
from .name_readings import name_readings, reading_reach
from .voice_picker import cancel_engine_module, engine_installed, engine_module_status, preview_file, start_engine_module, voice_choices
from . import narrator_cards
from .work_items import open_count, work_items
from .cast import CastError, CastPlayers
from .cast import search as cast_search
from .gcast import discover as gcast_discover
from .peer_players import PeerPlayers
from .sync import (LOCAL_PLAYER, SYNC_PORT, Devices, ExclusiveHTTPServer, Remote, SyncApp, SyncServer, away_addresses,
                   local_addresses, remote_command)

STATIC_DIR = Path(__file__).resolve().parent / "static"
MISSING_UI_PAGE = (
    "<!doctype html><html lang='vi'><meta charset='utf-8'><title>ABook</title>"
    "<body style='font-family:system-ui,sans-serif;background:#0e1115;color:#e8eaed;padding:48px;line-height:1.6'>"
    "<h1 style='font-size:22px'>Chưa dựng giao diện của ABook</h1>"
    "<p>Chạy <code>npm run build</code> trong thư mục <code>_internal\\ui</code> rồi mở lại ABook.</p>"
    "<p>Trong lúc chờ, giao diện cũ vẫn mở được: <code>app.py --classic</code>.</p></body></html>"
)
CHUNK = 256 * 1024
MUSIC_UNAVAILABLE_SECONDS = 24 * 3600  # bài tải hỏng (nguồn gỡ, 404...) nghỉ 24 giờ rồi thử lại
MUSIC_OFFLINE_SECONDS = 300            # tải hỏng vì mạng: cả máy coi như offline 5 phút
MY_MUSIC_IMPORT_LIMIT = 500             # số file tối đa trong một lượt nhập "Nhạc của tôi"
MUSIC_WARM_ROUNDS = 3                  # tải sẵn rồi chọn lại bài thay cho bài hỏng: tối đa 3 vòng
# Bài nhạc nền lớn hơn thế (bản dài 30-50 phút, có bài 110 MB) máy này coi như không dùng được: rãnh nhạc chọn bài khác, không
# tải (soát UX a23: tải trước cả cuốn mất 190 MB). Cỡ lấy từ danh mục (`bytes`), không có thì Content-Length / số byte đếm được.
MUSIC_TRACK_MAX_MB = 40
MUSIC_TRACK_MAX_BYTES = MUSIC_TRACK_MAX_MB * 1024 * 1024
TOO_BIG_TRACK = f"Bài nhạc này quá lớn (trên {MUSIC_TRACK_MAX_MB} MB) nên máy này không dùng - máy chọn bài khác"
MAX_BODY = 1024 * 1024
REFRESH_PATIENCE_SECONDS = 8  # "Hỏi lại thư viện": máy thức trả lời trong ngần này; máy đang ngủ thì chờ tiếp ở nền
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
    ".webmanifest": "application/manifest+json",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
}


class Dialogs(Protocol):
    def pick_folder(self, title: str, start: str) -> str | None: ...
    def pick_files(self, title: str, start: str, kind: str = "chapters") -> list[str]: ...
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

UNNAMED_PROBLEM = ("Sách này chưa có nhóm “vai phụ không tên” để đưa câu vào. Chọn một người cụ thể, hay bấm “Người khác…” để đặt tên"
                   " cho vai này (vd “lính gác”) - vai ấy sẽ có giọng riêng.")


# Người gác mốc "Duyệt trước khi thu" (App._precast_tick): từ mốc phân tích xong tới lúc thu xong chương đầu là vài phút.
PRECAST_POLL_SECONDS = 10.0
# Cuốn bật "Chờ tôi duyệt": supervisor giữ trong nhịp kiểm nguồn điện (5 giây) - chờ ngần này trước khi báo dù chưa thấy giữ.
PRECAST_HOLD_GRACE_SECONDS = 30.0


def _desktop_toast(title: str, message: str) -> None:
    """Thông báo Windows (notifier.py, như lúc dây chuyền tự dừng) trên luồng riêng: hiện toast mất tới vài giây."""
    from ..notifier import WindowsNotifier

    threading.Thread(target=lambda: WindowsNotifier().notify(title, message), name="precast-toast", daemon=True).start()


class ApiError(Exception):
    """`extra`: trường gửi kèm lời báo lỗi để giao diện làm được gì đó với nó (`suggestion` của một cách đọc bị từ chối)."""

    def __init__(self, status: int, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.extra = extra


def _needs_download(preset: str) -> bool:
    """Giọng của máy đọc khác mà máy này chưa tải (mô-đun tải thêm): chưa chọn, chưa nghe thử được."""
    other_engine = engine_voice(preset) if preset else None
    return other_engine is not None and not engine_installed(str(other_engine["engine"]))


def _held_record(body: dict[str, Any]) -> str | None:
    """Hồ sơ nghe mà trình phát đang phát (nó ghi vào đúng hồ sơ ấy, xem `Listening._held`); không có thì None."""
    record = body.get("record")
    return record if isinstance(record, str) and RECORD_ID.fullmatch(record) else None


def index_part(chain: list[Path], project: Path) -> int:
    """Số phần của `project` trong chuỗi (phần đầu = 1)."""
    return chain.index(project) + 1


def _cast_discovery() -> bool:
    return os.environ.get("ABOOK_CAST_DISCOVERY") != "0"


class MirrorMismatch(OSError):
    """Bản sao dự phòng của bài nhạc không khớp bản gốc (sha1 / số byte) - không phải lỗi mạng."""


class TrackTooBig(OSError):
    """Bài nhạc lớn hơn MUSIC_TRACK_MAX_MB (Content-Length hay số byte đã đếm) - dừng tải, không phải lỗi mạng."""

    def __init__(self, size: int) -> None:
        super().__init__(f"bài nhạc {size} byte, quá {MUSIC_TRACK_MAX_MB} MB")
        self.size = size



def broken_reason(error: Exception) -> str:
    """Vì sao một dự án không mở được, bằng lời người dùng hiểu: sổ làm việc (SQLite) của sách hỏng hay do bản app khác ghi - không để lộ
    tên cột / lỗi kỹ thuật. Lỗi khác giữ nguyên câu của nó."""
    if isinstance(error, sqlite3.DatabaseError):
        return "sổ làm việc của sách này bị hỏng hoặc do một bản ABook khác ghi, nên chưa mở được"
    return str(error)


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
        # Chỗ chờ "Hoàn tác" trước Thùng rác (trash_pending.py): xoá sách / dự án đổi tên vào `<thư viện>/.trash-pending`, hết hạn mới vào Thùng rác.
        self.trash = trash_pending.TrashPending()
        self._trash_sweeper = trash_pending.SweepTimer(self.sweep_trash)
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
        # "Nhạc của tôi" (music_local.py): nhạc người dùng tự nhập, của riêng máy này; file bài sách mang theo nằm trong files/.
        self.my_music = music_local.LocalMusic(self.music_dir / "mine", self.music_dir / "files")
        # Mô-đun "Phân tích nhạc" (music_module.py): ffmpeg + thư viện + model, người dùng bấm mới tải (không bao giờ tự tải). Thư viện đã tải
        # lần trước vào sys.path TRƯỚC khi cắm bộ phân tích; không thì bài nhập ở "chưa phân tích" và nhập vẫn chạy (thẻ đọc bằng tinytag).
        ffmpeg_setup.configure(self.music_dir.parent / ffmpeg_setup.FOLDER)
        music_module.configure(self.music_dir, after_install=self._music_module_installed,
                               studio_installed=lambda: self.studio is not None and bool(self.studio.installed()))
        music_student.configure(self.music_dir / music_student.PACKAGE_FOLDER)
        music_student.register()
        music_scene_student.configure(self.music_dir / music_scene_student.PACKAGE_FOLDER)  # học sinh hình không khí trong chương: tuỳ chọn, chưa phát hành
        # "Đo cảm xúc nhạc chính xác hơn" (music_valence.py): tuỳ chọn, mặc định tắt; bật rồi thì mở app là làm tiếp các bài chưa đo (không hại nếu đã xong).
        music_valence.configure(self.my_music, lambda: bool(self.preferences.get().get("preciseMusicMood")),
                                lambda value: self.preferences.update({"preciseMusicMood": value}))
        music_valence.kick()
        self._music_catalog: music_catalog.MusicCatalog | None = None
        self._music_lock = threading.Lock()
        # Danh sách phát máy tự chọn cho sách chỉ có chữ, đệm theo (mã sách, nguồn luật, version của luật) - music_playlist.pick.
        self._playlist_auto: dict[tuple[str, str, int], str | None] = {}
        # "Tính lại cảm xúc nhạc" (music_moods.py): việc nền theo từng cuốn {đường dẫn: {running, error}}.
        self._moods_jobs: dict[str, dict[str, Any]] = {}
        self._moods_lock = threading.Lock()
        self._music_fetching: dict[str, threading.Lock] = {}  # mỗi bài một khoá: luồng tải sẵn và trình phát không ghi đè nhau
        # Bài nào dùng được là chuyện của TỪNG MÁY (bộ đệm + mạng của máy này): sổ bài tải hỏng và cửa sổ "đang offline".
        self._music_clock: Callable[[], float] = time.time
        self._music_unavailable = self._read_unavailable()
        self._music_too_big = self._read_unavailable("too_big.json")  # {link: số byte}: bài quá MUSIC_TRACK_MAX_MB, không tải
        self._music_offline_until = 0.0
        if not read_only:
            self._adopt_new_book_ids()
            self._sweep_trash_at_start()
        # Thư mục đã xuất trong phiên này - chỉ những thư mục này được mở bằng "Mở thư mục" sau khi xuất.
        self.exports: set[str] = set()
        # Xuất .abook / .abookproj có nhạc nền chưa tải thì tải ngầm vài phút: tiến độ + Huỷ theo từng cuốn (`music_exporting`).
        self._music_exports: dict[str, dict[str, Any]] = {}
        self._music_exports_lock = threading.Lock()
        # "Xuất file sách" chạy nền, mỗi cuốn nhớ lần xuất gần nhất (export_jobs.py) - tải lại trang vẫn thấy tiến độ / kết quả.
        self.bookfile_jobs = export_jobs.BookFileJobs()
        # "Xuất M4B" cũng chạy nền, bản ghi riêng: đang đóng gói file sách vẫn xuất M4B được và ngược lại.
        self.m4b_jobs = export_jobs.BookFileJobs()
        # "Xuất sách nói" của sách Nghe ngay (listen_export.py): bản ghi riêng có tiến độ + huỷ; chương đã ghép dở nằm trong `export_work` để làm tiếp.
        self.listen_exports = export_jobs.BookFileJobs()
        # "Xuất cả dự án (.abookproj)" cũng chạy nền, có tiến độ (pha + đã/tổng) và Huỷ; đóng app thì huỷ gọn (`close`).
        self.projectfile_jobs = export_jobs.BookFileJobs()
        # Đóng app lúc đang gói dự án quá vài giây (hay máy tắt đột ngột) để lại file `.part` / thư mục tạm: nhớ nơi đã xuất, lần mở sau dọn.
        self.export_folders = export_leftovers.ExportFolders(preferences.path.with_name("export-folders.json"))
        if not read_only:
            self._sweep_export_leftovers_at_start()
        self.export_work_dir = preferences.path.with_name(listen_export.WORK_FOLDER)
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
        # Loa / TV trong mạng nhà (DLNA - webui/cast.py, Google Cast - webui/gcast.py): hiện trong danh sách máy như điện
        # thoại, máy này phục vụ audio. ABOOK_CAST_DISCOVERY=0 tắt việc tìm cả hai (bài thử - tests/conftest.py - không gửi
        # multicast ra mạng người chạy).
        self.cast = CastPlayers(self._cast_book, self._cast_audio, self._cast_save, cover=self._cast_cover,
                                find=lambda: cast_search() if _cast_discovery() else [],
                                find_google=lambda: gcast_discover() if _cast_discovery() else [])
        self._remote_refreshed = 0.0
        self._remote_lock = threading.Lock()
        self._state_synced: dict[str, float] = {}
        # "Tải về máy" cho sách "Trên máy khác"; phần sửa các cuốn của máy tính khác tự gửi về máy ấy sau `edits_send_delay` giây
        # kể từ lần sửa cuối (như điện thoại - EditsSync.kt), và mỗi lần làm mới thư viện. None: chỉ gửi khi bấm (bài thử).
        self.remote_downloads = remote_books.Downloads()
        self.edits_send_delay: float | None = 4.0
        self._edits_timers: dict[str, threading.Timer] = {}
        # App Windows đóng gói (webui/host.py): vỏ Tauri báo có bản mới (`update`), nhận lệnh cài qua `shell`; Studio
        # (thư viện + model làm sách) tải thêm khi cần (`studio`, webui/studio_setup.py). Bản dev: cả ba là None.
        self.update: dict[str, Any] | None = None
        self.shell: Callable[[dict[str, Any]], None] | None = None
        self.studio: Any = None
        # "Nghe ngay" (abook/readaloud): giọng máy đọc chương chỉ-có-chữ; clip đã đọc nằm trong bộ đệm dưới thư mục dữ liệu của app.
        # Giọng trực tuyến dùng khoá của người dùng (readaloud/byok.py): khoá nằm trong file riêng cạnh file tuỳ chọn, giao diện chỉ thấy bản che.
        # Giọng VieNeu (vieneu_module.py): mô-đun tải khi người dùng bấm; tải rồi thì giọng của nó vào danh sách, tải xong tự đo vài giây.
        self.readaloud = readaloud.ReadAloud(preferences.path.with_name("readaloud-cache"),
                                             keys=readaloud_keys.KeyStore(preferences.path.with_name(readaloud_keys.FILE_NAME)),
                                             vieneu_locate=vieneu_module.installed, supertonic_locate=supertonic_module.installed, vieneu_engines=vieneu_module.make_engine,
                                             rtf=lambda voice: supertonic_module.rtf(voice) or vieneu_module.rtf(voice))
        vieneu_module.configure(preferences.path.with_name(vieneu_module.FOLDER), benchmark=self.readaloud.vieneu.benchmark,
                                after_install=self.readaloud.vieneu.forget)
        # Giọng Supertonic (supertonic_module.py): cùng khung với VieNeu, mười giọng nam nữ, gỡ được.
        supertonic_module.configure(preferences.path.with_name(supertonic_module.FOLDER), benchmark=self.readaloud.supertonic.benchmark,
                                    after_install=self.readaloud.supertonic.forget)
        # Giọng ZeroTTS (zerotts_module.py): máy đọc khác cho Studio, người nghe chọn tay ở "Đổi giọng"; tải khi bấm.
        zerotts_module.configure(preferences.path.with_name(zerotts_module.FOLDER))
        if not (isinstance(runner, actions.FakeRunner) or os.environ.get("ABOOK_FAKE_RUNNER") == "1"):
            self.readaloud.warm()
        # Mốc từng chữ khi nghe (word_timing.py): app đóng gói không có numpy nên giao việc căn cho Python của Studio.
        word_timing.configure(lambda: self.studio)
        self.word_jobs = word_timing.Job()
        # "Nghe thử" một cách đọc tên trước khi lưu (reading_preview.py): một tiến trình giọng dùng chung, tắt trước khi cuốn nào chạy.
        self.previews = reading_preview.ReadingPreviews(
            preferences.path.with_name("reading-previews"), studio=lambda: self.studio, fake=self._fake_engine,
            busy=self.busy_book)
        # "Duyệt trước khi thu" (precast.py): người gác mốc phân tích xong sống khi có cuốn đang chạy; báo ra màn hình Windows
        # (giọng giả / bài thử: không báo gì).
        self._precast_lock = threading.RLock()
        self._precast_thread: threading.Thread | None = None
        self._precast_seen: dict[str, float] = {}  # lúc người gác thấy mốc lần đầu, theo cuốn (chờ supervisor giữ)
        self.notify_desktop: Callable[[str, str], None] = (
            (lambda _title, _message: None) if self._fake_engine() or read_only else _desktop_toast)

    def _fake_engine(self) -> bool:
        """Dựng giao diện / bài thử: runner giả thì "nghe thử" cũng dùng giọng giả (không đòi Studio hay card đồ hoạ)."""
        return isinstance(self.runner, actions.FakeRunner) or os.environ.get("ABOOK_FAKE_RUNNER") == "1"

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

    def export_job_status(self, jobs: Any, value: str) -> dict[str, Any]:
        """Việc xuất chạy nền của một cuốn. Cuốn không phải dự án (mở từ file, hay của máy khác) không bao giờ có lượt xuất: trả "idle" thay vì
        404 - trang sách của chúng hỏi trạng thái này và không có gì để báo lỗi."""
        path = self.library.resolve(value)
        if path is None:
            self._listenable(value)  # không có cuốn này thật thì vẫn 404
            return {"state": "idle"}
        return jobs.status(str(path))

    def running_exports(self) -> dict[str, list[dict[str, Any]]]:
        """Việc xuất đang chạy theo từng kiểu ("bookfile" | "m4b" | "audiobook" | "projectfile"): mỗi việc là trạng thái của `export_job_status` kèm `bookId`. Giao diện vừa
        mở (hay tải lại ở trang không phải trang sách) hỏi để hiện lại thông báo tiến độ - trước đây chỉ trang sách của cuốn đang xuất mới hỏi."""
        kinds = {"bookfile": self.bookfile_jobs, "m4b": self.m4b_jobs, "audiobook": self.listen_exports, "projectfile": self.projectfile_jobs}
        return {kind: [{"bookId": book_id(Path(key)), **status} for key, status in jobs.running()] for kind, jobs in kinds.items()}

    def _listenable(self, value: str) -> Path:
        """Phía Nghe: dự án hoặc cuốn mở từ file `.abook` (webui/packages.py). Studio vẫn chỉ dùng `_book`."""
        path = self.library.resolve_listenable(value)
        if path is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Không tìm thấy sách này trong thư viện")
        return path

    def _editable(self, value: str) -> Path:
        """Sách người dùng sửa được ("áp ngay", docs/EDITING.md): dự án có xưởng, cuốn nhập từ file `.abook` (lớp sửa
        `book_edits`), hay cuốn của máy tính khác (lớp sửa, gửi về máy ấy - hẹn gửi ngay ở đây). Cuốn của điện thoại chia sẻ thư
        viện thì không - sửa ở điện thoại ấy."""
        path = self._listenable(value)
        if packages.is_package(path) and remote_books.remote_of(packages.manifest(path)) is not None:
            if not remote_books.sends_edits(packages.manifest(path)):
                raise ApiError(HTTPStatus.CONFLICT, "Sách này lấy từ máy tính khác - muốn sửa thì sửa ở máy ấy")
            self._schedule_send_edits(value)
        return path

    def capabilities(self, path: Path | None = None) -> dict[str, bool]:
        """Máy này làm được gì với cuốn `path` (ui/src/shared/capabilities.ts): `toolchain` - Studio dùng được trên máy này
        (bản dev: luôn có; bản đóng gói: đã cài và không cũ); `workshop` - cuốn có dự án sản xuất ở đây; `link` - cuốn lấy từ
        thiết bị khác mà không sửa được ở đây (điện thoại chia sẻ thư viện); `sync` - cuốn của máy tính khác: sửa được ở đây,
        phần sửa gửi về máy ấy (như điện thoại với máy tính). Không có `path`: chỉ `toolchain` có nghĩa."""
        studio = self.studio
        toolchain = studio is None or bool(studio.installed() and not studio.outdated())
        workshop = path is not None and store.is_project(path)
        remote = (path is not None and not workshop and packages.is_package(path)
                  and remote_books.remote_of(packages.manifest(path)) is not None)
        sync = remote and remote_books.sends_edits(packages.manifest(path))
        return {"toolchain": toolchain, "workshop": workshop, "link": remote and not sync, "sync": sync}

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
        report: dict[str, Any] = {}
        try:
            target, how = packages.import_file(Path(path), self.library.root, self.library.projects(), self.fingerprints,
                                               report)
        except bookfile.BookFileError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error
        except OSError as error:  # ổ đầy giữa chừng, thư viện không ghi được: nói thật thay vì "lỗi máy chủ"
            raise ApiError(HTTPStatus.INSUFFICIENT_STORAGE, f"Không ghi được sách vào thư viện ({error.strerror or error}).") from error
        result: dict[str, Any] = {"id": book_id(target), "how": how}
        if report.get("edits"):
            # File mang theo thay đổi của người nghe: cuốn của máy này thì chờ người dùng quyết áp vào dự án (`edits` =
            # số thay đổi, giao diện hiện thông báo có nút); cuốn nhập thì phần sửa đã được hợp vào máy (`merge`).
            result["edits"] = report["edits"]
        if report.get("merge"):
            result["merge"] = report["merge"]
        return result

    def _book_source(self, path: str) -> Path:
        """File sách (EPUB / DOCX / PDF / TXT) hay thư mục TXT người dùng chọn để thêm vào thư viện."""
        cleaned = str(path).strip().strip('"').strip("'").strip()
        source = Path(cleaned).expanduser()
        if not cleaned or not source.exists():
            raise ApiError(HTTPStatus.NOT_FOUND, "Không thấy file hay thư mục này - có thể nó đã bị chuyển hay xoá.")
        return source

    def preview_text_book(self, path: str, split_chapters: bool = False, footnotes: Any = None) -> dict[str, Any]:
        """"Thêm sách từ file…", bước xem trước: đọc file sách bằng `importers.import_text` và trả danh sách chương + gợi ý. Chưa
        ghi gì vào thư viện. `split_chapters`: người dùng tích "Tách thành N chương" cho file TXT cả truyện. `footnotes`: đề xuất về chú thích
        người dùng đã tích (`importers.footnote_choice_from_json`)."""
        source = self._book_source(path)
        try:
            book = importers.import_text(source, split_chapters=split_chapters, keep_short=True,
                                         footnotes=importers.footnote_choice_from_json(footnotes))
            # Đúng bộ chữ này đã có trong thư viện: hỏi ngay ở đây ("Mở cuốn đó" / "Thêm bản riêng"), đừng để người dùng sửa tên
            # rồi mới biết lúc thêm.
            existing = textbook.find_existing(book, self.library.root)
            # Cũng đúng FILE này đã được thêm (chọn chương khác, tách hay không tách): nói ngay, đừng để thành cuốn trùng tên không ai báo.
            same = textbook.find_same_source(textbook.source_digest(source), self.library.root)
            return {**textbook.preview(book), "existing": self._existing_view(existing) if existing else None,
                    "sameSource": {**self._existing_view(same), "chapters": int(packages.manifest(same).get("chaptersTotal") or 0)} if same else None}
        except importers.ImportFailed as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error
        except OSError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, f"Không đọc được file này ({error.strerror or error}).") from error

    def _existing_view(self, folder: Path) -> dict[str, Any]:
        """Cuốn đã có trong thư viện, như bước xem trước cần: mã và tên đang hiện (kể cả tên người nghe đã đặt)."""
        title = book_edits.load(folder).get("title") or packages.manifest(folder).get("title") or folder.name
        return {"id": book_id(folder), "title": str(title)}

    def add_text_book(self, path: str, title: str = "", separate: bool = False, split_chapters: bool = False,
                      chapters: Any = None, footnotes: Any = None) -> dict[str, Any]:
        """"Thêm sách từ file…": nhập thành sách CHỈ-CÓ-CHỮ trong thư viện (textbook.py) - đọc được ngay, chưa có audio. Nhập lại
        đúng file ấy thì về cuốn đã có (`how`: "new" / "existing"), trừ khi người dùng chọn "Thêm bản riêng" (`separate`). `split_chapters`: như bước xem trước.
        `chapters`: các chương người dùng tích ở bước xem trước, kèm tên mới (`textbook.picks_from_json`); không có thì các chương mặc định.
        `footnotes`: đề xuất về chú thích đã tích, như lúc xem trước."""
        self._mutating()
        source = self._book_source(path)
        try:
            folder, how, book = textbook.add_to_library(source, title, self.library.root, self.library.projects(), self.fingerprints,
                                                        separate=separate, split_chapters=split_chapters,
                                                        picks=textbook.picks_from_json(chapters),
                                                        footnotes=importers.footnote_choice_from_json(footnotes))
        except (importers.ImportFailed, bookfile.BookFileError) as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error
        except OSError as error:
            raise ApiError(HTTPStatus.INSUFFICIENT_STORAGE, f"Không ghi được sách vào thư viện ({error.strerror or error}).") from error
        return {"id": book_id(folder), "how": how, "chapters": len(book.chapters)}

    def open_project_file(self, path: Path) -> dict[str, Any]:
        """Mở một file `.abookproj` (projectfile.py). Máy có Studio và file mang xưởng: dự án này đã có ở đây thì KHÔNG tạo bản
        trùng (phần sửa trong file được cất chờ người dùng đồng ý áp), chưa có thì giải nén thành dự án MỚI và mở ở Studio.
        Còn lại - file chỉ có phần nghe ("chờ dựng xưởng"), hay máy chưa cài Studio - nhập như một cuốn sách để nghe (và sửa
        lớp sửa), giữ nguyên xưởng trong thư mục để lưu lại được."""
        try:
            with projectfile.ProjectFile(path) as opened:
                if opened.workshop == projectfile.PRESENT and self.capabilities()["toolchain"]:
                    return self._open_workshop(opened)
                report: dict[str, Any] = {}
                target, how = packages.import_opened(opened, self.library.root, self.library.projects(), self.fingerprints,
                                                     report)
        except (projectfile.ProjectFileError, bookfile.BookFileError) as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error
        except OSError as error:
            raise ApiError(HTTPStatus.INSUFFICIENT_STORAGE, f"Không ghi được sách vào thư viện ({error.strerror or error}).") from error
        result: dict[str, Any] = {"id": book_id(target), "how": how}
        if report.get("edits"):
            result["edits"] = report["edits"]
        if report.get("merge"):
            result["merge"] = report["merge"]
        return result

    def _open_workshop(self, opened: projectfile.ProjectFile) -> dict[str, Any]:
        """File dự án có xưởng, máy có Studio. Cùng dự án đã có ở đây (mọi chương của file đều có y hệt trong dự án - file không
        mới hơn dự án) -> mở dự án ấy; file mang chương mà dự án này chưa có thì là bản KHÁC (làm tiếp ở nơi khác), thành dự án
        mới như trước. Phần sửa của người nghe trong file (điện thoại sửa rồi lưu) luôn được cất chờ người dùng quyết."""
        prints = opened.chapter_prints
        edits = book_edits.count(opened.edits)
        same = [project for project in self.library.projects()
                if prints and self.fingerprints.shared_chapters(project, prints) == len(prints)]
        if same:
            project = Path(min(same, key=continuation.part_number))
            if edits:
                book_edits.stash_incoming(project, opened.edits, opened.edits_cover(), opened.copy_member)
            self.library.preferences.add_recent(project)
            return {"id": book_id(project), "how": "project", **({"edits": edits} if edits else {})}
        target, report = opened.open_into(self.library.root)
        missing = len(opened.missing_sources)
        opened.copy_music(self.music_dir / "files")  # nhạc nền đi cùng gói: không phải tải lại
        if edits:
            book_edits.stash_incoming(target, opened.edits, opened.edits_cover(), opened.copy_member)
        self.library.preferences.add_recent(target)
        return {"id": book_id(target), "how": "studio", "missingSources": missing, "outside": report["outside"],
                **({"edits": edits} if edits else {})}

    def summary(self, path: Path) -> dict[str, Any]:
        running = self.runner.running(path)
        result = self.library.summary(path, running=running, starting=self.jobs.starting(path))
        result["startError"] = self.jobs.error(path)
        # Tạm dừng mà tiến trình vẫn sống (power_source): "battery" / "listener". Dây chuyền chỉ đứng ở checkpoint kế -
        # tới đó sổ vẫn ghi pha đang làm, nên "đang tạm dừng" khác "đã tạm dừng".
        result["paused"] = self.runner.pause_reason(path) if running else None
        result["canPause"] = bool(running and self.runner.can_pause(path))
        result["precast"] = precast.flags(path, result)
        if running:
            self._watch_precast()
        # Phần nối tiếp của "Làm tiếp cuốn này": danh sách Dự án gom theo chuỗi, không theo tên (soát UX 29-09, N10).
        place = continuation.series_of(path)
        result["series"] = {"root": book_id(place[0]), "part": place[1]} if place else None
        # Tập tạo cùng lúc với tập trước ("Tạo nhiều tập"): giọng và cách đọc tên sẽ gieo từ tập trước lúc nó bắt đầu chạy.
        result["seedPending"] = continuation.seed_pending(path)
        if result["paused"]:
            result["statusLabel"] = humanize.pause_label(result["paused"], reached=result.get("status") == "paused")
            result["eta"] = None
        result["cover"] = covers.cover_view(path, result["id"])
        result.pop("position", None)
        with self._queue_lock:
            result["queuePosition"] = self.queue.index(result["id"]) + 1 if result["id"] in self.queue else None
        return result

    def busy_book(self) -> dict[str, Any] | None:
        """Cuốn đang chặn "nghe thử" (cuốn nào đang chạy / khởi động) - tên, mã và pha để lời từ chối nói đúng; None: máy rảnh."""
        path = self._busy_elsewhere()
        if path is None:
            return None
        try:
            summary = self.summary(path)
            return {"title": str(summary["title"]), "bookId": str(summary["id"]), "phase": str(summary["phase"])}
        except Exception:  # noqa: BLE001 - sổ hỏng cũng không được làm mất lời từ chối
            return {"title": path.name, "bookId": book_id(path), "phase": ""}

    def _busy_elsewhere(self, path: Path | None = None) -> Path | None:
        """Cuốn khác `path` đang chạy hay khởi động (không `path`: cuốn nào cũng tính)."""
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
                try:
                    self._launch(path)
                except ApiError as error:
                    # Không chạy được (phần trước chưa phân vai xong): ra khỏi hàng, nói ở trang sách; các phần sau trong hàng
                    # cũng sẽ gặp đúng lỗi này và nói như thế.
                    self.jobs.fail(path, error.message)

    def library_view(self) -> dict[str, Any]:
        books = []
        for path in self.library.projects():
            try:
                books.append(self.summary(path))
            except Exception as exc:  # noqa: BLE001 - một sách hỏng không được làm mất cả thư viện
                books.append({"id": book_id(path), "path": str(path), "title": path.name, "broken": broken_reason(exc)})
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
            self._enqueue(value)
            return self.summary(path)
        with self._queue_lock:
            if value in self.queue:
                self.queue.remove(value)
        self._launch(path)
        return self.summary(path)

    def _enqueue(self, value: str) -> None:
        with self._queue_lock:
            if value not in self.queue:
                self.queue.append(value)
            if self._queue_thread is None:
                self._queue_thread = threading.Thread(target=self._drain_queue, name="production-queue", daemon=True)
                self._queue_thread.start()

    def _queue_successors(self, path: Path) -> None:
        """Các phần sau của "Tạo nhiều tập" còn chờ gieo (continuation.seed_pending) xếp hàng theo thứ tự sau phần vừa chạy,
        trừ phần đã xếp hàng / đang chạy. Hàng đợi chỉ sống cùng app: mở lại app thì không gì tự chạy, nhưng bấm chạy một phần
        là các phần chờ sau nó vào hàng lại."""
        chain = continuation.series_parts(path, self.library.projects())
        here = path.resolve()
        for part in chain[chain.index(here) + 1:] if here in chain else []:
            if continuation.seed_pending(part) and not self.runner.running(part) and not self.jobs.starting(part):
                self._enqueue(book_id(part))

    def _launch(self, path: Path) -> None:
        """Khởi động lượt chạy và ghi mốc (store.mark_run_started) - mốc lấy TRƯỚC khi khởi động: yêu cầu ghi trong lúc
        khởi động vẫn tính là đang chờ. Khởi động chạy nền (jobs.start) nên mốc chỉ ghi khi nó XONG VÀ KHÔNG LỖI: khởi
        động hỏng (chưa cài Studio, thiếu Ollama...) thì không ghi gì, sửa chờ áp vẫn còn nút "Áp dụng".

        Phần nối tiếp tạo cùng lúc với phần trước ("Tạo nhiều tập", continuation.link_pending) gieo ở đây: tới lượt chạy thì
        phần trước đã phân vai xong, và đây vẫn là sau `create` - trước mọi câu phân tích của phần này."""
        self.previews.shutdown()  # model nghe thử giữ VRAM: nhả trước khi cuốn bắt đầu (cả hai đường tới đây: Bắt đầu và hàng đợi)
        try:
            continuation.seed_when_ready(path)
        except continuation.ContinuationError as error:
            raise ApiError(HTTPStatus.CONFLICT, str(error)) from error
        started_at = time.time()

        def mark_when_started() -> None:
            if not self.jobs.error(path):
                store.mark_run_started(path, started_at)

        self.jobs.start(path, on_done=mark_when_started)
        precast.release(path)  # "Thu âm" sau khi tiến trình giữ đã chết: bấm làm tiếp là cho thu, như nút Thu âm lúc đang giữ
        self._queue_successors(path)
        self._watch_precast()

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
        if not paused:
            precast.release(path)  # "Thu âm" ở màn duyệt cũng đi đường này: supervisor đã giữ một lần thì thôi
        # Supervisor đọc yêu cầu ở vòng kế (tới 0,25 giây): trả trạng thái SẼ có, không phải trạng thái vừa đọc.
        result = self.summary(path)
        result["paused"] = "listener" if paused else None
        if paused:
            result["statusLabel"] = humanize.pause_label("listener", reached=result.get("status") == "paused")
            result["eta"] = None
        return result

    # ---- Duyệt trước khi thu (precast.py) ----

    def precast_view(self, value: str) -> dict[str, Any]:
        path = self._book(value)
        return precast.view(path, self.summary(path))

    def set_precast_wait(self, value: str, wait: bool) -> dict[str, Any]:
        """Công tắc "Chờ tôi duyệt trước khi thu" của một cuốn. Bật sau khi đã qua mốc thì không tạm dừng gì - mốc chỉ
        báo một lần; muốn đứng lại lúc ấy thì bấm "Tạm dừng"."""
        self._mutating()
        precast.set_wait(self._book(value), wait)
        return self.precast_view(value)

    def _watch_precast(self) -> None:
        # ABOOK_PRECAST_WATCH=0: bài thử (tests/conftest.py) gọi từng vòng `_precast_tick` - không luồng nền ngủ thay chúng.
        with self._precast_lock:
            if self.read_only or self._precast_thread is not None or os.environ.get("ABOOK_PRECAST_WATCH") == "0":
                return
            self._precast_thread = threading.Thread(target=self._precast_loop, name="precast-watch", daemon=True)
            self._precast_thread.start()

    def _precast_loop(self) -> None:
        while True:
            time.sleep(PRECAST_POLL_SECONDS)
            try:
                running = self._precast_tick()
            except Exception:  # noqa: BLE001 - người gác không bao giờ được làm hỏng app; vòng sau thử lại
                running = 1
            if not running:
                with self._precast_lock:
                    self._precast_thread = None
                return

    def _precast_tick(self, now: float | None = None) -> int:
        """Một vòng của người gác: cuốn đang chạy vừa qua mốc phân tích xong (precast.due) thì BÁO một lần. Giữ lại chờ duyệt
        không phải việc ở đây - supervisor của lượt chạy quyết (background_runner._hold_for_review), sống cả khi app đóng;
        cuốn bật "Chờ tôi duyệt" thì chờ nó giữ (tới PRECAST_HOLD_GRACE_SECONDS) để lời báo nói đúng sách đang chờ hay đang
        thu. Trả về số cuốn đang chạy (0: người gác nghỉ)."""
        now = time.monotonic() if now is None else now
        running = 0
        for path in self.library.projects():
            if not self.runner.running(path):
                continue
            running += 1
            try:
                summary = self.summary(path)
            except Exception:  # noqa: BLE001 - sổ đang ghi dở / sách hỏng: vòng sau
                continue
            with self._precast_lock:
                if not precast.due(path, summary):
                    continue
                record = precast.read(path)
                first = self._precast_seen.setdefault(str(path), now)
                if record["wait"] and record["heldAt"] is None and summary.get("canPause")                         and now - first < PRECAST_HOLD_GRACE_SECONDS:
                    continue
                precast.announce(path)
            held = record["heldAt"] is not None
            self.notify_desktop(
                f"“{summary.get('title') or path.name}” đã phân tích xong",
                "Sách đang chờ duyệt: xem giọng, cách đọc tên và người nói rồi bấm “Thu âm”." if held else
                "Duyệt giọng, cách đọc tên và người nói trước khi thu - sửa bây giờ không phải thu lại.",
            )
        return running

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
        path = self._editable(value)
        cleaned = store.clean_title(title)
        if not cleaned:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Tên sách không được để trống")
        if not store.is_project(path):
            # Cuốn nhập từ file: lớp sửa của người nghe (book_edits), lớp sách giữ nguyên.
            return {"title": book_edits.set_title(path, cleaned)}
        try:
            store.set_display_title(path, cleaned)
        except OSError as error:
            raise ApiError(HTTPStatus.CONFLICT, f"Không ghi được tên mới: {error}") from error
        return self.summary(path)

    def set_author(self, value: str, author: str) -> dict[str, Any]:
        """Đặt lại tác giả của một cuốn nhập từ file (lớp sửa của người nghe, book_edits); tên trống là "không rõ tác giả". Dự án Studio
        không có tác giả để sửa."""
        self._mutating()
        path = self._editable(value)
        if store.is_project(path):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Sách làm trong Studio chưa có mục tác giả")
        return {"author": book_edits.set_author(path, author)}

    def delete(self, value: str, *, undo: bool = False) -> dict[str, Any]:
        """Xoá một dự án: chuyển CẢ thư mục dự án vào Thùng rác (khôi phục được). File truyện gốc người dùng chọn lúc tạo
        nằm ngoài thư mục ấy, không bị đụng tới. Sách đang chạy phải dừng trước; đang xếp hàng thì bỏ khỏi hàng.
        `undo` (nút Xoá của người dùng): thư mục nằm chờ `UNDO_SECONDS` giây để "Hoàn tác" (`undo_trash`) rồi mới vào Thùng rác;
        không thì vào Thùng rác ngay (cuốn cũ bị thay khi "làm lại" - người dùng không thấy gì để hoàn tác)."""
        self._mutating()
        path = self._book(value)
        if self.runner.running(path) or self.jobs.starting(path):
            raise ApiError(HTTPStatus.CONFLICT, "Sách đang chạy - dừng sách rồi mới xoá được")
        resolved = path.resolve()
        if resolved == Path(resolved.anchor) or resolved == self.library.root.resolve() or not store.is_project(resolved):
            raise ApiError(HTTPStatus.CONFLICT, "Thư mục này không phải một dự án sách - không xoá")
        with self._queue_lock:
            queued = value in self.queue
            if queued:
                self.queue.remove(value)
        token = self._discard(
            resolved, "project", undo=undo, queued=queued,
            failure="Không chuyển được vào Thùng rác - có thể một file trong dự án đang mở (đang nghe cuốn này, hay thư mục"
                    " đang mở trong cửa sổ khác). Đóng rồi thử lại. ({error})")
        self.library.forget(path)
        return {"ok": True, "title": path.name, **({"undo": token} if token else {})}

    def _discard(self, folder: Path, kind: str, *, undo: bool, queued: bool, failure: str) -> str | None:
        """Đưa thư mục sách đã xoá ra khỏi thư viện: `undo` thì vào chỗ chờ (trả mã hoàn tác) và hẹn dọn vào Thùng rác lúc hết hạn;
        không (hay thư mục khác ổ với thư viện - đổi tên sẽ là chép) thì vào Thùng rác ngay như trước, trả None. Lỗi: 409 với
        lời `failure` ({error} là chi tiết)."""
        root = self.library.root.resolve()
        try:
            if undo and self.trash.fits(root, folder):
                token = self.trash.hold(root, folder, kind, queued=queued)
                self._schedule_trash_sweep(root)
                return token
            actions.move_to_recycle_bin(folder)
        except actions.RecycleCancelled as error:
            raise ApiError(HTTPStatus.CONFLICT, "Đã thôi xoá - cuốn vẫn ở chỗ cũ.") from error
        except OSError as error:
            raise ApiError(HTTPStatus.CONFLICT, failure.format(error=error)) from error
        return None

    def _schedule_trash_sweep(self, root: Path) -> None:
        """Hẹn dọn chỗ chờ ngay sau hạn "Hoàn tác". Bản dùng giọng giả / bài thử không hẹn (không luồng nào tự đẩy thư mục
        thử vào Thùng rác thật); đóng app thì `close` dọn nốt."""
        if self._fake_run():
            return
        self._trash_sweeper.schedule(root, trash_pending.UNDO_SECONDS + 1)

    def _fake_run(self) -> bool:
        return isinstance(self.runner, actions.FakeRunner) or os.environ.get("ABOOK_FAKE_RUNNER") == "1"

    def sweep_trash(self, root: Path | None = None, *, everything: bool = False, ask: bool = True) -> None:
        """Chuyển vào Thùng rác những cuốn đã xoá quá hạn "Hoàn tác" (`everything`: mọi cuốn, lúc app mở / đóng). Không văng:
        dọn không được thì cuốn còn nằm chờ, lần sau dọn tiếp. Không cho `root`: thư viện hiện tại và cả thư viện cũ còn cuốn
        nằm chờ (đổi thư viện giữa hạn). `ask=False`: không để Windows hiện hộp (lúc đóng app - xem `TrashPending.sweep`)."""
        if self.read_only:
            return
        roots = [root] if root else list(dict.fromkeys([self.library.root.resolve(), *self.trash.roots()]))
        for each in roots:
            try:
                self.trash.sweep(each, everything=everything, ask=ask)
            except Exception:  # noqa: BLE001 - dọn nền; hỏng thì để lần sau
                pass

    def _sweep_trash_at_start(self) -> None:
        """Lúc mở app: cuốn còn nằm chờ từ phiên trước (app chết giữa hạn) vào Thùng rác. Luồng nền - cuốn lớn vào Thùng rác
        mất vài giây, cửa sổ không được chờ. Giọng giả / bài thử không tự dọn (bài thử gọi `sweep_trash` trực tiếp)."""
        if self._fake_run():
            return
        threading.Thread(target=lambda: self.sweep_trash(everything=True), name="trash-sweep", daemon=True).start()

    def _sweep_export_leftovers_at_start(self) -> None:
        """Lúc mở app: dọn file tạm của lượt gói `.abookproj` bị cắt ngang ở phiên trước (`export_leftovers`). Luồng nền - thư mục xuất có thể nằm
        trên ổ mạng chậm. Giọng giả / bài thử không tự dọn (bài thử gọi `sweep_export_leftovers` trực tiếp)."""
        if self._fake_run():
            return
        threading.Thread(target=self.sweep_export_leftovers, name="export-leftovers", daemon=True).start()

    def sweep_export_leftovers(self) -> list[Path]:
        folders = [*self.export_folders.recent(), Path(self.preferences.get()["libraryRoot"]) / "Đã xuất"]
        return export_leftovers.sweep(folders, Path(tempfile.gettempdir()))

    def undo_trash(self, token: str) -> dict[str, Any]:
        """"Hoàn tác" một lần xoá: thư mục về đúng đường gốc, thư viện thấy lại. Hàng chờ KHÔNG được xếp lại - ghi trong lời
        báo (`wasQueued`) để người dùng tự xếp nếu muốn."""
        self._mutating()
        root = self.library.root.resolve()
        try:
            meta = self.trash.restore(self.trash.root_of(token, root), token)  # thư viện lúc xoá, nếu đã đổi giữa hạn
        except trash_pending.NotPending as error:
            raise ApiError(HTTPStatus.NOT_FOUND, "Hết thời gian hoàn tác - cuốn này đã nằm trong Thùng rác của Windows, "
                                                 "khôi phục từ đó được.") from error
        except trash_pending.Occupied as error:
            raise ApiError(HTTPStatus.CONFLICT, "Đã có sách trùng tên ở đó - đổi tên hay dời cuốn kia đi rồi hoàn tác (cuốn vừa "
                                                "xoá vẫn nằm chờ trong ít giây nữa).") from error
        except OSError as error:
            raise ApiError(HTTPStatus.CONFLICT, f"Không khôi phục được - có thể thư mục đích đang mở. ({error})") from error
        path = Path(meta["original"])
        if meta["kind"] == "project" and path.parent.resolve() != root:
            self.preferences.add_recent(path)  # dự án mở từ nơi khác thư viện: hiện lại qua "gần đây"
        return {"ok": True, "title": path.name, "wasQueued": bool(meta.get("queued"))}

    def remove_imported(self, value: str, *, undo: bool = False) -> dict[str, Any]:
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
        token = self._discard(path, "imported", undo=undo, queued=False,
                              failure="Không chuyển được vào Thùng rác - có thể một chương đang mở (đang nghe cuốn này). Thử lại. ({error})")
        return {"ok": True, **({"undo": token} if token else {})}

    def _ollama_base(self) -> str:
        """Địa chỉ Ollama mà dây chuyền gọi: Ollama riêng của Studio (app đóng gói) hay Ollama của máy (chạy từ mã nguồn)."""
        from ..config import build_settings

        if self.studio is not None:
            return str((self.studio.settings_overrides().get("analysis") or {}).get("base_url"))
        return str(build_settings()["analysis"].get("base_url", ""))

    def analysis_models(self) -> dict[str, Any]:
        """Model đọc hiểu truyện chọn được cho MỘT cuốn (trình tạo sách): các model có trong Ollama mà dây chuyền sẽ gọi -
        Ollama riêng của Studio trong app đóng gói, Ollama của máy khi chạy từ mã nguồn - cùng model mặc định của app. Hỏi
        HTTP /api/tags (không gọi CLI `ollama`: khi máy chủ tắt nó tự mở app khay); Ollama tắt thì danh sách rỗng."""
        import urllib.request

        from ..config import build_settings

        analysis = build_settings()["analysis"]
        default = str(analysis.get("model", ""))
        base = self._ollama_base()
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

    def _create_book(self, body: dict[str, Any], paths: list[str], title: str,
                     first_person_chapters: dict[str, str] | None) -> Path:
        """Tạo một dự án từ các lựa chọn của trình tạo sách - dùng chung cho sách thường và từng tập của "Tạo nhiều tập"."""
        root = actions.create_book(
            self.library.root, paths, title, str(body.get("profile", "high_quality")),
            str(body.get("narrator", "")), str(body.get("firstPerson", "")),
            settings_overrides=self._analysis_overrides(str(body.get("analysisModel", "") or "")),
            first_person_chapters=first_person_chapters,
            drop_credit_lines=body["dropCreditLines"] if isinstance(body.get("dropCreditLines"), bool) else None,
        )
        if body.get("precastWait") is True:
            precast.set_wait(root, True)  # "Chờ tôi duyệt trước khi thu" chọn ngay lúc tạo (mỗi tập của "Tạo nhiều tập")
        self.preferences.add_recent(root)
        return root

    def _apply_shared_readings(self, root: Path, paths: list[str]) -> list[str]:
        """Cách đọc dùng chung: mục nào có trong truyện thì sách mới nhận luôn, như người dùng sửa từng tên (trước khi chạy -
        chưa có câu nào phải thu lại)."""
        return shared_readings.apply(root, shared_readings.present(self.shared_readings.entries(),
                                                                   shared_readings.file_texts(paths)))

    def _queue_position(self, root: Path) -> int:
        with self._queue_lock:
            return self.queue.index(book_id(root)) + 1 if book_id(root) in self.queue else 0

    @staticmethod
    def _first_person_chapters(body: dict[str, Any]) -> dict[str, str] | None:
        chapters = body.get("firstPersonChapters")
        return {str(key): str(value) for key, value in chapters.items()} if isinstance(chapters, dict) else None

    def create(self, body: dict[str, Any]) -> dict[str, Any]:
        self._mutating()
        paths = [str(item) for item in body.get("paths", [])]
        try:
            split = volumes.split_paths(paths, body.get("volumeStarts"))
        except ValueError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error
        if len(split) > 1:
            return self._create_volumes(body, split)
        # "Làm tiếp cuốn này": phần mới gieo từ phần trước (continuation.py) - tìm phần trước TRƯỚC khi tạo, để id sai
        # không để lại một dự án mồ côi.
        previous = self._book(str(body["seedFrom"])) if body.get("seedFrom") else None
        # "Sửa thiết lập" của sách chưa bắt đầu: cuốn cũ được thay - kiểm TRƯỚC khi tạo, như phần trước ở trên.
        replaces = str(body.get("replaces") or "")
        replaced = self._book(replaces) if replaces else None
        if replaced is not None and (self.runner.running(replaced) or self.jobs.starting(replaced)
                                     or not store.can_redo(replaced)):
            raise ApiError(HTTPStatus.CONFLICT, "Sách cũ đã bắt đầu chạy và qua bước phân tích - không làm lại được nữa. Tạo sách mới hay dùng "
                                                "“Làm tiếp cuốn này”.")
        kept_covers: dict[str, bytes] = {}
        if replaced is not None and not store.not_started(replaced):
            # "Làm lại phân tích" (bản dở: phân tích bị ngắt): dự án mới cùng tên, cùng thiết lập sẽ MỞ LẠI đúng thư mục cũ
            # (project.create_or_open_project) và chạy tiếp bản dở - chính điều phải tránh. Nên bản dở vào Thùng rác TRƯỚC;
            # không bỏ được thì thôi, chưa tạo gì. Bìa cầm trong bộ nhớ qua lúc ấy.
            for name in (covers.COVER_FILE, covers.META_FILE):
                if (replaced / name).is_file():
                    kept_covers[name] = (replaced / name).read_bytes()
            self.delete(replaces)
            replaced = None
        root = self._create_book(body, paths, str(body.get("title", "")), self._first_person_chapters(body))
        for name, data in kept_covers.items():
            if not (root / name).exists():
                (root / name).write_bytes(data)
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
        shared = self._apply_shared_readings(root, paths)
        if body.get("start"):
            # Qua hàng đợi như nút "Bắt đầu": cuốn đang chạy thì cuốn mới xếp hàng, không tranh GPU (soát 28-09 - trước
            # đây "Tạo + bắt đầu ngay" chạy song song với cuốn đang sản xuất).
            self.start(book_id(root))
        # Đang có cuốn khác chạy thì cuốn mới vào hàng chờ: lời báo nói đúng thế, không "Đang khởi động" (soát UX a6 01-10).
        queued = self._queue_position(root)
        return {"id": book_id(root), "sharedReadings": shared, "queued": queued,
                **({"replaceError": replace_error} if replace_error else {}),
                **({"unchanged": True} if unchanged else {})}

    def _create_volumes(self, body: dict[str, Any], split: list[list[str]]) -> dict[str, Any]:
        """"Tạo nhiều tập" (B7): tập 1 là sách thường (qua `create`: kể cả "Làm tiếp cuốn này" / "Sửa thiết lập" nếu có), các
        tập sau là phần nối tiếp "Tên · Phần N" trong chuỗi continues.json - đúng quy ước của "Làm tiếp cuốn này".

        Các tập sau tạo NGAY (người dùng thấy đủ bộ, đúng thứ tự) nhưng chưa gieo: tập 1 chưa chạy nên chưa có nhân vật hay
        giọng để mang. Chúng ghi cờ "chờ gieo" (continuation.link_pending); `_launch` gieo từ phần trước đúng lúc tập ấy bắt
        đầu chạy - tức sau khi phần trước phân vai xong (hàng đợi chỉ cho chạy khi không cuốn nào khác đang chạy)."""
        title = str(body.get("title", ""))
        chapters = self._first_person_chapters(body)
        sizes = [len(volume) for volume in split]
        offsets = [sum(sizes[:index]) for index in range(len(split))]
        for number, volume in enumerate(split, start=1):
            if volumes.reading_order_problem(volume):
                raise ApiError(HTTPStatus.BAD_REQUEST, f"Tập {number} gồm chương của nhiều thư mục mà tên file xen nhau - dây chuyền "
                                                       "xếp chương theo tên file nên không giữ được thứ tự đọc. Dời chỗ cắt về ranh "
                                                       "giới giữa hai thư mục.")
        first = self.create({**body, "paths": split[0], "volumeStarts": None,
                             "firstPersonChapters": volumes.localize_chapters(chapters, offsets[0], sizes[0]) or {}})
        parts = [{"id": first["id"], "part": 1, "queued": first.get("queued", 0)}]
        made: list[str] = []
        previous = self._book(first["id"])
        try:
            for number, volume in enumerate(split[1:], start=2):
                root = self._create_book(body, volume, continuation.continued_title(title, number),
                                         volumes.localize_chapters(chapters, offsets[number - 1], sizes[number - 1]))
                made.append(book_id(root))
                continuation.link_pending(previous, root)
                self._apply_shared_readings(root, volume)
                previous = root
                if body.get("start"):
                    self._enqueue(book_id(root))  # sau tập trước, đúng thứ tự (tập 1 đang chạy hay đang khởi động)
                parts.append({"id": book_id(root), "part": number, "queued": self._queue_position(root)})
        except (ValueError, continuation.ContinuationError, OSError) as error:
            # Bộ dở dang không dùng được (tập sau nối vào chuỗi nào?): bỏ các tập sau vừa tạo, giữ tập 1 như sách thường.
            for made_id in made:
                try:
                    self.delete(made_id)
                except ApiError:
                    pass
            raise ApiError(HTTPStatus.CONFLICT, f"Đã tạo tập 1 nhưng không tạo được tập {len(parts) + 1}: {error}") from error
        return {**first, "parts": parts}

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
        """Rãnh nhạc của cuốn + lựa chọn của người dùng. Chưa có thì dựng (cần danh mục: lần đầu cần mạng). Cuốn nhập từ
        file: các mốc nhạc người làm sách đã gắn + phần người nghe đã sửa (`book_edits.music_view`), không dựng gì."""
        path = self._listenable(value)
        if packages.is_package(path):
            return self._with_auto_playlist(value, path, book_edits.music_view(packages.manifest(path), book_edits.load(path)))
        plan = music_plan.read_plan(path)
        error = ""
        if plan is None:
            try:
                plan = self.music_rebuild(value)
            except music_catalog.CatalogError as exc:
                error = str(exc)
        return self._music_payload(path, plan, error)

    def _music_payload(self, path: Path, plan: dict[str, Any] | None, error: str) -> dict[str, Any]:
        overrides = music_plan.read_overrides(path)
        with self._moods_lock:
            moods = dict(self._moods_jobs.get(str(path)) or {"running": False, "error": ""})
        return {"plan": plan, "overrides": overrides, "error": error, "taxonomy": self._music_taxonomy(),
                "bannedTracks": self._banned_tracks(overrides["banned"], plan), "moods": moods,
                "download": self.music_export_status(self.music_key(path, "warm"))}

    def _banned_tracks(self, banned: list[str], plan: dict[str, Any] | None) -> dict[str, dict[str, str]]:
        """Tên các bài đã bỏ ("Bài đã bỏ"): {link: {title, creator}} lấy từ danh mục; mất mạng / bài không còn thì bỏ qua
        (giao diện hiện tên file) - không bao giờ làm hỏng cả màn hình."""
        if not banned:
            return {}
        known = dict((plan or {}).get("tracks") or {})
        try:
            known.update(self._music_lookup(banned))
        except (music_catalog.CatalogError, OSError, ValueError):
            pass
        return {link: {key: known[link][key] for key in ("title", "creator")
                       if isinstance(known[link].get(key), str) and known[link][key]}
                for link in banned if isinstance(known.get(link), dict) and known[link].get("title")}

    def _music_taxonomy(self) -> dict[str, Any]:
        """Bảng phong cách / thể loại / tên 13 cảm xúc từ danh mục (đổi được không cần cập nhật app); mất mạng thì rỗng."""
        try:
            catalog = self.music_catalog()
            taxonomy = catalog.manifest().get("taxonomy")
            if not taxonomy:  # bản đệm từ trước khi danh mục có bảng phân loại: đọc lại một lần
                taxonomy = catalog.manifest(refresh=True).get("taxonomy")
            return dict(taxonomy or {})
        except music_catalog.CatalogError:
            return {}

    def _music_candidates(self, valence: float, arousal: float) -> Iterable[dict[str, Any]]:
        """Ứng viên tự động quanh một không khí: bài danh mục + bài "Nhạc của tôi" đã phân tích (chưa phân tích thì không)."""
        yield from self.music_catalog().near(valence, arousal, radius=1)
        yield from self.my_music.near(valence, arousal, radius=1)

    def _music_lookup(self, links: Iterable[str], project_root: Path | None = None) -> dict[str, dict[str, Any]]:
        """Thông tin các bài: danh mục cho link mạng, kho "Nhạc của tôi" cho link `local:`. Bài `local:` mà kho máy này không có
        (sách mở từ file, bài người làm sách tự nhập) thì lấy bản đã ghi trong rãnh nhạc của cuốn - tên bài không mất."""
        links = list(links)
        remote = [link for link in links if not music_plan.is_local(link)]
        found = self.music_catalog().lookup(remote) if remote else {}
        mine = [link for link in links if music_plan.is_local(link)]
        if mine:
            found.update(self.my_music.lookup(mine))
            lost = [link for link in mine if link not in found]
            kept = ((music_plan.read_plan(project_root) or {}).get("tracks") or {}) if project_root is not None and lost else {}
            found.update({link: kept[link] for link in lost if isinstance(kept.get(link), dict)})
        return found

    # ---- "Nhạc của tôi" (music_local.py) ---------------------------------------------------------------------------------
    def my_music_view(self) -> dict[str, Any]:
        """Danh sách bài đã nhập + có bộ phân tích âm thanh chưa (chưa có thì bài mới nhập ở trạng thái "chưa phân tích") + mô-đun "Phân tích
        nhạc" (tải một lần khi người dùng bấm; giao diện hỏi lại view này mỗi giây trong lúc tải). `stale`: số bài phân tích bằng bản model cũ."""
        return {"tracks": self.my_music.entries(), "analyzer": music_local.analyzer_available(),
                "module": music_module.status() | {"stale": self.my_music.stale_count(), "precise": music_valence.status()}}

    def my_music_precise(self, enabled: bool) -> dict[str, Any]:
        """Người dùng bật / tắt "Đo cảm xúc nhạc chính xác hơn": bật thì tải tháp MuQ (1,27 GB) nếu chưa có rồi đo nền các bài đã nhập; máy không đủ sức
        (dưới 8 GB RAM) hay chưa có "Phân tích nhạc" thì báo rõ, không bật."""
        self._mutating()
        if enabled:
            if not music_local.analyzer_available():
                raise ApiError(HTTPStatus.CONFLICT, "Cần tải Phân tích nhạc trước, rồi mới bật được đo cảm xúc chính xác hơn.")
            try:
                music_valence.enable()
            except ValueError as error:
                raise ApiError(HTTPStatus.CONFLICT, str(error)) from error
        else:
            music_valence.disable()
        return self.my_music_view()

    def my_music_module(self, scene: bool = False) -> dict[str, Any]:
        """Người dùng bấm "Phân tích nhạc": tải (hay cập nhật) mô-đun ở luồng nền rồi trả view. Đã đủ thì không làm gì. `scene`: bấm nút
        "Học sinh không khí cảnh" (phần tuỳ chọn, tải cùng cơ chế)."""
        self._mutating()
        if scene and (reason := music_module.scene_student_offered()):
            raise ApiError(HTTPStatus.CONFLICT, f"Chưa tải được bộ này: {reason}.")
        music_module.start(scene=scene)
        return self.my_music_view()

    def my_music_cancel(self, what: str) -> dict[str, Any]:
        """Người dùng bấm "Huỷ" khi đang tải một mô-đun nhạc (`module`: Phân tích nhạc + Học sinh cảnh, `precise`: đo cảm xúc chính xác hơn): dừng
        giữa chừng, `.part` ở lại để lần tải sau làm tiếp. Không có lần tải nào thì không làm gì."""
        self._mutating()
        (music_valence.cancel if what == "precise" else music_module.cancel)()
        return self.my_music_view()

    def _music_module_installed(self) -> None:
        """Sau khi mô-đun tải/cập nhật xong: phân tích nốt bài CHƯA phân tích và đo độ to bù. Bài đã có kết quả của bản cũ KHÔNG bị phân tích
        lại (kết quả cũ vẫn dùng được) - người dùng bấm "Phân tích lại"."""
        try:
            self.my_music.measure_missing()
            self.my_music.analyze_pending()
            music_valence.kick()
        except Exception:  # noqa: BLE001 - việc bù không được làm hỏng mô-đun vừa tải xong
            pass

    def my_music_import(self, paths: list[str]) -> dict[str, Any]:
        """Nhập các file nhạc (đường dẫn trên máy này, từ hộp chọn file). Từng file một: file hỏng không làm hỏng cả lượt - kết
        quả nói rõ file nào đã nhập, file nào đã có sẵn trong kho, file nào không nhập được và vì sao. Không cần mô-đun "Phân tích nhạc":
        chưa có thì bài ở "chưa phân tích" và chưa có độ to đo (mức mặc định)."""
        self._mutating()
        added: list[dict[str, Any]] = []
        existing: list[dict[str, Any]] = []
        failed: list[str] = []
        for raw in paths[:MY_MUSIC_IMPORT_LIMIT]:
            try:
                if not isinstance(raw, str) or not Path(raw).is_absolute():
                    raise music_local.MusicImportError("Đường dẫn file không hợp lệ.")
                track, duplicate = self.my_music.import_file(Path(raw))
            except music_local.MusicImportError as exc:
                failed.append(str(exc))
                continue
            (existing if duplicate else added).append(track)
        if added:
            music_valence.kick()  # số của đầu trò đã ghi rồi; V hợp (nếu người dùng bật) ghi đè sau ở luồng nền
        return {"added": added, "existing": existing, "failed": failed, **self.my_music_view()}

    def my_music_remove(self, digest: str) -> dict[str, Any]:
        self._mutating()
        if not self.my_music.remove(digest):
            raise ApiError(HTTPStatus.NOT_FOUND, "Bài này không còn trong Nhạc của tôi")
        return self.my_music_view()

    def my_music_auto(self, digest: str, auto: str | None) -> dict[str, Any]:
        """Công tắc tự chọn của một bài: "on" (cho máy tự chọn dù có vẻ có lời), "off" (không bao giờ tự chọn), None (mặc định). Chỉ là khoá của bài trên máy này."""
        self._mutating()
        if not self.my_music.set_auto(digest, auto):
            raise ApiError(HTTPStatus.NOT_FOUND, "Bài này không còn trong Nhạc của tôi")
        return self.my_music_view()

    def my_music_analyze(self) -> dict[str, Any]:
        """Phân tích các bài chưa phân tích (khi bộ phân tích đã có); chưa có thì nói rõ, không bịa."""
        self._mutating()
        if not music_local.analyzer_available():
            raise ApiError(HTTPStatus.CONFLICT, "Chưa có bộ phân tích âm thanh - bài nhập vào vẫn ghim tay được, "
                                                "nhưng máy chưa tự chọn chúng.")
        analysed = self.my_music.analyze_pending()
        music_valence.kick()
        return {"analysed": analysed, **self.my_music_view()}

    def my_music_reanalyse(self) -> dict[str, Any]:
        """Người dùng bấm "Phân tích lại N bài bằng bản mới" sau khi cập nhật mô-đun: ở luồng nền, không bao giờ tự chạy."""
        self._mutating()
        if not music_local.analyzer_available():
            raise ApiError(HTTPStatus.CONFLICT, "Chưa có bộ phân tích âm thanh - bài nhập vào vẫn ghim tay được, "
                                                "nhưng máy chưa tự chọn chúng.")
        music_module.run_job(lambda: (self.my_music.reanalyse(), music_valence.kick()))
        return self.my_music_view()

    def my_music_precise_remove(self) -> dict[str, Any]:
        """Người dùng bấm "Xoá file (1,27 GB)" khi đã tắt tuỳ chọn: xoá file MuQ của gói nhạc, giữ nguyên phần còn lại."""
        self._mutating()
        try:
            music_valence.remove_files()
        except ValueError as error:
            raise ApiError(HTTPStatus.CONFLICT, str(error)) from error
        return self.my_music_view()

    def my_music_file(self, digest: str) -> Path:
        """File bài của người dùng cho "Nghe thử" trên máy này (không qua Studio từ xa - đường theo sách lo phần phát)."""
        path = self.my_music.file(music_plan.LOCAL_PREFIX + digest)
        if path is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Không thấy bài này trong Nhạc của tôi")
        return path

    def music_rebuild(self, value: str, *, keep_scenes: bool = False, edited: set[str] | None = None,
                      warm_all: bool = False) -> dict[str, Any]:
        """Dựng lại rãnh nhạc. `keep_scenes`: chọn lại bài trên các đoạn plan hiện có (người dùng sửa một đoạn - không
        chia lại cả cuốn); mặc định chia lại đoạn ("Chọn lại nhạc", lần dựng đầu). `edited` (cần `keep_scenes`): các đoạn
        vừa bị sửa - khác None thì mọi đoạn KHÁC giữ bài cũ (trừ bài đã bị bỏ); None thì chọn lại tất cả. Tải sẵn: dựng cả
        cuốn (hay `warm_all` - vừa bật nhạc) thì mọi bài; sửa vài đoạn thì chỉ bài của đoạn đổi bài (soát UX a23: "Đổi bài"
        một đoạn tải lại cả cuốn)."""
        path = self._book(value)
        # "Chọn lại nhạc" = muốn dữ liệu mới nhất: đọc lại mục lục (nhỏ) thay vì bản đệm 24 giờ. Sửa một đoạn (ghim, im lặng,
        # bỏ bài) thì dùng bản đệm - mỗi lần bấm không chờ mạng.
        manifest = self.music_catalog().manifest(refresh=edited is None)
        previous = music_plan.read_plan(path) if keep_scenes else None
        plan = self._music_build(value, path, manifest, previous, edited)
        scenes: set[str] | None = None
        if edited is not None and not warm_all:
            before = {scene.get("key"): scene.get("link") for scene in (previous or {}).get("scenes") or []}
            scenes = {scene["key"] for scene in plan.get("scenes") or [] if before.get(scene.get("key")) != scene.get("link")}
        self._warm_music(plan, value, scenes)
        return plan

    def _music_build(self, value: str, path: Path, manifest: dict[str, Any], previous: dict[str, Any] | None,
                     edited: set[str] | None) -> dict[str, Any]:
        """Dựng + lưu rãnh nhạc, chỉ chọn bài dùng được TRÊN MÁY NÀY (`music_track_available`)."""
        return music_plan.build(path, self._music_candidates, lambda links: self._music_lookup(links, path),
                                catalog_revision=str(manifest.get("revision") or ""), book_key=value,
                                taxonomy=manifest.get("taxonomy"),
                                scenes=music_plan.scenes_of(previous),
                                keep=music_plan.kept_tracks(previous, edited) if edited is not None else None,
                                kept_siblings=music_plan.kept_siblings(previous, edited) if edited is not None else None,
                                available=self.music_track_available)

    def music_update(self, value: str, body: dict[str, Any]) -> dict[str, Any]:
        """Người dùng sửa (bật/tắt, phong cách, âm lượng, ghim, im lặng, bỏ bài): lưu lựa chọn rồi dựng lại rãnh nhạc.
        Mất mạng thì lựa chọn vẫn được lưu, rãnh nhạc dựng lại lần sau."""
        self._mutating()
        path = self._editable(value)
        if packages.is_package(path):
            extra = set(body) - {"enabled", "levelDb", "silence", "pins", "playlist"}
            if extra:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Sách đã đóng gói chỉ chỉnh được bật/tắt nhạc, mức nhạc, im lặng từng đoạn, đổi bài và danh sách nhạc nền")
            return self._with_auto_playlist(value, path, book_edits.set_music(path, body, self._my_track))
        music_plan.write_overrides(path, body)
        if music_plan.read_plan(path) is None:
            return self.music_view(value)
        # Sửa một đoạn / một bài (ghim, im lặng, bỏ bài, bật/tắt, mức nhạc): các đoạn khác giữ bài cũ - chỉ đoạn vừa sửa
        # và đoạn đang dùng bài vừa bỏ mới chọn lại. Đổi thể loại / phong cách là đổi gu của cả cuốn: chọn lại tất cả.
        retaste = "genre" in body or "family" in body
        edited = None if retaste else {str(key) for part in ("pins", "silence") for key in (body.get(part) or {})}
        return self._music_after_change(value, edited, warm_all=body.get("enabled") is True)

    def _music_after_change(self, value: str, edited: set[str] | None = None, *, warm_all: bool = False) -> dict[str, Any]:
        path = self._book(value)
        error = ""
        try:
            self.music_rebuild(value, keep_scenes=True, edited=edited, warm_all=warm_all)
        except music_catalog.CatalogError as exc:
            error = str(exc)
        return self._music_payload(path, music_plan.read_plan(path), error)

    # ---- đọc không khí cả đoạn bằng AI (music_moods.py): model tuỳ chọn, người dùng bấm mới tải ----------------------------
    def music_moods_model(self) -> dict[str, Any]:
        """Model đọc không khí đã tải chưa. App đóng gói: Ollama riêng của Studio (tải được từ đây). Chạy từ mã nguồn: Ollama
        của máy - chỉ xem có chưa, người dùng tự kéo model (`downloadable` false)."""
        if self.studio is not None:
            return {**self.studio.optional_status(music_moods.MODEL), "downloadable": True}
        return {"installed": music_moods.model_digest(self._ollama_base()) is not None, "downloading": False,
                "progress": None, "error": None, "downloadable": False}

    def music_moods_model_download(self) -> dict[str, Any]:
        self._mutating()
        if self.studio is None:
            raise ApiError(HTTPStatus.CONFLICT, f"Bản chạy từ mã nguồn dùng Ollama của máy: kéo model {music_moods.MODEL} ở đó")
        try:
            return {**self.studio.pull_optional(music_moods.MODEL), "downloadable": True}
        except Exception as exc:  # noqa: BLE001 - SetupError: Studio chưa cài / đang cài
            raise ApiError(HTTPStatus.CONFLICT, str(exc)) from exc

    def music_moods_compute(self, value: str) -> dict[str, Any]:
        """Người dùng bấm "Tính lại cảm xúc nhạc": chạy `music_moods.compute` (nếu model đọc không khí đã tải) rồi học sinh đoán hình không khí
        (nếu máy có gói, `music_scene_student`), rồi dựng lại rãnh nhạc (chia lại đoạn) ở luồng nền. Hai việc độc lập. Không chạy khi cuốn đang
        có dây chuyền (hai việc giành GPU) hay máy chưa có cái nào trong hai."""
        self._mutating()
        path = self._editable(value)
        if packages.is_package(path):
            raise ApiError(HTTPStatus.CONFLICT, "Sách mở từ file đã mang sẵn nhạc của người làm sách - không tính lại ở đây")
        if self.runner.running(path) or self.jobs.starting(path):
            raise ApiError(HTTPStatus.CONFLICT, "Cuốn này đang được làm - đợi xong rồi hãy tính lại cảm xúc nhạc")
        base = self._ollama_base()
        scene_ready = music_scene_student.present() and not music_module.scene_student_offered()
        if self.studio is not None:
            try:
                self.studio.ensure_ollama()  # Ollama riêng của Studio tự bật nếu đang tắt
            except Exception as exc:  # noqa: BLE001 - SetupError / OSError
                if not scene_ready:
                    raise ApiError(HTTPStatus.CONFLICT, f"Không bật được Ollama của Studio: {exc}") from exc
        if music_moods.model_digest(base) is None and not scene_ready:
            raise ApiError(HTTPStatus.CONFLICT, "Chưa tải model đọc không khí - bấm Tải trước")
        with self._moods_lock:
            if not (self._moods_jobs.get(str(path)) or {}).get("running"):
                self._moods_jobs[str(path)] = {"running": True, "error": ""}
                threading.Thread(target=self._moods_run, args=(value, path, base), name="music-moods", daemon=True).start()
        return self._music_payload(path, music_plan.read_plan(path), "")

    def _scene_student_run(self, path: Path) -> None:
        """Học sinh đoán hình không khí trong chương cho "Tính lại". Tiến trình này có torch (máy dev) thì chạy tại chỗ; không (bản cài) mà Studio đã cài thì
        chạy bằng Python của Studio ở tiến trình con, cùng thư mục mã với worker. KHÔNG BAO GIỜ ném."""
        try:
            if music_scene_student.dependencies_ok() or self.studio is None or not self.studio.installed():
                music_scene_student.run_after_analysis(path, lambda: False, lambda _line: None, lambda _kind, _payload: None)  # không gói thì bỏ qua
                return
            code = self.studio.code_for(path)
            music_scene_student.run_in_studio(path, self.studio.python, code, self.studio.environment(code), lambda _line: None)
        except Exception:  # noqa: BLE001 - tuỳ chọn: lỗi gì cũng chỉ là không có hình không khí
            pass

    def _moods_run(self, value: str, path: Path, base: str) -> None:
        error = ""
        try:
            failure: Exception | None = None
            try:
                if music_moods.model_digest(base) is not None:
                    music_moods.compute(path, base)
            except Exception as exc:  # noqa: BLE001 - lỗi P0 không chặn học sinh; báo sau khi đã dựng lại
                failure = exc
            self._scene_student_run(path)
            self.music_rebuild(value)
            if failure is not None:
                raise failure
        except Exception as exc:  # noqa: BLE001 - việc nền: lỗi hiện ở tab Nhạc, không làm sập máy chủ
            error = str(getattr(exc, "message", None) or exc)
        finally:
            music_moods.release(base)
            with self._moods_lock:
                self._moods_jobs[str(path)] = {"running": False, "error": error}

    def _music_ranked(self, path: Path, scene_key: str, *, limit: int, exclude: Iterable[str] = (),
                      available: Callable[[str], bool] | None = None,
                      book_key: str | None = None, pool: str = "all") -> list[dict[str, Any]] | None:
        """Bài hợp nhất cho MỘT đoạn của plan (music_select.rank): cùng điểm và bộ lọc với lúc máy chọn, tôn trọng phong cách
        / thế giới của cuốn và bài đã bỏ. None = plan không có đoạn này. `pool`: "all" (danh mục + Nhạc của tôi đã phân tích,
        như lúc máy chọn), "catalog" hay "mine"."""
        plan = music_plan.read_plan(path)
        scenes = (plan or {}).get("scenes") or []
        index = next((i for i, scene in enumerate(scenes) if scene.get("key") == scene_key), None)
        if index is None:
            return None
        overrides = music_plan.read_overrides(path)
        catalog = self.music_catalog()
        genres = (catalog.manifest().get("taxonomy") or {}).get("genres") or {}
        genre_styles = (genres.get(overrides["genre"]) or {}).get("styles") if overrides["genre"] else None
        recent: list[str] = []  # như music_select.choose: bài đã chơi ở mấy đoạn trước, đoạn kề cùng bài không tính lặp
        for scene in scenes[:index]:
            if scene.get("link") and (not recent or recent[-1] != scene["link"]):
                recent.append(scene["link"])
        near = {"all": self._music_candidates, "catalog": lambda v, a: catalog.near(v, a, radius=1),
                "mine": lambda v, a: self.my_music.near(v, a, radius=1)}[pool]
        return music_select.rank(scenes[index], near, book_key=book_key or book_id(path),
                                 family=overrides["family"], banned=overrides["banned"], genre_styles=genre_styles,
                                 recent=recent, exclude=exclude, limit=limit, available=available)

    def _my_track(self, link: str) -> tuple[dict[str, Any], Path] | None:
        """(thông tin, file) của một bài trong "Nhạc của tôi" của máy này, hay None - cho `book_edits.set_music` (đổi bài một mốc của
        sách đóng gói sang bài của người nghe)."""
        info, path = self.my_music.lookup([link]).get(link), self.my_music.file(link)
        return (info, path) if info is not None and path is not None else None

    def _packaged_alternatives(self, path: Path, scene_key: str) -> dict[str, Any]:
        """"Đổi bài" của sách đóng gói: mốc nhạc người làm sách gắn không có "không khí" để chấm điểm, nên danh mục không đề xuất
        bài nào - chỉ có nhóm "Nhạc của tôi" (mọi bài đã nhập trừ bài đang dùng ở mốc này, bài chưa phân tích đi trước sau bài đã
        phân tích), cùng hình với nhóm của sách có xưởng."""
        view = book_edits.music_view(packages.manifest(path), book_edits.load(path))
        if not any(cue["key"] == scene_key for cue in view["cues"]):
            raise ApiError(HTTPStatus.NOT_FOUND, "Không thấy đoạn nhạc này trong sách.")
        edits = book_edits.load(path)
        current = ((edits.get("music") or {}).get("pins") or {}).get(scene_key) or book_edits.base_links(packages.manifest(path)).get(scene_key)
        items = []
        for track in self.my_music.entries():
            if track["link"] == current:
                continue
            items.append({"link": track["link"], "title": track["title"], "creator": track["creator"], "attribution": "",
                          "duration": track["duration"], "analysed": track["analysed"], "fits": False, **music_local.auto_keys(track)})
        items.sort(key=lambda item: (not item["analysed"], item["title"].lower()))
        return {"key": scene_key, "alternatives": [], "mine": items}

    def music_alternatives(self, value: str, scene_key: str, limit: int = 6) -> dict[str, Any]:
        """"Đổi bài": tối đa `limit` bài khác cho một đoạn, hợp nhất trước - cùng điểm và bộ lọc với lúc máy chọn
        (music_select.rank), tôn trọng phong cách / thế giới của cuốn, bỏ bài đã bỏ, bài đang chọn và bài máy này không lấy được."""
        listenable = self._listenable(value)
        if packages.is_package(listenable):
            return self._packaged_alternatives(listenable, scene_key)
        path = self._book(value)
        plan = music_plan.read_plan(path)
        current = next((scene.get("link") for scene in (plan or {}).get("scenes") or []
                        if scene.get("key") == scene_key), None)
        ranked = self._music_ranked(path, scene_key, limit=limit, exclude=[current] if current else [], book_key=value,
                                    available=self.music_track_available, pool="catalog")
        if ranked is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Không thấy đoạn nhạc này - hãy chọn lại nhạc rồi thử lại.")
        info = self.music_catalog().lookup([track["link"] for track in ranked]) if ranked else {}
        items = []
        for track in ranked:
            known = {**track, **info.get(track["link"], {})}
            item = {"link": track["link"], "title": known.get("title") or "", "creator": known.get("creator") or "",
                    "attribution": known.get("attribution") or "", "score": track["score"]}
            if known.get("duration"):
                item["duration"] = known["duration"]
            items.append(item)
        return {"key": scene_key, "alternatives": items, "mine": self._music_mine(path, scene_key, current, value)}

    def _music_mine(self, path: Path, scene_key: str, current: str | None, book_key: str) -> list[dict[str, Any]]:
        """Nhóm "Nhạc của tôi" trong "Đổi bài": MỌI bài người dùng đã nhập (trừ bài đang chọn và bài đã bỏ cho cuốn này) - ghim
        tay được kể cả bài chưa phân tích. Bài hợp không khí đoạn này (qua ngưỡng im lặng) đứng trước, kèm điểm."""
        banned = set(music_plan.read_overrides(path)["banned"])
        fits = {track["link"]: track["score"] for track in self._music_ranked(
            path, scene_key, limit=1_000_000, book_key=book_key, available=self.music_track_available, pool="mine") or []}
        items = []
        for track in self.my_music.entries():
            link = track["link"]
            if link == current or link in banned:
                continue
            item = {"link": link, "title": track["title"], "creator": track["creator"], "attribution": "",
                    "duration": track["duration"], "analysed": track["analysed"], "fits": link in fits, **music_local.auto_keys(track)}
            if link in fits:
                item["score"] = fits[link]
            items.append(item)
        items.sort(key=lambda item: (not item["fits"], not item["analysed"], item.get("score", 0.0), item["title"].lower()))
        return items

    def _music_alternatives(self, path: Path, scene_key: str, exclude: list[str], *, limit: int = 6,
                            available: Callable[[str], bool] | None = None) -> list[dict[str, Any]]:
        """Bài thay thế (kèm thông tin ghi công / độ to) cho một đoạn mà bài đã chọn không dùng được trên máy này; mất danh
        mục hay không có bài nào hợp thì rỗng - chỗ ấy im lặng."""
        try:
            ranked = self._music_ranked(path, scene_key, limit=limit, exclude=exclude, available=available) or []
            info = self._music_lookup([track["link"] for track in ranked]) if ranked else {}
        except (music_catalog.CatalogError, OSError, ValueError):
            return []
        return [{**track, **info.get(track["link"], {})} for track in ranked]

    def music_export_source(self) -> music_plan.TrackSource:
        """Nguồn file nhạc cho gói sách (.abook, .abookproj): lấy / tải bài đã chọn, không được thì bài thay thế dùng được
        trên máy này (music_plan.package)."""
        return music_plan.TrackSource(self.music_track_for_export, lambda root, key, exclude: self._music_alternatives(
            root, key, exclude, available=self.music_track_available))

    @contextlib.contextmanager
    def music_exporting(self, key: str, projects: list[Path]) -> Iterator[music_plan.TrackSource]:
        """Nguồn nhạc cho MỘT lượt xuất của cuốn `key` (đường dẫn dự án), kèm tiến độ tải ("Đang tải nhạc nền (k/n)…" trong hộp
        Xuất: `music_export_status`) và huỷ (`cancel_music_export`). Huỷ có hiệu lực trước bài kế phải tải; mọi file sách chỉ
        được ghi SAU khi nhạc đã gom xong (bookfile.listening_layer) nên huỷ ở đây không để lại file dở - việc ném
        `export_jobs.Cancelled` để chỗ gọi đổi thành lời báo."""
        from .export import audio_bytes

        _size, pending = audio_bytes(projects, self.music_track_cached)
        state: dict[str, Any] = {"done": 0, "total": pending, "cancel": threading.Event(), "seen": set()}
        base = self.music_export_source()

        def file(link: str) -> Path | None:
            if state["cancel"].is_set():
                raise export_jobs.Cancelled()
            fresh = self.music_track_cached(link) is None and link not in state["seen"]
            path = base.file(link)
            if fresh:
                state["seen"].add(link)
                state["done"] += 1
            return path

        with self._music_exports_lock:
            self._music_exports[key] = state
        try:
            yield music_plan.TrackSource(file, base.alternatives)
        finally:
            with self._music_exports_lock:
                if self._music_exports.get(key) is state:
                    del self._music_exports[key]

    @staticmethod
    def music_key(project: Path, kind: str = "bookfile") -> str:
        """Khoá `music_exporting` của MỘT kiểu xuất trên cuốn `project`: `.abook` và `.abookproj` có thể cùng chạy (hai việc nền riêng), mỗi bên
        một khoá nên không ghi đè trạng thái hay huỷ nhầm lượt của nhau. `.abook` giữ khoá cũ (đường dẫn dự án)."""
        return str(project) if kind == "bookfile" else f"{kind}:{project}"

    def music_export_status(self, key: str) -> dict[str, Any]:
        """{active, done, total}: lượt xuất của cuốn `key` đang tải nhạc nền để đóng kèm (bài thứ `done` trong `total` bài chưa có).
        Lượt tải sẵn (`_warm_run`, khoá kind "warm") thêm {doneBytes, totalBytes}: tab Nhạc báo MB."""
        with self._music_exports_lock:
            state = self._music_exports.get(key)
            if state is None:
                return {"active": False, "done": 0, "total": 0}
            status = {"active": True, "done": state["done"], "total": max(state["total"], state["done"])}
            if "totalBytes" in state:
                status.update(doneBytes=state["doneBytes"], totalBytes=max(state["totalBytes"], state["doneBytes"]))
            return status

    def cancel_music_export(self, key: str) -> bool:
        with self._music_exports_lock:
            state = self._music_exports.get(key)
        if state is not None:
            state["cancel"].set()
        return state is not None

    def music_sync_source(self) -> music_plan.TrackSource:
        """Nguồn file nhạc cho điện thoại nghe / đồng bộ (webui/sync.py): chỉ bài ĐÃ có trong bộ đệm (không tải trong lượt
        hỏi). Bài của plan mà máy này không dùng được (`music_track_available`) thì thay bằng bài kế dùng được - như
        `_music_playable` ở trình phát máy tính; bài chỉ mới chưa tải xong thì chờ đợt tải sẵn, không thay vội."""
        def alternatives(root: Path, key: str, exclude: list[str]) -> list[dict[str, Any]]:
            if any(self.music_track_available(link) for link in exclude):
                return []
            return self._music_alternatives(root, key, exclude, available=self.music_track_available)
        return music_plan.TrackSource(self.music_track_cached, alternatives)

    def music_cues(self, value: str, chapter_id: int) -> dict[str, Any]:
        """Nhạc của một chương cho trình phát: mốc thời gian + đường lấy file qua máy này (đệm, tua được)."""
        path = self._listenable(value)
        if packages.is_package(path):
            # Cuốn mở từ file `.abook`: nhạc người sản xuất đã gắn nằm sẵn trong gói (bookfile.py, music_plan.package).
            music = packages.edited_manifest(path).get("music")  # đã qua lớp sửa: tắt, mức mới, đoạn im lặng
            cues = [dict(cue, src=f"/api/books/{quote(value, safe='')}/music/files/{cue['track'].split('/')[1]}")
                    for cue in music_plan.packaged_cues(music, chapter_id)]
            level = music.get("levelDb") if isinstance(music, dict) else None
            level = level if isinstance(level, (int, float)) else music_plan.DEFAULT_LEVEL_DB
            tracks = music.get("tracks") if isinstance(music, dict) and isinstance(music.get("tracks"), dict) else {}
            by_link = {cue["link"]: tracks.get(cue["track"]) for cue in cues}
            music_plan.apply_gain(cues, level, by_link)  # sách xuất bởi bản cũ: mốc chưa có gainDb (không có file để đo)
            return {"cues": cues, "levelDb": level, "credits": self._music_credits(cues, by_link)}
        plan = music_plan.read_plan(path)
        if plan is None:
            return {"cues": [], "levelDb": music_plan.DEFAULT_LEVEL_DB, "credits": {}}
        tracks = dict(plan.get("tracks") or {})
        cues = [dict(cue, src=self._music_src(value, cue["link"]))
                for cue in self._music_playable(path, music_plan.chapter_cues(plan, chapter_id), tracks)]
        level = plan.get("levelDb", music_plan.DEFAULT_LEVEL_DB)
        music_plan.apply_gain(cues, level, tracks, self.music_track_cached)
        return {"cues": cues, "levelDb": level, "credits": self._music_credits(cues, tracks)}

    # ---- danh sách phát cho sách nghe bằng "Nghe ngay" (music_playlist.py) ---------------------------------------------
    def music_playlists(self) -> dict[str, Any]:
        """Menu "Nhạc nền" của sách chỉ có chữ: các danh sách phát của danh mục + số bài trong "Nhạc của tôi". Chưa tải được
        danh mục (mất mạng lần đầu) thì không có danh sách nào, kèm lý do."""
        error = ""
        try:
            playlists = music_playlist.summaries(self.music_catalog().playlists())
        except music_catalog.CatalogError as exc:
            playlists, error = [], str(exc)
        return {"playlists": playlists, "mine": len(self.my_music.entries()), "error": error}

    def music_playlist_queue(self, value: str) -> dict[str, Any]:
        """Hàng bài của danh sách phát cho cuốn này: người nghe đã chọn (`music.playlist` của lớp sửa) hay, khi chưa chọn gì, máy
        tự chọn (`playlistAuto` true - `_auto_playlist`): [{link, src, duration, gainDb}] theo thứ tự phát, kèm ghi công. Cuốn có
        nhạc của người làm sách (nhạc theo cảnh thắng), đã tắt ("off"), máy không chọn được, hay danh mục không còn danh sách ấy:
        không bài nào. Bài máy này không dùng được (offline chưa có trong bộ đệm, nguồn hỏng) bị bỏ."""
        path = self._listenable(value)
        result: dict[str, Any] = {"playlist": None, "tracks": [], "levelDb": music_plan.DEFAULT_LEVEL_DB, "credits": {}, "error": ""}
        if not packages.is_package(path) or packages.manifest(path).get("music"):
            return result
        changes = book_edits.load(path).get("music") or {}
        choice = changes.get("playlist")
        auto = not choice
        if auto:  # chưa chọn gì: máy chọn danh sách hợp với cuốn (không chọn được thì không nhạc)
            choice = self._auto_playlist(value, path)
        if not choice or choice == music_playlist.OFF:
            return result
        level = float(changes.get("levelDb", music_plan.DEFAULT_LEVEL_DB))
        result.update(playlist=choice, levelDb=level, **({"playlistAuto": True} if auto else {}))
        if choice == music_playlist.MINE:
            info = {entry["link"]: entry for entry in reversed(self.my_music.entries())}  # cũ trước: bài mới nhập nối vào cuối
            links = list(info)
        else:
            try:
                catalog = self.music_catalog()
                links = music_playlist.links_of(catalog.playlists(), choice)
                info = catalog.lookup(links) if links else {}
            except music_catalog.CatalogError as exc:
                return {**result, "error": str(exc)}
        tracks = music_playlist.queue(links, info, self.music_track_available)
        music_plan.apply_gain(tracks, level, info, self.music_track_cached)
        for track in tracks:
            digest = music_plan.local_hash(track["link"])
            track["src"] = (f"/api/music/local/{digest}/file" if digest is not None
                            else "/api/music/track?link=" + quote(track["link"], safe=""))
        return {**result, "tracks": tracks, "credits": self._music_credits(tracks, info)}

    def _with_auto_playlist(self, value: str, path: Path, view: dict[str, Any]) -> dict[str, Any]:
        """Màn "Nhạc nền" của sách đóng gói + danh sách máy chọn: sách chưa có lựa chọn nào (`playlist` không có khoá) và không có nhạc của
        người làm sách thì `playlist` là mã máy chọn, kèm `playlistAuto` true. Đã chọn (kể cả "off") thì giữ nguyên."""
        if "playlist" not in view and not packages.manifest(path).get("music"):
            auto = self._auto_playlist(value, path)
            if auto is not None:
                view.update(playlist=auto, playlistAuto=True)
            elif not self.preferences.get().get("autoMusic", True) and packages.text_book(packages.manifest(path)):
                view["autoOff"] = True  # cuốn chưa chọn nhạc và người dùng đã tắt "máy tự chọn" trong Cài đặt: nút nói đúng là chưa có nhạc
        return view

    def _auto_playlist(self, value: str, path: Path) -> str | None:
        """Danh sách phát máy chọn cho sách CHỈ CÓ CHỮ chưa được người nghe chọn gì (`music.playlist` không có khoá): luật của mục lục
        danh mục nếu hợp lệ, không thì bản đóng kèm (chưa tải được danh mục cũng chọn được); đầu vào là tên sách + chữ các chương.
        Đệm theo (mã sách, nguồn luật, version luật). Không chọn được (không phải sách chữ, luật hỏng) thì None."""
        book = packages.manifest(path)
        if not packages.text_book(book) or not self.preferences.get().get("autoMusic", True):
            return None
        try:
            manifest = self.music_catalog().manifest()
        except music_catalog.CatalogError:
            manifest = None
        picker, source = music_playlist.usable_picker(manifest)
        if picker is None:
            return None
        key = (value, source, picker["version"])
        if key in self._playlist_auto:
            return self._playlist_auto[key]
        unread = False

        def chapters() -> Iterable[str]:
            nonlocal unread
            for chapter in book.get("chapters") or []:
                text = packages.chapter_text(path, chapter["id"]) if isinstance(chapter, dict) and isinstance(chapter.get("id"), int) else None
                if text is None:
                    unread = True  # chữ chưa có ở máy này (sách của máy khác chưa tải): lần sau thử lại, đừng đệm
                else:
                    yield text

        code = music_playlist.pick(picker, str(book.get("title") or ""), chapters())
        if not unread:
            self._playlist_auto[key] = code
        return code

    def _music_src(self, value: str, link: str) -> str:
        """Đường lấy file bài qua máy này. Bài danh mục: `/api/music/track?link=` (máy chủ chỉ tải bài CÓ trong danh mục); bài
        "Nhạc của tôi": đường THEO SÁCH như file trong gói - chỉ cuốn có đoạn dùng bài ấy mới lấy được."""
        path = self.music_track_cached(link) if music_plan.is_local(link) else None
        if path is None:
            return "/api/music/track?link=" + quote(link, safe="")
        return f"/api/books/{quote(value, safe='')}/music/files/{music_plan.track_name(link, path).split('/')[1]}"

    def _music_playable(self, path: Path, cues: list[dict[str, Any]], tracks: dict[str, Any]) -> list[dict[str, Any]]:
        """Mốc nhạc mà máy này phát được: mốc có bài không dùng được (offline và chưa có trong bộ đệm, hay nguồn đã hỏng) thì
        thay bằng bài hợp nhất dùng được cho đoạn ấy; không có bài nào mới bỏ mốc (im lặng). Thông tin bài thay thế thêm vào
        `tracks` (ghi công, độ to). Plan không đổi - chỉ lượt phát này."""
        playable = []
        for cue in cues:
            if self.music_track_available(cue["link"]):
                playable.append(cue)
                continue
            for other in self._music_alternatives(path, cue["key"], [cue["link"]], limit=1,
                                                  available=self.music_track_available):
                tracks[other["link"]] = {key: other[key] for key in music_plan.TRACK_INFO_KEYS if key in other}
                playable.append(dict(cue, link=other["link"]))
        return playable

    @staticmethod
    def _music_credits(cues: list[dict[str, Any]], tracks: dict[str, Any]) -> dict[str, dict[str, str]]:
        """Ghi công tác giả của các bài chương này dùng (CC BY đòi nêu tên ở nơi nhạc phát): {link: {title, creator,
        attribution, landing, license, licenseUrl}} - chỉ khoá nào có. `tracks`: dự án = plan["tracks"][link];
        gói sách = {link: tracks[tên]}."""
        credits: dict[str, dict[str, str]] = {}
        for cue in cues:
            info = tracks.get(cue["link"])
            if not isinstance(info, dict):
                continue
            credit = {key: info[key] for key in ("title", "creator", "attribution", "landing", "license", "licenseUrl")
                      if isinstance(info.get(key), str) and info[key]}
            if credit:
                credits[cue["link"]] = credit
        return credits

    def music_track_cached(self, link: str) -> Path | None:
        """Bài đã có trong bộ đệm của máy (không tải): cho gói điện thoại hỏi thường xuyên. Bài "Nhạc của tôi": file trong kho."""
        if music_plan.is_local(link):
            return self.my_music.file(link)
        target = self.music_dir / "files" / (hashlib.sha1(link.encode("utf-8")).hexdigest() + ".mp3")
        return target if target.is_file() else None

    def _warm_music(self, plan: dict[str, Any] | None, value: str | None = None, scenes: set[str] | None = None) -> None:
        """Tải sẵn các bài của rãnh nhạc vừa dựng (luồng nền): điện thoại và file sách lấy được nhạc ngay. Nhạc tắt thì không
        tải gì; `scenes` (khoá đoạn) khác None thì chỉ bài của các đoạn ấy."""
        if not (plan or {}).get("enabled"):
            return
        if any(scene.get("link") and (scenes is None or scene.get("key") in scenes) for scene in plan.get("scenes") or []):
            threading.Thread(target=self._warm_run, args=(plan, value, scenes), name="music-warm", daemon=True).start()

    def _warm_run(self, plan: dict[str, Any] | None, value: str | None, scenes: set[str] | None = None) -> None:
        """Tải từng bài của plan (chỉ các đoạn `scenes` nếu có); bài nào máy này không lấy được (mạng, nguồn hỏng, quá
        MUSIC_TRACK_MAX_MB) thì dựng lại plan với các đoạn khác giữ bài cũ - đoạn ấy lấy bài kế dùng được thay vì im lặng -
        rồi tải sẵn bài mới. Tối đa MUSIC_WARM_ROUNDS vòng. Tiến độ (bài, MB) ở `music_export_status(music_key(cuốn, "warm"))`
        - tab Nhạc hiện và huỷ được (`cancel_music_export`); các lượt cùng cuốn chạy chồng nhau dùng chung một trạng thái."""
        key: str | None = None
        if value is not None:
            with contextlib.suppress(ApiError):
                key = self.music_key(self._book(value), "warm")
        fresh = {"done": 0, "total": 0, "doneBytes": 0, "totalBytes": 0, "cancel": threading.Event(), "seen": set(), "runs": 0}
        with self._music_exports_lock:
            state = self._music_exports.get(key) if key is not None else None
            if state is None or state["cancel"].is_set():
                state = fresh
                if key is not None:
                    self._music_exports[key] = state
            state["runs"] += 1
        try:
            self._warm_rounds(plan, value, scenes, state)
        finally:
            with self._music_exports_lock:
                state["runs"] -= 1
                if state["runs"] == 0 and key is not None and self._music_exports.get(key) is state:
                    del self._music_exports[key]

    def _warm_rounds(self, plan: dict[str, Any] | None, value: str | None, scenes: set[str] | None,
                     state: dict[str, Any]) -> None:
        for _ in range(MUSIC_WARM_ROUNDS):
            links = sorted({scene["link"] for scene in (plan or {}).get("scenes") or []
                            if scene.get("link") and (scenes is None or scene.get("key") in scenes)})
            sizes = self._music_sizes([link for link in links if self.music_track_cached(link) is None])
            with self._music_exports_lock:
                for link, size in sizes.items():
                    if link not in state["seen"]:
                        state["seen"].add(link)
                        state["total"] += 1
                        state["totalBytes"] += size or 0
            failed: set[str] = set()
            for link in links:
                if state["cancel"].is_set():
                    return  # người dùng huỷ: bài chưa tải để trình phát tải khi cần, không phải bài hỏng
                path = self.music_track_cached(link)
                if path is None and self.music_track_available(link):  # đang offline thì khỏi chờ mạng từng bài
                    try:
                        path = self._warm_fetch(link, sizes.get(link), state)
                    except export_jobs.Cancelled:
                        return
                if path is None:
                    failed.add(link)
                else:
                    music_plan.measured_lufs(path)  # đo sẵn độ to thật của bài (thắng số danh mục), trình phát khỏi chờ
            if not failed or value is None or plan is None:
                return
            try:
                path = self._book(value)
                on_disk = music_plan.read_plan(path)
                if on_disk is None or on_disk.get("built") != plan.get("built"):
                    return  # người dùng đã sửa / dựng lại trong lúc tải: lần dựng ấy tự lo phần của nó
                lost = {scene["key"] for scene in plan["scenes"] if scene.get("link") in failed}
                plan = self._music_build(value, path, self.music_catalog().manifest(), plan, lost)
                scenes = lost  # vòng sau chỉ tải bài thay cho các đoạn ấy
            except (ApiError, music_catalog.CatalogError, OSError, ValueError):
                return

    def _music_sizes(self, links: list[str]) -> dict[str, int | None]:
        """Cỡ (byte) theo danh mục của các bài sắp tải; không biết thì None (Content-Length bù khi bắt đầu tải)."""
        try:
            known = self.music_catalog().lookup([link for link in links if not music_plan.is_local(link)])
        except (music_catalog.CatalogError, OSError, ValueError):
            known = {}
        sizes: dict[str, int | None] = {}
        for link in links:
            size = (known.get(link) or {}).get("bytes")
            sizes[link] = size if isinstance(size, int) and 0 < size <= MUSIC_TRACK_MAX_BYTES else None
        return sizes

    def _warm_fetch(self, link: str, size: int | None, state: dict[str, Any]) -> Path | None:
        """Tải một bài cho lượt tải sẵn, cộng tiến độ MB vào `state`; hỏng thì bỏ phần của bài ấy khỏi tổng."""
        counted = {"length": size or 0, "copied": 0}

        def progress(copied: int, length: int | None) -> None:
            with self._music_exports_lock:
                if not counted["length"] and length:
                    counted["length"] = length
                    state["totalBytes"] += length
                state["doneBytes"] += copied - counted["copied"]
                counted["copied"] = copied

        path: Path | None = None
        try:
            path = self.music_track_for_export(link, progress=progress, cancel=state["cancel"])
        finally:
            with self._music_exports_lock:
                state["done"] += 1
                if path is None:
                    state["doneBytes"] -= counted["copied"]
                    state["totalBytes"] = max(0, state["totalBytes"] - counted["length"])
        return path

    def _read_unavailable(self, name: str = "unavailable.json") -> dict[str, float]:
        try:
            data = json.loads((self.music_dir / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {link: float(when) for link, when in data.items() if isinstance(when, (int, float))}

    def _music_mark(self, link: str, failed: bool) -> None:
        """Ghi / xoá dấu "máy này không tải được bài này" (music_dir/unavailable.json: {link: giờ hỏng}); dấu hết hạn sau 24 giờ."""
        with self._music_lock:
            now = self._music_clock()
            kept = {key: when for key, when in self._music_unavailable.items()
                    if now - when < MUSIC_UNAVAILABLE_SECONDS and key != link}
            if failed:
                kept[link] = now
            if kept == self._music_unavailable:
                return
            self._music_unavailable = kept
            with contextlib.suppress(OSError):
                atomic_write_json(self.music_dir / "unavailable.json", kept)

    def _music_mark_too_big(self, link: str, size: int) -> None:
        """Ghi "bài này quá MUSIC_TRACK_MAX_MB" (music_dir/too_big.json: {link: số byte}) - không hết hạn: cỡ bài không đổi."""
        with self._music_lock:
            if self._music_too_big.get(link) == size:
                return
            self._music_too_big = {**self._music_too_big, link: float(size)}
            with contextlib.suppress(OSError):
                atomic_write_json(self.music_dir / "too_big.json", self._music_too_big)

    def music_track_available(self, link: str) -> bool:
        """Bài này dùng được TRÊN MÁY NÀY không: có trong bộ đệm thì được (kể cả offline); đang offline (tải hỏng vì mạng trong
        5 phút qua), bài đã bị đánh dấu hỏng (chưa quá 24 giờ) hay quá MUSIC_TRACK_MAX_MB thì không; chưa biết thì cứ coi là được."""
        if self.music_track_cached(link) is not None:
            return True
        if music_plan.is_local(link):
            return False  # nhạc người dùng nhập không tải được từ đâu: không có file là không dùng được
        with self._music_lock:
            if self._music_too_big.get(link, 0) > MUSIC_TRACK_MAX_BYTES:
                return False
            now = self._music_clock()
            if now < self._music_offline_until:
                return False
            failed_at = self._music_unavailable.get(link)
            return failed_at is None or now - failed_at >= MUSIC_UNAVAILABLE_SECONDS

    @staticmethod
    def _music_network_failure(exc: OSError) -> bool:
        """Lỗi tầng mạng (không có mạng, DNS, hết giờ, đứt kết nối) - khác nguồn trả lỗi HTTP hay bản sao sai sha1."""
        if isinstance(exc, (urllib.error.HTTPError, MirrorMismatch, TrackTooBig)):
            return False
        return isinstance(exc, (urllib.error.URLError, socket.timeout, socket.gaierror, ConnectionError))

    def music_track_for_export(self, link: str, **fetch: Any) -> Path | None:
        """Bài nhạc để gói vào file sách: lấy từ bộ đệm / tải về; không lấy được thì None (chỗ ấy im lặng). `fetch`: tiến độ /
        huỷ của `music_track_file` (huỷ thì ném export_jobs.Cancelled)."""
        if music_plan.is_local(link):
            return self.my_music.file(link)
        try:
            return self.music_track_file(link, **fetch)
        except (ApiError, OSError):
            return None

    @staticmethod
    def _music_copy(response: Any, sink: Any, progress: Callable[[int, int | None], None] | None,
                    cancel: threading.Event | None) -> None:
        """Chép bài đang tải từng khúc: dừng khi quá MUSIC_TRACK_MAX_MB (Content-Length báo trước, hay đếm thật khi nguồn không
        báo) và khi người dùng huỷ; `progress(số byte đã chép, Content-Length hay None)` sau mỗi khúc."""
        headers = getattr(response, "headers", None)
        try:
            length = int(headers.get("Content-Length")) if headers is not None and headers.get("Content-Length") else None
        except (TypeError, ValueError):
            length = None
        if length is not None and length > MUSIC_TRACK_MAX_BYTES:
            raise TrackTooBig(length)
        copied = 0
        while True:
            if cancel is not None and cancel.is_set():
                raise export_jobs.Cancelled()
            chunk = response.read(1 << 16)
            if not chunk:
                return
            copied += len(chunk)
            if copied > MUSIC_TRACK_MAX_BYTES:
                raise TrackTooBig(copied)
            sink.write(chunk)
            if progress is not None:
                progress(copied, length)

    def music_track_file(self, link: str, *, progress: Callable[[int, int | None], None] | None = None,
                         cancel: threading.Event | None = None) -> Path:
        """File nhạc của một bài trong danh mục: tải một lần từ nguồn gốc vào bộ nhớ đệm, lần sau dùng lại. Chỉ bài CÓ
        trong danh mục - máy chủ này không thành chỗ tải hộ link tuỳ ý. Bài quá MUSIC_TRACK_MAX_MB thì không tải (ghi sổ
        `_music_mark_too_big`: rãnh nhạc chọn bài khác)."""
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
        info = known[link] if isinstance(known[link], dict) else {}
        # Nguồn gốc trước; hỏng (mạng, 404, nguồn gỡ bài) thì sang bản sao dự phòng trên archive.org mà danh mục ghi ở
        # `mirrors`. Bản sao phải khớp `sha1` (và `bytes`) của bản gốc - bài không có `sha1` thì không dùng bản sao, không
        # phát nhầm bài.
        expected = info.get("sha1") if isinstance(info.get("sha1"), str) else None
        size = info.get("bytes") if isinstance(info.get("bytes"), int) else None
        mirrors = [url for url in info.get("mirrors") or [] if isinstance(url, str) and url.startswith("https://")
                   ] if expected else []
        if size is not None and size > MUSIC_TRACK_MAX_BYTES:
            self._music_mark_too_big(link, size)
            raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, TOO_BIG_TRACK)
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._music_lock:
            fetching = self._music_fetching.setdefault(link, threading.Lock())
        # Cùng một bài đang được tải (luồng tải sẵn sau khi đổi nhạc, hay trình phát khác): chờ nó xong rồi dùng luôn.
        with fetching:
            if target.is_file():
                return target
            failure: OSError | None = None
            network_only = True
            for url in [link, *mirrors]:
                part = target.with_name(f"{target.stem}.{secrets.token_hex(4)}.part")
                try:
                    request = urllib.request.Request(url, headers={"User-Agent": music_catalog.USER_AGENT})
                    with urllib.request.urlopen(request, timeout=60) as response, part.open("wb") as sink:
                        self._music_copy(response, sink, progress, cancel)
                    if url != link and ((size is not None and part.stat().st_size != size)
                                        or hashlib.sha1(part.read_bytes()).hexdigest() != str(expected).lower()):
                        raise MirrorMismatch(f"bản sao khác bản gốc: {url}")
                    os.replace(part, target)
                    self._music_offline_until = 0.0  # tải được = có mạng
                    self._music_mark(link, failed=False)
                    return target
                except TrackTooBig as exc:  # bản sao cùng cỡ: khỏi thử
                    self._music_offline_until = 0.0
                    self._music_mark_too_big(link, exc.size)
                    raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, TOO_BIG_TRACK) from exc
                except OSError as exc:
                    failure = exc
                    network_only = network_only and self._music_network_failure(exc)
                finally:
                    with contextlib.suppress(OSError):
                        part.unlink(missing_ok=True)  # thành công thì part đã thành target; hỏng / huỷ: không để file dở
            # Mọi nguồn hỏng vì mạng: cả máy đang offline (không đánh dấu bài - bài vẫn tốt); còn lại: bài này hỏng.
            if network_only:
                self._music_offline_until = self._music_clock() + MUSIC_OFFLINE_SECONDS
            else:
                self._music_mark(link, failed=True)
            raise ApiError(HTTPStatus.BAD_GATEWAY, "Không tải được bài nhạc từ nguồn - kiểm tra mạng") from failure

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
        chain = continuation.series_parts(here, self.library.projects())
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
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thư mục này không phải một dự án. Chọn đúng thư mục của dự án sách nói (thư mục ABook đã tạo cho nó); còn file .abook hay .abookproj thì mở từ Thư viện.")
        self.preferences.add_recent(path.resolve())
        return {"id": book_id(path.resolve())}

    # ---- đồng bộ điện thoại ------------------------------------------------------------------------------

    def sync_view(self) -> dict[str, Any]:
        running = self.sync_server is not None
        addresses = local_addresses() if self.sync_host == "0.0.0.0" else [self.sync_host]
        return {
            "enabled": running,
            "wanted": bool(self.preferences.get().get("syncEnabled")),
            "error": self.sync_error,
            "name": socket_name(),
            "port": self.sync_server.port if running else self.sync_port,
            "addresses": addresses,
            # Địa chỉ trên card mạng riêng ảo (Tailscale, ZeroTier, WireGuard...): dùng khi ở ngoài nhà.
            "awayAddresses": away_addresses(addresses),
            "pairing": self.devices.pairing() if running else None,
            "pairingBlocked": running and self.devices.blocked,
            # Vân tay chứng chỉ TLS của máy này (tls.py): hiện cạnh mã ghép để người dùng đối chiếu nếu muốn.
            "fingerprint": tls.display(self.sync_server.fingerprint) if running else "",
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
                              player=self.player, cast=self.cast, music_track=self.music_sync_source(), my_music=self.my_music,
                              after_edits=lambda value, _report: self._music_after_change(value))
                # Danh tính TLS sinh một lần, nằm cạnh tuỳ chọn: đổi nó là mọi thiết bị đã ghép phải ghép lại.
                identity = tls.load_or_create(self.preferences.path.with_name(tls.FILE_NAME))
                self.sync_server = SyncServer(app, host=self.sync_host, port=self.sync_port, identity=identity).start()
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
        self.previews.shutdown()
        self.projectfile_jobs.shutdown()  # đang gói dự án: dừng ở file kế, dọn file tạm (không treo tắt app quá vài giây)
        self._trash_sweeper.cancel()
        # Hết hạn "Hoàn tác" hay chưa, đóng app là cuốn vừa xoá vào Thùng rác - trừ cuốn Thùng rác không nhận trọn (Windows sẽ hỏi
        # "xoá hẳn", mà đóng app không được chờ ai bấm): nó ở lại chỗ chờ tới lần mở sau.
        self.sweep_trash(everything=True, ask=False)

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
            command = remote_command(body, cast=self.cast.owns(device))
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
        return self.cover_file(book) if book is not None else None

    @staticmethod
    def cover_file(path: Path) -> Path | None:
        """Ảnh bìa như người nghe thấy: dự án và sách của máy khác theo `covers`, cuốn nhập từ file theo lớp sửa."""
        return book_edits.cover_file(path) if packages.is_package(path) else covers.cover_file(path)

    def report_player(self, body: dict[str, Any]) -> dict[str, Any]:
        """Giao diện máy này báo trình phát của nó và treo tới `wait` giây chờ lệnh từ máy đã ghép (như điện thoại báo
        máy tính, sync.Remote). Đồng bộ tắt thì không ai gửi lệnh được: trả ngay `idle`, giao diện thưa lại."""
        if self.sync_server is None:
            return {"commands": [], "idle": True}
        commands = self.player.report(LOCAL_PLAYER, socket_name(), body, body.get("wait", 0))
        return {"commands": [{key: value for key, value in command.items() if key != "at"} for command in commands]}

    # ---- nghe ------------------------------------------------------------------------------------------

    def refresh_remote(self, *, wait: bool = False, patience: float | None = None) -> None:
        """Hỏi lại thư viện của các máy tính khác: chạy nền, tối đa mỗi phút một lần (thư viện được hỏi mỗi vài giây);
        `wait` - ngay (vừa ghép, người dùng bấm làm mới) và đợi xong, tối đa `patience` giây: điện thoại đang ngủ thì việc hỏi
        chạy tiếp ở nền (remote_books chờ nó dậy tới 5 phút) và giao diện xem `waking` của máy ấy."""
        if not self.computers.list():
            return
        finished = threading.Event()

        def run() -> None:
            try:
                remote_books.refresh(self.library.root, self.computers, asked=wait)
                self._send_pending_edits()
            finally:
                self._remote_lock.release()
                finished.set()
        if wait:
            if not self._remote_lock.acquire(timeout=-1 if patience is None else patience):
                return
        elif time.time() - self._remote_refreshed < 60 or not self._remote_lock.acquire(blocking=False):
            return
        self._remote_refreshed = time.time()
        threading.Thread(target=run, name="remote-books", daemon=True).start()
        if wait:
            finished.wait(patience)

    def stop_waiting_computer(self, computer: str) -> dict[str, Any]:
        """Người dùng thôi chờ điện thoại đang ngủ (remote_books.stop_waiting)."""
        remote_books.stop_waiting(computer)
        return self.computers_view()

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

    def _remote_package(self, value: str) -> Path:
        """Cuốn "Trên máy khác" (cuốn ảo của remote_books); cuốn khác: 409."""
        path = self._listenable(value)
        if not packages.is_package(path) or remote_books.remote_of(packages.manifest(path)) is None:
            raise ApiError(HTTPStatus.CONFLICT, "Cuốn này đã nằm trên máy này")
        return path

    def remote_download(self, value: str, action: str) -> dict[str, Any]:
        """"Tải về máy" một cuốn của máy khác (remote_books.Downloads): `status`, `start` (hay tải tiếp), `cancel`."""
        path = self._remote_package(value)
        if action == "status":
            # Đứt vì máy kia tắt / mất mạng: máy kia lên lại thì tải tiếp luôn (giao diện hỏi tình trạng mỗi vài giây khi đang đứt).
            if not self.read_only:
                self.remote_downloads.resume_interrupted(path, self._computer_answers)
            return self.remote_downloads.status(path)
        self._mutating()
        if action == "cancel":
            return self.remote_downloads.cancel(path)
        try:
            return self.remote_downloads.start(path)
        except remote_books.RemoteError as error:
            raise ApiError(HTTPStatus.CONFLICT, str(error)) from error

    def _computer_answers(self, computer: str) -> bool:
        """Máy đã ghép `computer` có trả lời ngay lúc này không (hỏi nhẹ, trần 1,5 giây - không chờ máy ngủ dậy)."""
        entry = self.computers.get(computer)
        return entry is not None and remote_books.reachable(entry, timeout=1.5)

    def computer_reachable(self, computer: str) -> dict[str, Any]:
        """{"reachable"}: máy đã ghép trả lời ngay lúc này không - màn nghe hỏi khi một chương của sách "Trên máy khác" không phát được,
        để nói đúng "máy ấy tắt hay mất mạng" thay vì "file có thể đã bị xoá"."""
        if self.computers.get(computer) is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Máy này không ghép với máy ấy")
        return {"reachable": self._computer_answers(computer)}

    def send_remote_edits(self, value: str) -> dict[str, Any]:
        """"Gửi về máy tính": phần sửa của cuốn của máy tính khác về máy ấy ngay (remote_books.send_edits). Trả `editsSync` mới."""
        self._mutating()
        path = self._remote_package(value)
        if not remote_books.sends_edits(packages.manifest(path)):
            raise ApiError(HTTPStatus.CONFLICT, "Sách này lấy từ máy tính khác - muốn sửa thì sửa ở máy ấy")
        try:
            return remote_books.send_edits(path)
        except remote_books.RemoteError as error:
            raise ApiError(HTTPStatus.BAD_GATEWAY, str(error)) from error

    def _schedule_send_edits(self, value: str) -> None:
        """Hẹn gửi phần sửa của cuốn sau `edits_send_delay` giây; mỗi lần sửa lại dời hẹn (người dùng đang sửa dở thì chưa gửi).
        Gửi hỏng thì thôi: lần làm mới thư viện sau gửi lại."""
        if self.edits_send_delay is None:
            return

        def run() -> None:
            self._edits_timers.pop(value, None)
            path = self.library.resolve_listenable(value)
            if path is not None and packages.is_package(path):
                try:
                    remote_books.send_edits(path)
                except remote_books.RemoteError:
                    pass
        previous = self._edits_timers.pop(value, None)
        if previous is not None:
            previous.cancel()
        timer = threading.Timer(self.edits_send_delay, run)
        timer.daemon = True
        self._edits_timers[value] = timer
        timer.start()

    def _send_pending_edits(self) -> None:
        """Vừa nói chuyện được với các máy đã ghép: gửi nốt phần sửa còn tồn của mọi cuốn của máy tính khác."""
        if self.edits_send_delay is None:
            return
        for path in packages.folders(self.library.root):
            try:
                book = packages.manifest(path)
                if remote_books.sends_edits(book) and not book_edits.is_empty(book_edits.load(path)):
                    remote_books.send_edits(path)
            except (remote_books.RemoteError, OSError, ValueError):
                continue

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
            self.computers.pair(address, code, socket_name(),
                                own_port=self.sync_server.port if self.sync_server is not None else None)
        except remote_books.RemoteError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error
        self.refresh_remote(wait=True)
        return self.computers_view()

    def paired_bluetooth(self) -> dict[str, Any]:
        """Điện thoại / máy tính đã ghép Bluetooth trong Cài đặt Windows - để chọn đường Bluetooth cho một máy đã ghép qua Wi-Fi."""
        return {"devices": bluetooth.paired_devices()}

    def set_computer_bluetooth(self, computer: str, address: str) -> dict[str, Any]:
        self._mutating()
        try:
            self.computers.set_bluetooth(computer, address)
        except remote_books.RemoteError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error
        return self.computers_view()

    def unsent_computer_edits(self, computer: str) -> dict[str, Any]:
        """Phần sửa chưa gửi của sách máy tính khác - thứ thôi ghép sẽ xoá (hộp xác nhận hỏi trước): từng cuốn, tổng, và `sendable` =
        máy kia là máy tính (nhận được sửa; điện thoại chia sẻ thư viện thì không). `reachable`: máy kia trả lời NGAY lúc hỏi (chỉ hỏi khi
        có gì để gửi) - trạng thái "thấy lần cuối" của danh sách máy có thể cũ cả phút, hộp nói "Gửi trước" mà máy kia đã tắt."""
        entry = self.computers.get(computer)
        if entry is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Máy này không ghép với máy ấy")
        books = [{"title": item["title"], "changes": item["changes"]} for item in remote_books.unsent_edits(self.library.root, computer)]
        sendable = entry.get("kind") == "computer"
        view: dict[str, Any] = {"books": books, "changes": sum(item["changes"] for item in books), "sendable": sendable}
        # Cái máy này sẽ quên khi thôi ghép (hộp xác nhận nói rõ): số cuốn, MB đã tải, số cuốn đang có chỗ nghe / dấu trang (giữ lại -
        # ghép lại đúng máy ấy là hiện lại, xem Computers.pair).
        cached = remote_books.cached_books(self.library.root, computer)
        places = 0
        for item in cached:
            state = self.listening.get(book_id(item["package"]))
            if state.get("chapters") or state.get("bookmarks"):
                places += 1
        view["cache"] = {"books": len(cached), "bytes": sum(item["bytes"] for item in cached), "places": places}
        if books and sendable:
            view["reachable"] = remote_books.reachable(entry)
        return view

    def forget_computer(self, computer: str, edits: str = "") -> dict[str, Any]:
        """Thôi ghép. Còn sửa chưa gửi thì từ chối (409), trừ khi `edits` = "send" (gửi hết về máy ấy rồi mới gỡ; hỏng giữa chừng thì không
        gỡ, 502) hay "discard" (người dùng chọn bỏ)."""
        self._mutating()
        try:
            if edits == "send":
                remote_books.send_unsent(self.library.root, computer)
            self.remote_downloads.cancel_computer(computer)
            self.computers.forget(computer, self.library.root, discard=edits == "discard")
        except remote_books.UnsentEdits as error:
            raise ApiError(HTTPStatus.CONFLICT, str(error)) from error
        except remote_books.RemoteError as error:
            raise ApiError(HTTPStatus.BAD_GATEWAY, str(error)) from error
        return self.computers_view()

    def listen_library(self) -> list[dict[str, Any]]:
        """Sách nghe được: mọi sách đã có ít nhất một chương xong - đang sản xuất cũng nghe được phần đã xong. Sách vừa
        tạo, đang làm mà chưa có chương nào, cũng có mặt (chưa nghe được) - người mới tạo sách hỏi "sách của tôi đâu?"."""
        self.refresh_remote()
        books = []
        toolchain = self.capabilities()["toolchain"]  # một lần cho cả danh sách

        def capabilities_of(path: Path) -> dict[str, bool]:
            return {**self.capabilities(path), "toolchain": toolchain}

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
            view["capabilities"] = capabilities_of(path)
            books.append(view)
        for path in self.library.packages():
            value = book_id(path)
            try:
                view = packages.listen(path, value, self.listening.get(value), with_chapters=False)
            except (OSError, ValueError):  # gói hỏng: bỏ qua, như sách hỏng
                continue
            self._built_workshop(view, path)
            view["capabilities"] = capabilities_of(path)
            if view["capabilities"].get("sync"):  # cuốn của máy tính khác: phần sửa chưa gửi về máy ấy, kết quả lần gửi trước
                view["editsSync"] = remote_books.edits_state(path)
            books.append(view)
        books.sort(key=lambda item: ((item["state"].get("last") or {}).get("at") or 0, item.get("updatedAt") or 0),
                   reverse=True)
        return books

    def _built_workshop(self, view: dict[str, Any], path: Path) -> None:
        """Cuốn chờ xưởng đã được “Dựng xưởng”: `projectFile.built` = mã dự án (nếu dự án còn trong thư viện) - giao diện mời mở nó
        thay vì dựng thêm một cái nữa. Sách chỉ-chữ ("Làm sách nói từ cuốn này") thì `studioProject`."""
        info = view.get("projectFile")
        if isinstance(info, dict) and info.get("workshop") == "pending":
            made = workshop.built(path)
            info["built"] = made if made and self.library.resolve(made) is not None else None
        if view.get("stage") == packages.TEXT_STATE:
            made = workshop.built(path)
            view["studioProject"] = made if made and self.library.resolve(made) is not None else None

    def build_workshop(self, value: str) -> dict[str, Any]:
        """“Dựng xưởng” (workshop.py): cuốn sách đang chờ xưởng thành một dự án Studio mới, chưa chạy."""
        self._mutating()
        path = self._listenable(value)
        if not self.capabilities()["toolchain"]:
            raise ApiError(HTTPStatus.CONFLICT, "Cần cài Studio để dựng xưởng")
        try:
            result = workshop.build(path, self.library.root, lambda paths, title, narrator: self._create_book(
                {"narrator": narrator}, paths, title, None))
        except workshop.WorkshopError as error:
            raise ApiError(HTTPStatus.CONFLICT, str(error)) from error
        except ValueError as error:  # dây chuyền từ chối tạo (không có chữ nào dùng được...)
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error
        project = result.pop("project")
        return {"id": book_id(project), **result}

    def listen_book(self, value: str) -> dict[str, Any]:
        path = self._listenable(value)
        self.sync_remote_state(value, wait=True)
        if packages.is_package(path):
            view = packages.listen(path, value, self.listening.get(value))
            self._built_workshop(view, path)
        else:
            view = listen_view.book(path, value, self.summary(path), self.listening.get(value))
        view["records"] = self.listening.records(value)  # hồ sơ nghe gắn với cuốn này (webui/listening.py)
        view["capabilities"] = self.capabilities(path)
        if view["capabilities"].get("sync"):
            view["editsSync"] = remote_books.edits_state(path)
        return view

    def voices(self) -> list[dict[str, Any]]:
        from ..voice_catalog import DEFAULT_NARRATOR_BY_GENDER, narrator_presets

        defaults = set(DEFAULT_NARRATOR_BY_GENDER.values())
        return [
            {
                "name": preset["name"],
                "gender": {"male": "Nam", "female": "Nữ"}.get(preset["gender"], ""),
                "region": preset["region"],
                "style": {"tu_nhien": "Tự nhiên", "doc_truyen": "Kể chuyện"}.get(preset["style"], preset["style"]),
                "recommended": preset["name"] in defaults,
                "preview": preview_file(preset["name"]) is not None,
            }
            for preset in narrator_presets()
        ]

    def voice_file(self, name: str) -> Path | None:
        return preview_file(name)


# ---- HTTP ------------------------------------------------------------------------------------------------

Route = tuple[str, re.Pattern[str], Callable[..., Any]]


class Handler(BaseHTTPRequestHandler):
    server_version = "ABook"
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
            raw = self.rfile.read(length)
            self._body_read = True
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, "JSON không hợp lệ") from exc
        return data if isinstance(data, dict) else {}

    def _send_file(self, path: Path, *, cache: bool = False) -> None:
        size = path.stat().st_size
        content_type = (TYPES.get(path.suffix.lower()) or music_plan.TRACK_TYPES.get(path.suffix.lower())
                        or mimetypes.guess_type(path.name)[0] or "application/octet-stream")
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

    def _export_root(self, body: dict[str, Any]) -> Path:
        """Thư mục mọi kiểu xuất ghi vào: nơi người dùng chọn (`target`), không thì "Đã xuất" trong thư viện."""
        target = self._target(body)
        return Path(target) if target else Path(self.app.preferences.get()["libraryRoot"]) / "Đã xuất"

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
        self._body_read = False
        try:
            self._route(method)
        finally:
            self._drain_body()

    def _drain_body(self) -> None:
        """Thân yêu cầu mà handler không đọc (nút Huỷ, "Tải công cụ"... giao diện vẫn gửi `{}`) nằm lại trong kết nối giữ sống: không bỏ đi thì yêu cầu kế
        tiếp trên kết nối ấy đọc ra dòng đầu `{}GET /...` và nhận 501."""
        if self._body_read:
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            self.close_connection = True  # thân lớn / hỏng: không đọc, đóng kết nối sau câu trả lời
        elif length:
            self.rfile.read(length)

    def _route(self, method: str) -> None:
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
        except sqlite3.DatabaseError as error:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": broken_reason(error)})
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

    def get_app(self, query: dict[str, list[str]]) -> None:
        prefs = self.app.preferences.get()
        # `?book=<mã>`: khả năng của máy này với CUỐN ấy (workshop, link); không có thì chỉ `toolchain` có nghĩa.
        wanted = (query.get("book") or [""])[0]
        located = self.app.library.resolve_listenable(self.app.library.canonical(wanted)) if wanted else None
        self._send_json(HTTPStatus.OK, {
            "capabilities": self.app.capabilities(located),
            "version": self.app.version,
            "readOnly": self.app.read_only,
            "dialogs": self.app.dialogs is not None,
            # App Windows đóng gói: bản mới vỏ tìm thấy ({version, notes}), hay None; Studio đã cài chưa (None: bản dev,
            # Studio chính là runtime cạnh mã nguồn).
            "update": self.app.update,
            "studio": None if self.app.studio is None else {"installed": self.app.studio.installed(),
                                                             "outdated": bool(self.app.studio.outdated()),
                                                             "damaged": bool(self.app.studio.damaged())},
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
        # Cuốn không có xưởng: danh sách ý muốn đang chờ Studio trong lớp sửa (book_wishes.pending_details).
        project = self.app._editable(value)
        if packages.is_package(project):
            self._send_json(HTTPStatus.OK, book_wishes.pending_details(project, book_edits.load(project).get("wishes")))
            return
        with closing(store.connect(project)) as connection:
            row = connection.execute("SELECT updated_at FROM book WHERE id=1").fetchone()
        since = store.changes_since(project, float(row["updated_at"] or 0) if row is not None else 0.0)
        self._send_json(HTTPStatus.OK, store.pending_details(project, since))

    def get_wishes(self, _query: dict[str, list[str]], value: str) -> None:
        # Trang đọc của cuốn không có xưởng: câu nào đang có ý muốn chờ Studio (book_wishes.by_line). Cuốn có xưởng ghi thẳng
        # yêu cầu vào dự án (overrides.json) nên không có ý muốn nào ở đây.
        project = self.app._editable(value)
        wishes = book_edits.load(project).get("wishes") if packages.is_package(project) else None
        self._send_json(HTTPStatus.OK, book_wishes.by_line(project, wishes))

    def post_pending_withdraw(self, _query: dict[str, list[str]], value: str) -> None:
        # Bỏ một thay đổi khỏi hộp "Áp dụng N thay đổi" trước khi áp (soát UX a6 01-10: muốn bỏ một mục thì phải đi tìm lại
        # đúng thẻ / đúng câu ở ba tab khác nhau). Chỉ khi sách KHÔNG chạy: đang chạy thì dây chuyền có thể đang áp chính
        # yêu cầu ấy ở ranh giới chương. Yêu cầu từng thay một yêu cầu cũ thì yêu cầu cũ trở lại (withdraw_requests).
        self.app._mutating()
        path = self.app._editable(value)
        package = packages.is_package(path)
        if not package and (self.app.runner.running(path) or self.app.jobs.starting(path)):
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
        if package:
            mine = book_wishes.made_at(path, section, group or [key], requested_at)
        else:
            mine = listener_overrides.requests_made_at(listener_overrides.read_overrides(path), section, group or [key], requested_at)
        if not mine:
            raise ApiError(HTTPStatus.CONFLICT, "Thay đổi này vừa được thay bằng một lựa chọn sau - mở lại hộp để xem.")
        if package:
            book_wishes.withdraw(path, section, list(mine), requested_at)  # cả bí danh của lần "Gộp vào…" ấy
        elif section == "retakes":
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
        path = self.app._editable(value)
        body = self._body()
        source = str(body.get("from", "")).strip()[:200]
        target = str(body.get("into", "")).strip()[:200]
        if not source or not target or aliases.key(source) == aliases.key(target):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Chọn hai người khác nhau")
        if packages.is_package(path):
            # Cuốn không có xưởng: mọi câu nói của người này thành ý muốn "là lời của người kia" + bí danh, chờ Studio.
            index, cast = book_wishes.Lines(path), book_wishes.people(path)
            found = book_wishes.speaker_lines(index, cast, source)
            if not found:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Người này không còn câu nói nào để gộp")
            problem = book_wishes.speaker_problem(index, cast, found[0][0], found[0][1], target)
            if problem is not None:
                raise ApiError(HTTPStatus.BAD_REQUEST, SPEAKER_PROBLEMS.get(problem, "Không gộp được vào người này"))
            now = time.time()
            book_wishes.request_speakers(path, found, target, now=now)
            book_wishes.request_alias(path, source, target, now=now)
            self._send_json(HTTPStatus.OK, {"lines": len(found), "requestedAt": now})
            return
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

    def post_rename_character(self, _query: dict[str, list[str]], value: str) -> None:
        # Tab Nhân vật: "Đổi tên" - chỉ cái tên trên màn hình (names.json cạnh sổ dự án), không đụng sổ nhân vật, giọng hay
        # audio, nên có hiệu lực ngay chứ không chờ "Áp dụng". Tên rỗng hay đúng tên gốc là trở về tên gốc.
        self.app._mutating()
        path = self.app._editable(value)
        body = self._body()
        character = str(body.get("character", "")).strip()[:200]
        if not character or character.upper() == "NARRATOR":
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu nhân vật")
        new_name = body.get("name")
        new_name = new_name if isinstance(new_name, str) else ""  # null / số / danh sách = bỏ tên đã đặt, không phải chữ "None"
        if packages.is_package(path):
            self._send_json(HTTPStatus.OK, book_edits.set_character_name(path, character, new_name))
            return
        original = store.original_name(path, character)
        if original is None:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Không có nhân vật này trong sách")
        renames.set_name(path, character, new_name, original)
        now_shown = renames.shown(path, character)
        self._send_json(HTTPStatus.OK, {"character": character, "name": now_shown or original,
                                        "original": original, "renamed": bool(now_shown)})

    def post_chapter_retake(self, _query: dict[str, list[str]], value: str, chapter: str) -> None:
        # Menu "…" của một chương: thu lại MỌI câu đã thu của chương bằng hạt giống mới (soát UX a5/a6 01-10: cả chương nghe
        # không ổn thì phải bấm "Cần thu lại" từng câu). Cùng đường với "Cần thu lại" một câu (overrides.json `retakes`),
        # cùng một mốc thời gian để hộp "Áp dụng" coi là một thay đổi; dây chuyền áp ở ranh giới như mọi yêu cầu.
        self.app._mutating()
        path = self.app._editable(value)
        if packages.is_package(path):
            found = book_wishes.chapter_lines(book_wishes.Lines(path), int(chapter))
            if not found:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Chương này chưa có câu nào đã thu để thu lại.")
            now = time.time()
            book_wishes.request_retakes(path, found, now=now)
            self._send_json(HTTPStatus.OK, {"lines": len(found), "requestedAt": now})
            return
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

    def get_precast(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.precast_view(value))

    def put_precast(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.set_precast_wait(value, self._body().get("wait") is True))

    def delete_listen_book(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.remove_imported(value, undo=True))

    def put_title(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.rename(value, str(self._body().get("title") or "")))

    def put_author(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.set_author(value, str(self._body().get("author") or "")))

    def put_chapter_title(self, _query: dict[str, list[str]], value: str, chapter: str) -> None:
        # Đổi tên một chương (trang nghe, điện thoại): `title` (nhãn, "Chương 12") và/hay `subtitle` (tên phụ, "" là bỏ);
        # `revert` hay cả hai trống là trở về tên gốc. Dự án: chapter_titles.json cạnh sổ; cuốn nhập từ file: lớp sửa.
        self.app._mutating()
        path = self.app._editable(value)
        body = self._body()
        title = None if body.get("revert") else body.get("title")
        subtitle = None if body.get("revert") else body.get("subtitle")
        if (title is not None and not isinstance(title, str)) or (subtitle is not None and not isinstance(subtitle, str)):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Tên chương phải là chữ")
        if packages.is_package(path):
            self._send_json(HTTPStatus.OK, book_edits.set_chapter_title(path, int(chapter), title, subtitle))
            return
        number = int(chapter)
        if not any(item["id"] == number for item in store.chapters(path)):
            raise ApiError(HTTPStatus.NOT_FOUND, "Không có chương này trong sách")
        clean_title = book_edits.clean_text(title, store.TITLE_MAX) if title is not None else ""
        clean_subtitle = book_edits.clean_text(subtitle, store.TITLE_MAX) if subtitle is not None else None
        store.set_chapter_title(path, number, clean_title, clean_subtitle)
        shown = next(item for item in store.chapters(path) if item["id"] == number)
        self._send_json(HTTPStatus.OK, {"chapterId": number, "title": shown["displayTitle"], "subtitle": shown["subtitle"],
                                        "fullTitle": shown["fullTitle"]})

    def get_edits(self, _query: dict[str, list[str]], value: str) -> None:
        # "N thay đổi" của người nghe: `applied` - đã áp trên cuốn nhập từ file (lớp sửa); `waiting` - phần sửa trong file
        # `.abook` vừa mở ra đúng dự án của máy này, chờ người dùng đồng ý áp (book_edits.fold).
        path = self.app._editable(value)
        if packages.is_package(path):
            edits = book_edits.load(path)
            self._send_json(HTTPStatus.OK, {"applied": book_edits.count_applied(edits), "waiting": 0,
                                            "wishes": book_edits.count_wishes(edits)})
        else:
            self._send_json(HTTPStatus.OK, {"applied": 0, "waiting": book_edits.count(book_edits.incoming(path))})

    def delete_edits(self, _query: dict[str, list[str]], value: str) -> None:
        # "Bỏ mọi thay đổi" của cuốn nhập từ file: sách trở về như người làm sách đã đóng gói. Dự án: bỏ phần sửa đang chờ.
        self.app._mutating()
        path = self.app._editable(value)
        if packages.is_package(path):
            book_edits.clear(path)
        else:
            book_edits.dismiss_incoming(path)
        self._send_json(HTTPStatus.OK, {"applied": 0, "waiting": 0})

    def post_edits_fold(self, _query: dict[str, list[str]], value: str) -> None:
        # Người dùng đồng ý "N thay đổi - áp vào dự án?": áp phần sửa của file `.abook` vào dự án bằng chính các hàm Studio dùng.
        self.app._mutating()
        path = self.app._editable(value)
        if not store.is_project(path):
            raise ApiError(HTTPStatus.CONFLICT, "Chỉ dự án trên máy này mới áp được thay đổi từ file")
        report = book_edits.fold(path, self.app.my_music)
        if report["music"]:
            try:
                self.app._music_after_change(value)
            except (music_catalog.CatalogError, OSError):
                pass  # mất mạng: lựa chọn đã lưu, rãnh nhạc dựng lại lần sau
        self._send_json(HTTPStatus.OK, report)

    def get_edits_inbox(self, _query: dict[str, list[str]], value: str) -> None:
        # Hộp thư thay đổi từ điện thoại (edits_inbox.py): ý muốn chờ Studio của thiết bị chưa được điều khiển sản xuất - chờ chủ
        # máy "Áp dụng" hay "Bỏ qua" từng mục / từng thiết bị. Dự án của máy này mới có.
        path = self.app._book(value)
        self._send_json(HTTPStatus.OK, edits_inbox.view(path))

    def _inbox_target(self, value: str) -> tuple[Path, str, list[str] | None]:
        self.app._mutating()
        path = self.app._book(value)
        body = self._body()
        device = str(body.get("device") or "")
        items = body.get("items")
        if not device:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu thiết bị")
        if items is not None and not (isinstance(items, list) and all(isinstance(item, str) for item in items)):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Danh sách mục không hợp lệ")
        return path, device, items

    def post_edits_inbox_apply(self, _query: dict[str, list[str]], value: str) -> None:
        # "Áp dụng" một mục (`items`) hay mọi mục của một thiết bị: thành yêu cầu của dự án, vào "Áp dụng N thay đổi" - chưa chạy gì.
        path, device, items = self._inbox_target(value)
        self._send_json(HTTPStatus.OK, edits_inbox.apply(path, device, items))

    def post_edits_inbox_skip(self, _query: dict[str, list[str]], value: str) -> None:
        path, device, items = self._inbox_target(value)
        self._send_json(HTTPStatus.OK, edits_inbox.skip(path, device, items))

    def post_workshop(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.CREATED, self.app.build_workshop(value))

    def post_save(self, _query: dict[str, list[str]], value: str) -> None:
        # "Lưu" / "Lưu thành…" một cuốn nhập từ file: đóng lại thành file mới kèm thay đổi của người nghe. `as` "abook" (phiên bản
        # 4 nếu có thay đổi) hay "abookproj" (cuốn từ `.abookproj` giữ xưởng của nó, copy nguyên byte; cuốn từ `.abook` thành
        # file "chờ dựng xưởng"); không nói thì giữ đúng loại file cuốn đã đến. Ra thư mục xuất (như "Xuất"), hay `target`.
        path = self.app._editable(value)
        body = self._body()
        if not packages.is_package(path):
            raise ApiError(HTTPStatus.CONFLICT, "Dự án có xưởng: dùng nút Xuất (file sách .abook hay dự án .abookproj)")
        kind = str(body.get("as") or ("abookproj" if packages.workshop_state(path) else "abook"))
        if kind not in ("abook", "abookproj"):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Loại file không biết")
        root = self._export_root(body)
        title = str(packages.edited_manifest(path).get("title") or path.name)
        try:
            if kind == "abookproj":
                out = projectfile.repack(path, root / projectfile.default_name(title))
            else:
                out = bookfile.repack(path, root / bookfile.default_name(title))
        except (bookfile.BookFileError, projectfile.ProjectFileError) as error:
            raise ApiError(HTTPStatus.CONFLICT, str(error)) from error
        self.app.exports.add(str(out.parent))
        self._send_json(HTTPStatus.OK, {"file": str(out), "folder": str(out.parent), "size": out.stat().st_size,
                                        "edits": book_edits.count(book_edits.load(path))})

    def delete_book(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.delete(value, undo=True))

    def post_trash_undo(self, _query: dict[str, list[str]], token: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.undo_trash(token))

    def post_reveal(self, _query: dict[str, list[str]], value: str) -> None:
        actions.reveal(self.app._book(value))
        self._send_json(HTTPStatus.OK, {"ok": True})

    def _series_parts(self, value: str, body: dict[str, Any]) -> list[Path] | None:
        """"Cả bộ" trong hộp Xuất: các phần của cuốn (continuation.series_parts), None khi xuất riêng phần này."""
        if not body.get("series"):
            return None
        parts = continuation.series_parts(self.app._book(value), self.app.library.projects())
        if len(parts) < 2:
            raise ApiError(HTTPStatus.CONFLICT, "Cuốn này chưa có phần nào khác để xuất cùng")
        return parts

    def post_export(self, _query: dict[str, list[str]], value: str) -> None:
        from .export import export_book, export_series

        project = self.app._book(value)
        body = self._body()
        root = self._export_root(body)
        parts = self._series_parts(value, body)
        try:
            if parts is None:
                result = export_book(project, root, cover=body.get("cover"))
            else:
                result = export_series(parts, root, lambda part, folder, label: export_book(
                    part, folder, cover=body.get("cover"), folder_name=label))
                result["files"] = sum(part["files"] for part in result["parts"])
        except ValueError as error:
            raise ApiError(HTTPStatus.CONFLICT, str(error)) from error
        self.app.exports.add(result["folder"])
        self._send_json(HTTPStatus.OK, result)

    def _bookfile_packer(self, value: str) -> Callable[[], dict[str, Any]]:
        """Đọc yêu cầu xuất `.abook` (thuộc luồng yêu cầu: thân, `target`, các phần của bộ) và trả việc đóng gói chưa chạy: gọi nó
        thì ghi file, trả {file, folder, size...} và ghi nhớ thư mục cho "Mở thư mục". Lỗi đóng gói/đầu vào ném ApiError 409."""
        # Một cuốn trong một file (bookfile.py) - mở bằng app ở máy khác, gửi cho người khác. Cả bộ: `single` (mặc định của
        # giao diện) gộp mọi phần vào MỘT file phiên bản 3 (bookfile.pack_series); không thì mỗi phần một file trong thư
        # mục bộ - cần khi thẻ nhớ / USB FAT32 không chứa nổi file trên 4 GiB.
        from .export import export_series, export_series_file, free_path

        project = self.app._book(value)
        body = self._body()
        root = self._export_root(body)
        parts = self._series_parts(value, body)
        single = bool(body.get("single"))
        app = self.app

        def run() -> dict[str, Any]:
            try:
                with app.music_exporting(app.music_key(project), parts or [project]) as music:
                    def pack(part: Path, folder: Path, name: str) -> dict[str, Any]:
                        path = bookfile.pack(part, free_path(folder / bookfile.default_name(name)), music_track=music)
                        return {"file": str(path), "size": path.stat().st_size}

                    if parts is None:
                        path = pack(project, root, store.summarize(project)["title"] or project.name)
                        result = {**path, "folder": str(Path(path["file"]).parent)}
                    elif single:
                        result = export_series_file(parts, root, lambda listed, file: bookfile.pack_series(
                            listed, file, music_track=music))
                    else:
                        result = export_series(parts, root, pack)
                        result["size"] = sum(part["size"] for part in result["parts"])
            except export_jobs.Cancelled as error:
                raise ApiError(HTTPStatus.CONFLICT, "Đã huỷ xuất.", reason="cancelled") from error
            except (bookfile.BookFileError, ValueError) as error:
                raise ApiError(HTTPStatus.CONFLICT, str(error)) from error
            app.exports.add(result["folder"])
            return result

        return run

    def post_bookfile(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self._bookfile_packer(value)())

    def post_bookfile_job(self, _query: dict[str, list[str]], value: str) -> None:
        # Cùng việc đóng gói của `post_bookfile` nhưng chạy nền: trả ngay trạng thái (có mã), `get_bookfile_job` hỏi tiếp - tải lại
        # trang giữa chừng hay sau khi xong vẫn hỏi lại được (export_jobs.py). Đang có lượt chạy cho cuốn này thì trả lượt ấy.
        run = self._bookfile_packer(value)
        self._send_json(HTTPStatus.ACCEPTED, self.app.bookfile_jobs.start(str(self.app._book(value)), run))

    def get_bookfile_job(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.export_job_status(self.app.bookfile_jobs, value))

    def post_m4b_job(self, _query: dict[str, list[str]], value: str) -> None:
        # Cả cuốn thành một file `.m4b` có mục lục chương (export.export_m4b) - việc nền như "Xuất file sách": giải mã và mã
        # hoá lại cả cuốn mất vài phút với sách dài. Hỏi trạng thái bằng GET; đang có lượt chạy cho cuốn này thì trả lượt ấy.
        from .export import export_m4b

        project = self.app._book(value)
        body = self._body()
        root = self._export_root(body)
        app = self.app

        def run() -> dict[str, Any]:
            result = export_m4b(project, root, cover=body.get("cover"))
            app.exports.add(result["folder"])
            return result

        self._send_json(HTTPStatus.ACCEPTED, self.app.m4b_jobs.start(str(project), run))

    def get_m4b_job(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.export_job_status(self.app.m4b_jobs, value))

    # ---- xuất sách nói của sách Nghe ngay (listen_export.py) --------------------------------------------------------------

    def _audiobook_inputs(self, value: str, voice: Any) -> tuple[Path, listen_export.Reading, list[listen_export.Chapter]]:
        """Cuốn, cách đọc (giọng + gốc Nhật / Hàn + cách đọc riêng - đúng thứ trình phát dùng) và các chương của một lượt xuất sách nói. Chỉ sách Nghe ngay
        (chỉ có chữ, nằm trên máy này); sách Studio đã có audio thì xuất MP3 / M4B có sẵn."""
        path = self.app._listenable(value)
        if not packages.is_package(path) or not packages.text_book(packages.manifest(path)):
            raise ApiError(HTTPStatus.CONFLICT, "Chỉ sách chỉ có chữ (EPUB, TXT...) mới xuất sách nói ở đây")
        if remote_books.remote_of(packages.manifest(path)) is not None:
            raise ApiError(HTTPStatus.CONFLICT, "Sách này lấy từ máy tính khác - xuất sách nói ở máy ấy")
        if not isinstance(voice, str) or not voice:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu giọng đọc")
        try:
            self.app.readaloud._resolve(voice)
        except VoiceError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error), reason=error.reason) from error
        body = {"bookId": value}
        reading = listen_export.Reading(voice, self._reading_origin(body), self._book_readings(body))
        return path, reading, listen_export.load_chapters(path)

    def get_audiobook_plan(self, query: dict[str, list[str]], value: str) -> None:
        # Cho hộp "Xuất sách nói": số chương / chữ / giờ nghe, ước thời gian máy làm (giọng đã đo tốc độ), chương đã làm sẵn từ lần trước, và ffmpeg đã có chưa.
        voice = (query.get("voice") or [""])[0]
        _path, reading, chapters = self._audiobook_inputs(value, voice)
        info = listen_export.plan(chapters, reading, listen_export.work_folder(self.app.export_work_dir, value), self.app.readaloud.speed(voice))
        self._send_json(HTTPStatus.OK, {**info, "ffmpeg": ffmpeg_setup.status()})

    def post_audiobook_job(self, _query: dict[str, list[str]], value: str) -> None:
        # Việc nền như "Xuất M4B", có tiến độ (chương i/N, %, ước còn lại) và Huỷ; tải lại trang vẫn hỏi lại được. Đang có lượt cho cuốn này thì trả lượt ấy.
        self.app._mutating()
        body = self._body()
        fmt = body.get("format")
        if fmt not in listen_export.FORMATS:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Chỉ xuất được MP3 hoặc M4B")
        path, reading, chapters = self._audiobook_inputs(value, body.get("voice"))
        if not chapters:
            raise ApiError(HTTPStatus.CONFLICT, "Sách chưa có chương nào có chữ để đọc")
        if not ffmpeg_setup.ready():
            raise ApiError(HTTPStatus.CONFLICT, "Máy này chưa có công cụ ghép âm thanh (ffmpeg) - tải nó trong hộp Xuất sách nói rồi bấm lại")
        root = self._export_root(body)
        cover = body.get("cover") if isinstance(body.get("cover"), str) else None
        app = self.app
        jobs = app.listen_exports
        key = str(path)

        def run() -> dict[str, Any]:
            result = listen_export.export_audiobook(
                app.readaloud, path, root, app.export_work_dir, fmt=fmt, reading=reading, book_id=value, cover_drawn=cover,
                progress=lambda **fields: jobs.update(key, **fields), cancelled=lambda: jobs.cancelled(key))
            app.exports.add(result["folder"])
            return result

        self._send_json(HTTPStatus.ACCEPTED, jobs.start(key, run))

    def get_audiobook_job(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.listen_exports.status(str(self.app._listenable(value))))

    def post_audiobook_cancel(self, _query: dict[str, list[str]], value: str) -> None:
        # "Huỷ": việc dừng ở chỗ an toàn kế (giữa hai đoạn); chương đã ghép được giữ cho lần xuất sau.
        self.app._mutating()
        jobs = self.app.listen_exports
        key = str(self.app._listenable(value))
        jobs.cancel(key)
        self._send_json(HTTPStatus.OK, jobs.status(key))

    def get_export_jobs(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.running_exports())

    def get_ffmpeg(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, ffmpeg_setup.status())

    def post_ffmpeg(self, _query: dict[str, list[str]]) -> None:
        # Người dùng bấm tải công cụ ghép âm thanh (không bao giờ tự tải).
        self.app._mutating()
        ffmpeg_setup.start()
        self._send_json(HTTPStatus.OK, ffmpeg_setup.status())

    def post_ffmpeg_cancel(self, _query: dict[str, list[str]]) -> None:
        self.app._mutating()
        ffmpeg_setup.cancel()
        self._send_json(HTTPStatus.OK, ffmpeg_setup.status())

    def get_word_timings(self, _query: dict[str, list[str]], value: str) -> None:
        # "Căn từ cho sách đã làm": tiến độ + số câu đã có mốc chữ (word_timing.Job.status).
        self._send_json(HTTPStatus.OK, self.app.word_jobs.status(self.app._book(value)))

    def post_word_timings(self, _query: dict[str, list[str]], value: str) -> None:
        # Căn mọi chương của sách đã làm rồi đóng lại file sách trong `output/` kèm mốc chữ (việc nền; hỏi tiến độ bằng GET).
        project = self.app._book(value)
        if self.app.runner.running(project) or self.app.jobs.starting(project):
            raise ApiError(HTTPStatus.CONFLICT, "Sách đang chạy - căn từng chữ khi nó đã chạy xong hoặc đã dừng.")
        if not word_timing.enabled():
            raise ApiError(HTTPStatus.CONFLICT, "Căn từng chữ đang bị tắt trên máy này.")

        def repack() -> Path:
            return bookfile.pack(project, project / "output" / bookfile.default_name(store.summarize(project)["title"] or project.name),
                                 music_track=self.app.music_export_source())

        self._send_json(HTTPStatus.ACCEPTED, self.app.word_jobs.start(project, repack))

    def _music_key(self, query: dict[str, list[str]], value: str) -> str:
        """Khoá nhạc của lượt xuất đang hỏi: `?kind=projectfile` là `.abookproj`, không có là `.abook`."""
        kind = "projectfile" if (query.get("kind") or [""])[0] == "projectfile" else "bookfile"
        return self.app.music_key(self.app._book(value), kind)

    def get_music_export(self, query: dict[str, list[str]], value: str) -> None:
        # Hộp Xuất hỏi giữa lúc đóng gói: đang tải nhạc nền bài thứ mấy / tổng số.
        self._send_json(HTTPStatus.OK, self.app.music_export_status(self._music_key(query, value)))

    def post_music_export_cancel(self, query: dict[str, list[str]], value: str) -> None:
        # "Huỷ" xuất có nhạc nền: dừng trước bài kế phải tải, không ghi file sách nào.
        self.app._mutating()
        self._send_json(HTTPStatus.OK, {"cancelling": self.app.cancel_music_export(self._music_key(query, value))})

    def get_export_size(self, query: dict[str, list[str]], value: str) -> None:
        # Cỡ ước lượng của bản xuất `.abook` (audio các chương nghe được; `series=1`: cả bộ) - hộp Xuất báo trước và cảnh
        # báo khi quá 4 GiB (thẻ nhớ / USB FAT32 không chứa nổi một file lớn hơn).
        from .export import audio_bytes

        projects = self._series_parts(value, {"series": (query.get("series") or ["0"])[0] == "1"}) or [self.app._book(value)]
        # Cỡ gồm cả nhạc nền đóng kèm (bài đã có trong bộ đệm - không tải trong lượt hỏi); `musicPending` = bài chưa tải.
        size, pending = audio_bytes(projects, self.app.music_track_cached)
        self._send_json(HTTPStatus.OK, {"bytes": size, "parts": len(projects), "musicPending": pending})

    def _projectfile_packer(self, value: str) -> Callable[[], dict[str, Any]]:
        """Đọc yêu cầu xuất `.abookproj` (thuộc luồng yêu cầu) và trả việc đóng gói chưa chạy: gọi nó thì ghi file, trả {file, folder, size,
        missingSources} và ghi nhớ thư mục cho "Mở thư mục". Hỏng thì ném `projectfile.ProjectFileError`, huỷ thì `export_jobs.Cancelled`
        (chỗ gọi đổi thành lời báo). Dùng chung cho `post_projectfile` (đồng bộ) và `post_projectfile_job` (nền, có tiến độ)."""
        from .export import free_path

        project = self.app._book(value)
        root = self._export_root(self._body())
        title = store.summarize(project)["title"] or project.name
        app = self.app
        key = str(project)
        app.export_folders.remember(root)
        music_key = app.music_key(project, "projectfile")

        def progress(phase: str, done: int, total: int) -> None:
            if app.projectfile_jobs.cancelled(key):
                raise export_jobs.Cancelled()
            app.projectfile_jobs.update(key, phase=phase, done=done, total=total)

        def run() -> dict[str, Any]:
            with app.music_exporting(music_key, [project]) as music:
                path = projectfile.pack(project, free_path(root / projectfile.default_name(title)),
                                        running=app.runner.running(project), music_track=music, progress=progress)
            with projectfile.ProjectFile(path) as packed:
                missing = packed.missing_sources
            app.exports.add(str(path.parent))
            return {"file": str(path), "folder": str(path.parent), "size": path.stat().st_size, "missingSources": missing}

        return run

    def post_projectfile(self, _query: dict[str, list[str]], value: str) -> None:
        # Cả dự án trong một file (projectfile.py) - chuyển máy, sao lưu, làm tiếp ở chỗ khác.
        run = self._projectfile_packer(value)
        try:
            result = run()
        except export_jobs.Cancelled as error:
            raise ApiError(HTTPStatus.CONFLICT, "Đã huỷ xuất.", reason="cancelled") from error
        except projectfile.ProjectFileError as error:
            raise ApiError(HTTPStatus.CONFLICT, str(error)) from error
        self._send_json(HTTPStatus.OK, result)

    def post_projectfile_job(self, _query: dict[str, list[str]], value: str) -> None:
        # Cùng việc đóng gói chạy nền: trả ngay trạng thái (có mã); hỏi tiếp bằng GET (pha + đã/tổng, hay file ra), Huỷ bằng POST .../cancel.
        # Dự án 400 chương mất ~1,5 phút - đồng bộ thì trình duyệt đứng chờ không biết tiến độ. Một-lúc-một-cuốn: đang chạy thì trả lượt ấy.
        self._send_json(HTTPStatus.ACCEPTED, self.app.projectfile_jobs.start(str(self.app._book(value)), self._projectfile_packer(value)))

    def get_projectfile_job(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.export_job_status(self.app.projectfile_jobs, value))

    def post_projectfile_job_cancel(self, _query: dict[str, list[str]], value: str) -> None:
        # "Huỷ": dừng ở điểm kiểm kế (giữa hai file; hay trước bài nhạc kế phải tải), không để lại file nào - cả file tạm.
        self.app._mutating()
        key = str(self.app._book(value))
        self.app.projectfile_jobs.cancel(key)
        self.app.cancel_music_export(self.app.music_key(Path(key), "projectfile"))  # chỉ nhạc của chính việc gói dự án, không đụng việc xuất .abook
        self._send_json(HTTPStatus.OK, self.app.projectfile_jobs.status(key))

    def get_review(self, query: dict[str, list[str]], value: str) -> None:
        project = self.app._book(value)
        verdicts = self.app.reviews.get(value)
        self._send_json(HTTPStatus.OK, review_view(project, verdicts, include_minor=query.get("all") == ["1"]))

    def _view(self, value: str, name: str, make: Callable[[Path], Any]) -> Any:
        """Một màn chỉ đọc của xưởng: dự án có xưởng trên máy này thì tính từ sổ dự án; cuốn nhập từ `.abookproj` thì đọc bản chụp
        trong file (project_views.py, cùng JSON) - 404 nếu file không mang bản chụp ấy."""
        path = self.app._listenable(value)
        if not packages.is_package(path):
            return make(self.app._book(value))
        data = packages.view(path, name)
        if data is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "File dự án này không kèm bản chụp của màn đó")
        return data

    def get_work(self, query: dict[str, list[str]], value: str) -> None:
        # "Việc cần duyệt" (docs/STUDIO_REVIEW.md): chỗ máy nghi ngờ, xếp theo lợi trên mỗi lần bấm.
        # Câu đã chấm ở "Cần nghe lại" không còn là việc (phán quyết nằm ở reviews.json của máy này, không trong sổ dự án).
        view = self._view(value, "work", lambda root: work_items(root, self.app.reviews.get(value)))
        if (query.get("count") or [""])[0] == "1":
            # Nhãn của tab chỉ cần con số (việc đã quyết đang chờ áp dụng không còn là việc cần làm): không gửi/đọc cả danh sách vài MB.
            self._send_json(HTTPStatus.OK, {"count": open_count(view)})
            return
        self._send_json(HTTPStatus.OK, view)

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

    def post_music_download_cancel(self, _query: dict[str, list[str]], value: str) -> None:
        # "Huỷ tải" ở tab Nhạc: dừng lượt tải sẵn nhạc nền của cuốn (bài đang tải dở bỏ đi; trình phát vẫn tải bài khi cần).
        self.app._mutating()
        self.app.cancel_music_export(self.app.music_key(self.app._book(value), "warm"))
        self._send_json(HTTPStatus.OK, self.app.music_view(value))

    def post_music_moods(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.music_moods_compute(value))

    def get_music_moods_model(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.music_moods_model())

    def post_music_moods_model(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.music_moods_model_download())

    def get_music_alternatives(self, _query: dict[str, list[str]], value: str, key: str) -> None:
        try:
            self._send_json(HTTPStatus.OK, self.app.music_alternatives(value, key))
        except music_catalog.CatalogError as error:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, str(error)) from error

    def get_music_cues(self, _query: dict[str, list[str]], value: str, chapter: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.music_cues(value, int(chapter)))

    def get_music_playlist(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.music_playlist_queue(value))

    def get_music_playlists(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.music_playlists())

    def get_music_packaged(self, _query: dict[str, list[str]], value: str, name: str) -> None:
        path = self.app._listenable(value)
        # Sách mở từ file: bài trong gói. Dự án: bài "Nhạc của tôi" mà đoạn của chính cuốn này dùng (music_plan.track_file_named).
        target = (packages.music_file(path, f"music/{name}") if packages.is_package(path)
                  else music_plan.track_file_named(path, f"music/{name}", self.app.music_sync_source()))
        if target is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Không có bài nhạc này trong sách")
        self._send_file(target, cache=True)

    def get_my_music(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.my_music_view())

    def post_my_music_import(self, _query: dict[str, list[str]]) -> None:
        paths = self._body().get("paths")
        if not isinstance(paths, list):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu danh sách file nhạc")
        self._send_json(HTTPStatus.OK, self.app.my_music_import(paths))

    def post_my_music_module(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.my_music_module(scene=self._body().get("scene") is True))

    def post_my_music_module_cancel(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.my_music_cancel("module"))

    def post_my_music_precise_cancel(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.my_music_cancel("precise"))

    def post_my_music_reanalyse(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.my_music_reanalyse())

    def post_my_music_precise(self, _query: dict[str, list[str]]) -> None:
        enabled = self._body().get("enabled")
        if not isinstance(enabled, bool):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu enabled (true / false)")
        self._send_json(HTTPStatus.OK, self.app.my_music_precise(enabled))

    def post_my_music_precise_remove(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.my_music_precise_remove())

    def post_my_music_auto(self, _query: dict[str, list[str]], digest: str) -> None:
        body = self._body()
        auto = body.get("auto")
        if "auto" not in body or (auto is not None and auto not in music_local.AUTO_VALUES):
            raise ApiError(HTTPStatus.BAD_REQUEST, "auto phải là \"on\", \"off\" hay null")
        self._send_json(HTTPStatus.OK, self.app.my_music_auto(digest, auto))

    def post_my_music_analyze(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.my_music_analyze())

    def delete_my_music(self, _query: dict[str, list[str]], digest: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.my_music_remove(digest))

    def get_my_music_file(self, _query: dict[str, list[str]], digest: str) -> None:
        self._send_file(self.app.my_music_file(digest), cache=True)

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
        self._send_json(HTTPStatus.OK, self._view(value, "names", name_readings))

    def get_casting(self, _query: dict[str, list[str]], value: str) -> None:
        # Tab "Kịch bản" (casting_review.py): chương nào bao nhiêu câu thoại, bao nhiêu chỗ máy nghi, bao nhiêu câu đã quyết.
        self._send_json(HTTPStatus.OK, self._view(value, "casting", casting_chapters))

    def get_reading_reach(self, query: dict[str, list[str]], value: str) -> None:
        # Ô "Thêm cách đọc cho từ bất kỳ" (NameReadings.tsx): trước khi lưu, nói cách đọc sẽ chạm tới bao nhiêu câu (name_readings.reading_reach).
        surface = " ".join(((query.get("surface") or [""])[0]).split())[:80]
        if not surface:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu chữ cần xem")
        self._send_json(HTTPStatus.OK, reading_reach(self.app._book(value), surface))

    def get_casting_stamp(self, _query: dict[str, list[str]], value: str) -> None:
        # Hỏi nhẹ mỗi vài giây: lần ghi yêu cầu cuối (overrides.json) - đổi nghĩa là cửa sổ khác vừa sửa, tab Kịch bản tự làm mới (B19).
        self._send_json(HTTPStatus.OK, {"stamp": casting_stamp(self.app._book(value))})

    def get_casting_chapter(self, _query: dict[str, list[str]], value: str, chapter: str) -> None:
        if packages.is_package(self.app._listenable(value)):
            raise ApiError(HTTPStatus.NOT_FOUND, "File dự án không kèm từng câu của chương - đọc chữ trong sách")
        view = casting_chapter(self.app._book(value), int(chapter))
        if view is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Không có chương này")
        self._send_json(HTTPStatus.OK, view)

    def _checked_reading(self, body: dict[str, Any], surface: str) -> str:
        """Cách đọc người nghe gửi (`spokenForm`) cho tên `surface`, sau phép kiểm của dây chuyền - dùng chung cho "Lưu" và
        "Nghe thử": nghe được là lưu được."""
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
        return spoken

    def post_pronunciation_preview(self, _query: dict[str, list[str]], value: str) -> None:
        # "Nghe thử" trước khi lưu: thu thử một câu có tên ấy với cách đọc đang gõ - không ghi gì vào sách (reading_preview.py).
        self.app._mutating()
        path = self.app._book(value)
        body = self._body()
        surface = str(body.get("surface", "")).strip()[:80]
        spoken = self._checked_reading(body, surface)
        segment = body.get("segmentId")
        try:
            result = self.app.previews.preview(path, book_id(path), surface, spoken,
                                               int(segment) if isinstance(segment, int) and not isinstance(segment, bool) else None)
        except reading_preview.PreviewError as error:
            raise ApiError(error.status, error.message, reason=error.reason, **error.extra) from error
        self._send_json(HTTPStatus.OK, result)

    def post_voice_preview(self, _query: dict[str, list[str]], value: str) -> None:
        # "Nghe thử bằng câu của sách" (hộp "Đổi giọng", hộp "Áp dụng"): một câu của nhân vật đọc bằng giọng đang cân nhắc -
        # cùng tiến trình, hàng chờ, phép nhường card cho sách và bản cất như nghe thử cách đọc tên (reading_preview.py).
        self.app._mutating()
        path = self.app._book(value)
        body = self._body()
        character = str(body.get("character", "")).strip()[:200]
        preset = str(body.get("preset", "") or "").strip()[:120]
        if not character:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu nhân vật")
        if _needs_download(preset):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Giọng này cần tải thêm trước khi nghe thử")
        segment = body.get("segmentId")
        try:
            result = self.app.previews.voice_preview(
                path, book_id(path), character, preset=preset, gender=str(body.get("gender", "") or "").strip()[:10],
                avoid=str(body.get("avoid", "") or "").strip()[:200],
                segment_id=int(segment) if isinstance(segment, int) and not isinstance(segment, bool) else None)
        except reading_preview.PreviewError as error:
            message = VOICE_PROBLEMS.get(error.reason, error.message) if error.status == HTTPStatus.BAD_REQUEST else error.message
            raise ApiError(error.status, message, reason=error.reason, **error.extra) from error
        self._send_json(HTTPStatus.OK, result)

    def media_reading_preview(self, _query: dict[str, list[str]], value: str, key: str) -> None:
        target = self.app.previews.file(book_id(self.app._book(value)), key)
        if target is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Bản nghe thử này không còn - bấm Nghe thử lại.")
        self._send_file(target, cache=True)

    def post_pronunciation(self, _query: dict[str, list[str]], value: str) -> None:
        # Sửa cách đọc một tên. Giao diện KHÔNG ghi SQLite của sách: nó ghi mong muốn vào overrides.json, dây chuyền áp
        # ở ranh giới chương kế tiếp (hoặc lần chạy tới) và thu lại mọi câu đã thu có tên ấy - listener_overrides.py.
        self.app._mutating()
        path = self.app._editable(value)
        package = packages.is_package(path)  # không có xưởng: ý muốn vào lớp sửa (book_wishes), chờ Studio
        body = self._body()
        surface = str(body.get("surface", "")).strip()[:80]
        if body.get("withdraw") and package:
            self._withdraw(path, "pronunciations", [listener_overrides.surface_key(surface)] if surface else [], body)
            return
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
        spoken = self._checked_reading(body, surface)
        now = time.time()
        if package:
            book_wishes.request_pronunciation(path, surface, spoken, now=now)
            self._send_json(HTTPStatus.OK, {"surface": surface, "spokenForm": spoken, "requestedAt": now})
            return
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
        package = packages.is_package(path)
        mine = (book_wishes.made_at(path, section, keys, requested_at) if package
                else listener_overrides.requests_made_at(listener_overrides.read_overrides(path), section, keys, requested_at))
        if not mine:
            raise ApiError(HTTPStatus.CONFLICT, "Quyết định này đã được thay bằng một lựa chọn sau - không còn gì để hoàn tác.")
        if package:
            # Ý muốn chờ Studio chưa vào sách bao giờ: rút là xong, ý muốn nó thay (`replaced`) trở lại.
            removed = book_wishes.withdraw(path, section, list(mine), requested_at)
            self._send_json(HTTPStatus.OK, {"undone": len(removed), "restored": False})
            return
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
        path = self.app._editable(value)
        package = packages.is_package(path)
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
        if package:
            index, cast = book_wishes.Lines(path), book_wishes.people(path)
        for stable_id, text_sha256 in lines:
            problem = (book_wishes.speaker_problem(index, cast, stable_id, text_sha256, speaker, new_gender) if package
                       else store.speaker_request_problem(path, stable_id, text_sha256, speaker, new_gender))
            if problem is not None:
                if problem == listener_overrides.NO_VOICE and speaker == listener_overrides.UNNAMED:
                    # Sách chưa có nhóm "vai phụ không tên" nào để mượn giọng (nhóm ấy do bước phân tích tạo khi gặp vai như vậy).
                    raise ApiError(HTTPStatus.BAD_REQUEST, UNNAMED_PROBLEM)
                raise ApiError(HTTPStatus.BAD_REQUEST, SPEAKER_PROBLEMS.get(problem, "Không đổi được người nói câu này"))
        now = time.time()
        # Cửa sổ khác (hay máy khác) vừa sửa chính câu này: `seen` là điều giao diện này tưởng đang ghi cho từng câu ("" = chưa ai quyết).
        # Khác với điều thật sự đang ghi thì báo lại để người nghe biết mình vừa ghi đè (soát UX a23 B19) - vẫn ghi, không bao giờ chặn.
        elsewhere = {} if package else self._edited_elsewhere(path, lines, body.get("seen"))
        if package:
            book_wishes.request_speakers(path, lines, speaker, now=now, new_gender=new_gender)
            alias = str(body.get("alias", "") or "").strip()[:200]
            remembered = bool(alias) and book_wishes.request_alias(path, alias, speaker, now=now)
            self._send_json(HTTPStatus.OK, {"lines": len(lines), "speaker": speaker, "new": bool(new_gender),
                                            "alias": remembered, "requestedAt": now})
            return
        listener_overrides.request_speakers(path, lines, speaker, now=now, new_gender=new_gender)
        # Thẻ "Một người hai tên": ngoài các câu này, ghi luôn cấp TÊN (aliases.py) - phần sau của cuốn tự hiểu.
        alias = str(body.get("alias", "") or "").strip()[:200]
        remembered = bool(alias) and aliases.add(path, alias, speaker)
        # Thẻ 『』 với phạm vi "Cả cuốn": quy ước của cuốn (bracket_rule.py) - các phần sau tự áp trước khi phân vai.
        if body.get("bracketRule"):
            remembered = bracket_rule.save(path, speaker) or remembered
        self._send_json(HTTPStatus.OK, {"lines": len(lines), "speaker": speaker, "new": bool(new_gender),
                                        "alias": remembered, "requestedAt": now, "elsewhere": elsewhere})

    @staticmethod
    def _edited_elsewhere(path: Path, lines: list[tuple[str, str]], seen: Any) -> dict[str, str]:
        """{mã câu: người đang được ghi} cho những câu mà điều đang ghi trong overrides.json khác điều giao diện đã thấy (`seen`)."""
        if not isinstance(seen, dict):
            return {}
        recorded = {entry["stable_id"]: entry for entry in listener_overrides.speaker_requests(listener_overrides.read_overrides(path))}
        out: dict[str, str] = {}
        for stable_id, text_sha256 in lines:
            if stable_id not in seen:
                continue
            now_there = recorded.get(stable_id)
            actual = now_there["speaker"] if now_there is not None and now_there["text_sha256"] == text_sha256 else ""
            if actual != str(seen[stable_id] or ""):
                out[stable_id] = actual
        return out

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
        path = self.app._editable(value)
        package = packages.is_package(path)
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
        if package:
            if intensity is not None and not 0 <= intensity <= book_wishes.INTENSITY_MAX:
                raise ApiError(HTTPStatus.BAD_REQUEST, f"Cường độ phải từ 0 tới {book_wishes.INTENSITY_MAX}")
            problem = book_wishes.line_problem(book_wishes.Lines(path), book_wishes.people(path), stable_id, text_sha256,
                                               kind=kind, emotion=emotion, speaker=speaker, spoken=spoken)
        else:
            problem = store.line_request_problem(path, stable_id, text_sha256, kind=kind, emotion=emotion,
                                                 intensity=intensity, speaker=speaker, spoken=spoken)
        if problem is not None:
            raise ApiError(HTTPStatus.BAD_REQUEST, LINE_PROBLEMS.get(problem, "Không đổi được cách đọc câu này"))
        write = book_wishes.request_line if package else listener_overrides.request_line
        write(path, stable_id, text_sha256, kind=kind, emotion=emotion, intensity=intensity,
              speaker=speaker, spoken=spoken, now=time.time())
        self._send_json(HTTPStatus.OK, {"stableId": stable_id, "kind": kind, "emotion": emotion, "intensity": intensity,
                                        "spoken": spoken})

    def post_narrator_section(self, _query: dict[str, list[str]], value: str) -> None:
        # Thẻ "người kể của đoạn khác" (narrator_cards.py): quyết định lưu ở narrator_sections.json cạnh sổ dự án; dây chuyền
        # đọc lại ở mỗi lô phân tích chưa chạy. Chỉ dự án có xưởng trên máy này - cuốn nhập từ file không có phân tích để áp.
        self.app._mutating()
        path = self.app._book(value)
        try:
            result = narrator_cards.decide(path, self._body())
        except ValueError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error
        self._send_json(HTTPStatus.OK, result)

    def post_voice(self, _query: dict[str, list[str]], value: str) -> None:
        # Giọng / giới của MỘT nhân vật (thẻ "Nam hay nữ", "Chung giọng"): như người nói - ghi mong muốn vào overrides.json,
        # dây chuyền áp ở ranh giới chương; hỏi SQLite chỉ đọc bằng đúng phép dây chuyền dùng để từ chối tại chỗ.
        self.app._mutating()
        path = self.app._editable(value)
        package = packages.is_package(path)
        body = self._body()
        character = str(body.get("character", "")).strip()[:200]
        if body.get("withdraw"):
            self._withdraw(path, "voices", [listener_overrides.character_key(character)] if character else [], body)
            return
        preset = str(body.get("preset", "") or "").strip()[:120]
        gender = str(body.get("gender", "") or "").strip()[:10]
        avoid = str(body.get("avoid", "") or "").strip()[:200]
        if not character:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu nhân vật")
        if _needs_download(preset):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Giọng này cần tải thêm trước khi chọn")
        if package and not (preset or gender or avoid):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu giọng hoặc giới tính")
        problem = (book_wishes.voice_problem(book_wishes.people(path), character, gender=gender) if package
                   else store.voice_request_problem(path, character, preset=preset, gender=gender, avoid=avoid))
        if problem is not None:
            raise ApiError(HTTPStatus.BAD_REQUEST, VOICE_PROBLEMS.get(problem, "Không đổi được giọng nhân vật này"))
        now = time.time()
        write = book_wishes.request_voice if package else listener_overrides.request_voice
        write(path, character, preset=preset, gender=gender, avoid=avoid, now=now)
        self._send_json(HTTPStatus.OK, {"character": character, "preset": preset, "gender": gender,
                                        "avoid": avoid, "requestedAt": now})

    def post_review(self, _query: dict[str, list[str]], value: str) -> None:
        self.app._mutating()  # ghi reviews.json và (Cần thu lại) overrides.json - như mọi yêu cầu sửa khác
        body = self._body()
        verdict = body.get("verdict")
        if verdict not in (None, "ok", "redo"):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Phán quyết không hợp lệ")
        # Một câu (`stableId`) hay cả nhóm (`lines`: Shift-chọn ở tab Kịch bản) - cả nhóm cùng một mốc `now`, nên hộp "Áp dụng"
        # đếm một lần bấm là một thay đổi (store.BY_CLICK) và bỏ được cả nhóm.
        refs = body.get("lines")
        stable_ids = ([str(item.get("stableId", ""))[:80] for item in refs[:2000] if isinstance(item, dict)]
                      if isinstance(refs, list) else [str(body.get("stableId", ""))[:80]])
        project = self.app._editable(value)
        now = time.time()
        # Một câu: lời đáp `{ok}` như trước (điện thoại và hợp đồng ghi sẵn đáp y vậy); nhóm: thêm số câu + mốc để Hoàn tác.
        reply = (lambda count: {"ok": True, "lines": count, "requestedAt": now}) if isinstance(refs, list) else (lambda _count: {"ok": True})
        if packages.is_package(project):
            # Cuốn không có xưởng chưa có hàng đợi "Cần nghe lại": chỉ phần "Cần thu lại" - ý muốn chờ Studio.
            lines = book_wishes.Lines(project)
            asked: list[tuple[str, str]] = []
            for stable_id in stable_ids:
                found = lines.get(stable_id)
                if verdict == "redo" and found is not None and found[1].get("textSha256"):
                    asked.append((stable_id, str(found[1]["textSha256"])))
                elif verdict != "redo":
                    book_wishes.cancel_retake(project, stable_id)
            if asked:
                book_wishes.request_retakes(project, asked, now=now)
            self._send_json(HTTPStatus.OK, reply(len(asked)))
            return
        chapter_id = int(body.get("chapterId", 0))
        asked_count = 0
        for stable_id in stable_ids:
            self.app.reviews.set(value, stable_id, verdict, chapter_id)
            # "Cần thu lại" là một yêu cầu cho dây chuyền (overrides.json `retakes`: thu bằng hạt giống mới ở lần chạy tới -
            # sách đã xong: nút "Áp dụng thay đổi"); đổi ý thì bỏ yêu cầu chưa áp.
            text_sha256 = store.segment_text_sha256(project, stable_id)
            if verdict == "redo" and text_sha256:
                listener_overrides.request_retake(project, stable_id, text_sha256, now=now)
                asked_count += 1
            elif verdict != "redo":
                listener_overrides.cancel_retake(project, stable_id)
        self._send_json(HTTPStatus.OK, reply(asked_count))

    def put_cover(self, _query: dict[str, list[str]], value: str) -> None:
        self.app._mutating()
        path = self.app._editable(value)
        # Ảnh chụp điện thoại vài MB thành data URL còn to hơn 1/3: trần riêng cho đúng yêu cầu này.
        body = self._body(limit=covers.MAX_UPLOAD_BYTES * 4 // 3 + 4096)
        if packages.is_package(path):
            # Cuốn nhập từ file: bìa người nghe đặt nằm ở lớp sửa (edits/cover.jpg), bìa của người làm sách giữ nguyên.
            try:
                raw = (cover_search.download_image(str(body["url"])) if body.get("url")
                       else covers.decode_data_url(str(body.get("image", ""))))
            except covers.CoverError as exc:
                raise ApiError(HTTPStatus.BAD_REQUEST, str(exc)) from exc
            self._send_json(HTTPStatus.OK, {"cover": book_edits.set_cover(path, raw, now=int(time.time()))})
            return
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
        path = self.app._editable(value)
        if packages.is_package(path):
            book_edits.remove_cover(path)
        else:
            covers.remove_cover(path)
        self._send_json(HTTPStatus.OK, {"cover": None})

    def media_cover(self, _query: dict[str, list[str]], value: str) -> None:
        path = self.app.cover_file(self.app._listenable(value))
        if path is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Sách này chưa có ảnh bìa")
        self._send_file(path, cache=True)

    def post_reveal_export(self, _query: dict[str, list[str]]) -> None:
        folder = str(self._body().get("folder", ""))
        if folder not in self.app.exports:
            raise ApiError(HTTPStatus.FORBIDDEN, "Không mở được thư mục này")
        actions.reveal(Path(folder))
        self._send_json(HTTPStatus.OK, {"ok": True})

    def post_open_url(self, _query: dict[str, list[str]]) -> None:
        # Cửa sổ Tauri nuốt `target=_blank`: trang nhờ máy chủ mở liên kết ngoài. Chỉ http/https; đường này không có trong
        # remote_studio.ALLOWED nên thiết bị ở xa không bao giờ chạm tới.
        try:
            actions.open_url(str(self._body().get("url", "")))
        except ValueError as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(exc)) from exc
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

    def get_computers_bluetooth(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.paired_bluetooth())

    def post_computer_bluetooth(self, _query: dict[str, list[str]], computer: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.set_computer_bluetooth(computer, str(self._body().get("address") or "")))

    def post_computers_refresh(self, _query: dict[str, list[str]]) -> None:
        # Máy thức trả lời trong vài giây; máy đang ngủ thì trả về ngay với `waking`, việc hỏi chạy tiếp ở nền.
        self.app.refresh_remote(wait=True, patience=REFRESH_PATIENCE_SECONDS)
        self._send_json(HTTPStatus.OK, self.app.computers_view())

    def post_computer_stop_waiting(self, _query: dict[str, list[str]], computer: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.stop_waiting_computer(computer))

    def get_computer_reachable(self, _query: dict[str, list[str]], computer: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.computer_reachable(computer))

    def get_computer_unsent(self, _query: dict[str, list[str]], computer: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.unsent_computer_edits(computer))

    def delete_computer(self, query: dict[str, list[str]], computer: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.forget_computer(computer, (query.get("edits") or [""])[0]))

    def get_listen_library(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.listen_library())

    def post_open_book_file(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.open_book_file(str(self._body().get("path") or "")))

    def post_import_preview(self, _query: dict[str, list[str]]) -> None:
        body = self._body()
        self._send_json(HTTPStatus.OK, self.app.preview_text_book(str(body.get("path") or ""), body.get("splitChapters") is True, body.get("footnotes")))

    def post_import_book(self, _query: dict[str, list[str]]) -> None:
        body = self._body()
        self._send_json(HTTPStatus.OK, self.app.add_text_book(str(body.get("path") or ""), str(body.get("title") or ""),
                                                              body.get("separate") is True, body.get("splitChapters") is True,
                                                              body.get("chapters"), body.get("footnotes")))

    def get_chapter_text(self, _query: dict[str, list[str]], value: str, chapter: str) -> None:
        # Chữ của chương trong sách CHỈ-CÓ-CHỮ (texts/<mã>.txt): trang đọc dựng các đoạn từ đây (listen/textScript.ts).
        path = self.app._listenable(value)
        text = packages.chapter_text(path, int(chapter)) if packages.is_package(path) else None
        if text is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Chương này không có chữ riêng")
        self._send_json(HTTPStatus.OK, {"chapterId": int(chapter), "text": text})

    def get_suggestions(self, _query: dict[str, list[str]], value: str) -> None:
        # Gợi ý của bộ nhập sách cho một cuốn chỉ-chữ (dòng ghi công ở đầu chương, dòng ủng hộ / nguồn ở cuối chương), kèm chúng đang bỏ khỏi phần đọc hay chưa -
        # trang sách hiện những gợi ý còn chờ để người nghe chấp nhận bất cứ lúc nào.
        path = self.app._listenable(value)
        out: list[dict[str, Any]] = []
        if packages.is_package(path):
            for chapter in packages.edited_manifest(path).get("chapters") or []:
                if not isinstance(chapter, dict) or not isinstance(chapter.get("id"), int):
                    continue
                text = packages.chapter_text(path, chapter["id"])
                skipped = set(chapter.get("skip") or [])
                for line, _at_end in importers.chapter_credit_suggestions(text) if text else []:
                    out.append({"chapter": chapter["id"], "title": chapter.get("fullTitle") or chapter.get("title") or "",
                                "line": line, "skipped": line in skipped})
        self._send_json(HTTPStatus.OK, {"suggestions": out})

    def put_skip_line(self, _query: dict[str, list[str]], value: str) -> None:
        # Người nghe chấp nhận (hay bỏ chấp nhận) một gợi ý: dòng `line` của các chương `chapters` bị bỏ khỏi phần đọc - biến đổi để
        # đọc trong lớp sửa, chữ của sách không đổi.
        self.app._mutating()
        path = self.app._editable(value)
        body = self._body()
        if not packages.is_package(path):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Chỉ sách nhập từ file mới bỏ được dòng khỏi phần đọc.")
        chapters = body.get("chapters")
        if not isinstance(body.get("line"), str):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Dòng cần bỏ phải là chữ.")
        if not isinstance(chapters, list) or any(not isinstance(item, int) or isinstance(item, bool) for item in chapters):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Không có chương này trong sách")
        self._send_json(HTTPStatus.OK, {"skip": book_edits.set_skip_line(path, chapters, body["line"], body.get("skip") is not False)})

    def get_readings(self, _query: dict[str, list[str]], value: str) -> None:
        # "Cách đọc tên" của hộp sửa sách: cách đọc riêng người nghe đặt cho cuốn nhập từ file (lớp sửa `readings`).
        path = self.app._listenable(value)
        self._send_json(HTTPStatus.OK, book_edits.readings_view(book_edits.load(path) if packages.is_package(path) else {}))

    def put_readings(self, _query: dict[str, list[str]], value: str) -> None:
        # "Đọc từ này là…": đặt (hay bỏ - `spoken` rỗng) cách đọc riêng của một từ cho cả cuốn. Chỉ giọng đọc đổi, chữ của sách không đổi.
        self.app._mutating()
        path = self.app._editable(value)
        body = self._body()
        if not packages.is_package(path):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Cuốn có xưởng sửa cách đọc tên ở Studio.")
        if not isinstance(body.get("surface"), str) or not isinstance(body.get("spoken", ""), str):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu từ hoặc cách đọc")
        self._send_json(HTTPStatus.OK, book_edits.set_reading(path, body["surface"], body.get("spoken", "")))

    def get_listen_book(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.listen_book(value))

    def get_remote_download(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.remote_download(value, "status"))

    def post_remote_download(self, _query: dict[str, list[str]], value: str) -> None:
        # "Tải về máy" cuốn của máy khác (hay tải tiếp phần còn thiếu) - chạy nền, giao diện hỏi tiến độ bằng GET.
        self._send_json(HTTPStatus.OK, self.app.remote_download(value, "start"))

    def delete_remote_download(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.remote_download(value, "cancel"))

    def post_send_edits(self, _query: dict[str, list[str]], value: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.send_remote_edits(value))

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
            record=_held_record(body), index=body["index"] if isinstance(body.get("index"), int) else None,
            quote=str(body.get("quote") or ""),
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
        library = self.app.library
        self._send_json(HTTPStatus.OK, self.app.listening.latest_night(exists=lambda book: library.resolve_listenable(book) is not None))

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
        # `title`: Tên sách đang điền - dòng tên truyện đầu file trùng nó thì không thành chương "Mở đầu".
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
            folder = txt_split.split(source, root, str(body.get("title") or ""))
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
        target = actions.upload_source(Path(self.app.preferences.get()["libraryRoot"]), str(body.get("folder", "")),
                                       str(body.get("name", "")), data)
        # `path`: file lẻ được quét như khi chọn từng file (tách một file cả truyện thì thư mục chương thay chỗ nó).
        self._send_json(HTTPStatus.OK, {"folder": str(target.parent), "path": str(target)})

    def post_first_person(self, _query: dict[str, list[str]]) -> None:
        body = self._body()
        self._send_json(HTTPStatus.OK, actions.first_person_hint(self._source_paths(body.get("paths"), body.get("seedFrom"))))

    def get_voices(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.voices())

    def get_preferences(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.preferences.get())

    def get_readaloud_voices(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.readaloud.voices())

    def _reading_origin(self, body: dict[str, Any]) -> str | None:
        """Gốc Nhật / Hàn để đọc tên ("ja" / "ko"/ None): `origin` trong yêu cầu thắng ("none" = không phiên âm); không có thì theo cuốn `bookId`
        (ghi đè của người dùng, không thì máy đoán từ các chương đầu và nhớ - readaloud/names.py)."""
        explicit = body.get("origin")
        if explicit in ("ja", "ko", "none"):
            return None if explicit == "none" else explicit
        book = body.get("bookId")
        if not isinstance(book, str) or not book:
            return None

        def texts() -> Any:
            path = self.app._listenable(book)
            chapters = packages.edited_manifest(path).get("chapters") or [] if packages.is_package(path) else []
            ids = [chapter["id"] for chapter in chapters if isinstance(chapter, dict) and isinstance(chapter.get("id"), int)]
            return (text for text in (packages.chapter_text(path, chapter) for chapter in ids) if text)

        try:
            return self.app.readaloud.origins.origin(book, texts)
        except ApiError:
            return None

    def _book_readings(self, body: dict[str, Any]) -> dict[str, str]:
        """Cách đọc riêng cho lần đọc này: `readings` trong yêu cầu ("Nghe thử" một cách đọc chưa lưu - kiểm như lớp sửa) thắng; không có thì
        của cuốn `bookId` (lớp sửa `readings` của cuốn nhập từ file)."""
        if "readings" in body:  # {} = nghe chữ của sách, không cách đọc riêng nào ("Nghe thử" khi ô cách đọc trống)
            return book_edits.validate_readings(body["readings"]) if body["readings"] != {} else {}
        book = body.get("bookId")
        if not isinstance(book, str) or not book:
            return {}
        try:
            path = self.app._listenable(book)
        except ApiError:
            return {}
        return dict(book_edits.load(path).get("readings") or {}) if packages.is_package(path) else {}

    def post_readaloud_clip(self, _query: dict[str, list[str]]) -> None:
        # Một đoạn chữ -> một clip (audio tốc độ 1,0 + mốc từng chữ). Lỗi nói đúng lý do (`reason`) để trình phát đổi sang giọng máy hay báo người nghe.
        body = self._body()
        text, voice = body.get("text"), body.get("voice")
        if not isinstance(text, str) or not isinstance(voice, str):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu giọng hay chữ")
        try:
            clip = self.app.readaloud.clip(voice, text, cached_only=bool(body.get("cachedOnly")), origin=self._reading_origin(body),
                                           readings=self._book_readings(body))
        except VoiceError as error:
            if error.reason == "uncached":
                # Chỉ tra bộ đệm mà chưa có là câu trả lời bình thường (trình phát hỏi hàng loạt lúc nạp chương), không phải lỗi: 200 để
                # console của trình duyệt không đầy dòng 404 đỏ.
                self._send_json(HTTPStatus.OK, {"cached": False, "reason": "uncached"})
                return
            status = {"offline": HTTPStatus.SERVICE_UNAVAILABLE, "timeout": HTTPStatus.GATEWAY_TIMEOUT, "voice": HTTPStatus.BAD_REQUEST,
                      "empty": HTTPStatus.UNPROCESSABLE_ENTITY}.get(error.reason, HTTPStatus.BAD_GATEWAY)
            raise ApiError(status, str(error), reason=error.reason) from error
        self._send_json(HTTPStatus.OK, {"url": f"/media/readaloud/{clip['file']}", "duration_ms": clip["duration_ms"], "words": clip["words"]})

    def get_readaloud_vieneu(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, vieneu_module.status())

    def _start_voice_module(self, module: Any) -> None:
        # Người dùng bấm tải các lựa chọn đã đánh dấu (`choices`), hay "Cập nhật" (không có `choices`: chỉ các phần đã cũ của những gì đã tải).
        # Chung cho các mô-đun giọng tải thêm (vieneu_module, supertonic_module).
        self.app._mutating()
        choices = self._body().get("choices")
        if choices is not None and (not isinstance(choices, list) or not all(isinstance(item, str) for item in choices)):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Lựa chọn không hợp lệ")
        try:
            module.start(choices)
        except ValueError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error
        self._send_json(HTTPStatus.OK, module.status())

    def post_readaloud_vieneu(self, _query: dict[str, list[str]]) -> None:
        self._start_voice_module(vieneu_module)

    def get_readaloud_supertonic(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, supertonic_module.status())

    def post_readaloud_supertonic(self, _query: dict[str, list[str]]) -> None:
        self._start_voice_module(supertonic_module)

    def post_readaloud_vieneu_accelerate(self, _query: dict[str, list[str]]) -> None:
        # Công tắc "Dùng bản tăng tốc" (vieneu_module.set_accelerate): tắt/bật cách đọc của giọng VieNeu Turbo; tự đo lại tốc độ sau đó.
        self.app._mutating()
        on = self._body().get("on")
        if not isinstance(on, bool):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu on (true/false)")
        try:
            vieneu_module.set_accelerate(on)
        except ValueError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error
        self._send_json(HTTPStatus.OK, vieneu_module.status())

    def post_readaloud_vieneu_cancel(self, _query: dict[str, list[str]]) -> None:
        # "Huỷ" khi đang tải: dừng giữa chừng, phần đã tải giữ để lần sau làm tiếp.
        self.app._mutating()
        vieneu_module.cancel()
        self._send_json(HTTPStatus.OK, vieneu_module.status())

    def post_readaloud_supertonic_cancel(self, _query: dict[str, list[str]]) -> None:
        self.app._mutating()
        supertonic_module.cancel()
        self._send_json(HTTPStatus.OK, supertonic_module.status())

    def post_readaloud_supertonic_measure(self, _query: dict[str, list[str]]) -> None:
        self.app._mutating()
        supertonic_module.measure_again()
        self._send_json(HTTPStatus.OK, supertonic_module.status())

    def post_readaloud_supertonic_remove(self, _query: dict[str, list[str]]) -> None:
        # "Gỡ": lấy lại chỗ của giọng đã tải (thư viện dùng chung với mô-đun khác nên ở lại).
        self.app._mutating()
        choice = self._body().get("choice")
        try:
            supertonic_module.remove(choice if isinstance(choice, str) else supertonic_module.CHOICE)
        except ValueError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error
        self._send_json(HTTPStatus.OK, supertonic_module.status())

    def get_studio_engine(self, _query: dict[str, list[str]], engine: str) -> None:
        # Mô-đun tải thêm của máy đọc khác ở hộp "Đổi giọng" (voice_picker.engine_module_status): ZeroTTS, Supertonic.
        self._send_json(HTTPStatus.OK, engine_module_status(engine))

    def post_studio_engine(self, _query: dict[str, list[str]], engine: str) -> None:
        # "Tải giọng" ở hộp "Đổi giọng": tải phần còn thiếu / đã cũ ở luồng nền; hộp hỏi lại trạng thái mỗi giây.
        self.app._mutating()
        try:
            self._send_json(HTTPStatus.OK, start_engine_module(engine))
        except ValueError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error

    def post_studio_engine_cancel(self, _query: dict[str, list[str]], engine: str) -> None:
        # "Huỷ" khi hộp "Đổi giọng" đang tải giọng: dừng giữa chừng, phần đã tải giữ để lần sau làm tiếp.
        self.app._mutating()
        try:
            self._send_json(HTTPStatus.OK, cancel_engine_module(engine))
        except ValueError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error

    def post_studio_zerotts_remove(self, _query: dict[str, list[str]]) -> None:
        self.app._mutating()
        try:
            zerotts_module.remove()
        except ValueError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error
        self._send_json(HTTPStatus.OK, zerotts_module.status())

    def get_readaloud_prepare(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.readaloud.prepare.status())

    def post_readaloud_prepare(self, _query: dict[str, list[str]]) -> None:
        # "Làm trước": chữ các đoạn của những chương sắp nghe (đúng như trình phát chia) -> đọc sẵn vào bộ đệm ở luồng nền.
        self.app._mutating()
        body = self._body(limit=8 * 1024 * 1024)
        voice, texts = body.get("voice"), body.get("texts")
        if not isinstance(voice, str) or not isinstance(texts, list) or not all(isinstance(text, str) for text in texts):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu giọng hay chữ")
        try:
            self.app.readaloud._resolve(voice)
        except VoiceError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error), reason=error.reason) from error
        texts = [text for text in texts if len(text) <= readaloud.MAX_TEXT]
        self._send_json(HTTPStatus.OK, self.app.readaloud.prepare.start(voice, texts, str(body.get("label") or "")[:200], self._reading_origin(body),
                                                                         self._book_readings(body)))

    def delete_readaloud_prepare(self, _query: dict[str, list[str]]) -> None:
        self.app._mutating()
        self.app.readaloud.prepare.cancel()
        self._send_json(HTTPStatus.OK, self.app.readaloud.prepare.status())

    def post_readaloud_vieneu_measure(self, _query: dict[str, list[str]]) -> None:
        self.app._mutating()
        vieneu_module.measure_again()
        self._send_json(HTTPStatus.OK, vieneu_module.status())

    def get_readaloud_online(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self.app.readaloud.online_providers())

    def put_readaloud_online(self, _query: dict[str, list[str]], provider: str) -> None:
        # Khoá đi trong THÂN yêu cầu (không bao giờ trong địa chỉ); trả về chỉ bản che.
        body = self._body()
        key, region = body.get("key"), body.get("region", "")
        if not isinstance(key, str) or len(key) > 512 or not isinstance(region, str):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Thiếu khoá")
        if provider == "azure" and not readaloud_azure.valid_region(region.strip().lower()):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Vùng Azure chưa đúng (ví dụ: southeastasia)")
        try:  # khoá rỗng = giữ khoá đã lưu, chỉ đổi vùng
            self._send_json(HTTPStatus.OK, self.app.readaloud.set_key(provider, key, region if provider == "azure" else ""))
        except ValueError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error

    def delete_readaloud_online(self, _query: dict[str, list[str]], provider: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.readaloud.remove_key(provider))

    def post_readaloud_online_check(self, _query: dict[str, list[str]], provider: str) -> None:
        self._send_json(HTTPStatus.OK, self.app.readaloud.check_key(provider))

    def media_readaloud(self, _query: dict[str, list[str]], name: str) -> None:
        path = self.app.readaloud.cache.path(name)
        if path is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Không có clip này")
        self._send_file(path, cache=True)  # tên file là băm của giọng + chữ: nội dung không bao giờ đổi

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
        if isinstance(body.get("autoMusic"), bool):
            allowed["autoMusic"] = body["autoMusic"]
        # Mặc định của trình tạo sách: chất lượng là một trong ba mức; giọng kể là tên giọng có thật ("" = máy đề xuất).
        if body.get("newBookProfile") in ("fast", "balanced", "high_quality"):
            allowed["newBookProfile"] = body["newBookProfile"]
        if isinstance(body.get("newBookNarrator"), str):
            narrator = body["newBookNarrator"].strip()[:80]
            if not narrator or narrator in {voice["name"] for voice in self.app.voices()}:
                allowed["newBookNarrator"] = narrator
        # Mẫu thiết lập có tên: sai (tên trùng, quá 20 mẫu...) thì báo lại để người dùng sửa, không lặng lẽ bỏ mất mẫu vừa lưu.
        if "bookTemplates" in body:
            try:
                allowed["bookTemplates"] = clean_book_templates(body["bookTemplates"], {voice["name"] for voice in self.app.voices()})
            except ValueError as error:
                raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error
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
        setup = self._studio_setup()
        self.app.previews.shutdown()  # cập nhật thay Python của Studio: tiến trình nghe thử đang mở nó thì Windows không cho thay
        self._send_json(HTTPStatus.OK, setup.start())

    def post_studio_setup_cancel(self, _query: dict[str, list[str]]) -> None:
        self._send_json(HTTPStatus.OK, self._studio_setup().cancel())

    def delete_studio_setup(self, _query: dict[str, list[str]]) -> None:
        setup = self._studio_setup()
        busy = self.app._busy_elsewhere()
        if busy is not None:
            raise ApiError(HTTPStatus.CONFLICT, f"Đang làm cuốn \"{busy.name}\" - dừng cuốn ấy trước khi gỡ Studio")
        self.app.previews.shutdown()
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
        kind = "music" if body.get("kind") == "music" else "chapters"  # loại file hộp chọn cho xem: chương truyện hay nhạc
        paths = self.app.dialogs.pick_files(str(body.get("title", "Chọn file TXT")), str(body.get("start", "")), kind)
        self._send_json(HTTPStatus.OK, {"paths": paths})

    def media_voice(self, _query: dict[str, list[str]], name: str) -> None:
        path = self.app.voice_file(name)
        if path is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Giọng này chưa có bản nghe thử trên máy này (bản nghe thử đi kèm Studio)")
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
    ("GET", re.compile(r"/api/studio/(zerotts|supertonic)"), Handler.get_studio_engine),
    ("POST", re.compile(r"/api/studio/(zerotts|supertonic)"), Handler.post_studio_engine),
    ("POST", re.compile(r"/api/studio/(zerotts|supertonic)/cancel"), Handler.post_studio_engine_cancel),
    ("POST", re.compile(r"/api/studio/zerotts/remove"), Handler.post_studio_zerotts_remove),
    ("DELETE", re.compile(r"/api/studio/setup"), Handler.delete_studio_setup),
    ("GET", re.compile(r"/api/library"), Handler.get_library),
    ("GET", re.compile(r"/api/voices"), Handler.get_voices),
    ("GET", re.compile(r"/api/readaloud/voices"), Handler.get_readaloud_voices),
    ("POST", re.compile(r"/api/readaloud/clip"), Handler.post_readaloud_clip),
    ("GET", re.compile(r"/api/readaloud/vieneu"), Handler.get_readaloud_vieneu),
    ("GET", re.compile(r"/api/readaloud/prepare"), Handler.get_readaloud_prepare),
    ("POST", re.compile(r"/api/readaloud/prepare"), Handler.post_readaloud_prepare),
    ("DELETE", re.compile(r"/api/readaloud/prepare"), Handler.delete_readaloud_prepare),
    ("POST", re.compile(r"/api/readaloud/vieneu"), Handler.post_readaloud_vieneu),
    ("POST", re.compile(r"/api/readaloud/vieneu/measure"), Handler.post_readaloud_vieneu_measure),
    ("POST", re.compile(r"/api/readaloud/vieneu/cancel"), Handler.post_readaloud_vieneu_cancel),
    ("POST", re.compile(r"/api/readaloud/vieneu/accelerate"), Handler.post_readaloud_vieneu_accelerate),
    ("GET", re.compile(r"/api/readaloud/supertonic"), Handler.get_readaloud_supertonic),
    ("POST", re.compile(r"/api/readaloud/supertonic"), Handler.post_readaloud_supertonic),
    ("POST", re.compile(r"/api/readaloud/supertonic/measure"), Handler.post_readaloud_supertonic_measure),
    ("POST", re.compile(r"/api/readaloud/supertonic/cancel"), Handler.post_readaloud_supertonic_cancel),
    ("POST", re.compile(r"/api/readaloud/supertonic/remove"), Handler.post_readaloud_supertonic_remove),
    ("GET", re.compile(r"/api/readaloud/online"), Handler.get_readaloud_online),
    ("PUT", re.compile(r"/api/readaloud/online/(azure|google|fpt|viettel)"), Handler.put_readaloud_online),
    ("DELETE", re.compile(r"/api/readaloud/online/(azure|google|fpt|viettel)"), Handler.delete_readaloud_online),
    ("POST", re.compile(r"/api/readaloud/online/(azure|google|fpt|viettel)/check"), Handler.post_readaloud_online_check),
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
    ("GET", re.compile(BOOK + r"/wishes"), Handler.get_wishes),
    ("POST", re.compile(BOOK + r"/pending-changes/withdraw"), Handler.post_pending_withdraw),
    ("POST", re.compile(BOOK + r"/chapters/(\d+)/retake"), Handler.post_chapter_retake),
    ("POST", re.compile(BOOK + r"/characters/merge"), Handler.post_merge_character),
    ("POST", re.compile(BOOK + r"/characters/rename"), Handler.post_rename_character),
    ("GET", re.compile(BOOK + r"/chapters/(\d+)/script"), Handler.get_script),
    ("POST", re.compile(BOOK + r"/start"), Handler.post_start),
    ("POST", re.compile(BOOK + r"/stop"), Handler.post_stop),
    ("POST", re.compile(BOOK + r"/pause"), Handler.post_pause),
    ("GET", re.compile(BOOK + r"/precast"), Handler.get_precast),
    ("PUT", re.compile(BOOK + r"/precast"), Handler.put_precast),
    ("POST", re.compile(BOOK + r"/reveal"), Handler.post_reveal),
    # Chỉ trên máy này: Studio từ xa (remote_studio.ALLOWED) không có hai đường này.
    ("PUT", re.compile(BOOK + r"/title"), Handler.put_title),
    ("PUT", re.compile(BOOK + r"/author"), Handler.put_author),
    ("PUT", re.compile(BOOK + r"/chapters/(\d+)/title"), Handler.put_chapter_title),
    ("GET", re.compile(BOOK + r"/suggestions"), Handler.get_suggestions),
    ("PUT", re.compile(BOOK + r"/skip"), Handler.put_skip_line),
    ("GET", re.compile(BOOK + r"/readings"), Handler.get_readings),
    ("PUT", re.compile(BOOK + r"/readings"), Handler.put_readings),
    ("GET", re.compile(BOOK + r"/edits"), Handler.get_edits),
    ("DELETE", re.compile(BOOK + r"/edits"), Handler.delete_edits),
    ("POST", re.compile(BOOK + r"/edits/fold"), Handler.post_edits_fold),
    ("GET", re.compile(BOOK + r"/edits-inbox"), Handler.get_edits_inbox),
    ("POST", re.compile(BOOK + r"/edits-inbox/apply"), Handler.post_edits_inbox_apply),
    ("POST", re.compile(BOOK + r"/edits-inbox/skip"), Handler.post_edits_inbox_skip),
    ("POST", re.compile(BOOK + r"/save"), Handler.post_save),
    ("POST", re.compile(BOOK + r"/workshop"), Handler.post_workshop),
    ("DELETE", re.compile(BOOK), Handler.delete_book),
    # "Hoàn tác" xoá sách (trash_pending.py): đi cùng quyền với hai đường xoá - chỉ trên máy này, remote_studio.ALLOWED không có.
    ("POST", re.compile(r"/api/trash/([0-9a-f]{32})/undo"), Handler.post_trash_undo),
    ("POST", re.compile(BOOK + r"/export"), Handler.post_export),
    ("GET", re.compile(BOOK + r"/review"), Handler.get_review),
    ("GET", re.compile(BOOK + r"/work"), Handler.get_work),
    ("GET", re.compile(BOOK + r"/casting"), Handler.get_casting),
    ("GET", re.compile(BOOK + r"/continuation"), Handler.get_continuation),
    ("GET", re.compile(BOOK + r"/redo"), Handler.get_redo),
    ("GET", re.compile(BOOK + r"/music"), Handler.get_music),
    ("PUT", re.compile(BOOK + r"/music"), Handler.put_music),
    ("POST", re.compile(BOOK + r"/music/rebuild"), Handler.post_music_rebuild),
    ("POST", re.compile(BOOK + r"/music/moods"), Handler.post_music_moods),
    ("POST", re.compile(BOOK + r"/music/download/cancel"), Handler.post_music_download_cancel),
    ("GET", re.compile(r"/api/music/moods-model"), Handler.get_music_moods_model),
    ("POST", re.compile(r"/api/music/moods-model"), Handler.post_music_moods_model),
    ("GET", re.compile(BOOK + r"/music/scenes/([^/]+)/alternatives"), Handler.get_music_alternatives),
    ("GET", re.compile(BOOK + r"/music/chapters/(\d+)"), Handler.get_music_cues),
    ("GET", re.compile(BOOK + r"/music/playlist"), Handler.get_music_playlist),
    ("GET", re.compile(r"/api/music/playlists"), Handler.get_music_playlists),
    ("GET", re.compile(BOOK + r"/music/files/(" + music_plan.TRACK_NAME + ")"), Handler.get_music_packaged),
    ("GET", re.compile(r"/api/music/track"), Handler.get_music_track),
    # "Nhạc của tôi": chỉ trên máy này (Studio từ xa không có các đường này - nhạc của người dùng không ra khỏi máy trừ qua sách).
    ("GET", re.compile(r"/api/music/local"), Handler.get_my_music),
    ("POST", re.compile(r"/api/music/local/import"), Handler.post_my_music_import),
    ("POST", re.compile(r"/api/music/local/module"), Handler.post_my_music_module),
    ("POST", re.compile(r"/api/music/local/module/cancel"), Handler.post_my_music_module_cancel),
    ("POST", re.compile(r"/api/music/local/reanalyse"), Handler.post_my_music_reanalyse),
    ("POST", re.compile(r"/api/music/local/precise"), Handler.post_my_music_precise),
    ("POST", re.compile(r"/api/music/local/precise/remove"), Handler.post_my_music_precise_remove),
    ("POST", re.compile(r"/api/music/local/precise/cancel"), Handler.post_my_music_precise_cancel),
    ("POST", re.compile(r"/api/music/local/analyze"), Handler.post_my_music_analyze),
    ("POST", re.compile(r"/api/music/local/([0-9a-f]{40})/auto"), Handler.post_my_music_auto),
    ("DELETE", re.compile(r"/api/music/local/([0-9a-f]{40})"), Handler.delete_my_music),
    ("GET", re.compile(r"/api/music/local/([0-9a-f]{40})/file"), Handler.get_my_music_file),
    ("GET", re.compile(BOOK + r"/parts"), Handler.get_parts),
    ("GET", re.compile(BOOK + r"/pronunciations"), Handler.get_name_readings),
    ("GET", re.compile(BOOK + r"/pronunciations/reach"), Handler.get_reading_reach),
    ("GET", re.compile(BOOK + r"/casting/stamp"), Handler.get_casting_stamp),
    ("GET", re.compile(BOOK + r"/casting/(\d+)"), Handler.get_casting_chapter),
    ("POST", re.compile(BOOK + r"/review"), Handler.post_review),
    ("POST", re.compile(BOOK + r"/pronunciation"), Handler.post_pronunciation),
    ("POST", re.compile(BOOK + r"/pronunciation/preview"), Handler.post_pronunciation_preview),
    ("POST", re.compile(BOOK + r"/voice/preview"), Handler.post_voice_preview),
    ("GET", re.compile(BOOK + r"/shared-readings"), Handler.get_book_shared_readings),
    ("POST", re.compile(BOOK + r"/shared-readings"), Handler.post_book_shared_readings),
    ("GET", re.compile(r"/api/readings"), Handler.get_shared_readings),
    ("GET", re.compile(r"/api/analysis-models"), Handler.get_analysis_models),
    ("POST", re.compile(r"/api/readings"), Handler.post_shared_readings),
    ("POST", re.compile(BOOK + r"/bookfile"), Handler.post_bookfile),
    ("POST", re.compile(BOOK + r"/bookfile-job"), Handler.post_bookfile_job),
    ("GET", re.compile(BOOK + r"/bookfile-job"), Handler.get_bookfile_job),
    ("POST", re.compile(BOOK + r"/m4b-job"), Handler.post_m4b_job),
    ("GET", re.compile(BOOK + r"/m4b-job"), Handler.get_m4b_job),
    ("GET", re.compile(BOOK + r"/export-size"), Handler.get_export_size),
    ("GET", re.compile(BOOK + r"/music-export"), Handler.get_music_export),
    ("POST", re.compile(BOOK + r"/music-export/cancel"), Handler.post_music_export_cancel),
    ("GET", re.compile(LISTEN + r"/audiobook/plan"), Handler.get_audiobook_plan),
    ("GET", re.compile(LISTEN + r"/audiobook"), Handler.get_audiobook_job),
    ("POST", re.compile(LISTEN + r"/audiobook"), Handler.post_audiobook_job),
    ("POST", re.compile(LISTEN + r"/audiobook/cancel"), Handler.post_audiobook_cancel),
    ("GET", re.compile(r"/api/export-jobs"), Handler.get_export_jobs),
    ("GET", re.compile(r"/api/ffmpeg"), Handler.get_ffmpeg),
    ("POST", re.compile(r"/api/ffmpeg"), Handler.post_ffmpeg),
    ("POST", re.compile(r"/api/ffmpeg/cancel"), Handler.post_ffmpeg_cancel),
    ("GET", re.compile(BOOK + r"/word-timings"), Handler.get_word_timings),
    ("POST", re.compile(BOOK + r"/word-timings"), Handler.post_word_timings),
    ("POST", re.compile(BOOK + r"/projectfile"), Handler.post_projectfile),
    ("POST", re.compile(BOOK + r"/projectfile-job"), Handler.post_projectfile_job),
    ("GET", re.compile(BOOK + r"/projectfile-job"), Handler.get_projectfile_job),
    ("POST", re.compile(BOOK + r"/projectfile-job/cancel"), Handler.post_projectfile_job_cancel),
    ("POST", re.compile(BOOK + r"/speaker"), Handler.post_speaker),
    ("POST", re.compile(BOOK + r"/narrator-section"), Handler.post_narrator_section),
    ("POST", re.compile(BOOK + r"/voice"), Handler.post_voice),
    ("POST", re.compile(BOOK + r"/line"), Handler.post_line),
    ("GET", re.compile(BOOK + r"/voices"), Handler.get_voice_choices),
    ("GET", re.compile(BOOK + r"/cover/search"), Handler.get_cover_search),
    ("PUT", re.compile(BOOK + r"/cover"), Handler.put_cover),
    ("DELETE", re.compile(BOOK + r"/cover"), Handler.delete_cover),
    ("POST", re.compile(r"/api/reveal-export"), Handler.post_reveal_export),
    ("POST", re.compile(r"/api/open-url"), Handler.post_open_url),
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
    ("GET", re.compile(r"/api/computers/bluetooth"), Handler.get_computers_bluetooth),
    ("POST", re.compile(r"/api/computers/([0-9a-f]{12})/bluetooth"), Handler.post_computer_bluetooth),
    ("POST", re.compile(r"/api/computers/([0-9a-f]{12})/stop-waiting"), Handler.post_computer_stop_waiting),
    ("GET", re.compile(r"/api/computers/([0-9a-f]{12})/unsent"), Handler.get_computer_unsent),
    ("GET", re.compile(r"/api/computers/([0-9a-f]{12})/reachable"), Handler.get_computer_reachable),
    ("DELETE", re.compile(r"/api/computers/([0-9a-f]{12})"), Handler.delete_computer),
    ("GET", re.compile(r"/api/listen/library"), Handler.get_listen_library),
    ("POST", re.compile(r"/api/listen/open-book-file"), Handler.post_open_book_file),
    # Thêm sách từ EPUB / DOCX / PDF / TXT: xem trước danh sách chương, rồi nhập thành sách chỉ-chữ (chỉ trên máy này).
    ("POST", re.compile(r"/api/listen/import/preview"), Handler.post_import_preview),
    ("POST", re.compile(r"/api/listen/import"), Handler.post_import_book),
    ("GET", re.compile(LISTEN + r"/chapters/(\d+)/text"), Handler.get_chapter_text),

    ("GET", re.compile(LISTEN), Handler.get_listen_book),
    ("GET", re.compile(LISTEN + r"/download"), Handler.get_remote_download),
    ("POST", re.compile(LISTEN + r"/download"), Handler.post_remote_download),
    ("DELETE", re.compile(LISTEN + r"/download"), Handler.delete_remote_download),
    ("POST", re.compile(LISTEN + r"/edits/send"), Handler.post_send_edits),
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
    ("GET", re.compile(r"/media/readaloud/([0-9a-f]{64}\.(?:mp3|wav))"), Handler.media_readaloud),
    ("GET", re.compile(r"/media/books/([A-Za-z0-9_-]+)/chapters/(\d+)"), Handler.media_chapter),
    ("GET", re.compile(r"/media/books/([A-Za-z0-9_-]+)/samples/(\d+)"), Handler.media_sample),
    ("GET", re.compile(r"/media/books/([A-Za-z0-9_-]+)/cover"), Handler.media_cover),
    ("GET", re.compile(r"/media/books/([A-Za-z0-9_-]+)/reading-previews/([0-9a-f]{32})\.wav"), Handler.media_reading_preview),
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

