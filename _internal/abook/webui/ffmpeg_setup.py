"""ffmpeg tải lúc cần cho bản app chỉ-nghe (Python nhúng chỉ có shell/python/requirements.txt, không có ffmpeg): lần NHẬP NHẠC đầu tiên
("Nhạc của tôi", music_local.py đọc thẻ + độ dài, music_mel.py giải mã) mới tải - cùng cách với gói model nhạc (music_student.py):
đường tải ghim cứng (URL + SHA-256 + cỡ), qua studio_setup.download (.part, kiểm băm, rồi mới đổi tên). Không nằm trong bộ cài.

Nguồn: bánh xe imageio-ffmpeg 0.6.0 trên PyPI (một file zip) chứa đúng một exe tĩnh - FFmpeg 7.1 bản "essentials" của gyan.dev
(cấu hình GPL-3.0; phần bọc imageio-ffmpeg BSD-2-Clause, docs/THIRD_PARTY.md). Chỉ Windows x86_64 có đường tải; nền tảng khác phải tự
cài ffmpeg (trạng thái lỗi nói rõ). Máy đã có ffmpeg (imageio_ffmpeg, hay trong PATH) thì không tải gì: `ready()` đúng ngay.

Giao diện hỏi `status()` ~mỗi giây trong lúc tải. ABOOK_FFMPEG_DOWNLOAD=0: không bao giờ tải (bộ kiểm đặt sẵn).
"""
from __future__ import annotations

import os
import platform
import shutil
import sys
import threading
import zipfile
from pathlib import Path
from typing import Any

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
_thread: threading.Thread | None = None
_state: dict[str, Any] = {"state": "idle", "done": 0, "total": WHEEL.size, "error": ""}


def configure(folder: Path | str | None) -> None:
    """Thư mục đặt ffmpeg tải về (server.py: <dữ liệu app>/tools/ffmpeg); đã có exe ở đó thì đăng ký ngay. Cũng đặt lại trạng thái."""
    global _folder
    with _lock:
        _folder = Path(folder) if folder is not None else None
        _state.update(state="idle", done=0, total=WHEEL.size, error="")
        exe = _exe()
        io_utils.use_downloaded_ffmpeg(exe if exe is not None and exe.is_file() else None)


def _exe() -> Path | None:
    return _folder / EXE_NAME if _folder is not None else None


def ready() -> bool:
    """ffmpeg dùng được ngay không (imageio_ffmpeg, bản đã tải, hay ffmpeg trong PATH). Rẻ: không chạy tiến trình nào."""
    return Path(io_utils.ffmpeg_executable()).is_file()


def status() -> dict[str, Any]:
    with _lock:
        return dict(_state)


def _set(**values: Any) -> None:
    with _lock:
        _state.update(values)


def _can_download() -> str:
    """Rỗng nếu tải được; không thì lý do (tiếng Việt) để báo người dùng."""
    if os.environ.get(ENV_DOWNLOAD, "1") == "0":
        return "tải bộ đọc nhạc đang bị tắt trên máy này"
    if _folder is None:
        return "chưa có thư mục để đặt bộ đọc nhạc"
    if sys.platform != "win32" or platform.machine().lower() not in ("amd64", "x86_64"):
        return "bản tải sẵn chỉ có cho Windows 64-bit - hãy cài ffmpeg cho máy này (có trong PATH) rồi nhập lại"
    return ""


def start() -> None:
    """Bắt đầu tải ở luồng nền. Gọi nhiều lần cũng chỉ một lượt; đang lỗi thì gọi lại là thử lại; đã có ffmpeg thì không làm gì."""
    global _thread
    with _lock:
        if _state["state"] == "downloading" and _thread is not None and _thread.is_alive():
            return
        if ready():
            _set(state="ready", error="")
            return
        reason = _can_download()
        if reason:
            _set(state="error", error=reason)
            return
        _set(state="downloading", done=0, total=WHEEL.size, error="")
        _thread = threading.Thread(target=_run, name="ffmpeg-setup", daemon=True)
        _thread.start()


def join(timeout: float | None = None) -> None:
    """Đợi luồng tải xong (bài thử)."""
    thread = _thread
    if thread is not None:
        thread.join(timeout)


def _reason(error: BaseException) -> str:
    if isinstance(error, studio_setup.SetupError):
        if error.__cause__ is not None:  # download() bọc lỗi mạng
            return "không tải được - kiểm tra kết nối mạng rồi thử lại"
        return "file tải về không đúng bản đã ghim (đã xoá) - thử lại"
    if isinstance(error, (zipfile.BadZipFile, KeyError)):
        return "gói tải về không có ffmpeg - thử lại"
    if isinstance(error, OSError):
        return f"không ghi được vào ổ đĩa ({error.strerror or error})"
    return f"lỗi không ngờ ({type(error).__name__}: {error})"


def _run() -> None:
    try:
        assert _folder is not None
        _folder.mkdir(parents=True, exist_ok=True)
        wheel = _folder / "imageio_ffmpeg.whl"
        studio_setup.download(WHEEL, wheel, lambda done, total: _set(done=done, total=total or WHEEL.size), lambda: False)
        _set(done=WHEEL.size)
        exe = _folder / EXE_NAME
        part = exe.with_name(exe.name + ".part")
        with zipfile.ZipFile(wheel) as bundle, bundle.open(MEMBER) as source, part.open("wb") as target:
            shutil.copyfileobj(source, target, 1 << 20)
        os.replace(part, exe)
        wheel.unlink(missing_ok=True)
        io_utils.use_downloaded_ffmpeg(exe)
        _set(state="ready", error="")
    except Exception as error:  # noqa: BLE001 - mọi lỗi đều thành một câu cho người dùng, không bao giờ im lặng
        _set(state="error", error=_reason(error))
