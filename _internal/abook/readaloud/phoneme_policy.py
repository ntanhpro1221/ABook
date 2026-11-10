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
    def __init__(self) -> None:
        from .english_policy import ENGLISH_ONLY, FUNCTION, POLICY, SINGLE, WEAK

        data = POLICY["shared_vietnamese"]
        self.words = frozenset(data["words"])
        self.strong = frozenset(data["strong"])
        self.before_english = frozenset(data["before_english"])
        self.nouns = frozenset(data["nouns"])
        self.echo = frozenset(data["echo"])
        self.pairs = frozenset((first, second) for first, second in data["pairs"])
        self.sentinels = tuple(data["sentinels"])
        self.listed = self.words | self.echo | {word for pair in self.pairs for word in pair}
        self.never_toneless = ENGLISH_ONLY | WEAK | FUNCTION | SINGLE | self.listed
        self.english = ENGLISH_ONLY | FUNCTION
        self.find = re.compile(r"(?<![\w'’])(?:" + "|".join(sorted(self.listed)) + r")(?![\w'’])", re.IGNORECASE)


@lru_cache(maxsize=1)
def _shared() -> _Shared:
    return _Shared()


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


def vietnamese_shared(text: str, capitals: frozenset[str] = frozenset()) -> list[int]:
    """Which listed shared words of normalized `text` the sentence proves Vietnamese.

    sea-g2p holds 231 words in both dictionaries and gives each the language of
    its nearest unambiguous neighbour, English on a tie, and an unknown name
    counts as English: "con boss to quá", "quay sang Susan", "Lucy bay" come
    out /tuː/, /sæŋ/, /beɪ/. Returned are positions among the listed words of
    `text`, in order. Evidence, each rule measured on the corpus
    (_internal/docs/TEXT_NORMALIZATION.md): a Vietnamese word right after it;
    a Vietnamese word right before it unless an English word follows; a word
    that is a Vietnamese verb or preposition far more often than anything else
    standing between names; written laughter; a compound of two shared words.
    A word inside <en>, beside one, or written with a capital mid-sentence is
    never claimed.
    """
    from .english_policy import vietnamese
    from .names import english_words

    shared = _shared()
    words: list[str] = []
    joined: list[bool] = []  # no punctuation between this word and the one before
    explicit: list[bool] = []
    gap = True
    for match in _TOKEN.finditer(text):
        if match.group(3):
            gap = True
            continue
        words.append("" if match.group(1) else match.group(2).lower())
        # Spelled letters ("<en>G M</en>") name something; only a tagged word proves an English phrase.
        explicit.append(bool(match.group(1)) and any(len(part) > 1 for part in match.group(1)[4:-5].split()))
        joined.append(not gap)
        gap = False
    accented = any(not word.isascii() and vietnamese(word) for word in words)
    dictionary = english_words()
    kinds: dict[int, str] = {}

    def kind(index: int) -> str:
        """E explicit English, n a name, s listed, V Vietnamese, e certainly English, o anything else."""
        if index not in kinds:
            word = words[index]
            if explicit[index]:
                found = "E"
            elif not word or word in capitals:
                found = "n"
            elif word in shared.listed:
                found = "s"
            elif not word.isascii():
                found = "V" if vietnamese(word) else "o"
            elif accented and len(word) > 1 and word not in shared.never_toneless and vietnamese(word):
                found = "V"  # a toneless syllable in a Vietnamese sentence: "quay", "con", "ninh"
            elif word in shared.english or (word.isalpha() and word in dictionary):
                found = "e"
            else:
                found = "o"
            kinds[index] = found
        return kinds[index]

    listed = [index for index, word in enumerate(words) if word in shared.listed]
    open_ = [index for index in listed if kind(index) == "s"]
    proven: set[int] = set()

    def side(index: int, step: int) -> int | None:
        other = index + step
        if not 0 <= other < len(words) or not joined[max(index, other)]:
            return None
        return other

    def vietnamese_at(index: int | None) -> bool:
        return index is not None and (index in proven or kind(index) == "V")

    changed = True
    while changed:
        changed = False
        for index in open_:
            if index in proven:
                continue
            word = words[index]
            left, right = side(index, -1), side(index, 1)
            beside = [kind(other) if other is not None else "" for other in (left, right)]
            if "E" in beside:
                continue
            found = False
            if word in shared.words:
                if vietnamese_at(right):
                    found = not (word in shared.nouns and beside[0] == "e")  # "Lost Day là", "Big Bang ấy"
                elif vietnamese_at(left):
                    found = beside[1] in ("", "n", "s") or word in shared.before_english  # "leo rank", not "rất so cute"
                elif word in shared.strong and accented:
                    # "Julius sang Emily", "do Kaori"; not "say goodbye", not a bare "So, ..."
                    found = "e" not in beside and ("n" in beside or "o" in beside)
            if not found and word in shared.echo:
                found = any(0 <= other < len(words) and words[other] == word for other in (index - 1, index + 1))
            if not found:
                found = ((right is not None and (word, words[right]) in shared.pairs)
                         or (left is not None and (words[left], word) in shared.pairs))
            if found:
                proven.add(index)
                changed = True
    return [position for position, index in enumerate(listed) if index in proven]


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
        return [(*match.span(2), match.group(2).lower()) for match in _TOKEN.finditer(value)
                if match.group(2) and match.group(2).lower() in shared.listed]

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
