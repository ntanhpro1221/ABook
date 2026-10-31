"""Fail loudly on Qt failures, missing glyphs, QML binding errors or JS values leaked onto the screen, even when the process returned zero."""
import argparse
from pathlib import Path
import re

BINDING_ERROR = re.compile(r"([\w/.-]+\.(?:qml|js):\d+)(?::\d+)?: (?:TypeError|ReferenceError|RangeError|Unable to assign \[undefined\])")


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
    # A QML binding that reads a field of missing data leaves the item half drawn and the test may still pass: a TypeError /
    # ReferenceError / RangeError, or "Unable to assign [undefined]" when the missing field lands in a typed property (the
    # property keeps its old value). Bindings print "file.qml:line:column: ..." - the column is optional, the line is kept.
    # Any .qml / .js counts, the tests' own included; the path is shown from desktop_qt/ on.
    type_errors = sorted({re.sub(r"^.*?desktop_qt/", "", m.group(1)) for m in re.finditer(BINDING_ERROR, text)})
    for where in type_errors:
        print(f"QML_TYPE_ERROR {where}", flush=True)
    # GlyphAudit (tests/glyphaudit.h) sees every shown text: "undefined" / "NaN" / "[object Object]" on screen is a missing field
    leaks = [line for line in text.splitlines() if "TEXT_LEAK {" in line]
    for leak in leaks:
        print(leak, flush=True)
    print(f"TEST_TOTALS {passed} passed, {failed} failed, {skipped} skipped; GLYPH_MISSING {len(hits)}; "
          f"QML_TYPE_ERROR {len(type_errors)}; TEXT_LEAK {len(leaks)}", flush=True)
    return bool(totals) and not hits and not type_errors and not leaks and not failed and not re.search(r"^FAIL", text, re.MULTILINE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    args = parser.parse_args()
    raise SystemExit(0 if check(args.log) else 1)
