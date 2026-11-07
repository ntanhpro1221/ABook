"""Every text-mode subprocess call in the app must say how to survive bytes it cannot decode.

07-11: `nvidia-smi pmon` on Windows prints stray bytes in the command column. With
`text=True` and no `errors=`, the reader thread raised UnicodeDecodeError every ~24 s
during a recording, `stdout` came back None and the GPU share probe silently returned
nothing. A tool's output is not ours to trust: decode as UTF-8 and replace what fails.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNED = [ROOT / "abook", ROOT / "scripts"]
SKIP_PARTS = {"vendor", "node_modules", "__pycache__"}
CALLS = {"run", "Popen", "check_output", "check_call", "call"}


def _text_calls_without_errors(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        if name not in CALLS:
            continue
        keywords = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg}
        text = keywords.get("text") or keywords.get("universal_newlines")
        if isinstance(text, ast.Constant) and text.value is True and "errors" not in keywords:
            lines.append(node.lineno)
    return lines


def test_text_mode_subprocess_calls_declare_errors() -> None:
    offenders = []
    for base in SCANNED:
        for path in sorted(base.rglob("*.py")):
            if SKIP_PARTS & set(path.relative_to(ROOT).parts):
                continue
            for line in _text_calls_without_errors(path):
                offenders.append(f"{path.relative_to(ROOT)}:{line}")
    assert not offenders, "text=True without errors= (add encoding=\"utf-8\", errors=\"replace\"):\n" + "\n".join(offenders)
