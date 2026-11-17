"""ffmpeg: một phần của mô-đun "Phân tích nhạc" (music_module.py), tải khi người dùng bấm - KHÔNG nằm trong bộ cài, KHÔNG cần để nhập
nhạc (thẻ + độ dài đọc bằng tinytag). ffmpeg chỉ phục vụ phần phân tích: giải mã cho model (music_mel.py) và đo độ to (music_plan.py).
Đường tải ghim cứng (URL + SHA-256 + cỡ), qua studio_setup.download (.part, kiểm băm, rồi mới đổi tên).

Nguồn: ZIP FFmpeg-Builds (BtbN) n8.1.3-27-g8dca1586f4 win64-gpl-8.1 (nhánh release/8.1), Windows x64 tĩnh GPL-3.0-or-later,
thẻ autobuild-2026-10-31-12-59 = bản CUỐI THÁNG (FFmpeg-Builds giữ bản cuối mỗi tháng 2 năm, bản ngày chỉ 14 ngày rồi xoá, URL 404).
Đổi pin: chỉ chọn thẻ ngày cuối tháng (test_ffmpeg_setup kiểm), rồi chạy scripts/ffmpeg_pinned_codecs.py với exe mới.
Chỉ tải phần nén của ffmpeg.exe bằng HTTP Range; ghim SHA-256/cỡ cả phần nén và exe, kiểm CRC (docs/THIRD_PARTY.md). Chỉ Windows x86_64 có đường tải; nền tảng khác phải tự
cài ffmpeg (lý do nói rõ). Máy đã có ffmpeg không phải của mình (imageio_ffmpeg, hay trong PATH) thì `external()` đúng và mô-đun không
tải gì. Việc tải/đặt trạng thái do music_module.py lo; ở đây chỉ có `install` (đồng bộ) và các phép kiểm.

Bố cục `tools/ffmpeg`: mỗi pin một thư mục `<16 ký tự đầu của pin>/ffmpeg.exe`; `installed.sha256` (ghi nguyên tử SAU khi exe đã nằm
đúng chỗ) là con trỏ tới bản đang dùng. Cập nhật không bao giờ ghi đè exe đang chạy (Windows khoá file của tiến trình đang chạy:
một lượt xuất dùng bản cũ trong lúc bản mới tải xong): bản mới vào thư mục riêng, con trỏ đổi, bản cũ để lại và chỉ bị xoá khi
xoá được (không còn tiến trình nào giữ) - ngay sau khi cài và mỗi lần app mở. `ffmpeg.exe` nằm thẳng trong thư mục là bố cục trước
0.4.175 (Gyan 8.1.2): vẫn nhận ra để mời cập nhật. File tải dở mang tên theo pin, nên phần dở của pin khác không bao giờ bị nối vào.

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
    "https://github.com/FFmpeg-Builds/FFmpeg-Builds/releases/download/autobuild-2026-10-31-12-59/ffmpeg-n8.1.3-27-g8dca1586f4-win64-gpl-8.1.zip",
    "7ec86ab76b06d90656139025394513670c2ff8b6404b957be24bf1ec09792520",
    63_753_164,
)
MEMBER = "ffmpeg-n8.1.3-27-g8dca1586f4-win64-gpl-8.1/bin/ffmpeg.exe"
ARCHIVE_SIZE = 194_182_300
EXE_SIZE = 165_577_728
EXE_SHA256 = "c46215f8889634396f0ac0acac738ef2145175e5b6caf28b3daa8ac9a9980c5f"
EXE_CRC = 876847253
ENV_DOWNLOAD = "ABOOK_FFMPEG_DOWNLOAD"  # "0" = không bao giờ tải
NOUN = "bộ đọc nhạc (ffmpeg)"  # trong câu báo lỗi tải
FOLDER = Path("tools") / "ffmpeg"  # dưới thư mục dữ liệu của app (server.py)
EXE_NAME = "ffmpeg.exe"

_lock = threading.RLock()
_folder: Path | None = None


def configure(folder: Path | str | None) -> None:
    """Thư mục đặt ffmpeg tải về (server.py: <dữ liệu app>/tools/ffmpeg); đã có exe ở đó thì đăng ký ngay, rồi dọn các bản cũ không ai giữ."""
    global _folder
    with _lock:
        _folder = Path(folder) if folder is not None else None
        exe = _exe()
        io_utils.use_downloaded_ffmpeg(exe if exe is not None and exe.is_file() else None)
        if exe is not None and exe.is_file() and _installed_current():
            _prune(exe)


def _slot(stamp: str) -> str:
    """Tên thư mục của một pin (SHA-256 phần nén)."""
    return stamp[:16]


def _stamp() -> str:
    if _folder is None:
        return ""
    try:
        return (_folder / "installed.sha256").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""


def _exe() -> Path | None:
    """Exe con trỏ `installed.sha256` chỉ tới; không có thì `ffmpeg.exe` của bố cục cũ (để còn mời cập nhật)."""
    if _folder is None:
        return None
    stamp = _stamp()
    if len(stamp) == 64 and all(c in "0123456789abcdef" for c in stamp):
        pinned = _folder / _slot(stamp) / EXE_NAME
        if pinned.is_file():
            return pinned
    return _folder / EXE_NAME


def _prune(keep: Path) -> None:
    """Xoá các bản ffmpeg khác `keep` (thư mục pin khác, `ffmpeg.exe` bố cục cũ) và phần tải dở của pin khác. Bản nào đang chạy
    thì Windows không cho xoá: để đó, lần sau dọn. Không bao giờ ném lỗi."""
    assert _folder is not None
    current = _slot(pin())
    for path in list(_folder.iterdir()) if _folder.is_dir() else []:
        try:
            if path.is_dir() and path != keep.parent and len(path.name) == 16 and all(c in "0123456789abcdef" for c in path.name):
                for child in path.iterdir():
                    child.unlink()
                path.rmdir()
            elif path.is_file() and path != keep and (path.name in (EXE_NAME, EXE_NAME + ".part", "ffmpeg.deflate", "ffmpeg.deflate.part")
                                                     or (path.name.startswith("ffmpeg-") and ".deflate" in path.name and current not in path.name)):
                path.unlink()
        except OSError:
            continue


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


def current() -> bool:
    """Downloaded tool matches its own install stamp, independent of music/module.json."""
    return external() or _installed_current()


def _installed_current() -> bool:
    """Con trỏ chỉ tới đúng pin và exe của pin ấy nằm trong thư mục riêng của nó."""
    return _folder is not None and _stamp() == pin() and (_folder / _slot(pin()) / EXE_NAME).is_file()


def outdated() -> bool:
    return downloaded() and not current()


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
        if _installed_current():
            exe = _folder / _slot(pin()) / EXE_NAME
            io_utils.use_downloaded_ffmpeg(exe)
            progress(WHEEL.size, WHEEL.size)
            return exe
        result = _install(progress, cancelled)
        # Con trỏ đổi SAU khi exe mới đã kiểm xong và nằm đúng chỗ; bản cũ (có thể đang chạy) không bị chạm tới
        io_utils.atomic_write_text(_folder / "installed.sha256", pin())
        io_utils.use_downloaded_ffmpeg(result)
        _prune(result)
        return result


def _install(progress: Callable[[int, int], None], cancelled: Callable[[], bool]) -> Path:
    """Tải riêng mục FFmpeg đã ghim vào thư mục của pin, kiểm băm/CRC/cỡ. Không ghi đè exe nào đang dùng: thư mục của pin mới chưa
    từng được trỏ tới; exe của pin này đã nằm sẵn và đúng (mất con trỏ) thì dùng lại, không tải. Đồng bộ - gọi ở luồng nền của
    mô-đun. Ném lỗi để mô-đun nói lý do (`reason`)."""
    assert _folder is not None
    _folder.mkdir(parents=True, exist_ok=True)
    exe = _folder / _slot(pin()) / EXE_NAME
    if exe.is_file() and exe.stat().st_size == EXE_SIZE and studio_setup._sha256(exe) == EXE_SHA256:
        progress(WHEEL.size, WHEEL.size)
        return exe
    archive = _folder / f"ffmpeg-{_slot(pin())}.deflate"  # tên theo pin: phần dở của pin khác không bao giờ bị nối vào
    offset = zip_range.member_offset(WHEEL, ARCHIVE_SIZE, MEMBER, EXE_SIZE, EXE_CRC, cancelled)
    studio_setup.download(WHEEL, archive, progress, cancelled, byte_range=(offset, ARCHIVE_SIZE))
    exe.parent.mkdir(exist_ok=True)  # chỉ tạo khi đã có phần nén đúng băm: lượt hỏng không để lại thư mục rỗng
    part = exe.with_name(exe.name + ".part")
    zip_range.inflate(archive, part, EXE_SIZE, EXE_SHA256, EXE_CRC, cancelled)
    os.replace(part, exe)
    os.remove(archive.resolve())
    return exe


# ---- tải riêng ffmpeg (xuất sách nói: hộp Xuất mời tải khi máy chưa có) ---------------------------------------------------------
# Mô-đun "Phân tích nhạc" tải ffmpeg cùng thư viện + model; xuất sách nói chỉ cần ffmpeg (~64 MB) nên có đường tải riêng, cùng `install` và cùng thư mục.

_state: dict[str, object] = {"downloading": False, "done": 0, "total": 0, "error": ""}
_cancel = threading.Event()
_thread: threading.Thread | None = None


def status() -> dict[str, object]:
    """Cho giao diện: `ready` (dùng được ngay), `downloading` + `done`/`total` byte, `error` (lần tải gần nhất hỏng, lời tiếng Việt), `bytes` (cỡ tải), `blocked` (rỗng nếu tải được)."""
    with _lock:
        state = dict(_state)
    ok = ready()
    behind = outdated()
    return {"ready": ok, "outdated": behind, "downloading": bool(state["downloading"]), "done": state["done"], "total": state["total"], "error": state["error"],
            "errorDetail": state.get("error_detail", "") if state["error"] else "",
            "retrying": bool(state["downloading"]) and studio_setup.retrying(_thread),
            "bytes": WHEEL.size, "blocked": "" if ok and not behind else cannot_download()}


def start() -> None:
    """Người dùng bấm tải/cập nhật; bản đã đúng pin hay đang tải thì không làm gì."""
    global _thread
    with _lock:
        if (ready() and not outdated()) or _state["downloading"]:
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
