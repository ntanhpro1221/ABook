"""Write the Kotlin copy of the shared-word table (`abook/readaloud/shared_words.json` -> `vieneu/SharedWords.kt`).

The table decides, for a word sea-g2p holds in both of its dictionaries with two different sounds (do, sang, bay, to...),
whether one occurrence is Vietnamese (`phoneme_policy.vietnamese_shared`, `PhonemePolicy.vietnameseShared`). It is learned,
not written: `docs/SHARED_WORDS.md` says how it is fitted from the private corpus (the fitting scripts and labelled rows hold
story sentences, so they stay outside the repository) and what it measured.
Android cannot carry it in BuildConfig (one JVM string constant holds at most 65535 bytes), so it is a generated source file
of short chunks, as `EnglishWords.kt` is. tests/test_shared_vietnamese.py checks the two copies are the same table.

Run again after the JSON changes: runtime/.venv/Scripts/python.exe scripts/build_shared_words.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "abook" / "readaloud" / "shared_words.json"
KOTLIN = ROOT / "mobile" / "android" / "app" / "src" / "main" / "java" / "vn" / "abook" / "player" / "vieneu" / "SharedWords.kt"
CHUNK_BYTES = 20_000  # one JVM string constant holds at most 65535 bytes


def kotlin(text: str) -> str:
    """The Kotlin source holding `text`, the table's JSON on one line."""
    if '"""' in text or "$" in text or "\\" in text:
        raise ValueError("the table must stay plain: no backslash, dollar sign or triple quote")
    chunks, start = [], 0
    while start < len(text):
        end = start + 1
        while end < len(text) and len(text[start:end + 1].encode("utf-8")) <= CHUNK_BYTES:
            end += 1
        chunks.append(text[start:end])
        start = end
    lines = ["package vn.abook.player.vieneu", "",
             "/**",
             " * The learned shared-word table - an EXACT copy of `abook/readaloud/shared_words.json` (scripts/build_shared_words.py writes this file;",
             " * tests/test_shared_vietnamese.py checks the copy). Do not edit by hand.",
             " */",
             "internal object SharedWords {",
             "    val JSON: String by lazy {",
             "        listOf("]
    lines += ['        """' + chunk + '""",' for chunk in chunks]
    lines += ["        ).joinToString(\"\")", "    }", "}", ""]
    return "\n".join(lines)


def table_text() -> str:
    text = TABLE.read_text(encoding="utf-8").strip()
    json.loads(text)
    return text


def main() -> int:
    source = kotlin(table_text())
    if "--check" in sys.argv:
        return 0 if KOTLIN.read_text(encoding="utf-8") == source else 1
    with KOTLIN.open("w", encoding="utf-8", newline="\n") as out:
        out.write(source)
    print(f"{KOTLIN.name}: {len(source.encode('utf-8'))} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
