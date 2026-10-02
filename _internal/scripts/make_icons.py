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
    mobile/android/app/src/main/res/...           launcher (thường, tròn, thích ứng + đơn sắc Android 13), màn chờ

Cỡ 16-32 px vẽ bản GIẢN LƯỢC (ba tay sách, nét dày, không đường trang): thu nhỏ bản đầy đủ xuống 16 px chỉ còn vệt nhoè.
Qt vẽ SVG (QtSvg), Pillow ghi ICO nhiều cỡ.
"""
from __future__ import annotations

import argparse
import math
import os
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
# (thư mục, cỡ icon 48dp, cỡ lớp thích ứng 108dp)
DENSITIES = (("mdpi", 48, 108), ("hdpi", 72, 162), ("xhdpi", 96, 216), ("xxhdpi", 144, 324), ("xxxhdpi", 192, 432))
SPLASHES = {"drawable": (480, 320)} | {
    f"drawable-{o}-{d}": size for d, (p, l) in {"mdpi": ((320, 480), (480, 320)), "hdpi": ((480, 800), (800, 480)),
                                                "xhdpi": ((720, 1280), (1280, 720)), "xxhdpi": ((960, 1600), (1600, 960)),
                                                "xxxhdpi": ((1280, 1920), (1920, 1280))}.items()
    for o, size in (("port", p), ("land", l))}

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


def app_icon(*, small: bool = False, round_: bool = False) -> str:
    """Ô vuông bo góc (Windows, launcher cũ) hoặc hình tròn (launcher tròn); hình sách-loa chiếm ~55% bề ngang."""
    shape = ('<circle cx="512" cy="512" r="512" fill="url(#forest)"/>' if round_
             else '<rect width="1024" height="1024" rx="228" fill="url(#forest)"/>')
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


def adaptive_foreground(*, mono: str | None = None) -> str:
    """Lớp trước của icon thích ứng (108dp, launcher cắt lấy 72dp giữa): hình thu 72/108 để trông như ô icon app."""
    return _svg(_placed(glyph(mono=mono), 72 / 108))


def splash(width: int, height: int) -> str:
    scale = min(width, height) / 1024 * 0.55
    body = _placed(glyph(), scale, (width / 2, height / 2))
    background = f'<rect width="{width}" height="{height}" fill="url(#forest)"/>'
    return _svg(background + body, _forest(), width, height)


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


def write_android() -> list[Path]:
    written = []
    monochrome = adaptive_foreground(mono="#ffffff")
    for folder, launcher, layer in DENSITIES:
        target = RES / f"mipmap-{folder}"
        for name, markup, size in (("ic_launcher.png", app_icon(small=launcher < 96), launcher),
                                   ("ic_launcher_round.png", app_icon(small=launcher < 96, round_=True), launcher),
                                   ("ic_launcher_foreground.png", adaptive_foreground(), layer),
                                   ("ic_launcher_monochrome.png", monochrome, layer)):
            rasterize(markup, size).save(target / name)
            written.append(target / name)
    (RES / "drawable" / "ic_launcher_background.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!-- Nền icon thích ứng: xanh rừng, đậm dần xuống dưới (scripts/make_icons.py). -->\n'
        '<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">\n'
        f'    <gradient android:angle="270" android:startColor="{FOREST_TOP}" android:endColor="{FOREST_BOTTOM}" />\n'
        '</shape>\n', encoding="utf-8", newline="\n")
    for name in ("ic_launcher.xml", "ic_launcher_round.xml"):
        (RES / "mipmap-anydpi-v26" / name).write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
            '    <background android:drawable="@drawable/ic_launcher_background" />\n'
            '    <foreground android:drawable="@mipmap/ic_launcher_foreground" />\n'
            '    <monochrome android:drawable="@mipmap/ic_launcher_monochrome" />\n'
            '</adaptive-icon>\n', encoding="utf-8", newline="\n")
    (RES / "values" / "ic_launcher_background.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        f'    <color name="ic_launcher_background">{FOREST_TOP.upper()}</color>\n</resources>\n',
        encoding="utf-8", newline="\n")
    for folder, (width, height) in SPLASHES.items():
        rasterize(splash(width, height), width, height).convert("RGB").save(RES / folder / "splash.png")
        written.append(RES / folder / "splash.png")
    return written


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
    if args.preview:
        preview(args.preview)
    print(ASSETS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
