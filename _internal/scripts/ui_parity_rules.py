"""Fourteen cross-platform UI rules (L1-L14) for web, Qt and Android, read straight from the sources.

docs/UI_PARITY.md keeps the shared dictionary and the existing web <-> native detectors; this file adds what they never compared:
Qt <-> Android directly, the dictionary's "Thay cho" column, colour tokens, the spacing/type scale, component radius roles, motion
tokens, hard show/hide, the "…" button's spoken name, label length, same-control pairs, row summary case (L11) and floating layers
that swallow taps (L12), labels centred in their fixed-height surface (L13) and opaque fills on floating layers (L14). Exceptions and the remaining-work lists
live in scripts/ui_parity_rules.json, each with a reason. Every check returns a list of readable problems; tests/test_ui_parity_rules.py
asserts they are empty and that each rule bites a planted violation.

Run: python -X utf8 scripts/ui_parity_rules.py          (print every problem)
     python -X utf8 scripts/ui_parity_rules.py --counts (current counts of the ratchet lists, to lower the JSON after a fix)
     python -X utf8 scripts/ui_parity_rules.py --instant [--all] (L7 table by platform/category; --all also lists proved-safe sites)
"""
from __future__ import annotations

import difflib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "scripts" / "ui_parity_rules.json"
WEB = "ui/src"
QT = "desktop_qt/qml"
AND = "mobile/android/app/src/main/java/vn/abook/player/ui"
AND_ALL = "mobile/android/app/src/main/java/vn/abook/player"
KEY = re.compile(r"\bS\.(s_[a-z0-9_]+)")


def _module(path: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def strings() -> dict[str, str]:
    return json.loads((ROOT / "ui_strings/vi.json").read_text(encoding="utf-8"))["strings"]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _skip(path: Path) -> bool:
    p = path.as_posix()
    name = path.name
    return (".test." in name or name.endswith("Test.kt") or "/gallery/" in p or "/perf/" in p or "/testing/" in p
            or name in ("strings.generated.ts", "UiStrings.js", "UiStrings.kt", "Theme.qml", "BenchScenario.qml", "Tokens.kt")
            or "/theme/" in p)


def web_files() -> list[Path]:
    return sorted(p for p in (ROOT / WEB).rglob("*.tsx") if not _skip(p))


def qt_files() -> list[Path]:
    return sorted(p for p in (ROOT / QT).glob("*.qml") if not _skip(p))


def qt_js_files() -> list[Path]:
    return sorted(p for p in (ROOT / QT).glob("*.js") if not _skip(p) and p.name not in ("LucidePaths.js",))


def and_files() -> list[Path]:
    return sorted(p for p in (ROOT / AND).rglob("*.kt") if not _skip(p))


def lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").split("\n")


def glob_files(patterns: list[str]) -> list[Path]:
    out: set[Path] = set()
    for pattern in patterns:
        if pattern.startswith("!"):
            continue
        out |= set(ROOT.glob(pattern))
    for pattern in patterns:
        if pattern.startswith("!"):
            out -= set(ROOT.glob(pattern[1:]))
    return sorted(p for p in out if p.is_file())


def keys_in(paths: list[Path]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for path in paths:
        for i, line in enumerate(lines(path), 1):
            if line.strip().startswith(("//", "*", "/*")):
                continue
            for key in KEY.findall(line):
                out.setdefault(key, []).append(f"{rel(path)}:{i}")
    return out


def loose(text: str) -> str:
    text = unicodedata.normalize("NFC", text.replace(" ", " "))
    text = re.sub(r"\{\d+\}", "{}", text)
    return re.sub(r"\s+", " ", text).strip().rstrip(".…:").strip().lower()


def words(text: str) -> list[str]:
    text = re.sub(r"\{\d+\}", "X", text)
    return [w for w in re.split(r"\s+", text.strip()) if w and w not in ("-", "·", "–", "/", "›")]


# ---------------------------------------------------------------------------------------------------------------- L1 Qt <-> Android, web desktop <-> phone
def _near(a: str, b: str) -> bool:
    """Two different texts that most likely name the same thing: one is the other plus a few words (\"Chưa có sách\" / \"Chưa có sách trên máy\"),
    or the two are nearly the same string. A Qt fragment glued to a value (\" người có lời thoại\" vs \"{0} người có lời thoại\") is the same
    words built two ways, not two wordings: not reported here."""
    strip_slots = lambda t: re.sub(r"\s+", " ", re.sub(r"\{\}|[“”\"':]", " ", loose(t))).strip()
    la, lb = strip_slots(a), strip_slots(b)
    if la == lb or a != a.strip() or b != b.strip() or a.rstrip().endswith(".") or b.rstrip().endswith("."):
        return False
    short, long_ = sorted((la, lb), key=len)
    ws, wl = len(words(short)), len(words(long_))
    if ws >= 3 and ws * 2 >= wl and long_.startswith(short + " "):
        return True
    return len(short) >= 12 and difflib.SequenceMatcher(None, la, lb).ratio() >= 0.9


def l1_cross_platform() -> list[str]:
    """Paired screens: a text on one side that is a near variant of a text on the other side is the same thing written twice."""
    cfg = config()["L1"]
    vi = strings()
    allowed = {(a["a"], a["b"]) for a in cfg.get("allow", [])} | {(a["b"], a["a"]) for a in cfg.get("allow", [])}
    problems: list[str] = []
    for screen in cfg["screens"]:
        for left, right in (("qt", "android"), ("web_desktop", "web_phone")):
            if left not in screen or right not in screen:
                continue
            ka, kb = keys_in(glob_files(screen[left])), keys_in(glob_files(screen[right]))
            only_a, only_b = set(ka) - set(kb), set(kb) - set(ka)
            for x in sorted(only_a):
                for y in sorted(only_b):
                    ta, tb = vi.get(x, ""), vi.get(y, "")
                    if ta and tb and _near(ta, tb) and (ta, tb) not in allowed:
                        problems.append(f"L1 [{screen['id']}] {left} {ta!r} ({ka[x][0]}) <-> {right} {tb!r} ({kb[y][0]}): cùng việc, hai chữ")
    return problems


# ---------------------------------------------------------------------------------------------------------------- L2 dictionary "Thay cho"
def dictionary_rows() -> list[tuple[str, str, str]]:
    doc = (ROOT / "docs/UI_PARITY.md").read_text(encoding="utf-8")
    start, end = doc.index("## Từ điển chữ chung"), doc.index("<!-- ui_parity:begin")
    rows = []
    for line in doc[start:end].split("\n"):
        if not line.startswith("|") or line.startswith("|---") or line.startswith("| Việc"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3:
            rows.append((cells[0], cells[1], cells[2]))
    return rows


def exact(text: str) -> str:
    """Same copy for the dictionary: case and punctuation count ("Mở Cài đặt" is banned, "Mở cài đặt" is not); slots and spaces do not."""
    text = unicodedata.normalize("NFC", text.replace(" ", " "))
    text = re.sub(r"\{[^}]*\}", "{}", text)
    return re.sub(r"\s+", " ", text).strip()


def _cells(cell: str) -> list[str]:
    """Items of a dictionary cell: `;` starts a new item only before a capital, a quote or a slot (\"Chạy nền; huỷ vẫn giữ…\" is one sentence)."""
    out = []
    for item in re.split(r";\s+(?=[A-ZĐÂĂÊÔƠƯÁÀẢÃẠÉÈẺẼẸÍÌỈĨỊÓÒỎÕỌÚÙỦŨỤÝỲỶỸỴ\"“{])|\",\s*\"", cell):
        item = item.strip().strip("\"“”").strip()
        if len(item) >= 4 and item != "-":
            out.append(exact(item))
    return out


def banned_texts() -> list[tuple[str, str]]:
    return [(task, item) for task, _good, bad in dictionary_rows() for item in _cells(bad)]


def platform_sources() -> list[Path]:
    return (web_files() + sorted(p for p in (ROOT / WEB).rglob("*.ts") if not _skip(p)) + qt_files() + qt_js_files()
            + sorted(p for p in (ROOT / AND_ALL).rglob("*.kt") if not _skip(p)))


def l2_banned_words() -> list[str]:
    vi = strings()
    by_text: dict[str, list[str]] = {}
    for key, text in vi.items():
        by_text.setdefault(exact(text), []).append(key)
    allow = {(a["task"], a["text"]) for a in config()["L2"].get("allow", [])}
    used = keys_in(platform_sources())
    problems = []
    chosen = {}
    for task, good, _bad in dictionary_rows():
        for piece in re.split(r"\s+·\s+|\s*/\s*", re.sub(r"\([^)]*\)", "", good)):
            if len(piece.strip()) >= 4:
                chosen.setdefault(exact(piece.strip().strip("\"“”")), task)
    for task, text in banned_texts():
        if text in chosen and chosen[text] != task:
            problems.append(f"L2 từ điển tự mâu thuẫn: hàng [{task}] bỏ {text!r}, hàng [{chosen[text]}] lại chọn nó")
        if (task, text) in allow:
            continue
        for key in by_text.get(text, []):
            if key in used:
                problems.append(f"L2 [{task}] chữ đã bỏ {vi[key]!r} ({key}) còn dùng: {', '.join(used[key][:3])}")
    return problems


# ---------------------------------------------------------------------------------------------------------------- L3 colour tokens
def l3_tokens() -> list[str]:
    cfg = config()["L3"]
    data = json.loads((ROOT / "ui_design/tokens.json").read_text(encoding="utf-8"))["colors"]
    web_only = {k["key"] for k in cfg["web_only"]}
    keys = [k for k in data["light"] if k not in web_only]
    theme = (ROOT / QT / "Theme.qml").read_text(encoding="utf-8")
    kt = (ROOT / AND / "theme/Tokens.kt").read_text(encoding="utf-8")
    problems: list[str] = []
    qt_names = _module(ROOT / "desktop_qt/tools/gen_theme.py").COLOR_NAMES
    generator_web_only = set(_module(ROOT / "scripts/gen_native_tokens.py").WEB_ONLY_COLORS)
    if generator_web_only != web_only:
        problems.append(f"L3 danh sách màu chỉ-web của generator {sorted(generator_web_only)} khác ui_parity_rules.json {sorted(web_only)}")
    for key in keys:
        camel = qt_names.get(key) or re.sub(r"-([a-z0-9])", lambda m: m.group(1).upper(), key)
        snake = key.replace("-", "_").upper()
        if not re.search(rf"readonly property (?:color|real) {camel}:", theme):
            problems.append(f"L3 Theme.qml thiếu token màu --{key} (thuộc tính `{camel}`)")
        if not re.search(rf"const val {snake} =", kt):
            problems.append(f"L3 Tokens.kt thiếu token màu --{key} (`{snake}`)")
    return problems + hand_colours()


def hand_colours() -> list[str]:
    """QML / Compose UI files paint with Theme.* / Abook.colors.*, never a literal colour (exceptions: L3.allow)."""
    problems: list[str] = []
    allow = {(a["file"], a["match"]) for a in config()["L3"]["allow"]}
    hexes = re.compile(r"\"#[0-9a-fA-F]{3,8}\"|Qt\.rgba\(|Qt\.alpha\(")
    for path in qt_files():
        for i, line in enumerate(lines(path), 1):
            for m in hexes.finditer(line):
                if (rel(path), m.group(0).strip('"')) not in allow and (rel(path), m.group(0)) not in allow and (rel(path), "*") not in allow:
                    problems.append(f"L3 {rel(path)}:{i} màu viết tay {m.group(0)} - dùng Theme.*")
    kcolor = re.compile(r"Color\(0x[0-9A-Fa-f]+\)|Color\.(?:Black|White|Gray|DarkGray|LightGray)\b|Color\((?:red|r) *=")
    for path in and_files():
        for i, line in enumerate(lines(path), 1):
            if line.strip().startswith("//"):
                continue
            for m in kcolor.finditer(line):
                if (rel(path), m.group(0)) not in allow and (rel(path), "*") not in allow:
                    problems.append(f"L3 {rel(path)}:{i} màu viết tay {m.group(0)} - dùng Abook.colors.*")
    return problems


# ---------------------------------------------------------------------------------------------------------------- L4 spacing / type scale / weight
SPACE_OK = {0, 4, 8, 12, 16, 20, 24, 32, 40, 48, 64}
TYPE_OK = {12, 14, 16, 18, 20, 24, 32}
WEIGHT_OK = {400, 500, 700}
TW_SPACE = re.compile(r"(?<![\w\-\[])-?(?:p|px|py|pt|pb|pl|pr|ps|pe|m|mx|my|mt|mb|ml|mr|ms|me|gap|gap-x|gap-y|space-x|space-y)-(\d+(?:\.\d+)?)(?![\w.%\]])")
TW_SPACE_ARB = re.compile(r"(?<![\w\-])-?(?:p|px|py|pt|pb|pl|pr|m|mx|my|mt|mb|ml|mr|gap|gap-x|gap-y)-\[(\d+(?:\.\d+)?)(px|rem)\]")
TW_TEXT_ARB = re.compile(r"\btext-\[(\d+(?:\.\d+)?)(px|rem)\]")
TW_WEIGHT = re.compile(r"\bfont-(thin|extralight|light|semibold|extrabold|black)\b")
QT_SPACE = re.compile(r"\b(spacing|padding|leftPadding|rightPadding|topPadding|bottomPadding|horizontalPadding|verticalPadding|rowSpacing|columnSpacing|"
                      r"(?:anchors\.)?(?:leftMargin|rightMargin|topMargin|bottomMargin|margins))\s*:\s*(\d+)\s*(?=$|[;}\s])")
QT_SIZE = re.compile(r"\bfont\.pixelSize\s*:\s*(\d+)\b")
QT_WEIGHT = re.compile(r"\bfont\.weight\s*:\s*(\d+)\b|\bfont\.weight\s*:\s*Font\.(DemiBold|Light|Black|ExtraBold|Thin)\b")
KT_SPACE = re.compile(r"\.padding\(([^()]*)\)|spacedBy\(([^()]*)\)")
KT_DP = re.compile(r"(\d+(?:\.\d+)?)\.dp")
KT_SIZE = re.compile(r"fontSize\s*=\s*(\d+(?:\.\d+)?)\.sp")
KT_WEIGHT = re.compile(r"FontWeight\.(SemiBold|Light|Black|ExtraBold|Thin|ExtraLight)\b|FontWeight\((\d+)\)")


def scale_hits() -> list[tuple[str, str, int, str]]:
    """(rule, file, line, token) for every spacing / font size / weight outside the scale."""
    out = []
    for path in web_files():
        for i, line in enumerate(lines(path), 1):
            for m in TW_SPACE.finditer(line):
                if float(m.group(1)) * 4 not in SPACE_OK:
                    out.append(("space", rel(path), i, m.group(0)))
            for m in TW_SPACE_ARB.finditer(line):
                px = float(m.group(1)) * (16 if m.group(2) == "rem" else 1)
                if px not in SPACE_OK:
                    out.append(("space", rel(path), i, m.group(0)))
            for m in TW_TEXT_ARB.finditer(line):
                px = float(m.group(1)) * (16 if m.group(2) == "rem" else 1)
                if px not in TYPE_OK:
                    out.append(("type", rel(path), i, m.group(0)))
            for m in TW_WEIGHT.finditer(line):
                out.append(("weight", rel(path), i, m.group(0)))
    for path in qt_files():
        for i, line in enumerate(lines(path), 1):
            for m in QT_SPACE.finditer(line):
                if int(m.group(2)) not in SPACE_OK:
                    out.append(("space", rel(path), i, m.group(0).strip()))
            for m in QT_SIZE.finditer(line):
                if int(m.group(1)) not in TYPE_OK:
                    out.append(("type", rel(path), i, m.group(0)))
            for m in QT_WEIGHT.finditer(line):
                if m.group(2) or int(m.group(1)) not in WEIGHT_OK:
                    out.append(("weight", rel(path), i, m.group(0)))
    for path in and_files():
        for i, line in enumerate(lines(path), 1):
            for m in KT_SPACE.finditer(line):
                for d in KT_DP.findall(m.group(0)):
                    if float(d) not in SPACE_OK:
                        out.append(("space", rel(path), i, m.group(0)[:60]))
            for m in KT_SIZE.finditer(line):
                if float(m.group(1)) not in TYPE_OK:
                    out.append(("type", rel(path), i, m.group(0)))
            for m in KT_WEIGHT.finditer(line):
                if m.group(1) or int(m.group(2)) not in WEIGHT_OK:
                    out.append(("weight", rel(path), i, m.group(0)))
    return out


def _ratchet(rule: str, hits: Counter, baseline: dict[str, int], what: str) -> list[str]:
    problems = []
    for name, n in sorted(hits.items()):
        if n > baseline.get(name, 0):
            problems.append(f"{rule} {name}: {n} {what} (danh sách tồn cho phép {baseline.get(name, 0)}) - chỉ được giảm")
    for name, n in sorted(baseline.items()):
        if hits.get(name, 0) < n:
            problems.append(f"{rule} {name}: đã giảm còn {hits.get(name, 0)} (tồn ghi {n}) - hạ số trong scripts/ui_parity_rules.json")
    return problems


def l4_scale() -> list[str]:
    cfg = config()["L4"]
    allow = {(a["file"], a["token"]) for a in cfg["allow"]}
    hits = [h for h in scale_hits() if (h[1], h[3]) not in allow]
    per = Counter(f"{rule} {_platform(path)}" for rule, path, _i, _t in hits)
    return _ratchet("L4", per, cfg["remaining"], "chỗ ngoài thang token")


def _platform(path: str) -> str:
    return "web" if path.startswith(WEB) else "qt" if path.startswith(QT) else "android"


# ---------------------------------------------------------------------------------------------------------------- L5 radius roles
def l5_radius_roles() -> list[str]:
    """Component -> radius role table; every listed component file must use exactly its role. Plus: an absolute overlay that fills its
    parent (`absolute inset-0 … rounded-*`) inside a cover must use the cover's role."""
    cfg = config()["L5"]
    problems = []
    for item in cfg["components"]:
        text = (ROOT / item["file"]).read_text(encoding="utf-8")
        for bad in item["forbid"]:
            if re.search(bad, text):
                problems.append(f"L5 {item['file']}: {item['name']} phải bo vai `{item['role']}`, còn {bad!r}")
        if not re.search(item["require"], text):
            problems.append(f"L5 {item['file']}: {item['name']} thiếu bo vai `{item['role']}` ({item['require']!r})")
    for path in web_files():
        src = lines(path)
        for i, line in enumerate(src, 1):
            if "absolute inset-0" in line and "overflow-hidden" in line and "rounded-control" in line:
                ctx = "\n".join(src[max(0, i - 12):i])
                if "rounded-cover" in ctx:
                    problems.append(f"L5 {rel(path)}:{i} lớp phủ trong bìa bo `rounded-control`, bìa bo `rounded-cover`")
    return problems


# ---------------------------------------------------------------------------------------------------------------- L6 motion tokens
def l6_motion_tokens() -> list[str]:
    tokens = json.loads((ROOT / "ui_design/tokens.json").read_text(encoding="utf-8"))
    timing = tokens.get("timing", {})
    problems = []
    need = ("skeletonLow", "skeletonPeriodMs", "noticeMs", "undoMs", "reducedFadeMs", "indeterminateMs", "spinMs")
    for key in need:
        if key not in timing:
            problems.append(f"L6 ui_design/tokens.json thiếu timing.{key}")
    if problems:
        return problems
    # These values are the approved DESIGN contract, not a free choice of the generator.
    for key, expected in {"skeletonLow": 0.6, "skeletonPeriodMs": 1600, "noticeMs": 4000,
                          "undoMs": 28000, "indeterminateMs": 1400, "spinMs": 1000}.items():
        if timing[key] != expected:
            problems.append(f"L6 timing.{key} = {timing[key]!r}, DESIGN yêu cầu {expected}")
    if not 0 < timing["reducedFadeMs"] <= 120:
        problems.append("L6 timing.reducedFadeMs phải > 0 và <= 120 (giữ mờ, không cắt cứng)")
    cfg = config()["L6"]
    for item in cfg["uses"]:
        path = ROOT / item["file"]
        text = path.read_text(encoding="utf-8")
        if not re.search(item["require"], text):
            problems.append(f"L6 {item['file']}: {item['what']} phải đọc token ({item['require']!r})")
        for bad in item.get("forbid", []):
            for i, line in enumerate(text.split("\n"), 1):
                if re.search(bad, line):
                    problems.append(f"L6 {item['file']}:{i} {item['what']} viết tay: {line.strip()[:90]}")
    # Qt: reduced motion never cuts an opacity / colour fade to 0.
    for path in qt_files():
        for i, line in enumerate(lines(path), 1):
            context = "\n".join(lines(path)[max(0, i - 5):i])
            behavior = re.findall(r'Behavior on (\w+)', context)
            geometry = (behavior and behavior[-1] not in ("opacity", "color")) or re.search(r'property:\s*"[xy]"|properties:\s*"x,y"', line)
            if not geometry and re.search(r"duration\s*:\s*Theme\.reduceMotion\s*\?\s*0\b", line) and re.search(r"opacity|ColorAnimation|color", context):
                problems.append(f"L6 {rel(path)}:{i} giảm chuyển động cắt cứng (`reduceMotion ? 0`) - dùng Theme.motionReduced")
    # Every skeleton pulse reads the shared token.
    for path in qt_files():
        text = path.read_text(encoding="utf-8")
        if "Skeleton" in path.name or "skeleton" in text.lower():
            for i, line in enumerate(text.split("\n"), 1):
                if re.search(r"SequentialAnimation[^\n]*loops", line) and "opacity" in "\n".join(text.split("\n")[i - 1:i + 4]):
                    window = "\n".join(text.split("\n")[i - 1:i + 6])
                    if "Theme.skeleton" not in window:
                        problems.append(f"L6 {rel(path)}:{i} nhịp khung chờ không đọc Theme.skeletonLow / skeletonHalf")
    return problems


# ---------------------------------------------------------------------------------------------------------------- L7 hard show / hide
def instant_rows() -> list[dict]:
    """Every show/hide site on the three platforms with its category (scripts/ui_instant.py): "a-*" is a hard toggle the user
    sees, "b-*" is proved safe by a general structural rule (never a per-line exception)."""
    ui_instant = _module(Path(__file__).with_name("ui_instant.py"))
    rel_ = lambda p: rel(p)
    # Theme helpers contain real UI (the reveal snapshot); only generated tokens
    # are excluded. The colour/scale scanners have a different reason to skip theme/.
    android = sorted(set(and_files()) | {p for p in (ROOT / AND / "theme").glob("*.kt") if p.name != "Tokens.kt"})
    return (ui_instant.qt_classify(qt_files(), rel_) + ui_instant.web_classify(web_files(), rel_)
            + ui_instant.kt_classify(android, rel_))


def instant_hits() -> list[tuple[str, int, str]]:
    return [(r["path"], r["line"], r["text"]) for r in instant_rows() if r["category"].startswith("a")]


def l7_instant() -> list[str]:
    cfg = config()["L7"]
    problems = []
    hits = instant_hits()
    # Confirmed repairs must not disappear into a heuristic's nearby-animation window.
    for item in cfg["fixed"]:
        for i, line in enumerate(lines(ROOT / item["file"]), 1):
            if item["match"] in line and not line.lstrip().startswith("//"):
                problems.append(f"L7 {item['file']}:{i} đã sửa ({item['what']}) mà lại hiện/ẩn cứng: {line.strip()}")
    ui_instant = _module(Path(__file__).with_name("ui_instant.py"))
    problems += [f"L7 {p}" for p in ui_instant.qt_reveal_targets(qt_files(), rel)]
    per = Counter(path for path, _i, _l in hits)
    return problems + _ratchet("L7", per, cfg["remaining"], "chỗ hiện/ẩn cứng")


# ---------------------------------------------------------------------------------------------------------------- L8 "…" button name
def _same_object(src: list[str], i: int) -> list[str]:
    """QML lines of the object that holds line i: neighbours at the same indentation, up to the object's own braces."""
    indent = len(src[i]) - len(src[i].lstrip())
    out = [src[i]]
    for step in (-1, 1):
        j = i + step
        while 0 <= j < len(src):
            depth = len(src[j]) - len(src[j].lstrip())
            if src[j].strip() and depth < indent:
                break
            if depth == indent:
                out.append(src[j])
            j += step
    # One-line objects (`IconButton { …; icon: "ellipsis"; Accessible.name: … }`) hold everything on the line itself.
    return [src[i]] if re.search(r"\w\s*\{.*\}\s*$", src[i]) else out


def l8_ellipsis_names() -> list[str]:
    vi = strings()
    ok = lambda key: loose(vi.get(key, "")).startswith("thêm tuỳ chọn")
    problems = []
    for path in qt_files():
        src = lines(path)
        for i, line in enumerate(src):
            if re.search(r"\bicon:\s*\"ellipsis\"", line):
                block = "\n".join(_same_object(src, i))
                # The spoken name wins: a visible short label ("Thêm" under the icon) is fine when the spoken name says it all.
                spoken = re.findall(r"Accessible\.name:\s*[^\n;]*?S\.(s_[a-z0-9_]+)", block)
                for key in spoken or re.findall(r"\b(?:tip|tooltip|label):\s*[^\n;]*?S\.(s_[a-z0-9_]+)", block):
                    if not ok(key):
                        problems.append(f"L8 {rel(path)}:{i + 1} nút \"…\" tên {vi.get(key)!r} - phải là \"Thêm tuỳ chọn…\"")
    for path in and_files():
        for i, line in enumerate(lines(path), 1):
            if "Icons.Ellipsis" in line or "Lucide.Ellipsis" in line or "\"ellipsis\"" in line:
                for key in KEY.findall(line):
                    if not ok(key):
                        problems.append(f"L8 {rel(path)}:{i} nút \"…\" tên {vi.get(key)!r} - phải là \"Thêm tuỳ chọn…\"")
    for path in web_files():
        src = lines(path)
        for i, line in enumerate(src):
            if re.search(r"<(?:MoreHorizontal|Ellipsis)\b|icon=\{(?:MoreHorizontal|Ellipsis)\}", line):
                start = i  # the trigger's own opening tag: the line itself, or the nearest `<button` / `<Component` above the icon
                while start > max(0, i - 8) and "aria-label=" not in src[start] and not re.search(r"<(?:button|[A-Z][\w.]*)\b(?!.*<(?:MoreHorizontal|Ellipsis))", src[start]):
                    start -= 1
                block = line if "aria-label=" in line else "\n".join(src[start: i + 1])
                for key in re.findall(r"aria-label=\{[^}]*?S\.(s_[a-z0-9_]+)", block)[-1:]:
                    if not ok(key):
                        problems.append(f"L8 {rel(path)}:{i + 1} nút \"…\" tên {vi.get(key)!r} - phải là \"Thêm tuỳ chọn…\"")
    return problems


# ---------------------------------------------------------------------------------------------------------------- L9 label length
LABEL_CTX = {
    "web": re.compile(r"(<Button\b|<ActionButton\b|<TextButton\b|<MenuRow\b|<DropdownMenu\.Item\b|<TabLabel\b|<Switch\b|<DisclosureRow\b|<EmptyState\b|<Dialog\b|<Sheet\b|<ScreenHeader\b|<LogBox\b|<button\b|(?<![\w.])label\s*[:=])"),
    "qt": re.compile(r"(\bButton\s*\{|\bTextLink\s*\{|\bMenuRow\s*\{|\bDisclosureRow\s*\{|\b(?:label|title):|\bActionButton\s*\{|\bTabLabel\s*\{|\bNewSwitchRow\s*\{|\bSettingRow\s*\{)"),
    "android": re.compile(r"(PrimaryButton\(|TextAction\(|DangerButton\(|MenuRow\(|DisclosureRow\(|SwitchRow\(|TabLabel\(|SecondaryButton\(|ChoiceRow\(|ScreenHeader\(|SheetRow\()"),
}


def syllables(text: str) -> int:
    return len(words(text))


def _is_label(text: str) -> bool:
    t = text.strip()
    return bool(t) and not t.endswith((".", "?", "!", ":")) and syllables(t) > 4


def long_labels() -> dict[str, list[str]]:
    vi = strings()
    out: dict[str, list[str]] = {}
    for plat, files in (("web", web_files()), ("qt", qt_files()), ("android", and_files())):
        ctx = LABEL_CTX[plat]
        for path in files:
            src = lines(path)
            for i, original in enumerate(src):
                if original.strip().startswith(("//", "*", "/*")):
                    continue
                # A description/input hint is not a control label, even on the same line as a Button.
                line = re.sub(r'\b(?:placeholder|description|hint|help|detail|summary|error|message|body|note)(?:Text)?\s*(?:[:=]\s*\{?|=\s*)[^;}\n]*', '', original)
                if "<MoreInfo" in line:
                    line = re.sub(r'(<MoreInfo\b[^>]*>).*', r'\1', line)
                if plat == "qt" and not re.search(r'\b(?:text|label|title|name|tip)\s*:', line):
                    continue
                if plat == "qt" and re.search(r'\b(?:onClicked|function|notify|notice|showError|say)\b', line):
                    continue
                if plat == "web":
                    # Handler bodies and tooltip descriptions can contain entire messages. Only the visible child or explicit label counts.
                    line = re.sub(r'\bon\w+=\{.*?\}(?=\s+\w+=|>|\s*/>)', '', line)
                here = ctx.search(line) or (plat == "qt" and i > 0 and ctx.search(src[i - 1] + src[max(0, i - 2)]))
                if not here:
                    continue
                for key in KEY.findall(line):
                    text = vi.get(key)
                    if text and _is_label(text):
                        out.setdefault(text, []).append(f"{rel(path)}:{i + 1}")
    return out


def l9_label_length() -> list[str]:
    cfg = config()["L9"]
    allow = {a["text"] for a in cfg["allow"]}
    found = long_labels()
    problems = [f"L9 nhãn {syllables(t)} chữ {t!r} ({locs[0]}) - tối đa 4" for t, locs in sorted(found.items()) if t not in allow]
    for t in sorted(allow - set(found)):
        problems.append(f"L9 ngoại lệ thừa {t!r} - không còn nhãn nào dùng, xoá khỏi scripts/ui_parity_rules.json")
    return problems


# ---------------------------------------------------------------------------------------------------------------- L10 same control, same words
def l10_control_pairs() -> list[str]:
    vi = strings()
    problems = []
    for item in config()["L10"]["controls"]:
        keys = {}
        for plat, where in item["at"].items():
            path = ROOT / where["file"]
            text = path.read_text(encoding="utf-8")
            for pattern in where.get("require", []):
                if not re.search(pattern, text, re.S):
                    problems.append(f"L10 [{item['id']}] {plat}: thiếu hợp đồng {pattern!r}")
            for pattern in where.get("forbid", []):
                if re.search(pattern, text, re.S):
                    problems.append(f"L10 [{item['id']}] {plat}: còn hợp đồng cũ {pattern!r}")
            if "key" not in where:
                continue
            if where["key"] not in vi:
                problems.append(f"L10 [{item['id']}] {plat}: khoá {where['key']} không có trong vi.json")
                continue
            if f"S.{where['key']}" not in text:
                problems.append(f"L10 [{item['id']}] {plat}: {where['file']} không còn dùng {where['key']} ({vi[where['key']]!r})")
            keys[plat] = where["key"]
        texts = {plat: vi.get(k) for plat, k in keys.items()}
        if len(set(texts.values())) > 1:
            problems.append(f"L10 [{item['id']}] cùng điều khiển, chữ khác: " + "; ".join(f"{p}={t!r}" for p, t in texts.items()))
    return problems


# --- L11: a row summary (the value line under a row title) starts with a capital, on all three platforms ---------------------------
# 0.4.168 Android Settings: "Nghe · nhạc tự chọn" beside "Giọng · Hoài My", "Giao diện · Tự động", "Nâng cao · Phiên bản 0.4.168".
SUMMARY_ARG = re.compile(r"\b(?:summary|hint)\s*(?:=(?![=>])|:(?!:))\s*")
OPENERS, CLOSERS = "([{", ")]}"


def summary_files() -> list[Path]:
    web = [p for p in (ROOT / WEB).rglob("*") if p.suffix in (".ts", ".tsx")]
    return sorted(p for p in web + qt_files() + qt_js_files() + and_files() if not _skip(p))


def _expression(text: str, start: int) -> str:
    """The argument/property value that starts at `start`: up to the first , ; ) ] } or line end outside brackets and strings."""
    depth, quote, i = 0, "", start
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\":
                i += 1
            elif c == quote:
                quote = ""
        elif c in "\"'`":
            quote = c
        elif c in OPENERS:
            depth += 1
        elif c in CLOSERS:
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and c in ",;\n":
            break
        i += 1
    return text[start:i]


def _block(text: str, start: int) -> str:
    """From `start` to the brace that closes the first { after it."""
    depth, i = 0, text.index("{", start)
    for j in range(i, len(text)):
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        if depth == 0:
            return text[start:j + 1]
    return text[start:]


def leading_keys(expression: str) -> list[str]:
    """Catalog keys that can START the shown text: not a fragment after `+`, not a value inside another S call's arguments."""
    blank = list(expression)
    for match in KEY.finditer(expression):
        end = match.end()
        if end < len(expression) and expression[end] == "(":
            close = end + len(_expression(expression, end + 1)) + 1
            blank[end + 1:close] = " " * (close - end - 1)
    flat = "".join(blank)
    return [m.group(1) for m in KEY.finditer(flat) if not re.search(r"\+\s*$", flat[:m.start()])]


def _sentence_case(value: str) -> bool:
    first = next((c for c in re.sub(r"\{\d+\}", "", value) if not c.isspace()), "")
    return not first.isalpha() or first.isupper() or value.lstrip().startswith("{")


def l11_summary_case() -> list[str]:
    cfg = config()["L11"]
    vi = strings()
    allowed = {(a["file"], a["key"]) for a in cfg["allow"]}
    used: set[tuple[str, str]] = set()
    sites: list[tuple[str, int, str]] = []
    problems: list[str] = []
    for path in summary_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in SUMMARY_ARG.finditer(text):
            sites += [(rel(path), text.count("\n", 0, match.end()) + 1, key) for key in leading_keys(_expression(text, match.end()))]
    for producer in cfg["producers"]:
        path = ROOT / producer["file"]
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        found = re.search(producer["start"], text)
        if not found:
            problems.append(f"L11 {producer['file']}: không còn {producer['start']!r} - cập nhật L11.producers")
            continue
        if "arg" in producer:  # a positional hint: the n-th argument of every call
            for call in re.finditer(producer["start"], text):
                rest, args, at = text[call.end():], [], 0
                while len(args) <= producer["arg"]:
                    args.append(_expression(rest, at))
                    at += len(args[-1])
                    if at >= len(rest) or rest[at] != ",":
                        break
                    at += 1
                if len(args) > producer["arg"]:
                    line = text.count("\n", 0, call.end()) + 1
                    sites += [(producer["file"], line, key) for key in leading_keys(args[producer["arg"]])]
            continue
        block = _block(text, found.start())
        line = text.count("\n", 0, found.start()) + 1
        for statement in re.split(r"\breturn\b|=>|->|\n", block):
            sites += [(producer["file"], line, key) for key in leading_keys(statement)]
    for file, line, key in sorted(set(sites)):
        value = vi.get(key)
        if value is None or _sentence_case(value):
            continue
        if (file, key) in allowed:
            used.add((file, key))
            continue
        problems.append(f"L11 {file}:{line}: dòng tóm tắt bắt đầu bằng chữ thường {value!r} ({key}) - viết hoa chữ đầu như mọi dòng khác")
    problems += [f"L11 allow thừa (đã hết vi phạm): {f} {k}" for f, k in sorted(allowed - used)]
    return problems


# --- L12: a floating layer over scrolling content swallows every tap in its frame -------------------------------------------------
# Chủ sách 17-11 (Kho nhạc trên OPPO): bấm thanh "Đang nghe thử" thì cú bấm lọt xuống dòng bài nằm dưới. Mọi lớp nổi đè lên nội dung cuộn - thanh
# nổi, thanh phát nhỏ, lời báo, chip, tấm, dải nút... - phải nuốt cú bấm ở cả vùng trống và phần đệm của nó.
#  Android: một phần tử đặt bằng `.align(Alignment.Bottom…)` - hay `.align(Alignment.<góc / giữa>)` trong một Box có danh sách cuộn - mang trong
#           chính chuỗi Modifier của nó một chỗ bắt chạm (floatingLayer() ngoài cùng, pressable/clickable/pointerInput/sheetSurface) đứng trước
#           `padding` đầu tiên. Không node nào chia chạm với anh em nằm dưới
#           (`sharePointerInputWithSiblings() = true`): soát 18-11, Compose nối dòng nằm dưới vào làm CON của lớp và giao cú bấm cho nó trước.
#  Web:     một lớp `fixed` / `sticky` / `absolute` không được `pointer-events-none` (trừ trang trí aria-hidden), vì khi ấy cú bấm đi xuyên.
#           Menu / Popover của Radix chỉ dùng qua bọc chung (shared/DropdownMenu.tsx, shared/Popover.tsx) mà Content gắn lớp chặn ngoài
#           (outsideShield.ts): bấm ra ngoài chỉ đóng, như Qt / Android - soát 18-11 lần 4 (modal={false} và Popover để cú bấm tới thứ nằm dưới).
#  Qt:      một Item nổi (`z:` dương, dính đáy `y: root.height - height`, đưa lên Overlay `parent: …overlay`, hay `anchors.bottom: parent.bottom`
#           cạnh một danh sách cuộn) có TapShield, hoặc chính nó / kiểu của nó là nút, Backdrop hay có TapShield làm con đầu của gốc (một nút bên
#           trong KHÔNG đủ: chỗ trống quanh nút vẫn lọt - soát 18-11). Popup / Drawer / Menu / Dialog của Qt Quick Controls và lớp WindowLayer cũng
#           là lớp nổi: phải có TapShield. Nền "bấm ra ngoài thì đóng" là Backdrop (TapHandler giữ riêng), không phải MouseArea hay TapHandler thụ động.
# Ngoại lệ có lý do riêng ở scripts/ui_parity_rules.json "L12".

L12_ANDROID_CATCH = re.compile(r"\bfloatingLayer\(|\bpressable\b|\bclickable\b|\bcombinedClickable\b|\bpointerInput\b|\bsheetSurface\(")
L12_QT_CATCH = re.compile(r"TapShield|Backdrop|MouseArea|Interactive|IconButton|Button|TapHandler")
L12_QT_FLOAT = re.compile(r"^[ \t]*(?:z:\s*[1-9]\d*\b|y:\s*(?:root|parent)\.height\s*-\s*height\s*(?:$|;|-)|parent:\s*[\w.]*\.overlay\b)", re.M)
# Dính đáy bằng neo: lớp nổi khi khối cha có một danh sách / vùng cuộn anh em (soát 18-11 lần 4: L12 chỉ thấy `y: root.height - height`).
L12_QT_BOTTOM = re.compile(r"^[ \t]*anchors\.bottom:\s*parent\.bottom\b", re.M)
L12_QT_SCROLLER = re.compile(r"(?<![\w.])(?:[A-Z]\w*\.)?(?:ListView|GridView|TableView|Flickable|ScrollView)\s*\{")
# Radix có lớp tự đóng khi nhấn ra ngoài: chỉ dùng qua bọc chung có lớp chặn ngoài.
L12_WEB_WRAPPERS = {"@radix-ui/react-dropdown-menu": "ui/src/shared/DropdownMenu.tsx", "@radix-ui/react-popover": "ui/src/shared/Popover.tsx"}
# Kiểu nổi của Qt Quick Controls (cửa sổ con vẽ trên Overlay): `C.Popup {`, `Popup {`, `T.Drawer {`... (không bắt `ShortcutsDialog`, `CastMenu`).
L12_QT_POPUP = re.compile(r"(?<![\w.])(?:[A-Z]\w*\.)?(?:Popup|Drawer|Menu|Dialog)\s*\{")
# Node chia chạm với anh em nằm dưới (Compose): dòng nằm dưới thành con của lớp trong chuỗi giao sự kiện và nhận cú bấm TRƯỚC lớp.
L12_ANDROID_SHARE = re.compile(r"sharePointerInputWithSiblings\(\)\s*(?::\s*Boolean\s*)?(?:=\s*true\b|\{[^{}]*\breturn\s+true\b)")


def _code_only(text: str) -> str:
    """Comments blanked (same length) so a bracket inside a comment does not move an argument's edge."""
    return re.sub(r"//[^\n]*|/\*[\s\S]*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def _argument(text: str, at: int) -> tuple[int, int]:
    """The call argument (or `x = …` value) around position `at`: [start, end)."""
    depth, start = 0, at
    while start > 0:
        c = text[start - 1]
        if c in ")]}":
            depth += 1
        elif c in "([{":
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and (c == "," or (c == "=" and text[start - 2] not in "=!<>" and text[start] != "=")):
            break
        start -= 1
    depth, end = 0, at
    while end < len(text):
        c = text[end]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif c == "," and depth == 0:
            break
        end += 1
    return start, end


def l12_android_hits() -> list[tuple[str, int, str, bool]]:
    hits = []
    for path in and_files():
        text = _code_only(path.read_text(encoding="utf-8"))
        for m in re.finditer(r"\.align\(", text):
            _arg_start, arg_end = _argument(text, m.end())
            where = text[m.end():arg_end]
            # Bottom: thanh / dải đáy luôn là lớp nổi. Góc / giữa của Box (TopEnd, Center...): chỉ khi Box ấy có danh sách cuộn (đè lên nội dung cuộn);
            # `Alignment.CenterHorizontally` / `End` là căn trong Column / Row, không nổi.
            if "Alignment.Bottom" not in where:
                box = re.search(r"Alignment\.(?:Top|Center)(?:Start|Center|End)?\b", where)
                if not box or re.search(r"Alignment\.Center(?:Horizontally|Vertically)\b", where) or not _kt_over_scroll(text, m.start()):
                    continue
            start, end = _argument(text, m.start())
            chain = " ".join(text[start:end].split())
            hits.append((rel(path), text.count("\n", 0, m.start()) + 1, chain, l12_android_catches(chain)))
    return hits


def _kt_over_scroll(text: str, at: int) -> bool:
    """Phần tử ở `at` nằm trong khối nội dung `{...}` (của Box) có một danh sách cuộn anh em."""
    depth, i = 0, at
    while i > 0:
        i -= 1
        if text[i] == "}":
            depth += 1
        elif text[i] == "{":
            if depth == 0:
                break
            depth -= 1
    # Nhánh của `when { ... }`: phần tử THAY danh sách (đang tải / lỗi), không đè lên nó.
    if re.search(r"\bwhen\s*(?:\([^()]*\))?\s*$", text[max(0, i - 200):i]):
        return False
    depth, j = 0, i
    while j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return bool(re.search(r"\bLazy(?:Column|Row|VerticalGrid|HorizontalGrid|VerticalStaggeredGrid)\(|\.(?:vertical|horizontal)Scroll\(", text[i:j]))


def l12_android_catches(chain: str) -> bool:
    """Chỗ bắt chạm phải đứng TRƯỚC `padding` đầu tiên của chuỗi: `.padding(...).pressable {}` để phần đệm cho cú bấm lọt xuống (soát 17-11)."""
    catch = L12_ANDROID_CATCH.search(chain)
    pad = re.search(r"\.padding\(", chain)
    return bool(catch) and (pad is None or catch.start() < pad.start())


def l12_web_hits() -> list[tuple[str, int, str]]:
    hits = []
    for path in web_files():
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"([\"'`])((?:(?!\1)[^\n])*\bpointer-events-none\b(?:(?!\1)[^\n])*)\1", text):
            classes = m.group(2)
            if not re.search(r"(?<![-\w:\[])(?:fixed|sticky|absolute)\b", classes):
                continue
            tag = text[text.rfind("<", 0, m.start()):text.find(">", m.end()) + 1]
            if "aria-hidden" in tag:
                continue
            hits.append((rel(path), text.count("\n", 0, m.start()) + 1, classes))
    return hits


def _qt_block(text: str, at: int) -> tuple[str, str]:
    """Type name and full text of the QML object whose direct property sits at `at`."""
    depth, i = 0, at
    while i > 0:
        i -= 1
        if text[i] == "}":
            depth += 1
        elif text[i] == "{":
            if depth == 0:
                break
            depth -= 1
    head = re.search(r"([A-Za-z_][\w.]*)\s*$", text[:i])
    depth, j = 0, i
    while j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return (head.group(1) if head else ""), text[i:j + 1]


def _qt_catches(name: str, seen: set[str] | None = None) -> bool:
    """Kiểu QML `name` tự bắt cú bấm trong CẢ khung: là / dựng trên nút, hay tệp của nó có TapShield. Một MouseArea ở đâu đó trong tệp không đủ."""
    if L12_QT_CATCH.fullmatch(name):
        return True
    seen = seen if seen is not None else set()
    path = ROOT / QT / f"{name}.qml"
    if name in seen or not path.exists():
        return False
    seen.add(name)
    text = _code_only(path.read_text(encoding="utf-8"))
    root = re.search(r"^([A-Z][\w.]*)\s*\{", text, re.M)
    if root:
        # Soát 18-11 lần 4: một TapShield ở đâu đó trong tệp (một bảng con) không làm cả khung của kiểu bắt chạm. Phải là con đầu của gốc (hay
        # Backdrop phủ cả cửa sổ), hoặc con đầu của bảng chính - con Item đầu của gốc (Sidebar: panel; PlayerNotice: viên thuốc mang cỡ của gốc).
        body = _qt_braces(text, root.end() - 1)
        kids = [k for k in _qt_children(body) if not L12_QT_NOT_ITEM.fullmatch(k[1])]
        if kids and kids[0][1] in ("TapShield", "Backdrop"):
            return True
        if kids:
            panel = _qt_braces(body, body.find("{", kids[0][0]))
            inner = [k for k in _qt_children(panel) if not L12_QT_NOT_ITEM.fullmatch(k[1])]
            if inner and inner[0][1] == "TapShield":
                return True
    # Chính nó là điều khiển phủ cả khung (thanh tua: MouseArea phủ kín có việc khi bấm / kéo).
    for m in re.finditer(r"(?<![\w.])MouseArea\s*\{", text):
        block = _qt_braces(text, m.end() - 1)
        if re.search(r"anchors\.fill:\s*parent\b", block) and re.search(r"\bon(?:Pressed|Clicked|PositionChanged)\s*:", block):
            return True
    return bool(root and _qt_catches(root.group(1), seen))


def l12_qt_hits() -> list[tuple[str, int, str, bool]]:
    hits = []
    for path in qt_files():
        text = _code_only(path.read_text(encoding="utf-8"))
        floats = list(L12_QT_FLOAT.finditer(text)) + [m for m in L12_QT_BOTTOM.finditer(text) if _qt_over_scroll(text, m.start())]
        for m in floats:
            kind, block = _qt_block(text, m.start())
            name = re.search(r"^\s*(?:id|objectName):\s*\"?(\w+)", block[1:], re.M)
            label = f"{kind}#{name.group(1)}" if name else kind
            # Soát 18-11: một nút bên trong khối (`Rectangle { z: 2; IconButton {} }`) không làm chỗ trống quanh nó thôi lọt.
            caught = _qt_catches(kind) or bool(re.search(r"(?<![\w.])TapShield\s*\{", block))
            hits.append((rel(path), text.count("\n", 0, m.start()) + 1, label, caught))
    return hits


def _qt_over_scroll(text: str, at: int) -> bool:
    """Object có thuộc tính ở `at` có một anh em (con trực tiếp của cùng khối cha) là danh sách / vùng cuộn mà không neo đáy lên đầu lớp
    (`anchors.bottom: <lớp>.top` thì danh sách dừng trên lớp, không bị đè)."""
    def opening(k: int) -> int:
        depth = 0
        while k > 0:
            k -= 1
            if text[k] == "}":
                depth += 1
            elif text[k] == "{":
                if depth == 0:
                    return k
                depth -= 1
        return -1
    own = opening(at)
    head = re.search(r"[A-Za-z_][\w.]*\s*$", text[:own]) if own > 0 else None
    outer = opening(head.start()) if head else -1
    if outer < 0:
        return False
    parent = _qt_braces(text, outer)
    mine = _qt_braces(text, own)
    # Chỉ dải mang điều khiển (thanh nút nổi), không phải chính vùng cuộn hay dải mờ trang trí / khung chờ.
    if L12_QT_SCROLLER.search(mine) or not re.search(r"(?<![\w.])(?:Interactive|IconButton|\w*Button|MouseArea|TapHandler)\s*\{", mine):
        return False
    for kid_at, _kind in _qt_children(parent):
        brace = parent.find("{", kid_at)
        # Vùng cuộn khai báo SAU lớp thì vẽ đè lên lớp, không bị lớp đè.
        if outer + brace >= own or not L12_QT_SCROLLER.match(parent, kid_at):
            continue
        if re.search(r"^[ \t]*anchors\.bottom:\s*(?!parent\b)\w+\.top\b", _qt_braces(parent, brace), re.M):
            continue
        return True
    return False


# Kiểu QML không phải Item (không vào `children`): đứng trước TapShield vẫn để khiên là con đầu tiên.
L12_QT_NOT_ITEM = re.compile(r"\w*Handler|\w*Animation|Behavior|Connections|Listen|Timer|QtObject|Binding|Shortcut|Reveal|ClockUser|Component")


def _qt_children(block: str) -> list[tuple[int, str]]:
    """Các object con trực tiếp (vị trí, kiểu) của khối QML `{...}`: bỏ giá trị thuộc tính (`transform: Translate {}`), `Behavior on x {}`."""
    out, depth = [], 0
    for m in re.finditer(r"[{}]|(?<![\w.:])([A-Z]\w*)\s*\{", block):
        if m.group(0) == "{":
            depth += 1
        elif m.group(0) == "}":
            depth -= 1
        else:
            if depth == 1:
                line = block[block.rfind("\n", 0, m.start()) + 1:m.start()]
                if not re.search(r"\w\s*:\s*$", line):
                    out.append((m.start(), m.group(1)))
            depth += 1
    return out


def l12_qt_layer_problems() -> list[str]:
    """Nút trong lớp có TapShield phải giữ riêng cú bấm (đo 17-11: TapHandler thụ động để cú bấm tới cả Interactive nằm dưới lớp). Cách sửa chung:
    Interactive tự bật `holdsTap` khi một tổ tiên có TapShield làm con ĐẦU TIÊN. Luật giữ cho cách ấy còn đúng: Interactive còn dò khiên, khiên luôn
    là con đầu tiên, khiên không nuốt nút Back, và không còn lớp nào tự chặn bằng `MouseArea { anchors.fill: parent }` trơn (nút trong lớp ấy không
    được bật holdsTap)."""
    problems = []
    inter = ROOT / QT / "Interactive.qml"
    text = _code_only(inter.read_text(encoding="utf-8")) if inter.exists() else ""
    if not (re.search(r"instanceof\s+TapShield", text) and re.search(r"gesturePolicy:\s*root\.holdsTap\b", text)
            and re.search(r"holdsTap:\s*exclusiveTap\s*\|\|", text)):
        problems.append("L12 Qt: Interactive.qml không còn tự giữ riêng cú bấm trong lớp có TapShield (holdsTap / instanceof TapShield / gesturePolicy)")
    shield = ROOT / QT / "TapShield.qml"
    if shield.exists():
        body = _code_only(shield.read_text(encoding="utf-8"))
        if re.search(r"AllButtons|BackButton|ForwardButton", body) or not re.search(r"ReleaseWithinBounds", body):
            problems.append("L12 Qt: TapShield.qml phải giữ riêng cú bấm trái/phải/giữa (ReleaseWithinBounds) và để nút Back / Forward đi tiếp")
    backdrop = ROOT / QT / "Backdrop.qml"
    if backdrop.exists():
        body = _code_only(backdrop.read_text(encoding="utf-8"))
        # Soát 18-11 lần 4: nền thiếu HoverHandler thì dòng dưới màn mờ vẫn sáng hover, hiện chú thích, con trỏ thành bàn tay.
        if re.search(r"AllButtons|BackButton|ForwardButton", body) or not re.search(r"ReleaseWithinBounds", body) or not re.search(r"\bHoverHandler\b", body):
            problems.append("L12 Qt: Backdrop.qml phải giữ riêng cú bấm (ReleaseWithinBounds), giữ con trỏ (HoverHandler) và để nút Back / Forward đi tiếp")
    for path in qt_files():
        text = _code_only(path.read_text(encoding="utf-8"))
        for m in re.finditer(r"(?<![\w.])TapShield\s*\{", text):
            if path.name == "TapShield.qml":
                continue
            depth, start = 0, m.start()
            while start > 0:
                start -= 1
                if text[start] == "}":
                    depth += 1
                elif text[start] == "{":
                    if depth == 0:
                        break
                    depth -= 1
            _kind, block = _qt_block(text, m.start())
            kids = [k for k in _qt_children(block) if not L12_QT_NOT_ITEM.fullmatch(k[1])]
            first = kids[0] if kids else None
            if not first or first[1] != "TapShield" or start + first[0] != m.start():
                problems.append(f"L12 {rel(path)}:{text.count(chr(10), 0, m.start()) + 1}: TapShield không là con đầu tiên của lớp: nút trong lớp không "
                                "tự giữ riêng cú bấm (Interactive chỉ nhìn con đầu tiên)")
        for m in re.finditer(r"(?<![\w.])MouseArea\s*\{", text):
            block = _qt_braces(text, m.end() - 1)
            if not re.search(r"anchors\.fill:\s*parent\b", block) or re.search(r"acceptedButtons:\s*Qt\.NoButton\b", block):
                continue
            line = text.count(chr(10), 0, m.start()) + 1
            if re.search(r"\bon(?:Pressed|Clicked|Released)\s*:[^\n]*\b(?:close|dismiss)\w*\(", block):
                problems.append(f"L12 {rel(path)}:{line}: nền bấm-ra-ngoài là MouseArea: TapHandler thụ động của thứ nằm dưới vẫn thấy cú bấm, nên bấm ra "
                                "ngoài vừa đóng lớp vừa kích hoạt thứ dưới - dùng Backdrop")
            elif not re.search(r"\bon(?:Pressed|Clicked|Released|DoubleClicked|PressAndHold|Wheel|PositionChanged)\s*:|\bdrag\.target\s*:", block):
                problems.append(f"L12 {rel(path)}:{line}: `MouseArea {{ anchors.fill: parent }}` chỉ để chặn cú bấm của lớp: dùng TapShield (con đầu tiên) "
                                "để nút trong lớp tự giữ riêng cú bấm và nút Back đi tiếp")
        for m in re.finditer(r"(?<![\w.])TapHandler\s*\{", text):
            block = _qt_braces(text, m.end() - 1)
            if re.search(r"\bon(?:Tapped|SingleTapped|Pressed|PressedChanged)\s*:[^\n]*\b(?:close|dismiss)\w*\(", block) \
                    and not re.search(r"gesturePolicy:\s*TapHandler\.(?:ReleaseWithinBounds|WithinBounds)\b", block):
                problems.append(f"L12 {rel(path)}:{text.count(chr(10), 0, m.start()) + 1}: nền bấm-ra-ngoài là TapHandler thụ động (DragThreshold): thứ nằm "
                                "dưới vẫn nhận cú bấm - dùng Backdrop")
        for m in L12_QT_POPUP.finditer(text):
            block = _qt_braces(text, m.end() - 1)
            if not re.search(r"(?<![\w.])TapShield\s*\{", block):
                problems.append(f"L12 {rel(path)}:{text.count(chr(10), 0, m.start()) + 1}: lớp nổi {m.group(0)[:-1].strip()} không có TapShield: hàng / chỗ "
                                "trống của nó để cú bấm tới thứ nằm dưới (đặt TapShield làm con đầu của contentItem)")
            # Soát 18-11 lần 4: Popup không modal đóng khi nhấn ra ngoài (mặc định của closePolicy) nhưng để cú nhấn ấy đi tiếp xuống trang.
            policy = re.search(r"closePolicy:\s*([^\n]*)", block)
            if not re.search(r"\bmodal:\s*true\b", block) and (policy is None or "CloseOnPressOutside" in policy.group(1)):
                problems.append(f"L12 {rel(path)}:{text.count(chr(10), 0, m.start()) + 1}: {m.group(0)[:-1].strip()} không modal đóng khi nhấn ra ngoài: cú nhấn "
                                "ấy vẫn tới thứ nằm dưới - bỏ CloseOnPressOutside, đặt Backdrop dưới bảng")
        root = re.search(r"^([A-Z][\w.]*)\s*\{", text, re.M)
        if root and root.group(1) == "WindowLayer" and not re.search(r"(?<![\w.])TapShield\s*\{", text):
            problems.append(f"L12 {rel(path)}: lớp WindowLayer không có TapShield: bảng của nó để cú bấm tới thứ nằm dưới")
    return problems


def _qt_braces(text: str, at: int) -> str:
    """Khối `{...}` mở ở vị trí `at`."""
    depth = 0
    for j in range(at, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[at:j + 1]
    return text[at:]


def l12_android_layer_problems() -> list[str]:
    """floatingLayer phải CHẶN (không chia chạm với anh em) - soát 18-11: bản chia chạm làm dòng nằm dưới nhận cú bấm trước lớp, kể cả dưới thanh tab
    và thanh phát nhỏ. Cú vuốt đi qua bằng `scrollThrough` (lớp tự kéo danh sách), không bằng chia chạm."""
    problems = []
    for path in and_files():
        text = _code_only(path.read_text(encoding="utf-8"))
        for m in L12_ANDROID_SHARE.finditer(text):
            problems.append(f"L12 {rel(path)}:{text.count(chr(10), 0, m.start()) + 1}: node chia chạm với anh em nằm dưới (sharePointerInputWithSiblings): "
                            "Compose giao cú bấm cho dòng nằm dưới TRƯỚC lớp - lớp nổi phải chặn hết")
    components = ROOT / AND / "components/Components.kt"
    text = _code_only(components.read_text(encoding="utf-8")) if components.exists() else ""
    m = re.search(r"fun Modifier\.floatingLayer\(", text)
    if not m:
        problems.append("L12 Android: thiếu Modifier.floatingLayer() ở components/Components.kt")
    else:
        body = text[m.start():text.find("\n\n", m.start()) if "\n\n" in text[m.start():] else len(text)]
        if not re.search(r"\bpointerInput\([^)]*\)\s*\{\s*(?:detectTapGestures|awaitEachGesture)\b", body):
            problems.append("L12 Android: Modifier.floatingLayer() không còn bắt chạm bằng pointerInput { detectTapGestures } (chặn hết trong khung của lớp)")
    return problems


def l12_web_layer_problems() -> list[str]:
    """Menu / Popover của Radix không modal để cú bấm ra ngoài tới thứ nằm dưới (soát 18-11 lần 4). Mọi nơi dùng qua bọc chung; Content của bọc gắn
    lớp chặn ngoài (useOutsideShield) và lớp chặn được chèn ngay dưới bảng."""
    problems = []
    for path in web_files():
        name = rel(path)
        if name in L12_WEB_WRAPPERS.values() or re.search(r"\.test\.[jt]sx?$", name):
            continue
        text = path.read_text(encoding="utf-8")
        for radix, wrapper in L12_WEB_WRAPPERS.items():
            for m in re.finditer(r"[\"'`]" + re.escape(radix) + r"[\"'`]", text):
                problems.append(f"L12 {name}:{text.count(chr(10), 0, m.start()) + 1}: dùng {radix} thẳng - đi qua {wrapper} (bấm ra ngoài chỉ đóng)")
    for wrapper in L12_WEB_WRAPPERS.values():
        path = ROOT / wrapper
        # Gắn bằng ref (`ref={useOutsideShield(ref)}`) hay trải cả bộ xử lý của khiên (`{...useOutsideShield(ref, onInteractOutside)}`, từ khi khiên giữ
        # tới hết cử chỉ - ce8096487); cả hai đều phải đưa CHÍNH ref của Content.
        wired = r"(?:ref=\{useOutsideShield\(ref\)\}|\{\.\.\.useOutsideShield\(ref\s*[,)])"
        if not path.exists() or not re.search(r"export const Content = forwardRef[\s\S]*?" + wired, path.read_text(encoding="utf-8")):
            problems.append(f"L12 {wrapper}: Content không gắn lớp chặn ngoài (useOutsideShield)")
    shield = ROOT / "ui/src/shared/outsideShield.ts"
    body = shield.read_text(encoding="utf-8") if shield.exists() else ""
    if not (re.search(r"wrapper\.before\(", body) and re.search(r"position:\s*\"fixed\"", body)):
        problems.append("L12 ui/src/shared/outsideShield.ts: lớp chặn ngoài phải phủ cả cửa sổ (fixed) và nằm ngay dưới bảng (wrapper.before)")
    return problems


def l12_floating_layers() -> list[str]:
    cfg = config().get("L12", {})
    problems, used = [], set()
    allow = {(a["platform"], a["file"], a["what"]) for a in cfg.get("allow", [])}
    problems += l12_android_layer_problems()
    if not (ROOT / QT / "TapShield.qml").exists():
        problems.append("L12 Qt: thiếu desktop_qt/qml/TapShield.qml")
    problems += l12_qt_layer_problems()
    problems += l12_web_layer_problems()
    for path, line, chain, caught in l12_android_hits():
        key = ("android", path, chain)
        if key in allow:
            used.add(key)
        elif not caught:
            problems.append(f"L12 {path}:{line}: lớp nổi không nuốt chạm (thêm .floatingLayer() ngoài cùng): {chain[:120]}")
    for path, line, classes in l12_web_hits():
        key = ("web", path, classes)
        if key in allow:
            used.add(key)
        else:
            problems.append(f"L12 {path}:{line}: lớp nổi `pointer-events-none` cho cú bấm đi xuyên: {classes[:120]}")
    for path, line, label, caught in l12_qt_hits():
        key = ("qt", path, label)
        if key in allow:
            used.add(key)
        elif not caught:
            problems.append(f"L12 {path}:{line}: Item nổi {label} không có TapShield: cú bấm vào chỗ trống lọt xuống dưới")
    problems += [f"L12 allow thừa (đã hết vi phạm): {p} {f} {w}" for p, f, w in sorted(allow - used)]
    return problems



# --- L13: a label inside a fixed / minimum height surface must be centred (chủ sách 22-11 "Về chỗ vừa nghe") ---------------------------------------
# BasicText lays its line out at the TOP of its own box. Give that box a minimum / fixed height plus a visible surface or a tap target and the words stick
# to the upper edge with an empty strip below. The height belongs to a Box (contentAlignment = Center) around the text, or the text fills a centring parent.
L13_TEXT = re.compile(r"(?<![\w.])(?:BasicText|Text)\(")
L13_HEIGHT = re.compile(r"\.(?:heightIn\(\s*min\b|heightIn\(\s*\d|height\(|size\(|requiredHeight\(|requiredSize\(|defaultMinSize\([^)]*minHeight|fillMaxHeight\(|fillMaxSize\()")
L13_SURFACE = re.compile(r"\.(?:background\(|border\(|drawBehind\b|pressable\b|clickable\b|combinedClickable\b|toggleable\b|selectable\b|insetSurface\()")


def _call_args(text: str, open_paren: int) -> list[str]:
    """Top-level arguments of the call whose `(` is at `open_paren`."""
    depth, start, args = 0, open_paren + 1, []
    for i in range(open_paren, len(text)):
        c = text[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                args.append(text[start:i])
                return args
        elif c == "," and depth == 1:
            args.append(text[start:i])
            start = i + 1
    return args


L13_HOLDER = re.compile(r"(?<![\w.])(Box|Row)\(")


def _call_end(text: str, open_paren: int) -> int:
    """Index just after the `)` closing the call opened at `open_paren`."""
    depth = 0
    for i in range(open_paren, len(text)):
        if text[i] in "([{":
            depth += 1
        elif text[i] in ")]}":
            depth -= 1
            if depth == 0:
                return i + 1
    return len(text)


def _only_label(body: str) -> bool:
    """The content lambda `{ ... }` holds exactly one BasicText / Text call and nothing else."""
    inner = body[1:-1].strip()
    m = L13_TEXT.match(inner)
    return bool(m) and _call_end(inner, m.end() - 1) == len(inner)


def l13_android_hits() -> list[tuple[str, int, str]]:
    hits = []
    for path in and_files():
        text = _code_only(path.read_text(encoding="utf-8"))
        # A Box / Row with a min / fixed height and a surface whose only child is a label, not centred: the same top-stuck line.
        for m in L13_HOLDER.finditer(text):
            args = _call_args(text, m.end() - 1)
            chain = " ".join((args[0] if args else "").split())
            if not re.match(r"(?:Modifier|modifier)\b", chain) or not (L13_HEIGHT.search(chain) and L13_SURFACE.search(chain)):
                continue
            rest = " ".join(" ".join(args[1:]).split())
            # Any explicit alignment is a decision (TextAction aligns CenterEnd); only the default TopStart leaves the line stuck at the top.
            if (m.group(1) == "Box" and "contentAlignment" in rest) or (m.group(1) == "Row" and "verticalAlignment" in rest):
                continue
            j = _call_end(text, m.end() - 1)
            while j < len(text) and text[j] in " \t":
                j += 1
            if j < len(text) and text[j] == "{" and _only_label(_qt_braces(text, j)):
                hits.append((rel(path), text.count("\n", 0, m.start()) + 1, f"{m.group(1)}({chain})"))
        for m in L13_TEXT.finditer(text):
            for arg in _call_args(text, m.end() - 1)[1:]:
                chain = " ".join(arg.split())
                chain = re.sub(r"^modifier\s*=\s*", "", chain)
                if not re.match(r"(?:Modifier|modifier)\b", chain):
                    continue
                if L13_HEIGHT.search(chain) and L13_SURFACE.search(chain):
                    hits.append((rel(path), text.count("\n", 0, m.start()) + 1, chain))
    return hits


def l13_centred_labels() -> list[str]:
    allow = {(a["file"], a["what"]) for a in config().get("L13", {}).get("allow", [])}
    problems, used = [], set()
    for path, line, chain in l13_android_hits():
        if (path, chain) in allow:
            used.add((path, chain))
            continue
        problems.append(f"L13 {path}:{line}: chữ có chiều cao tối thiểu / cố định + nền hay chỗ bấm trên CHÍNH nó - BasicText đặt dòng ở đỉnh khung, chữ "
                        f"dính mép trên: đặt chiều cao / nền vào Box(contentAlignment = Alignment.Center) bọc chữ: {chain[:120]}")
    problems += [f"L13 allow thừa (đã hết vi phạm): {f} {w}" for f, w in sorted(allow - used)]
    return problems


# --- L14: anything floating over content has an opaque fill (chủ sách 22-11: story text read through the chip) ------------------------------------
# The `*-soft` tokens (and the scrim) are translucent in dark mode; `x.copy(alpha = …)` / `bg-x/NN` / `opacity: 0.9 *` are translucent everywhere. In the
# flow they sit on an opaque page, which is what they are for; over other content the words underneath read through. Floating fills compose the tint over
# the panel instead (Android `floatingFill`, web `bg-panel` + inner tint, Qt an opaque Rectangle under the tint).
L14_KT_TRANSLUCENT = re.compile(r"\b(?:accentSoft|warningSoft|infoSoft|dangerSoft|successSoft|scrim)\b(?!\s*\.compositeOver)|\.copy\(\s*alpha\s*=")
L14_KT_FILL = re.compile(r"\.background\(|\bdrawRoundRect\(|\bdrawRect\(")
L14_WEB_FLOAT = re.compile(r"(?<![-\w:\[])(?:fixed|absolute|sticky)\b")
L14_WEB_TRANSLUCENT = re.compile(r"(?<![-\w\[])(?:[a-z0-9]+:)*bg-(?:[a-z0-9-]*-soft|[a-z0-9-]+/\d+|scrim)\b")
L14_QT_TRANSLUCENT = re.compile(r"(?:^|;)\s*color:\s*(?:Theme\.\w*(?:Soft|scrim)\b|Qt\.alpha\(|Qt\.rgba\()", re.M)
L14_QT_PART_OPACITY = re.compile(r"(?:^|;)\s*opacity:[^\n;]*?(?<![\w.])0?\.\d+\s*\*", re.M)
# Floating in QML: raised (z), re-parented onto another item's content, or named as an overlay.
L14_QT_FLOATING = re.compile(r"(?:^|;)\s*(?:z:\s*[1-9]|parent:\s*\w|objectName:\s*\"[^\"]*(?:Chip|Notes|Plate|Toast|Bubble|Drop|Return)\")", re.M)


def l14_android_hits() -> list[tuple[str, int, str]]:
    """Every translucent fill drawn by Android UI code (`.background(…)`, drawRect / drawRoundRect). Floating or not is a review decision: an in-flow use
    is listed in the JSON with its reason, anything else must use `floatingFill`."""
    hits = []
    for path in and_files():
        if path.name == "FloatingChip.kt":
            continue
        text = _code_only(path.read_text(encoding="utf-8"))
        for m in L14_KT_FILL.finditer(text):
            args = _call_args(text, m.end() - 1)
            colour = " ".join((args[0] if args else "").split())
            if L14_KT_TRANSLUCENT.search(colour):
                hits.append((rel(path), text.count("\n", 0, m.start()) + 1, colour))
    return hits


def l14_web_hits() -> list[tuple[str, int, str]]:
    hits = []
    for path in web_files():
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"([\"'`])((?:(?!\1)[^\n])*)\1", text):
            classes = m.group(2)
            if L14_WEB_FLOAT.search(classes) and L14_WEB_TRANSLUCENT.search(classes) and not re.search(r"(?<![-\w])bg-gradient-", classes):
                hits.append((rel(path), text.count("\n", 0, m.start()) + 1, " ".join(classes.split())))
    return hits


def _qt_ancestors(text: str, at: int) -> list[str]:
    """Blocks `{...}` enclosing position `at`, innermost first (only the block's own direct lines matter to callers)."""
    blocks, depth, i = [], 0, at
    while i > 0:
        i -= 1
        if text[i] == "}":
            depth += 1
        elif text[i] == "{":
            if depth == 0:
                blocks.append(_qt_braces(text, i))
            else:
                depth -= 1
    return blocks


def _qt_own(block: str) -> str:
    """The direct property lines of a QML block (children blanked)."""
    out, depth = [], 0
    for c in block[1:-1]:
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            continue
        if depth == 0:
            out.append(c)
    return "".join(out)


def l14_qt_hits() -> list[tuple[str, int, str]]:
    hits = []
    for path in qt_files():
        text = path.read_text(encoding="utf-8")
        root = re.search(r"^([A-Z][\w.]*)\s*\{", text, re.M)
        overlay_file = bool(root and root.group(1) in ("WindowLayer", "Popup", "Drawer", "Dialog", "ToolTip"))
        for m in re.finditer(r"(?<![\w.])Rectangle\s*\{", text):
            block = _qt_braces(text, m.end() - 1)
            own = _qt_own(block)
            translucent = L14_QT_TRANSLUCENT.search(own) or L14_QT_PART_OPACITY.search(own)
            if not translucent or "GradientStop" in own:
                continue
            chain = [own] + [_qt_own(b) for b in _qt_ancestors(text, m.start())]
            floating = overlay_file or any(L14_QT_FLOATING.search(c) for c in chain)
            if floating:
                name = re.search(r"(?:^|;)\s*(?:id|objectName):\s*\"?(\w+)", own, re.M)
                label = name.group(1) if name else " ".join(translucent.group(0).strip(" ;").split())
                hits.append((rel(path), text.count("\n", 0, m.start()) + 1, f"Rectangle#{label}"))
    return hits


def l14_opaque_floating() -> list[str]:
    cfg = config().get("L14", {})
    allow = {(a["platform"], a["file"], a["what"]) for a in cfg.get("allow", [])}
    problems, used = [], set()
    chip = ROOT / AND / "components/FloatingChip.kt"
    body = _code_only(chip.read_text(encoding="utf-8")) if chip.exists() else ""
    if not re.search(r"fun floatingFill\([^)]*\)[^=]*=\s*tint\.compositeOver\(colors\.panel\)", body):
        problems.append("L14 Android: components/FloatingChip.kt phải có floatingFill = tint.compositeOver(colors.panel) (nền đục cho lớp nổi)")
    if not re.search(r"\.background\(floatingFill\(", body):
        problems.append("L14 Android: FloatingChip không tô bằng floatingFill")
    for platform, hits in (("android", l14_android_hits()), ("web", l14_web_hits()), ("qt", l14_qt_hits())):
        for path, line, what in hits:
            key = (platform, path, what)
            if key in allow:
                used.add(key)
                continue
            problems.append(f"L14 {path}:{line}: nền trong suốt một phần ({what[:100]}) - nổi trên nội dung thì chữ bên dưới lộ qua; dùng nền đục "
                            "(Android floatingFill, web bg-panel, Qt Rectangle đục) hoặc ghi lý do trong ui_parity_rules.json nếu nó nằm trong dòng chảy")
    problems += [f"L14 allow thừa (đã hết vi phạm): {p} {f} {w}" for p, f, w in sorted(allow - used)]
    return problems

RULES = {
    "L1": l1_cross_platform, "L2": l2_banned_words, "L3": l3_tokens, "L4": l4_scale, "L5": l5_radius_roles,
    "L6": l6_motion_tokens, "L7": l7_instant, "L8": l8_ellipsis_names, "L9": l9_label_length, "L10": l10_control_pairs,
    "L11": l11_summary_case, "L12": l12_floating_layers, "L13": l13_centred_labels, "L14": l14_opaque_floating,
}


def counts() -> dict:
    per4 = Counter(f"{rule} {_platform(path)}" for rule, path, _i, tok in scale_hits()
                   if (path, tok) not in {(a["file"], a["token"]) for a in config()["L4"]["allow"]})
    per7 = Counter(path for path, _i, _l in instant_hits())
    return {"L4": dict(sorted(per4.items())), "L7": dict(sorted(per7.items()))}


def main(argv: list[str]) -> int:
    if "--instant" in argv:
        rows = instant_rows()
        table = Counter((r["platform"], r["category"]) for r in rows)
        print(f"L7: {sum(1 for r in rows if r['category'].startswith('a'))} chỗ hiện/ẩn cứng (a) / {len(rows)} chỗ hiện/ẩn")
        for (platform, category), n in sorted(table.items()):
            print(f"  {platform:8} {category:22} {n}")
        for r in rows:
            if r["category"].startswith("a") or "--all" in argv:
                print(f"{r['path']}:{r['line']}: [{r['category']}] {r['text']}" + (f"  ({r['reason']})" if "--all" in argv else ""))
        return 0
    if "--counts" in argv:
        print(json.dumps(counts(), ensure_ascii=False, indent=2))
        return 0
    only = [a for a in argv if a in RULES]
    bad = 0
    for name, rule in RULES.items():
        if only and name not in only:
            continue
        problems = rule()
        print(f"{name}: {len(problems)}")
        for p in problems:
            print("   ", p)
        bad += len(problems)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
