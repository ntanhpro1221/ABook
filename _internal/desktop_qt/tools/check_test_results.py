"""Fail loudly on Qt failures, missing glyphs or QML TypeErrors, even when the process returned zero."""
import argparse
from pathlib import Path
import re


def check(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    hits = [line for line in text.splitlines() if "GLYPH_MISSING" in line]
    print(f"GLYPH_MISSING {len(hits)} ({path.name})", flush=True)
    for hit in hits:
        print(hit, flush=True)  # JSON carries the codepoint and QML source file.
    totals = re.findall(r"Totals: (\d+) passed, (\d+) failed, (\d+) skipped", text)
    passed = sum(int(row[0]) for row in totals)
    failed = sum(int(row[1]) for row in totals)
    skipped = sum(int(row[2]) for row in totals)
    # A QML binding that reads a field of missing data prints a TypeError and leaves the item half drawn; the test may still pass.
    type_errors = sorted({m.group(1) for m in re.finditer(r"(qml/[\w/]+\.(?:qml|js):\d+): TypeError", text)})
    for where in type_errors:
        print(f"QML_TYPE_ERROR {where}", flush=True)
    print(f"TEST_TOTALS {passed} passed, {failed} failed, {skipped} skipped; GLYPH_MISSING {len(hits)}; "
          f"QML_TYPE_ERROR {len(type_errors)}", flush=True)
    return bool(totals) and not hits and not type_errors and not failed and not re.search(r"^FAIL", text, re.MULTILINE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    args = parser.parse_args()
    raise SystemExit(0 if check(args.log) else 1)
