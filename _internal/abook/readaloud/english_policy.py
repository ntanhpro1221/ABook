"""VieNeu reading decisions. The policy data and test cases are shared with Kotlin.

An English dictionary match alone is never evidence against a Vietnamese syllable:
"to", "con" and "ban" stay Vietnamese. The sentence around the word can be evidence
(`english_context`): "Oh my god", "I love you", "Go!", "một bản hit".
Japanese/Korean rules run first; unresolved names retain their existing route.
Only automatic readings use this policy. Listener readings remain explicit choices.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from . import names

POLICY = json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8"))
VERSION = int(POLICY["version"])
PROVENANCE = str(POLICY["provenance"])
ACRONYMS = frozenset(POLICY["acronyms"])
_CONTEXT = POLICY["context"]
ENGLISH_ONLY = frozenset(_CONTEXT["only"])  # a syllable shape, never a correctly spelled Vietnamese word
WEAK = frozenset(_CONTEXT["weak"])  # rare as Vietnamese: one certain English neighbour decides
ALONE = frozenset(_CONTEXT["alone"])  # English when the word is the whole exclamation
SINGLE = frozenset(_CONTEXT["letters"])  # "I", "a": not dictionary entries, English inside an English run
FUNCTION = frozenset(_CONTEXT["function"])  # grammar words: Vietnamese prose borrows nouns, not these
FOLLOWED = frozenset(_CONTEXT["followed"])  # "X no Y" is Japanese: only a following English word counts
_BREAKS = ".!?…,;:"
_NUMBER = re.compile(r"[0-9]|[IVXLCDM]+(?![^\W\d_])")  # a digit or a Roman numeral, not "Cả"


def english_letters(core: str) -> str:
    """The owner's Z is zed; the frontend's bare Z otherwise says zee."""
    return "<en>" + " ".join(POLICY["english_letter_words"].get(ch, ch) for ch in core.upper()) + "</en>"


def letter_name(toks: list[str], index: int) -> bool:
    """A lone capital letter used as a person's or thing's name ("thấy Y ở đây", "ông X", "cô gái tên K"): read its English letter name.

    Owner 10-11: a codename may be read as the English letter. Only after a word from
    "letter_name_cues" inside the sentence, and never beside another capitalised word:
    "Y Mặc", "Thần Y" and "Waldo K. Maskelyne" are pieces of names, "lớp A", "tia X" labels.
    Lowercase "y" and a sentence-initial "Y" stay the Vietnamese pronoun.
    """
    before, core, after = names.split_token(toks[index])
    if len(core) != 1 or not "A" <= core <= "Z" or index == 0 or names.sentence_start(toks, index):
        return False
    if core in POLICY["vietnamese_letter_names"]:  # owner 11-11: "K" as Vietnamese "ca" sounds more natural than "kei"
        return False
    if any(ch.isalnum() or ch in "-'’" for ch in before + after) or after[:1] == "." and index + 1 < len(toks) and toks[index + 1][:1].isupper():
        return False
    previous = names.split_token(toks[index - 1])
    if previous[2] or previous[1].casefold() not in POLICY["letter_name_cues"]:
        return False
    following = names.split_token(toks[index + 1])[1] if index + 1 < len(toks) and not after else ""
    return not following[:1].isupper() and not following[:1].isdigit()


def vietnamese(surface: str) -> bool:
    from ..analysis import is_vietnamese_syllable

    words = surface.split()
    return bool(words) and all(is_vietnamese_syllable(word) for word in words)


def _kind(token: str) -> tuple[str, str, str, str, str]:
    """(kind, lowercase word, case, punctuation before, punctuation after) of one shown token.

    v: carries a non-ASCII letter or a combining tone mark - Vietnamese evidence;
    e: certainly English; h: an English word spelled like a Vietnamese syllable;
    o: another ASCII word (romaji, an unlisted name, toneless Vietnamese); "": no word.
    """
    before, core, after = names.split_token(token)
    core = core.replace("’", "'")
    edges = before, after
    if not core or before[-1:].isdigit() or re.match(r"\.?[0-9]", after):  # "8man", "No.7"
        return "", "", "", *edges
    if not core.isascii() or unicodedata.combining(after[:1] or " "):
        return "v", "", "", *edges
    low = core.lower()
    if not all(ch.isalpha() or ch in "-'" for ch in low):
        return "", "", "", *edges
    case = "U" if len(core) > 1 and core.isupper() else "T" if core[0].isupper() else "l"
    words = names.english_words()
    if low in ENGLISH_ONLY:
        return "e", low, case, *edges
    if low.isalpha() and vietnamese(low):
        return ("h" if low in words or low in SINGLE else "o"), low, case, *edges
    if low in FUNCTION or (low.isalpha() and low in words):
        return "e", low, case, *edges
    parts = re.split("[-']", low)
    if len(parts) > 1 and not all(vietnamese(part) for part in parts if part) and (
            low.replace("-", "") in words or (len(parts[0]) > 1 and parts[0] in words)):
        return "e", low, case, *edges
    return "o", low, case, *edges


def english_context(toks: list[str]) -> set[int]:
    """Indices of syllable-shaped English words that this sentence proves English.

    A run is a stretch of ASCII words with no punctuation and no Vietnamese word
    inside. Four rules, each measured on the corpus (_internal/docs/TEXT_NORMALIZATION.md):
    a word that cannot be Vietnamese as spelled; a run holding an English grammar
    word; a rarely-Vietnamese word beside a certain English word written in the
    same case; "Go!" / "No!" standing alone. A toneless Vietnamese line is left alone.
    """
    kinds = [_kind(token) for token in toks]
    if not any(kind == "h" or low in ENGLISH_ONLY for kind, low, *_ in kinds):
        return set()
    if not any(kind[0] == "v" for kind in kinds):
        toneless = sum(kind == "o" and vietnamese(low) for kind, low, *_ in kinds)
        certain = sum(kind == "e" and low not in ENGLISH_ONLY for kind, low, *_ in kinds)
        if toneless >= 2 and toneless > certain:
            return set()

    def joined(left: int) -> bool:
        """No punctuation between this token and the next."""
        return not kinds[left][4] and not kinds[left + 1][3]

    found: set[int] = set()
    index = 0
    while index < len(toks):
        if kinds[index][0] not in ("e", "h", "o"):
            index += 1
            continue
        start = index
        while index + 1 < len(toks) and kinds[index + 1][0] in ("e", "h", "o") and joined(index):
            index += 1
        end = index
        index += 1
        # Touching a Vietnamese word with nothing between: that edge may belong to the Vietnamese sentence.
        open_left = start > 0 and kinds[start - 1][0] == "v" and joined(start - 1)
        open_right = end + 1 < len(toks) and kinds[end + 1][0] == "v" and joined(end)
        size = end - start + 1
        others = sum(kinds[i][0] == "o" for i in range(start, end + 1))
        # A capitalised grammar word may be a name ("Will bay."): one alone is no evidence.
        function = [kinds[i][2] for i in range(start, end + 1) if kinds[i][1] in FUNCTION]
        grammar = size >= 2 and 3 * others <= size and (len(function) >= 2 or any(case != "T" for case in function))
        for i in range(start, end + 1):
            kind, low, case = kinds[i][:3]
            if low in ENGLISH_ONLY:
                # Two capitals alone are an abbreviation ("ngành IT"); in a shouted run they are the word ("STOP IT!").
                if case != "U" or len(low) > 2 or any(start <= j <= end and kinds[j][2] == "U" for j in (i - 1, i + 1)):
                    found.add(i)
                continue
            if kind != "h":
                continue
            if grammar and (low in WEAK or not ((i == start and open_left) or (i == end and open_right))):
                found.add(i)
                continue
            if low in WEAK and not any(0 <= j < len(toks) and kinds[j][1] == low for j in (i - 1, i + 1)):  # "the the", "hi hi"
                for j in (i - 1, i + 1):
                    if not start <= j <= end or kinds[j][0] != "e" or (j < i and low in FOLLOWED):
                        continue
                    first = min(i, j)
                    if (low in SINGLE or (case == "l") == (kinds[j][2] == "l")
                            or (kinds[first][2] != "l" and first == start and not open_left)):
                        found.add(i)
            # The whole exclamation ("Go!", "[Yes / No]"), not a quoted word inside a Vietnamese sentence.
            if (size == 1 and low in ALONE
                    and (i == 0 or not kinds[i - 1][0] or any(ch in _BREAKS for ch in kinds[i - 1][4]))
                    and (i + 1 == len(toks) or any(ch in _BREAKS for ch in kinds[i][4]))
                    and not (i + 1 < len(toks) and _NUMBER.match(toks[i + 1]))):  # "No. 7", "No. III"
                found.add(i)
    return found


def loanword_english(toks: list[str]) -> set[int]:
    """Indices of `names.LOANWORDS` words that sit inside an English run and so stay English ("Game over", "the net", "talk show").

    A run here is a stretch, with no punctuation inside, of loanwords and words that are certainly English
    (kind "e") or proven English by the sentence (`english_context`), with "a" / "I" between them ("Like a
    rolling stone"). A toneless Vietnamese syllable or an unknown ASCII word ends it: in "ngồi trên sofa xem TV" and "chơi game hay xem anime" the loanword stands
    alone (measured 11-11: the wider run of `english_context` kept those English). The run is English when it
    holds such a word that is not itself a loanword: "board game", "fan service", "nick name", "I like you".
    A capitalised English word inside the sentence beside a lowercase or shouted loanword is a name
    ("fan Rose", "BAN Rose"), not evidence; at the start of a sentence it is ("Talk show"). Loanwords never
    count as evidence for each other: "chơi game online", "admin BAN nick".
    """
    loan = {i for i, token in enumerate(toks) if names.split_token(token)[1].lower() in names.LOANWORDS}
    if not loan:
        return set()
    kinds = [_kind(token) for token in toks]
    flagged = english_context(toks)
    found: set[int] = set()
    member = [i in loan or i in flagged or kinds[i][0] == "e" or kinds[i][1] in SINGLE for i in range(len(toks))]
    index = 0
    while index < len(toks):
        if not member[index]:
            index += 1
            continue
        start = index
        while index + 1 < len(toks) and member[index + 1] and not kinds[index][4] and not kinds[index + 1][3]:
            index += 1
        span = range(start, index + 1)
        index += 1
        for i in span:
            if i not in loan:
                continue
            if any(j not in loan and (j in flagged or (kinds[j][0] == "e" and (
                    kinds[j][2] != "T" or kinds[i][2] == "T" or names.sentence_start(toks, j)))) for j in span):
                found.add(i)
    return found


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
    english = english_context(toks)
    for index, token in enumerate(toks):
        if index in protected:
            continue
        before, core, after = names.split_token(token)
        from .abbreviations import contextual_letters, pronoun_ai, standard_reading

        if contextual_letters(core, toks, index) or (out[index] == token and index not in english and letter_name(toks, index)):
            out[index] = before + english_letters(core) + after
            continue
        if pronoun_ai(toks, index) or standard_reading(core, toks, index, before, after):
            continue
        if not core or before[-1:].isdigit() or re.match(r"^[-–]?\d", after):
            continue
        if core in POLICY["preserve_acronyms"]:
            continue
        if asian[index] != token:
            continue
        if index in english:
            from .abbreviations import spelled

            shouted = len(core) > 1 and core.isupper()
            marked = "<en>" + (core.lower() if shouted else core) + "</en>"
            expanded = spelled(core) if shouted else None  # the abbreviation rule already spelled the capitals out
            if out[index].casefold() == token.casefold():
                out[index] = before + marked + after
                continue
            if expanded and expanded in out[index]:
                out[index] = out[index].replace(expanded, marked, 1)
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
                and out[index].casefold() != token.casefold()):
            # A foreign spelling decision cannot undo structural/sound-effect TN.
            continue
        # A changed chapter/volume/level label is structural, not a foreign word.
        if core.lower() in {"chap", "vol", "lv", "lvl"} and out[index] != token:
            continue
        out[index] = before + choice[0] + after
