"""Shared romaji phonotactics and Vietnamese fallback, with automatic provenance."""
from __future__ import annotations

import json
import gzip
import re
from functools import lru_cache
from pathlib import Path

POLICY = json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8"))
VERSION = int(POLICY["version"])
NAMESPACE = str(POLICY["namespace"])
PROVENANCE = str(POLICY["provenance"])
_LETTERS = "A-Za-zāīūēōâîûêôĀĪŪĒŌÂÎÛÊÔ"
_WORD = re.compile(rf"[{_LETTERS}]+(?:[-'][{_LETTERS}]+)*")
_NOTE = re.compile(r"\[note\d+\]", re.IGNORECASE)


@lru_cache(maxsize=1)
def lexical_guard() -> frozenset[str]:
    """General English vocabulary, including common Western proper nouns."""
    with gzip.open(Path(__file__).with_name("japanese_lexicon.txt.gz"), "rt", encoding="utf-8") as stream:
        return frozenset(stream.read().split())


def _normalized(core: str, origin: str | None) -> str:
    if origin != "ja":
        return core
    parts = core.split("-")
    # Only the suffix is compressed: repeated letters in the name still abstain.
    for index in range(1, len(parts)):
        low = parts[index].casefold()
        for suffix in POLICY["suffixes"]:
            if re.fullmatch("".join(re.escape(ch) + "+" for ch in suffix), low):
                parts[index] = suffix
                break
    return "-".join(part.capitalize() if part.isupper() else part for part in parts)


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


def _candidate(core: str, origin: str | None = None) -> tuple[int, bool]:
    from ..analysis import is_vietnamese_syllable
    from ..romanization import romanized_reading
    from .names import english_words

    head, honorific = _head(_normalized(core, origin))
    if (len(head) < 2 or not head[:1].isupper() or head[1:] != head[1:].lower()
            or is_vietnamese_syllable(head) or head.casefold() in english_words()
            or (origin == "ja" and head.casefold() in lexical_guard())
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


def contextual_names(toks: list[str], origin: str | None = None) -> set[int]:
    from .names import split_token

    parts = [split_token(token) for token in toks]
    valid = [_candidate(core, origin)[0] > 0 for _, core, _ in parts]
    found: set[int] = set()
    for index in range(len(parts) - 1):
        if valid[index] and valid[index + 1] and not parts[index][2] and not parts[index + 1][0]:
            found.update((index, index + 1))
    return found


def _reading_word(core: str, origin: str | None, *, contextual: bool = False) -> str | None:
    from ..romanization import romanized_reading
    from .names import lone_syllable

    core = _normalized(core, origin)
    count, honorific = _candidate(core, origin)
    minimum = POLICY["routing"]["known_ja_min_syllables" if origin == "ja" else "min_syllables"]
    if origin == "ko" or not count or not (contextual or honorific or count >= minimum):
        return None
    head, _ = _head(core)
    parts = core.split("-")
    if len(parts) > 1 and all(len(p) == 1 and p.casefold() == head[:1].casefold() for p in parts[:-1]):
        full = lone_syllable(romanized_reading(head, "ja"))
        if full:
            mora = full.split("-")[0]
            return "-".join([mora] * (len(parts) - 1) + [full.lower()])
    return lone_syllable(romanized_reading(core, "ja"))


def reading(core: str, origin: str | None, *, contextual: bool = False) -> str | None:
    """Use presentation boundaries only with independent book-level evidence.

    Return a spoken form; source text and its offsets are never edited.
    ASCII fragments inside a Unicode word are not separate names.
    """
    if origin != "ja":
        return _reading_word(core, origin, contextual=contextual)
    notes = list(_NOTE.finditer(core))
    found = False
    pieces = []
    end = 0
    for match in _WORD.finditer(core):
        if any(note.start() <= match.start() < note.end() for note in notes):
            continue
        if ((match.start() and core[match.start() - 1].isalpha())
                or (match.end() < len(core) and core[match.end()].isalpha())):
            continue
        said = _reading_word(match.group(), origin, contextual=contextual)
        if said:
            pieces.extend((core[end:match.start()], said))
            end = match.end()
            found = True
    if not found:
        return None
    return "".join([*pieces, core[end:]])


def apply_tokens(toks: list[str], out: list[str], origin: str | None) -> None:
    """VieNeu-only routing, before keep-English and explicit listener readings."""
    from .names import name_reading, split_token

    contextual = contextual_names(toks, origin) if origin != "ko" else set()
    for index, token in enumerate(toks):
        source = _NOTE.sub("", token) if origin == "ja" else token
        before, core, after = split_token(source)
        if not core or before[-1:].isdigit() or re.match(r"^[-–]?\d", after):
            continue
        said = reading(core, origin, contextual=index in contextual)
        if said:
            out[index] = before + said + after
        elif origin == "ja" and out[index] == before + str(name_reading(core, origin)) + after:
            # The direct-reading policy also governs short ambiguous spellings.
            out[index] = token


def read_unmodified(source: str, spoken: str, origin: str | None, *, contextual: bool = False) -> str:
    """Route unambiguous source words beside an already rendered vocalization.

    Never feed the vocalization back through name parsing. An earlier name-only
    reading can still be corrected by the same direct policy as a whole token.
    """
    from . import names, shouts

    matches = list(_WORD.finditer(source))
    replacements = []
    for match in matches:
        raw = match.group()
        if (sum(m.group() == raw for m in matches) != 1
                or (match.start() and source[match.start() - 1].isalpha())
                or (match.end() < len(source) and source[match.end()].isalpha())
                or any(note.start() <= match.start() < note.end() for note in _NOTE.finditer(source))):
            continue
        vocal = [raw]
        shouts.read_shouts([raw], vocal, origin)
        if vocal != [raw]:
            continue
        old = names.name_reading(raw, origin)
        locations = set()
        for form in {raw, old} - {None}:
            for found in re.finditer(re.escape(form), spoken):
                if ((not found.start() or not spoken[found.start() - 1].isalpha())
                        and (found.end() == len(spoken) or not spoken[found.end()].isalpha())):
                    locations.add((found.start(), found.end()))
        if len(locations) != 1:
            continue
        said = _reading_word(raw, origin, contextual=contextual)
        if said is None and origin != "ja":
            continue
        start, stop = locations.pop()
        replacements.append((start, stop, said or raw))
    for start, stop, said in sorted(replacements, reverse=True):
        spoken = spoken[:start] + said + spoken[stop:]
    return spoken


def metadata(surface: str) -> dict:
    """Keep source long-vowel spelling even when the Vietnamese fallback folds it."""
    return {
        "provenance": PROVENANCE,
        "reading_namespace": NAMESPACE,
        "source_spelling": surface,
        "long_vowels": [m.group() for m in re.finditer(r"[āīūēōâîûêô]|aa|ii|uu|ee|oo|ou|ei", surface.casefold())],
    }
