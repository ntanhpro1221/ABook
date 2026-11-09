"""Dựng MỌI icon của ABook từ một nguồn vector - chủ sách chốt 27-09.

Hình: một cuốn sách bìa cứng mở XOÈ, nhìn từ đầu sách, thành cái loa - gáy tròn là thân loa, xấp giấy xoè là nón loa,
hai nét sóng âm toả ra từ mép giấy. Phối màu RỪNG + ĐẤT NUNG (nền xanh rừng, bìa đất nung, giấy kem). Không có chữ.

Hai loại file là biến thể của chính icon app:
    .abook      ô icon app gấp góc trang - góc gấp của "file" cũng là góc gấp đánh dấu trang sách
    .abookproj  y như .abook nhưng hai nét sóng là NÉT ĐỨT - cuốn sách chưa thành tiếng

    runtime/.venv/Scripts/python.exe scripts/make_icons.py [--preview <thư mục>]

Ra (vẽ lại toàn bộ mỗi lần chạy):
    abook/assets/app.ico + .png   icon app Windows: cửa sổ, khay, shortcut (16-256 px)
    abook/assets/book_file.ico + .png      file .abook
    abook/assets/project_file.ico + .png   file .abookproj
    abook/assets/icon/*.svg                bản vector gốc: phóng to bao nhiêu cũng không vỡ
    mobile/android/app/src/main/res/...           launcher thường + tròn (PNG, Android 7); lớp thích ứng, đơn sắc Android 13, màn chờ,
                                                  icon thông báo là VectorDrawable - nét luôn sắc dù hệ thống phóng bao nhiêu
    ui/public/*.png                       "Thêm vào màn hình chính" của trình duyệt (iPhone, iPad, Android): tràn viền, hệ điều hành tự bo

Cỡ 16-32 px vẽ bản GIẢN LƯỢC (ba tay sách, nét dày, không đường trang): thu nhỏ bản đầy đủ xuống 16 px chỉ còn vệt nhoè.
Qt vẽ SVG (QtSvg), Pillow ghi ICO nhiều cỡ.
"""
from __future__ import annotations

import argparse
import math
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PIL import Image
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "abook" / "assets"
RES = ROOT / "mobile" / "android" / "app" / "src" / "main" / "res"

FOREST_TOP, FOREST_BOTTOM = "#1f4c3c", "#0e2a21"
TERRACOTTA, TERRACOTTA_LIGHT = "#e0764f", "#f3a383"
PAPER, PAPER_SHADE, PAGE_LINE = "#fbf3e2", "#efe2c4", "#cdb68c"
WAVE = "#f5e8cc"
FLAP, FLAP_EDGE = "#fbf3e2", "#e3d2ae"

WINDOWS_SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
SMALL_MAX = 32
# (thư mục, cỡ icon 48dp)
DENSITIES = (("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192))

Pt = tuple[float, float]


# ---- hình học (toạ độ 1024 x 1024) ------------------------------------------------------------------------------


def _polar(c: Pt, r: float, degrees: float) -> Pt:
    a = math.radians(degrees)
    return c[0] + r * math.cos(a), c[1] + r * math.sin(a)


def _arc(c: Pt, r: float, a0: float, a1: float, n: int = 40) -> list[Pt]:
    return [_polar(c, r, a0 + (a1 - a0) * i / n) for i in range(n + 1)]


def _points(points: list[Pt]) -> str:
    return " ".join(f"{x:.1f} {y:.1f}" for x, y in points)


def _dashes(radius: float, span: float, width: float, count: int) -> str:
    """Nét đứt đều hai đầu: `count` gạch, gạch đầu và cuối chạm đúng hai đầu cung (đầu tròn tính vào độ dài gạch)."""
    length = radius * math.radians(2 * span)
    visible = length / (count * 2 - 1) * 1.15
    gap = (length - count * visible) / (count - 1)
    return f' stroke-dasharray="{max(0.1, visible - width):.1f} {gap + width:.1f}"'


def glyph(*, small: bool = False, dashed: bool = False, mono: str | None = None) -> str:
    """Sách mở xoè thành cái loa. small: bản giản lược cho 16-32 px; dashed: sóng nét đứt (.abookproj);
    mono: tô MỘT màu (icon đơn sắc của Android 13, hệ thống tự nhuộm)."""
    spine, half, reach, square = (296.0, 512.0), 40.0, 290.0, 20.0
    board, spine_r, wave_w, groups = (44.0, 52.0, 56.0, 3) if small else (30.0, 44.0, 38.0, 5)
    wave_start, wave_gap = (78.0, 98.0) if small else (74.0, 88.0)
    cover, cover_light = (mono, mono) if mono else (TERRACOTTA, TERRACOTTA_LIGHT)
    parts: list[str] = []
    for index in range(2):
        radius = reach + square + wave_start + wave_gap * index
        span = half * (0.9 - 0.07 * index)
        colour = mono or WAVE
        opacity = 1.0 if index == 0 or mono else 0.55
        dash = _dashes(radius, span, wave_w, 3 if small else 4) if dashed else ""
        parts.append(f'<path d="M {_points(_arc(spine, radius, -span, span))}" stroke="{colour}"'
                     f' stroke-width="{wave_w}" fill="none" stroke-linecap="round" opacity="{opacity}"{dash}/>')
    inner = half - math.degrees(board / 2 / reach) * 2.2  # giấy nằm giữa hai tấm bìa
    gap = 2.0 if small else 1.2
    for group in range(groups):
        a0 = -inner + 2 * inner * group / groups + gap / 2
        a1 = -inner + 2 * inner * (group + 1) / groups - gap / 2
        end = reach - 10 * abs(group - (groups - 1) / 2) / ((groups - 1) / 2)  # mép giấy so le như sách thật xoè
        wedge = [spine, *_arc(spine, end, a0, a1, 16)]
        fill = mono or (PAPER if group % 2 == 0 else PAPER_SHADE)
        parts.append(f'<path d="M {_points(wedge)} Z" fill="{fill}"/>')
        if not small and not mono:
            for k in (1, 2):
                x, y = _polar(spine, end - 2, a0 + (a1 - a0) * k / 3)
                parts.append(f'<path d="M {spine[0]} {spine[1]} L {x:.1f} {y:.1f}" stroke="{PAGE_LINE}"'
                             f' stroke-width="3" opacity="0.8"/>')
    for sign in (-1, 1):
        x, y = _polar(spine, reach + square, sign * half)
        parts.append(f'<path d="M {spine[0]} {spine[1]} L {x:.1f} {y:.1f}" stroke="{cover}" stroke-width="{board}"'
                     f' stroke-linecap="round"/>')
        if not small and not mono:
            (sx, sy), (ex, ey) = _polar(spine, 60, sign * half), _polar(spine, reach + square - 6, sign * half)
            parts.append(f'<path d="M {sx:.1f} {sy:.1f} L {ex:.1f} {ey:.1f}" stroke="{cover_light}"'
                         f' stroke-width="{board * 0.25}" stroke-linecap="round" opacity="0.9"/>')
    parts.append(f'<circle cx="{spine[0]}" cy="{spine[1]}" r="{spine_r}" fill="{cover}"/>')
    if not small and not mono:
        parts.append(f'<path d="M {_points(_arc(spine, spine_r * 0.62, 120, 240, 20))}" stroke="{cover_light}"'
                     f' stroke-width="7" fill="none" stroke-linecap="round" opacity="0.8"/>')
    return "".join(parts)


GLYPH_CENTRE = (520.0, 512.0)  # tâm thị giác của hình (bề ngang gồm cả sóng)


def _placed(body: str, scale: float, centre: Pt = (512.0, 512.0)) -> str:
    dx, dy = centre[0] - GLYPH_CENTRE[0] * scale, centre[1] - GLYPH_CENTRE[1] * scale
    return f'<g transform="translate({dx:.2f} {dy:.2f}) scale({scale:.4f})">{body}</g>'


def _svg(body: str, defs: str = "", width: int = 1024, height: int = 1024) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
            f'<defs>{defs}</defs>{body}</svg>')


def _forest(gid: str = "forest") -> str:
    return (f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{FOREST_TOP}"/>'
            f'<stop offset="1" stop-color="{FOREST_BOTTOM}"/></linearGradient>')


def app_icon(*, small: bool = False, round_: bool = False, square: bool = False) -> str:
    """Ô vuông bo góc (Windows, launcher cũ), hình tròn (launcher tròn) hoặc vuông tràn viền (`square`: iOS và trình duyệt tự bo,
    góc trong suốt sẽ hiện thành đen); hình sách-loa chiếm ~55% bề ngang."""
    shape = ('<circle cx="512" cy="512" r="512" fill="url(#forest)"/>' if round_
             else f'<rect width="1024" height="1024" rx="{0 if square else 228}" fill="url(#forest)"/>')
    scale = (1.08 if small else 1.0) * (0.92 if round_ else 1.0)
    return _svg(shape + _placed(glyph(small=small), scale), _forest())


def file_icon(*, small: bool = False, dashed: bool = False) -> str:
    """Ô icon app, nhỏ hơn một chút như icon tài liệu, góc trên phải gấp xuống (mặt sau là giấy).

    Gấp như gấp giấy thật: nếp gấp là một nhát thẳng (hai đầu sắc), còn vạt lật xuống CHÍNH LÀ góc bo cũ của ô,
    phản chiếu qua nếp gấp - nên đầu vạt giữ đúng bán kính bo của ba góc kia (chủ sách 27-09: đầu vạt không được nhọn
    hơn chính nó lúc chưa gập).
    """
    inset, fold, r = 64.0, 272.0, 896 * 228 / 1024  # cùng độ tròn với icon app (22% cạnh ô)
    x0, y0, x1, y1 = inset, inset, 1024 - inset, 1024 - inset
    a, b = (x1 - fold, y0), (x1, y0 + fold)  # hai đầu nếp gấp
    outline = (f"M {x0 + r} {y0} H {a[0]} L {b[0]} {b[1]} V {y1 - r} A {r} {r} 0 0 1 {x1 - r} {y1}"
               f" H {x0 + r} A {r} {r} 0 0 1 {x0} {y1 - r} V {y0 + r} A {r} {r} 0 0 1 {x0 + r} {y0} Z")
    # góc bo (tâm (x1 - r, y0 + r)) lật qua đường a-b: tâm sang (x1 - fold + r, y0 + fold - r), bán kính giữ nguyên
    flap_path = (f"M {a[0]} {a[1]} V {y0 + fold - r} A {r} {r} 0 0 0 {x1 - fold + r} {y0 + fold} H {b[0]} Z")
    shadow = f'<path d="{flap_path}" fill="#000000" opacity="0.22" transform="translate(-8 14)"/>'
    flap = (f'<path d="{flap_path}" fill="{FLAP}" stroke="{FLAP_EDGE}" stroke-width="6"'
            f' stroke-linejoin="round"/>')
    body = _placed(glyph(small=small, dashed=dashed), 0.92 if small else 0.88, (512.0, 530.0))
    return _svg(f'<path d="{outline}" fill="url(#forest)"/>{body}{shadow}{flap}', _forest())


def adaptive_foreground_body(*, mono: str | None = None) -> str:
    """Lớp trước của icon thích ứng (108dp, launcher cắt lấy 72dp giữa): hình thu 72/108 để trông như ô icon app."""
    return _placed(glyph(mono=mono), 72 / 108)


# ---- vẽ + ghi --------------------------------------------------------------------------------------------------


def rasterize(markup: str, width: int, height: int | None = None) -> Image.Image:
    height = height or width
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(markup.encode("utf-8"))).render(painter, QRectF(0, 0, width, height))
    painter.end()
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    return Image.frombuffer("RGBA", (width, height), bytes(image.constBits()), "raw", "RGBA",
                            image.bytesPerLine(), 1).copy()


def write_ico(path: Path, full: str, small: str) -> None:
    images = [rasterize(small if size <= SMALL_MAX else full, size) for size in WINDOWS_SIZES]
    images[-1].save(path, format="ICO", sizes=[(s, s) for s in WINDOWS_SIZES], append_images=images[:-1])
    images[-1].save(path.with_suffix(".png"))


# ---- VectorDrawable (Android) ----------------------------------------------------------------------------------
# Chỉ những gì glyph() dùng: <g transform="translate() scale()">, <path> (nét / tô, opacity), <circle>.

ANDROID_NS = 'xmlns:android="http://schemas.android.com/apk/res/android"'
# Màn chờ Android 12+ (và core-splashscreen ở bản cũ): khung 240 dp, hệ thống chỉ giữ vòng tròn 160 dp giữa khung. Logo là icon app
# tròn vẽ đúng trong vòng ấy: hãng nào cắt ô vuông bo góc (OPPO) cũng thấy trọn hình, và vector thì không nhoè khi phóng.
SPLASH_FRAME_DP, SPLASH_LOGO_DP = 240.0, 160.0
# Nút Đóng trên thông báo phát (Lucide "x", khung 24).
CLOSE_PATH = "M18,6L6,18M6,6L18,18"


def _vector_path(d: str) -> str:
    """'M x y x y ...' của SVG (các cặp sau M là đường thẳng) -> pathData có L tường minh."""
    def one(match: re.Match[str]) -> str:
        numbers = match.group(1).split()
        pairs = [f"{numbers[i]},{numbers[i + 1]}" for i in range(0, len(numbers), 2)]
        return "M" + pairs[0] + ("L" + " ".join(pairs[1:]) if len(pairs) > 1 else "")
    return re.sub(r"M\s*([-\d.\s]+)", one, d).replace(" Z", "Z").strip()


def _vector_body(markup: str, depth: int = 1) -> str:
    out: list[str] = []

    def walk(node: ET.Element, level: int) -> None:
        pad = "    " * level
        tag = node.tag.rsplit("}", 1)[-1]
        if tag == "g":
            move = re.search(r"translate\(([-\d.]+) ([-\d.]+)\) scale\(([-\d.]+)\)", node.get("transform", ""))
            dx, dy, s = move.groups() if move else ("0", "0", "1")
            out.append(f'{pad}<group android:translateX="{dx}" android:translateY="{dy}" android:scaleX="{s}" android:scaleY="{s}">')
            for child in node:
                walk(child, level + 1)
            out.append(f"{pad}</group>")
            return
        if tag == "circle":
            cx, cy, r = (float(node.get(k)) for k in ("cx", "cy", "r"))
            data = f"M{cx - r:g},{cy:g}A{r:g},{r:g} 0 1,1 {cx + r:g},{cy:g}A{r:g},{r:g} 0 1,1 {cx - r:g},{cy:g}Z"
        elif tag == "path":
            data = _vector_path(node.get("d", ""))
        else:
            for child in node:
                walk(child, level)
            return
        alpha = node.get("opacity")
        attrs = [f'android:pathData="{data}"']
        fill, stroke = node.get("fill"), node.get("stroke")
        if fill and fill != "none":
            attrs.append(f'android:fillColor="{fill}"')
            if alpha and float(alpha) < 1:
                attrs.append(f'android:fillAlpha="{alpha}"')
        if stroke:
            attrs += [f'android:strokeColor="{stroke}"', f'android:strokeWidth="{node.get("stroke-width", "1")}"']
            if node.get("stroke-linecap"):
                attrs.append(f'android:strokeLineCap="{node.get("stroke-linecap")}"')
            if alpha and float(alpha) < 1:
                attrs.append(f'android:strokeAlpha="{alpha}"')
        out.append(f"{pad}<path " + " ".join(attrs) + " />")

    walk(ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg">{markup}</svg>'), depth)
    return "\n".join(out)


def _vector(note: str, size_dp: float, body: str, viewport: float = 1024.0, aapt: bool = False) -> str:
    extra = '\n    xmlns:aapt="http://schemas.android.com/aapt"' if aapt else ""
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            f'<!-- {note} Sinh bởi scripts/make_icons.py - đừng sửa tay. -->\n'
            f'<vector {ANDROID_NS}{extra}\n    android:width="{size_dp:g}dp" android:height="{size_dp:g}dp"\n'
            f'    android:viewportWidth="{viewport:g}" android:viewportHeight="{viewport:g}">\n{body}\n</vector>\n')


def splash_icon() -> str:
    scale = SPLASH_LOGO_DP / SPLASH_FRAME_DP
    offset = 1024 * (1 - scale) / 2
    circle = ('        <path android:pathData="M0,512A512,512 0 1,1 1024,512A512,512 0 1,1 0,512Z">\n'
              '            <aapt:attr name="android:fillColor">\n'
              '                <gradient android:type="linear" android:startX="0" android:startY="0" android:endX="0" android:endY="1024"\n'
              f'                    android:startColor="{FOREST_TOP}" android:endColor="{FOREST_BOTTOM}" />\n'
              '            </aapt:attr>\n        </path>')
    body = (f'    <group android:translateX="{offset:.2f}" android:translateY="{offset:.2f}" android:scaleX="{scale:.4f}" android:scaleY="{scale:.4f}">\n'
            f'{circle}\n{_vector_body(_placed(glyph(), 0.92), depth=2)}\n    </group>')
    return _vector("Màn chờ: icon app tròn trong vòng 160 dp của khung 240 dp (Android 12+ chỉ giữ vòng ấy).", SPLASH_FRAME_DP, body, aapt=True)


def notification_icon() -> str:
    """Icon nhỏ của mọi thông báo: hình giản lược (đọc được ở 24 dp), một màu - hệ thống tự nhuộm."""
    return _vector("Icon nhỏ của mọi thông báo (một màu, hệ thống nhuộm).", 24,
                   _vector_body(_placed(glyph(small=True, mono="#ffffff"), 1.45)))


def close_icon() -> str:
    return _vector("Nút Đóng trên thông báo phát (Lucide x).", 24,
                   f'    <path android:pathData="{CLOSE_PATH}" android:strokeColor="#ffffff" android:strokeWidth="2"'
                   ' android:strokeLineCap="round" android:strokeLineJoin="round" />', viewport=24)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def write_android() -> list[Path]:
    """Launcher thường / tròn vẫn là PNG theo mật độ (Android 7 chưa có icon thích ứng); mọi thứ còn lại là vector."""
    written = []
    for folder, launcher in DENSITIES:
        target = RES / f"mipmap-{folder}"
        for name, markup in (("ic_launcher.png", app_icon(small=launcher < 96)),
                             ("ic_launcher_round.png", app_icon(small=launcher < 96, round_=True))):
            rasterize(markup, launcher).save(target / name)
            written.append(target / name)
    drawable = RES / "drawable"
    written += [
        _write(drawable / "ic_launcher_foreground.xml", _vector(
            "Lớp trước icon thích ứng (108 dp, launcher giữ 72 dp giữa).", 108, _vector_body(adaptive_foreground_body()))),
        _write(drawable / "ic_launcher_monochrome.xml", _vector(
            "Icon đơn sắc Android 13 (hệ thống tự nhuộm).", 108, _vector_body(adaptive_foreground_body(mono="#ffffff")))),
        _write(drawable / "splash_icon.xml", splash_icon()),
        _write(drawable / "ic_notification.xml", notification_icon()),
        _write(drawable / "ic_notification_close.xml", close_icon()),
        _write(drawable / "ic_launcher_background.xml",
               '<?xml version="1.0" encoding="utf-8"?>\n'
               '<!-- Nền icon thích ứng: xanh rừng, đậm dần xuống dưới (scripts/make_icons.py). -->\n'
               '<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">\n'
               f'    <gradient android:angle="270" android:startColor="{FOREST_TOP}" android:endColor="{FOREST_BOTTOM}" />\n'
               '</shape>\n'),
    ]
    for name in ("ic_launcher.xml", "ic_launcher_round.xml"):
        written.append(_write(RES / "mipmap-anydpi-v26" / name,
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
            '    <background android:drawable="@drawable/ic_launcher_background" />\n'
            '    <foreground android:drawable="@drawable/ic_launcher_foreground" />\n'
            '    <monochrome android:drawable="@drawable/ic_launcher_monochrome" />\n'
            '</adaptive-icon>\n'))
    written.append(_write(RES / "values" / "ic_launcher_background.xml",
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        f'    <color name="ic_launcher_background">{FOREST_TOP.upper()}</color>\n</resources>\n'))
    return written


# Trang nghe qua trình duyệt (apple-touch-icon + web app manifest trong ui/index.html): tên file cố định vì index.html trỏ tới.
WEB_ICONS = (("apple-touch-icon.png", 180), ("icon-192.png", 192), ("icon-512.png", 512))


def write_web() -> list[Path]:
    target = ROOT / "ui" / "public"
    target.mkdir(parents=True, exist_ok=True)
    for name, size in WEB_ICONS:
        rasterize(app_icon(square=True), size).convert("RGB").save(target / name)
    return [target / name for name, _ in WEB_ICONS]


def preview(folder: Path) -> None:
    """Các cỡ trên nền sáng và nền tối, như Explorer / thanh tác vụ ở hai chế độ."""
    folder.mkdir(parents=True, exist_ok=True)
    rows = (("app", app_icon(), app_icon(small=True)), ("abook", file_icon(), file_icon(small=True)),
            ("abookproj", file_icon(dashed=True), file_icon(small=True, dashed=True)))
    sizes = (256, 128, 64, 48, 32, 24, 16)
    width = sum(sizes) + 24 * (len(sizes) + 1)
    sheet = Image.new("RGBA", (width, len(rows) * 2 * 280), (255, 255, 255, 255))
    for index, (_name, full, small) in enumerate(rows):
        for band, colour in ((0, (255, 255, 255, 255)), (1, (32, 32, 32, 255))):
            top = (index * 2 + band) * 280
            sheet.paste(colour, (0, top, width, top + 280))
            x = 24
            for size in sizes:
                sheet.alpha_composite(rasterize(small if size <= SMALL_MAX else full, size), (x, top + 12 + 256 - size))
                x += size + 24
    sheet.save(folder / "icons_preview.png")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--preview", type=Path, default=None, help="thư mục ghi bảng xem trước các cỡ")
    parser.add_argument("--no-android", action="store_true", help="không ghi tài nguyên Android")
    args = parser.parse_args()
    app = QGuiApplication([])  # noqa: F841 - QtSvg cần một ứng dụng Qt
    sources = ASSETS / "icon"
    sources.mkdir(parents=True, exist_ok=True)
    for name, markup in (("app.svg", app_icon()), ("app_small.svg", app_icon(small=True)),
                         ("abook.svg", file_icon()), ("abookproj.svg", file_icon(dashed=True)),
                         ("glyph.svg", _svg(glyph())), ("glyph_mono.svg", _svg(glyph(mono="#000000")))):
        (sources / name).write_text(markup + "\n", encoding="utf-8", newline="\n")
    write_ico(ASSETS / "app.ico", app_icon(), app_icon(small=True))
    write_ico(ASSETS / "book_file.ico", file_icon(), file_icon(small=True))
    write_ico(ASSETS / "project_file.ico", file_icon(dashed=True), file_icon(small=True, dashed=True))
    if not args.no_android:
        write_android()
    write_web()
    if args.preview:
        preview(args.preview)
    print(ASSETS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
