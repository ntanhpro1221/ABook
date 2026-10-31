"""Hồ sơ người dùng riêng cho mọi lượt chạy ABookDesk của công cụ đo / chụp / smoke.

LOCALAPPDATA / APPDATA trong môi trường chỉ đổi những chỗ app tự ghép từ biến môi trường (desktop_qt.ini, tiến độ chờ gửi).
QStandardPaths (cache nhạc music_pcm, ...) hỏi SHGetKnownFolderPath, mà hàm ấy theo USERPROFILE của tiến trình: không có USERPROFILE
riêng thì cache của lượt đo vào thẳng %LOCALAPPDATA%\\ABook của chủ máy (30-10: 40 bài nhạc thử, 300 MB, từ các lượt đo mở lại).
"""
import os
from pathlib import Path

PROFILE = "profile"


def isolate(env: dict) -> dict:
    """Đặt USERPROFILE riêng (thư mục `profile` trong LOCALAPPDATA đã đổi của env) và tạo AppData\\Local, AppData\\Roaming
    trong đó - thiếu thư mục thì SHGetKnownFolderPath hỏng và Qt trả đường rỗng. Trả về chính env."""
    local = env.get("LOCALAPPDATA")
    real = os.environ.get("LOCALAPPDATA")
    if not local or (real and os.path.normcase(os.path.abspath(local)) == os.path.normcase(os.path.abspath(real))):
        raise RuntimeError("Lượt chạy app phải có LOCALAPPDATA riêng trước khi tách hồ sơ")
    profile = Path(local) / PROFILE
    for sub in ("AppData/Local", "AppData/Roaming"):
        (profile / sub).mkdir(parents=True, exist_ok=True)
    env["USERPROFILE"] = str(profile)
    return env
