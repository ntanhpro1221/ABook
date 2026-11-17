"""Reject a number and its unit joined by a breakable space: "97 %" must never wrap into "97" / "%".

DESIGN.md "Số và đơn vị": a visible number and its unit (%, time, size, frequency, level, tempo) are joined by U+00A0 on
web, Android and Qt. The rule covers the shared catalog (ui_strings/vi.json) and text built in code; spoken text for the
voice engine and log lines are not visible copy.
"""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
NBSP = "\u00a0"
UNITS = ("%", "giờ", "phút", "giây", "ms", "KB", "MB", "GB", "TB", "kHz", "Hz", "dBFS", "dB", "s", "nhịp/phút")
_UNIT = "(?:" + "|".join(re.escape(unit) for unit in UNITS) + r")(?![\wÀ-ỹ-])"
# Inside one piece of copy: a digit or a value slot ({0}, %1, ${x}, $x) then a plain space then a unit.
INNER = re.compile(r"(?:\d|\}|\$[A-Za-z_]\w*)( )" + _UNIT)
# A fragment appended after a value in code ("x + ' %'", S.s_phut = " phút").
LEADING = re.compile(r"^( )" + _UNIT)
LITERAL = re.compile(r'"(?:[^"\\\n]|\\.)*"|`(?:[^`\\]|\\.)*`|\'(?:[^\'\\\n]|\\.)*\'')
# JSX text after an expression: <span>{value} %</span>.
JSX = re.compile(r"\}( )" + _UNIT + r"(?=\s*(?:<|$))")
GENERATED = {"UiStrings.kt", "strings.generated.ts", "UiStrings.js", "uistrings.generated.h"}
# Spoken readings for the voice engine and developer-only tools are not visible copy.
SKIPPED = ("mobile/android/app/src/main/java/vn/abook/player/vieneu/", "ui/src/perf/")
# A JSX attribute string is not a JavaScript string: suffix="\u00a0dBFS" renders the six characters \u00a0, which no
# space rule can see. Escapes belong in an expression (suffix={DBFS} or suffix={"\u00a0dBFS"}). The lookbehinds and
# the trailing guard keep TypeScript assignments (const raw='a\nb';, f(a="\n")) out.
JSX_ESCAPE = re.compile(
    r"(?<![\w.$])(?<!const )(?<!let )(?<!var )[A-Za-z_][\w-]*=([\"'])(?:(?!\1)[^\n\\])*"
    r"\\(?:u[0-9a-fA-F{]|x[0-9a-fA-F]{2}|[ntr0])(?:(?!\1)[^\n])*\1(?!\s*[;,)])"
)
LOG = re.compile(r"\b(?:AppLog|Log)\.[a-z]\(|console\.(?:log|warn|error)\(|qDebug\(|qWarning\(")


def join(text: str) -> str:
    """The same copy with every number-unit space made non-breaking."""
    text = INNER.sub(lambda match: match.group(0).replace(" ", NBSP, 1), text)
    return LEADING.sub(lambda match: NBSP + match.group(0)[1:], text)


def breaks(text: str) -> bool:
    return bool(INNER.search(text) or LEADING.search(text))


def source_lines(source: str, jsx: bool) -> list[int]:
    found = []
    for number, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith(("//", "*", "/*", "#")) or LOG.search(line):
            continue
        code = line.split(" //", 1)[0]
        if any(breaks(literal[1:-1]) for literal in LITERAL.findall(code)) or (jsx and JSX.search(code)):
            found.append(number)
    return found


def jsx_escape_lines(source: str) -> list[int]:
    """Lines whose JSX attribute string holds a JavaScript escape that JSX will print literally."""
    found = []
    for number, line in enumerate(source.splitlines(), 1):
        if line.strip().startswith(("//", "*", "/*")):
            continue
        if JSX_ESCAPE.search(line.split(" //", 1)[0]):
            found.append(number)
    return found


def sources():
    paths = list((ROOT / "ui/src").rglob("*.ts")) + list((ROOT / "ui/src").rglob("*.tsx"))
    paths += list((ROOT / "desktop_qt/qml").glob("*.qml")) + list((ROOT / "desktop_qt/qml").glob("*.js"))
    paths += list((ROOT / "desktop_qt/src").glob("*.cpp")) + list((ROOT / "desktop_qt/src").glob("*.h"))
    paths += list((ROOT / "mobile/android/app/src/main/java").rglob("*.kt"))
    for path in sorted(paths):
        name = path.relative_to(ROOT).as_posix()
        if path.name in GENERATED or ".test." in path.name or name.startswith(SKIPPED):
            continue
        yield name, path


def findings():
    catalog = json.loads((ROOT / "ui_strings/vi.json").read_text(encoding="utf-8"))["strings"]
    for key, value in catalog.items():
        if breaks(value):
            yield f"ui_strings/vi.json {key}: {value!r} joins a number and its unit with a plain space (use U+00A0)"
    for name, path in sources():
        for line in source_lines(path.read_text(encoding="utf-8"), path.suffix == ".tsx"):
            yield f"{name}:{line}: a number and its unit are joined by a plain space (use \\u00a0)"
        if path.suffix == ".tsx":
            for line in jsx_escape_lines(path.read_text(encoding="utf-8")):
                yield f"{name}:{line}: a JSX attribute string prints its escape literally (write it as {{\"...\"}} or a constant)"


def main():
    found = list(findings())
    print("\n".join(found)) if found else None
    print(f"Number-unit spacing audit: {len(found)} violations")
    return bool(found)


if __name__ == "__main__":
    raise SystemExit(main())
