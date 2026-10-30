"""Fail loudly on Qt failures or missing glyphs, even when the process returned zero."""
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
    print(f"TEST_TOTALS {passed} passed, {failed} failed, {skipped} skipped; GLYPH_MISSING {len(hits)}", flush=True)
    return bool(totals) and not hits and not failed and not re.search(r"^FAIL", text, re.MULTILINE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    args = parser.parse_args()
    raise SystemExit(0 if check(args.log) else 1)
