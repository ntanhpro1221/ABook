"""A Repeater delegate has no parent while it is created or torn down, so its root never binds to `parent`
(a TypeError the Qt tests count as a failure, and a zero width meanwhile). It sizes from the Repeater's container by id
(review174b Thấp-4, after a1ec75c52 in EditBook.qml)."""
from pathlib import Path
import re

QML = Path(__file__).resolve().parents[1] / "desktop_qt" / "qml"
OBJECT = re.compile(r"^\s*(?:[a-z][\w.]*\s*:\s*)?[A-Z][\w.]*\s*\{")
PROPERTY = re.compile(r"^\s*[a-z][\w.]*\s*:")


def _code(line: str) -> str:
    return re.sub(r"//.*$", "", re.sub(r'"(?:\\.|[^"\\])*"', '""', line))


def delegate_root_parent_bindings(text: str) -> list[int]:
    lines = [_code(line) for line in text.split("\n")]
    found = []
    for index, line in enumerate(lines):
        if not re.match(r"^\s*Repeater\s*\{", line):
            continue
        depth, j, delegate = line.count("{") - line.count("}"), index + 1, None
        while j < len(lines) and depth > 0:
            if depth == 1 and delegate is None and re.match(r"^\s*(?:delegate:\s*)?[A-Z][\w.]*\s*\{", lines[j]):
                delegate = j
            depth += lines[j].count("{") - lines[j].count("}")
            j += 1
        if delegate is None:
            continue
        inside = 0
        for k in range(delegate, len(lines)):
            if k > delegate and inside == 1 and PROPERTY.match(lines[k]) and not OBJECT.match(lines[k]) \
                    and re.search(r"\bparent\.width\b", lines[k]):
                found.append(k + 1)
            inside += lines[k].count("{") - lines[k].count("}")
            if inside <= 0:
                break
    return found


def test_the_scanner_finds_a_parent_binding_on_a_delegate_root_only():
    sample = ("Column {\n    Repeater {\n        model: 3\n        Text {\n            width: parent.width\n"
              "            Rectangle { width: parent.width }\n        }\n    }\n}\n")
    assert delegate_root_parent_bindings(sample) == [5]


def test_no_repeater_delegate_root_binds_to_its_parent_width():
    found = [f"{path.name}:{line}" for path in sorted(QML.rglob("*.qml"))
             for line in delegate_root_parent_bindings(path.read_text(encoding="utf-8"))]
    assert found == []
