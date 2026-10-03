"""ffmpeg: một phần của mô-đun "Phân tích nhạc" (music_module.py), tải khi người dùng bấm - KHÔNG nằm trong bộ cài, KHÔNG cần để nhập
nhạc (thẻ + độ dài đọc bằng tinytag). ffmpeg chỉ phục vụ phần phân tích: giải mã cho model (music_mel.py) và đo độ to (music_plan.py).
Đường tải ghim cứng (URL + SHA-256 + cỡ), qua studio_setup.download (.part, kiểm băm, rồi mới đổi tên).

Nguồn: bánh xe imageio-ffmpeg 0.6.0 trên PyPI (một file zip) chứa đúng một exe tĩnh - FFmpeg 7.1 bản "essentials" của gyan.dev
(cấu hình GPL-3.0; phần bọc imageio-ffmpeg BSD-2-Clause, docs/THIRD_PARTY.md). Chỉ Windows x86_64 có đường tải; nền tảng khác phải tự
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
import zipfile
from pathlib import Path
from typing import Callable

from .. import io_utils
from . import studio_setup

WHEEL = studio_setup.Download(
    "bộ đọc nhạc (ffmpeg)",
    "https://files.pythonhosted.org/packages/2c/c6/fa760e12a2483469e2bf5058c5faff664acf66cadb4df2ad6205b016a73d/"
    "imageio_ffmpeg-0.6.0-py3-none-win_amd64.whl",
    "02fa47c83703c37df6bfe4896aab339013f62bf02c5ebf2dce6da56af04ffc0a",
    31_246_824,
)
MEMBER = "imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe"
ENV_DOWNLOAD = "ABOOK_FFMPEG_DOWNLOAD"  # "0" = không bao giờ tải
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
        return "bản tải sẵn chỉ có cho Windows 64-bit - hãy cài ffmpeg cho máy này (có trong PATH) rồi bấm lại"
    return ""


def reason(error: BaseException) -> str:
    if isinstance(error, studio_setup.SetupError):
        if error.__cause__ is not None:  # download() bọc lỗi mạng
            return "không tải được - kiểm tra kết nối mạng rồi thử lại"
        return "file tải về không đúng bản đã ghim (đã xoá) - thử lại"
    if isinstance(error, (zipfile.BadZipFile, KeyError)):
        return "gói tải về không có ffmpeg - thử lại"
    if isinstance(error, OSError):
        return f"không ghi được vào ổ đĩa ({error.strerror or error})"
    return f"lỗi không ngờ ({type(error).__name__}: {error})"


def install(progress: Callable[[int, int], None], cancelled: Callable[[], bool] = lambda: False) -> Path:
    """Tải bánh xe (ghim), lấy ra exe, đăng ký với io_utils. Đồng bộ - gọi ở luồng nền của mô-đun. Ném lỗi để mô-đun nói lý do (`reason`)."""
    assert _folder is not None
    _folder.mkdir(parents=True, exist_ok=True)
    wheel = _folder / "imageio_ffmpeg.whl"
    studio_setup.download(WHEEL, wheel, progress, cancelled)
    exe = _folder / EXE_NAME
    part = exe.with_name(exe.name + ".part")
    with zipfile.ZipFile(wheel) as bundle, bundle.open(MEMBER) as source, part.open("wb") as target:
        shutil.copyfileobj(source, target, 1 << 20)
    os.replace(part, exe)
    wheel.unlink(missing_ok=True)
    io_utils.use_downloaded_ffmpeg(exe)
    return exe
