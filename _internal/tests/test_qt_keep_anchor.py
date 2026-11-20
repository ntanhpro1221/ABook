"""QML objects that live outside the visual tree anchor their JS wrapper with Keep.hold (desktop_qt/src/keep.h).

The V4 collector marks a QML object's property storage only through its JS wrapper. QQuickItem wrappers mark their visual
children; every other object (a Reveal after `parent = null`, a pointer handler, a Connections, a non-visual store declared
as a child) depends on the weak QObject-wrapper pass, which drops the wrapper when the topmost QObject ancestor is JS-owned.
The storage then vanishes while the object lives: "Cannot find member data", properties read as 0, Reveal transitions that
never finish (WidthTests 0.4.173: Studio2/Studio5/ModalLayer). tests/width/tst_keep.qml reproduces it deterministically.

Rules for desktop_qt/qml:
- leaving the visual tree (`parent = null`) only in Reveal.qml, after Keep.hold;
- a non-singleton component whose root is non-visual holds its root;
- a non-visual object declared as a child with its own properties or functions holds itself (or is a property value,
  which the declaring object's storage references strongly);
- a child Connections is a Listen (Connections + Keep.hold).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "desktop_qt"
QML = ROOT / "qml"
NON_VISUAL = {"QtObject", "Connections", "Timer", "WheelHandler", "TapHandler", "DragHandler", "HoverHandler", "PointHandler",
              "PinchHandler", "Binding", "Shortcut", "Instantiator"}
DECLARATION = re.compile(r"^\s*(?:(?:readonly|required|default)\s+)*(?:property\s+[\w.<>]+\s+\w+|function\s+\w+)")
LEAVE_TREE = re.compile(r"\bparent\s*=\s*null\b")


def _strip(text):
    """Blank out strings and comments, keeping line numbers."""
    text = re.sub(r'"(?:\\.|[^"\\\n])*"', '""', text)
    text = re.sub(r"'(?:\\.|[^'\\\n])*'", "''", text)
    text = re.sub(r"`(?:\\.|[^`\\])*`", lambda m: "``" + "\n" * m.group(0).count("\n"), text)
    text = re.sub(r"//[^\n]*", "", text)
    return re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)


def _block(text, brace):
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[brace + 1:index]
    return text[brace + 1:]


def _own_declarations(body):
    depth = 0
    found = False
    for line in body.split("\n"):
        if depth == 0 and DECLARATION.match(line):
            found = True
        depth += line.count("{") - line.count("}")
    return found


def violations(root=QML):
    found = []
    for path in sorted(root.glob("*.qml")):
        raw = path.read_text(encoding="utf-8")
        text = _strip(raw)
        line_of = lambda offset: text.count("\n", 0, offset) + 1
        for match in LEAVE_TREE.finditer(text):
            before = text[:match.start()]
            if path.name != "Reveal.qml" or "Keep.hold(" not in before[before.rfind("Component.onCompleted"):]:
                found.append(f"{path.name}:{line_of(match.start())}: leaves the visual tree without Keep.hold (only Reveal does this)")
        first = re.search(r"^([A-Z][\w.]*)\s*\{", text, re.M)
        for match in re.finditer(r"(property\s+[\w.<>]+\s+\w+\s*:\s*)?\b([A-Z][\w.]*)\s*\{", text):
            kind = match.group(2)
            if kind not in NON_VISUAL:
                continue
            body = _block(text, match.end() - 1)
            is_root = first is not None and match.start(2) == first.start(1)
            where = f"{path.name}:{line_of(match.start(2))}"
            if is_root:
                if "pragma Singleton" not in text and "Keep.hold(" not in body:
                    found.append(f"{where}: non-visual component root {kind} must call Keep.hold on itself")
                continue
            if match.group(1):
                continue   # property value: the declaring object's storage holds it
            if kind == "Connections":
                found.append(f"{where}: child Connections must be a Listen")
            elif _own_declarations(body) and "Keep.hold(" not in body:
                found.append(f"{where}: child {kind} with its own properties/functions must call Keep.hold on itself")
    return found


def test_objects_outside_the_visual_tree_are_anchored():
    found = violations()
    assert not found, "\n".join(found)


def missing_module_imports(root=QML):
    """Keep and Listen come from the ABook module: a file loaded through its directory (as WidthTests does) does not see
    them without `import ABook` (Studio1 0.4.173: "ReferenceError: Keep is not defined" in UiActivity.qml)."""
    found = []
    for path in sorted(root.glob("*.qml")):
        text = _strip(path.read_text(encoding="utf-8"))
        if re.search(r"\bKeep\.hold\(|^\s*Listen\s*\{", text, re.M) and not re.search(r"^import ABook\b", text, re.M):
            found.append(path.name)
    return found


def test_anchor_users_import_the_module(tmp_path):
    assert missing_module_imports() == []
    (tmp_path / "Bad.qml").write_text("import QtQuick\nQtObject {\n    id: root\n    Component.onCompleted: Keep.hold(root)\n}\n", encoding="utf-8")
    (tmp_path / "Good.qml").write_text("import QtQuick\nimport ABook\nItem {\n    Listen { target: x }\n}\n", encoding="utf-8")
    assert missing_module_imports(tmp_path) == ["Bad.qml"]


def test_shared_anchors_hold_themselves():
    for name, owner in (("Reveal.qml", "reveal"), ("SmoothWheel.qml", "root"), ("Listen.qml", "listen")):
        assert f"Keep.hold({owner})" in (QML / name).read_text(encoding="utf-8"), name


def test_every_qml_harness_registers_keep():
    cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    for target in ("ABookDesk WIN32", "WidthTests", "HitlTests", "SidebarTests"):
        start = cmake.index(f"qt_add_executable({target}")
        assert "src/keep.h" in cmake[start:cmake.index(")", start)], target
    assert re.search(r"^\s+qml/Listen\.qml$", cmake, re.M)
    for harness in ("tests/test_width.cpp", "tests/test_sidebar.cpp"):
        assert re.search(r'qmlRegisterSingletonType<Keep>\("ABook", 1, 0, "Keep"', (ROOT / harness).read_text(encoding="utf-8")), harness
    assert re.search(r"^Listen 1\.0 \.\./\.\./\.\./\.\./qml/Listen\.qml$", (ROOT / "tests/qml/stub/ABook/qmldir").read_text(encoding="utf-8"), re.M)


def test_detector_sees_each_unanchored_shape(tmp_path):
    cases = {
        "Leave.qml": "Item {\n    Component.onCompleted: parent = null\n}\n",
        "Store.qml": "QtObject {\n    id: root\n    property int n: 1\n}\n",
        "Bare.qml": "Item {\n    Connections { target: x; function onY() {} }\n}\n",
        "Timed.qml": "Item {\n    Timer {\n        id: t\n        property bool fired: false\n    }\n}\n",
    }
    for name, text in cases.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    found = violations(tmp_path)
    assert len(found) == 4 and {line.split(":")[0] for line in found} == set(cases), found


def test_detector_accepts_anchored_shapes(tmp_path):
    (tmp_path / "Ok.qml").write_text(
        "Item {\n"
        "    property QtObject state: QtObject { property int n: 1 }\n"
        "    Listen { target: x; function onY() {} }\n"
        "    Timer { id: t; property bool fired: false; Component.onCompleted: Keep.hold(t) }\n"
        "    Timer { interval: 5; onTriggered: run() }\n"
        "}\n", encoding="utf-8")
    (tmp_path / "Root.qml").write_text("QtObject {\n    id: root\n    Component.onCompleted: Keep.hold(root)\n    property int n\n}\n", encoding="utf-8")
    (tmp_path / "Single.qml").write_text("pragma Singleton\nimport QtQml\nQtObject {\n    property int n\n}\n", encoding="utf-8")
    assert violations(tmp_path) == []


VALUE_TYPES = {"real", "int", "bool", "string", "var", "color", "url", "double", "date", "point", "size", "rect", "font",
               "list", "alias", "variant", "vector2d", "vector3d", "matrix4x4"}
HANDLER_OPEN = re.compile(r"^\s*(?:on[A-Z]\w*\s*:|function\s+\w+|Component\.on\w+\s*:)")


def guarded_rereads(root=QML):
    """An anchored object (Keep.hold on its root id) does not bind its inline property-value objects to its own object properties.

    Gate 22: "QML SmoothWheel: Cannot find member data", twice, at NowPlaying.qml:225 when a NowPlaying scene was torn down
    in the full WidthTests run. Outside a real wheel turn the only reader of SmoothWheel's property storage was the glide
    animation's binding `target: root.flick`; it now gets the target when a wheel turn starts.
    """
    found = []
    value_block = re.compile(r"^\s*(?:(?:readonly|required|default)\s+)*property\s+[\w.<>]+\s+\w+\s*:\s*[A-Z][\w.]*\s*\{")
    for path in sorted(root.glob("*.qml")):
        text = _strip(path.read_text(encoding="utf-8"))
        owner = re.search(r"\bKeep\.hold\((\w+)\)", text)
        first = re.search(r"^[A-Z][\w.]*\s*\{", text, re.M)
        if not owner or not first:
            continue
        root_id = re.search(r"\bid:\s*(\w+)", text[first.end():])
        if not root_id or root_id.group(1) != owner.group(1):
            continue
        # Object properties naming another object (guarded by Qt); an inline value (`property T x: T {`) is owned storage.
        objects = [m.group(2) for m in re.finditer(r"^\s{4}(?:(?:readonly|required|default)\s+)*property\s+([\w.<>]+)\s+(\w+)(\s*:\s*[A-Z][\w.]*\s*\{)?",
                                                   text, re.M)
                   if m.group(1) not in VALUE_TYPES and not m.group(3)]
        if not objects:
            continue
        reader = re.compile(rf"\b{owner.group(1)}\.(?:{'|'.join(objects)})\b")
        depth = 0
        inside = None   # depth at which the current inline property-value object was opened
        for number, line in enumerate(text.split("\n"), 1):
            if inside is None and value_block.match(line):
                inside = depth
            elif inside is not None and not HANDLER_OPEN.match(line) and (hit := reader.search(line)) \
                    and re.search(r"\b\w+\s*:[^:]*$", line[:hit.start()]):
                found.append(f"{path.name}:{number}: binding re-reads {hit.group(0)}; assign it when the event starts")
            depth += line.count("{") - line.count("}")
            if inside is not None and depth <= inside:
                inside = None
    return found


def test_anchored_objects_do_not_rebind_their_own_objects():
    assert guarded_rereads() == []


def test_reread_detector_sees_the_gate22_shapes(tmp_path):
    (tmp_path / "Wheel.qml").write_text(
        "import ABook\nWheelHandler {\n    id: root\n    Component.onCompleted: Keep.hold(root)\n"
        "    required property Flickable flick\n    property real step: 110\n"
        "    onWheel: (event) => {\n        glide.target = root.flick\n        flick.contentY = root.step\n    }\n"
        "    property NumberAnimation glide: NumberAnimation {\n        target: root.flick\n        duration: root.step\n    }\n}\n",
        encoding="utf-8")
    (tmp_path / "Fade.qml").write_text(
        "import ABook\nItem {\n    id: reveal\n    property Item target: parent\n    property bool shown\n"
        "    Component.onCompleted: { bind.target = target; Keep.hold(reveal) }\n"
        "    Binding { id: bind; target: null; property: \"visible\"; value: reveal.shown }\n"
        "    Binding { target: reveal.target; property: \"opacity\"; value: 1 }\n}\n", encoding="utf-8")
    found = guarded_rereads(tmp_path)
    assert [f.split(": binding")[0] for f in found] == ["Wheel.qml:12"], found
