"""ffmpeg: một phần của mô-đun "Phân tích nhạc" (music_module.py), tải khi người dùng bấm - KHÔNG nằm trong bộ cài, KHÔNG cần để nhập
nhạc (thẻ + độ dài đọc bằng tinytag). ffmpeg chỉ phục vụ phần phân tích: giải mã cho model (music_mel.py) và đo độ to (music_plan.py).
Đường tải ghim cứng (URL + SHA-256 + cỡ), qua studio_setup.download (.part, kiểm băm, rồi mới đổi tên).

Nguồn: ZIP GyanD/codexffmpeg 8.1.2 essentials, Windows x64 tĩnh GPL-3.0-or-later, tag cố định 8.1.2.
Chỉ tải phần nén của ffmpeg.exe bằng HTTP Range; ghim SHA-256/cỡ cả phần nén và exe, kiểm CRC (docs/THIRD_PARTY.md). Chỉ Windows x86_64 có đường tải; nền tảng khác phải tự
cài ffmpeg (lý do nói rõ). Máy đã có ffmpeg không phải của mình (imageio_ffmpeg, hay trong PATH) thì `external()` đúng và mô-đun không
tải gì. Việc tải/đặt trạng thái do music_module.py lo; ở đây chỉ có `install` (đồng bộ) và các phép kiểm.

ABOOK_FFMPEG_DOWNLOAD=0: không bao giờ tải (bộ kiểm đặt sẵn).
"""
from __future__ import annotations

import os
import platform
import shutil
import sys
import threading
from pathlib import Path
from typing import Callable

from .. import io_utils
from . import studio_setup, zip_range

# Giữ tên WHEEL cho caller: cỡ/băm của phần DEFLATE, URL của ZIP có tag cố định.
WHEEL = studio_setup.Download(
    "bộ đọc nhạc (ffmpeg)",
    "https://github.com/GyanD/codexffmpeg/releases/download/8.1.2/ffmpeg-8.1.2-essentials_build.zip",
    "fcc9bb26d29ef695533bec19e0b2e15f0d3745cb900d260d8b6c97eab07277aa",
    35_710_575,
)
MEMBER = "ffmpeg-8.1.2-essentials_build/bin/ffmpeg.exe"
ARCHIVE_SIZE = 109_728_040
EXE_SIZE = 101_897_728
EXE_SHA256 = "1326dde4c84ff1f96fe6b8916c5bed29e163e9b5dccf995f6f3db069d143ec5e"
EXE_CRC = 1558300500
ENV_DOWNLOAD = "ABOOK_FFMPEG_DOWNLOAD"  # "0" = không bao giờ tải
NOUN = "bộ đọc nhạc (ffmpeg)"  # trong câu báo lỗi tải
FOLDER = Path("tools") / "ffmpeg"  # dưới thư mục dữ liệu của app (server.py)
EXE_NAME = "ffmpeg.exe"

_lock = threading.RLock()
_folder: Path | None = None


def configure(folder: Path | str | None) -> None:
    """Thư mục đặt ffmpeg tải về (server.py: <dữ liệu app>/tools/ffmpeg); đã có exe ở đó thì đăng ký ngay."""
    global _folder
    with _lock:
        _folder = Path(folder) if folder is not None else None
        exe = _exe()
        io_utils.use_downloaded_ffmpeg(exe if exe is not None and exe.is_file() else None)


def _exe() -> Path | None:
    return _folder / EXE_NAME if _folder is not None else None


def ready() -> bool:
    """ffmpeg dùng được ngay không (imageio_ffmpeg, bản đã tải, hay ffmpeg trong PATH). Rẻ: không chạy tiến trình nào."""
    return io_utils.ffmpeg_available()


def external() -> bool:
    """Máy có ffmpeg KHÔNG phải do mô-đun tải (imageio_ffmpeg của Studio / máy dev, hay trong PATH): khi ấy không tải gì."""
    try:
        import imageio_ffmpeg

        if Path(imageio_ffmpeg.get_ffmpeg_exe()).is_file():
            return True
    except Exception:  # noqa: BLE001 - thiếu gói / thiếu binary đều là "không có"
        pass
    return shutil.which("ffmpeg") is not None


def downloaded() -> bool:
    """File exe do mô-đun tải đã nằm đúng chỗ."""
    exe = _exe()
    return exe is not None and exe.is_file()


def pin() -> str:
    return WHEEL.sha256


def cannot_download() -> str:
    """Rỗng nếu tải được; không thì lý do (tiếng Việt) để báo người dùng."""
    if os.environ.get(ENV_DOWNLOAD, "1") == "0":
        return "tải bộ đọc nhạc đang bị tắt trên máy này"
    if _folder is None:
        return "chưa có thư mục để đặt bộ đọc nhạc"
    if sys.platform != "win32" or platform.machine().lower() not in ("amd64", "x86_64"):
        return "Máy này chưa có bản tải sẵn của bộ xuất âm thanh — bạn xem Chi tiết để nhờ hỗ trợ."
    return ""


def install(progress: Callable[[int, int], None], cancelled: Callable[[], bool] = lambda: False) -> Path:
    from .install_locks import destination_lock

    assert _folder is not None
    with destination_lock(_folder / "install"):
        stamp = _folder / "installed.sha256"
        exe = _folder / EXE_NAME
        if exe.is_file() and stamp.is_file() and stamp.read_text(encoding="utf-8") == pin():
            io_utils.use_downloaded_ffmpeg(exe)
            progress(WHEEL.size, WHEEL.size)
            return exe
        result = _install(progress, cancelled)
        io_utils.atomic_write_text(stamp, pin())
        return result


def _install(progress: Callable[[int, int], None], cancelled: Callable[[], bool]) -> Path:
    """Tải riêng mục FFmpeg đã ghim, kiểm băm trước khi đăng ký với io_utils. Đồng bộ - gọi ở luồng nền của mô-đun. Ném lỗi để mô-đun nói lý do (`reason`)."""
    assert _folder is not None
    _folder.mkdir(parents=True, exist_ok=True)
    archive = _folder / "ffmpeg.deflate"
    offset = zip_range.member_offset(WHEEL, ARCHIVE_SIZE, MEMBER, EXE_SIZE, EXE_CRC, cancelled)
    studio_setup.download(WHEEL, archive, progress, cancelled, byte_range=(offset, ARCHIVE_SIZE))
    exe = _folder / EXE_NAME
    part = exe.with_name(exe.name + ".part")
    zip_range.inflate(archive, part, EXE_SIZE, EXE_SHA256, EXE_CRC, cancelled)
    os.replace(part, exe)
    os.remove(archive.resolve())
    io_utils.use_downloaded_ffmpeg(exe)
    return exe


# ---- tải riêng ffmpeg (xuất sách nói: hộp Xuất mời tải khi máy chưa có) ---------------------------------------------------------
# Mô-đun "Phân tích nhạc" tải ffmpeg cùng thư viện + model; xuất sách nói chỉ cần ffmpeg (~36 MB) nên có đường tải riêng, cùng `install` và cùng thư mục.

_state: dict[str, object] = {"downloading": False, "done": 0, "total": 0, "error": ""}
_cancel = threading.Event()
_thread: threading.Thread | None = None


def status() -> dict[str, object]:
    """Cho giao diện: `ready` (dùng được ngay), `downloading` + `done`/`total` byte, `error` (lần tải gần nhất hỏng, lời tiếng Việt), `bytes` (cỡ tải), `blocked` (rỗng nếu tải được)."""
    with _lock:
        state = dict(_state)
    ok = ready()
    return {"ready": ok, "downloading": bool(state["downloading"]), "done": state["done"], "total": state["total"], "error": state["error"],
            "errorDetail": state.get("error_detail", "") if state["error"] else "",
            "retrying": bool(state["downloading"]) and studio_setup.retrying(_thread),
            "bytes": WHEEL.size, "blocked": "" if ok else cannot_download()}


def start() -> None:
    """Bắt đầu tải ở luồng nền (không làm gì nếu đã có ffmpeg hay đang tải). Không tải được thì `error` ghi lý do."""
    global _thread
    with _lock:
        if ready() or _state["downloading"]:
            return
        reason_blocked = cannot_download()
        if reason_blocked:
            _state.update(error=reason_blocked[0].upper() + reason_blocked[1:] + ".")
            return
        _cancel.clear()
        _state.update(downloading=True, done=0, total=WHEEL.size, error="")
        _thread = threading.Thread(target=_download, name="ffmpeg-download", daemon=True)
        _thread.start()


def cancel() -> None:
    """Dừng tải giữa chừng (phần đã tải được giữ để lần sau làm tiếp)."""
    _cancel.set()


def join(timeout: float | None = None) -> None:
    """Đợi luồng tải xong (bài thử)."""
    thread = _thread
    if thread is not None:
        thread.join(timeout)


def _download() -> None:
    def progress(done: int, _total: int = 0) -> None:
        with _lock:
            _state["done"] = done

    try:
        install(progress, _cancel.is_set)
        error, detail = "", ""
    except Exception as failure:  # noqa: BLE001 - mọi lỗi tải phải thành lời cho người dùng, không giết luồng im lặng
        error, detail = ("Đã dừng tải.", "") if _cancel.is_set() else studio_setup.download_failure(NOUN, failure)
    with _lock:
        _state.update(downloading=False, error=error, error_detail=detail)
