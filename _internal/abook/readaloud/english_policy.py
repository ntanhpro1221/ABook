"""VieNeu reading decisions. The policy data and test cases are shared with Kotlin.

An English dictionary match is never evidence against a Vietnamese syllable.
Japanese/Korean rules run first; unresolved names retain their existing route.
Only automatic readings use this policy. Listener readings remain explicit choices.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import names

POLICY = json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8"))
VERSION = int(POLICY["version"])
PROVENANCE = str(POLICY["provenance"])
ACRONYMS = frozenset(POLICY["acronyms"])


def vietnamese(surface: str) -> bool:
    from ..analysis import is_vietnamese_syllable

    words = surface.split()
    return bool(words) and all(is_vietnamese_syllable(word) for word in words)


def keeps_word(core: str, origin: str | None) -> bool:
    """Keep lexical English and Western spelling; abstain on ambiguous Asian names.

    Unknown spellings that the existing Japanese/Korean transliterators accept
    are deliberately left to the current reading route, including without origin.
    This is a conservative spelling rule, not a language classifier.
    """
    from ..romanization import romanized_reading
    from . import shouts

    if core in POLICY["preserve_acronyms"]:
        return False
    vocalized = [core]
    shouts.read_shouts([core], vocalized)
    if vocalized != [core]:
        return False

    parts = re.split("[-'’]", core)
    if core.isupper() and set(core.lower()) <= set("ivxlcdm"):
        return False
    minimum = 1 if "'" in core or "’" in core else 2
    if any(len(p) < minimum or not p.isascii() or not p.isalpha() for p in parts):
        return False
    if vietnamese(core) or core.lower() in names.JAPANESE_COMMON:
        return False
    if names.name_reading(core, origin) or names.honorific_reading(core, origin):
        return False
    if core.replace("-", "").lower() in names.english_words() or core.lower() in POLICY["english_words"]:
        return True
    return all(romanized_reading(core, lang) is None for lang in names.ORIGINS)


def reading(core: str, origin: str | None) -> tuple[str, str] | None:
    if core in POLICY["preserve_acronyms"]:
        return None
    if core in ACRONYMS:
        return "<en>" + " ".join(core) + "</en>", "spell_english"
    from .abbreviations import LETTERS, ROMAN_LETTERS, spelled

    if (core.isascii() and core.isalpha() and core.isupper()
            and not vietnamese(core) and not ROMAN_LETTERS.issuperset(core.lower())
            and spelled(core) == " ".join(LETTERS[ch] for ch in core.lower())):
        return "<en>" + " ".join(core) + "</en>", "spell_english"
    if keeps_word(core, origin):
        return core, "keep_english"
    return None


def apply_tokens(toks: list[str], out: list[str], origin: str | None) -> None:
    """Run after punctuation TN, before explicit per-book listener readings.

    Preserve contextual Korean names and structural TN such as chapter labels.
    Tags are generated only here, so angle-bracket TN cannot consume them.
    """
    asian = names.spoken_names(toks, origin, True)
    for index, token in enumerate(toks):
        before, core, after = names.split_token(token)
        if not core or before[-1:].isdigit() or re.match(r"^[-–]?\d", after):
            continue
        if core in POLICY["preserve_acronyms"]:
            continue
        if asian[index] != token and core.lower() not in names.DICTIONARY_WORDS:
            continue
        if core not in ACRONYMS and vietnamese(core):
            from .abbreviations import spelled
            from .vieneu import roman_value

            if out[index].casefold() == token.casefold():
                out[index] = token
            elif core.isupper() and roman_value(core) is None:
                expanded = spelled(core)
                if expanded:
                    out[index] = out[index].replace(expanded, core, 1)
            continue
        choice = reading(core, origin)
        if choice is None:
            continue
        if choice[1] == "spell_english":
            from .abbreviations import spelled

            expanded = spelled(core)
            if expanded and expanded in out[index]:
                out[index] = out[index].replace(expanded, choice[0], 1)
            elif core in out[index]:
                out[index] = out[index].replace(core, choice[0], 1)
            continue
        if (choice[1] == "keep_english" and out[index] != token
                and out[index].casefold() != token.casefold()
                and core.lower() not in names.DICTIONARY_WORDS):
            # A foreign spelling decision cannot undo structural/sound-effect TN.
            continue
        # A changed chapter/volume/level label is structural, not a foreign word.
        if core.lower() in {"chap", "vol", "lv", "lvl"} and out[index] != token:
            continue
        out[index] = before + choice[0] + after
