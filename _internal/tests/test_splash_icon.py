"""Màn chờ mở app chỉ là hình sách-loa trên nền app, không vòng nền xanh rừng của icon app.

Chủ sách 17-11 (ảnh màn chờ trên OPPO): "chỉ icon thôi, bỏ cái bao nền đi". Icon launcher, icon cửa sổ, favicon vẫn giữ nền.
Lead 18-11: màn chờ theo theme - drawable-night giữ giấy + sóng kem trên nền tối; drawable (theme sáng) đổi giấy viền xanh rừng,
sóng xanh rừng vì kem gần như mất trên nền sáng. Mỗi nét >= 3:1 với nền theme của nó; bìa cam giữ nguyên ở cả hai.
"""
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "mobile" / "android" / "app" / "src" / "main" / "res"
SPLASHES = {"light": RES / "drawable" / "splash_icon.xml", "night": RES / "drawable-night" / "splash_icon.xml"}
FOREST = ("#1f4c3c", "#0e2a21")
DESIGN = ROOT / "docs" / "DESIGN.md"
MIN_CONTRAST = 3.0


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


def _design_bg():
    """Hàng `--bg` của bảng màu DESIGN.md: {sáng, tối}."""
    row = re.search(r"^\| `--bg`[^|]*\| (#[0-9a-f]{6}) \| (#[0-9a-f]{6}) \|", DESIGN.read_text(encoding="utf-8"), re.M | re.I)
    assert row, "DESIGN.md mất hàng --bg"
    return {"light": row.group(1).lower(), "night": row.group(2).lower()}


def _app_bg(folder):
    text = (RES / folder / "colors.xml").read_text(encoding="utf-8")
    return re.search(r'<color name="app_bg">(#[0-9a-fA-F]{6})</color>', text).group(1).lower()


def _luminance(hex_colour):
    def channel(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _over(colour, alpha, under):
    return "#" + "".join(f"{round(int(colour[i:i + 2], 16) * alpha + int(under[i:i + 2], 16) * (1 - alpha)):02x}"
                         for i in (1, 3, 5))


def _contrast(a, b):
    lo, hi = sorted((_luminance(a), _luminance(b)))
    return (hi + 0.05) / (lo + 0.05)


def splash_inks(make_icons, *, night, bg):
    """{(vai, màu đã trộn alpha, tỉ lệ tương phản với nền)} của từng nét / mặt trong hình màn chờ, trừ bìa cam (Lead giữ nguyên).

    Gân trang nằm TRÊN giấy nên trộn alpha trên giấy. Ở bản tối gân là chi tiết bên trong giấy kem - mặt chạm nền là giấy, nên đo
    giấy; ở bản sáng giấy kem gần trùng nền, mặt chạm nền là viền xanh rừng, nên đo viền.
    """
    cover = {make_icons.TERRACOTTA.lower(), make_icons.TERRACOTTA_LIGHT.lower()}
    papers = {make_icons.PAPER.lower(), make_icons.PAPER_SHADE.lower()}
    inks = set()
    for node in ET.fromstring(make_icons._svg(make_icons.splash_body(night=night))).iter():
        alpha = float(node.get("opacity", "1"))
        stroke, fill = (node.get("stroke") or "").lower(), (node.get("fill") or "").lower()
        if stroke and stroke not in cover:
            if fill in papers:
                role, under = "viền giấy", bg
            elif fill == "none":
                role, under = "sóng", bg
            else:
                role, under = "gân giấy", make_icons.PAPER.lower()
            if not (night and role == "gân giấy"):
                inks.add((role, _over(stroke, alpha, under)))
        if fill in papers and night:
            inks.add(("giấy", _over(fill, alpha, bg)))
    return sorted((role, colour, round(_contrast(colour, bg), 2)) for role, colour in inks)


@pytest.mark.parametrize("theme", ["light", "night"])
def test_splash_drawable_has_no_background_disc(theme):
    text = SPLASHES[theme].read_text(encoding="utf-8").lower()
    assert "<gradient" not in text and "aapt:attr" not in text, "màn chờ lại có nền gradient"
    assert FOREST[1] not in text, "màn chờ dùng màu đáy nền icon app"
    # Không path nào là hình tròn phủ cả khung (vòng nền cũ: M0,512A512,512 ...), không mặt nào tô bằng màu nền icon app.
    assert not re.search(r'pathdata="m0,512a512,512', text)
    assert f'fillcolor="{FOREST[0]}"' not in text


def test_night_splash_keeps_the_cream_glyph_and_light_splash_uses_forest_ink():
    night = SPLASHES["night"].read_text(encoding="utf-8").lower()
    light = SPLASHES["light"].read_text(encoding="utf-8").lower()
    assert FOREST[0] not in night and "#f5e8cc" in night
    assert f'strokecolor="{FOREST[0]}"' in light and "#f5e8cc" not in light
    for text in (night, light):  # bìa cam giống hệt ở cả hai theme
        assert "#e0764f" in text and "#f3a383" in text


def test_splash_theme_keeps_icon_on_app_background_in_both_modes():
    styles = (RES / "values" / "styles.xml").read_text(encoding="utf-8")
    assert '<item name="windowSplashScreenAnimatedIcon">@drawable/splash_icon</item>' in styles
    assert '<item name="windowSplashScreenBackground">@color/app_bg</item>' in styles
    assert '<item name="windowSplashScreenIconBackgroundColor">@color/app_bg</item>' in styles
    night_styles = (RES / "values-night" / "styles.xml").read_text(encoding="utf-8")
    assert "windowSplashScreen" not in night_styles, "theme tối ghi đè màn chờ - phải lấy app_bg của values-night"
    assert {"light": _app_bg("values"), "night": _app_bg("values-night")} == _design_bg()


@pytest.mark.parametrize("theme", ["light", "night"])
def test_splash_drawable_is_what_make_icons_writes(theme):
    make_icons = _make_icons()
    assert SPLASHES[theme].read_text(encoding="utf-8") == make_icons.splash_icon(night=theme == "night")


@pytest.mark.parametrize("theme", ["light", "night"])
def test_splash_glyph_fits_the_160dp_safe_circle_and_fills_it(theme):
    make_icons = _make_icons()
    size = 1024
    image = make_icons.rasterize(make_icons._svg(make_icons.splash_body(night=theme == "night")), size)
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


@pytest.mark.parametrize("theme", ["light", "night"])
def test_splash_ink_contrasts_with_its_theme_background(theme):
    make_icons = _make_icons()
    bg = _design_bg()[theme]
    inks = splash_inks(make_icons, night=theme == "night", bg=bg)
    roles = {role for role, _, _ in inks}
    assert roles == ({"sóng", "giấy"} if theme == "night" else {"sóng", "viền giấy", "gân giấy"}), inks
    weak = [ink for ink in inks if ink[2] < MIN_CONTRAST]
    assert weak == [], f"nét màn chờ {theme} mờ trên nền {bg}: {weak}"


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
