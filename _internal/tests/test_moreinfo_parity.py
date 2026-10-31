"""Lời giải thích gập sau dấu "?" (MoreInfo) giống từng chữ ở web, Qt và điện thoại, màn nào có ở cả hai nền thì có ở cả hai.

Ba phía, đọc nguồn, không chạy app:
  - web: `<MoreInfo label="...">...</MoreInfo>` trong ui/src (nhãn mặc định đọc từ shared/SettingsNav.tsx);
  - Qt: khối `MoreInfo { label: ...; <chữ> }` trong desktop_qt/qml (nhãn mặc định đọc từ MoreInfo.qml);
  - điện thoại: lời gọi `MoreInfo("nhãn", chữ, "tag")` của ui/components/ListParts.kt.
Chữ được đọc ở chỗ ĐỊNH NGHĨA, không ở chỗ nhắc tên: `{MY_MUSIC_HELP}`, `Logic.pauseWhy(...)`, `WorkText.VOICE_NARRATOR_MORE`, `KEY_HELP[...]` đều
lần về hằng số / hàm của nền ấy và lấy các chuỗi trong đó. Hai phía "giống" khi mọi đoạn chữ của phía này nằm trong chữ của phía kia (và ngược lại).

BẢNG dưới ghép từng MoreInfo của web với Qt và điện thoại. Phía nào không có thì phải ghi lý do (màn chỉ có ở một nền, hay nền ấy chưa làm).
MoreInfo mới ở bất kỳ nền nào mà chưa có trong bảng làm test đỏ: phải nghĩ xem nền kia có màn ấy không.
"""
from __future__ import annotations

import functools
import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "ui" / "src"
QML = ROOT / "desktop_qt" / "qml"
PHONE = ROOT / "mobile" / "android" / "app" / "src" / "main" / "java" / "vn" / "abook" / "player"
PHONE_UI = PHONE / "ui"


# ---- đọc nguồn: chuỗi, ngoặc, chú thích ------------------------------------------------------------------------------------------------------

QUOTES = "\"'`"
OPEN = {"(": ")", "[": "]", "{": "}"}


def skip_string(text: str, i: int) -> int:
    """`text[i]` là dấu mở chuỗi; trả về chỉ số ngay sau dấu đóng (chuỗi ba dấu kép của Kotlin cũng được)."""
    quote = text[i]
    if quote == '"' and text.startswith('"""', i):
        end = text.find('"""', i + 3)
        return len(text) if end < 0 else end + 3
    j = i + 1
    while j < len(text) and text[j] != quote:
        j += 2 if text[j] == "\\" else 1
    return j + 1


def match_close(text: str, i: int) -> int:
    """`text[i]` là ( [ { ; trả về chỉ số của dấu đóng tương ứng, bỏ qua chuỗi."""
    depth = 0
    j = i
    while j < len(text):
        char = text[j]
        if char in QUOTES:
            j = skip_string(text, j)
            continue
        if char in OPEN:
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    raise ValueError(f"không có dấu đóng cho {text[i:i + 40]!r}")


def strip_comments(text: str) -> str:
    """Bỏ `// ...` và `/* ... */` ngoài chuỗi (Kotlin, JS); giữ nguyên số dòng."""
    out: list[str] = []
    i = 0
    while i < len(text):
        char = text[i]
        if char in QUOTES and not (char == "'" and i > 0 and text[i - 1].isalnum()):
            j = skip_string(text, i)
            out.append(text[i:j])
            i = j
        elif text.startswith("//", i):
            end = text.find("\n", i)
            i = len(text) if end < 0 else end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = len(text) if end < 0 else end + 2
            out.append("\n" * text.count("\n", i, end))
            i = end
        else:
            out.append(char)
            i += 1
    return "".join(out)


def literal_pieces(expr: str, templates: bool = False) -> list[str]:
    """Các đoạn chữ của mọi chuỗi trong `expr`; chuỗi có chỗ nội suy (`${...}`, Kotlin `$tên`) bị cắt ở đó."""
    pieces: list[str] = []
    i = 0
    while i < len(expr):
        quote = expr[i]
        if quote not in QUOTES:
            i += 1
            continue
        interpolates = templates or quote == "`"
        j = i + 1
        buf = ""
        while j < len(expr) and expr[j] != quote:
            char = expr[j]
            if char == "\\" and j + 1 < len(expr):
                buf += expr[j + 1]
                j += 2
            elif interpolates and char == "$" and expr.startswith("${", j):
                pieces.append(buf)
                buf = ""
                j = match_close(expr, j + 1) + 1
            elif interpolates and templates and char == "$" and j + 1 < len(expr) and (expr[j + 1].isalpha() or expr[j + 1] == "_"):
                pieces.append(buf)
                buf = ""
                j += 1
                while j < len(expr) and (expr[j].isalnum() or expr[j] == "_"):
                    j += 1
            else:
                buf += char
                j += 1
        pieces.append(buf)
        i = j + 1
    return pieces


def blank_strings(expr: str) -> str:
    """`expr` với ruột mọi chuỗi thay bằng khoảng trắng: tìm tên hằng / hàm mà không vướng chữ trong chuỗi."""
    out: list[str] = []
    i = 0
    while i < len(expr):
        if expr[i] in QUOTES:
            j = skip_string(expr, i)
            out.append(" " * (j - i))
            i = j
        else:
            out.append(expr[i])
            i += 1
    return "".join(out)


def split_args(text: str) -> list[str]:
    """Các đối số ở mức ngoài cùng của một danh sách `a, b, c` (bỏ qua chuỗi và ngoặc lồng)."""
    args: list[str] = []
    depth = 0
    start = 0
    i = 0
    while i < len(text):
        char = text[i]
        if char in QUOTES:
            i = skip_string(text, i)
            continue
        if char in OPEN:
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            args.append(text[start:i].strip())
            start = i + 1
        i += 1
    tail = text[start:].strip()
    if tail:
        args.append(tail)
    return args


def statement_end(text: str, start: int) -> int:
    """Hết câu lệnh bắt đầu ở `start`: `;` ngoài ngoặc, hay xuống dòng khi dòng không còn dở (kiểu JS không chấm phẩy và Kotlin)."""
    depth = 0
    i = start
    while i < len(text):
        char = text[i]
        if char in QUOTES:
            i = skip_string(text, i)
            continue
        if char in OPEN:
            depth += 1
        elif char in ")]}":
            if depth == 0:
                return i
            depth -= 1
        elif char == ";" and depth == 0:
            return i
        elif char == "\n" and depth == 0:
            before = text[start:i].rstrip()
            after = text[i:].lstrip()
            if before and before[-1] not in "+-*/=?:,&|" and not (after[:1] in ("+", "?", ":", ".", "&", "|") and not after.startswith("//")):
                return i
        i += 1
    return len(text)


# ---- tra định nghĩa: hằng số và hàm theo tên ---------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Dialect:
    name: str
    glob: tuple[tuple[Path, str], ...]   # (thư mục, mẫu file)
    skip: tuple[str, ...]                # đoạn tên file bị loại (test)
    const: str                           # mẫu chữ khai báo hằng với {n} là tên
    func: str
    templates: bool                      # `$tên` trong chuỗi là nội suy (Kotlin)


TS = Dialect("ts", ((WEB, "**/*.ts"), (WEB, "**/*.tsx")), (".test.", ".dom.test."), r"\b(?:const|let|var)\s+{n}\b[^=\n;(]*=(?!=)", r"\bfunction\s+{n}\s*[<(]", False)
JS = Dialect("js", ((QML, "*.js"),), (), r"\b(?:const|let|var)\s+{n}\b\s*=(?!=)", r"\bfunction\s+{n}\s*\(", False)
KT = Dialect("kt", ((PHONE, "**/*.kt"),), (), r"\bval\s+{n}\b[^=\n]*=(?!=)", r"\bfun\s+(?:<[^>]+>\s*)?(?:\w+\.)?{n}\s*\(", True)


@functools.lru_cache(maxsize=None)
def corpus(dialect: Dialect) -> tuple[tuple[str, str], ...]:
    files = []
    for base, pattern in dialect.glob:
        for path in sorted(base.glob(pattern)):
            if "node_modules" in path.parts or any(mark in path.name for mark in dialect.skip):
                continue
            files.append((path.name, strip_comments(path.read_text(encoding="utf-8"))))
    return tuple(files)


@functools.lru_cache(maxsize=None)
def definitions(dialect: Dialect, name: str) -> tuple[str, ...]:
    """Thân của mọi hằng / hàm tên `name` trong nền ấy."""
    found: list[str] = []
    const = re.compile(dialect.const.format(n=re.escape(name)))
    func = re.compile(dialect.func.format(n=re.escape(name)))
    for _file, text in corpus(dialect):
        if name not in text:
            continue
        for match in const.finditer(text):
            found.append(text[match.end():statement_end(text, match.end())])
        for match in func.finditer(text):
            open_paren = text.index("(", match.start() + len("function") if dialect.name != "kt" else match.start())
            close = match_close(text, open_paren)
            rest = text[close + 1:]
            stripped = rest.lstrip()
            offset = close + 1 + (len(rest) - len(stripped))
            typed = re.match(r":\s*[\w<>?.,\[\] ]+?(?=\s*[={])", stripped)
            if typed:
                offset += typed.end()
                stripped = text[offset:].lstrip()
                offset = len(text) - len(stripped)
            if stripped.startswith("="):
                found.append(text[offset + 1:statement_end(text, offset + 1)])
            elif stripped.startswith("{"):
                found.append(text[offset:match_close(text, offset) + 1])
            else:  # chữ ký TS có kiểu trả về phức tạp: thân là khối `{` đầu tiên sau chữ ký
                brace = text.find("{", offset)
                found.append(text[brace:match_close(text, brace) + 1] if brace >= 0 else "")
    return tuple(found)


def make_resolver(dialect: Dialect):
    """`resolve(tên)` -> các đoạn chữ trong định nghĩa; trong thân hàm chỉ lần tiếp các HẰNG (không lần hàm gọi hàm)."""
    referenced: dict[str, list[tuple[str, ...]]] = {}

    def resolve(name: str, depth: int = 0) -> list[str]:
        out: list[str] = []
        bodies = definitions(dialect, name)
        if bodies:
            referenced[name] = [tuple(piece_text(body, dialect, resolve, depth + 1)) for body in bodies]
        for body in bodies:
            out.extend(piece_text(body, dialect, resolve, depth + 1))
        return out

    resolve.referenced = referenced  # type: ignore[attr-defined]
    return resolve


def piece_text(expr: str, dialect: Dialect, resolve, depth: int = 0) -> list[str]:
    """Các đoạn chữ của một biểu thức: chuỗi trong nó, cộng chuỗi trong hằng / hàm mà nó nhắc tên."""
    pieces = literal_pieces(expr, dialect.templates)
    if depth > 2:
        return pieces
    code = blank_strings(expr)
    for match in re.finditer(r"\b([A-Z][A-Z0-9_]{3,})\b|\b([A-Za-z_]\w*)\s*\(", code):
        if match.group(1):
            pieces.extend(resolve(match.group(1), depth))
        elif depth == 0:
            pieces.extend(resolve(match.group(2), depth))
    return pieces


# ---- đọc MoreInfo của từng nền -----------------------------------------------------------------------------------------------------------------

@dataclass
class Info:
    file: str
    labels: list[str]
    pieces: list[str]
    tag: str = ""

    @property
    def label(self) -> str:
        return self.labels[0]


def default_label_web() -> str:
    found = re.search(r"function MoreInfo\(\{[^}]*?label\s*=\s*\"([^\"]+)\"", (WEB / "shared" / "SettingsNav.tsx").read_text(encoding="utf-8"))
    assert found, "SettingsNav.tsx: không thấy nhãn mặc định của MoreInfo"
    return found.group(1)


def default_label_qt() -> str:
    found = re.search(r"property string label:\s*\"([^\"]+)\"", (QML / "MoreInfo.qml").read_text(encoding="utf-8"))
    assert found, "MoreInfo.qml: không thấy nhãn mặc định"
    return found.group(1)


def web_pieces(body: str, resolve) -> list[str]:
    """Chữ trong thân `<MoreInfo>`: đoạn chữ JSX trần, và chuỗi / hằng / hàm trong mỗi `{...}`."""
    out: list[str] = []
    text = ""
    i = 0
    while i < len(body):
        char = body[i]
        if char == "{":
            j = match_close(body, i)
            if text.strip():
                out.append(text)
            text = ""
            expr = body[i + 1:j]
            if not expr.strip().startswith("/*"):
                out.extend(piece_text(expr, TS, resolve))
            i = j + 1
        elif char == "<":
            if text.strip():
                out.append(text)
            text = ""
            i = body.index(">", i) + 1
        else:
            text += char
            i += 1
    if text.strip():
        out.append(text)
    return out


def web_infos(files: dict[str, str], resolve, default: str) -> list[Info]:
    """Mọi `<MoreInfo>` trong các file (tên tương đối ui/src -> nội dung)."""
    infos: list[Info] = []
    for name, text in files.items():
        for match in re.finditer(r"<MoreInfo\b", text):
            i = match.end()
            while text[i] != ">":  # hết thẻ mở, bỏ qua chuỗi và {...} trong thuộc tính
                if text[i] in QUOTES:
                    i = skip_string(text, i)
                elif text[i] == "{":
                    i = match_close(text, i) + 1
                else:
                    i += 1
            opening = text[match.end():i]
            end = text.index("</MoreInfo>", i)
            label = re.search(r"\blabel=\"([^\"]+)\"", opening)
            infos.append(Info(name, [label.group(1) if label else default], web_pieces(text[i + 1:end], resolve)))
    return infos


def split_depth0(body: str) -> tuple[str, list[str]]:
    """Khối QML: phần ở mức ngoài cùng (thuộc tính của chính nó) và ruột các khối con."""
    top: list[str] = []
    nested: list[str] = []
    i = 0
    while i < len(body):
        char = body[i]
        if char in QUOTES:
            j = skip_string(body, i)
            top.append(body[i:j])
            i = j
        elif char == "{":
            j = match_close(body, i)
            nested.append(body[i + 1:j])
            i = j + 1
        else:
            top.append(char)
            i += 1
    return "".join(top), nested


def qt_infos(files: dict[str, str], resolve, default: str) -> list[Info]:
    """Mọi khối `MoreInfo { ... }` trong các file QML (tên file -> nội dung)."""
    infos: list[Info] = []
    for name, text in files.items():
        text = strip_comments(text)
        for match in re.finditer(r"(?<![\w\".])MoreInfo\s*\{", text):
            start = match.end() - 1
            body = text[start + 1:match_close(text, start)]
            top, nested = split_depth0(body)
            found = re.search(r"\blabel\s*:\s*([^\n;]+)", top)
            labels = [piece for piece in literal_pieces(found.group(1)) if piece] if found else [default]
            pieces = [p for block in nested for p in piece_text(block, JS, resolve)]
            infos.append(Info(name, labels or [default], pieces))
    return infos


def phone_infos(files: dict[str, str], resolve) -> list[Info]:
    """Mọi lời gọi `MoreInfo("nhãn", chữ, "tag")` trong các file Kotlin (tên tương đối ui/ -> nội dung)."""
    infos: list[Info] = []
    for name, text in files.items():
        text = strip_comments(text)
        for match in re.finditer(r"\b(?:[A-Za-z_]\w*\.)*MoreInfo\(", text):
            if text[max(0, match.start() - 4):match.start()] == "fun ":
                continue
            open_paren = match.end() - 1
            args = split_args(text[open_paren + 1:match_close(text, open_paren)])
            assert len(args) >= 3, f"{name}: MoreInfo cần nhãn, chữ, tag - gặp {args}"
            label = "".join(piece_text(args[0], KT, resolve))
            tag = "".join(literal_pieces(args[2], True))
            infos.append(Info(name, [label], piece_text(args[1], KT, resolve), tag))
    return infos


# ---- đọc thật từ cây ------------------------------------------------------------------------------------------------------------------------------

def read_tree(base: Path, patterns: tuple[str, ...], skip: tuple[str, ...] = ()) -> dict[str, str]:
    files: dict[str, str] = {}
    for pattern in patterns:
        for path in sorted(base.glob(pattern)):
            if "node_modules" in path.parts or any(mark in path.name for mark in skip):
                continue
            files[path.relative_to(base).as_posix()] = path.read_text(encoding="utf-8")
    return files


@dataclass
class Tree:
    web: list[Info]
    qt: list[Info]
    phone: list[Info]
    resolvers: list = field(default_factory=list)


@functools.lru_cache(maxsize=1)
def real_tree() -> Tree:
    ts, js, kt = make_resolver(TS), make_resolver(JS), make_resolver(KT)
    web = web_infos(read_tree(WEB, ("**/*.tsx",), (".test.",)), ts, default_label_web())
    qt = qt_infos(read_tree(QML, ("*.qml",)), js, default_label_qt())
    phone = phone_infos(read_tree(PHONE_UI, ("**/*.kt",)), kt)
    return Tree(web, qt, phone, [ts, js, kt])


# ---- so chữ ----------------------------------------------------------------------------------------------------------------------------------------------

def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def significant(pieces: list[str]) -> list[str]:
    """Đoạn chữ đủ dài để nói điều gì: có từ hai chữ trở lên (bỏ tên khoá / nhãn đối tượng, dấu câu đầu cuối và đoạn nội suy)."""
    trimmed = (norm(p).strip(" .,;:") for p in pieces)
    return [n for n in trimmed if len(re.findall(r"\w", n)) >= 6 and re.search(r"\s", n)]


def missing_from(source: list[str], target: list[str], allowed: tuple[str, ...] = ()) -> list[str]:
    """Đoạn chữ của `source` không nằm trong chữ của `target` (trừ đoạn có một mẩu trong `allowed`)."""
    joined = norm(" ".join(significant(target)))
    return [piece for piece in significant(source) if piece not in joined and not any(mark in piece for mark in allowed)]


@dataclass(frozen=True)
class Row:
    """Một MoreInfo của web và chỗ của nó ở Qt / điện thoại. Phía nào `None` thì `why_*` giải thích."""
    id: str
    web: tuple[str, str] | None                # (file dưới ui/src, nhãn)
    qt: tuple[tuple[str, str], ...] = ()       # (file QML, nhãn)
    phone: tuple[str, str] | None = None       # (file dưới ui/, tag)
    why_qt: str = ""
    why_phone: str = ""
    qt_text: str = "same"                      # "same" | "label": chữ là danh sách động, chỉ kiểm nhãn
    phone_text: str = "same"                   # "same" | "label" | "core"
    core: tuple[str, ...] = ()                 # phone_text == "core": các đoạn hai phía đều phải có
    web_not_on_phone: tuple[str, ...] = ()     # đoạn chữ web mà điện thoại có lý do không có (ghi ở why_phone)
    qt_extra_ok: bool = False                  # Qt có thêm chữ có lý do (một khối gánh hai lời của web, hay hàm dựng HTML của địa chỉ): chỉ đòi chữ web nằm trong Qt


ROWS: tuple[Row, ...] = (
    Row("own-diagnostics", ("desktop/OwnDiagnostics.tsx", "Tìm hiểu thêm"), (("AdvancedDiagnostics.qml", "Tìm hiểu thêm"),),
        ("screens/SettingsAdvanced.kt", "logs_more"), phone_text="core", core=("tự che khoá, mã ghép, đường dẫn và IP nhận ra được.",),
        why_phone="nhật ký điện thoại có thêm tên sách và việc thiết bị đã ghép đọc được khi bật Kết nối Wi-Fi, nên câu dài hơn; phần quyền riêng tư giống từng chữ"),
    Row("phone-sync-code", ("desktop/PhoneSync.tsx", "Cách dùng mã"), (("PhoneSyncPairing.qml", "Cách dùng mã"),), None, qt_extra_ok=True,
        why_phone="phía máy tính của cuộc ghép; điện thoại có 'Cách lấy mã' (devices/PairScreen.kt) nói cho phía của nó"),
    Row("my-music", ("listen/MyMusic.tsx", "Nhạc riêng"), (("MyMusicSettings.qml", "Nhạc riêng"),), ("voice/MyMusicScreen.kt", "music_help")),
    Row("read-aloud-storage", ("listen/ReadAloudStorage.tsx", "Tìm hiểu thêm"), (("AdvancedStorage.qml", "Tìm hiểu thêm"),), ("screens/SettingsAdvanced.kt", "cache_more")),
    Row("provider-key", ("listen/VoiceSettings.tsx", "Nhận khoá"), (("ProviderKey.qml", "Nhận khoá"),), ("voice/VoiceSheets.kt", "key_help")),
    Row("keys-note", ("listen/VoiceSettings.tsx", "Tìm hiểu thêm"), (("SettingsVoice.qml", "Tìm hiểu thêm"),), ("voice/KeysScreen.kt", "keys_more")),
    Row("wishes", ("listen/WishesDialog.tsx", "Tìm hiểu thêm"), (), None,
        why_qt="hộp 'Việc chờ gửi / Việc chờ Studio' chưa có ở Qt", why_phone="điện thoại chưa có hộp 'Việc chờ gửi'; hàng trạng thái gửi ở Sửa sách (editbook/SyncText.kt) có nút Gửi nên nói khác"),
    Row("diagnostics-errors", ("shared/DiagnosticsView.tsx", "Chi tiết kỹ thuật"), (("PhoneDiagnostics.qml", "Chi tiết kỹ thuật"),), None, qt_text="label",
        why_phone="chẩn đoán điện thoại của máy tính; điện thoại xem nhật ký Studio có công tắc 'Chi tiết kỹ thuật' (studio/StudioLog.kt), không phải lời gập"),
    Row("music-module", ("studio/MusicModuleNotice.tsx", "Phân tích nhạc"), (("MyMusicModule.qml", "Phân tích nhạc"), ("EditBookMyMusic.qml", "Phân tích nhạc")), None,
        why_phone="thẻ mô-đun 'Phân tích nhạc' chưa có giao diện ở điện thoại (lõi LocalStudio.kt có, chưa có màn)"),
    Row("studio-my-music", ("studio/MusicTab.tsx", "Nhạc riêng"), (("StudioMyMusic.qml", "Nhạc riêng"), ("EditBookMyMusic.qml", "Nhạc riêng")), ("music/MusicPanel.kt", "music_help")),
    Row("first-person-guess", ("studio/NewProjectScreen.tsx", "Máy đoán"), (("NewVoice.qml", "Máy đoán"),), ("studio/StudioNewScreen.kt", "studio_new_guess")),
    Row("pause-why", ("studio/NewProjectScreen.tsx", "Vì sao?"), (("NewStartNotes.qml", "Vì sao?"),), ("studio/StudioNewScreen.kt", "studio_new_pause_why"),
        web_not_on_phone=("Thời gian tham khảo",), why_phone="điện thoại chưa có số ước thời gian phân tích khi tạo sách, nên không có câu 'Thời gian tham khảo'"),
    Row("phone-edits", ("studio/PhoneEdits.tsx", "Đã áp dụng"), (("PhoneEdits.qml", "Đã áp dụng"),), None,
        why_phone="máy tính duyệt thay đổi do điện thoại gửi tới; điện thoại là phía gửi"),
    Row("precast-free", ("studio/PrecastReview.tsx", "Khi áp dụng"), (("PrecastReview.qml", "Khi áp dụng"),), ("studio/PrecastScreen.kt", "studio_precast_when")),
    Row("battery", ("studio/ProjectScreen.tsx", "Dùng pin"), (("ProjectScreen.qml", "Dùng pin"),), ("studio/StudioProjectScreen.kt", "studio_battery_info"),
        web_not_on_phone=("hoặc đổi ở Cài đặt › Studio",), why_phone="điện thoại luôn là máy từ xa của Studio, không có Cài đặt › Studio để đổi"),
    Row("retake-chapter", ("studio/ProjectScreen.tsx", "Thu lại chương"), (("ProjectScreen.qml", "Thu lại chương"),), None,
        why_phone="điện thoại chưa có việc 'Thu lại cả chương' ở tab Chương"),
    Row("redo-chapters", ("studio/ReviewQueue.tsx", "Tìm hiểu thêm"), (("ReviewQueue.qml", "Tìm hiểu thêm"),), ("studio/ReviewTab.kt", "studio_review_redo_more")),
    Row("script-keys", ("studio/ScriptTab.tsx", "Phím tắt"), (("ScriptTab.qml", "Phím tắt"),), None,
        why_phone="phím tắt bàn phím; điện thoại không có"),
    Row("template-bar", ("studio/TemplateBar.tsx", "Tìm hiểu thêm"), (("NewTemplateBar.qml", "Tìm hiểu thêm"),), None,
        why_phone="điện thoại chưa có mẫu dự án khi tạo sách"),
    Row("voice-narrator", ("studio/VoicePicker.tsx", "Tìm hiểu thêm"), (("CastVoice.qml", "Tìm hiểu thêm"),), ("studio/CastTab.kt", "studio_voice_narrator_more"), qt_extra_ok=True),
    Row("voice-shared", ("studio/VoicePicker.tsx", "Dùng chung giọng"), (("CastVoice.qml", "Dùng chung giọng"),), ("studio/CastTab.kt", "studio_voice_shared_more"), qt_extra_ok=True),
    Row("volume-split", ("studio/VolumeSplit.tsx", "Tìm hiểu thêm"), (("NewVolumes.qml", "Tìm hiểu thêm"),), None,
        why_phone="điện thoại chưa có việc chia sách thành nhiều tập khi tạo sách"),
    # Chỉ điện thoại: ghép nối với máy tính (web không có màn này; phía máy tính của nó là 'Cách dùng mã' ở trên).
    Row("pair-code", None, (), ("devices/PairScreen.kt", "pair_code_help"), why_qt="màn Nối máy tính chỉ có ở điện thoại", why_phone="chỉ điện thoại"),
    Row("pair-away", None, (), ("devices/PairScreen.kt", "pair_away_help"), why_qt="màn Nối máy tính chỉ có ở điện thoại", why_phone="chỉ điện thoại"),
    Row("pair-bluetooth", None, (), ("devices/PairScreen.kt", "bluetooth_reason"), why_qt="quyền Bluetooth chỉ có ở Android", why_phone="chỉ điện thoại"),
)


def find(infos: list[Info], file: str, key: str, by_tag: bool = False) -> Info | None:
    for info in infos:
        if info.file == file and ((info.tag == key) if by_tag else (key in info.labels)):
            return info
    return None


def problems(row: Row, tree: Tree) -> list[str]:
    """Mọi chỗ MoreInfo của `row` lệch giữa các nền; rỗng là khớp."""
    out: list[str] = []
    web = find(tree.web, *row.web) if row.web else None
    if row.web and web is None:
        out.append(f"{row.id}: web {row.web} không còn trong code")
    if row.web and not row.qt and not row.why_qt:
        out.append(f"{row.id}: Qt không có mà không ghi lý do")
    if not row.phone and not row.why_phone:
        out.append(f"{row.id}: điện thoại không có mà không ghi lý do")
    if row.web and row.phone and row.why_phone and row.phone_text == "same" and not row.web_not_on_phone:
        out.append(f"{row.id}: why_phone chỉ dùng khi chữ điện thoại khác web")
    for file, label in row.qt:
        qt = find(tree.qt, file, label)
        if qt is None:
            out.append(f"{row.id}: Qt {file} thiếu MoreInfo \"{label}\"")
            continue
        if web is None or row.qt_text == "label":
            continue
        gone = missing_from(web.pieces, qt.pieces)
        extra = [] if row.qt_extra_ok else missing_from(qt.pieces, web.pieces)
        out += [f"{row.id}: chữ web không có ở {file}: {piece!r}" for piece in gone]
        out += [f"{row.id}: chữ {file} không có ở web: {piece!r}" for piece in extra]
    if row.phone:
        file, tag = row.phone
        phone = find(tree.phone, file, tag, by_tag=True)
        if phone is None:
            out.append(f"{row.id}: điện thoại {file} thiếu MoreInfo tag \"{tag}\"")
        elif web is not None:
            if phone.label != web.label:
                out.append(f"{row.id}: nhãn điện thoại \"{phone.label}\" khác web \"{web.label}\"")
            if row.phone_text == "same":
                out += [f"{row.id}: chữ web không có ở điện thoại: {piece!r}" for piece in missing_from(web.pieces, phone.pieces, row.web_not_on_phone)]
                out += [f"{row.id}: chữ điện thoại không có ở web: {piece!r}" for piece in missing_from(phone.pieces, web.pieces)]
            elif row.phone_text == "core":
                for piece in row.core:
                    for side, where in ((web, "web"), (phone, "điện thoại")):
                        if piece not in norm(" ".join(side.pieces)):
                            out.append(f"{row.id}: {where} thiếu đoạn chung {piece!r}")
    return out


# ---- test ------------------------------------------------------------------------------------------------------------------------------------------------

def key_set(infos: list[Info], by_tag: bool = False) -> set[tuple[str, str]]:
    return {(info.file, info.tag) if by_tag else (info.file, label) for info in infos for label in ([info.tag] if by_tag else info.labels)}


def test_the_table_agrees_with_every_platform():
    tree = real_tree()
    found = [line for row in ROWS for line in problems(row, tree)]
    assert not found, "\n".join(found)


def test_every_more_info_in_code_has_a_row():
    tree = real_tree()
    web_keys = {row.web for row in ROWS if row.web}
    qt_keys = {key for row in ROWS for key in row.qt}
    phone_keys = {row.phone for row in ROWS if row.phone}
    assert key_set(tree.web) == web_keys, f"web: {key_set(tree.web) ^ web_keys}"
    assert key_set(tree.qt) == qt_keys, f"Qt: {key_set(tree.qt) ^ qt_keys}"
    assert key_set(tree.phone, by_tag=True) == phone_keys, f"điện thoại: {key_set(tree.phone, by_tag=True) ^ phone_keys}"


def test_the_readers_found_the_real_screens():
    # Phép đọc hỏng im lặng (không thấy gì) sẽ làm các test trên xanh giả.
    tree = real_tree()
    assert len(tree.web) >= 20 and len(tree.qt) >= 20 and len(tree.phone) >= 10, (len(tree.web), len(tree.qt), len(tree.phone))
    assert all(info.pieces for info in tree.web if info.file != "shared/DiagnosticsView.tsx" and info.file != "studio/ScriptTab.tsx"), "một MoreInfo web không đọc ra chữ"
    assert all(info.pieces for info in tree.phone), "một MoreInfo điện thoại không đọc ra chữ"
    assert default_label_web() == default_label_qt() == "Tìm hiểu thêm"


def test_one_text_has_one_source_per_platform():
    # "Không chép tay lệch": hằng số cùng tên định nghĩa ở nhiều file của một nền thì phải giống nhau (Qt: MY_MUSIC_HELP ở hai file .js).
    tree = real_tree()
    for resolve in tree.resolvers:
        for name, versions in resolve.referenced.items():
            if not re.fullmatch(r"[A-Z][A-Z0-9_]+", name):
                continue  # hàm trùng tên ở file khác nhau (formatNumber...) là việc khác nhau; hằng số thì phải một chữ
            assert len({tuple(norm(p) for p in v) for v in versions}) <= 1, f"{name} định nghĩa khác nhau ở các file của cùng một nền"


def test_rows_with_no_counterpart_say_why():
    for row in ROWS:
        assert row.web or row.phone, row.id
        if row.web and not row.qt:
            assert row.why_qt, row.id
        if not row.phone:
            assert row.why_phone, row.id


# ---- kiểm lực: phép so phải BẮT được lệch, không chỉ xác nhận đúng -----------------------------------------------------------------------------

def fake_tree(web_ts: str, qml: str, kotlin: str) -> Tree:
    ts, js, kt = make_resolver(TS), make_resolver(JS), make_resolver(KT)
    return Tree(
        web_infos({"a/A.tsx": web_ts}, ts, "Tìm hiểu thêm"),
        qt_infos({"A.qml": qml}, js, "Tìm hiểu thêm"),
        phone_infos({"s/A.kt": kotlin}, kt),
    )


FAKE_ROW = Row("fake", ("a/A.tsx", "Nhạc riêng"), (("A.qml", "Nhạc riêng"),), ("s/A.kt", "tag_a"))
WEB_OK = '<MoreInfo label="Nhạc riêng">Nhạc được chép vào kho máy này; chọn cho từng đoạn.</MoreInfo>'
QML_OK = 'MoreInfo { label: "Nhạc riêng"; HintText { text: "Nhạc được chép vào kho máy này; chọn cho từng đoạn." } }'
KT_OK = 'MoreInfo("Nhạc riêng", "Nhạc được chép vào kho máy này; chọn cho từng đoạn.", "tag_a")'


def test_a_matching_fake_has_no_problems():
    assert problems(FAKE_ROW, fake_tree(WEB_OK, QML_OK, KT_OK)) == []


def test_a_missing_phone_item_is_caught():
    found = problems(FAKE_ROW, fake_tree(WEB_OK, QML_OK, "val nothing = 1"))
    assert any("thiếu MoreInfo" in line and "điện thoại" in line for line in found), found


def test_a_missing_qt_item_is_caught():
    found = problems(FAKE_ROW, fake_tree(WEB_OK, "Item { }", KT_OK))
    assert any("Qt" in line and "thiếu MoreInfo" in line for line in found), found


def test_a_drifted_text_is_caught_on_both_sides():
    drifted = KT_OK.replace("kho máy này", "kho máy kia")
    found = problems(FAKE_ROW, fake_tree(WEB_OK, QML_OK, drifted))
    assert any("web không có ở điện thoại" in line for line in found) and any("điện thoại không có ở web" in line for line in found), found
    found = problems(FAKE_ROW, fake_tree(WEB_OK, QML_OK.replace("từng đoạn", "mỗi đoạn"), KT_OK))
    assert any("Qt" in line or "A.qml" in line for line in found), found


def test_a_drifted_label_is_caught():
    found = problems(FAKE_ROW, fake_tree(WEB_OK, QML_OK, KT_OK.replace('"Nhạc riêng"', '"Nhạc của tôi"')))
    assert any("nhãn điện thoại" in line for line in found), found


def test_an_unmapped_more_info_is_visible_to_the_key_check():
    tree = fake_tree(WEB_OK + '<MoreInfo label="Mới">Một lời giải thích mới.</MoreInfo>', QML_OK, KT_OK)
    assert key_set(tree.web) == {("a/A.tsx", "Nhạc riêng"), ("a/A.tsx", "Mới")}
    assert key_set(tree.web) != {FAKE_ROW.web}


def test_text_behind_a_constant_or_a_function_is_read_at_its_definition(tmp_path: Path):
    # Chữ nằm ở hằng / hàm, không ở chỗ nhắc tên: đổi chữ ở định nghĩa thì so chữ phải đổi theo.
    ts, kt = make_resolver(TS), make_resolver(KT)
    web = web_infos({"a/A.tsx": '<MoreInfo label="X">{FAKE_HELP_FOR_TEST}</MoreInfo>'}, lambda name, depth=0: ["Lời ở hằng số thật"] if name == "FAKE_HELP_FOR_TEST" else [], "Tìm hiểu thêm")
    assert web[0].pieces == ["Lời ở hằng số thật"]
    phone = phone_infos({"s/A.kt": 'MoreInfo("X", Fake.helpFor(book), "t")'}, lambda name, depth=0: ["Lời từ hàm"] if name == "helpFor" else [])
    assert phone[0].pieces == ["Lời từ hàm"] and phone[0].tag == "t"
    assert ts is not kt


def test_template_strings_are_split_at_interpolation():
    assert significant(literal_pieces("`${a}/${b} chương đầu có lời kể`")) == ["chương đầu có lời kể"]
    assert significant(literal_pieces('"Tự gửi khi $where trả lời lại; bấm ${x} để gửi ngay"', templates=True)) == ["Tự gửi khi", "trả lời lại; bấm", "để gửi ngay"]


def test_comments_and_declarations_are_not_taken_for_calls():
    kotlin = '/** MoreInfo("a", b, "c") trong chú thích */\nfun MoreInfo(label: String, text: String, tag: String) {}\n// MoreInfo("x", "y", "z")\n'
    assert phone_infos({"s/B.kt": kotlin}, make_resolver(KT)) == []
