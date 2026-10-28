"""Sinh dữ liệu nét icon cho app điện thoại (Kotlin) và app máy tính (QML) từ ĐÚNG gói lucide mà bản web dùng.

DESIGN.md luật 8: hai nền tảng cùng biểu tượng cho cùng một việc. Bản web vẽ lucide; điện thoại native và máy tính Qt đọc cùng hình ở đây,
không vẽ tay phỏng theo. Mỗi icon thành MỘT chuỗi đường SVG trên lưới 24 (circle / rect / line / polyline đổi sang path), nét do nơi vẽ đặt:
2 đơn vị lưới, đầu và góc tròn, co giãn theo cỡ icon như lucide-react.

Chạy từ _internal (sau khi thêm tên vào ICONS):
  runtime/.venv/Scripts/python.exe scripts/gen_lucide_icons.py            # Kotlin
  runtime/.venv/Scripts/python.exe scripts/gen_lucide_icons.py --qml DIR  # thêm LucidePaths.js cho Qt
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "ui/node_modules/lucide-react/dist/esm/icons"
KOTLIN_OUT = ROOT / "mobile/android/app/src/main/java/vn/abook/player/ui/components/LucidePaths.kt"

# Tên file lucide (kebab-case), mỗi tên một dòng theo thứ tự chữ cái: bản sinh ổn định, hai nhánh thêm icon khác nhau gộp không xung đột.
ICONS = sorted({
    "maximize-2",
    "folder-x",
    "history",
    "info",
    "mic-vocal",
    "sliders-horizontal",
    "wand-sparkles",
    "picture-in-picture-2",
    "pin-off",
    "arrow-down-wide-narrow",
    "arrow-left",
    "audio-lines",
    "battery-charging",
    "bluetooth",
    "book-audio",
    "book-open",
    "book-open-check",
    "book-open-text",
    "book-plus",
    "cast",
    "check",
    "check-check",
    "chevron-down",
    "chevron-left",
    "chevron-right",
    "chevron-up",
    "circle",
    "circle-alert",
    "circle-dashed",
    "circle-question-mark",
    "clapperboard",
    "copy",
    "cpu",
    "download",
    "eighth-note",
    "ellipsis",
    "file",
    "file-audio",
    "file-down",
    "file-text",
    "folder",
    "folder-down",
    "folder-open",
    "globe",
    "headphones",
    "image-plus",
    "key-round",
    "keyboard",
    "laptop",
    "library",
    "lightbulb",
    "list-ordered",
    "loader-circle",
    "locate",
    "minus",
    "monitor",
    "monitor-smartphone",
    "monitor-speaker",
    "moon",
    "moon-star",
    "palette",
    "panel-left-close",
    "panel-left-open",
    "pause",
    "pencil",
    "pin",
    "play",
    "plus",
    "radar",
    "refresh-cw",
    "rotate-ccw",
    "rotate-cw",
    "save",
    "search",
    "settings",
    "share-2",
    "shield-alert",
    "shuffle",
    "skip-back",
    "skip-forward",
    "smartphone",
    "speaker",
    "square",
    "stethoscope",
    "text-cursor-input",
    "trash-2",
    "triangle-alert",
    "tv",
    "unplug",
    "undo-2",
    "upload",
    "volume-1",
    "volume-2",
    "volume-x",
    "wifi-off",
    "wrench",
    "x",
})

NODE = re.compile(r'\[\s*"(\w+)",\s*\{([^}]*)\}\s*\]')
ATTR = re.compile(r'(\w+):\s*"([^"]*)"')


def num(v: float) -> str:
    return ("%.3f" % v).rstrip("0").rstrip(".")


def load(name: str) -> tuple[str, list[tuple[str, dict]]]:
    path = ICON_DIR / f"{name}.mjs"
    text = path.read_text(encoding="utf-8")
    alias = re.search(r"export \{ default \} from '\./([\w-]+)\.mjs'", text)
    if alias:
        return load(alias.group(1))
    version = re.search(r"lucide-react v([\d.]+)", text).group(1)
    body = re.search(r"node:\s*\[(.*?)\]\s*(?:,\s*aliases|\})", text, re.S).group(1)
    nodes = [(tag, dict(ATTR.findall(attrs))) for tag, attrs in NODE.findall(body)]
    if not nodes:
        sys.exit(f"{name}: không đọc được nét")
    return version, nodes


NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def absolute_start(d: str) -> str:
    """Đường mở bằng `m` thường: đứng một mình thì điểm đầu là tuyệt đối, nhưng ghép sau đường khác thì thành tương đối (lệch cả icon).
    Đổi thành `M x y` + `l` cho các cặp số ngầm theo sau (chúng vẫn là lineto tương đối)."""
    d = d.lstrip()
    if not d.startswith("m"):
        return d
    rest = d[1:]
    first = NUMBER.match(rest.lstrip(" ,"))
    rest = rest.lstrip(" ,")[first.end():]
    second = NUMBER.match(rest.lstrip(" ,"))
    rest = rest.lstrip(" ,")[second.end():]
    tail = rest.lstrip(" ,")
    head = f"M{first.group()} {second.group()}"
    return head + ("l" + tail if tail and NUMBER.match(tail) else tail)


def to_path(tag: str, a: dict) -> str:
    f = lambda k, d=0.0: float(a.get(k, d))
    if "transform" in a or a.get("fill", "currentColor") != "currentColor":
        sys.exit(f"{tag} có transform/fill lạ - chưa hỗ trợ: {a}")
    if tag == "path":
        return absolute_start(a["d"])
    if tag in ("circle", "ellipse"):
        cx, cy = f("cx"), f("cy")
        rx = f("r") if tag == "circle" else f("rx")
        ry = f("r") if tag == "circle" else f("ry")
        return f"M{num(cx - rx)} {num(cy)}a{num(rx)} {num(ry)} 0 1 0 {num(2 * rx)} 0a{num(rx)} {num(ry)} 0 1 0 {num(-2 * rx)} 0"
    if tag == "rect":
        x, y, w, h = f("x"), f("y"), f("width"), f("height")
        rx = f("rx", a.get("ry", 0))
        ry = f("ry", a.get("rx", 0))
        if not rx:
            return f"M{num(x)} {num(y)}h{num(w)}v{num(h)}h{num(-w)}Z"
        return (f"M{num(x + rx)} {num(y)}h{num(w - 2 * rx)}a{num(rx)} {num(ry)} 0 0 1 {num(rx)} {num(ry)}v{num(h - 2 * ry)}"
                f"a{num(rx)} {num(ry)} 0 0 1 {num(-rx)} {num(ry)}h{num(-(w - 2 * rx))}a{num(rx)} {num(ry)} 0 0 1 {num(-rx)} {num(-ry)}"
                f"v{num(-(h - 2 * ry))}a{num(rx)} {num(ry)} 0 0 1 {num(rx)} {num(-ry)}Z")
    if tag == "line":
        return f"M{a['x1']} {a['y1']}L{a['x2']} {a['y2']}"
    if tag in ("polyline", "polygon"):
        pts = a["points"].replace(",", " ").split()
        pairs = [f"{pts[i]} {pts[i + 1]}" for i in range(0, len(pts), 2)]
        return "M" + "L".join(pairs) + ("Z" if tag == "polygon" else "")
    sys.exit(f"thẻ {tag} chưa hỗ trợ")


def const(name: str) -> str:
    return name.upper().replace("-", "_")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--qml", type=Path, help="thư mục qml của app máy tính (ghi LucidePaths.js)")
    ap.add_argument("--qml-only", action="store_true", help="chỉ ghi Qt, không thay file của điện thoại (cần --qml)")
    args = ap.parse_args()
    if args.qml_only and not args.qml:
        ap.error("--qml-only cần --qml")
    data = {}
    versions = set()
    for name in ICONS:
        version, nodes = load(name)
        versions.add(version)
        data[name] = "".join(to_path(tag, a) for tag, a in nodes)
        # Phần tô (chấm của palette...): lucide vẫn vẽ nét quanh nó, nên phần này vừa nằm trong nét vừa được tô.
        filled = "".join(to_path(tag, a) for tag, a in nodes if a.get("fill") == "currentColor")
        if filled:
            data[name + "-fill"] = filled
    version = "/".join(sorted(versions))
    lines = [
        "package vn.abook.player.ui.components",
        "",
        f"/* SINH TỰ ĐỘNG bởi scripts/gen_lucide_icons.py từ lucide-react v{version} (ISC, docs/THIRD_PARTY.md) - không sửa tay. */",
        "",
        "/** Nét icon lucide trên lưới 24, mỗi icon một chuỗi đường SVG (cùng hình bản web dùng); `_FILL` là phần tô thêm của icon có chấm đặc. */",
        "internal object LucidePaths {",
    ]
    lines += [f'    const val {const(n)} = "{d}"' for n, d in data.items()]
    lines += ["}", ""]
    if not args.qml_only:
        KOTLIN_OUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
        print(f"{len(data)} icon -> {KOTLIN_OUT.relative_to(ROOT)}")
    if args.qml:
        js = [".pragma library", "", f"// SINH TỰ ĐỘNG bởi scripts/gen_lucide_icons.py từ lucide-react v{version} (ISC) - không sửa tay.", ""]
        js += [f'var {const(n)} = "{d}";' for n, d in data.items()]
        out = args.qml / "LucidePaths.js"
        out.write_text("\n".join(js) + "\n", encoding="utf-8", newline="\n")
        print(f"{len(data)} icon -> {out}")


if __name__ == "__main__":
    main()
