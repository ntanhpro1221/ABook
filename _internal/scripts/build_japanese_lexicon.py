"""Build the shared lexical guard from general CMUdict and BERT vocabulary.

The gzip is deterministic. Neither book text nor evaluation labels are inputs.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
from pathlib import Path

from build_english_words import bert_vocab

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 20_000
TARGET = ROOT / "abook/readaloud/japanese_lexicon.txt.gz"


def words() -> list[str]:
    cmu = {line.split(" ", 1)[0].split("(")[0]
           for line in (ROOT / "abook/assets/cmudict.dict").read_text(encoding="utf-8").splitlines()
           if line.strip()}
    common = {word for word in bert_vocab()[:LIMIT + 1]
              if re.fullmatch(r"[a-z]{2,}", word) and word in cmu}
    prefixes = ("re", "un", "pre", "non", "dis", "mis", "over", "under", "anti", "de")
    derived = {word for word in cmu if any(word.startswith(prefix)
               and len(word) - len(prefix) >= 3 and word[len(prefix):] in common
               for prefix in prefixes)}
    return sorted(common | derived)


if __name__ == "__main__":
    raw = ("\n".join(words()) + "\n").encode("utf-8")
    TARGET.write_bytes(gzip.compress(raw, mtime=0))
    print(json.dumps({"limit": LIMIT, "words": len(raw.splitlines()),
                      "sha256": hashlib.sha256(TARGET.read_bytes()).hexdigest()}))
