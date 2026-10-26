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
"""
from __future__ import annotations

import importlib.util
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "ui" / "src"
KT_CORE = ROOT / "mobile" / "android" / "app" / "src" / "main" / "java" / "vn" / "abook" / "player"
KT = KT_CORE / "ui"
DOC = ROOT / "docs" / "UI_PARITY.md"
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
                  "setOf", "mapOf", "arrayOf", "put", "putExtra", "getString", "optString", "getJSONObject", "getJSONArray", "has",
                  "Intent", "IntentFilter", "toRegex", "startsWith", "endsWith", "contains", "split", "replace", "trim", "removePrefix",
                  "removeSuffix", "equals", "format", "assert", "Pair", "to", "storageKey", "route", "key", "id", "tag", "name", "optBoolean",
                  "optInt", "optLong", "optDouble", "getBoolean", "getInt", "getLong", "getDouble", "getString", "joinToString", "indexOf", "w", "e", "d", "i"}
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


_ICON_CACHE: dict[str, str] = {}


def alias_target(name: str) -> str:
    """Tên lucide -> tên gốc theo chuỗi alias (`trash-2` -> `trash`, `more-horizontal` -> `ellipsis`): hai tên một hình thì tính là một icon."""
    icons = _lucide_dir()
    for _ in range(4):
        path = icons / f"{name}.mjs"
        if not path.is_file():
            break
        m = re.search(r"export \{ default \} from '\./([\w-]+)\.mjs'", path.read_text(encoding="utf-8"))
        if not m:
            break
        name = m.group(1)
    return name


def lucide_name(ident: str) -> str:
    """`MoreHorizontal` / `Trash2` / `EllipsisIcon` -> tên file lucide thật (theo alias), vd `ellipsis`, `trash-2`."""
    if ident in _ICON_CACHE:
        return _ICON_CACHE[ident]
    base = ident[:-4] if ident.endswith("Icon") and len(ident) > 4 else ident
    kebab = re.sub(r"(?<=[a-z])(?=[A-Z0-9])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=[0-9])(?=[A-Za-z])", "-", base).lower()
    name = alias_target(kebab)
    _ICON_CACHE[ident] = name
    return name


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
    nested: list[tuple[int, int]] = []  # giá trị thuộc tính có JSX (`footer={<Actions>...</Actions>}`): chữ trong đó cũng là chữ giao diện

    def built(end: int, closed: bool) -> tuple[Element, int, bool]:
        el = Element(tag, line_of(src, i), attrs)
        for start, stop in nested:
            holder = Element("", el.line, {})
            scan_container(src, start, stop, holder)
            el.children += [c for c in holder.children if c[0] == "el"]
        return el, end, closed

    n = len(src)
    while j < n:
        while j < n and src[j].isspace():
            j += 1
        if j >= n:
            return None, i, False
        c = src[j]
        if c == "/" and src.startswith("/>", j):
            return built(j + 2, True)
        if c == ">":
            return built(j + 1, False)
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
            if re.search(r"<[A-Za-z>]", attrs[name]):
                nested.append((j + 1, end - 1))
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


def value_literals(src: str, i: int) -> list[tuple[int, str]]:
    """Các chuỗi trong MỘT giá trị bắt đầu ở `i` (tới dấu `,` / `;` / ngoặc đóng ở mức 0): `ok ? "a" : "b"`."""
    out: list[tuple[int, str]] = []
    depth = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c in "\"'`":
            j = skip_string(src, i)
            out.append((i, literal_text(src[i:j])))
            i = j
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif c in ",;" and depth == 0:
            break
        i += 1
    return out


PROP_LITERAL = re.compile(r"(?<![\w-])(label|title|description|caption|text|placeholder|hint|message|empty|heading|subtitle|note|all|listening|new|finished)\s*:")


def web_scan_file(path: Path, scan: Scan) -> None:
    src = path.read_bytes().decode("utf-8")
    file = rel(path)
    if path.suffix == ".ts":
        # File logic: mọi chuỗi có dạng chữ giao diện (hoa đầu / có dấu tiếng Việt), kể cả chuỗi trả về từ hàm nhãn.
        for pos, text in literals_in(strip_ts_comments(src)):
            if looks_ui(text, strict=True):
                scan.items.append(Item("web", file, line_of(src, pos), text, "ts"))
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
    # Chữ nằm trong hằng / bảng ngoài JSX (`{ value: "new", label: "Chưa nghe" }`): chỉ lấy khoá mang nghĩa nhãn, đọc từng chuỗi từ đúng chỗ khoá
    # (không đi dọc cả file - chữ JSX có dấu nháy lẻ làm lệch).
    plain = strip_ts_comments(src)
    # Chuỗi chữ trả về từ hàm / gán biến trong .tsx (`return "Đang tìm"`, `const title = ok ? "A" : "B"`) cũng là chữ giao diện, như bên .ts.
    for pos, text in literals_in(plain):
        if looks_ui(text, strict=True) and len(text) <= 300 and "=>" not in text and (" " in text.strip() or re.search(r"[À-ỹ]", text)) and not re.match(r"^[A-Z]\d", text):
            scan.items.append(Item("web", file, line_of(plain, pos), text, "tsx-literal"))
    for m in PROP_LITERAL.finditer(plain):
        for start, text in value_literals(plain, m.end()):
            if looks_ui(text, strict=True):
                scan.items.append(Item("web", file, line_of(plain, start), text, f"prop:{m.group(1)}"))


def web_scan() -> Scan:
    scan = Scan()
    for d in WEB_DIRS:
        for path in sorted((WEB / d).rglob("*")):
            if path.suffix in (".ts", ".tsx") and ".test." not in path.name and not path.name.endswith(".d.ts"):
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
        out[m.group(1)] = alias_target(m.group(2).lower().replace("_", "-"))
    return out


def glyph_icons() -> dict[str, str]:
    """PlayerGlyph("⋯") -> `ellipsis`: bảng `"⋯" -> LucidePaths.ELLIPSIS` trong nowplaying/PlayerVisuals.kt."""
    text = (KT / "nowplaying" / "PlayerVisuals.kt").read_bytes().decode("utf-8")
    return {m.group(1): alias_target(m.group(2).lower().replace("_", "-")) for m in re.finditer(r'"([^"\w]+)"\s*->\s*LucidePaths\.(\w+)', text)}


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
        return alias_target(lm.group(1).lower().replace("_", "-")) if lm else "native:LucideIcon"
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
    s = re.sub(r"\d+(?:[.,]\d+)?", "{}", s)  # "Lùi 15 giây" (native) = "Lùi ${n} giây" (web)
    s = s.replace("{}{}", "{}")
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
    out += section_e(web, native)
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


# ---------------------------------------------------------------------------------------------------------------------------------------
# Giai đoạn 2: luật cứng. Cặp màn web <-> native (ui_parity_pairs.json), bảng việc -> icon (docs/UI_PARITY.md), luật chữ (dấu thanh, dấu ba chấm).

PAIRS = ROOT / "scripts" / "ui_parity_pairs.json"
ICON_TABLE_BEGIN = "<!-- ui_parity:icons -->"
ICON_TABLE_END = "<!-- ui_parity:icons:end -->"
# Chữ giả / mẫu của thư viện mẫu và dữ liệu thử không phải chữ giao diện (có trích sách thật): không quét luật chữ.
COPY_SKIP_WEB = ("gallery/",)
# Chuỗi của lõi native KHÔNG phải chữ giao diện (so khớp chữ trong truyện, mã giọng): đổi dấu thanh sẽ làm hỏng việc khớp.
COPY_TONE_DATA = ("BookImport.kt:2241", "readaloud/VoiceGain.kt", "vieneu/VieneuUnits.kt")
COPY_SKIP_NATIVE = ("nowplaying/FakeNowPlayingModel.kt", "data/DemoLibrary.kt", "data/DemoPlayback.kt")
NEW_TONE = re.compile(r"[òóỏõọ][ae]|[ùúủũụ]y|[ÒÓỎÕỌ][AEae]|[ÙÚỦŨỤ][Yy]")
WEB_ROOT = "ui/src/"
NATIVE_ROOT = "mobile/android/app/src/main/java/vn/abook/player/ui/"


def pair_specs() -> list[dict]:
    import json
    return json.loads(PAIRS.read_bytes().decode("utf-8"))["pairs"]


def match_files(patterns: list[str], names: list[str]) -> list[str]:
    """`names` (đường dẫn tương đối) khớp mẫu glob; mẫu bắt đầu bằng `!` loại bớt."""
    from fnmatch import fnmatch
    chosen = [n for n in names if any(fnmatch(n, p) for p in patterns if not p.startswith("!"))]
    return [n for n in chosen if not any(fnmatch(n, p[1:]) for p in patterns if p.startswith("!"))]


def sentence(text: str) -> bool:
    """Câu dài (lời gợi ý dưới một dòng cài đặt, câu báo): hoa đầu, kết thúc bằng dấu câu, nhiều hơn một chữ."""
    t = text.strip()
    return bool(t[:1]) and t[0].isupper() and len(t.split()) > 1 and t[-1] in ".?!" and t.count("(") == t.count(")")


def label_items(items: list[Item], root: str, files: list[str], sentences: bool = False) -> dict[str, list[Item]]:
    """Nhãn (khoá lỏng) -> chữ, chỉ trong các file đã chọn và chỉ nhãn ngắn viết như nhãn (cặp có `sentences`: cả câu dài)."""
    out: dict[str, list[Item]] = defaultdict(list)
    for item in items:
        name = item.file[len(root):] if item.file.startswith(root) else item.file
        if name in files and (short(item.text) or (sentences and sentence(item.text))):
            out[key_loose(item.text)].append(item)
    return out


def pair_diff(web: Scan, native: Scan, spec: dict) -> dict:
    """Nhãn chỉ có ở một phía của một cặp màn, đã trừ danh sách cho phép (`allow`) và danh sách thiếu thật (`missing`)."""
    web_names = sorted({i.file[len(WEB_ROOT):] for i in web.items})
    native_names = sorted({i.file[len(NATIVE_ROOT):] for i in native.items})
    wf = match_files(spec["web"], web_names)
    nf = match_files(spec["native"], native_names)
    w = label_items(sorted(set(web.items), key=lambda i: (i.file, i.line, i.text)), WEB_ROOT, wf, bool(spec.get("sentences")))
    n = label_items(sorted(set(native.items), key=lambda i: (i.file, i.line, i.text)), NATIVE_ROOT, nf, bool(spec.get("sentences")))
    # `web_also`: file web chỉ để làm ĐỐI CHIẾU cho chữ native (nhãn chung nằm ở file khác); chữ của chúng không bị đòi phải có ở native.
    w_all = dict(w)
    for key, found in label_items(sorted(set(web.items), key=lambda i: (i.file, i.line, i.text)), WEB_ROOT, match_files(spec.get("web_also", []), web_names),
                                  bool(spec.get("sentences"))).items():
        w_all.setdefault(key, found)
    only = spec.get("only")  # "web": chỉ đòi nhãn web phải có ở native (không đòi chiều ngược lại)

    def listed(side: str, key: str, item: Item, entries: list[dict]) -> dict | None:
        from fnmatch import fnmatch
        root = WEB_ROOT if side == "web" else NATIVE_ROOT
        name = item.file[len(root):]
        for e in entries:
            if e["side"] != side:
                continue
            if "file" in e and fnmatch(name, e["file"]):
                return e
            if "label" in e and key_loose(e["label"]) == key:
                return e
            if "match" in e and re.search(e["match"], key):
                return e
        return None

    allow, missing = spec.get("allow", []), spec.get("missing", [])
    deferred = spec.get("deferred", [])
    result = {"id": spec["id"], "web_files": wf, "native_files": nf, "web_labels": len(w), "native_labels": len(n), "web_only": [], "native_only": [],
              "allowed": [], "missing": [], "deferred": []}
    for side, mine, other in (("web", w, n), ("native", n, w_all)):
        if only and side != only:
            continue
        for key in sorted(mine):
            if key in other:
                continue
            if listed(side, key, mine[key][0], allow):
                result["allowed"].append((side, mine[key][0]))
            elif listed(side, key, mine[key][0], missing):
                result["missing"].append((side, mine[key][0]))
            elif listed(side, key, mine[key][0], deferred):
                result["deferred"].append((side, mine[key][0]))
            else:
                result[f"{side}_only"].append(mine[key][0])
    return result


def icon_table() -> list[tuple[str, str]]:
    """Bảng việc -> icon viết tay trong docs/UI_PARITY.md: [(mẫu nhãn theo khoá lỏng, icon lucide)]. Hàng: `| Nhãn, Nhãn* | `icon` | ... |` (`*` = bất kỳ)."""
    text = DOC.read_bytes().decode("utf-8") if DOC.is_file() else ""
    if ICON_TABLE_BEGIN not in text or ICON_TABLE_END not in text:
        return []
    block = text[text.index(ICON_TABLE_BEGIN):text.index(ICON_TABLE_END)]
    out: list[tuple[str, str]] = []
    for line in block.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[1].startswith("`") and cells[1].endswith("`"):
            out += [("*".join(key_loose(part) for part in label.strip().split("*")), cells[1].strip("`")) for label in cells[0].split(",")]
    return out


def icon_violations(web: Scan, native: Scan) -> list[str]:
    from fnmatch import fnmatchcase
    table = icon_table()
    bad = []
    for p in sorted(set(web.pairs) | set(native.pairs), key=lambda p: (p.side, p.file, p.line)):
        key = key_loose(p.label)
        for pattern, want in table:
            if fnmatchcase(key, pattern) and p.icon != alias_target(want):
                bad.append(f"{p.file}:{p.line} \"{p.label}\" dùng {p.icon}, bảng việc -> icon ghi {want}")
                break
    return bad


def strip_ts_comments(src: str) -> str:
    """Bỏ chú thích // và /* */ của TS (giữ số dòng), không đụng chuỗi."""
    out = list(src)
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c in "\"'`":
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


# Chữ tận cùng `…` / `...` ngay sau một chữ cái hay số (và trước dấu đóng chuỗi / thẻ / hết dòng JSX), hay `${...}…` trong chuỗi mẫu có chữ: trạng thái,
# nhãn, nút, gợi ý ô nhập đều không kèm dấu ba chấm. `…` đứng một mình (nút "Thêm tuỳ chọn") và `…` ở đầu chữ không dính.
ELLIPSIS_END = re.compile(r"(?<=[^\W_])(?:…|\.\.\.)(?=[\"'`<]|\s*$)|`(?:[^`$\n]|\$\{[^}\n]*\})*[^\W\d_][ ]?(?:\$\{[^}\n]*\})?…`")
# Hàm cắt bớt chữ dài bằng `…` (không phải chữ giao diện) và một dấu cắt ở vân tay.
# Nhóm Xuất đang được gộp ở nhánh khác: file của nó chưa quét luật chữ (Lead đã dặn bỏ qua). Gộp xong thì sửa rồi xoá dòng này.
COPY_PENDING_EXPORT = ("android/ExportAudiobook.tsx", "android/ExportM4b.tsx", "android/ExportMp3.tsx", "desktop/AudiobookDialog.tsx", "desktop/ExportBookFileJob.tsx",
                       "desktop/bookFileExport.ts", "desktop/listenExport.ts", "studio/ExportBook.tsx", "studio/projectPacking.ts")
# Nhóm Nhạc do phiên Music đang sửa: cùng lý do.
COPY_PENDING_MUSIC = ("listen/MyMusic.tsx", "studio/MusicTab.tsx", "studio/musicLocal.ts")
COPY_ELLIPSIS_OK = ("shared/format.ts", "listen/findText.ts", "desktop/bookFileExport.ts:262", "desktop/OtherComputers.tsx:197", "android/SettingsScreen.tsx:347")


def copy_violations(web: Scan, native: Scan) -> tuple[list[str], list[str]]:
    """Luật chữ giao diện: (vi phạm cứng, nhắc nhẹ). Cứng: dấu thanh kiểu mới, chữ tận cùng `…` / `...`. Nhẹ: nhãn tận cùng `:`."""
    hard: list[str] = []
    soft: list[str] = []
    # Native: cả giao diện (ui/) lẫn lõi (vn/abook/player/*.kt ngoài ui/) - lõi cũng sinh lời người nghe đọc (lỗi, thông báo, tên mặc định).
    for base, skip, exts, strip, web_side in ((WEB, COPY_SKIP_WEB, (".ts", ".tsx"), strip_ts_comments, True), (KT, COPY_SKIP_NATIVE, (".kt",), blank_comments, False),
                                              (KT_CORE, COPY_SKIP_NATIVE + ("ui/",), (".kt",), blank_comments, False)):
        for path in sorted(base.rglob("*")):
            name = path.relative_to(base).as_posix()
            if path.suffix not in exts or ".test." in path.name or name.endswith(".d.ts") or name.startswith(skip) or name.startswith("theme/") or name in COPY_PENDING_EXPORT or name in COPY_PENDING_MUSIC:
                continue
            src = strip(path.read_bytes().decode("utf-8"))
            for lineno, line in enumerate(src.split(chr(10)), 1):
                if NEW_TONE.search(line) and not any(name == ok or f"{name}:{lineno}" == ok for ok in COPY_TONE_DATA):
                    hard.append(f"{rel(path)}:{lineno} dấu thanh kiểu mới: {line.strip()[:90]}")
                if web_side and ELLIPSIS_END.search(line) and not any(name == ok or f"{name}:{lineno}" == ok for ok in COPY_ELLIPSIS_OK):
                    hard.append(f"{rel(path)}:{lineno} chữ tận cùng dấu ba chấm: {line.strip()[:90]}")
    for items in (web.items, native.items):
        for i in sorted(set(items), key=lambda i: (i.file, i.line, i.text)):
            t = i.text.strip()
            if t.endswith(":") and short(t):
                soft.append(f"{i.file}:{i.line} nhãn tận cùng dấu hai chấm: {t[:80]}")
    return hard, soft


def section_e(web: Scan, native: Scan) -> list[str]:
    out = ["## e. Cặp màn web <-> native (luật cứng, scripts/ui_parity_pairs.json)", "",
           "Trong một cặp, mỗi nhãn ngắn phải có ở cả hai phía (khoá lỏng) trừ khi nằm trong `allow` (có lý do) hay `missing` (tính năng native chưa có thật - "
           "Lead xếp lịch). Cột lệch phải bằng 0 thì `--check` mới qua.", "",
           "| cặp | nhãn web | nhãn native | lệch web | lệch native | cho phép | thiếu thật |", "|---|---|---|---|---|---|---|"]
    diffs = [pair_diff(web, native, spec) for spec in pair_specs()]
    for d in diffs:
        out.append(f"| {d['id']} | {d['web_labels']} | {d['native_labels']} | {len(d['web_only'])} | {len(d['native_only'])} | {len(d['allowed'])} | {len(d['missing'])} |")
    for d in diffs:
        if d["missing"]:
            out += ["", f"Thiếu thật ở native - `{d['id']}`: " + "; ".join(esc(i.text, 40) for _, i in d["missing"][:40])]
    out.append("")
    return out


def hard_checks(web: Scan, native: Scan) -> list[str]:
    """Mọi lỗi của luật cứng (rỗng = qua)."""
    problems: list[str] = []
    for spec in pair_specs():
        d = pair_diff(web, native, spec)
        problems += [f"[{d['id']}] chỉ có ở web: \"{i.text}\" ({i.file.replace(WEB_ROOT, '')}:{i.line})" for i in d["web_only"]]
        problems += [f"[{d['id']}] chỉ có ở native: \"{i.text}\" ({i.file.replace(NATIVE_ROOT, 'native/')}:{i.line})" for i in d["native_only"]]
    problems += [f"[icon] {v}" for v in icon_violations(web, native)]
    hard, _ = copy_violations(web, native)
    problems += [f"[chữ] {v}" for v in hard]
    return problems


HEAD = """# Chữ, icon và bo góc giống nhau giữa các nền tảng giao diện

Chủ sách 26-10: "giao diện giữa các nền tảng phải làm đồng nhất ở mọi chỗ có thể nhé, từng cái chữ, từng cái icon, từng cái bo góc".
Ba thứ, ba nguồn chung, đều có luật máy (`python -X utf8 scripts/ui_parity.py --check`, chạy trong `tests/test_ui_parity.py`):

- **Bo góc**: `docs/DESIGN.md` 5.5 -> `scripts/gen_native_tokens.py` -> `Tokens.kt` (native) + `ui/src/shared/tokens.generated.css` (web:
  `rounded-control` / `rounded-cover` / `rounded-sheet`). Luật máy: `ui/src/shared/radiusRules.test.ts`, `RadiusRulesTest.kt`.
- **Icon**: lucide. `scripts/gen_lucide_icons.py` (MỘT danh sách `ICONS`) sinh nét cho native và Qt từ đúng gói web dùng; luật `IconRulesTest.kt`.
  Một việc = một icon trên mọi nền tảng: bảng "Việc -> icon" dưới đây là luật, `--check` báo nhãn nào dùng icon khác bảng (bên nào cũng vậy).
- **Chữ**: cặp màn `scripts/ui_parity_pairs.json` (nhãn có ở một phía mà phía kia không có thì `--check` đỏ, trừ mục `allow` có lý do),
  luật chữ bên dưới, và bảng đo lệch tự sinh ở cuối file.

## Việc -> icon

Tên icon theo lucide (hai tên một hình, vd `trash` = `trash-2`, tính là một). `*` khớp mọi chữ. Hàng nào thêm vào đây thì mọi chỗ dùng nhãn ấy,
web lẫn native, phải dùng đúng icon này.

<!-- ui_parity:icons -->
| Việc (nhãn) | Icon | Ghi chú |
|---|---|---|
| Bỏ ghép, Bỏ ghép* | `unplug` | gỡ một thiết bị đã ghép |
| Ghép lại | `link-2` | ghép lại thiết bị đã bỏ |
| Xoá, Xoá khoá, Xoá hồ sơ*, Xoá khỏi*, Xoá bản đọc, Bỏ ảnh bìa | `trash-2` | xoá / gỡ hẳn một thứ |
| Xoá ô tìm | `x` | xoá chữ trong ô, không xoá dữ liệu |
| Đọc theo | `text-align-start` | chữ chạy theo giọng |
| Thêm tuỳ chọn* | `ellipsis` | nút "..." của một hàng / màn; nhãn nghe được là "Thêm tuỳ chọn", không bao giờ "Thêm" trơn (đó là dấu cộng) |
| Thêm sách | `plus` | |
| Làm mới | `refresh-cw` | |
| Nhạc nền | `eighth-note` | |
| Sửa thông tin | `pencil` | |
| Tìm | `search` | |
| Từ đầu | `rotate-ccw` | |
<!-- ui_parity:icons:end -->

## Luật chữ

Máy kiểm trong mã nguồn giao diện (web `ui/src`, native `.../ui/`, bỏ thư viện mẫu và chữ giả); chỗ trích sách thật không bị sửa.

1. **Dấu thanh kiểu cũ**: hoà, khoá, xoá, loá, thuý, tuỳ (không hòa, khóa, xóa, tùy...). "quý" giữ nguyên. Máy báo `òa/óa/ỏa/õa/ọa`, `òe/óe/...`, `ùy/úy/...`.
2. **Không `…` hay `...` ở cuối nhãn, trạng thái, nút, gợi ý ô nhập**: "Đang gửi", "Chia sẻ", "Lưu thành". `…` chỉ còn là hình nút "Thêm tuỳ chọn".
3. **Không `:` cuối nhãn** khi giá trị nằm ở thành phần riêng; `:` chỉ nằm giữa câu chạy. Máy chỉ nhắc (nhẹ), chưa đỏ.
4. **Viết hoa đầu nhãn** đứng riêng ("Đang phát"); mảnh dán sau tên bằng " · " cũng viết hoa; tên màn giữa câu giữ hoa ("Mở Cài đặt").
5. **Cùng việc, cùng chữ**: chữ web là chuẩn, trừ khi chữ native rõ ràng hơn theo DESIGN (nhãn 1-4 chữ, giản dị, gọi "bạn") thì đổi cả web.

"""


def render_doc(current: str | None) -> str:
    body = render_body()
    if current and BEGIN in current and END in current:
        head = current[:current.index(BEGIN)]
        tail = current[current.index(END) + len(END):].lstrip("\n")
        return head + body + (("\n" + tail) if tail else "")
    return HEAD + body


def main(argv: list[str]) -> int:
    if "--diff" in argv:  # in lệch cặp màn / icon / chữ, không ghi gì; `--diff ID` chỉ một cặp
        web, native = web_scan(), native_scan()
        only = [a for a in argv if a != "--diff"]
        for line in hard_checks(web, native):
            if not only or line.startswith(f"[{only[0]}]") or line.startswith(("[icon]", "[chữ]")):
                print(line)
        return 0
    current = DOC.read_bytes().decode("utf-8") if DOC.is_file() else None
    text = render_doc(current)
    if "--check" in argv:
        problems = [] if current == text else [f"{DOC} không còn khớp mã nguồn - chạy scripts/ui_parity.py"]
        problems += hard_checks(web_scan(), native_scan())
        for line in problems:
            print(line, file=sys.stderr)
        return 1 if problems else 0
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_bytes(text.encode("utf-8"))  # LF
    print(f"đã ghi {DOC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
