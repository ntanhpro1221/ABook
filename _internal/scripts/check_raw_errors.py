"""No Android screen shows a raw exception message.

Every read of a Throwable's text (`error.message`, `e.localizedMessage`, `"$error"`, `error.toString()`) in the app's Kotlin
sources must go through `UserText` (vn/abook/player/UserText.kt), which turns platform errors into Vietnamese and logs the
technical detail. A read that never reaches a screen (logging, a technical "Chi tiết" line, a check on the text) is listed in
`raw_errors_reviewed.json` with the exact file, the exact line and why it is safe. Any other read fails this check.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.ui_parity import blank_comments  # noqa: E402

SOURCES = ROOT / "mobile/android/app/src/main/java/vn/abook/player"
REVIEWED = ROOT / "scripts/raw_errors_reviewed.json"
SKIP = {"UiStrings.kt", "UserText.kt"}
# Throwable names used across the app, plus every `catch (x: ...)` and `onFailure { x ->` name found in the file.
NAMES = {"error", "e", "t", "ex", "exception", "cause", "failure", "throwable", "earlier", "problem", "lastError"}
BINDERS = re.compile(r"catch\s*\(\s*(\w+)\s*:|(?:onFailure|getOrElse|recover|recoverCatching|exceptionally)\s*\{\s*(\w+)\s*->")
IMPLICIT = re.compile(r"(?:onFailure|getOrElse|recover|recoverCatching)\s*\{(?!\s*\w+\s*->)")
LOGGING = re.compile(r"\bAppLog\.[iwe]\(|\bLog\.[iwedv]\(|\blog\(|\bfun technical\(")


def _names(source: str) -> set[str]:
    names = set(NAMES)
    for match in BINDERS.finditer(source):
        names.add(match.group(1) or match.group(2))
    if IMPLICIT.search(source):
        names.add("it")
    names.discard("_")
    return names


def _patterns(names: set[str]) -> list[re.Pattern[str]]:
    alt = "|".join(sorted(map(re.escape, names), key=len, reverse=True))
    return [
        re.compile(rf"\b(?:{alt})\s*\??\.\s*(?:message|localizedMessage)\b"),
        re.compile(r"exceptionOrNull\(\)\s*\??\.\s*(?:message|localizedMessage)\b"),
        re.compile(rf"\b(?:{alt})\s*\??\.\s*(?:toString|stackTraceToString)\(\)"),
        re.compile(rf"\$\{{\s*(?:{alt})\s*\}}|\$(?:{alt})\b(?![.\w(])"),
    ]


def scan_file(path: Path, rel: str) -> list[tuple[str, str]]:
    source = blank_comments(path.read_text(encoding="utf-8"))
    patterns = _patterns(_names(source))
    found = []
    for line in source.splitlines():
        if LOGGING.search(line):
            continue
        if any(p.search(line) for p in patterns):
            found.append((rel, line.strip()))
    return found


def findings(root: Path = SOURCES) -> list[tuple[str, str]]:
    found = []
    for path in sorted(root.rglob("*.kt")):
        if path.name in SKIP:
            continue
        found += scan_file(path, path.relative_to(root).as_posix())
    return found


def reviewed() -> list[dict]:
    return json.loads(REVIEWED.read_text(encoding="utf-8"))


def main() -> int:
    allowed = {(x["file"], x["line"]) for x in reviewed()}
    found = findings()
    new = [f for f in found if f not in allowed]
    stale = sorted(allowed - set(found))
    for file, line in new:
        print(f"raw error text may reach the UI (route it through UserText.of): {file}: {line}", file=sys.stderr)
    for file, line in stale:
        print(f"stale review entry (line gone or changed): {file}: {line}", file=sys.stderr)
    print(f"raw errors: {len(found)} reads, {len(new)} unreviewed, {len(stale)} stale")
    return 1 if new or stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
