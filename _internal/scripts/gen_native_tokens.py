"""Sinh hằng số token của giao diện native (Kotlin) từ docs/DESIGN.md - MỘT nguồn (docs/NATIVE_PHONE_UI.md §2).

Đọc: §5.1 bảng màu (sáng / tối), §5.5 khoảng cách, chữ, bo góc, vùng chạm, §5.2 thời lượng chuyển động; đường cong lấy từ
ui/src/shared/motion.ts (EASE - DESIGN.md chỉ gọi tên "Material 3"). Ghi ra BA file từ cùng một lần đọc:
mobile/android/app/src/main/java/vn/abook/player/ui/theme/Tokens.kt (native), ui/src/shared/tokens.generated.css (web: bo góc thành
`rounded-control` / `rounded-cover` / `rounded-sheet` của Tailwind, thay hẳn thang bo góc mặc định). §5.5 "Khổ cửa sổ" (năm khổ theo bề ngang nội dung)
đi vào cả Tokens.kt (`WidthClass`) và ui/src/shared/widthClass.generated.ts; desktop_qt/tools/gen_theme.py đọc cùng bảng qua `width_classes`.

    python -X utf8 scripts/gen_native_tokens.py          # ghi lại Tokens.kt, tokens.generated.css, widthClass.generated.ts
    python -X utf8 scripts/gen_native_tokens.py --check  # thoát 1 nếu một trong ba file lệch DESIGN.md (tests/test_native_tokens.py)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "docs" / "DESIGN.md"
MOTION_TS = ROOT / "ui" / "src" / "shared" / "motion.ts"
OUT = ROOT / "mobile" / "android" / "app" / "src" / "main" / "java" / "vn" / "abook" / "player" / "ui" / "theme" / "Tokens.kt"
OUT_CSS = ROOT / "ui" / "src" / "shared" / "tokens.generated.css"
OUT_TS = ROOT / "ui" / "src" / "shared" / "widthClass.generated.ts"

# Tên token trong DESIGN.md -> tên hằng Kotlin.
COLOR_NAMES = {
    "bg": "BG", "panel": "PANEL", "bg-sunken": "BG_SUNKEN", "line": "LINE", "text": "TEXT", "text-2": "TEXT_2",
    "text-3": "TEXT_3", "fg-3": "FG_3", "control-line": "CONTROL_LINE", "accent": "ACCENT", "accent-ink": "ACCENT_INK", "accent-text": "ACCENT_TEXT",
    "accent-soft": "ACCENT_SOFT", "success": "SUCCESS", "danger": "DANGER",
}


def section(text: str, start: str, end: str) -> str:
    a = text.index(start)
    return text[a:text.index(end, a)]


def argb(value: str) -> int:
    value = value.strip()
    m = re.fullmatch(r"#([0-9a-fA-F]{6})", value)
    if m:
        return 0xFF000000 | int(m.group(1), 16)
    m = re.fullmatch(r"rgb\((\d+) (\d+) (\d+) / ([0-9.]+)\)", value)
    if m:
        r, g, b = (int(m.group(i)) for i in (1, 2, 3))
        return (round(float(m.group(4)) * 255) << 24) | (r << 16) | (g << 8) | b
    raise ValueError(f"màu lạ: {value!r}")


def split_values(cell: str) -> list[str]:
    """Tách "a / b" nhưng không cắt trong ngoặc: `rgb(233 169 69 / .14)` là MỘT màu."""
    return re.split(r" / (?![^(]*\))", cell)


def colors(design: str) -> tuple[dict[str, int], dict[str, int]]:
    light: dict[str, int] = {}
    dark: dict[str, int] = {}
    for line in section(design, "### 5.1", "### 5.2").splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 5 or not cells[1].startswith("`--"):
            continue
        names = re.findall(r"`--([a-z0-9-]+)`", cells[1])  # hàng `--success` / `--danger` mang hai tên, hai màu mỗi bảng
        light_cells = [c.strip() for c in split_values(cells[2])]
        dark_cells = [c.strip() for c in split_values(cells[3])]
        for name, lc, dc in zip(names, light_cells, dark_cells):
            if name in COLOR_NAMES:
                light[COLOR_NAMES[name]] = argb(lc)
                dark[COLOR_NAMES[name]] = argb(dc)
    missing = set(COLOR_NAMES.values()) - set(light)
    assert not missing, f"DESIGN.md §5.1 thiếu màu: {sorted(missing)}"
    return light, dark


def sizes(design: str) -> dict[str, object]:
    s = re.sub(r"\s+", " ", section(design, "### 5.5", "## 6."))  # DESIGN.md xuống dòng giữa câu
    spacing_line = re.search(r"\*\*Khoảng cách\*\*: ([0-9 ·]+) px", s)
    assert spacing_line, "DESIGN.md §5.5 không còn dòng Khoảng cách"
    out: dict[str, object] = {"SPACING": [int(n) for n in spacing_line.group(1).split("·")]}
    out["MARGIN_PHONE"] = int(re.search(r"Lề màn: điện thoại (\d+)", s).group(1))
    out["SECTION_GAP_PHONE"] = int(re.search(r"Giữa các phần của một màn: (\d+) \(điện thoại\)", s).group(1))
    type_line = re.search(r"\*\*Chữ\*\*[^:]*: (.+?)\. Đậm", s).group(1)
    labels = {
        "CAPTION": "phụ chú", "BODY_SMALL": "thân phụ", "BODY": "thân", "SECTION_TITLE": "tiêu đề mục",
        "SCREEN_TITLE_PHONE": "tiêu đề màn điện thoại", "SCREEN_TITLE_DESKTOP": "tiêu đề màn máy tính", "READING": "chữ đọc theo",
    }
    for key, label in labels.items():
        m = re.search(rf"(\d+)(?:/([0-9.]+))? {re.escape(label)}(?: ·|$)", type_line)
        assert m, f"DESIGN.md §5.5 không còn cỡ chữ '{label}'"
        out[key] = int(m.group(1))
        if key == "READING":
            out["READING_LEADING"] = float(m.group(2))
    radius = re.search(r"\*\*Bo góc\*\*: (\d+) điều khiển · (\d+) bìa/ảnh · (\d+) bảng trượt/hộp thoại", s)
    assert radius, "DESIGN.md §5.5 không còn dòng Bo góc"
    out["RADIUS"] = [int(radius.group(i)) for i in (1, 2, 3)]
    out["TOUCH_PHONE"] = int(re.search(r"Vùng chạm\*\*: tối thiểu (\d+)×\d+ \(điện thoại\)", s).group(1))
    return out


def width_classes(design: str) -> list[tuple[str, int]]:
    """Bảng "Khổ cửa sổ" của §5.5: [(tên, từ bao nhiêu px)] tăng dần, khổ đầu bắt đầu từ 0. Tên là định danh camelCase trong bảng."""
    s = section(design, "#### Khổ cửa sổ", "- **Khoảng cách**")
    rows = [(m.group(1), int(m.group(2))) for m in re.finditer(r"^\| `([A-Za-z]+)` \| (\d+) \|$", s, re.M)]
    assert [name for name, _ in rows] == ["compact", "medium", "expanded", "large", "extraLarge"], "DESIGN.md §5.5 Khổ cửa sổ: bảng phải đủ năm khổ theo thứ tự"
    froms = [px for _, px in rows]
    assert froms[0] == 0 and froms == sorted(set(froms)), "DESIGN.md §5.5 Khổ cửa sổ: khổ đầu từ 0, các mốc tăng dần"
    return rows


def snake(camel: str) -> str:
    return re.sub(r"(?<!^)([A-Z])", r"_\1", camel).upper()


def motion(design: str) -> list[int]:
    s = re.sub(r"\s+", " ", section(design, "### 5.2", "### 5.3"))
    m =re.search(r"nhanh (\d+)/(\d+) ms, vừa (\d+)/(\d+), chậm (\d+)/(\d+)", s)
    assert m, "DESIGN.md §5.2 không còn dòng thời lượng"
    return [int(m.group(i)) for i in range(1, 7)]


def easings() -> dict[str, list[float]]:
    ts = MOTION_TS.read_text(encoding="utf-8")
    out = {}
    for name in ("standard", "decelerate", "accelerate"):
        m = re.search(rf'{name}: "cubic-bezier\(([^)]*)\)"', ts)
        assert m, f"motion.ts không còn EASE.{name}"
        out[name] = [float(v) for v in m.group(1).split(",")]
    return out


def number(value: float) -> str:
    return f"{value:g}f"


def render() -> str:
    design = DESIGN.read_text(encoding="utf-8")
    light, dark = colors(design)
    size = sizes(design)
    fast, fast_out, medium, medium_out, slow, slow_out = motion(design)
    ease = easings()
    spacing = size["SPACING"]
    radius = size["RADIUS"]
    lines = [
        "// SINH TỰ ĐỘNG bởi scripts/gen_native_tokens.py từ docs/DESIGN.md (§5.1, §5.2, §5.5) và ui/src/shared/motion.ts. KHÔNG sửa tay:",
        "// sửa DESIGN.md rồi chạy lại script (tests/test_native_tokens.py bắt lệch).",
        "package vn.abook.player.ui.theme",
        "",
        "/** Màu ARGB, bảng sáng. */",
        "internal object LightPalette {",
    ]
    for name in COLOR_NAMES.values():
        lines.append(f"    const val {name} = 0x{light[name]:08X}L")
    lines += ["}", "", "/** Màu ARGB, bảng tối. */", "internal object DarkPalette {"]
    for name in COLOR_NAMES.values():
        lines.append(f"    const val {name} = 0x{dark[name]:08X}L")
    lines += ["}", "", "/** Khoảng cách, bo góc, vùng chạm (dp). */", "internal object Dimens {"]
    for value in spacing:
        lines.append(f"    const val SPACE_{value} = {value}")
    lines += [
        f"    const val MARGIN_PHONE = {size['MARGIN_PHONE']}",
        f"    const val SECTION_GAP_PHONE = {size['SECTION_GAP_PHONE']}",
        f"    const val RADIUS_CONTROL = {radius[0]}",
        f"    const val RADIUS_COVER = {radius[1]}",
        f"    const val RADIUS_SHEET = {radius[2]}",
        f"    const val TOUCH_PHONE = {size['TOUCH_PHONE']}",
        "}",
        "",
        "/** Cỡ chữ (sp) và dòng của chữ đọc theo. */",
        "internal object TypeScale {",
    ]
    for key in ("CAPTION", "BODY_SMALL", "BODY", "SECTION_TITLE", "SCREEN_TITLE_PHONE", "SCREEN_TITLE_DESKTOP", "READING"):
        lines.append(f"    const val {key} = {size[key]}")
    lines += [
        f"    const val READING_LEADING = {number(size['READING_LEADING'])}",
        "}",
        "",
        "/** Thời lượng chuyển động (ms): vào / ra. */",
        "internal object MotionMs {",
        f"    const val FAST = {fast}",
        f"    const val FAST_OUT = {fast_out}",
        f"    const val MEDIUM = {medium}",
        f"    const val MEDIUM_OUT = {medium_out}",
        f"    const val SLOW = {slow}",
        f"    const val SLOW_OUT = {slow_out}",
        "}",
        "",
        "/** Đường cong cubic-bezier (x1, y1, x2, y2), Material 3. */",
        "internal object Bezier {",
    ]
    for name, v in ease.items():
        for suffix, value in zip(("X1", "Y1", "X2", "Y2"), v):
            lines.append(f"    const val {name.upper()}_{suffix} = {number(value)}")
    lines += [
        "}",
        "",
        "/** Khổ cửa sổ theo bề ngang NỘI DUNG (dp), DESIGN.md §5.5: mỗi khổ bắt đầu từ `fromDp`; so khổ bằng `>=` (thứ tự khai báo). */",
        "internal enum class WidthClass(val fromDp: Int) {",
    ]
    classes = width_classes(design)
    for i, (name, px) in enumerate(classes):
        lines.append(f"    {snake(name)}({px}){',' if i < len(classes) - 1 else ';'}")
    lines += [
        "}",
        "",
        "/** Khổ của một bề ngang nội dung (dp): khổ lớn nhất có `fromDp` không vượt quá nó. */",
        "internal fun widthClass(dp: Float): WidthClass = WidthClass.entries.last { dp >= it.fromDp }",
        "",
    ]
    return "\n".join(lines)


def render_ts() -> str:
    """Khổ cửa sổ cho web: cùng bảng với WidthClass của Tokens.kt và Theme.widthClass của Qt."""
    classes = width_classes(DESIGN.read_text(encoding="utf-8"))
    names = ", ".join(f'"{n}"' for n, _ in classes)
    lines = [
        "// SINH TỰ ĐỘNG bởi scripts/gen_native_tokens.py từ docs/DESIGN.md §5.5 (Khổ cửa sổ). KHÔNG sửa tay: sửa DESIGN.md rồi chạy lại script",
        "// (tests/test_native_tokens.py bắt lệch). Cùng một nguồn với WidthClass của Tokens.kt (điện thoại) và Theme.widthClass (Qt).",
        "",
        f"export const WIDTH_CLASSES = [{names}] as const;",
        "export type WidthClass = (typeof WIDTH_CLASSES)[number];",
        "",
        "/** Bề ngang nội dung (px) mà mỗi khổ bắt đầu. */",
        "export const WIDTH_FROM: Record<WidthClass, number> = {",
    ]
    lines += [f"  {n}: {px}," for n, px in classes]
    lines += [
        "};",
        "",
        "/** Khổ của một bề ngang nội dung (px): khổ lớn nhất có mốc không vượt quá nó. */",
        "export function widthClass(px: number): WidthClass {",
        "  let found: WidthClass = WIDTH_CLASSES[0];",
        "  for (const name of WIDTH_CLASSES) if (px >= WIDTH_FROM[name]) found = name;",
        "  return found;",
        "}",
        "",
        "/** `px` đạt ít nhất khổ `name`. */",
        "export function widthAtLeast(px: number, name: WidthClass): boolean {",
        "  return px >= WIDTH_FROM[name];",
        "}",
        "",
    ]
    return "\n".join(lines)


def render_css() -> str:
    """Bo góc cho web. `--radius-*: initial` xoá thang mặc định của Tailwind (2/4/6/8/12/16/24 px): chỉ còn ba vai của DESIGN.md §5.5 +
    `rounded-full` (nút tròn) và `rounded-none`. `static` để biến luôn có mặt, CSS thường dùng được `var(--radius-control)`."""
    radius = sizes(DESIGN.read_text(encoding="utf-8"))["RADIUS"]
    return "\n".join([
        "/* SINH TỰ ĐỘNG bởi scripts/gen_native_tokens.py từ docs/DESIGN.md §5.5 (bo góc). KHÔNG sửa tay: sửa DESIGN.md rồi chạy lại script",
        "   (tests/test_native_tokens.py bắt lệch). Cùng một nguồn với Tokens.kt của app điện thoại. */",
        "@theme static {",
        "  --radius-*: initial;",
        f"  --radius-control: {radius[0]}px;",
        f"  --radius-cover: {radius[1]}px;",
        f"  --radius-sheet: {radius[2]}px;",
        "}",
        "",
    ])


OUTPUTS = ((OUT, render), (OUT_CSS, render_css), (OUT_TS, render_ts))


def main(argv: list[str]) -> int:
    if "--check" in argv:
        stale = [out for out, make in OUTPUTS if (out.read_bytes().decode("utf-8") if out.is_file() else "") != make()]
        for out in stale:
            print(f"{out} lệch DESIGN.md - chạy scripts/gen_native_tokens.py", file=sys.stderr)
        return 1 if stale else 0
    for out, make in OUTPUTS:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(make().encode("utf-8"))  # LF, không qua write_text (Windows ghi CRLF)
        print(f"đã ghi {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
