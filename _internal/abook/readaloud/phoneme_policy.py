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
_LETTER_RUN = re.compile(r"[^\W\d_]+")
_SENTENCE = re.compile(r"[^.!?…;:\n\"“”«»「」『』]+")  # a quoted shout is a sentence of its own
_QUOTES = " \t\r\n\"'“”‘’«»()[]{}「」『』〈〉《》【】—–-*"
_SENTENCE_END = ".!?…:;"
_PHONEME_MARKS = ".,!?"
_STRONG = frozenset(".!?;:…")  # a neighbour beyond one of these is no neighbour
_IDENTITY = frozenset("Vahs")  # word classes whose very word is evidence, not only its kind
_FOREIGN = "efnX"
_LETTERS = re.compile("[a-z]+")
_LOWER = re.compile(r"(?<![\w'’<>/])[a-z]+(?![\w'’])")
_TONE = re.compile("[2-6ɜ]")  # sea-g2p's tone marks: a Vietnamese reading has one unless its tone is level
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
        # Tier 1 is sure outside [doubt[0], doubt[1]); a word written as a name is Vietnamese from name_threshold, in doubt from name_doubt.
        self.doubt = (int(data["doubt"][0]), int(data["doubt"][1]))
        self.name_threshold, self.name_doubt = int(data["name_threshold"]), int(data["name_doubt"])
        self.sentinels = tuple(data["sentinels"])
        self.find = re.compile(r"(?<![\w'’])(?:" + "|".join(sorted(self.listed)) + r")(?![\w'’])", re.IGNORECASE)


@lru_cache(maxsize=1)
def _shared() -> _Shared:
    return _Shared()


class Rulings:
    """What a book already knows about its shared words (shared_rulings.py): the second tier's answers by context
    (`shared_word_contexts` key -> Vietnamese?), the roster's Vietnamese names ("an", "long") and its foreign names
    that are spelled like a Vietnamese syllable ("dan", "tom": `english_names`), lower-case."""

    __slots__ = ("contexts", "names", "foreign")

    def __init__(self, contexts: dict[str, bool] | None = None, names: frozenset[str] | set[str] | None = None,
                 foreign: frozenset[str] | set[str] | None = None) -> None:
        self.contexts = dict(contexts or {})
        self.names = frozenset(names or ())
        self.foreign = frozenset(foreign or ())

    def __bool__(self) -> bool:
        return bool(self.contexts or self.names or self.foreign)


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


def capitalised(text: str, source: str | None = None) -> frozenset[str]:
    """ASCII words written as a name, lower-cased: a capital inside a sentence, or shouting ("admin BAN nick", "TOKYO BAY").

    The first word of a sentence proves nothing, and the normalizer lower-cases
    everything before the phonemizer sees it, so the caller collects these from
    the text as it was spoken - and from `source`, the text as it was WRITTEN,
    because the text layer lower-cases a shouted word before it is spoken. A
    sentence shouted from end to end ("BAY ĐI!", "LUNG LAY!") is prose; only the
    written text can tell (spoken, half of the shout is lower-case already).
    """
    found = set()
    for value in (text, source):
        if not value:
            continue
        for match in _CAPITAL.finditer(value):
            word = match.group()
            if len(word) > 1 and word.isupper():
                if source and value is not source:
                    continue
                sentence = next(part.group() for part in _SENTENCE.finditer(value) if part.start() <= match.start() < part.end())
                if any(run != run.upper() for run in _LETTER_RUN.findall(sentence)):
                    found.add(word.lower())
                continue
            head = value[:match.start()].rstrip(_QUOTES)
            if head and head[-1] not in _SENTENCE_END:
                found.add(word.lower())
    return frozenset(found)


@contextmanager
def sentence_case(text: str, source: str | None = None, rulings: "Rulings | None" = None) -> Iterator[None]:
    """Remember `capitalised(text, source)` and the book's rulings for a frontend that only hands over normalized chunks (Studio)."""
    previous = getattr(_case, "capitals", frozenset()), getattr(_case, "rulings", None), getattr(_case, "named", frozenset())
    _case.capitals, _case.rulings = capitalised(text, source), rulings
    _case.named = written_names(text, source) & rulings.foreign if rulings else frozenset()
    try:
        yield
    finally:
        _case.capitals, _case.rulings, _case.named = previous


@contextmanager
def book_rulings(rulings: "Rulings | None") -> Iterator[None]:
    """Remember the book's rulings for the phonemizer of this thread ("Nghe ngay": the clip service knows the book, the
    engine many calls below only sees pieces of text)."""
    previous = getattr(_case, "rulings", None)
    _case.rulings = rulings
    try:
        yield
    finally:
        _case.rulings = previous


def remembered_case() -> frozenset[str]:
    return getattr(_case, "capitals", frozenset())


def remembered_rulings() -> "Rulings | None":
    return getattr(_case, "rulings", None)


def remembered_named() -> frozenset[str]:
    """The roster's foreign names this utterance writes as a name (`english_names`)."""
    return getattr(_case, "named", frozenset())


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


def shared_word_scores(text: str, capitals: frozenset[str] = frozenset()) -> list[tuple[str, int, bool]]:
    """(word, score, written as a name) for every table word of normalized `text`, in order.

    The score is the learned sum of _internal/docs/SHARED_WORDS.md, in hundredths
    of a logit that the occurrence is Vietnamese: what the word is over a million
    corpus occurrences, the kind of each neighbour and of the two together, how
    much more often that very neighbour stands beside the word when it is
    Vietnamese, the kind of the word one further out, whether the chunk has any
    Vietnamese diacritic and what share of it is certainly English or certainly
    Vietnamese, whether the text layer tagged the word, whether it is doubled.
    A word alone in an <en> tag counts, a longer tag does not. The last field is
    True for a word of `capitals`: its score is the one it would have as prose.
    """
    shared = _shared()
    tokens = _shared_tokens(text, capitals)
    english = sum(kind in "eX" for _, kind, _ in tokens)
    accented = sum(kind == "V" for _, kind, _ in tokens)
    others = len(tokens) - 1
    out: list[tuple[str, int, bool]] = []
    for index, (word, kind, _) in enumerate(tokens):
        entry = shared.words.get(word)
        if entry is None:
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
        out.append((word, score, kind == "n"))
    return out


def shared_word_contexts(text: str) -> list[str]:
    """The key of every table word of normalized `text`, in order: two words each side as the phonemizer sees them.

    A ruling of the second tier (shared_rulings.py) is stored under this key, so
    a reader with no model finds it again in the same sentence: "^" stands for
    the edge of the chunk or a `. ! ? ; : …`, a comma is kept as ",".
    """
    tokens = _shared_tokens(text, frozenset())
    listed = _shared().listed

    def side(index: int, step: int) -> list[str]:
        found: list[str] = []
        at = index
        while len(found) < 2:
            other = at + step
            if not 0 <= other < len(tokens):
                found.append("^")
                break
            gap = tokens[max(at, other)][2]
            if _STRONG.intersection(gap):
                found.append("^")
                break
            found.append(("," if gap else "") + tokens[other][0] if step < 0 else tokens[other][0] + ("," if gap else ""))
            at = other
        return found

    return [" ".join(reversed(side(index, -1))) + "|" + word + "|" + " ".join(side(index, 1))
            for index, (word, _, _) in enumerate(tokens) if word in listed]


def shared_word_verdicts(text: str, capitals: frozenset[str] = frozenset(),
                         rulings: "Rulings | None" = None) -> list[tuple[str, bool, bool, str]]:
    """(word, Vietnamese?, sure?, who decided) for every table word of normalized `text`, in order.

    Tier 1 is the score: prose is Vietnamese from `threshold` up and sure outside
    the `doubt` band; a word written as a name (a capital mid-sentence, shouting)
    is only called Vietnamese from `name_threshold` up and is in doubt from
    `name_doubt` up. One shape is in doubt whatever its score: a word that opens
    a sentence, then a certainly English word, then an accented Vietnamese one
    ("Do trans sắp thi", "Do blog tồn tại") - in the corpus sample that is a
    Vietnamese sentence with a borrowed noun, never an English one, and a short
    sentence drags the score down by its share of English words. Tier 2 answers the doubtful ones where a model is at hand
    (Studio); its rulings travel with the book, so a reader without a model
    (the phone) gets the same answer: a ruling for this very context, then the
    book's Vietnamese names (a character of the roster called "An": every "An"
    written as a name, a doubtful one in prose, and one that opens a sentence
    unless an English word follows it - "An nói." but "An apple"), then tier 1's
    own best guess.
    """
    shared = _shared()
    keys = shared_word_contexts(text) if rulings else []
    tokens = _shared_tokens(text, capitals)
    heads: list[bool] = []  # opens a sentence and no English word follows: where a roster name is a name
    borrowed: list[bool] = []  # opens a sentence, then an English word, then an accented Vietnamese one
    for index, (word, _, gap) in enumerate(tokens):
        if word not in shared.words:
            continue
        opens = "^" in gap or bool(_STRONG.intersection(gap))
        english = index + 1 < len(tokens) and not tokens[index + 1][2] and tokens[index + 1][1] in "eX"
        heads.append(opens and not english)
        borrowed.append(opens and english and index + 2 < len(tokens) and not tokens[index + 2][2] and tokens[index + 2][1] == "V")
    out: list[tuple[str, bool, bool, str]] = []
    for position, (word, score, name) in enumerate(shared_word_scores(text, capitals)):
        if name:
            claimed, sure = score >= shared.name_threshold, not shared.name_doubt <= score < shared.name_threshold
        else:
            claimed = score >= shared.threshold
            sure = not (shared.doubt[0] <= score < shared.doubt[1] or (borrowed[position] and not claimed))
        who = "table"
        if rulings:
            ruled = rulings.contexts.get(keys[position])
            if ruled is not None:
                claimed, sure, who = ruled, True, "ruling"
            elif word in rulings.names and (name or not sure or heads[position]):
                claimed, sure, who = True, True, "roster"
            elif word in rulings.foreign and (name or heads[position]):
                claimed, sure, who = False, True, "roster"
        out.append((word, claimed, sure, who))
    return out


def vietnamese_shared(text: str, capitals: frozenset[str] = frozenset(), rulings: "Rulings | None" = None) -> list[int]:
    """Which shared words of normalized `text` are Vietnamese: positions among the table's words of `text`.

    sea-g2p holds 231 words in both dictionaries and gives each the language of
    its nearest unambiguous neighbour, English on a tie, and an unknown name
    counts as English: "con boss to quá", "quay sang Susan", "Lucy bay" come
    out /tuː/, /sæŋ/, /beɪ/. The decision is `shared_word_verdicts`.
    """
    return [position for position, (_, claimed, _, _) in enumerate(shared_word_verdicts(text, capitals, rulings)) if claimed]


def _reading(word: str, g2p: Callable[[str], str]) -> tuple[str, str]:
    """(Vietnamese, English) phonemes of one shared word, from the dictionary that is loaded."""
    if word not in _readings:
        _readings[word] = (g2p("ạ " + word + " ạ").split()[1], g2p("<en>" + word + "</en>").strip())
    return _readings[word]


def _listed_spans(value: str) -> list[tuple[int, int, str]]:
    """(start, end, word) of every table word of `value`; a word alone in an <en> tag spans the whole tag."""
    listed = _shared().listed
    found = []
    for match in _TOKEN.finditer(value):
        if match.group(3):
            continue
        word = (match.group(1)[4:-5].strip() if match.group(1) else match.group(2)).lower()
        if word in listed:
            found.append((*match.span(), word))
    return found


def english_read(given: str, phonemes: str, g2p: Callable[[str], str]) -> list[bool] | None:
    """For every table word of `given` (the phonemizer's input, `phonemes` its output): did sea-g2p read it English?

    All of them are swapped for one stand-in at once; the stand-in takes the
    language sea-g2p gives that place. None when the places cannot be told apart.
    """
    shared = _shared()
    spans = _listed_spans(given)
    if not spans:
        return []
    before = phonemes.split()
    spoken = {match.group(2).lower() for match in _TOKEN.finditer(given) if match.group(2)}
    for sentinel in shared.sentinels:
        if sentinel in spoken:
            continue
        marked = given
        for start, end, _ in reversed(spans):
            marked = marked[:start] + sentinel + marked[end:]
        after = g2p(marked).split()
        places = [index for index, (new, old) in enumerate(zip(after, before)) if new != old]
        if len(after) != len(before) or len(places) != len(spans):
            continue
        vietnamese, english = _reading(sentinel, g2p)
        cores = [after[index].rstrip(_PHONEME_MARKS) for index in places]
        if all(core in (vietnamese, english) for core in cores):
            return [core == english for core in cores]
    return None


def written_names(text: str, source: str | None = None) -> frozenset[str]:
    """ASCII words written with a capital wherever they stand, lower-cased - also the one that opens a sentence
    ("Dan!", "Dan cười."), which `capitalised` leaves out. A word that is also there in lower case is not one."""
    upper: set[str] = set()
    lower: set[str] = set()
    for value in (text, source):
        if value:
            upper.update(match.group().lower() for match in _CAPITAL.finditer(value))
            lower.update(_LOWER.findall(value))
    return frozenset(upper - lower)


def english_names(given: str, raw: str, phonemes: str, g2p: Callable[[str], str], words: frozenset[str]) -> str:
    """Give a foreign roster name that is spelled like a Vietnamese syllable its English sound ("Dan" /zaːn/ -> /dæn/).

    sea-g2p has no English entry for such a word, not even inside an <en> tag: the Vietnamese syllable wins. It does
    read the possessive in English ("dan's" -> /dˈænz/, "tom's" -> /tˈɑːmz/), so each of `words` is swapped for its
    possessive in the phonemizer's input only (`given`; `raw` is its output) and the closing /z/ or /s/ is dropped:
    every phoneme is sea-g2p's own. A swap that moves any other word, or that does not come back as one English
    word, is thrown away and the name stays as it was in `phonemes`.
    """
    if not words:
        return phonemes
    tokens, before, out = given.split(), raw.split(), phonemes.split()
    if not len(tokens) == len(before) == len(out):
        return phonemes
    changed = False
    for index, token in enumerate(tokens):
        match = _LETTER_RUN.search(token)
        if match is None or match.group() not in words or _LETTER_RUN.search(token, match.end()):
            continue
        marked = list(tokens)
        marked[index] = token[:match.end()] + "'s" + token[match.end():]
        after = g2p(" ".join(marked)).split()
        if len(after) != len(before) or any(new != old for at, (new, old) in enumerate(zip(after, before)) if at != index):
            continue
        said = after[index].rstrip(_PHONEME_MARKS)
        if len(said) < 3 or said[-1] not in "zs" or _TONE.search(said):
            continue
        out[index] = said[:-1] + out[index][len(out[index].rstrip(_PHONEME_MARKS)):]
        changed = True
    return " ".join(out) if changed else phonemes


def restore_vietnamese(text: str, phonemes: str, source: str | Callable[[], str], g2p: Callable[[str], str],
                       capitals: frozenset[str] = frozenset(), rulings: "Rulings | None" = None) -> str:
    """Give the shared words that `vietnamese_shared` claims their Vietnamese phonemes.

    `phonemes` is `g2p(source)`; `text` is the chunk the decision is made on.
    The spoken text is not touched: there is no Vietnamese tag, invisible
    characters do not isolate a word, and real punctuation would move the ASR
    anchors, the cache key and the rhythm. Each claimed word is swapped, in the
    phonemizer's input only, for another shared word that is not in the
    sentence. sea-g2p resolves a run of shared words as one unit, so the swap
    changes no other word's language, and the stand-in's phonemes mark the
    exact place. A result that differs anywhere else is thrown away. Every
    phoneme put in is sea-g2p's own Vietnamese reading of that word.
    """
    shared = _shared()
    present = {word.lower() for word in shared.find.findall(text)}
    if not present or not any(_reading(word, g2p)[1] in phonemes for word in present):
        return phonemes  # nothing was read as English: the usual sentence ends here
    proven = vietnamese_shared(text, capitals, rulings)
    if not proven:
        return phonemes
    given = source() if callable(source) else source
    spans = _listed_spans(given)
    if [word for *_, word in spans] != [word for *_, word in _listed_spans(text)]:
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
