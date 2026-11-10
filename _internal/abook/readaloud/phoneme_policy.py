"""Corrections at the shared VieNeu phoneme boundary, after text normalization."""
from __future__ import annotations

import re
import threading
from contextlib import contextmanager
from functools import lru_cache
from typing import Callable, Iterator

_GI = re.compile(r"(?<!\w)gi(?!\w)", re.IGNORECASE)
_BARE_Z = re.compile(r"(?<!\S)z(?=[.,!?;:…]*(?:\s|$))")
_INTERJECTION = re.compile(r"(?<![\w'-])([A-Za-z]+(?:['’][A-Za-z]+)*)[!?]")
_VOWELS = "aeiouyæɐɑɒɔəɘɛɜɤɯɵøœʉʊʌɪɨɚɝᵻᵿ"
_STRESSED_DIPHTHONG = re.compile(r"^(wˈ)(e(?=ɪ)|o(?=ʊ)|a(?=[ɪʊ])|ɔ(?=ɪ))")
_SYLLABIC_O = re.compile(r"o[.,!?;:…]*")
_LETTER_O = re.compile(r"ˈo([.,!?;:…]*)")
# sea-g2p's own tokens (src/g2p/mod.rs RE_TOKEN): an <en> span, a word, one punctuation mark.
_TOKEN = re.compile(r"(<en>.*?</en>)|(\w+(?:['’]\w+)*)|([^\w\s])", re.IGNORECASE)
_CAPITAL = re.compile(r"(?<![\w'’<>/])[A-Z][A-Za-z]*(?![\w'’])")
_QUOTES = " \t\r\n\"'“”‘’«»()[]{}「」『』〈〉《》【】—–-*"
_SENTENCE_END = ".!?…:;"
_PHONEME_MARKS = ".,!?"
_STRONG = frozenset(".!?;:…")  # a neighbour beyond one of these is no neighbour
_IDENTITY = frozenset("Vahs")  # word classes whose very word is evidence, not only its kind
_FOREIGN = "efnX"
_LETTERS = re.compile("[a-z]+")
_APOSTROPHE = re.compile("['’]")
_readings: dict[str, tuple[str, str]] = {}
_case = threading.local()


def repair_syllabic_gi(text: str, phonemes: str) -> str:
    """sea-g2p emits bare /z/ for standalone ``gi`` instead of the syllable /zi/.

    Romaji ji becomes the owner's Vietnamese ``gi`` (also inside hyphenated
    names). Require matching counts before repairing the missing nucleus;
    consonants inside other phoneme words and ordinary ``gì`` are untouched.
    """
    count = len(_GI.findall(text))
    if not count or count != len(_BARE_Z.findall(phonemes)):
        return phonemes
    return _BARE_Z.sub("zˈi", phonemes)


def repair_syllabic_o(text: str, phonemes: str) -> str:
    """A bare o surviving the first normalizer pass is a name syllable.

    The package normalizes again and reads it as the letter ô. Align whole
    normalized words before restoring /ɔ/; a literal source letter has already
    become ô on the first pass. This matches the reader's keep_lone_o rule.
    """
    words, phones = text.split(), phonemes.split()
    if len(words) != len(phones):
        return phonemes
    changed = False
    for index, (word, phone) in enumerate(zip(words, phones)):
        if _SYLLABIC_O.fullmatch(word) and _LETTER_O.fullmatch(phone):
            phones[index] = "ˈɔ" + phone[2:]
            changed = True
    return " ".join(phones) if changed else phonemes


def emphasize_english_interjections(text: str, phonemes: str, g2p: Callable[[str], str]) -> str:
    """Give a short English cry strong stress; sustain a diphthong after /w/.

    The dictionary's weak function-word stress and brief /w/ + diphthongs can
    collapse into neighboring Vietnamese syllables in VieNeu. Only a known,
    unambiguously foreign word immediately before ?/! is eligible. Keep all
    words, punctuation and inference boundaries, and never add a second length
    marker. This is phonetic emphasis, not a spelling alias for ASR.
    """
    from . import names
    from .english_policy import POLICY, vietnamese

    for match in _INTERJECTION.finditer(text):
        word = match.group(1).lower()
        if (word not in names.english_words() and word not in POLICY["english_words"]
                or vietnamese(word) or word in names.JAPANESE_COMMON):
            continue
        original = g2p(word).strip()
        # Short interjections have at most two nuclei; do not retime long words.
        if not original or len(re.findall(r"[" + _VOWELS + r"]+", original.replace("ː", ""))) > 2:
            continue
        strong = original.replace("ˌ", "ˈ")
        strong = _STRESSED_DIPHTHONG.sub(r"\1\2ː", strong, count=1)
        if strong != original:
            phonemes = re.sub(r"(?<!\S)" + re.escape(original) + r"(?=[!?])", lambda _: strong, phonemes)
    return phonemes


class _Shared:
    """The learned table `shared_words.json` (scripts/build_shared_words.py, _internal/docs/SHARED_WORDS.md)."""

    def __init__(self) -> None:
        import json
        from pathlib import Path

        data = json.loads(Path(__file__).with_name("shared_words.json").read_text(encoding="utf-8"))
        self.words: dict[str, dict] = data["words"]
        self.listed = frozenset(self.words)  # the words the table may call Vietnamese
        self.shared = frozenset(data["shared"])  # every word sea-g2p holds in both dictionaries with two sounds
        self.classes = {name: index for index, name in enumerate(data["classes"])}
        self.foreign = frozenset(self.classes[name] for name in _FOREIGN)
        self.second = data["second"]
        self.coarse, self.pair = data["coarse"], data["pair"]  # the two neighbours taken together, each as one of five kinds
        self.no_diacritics, self.tagged = int(data["no_diacritics"]), int(data["tagged"])
        self.english_share, self.vietnamese_share = int(data["english_share"]), int(data["vietnamese_share"])
        self.threshold = int(data["threshold"])
        self.sentinels = tuple(data["sentinels"])
        self.find = re.compile(r"(?<![\w'’])(?:" + "|".join(sorted(self.listed)) + r")(?![\w'’])", re.IGNORECASE)


@lru_cache(maxsize=1)
def _shared() -> _Shared:
    return _Shared()


@lru_cache(maxsize=8192)
def _word_class(word: str) -> str:
    """The kind of one lower-case word of a normalized chunk.

    V a Vietnamese syllable with a diacritic, o other non-ASCII, e certainly
    English, s in both sea-g2p dictionaries with two sounds, h a toneless
    Vietnamese syllable that is also an English word, a a toneless syllable
    that is not, f any other ASCII word (a name, romaji).
    """
    from .english_policy import ENGLISH_ONLY, FUNCTION, vietnamese
    from .names import english_words

    if not word.isascii():
        return "V" if vietnamese(word) else "o"
    if word in ENGLISH_ONLY or word in FUNCTION:
        return "e"
    if word in _shared().shared:
        return "s"
    if _LETTERS.fullmatch(word) and vietnamese(word):
        return "h" if word in english_words() else "a"
    return "e" if word in english_words() or _APOSTROPHE.split(word)[0] in english_words() else "f"


def capitalised(text: str) -> frozenset[str]:
    """ASCII words written with a capital inside a sentence, lower-cased: names, not prose.

    The first word of a sentence proves nothing, and the normalizer lower-cases
    everything before the phonemizer sees it, so the caller collects these from
    the text as it was spoken.
    """
    found = set()
    for match in _CAPITAL.finditer(text):
        head = text[:match.start()].rstrip(_QUOTES)
        if head and head[-1] not in _SENTENCE_END:
            found.add(match.group().lower())
    return frozenset(found)


@contextmanager
def sentence_case(text: str) -> Iterator[None]:
    """Remember `capitalised(text)` for a frontend that only hands over normalized chunks (Studio)."""
    previous = getattr(_case, "capitals", frozenset())
    _case.capitals = capitalised(text)
    try:
        yield
    finally:
        _case.capitals = previous


def remembered_case() -> frozenset[str]:
    return getattr(_case, "capitals", frozenset())


def _shared_tokens(text: str, capitals: frozenset[str]) -> list[tuple[str, str, str]]:
    """(word, class, punctuation before it) for every sea-g2p word of `text`; an <en> span is one token of class X."""
    out: list[tuple[str, str, str]] = []
    gap = "^"
    for match in _TOKEN.finditer(text):
        if match.group(3):
            gap += match.group(3)
            continue
        if match.group(1):
            out.append((match.group(1)[4:-5].strip().lower(), "X", gap))
        else:
            word = match.group(2).lower()
            out.append((word, "n" if word in capitals and word.isascii() else _word_class(word), gap))
        gap = ""
    return out


def vietnamese_shared(text: str, capitals: frozenset[str] = frozenset()) -> list[int]:
    """Which shared words of normalized `text` the sentence makes Vietnamese.

    sea-g2p holds 231 words in both dictionaries and gives each the language of
    its nearest unambiguous neighbour, English on a tie, and an unknown name
    counts as English: "con boss to quá", "quay sang Susan", "Lucy bay" come
    out /tuː/, /sæŋ/, /beɪ/. Returned are positions among the table's words of
    `text`, in order (a word alone in an <en> tag counts, a longer tag does not).

    The decision is a learned score, not a rule list (_internal/docs/SHARED_WORDS.md):
    what the word is over a million corpus occurrences, the kind of each
    neighbour and of the two together, how much more often that very neighbour
    stands beside the word when it is Vietnamese, the kind of the word one
    further out, whether the chunk has any Vietnamese diacritic and what share
    of it is certainly English or certainly Vietnamese, whether the text layer
    tagged the word, whether it is doubled. A word written with a capital
    mid-sentence is a name and is never claimed.
    """
    shared = _shared()
    tokens = _shared_tokens(text, capitals)
    english = sum(kind in "eX" for _, kind, _ in tokens)
    accented = sum(kind == "V" for _, kind, _ in tokens)
    others = len(tokens) - 1
    proven: list[int] = []
    position = -1
    for index, (word, kind, _) in enumerate(tokens):
        entry = shared.words.get(word)
        if entry is None:
            continue
        position += 1
        if kind == "n":
            continue
        score = entry["p"]
        foreign = 0
        pair = 0
        for side, step in (("l", -1), ("r", 1)):
            other = index + step
            if not 0 <= other < len(tokens):
                found = shared.classes["^"]
            else:
                gap = tokens[max(index, other)][2]
                beside, its = tokens[other][0], tokens[other][1]
                found = shared.classes[its if not gap else "^" if _STRONG.intersection(gap) else ",v" if its in _IDENTITY else ",x"]
            score += entry[side][found]
            pair = pair * 5 + shared.coarse[found]
            if not 0 <= other < len(tokens) or gap:
                continue
            foreign += found in shared.foreign
            if its in _IDENTITY:
                score += entry[side.upper()].get(beside, 0)
            further = other + step
            if not 0 <= further < len(tokens) or tokens[max(other, further)][2]:
                second = "|"
            else:
                second = "v" if tokens[further][1] == "V" else "t" if tokens[further][1] in "ahs" else "x"
            score += shared.second[side.upper()][second]
        score += shared.pair[pair]
        if foreign == 2:
            score += entry["f"]
        if not accented:
            score += shared.no_diacritics
        if others:  # how much of the chunk is certainly English, how much certainly Vietnamese
            score += shared.english_share * (english - (kind == "X")) // others + shared.vietnamese_share * accented // others
        if kind == "X":
            score += shared.tagged
        if any(0 <= other < len(tokens) and tokens[other][0] == word for other in (index - 1, index + 1)):
            score += entry["x"]
        if score >= shared.threshold:
            proven.append(position)
    return proven


def _reading(word: str, g2p: Callable[[str], str]) -> tuple[str, str]:
    """(Vietnamese, English) phonemes of one shared word, from the dictionary that is loaded."""
    if word not in _readings:
        _readings[word] = (g2p("ạ " + word + " ạ").split()[1], g2p("<en>" + word + "</en>").strip())
    return _readings[word]


def restore_vietnamese(text: str, phonemes: str, source: str | Callable[[], str], g2p: Callable[[str], str],
                       capitals: frozenset[str] = frozenset()) -> str:
    """Give the shared words that `vietnamese_shared` claims their Vietnamese phonemes.

    `phonemes` is `g2p(source)`; `text` is the chunk the decision is made on.
    The spoken text is not touched: there is no Vietnamese tag, invisible
    characters do not isolate a word, and real punctuation would move the ASR
    anchors, the cache key and the rhythm. Each claimed word is swapped, in the
    phonemizer's input only, for another shared word that is not in the
    sentence. sea-g2p resolves a run of shared words as one unit, so the swap
    changes no other word's language, and the stand-in's phonemes mark the
    exact place. A result that differs anywhere else is thrown away.
    """
    shared = _shared()
    present = {word.lower() for word in shared.find.findall(text)}
    if not present or not any(_reading(word, g2p)[1] in phonemes for word in present):
        return phonemes  # nothing was read as English: the usual sentence ends here
    proven = vietnamese_shared(text, capitals)
    if not proven:
        return phonemes
    given = source() if callable(source) else source

    def listed(value: str) -> list[tuple[int, int, str]]:
        found = []
        for match in _TOKEN.finditer(value):
            if match.group(3):
                continue
            word = (match.group(1)[4:-5].strip() if match.group(1) else match.group(2)).lower()
            if word in shared.listed:
                found.append((*match.span(), word))  # the stand-in takes the place of the whole <en> tag
        return found

    spans = listed(given)
    if [word for *_, word in spans] != [word for *_, word in listed(text)]:
        return phonemes  # the second normalization moved a shared word: do not guess
    before = phonemes.split()
    claimed = [spans[position] for position in proven]
    spoken = {match.group(2).lower() for match in _TOKEN.finditer(given) if match.group(2)}
    for sentinel in shared.sentinels:
        if sentinel in spoken:
            continue
        marked = given
        for start, end, _ in reversed(claimed):
            marked = marked[:start] + sentinel + marked[end:]
        after = g2p(marked).split()
        places = [index for index, (new, old) in enumerate(zip(after, before)) if new != old]
        if len(after) != len(before) or len(places) != len(claimed):
            continue
        out = list(before)
        for index, (*_, word) in zip(places, claimed):
            vietnamese, english = _reading(word, g2p)
            core = before[index].rstrip(_PHONEME_MARKS)
            if after[index].rstrip(_PHONEME_MARKS) not in _reading(sentinel, g2p) or core not in (vietnamese, english):
                break
            out[index] = vietnamese + before[index][len(core):]
        else:
            return " ".join(out)
    return phonemes
