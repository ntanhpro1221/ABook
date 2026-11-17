"""A book's author is the listener's own text: never cut with "…" or after N lines, on web, Android or Qt.

DESIGN.md 5.5 "Tên một dòng": one line goes through OneLineFit (shrink to fit, else wrap at full size). The web scan
(ui/src/shared/userTextClip.test.ts, USER_TEXT has `.author`) and Android TextCutScanTest catch their own platform; this
scan reads all three without a toolchain, so a Qt `elide` with a `text-cut-ok` note cannot slip through either.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTHOR = re.compile(r"\bauthor\b")
QML_CUT = re.compile(r"\belide\s*:\s*Text\.Elide(?:Right|Left|Middle)\b|\bmaximumLineCount\s*:")
TSX_CUT = re.compile(r"\b(?:truncate|line-clamp-\d)\b")
KT_CUT = re.compile(r"\bmaxLines\s*=|TextOverflow\.(?:Ellipsis|StartEllipsis|MiddleEllipsis)")


def qml_blocks(source: str):
    """(first line, text) of each innermost `Type { ... }` object block."""
    stack: list[tuple[int, list[str]]] = []
    for number, line in enumerate(source.splitlines(), 1):
        for char in line.split("//", 1)[0] + "\n":
            if char == "{":
                stack.append((number, []))
            elif char == "}" and stack:
                start, body = stack.pop()
                yield start, "".join(body)
            elif stack:
                stack[-1][1].append("\n" if char == ";" else char)


def qml_findings(source: str) -> list[int]:
    found = []
    for start, body in qml_blocks(source):
        text = [line for line in body.splitlines() if re.match(r"\s*text\s*:", line)]
        if any(AUTHOR.search(line) for line in text) and QML_CUT.search(body):
            found.append(start)
    return found


def line_findings(source: str, cut: re.Pattern[str]) -> list[int]:
    return [number for number, line in enumerate(source.splitlines(), 1)
            if AUTHOR.search(line) and cut.search(line.split("//", 1)[0])]


def test_detectors_see_a_cut_author_and_pass_a_fitted_one():
    assert qml_findings("Text {\n  text: book.author\n  elide: Text.ElideRight // text-cut-ok\n}") == [1]
    assert qml_findings("Text {\n  text: book.author\n  maximumLineCount: 1\n}") == [1]
    assert qml_findings("Item {\n  Text { text: root.book.author || \"\"; elide: Text.ElideRight }\n}") == [2]
    assert qml_findings("OneLineFit {\n  text: book.author\n  room: 100\n}") == []
    assert qml_findings("Item {\n  Text { text: book.author }\n  Text { text: title; elide: Text.ElideRight }\n}") == []
    assert line_findings('<p className="truncate">{book.author}</p>', TSX_CUT) == [1]
    assert line_findings('<OneLineFit className="text-xs">{book.author}</OneLineFit>', TSX_CUT) == []
    assert line_findings("BasicText(lead.author, maxLines = 1, overflow = TextOverflow.Ellipsis)", KT_CUT) == [1]
    assert line_findings("BasicText(lead.author, autoSize = OneLineFit.of(style))", KT_CUT) == []


def test_qt_text_cut_check_passes_without_a_qt_build():
    """build.bat runs desktop_qt/tools/check_text_cut.py; running it here catches a QML cut before anyone builds Qt
    (the collapsed-summary measurer of BookMetadataDetails.qml once failed it unnoticed)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_text_cut", ROOT / "desktop_qt/tools/check_text_cut.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    errors = [error for path in sorted((ROOT / "desktop_qt/qml").glob("*.qml")) for error in module.scan(path)]
    assert errors == []


def test_no_platform_cuts_the_author():
    found = []
    for path in sorted((ROOT / "desktop_qt/qml").glob("*.qml")):
        found += [f"{path.name}:{line}" for line in qml_findings(path.read_text(encoding="utf-8"))]
    for path in sorted((ROOT / "ui/src").rglob("*.tsx")):
        if ".test." not in path.name:
            found += [f"{path.name}:{line}" for line in line_findings(path.read_text(encoding="utf-8"), TSX_CUT)]
    for path in sorted((ROOT / "mobile/android/app/src/main/java").rglob("*.kt")):
        found += [f"{path.name}:{line}" for line in line_findings(path.read_text(encoding="utf-8"), KT_CUT)]
    assert found == [], "the author is cut; use OneLineFit (shrink, then wrap): " + ", ".join(found)
