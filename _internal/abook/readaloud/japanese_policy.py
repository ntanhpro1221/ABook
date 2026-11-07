"""Shared romaji phonotactics and Vietnamese fallback, with automatic provenance."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

POLICY = json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8"))
VERSION = int(POLICY["version"])
NAMESPACE = str(POLICY["namespace"])
PROVENANCE = str(POLICY["provenance"])


def _head(core: str) -> tuple[str, bool]:
    parts = core.split("-")
    honorific = len(parts) > 1 and parts[-1].casefold() in POLICY["honorifics"]
    while len(parts) > 1 and parts[-1].casefold() in POLICY["suffixes"]:
        parts.pop()
    # Initial stutters inherit the complete name's evidence.
    while len(parts) > 1 and len(parts[0]) == 1 and parts[0].casefold() == parts[-1][:1].casefold():
        parts.pop(0)
    return "-".join(parts), honorific


@lru_cache(maxsize=8192)
def syllables(core: str) -> int:
    """Count nuclei after consuming all romaji; long vowels count once.

    Syllabic n and geminates require a preceding nucleus. The pronunciation
    parser uses the same onset/vowel and geminate tables.
    """
    from ..romanization import _ja_spelling

    word = _ja_spelling(core.casefold().translate(str.maketrans(POLICY["long_vowels"])), [])
    count = i = 0
    while i < len(word):
        c, after = word[i], word[i + 1:i + 2]
        if c == "n" and (not after or after not in "aiueoy"):
            if not count:
                return 0
            i += 2 if after == "'" else 1
            continue
        if c == "m" and after and after in "bmp":
            if not count:
                return 0
            i += 1
            continue
        if c in POLICY["geminate_coda"] and (after == c or (c == "t" and word[i + 1:i + 3] == "ch")):
            if not count:
                return 0
            i += 1
            continue
        onset = "" if c in "aiueoŏ" else next((o for o in POLICY["onsets"] if word.startswith(o, i)), c)
        at = i + len(onset)
        vowel = word[at:at + 1].replace("ŏ", "o")
        if not vowel or vowel not in "aiueo" or (onset and vowel not in POLICY["allowed"].get(onset, "")):
            return 0
        count += 1
        i = at + 1
        if word[i:i + 1] == vowel or (vowel, word[i:i + 1]) in (("o", "u"), ("e", "i")):
            i += 1
    return count


def _candidate(core: str) -> tuple[int, bool]:
    from ..analysis import is_vietnamese_syllable
    from ..romanization import romanized_reading
    from .names import english_words

    head, honorific = _head(core)
    if (len(head) < 2 or not head[:1].isupper() or head[1:] != head[1:].lower()
            or is_vietnamese_syllable(head) or head.casefold() in english_words()
            or head.casefold() in POLICY["common"] or re.search(r"(.)\1\1", head.casefold())):
        return 0, False
    count = syllables(head)
    return (count, honorific) if count and romanized_reading(head, "ja") else (0, False)


def routing_origin(surface: str, origin: str | None) -> str | None:
    if origin is not None:
        return origin
    words = surface.split()
    return "ja" if contextual_names(words) or any(_supported(word) for word in words) else None


def _supported(core: str) -> bool:
    count, honorific = _candidate(core)
    return bool(count and (honorific or count >= POLICY["routing"]["min_syllables"]))


def contextual_names(toks: list[str]) -> set[int]:
    from .names import split_token

    parts = [split_token(token) for token in toks]
    valid = [_candidate(core)[0] > 0 for _, core, _ in parts]
    found: set[int] = set()
    for index in range(len(parts) - 1):
        if valid[index] and valid[index + 1] and not parts[index][2] and not parts[index + 1][0]:
            found.update((index, index + 1))
    return found


def reading(core: str, origin: str | None, *, contextual: bool = False) -> str | None:
    from ..romanization import romanized_reading
    from .names import lone_syllable

    count, honorific = _candidate(core)
    if origin == "ko" or not count or not (contextual or honorific or count >= POLICY["routing"]["min_syllables"]):
        return None
    head, _ = _head(core)
    parts = core.split("-")
    if len(parts) > 1 and all(len(p) == 1 and p.casefold() == head[:1].casefold() for p in parts[:-1]):
        full = lone_syllable(romanized_reading(head, "ja"))
        if full:
            mora = full.split("-")[0]
            return "-".join([mora] * (len(parts) - 1) + [full.lower()])
    return lone_syllable(romanized_reading(core, "ja"))


def apply_tokens(toks: list[str], out: list[str], origin: str | None) -> None:
    """VieNeu-only routing, before keep-English and explicit listener readings."""
    from .names import name_reading, split_token

    contextual = contextual_names(toks) if origin != "ko" else set()
    for index, token in enumerate(toks):
        before, core, after = split_token(token)
        if not core or before[-1:].isdigit() or re.match(r"^[-–]?\d", after):
            continue
        said = reading(core, origin, contextual=index in contextual)
        if said:
            out[index] = before + said + after
        elif origin == "ja" and out[index] == before + str(name_reading(core, origin)) + after:
            # The direct-reading policy also governs short ambiguous spellings.
            out[index] = token


def metadata(surface: str) -> dict:
    """Keep source long-vowel spelling even when the Vietnamese fallback folds it."""
    return {
        "provenance": PROVENANCE,
        "reading_namespace": NAMESPACE,
        "source_spelling": surface,
        "long_vowels": [m.group() for m in re.finditer(r"[āīūēōâîûêô]|aa|ii|uu|ee|oo|ou|ei", surface.casefold())],
    }
