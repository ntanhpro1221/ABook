"""Corrections at the shared VieNeu phoneme boundary, after text normalization."""
from __future__ import annotations

import re
from typing import Callable

_GI = re.compile(r"(?<!\w)gi(?!\w)", re.IGNORECASE)
_BARE_Z = re.compile(r"(?<!\S)z(?=[.,!?;:…]*(?:\s|$))")
_INTERJECTION = re.compile(r"(?<![\w'-])([A-Za-z]+(?:['’][A-Za-z]+)*)[!?]")
_VOWELS = "aeiouyæɐɑɒɔəɘɛɜɤɯɵøœʉʊʌɪɨɚɝᵻᵿ"
_STRESSED_DIPHTHONG = re.compile(r"^(wˈ)(e(?=ɪ)|o(?=ʊ)|a(?=[ɪʊ])|ɔ(?=ɪ))")
_SYLLABIC_O = re.compile(r"o[.,!?;:…]*")
_LETTER_O = re.compile(r"ˈo([.,!?;:…]*)")


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
