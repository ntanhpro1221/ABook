"""Máy dò lệch chữ, icon và bo góc giữa web máy tính và bản Qt Quick (chủ sách 26-10: "từng cái chữ, từng cái icon, từng cái bo góc").

Hai phía, đọc nguồn, không chạy app, không mạng:

  - web máy tính: ui/src/desktop, ui/src/listen, ui/src/shared (cùng bộ đọc JSX của scripts/ui_parity.py - import, không chép);
  - Qt: desktop_qt/qml/*.qml. Chữ = giá trị của text / title / subtitle / tip / label(s) / placeholderText / Accessible.name ..., chuỗi
    qsTr(...), và chuỗi thường tiếng Việt ở chỗ khác (thuộc tính riêng, hàm). Cặp nhãn-icon = một đối tượng có cả `icon:` (tên lucide) và
    chữ (Button, MenuRow, NavItem, ControlChip, IconButton với `tip`), hay `Icon { name: ... }` đứng cạnh `Text` trong cùng một khối.
    Nhánh `a ? "x" : "y"` của nhãn và icon cùng điều kiện được ghép theo thứ tự (Phát / Tạm dừng).

Ghép theo màn (bảng MÀN dưới): mỗi màn là vài file QML và vài file / hàm web. Ghi phần SINH TỰ ĐỘNG của docs/UI_PARITY_QT.md (giữa hai dấu
<!-- ui_parity_qt:begin/end -->; phần ngoài dấu là chữ tay, gồm bảng cũ -> mới của các lần sửa):
  a. cùng việc khác chữ; b. cùng nhãn khác icon / cùng icon khác nhãn; c. nhãn chỉ có một bên (theo màn); d. bo góc QML không theo token;
  e. dấu thanh kiểu mới (òa / óa / úy ...) và "…" / "..." cuối nhãn; f. phím tắt trong chú thích khác web.

    python -X utf8 scripts/ui_parity_qt.py          # ghi lại phần sinh tự động của docs/UI_PARITY_QT.md
    python -X utf8 scripts/ui_parity_qt.py --check  # thoát 1 nếu docs/UI_PARITY_QT.md không còn khớp mã nguồn (tests/test_ui_parity_qt.py)
"""
from __future__ import annotations

import fnmatch
import functools
import importlib.util
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _base():
    """scripts/ui_parity.py (bộ đọc JSX, khoá so chữ, tên lucide) - nạp một lần, dùng chung."""
    if "ui_parity" in sys.modules:
        return sys.modules["ui_parity"]
    spec = importlib.util.spec_from_file_location("ui_parity", ROOT / "scripts" / "ui_parity.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["ui_parity"] = module  # @dataclass tra cứu module của lớp qua sys.modules
    spec.loader.exec_module(module)
    return module


up = _base()
# key_loose là hàm thuần, mục a gọi nó cho mỗi cặp (Qt x web): nhớ kết quả, không thì hơn 147 file QML mất vài phút.
up.key_loose = functools.lru_cache(maxsize=None)(up.key_loose)
Item, Pair, Scan = up.Item, up.Pair, up.Scan

WEB = up.WEB
QML = ROOT / "desktop_qt" / "qml"
DOC = ROOT / "docs" / "UI_PARITY_QT.md"
BEGIN = "<!-- ui_parity_qt:begin (SINH TỰ ĐỘNG bởi scripts/ui_parity_qt.py - không sửa tay, chạy lại script) -->"
END = "<!-- ui_parity_qt:end -->"

# Web máy tính: thư mục có giao diện của app Tauri (android/ là giao diện điện thoại cũ; studio/ chỉ nạp từng file có màn Qt, qua bảng MÀN).
WEB_DIRS = ("desktop", "listen", "shared")
# File QML không phải giao diện: kịch bản đo của người làm.
QML_SKIP = {"BenchScenario.qml"}

# Màn: (tên, file QML, nguồn web). Nguồn web = (file, tên hàm / hằng cấp trên cùng) - None là cả file.
SCREENS: list[tuple[str, tuple[str, ...], tuple[tuple[str, tuple[str, ...] | None], ...]]] = [
    ("Khay và cửa sổ mini", ("DesktopTray.qml", "TrayMenuModel.qml", "WindowMode.qml", "MiniPlayer.qml"), ()),
    ("Thư viện", ("Library*.qml", "BookCell.qml", "GeneratedCover.qml", "CoverView.qml"),
     (("listen/LibraryScreen.tsx", None), ("desktop/App.tsx", ("EmptyLibrary", "LibraryRoute", "OpenBookFileButton")),
      ("shared/BookCover.tsx", None))),
    ("Thanh phát", ("PlayerBar.qml", "PlayButton.qml", "SkipButton.qml", "SkipGlyph.qml", "SeekBar.qml", "PlayerNotice.qml"),
     (("listen/PlayerViews.tsx", ("SeekBar", "skipIcon", "Transport", "PlayerBar", "TrackSubtitle", "PlayerAlert", "CompactProgress",
                                  "FadingNotice", "MenuRow", "MoreMenu")),
      ("listen/labels.ts", None))),
    ("Đang nghe", ("NowPlaying.qml", "ControlChip.qml", "ChoiceChip.qml", "SpeedPopover.qml", "SleepPopover.qml", "ChaptersPopover.qml",
                   "ChapterList.qml", "ChapterRow.qml", "ChapterReader.qml", "VolumeControl.qml", "ReadingSuggestions.qml", "PageSwitch.qml", "Popover.qml"),
     (("listen/PlayerViews.tsx", ("NowPlaying", "NowPlayingColumn", "CoverToggle", "BookProgressLine", "AfterTheEnd", "CaughtUpNotice",
                                  "ChapterPanel", "PANELS", "SpeedMenu", "SleepMenu", "SleepPicker", "MenuShell", "MenuNote", "MusicMenu",
                                  "VoiceMenu", "VolumeControl", "SleepRing", "Transport")),
      ("listen/BookScreen.tsx", ("ChapterRow",)), ("listen/labels.ts", None), ("listen/sleep.ts", None))),
    ("Đọc theo", ("ReadAlongView.qml",),
     (("listen/ReadAlongText.tsx", None), ("listen/PlayerViews.tsx", ("ReadAlong",)))),
    ("Trang sách", ("BookPage.qml", "Cast*.qml", "Clip.qml", "History*", "Record*"),
     (("listen/BookScreen.tsx", None), ("listen/labels.ts", None))),
    ("Cài đặt", ("SettingsScreen.qml", "SettingsBody.qml", "Settings*.qml", "Voice*.qml", "VoiceLogic.js", "ProviderKey.qml",
                 "Listen*.qml", "Sleep*.qml", "Look*.qml", "Advanced*.qml", "MyMusic*", "NativeFolders.qml", "ThirdPartyText.qml",
                 "Devices*", "PhoneSync*.qml", "PhoneDiagnostics.qml", "OtherComputers*.qml", "StudioSettings.qml", "StudioRows.qml",
                 "BookTemplates.qml", "SharedReadingsSettings.qml", "NewBookDefaults.qml", "SettingRow.qml", "SettingChoices.qml",
                 "SectionBlock.qml", "DisclosureRow.qml", "MoreInfo.qml", "ChoiceRow.qml", "Select.qml", "ShortcutsDialog.qml", "PlayerKeys.qml"),
     (("desktop/SettingsScreen.tsx", None), ("shared/SettingsNav.tsx", None), ("shared/DisclosureRow.tsx", None),
      ("shared/settingsSummary.ts", None), ("desktop/SleepSchedule.tsx", None), ("listen/VoiceSettings.tsx", None),
      ("listen/VieneuModuleCard.tsx", None), ("listen/VoiceSpeedSetting.tsx", None), ("listen/MyMusic.tsx", None),
      ("listen/Shortcuts.tsx", None), ("listen/ReadAloudStorage.tsx", None), ("desktop/OwnDiagnostics.tsx", None),
      ("desktop/updateCheck.ts", None), ("shared/ThirdPartyList.tsx", None), ("desktop/PhoneSync.tsx", None),
      ("desktop/OtherComputers.tsx", None), ("desktop/BookTemplates.tsx", None), ("studio/StudioSetup.tsx", None),
      ("studio/sharedReadings.tsx", None))),
    ("Thêm sách", ("AddBook.qml", "Import*"),
     (("listen/AddBook.tsx", None), ("listen/importQueue.ts", None), ("listen/textImport.ts", None))),
    ("Sửa sách", ("EditBook*", "CoverSearch.qml", "BookMusicSettings.qml"),
     (("listen/EditBook.tsx", None), ("shared/CoverSearch.tsx", None))),
    ("Thanh bên", ("Sidebar.qml", "NavItem.qml", "ConnectionChip.qml", "ConnectionPopover.qml"),
     (("desktop/Shell.tsx", ("Brand", "NavItem", "TabItem", "Producing", "UpdateNotice", "DesktopSidebar")),)),
    ("Studio dự án", ("ProjectsScreen.qml", "ProjectScreen.qml", "ProjectRow.qml", "ProjectMenu.qml", "StudioMenuRow.qml", "StudioBar.qml",
                      "StatusPill.qml", "OnComputerPill.qml", "StudioChapterRow.qml", "StudioTabs.qml", "TabLabel.qml", "StudioConfirm.qml",
                      "StudioRename.qml", "StudioDialogs.qml", "StudioStore.qml", "StudioLogic.js"),
     (("studio/ProjectsScreen.tsx", None), ("studio/ProjectScreen.tsx", None))),
    ("Studio máy khác", ("StudioScreen.qml", "PeerBar.qml", "EmptyState.qml"),
     (("desktop/PeerBar.tsx", None), ("shared/peerStudio.ts", None), ("desktop/App.tsx", ("PeerTrouble", "StudioClosed")))),
    ("Thanh tiêu đề", ("Main.qml", "TitleBar.qml", "CaptionButton.qml", "CaptionGlyph.qml"),
     (("desktop/Shell.tsx", ("TITLES", "Shell")), ("shared/title.ts", None))),
    ("Chung", ("Button.qml", "IconButton.qml", "MenuRow.qml", "ScreenHeader.qml", "ScreenStack.qml", "Interactive.qml", "Icon.qml",
               "Scrollbar.qml", "SmoothWheel.qml", "Nav.qml", "ClockUser.qml", "Modal.qml", "Api.qml", "Collapse.qml",
               "FormField.qml", "FormLabel.qml", "HintText.qml", "SettingsItem.qml", "Switch.qml", "ScrollEdges.qml", "Toast.qml"),
     (("shared/ScreenHeader.tsx", None), ("shared/ui.tsx", None), ("desktop/App.tsx", ("App",)))),
]

# Thuộc tính QML mang chữ cho người dùng.
TEXT_PROPS = {"text", "title", "subtitle", "tip", "label", "labels", "placeholderText", "Accessible.name", "Accessible.description",
              "ToolTip.text", "description", "hint", "caption", "message", "emptyText", "heading"}
# Thuộc tính / lệnh gọi không bao giờ là chữ cho người dùng.
SKIP_PROPS = {"sequences", "sequence", "shortcut", "source", "objectName", "name", "icon", "kind", "state", "placement", "property",
              "font.family", "id", "key", "mode"}
SKIP_CALLS = ("console.", "Bench.", "Platform.setting", "Platform.setSetting", "Qt.resolvedUrl")
# Chú thích có phím tắt: "Thu nhỏ  (Esc)" -> ("Thu nhỏ", "Esc"). Web ghép bằng withShortcut(label, key) nên chữ và phím đứng riêng.
SHORTCUT = re.compile(r"^(.*?\S)\s+\(((?:Ctrl|Shift|Alt)\+[^()]+|Esc|Space|Enter|Tab|F\d+|[←→↑↓]|[A-Z0-9])\)$")
HEADER_LINE = re.compile(r"(?m)^\s*(?:import|pragma)\b.*$")
TYPE_START = re.compile(r"([A-Z][\w.]*)(?:\s+on\s+[\w.]+)?\s*\{")


@dataclass
class QmlObject:
    type: str
    line: int
    props: dict[str, tuple[str, int]] = field(default_factory=dict)  # tên -> (biểu thức thô, dòng)
    children: list["QmlObject"] = field(default_factory=list)


# ---------------------------------------------------------------------------------------------------------------------------------------
# Bộ đọc QML nhỏ


def statement_end(src: str, i: int) -> int:
    """Hết một biểu thức giá trị QML bắt đầu ở `i`: tới cuối dòng ở mức ngoặc 0, trừ khi dòng sau nối tiếp (`?` `:` `+` `.` `&&` `||`)
    hay dòng này kết thúc bằng toán tử."""
    n = len(src)
    while i < n:
        c = src[i]
        if c in "\"'`":
            i = up.skip_string(src, i)
            continue
        if c == "/" and src[i + 1:i + 2] in ("/", "*"):
            if src[i + 1] == "/":
                j = src.find("\n", i)
                i = n if j < 0 else j
                continue
            i = up.skip_comment(src, i)
            continue
        if c in "([{":
            close = {"(": ")", "[": "]", "{": "}"}[c]
            i = up.skip_balanced(src, i, c, close)
            continue
        if c == ";":
            return i
        if c == "}":
            return i
        if c == "\n":
            before = src[:i].rstrip()
            after = src[i + 1:].lstrip()
            if re.search(r"(?:[?:+\-*/,=]|&&|\|\|)$", before) or re.match(r"(?:[?:+.]|&&|\|\|)(?!\w+\s*:)", after):
                i += 1
                continue
            return i
        i += 1
    return n


def parse_body(src: str, i: int, stop: int, obj: QmlObject) -> None:
    """Thân `{...}` của một đối tượng QML từ `i` tới `stop` (vị trí dấu `}`): thuộc tính trực tiếp và đối tượng con."""
    while i < stop:
        while i < stop and src[i] in " \t\r\n;":
            i += 1
        if i >= stop:
            return
        if src.startswith("//", i) or src.startswith("/*", i):
            i = up.skip_comment(src, i)
            continue
        rest = src[i:i + 200]
        m = re.match(r"(?:(?:readonly|default|required)\s+)*property\s+[\w.<>]+\s+(\w+)\s*(:)?", rest)
        if m:
            i += m.end()
            if not m.group(2):
                continue
            i = value(src, i, stop, obj, m.group(1))
            continue
        m = re.match(r"(?:function\s+\w+\s*\([^)]*\)\s*)\{", rest)
        if m:
            end = up.skip_balanced(src, i + m.end() - 1, "{", "}")
            obj.props.setdefault(f"function@{up.line_of(src, i)}", (src[i:end], up.line_of(src, i)))
            i = end
            continue
        m = re.match(r"enum\s+\w+\s*\{", rest)
        if m:
            i = up.skip_balanced(src, i + m.end() - 1, "{", "}")
            continue
        if re.match(r"signal\b", rest):
            j = src.find("\n", i)
            i = stop if j < 0 else j
            continue
        m = TYPE_START.match(rest)
        if m:
            child = QmlObject(m.group(1), up.line_of(src, i))
            open_at = i + m.end() - 1
            end = up.skip_balanced(src, open_at, "{", "}")
            parse_body(src, open_at + 1, end - 1, child)
            obj.children.append(child)
            i = end
            continue
        m = re.match(r"([\w.]+)\s*:", rest)
        if m:
            i = value(src, i + m.end(), stop, obj, m.group(1))
            continue
        i += 1


def value(src: str, i: int, stop: int, obj: QmlObject, name: str) -> int:
    """Giá trị của thuộc tính `name` bắt đầu ở `i`: đối tượng con (`delegate: Item {...}`), khối JS, hay biểu thức."""
    while i < stop and src[i] in " \t":
        i += 1
    m = TYPE_START.match(src[i:i + 200])
    if m:
        child = QmlObject(m.group(1), up.line_of(src, i))
        open_at = i + m.end() - 1
        end = up.skip_balanced(src, open_at, "{", "}")
        parse_body(src, open_at + 1, end - 1, child)
        child.props.setdefault("@as", (name, child.line))
        obj.children.append(child)
        return end
    end = min(statement_end(src, i), stop)
    obj.props[name] = (src[i:end], up.line_of(src, i))
    # Đối tượng QML lồng trong giá trị (mảng `[ Item {...} ]`, `Component { ... }` trong JS) vẫn là con để ghép icon / chữ
    for cm in TYPE_START.finditer(src, i, end):
        if src[cm.start() - 1:cm.start()].isalnum():
            continue
        child = QmlObject(cm.group(1), up.line_of(src, cm.start()))
        open_at = cm.end() - 1
        cend = up.skip_balanced(src, open_at, "{", "}")
        parse_body(src, open_at + 1, cend - 1, child)
        obj.children.append(child)
    return max(end, i + 1)


def parse_qml(src: str) -> QmlObject:
    root = QmlObject("<file>", 1)
    i = 0
    n = len(src)
    while i < n:
        m = HEADER_LINE.match(src, i)
        if m:
            i = m.end() + 1
            continue
        if src.startswith("//", i) or src.startswith("/*", i):
            i = up.skip_comment(src, i)
            continue
        tm = TYPE_START.match(src, i)
        if tm:
            obj = QmlObject(tm.group(1), up.line_of(src, i))
            open_at = tm.end() - 1
            end = up.skip_balanced(src, open_at, "{", "}")
            parse_body(src, open_at + 1, end - 1, obj)
            root.children.append(obj)
            i = end
            continue
        i += 1
    return root


def walk(obj: QmlObject):
    yield obj
    for child in obj.children:
        yield from walk(child)


# ---------------------------------------------------------------------------------------------------------------------------------------
# Chữ và icon trong biểu thức


_LIT = r"(?:\"(?:[^\"\\\n]|\\.)*\"|'(?:[^'\\\n]|\\.)*')"
_OPERAND = r"(?:[\w.]+(?:\([^()\"'\n]*\))?)"
# "Nghe " + name + " nói" -> "Nghe {} nói": mẫu như `${}` của web, để nhãn ghép ở QML/JS khớp nhãn mẫu bên web
_CHAIN = re.compile(rf"(?:{_LIT}|{_OPERAND})(?:\s*\+\s*(?:{_LIT}|{_OPERAND}))+")


def joined_literals(expr: str) -> list[tuple[int, int, str]]:
    """Chuỗi nối bằng `+` có cả chuỗi lẫn biến: (đầu, cuối, nội dung với `{}` thay mỗi biến)."""
    out = []
    for m in _CHAIN.finditer(expr):
        parts = re.findall(rf"{_LIT}|{_OPERAND}", m.group(0))
        if not any(p[0] in "\"'" for p in parts) or all(p[0] in "\"'" for p in parts):
            continue
        # literal_text bỏ dấu cách hai đầu của từng mảnh; giữ lại để "Nghe " + x + " nói" ra "Nghe {} nói", không "Nghe{}nói"
        text = "".join((" " if p[1:2].isspace() else "") + up.literal_text(p) + (" " if p[-2:-1].isspace() else "")
                       if p[0] in "\"'" else "{}" for p in parts)
        text = re.sub(r"\s+", " ", re.sub(r"(?:\{\})+", "{}", text)).strip()
        out.append((m.start(), m.end(), text))
    return out


def options(expr: str) -> list[str]:
    """Chuỗi trực tiếp của biểu thức (mọi nhánh của `?:`, phần tử mảng), không lấy chuỗi nằm trong lệnh gọi bị bỏ qua.
    Chuỗi nối với biến (`"Nghe " + name + " nói"`) thành một mẫu `Nghe {} nói`."""
    out = []
    chains = joined_literals(expr)
    for start, _, text in chains:
        before = expr[max(0, start - 40):start]
        if not any(re.search(re.escape(call) + r"\w*\($", before.rstrip()) for call in SKIP_CALLS):
            out.append(text)
    for pos, text in up.literals_in(expr):
        if any(start <= pos < end for start, end, _ in chains):
            continue
        before = expr[max(0, pos - 40):pos]
        if any(re.search(re.escape(call) + r"\w*\($", before.rstrip()) for call in SKIP_CALLS):
            continue
        if re.search(r"(?:===|!==|==|!=)\s*$", before) or re.match(r"\s*(?:===|!==|==|!=)", expr[pos + len(text) + 2:]):
            continue  # so sánh trạng thái: Player.sleepKind === "minutes"
        out.append(text)
    return out


def split_shortcut(text: str) -> tuple[str, str]:
    m = SHORTCUT.match(text.strip())
    return (m.group(1), m.group(2)) if m else (text.strip(), "")


_LUCIDE: set[str] | None = None


def lucide_names() -> set[str]:
    """Tên lucide Qt vẽ được: hằng trong LucidePaths.js (ARROW_LEFT -> arrow-left)."""
    global _LUCIDE
    if _LUCIDE is None:
        text = (QML / "LucidePaths.js").read_bytes().decode("utf-8")
        _LUCIDE = {m.group(1).lower().replace("_", "-") for m in re.finditer(r"^var (\w+) =", text, re.M) if not m.group(1).endswith("_FILL")}
    return _LUCIDE


def icon_options(expr: str) -> list[str]:
    names = lucide_names()
    return [t for t in options(expr) if t in names]


def ternary_cond(expr: str) -> str:
    m = re.match(r"\s*([^?\"']+?)\s*\?", expr)
    return re.sub(r"\s+", "", m.group(1)) if m else ""


def pair_up(label_expr: str, icon_expr: str) -> list[tuple[str, str]]:
    """Ghép nhãn với icon: cùng điều kiện `?:` và cùng số nhánh thì theo thứ tự; một icon thì đi với mọi nhãn; không thì nhãn đầu."""
    labels = [split_shortcut(t)[0] for t in options(label_expr) if up.looks_ui(t)]
    icons = icon_options(icon_expr)
    if not labels or not icons:
        return []
    if len(labels) == len(icons) and len(icons) > 1 and ternary_cond(label_expr) and ternary_cond(label_expr) == ternary_cond(icon_expr):
        return list(zip(labels, icons))
    if len(icons) == 1:
        return [(label, icons[0]) for label in labels]
    if len(labels) == 1:
        return [(labels[0], icon) for icon in icons]
    return [(labels[0], icons[0])]


# ---------------------------------------------------------------------------------------------------------------------------------------
# Quét


@dataclass
class QtScan(Scan):
    shortcuts: list[tuple[str, str, str, int]] = field(default_factory=list)  # (nhãn, phím, file, dòng)
    radii: list[tuple[str, int, str]] = field(default_factory=list)            # (file, dòng, biểu thức) không theo token
    spaced: list[tuple[str, str, int]] = field(default_factory=list)           # (chữ, file, dòng): hai dấu cách trước "(phím)"


RADIUS_OK = re.compile(
    r"^(?:Theme\.radius(?:Control|Cover|Sheet)"          # ba vai của DESIGN.md 5.5
    r"|0"                                                 # không bo
    r"|(?:width|height|size|implicitWidth|implicitHeight)\s*/\s*2"  # tròn
    r"|(?:parent|root|\w+)\.(?:radius|ringRadius)"        # lấy lại bo của khung chứa
    r"|(?:Theme\.radius(?:Control|Cover|Sheet)|(?:root|parent)\.(?:radius|ringRadius))\s*\+\s*(?:\d+|root\.ringMargin)"  # vòng đồng tâm ngoài
    r")$")


def radius_ok(expr: str) -> bool:
    """Bo góc hợp lệ: một giá trị của RADIUS_OK, hay `điều kiện ? A : B` mà cả hai nhánh hợp lệ (chọn giữa hai token, khung có / không viền)."""
    expr = expr.strip()
    if RADIUS_OK.match(expr):
        return True
    depth, q = 0, -1
    for i, c in enumerate(expr):
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif depth == 0 and c == "?" and q < 0:
            q = i
        elif depth == 0 and c == ":" and q >= 0:
            return radius_ok(expr[q + 1:i]) and radius_ok(expr[i + 1:])
    return False


def forwarded_icons(trees: dict[str, QmlObject]) -> dict[str, dict[str, str]]:
    """Component -> {thuộc tính: icon}: nút có icon cố định mà chữ lấy từ thuộc tính của chính component (ScreenHeader: IconButton
    `icon: "arrow-left"`, `tip: root.backLabel + " (Esc)"`), để nơi dùng `ScreenHeader { backLabel: "Về Thư viện" }` cũng thành cặp."""
    out: dict[str, dict[str, str]] = defaultdict(dict)
    for name, root in trees.items():
        for obj in walk(root):
            if "icon" not in obj.props:
                continue
            icons = icon_options(obj.props["icon"][0])
            label_expr = obj.props.get("text", obj.props.get("tip", ("", 0)))[0]
            for prop in re.findall(r"\broot\.(\w+)", label_expr):
                if len(icons) == 1 and prop not in ("text", "tip"):
                    out[name][prop] = icons[0]
    return out


def qml_scan_file(path: Path, scan: QtScan, forwards: dict[str, dict[str, str]] | None = None) -> None:
    raw = path.read_bytes().decode("utf-8")
    src = up.blank_comments(raw)
    file = up.rel(path) if path.is_relative_to(ROOT) else f"desktop_qt/qml/{path.name}"  # test đọc file tạm ngoài repo
    root = parse_qml(src)
    forwards = forwards or {}
    seen: set[tuple[int, str]] = set()

    def add(line: int, text: str, kind: str) -> None:
        label, key = split_shortcut(text)
        if (line, label) in seen:
            return
        seen.add((line, label))
        scan.items.append(Item("qt", file, line, label, kind))
        if key:
            scan.shortcuts.append((label, key, file, line))

    for obj in walk(root):
        for name, (expr, line) in obj.props.items():
            if name.startswith("function@") or re.match(r"on[A-Z]", name):
                for t in options(expr):
                    if up.HAS_VI.search(t) and up.looks_ui(t):
                        add(line, t, "qml:js")
                continue
            if name == "radius":
                r = re.sub(r"\s+", " ", expr).strip()
                if not radius_ok(r):
                    scan.radii.append((file, line, r))
            if name in SKIP_PROPS:
                continue
            # literal_text gộp dấu cách, nên hai dấu cách trước "(phím)" phải đọc ở biểu thức thô
            for m in re.finditer(r"([\"'])([^\"'\n]*?\S) {2,}(\([^\"'\n]*\))\1", expr):
                if SHORTCUT.match(f"{m.group(2)} {m.group(3)}"):
                    scan.spaced.append((f"{m.group(2)}  {m.group(3)}", file, line))
            # thuộc tính chữ: mọi chuỗi giống chữ; thuộc tính khác (`property string note`, mảng `{ label: "Tự động" }`): chuỗi tiếng Việt
            for t in options(expr):
                if up.looks_ui(t) and (name in TEXT_PROPS or up.HAS_VI.search(t)):
                    add(line, t, f"qml:{name}")
        # cặp nhãn - icon qua thuộc tính chuyển tiếp (giá trị mặc định trong chính component, hay giá trị ở nơi dùng)
        for prop, icon in forwards.get(path.stem if root.children and obj is root.children[0] else obj.type, {}).items():
            if prop in obj.props:
                expr, line = obj.props[prop]
                for t in options(expr):
                    if up.looks_ui(t):
                        scan.pairs.append(Pair("qt", file, line, split_shortcut(t)[0], icon, f"forward:{prop}"))
        # cặp nhãn - icon trong cùng đối tượng
        if "icon" in obj.props:
            icon_expr, line = obj.props["icon"]
            label_expr = obj.props.get("text", obj.props.get("tip", ("", 0)))[0]
            for label, icon in pair_up(label_expr, icon_expr):
                scan.pairs.append(Pair("qt", file, line, label, icon, "prop:icon"))
        # Icon { name: ... } cạnh Text { text: ... } trong cùng khối
        kids = obj.children
        for index, child in enumerate(kids):
            if child.type != "Icon" or "name" not in child.props:
                continue
            for step in (1, -1):
                k = index + step
                while 0 <= k < len(kids) and kids[k].type == "Icon":
                    k += step
                if 0 <= k < len(kids) and kids[k].type == "Text" and "text" in kids[k].props:
                    found = pair_up(kids[k].props["text"][0], child.props["name"][0])
                    for label, icon in found:
                        scan.pairs.append(Pair("qt", file, child.line, label, icon, "sibling"))
                    if found:
                        break
            else:
                # Icon đứng một mình trong nút có `tip` (PlayButton: Interactive { tip; Icon {...} }): nhãn là chú thích của nút
                if "tip" in obj.props and not any(c.type == "Text" for c in kids):
                    for label, icon in pair_up(obj.props["tip"][0], child.props["name"][0]):
                        scan.pairs.append(Pair("qt", file, child.line, label, icon, "tip"))
        if obj.type == "Icon" or "icon" in obj.props:
            scan.icon_sites += 1
    # chuỗi qsTr(...) ở bất cứ đâu
    for m in re.finditer(r"qsTr\(\s*([\"'])", src):
        end = up.skip_string(src, m.start(1))
        text = up.literal_text(src[m.start(1):end])
        if up.looks_ui(text):
            add(up.line_of(src, m.start(1)), text, "qml:qsTr")


def qt_scan() -> QtScan:
    scan = QtScan()
    paths = [p for p in sorted(QML.glob("*.qml")) if p.name not in QML_SKIP]
    trees = {p.stem: parse_qml(up.blank_comments(p.read_bytes().decode("utf-8"))) for p in paths}
    forwards = forwarded_icons(trees)
    for path in paths:
        qml_scan_file(path, scan, forwards)
    for path in sorted(QML.glob("*.js")):
        if path.name != "LucidePaths.js":
            js_scan_file(path, scan)
    return scan


def js_scan_file(path: Path, scan: QtScan) -> None:
    """Chữ trong file .js cạnh QML (CastLogic.js, VoiceLogic.js): chuỗi tiếng Việt, chuỗi nối thành mẫu `{}`."""
    src = up.blank_comments(path.read_bytes().decode("utf-8"))
    file = up.rel(path) if path.is_relative_to(ROOT) else f"desktop_qt/qml/{path.name}"
    chains = joined_literals(src)
    found = [(start, text) for start, _, text in chains]
    found += [(pos, text) for pos, text in up.literals_in(src) if not any(s <= pos < e for s, e, _ in chains)]
    for pos, text in sorted(found):
        if up.HAS_VI.search(text) and up.looks_ui(text):
            scan.items.append(Item("qt", file, up.line_of(src, pos), split_shortcut(text)[0], "js"))


JSX_TEXT = re.compile(r"(?<=[>}])([^<>{}`\"']*[^\W\d_][^<>{}`\"']*)(?=[<{])")
OBJECT_TEXT = re.compile(r"\b(label|title|text|hint|description|heading|subtitle|placeholder|caption|summary|message|dialogLabel)\s*:\s*([\"'`])")


def web_scan() -> Scan:
    """Bộ đọc của ui_parity.py, thêm ba thứ nó không cần cho điện thoại: `label: "..."` trong đối tượng JS của file .tsx (SettingsNav, PANELS,
    `back={{ label }}`), mọi chuỗi tiếng Việt của file .ts có trong bảng màn (labels.ts: "Tạm dừng" / "Phát" do hàm trả về), và cặp nhãn-icon
    của nút ← ScreenHeader (`back={{ label: "Về Thư viện" }}` -> icon của BackButton)."""
    scan = Scan()
    mapped = {f"ui/src/{file}" for _, _, sources in SCREENS for file, _ in sources}
    back_icons = list(dict.fromkeys(up.lucide_imports((WEB / "shared" / "ScreenHeader.tsx").read_bytes().decode("utf-8")).values()))
    extra = sorted({WEB / file for _, _, sources in SCREENS for file, _ in sources if file.split("/")[0] not in WEB_DIRS})
    for d in WEB_DIRS + ("",):
        for path in (sorted((WEB / d).rglob("*")) if d else extra):
            if path.suffix not in (".ts", ".tsx") or ".test." in path.name or path.name.endswith(".d.ts"):
                continue
            up.web_scan_file(path, scan)
            src = path.read_bytes().decode("utf-8")
            file = up.rel(path)
            have = {(i.line, i.text) for i in scan.items if i.file == file}
            if path.suffix == ".tsx":
                for m in OBJECT_TEXT.finditer(src):
                    end = up.skip_string(src, m.start(2))
                    text = up.literal_text(src[m.start(2):end])
                    line = up.line_of(src, m.start(2))
                    if up.looks_ui(text) and (line, text) not in have:
                        scan.items.append(Item("web", file, line, text, f"prop:{m.group(1)}"))
                # chữ JSX nằm trong JSX của một thuộc tính (`idle={<div>Hẹn giờ đã tắt tiếng lúc …</div>}`): bộ đọc gốc không vào đó
                plain = up.blank_comments(src)
                for m in JSX_TEXT.finditer(plain):
                    text = re.sub(r"\s+", " ", m.group(1)).strip()
                    line = up.line_of(plain, m.start(1) + len(m.group(1)) - len(m.group(1).lstrip()))
                    if up.HAS_VI.search(text) and up.looks_ui(text) and not re.search(r"=>|;|&&|\|\||\breturn\b|\$", text) \
                            and not any(t == text for (_, t) in have):
                        scan.items.append(Item("web", file, line, text, "jsx-text"))
                if len(back_icons) == 1:
                    for m in re.finditer(r"back=\{\{\s*label:\s*\"([^\"]+)\"", src):
                        scan.pairs.append(Pair("web", file, up.line_of(src, m.start()), m.group(1), back_icons[0], "back"))
            elif file in mapped:
                for pos, text in up.literals_in(src):
                    line = up.line_of(src, pos)
                    if up.HAS_VI.search(text) and up.looks_ui(text) and (line, text) not in have:
                        scan.items.append(Item("web", file, line, text, "ts:literal"))
    return scan


# ---------------------------------------------------------------------------------------------------------------------------------------
# Màn


TOP_DECL = re.compile(r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|const|let|class|type|interface|enum)\s+(\w+)", re.M)
_RANGES: dict[str, dict[str, tuple[int, int]]] = {}


def ranges(file: str) -> dict[str, tuple[int, int]]:
    """Tên khai báo cấp trên cùng -> (dòng đầu, dòng cuối) của file web."""
    if file not in _RANGES:
        src = (WEB / file).read_bytes().decode("utf-8")
        marks = [(up.line_of(src, m.start()), m.group(1)) for m in TOP_DECL.finditer(src)]
        total = src.count("\n") + 1
        out: dict[str, tuple[int, int]] = {}
        for index, (line, name) in enumerate(marks):
            end = marks[index + 1][0] - 1 if index + 1 < len(marks) else total
            out.setdefault(name, (line, end))
        _RANGES[file] = out
    return _RANGES[file]


def web_in_screen(item, screen: str) -> bool:
    for name, _, sources in SCREENS:
        if name != screen:
            continue
        for file, decls in sources:
            if item.file != f"ui/src/{file}":
                continue
            if decls is None:
                return True
            spans = ranges(file)
            if any(d in spans and spans[d][0] <= item.line <= spans[d][1] for d in decls):
                return True
    return False


def qt_screen(file: str) -> str:
    name = Path(file).name
    for screen, files, _ in SCREENS:   # tên trùng khớp trước, rồi mẫu (Settings*.qml): file QML của một màn đặt tên theo tiền tố
        if name in files:
            return screen
    for screen, files, _ in SCREENS:
        if any(fnmatch.fnmatchcase(name, f) for f in files if "*" in f):
            return screen
    return "Khác"


def short_where(items, limit: int = 2) -> str:
    seen = sorted({f"{i.file.replace('ui/src/', '').replace('desktop_qt/qml/', 'qt/')}:{i.line}" for i in items})
    more = f" (+{len(seen) - limit})" if len(seen) > limit else ""
    return ", ".join(f"`{s}`" for s in seen[:limit]) + more


# ---------------------------------------------------------------------------------------------------------------------------------------
# Báo cáo


def render_body() -> str:
    return render_report(web_scan(), qt_scan())


def render_report(web: Scan, qt: QtScan) -> str:
    w_items = sorted(set(web.items), key=lambda i: (i.file, i.line, i.text))
    q_items = sorted(set(qt.items), key=lambda i: (i.file, i.line, i.text))
    w_pairs = sorted(set(web.pairs), key=lambda p: (p.file, p.line, p.label, p.icon))
    q_pairs = sorted(set(qt.pairs), key=lambda p: (p.file, p.line, p.label, p.icon))
    w_by = up.group(w_items, lambda i: up.key_loose(i.text))
    q_by = up.group(q_items, lambda i: up.key_loose(i.text))
    screens = [s for s, _, _ in SCREENS]
    w_screen = {s: [i for i in w_items if web_in_screen(i, s)] for s in screens}
    w_pairs_screen = {s: [p for p in w_pairs if web_in_screen(p, s)] for s in screens}
    out = [BEGIN, ""]
    out.append(f"Quét: web máy tính {len(w_items)} chữ ({len(w_by)} khác nhau), {len(w_pairs)} cặp nhãn-icon; Qt {len(q_items)} chữ "
               f"({len(q_by)} khác nhau), {len(q_pairs)} cặp nhãn-icon (icon dùng ở {qt.icon_sites} chỗ). Khoá so lỏng như UI_PARITY.md "
               "(hạ chữ, dấu thanh một kiểu, `...` = `…`, bỏ dấu câu cuối); phím tắt trong chú thích Qt (`Thu nhỏ (Esc)`) tách khỏi nhãn.")
    out.append("")
    out += section_a(q_items, w_screen, w_by, q_pairs, w_pairs_screen)
    out += section_b(q_pairs, w_pairs, w_pairs_screen)
    out += section_c(q_items, w_screen, w_by, q_by)
    out += section_d(qt.radii)
    out += section_e(q_items, w_by)
    out += section_f(qt.shortcuts, qt.spaced)
    out += ["", END, ""]
    return "\n".join(out)


def template_hit(text: str, templates: list[str]) -> bool:
    """Chữ Qt khớp một mẫu web có chỗ điền: "Lùi 15 giây" ~ `Lùi ${SKIP_SECONDS} giây` ("Lùi {} giây")."""
    key = up.key_loose(text)
    for t in templates:
        parts = up.key_loose(t).split("{}")
        if len(parts) > 1 and any(p.strip() for p in parts) and re.fullmatch(".+?".join(re.escape(p) for p in parts), key):
            return True
    return False


def similar(a_text: str, b_text: str, shared_icon: bool) -> float | None:
    a, b = up.tokens(a_text), up.tokens(b_text)
    jac = len(a & b) / len(a | b) if a | b else 0.0
    ratio = SequenceMatcher(None, up.fold(a_text), up.fold(b_text)).ratio()
    if (jac >= 0.5 and ratio >= 0.5) or ratio >= 0.8 or (shared_icon and max(jac, ratio) >= 0.2):
        return max(jac, ratio) + (0.3 if shared_icon else 0.0)
    return None


def section_a(q_items, w_screen, w_by, q_pairs, w_pairs_screen) -> list[str]:
    """Nhãn ngắn Qt chưa có nguyên văn ở web CÙNG MÀN mà giống một nhãn web của màn ấy (chung từ, gần nhau, hay chung icon)."""
    q_icons: dict[str, set[str]] = defaultdict(set)
    for p in q_pairs:
        q_icons[up.key_loose(p.label)].add(p.icon)
    rows = []
    for screen, items in w_screen.items():
        w_keys = {up.key_loose(i.text): i for i in items if up.short(i.text)}
        w_icons: dict[str, set[str]] = defaultdict(set)
        for p in w_pairs_screen[screen]:
            w_icons[up.key_loose(p.label)].add(p.icon)
        q_here = {}
        for i in q_items:
            if qt_screen(i.file) == screen and up.short(i.text) and len(up.key_loose(i.text)) >= 3:
                q_here.setdefault(up.key_loose(i.text), i)
        templates = [i.text for i in items if "{}" in i.text]
        for qk, qi in sorted(q_here.items()):
            if qk in w_keys or qk in w_by or template_hit(qi.text, templates):
                continue
            best = None
            for wk, wi in w_keys.items():
                if wk in {up.key_loose(x.text) for x in q_items}:
                    continue
                score = similar(qi.text, wi.text, bool(q_icons.get(qk, set()) & w_icons.get(wk, set())))
                if score is not None and (best is None or score > best[0]):
                    best = (score, wi)
            if best:
                rows.append((screen, -round(best[0], 3), qi, best[1]))
    rows.sort(key=lambda r: (r[0], r[1], r[2].text))
    out = ["## a. Cùng việc, khác chữ", "",
           f"Nhãn ngắn Qt không có nguyên văn (khoá lỏng) ở web máy tính mà giống một nhãn web CÙNG MÀN chưa có ở Qt. {len(rows)} cặp; "
           "mỗi nhãn Qt lấy một nhãn web giống nhất. Giống không có nghĩa là cùng việc: người sửa xem mã hai bên trước khi đổi.", "",
           "| màn | Qt | web | giống | nơi |", "|---|---|---|---|---|"]
    for screen, score, qi, wi in rows:
        out.append(f"| {screen} | {up.esc(qi.text)} | {up.esc(wi.text)} | {min(1.0, -score):.2f} | {short_where([qi], 1)} ~ {short_where([wi], 1)} |")
    if not rows:
        out.append("| (không có) | | | | |")
    out.append("")
    return out


def section_b(q_pairs, w_pairs, w_pairs_screen) -> list[str]:
    q_pairs = [p for p in q_pairs if up.short(p.label)]
    w_short = [p for p in w_pairs if up.short(p.label)]
    w_lab: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    q_lab: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for p in w_short:
        w_lab[up.key_loose(p.label)][p.icon].append(p)
    for p in q_pairs:
        q_lab[up.key_loose(p.label)][p.icon].append(p)
    diff_icon = [(k, set(w_lab[k]), set(q_lab[k])) for k in sorted(set(w_lab) & set(q_lab)) if not set(w_lab[k]) & set(q_lab[k])]
    out = ["## b. Cùng nhãn khác icon, cùng icon khác nhãn", "",
           f"**Cùng nhãn, khác icon** ({len(diff_icon)} nhãn Qt có icon mà icon ấy không đi với nhãn này ở bất cứ đâu trên web máy tính):", "",
           "| nhãn | web | Qt | nơi |", "|---|---|---|---|"]
    for k, wi, qi in diff_icon:
        wp = [p for i in sorted(wi) for p in w_lab[k][i]]
        qp = [p for i in sorted(qi) for p in q_lab[k][i]]
        out.append(f"| {up.esc(qp[0].label)} | {', '.join(sorted(wi))} | {', '.join(sorted(qi))} | {short_where(qp, 1)} ~ {short_where(wp, 1)} |")
    if not diff_icon:
        out.append("| (không có) | | | |")
    # cùng icon khác nhãn: theo màn, icon Qt dùng với nhãn mà web cùng màn không bao giờ ghép với icon ấy
    rows = []
    for p in q_pairs:
        screen = qt_screen(p.file)
        here = [w for w in w_pairs_screen.get(screen, []) if w.icon == p.icon]
        if here and up.key_loose(p.label) not in {up.key_loose(w.label) for w in here}:
            rows.append((screen, p, sorted({w.label for w in here})))
    out += ["", f"**Cùng icon, khác nhãn** ({len(rows)} cặp Qt; web cùng màn dùng cùng icon với nhãn khác):", "",
            "| màn | icon | Qt | web cùng màn | nơi |", "|---|---|---|---|---|"]
    for screen, p, labels in rows:
        out.append(f"| {screen} | {p.icon} | {up.esc(p.label)} | {', '.join(up.esc(x) for x in labels[:3])} | {short_where([p], 1)} |")
    if not rows:
        out.append("| (không có) | | | | |")
    # nhãn web cùng màn có icon mà Qt cùng nhãn không có icon nào
    q_any = {up.key_loose(p.label) for p in q_pairs}
    out += ["", f"Số cặp: web máy tính {len(w_short)}, Qt {len(q_pairs)}. Nhãn Qt có icon ({len(q_any)}): "
            + ", ".join(f"`{up.esc(q_lab[k][next(iter(q_lab[k]))][0].label, 30)}`" for k in sorted(q_any)) + ".", ""]
    return out


def section_c(q_items, w_screen, w_by, q_by) -> list[str]:
    out = ["## c. Nhãn chỉ có một bên, theo màn", "",
           "Nhãn ngắn (<= 6 chữ). **Chỉ Qt**: không có ở web cùng màn; `*` = web có ở màn khác. **Chỉ web**: nhãn web của màn không có ở đâu trong "
           "Qt - phần lớn là tính năng Qt chưa làm (bản thử), chỉ đếm và kể 15 đầu.", ""]
    for screen, items in w_screen.items():
        w_keys = {up.key_loose(i.text) for i in items}
        templates = [i.text for i in items if "{}" in i.text]
        q_here = [i for i in q_items if qt_screen(i.file) == screen and up.short(i.text)]
        q_only: dict[str, Item] = {}
        for i in q_here:
            k = up.key_loose(i.text)
            if k not in w_keys and not template_hit(i.text, templates):
                q_only.setdefault(k, i)
        w_only: dict[str, Item] = {}
        q_texts = [i.text for i in q_here]
        for i in items:
            k = up.key_loose(i.text)
            if up.short(i.text) and k not in q_by and not ("{}" in i.text and any(template_hit(t, [i.text]) for t in q_texts)):
                w_only.setdefault(k, i)
        out.append(f"### {screen}")
        out.append("")
        shown = sorted(q_only.values(), key=lambda i: (i.file, i.line))
        text = "; ".join(f"{up.esc(i.text)}{'*' if up.key_loose(i.text) in w_by else ''} ({short_where([i], 1)})" for i in shown)
        out.append(f"- chỉ Qt ({len(shown)}): {text or '(không có)'}")
        ws = sorted(w_only.values(), key=lambda i: (i.file, i.line))
        text = "; ".join(f"{up.esc(i.text)} (`{i.line}`)" for i in ws[:15])
        out.append(f"- chỉ web ({len(ws)}): {text or '(không có)'}{'; ...' if len(ws) > 15 else ''}")
        out.append("")
    other = sorted({i.file for i in q_items if qt_screen(i.file) == "Khác"})
    if other:
        out += [f"File QML chưa xếp màn (thêm vào SCREENS): {', '.join(f'`{f}`' for f in other)}.", ""]
    return out


def section_d(radii) -> list[str]:
    out = ["## d. Bo góc QML không theo token", "",
           "Hợp lệ: `Theme.radiusControl / radiusCover / radiusSheet` (DESIGN.md 5.5, `desktop_qt/tools/gen_theme.py`), `0`, tròn (`width / 2`, "
           "`height / 2`), lấy lại bo khung chứa (`parent.radius`), vòng đồng tâm ngoài (`Theme.radiusCover + 8` của bóng, vòng tiêu điểm). "
           f"Còn lại ({len(radii)}):", "", "| nơi | radius |", "|---|---|"]
    for file, line, expr in radii:
        out.append(f"| `{file.replace('desktop_qt/qml/', 'qt/')}:{line}` | `{up.esc(expr, 60)}` |")
    if not radii:
        out.append("| (không có) | |")
    out.append("")
    return out


NEW_TONE = re.compile(r"[òóỏõọ][ae]|[ùúủũụ]y")


def section_e(q_items, w_by) -> list[str]:
    out = ["## e. Dấu thanh kiểu mới và dấu ba chấm cuối nhãn", ""]
    tone = sorted({(i.text, short_where([i], 1)) for i in q_items if NEW_TONE.search(i.text)})
    out.append(f"**Dấu thanh kiểu mới (`òa óa úy`)** trong chữ Qt ({len(tone)}); web và native đa số viết kiểu cũ (`oà oá uý`, UI_PARITY.md d2):")
    out.append("")
    for text, w in tone:
        web_forms = sorted({i.text for i in w_by.get(up.key_loose(text), [])})
        out.append(f"- {up.esc(text, 60)} ({w})" + (f" - web: {', '.join(f'`{up.esc(f, 40)}`' for f in web_forms[:2])}" if web_forms else ""))
    if not tone:
        out.append("- (không có)")
    dots = sorted({(i.text, short_where([i], 1)) for i in q_items if re.search(r"(?:…|\.\.\.)$", i.text)})
    out += ["", f"**Nhãn kết thúc bằng `…` / `...`** ({len(dots)}): DESIGN.md chỉ cho `…` ở chữ đang chờ (\"Đang mở…\"), không cho nhãn nút.", ""]
    for text, w in dots:
        web_forms = sorted({i.text for i in w_by.get(up.key_loose(text), [])})
        mark = " - ASCII `...`" if text.endswith("...") else ""
        out.append(f"- {up.esc(text, 60)} ({w}){mark}" + (f" - web: {', '.join(f'`{up.esc(f, 40)}`' for f in web_forms[:2])}" if web_forms else " - web: (không có)"))
    if not dots:
        out.append("- (không có)")
    out.append("")
    return out


def web_shortcuts() -> dict[str, set[str]]:
    """Nhãn (mẫu: `Lùi ${SKIP_SECONDS} giây` -> "Lùi {} giây") -> phím tắt mà web ghép bằng withShortcut(nhãn, "Phím")."""
    out: dict[str, set[str]] = defaultdict(set)
    for d in WEB_DIRS:
        for path in sorted((WEB / d).rglob("*.ts*")):
            if ".test." in path.name:
                continue
            src = path.read_bytes().decode("utf-8")
            for m in re.finditer(r"withShortcut\(", src):
                end = up.skip_balanced(src, m.end() - 1, "(", ")")
                found = [t for _, t in up.literals_in(src[m.end():end - 1])]
                if len(found) >= 2:
                    for label in found[:-1]:
                        out[label].add(found[-1])
    return out


def section_f(shortcuts, spaced) -> list[str]:
    known = web_shortcuts()
    out = ["## f. Phím tắt trong chú thích", "",
           "Chú thích Qt ghi phím tắt sau nhãn; web ghép bằng `withShortcut(nhãn, phím)`. Phím khác nhau là khác HÀNH VI (phím thật trong "
           "`Main.qml` / `player.tsx`), không chỉ khác chữ.", "", "| nhãn | Qt | web | nơi |", "|---|---|---|---|"]
    rows = 0
    for label, key, file, line in sorted(set(shortcuts), key=lambda r: (r[2], r[3], r[0], r[1])):
        web_keys = {k for text, keys in known.items() if up.key_loose(text) == up.key_loose(label) or template_hit(label, [text]) for k in keys}
        if key not in web_keys:
            out.append(f"| {up.esc(label)} | `{key}` | {', '.join(f'`{k}`' for k in sorted(web_keys)) or '(không ghi)'} | `{file.replace('desktop_qt/qml/', 'qt/')}:{line}` |")
            rows += 1
    if not rows:
        out.append("| (không có) | | | |")
    out += ["", f"Chú thích có hai dấu cách trước phím (web `withShortcut` ghép một dấu cách): {len(spaced)}"
            + ("" if not spaced else " - " + "; ".join(f"`{up.esc(t)}` (`{f.replace('desktop_qt/qml/', 'qt/')}:{n}`)" for t, f, n in sorted(set(spaced), key=lambda r: (r[1], r[2], r[0])))) + ".", ""]
    return out


# ---------------------------------------------------------------------------------------------------------------------------------------


HEAD = """# Lệch chữ, icon và bo góc giữa web máy tính và bản Qt

Chủ sách 26-10: "giao diện giữa các nền tảng phải làm đồng nhất ở mọi chỗ có thể nhé, từng cái chữ, từng cái icon, từng cái bo góc".
Cùng nguồn chung như `docs/UI_PARITY.md` (web <-> điện thoại native): bo góc `Theme.qml` sinh bởi `desktop_qt/tools/gen_theme.py` từ DESIGN.md 5.5,
icon `LucidePaths.js` sinh bởi `scripts/gen_lucide_icons.py --qml`. Bảng dưới do `scripts/ui_parity_qt.py` sinh (`--check` báo lệch,
`tests/test_ui_parity_qt.py` chạy `--check`). Bộ đọc là heuristic trên mã nguồn: chữ dựng từ dữ liệu (tên chương, thời gian) không tính.

"""


def render_doc(current: str | None) -> str:
    body = render_body()
    if current and BEGIN in current and END in current:
        head = current[:current.index(BEGIN)]
        tail = current[current.index(END) + len(END):].lstrip("\n")
        return head + body + (("\n" + tail) if tail else "")
    return HEAD + body


def main(argv: list[str]) -> int:
    current = DOC.read_bytes().decode("utf-8") if DOC.is_file() else None
    text = render_doc(current)
    if "--check" in argv:
        if current != text:
            print(f"{DOC} không còn khớp mã nguồn - chạy scripts/ui_parity_qt.py", file=sys.stderr)
            return 1
        return 0
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_bytes(text.encode("utf-8"))  # LF
    print(f"đã ghi {DOC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
