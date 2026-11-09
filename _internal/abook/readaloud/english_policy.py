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


def english_letters(core: str) -> str:
    """The owner's Z is zed; the frontend's bare Z otherwise says zee."""
    return "<en>" + " ".join(POLICY["english_letter_words"].get(ch, ch) for ch in core.upper()) + "</en>"


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
    from .japanese_policy import reading as japanese_reading

    if japanese_reading(core, origin) or names.name_reading(core, origin) or names.honorific_reading(core, origin):
        return False
    if core.replace("-", "").lower() in names.english_words() or core.lower() in POLICY["english_words"]:
        return True
    return all(romanized_reading(core, lang) is None for lang in names.ORIGINS)


def reading(core: str, origin: str | None) -> tuple[str, str] | None:
    from .abbreviations import standard_reading

    # These need the occurrence's sentence; never lock a context-free default.
    if (core.casefold() in POLICY["contextual_abbreviations"] or core.casefold() in POLICY["contextual_letter_names"]
            or core.casefold() in POLICY["case_sensitive_abbreviations"]):
        return None
    standard = standard_reading(core, [core], 0)
    if standard:
        return standard, "owner_abbreviation"
    if core in POLICY["preserve_acronyms"]:
        return None
    from .japanese_policy import reading as japanese_reading

    if japanese_reading(core, origin):
        return None
    if core in ACRONYMS:
        return english_letters(core), "spell_english"
    from .abbreviations import LETTERS, ROMAN_LETTERS, spelled

    if (core.isascii() and core.isalpha() and core.isupper()
            and not vietnamese(core) and not ROMAN_LETTERS.issuperset(core.lower())
            and spelled(core) == " ".join(LETTERS[ch] for ch in core.lower())):
        return english_letters(core), "spell_english"
    if keeps_word(core, origin):
        return core.lower() if core.isupper() else core, "keep_english"
    return None


def apply_tokens(toks: list[str], out: list[str], origin: str | None, *, protected: set[int] | None = None) -> None:
    """Run after punctuation TN, before explicit per-book listener readings.

    Preserve contextual Korean names and structural TN such as chapter labels.
    Tags are generated only here, so angle-bracket TN cannot consume them.
    """
    from .japanese_policy import apply_tokens as japanese_tokens, contextual_names, read_unmodified

    protected = protected or set()
    proposed = list(out)
    japanese_tokens(toks, proposed, origin)
    contextual = contextual_names(toks, origin) if protected and origin != "ko" else set()
    for index, said in enumerate(proposed):
        if index not in protected:
            out[index] = said
        else:
            out[index] = read_unmodified(toks[index], out[index], origin, contextual=index in contextual)
    asian = names.spoken_names(toks, origin, True)
    for index, token in enumerate(toks):
        if index in protected:
            continue
        before, core, after = names.split_token(token)
        from .abbreviations import contextual_letters, pronoun_ai, standard_reading

        if contextual_letters(core, toks, index):
            out[index] = before + english_letters(core) + after
            continue
        if pronoun_ai(toks, index) or standard_reading(core, toks, index, before, after):
            continue
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
                out[index] = token.lower() if core.isascii() and len(core) >= 2 and core.isupper() else token
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
