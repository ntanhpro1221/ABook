"""Two layout rules of the Qt desktop app, checked in the source (Lead's review of the 0.4.151 shots).

1. A separator never starts or ends a line (the web's LINE BREAK rule; the web glues every text node with installKeepDots, Android
   hides a dot at a line end): strings join pieces with "\\u00a0·\\u00a0", the dot bound to both pieces, never " · " or "\\u00a0· ".
   tests/width/Separators.js catches the wrapped result on every rendered scene; this catches the string before it ever wraps.
2. Floating layers wear the shared Shadow.qml (Gaussian, web shadow tokens), never stacked translucent black Rectangles that
   paint as a staircase.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / "desktop_qt"


def string_literals(source: str):
    """(line, body) of every "..." / '...' / `...` literal in JS/QML/C++ source, skipping // and /* */ comments."""
    i, n, line = 0, len(source), 1
    while i < n:
        c = source[i]
        if source.startswith("//", i):
            end = source.find("\n", i)
            i = n if end < 0 else end
            continue
        if source.startswith("/*", i):
            end = source.find("*/", i + 2)
            line += source.count("\n", i, n if end < 0 else end)
            i = n if end < 0 else end + 2
            continue
        if c in "\"'`":
            j, start = i + 1, line
            while j < n and source[j] != c and (c == "`" or source[j] != "\n"):
                j += 2 if source[j] == "\\" else 1
            yield start, source[i + 1:j]
            line += source.count("\n", i, j)
            i = j + 1
            continue
        if c == "\n":
            line += 1
        i += 1


def sources():
    yield from sorted((ROOT / "qml").glob("*.qml"))
    yield from sorted((ROOT / "qml").glob("*.js"))
    yield from sorted((ROOT / "src").glob("*.cpp"))


def test_separators_are_bound_to_both_pieces():
    # a plain space on either side of the dot (" · ", "\u00a0· "), also across a RichText tag (" <span ...>· "), and a piece that
    # STARTS with "·": glued after a string this cannot see, or a lone Flow piece that leads the row once the Flow wraps (FlowDetail
    # drops its dot there)
    bare = [f"{path.name}:{line}: {body!r}" for path in sources() if path.name != "FlowDetail.qml"
            for line, body in string_literals(path.read_text(encoding="utf-8"))
            if re.search(r"[ \t](<[^<>]*>)*·|·(<[^<>]*>)*[ \t]|^\s*·", body)]
    assert not bare, ("dùng \"\\u00a0·\\u00a0\" (dấu ngăn dính cả hai mảnh, không bao giờ đứng đầu hay cuối dòng) hay FlowDetail:\n"
                      + "\n".join(bare))


def styled_blocks(source: str):
    """(first line, text) of every QML object block that sets textFormat: Text.StyledText (also conditionally)."""
    lines = source.split("\n")
    for i, line in enumerate(lines):
        if "textFormat:" not in line or "Text.StyledText" not in line:
            continue
        indent = len(line) - len(line.lstrip())
        start = next(j for j in range(i, -1, -1) if lines[j].rstrip().endswith("{") and len(lines[j]) - len(lines[j].lstrip()) < indent)
        outer = len(lines[start]) - len(lines[start].lstrip())
        end = next((j for j in range(i, len(lines)) if lines[j].strip().startswith("}") and len(lines[j]) - len(lines[j].lstrip()) == outer), len(lines))
        yield start + 1, "\n".join(lines[start:end + 1])


def test_markup_spells_the_bound_separator_as_an_entity():
    """StyledText (explicit, or AutoText that sees a tag) folds a real U+00A0 into a plain space, so "\\u00a0· " breaks before the dot
    again there (measured: "Đang làm dở\\u00a0· 3/10" wraps "· 3/10" onto line 2; "&nbsp;· " stays put; RichText keeps both). In markup
    the separator is "&nbsp;·&nbsp;": literals on a line that builds tags, every Text.StyledText block, and every esc()/escapeHtml() that
    carries plain text into markup."""
    nb = "\\u00a0"
    tagged = [f"{path.name}:{line}" for path in [*sorted((ROOT / "qml").glob("*.qml")), *sorted((ROOT / "qml").glob("*.js"))]
              for line, text in enumerate(path.read_text(encoding="utf-8").split("\n"), 1)
              if nb in text and not text.lstrip().startswith("//")
              and any(re.search(r"<[a-zA-Z/]", body) for _, body in string_literals(text))]
    styled = [f"{path.name}:{start}" for path in sorted((ROOT / "qml").glob("*.qml"))
              for start, block in styled_blocks(path.read_text(encoding="utf-8"))
              if any(nb in body for _, body in string_literals(block))]
    escapes = [f"{path.name}:{line}" for path in [*sorted((ROOT / "qml").glob("*.qml")), *sorted((ROOT / "qml").glob("*.js"))]
               for source in [path.read_text(encoding="utf-8").split("\n")]
               for line, text in enumerate(source, 1) if re.search(r"function (esc|escapeHtml)\(", text)
               and "&nbsp;" not in text + (source[line] if line < len(source) else "")]
    assert not tagged + styled + escapes, ("trong markup viết \"&nbsp;·&nbsp;\", không phải \"\\u00a0·\\u00a0\" (StyledText gộp NBSP thành dấu cách): "
                                           + ", ".join(tagged + styled + escapes))


def test_string_scanner_skips_comments_and_reads_escapes():
    found = list(string_literals('a = "x · y" // "b · c"\n/* "d · e" */ f = "g\\u00a0· h"'))
    assert [body for _, body in found] == ["x · y", "g\\u00a0· h"]


def test_floating_layers_use_the_shared_shadow():
    fake = re.compile(r'Rectangle\s*\{[^{}\n]*anchors\.margins:\s*-\d[^{}\n]*color:\s*"#000000"[^{}\n]*opacity')
    offenders = [f"{path.name}:{source[:m.start()].count(chr(10)) + 1}" for path in sorted((ROOT / "qml").glob("*.qml"))
                 for source in [path.read_text(encoding="utf-8")] for m in fake.finditer(source)]
    assert not offenders, "bóng giả bằng Rectangle đen mờ chồng nhau (thành bậc thang) - dùng Shadow {}: " + ", ".join(offenders)
    for name in ["Modal.qml", "Popover.qml", "ConnectionPopover.qml", "Select.qml", "Toast.qml"]:
        assert re.search(r"\bShadow\s*\{", (ROOT / "qml" / name).read_text(encoding="utf-8")), name


def test_load_errors_use_the_shared_inline_error():
    """3. Every load error is InlineError.qml (warning triangle, grey sentence, ghost "Thử lại"): no hand-built copy of it, and no
    sentence dressed up as a ghost button ("Bạn hãy thử tải lại tiến độ." in gold that wrapped "tiến / độ." at the sidebar)."""
    own = {"InlineError.qml", "PlayerAlert.qml"}  # PlayerAlert: the player's alert with several actions, its own pattern on the web too
    copies = [path.name for path in sorted((ROOT / "qml").glob("*.qml")) if path.name not in own
              for source in [path.read_text(encoding="utf-8")] if '"triangle-alert"' in source and 'text: "Thử lại"' in source]
    assert not copies, "lỗi tải tự dựng - dùng InlineError {}: " + ", ".join(copies)
    dressed = [f"{path.name}:{line}" for path in sorted((ROOT / "qml").glob("*.qml"))
               for line, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
               if "Button" in text and re.search(r'text:\s*"Bạn hãy[^"]*tải lại', text)]
    assert not dressed, "câu báo lỗi đặt làm chữ của nút - dùng InlineError {}: " + ", ".join(dressed)


def text_blocks(source: str):
    """(line, block) of every `Text { ... }` object in QML source, braces matched outside string literals."""
    for m in re.finditer(r"(?<![\w.])Text\s*\{", source):
        depth, i, quote = 0, m.end() - 1, None
        while i < len(source):
            c = source[i]
            if quote:
                if c == "\\":
                    i += 1
                elif c == quote:
                    quote = None
            elif c in "\"'`":
                quote = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        yield source[:m.start()].count("\n") + 1, source[m.start():i + 1]


DATA_TEXT = re.compile(r"\btext:[^\n;]*\.(title|bookTitle|chapterTitle|fullTitle|lastChapter|name|author|subtitle)\b")


def test_wrapping_titles_keep_their_dots():
    """4. Free text from the data ("Thành Phố Sương Mù · Tập 2" in the sidebar wrapped "·" onto the end of line 1, gallery 01-11) may
    carry a " · " the app did not write: a Text that wraps and shows a title, name or author goes through TextWrap.keepDots (or
    TextWrap.pretty, which keeps dots too), like installKeepDots on the web."""
    loose = [f"{path.name}:{line}" for path in sorted((ROOT / "qml").glob("*.qml"))
             for line, block in text_blocks(path.read_text(encoding="utf-8"))
             if re.search(r"wrapMode:\s*Text\.(Wrap|WordWrap|WrapAnywhere|WrapAtWordBoundaryOrAnywhere)\b", block)
             and (hit := DATA_TEXT.search(block)) and not re.search(r"\b(keepDots|pretty)\(", hit.group(0))]
    assert not loose, "Text xuống dòng hiện tên / tiêu đề phải qua TextWrap.keepDots(...): " + ", ".join(loose)


def test_text_block_scanner_matches_braces_outside_strings():
    blocks = list(text_blocks('Item {\n    Text { text: "a { b"; wrapMode: Text.Wrap }\n    Text {\n        text: x.title\n    }\n}'))
    assert [line for line, _ in blocks] == [2, 3]
    assert blocks[0][1].endswith("Text.Wrap }") and blocks[1][1].endswith("x.title\n    }")
