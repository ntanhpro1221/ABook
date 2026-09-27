"""Vẽ icon cho file sách của app (webui/bookfile.py): mọi file mang đuôi ấy hiện icon này trong Explorer, như .rar, .psd.

    runtime/.venv/Scripts/python.exe scripts/make_book_file_icon.py [--preview <png>]

Cùng bộ màu với icon app (ebook_reader/assets/ebook_reader.png): nền xanh navy, sách mở màu kem, sóng âm màu cyan -
nhưng là một TRANG GIẤY GẬP GÓC như mọi icon tài liệu của Windows, để nhìn là biết "file", không lẫn với app. Cỡ lớn vẽ
ở 1024 px rồi thu nhỏ; cỡ 16-32 px vẽ riêng bản giản lược, vì thu nhỏ bản đầy đủ xuống 16 px chỉ còn một vệt nhoè.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ebook_reader" / "assets" / "book_file.ico"
NAVY = (23, 35, 64, 255)
RIM = (62, 84, 134, 255)
FOLD = (52, 74, 122, 255)
CREAM = (251, 243, 224, 255)
CYAN = (34, 195, 214, 255)
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)


def _page(draw: ImageDraw.ImageDraw, size: float, fold: float, rim: float) -> None:
    """Trang giấy dọc, góc trên phải gập xuống. Viền sáng hơn nền trang: nổi được cả trên nền tối của Explorer."""
    left, top, right, bottom = size * 0.16, size * 0.05, size * 0.84, size * 0.95
    corner = size * 0.045
    outline = [(left + corner, top), (right - fold, top), (right, top + fold), (right, bottom - corner),
               (right - corner, bottom), (left + corner, bottom), (left, bottom - corner), (left, top + corner)]
    draw.polygon(outline, fill=RIM)
    inset = [(x + (rim if x < size / 2 else -rim), y + (rim if y < size / 2 else -rim)) for x, y in outline]
    draw.polygon(inset, fill=NAVY)
    draw.polygon([(right - fold, top), (right - fold, top + fold), (right, top + fold)], fill=FOLD)


def _curve(a: tuple[float, float], control: tuple[float, float], b: tuple[float, float], steps: int = 12):
    return [((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * control[0] + t * t * b[0],
             (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * control[1] + t * t * b[1])
            for t in (index / steps for index in range(steps + 1))]


def _book(draw: ImageDraw.ImageDraw, cx: float, cy: float, width: float) -> None:
    """Sách mở như trên icon app: hai trang kem, gáy giữa, mép trên phẳng, mép dưới võng về gáy."""
    half, height, gap = width / 2, width * 0.66, width * 0.03
    top, bottom = cy - height / 2, cy + height / 2
    for side in (-1, 1):
        spine, outer = cx + side * gap, cx + side * half
        page = [(spine, top + height * 0.04), (outer, top)]
        page += [(outer, bottom - height * 0.1)]
        page += _curve((outer, bottom - height * 0.1), ((spine + outer) / 2, bottom - height * 0.14), (spine, bottom))
        draw.polygon(page, fill=CREAM)


def _waves(draw: ImageDraw.ImageDraw, cx: float, cy: float, radii: tuple[float, ...], stroke: float) -> None:
    for radius in radii:
        draw.arc([cx - radius, cy - radius, cx + radius, cy + radius], start=-50, end=50, fill=CYAN,
                 width=max(1, round(stroke)))


def _emblem(draw: ImageDraw.ImageDraw, size: float, *, stroke: float, radii: tuple[float, ...]) -> None:
    """Sóng âm toả ra từ mép phải của sách - mép ấy bị khoét lõm theo cùng tâm với sóng."""
    cx, cy = size * 0.40, size * 0.57
    _book(draw, cx=cx, cy=cy, width=size * 0.42)
    centre = (size * 0.63, cy)  # ngay mép phải trang sách: khoét thành mép lõm, không thành lỗ
    cut = size * 0.07
    draw.ellipse([centre[0] - cut, cy - cut, centre[0] + cut, cy + cut], fill=NAVY)
    _waves(draw, centre[0], centre[1], radii, stroke)


def draw_full(size: int) -> Image.Image:
    scale = 4
    canvas = size * scale
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    _page(draw, canvas, fold=canvas * 0.2, rim=canvas * 0.014)
    _emblem(draw, canvas, stroke=canvas * 0.04, radii=(canvas * 0.105, canvas * 0.17))
    return image.resize((size, size), Image.Resampling.LANCZOS)


def draw_small(size: int) -> Image.Image:
    """16-32 px: trang, khối kem, MỘT sóng dày - đủ nhận ra ở cỡ ô danh sách file."""
    scale = 8
    canvas = size * scale
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    _page(draw, canvas, fold=canvas * 0.25, rim=canvas * 0.045)
    left, top = canvas * 0.27, canvas * 0.43
    draw.rectangle([left, top, left + canvas * 0.25, top + canvas * 0.33], fill=CREAM)
    _waves(draw, cx=canvas * 0.47, cy=canvas * 0.595, radii=(canvas * 0.19,), stroke=canvas * 0.085)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def render(size: int) -> Image.Image:
    return draw_small(size) if size <= 32 else draw_full(size)


def preview(path: Path) -> None:
    """Các cỡ trên nền sáng và nền tối, như Explorer ở hai chế độ."""
    sizes = (16, 24, 32, 48, 64, 96, 128, 256)
    width = sum(sizes) + 20 * (len(sizes) + 1)
    sheet = Image.new("RGBA", (width, 2 * 256 + 60), (255, 255, 255, 255))
    ImageDraw.Draw(sheet).rectangle([0, 256 + 30, width, 2 * 256 + 60], fill=(32, 32, 32, 255))
    x = 20
    for size in sizes:
        icon = render(size)
        sheet.alpha_composite(icon, (x, 10 + (256 - size)))
        sheet.alpha_composite(icon, (x, 256 + 40 + (256 - size)))
        x += size + 20
    sheet.save(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--preview", type=Path, default=None, help="ghi thêm bảng xem trước các cỡ")
    args = parser.parse_args()
    icons = [render(size) for size in SIZES]
    icons[-1].save(OUT, format="ICO", sizes=[(size, size) for size in SIZES], append_images=icons[:-1])
    icons[-1].save(OUT.with_suffix(".png"))
    if args.preview:
        preview(args.preview)
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
