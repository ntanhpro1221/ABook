"""App máy tính Qt dùng icon bo góc của Windows ở mọi chỗ (cửa sổ, thanh tác vụ, khay, file exe).

Chủ sách 29-10 (ảnh thanh tác vụ): "icon không được bo tròn" - bản Qt lấy icon vuông tràn viền của web
(ui/public/icon-192.png, icon maskable cho điện thoại) nên hiện thành ô vuông giữa các icon bo góc.
"""
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
QT = ROOT / "desktop_qt"
ICO = ROOT / "abook" / "assets" / "app.ico"


def test_qt_never_uses_the_square_web_icon():
    hits = []
    for path in [QT / "CMakeLists.txt", *QT.glob("src/*.cpp"), *QT.glob("qml/*.qml")]:
        if re.search(r"ui/public/icon-|/app/icon-\d+", path.read_text(encoding="utf-8")):
            hits.append(path.relative_to(ROOT).as_posix())
    assert hits == [], f"dùng icon vuông của web: {hits}"


def test_exe_window_and_tray_use_app_ico():
    cmake = (QT / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "appicon.rc" in cmake and "abook/assets/app.ico" in cmake
    assert ":/app/app.ico" in (QT / "src" / "main.cpp").read_text(encoding="utf-8")
    assert "qrc:/app/app.ico" in (QT / "qml" / "DesktopTray.qml").read_text(encoding="utf-8")


def test_app_ico_has_rounded_transparent_corners():
    with Image.open(ICO) as ico:
        for size in sorted(ico.info["sizes"]):
            ico.size = size
            frame = ico.convert("RGBA")
            w, h = frame.size
            if w < 24:
                continue
            assert frame.getpixel((0, 0))[3] == 0 and frame.getpixel((w - 1, h - 1))[3] == 0, f"{size}: góc không trong suốt"
            assert frame.getpixel((w // 2, h // 2))[3] == 255
