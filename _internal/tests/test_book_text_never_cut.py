"""Book and user text (book title, chapter title, author, "· chương" of the primary button...) is never cut with "…" (left174).

DESIGN.md 5.5 "Tên một dòng": one line goes through OneLineFit (shrink to fit, else wrap at full size) on every platform.
The generic exemptions (`text-cut-ok` in QML, `cắt-có-chủ-ý` in Kotlin) cannot hide a cut of book text: the 0.4.173 bug
"Nghe tiếp · Chương 3: Một cái t…" on the Android book page sat behind such an exemption. The web side is
ui/src/shared/userTextClip.test.ts (JSX tree + clip inventory); Android TextCutScanTest.scanBookText runs the same rule in
Gradle. This file reads QML and Kotlin without a toolchain, so a cut is caught before anyone builds.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Book text and user names (machine, phone, profile, voice, person, project): QML and Kotlin use the same words (leftfix L5).
NAMES = (r"title|fullTitle|chapterTitle|bookTitle|displayTitle|subtitle|author|firstLine|sub|subLine|statusText|source"
         r"|name|displayName|label|narrator")
QML_BOOK = re.compile(rf"\b(?:{NAMES})\b")
# `elide: wide ? Text.ElideNone : Text.ElideRight` cuts as well (leftfix review section 4).
QML_CUT = re.compile(r"\belide\s*:[^\n]*Text\.Elide(?:Right|Left|Middle)\b|\bmaximumLineCount\s*:|\btruncate\s*:")
KT_BOOK = re.compile(rf"\b(?:{NAMES})\b")
KT_CUT = re.compile(r"\bmaxLines\s*=|TextOverflow\.(?:Ellipsis|Clip|StartEllipsis|MiddleEllipsis)|\bsoftWrap\s*=\s*false"
                    r"|\.(?:take|takeLast|drop|dropLast|substring)\s*\(")

# Cuts of book text that stay, one reason each - the same decision on all three platforms (left174 result.md). Each key passes
# exactly ONCE (leftfix L4: a second Text with the same expression in the same file is a new cut, not the kept one).
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
    # Caught once `label` / `sub` joined the name words (leftfix L5); none of them cuts book or user text:
    "BookCover.kt:sub.uppercase()": "volume tag on a drawn cover: softWrap=false inside FitText (auto-size down to 2 sp), so it shrinks, never cuts",
    "LibraryChrome.kt:filter.label": "library filter chip: app vocabulary (Tất cả, Đang nghe...), not book text",
    "Shell.kt:tab.label": "bottom tab label: app vocabulary, not book text",
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


def kept_once(found: list[str], kept: list[tuple[str, int]]) -> list[str]:
    """Kept cuts pass once each; the second occurrence of the same key is reported."""
    seen: dict[str, int] = {}
    for key, line in kept:
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            name, expression = key.split(":", 1)
            found.append(f"{name}:{line} {expression} (second occurrence of a kept cut)")
    return found


def qml_findings(name: str, source: str) -> list[str]:
    found, kept = [], []
    for start, body in qml_blocks(source):
        texts = [m.group(1).strip() for m in re.finditer(r"^\s*text\s*:\s*(.+)$", body, re.M)]
        book = [text for text in texts if QML_BOOK.search(text)]
        if book and QML_CUT.search(body):
            if f"{name}:{book[0]}" in QML_KEPT:
                kept.append((f"{name}:{book[0]}", start))
            else:
                found.append(f"{name}:{start} {book[0]}")
    return kept_once(found, kept)


def split_arguments(args: str) -> list[str]:
    """Top-level arguments of a call (strings, nested calls and lambdas kept whole)."""
    depth, quoted, escaped, start, parts = 0, False, False, 0, []
    for index, char in enumerate(args):
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "({[":
            depth += 1
        elif char in ")}]":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(args[start:index])
            start = index + 1
    parts.append(args[start:])
    return [part.strip() for part in parts]


def call_end(code: str, start: int) -> int:
    """Index just after the `)` closing the call whose `(` ends at `start`."""
    depth, index, quoted, escaped = 1, start, False, False
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
        elif char in "({[":
            depth += 1
        elif char in ")}]":
            depth -= 1
    return index


def kt_findings(name: str, source: str) -> list[str]:
    code = re.sub(r"(?s)/\*.*?\*/|//[^\n]*", lambda m: re.sub(r"[^\n]", " ", m.group(0)), source)
    found, kept = [], []
    # Every text composable, including wrappers named *Text (RowText, HintText...).
    for match in re.finditer(r"\b(?:BasicText|Text|ClockLabel|WrapText|[A-Z]\w*Text)\s*\(", code):
        index = call_end(code, match.end())
        call = code[match.start():index]
        args = split_arguments(code[match.end():index - 1])
        # The text is the named argument `text = ...` wherever it stands, else the first positional argument (leftfix review section 4:
        # `BasicText(modifier = m, text = book.title, maxLines = 1)` slipped past a first-argument-only scan).
        named = [re.fullmatch(r"text\s*=\s*(.+)", arg, re.S) for arg in args]
        positional = [arg for arg in args if not re.match(r"[a-zA-Z_]\w*\s*=(?!=)", arg)]
        text = next((hit.group(1).strip() for hit in named if hit), positional[0] if positional else "")
        if KT_BOOK.search(text) and KT_CUT.search(call):
            line = source[:match.start()].count("\n") + 1
            if f"{name}:{text}" in KT_KEPT:
                kept.append((f"{name}:{text}", line))
            else:
                found.append(f"{name}:{line} {text}")
    return kept_once(found, kept)


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


def test_detectors_close_the_holes_found_by_the_leftfix_review():
    # named `text =` argument, anywhere in the call
    assert len(kt_findings("t.kt", "BasicText(modifier = Modifier, text = book.title, maxLines = 1)")) == 1
    assert len(kt_findings("t.kt", "BasicText(\n  style = ink,\n  text = project.name,\n  overflow = TextOverflow.Ellipsis)")) == 1
    assert kt_findings("t.kt", "BasicText(modifier = Modifier, text = clock, maxLines = 1)") == []
    # wrappers named *Text and names (person, project, machine)
    assert len(kt_findings("t.kt", "RowText(character.name, maxLines = 1)")) == 1
    # QML: conditional elide and names / sub lines (symmetric with Kotlin)
    assert len(qml_findings("t.qml", "Text {\n  text: root.subLine\n  elide: wide ? Text.ElideNone : Text.ElideRight\n}")) == 1
    assert len(qml_findings("t.qml", "Text {\n  text: modelData.name\n  maximumLineCount: 1\n}")) == 1
    assert QML_BOOK.pattern == KT_BOOK.pattern
    # a kept cut passes once; a second Text with the same expression in the same file is a new cut
    kept = "Text {\n  text: TextWrap.keepDots(root.title)\n  maximumLineCount: 2\n}\n"
    assert len(qml_findings("BookCell.qml", kept + kept)) == 1
    tile = "BasicText(title, maxLines = 2, overflow = TextOverflow.Ellipsis)\n"
    assert kt_findings("LibraryScreen.kt", tile) == []
    assert len(kt_findings("LibraryScreen.kt", tile + tile)) == 1


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
