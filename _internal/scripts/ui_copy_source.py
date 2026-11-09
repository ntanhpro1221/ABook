"""Resolve generated UI references for source based parity/layout audits.

This is analysis only: builds consume the generated language modules directly.
"""
import json
import re
from pathlib import Path
from functools import lru_cache

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=2)
def _entries(path, modified):
    return json.loads(Path(path).read_text(encoding="utf-8"))["strings"]


def expand(src, language):
    from scripts.gen_ui_strings import catalog, quote, slots
    source = ROOT / "ui_strings/vi.json"
    entries = _entries(str(source), source.stat().st_mtime_ns)
    # Use the existing balanced lexer so nested calls and quoted commas survive.
    from scripts.ui_parity import skip_balanced, skip_string
    pattern = re.compile(r"\bS\.(s_[a-z0-9_]+)\b")
    def resolve(m):
        key = m.group(1)
        if key not in entries:
            raise ValueError(f"Unknown UI string: {key}")
        value = entries[key]
        end = m.end()
        args = []
        if slots(value):
            start = end
            while src[start:start + 1].isspace():
                start += 1
            if src[start:start + 1] != "(":
                return m.group(0), end
            end = skip_balanced(src, start, "(", ")")
            a = i = start + 1
            while i < end - 1:
                if src[i] in "\"'`":
                    i = skip_string(src, i)
                    continue
                if src[i] in "([{":
                    i = skip_balanced(src, i, src[i], {"(": ")", "[": "]", "{": "}"}[src[i]])
                    continue
                if src[i] == ",":
                    args.append(expand(src[a:i].strip(), language))
                    a = i + 1
                i += 1
            args.append(expand(src[a:end - 1].strip(), language))
        if language in ("kt", "ts") and args:
            escaped = value.replace("\\", "\\\\").replace("`" if language == "ts" else '"', "\\`" if language == "ts" else '\\"').replace("\n", "\\n")
            for i, arg in enumerate(args):
                escaped = escaped.replace("{" + str(i) + "}", "${" + arg + "}")
            return ("`" if language == "ts" else '"') + escaped + ("`" if language == "ts" else '"'), end
        if args:
            parts = re.split(r"(\{\d+\})", value)
            return "(" + " + ".join(args[int(p[1:-1])] if re.fullmatch(r"\{\d+\}", p) else quote(p) for p in parts if p) + ")", end
        return quote(value), end
    out = []
    pos = 0
    for m in pattern.finditer(src):
        if m.start() < pos:
            continue
        replacement, end = resolve(m)
        out += [src[pos:m.start()], replacement]
        pos = end
    return "".join(out) + src[pos:]
