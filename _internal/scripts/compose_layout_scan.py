"""Conservative source guard for sibling roots in Compose animation content.

Animation containers overlay their roots. Flow belongs in an explicit layout.
This is a lexical guard, not a Kotlin type checker; UI tests measure actual bounds.
"""
from __future__ import annotations

import re
from pathlib import Path

ANIMATIONS = re.compile(r"\b(Reveal|ReducedFade|AnimatedVisibility|AnimatedContent|SheetPages)\s*\(")
LITERALS = re.compile(
    r'"""[\s\S]*?"""|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*',
)


def mask(source: str) -> str:
    """Hide literals and nested Kotlin comments without changing offsets."""
    out = list(source)
    at = 0
    while match := LITERALS.search(source, at):
        start, end = match.span()
        if match[0] == "/*":
            depth = 1
            while depth and end < len(source):
                if source.startswith("/*", end):
                    depth += 1
                    end += 2
                elif source.startswith("*/", end):
                    depth -= 1
                    end += 2
                else:
                    end += 1
        for i in range(start, end):
            if out[i] != "\n":
                out[i] = " "
        at = end
    return "".join(out)


def close(text: str, start: int) -> int:
    stack = []
    for i in range(start, len(text)):
        c = text[i]
        if c in "({[":
            stack.append(c)
        elif c in ")}]":
            if not stack or stack.pop() != {")": "(", "}": "{", "]": "["}[c]:
                raise ValueError(f"Unbalanced Kotlin delimiter at {i}")
            if not stack:
                return i + 1
    raise ValueError(f"Unclosed Kotlin delimiter at {start}")


def statements(text: str) -> list[str]:
    result = []
    start = i = 0
    while i < len(text):
        if text[i] in "({[":
            i = close(text, i)
        elif text[i] in "\n;":
            # Kotlin permits a chained call or else on the following line.
            tail = text[i + 1:].lstrip()
            if tail.startswith((".", "?.", "else")) or text[start:i].rstrip().endswith(("=", "->", ",", "+", "?:")):
                i += 1
                continue
            if part := text[start:i].strip():
                result.append(part)
            start = i = i + 1
        else:
            i += 1
    if part := text[start:].strip():
        result.append(part)
    return result


def without_parameters(body: str) -> str:
    """Drop a lambda parameter list, but never an arrow inside a call/block."""
    body = body.lstrip()
    i = 0
    while i < len(body):
        if body.startswith("->", i):
            return body[i + 2:]
        if body[i] in "{\n;":
            break
        if body[i] in "([":
            end = close(body, i)
            # A parameter destructuring tuple may precede an arrow.
            if body[end:].lstrip().startswith("->"):
                i = end
                continue
            break
        i += 1
    return body


def roots(body: str) -> int:
    return sum(statement_roots(part) for part in statements(without_parameters(body)))


def statement_roots(part: str) -> int:
    part = part.strip()
    if not part or re.match(r"(?:val|var|fun|return|throw|check|require)\b", part):
        return 0
    if part.startswith("{"):
        return roots(part[1:close(part, 0) - 1])
    if re.match(r"(?:if|for|while|when)\b", part):
        kind = re.match(r"\w+", part)[0]
        if kind == "when":
            opening = part.index("{")
            branches = statements(part[opening + 1:close(part, opening) - 1])
            return max((statement_roots(branch.split("->", 1)[1]) for branch in branches if "->" in branch), default=0)
        opening = part.index("(")
        end = close(part, opening)
        rest = part[end:].strip()
        if kind in {"for", "while"}:
            # Even one child emitted on each iteration produces multiple roots.
            return 2 if statement_roots(rest) else 0
        if rest.startswith("{"):
            end = close(rest, 0)
            yes = roots(rest[1:end - 1])
            no = rest[end:].strip().removeprefix("else").strip()
            return max(yes, statement_roots(no))
        # Single-expression branches each emit at most their own roots.
        branches = re.split(r"\belse\b", rest, maxsplit=1)
        return max(map(statement_roots, branches), default=0)
    # These calls do not create a layout node. Inspect their content as well.
    i = 0
    while i < len(part):
        if part[i] in "([":
            i = close(part, i)
        elif part[i] == "{":
            head = part[:i]
            if re.match(r"(?:key|CompositionLocalProvider|run|with|repeat)\s*[(\{]", part) or re.search(r"\?*\.(?:let|run|also|forEach|forEachIndexed)\s*$", head):
                count = roots(part[i + 1:close(part, i) - 1])
                return 2 if ("forEach" in head or head.startswith("repeat")) and count else count
            break
        else:
            i += 1
    return 1


def scan(source: str) -> list[tuple[int, str]]:
    text = mask(source)
    found = []
    for match in ANIMATIONS.finditer(text):
        if re.search(r"\bfun\s+(?:<[^>]+>\s*)?$", text[:match.start()]):
            continue
        opening = text.index("(", match.start())
        end = close(text, opening)
        tail = end
        while tail < len(text) and text[tail].isspace():
            tail += 1
        if tail < len(text) and text[tail] == "{":
            body = text[tail + 1:close(text, tail) - 1]
        elif named := re.search(r"\bcontent\s*=\s*\{", text[opening:end]):
            tail = opening + named.end() - 1
            body = text[tail + 1:close(text, tail) - 1]
        else:
            continue  # Forwarded content is checked at its callers.
        if roots(body) > 1:
            found.append((source.count("\n", 0, match.start()) + 1, match[1]))
    return found


def scan_tree(root: Path) -> list[str]:
    return [f"{path.relative_to(root).as_posix()}:{line}: {name} needs an explicit layout"
            for path in sorted(root.rglob("*.kt"))
            for line, name in scan(path.read_text(encoding="utf-8"))]
