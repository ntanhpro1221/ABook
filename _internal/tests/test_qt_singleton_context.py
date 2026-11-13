"""QML chỉ đọc singleton ở nơi singleton ấy thật sự có (build.bat 13-11: SkipGlyphTests QML_TYPE_ERROR).

Loại lỗi: 628780f01 đổi `font.weight` của SkipGlyph.qml sang `Theme.weightMedium`. Trong app, SkipGlyph nằm trong module
ABook nên `Theme` là singleton; nhưng tests/test_skipglyph.cpp nạp nó thẳng từ thư mục nguồn (`import "file:///.../qml"`,
không qmldir): ở đó `Theme` chỉ là kiểu QML thường, `Theme.weightMedium` là undefined, chữ "15" giữ nét mặc định và
log có "Unable to assign [undefined] to int". qmllint (tools/check_qml_members.py) soát theo module nên không thấy.

Hai luật đọc nguồn, chạy trong qt_pytests (trước mọi QtTest):
1. Mọi `Theme.tên` trong qml/ và tests/ phải được khai trong Theme.qml (thuộc tính / hàm / tín hiệu).
2. Kiểu QML mà một bộ thử C++ nạp ngoài module (từ thư mục nguồn), cùng mọi kiểu cùng thư mục nó dựng tiếp, không được
   đọc singleton của module: singleton QML (QT_QML_SINGLETON_TYPE trong CMakeLists.txt) hay C++ (QML_SINGLETON).
"""
from __future__ import annotations

import re
import importlib.util
from pathlib import Path

QT = Path(__file__).resolve().parents[1] / "desktop_qt"
QML = QT / "qml"


def theme_members(qml: Path = QML) -> set[str]:
    text = (qml / "Theme.qml").read_text(encoding="utf-8")
    names = set(re.findall(r"^\s*(?:readonly\s+)?property\s+[\w<>.]+\s+(\w+)", text, re.M))
    names |= set(re.findall(r"^\s*(?:function|signal)\s+(\w+)", text, re.M))
    return names


def unknown_theme_members(qt: Path = QT) -> list[str]:
    known = theme_members(qt / "qml")
    found = []
    for path in sorted([*(qt / "qml").glob("*.qml"), *(qt / "qml").glob("*.js"), *(qt / "tests").rglob("*.qml"), *(qt / "tests").rglob("*.js")]):
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"(?<![\w.$\"'/])Theme\.([A-Za-z_]\w*)", text):
            if m.group(1) not in known and not m.group(1).endswith("Changed"):
                found.append(f"{path.relative_to(qt).as_posix()}:{text.count(chr(10), 0, m.start()) + 1}: Theme.{m.group(1)}")
    return found


def singletons(qt: Path = QT) -> set[str]:
    cmake = (qt / "CMakeLists.txt").read_text(encoding="utf-8")
    names = set()
    for files in re.findall(r"set_source_files_properties\(([^)]*?)PROPERTIES\s+QT_QML_SINGLETON_TYPE\s+TRUE", cmake):
        names |= {Path(f).stem for f in files.split() if f.endswith(".qml")}
    for header in (qt / "src").glob("*.h"):
        text = header.read_text(encoding="utf-8", errors="replace")
        for block in re.finditer(r"class\s+(\w+)[^{;]*\{(.*?)\n\};", text, re.S):
            if "QML_SINGLETON" in block.group(2):
                named = re.search(r"QML_NAMED_ELEMENT\((\w+)\)", block.group(2))
                names.add(named.group(1) if named else block.group(1))
    return names


def standalone_types(qt: Path = QT) -> set[str]:
    """Kiểu mà bộ thử C++ dựng từ một chuỗi QML có `import "file:///<thư mục nguồn>"` (không qua module ABook)."""
    found = set()
    for test in (qt / "tests").glob("*.cpp"):
        text = test.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'import \\"file:///[^\n]*?\\n(\w+)\s*\{', text):
            found.add(m.group(1))
    return found


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", "", text)


def singleton_reads_outside_module(qt: Path = QT) -> list[str]:
    names = singletons(qt)
    qml = qt / "qml"
    todo, seen, found = sorted(standalone_types(qt)), set(), []
    while todo:
        kind = todo.pop()
        path = qml / f"{kind}.qml"
        if kind in seen or not path.exists():
            continue
        seen.add(kind)
        text = strip_comments(path.read_text(encoding="utf-8"))
        for m in re.finditer(r"(?<![\w.$\"'])([A-Z]\w*)\s*(?:\.|\{)", text):
            name = m.group(1)
            if name in names and text[m.end() - 1] == ".":
                found.append(f"{path.name}:{text.count(chr(10), 0, m.start()) + 1}: {name}. (nạp ngoài module, {name} không phải singleton ở đó)")
            elif text[m.end() - 1] == "{" and (qml / f"{name}.qml").exists():
                todo.append(name)
    return found


def test_theme_members_exist():
    assert unknown_theme_members() == []


def test_runtime_audit_rejects_detached_parent_even_with_passing_totals(tmp_path, capsys):
    """The parity3 errors come from detached Repeater delegates, not singleton lookup.

    A source/module check cannot prove parent lifetime. The runtime gate must reject
    these warnings even when every QML test assertion passes, and count locations once.
    """
    spec = importlib.util.spec_from_file_location("qt_result_context_audit", QT / "tools/check_test_results.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    clean = "Totals: 1 passed, 0 failed, 0 skipped, 0 blacklisted\n"
    warnings = [
        f"QWARN : Context::destroy() file:///D:/app/desktop_qt/qml/{file}:{line}:29: TypeError: Cannot read property 'width' of null\n"
        for file, line in (("SettingsVoice.qml", 184), ("SettingsVoice.qml", 307), ("VoiceModule.qml", 185), ("VoiceSpeed.qml", 75))
    ]
    log = tmp_path / "qt-context.txt"
    log.write_text(clean + "".join(warnings) + warnings[0], encoding="utf-8")
    assert not audit.check(log)
    output = capsys.readouterr().out
    assert "TEST_TOTALS 1 passed, 0 failed" in output
    assert "QML_TYPE_ERROR 4;" in output
    log.write_text(clean, encoding="utf-8")
    assert audit.check(log)
    assert "QML_TYPE_ERROR 0;" in capsys.readouterr().out


def test_standalone_qml_reads_no_module_singleton():
    assert standalone_types(), "máy dò không còn thấy bộ thử nào nạp QML ngoài module (test_skipglyph.cpp): xem lại mẫu"
    assert singleton_reads_outside_module() == []


def test_detectors_catch_the_planted_faults(tmp_path):
    qt = tmp_path / "desktop_qt"
    (qt / "qml").mkdir(parents=True)
    (qt / "tests").mkdir()
    (qt / "src").mkdir()
    (qt / "qml" / "Theme.qml").write_text("pragma Singleton\nQtObject {\n    readonly property int weightMedium: 500\n}\n", encoding="utf-8")
    (qt / "CMakeLists.txt").write_text("set_source_files_properties(qml/Theme.qml PROPERTIES QT_QML_SINGLETON_TYPE TRUE)\n", encoding="utf-8")
    (qt / "src" / "player.h").write_text("class Player : public QObject {\n    QML_ELEMENT\n    QML_SINGLETON\n};\n", encoding="utf-8")
    (qt / "tests" / "test_glyph.cpp").write_text('QByteArray s = QByteArray("import QtQuick\\nimport \\"file:///") + dir + "\\"\\nGlyph {}\\n";\n', encoding="utf-8")
    (qt / "qml" / "Glyph.qml").write_text("Item {\n    // Theme.weightMedium trong chú thích không tính\n    Part {}\n}\n", encoding="utf-8")
    (qt / "qml" / "Part.qml").write_text("Text { font.weight: Theme.weightMedium; visible: Player.playing }\n", encoding="utf-8")
    (qt / "qml" / "Screen.qml").write_text("Text { font.weight: Theme.weightHeavy; color: Theme.weightMedium }\n", encoding="utf-8")
    assert singletons(qt) == {"Theme", "Player"}
    assert standalone_types(qt) == {"Glyph"}
    assert [hit.split(":")[0] + ":" + hit.split(": ")[1].split(" ")[0] for hit in singleton_reads_outside_module(qt)] == ["Part.qml:Theme.", "Part.qml:Player."]
    assert unknown_theme_members(qt) == ["qml/Screen.qml:1: Theme.weightHeavy"]
