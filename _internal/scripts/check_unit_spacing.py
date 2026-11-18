"""Reject a number and its unit joined by a breakable space: "97 %" must never wrap into "97" / "%".

DESIGN.md "Số và đơn vị": a visible number and its unit (%, time, size, frequency, level, tempo) are joined by U+00A0 on
web, Android and Qt. The rule covers the shared catalog (ui_strings/vi.json), text built in client code, and text the
Python server builds for the app (errors, progress, the technical log the app shows, notifications).

What is not visible copy, and why it is told apart by its shape rather than by a list of exceptions:
- client code: spoken readings for the voice engine (Android vieneu/), developer tools (ui/src/perf/), log calls;
- server code: docstrings and bare string statements (documentation), arguments of `print`, the `logging` module and
  `warnings.warn` (they go to the console or a log file, never to the app), English text (the app speaks only
  Vietnamese - one catalog, vi.json - so English server text is for developers: asserts, internal errors), and a number
  already read out as words for the voice engine (`vietnamese_number(h) + " giờ"`), where nothing can break off a digit.
"""
from pathlib import Path
import ast
import json
import re

ROOT = Path(__file__).resolve().parents[1]
NBSP = "\u00A0"
UNITS = ("%", "giờ", "phút", "giây", "ms", "KB", "MB", "GB", "TB", "kHz", "Hz", "dBFS", "dB", "s", "nhịp/phút")
_UNIT = "(?:" + "|".join(re.escape(unit) for unit in UNITS) + r")(?![\wÀ-ỹ-])"
# Inside one piece of copy: a digit or a value slot ({0}, %1, ${x}, $x, %d, %.1f, %(name)s) then a plain space then a unit.
_SLOT = r"(?:\d|\}|\$[A-Za-z_]\w*|%(?:\(\w+\))?[-+#0]*\d*(?:\.\d+)?[sdfgi])"
INNER = re.compile(_SLOT + "( )" + _UNIT)
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

# Server code: the shipped Python package and its entry point; vendored libraries are not ours.
SERVER = ("abook", "app.py")
VENDORED = ("abook/vendor/", "abook/_vendor/")
VIETNAMESE = re.compile(r"[À-ỹĐđ]")
ENGLISH_WORD = re.compile(r"\b[a-z]{3,}\b")
LOG_LEVELS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}
# A function that reads a number out as words for the voice engine (vietnamese_number, integer_reading...).
READING = re.compile(r"^vietnamese_number|_reading$")


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


def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _loggers(tree: ast.AST) -> set[str]:
    """Names bound to a `logging.getLogger(...)` logger in this module (`LOG = logging.getLogger(__name__)`)."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and _name(node.value.func) == "getLogger":
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return names


def _developer_output(call: ast.Call, loggers: set[str]) -> bool:
    """`print(...)`, `logging.x(...)`, `logger.x(...)`, `logging.getLogger(..).x(...)`, `warnings.warn(...)`, `sys.stderr.write(...)`."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id == "print"
    if not isinstance(func, ast.Attribute):
        return False
    owner = func.value
    if func.attr == "warn" and _name(owner) == "warnings":
        return True
    if func.attr == "write" and _name(owner) in ("stderr", "stdout"):
        return True
    if func.attr not in LOG_LEVELS:
        return False
    if isinstance(owner, ast.Call):
        return _name(owner.func) == "getLogger"
    return isinstance(owner, ast.Name) and (owner.id == "logging" or owner.id in loggers)


def _reads_aloud(node: ast.AST) -> bool:
    """The value is a number already read out as words (`vietnamese_number(h)`, `x if x else 'không'`)."""
    return any(isinstance(part, ast.Call) and READING.search(_name(part.func)) for part in ast.walk(node))


def _rightmost(node: ast.AST) -> ast.AST:
    while isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        node = node.right
    return node


def _text(node: ast.AST) -> str:
    if isinstance(node, ast.Constant):
        return node.value
    return "".join(part.value if isinstance(part, ast.Constant) else "chữ" if _reads_aloud(part) else "{}" for part in node.values)


def visible_text(text: str) -> bool:
    """Server text the app can show: Vietnamese, or bare figures ("15 MB", "{} GB"). English sentences are developer text."""
    return bool(VIETNAMESE.search(text)) or not ENGLISH_WORD.search(text)


def python_lines(source: str) -> list[int]:
    """Lines of server code whose visible copy joins a number and its unit with a plain space."""
    tree = ast.parse(source)
    loggers = _loggers(tree)
    skipped: set[int] = set()
    spoken: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, (ast.Constant, ast.JoinedStr)):
            skipped.add(id(node.value))
        elif isinstance(node, ast.Call) and _developer_output(node, loggers):
            skipped.update(id(part) for part in ast.walk(node))
        elif isinstance(node, ast.JoinedStr):
            skipped.update(id(part) for part in node.values)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add) and _reads_aloud(_rightmost(node.left)):
            spoken.add(id(node.right))
    found = set()
    for node in ast.walk(tree):
        if id(node) in skipped:
            continue
        if not (isinstance(node, ast.JoinedStr) or isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        text = _text(node)
        if not visible_text(text):
            continue
        if INNER.search(text) or (id(node) not in spoken and LEADING.search(text)):
            found.add(node.lineno)
    return sorted(found)


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


def server_sources():
    paths = list((ROOT / SERVER[0]).rglob("*.py")) + [ROOT / SERVER[1]]
    for path in sorted(paths):
        name = path.relative_to(ROOT).as_posix()
        if not name.startswith(VENDORED):
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
    for name, path in server_sources():
        for line in python_lines(path.read_text(encoding="utf-8")):
            yield f"{name}:{line}: server copy joins a number and its unit with a plain space (use \\u00a0)"


def main():
    found = list(findings())
    print("\n".join(found)) if found else None
    print(f"Number-unit spacing audit: {len(found)} violations")
    return bool(found)


if __name__ == "__main__":
    raise SystemExit(main())
