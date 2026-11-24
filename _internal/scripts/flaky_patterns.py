"""Inventory load-sensitive test constructs; ratchet individual sites, not a total budget.

Findings are review candidates, not proof of a flake. In particular wall clocks under
fake timers, condition polling and protocol deadlines can be intentional. Existing
sites are recorded explicitly; a new file/site cannot spend another site's allowance.
"""
from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import re

INTERNAL = Path(__file__).resolve().parents[1]
BASELINE = INTERNAL / "tests/fixtures/flaky_patterns.json"
# Hai file Android mà nhánh dev/tlsleak đang viết lại (timer TLS): luật hạn-giờ-thật bỏ qua chúng để hai nhánh không xung đột.
# Bỏ khỏi danh sách này (và sửa hai file theo docs/WALLCLOCK_TESTS.md) khi tlsleak đã vào.
WALLCLOCK_DEFERRED = {
    "mobile/android/app/src/test/java/vn/abook/player/TlsRouteResolverTest.kt",
    "mobile/android/app/src/test/java/vn/abook/player/net/FastConnectTest.kt",
}
WALLCLOCK_RULES = {"elapsed-bound", "fixed-deadline", "raw-waitfor", "qt-visual-wall-wait", "qt-literal-timeout", "qt-fuzzy-settle"}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    code: str

    @property
    def key(self):
        return f"{self.path}|{self.rule}|{self.code}"


def test_files(root=INTERNAL):
    paths = set((root / "tests").rglob("*.py"))
    paths.update((root / "desktop_qt/tests").rglob("*.py"))
    for directory in ("scripts", "desktop_qt/tools"):
        paths.update((root / directory).rglob("test_*.py"))
    for path in (root / "mobile/android").glob("*/src/test/**/*.kt"):
        paths.add(path)
    for directory in ("ui/src", "ui/scripts", "ui/tests"):
        for path in (root / directory).rglob("*"):
            if path.is_file() and re.search(r"\.(?:test|spec)\.[cm]?[jt]sx?$", path.name):
                paths.add(path)
    paths.update(p for p in (root / "desktop_qt/tests").rglob("*") if p.suffix in {".qml", ".cpp", ".js"})
    return sorted(paths)


def suffix_of(relative, suffix):
    """QML test helper libraries (desktop_qt/tests/**/*.js) follow the QML rules plus the helper-only ones."""
    return ".qtjs" if suffix == ".js" and relative.startswith("desktop_qt/tests/") else suffix


def _name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _name(node.value) + "." + node.attr
    return ""


def python_patterns(text):
    tree = ast.parse(text)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    aliases = {}
    constants = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            aliases.update((a.asname or a.name, a.name) for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            aliases.update((a.asname or a.name, f"{node.module}.{a.name}") for a in node.names)
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            constants.update((t.id, node.value.value) for t in node.targets if isinstance(t, ast.Name))

    def resolve(node):
        head, *tail = _name(node).split(".")
        return ".".join([aliases.get(head, head), *tail])

    def value(node):
        if isinstance(node, ast.Name):
            return constants.get(node.id)
        if isinstance(node, (ast.Tuple, ast.List)):
            return tuple(value(item) for item in node.elts)
        try:
            return ast.literal_eval(node)
        except (ValueError, TypeError):
            return None

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _name(node.func)
        head, *tail = name.split(".")
        name = ".".join([aliases.get(head, head), *tail])
        code = ast.unparse(node)
        rules = []
        if name in {"time.sleep", "asyncio.sleep"}:
            rules.append("fixed-delay")
        if name in {"time.time", "datetime.datetime.now", "datetime.datetime.utcnow", "datetime.now", "datetime.utcnow"}:
            rules.append("wall-clock")
        if name in {"time.monotonic", "time.perf_counter", "time.monotonic_ns", "time.perf_counter_ns"}:
            rules.append("elapsed-clock")
        string_join = isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Constant) \
            and isinstance(node.func.value.value, str)
        if name.endswith((".wait", ".join", ".result")) and not string_join:
            duration = next((k.value for k in node.keywords if k.arg == "timeout"), node.args[0] if node.args else None)
            seconds = value(duration)
            if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) and 0 < seconds <= 1:
                rules.append("short-thread-timeout")
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Call) and _name(node.func.value.func).endswith("Event"):
                rules.append("fixed-delay")
        if name.endswith((".bind", ".create_server", "HTTPServer", "TCPServer", "ThreadingHTTPServer")) and node.args:
            address = value(node.args[0])
            if isinstance(address, tuple) and len(address) >= 2 and isinstance(address[1], int) and address[1] != 0:
                rules.append("fixed-listener-port")
            if isinstance(node.args[0], ast.Tuple) and len(node.args[0].elts) >= 2:
                port = node.args[0].elts[1]
                if isinstance(port, ast.Call) and _name(port.func).endswith(".stable_port"):
                    rules.append("fixed-listener-port")
        if name in {"tempfile.gettempdir", "tempfile.mktemp"}:
            rules.append("shared-temp")
        if name in {"os.chdir", "random.seed", "socket.setdefaulttimeout"}:
            rules.append("process-state")
        for rule in rules:
            yield node.lineno, rule, code
    lines = text.splitlines()
    yield from _wallclock_bounds(tree, resolve, lines)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        value_node = node.value
        if not (isinstance(value_node, ast.Subscript) and isinstance(value_node.value, ast.Call)):
            continue
        call = value_node.value
        if not (isinstance(call.func, ast.Attribute) and call.func.attr == "getsockname" and isinstance(call.func.value, ast.Name)):
            continue
        port, sock = node.targets[0].id, call.func.value.id
        scope = parents.get(node)
        context = None
        while scope is not None and not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            if isinstance(scope, ast.With) and any(isinstance(i.optional_vars, ast.Name) and i.optional_vars.id == sock for i in scope.items):
                context = scope
            scope = parents.get(scope)
        if scope is None:
            continue
        uses = [n.lineno for n in ast.walk(scope) if isinstance(n, ast.Name) and n.id == port and isinstance(n.ctx, ast.Load) and n.lineno > node.lineno]
        closes = [n.lineno for n in ast.walk(scope) if isinstance(n, ast.Call) and _name(n.func) == f"{sock}.close" and n.lineno > node.lineno]
        if context:
            closes.append(context.end_lineno)
        if uses and closes and min(closes) < min(uses):
            yield node.lineno, "released-port", ast.unparse(node) + f"; {sock} closed before first use"


CLOCKS = {"time.time", "time.monotonic", "time.perf_counter"}
# Dòng ghi dấu này được bỏ qua: nó nói rõ vì sao ngưỡng giờ thật ở đó là đúng (dòng nào cũng phải có lý do sau dấu).
WALLCLOCK_OK = re.compile(r"wallclock-ok: \S")


def _wallclock_bounds(tree, resolve, lines):
    """Hạn theo giờ thật phải đi qua tests/timing.py (nhân hệ số máy tải), không rải ngưỡng cứng trong test.

    elapsed-bound: so một khoảng thời gian đã trôi (đồng hồ - mốc, hay biến lấy từ đó) với cận TRÊN - "xong trong 2 giây".
    fixed-deadline: `đồng hồ + hằng số` (hạn chờ một điều kiện). Cận dưới (`>= 0.09`: đã chờ thật) không bị cấm.
    """
    def clock(node):
        return isinstance(node, ast.Call) and resolve(node.func) in CLOCKS

    def has_clock(node):
        return any(clock(n) for n in ast.walk(node))

    def uses_scale(node):
        return any(isinstance(n, ast.Call) and _name(n.func).split(".")[-1] in {"scaled", "deadline"} for n in ast.walk(node))

    def exempt(line):
        return 0 < line <= len(lines) and WALLCLOCK_OK.search(lines[line - 1])

    scopes = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module))]
    seen = set()
    for scope in scopes:
        tainted = {t.id for n in ast.walk(scope) if isinstance(n, ast.Assign) and isinstance(n.value, ast.BinOp)
                   and isinstance(n.value.op, ast.Sub) and has_clock(n.value.left) for t in n.targets if isinstance(t, ast.Name)}

        def timed(node):
            return (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub) and has_clock(node.left)) or (
                isinstance(node, ast.Name) and node.id in tainted)

        for node in ast.walk(scope):
            if id(node) in seen:
                continue
            if isinstance(node, ast.Compare):
                operands = [node.left, *node.comparators]
                for i, operand in enumerate(operands):
                    upper = (i < len(node.ops) and isinstance(node.ops[i], (ast.Lt, ast.LtE)) and operands[i + 1]) or (
                        i > 0 and isinstance(node.ops[i - 1], (ast.Gt, ast.GtE)) and operands[i - 1])
                    if timed(operand) and upper is not False and not uses_scale(upper) and not exempt(node.lineno):
                        seen.add(id(node))
                        yield node.lineno, "elapsed-bound", ast.unparse(node)
                        break
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                for near, far in ((node.left, node.right), (node.right, node.left)):
                    number = isinstance(far, ast.Constant) and isinstance(far.value, (int, float))
                    if clock(near) and (number or isinstance(far, ast.Name)):
                        if not uses_scale(far) and not exempt(node.lineno):
                            seen.add(id(node))
                            yield node.lineno, "fixed-deadline", ast.unparse(node)
                        break


def masked(text):
    """Mask comments and strings, preserving offsets/newlines for call matching."""
    pattern = r'//[^\n]*|/\*[\s\S]*?\*/|"""[\s\S]*?"""|"(?:\\.|[^"\\])*"|\x27(?:\\.|[^\x27\\])*\x27|`(?:\\.|[^`\\])*`'
    return re.sub(pattern, lambda m: re.sub(r"[^\n]", " ", m.group()), text)


QT_TIMED_CALL = re.compile(r"(?<![\w$])(tryVerify|tryCompare|waitForPolish|waitForRendering|waitForItemPolished)\s*\(")
QT_TIMEOUT_ARG = {"tryVerify": 1, "tryCompare": 3, "waitForPolish": 1, "waitForRendering": 1, "waitForItemPolished": 1}


def _call_args(code, start):
    """Top-level arguments of the call whose '(' ends at `start` (strings/comments already masked)."""
    depth, args, begin = 0, [], start
    for index in range(start, len(code)):
        char = code[index]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            if depth == 0:
                args.append(code[begin:index].strip())
                return args, index
            depth -= 1
        elif char == "," and depth == 0:
            args.append(code[begin:index].strip())
            begin = index + 1
    return args, len(code)


def qt_wait_patterns(code, suffix):
    # Qt Quick tests (build 0.4.174): a fixed real-time wait for visual transitions ran out under load (VisualReady.js
    # waited 5 s for settled()). Transitions step the test animation clock through VisualReady.waitSettled /
    # probe.finishTransitions; a helper's real-time bound goes through probe.ms (TestTiming), C++ through TestTiming::ms.
    if suffix in {".qml", ".qtjs"}:
        for match in QT_TIMED_CALL.finditer(code):
            args, end = _call_args(code, match.end())
            call = code[match.start():end]
            if match[1] in {"tryVerify", "tryCompare"} and re.search(r"\bsettled\s*\(|\.settled\b", call) and "finishTransitions" not in call:
                yield match.start(), "qt-visual-wall-wait"
            index = QT_TIMEOUT_ARG[match[1]]
            if suffix == ".qtjs" and len(args) > index and re.fullmatch(r"\d+", args[index]):
                yield match.start(), "qt-literal-timeout"
    elif suffix == ".cpp":
        for match in re.finditer(r"\bQTRY_\w+_WITH_TIMEOUT\s*\(", code):
            args, _ = _call_args(code, match.end())
            if args and re.fullmatch(r"\d+", args[-1]):
                yield match.start(), "qt-literal-timeout"


# QML compare()/tryCompare() accept numbers within 1e-5 (Qt TestCase.qml qtest_compareInternal), so waiting for an animated
# progress to reach its end value 0/1 passes while the animation is still running (0.4.176 build: NowPlaying p = 0.999994,
# the next click was swallowed when the animation ended). Wait for the exact end: tryVerify(() => item.p === 1).
QT_FUZZY_SETTLE = re.compile(r'(?<![\w$])tryCompare\s*\([^,()]+,\s*"(?:p|g|t|shown|progress|reveal|openT|pageT|wideT)"\s*,\s*[01](?:\.0*)?\s*\)')


def other_patterns(text, suffix):
    code = masked(text)
    if suffix in {".qml", ".qtjs"}:
        for match in QT_FUZZY_SETTLE.finditer(text):
            if code[match.start():match.start() + 10] != "tryCompare":
                continue  # inside a comment or string
            line = text.count("\n", 0, match.start()) + 1
            snippet = text.splitlines()[line - 1].strip()
            if not WALLCLOCK_OK.search(snippet):
                yield line, "qt-fuzzy-settle", snippet
    rules = {
        "fixed-delay": r"\bThread\s*\.\s*sleep\s*\(" if suffix == ".kt" else r"(?<![\w.])(?:setTimeout|setInterval)\s*\(",
        "wall-clock": r"\bSystem\s*\.\s*currentTimeMillis\s*\(" if suffix == ".kt" else r"\bDate\s*\.\s*now\s*\(|\bnew\s+Date\s*\(\s*\)",
        "elapsed-clock": r"\bSystem\s*\.\s*nanoTime\s*\(" if suffix == ".kt" else r"\bperformance\s*\.\s*now\s*\(",
        "fixed-listener-port": r"\bServerSocket\s*\(\s*[1-9]\d*\b",
        "shared-temp": r"\bFile\s*\(\s*System\s*\.\s*getProperty\s*\(" if suffix == ".kt" else r"\b(?:tmpdir|tmpName|mktemp)\s*\(",
        "released-port": r"\bServerSocket\s*\([^\n]*\)\s*\.use\s*\{\s*it\.localPort\s*\}",
    }
    # Hạn chờ theo giờ thật phải qua hệ số máy tải (Kotlin: TestTime.ms/nanos/seconds, web: scaledMs/eventually), không ngưỡng trần.
    # Dòng ghi `wallclock-ok: <lý do>` được bỏ qua.
    if suffix == ".kt":
        clock = r"\bSystem\s*\.\s*(?:currentTimeMillis|nanoTime)\s*\(\s*\)"
        rules["fixed-deadline"] = clock + r"\s*\+(?!\s*TestTime\b)\s*\S"
        rules["elapsed-bound"] = clock + r"\s*-\s*\w+\s*\)?\s*(?:/\s*[\w.]+\s*)?<(?!\s*TestTime\b)"
    elif suffix in {".ts", ".tsx", ".mjs", ".js"}:
        rules["raw-waitfor"] = r"\bvi\s*\.\s*waitFor\s*\("
        rules["elapsed-bound"] = r"\b(?:Date\s*\.\s*now|performance\s*\.\s*now)\s*\(\s*\)\s*-\s*\w+\s*<(?!\s*scaledMs\b)"
    if suffix in {".qml", ".qtjs", ".cpp"}:
        rules = {"qt-fixed-delay": r"(?<![\w.])wait\s*\(" if suffix != ".cpp" else r"\bQTest::qWait\s*\("}
    if suffix == ".cpp":
        # Include values derived from QElapsedTimer / chrono, not just inline elapsed() calls.
        timed = r"\b\w+\s*\.\s*(?:elapsed|nsecsElapsed)\s*\(\s*\)"
        chrono = r"(?:std::)?chrono::(?:\w+::)*now\s*\(\s*\)\s*-\s*\w+"
        aliases = set(re.findall(r"\b(\w+)\s*=\s*(?:" + timed + "|" + chrono + ")", code))
        names = r"|\b(?:" + "|".join(map(re.escape, sorted(aliases))) + r")\b" if aliases else ""
        values = "(?:" + timed + "|" + chrono + names + ")"
        rules["elapsed-bound"] = values + r"\s*(?:/\s*[\d.eE]+\s*)?<=?\s*\d"
        rules["fixed-deadline"] = r"(?:std::)?chrono::(?:\w+::)*now\s*\(\s*\)\s*\+\s*(?:std::)?chrono::\w+\s*\(\s*\d"
    for rule, pattern in rules.items():
        for match in re.finditer(pattern, code):
            line = code.count("\n", 0, match.start()) + 1
            # Keep the entire source line so literal paths/ports are reviewable.
            snippet = text.splitlines()[line - 1].strip()
            if rule == "shared-temp" and suffix == ".kt" and not re.search(r'getProperty\s*\(\s*"java\.io\.tmpdir"', snippet):
                continue
            if WALLCLOCK_OK.search(snippet):
                continue
            if rule == "qt-fixed-delay" and ("// fixed: proves absence" in snippet or re.search(r"// fixed: samples timing - \S", snippet)):
                continue  # checked more strictly by test_qt_fixed_waits.py
            yield line, rule, snippet
    for start, rule in qt_wait_patterns(code, suffix):
        line = code.count("\n", 0, start) + 1
        snippet = text.splitlines()[line - 1].strip()
        if not WALLCLOCK_OK.search(snippet):
            yield line, rule, snippet
    if suffix == ".kt":
        units = {"NANOSECONDS": 1e-9, "MICROSECONDS": 1e-6, "MILLISECONDS": .001, "SECONDS": 1.0,
                 "MINUTES": 60.0, "HOURS": 3600.0, "DAYS": 86400.0}
        for match in re.finditer(r"\.(await|join)\s*\(\s*(\d+)L?(?:\s*,\s*TimeUnit\.(\w+))?", code):
            scale = units.get(match[3]) if match[3] else .001 if match[1] == "join" else None
            if scale is not None and 0 < int(match[2]) * scale <= 1:
                line = code.count("\n", 0, match.start()) + 1
                yield line, "short-thread-timeout", text.splitlines()[line - 1].strip()


def scan(root=INTERNAL, sources=None):
    findings = []
    for path in test_files(root):
        relative = path.relative_to(root).as_posix()
        text = sources[relative] if sources and relative in sources else path.read_text(encoding="utf-8-sig")
        patterns = python_patterns(text) if path.suffix == ".py" else other_patterns(text, suffix_of(relative, path.suffix))
        findings.extend(Finding(relative, line, rule, code) for line, rule, code in patterns
                        if not (rule in WALLCLOCK_RULES and relative in WALLCLOCK_DEFERRED))
    return sorted(findings, key=lambda f: (f.path, f.line, f.rule))


def counts(findings):
    return Counter(f.key for f in findings)


def regressions(findings, baseline):
    return counts(findings) - Counter(baseline)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path)
    args = parser.parse_args()
    findings = scan()
    if args.inventory:
        args.inventory.write_text(json.dumps([f.__dict__ for f in findings], ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    new = regressions(findings, json.loads(BASELINE.read_text(encoding="utf-8")))
    for key, number in sorted(new.items()):
        print(f"{number} new: {key}")
    print(f"{len(findings)} existing candidates; {sum(new.values())} new sites")
    raise SystemExit(bool(new))
