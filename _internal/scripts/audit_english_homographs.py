"""Find Vietnamese syllables in an English pronunciation table, without opening a writer.

Usage: python -X utf8 scripts/audit_english_homographs.py PROJECT --output audit.json
An old listener_choice label is reported for review, not treated as proof of intent.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from abook.readaloud.english_policy import ACRONYMS, vietnamese


def findings(pronunciations, texts):
    out = []
    for item in pronunciations:
        surface = str(item["surface"])
        if surface in ACRONYMS or not vietnamese(surface) or str(item["spoken_form"]) == surface:
            continue
        pattern = re.compile(r"(?<!\w)" + re.escape(surface) + r"(?!\w)", re.IGNORECASE)
        occurrences = sum(len(pattern.findall(text)) for text in texts)
        out.append({"surface": surface, "spoken_form": str(item["spoken_form"]),
                    "source": str(item["source"]), "occurrences": occurrences,
                    "reason": "Vietnamese syllable; dictionary membership is not language evidence"})
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    path = args.project / "project.sqlite3"
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        pronunciations = list(conn.execute("select surface,spoken_form,source from pronunciations"))
        texts = [str(row[0]) for row in conn.execute("select coalesce(nullif(listener_text,''),text) from segments")]
    result = findings(pronunciations, texts)
    args.output.write_text(json.dumps({"read_only": True, "findings": result}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(result)} suspect readings; {sum(r['occurrences'] for r in result)} occurrences")


if __name__ == "__main__":
    main()
