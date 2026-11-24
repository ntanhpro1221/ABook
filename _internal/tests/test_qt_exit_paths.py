"""Máy dò cho lỗi "bấm Thoát ABook ở khay mà app vẫn ở khay" (chủ sách 24-11, bản Qt 0.4.174) - cả loại, không chỉ một dòng.

1. Thoát có chủ ý chỉ có một lối: `Platform.exitApp()` (QCoreApplication::exit). `Qt.quit()` / `QGuiApplication::quit()` hỏi từng
   cửa sổ trước, cửa sổ đang ẩn khay / hộp đang mở có thể từ chối, nên không QML hay C++ nào của app được gọi chúng.
2. Gán `ten: ten` trong một component lồng (Loader.sourceComponent, delegate, Component {...}) là tự gán: vế phải tìm thuộc tính
   của chính đối tượng trước id của component ngoài, nên nhận null. Đó đúng là `DesktopTray { windowMode: windowMode }` làm mọi
   mục khay chết. Chỉ chấp nhận khi id `ten` khai trong CÙNG component (ở đó id thắng thuộc tính)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "desktop_qt"
QML_DIRS = [ROOT / "qml"]
BARE_QUIT_QML = re.compile(r"\bQt\s*\.\s*(?:quit|exit)\s*\(")
BARE_QUIT_CPP = re.compile(r"\b(?:QCoreApplication|QGuiApplication|QApplication)\s*::\s*quit\s*\(|\bqApp\s*->\s*quit\s*\(")
BOUNDARY_OBJECT = re.compile(r"(?:\bsourceComponent|\bdelegate|\w+Component)\s*:\s*[A-Z][\w.]*\s*$")
COMPONENT = re.compile(r"(?:^|[^\w.])Component\s*$")
OBJECT = re.compile(r"(?:^|[\s:;{}])[A-Z][\w.]*\s*$")
SELF = re.compile(r"^\s*([a-z_]\w*)\s*:\s*\1\s*$")
ID = re.compile(r"^\s*id\s*:\s*(\w+)\s*$")


def _strip(text: str) -> str:
    """Bỏ chú thích và nội dung chuỗi (giữ xuống dòng để số dòng còn đúng)."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end < 0 else end + 2
            out.append(re.sub(r"[^\n]", " ", text[i:end]))
            i = end
        elif c in "\"'`":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            out.append(c + re.sub(r"[^\n]", " ", text[i + 1:j]) + c)
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def shadowed_self_bindings(text: str) -> list[tuple[int, str]]:
    """(dòng, tên) của mọi `ten: ten` trong đối tượng QML mà id `ten` không khai trong cùng component."""
    text = _strip(text)
    contexts = 1
    # Mỗi khung: (là đối tượng QML?, context của câu trong khung, context của khung con)
    stack: list[tuple[bool, int, int]] = [(True, 0, 0)]
    ids: dict[str, set[int]] = {}
    candidates: list[tuple[int, str, int]] = []
    segment, line, start_line = "", 1, 1

    def close_segment():
        is_object, context, _child = stack[-1]
        if is_object:
            if match := SELF.match(segment):
                candidates.append((start_line, match.group(1), context))
            elif match := ID.match(segment):
                ids.setdefault(match.group(1), set()).add(context)

    for c in text:
        if c in "\n;{}":
            if c == "{":
                head = segment
                is_object = bool(OBJECT.search(head))
                _parent_object, context, child = stack[-1]
                if is_object and BOUNDARY_OBJECT.search(head):
                    stack.append((True, contexts, contexts))     # đối tượng gốc của component lồng: context mới
                    contexts += 1
                elif is_object and COMPONENT.search(head):
                    stack.append((True, child, contexts))         # id của Component thuộc ngoài, con của nó thuộc context mới
                    contexts += 1
                else:
                    stack.append((is_object, child, child))
            else:
                close_segment()
                if c == "}" and len(stack) > 1:
                    stack.pop()
            segment = ""
            if c == "\n":
                line += 1
            start_line = line
            continue
        segment += c
    return [(at, name) for at, name, context in candidates if context not in ids.get(name, set())]


def test_shadowed_self_binding_detector_sees_the_tray_bug_and_not_the_safe_forms() -> None:
    broken = """Window {
    WindowMode { id: windowMode }
    Loader {
        sourceComponent: DesktopTray { windowMode: windowMode }
    }
    Component { id: rowFactory; Row { flick: flick } }
}
"""
    assert shadowed_self_bindings(broken) == [(4, "windowMode"), (6, "flick")]
    safe = """Item {
    Flickable { id: flick }
    SmoothWheel { flick: flick }
    MiniPlayer { windowMode: windowMode }
    WindowMode { id: windowMode }
    Loader { sourceComponent: Item { Flickable { id: inner }; SmoothWheel { inner: inner } } }
    function f() { return {target: target, name: name} }
    property var call: Api.call("POST", "/x", {enabled: enabled})
}
"""
    assert shadowed_self_bindings(safe) == []


def test_no_qml_binds_a_property_to_itself_inside_a_nested_component() -> None:
    found = []
    for folder in QML_DIRS:
        for path in sorted(folder.rglob("*.qml")):
            for at, name in shadowed_self_bindings(path.read_text(encoding="utf-8")):
                found.append(f"{path.relative_to(ROOT).as_posix()}:{at}: {name}: {name}")
    assert found == [], "tự gán trong component lồng (vế phải là chính thuộc tính, không phải id ngoài):\n" + "\n".join(found)


def test_every_deliberate_exit_goes_through_platform_exit_app() -> None:
    found = []
    for path in sorted((ROOT / "qml").rglob("*.qml")) + sorted((ROOT / "qml").rglob("*.js")):
        for at, text in enumerate(_strip(path.read_text(encoding="utf-8")).splitlines(), 1):
            if BARE_QUIT_QML.search(text):
                found.append(f"{path.relative_to(ROOT).as_posix()}:{at}")
    for path in sorted((ROOT / "src").rglob("*.cpp")) + sorted((ROOT / "src").rglob("*.h")):
        for at, text in enumerate(_strip(path.read_text(encoding="utf-8")).splitlines(), 1):
            if BARE_QUIT_CPP.search(text):
                found.append(f"{path.relative_to(ROOT).as_posix()}:{at}")
    assert found == [], "thoát trần (hỏi cửa sổ, có thể bị từ chối) - dùng Platform.exitApp() / QCoreApplication::exit:\n" + "\n".join(found)
    main = (ROOT / "qml" / "Main.qml").read_text(encoding="utf-8")
    assert "onExitRequested: Platform.exitApp()" in main
    assert "QCoreApplication::exit(0);" in (ROOT / "src" / "platform.cpp").read_text(encoding="utf-8")
