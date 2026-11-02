"""Khổ cửa sổ (DESIGN.md 5.5) có MỘT nguồn: bảng trong DESIGN.md. Qt, điện thoại, web chỉ dùng token sinh ra.

(1) Mọi file sinh ra khớp bảng; (2) không còn số 600 / 840 / 1200 / 1600 viết tay trong phép so BỀ RỘNG ở QML / Kotlin / TS.
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

INTERNAL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(INTERNAL / "tests"))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


NATIVE = _load("gen_native_tokens", INTERNAL / "scripts" / "gen_native_tokens.py")
THEME = _load("gen_theme", INTERNAL / "desktop_qt" / "tools" / "gen_theme.py")

BREAKPOINTS = (600, 840, 1200, 1600)
# Nơi quyết bố cục. Không quét file test (chúng được phép nêu số cụ thể), file sinh ra, thư viện bên thứ ba, màn thử gallery.
SCAN = (
    ("desktop_qt/qml", ("*.qml", "*.js")),
    ("mobile/android/app/src/main", ("*.kt",)),
    ("ui/src", ("*.ts", "*.tsx")),
)
SKIP_PARTS = {"gallery", "node_modules"}


def _strip_comments(text: str) -> str:
    """Bỏ chú thích nhưng giữ số dòng."""
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return re.sub(r"(?<![:\"'])//[^\n]*", "", text)


_NUM = r"(?<![\d.])(?:%s)(?!\d)(?:px|\.dp|\.value)?" % "|".join(str(b) for b in BREAKPOINTS)
_OP = r"(?<![=!<>\-])(?:>=|<=|>|<)(?![=>\-])"
# Tên nói về bề rộng: width, maxWidth, widthDp, screenWidthDp, contentWidth, w, dp, px.
_WIDTHY = r"(?:\b\w*[Ww]idth\w*\b|\b\w*Dp\b|\bdp\b|\bpx\b|\bw\b)"
_SPAN = r"[^;{}\n]{0,80}?"
_VIOLATION = [
    re.compile(_WIDTHY + _SPAN + _OP + r"\s*" + _NUM),            # width >= 840, maxWidth < 600.dp
    re.compile(_NUM + r"\s*" + _OP + _SPAN + _WIDTHY),            # 840 <= width
    re.compile(r"(?:min|max)-width:\s*(?:%s)px" % "|".join(str(b) for b in BREAKPOINTS)),  # media query viết tay
    re.compile(r"(?:min|max)-\[(?:%s)px\]" % "|".join(str(b) for b in BREAKPOINTS)),       # Tailwind min-[840px]:
]


def width_comparisons(text: str) -> list[tuple[int, str]]:
    """Các dòng so bề rộng với một trong bốn mốc bằng số viết tay: [(số dòng, dòng)]."""
    found = []
    for number, line in enumerate(_strip_comments(text).splitlines(), 1):
        if any(rule.search(line) for rule in _VIOLATION):
            found.append((number, line.strip()))
    return found


def _sources():
    for base, patterns in SCAN:
        for pattern in patterns:
            for path in sorted((INTERNAL / base).rglob(pattern)):
                rel = path.relative_to(INTERNAL).as_posix()
                if SKIP_PARTS & set(path.parts) or ".test." in path.name or "/test" in rel or "/androidTest" in rel or "generated" in path.name:
                    continue
                yield path


def test_no_handwritten_breakpoint_decides_layout():
    bad = []
    for path in _sources():
        for number, line in width_comparisons(path.read_bytes().decode("utf-8")):
            bad.append(f"{path.relative_to(INTERNAL).as_posix()}:{number}: {line}")
    assert not bad, "khổ cửa sổ chỉ lấy từ token (Theme.width*, WidthClass, shared/widthClass.generated):\n" + "\n".join(bad)


def test_detector_has_teeth():
    """Máy dò phải bắt dạng viết tay ở cả ba ngôn ngữ và không đụng số tình cờ."""
    caught = [
        "readonly property bool side: width >= 600",
        "if (w >= 840) return wide",
        "val wide = maxWidth >= 840.dp",
        "val two = screenWidthDp >= 1200",
        "if (contentWidth !== null && contentWidth >= 840) split()",
        "const narrow = window.innerWidth < 600;",
        "if (1600 <= width) big()",
        "const q = matchMedia('(min-width: 840px)');",
        'className="min-[1200px]:flex"',
    ]
    for line in caught:
        assert width_comparisons(line), f"máy dò bỏ sót: {line}"
    clean = [
        "readonly property bool side: width >= Theme.widthMedium",
        "val wide = widthClass(maxWidth.value) >= WidthClass.EXPANDED",
        "saved[2] >= 960 && saved[3] >= 600",
        "const MAX_SIDE = 1600;",
        "// if (w >= 840) trong chú thích",
        "font.weight: 600",
        "if (size.width() > 160) return",
        "advance(1200)",
    ]
    for line in clean:
        assert not width_comparisons(line), f"máy dò báo nhầm: {line}"


def test_width_table_is_five_classes():
    classes = NATIVE.width_classes(NATIVE.DESIGN.read_text(encoding="utf-8"))
    assert classes == [("compact", 0), ("medium", 600), ("expanded", 840), ("large", 1200), ("extraLarge", 1600)]


def test_generated_tokens_match_design_md():
    stale = [out.name for out, make in NATIVE.OUTPUTS if out.read_bytes().decode("utf-8") != make()]
    assert not stale, f"lệch DESIGN.md: {stale} - chạy scripts/gen_native_tokens.py"
    result = subprocess.run([sys.executable, "-X", "utf8", str(NATIVE.ROOT / "scripts" / "gen_native_tokens.py"), "--check"], capture_output=True)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")


def test_qt_theme_matches_design_md():
    assert THEME.OUT.read_bytes().decode("utf-8") == THEME.render(), "Theme.qml lệch DESIGN.md - chạy desktop_qt/tools/gen_theme.py"
    theme = THEME.OUT.read_text(encoding="utf-8")
    for name, px in NATIVE.width_classes(NATIVE.DESIGN.read_text(encoding="utf-8"))[1:]:
        assert f"readonly property int width{name[0].upper()}{name[1:]}: {px}" in theme


def test_generated_files_use_lf():
    for out, _ in NATIVE.OUTPUTS:
        assert b"\r" not in out.read_bytes()
