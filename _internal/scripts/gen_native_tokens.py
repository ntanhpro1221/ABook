"""Generate Compose/web design tokens from ui_design/tokens.json.

DESIGN.md is the checked specification. Qt's gen_theme.py reads the same JSON.
The stylesheet's generated declarations remain in place for the contrast audits.
--check compares every output without writing it.
"""
from __future__ import annotations

import re
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "docs" / "DESIGN.md"
MOTION_TS = ROOT / "ui" / "src" / "shared" / "motion.ts"
OUT = ROOT / "mobile" / "android" / "app" / "src" / "main" / "java" / "vn" / "abook" / "player" / "ui" / "theme" / "Tokens.kt"
OUT_CSS = ROOT / "ui" / "src" / "shared" / "tokens.generated.css"
OUT_TS = ROOT / "ui" / "src" / "shared" / "widthClass.generated.ts"
TOKEN_SOURCE = ROOT / "ui_design/tokens.json"


def tokens() -> dict:
    return json.loads(TOKEN_SOURCE.read_text(encoding='utf-8'))


def validate_design() -> None:
    """The JSON is implementation input; DESIGN.md is its checked specification."""
    data=tokens()
    design=DESIGN.read_text(encoding='utf-8')
    assert data['sizes']==sizes(design), 'tokens.json sizes differ from DESIGN.md'
    assert [tuple(row) for row in data['widthClasses']]==width_classes(design), 'tokens.json widths differ from DESIGN.md'
    assert list(data['motion'].values())==motion(design), 'tokens.json motion differs from DESIGN.md'
    light,dark=colors(design)
    for theme,palette in [('light',light),('dark',dark)]:
        for css_name,name in COLOR_NAMES.items():
            assert argb(data['colors'][theme][css_name])==palette[name], f'tokens.json {theme}.{css_name} differs from DESIGN.md'

# Tên token trong DESIGN.md -> tên hằng Kotlin.
COLOR_NAMES = {
    "bg": "BG", "panel": "PANEL", "bg-sunken": "BG_SUNKEN", "line": "LINE", "text": "TEXT", "text-2": "TEXT_2",
    "text-3": "TEXT_3", "fg-3": "FG_3", "control-line": "CONTROL_LINE", "accent": "ACCENT", "accent-ink": "ACCENT_INK", "accent-text": "ACCENT_TEXT",
    "accent-soft": "ACCENT_SOFT", "success": "SUCCESS", "danger": "DANGER",
    "scrim": "SCRIM", "success-ink": "SUCCESS_INK", "warning": "WARNING", "warning-soft": "WARNING_SOFT",
    "info-soft": "INFO_SOFT", "focus": "FOCUS", "switch-off": "SWITCH_OFF", "switch-thumb": "SWITCH_THUMB",
    "hover": "HOVER", "danger-soft": "DANGER_SOFT",
}


# Tokens that only the browser can use: a CSS image and two CSS box-shadow lists. Every other key of tokens.json "colors" reaches
# Compose and Qt (scripts/ui_parity_rules.py L3 checks both outputs against the JSON).
WEB_ONLY_COLORS = ("select-chevron", "shadow", "shadow-lg")


def palette_value(theme: dict[str, str], name: str) -> str:
    """Raw value of one colour token with `var(--x)` aliases resolved inside the same theme."""
    value = theme[name].strip()
    while value.startswith("var(--"):
        value = theme[value[6:-1]].strip()
    return value


def extra_colors() -> list[str]:
    """tokens.json colour keys beyond the DESIGN-checked COLOR_NAMES, in JSON order."""
    light = tokens()["colors"]["light"]
    return [k for k in light if k not in COLOR_NAMES and k not in WEB_ONLY_COLORS]


def kotlin_value(value: str) -> str:
    if value == "transparent":
        return "0x00000000L"
    if re.fullmatch(r"[0-9.]+", value):
        return number(float(value))
    return f"0x{argb(value):08X}L"


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
    return tokens()['easing']


def number(value: float) -> str:
    return f"{value:g}f"


def render() -> str:
    design = DESIGN.read_text(encoding="utf-8")
    data=tokens()
    light, dark = ({name:argb(data['colors'][theme][css_name]) for css_name,name in COLOR_NAMES.items()} for theme in ('light','dark'))
    size = data['sizes']
    fast, fast_out, medium, medium_out, slow, slow_out = data['motion'].values()
    ease = easings()
    spacing = size["SPACING"]
    radius = size["RADIUS"]
    lines = [
        "// Generated by scripts/gen_native_tokens.py from ui_design/tokens.json; checked against docs/DESIGN.md.",
        "// Edit the source JSON and run scripts/prepare_ui.py. Do not edit this file.",
        "package vn.abook.player.ui.theme",
        "",
        "/** Màu ARGB, bảng sáng. */",
        "internal object LightPalette {",
    ]
    themes = {theme: {**data['colors']['light'], **data['colors'][theme]} for theme in ('light', 'dark')}
    extras = extra_colors()
    for name in COLOR_NAMES.values():
        lines.append(f"    const val {name} = 0x{light[name]:08X}L")
    for key in extras:
        lines.append(f"    const val {key.replace('-', '_').upper()} = {kotlin_value(palette_value(themes['light'], key))}")
    lines += ["}", "", "/** Màu ARGB, bảng tối. */", "internal object DarkPalette {"]
    for name in COLOR_NAMES.values():
        lines.append(f"    const val {name} = 0x{dark[name]:08X}L")
    for key in extras:
        lines.append(f"    const val {key.replace('-', '_').upper()} = {kotlin_value(palette_value(themes['dark'], key))}")
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
    classes = data['widthClasses']
    for i, (name, px) in enumerate(classes):
        lines.append(f"    {snake(name)}({px}){',' if i < len(classes) - 1 else ';'}")
    lines += [
        "}",
        "",
        "/** Khổ của một bề ngang nội dung (dp): khổ lớn nhất có `fromDp` không vượt quá nó. */",
        "internal fun widthClass(dp: Float): WidthClass = WidthClass.entries.last { dp >= it.fromDp }",
        "",
    ]
    rows = data['coverPalettes']
    lines += ['/** Generated cover palette shared with web and Qt. */', 'internal object CoverPalette {', '    val rows = arrayOf(']
    for row in rows:
        lines.append('        intArrayOf(' + ', '.join(f'0xFF{v[1:].upper()}.toInt()' for v in row) + '),')
    lines += ['    )', '}', '']
    return "\n".join(lines)


def render_ts() -> str:
    """Khổ cửa sổ cho web: cùng bảng với WidthClass của Tokens.kt và Theme.widthClass của Qt."""
    classes = tokens()['widthClasses']
    names = ", ".join(f'"{n}"' for n, _ in classes)
    lines = [
        "// Generated by scripts/gen_native_tokens.py from ui_design/tokens.json; checked against docs/DESIGN.md.",
        "// Shared with Compose WidthClass and Qt Theme.widthClass. Do not edit this file.",
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
    size = tokens()['sizes']
    radius = size["RADIUS"]
    return "\n".join([
        "/* Generated by scripts/gen_native_tokens.py from ui_design/tokens.json; checked against docs/DESIGN.md.",
        "   Shared with Compose and Qt. Do not edit these declarations. */",
        "@theme static {",
        "  --radius-*: initial;",
        f"  --radius-control: {radius[0]}px;",
        f"  --radius-cover: {radius[1]}px;",
        f"  --radius-sheet: {radius[2]}px;",
        *[f"  --text-{name}: {size[key] / 16:g}rem;" for name, key in (
            ('caption', 'CAPTION'), ('body-small', 'BODY_SMALL'), ('body', 'BODY'), ('section', 'SECTION_TITLE'),
            ('title-phone', 'SCREEN_TITLE_PHONE'), ('title-desktop', 'SCREEN_TITLE_DESKTOP'), ('reading', 'READING'))],
        "}",
        "",
    ])


def render_motion() -> str:
    src = MOTION_TS.read_text(encoding="utf-8")
    names = ("fast", "fastOut", "medium", "mediumOut", "slow", "slowOut")
    values = tokens()['motion'].values()
    ms = "export const MOTION = {\n" + "".join(f"  {name}: {value},\n" for name, value in zip(names, values)) + "} as const;"
    ease = "export const EASE = {\n" + "".join(f'  {name}: "cubic-bezier({", ".join(f"{v:g}" for v in values)})",\n' for name, values in easings().items()) + "} as const;"
    src = re.sub(r"export const MOTION = \{.*?\} as const;", lambda _: ms, src, count=1, flags=re.S)
    return re.sub(r"export const EASE = \{.*?\} as const;", lambda _: ease, src, count=1, flags=re.S)


def render_styles() -> str:
    """The token declarations in styles.css are generated, including its palette.

    Keep semantic CSS alongside the declarations so existing contrast audits can
    read the actual stylesheet without reimplementing the CSS cascade.
    """
    design = DESIGN.read_text(encoding="utf-8")
    src = (ROOT / "ui/src/styles.css").read_text(encoding="utf-8")
    data=tokens()
    size = data['sizes']
    src = re.sub(r'(?m)^  --spacing: [^;]+;', f'  --spacing: {size["SPACING"][0] / 16:g}rem;', src)
    palettes = [data['colors'][name] for name in ('light','dark')]
    for i, head in enumerate((':root {', '[data-theme="dark"] {')):
        start = src.index(head)
        end = src.index('\n}', start)
        block = src[start:end]
        for name, value in palettes[i].items():
            pattern = rf'(?m)^(\s*--{re.escape(name)}:)\s*[^;]+;[^\n]*'
            line = f'  --{name}: {value}; /* generated: ui_design/tokens.json */'
            if re.search(pattern, block):
                block = re.sub(pattern, lambda _: line, block)
            else:
                block += '\n' + line
        src = src[:start] + block + src[end:]
    values = data['motion'].values()
    for name, value in zip(('fast', 'fast-out', 'medium', 'medium-out', 'slow', 'slow-out'), values):
        # First declaration is the standard duration; media query overrides remain.
        src = re.sub(rf'(?m)^  --motion-{name}: [^;]+;[^\n]*', f'  --motion-{name}: {value}ms; /* generated: ui_design/tokens.json */', src, count=1)
    for name, values in easings().items():
        value = ', '.join(f'{v:g}' for v in values)
        src = re.sub(rf'(?m)^  --ease-{name}: [^;]+;[^\n]*', f'  --ease-{name}: cubic-bezier({value}); /* generated: ui_design/tokens.json */', src, count=1)
    for name,props in data['surfaces'].items():
        head=f':root[data-surface="{name}"] {{'
        a=src.index(head);b=src.index('\n}',a)
        src=src[:a]+head+'\n'+'\n'.join(f'  --{key}: {value};' for key,value in props.items())+src[b:]
    return src


def render_cover() -> str:
    path=ROOT/'ui/src/shared/cover.ts'
    src=path.read_text(encoding='utf-8')
    block='const PALETTES: [string, string, string][] = [\n'+''.join('  ['+', '.join(json.dumps(c) for c in row)+'],\n' for row in tokens()['coverPalettes'])+'];'
    return re.sub(r'const PALETTES[^=]*=\s*\[.*?\n\];',lambda _:block,src,count=1,flags=re.S)


OUTPUTS = ((MOTION_TS, render_motion), (ROOT / "ui/src/styles.css", render_styles), (ROOT/'ui/src/shared/cover.ts', render_cover),
           (OUT, render), (OUT_CSS, render_css), (OUT_TS, render_ts))


def main(argv: list[str]) -> int:
    validate_design()
    if "--check" in argv:
        stale = [out for out, make in OUTPUTS if (out.read_bytes().decode("utf-8") if out.is_file() else "") != make()]
        for out in stale:
            print(f"{out} lệch DESIGN.md - chạy scripts/gen_native_tokens.py", file=sys.stderr)
        return 1 if stale else 0
    for out, make in OUTPUTS:
        out.parent.mkdir(parents=True, exist_ok=True)
        encoded=make().encode("utf-8")
        if not out.exists() or out.read_bytes()!=encoded:
            out.write_bytes(encoded)  # LF; preserve mtime while native compilers read generated headers
        print(f"đã ghi {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
