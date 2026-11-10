"""Shared romaji phonotactics and Vietnamese fallback, with automatic provenance."""
from __future__ import annotations

import json
import gzip
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

POLICY = json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8"))
VERSION = int(POLICY["version"])
NAMESPACE = str(POLICY["namespace"])
PROVENANCE = str(POLICY["provenance"])
_LETTERS = "A-Za-zāīūēōâîûêôĀĪŪĒŌÂÎÛÊÔ"
_WORD = re.compile(rf"[{_LETTERS}]+(?:[-'][{_LETTERS}]+)*")
_NOTE = re.compile(r"\[note\d+\]", re.IGNORECASE)
_KNOWN_NAMES = frozenset(POLICY["known_names"])
BOOK_NAMES_RULE = f"{VERSION}.2"  # `book_name_readings`: 2 = capitals of any book that the book writes as a name ("KAEL" -> "Kael")
_SENTENCE_END = re.compile(r"[.!?…:;\"”’」』)\]】*~—–-]$")


@lru_cache(maxsize=1)
def lexical_guard() -> frozenset[str]:
    """General English vocabulary, including common Western proper nouns."""
    with gzip.open(Path(__file__).with_name("japanese_lexicon.txt.gz"), "rt", encoding="utf-8") as stream:
        return frozenset(stream.read().split())


def _lexically_guarded(head: str) -> bool:
    low = head.casefold()
    # The broad English asset also contains romanized Japanese proper nouns.
    # A Japanese onset plus a complete parse can preserve an established name
    # reading in a Japanese book. Ordinary English vocabulary still wins first.
    marked = any(onset in low for onset in [*POLICY["onsets"], "wa"])
    return low in lexical_guard() and not marked and low not in _KNOWN_NAMES


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
    while (len(parts) > 1 and len(parts[0]) < len(parts[-1])
           and parts[-1].casefold().startswith(parts[0].casefold())):
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
    parts = head.split("-")
    if (len(head) < 2 or not head[:1].isupper()
            or any(part[1:] != part[1:].lower() for part in parts)
            or is_vietnamese_syllable(head)
            or (head.casefold() in english_words() and not (origin == "ja" and head.casefold() in _KNOWN_NAMES))
            or (origin == "ja" and _lexically_guarded(head))
            or head.casefold() in POLICY["common"] or re.search(r"(.)\1\1", head.casefold())):
        return 0, False
    counts = [syllables(part) for part in parts]
    count = sum(counts) if all(counts) else 0
    return (count, honorific) if count and romanized_reading(head, "ja") else (0, False)


def routing_origin(surface: str, origin: str | None) -> str | None:
    if origin is not None:
        return origin
    words = surface.split()
    return "ja" if contextual_names(words) or any(_supported(word) for word in words) else None


def _supported(core: str) -> bool:
    from .names import honorific_reading, term_origin

    if core.casefold() in POLICY["common"] or (term_origin(core) == "ja" and honorific_reading(core, None)):
        return True
    count, honorific = _candidate(core)
    return bool(count and honorific)


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
    from .names import honorific_reading, loanword_reading, lone_syllable, name_reading, term_origin

    source = core
    core = _normalized(core, origin)
    if origin == "ko":
        return None
    # A suffix only Korean has settles the whole name, even in a Japanese book.
    if term_origin(core) == "ko" and "-" in core:
        return name_reading(core, "ko")
    # Lexical Japanese and joined addresses have their own evidence. A name
    # detector's negative result must not erase either earlier reading.
    lexical = loanword_reading(core)
    if core.casefold() in POLICY["common"] and lexical:
        return lexical
    address = honorific_reading(core, origin) if term_origin(core) != "ko" else None
    if address:
        return address
    # Short capitals belong to letter/number TN unless an adjacent name or
    # joined address supplies independent evidence. Case folding is not evidence.
    if source.isupper() and len(source) <= 4 and not contextual:
        return None
    count, honorific = _candidate(core, origin)
    minimum = POLICY["routing"]["known_ja_min_syllables" if origin == "ja" else "min_syllables"]
    if origin is None and not (contextual or honorific):
        return None
    # A one-nucleus vocalization with a written long vowel was already readable
    # in a Japanese book; it is not an English word merely because it is short.
    long_sound = origin == "ja" and count == 1 and bool(re.search(r"([aiueo])\1", core.casefold()))
    if not count or not (contextual or honorific or count >= minimum or long_sound):
        if origin == "ja" and not _lexically_guarded(_head(core)[0]):
            return _spoken_syllable(name_reading(core, origin))
        return None
    head, _ = _head(core)
    parts = core.split("-")
    if len(parts) > 1 and all(len(p) == 1 and p.casefold() == head[:1].casefold() for p in parts[:-1]):
        full = lone_syllable(romanized_reading(head, "ja"))
        if full:
            mora = full.split("-")[0]
            return "-".join([mora] * (len(parts) - 1) + [full.lower()])
    return _spoken_syllable(lone_syllable(romanized_reading(core, "ja")))


def _spoken_syllable(said: str | None) -> str | None:
    from .shouts import distinct_from_english

    return distinct_from_english(said) if said else said


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


def _spelled_output(core: str, before: str, after: str) -> str | None:
    """What letter TN already emitted for a capitalized word, if anything."""
    from .abbreviations import spelled
    from .names import closing

    said = spelled(core)
    return before + said + closing(after, said) if said else None


def _titled_names(toks: list[str], origin: str | None) -> set[str]:
    """Words of this text written as a readable name ("Yui"): evidence for their capitals ("YUI")."""
    from .names import split_token

    found = set()
    for token in toks:
        core = split_token(token)[1]
        if core[:1].isupper() and core[1:].islower() and _reading_word(core, origin):
            found.add(core.casefold())
    return found


def _korean_reading(toks: list[str], index: int, core: str) -> str | None:
    """A Korean-only suffix ("Ji-eun-ssi") or a hyphenated name beside a Korean surname ("Park Seo-joon") is Korean in any book."""
    from .names import KOREAN_SURNAMES, korean_hyphenated_name, name_reading, split_token, term_origin

    if "-" in core and term_origin(core) == "ko":
        return name_reading(core, "ko")
    if not index:
        return None
    _, surname, tail = split_token(toks[index - 1])
    if tail or surname.lower() not in KOREAN_SURNAMES or surname != surname.capitalize():
        return None
    return korean_hyphenated_name(core)


def apply_tokens(toks: list[str], out: list[str], origin: str | None) -> None:
    """VieNeu-only routing, before keep-English and explicit listener readings."""
    from .names import name_reading, split_token

    contextual = contextual_names(toks, origin) if origin != "ko" else set()
    titled = _titled_names(toks, origin) if origin == "ja" else set()
    said_here: dict[str, str] = {}
    read_indices: set[int] = set()
    for index, token in enumerate(toks):
        source = _NOTE.sub("", token) if origin == "ja" else token
        before, core, after = split_token(source)
        if not core or before[-1:].isdigit() or re.match(r"^[-–]?\d", after):
            continue
        korean = _korean_reading(toks, index, core) if origin == "ja" else None
        if korean:
            out[index] = before + korean + after
            continue
        previous_name = name_reading(core, origin)
        # Letter TN only lowercased a word it had judged readable ("YUUKI"), or a
        # capitalized form stands beside its own titled spelling ("Yui ... YUI").
        evidence = False
        if origin == "ja" and core.isupper() and out[index] == _spelled_output(core, before, after):
            from .abbreviations import spelled

            evidence = (spelled(core) == core.lower() and len(core) >= 4) or core.casefold() in titled
        if out[index] != token and out[index] != before + str(previous_name) + after and not evidence:
            # Structural TN, letter spelling, loanwords and honorifics own their
            # output. Only an earlier name reading may be replaced or rejected.
            continue
        said = reading(core, origin, contextual=index in contextual or evidence)
        if said:
            out[index] = before + said + after
            said_here[core.casefold()] = said
            read_indices.add(index)
        elif (origin == "ja" and _lexically_guarded(_head(_normalized(core, origin))[0])
              and out[index] == before + str(previous_name) + after):
            out[index] = token
    if origin == "ja":
        _echoes(toks, out, said_here, read_indices)


def _echoes(toks: list[str], out: list[str], said_here: dict[str, str], read_indices: set[int]) -> None:
    """A lowercase word repeats a reading this text already gave ("Doki doki"), and a sentence
    particle stays Japanese right after a read word ("Ii yo"). Capital evidence still keeps
    English words and unaccented Vietnamese out: neither ever enters `said_here`."""
    from ..romanization import romanized_reading
    from .names import split_token

    said_here = dict(said_here)
    for token, spoken in zip(toks, out):  # "D-Doki doki": the stutter already read the word
        if "… " in spoken:
            said_here.setdefault(split_token(token)[1].rsplit("-", 1)[-1].casefold(), split_token(spoken.rsplit("… ", 1)[1])[1])
    for index, token in enumerate(toks):
        before, core, after = split_token(token)
        if not core.islower() or out[index] != token:
            continue
        said = said_here.get(core)
        if said is None and core in POLICY["particles"] and index - 1 in read_indices and not split_token(toks[index - 1])[2]:
            said = romanized_reading(core, "ja")
        if said:
            out[index] = before + said.lower() + after


def _evidenced_reading(word: str) -> str | None:
    """The reading of a guarded word once the book shows it is a name. It must equal what the same
    word says with an honorific: otherwise (Mike-san -> "Mike-xan") it has no romaji route at all."""
    from ..analysis import is_vietnamese_syllable
    from ..romanization import romanized_reading
    from .names import honorific_reading, lone_syllable

    if not word[:1].isupper() or not word[1:].islower() or is_vietnamese_syllable(word) or not syllables(word):
        return None
    said = lone_syllable(romanized_reading(word, "ja"))
    address = honorific_reading(word + "-san", "ja")
    return said if said and address and address.casefold().startswith(said.casefold() + "-") else None


def book_name_readings(texts: Iterable[str], character_names: Iterable[str] = (), origin: str | None = "ja") -> dict[str, str]:
    """{surface: reading} for names a book proves by itself, so that one character is never
    read two ways. Fed to the per-book `readings` route, which listener readings still override.

    A Japanese book (`origin` "ja"). Evidence for a word the English lexicon guards ("Abe"): a
    joined honorific anywhere in the book ("Abe-san"), or a character name whose other word is
    plainly Japanese ("Abe Takeshi"). A lone guarded name in the character list is not enough: it
    may be Western ("Mike"). Evidence for capitals of at most four letters ("YUI"): the same word
    written as a name ("Yui").
    Any book. Capitals that would be spelled letter by letter ("KAEL", "LYRA") are a shouted name
    when the book writes the same word capitalized inside a sentence at least twice, or lists it as
    a word of a character name. Their reading is that capitalized spelling itself ("Kael"):
    `abbreviations.capital_words` then reads the capitals exactly as the name is read elsewhere.
    """
    from .abbreviations import WORD_FROM, _capital_word
    from .names import split_token

    guarded: set[str] = set()
    titled: dict[str, int] = {}
    capitals: set[str] = set()
    for text in texts:
        previous = ""
        for token in text.split():
            before, core, _ = split_token(_NOTE.sub("", token))
            inside = bool(previous) and not before and not _SENTENCE_END.search(previous)
            previous = token
            if not core.isascii():
                continue
            parts = core.split("-")
            if len(parts) == 2 and parts[1].casefold() in POLICY["honorifics"]:
                guarded.add(parts[0])
            elif len(parts) == 1 and core.isupper():
                capitals.add(core)
            elif len(parts) == 1 and core[:1].isupper() and core[1:].islower():
                titled[core] = titled.get(core, 0) + inside
    listed: set[str] = set()
    for surface in character_names:
        # The character list writes names in capitals ("ABE TAKESHI").
        words = [word.capitalize() if word.isupper() else word for word in surface.split()]
        listed.update(word for word in words if word.isascii() and word.isalpha() and word == word.capitalize())
        if origin == "ja" and len(words) > 1 and all(word.isascii() for word in words) and any(_reading_word(word, "ja") for word in words):
            guarded.update(words)
    found: dict[str, str] = {}
    if origin == "ja":
        for word in guarded:
            said = None if _reading_word(word, "ja") else _evidenced_reading(word)
            if said:
                found[word] = found[word.upper()] = said
        for capital in capitals:
            word = capital.capitalize()
            if 2 <= len(capital) <= 4 and (word in titled or word in found):
                said = found.get(word) or _reading_word(word, "ja")
                if said:
                    found[capital] = said
    for capital in capitals:
        word = capital.capitalize()
        if (capital not in found and len(capital) >= WORD_FROM and capital.isalpha()
                and (titled.get(word, 0) >= 2 or word in listed) and _capital_word(capital)):
            found[capital] = word
    return found


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
        if said is None and not (origin == "ja" and _lexically_guarded(_head(_normalized(raw, origin))[0])):
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
