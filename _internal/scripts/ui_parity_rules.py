"""Eleven cross-platform UI rules (L1-L11) for web, Qt and Android, read straight from the sources.

docs/UI_PARITY.md keeps the shared dictionary and the existing web <-> native detectors; this file adds what they never compared:
Qt <-> Android directly, the dictionary's "Thay cho" column, colour tokens, the spacing/type scale, component radius roles, motion
tokens, hard show/hide, the "…" button's spoken name, label length and same-control pairs. Exceptions and the remaining-work lists
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


RULES = {
    "L1": l1_cross_platform, "L2": l2_banned_words, "L3": l3_tokens, "L4": l4_scale, "L5": l5_radius_roles,
    "L6": l6_motion_tokens, "L7": l7_instant, "L8": l8_ellipsis_names, "L9": l9_label_length, "L10": l10_control_pairs,
    "L11": l11_summary_case,
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
