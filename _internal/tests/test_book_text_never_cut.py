"""Book and user text (book title, chapter title, author, "· chương" of the primary button...) is never cut with "…" (left174).

DESIGN.md 5.5 "Tên một dòng": one line goes through OneLineFit (shrink to fit, else wrap at full size) on every platform.
The generic exemptions (`text-cut-ok` in QML, `cắt-có-chủ-ý` in Kotlin) cannot hide a cut of book text: the 0.4.173 bug
"Nghe tiếp · Chương 3: Một cái t…" on the Android book page sat behind such an exemption. The web side is
ui/src/shared/userTextClip.test.ts (BOOK_TEXT / BOOK_KEPT); Android TextCutScanTest.scanBookText runs the same rule in
Gradle. This file reads QML and Kotlin without a toolchain, so a cut is caught before anyone builds.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QML_BOOK = re.compile(r"\b(?:title|fullTitle|chapterTitle|bookTitle|displayTitle|subtitle|author|firstLine)\b")
QML_CUT = re.compile(r"\belide\s*:\s*Text\.Elide(?:Right|Left|Middle)\b|\bmaximumLineCount\s*:|\btruncate\s*:")
KT_BOOK = re.compile(r"\b(?:title|fullTitle|chapterTitle|bookTitle|author|subtitle|displayTitle|sub)\b")
KT_CUT = re.compile(r"\bmaxLines\s*=|TextOverflow\.(?:Ellipsis|Clip|StartEllipsis|MiddleEllipsis)|\bsoftWrap\s*=\s*false"
                    r"|\.(?:take|takeLast|drop|dropLast|substring)\s*\(")

# Cuts of book text that stay, one reason each - the same decision on all three platforms (left174 result.md).
QML_KEPT = {
    "BookCell.qml:TextWrap.keepDots(root.title)":
        "owner 15-11: library tiles in a row are the same height, the name under the cover is exactly 2 lines; full name on the book page",
    "MusicTrackRow.qml:TextWrap.keepDots(root.track.title || \"\")":
        "owner: music track titles at most 2 lines in music rows; the track sheet shows the full title",
}
KT_KEPT = {
    "LibraryScreen.kt:title": QML_KEPT["BookCell.qml:TextWrap.keepDots(root.title)"],
    "LibraryScreen.kt:sub": "status line built by the app (progress, chapter count), not book text; the author has its own OneLineFit line",
    "TrackRow.kt:track.title.ifEmpty { track.link.substringAfterLast('/') }": QML_KEPT["MusicTrackRow.qml:TextWrap.keepDots(root.track.title || \"\")"],
}


def qml_blocks(source: str):
    """(first line, text) of each innermost `Type { ... }` object block (comments dropped)."""
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


def qml_findings(name: str, source: str) -> list[str]:
    found = []
    for start, body in qml_blocks(source):
        texts = [m.group(1).strip() for m in re.finditer(r"^\s*text\s*:\s*(.+)$", body, re.M)]
        book = [text for text in texts if QML_BOOK.search(text)]
        if book and QML_CUT.search(body) and f"{name}:{book[0]}" not in QML_KEPT:
            found.append(f"{name}:{start} {book[0]}")
    return found


def kt_findings(name: str, source: str) -> list[str]:
    code = re.sub(r"(?s)/\*.*?\*/|//[^\n]*", lambda m: re.sub(r"[^\n]", " ", m.group(0)), source)
    found = []
    for match in re.finditer(r"\b(?:BasicText|Text|ClockLabel|WrapText)\s*\(", code):
        depth, index, quoted, escaped, first_end = 1, match.end(), False, False, -1
        while index < len(code) and depth:
            char = code[index]
            index += 1
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char in "({":
                depth += 1
            elif char in ")}":
                depth -= 1
                if depth == 0 and first_end < 0:
                    first_end = index - 1
            elif char == "," and depth == 1 and first_end < 0:
                first_end = index - 1
        call = code[match.start():index]
        first = code[match.end():index if first_end < 0 else first_end].strip()
        if KT_BOOK.search(first) and KT_CUT.search(call) and f"{name}:{first}" not in KT_KEPT:
            found.append(f"{name}:{source[:match.start()].count(chr(10)) + 1} {first}")
    return found


def test_detectors_catch_the_old_cuts_and_pass_fitted_text():
    # 0.4.173: the primary button's chapter sat behind a generic exemption
    old = ('// cắt-có-chủ-ý: nút một dòng\n'
           'BasicText("\\u00a0·\\u00a0" + sub, Modifier.weight(1f), style = ink, maxLines = 1, overflow = TextOverflow.Ellipsis)')
    assert len(kt_findings("BookScreen.kt", old)) == 1
    assert len(kt_findings("t.kt", "BasicText(chapter.title,\n maxLines = 1)")) == 1
    assert kt_findings("t.kt", 'BasicText("\\u00a0·\\u00a0" + sub, style = ink, autoSize = OneLineFit.of(ink))') == []
    assert kt_findings("t.kt", "BasicText(clock, maxLines = 1)") == []
    assert len(qml_findings("t.qml", "Text {\n  text: chapter.fullTitle\n  elide: Text.ElideRight // text-cut-ok: one line\n}")) == 1
    assert len(qml_findings("t.qml", "Text {\n  text: root.book.title\n  maximumLineCount: 1\n}")) == 1
    assert qml_findings("t.qml", "OneLineFit {\n  text: root.book.title\n  room: 100\n}") == []
    assert qml_findings("BookCell.qml", "Text {\n  text: TextWrap.keepDots(root.title)\n  maximumLineCount: 2\n}") == []


def test_no_platform_cuts_book_text():
    found = []
    for path in sorted((ROOT / "desktop_qt/qml").glob("*.qml")):
        found += qml_findings(path.name, path.read_text(encoding="utf-8"))
    for path in sorted((ROOT / "mobile/android/app/src/main/java").rglob("*.kt")):
        found += kt_findings(path.name, path.read_text(encoding="utf-8"))
    assert found == [], "book text is cut; use OneLineFit (shrink, then wrap): " + ", ".join(found)


def test_every_kept_cut_still_exists():
    """A kept cut that is gone (fixed) leaves the list, so the list never grows stale and hides a new cut."""
    sources = {path.name: path.read_text(encoding="utf-8") for path in (ROOT / "desktop_qt/qml").glob("*.qml")}
    sources.update({path.name: path.read_text(encoding="utf-8") for path in (ROOT / "mobile/android/app/src/main/java").rglob("*.kt")})
    for key in [*QML_KEPT, *KT_KEPT]:
        name, expression = key.split(":", 1)
        assert expression in sources.get(name, ""), key
