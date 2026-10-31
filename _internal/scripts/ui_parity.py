"""Máy dò lệch chữ và icon giữa các nền tảng giao diện (chủ sách 26-10: "từng cái chữ, từng cái icon, từng cái bo góc").

Hai phía: web (ui/src: desktop/, listen/, studio/, shared/, android/ - app máy tính Tauri và giao diện điện thoại cũ) và điện thoại native
(mobile/android/.../ui, Compose). Đọc nguồn của cả hai, không chạy app, không mạng:

  - chữ người nghe thấy: chữ trong JSX, thuộc tính label / title / aria-label / placeholder ..., chuỗi Kotlin đưa vào BasicText / hàng /
    contentDescription / nhãn;
  - cặp nhãn <-> icon: icon và nhãn cùng nằm trong một nút / hàng / mục menu (web: thẻ lucide-react cạnh chữ hay `icon={...}`; native: icon
    `XxxIcon(...)` trong cùng lệnh gọi hay cùng khối Row / Box với chữ). Icon quy về TÊN LUCIDE (file kebab-case) nên hai phía so được với nhau.

Ghi phần SINH TỰ ĐỘNG của docs/UI_PARITY.md (giữa hai dấu <!-- ui_parity:begin/end -->; phần ngoài dấu là chữ tay):
  a. cùng việc khác chữ; b. cùng chữ khác icon / cùng icon khác chữ; c. nhãn chỉ có ở một phía (nhóm theo màn); d. chữ hoa, dấu câu, "…" và
  "...", dấu thanh, số.
Giai đoạn này CHỈ báo cáo, không đổi chữ nào - Lead chọn dạng chuẩn.

    python -X utf8 scripts/ui_parity.py          # ghi lại phần sinh tự động của docs/UI_PARITY.md
    python -X utf8 scripts/ui_parity.py --check  # thoát 1 nếu docs/UI_PARITY.md không còn khớp mã nguồn (tests/test_ui_parity.py)
    python -X utf8 scripts/ui_parity.py --aliases  # sinh lại scripts/lucide_aliases.json từ ui/node_modules (sau khi đổi icon web nhập)
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "ui" / "src"
KT = ROOT / "mobile" / "android" / "app" / "src" / "main" / "java" / "vn" / "abook" / "player" / "ui"
DOC = ROOT / "docs" / "UI_PARITY.md"
# Bảng alias lucide (`more-horizontal` -> `ellipsis`) cho icon web nhập: máy dò không cần ui/node_modules; sinh lại bằng --aliases.
ALIASES = ROOT / "scripts" / "lucide_aliases.json"
BEGIN = "<!-- ui_parity:begin (SINH TỰ ĐỘNG bởi scripts/ui_parity.py - không sửa tay, chạy lại script) -->"
END = "<!-- ui_parity:end -->"

# Web: thư mục có giao diện thật; gallery/ là thư viện mẫu của người làm. Phía điện thoại web chỉ tính listen / android / shared khi so "chỉ một phía".
WEB_DIRS = ("android", "desktop", "listen", "shared", "studio")
PHONE_WEB_DIRS = ("android", "listen", "shared")

# Thuộc tính / khoá đối tượng mang chữ cho người nghe.
TEXT_ATTRS = {"label", "title", "aria-label", "ariaLabel", "placeholder", "alt", "description", "hint", "caption", "tooltip", "heading",
              "subtitle", "text", "emptyText", "helper", "confirmLabel", "cancelLabel", "summary", "message", "action"}
KT_NAMED = {"contentDescription", "label", "title", "hint", "text", "placeholder", "description", "subtitle", "caption", "action", "value",
            "summary", "message", "unit"}
KT_SKIP_CALLEE = {"testTag", "Regex", "Log", "File", "Uri", "println", "error", "require", "check", "checkNotNull", "requireNotNull",
                  "listOf", "setOf", "mapOf", "arrayOf", "put", "putExtra", "getString", "optString", "getJSONObject", "getJSONArray", "has",
                  "Intent", "IntentFilter", "toRegex", "startsWith", "endsWith", "contains", "split", "replace", "trim", "removePrefix",
                  "removeSuffix", "equals", "format", "assert", "Pair", "to", "storageKey", "route", "key", "id", "tag", "name", "optBoolean",
                  "optInt", "optLong", "optDouble", "getBoolean", "getInt", "getLong", "getDouble", "getString", "joinToString", "indexOf"}
KT_SKIP_NAMED = {"tag", "key", "route", "id", "storageKey", "testTag", "name", "action_id", "channel", "mime", "type", "scheme"}

VI_LETTERS = "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
HAS_VI = re.compile(f"[{VI_LETTERS}{VI_LETTERS.upper()}]")


@dataclass(frozen=True)
class Item:
    """Một chữ người nghe thấy: phía, vị trí, nội dung, loại nguồn (jsx / attr:label / kt:BasicText ...)."""
    side: str
    file: str
    line: int
    text: str
    kind: str


@dataclass(frozen=True)
class Pair:
    """Một nhãn đi cùng một icon (tên lucide, hay `native:Tên` nếu không phải lucide)."""
    side: str
    file: str
    line: int
    label: str
    icon: str
    how: str


@dataclass
class Scan:
    items: list[Item] = field(default_factory=list)
    pairs: list[Pair] = field(default_factory=list)
    icon_sites: int = 0  # số chỗ dùng icon trong mã (kể cả chỗ không ghép được với nhãn chữ), để biết bộ ghép phủ bao nhiêu


# ---------------------------------------------------------------------------------------------------------------------------------------
# Dùng chung


def looks_ui(text: str, strict: bool = False) -> bool:
    """Chuỗi có giống chữ cho người nghe không (không phải tên lớp, đường dẫn, mã). `strict`: nguồn không chắc là chữ (chuỗi Kotlin rời)."""
    s = text.strip()
    if len(s) < 2 or not re.search(r"[^\W\d_]", s):
        return False
    if HAS_VI.search(s):
        return True
    if re.search(r"[/\\]|://|\.(?:kt|tsx?|json|png|mp3|css|html|js)\b|^[#@.:]|[{}<>]=?\s*$|^\w+\(\)|\$\w", s) and " " not in s:
        return False
    if re.fullmatch(r"[a-z0-9_.:/-]+", s):  # id, tên lớp một từ, khoá
        return False
    if all(re.fullmatch(r"[a-z0-9:\[\]/.%#()_!,@*&>+-]+", t) for t in s.split()):  # danh sách lớp Tailwind / mã viết thường
        return False
    if re.fullmatch(r"[A-Z0-9_]+", s):  # hằng số
        return False
    if strict:
        return bool(re.match(r"[A-Z0-9]", s)) and bool(re.search(r"[a-z]", s)) and "_" not in s
    return bool(re.match(r"[A-ZĐ]", s)) or " " in s


def skip_string(src: str, i: int) -> int:
    """`i` ở dấu mở chuỗi " ' hay `; trả về vị trí ngay sau dấu đóng (bỏ qua escape; mẫu `${}` lồng nhau được đếm ngoặc)."""
    quote = src[i]
    i += 1
    while i < len(src):
        c = src[i]
        if c == "\\":
            i += 2
            continue
        if c == quote:
            return i + 1
        if quote in "`\"" and c == "$" and src[i + 1:i + 2] == "{":
            i = skip_balanced(src, i + 1, "{", "}")
            continue
        if quote == "'" and c == "\n":
            return i
        i += 1
    return i


def skip_comment(src: str, i: int) -> int:
    if src.startswith("//", i):
        j = src.find("\n", i)
        return len(src) if j < 0 else j
    if src.startswith("/*", i):
        j = src.find("*/", i + 2)
        return len(src) if j < 0 else j + 2
    return i


def skip_balanced(src: str, i: int, open_c: str, close_c: str) -> int:
    """`i` ở ngoặc mở; trả về vị trí ngay sau ngoặc đóng tương ứng, bỏ qua chuỗi và chú thích."""
    depth = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c in "\"'`":
            i = skip_string(src, i)
            continue
        if c == "/" and src[i + 1:i + 2] in ("/", "*"):
            i = skip_comment(src, i)
            continue
        if c == open_c:
            depth += 1
        elif c == close_c:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def literal_text(raw: str) -> str:
    """Nội dung chuỗi/mẫu đã bỏ dấu nháy; `${...}` và `$tên` thành `{}`; escape cơ bản."""
    body = raw[1:-1] if len(raw) >= 2 else raw
    out: list[str] = []
    i = 0
    while i < len(body):
        c = body[i]
        if c == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt == "u" and re.fullmatch(r"[0-9a-fA-F]{4}", body[i + 2:i + 6]):
                out.append(chr(int(body[i + 2:i + 6], 16)))
                i += 6
                continue
            out.append({"n": " ", "t": " "}.get(nxt, nxt))
            i += 2
            continue
        if c == "$" and body[i + 1:i + 2] == "{":
            i = skip_balanced(body, i + 1, "{", "}")
            out.append("{}")
            continue
        if c == "$" and re.match(r"[A-Za-z_]", body[i + 1:i + 2] or ""):
            j = i + 1
            while j < len(body) and (body[j].isalnum() or body[j] == "_"):
                j += 1
            out.append("{}")
            i = j
            continue
        out.append(c)
        i += 1
    return re.sub(r"\s+", " ", "".join(out)).strip()


def literals_in(src: str) -> list[tuple[int, str]]:
    """Mọi chuỗi "..." / '...' / `...` ở mức trên cùng của đoạn `src` (không vào trong chuỗi): (vị trí, nội dung)."""
    found: list[tuple[int, str]] = []
    i = 0
    while i < len(src):
        c = src[i]
        if c in "\"'`":
            j = skip_string(src, i)
            found.append((i, literal_text(src[i:j])))
            i = j
            continue
        if c == "/" and src[i + 1:i + 2] in ("/", "*"):
            i = skip_comment(src, i)
            continue
        i += 1
    return found


def line_of(src: str, pos: int) -> int:
    return src.count("\n", 0, pos) + 1


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


# ---------------------------------------------------------------------------------------------------------------------------------------
# Icon: quy về tên lucide


def _lucide_dir() -> Path:
    spec = importlib.util.spec_from_file_location("gen_lucide_icons", ROOT / "scripts" / "gen_lucide_icons.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ICON_DIR  # cùng thư mục gen_lucide_icons.py đọc nét: một nơi biết lucide nằm đâu


def lucide_kebab(ident: str) -> str:
    """`MoreHorizontal` / `Trash2` / `EllipsisIcon` -> tên file lucide theo chữ (`more-horizontal`, `trash-2`, `ellipsis`)."""
    base = ident[:-4] if ident.endswith("Icon") and len(ident) > 4 else ident
    return re.sub(r"(?<=[a-z])(?=[A-Z0-9])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=[0-9])(?=[A-Za-z])", "-", base).lower()


_ALIASES: dict[str, str] | None = None


def lucide_name(ident: str) -> str:
    """Tên lucide thật (theo bảng alias ALIASES), vd `MoreHorizontal` -> `ellipsis`, `Trash2` -> `trash-2`."""
    global _ALIASES
    if _ALIASES is None:
        _ALIASES = json.loads(ALIASES.read_bytes().decode("utf-8"))
    kebab = lucide_kebab(ident)
    return _ALIASES.get(kebab, kebab)


def alias_table() -> dict[str, str]:
    """Đọc gói lucide-react trong ui/node_modules: alias -> tên thật, cho mọi icon web nhập mà tên theo chữ là alias."""
    icons = _lucide_dir()
    if not icons.is_dir():
        raise SystemExit(f"thiếu {icons}: chạy npm ci trong ui/ trước khi sinh lại {ALIASES.name}")
    table: dict[str, str] = {}
    for path in web_files():
        src = path.read_bytes().decode("utf-8")
        for m in re.finditer(r"import\s*\{([^}]*)\}\s*from\s*[\"']lucide-react[\"']", src):
            for part in m.group(1).split(","):
                real = part.strip().partition(" as ")[0].strip()
                if not real or real.startswith("type "):
                    continue
                kebab = name = lucide_kebab(real)
                for _ in range(4):  # theo chuỗi alias: more-horizontal -> ellipsis
                    file = icons / f"{name}.mjs"
                    if not file.is_file():
                        break
                    hop = re.search(r"export \{ default \} from '\./([\w-]+)\.mjs'", file.read_text(encoding="utf-8"))
                    if not hop:
                        break
                    name = hop.group(1)
                if name != kebab:
                    table[kebab] = name
    return dict(sorted(table.items()))


def alias_json(table: dict[str, str]) -> str:
    return json.dumps(table, ensure_ascii=False, indent=2) + "\n"


# ---------------------------------------------------------------------------------------------------------------------------------------
# Web: bộ đọc JSX nhỏ


@dataclass
class Element:
    tag: str
    line: int
    attrs: dict[str, str]
    children: list = field(default_factory=list)  # ("text", str, line) | ("expr", [str], line) | ("el", Element)


# Vòng xoay chờ là trạng thái nhất thời đứng cạnh nhãn, không phải icon của việc.
TRANSIENT_ICONS = {"loader", "loader-2", "loader-circle", "loader-pinwheel"}
IDENT_BEFORE_OK = re.compile(r"(?:^|[(,=:?&|>\[{};!]|=>|\breturn|\belse)\s*$")


def parse_tag(src: str, i: int) -> tuple[Element | None, int, bool]:
    """`i` ở '<'. Trả về (phần tử với thuộc tính, vị trí sau '>', tự đóng?) hay (None, i, False) nếu không phải thẻ JSX."""
    m = re.match(r"<([A-Za-z][\w.]*|)", src[i:i + 80])
    if not m:
        return None, i, False
    tag = m.group(1)
    j = i + m.end()
    attrs: dict[str, str] = {}
    n = len(src)
    while j < n:
        while j < n and src[j].isspace():
            j += 1
        if j >= n:
            return None, i, False
        c = src[j]
        if c == "/" and src.startswith("/>", j):
            return Element(tag, line_of(src, i), attrs), j + 2, True
        if c == ">":
            return Element(tag, line_of(src, i), attrs), j + 1, False
        if c == "/" and src[j + 1:j + 2] in ("/", "*"):
            j = skip_comment(src, j)
            continue
        if c == "{":  # {...props}
            j = skip_balanced(src, j, "{", "}")
            continue
        am = re.match(r"[A-Za-z_][\w:.-]*", src[j:])
        if not am:
            return None, i, False
        name = am.group(0)
        j += am.end()
        while j < n and src[j].isspace():
            j += 1
        if src[j:j + 1] != "=":
            attrs[name] = ""
            continue
        j += 1
        while j < n and src[j].isspace():
            j += 1
        if src[j:j + 1] == "{":
            end = skip_balanced(src, j, "{", "}")
            attrs[name] = src[j + 1:end - 1]
            j = end
        elif src[j:j + 1] in ("\"", "'"):
            end = skip_string(src, j)
            attrs[name] = src[j:end]
            j = end
        else:
            return None, i, False
    return None, i, False


def scan_container(src: str, i: int, stop: int, parent: Element) -> None:
    """Trong `{...}` của phần tử con: JSX lồng (`cond ? <A/> : <B/>`) thành con của `parent` đúng thứ tự, chuỗi chữ thành "expr"."""
    strings: list[str] = []
    line = line_of(src, i)

    def flush() -> None:
        if strings:
            parent.children.append(("expr", list(strings), line))
            strings.clear()

    while i < stop:
        c = src[i]
        if c in "\"'`":
            end = skip_string(src, i)
            text = literal_text(src[i:end])
            if looks_ui(text):
                line = line_of(src, i) if not strings else line
                strings.append(text)
            i = end
            continue
        if c == "/" and src[i + 1:i + 2] in ("/", "*"):
            i = skip_comment(src, i)
            continue
        if c == "<" and re.match(r"<([A-Za-z]|>)", src[i:i + 2]) and IDENT_BEFORE_OK.search(src[max(0, i - 12):i]):
            child, end = parse_element(src, i)
            if child is not None:
                flush()
                parent.children.append(("el", child))
                i = end
                continue
        i += 1
    flush()


def parse_element(src: str, i: int) -> tuple[Element | None, int]:
    el, j, closed = parse_tag(src, i)
    if el is None:
        return None, i
    if closed:
        return el, j
    n = len(src)
    text_start = j
    while j < n:
        k = j
        while k < n and src[k] not in "<{":
            k += 1
        chunk = re.sub(r"\s+", " ", src[j:k]).strip()
        if chunk:
            el.children.append(("text", chunk, line_of(src, j)))
        if k >= n:
            return None, i
        if src[k] == "{":
            end = skip_balanced(src, k, "{", "}")
            scan_container(src, k + 1, end - 1, el)
            j = end
            continue
        if src.startswith("</", k):
            close = src.find(">", k)
            return el, (n if close < 0 else close + 1)
        child, end = parse_element(src, k)
        if child is None:
            return None, i
        el.children.append(("el", child))
        j = end
    return None, i


def jsx_elements(src: str) -> list[Element]:
    """Các phần tử JSX gốc của file (mỗi phần tử con nằm trong `children` của cha)."""
    roots: list[Element] = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c in "\"'`":
            i = skip_string(src, i) if c != "'" else skip_string(src, i)
            continue
        if c == "/" and src[i + 1:i + 2] in ("/", "*"):
            i = skip_comment(src, i)
            continue
        if c == "<" and re.match(r"<([A-Za-z]|>)", src[i:i + 2]) and IDENT_BEFORE_OK.search(src[max(0, i - 12):i]):
            el, end = parse_element(src, i)
            if el is not None:
                roots.append(el)
                i = end
                continue
        i += 1
    return roots


def lucide_imports(src: str) -> dict[str, str]:
    """Tên cục bộ -> tên lucide, từ `import { A, B as C } from "lucide-react"`."""
    out: dict[str, str] = {}
    for m in re.finditer(r"import\s*\{([^}]*)\}\s*from\s*[\"']lucide-react[\"']", src):
        for part in m.group(1).split(","):
            part = part.strip()
            if not part or part.startswith("type "):
                continue
            real, _, alias = part.partition(" as ")
            out[(alias or real).strip()] = lucide_name(real.strip())
    return out


def attr_texts(raw: str) -> list[str]:
    return [t for _, t in literals_in(raw) if looks_ui(t)]


def element_label(el: Element) -> list[str]:
    """Chữ của chính phần tử: chữ con trực tiếp, chuỗi trong {…}, hay thuộc tính label / title / aria-label."""
    kids = [c[1] if c[0] == "text" else " / ".join(c[1]) for c in el.children if c[0] in ("text", "expr")]
    kids = [k for k in kids if looks_ui(k)]
    if kids:
        return [" ".join(kids)]
    for name in ("label", "title", "aria-label", "ariaLabel", "tooltip"):
        if name in el.attrs:
            found = attr_texts(el.attrs[name])
            if found:
                return found
    return []


def web_scan_file(path: Path, scan: Scan) -> None:
    src = path.read_bytes().decode("utf-8")
    file = rel(path)
    if path.suffix == ".ts":
        for m in re.finditer(r"\b(label|title|text|hint|description|heading|subtitle|placeholder|caption|summary|message)\s*:\s*([\"'`])", src):
            end = skip_string(src, m.start(2))
            text = literal_text(src[m.start(2):end])
            if looks_ui(text):
                scan.items.append(Item("web", file, line_of(src, m.start(2)), text, f"prop:{m.group(1)}"))
        return
    icons = lucide_imports(src)

    def visit(el: Element) -> None:
        if el.tag in icons:
            scan.icon_sites += 1
        scan.icon_sites += sum(1 for name, raw in el.attrs.items() if re.search(r"icon", name, re.I) and any(x in icons for x in re.findall(r"[A-Za-z_]\w*", raw)))
        for name, raw in el.attrs.items():
            if name in TEXT_ATTRS and raw:
                for t in attr_texts(raw):
                    scan.items.append(Item("web", file, el.line, t, f"attr:{name}"))
        for child in el.children:
            if child[0] == "text" and looks_ui(child[1]):
                scan.items.append(Item("web", file, child[2], child[1], "jsx"))
            elif child[0] == "expr":
                for t in child[1]:
                    scan.items.append(Item("web", file, child[2], t, "jsx-expr"))
        labels = element_label(el)
        # icon={Foo} (Button, IconButton, Tab ...): chữ là con của chính phần tử hay thuộc tính label.
        for name, raw in el.attrs.items():
            if re.search(r"icon", name, re.I) and raw:
                names = [icons[x] for x in re.findall(r"[A-Za-z_]\w*", raw) if x in icons]
                for label in labels[:1]:
                    for icon in dict.fromkeys(names):
                        if icon not in TRANSIENT_ICONS:
                            scan.pairs.append(Pair("web", file, el.line, label, icon, f"prop:{name}"))
        # <Foo className="size-4" /> cạnh chữ cùng cha, hay icon duy nhất trong nút có aria-label.
        kids = el.children
        for index, child in enumerate(kids):
            if child[0] != "el" or child[1].tag not in icons:
                continue
            icon = icons[child[1].tag]
            near = None
            for step in (1, -1):
                k = index + step
                while 0 <= k < len(kids) and kids[k][0] == "el" and kids[k][1].tag in icons:
                    k += step  # nhiều icon liền nhau: bỏ qua cho tới chữ
                if 0 <= k < len(kids) and kids[k][0] in ("text", "expr"):
                    t = kids[k][1] if kids[k][0] == "text" else " / ".join(kids[k][1])
                    if looks_ui(t):
                        near = t
                        break
            if near is None and not any(c[0] in ("text", "expr") for c in kids):
                found = [x for name in ("aria-label", "ariaLabel", "title", "label") if name in el.attrs for x in attr_texts(el.attrs[name])]
                near = found[0] if found else None
            own = [x for name in ("aria-label", "ariaLabel", "title") if name in child[1].attrs for x in attr_texts(child[1].attrs[name])]
            if near is None and own:
                near = own[0]
            if near and icon not in TRANSIENT_ICONS:
                scan.pairs.append(Pair("web", file, child[1].line, near, icon, "sibling"))
        for child in kids:
            if child[0] == "el":
                visit(child[1])

    for root in jsx_elements(src):
        visit(root)


def web_files() -> list[Path]:
    return [path for d in WEB_DIRS for path in sorted((WEB / d).rglob("*"))
            if path.suffix in (".ts", ".tsx") and ".test." not in path.name and not path.name.endswith(".d.ts")]


def web_scan() -> Scan:
    scan = Scan()
    for path in web_files():
        web_scan_file(path, scan)
    return scan


# ---------------------------------------------------------------------------------------------------------------------------------------
# Native: bộ đọc Kotlin nhỏ


def blank_comments(src: str) -> str:
    """Thay chú thích bằng khoảng trắng (giữ vị trí và số dòng), không đụng chuỗi."""
    out = list(src)
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if src.startswith('"""', i):
            j = src.find('"""', i + 3)
            i = n if j < 0 else j + 3
            continue
        if c in "\"'":
            if c == "'" and not re.match(r"'(\\.|[^'\\])'", src[i:i + 6]):
                i += 1
                continue
            i = skip_string(src, i)
            continue
        if c == "/" and src[i + 1:i + 2] in ("/", "*"):
            end = skip_comment(src, i)
            for k in range(i, end):
                if out[k] != "\n":
                    out[k] = " "
            i = end
            continue
        i += 1
    return "".join(out)


def icon_wrappers() -> dict[str, str]:
    """`PencilIcon` -> `pencil` từ components/Icons.kt (mỗi hàm bọc một LucidePaths.X)."""
    text = (KT / "components" / "Icons.kt").read_bytes().decode("utf-8")
    out: dict[str, str] = {}
    for m in re.finditer(r"fun (\w+Icon)\([^)]*\)\s*=\s*(?:\n\s*)?LucideIcon\(LucidePaths\.(\w+)", text):
        out[m.group(1)] = m.group(2).lower().replace("_", "-")
    return out


def glyph_icons() -> dict[str, str]:
    """PlayerGlyph("⋯") -> `ellipsis`: bảng `"⋯" -> LucidePaths.ELLIPSIS` trong nowplaying/PlayerVisuals.kt."""
    text = (KT / "nowplaying" / "PlayerVisuals.kt").read_bytes().decode("utf-8")
    return {m.group(1): m.group(2).lower().replace("_", "-") for m in re.finditer(r'"([^"\w]+)"\s*->\s*LucidePaths\.(\w+)', text)}


ICON_CALL = re.compile(r"\b(\w+Icon|LucideIcon|PlayerGlyph)\(")


def kt_callee_before(src: str, pos: int) -> tuple[str, str | None]:
    """Lệnh gọi bao quanh vị trí `pos` (tên hàm) và tên đối số có tên đứng ngay trước chuỗi (nếu có)."""
    depth = 0
    i = pos - 1
    named = None
    m = re.search(r"(\w+)\s*=\s*$", src[max(0, pos - 40):pos])
    if m:
        named = m.group(1)
    while i >= 0:
        c = src[i]
        if c in ")]}":
            depth += 1
        elif c in "([{":
            if depth == 0:
                if c == "(":
                    m2 = re.search(r"(\w+)\s*$", src[max(0, i - 60):i])
                    return (m2.group(1) if m2 else ""), named
                if c == "{":
                    return "", named
            else:
                depth -= 1
        elif c == '"':  # đang đi lùi qua một chuỗi khác: bỏ qua tới dấu nháy mở của nó
            j = i - 1
            while j >= 0 and not (src[j] == '"' and src[j - 1:j] != "\\"):
                j -= 1
            i = j
        i -= 1
    return "", named


def call_at(src: str, name_start: int, paren: int) -> tuple[int, str]:
    """Hết lệnh gọi (gồm lambda theo sau) và chữ của nó. Trả về (vị trí hết, đoạn)."""
    end = skip_balanced(src, paren, "(", ")")
    j = end
    while j < len(src) and src[j] in " \t\r\n":
        j += 1
    if src[j:j + 1] == "{":
        end = skip_balanced(src, j, "{", "}")
    return end, src[name_start:end]


def top_level(segment: str, open_at: int) -> list[tuple[int, str]]:
    """Mọi chuỗi trực tiếp ở mức đối số (không nằm trong lệnh gọi lồng hay lambda) của lệnh gọi mở tại `open_at` trong `segment`."""
    found: list[tuple[int, str]] = []
    depth = 0
    i = open_at
    n = len(segment)
    while i < n:
        c = segment[i]
        if c == '"':
            j = skip_string(segment, i)
            if depth == 1:
                found.append((i, literal_text(segment[i:j])))
            i = j
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    return found


def icon_name(segment: str, m: re.Match, glyphs: dict[str, str], wrappers: dict[str, str]) -> str:
    """Tên lucide của lệnh vẽ icon khớp `m` trong `segment` (hay `native:Tên` nếu không quy được)."""
    name = m.group(1)
    if name == "LucideIcon":
        lm = re.match(r"\w+\(\s*LucidePaths\.(\w+)", segment[m.start():m.start() + 80])
        return lm.group(1).lower().replace("_", "-") if lm else "native:LucideIcon"
    if name == "PlayerGlyph":
        gm = re.match(r"\w+\(\s*\"([^\"]*)\"", segment[m.start():m.start() + 40])
        return glyphs.get(gm.group(1), "native:PlayerGlyph") if gm else "native:PlayerGlyph"
    return wrappers.get(name, f"native:{name}")


def eligible_icons(segment: str, open_at: int, glyphs: dict[str, str], wrappers: dict[str, str]) -> list[str]:
    """Icon nằm ở mức đối số hay trong lambda trực tiếp của lệnh gọi (không sâu hơn một lệnh gọi lồng khác)."""
    found: list[str] = []
    for m in ICON_CALL.finditer(segment):
        # chuỗi ngoặc từ đầu lệnh gọi tới icon: chỉ cho `(` đầu rồi toàn `{`
        stack: list[str] = []
        i = open_at
        end = m.start()
        while i < end:
            c = segment[i]
            if c == '"':
                i = skip_string(segment, i)
                continue
            if c in "([{":
                stack.append(c)
            elif c in ")]}":
                if stack:
                    stack.pop()
            i += 1
        if not stack or stack[0] != "(" and stack[0] != "{":
            continue
        if any(c == "(" for c in stack[1:]):
            continue
        icon = icon_name(segment, m, glyphs, wrappers)
        found.append(icon)
    return found


def kt_scan_file(path: Path, scan: Scan, wrappers: dict[str, str], glyphs: dict[str, str]) -> None:
    raw = path.read_bytes().decode("utf-8")
    src = blank_comments(raw)
    file = rel(path)
    scan.icon_sites += sum(1 for m in ICON_CALL.finditer(src) if src[max(0, m.start() - 4):m.start()] != "fun ")
    # 1. mọi chuỗi giống chữ cho người nghe
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if src.startswith('"""', i):
            j = src.find('"""', i + 3)
            i = n if j < 0 else j + 3
            continue
        if c == "'":
            m = re.match(r"'(\\.|[^'\\])'", src[i:i + 6])
            i += m.end() if m else 1
            continue
        if c != '"':
            i += 1
            continue
        j = skip_string(src, i)
        text = literal_text(src[i:j])
        callee, named = kt_callee_before(src, i)
        line = line_of(src, i)
        i = j
        if src[:i - len(text) - 2].rstrip().endswith("import") or callee in KT_SKIP_CALLEE or (named in KT_SKIP_NAMED):
            continue
        if re.match(r"^(?:.*Exception|.*Error)$", callee):
            continue
        ui_context = callee in {"BasicText", "Caption", "MenuRow", "ListRow", "ActionRow", "SwitchRow", "DisclosureRow", "Label"} or named in KT_NAMED
        if looks_ui(text, strict=not ui_context) and not (named is None and not callee and text.islower()):
            scan.items.append(Item("native", file, line, text, f"kt:{named or callee or 'literal'}"))
    # 2. cặp nhãn <-> icon: trong một lệnh gọi (nhãn là đối số trực tiếp) hay cùng khối Row / Box / Column
    seen: set[tuple[int, str]] = set()

    def pair_from_call(name_start: int, paren: int, via: str) -> None:
        end, segment = call_at(src, name_start, paren)
        open_at = paren - name_start
        labels = [t for _, t in top_level(segment, open_at) if looks_ui(t)]
        icons = eligible_icons(segment, open_at, glyphs, wrappers)
        if labels and icons:
            for icon in dict.fromkeys(icons):
                key = (name_start, icon)
                if key not in seen:
                    seen.add(key)
                    scan.pairs.append(Pair("native", file, line_of(src, name_start), labels[0], icon, via))

    for m in re.finditer(r"\b([A-Z]\w*)\(", src):
        if m.group(1).endswith("Icon") or m.group(1) in ("LucideIcon", "PlayerGlyph"):
            continue
        pair_from_call(m.start(), m.end() - 1, "call")
    for m in re.finditer(r"\b(Row|Box|Column)\(", src):
        end, segment = call_at(src, m.start(), m.end() - 1)
        body_start = skip_balanced(src, m.end() - 1, "(", ")")
        j = body_start
        while j < len(src) and src[j] in " \t\r\n":
            j += 1
        if src[j:j + 1] != "{":
            continue
        body_end = skip_balanced(src, j, "{", "}")
        body = src[j + 1:body_end - 1]
        statements: list[tuple[str, str | None, list[str]]] = []
        depth = 0
        k = 0
        while k < len(body):
            c = body[k]
            if c == '"':
                k = skip_string(body, k)
                continue
            if c in "([{":
                depth += 1
            elif c in ")]}":
                depth -= 1
            elif depth == 0:
                cm = re.match(r"([A-Z]\w*)\(", body[k:])
                if cm and (k == 0 or not (body[k - 1].isalnum() or body[k - 1] == ".")):
                    cend, cseg = call_at(body, k, k + cm.end() - 1)
                    open_at = cm.end() - 1
                    name = cm.group(1)
                    if name.endswith("Icon") or name in ("LucideIcon", "PlayerGlyph"):
                        statements.append(("icon", None, [icon_name(cseg, ICON_CALL.match(cseg), glyphs, wrappers)]))
                    else:
                        labels = [t for _, t in top_level(cseg, open_at) if looks_ui(t)]
                        if labels:
                            statements.append(("text", labels[0], []))
                    k = cend
                    continue
            k += 1
        icon_list = [icon for kind, _, icons in statements if kind == "icon" for icon in icons]
        texts = [t for kind, t, _ in statements if kind == "text" and t]
        if len(icon_list) == 1 and texts:
            key = (m.start(), icon_list[0])
            if key not in seen:
                seen.add(key)
                scan.pairs.append(Pair("native", file, line_of(src, m.start()), texts[0], icon_list[0], "row"))


def native_scan() -> Scan:
    scan = Scan()
    wrappers = icon_wrappers()
    glyphs = glyph_icons()
    for path in sorted(KT.rglob("*.kt")):
        if path.relative_to(KT).parts[0] == "theme" or path.name in ("Icons.kt", "LucidePaths.kt"):
            continue
        kt_scan_file(path, scan, wrappers, glyphs)
    return scan


# ---------------------------------------------------------------------------------------------------------------------------------------
# So sánh


def fold(text: str) -> str:
    """Bỏ dấu, hạ chữ, chỉ giữ chữ-số: để so chữ gần giống."""
    s = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", s.lower()).split())


OLD_TONE = {"òa": "oà", "óa": "oá", "ỏa": "oả", "õa": "oã", "ọa": "oạ", "òe": "oè", "óe": "oé", "ỏe": "oẻ", "õe": "oẽ", "ọe": "oẹ",
            "ùy": "uỳ", "úy": "uý", "ủy": "uỷ", "ũy": "uỹ", "ụy": "uỵ"}


def key_loose(text: str) -> str:
    """Khoá so "cùng chữ": NFC, hạ chữ, dấu thanh về một kiểu (oà/òa), "..." = "…", bỏ dấu câu cuối, một dấu cách."""
    s = unicodedata.normalize("NFC", text).lower()
    for new, old in OLD_TONE.items():
        s = s.replace(new, old)
    s = s.replace("...", "…").replace("×", "x").replace("−", "-").replace("–", "-")
    s = re.sub(r"\s*·\s*", " · ", s)
    s = re.sub(r"[\s…:.!?;,]+$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def group(items: list[Item], key) -> dict[str, list[Item]]:
    out: dict[str, list[Item]] = defaultdict(list)
    for item in items:
        out[key(item)].append(item)
    return out


def where(items: list[Item] | list[Pair], limit: int = 2) -> str:
    seen = sorted({f"{i.file.replace('ui/src/', '').replace('mobile/android/app/src/main/java/vn/abook/player/ui/', 'native/')}:{i.line}" for i in items})
    more = f" (+{len(seen) - limit})" if len(seen) > limit else ""
    return ", ".join(f"`{s}`" for s in seen[:limit]) + more


def esc(text: str, limit: int = 44) -> str:
    text = text.replace("|", "\\|").replace("`", "'")
    return text if len(text) <= limit else text[:limit - 1] + "…"


def render_body() -> str:
    web = web_scan()
    native = native_scan()
    return render_report(web, native)


def render_report(web: Scan, native: Scan) -> str:
    w_items = sorted(set(web.items), key=lambda i: (i.file, i.line, i.text))
    n_items = sorted(set(native.items), key=lambda i: (i.file, i.line, i.text))
    w_pairs = sorted(set(web.pairs), key=lambda p: (p.file, p.line, p.label, p.icon))
    n_pairs = sorted(set(native.pairs), key=lambda p: (p.file, p.line, p.label, p.icon))
    w_by = group(w_items, lambda i: key_loose(i.text))
    n_by = group(n_items, lambda i: key_loose(i.text))
    out: list[str] = [BEGIN, ""]
    out.append(f"Quét: web {len(w_items)} chữ ({len(w_by)} khác nhau), {len(w_pairs)} cặp nhãn-icon; native {len(n_items)} chữ ({len(n_by)} khác nhau), "
               f"{len(n_pairs)} cặp nhãn-icon. Nhãn so theo khoá lỏng (hạ chữ, dấu thanh một kiểu, `...` = `…`, bỏ dấu câu cuối).")
    out.append("")
    out += section_a(w_items, n_items, w_by, n_by, w_pairs, n_pairs)
    out += section_b(w_pairs, n_pairs, web.icon_sites, native.icon_sites)
    out += section_c(w_items, n_items, w_by, n_by)
    out += section_d(w_items, n_items, w_by, n_by)
    out += ["", END, ""]
    return "\n".join(out)


STOP = {"va", "cua", "cho", "the", "la", "mot", "nhung", "cac", "khi", "se", "da", "co", "khong", "voi", "nay", "no", "tu", "den", "trong", "o", "tren"}


def tokens(text: str) -> set[str]:
    """Từ không dấu của nhãn (bỏ từ nối); chỗ điền `{}` là một từ `zzz` để "Giọng" và "Giọng của {}" không bị coi là một."""
    return {t for t in fold(text.replace("{}", " zzz ")).split() if t not in STOP and len(t) > 1}


def short(text: str) -> bool:
    """Nhãn ngắn, viết như một nhãn (chữ hoa đầu, không phải mảnh câu như "chương (" hay "{} giọng")."""
    t = text.strip()
    return len(t) <= 48 and len(t.split()) <= 6 and bool(t[:1]) and (t[0].isupper() or t[0].isdigit()) and t.count("(") == t.count(")")


def section_a(w_items, n_items, w_by, n_by, w_pairs, n_pairs) -> list[str]:
    """Cùng việc khác chữ: nhãn ngắn chưa có nguyên văn ở phía kia mà giống một nhãn bên đó (chung từ, gần nhau, hay chung icon)."""
    w_icons: dict[str, set[str]] = defaultdict(set)
    n_icons: dict[str, set[str]] = defaultdict(set)
    for p in w_pairs:
        w_icons[key_loose(p.label)].add(p.icon)
    for p in n_pairs:
        n_icons[key_loose(p.label)].add(p.icon)
    w_only = {k: v for k, v in w_by.items() if k not in n_by and short(v[0].text) and len(k) >= 3}
    n_only = {k: v for k, v in n_by.items() if k not in w_by and short(v[0].text) and len(k) >= 3}
    index: dict[str, set[str]] = defaultdict(set)
    for k, v in w_only.items():
        for t in tokens(v[0].text):
            index[t].add(k)
    for k in w_only:
        for icon in w_icons.get(k, ()):
            index[f"icon:{icon}"].add(k)
    rows = []
    for nk, nv in n_only.items():
        cand: set[str] = set()
        for t in tokens(nv[0].text):
            cand |= index.get(t, set())
        for icon in n_icons.get(nk, ()):
            cand |= index.get(f"icon:{icon}", set())
        for wk in cand:
            wv = w_only[wk]
            a, b = tokens(nv[0].text), tokens(wv[0].text)
            jac = len(a & b) / len(a | b) if a | b else 0.0
            ratio = SequenceMatcher(None, fold(nv[0].text), fold(wv[0].text)).ratio()
            shared_icon = bool(n_icons.get(nk, set()) & w_icons.get(wk, set()))
            score = max(jac, ratio) + (0.3 if shared_icon else 0.0)
            if (jac >= 0.5 and ratio >= 0.5) or ratio >= 0.8 or (shared_icon and max(jac, ratio) >= 0.2):
                rows.append((-round(score, 3), nv[0].text, wv[0].text, nk, wk, shared_icon, nv, wv))
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    out = ["## a. Cùng việc, khác chữ", "",
           f"Cặp nhãn ngắn (<= 6 chữ) mà phía kia KHÔNG có nguyên văn nhưng có nhãn giống (chung từ, gần nhau, hay chung icon). {len(rows)} cặp; 40 cặp đầu "
           "theo độ giống. `icon` = cùng icon lucide.", "",
           "| native | web | giống | nơi |", "|---|---|---|---|"]
    for r in rows[:40]:
        out.append(f"| {esc(r[1])} | {esc(r[2])} | {min(1.0, -r[0]):.2f}{' · icon' if r[5] else ''} | {where(r[6], 1)} ~ {where(r[7], 1)} |")
    if not rows:
        out.append("| (không có) | | | |")
    out.append("")
    return out


def section_b(w_pairs: list[Pair], n_pairs: list[Pair], w_sites: int, n_sites: int) -> list[str]:
    w_pairs = [p for p in w_pairs if short(p.label)]
    n_pairs = [p for p in n_pairs if short(p.label)]
    w_lab: dict[str, dict[str, list[Pair]]] = defaultdict(lambda: defaultdict(list))
    n_lab: dict[str, dict[str, list[Pair]]] = defaultdict(lambda: defaultdict(list))
    for p in w_pairs:
        w_lab[key_loose(p.label)][p.icon].append(p)
    for p in n_pairs:
        n_lab[key_loose(p.label)][p.icon].append(p)
    diff_icon = []
    for label in sorted(set(w_lab) & set(n_lab)):
        wi, ni = set(w_lab[label]), set(n_lab[label])
        if not (wi & ni):
            diff_icon.append((label, wi, ni))
    out = ["## b. Cùng nhãn khác icon, cùng icon khác nhãn", "",
           f"**Cùng nhãn, khác icon** ({len(diff_icon)} nhãn có icon ở cả hai phía mà không chung icon nào):", "",
           "| nhãn | web | native | nơi |", "|---|---|---|---|"]
    for label, wi, ni in diff_icon[:40]:
        wp = [p for i in sorted(wi) for p in w_lab[label][i]]
        npp = [p for i in sorted(ni) for p in n_lab[label][i]]
        out.append(f"| {esc(wp[0].label)} | {', '.join(sorted(wi))} | {', '.join(sorted(ni))} | {where(wp, 1)} ~ {where(npp, 1)} |")
    if not diff_icon:
        out.append("| (không có) | | | |")
    w_icon: dict[str, dict[str, list[Pair]]] = defaultdict(lambda: defaultdict(list))
    n_icon: dict[str, dict[str, list[Pair]]] = defaultdict(lambda: defaultdict(list))
    for p in w_pairs:
        w_icon[p.icon][key_loose(p.label)].append(p)
    for p in n_pairs:
        n_icon[p.icon][key_loose(p.label)].append(p)
    same_icon = []
    for icon in sorted(set(w_icon) & set(n_icon)):
        wl, nl = set(w_icon[icon]), set(n_icon[icon])
        if not (wl & nl):
            same_icon.append((icon, wl, nl))
    out += ["", f"**Cùng icon, khác nhãn** ({len(same_icon)} icon dùng ở cả hai phía mà không chung nhãn nào):", "",
            "| icon | web | native |", "|---|---|---|"]
    for icon, wl, nl in same_icon[:40]:
        wl_show = ", ".join(esc(w_icon[icon][k][0].label) for k in sorted(wl)[:4])
        nl_show = ", ".join(esc(n_icon[icon][k][0].label) for k in sorted(nl)[:4])
        out.append(f"| {icon} | {wl_show} | {nl_show} |")
    if not same_icon:
        out.append("| (không có) | | |")
    n_native_only = sorted({p.icon for p in n_pairs if p.icon.startswith("native:")})
    out += ["", f"Phủ của bộ ghép: icon dùng ở {n_sites} chỗ trong mã native, ghép được với nhãn chữ ở {len(n_pairs)}; web {w_sites} chỗ, ghép được {len(w_pairs)}. "
            "Phần còn lại là icon không đi cùng nhãn chữ (nút chỉ icon, chỉ báo) hay nhãn dựng từ model (vd tên nhóm Cài đặt), nên KHÔNG có trong bảng.",
            f"Icon native chưa quy về lucide ({len(n_native_only)}): {', '.join(f'`{x}`' for x in n_native_only) or '(không có)'}.",
            f"Số cặp: web {len(w_pairs)}, native {len(n_pairs)}; icon lucide dùng: web {len({p.icon for p in w_pairs})}, native {len({p.icon for p in n_pairs})}.", ""]
    return out


def screen_of(item: Item) -> str:
    return item.file.replace("ui/src/", "").replace("mobile/android/app/src/main/java/vn/abook/player/ui/", "native/")


def section_c(w_items, n_items, w_by, n_by) -> list[str]:
    n_only = [i for i in n_items if key_loose(i.text) not in w_by and short(i.text)]
    w_only = [i for i in w_items if key_loose(i.text) not in n_by and short(i.text) and i.file.replace("ui/src/", "").split("/")[0] in PHONE_WEB_DIRS]
    w_other = [i for i in w_items if key_loose(i.text) not in n_by and short(i.text) and i.file.replace("ui/src/", "").split("/")[0] not in PHONE_WEB_DIRS]
    out = ["## c. Nhãn chỉ có ở một phía, theo màn", "",
           "Nhãn ngắn (<= 6 chữ) không có (theo khoá lỏng) ở phía kia - kể cả chữ giống chữ ở mục a. Để phân biệt tính năng thiếu với chữ trôi: "
           "một màn native có nhiều nhãn chỉ-native mà web cùng màn không có thường là tính năng mới; vài nhãn lẻ thường là chữ trôi (mục a).", "",
           f"### c1. Chỉ có ở native ({len({key_loose(i.text) for i in n_only})} nhãn)", ""]
    out += grouped(n_only, 25)
    out += ["", f"### c2. Chỉ có ở web phía điện thoại - listen/, android/, shared/ ({len({key_loose(i.text) for i in w_only})} nhãn)", ""]
    out += grouped(w_only, 25)
    other = group(w_other, lambda i: i.file.replace("ui/src/", "").split("/")[0])
    out += ["", "### c3. Chỉ có ở web phía máy tính / Studio (chỉ đếm)", "",
            "| thư mục | nhãn |", "|---|---|"]
    for name in sorted(other):
        out.append(f"| {name}/ | {len({key_loose(i.text) for i in other[name]})} |")
    if not other:
        out.append("| (không có) | |")
    out.append("")
    return out


def grouped(items: list[Item], cap: int) -> list[str]:
    by = group(items, screen_of)
    out: list[str] = []
    for screen in sorted(by):
        unique: dict[str, Item] = {}
        for i in by[screen]:
            unique.setdefault(key_loose(i.text), i)
        shown = sorted(unique.values(), key=lambda i: (i.line, i.text))
        text = "; ".join(f"{esc(i.text)} (`{i.line}`)" for i in shown[:cap])
        more = f"; ... +{len(shown) - cap}" if len(shown) > cap else ""
        out.append(f"- `{screen}` ({len(shown)}): {text}{more}")
    if not out:
        out.append("- (không có)")
    return out


def section_d(w_items, n_items, w_by, n_by) -> list[str]:
    out = ["## d. Chữ hoa, dấu câu, `…` và `...`, dấu thanh, số", ""]
    # d1: cùng khoá lỏng nhưng khác nguyên văn giữa hai phía
    diff = []
    for key in sorted(set(w_by) & set(n_by)):
        wt = sorted({i.text for i in w_by[key]})
        nt = sorted({i.text for i in n_by[key]})
        if not (set(wt) & set(nt)):
            diff.append((key, wt, nt, w_by[key], n_by[key]))
    out += [f"**d1. Cùng nhãn (theo khoá lỏng) nhưng khác nguyên văn giữa hai phía** ({len(diff)}):", "",
            "| web | native | khác ở | nơi |", "|---|---|---|---|"]
    for key, wt, nt, wi, ni in diff[:60]:
        out.append(f"| {esc(wt[0])} | {esc(nt[0])} | {diff_kind(wt[0], nt[0])} | {where(wi, 1)} ~ {where(ni, 1)} |")
    if not diff:
        out.append("| (không có) | | | |")
    # d2: thống kê kiểu viết theo phía
    def count(items, pattern):
        return sum(1 for i in items if re.search(pattern, i.text))
    rows = [
        ("dấu ba chấm ASCII `...`", r"\.\.\."), ("dấu ba chấm `…`", "…"), ("kết thúc bằng dấu chấm `.`", r"[^.]\.$"),
        ("kết thúc bằng `!`", r"!$"), ("kết thúc bằng `:`", r":$"),
        ("dấu thanh kiểu cũ `oà oá uý`", r"o[àáảãạ]|u[ýỳỷỹỵ]"), ("dấu thanh kiểu mới `òa óa úy`", r"[òóỏõọ][ae]|[ùúủũụ]y"),
        ("số thập phân dấu phẩy `1,5`", r"\d,\d"), ("số thập phân dấu chấm `1.5`", r"(?<![\d.])\d\.\d(?!\d{2})"),
        ("nhân bằng `×`", "×"), ("nhân bằng `x` sau số", r"\d\s?x\b"), ("ngăn cách `·`", "·"), ("ngăn cách ` - `", r" - "), ("gạch dài `—`/`–`", "[—–]"),
        ("giờ `1:30` hay `1 giờ 30`", r"\d:\d\d"), ("dấu `%` dính số", r"\d%"), ("dấu `%` cách số", r"\d %"),
    ]
    out += ["", "**d2. Kiểu viết theo phía** (số chữ khớp / tổng; chữ quét ở trên):", "", "| kiểu | web | native |", "|---|---|---|"]
    for name, pattern in rows:
        out.append(f"| {name} | {count(w_items, pattern)} / {len(w_items)} | {count(n_items, pattern)} / {len(n_items)} |")
    # d3: nhãn ngắn viết hoa chữ đầu / chữ thường chữ đầu
    def first_lower(items):
        return [i for i in items if len(i.text) <= 48 and len(i.text.split()) <= 6 and i.text[:1].islower() and i.kind.startswith(("jsx", "attr", "kt:BasicText", "kt:MenuRow", "kt:ListRow"))]
    wl, nl = first_lower(w_items), first_lower(n_items)
    out += ["", f"**d3. Nhãn ngắn bắt đầu bằng chữ thường** (web {len(wl)}, native {len(nl)}); 15 đầu mỗi phía:", ""]
    for name, lst in (("web", wl), ("native", nl)):
        sample = sorted({(i.text, where([i], 1)) for i in lst})[:15]
        out.append(f"- {name}: " + ("; ".join(f"{esc(t)} ({w})" for t, w in sample) or "(không có)"))
    new_style = re.compile(r"[òóỏõọ][ae]|[ùúủũụ]y")
    out += ["", "**d3b. Chữ dùng dấu thanh kiểu mới (`òa óa úy`) - kiểu thiểu số** (DESIGN.md chưa chọn kiểu nào); 12 đầu mỗi phía:", ""]
    for name, lst in (("web", w_items), ("native", n_items)):
        sample = sorted({(i.text, where([i], 1)) for i in lst if new_style.search(i.text)})[:12]
        out.append(f"- {name}: " + ("; ".join(f"{esc(t, 60)} ({w})" for t, w in sample) or "(không có)"))
    # d4: nhãn trùng khoá lỏng trong cùng một phía nhưng viết khác nhau
    for name, by in (("web", w_by), ("native", n_by)):
        mixed = [(k, sorted({i.text for i in v})) for k, v in sorted(by.items()) if len({i.text for i in v}) > 1 and short(v[0].text)]
        out += ["", f"**d4. {name}: cùng nhãn nhưng viết khác nhau trong chính phía này** ({len(mixed)}); 15 đầu:", ""]
        for k, forms in mixed[:15]:
            out.append(f"- " + " | ".join(f"`{esc(f)}`" for f in forms[:4]) + f" ({where(by[k], 2)})")
        if not mixed:
            out.append("- (không có)")
    return out


def diff_kind(a: str, b: str) -> str:
    kinds = []
    if a.lower() == b.lower() and a != b:
        kinds.append("chữ hoa")
    if ("..." in a) != ("..." in b) and ("…" in a or "…" in b):
        kinds.append("`…` / `...`")
    if re.sub(r"[\s…:.!?;,]+$", "", a) == re.sub(r"[\s…:.!?;,]+$", "", b) and a != b and not kinds:
        kinds.append("dấu câu cuối")
    if unicodedata.normalize("NFC", a).lower() != unicodedata.normalize("NFC", b).lower() and key_loose(a) == key_loose(b) and not kinds:
        kinds.append("dấu thanh / ký tự")
    return ", ".join(kinds) or "ký tự"


# ---------------------------------------------------------------------------------------------------------------------------------------


HEAD = """# Lệch chữ và icon giữa các nền tảng giao diện

Chủ sách 26-10: "giao diện giữa các nền tảng phải làm đồng nhất ở mọi chỗ có thể nhé, từng cái chữ, từng cái icon, từng cái bo góc".
Ba thứ, ba nguồn chung:

- **Bo góc**: `docs/DESIGN.md` 5.5 -> `scripts/gen_native_tokens.py` -> `Tokens.kt` (native) + `ui/src/shared/tokens.generated.css` (web:
  `rounded-control` / `rounded-cover` / `rounded-sheet`). Luật máy: `ui/src/shared/radiusRules.test.ts`, `RadiusRulesTest.kt`.
- **Icon**: lucide. `scripts/gen_lucide_icons.py` sinh nét cho native và Qt từ đúng gói web dùng; luật `IconRulesTest.kt`.
- **Chữ**: chưa có nguồn chung. Giai đoạn này chỉ ĐO lệch (bảng dưới); chọn dạng chuẩn là việc của Lead, chưa đổi chữ nào.

Bảng dưới do `scripts/ui_parity.py` sinh (`python -X utf8 scripts/ui_parity.py`; `--check` báo lệch, `tests/test_ui_parity.py` chạy `--check`).
Bộ đọc là heuristic trên mã nguồn (không chạy app): chữ nằm trong biểu thức phức tạp hay ghép chuỗi có thể sót; icon của hàng dựng bằng hàm bọc
(vd `GroupIcon(group)`) chưa quy về lucide thì ghi `native:Tên`. Sai lệch được báo cáo chứ KHÔNG làm hỏng test trong giai đoạn này.

"""


def render_doc(current: str | None) -> str:
    body = render_body()
    if current and BEGIN in current and END in current:
        head = current[:current.index(BEGIN)]
        tail = current[current.index(END) + len(END):].lstrip("\n")
        return head + body + (("\n" + tail) if tail else "")
    return HEAD + body


def main(argv: list[str]) -> int:
    if "--aliases" in argv:
        ALIASES.write_bytes(alias_json(alias_table()).encode("utf-8"))  # LF
        print(f"đã ghi {ALIASES}")
        return 0
    current = DOC.read_bytes().decode("utf-8") if DOC.is_file() else None
    text = render_doc(current)
    if "--check" in argv:
        if current != text:
            print(f"{DOC} không còn khớp mã nguồn - chạy scripts/ui_parity.py", file=sys.stderr)
            return 1
        return 0
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_bytes(text.encode("utf-8"))  # LF
    print(f"đã ghi {DOC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
