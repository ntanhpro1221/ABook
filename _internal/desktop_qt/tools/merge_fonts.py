"""Gộp các mảnh unicode-range của @fontsource/be-vietnam-pro (latin, latin-ext, vietnamese) thành MỘT file mỗi độ đậm.

Qt chọn một face cho mỗi (họ, độ đậm); nếu nạp ba mảnh rời, ký tự nằm ở mảnh khác bị rơi về font dự phòng. Gộp trước: fonts/BeVietnamPro-{Regular,Medium,Bold}.ttf.
Chạy một lần khi đổi font:  python -X utf8 merge_fonts.py <thư mục files của @fontsource/be-vietnam-pro>
Bản @fontsource không có tính năng tnum (chữ số đều độ rộng cho đồng hồ, %, đếm ngược): sau khi gộp, gọi cùng công cụ của bản
Android (mobile/android/scripts/add_tabular_digits.py) để thêm nó.
Giấy phép: SIL OFL 1.1 (fonts/OFL.txt).
"""
from __future__ import annotations

import sys
from pathlib import Path

from fontTools.merge import Merger
from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mobile" / "android" / "scripts"))
from add_tabular_digits import add_tabular  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "fonts"
WEIGHTS = {400: "Regular", 500: "Medium", 700: "Bold"}


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    src = Path(sys.argv[1])
    for weight, name in WEIGHTS.items():
        parts = [src / f"be-vietnam-pro-{subset}-{weight}-normal.woff" for subset in ("latin", "latin-ext", "vietnamese")]
        missing = [p for p in parts if not p.is_file()]
        if missing:
            print("thiếu:", *missing, sep="\n  ")
            return 1
        font = Merger().merge([str(p) for p in parts])
        font.flavor = None  # TTF thường, không bọc woff
        # Họ chung "Be Vietnam Pro" cho cả ba độ đậm (bản Medium gốc mang tên họ "Be Vietnam Pro Medium": Qt coi là họ khác,
        # Font.Medium rơi về Regular). Độ đậm do OS/2.usWeightClass quyết định.
        for record in font["name"].names:
            if record.nameID == 1:
                record.string = "Be Vietnam Pro"
            elif record.nameID == 2:
                record.string = name
        target = OUT / f"BeVietnamPro-{name}.ttf"
        font.save(str(target))
        add_tabular(target)
        chars = len(TTFont(str(target)).getBestCmap())
        print(f"{target.name}: {target.stat().st_size // 1024} KB, {chars} ký tự")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
