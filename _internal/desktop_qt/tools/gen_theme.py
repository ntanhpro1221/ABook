"""Sinh qml/Theme.qml từ token của DESIGN.md (một nguồn duy nhất, không chép tay).

Nguồn:
  docs/DESIGN.md           mục 5.1 bảng màu sáng/tối; 5.5 khoảng cách, cỡ chữ, bo góc; 6 chiều cao nút, lưới bìa
  ui/src/shared/motion.ts  MOTION (ms) và EASE (cubic-bezier) - cùng số với --motion-* / --ease-* của styles.css
  ui/src/shared/cover.ts   PALETTES - bảng màu bìa tự sinh

Dùng:  python -X utf8 gen_theme.py            ghi qml/Theme.qml
       python -X utf8 gen_theme.py --check    thoát 1 nếu Theme.qml cũ hơn nguồn (build.bat chạy trước khi dựng)
Thiếu một token mong đợi thì dừng ngay với lời nói rõ thiếu gì - không bao giờ sinh Theme.qml thiếu.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # _internal/desktop_qt
INTERNAL = ROOT.parent                  # _internal
DESIGN = INTERNAL / "docs" / "DESIGN.md"
MOTION_TS = INTERNAL / "ui" / "src" / "shared" / "motion.ts"
COVER_TS = INTERNAL / "ui" / "src" / "shared" / "cover.ts"
OUT = ROOT / "qml" / "Theme.qml"

# Tên token DESIGN.md -> tên thuộc tính QML (camelCase). Chỉ là đặt tên; giá trị luôn đọc từ DESIGN.md.
COLOR_NAMES = {
    "bg": "bg", "panel": "panel", "bg-sunken": "sunken", "line": "line", "text": "text", "text-2": "text2",
    "text-3": "text3", "fg-3": "faint", "accent": "accent", "accent-ink": "accentInk", "accent-text": "accentText",
    "accent-soft": "accentSoft", "success": "success", "danger": "danger", "warning": "warning", "focus": "focus",
    "switch-off": "switchOff", "switch-thumb": "switchThumb",
}
# Cụm mô tả cỡ chữ trong DESIGN.md 5.5 -> tên thuộc tính.
TYPE_NAMES = {
    "phụ chú": "caption", "thân phụ": "bodySmall", "thân": "body", "tiêu đề mục": "section",
    "tiêu đề màn điện thoại": "titlePhone", "tiêu đề màn máy tính": "titleDesktop", "chữ đọc theo": "reading",
}
EASE_NAMES = {"standard": "Standard", "decelerate": "Decelerate", "accelerate": "Accelerate"}
MOTION_NAMES = {"fast": "Fast", "fastOut": "FastOut", "medium": "Medium", "mediumOut": "MediumOut", "slow": "Slow", "slowOut": "SlowOut"}


class Missing(SystemExit):
    def __init__(self, what: str) -> None:
        super().__init__(f"gen_theme: không tìm thấy {what} - DESIGN.md / motion.ts / cover.ts đổi dạng? Sửa gen_theme.py cho khớp.")


def section(text: str, start: str, end: str) -> str:
    i = text.find(start)
    if i < 0:
        raise Missing(f"mục '{start}'")
    j = text.find(end, i + len(start))
    return text[i:j if j > 0 else len(text)]


def to_qt_color(value: str) -> str:
    value = value.strip()
    if value.startswith("#"):
        return value.lower()
    m = re.fullmatch(r"rgb\(\s*(\d+)\s+(\d+)\s+(\d+)\s*/\s*([\d.]+)\s*\)", value)
    if not m:
        raise Missing(f"màu hiểu được ('{value}')")
    r, g, b, a = int(m[1]), int(m[2]), int(m[3]), float(m[4])
    return f"#{round(a * 255):02x}{r:02x}{g:02x}{b:02x}"  # Qt: #AARRGGBB


def colors(design: str) -> dict[str, tuple[str, str]]:
    block = section(design, "### 5.1", "### 5.2")
    found: dict[str, tuple[str, str]] = {}
    for line in block.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not cells[0].startswith("`--"):
            continue
        names = re.findall(r"`--([a-z0-9-]+)`", cells[0].split("(")[0])
        light, dark = cells[1], cells[2]
        if len(names) > 1:
            lights, darks = [v.strip() for v in light.split(" / ")], [v.strip() for v in dark.split(" / ")]
        else:
            lights, darks = [light], [dark]
        if not (len(names) == len(lights) == len(darks)):
            raise Missing(f"đủ giá trị cho hàng {names}")
        for n, lv, dv in zip(names, lights, darks):
            found[n] = (to_qt_color(lv), to_qt_color(dv))
    for n in COLOR_NAMES:
        if n not in found:
            raise Missing(f"token màu --{n}")
    return found


def scale(design: str) -> dict:
    block = section(design, "### 5.5", "## 6.")
    out: dict = {}
    m = re.search(r"\*\*Khoảng cách\*\*:\s*([\d ·]+?)\s*px", block)
    if not m:
        raise Missing("dòng Khoảng cách")
    out["space"] = [int(x) for x in re.findall(r"\d+", m[1])]
    m = re.search(r"Lề màn: điện thoại (\d+), máy tính (\d+)\.\s+Giữa các phần của một màn:\s+(\d+)\s+\(điện thoại\)\s+/\s+(\d+)\s+\(máy tính\)", block)
    if not m:
        raise Missing("dòng Lề màn / Giữa các phần")
    out["marginDesktop"], out["sectionGapDesktop"] = int(m[2]), int(m[4])
    m = re.search(r"\*\*Chữ\*\* \(([^)]+)\):\s*(.+?)\.\s+Đậm:\s*([\d /]+?)\s+-", block, re.S)
    if not m:
        raise Missing("dòng Chữ")
    out["family"] = m[1].strip()
    out["weights"] = [int(x) for x in re.findall(r"\d+", m[3])]
    sizes: dict[str, tuple[int, float | None]] = {}
    for item in re.sub(r"\s+", " ", m[2]).split(" · "):
        mm = re.fullmatch(r"\s*(\d+)(?:/([\d.]+))?\s+(.+?)\s*", item)
        if not mm:
            raise Missing(f"cỡ chữ ('{item}')")
        name = TYPE_NAMES.get(mm[3])
        if name is None:
            raise Missing(f"tên cỡ chữ '{mm[3]}' trong TYPE_NAMES")
        sizes[name] = (int(mm[1]), float(mm[2]) if mm[2] else None)
    for name in TYPE_NAMES.values():
        if name not in sizes:
            raise Missing(f"cỡ chữ {name}")
    out["sizes"] = sizes
    m = re.search(r"\*\*Bo góc\*\*:\s*(\d+) điều khiển · (\d+) bìa/ảnh · (\d+) bảng trượt/hộp thoại", block)
    if not m:
        raise Missing("dòng Bo góc")
    out["radii"] = {"control": int(m[1]), "cover": int(m[2]), "sheet": int(m[3])}
    m = re.search(r"(\d+)×\d+ \(máy tính", block)
    if not m:
        raise Missing("vùng chạm máy tính")
    out["hitDesktop"] = int(m[1])
    comps = section(design, "## 6. Thành phần", "## 7.")
    m = re.search(r"nền hổ phách, cao (\d+) / (\d+)", comps)
    if not m:
        raise Missing("chiều cao nút chính")
    out["buttonDesktop"] = int(m[2])
    m = re.search(r"hàng tiêu đề cao (\d+) / (\d+),\s+tiêu đề (\d+)\s+/\s+(\d+)", comps)
    if not m:
        raise Missing("hàng tiêu đề màn")
    out["headerRowDesktop"] = int(m[2])
    m = re.search(r"máy tính tự giãn (\d+)-(\d+) px", comps)
    if not m:
        raise Missing("lưới bìa 160-200")
    out["coverMin"], out["coverMax"] = int(m[1]), int(m[2])
    m = re.search(r"bìa (\d+):(\d+), bo (\d+)", comps)
    if not m:
        raise Missing("tỉ lệ bìa 2:3")
    out["coverRatio"] = int(m[2]) / int(m[1])
    return out


def motion(ts: str) -> tuple[dict[str, int], dict[str, str]]:
    m = re.search(r"export const MOTION = \{(.*?)\}", ts, re.S)
    if not m:
        raise Missing("MOTION")
    ms = {k: int(v) for k, v in re.findall(r"(\w+):\s*(\d+)", m[1])}
    m = re.search(r"export const EASE = \{(.*?)\}", ts, re.S)
    if not m:
        raise Missing("EASE")
    ease = dict(re.findall(r'(\w+):\s*"(cubic-bezier\([^"]+\))"', m[1]))
    for k in MOTION_NAMES:
        if k not in ms:
            raise Missing(f"MOTION.{k}")
    for k in EASE_NAMES:
        if k not in ease:
            raise Missing(f"EASE.{k}")
    return ms, ease


def palettes(ts: str) -> list[tuple[str, str, str]]:
    m = re.search(r"const PALETTES[^=]*=\s*\[(.*?)\n\];", ts, re.S)
    if not m:
        raise Missing("PALETTES")
    rows = re.findall(r'\["(#[0-9a-fA-F]{6})",\s*"(#[0-9a-fA-F]{6})",\s*"(#[0-9a-fA-F]{6})"\]', m[1])
    if not rows:
        raise Missing("hàng PALETTES")
    return [(a.lower(), b.lower(), c.lower()) for a, b, c in rows]


def bezier(css: str) -> list[float]:
    nums = [float(x) for x in re.findall(r"[\d.]+", css)]
    if len(nums) != 4:
        raise Missing(f"đường cong '{css}'")
    return nums + [1.0, 1.0]  # Qt BezierSpline: điểm điều khiển 1, 2 rồi điểm cuối (1,1)


def fmt(x: float) -> str:
    return f"{x:g}"


def render() -> str:
    design = DESIGN.read_text(encoding="utf-8")
    col, sc = colors(design), scale(design)
    ms, ease = motion(MOTION_TS.read_text(encoding="utf-8"))
    pal = palettes(COVER_TS.read_text(encoding="utf-8"))
    L: list[str] = []
    a = L.append
    a("// GENERATED by desktop_qt/tools/gen_theme.py from docs/DESIGN.md, ui/src/shared/motion.ts, ui/src/shared/cover.ts.")
    a("// Không sửa tay: đổi token ở nguồn rồi chạy lại gen_theme.py (build.bat tự kiểm).")
    a("pragma Singleton")
    a("import QtQuick")
    a("")
    a("QtObject {")
    a('    // "auto" theo Windows; "light" / "dark" để thử')
    a('    property string mode: "auto"')
    a("    readonly property bool dark: mode === \"dark\" || (mode === \"auto\" && Qt.styleHints.colorScheme === Qt.Dark)")
    a("    // Windows > Trợ năng > Hiệu ứng động tắt: bỏ trượt / bay, giữ mờ <= 120 ms (DESIGN.md 5.2). Main.qml gán từ Platform.")
    a("    property bool reduceMotion: false")
    a("")
    a("    // ---- Khổ cửa sổ: CONTENT width, after the sidebar ----")
    a("    // Temporary single block until DESIGN.md has Khổ cửa sổ; move values to its parser then.")
    a("    readonly property int widthMedium: 600")
    a("    readonly property int widthExpanded: 840")
    a("    readonly property int widthLarge: 1200")
    a("    readonly property int widthExtraLarge: 1600")
    a("    function widthClass(w) { return w < widthMedium ? 0 : w < widthExpanded ? 1 : w < widthLarge ? 2 : w < widthExtraLarge ? 3 : 4 }")
    a("")
    a("    // ---- màu (DESIGN.md 5.1) ----")
    for dm, qn in COLOR_NAMES.items():
        light, dark = col[dm]
        a(f'    readonly property color {qn}: dark ? "{dark}" : "{light}"')
    a("")
    a("    // ---- khoảng cách, bo góc, kích thước (5.5, 6) ----")
    for v in sc["space"]:
        a(f"    readonly property int s{v}: {v}")
    a(f"    readonly property int margin: {sc['marginDesktop']}")
    a(f"    readonly property int sectionGap: {sc['sectionGapDesktop']}")
    a(f"    readonly property int radiusControl: {sc['radii']['control']}")
    a(f"    readonly property int radiusCover: {sc['radii']['cover']}")
    a(f"    readonly property int radiusSheet: {sc['radii']['sheet']}")
    a(f"    readonly property int hit: {sc['hitDesktop']}")
    a(f"    readonly property int buttonHeight: {sc['buttonDesktop']}")
    a(f"    readonly property int headerRow: {sc['headerRowDesktop']}")
    a(f"    readonly property int coverMin: {sc['coverMin']}")
    a(f"    readonly property int coverMax: {sc['coverMax']}")
    a(f"    readonly property real coverRatio: {fmt(sc['coverRatio'])}   // cao / rộng")
    a("")
    a("    // ---- chữ (5.5) ----")
    a(f'    readonly property string family: "{sc["family"]}"')
    w = sc["weights"]
    a(f"    readonly property int weightRegular: {w[0]}")
    a(f"    readonly property int weightMedium: {w[1]}")
    a(f"    readonly property int weightBold: {w[2]}")
    for name, (size, lh) in sc["sizes"].items():
        a(f"    readonly property int size{name[0].upper()}{name[1:]}: {size}")
        if lh is not None:
            a(f"    readonly property real lineHeight{name[0].upper()}{name[1:]}: {fmt(lh)}")
    a("")
    a("    // ---- chuyển động (5.2; cùng số với motion.ts) ----")
    for k, qn in MOTION_NAMES.items():
        a(f"    readonly property int motion{qn}: {ms[k]}")
    for k, qn in EASE_NAMES.items():
        a(f"    readonly property var ease{qn}: [{', '.join(fmt(x) for x in bezier(ease[k]))}]")
    a("    // Nhấn: thu 0,97 + tối nền 6 % trong 90 ms, thả về trong 120 ms (5.2)")
    a("    readonly property real pressScale: 0.97")
    a("    readonly property real pressShade: 0.06")
    a("")
    a("    // ---- bìa tự sinh khi sách chưa có ảnh (cover.ts PALETTES: từ, đến, mực) ----")
    a("    readonly property var coverPalettes: [")
    for i, (f, t, ink) in enumerate(pal):
        a(f'        ["{f}", "{t}", "{ink}"]{"," if i < len(pal) - 1 else ""}')
    a("    ]")
    a("}")
    return "\n".join(L) + "\n"


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        current = OUT.read_bytes() if OUT.exists() else b""
        if current != text.encode("utf-8"):
            print("Theme.qml cũ so với token. Chạy: python -X utf8 tools/gen_theme.py", file=sys.stderr)
            return 1
        print("Theme.qml khớp token.")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(text.encode("utf-8"))  # LF (write_text trên Windows ghi CRLF)
    print(f"đã ghi {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
