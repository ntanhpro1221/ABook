"""Màn chờ mở app chỉ là hình sách-loa trên nền app, không vòng nền xanh rừng của icon app.

Chủ sách 17-11 (ảnh màn chờ trên OPPO): "chỉ icon thôi, bỏ cái bao nền đi". Icon launcher, icon cửa sổ, favicon vẫn giữ nền.
"""
import math
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "mobile" / "android" / "app" / "src" / "main" / "res"
SPLASH = RES / "drawable" / "splash_icon.xml"
FOREST = ("#1f4c3c", "#0e2a21")


def _make_icons():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import make_icons
    finally:
        sys.path.pop(0)
    from PySide6.QtGui import QGuiApplication
    QGuiApplication.instance() or QGuiApplication([])
    return make_icons


def test_splash_drawable_has_no_background_disc():
    text = SPLASH.read_text(encoding="utf-8").lower()
    assert "<gradient" not in text and "aapt:attr" not in text, "màn chờ lại có nền gradient"
    for colour in FOREST:
        assert colour not in text, f"màn chờ dùng màu nền icon app {colour}"
    # Không path nào là hình tròn phủ cả khung (vòng nền cũ: M0,512A512,512 ...).
    assert not re.search(r'pathData="M0,512A512,512', text)


def test_splash_theme_keeps_icon_on_app_background():
    styles = (RES / "values" / "styles.xml").read_text(encoding="utf-8")
    assert '<item name="windowSplashScreenAnimatedIcon">@drawable/splash_icon</item>' in styles
    assert '<item name="windowSplashScreenIconBackgroundColor">@color/app_bg</item>' in styles


def test_splash_drawable_is_what_make_icons_writes():
    make_icons = _make_icons()
    assert SPLASH.read_text(encoding="utf-8") == make_icons.splash_icon()


def test_splash_glyph_fits_the_160dp_safe_circle_and_fills_it():
    make_icons = _make_icons()
    size = 1024
    image = make_icons.rasterize(make_icons._svg(make_icons.splash_body()), size)
    alpha = image.getchannel("A").load()
    centre = size / 2
    reach = max(math.hypot(x + 0.5 - centre, y + 0.5 - centre)
                for y in range(size) for x in range(size) if alpha[x, y] > 8)
    safe = size / 2 * make_icons.SPLASH_LOGO_DP / make_icons.SPLASH_FRAME_DP
    assert reach <= safe, f"hình bị Android cắt: mực tới {reach:.0f}, vòng an toàn {safe:.0f}"
    assert reach >= 0.88 * safe, f"hình quá nhỏ trong vòng an toàn: {reach:.0f} / {safe:.0f}"
    # Góc khung trong suốt: nền là app_bg của theme, không phải ô màu riêng.
    assert alpha[0, 0] == alpha[size - 1, size - 1] == 0
    assert alpha[int(centre), int(centre * 0.2)] == 0


@pytest.mark.parametrize("name", ["ic_launcher_background.xml"])
def test_launcher_icon_still_has_its_background(name):
    text = (RES / "drawable" / name).read_text(encoding="utf-8").lower()
    assert FOREST[0] in text and FOREST[1] in text


def test_desktop_and_web_loading_screens_show_no_background_icon():
    """Trang chờ của vỏ máy tính (shell/loading) và trang web lúc tải chưa vẽ icon app có nền; nếu sau này thêm logo thì dùng
    hình trần (abook/assets/icon/glyph.svg), không dùng icon app / launcher."""
    boxed = re.compile(r"app\.(ico|png|svg)|app_small\.svg|icon-(192|512)\.png|apple-touch-icon|#1f4c3c|#0e2a21", re.I)
    pages = [ROOT / "shell" / "loading" / "index.html", ROOT / "ui" / "index.html"]
    hits = []
    for page in pages:
        text = page.read_text(encoding="utf-8")
        body = text[text.lower().index("<body"):]  # <head> giữ favicon / icon cài lên màn hình chính - những icon đó cần nền
        hits += [f"{page.relative_to(ROOT).as_posix()}: {m.group(0)}" for m in boxed.finditer(body)]
    assert hits == [], f"màn chờ dùng icon có nền: {hits}"
