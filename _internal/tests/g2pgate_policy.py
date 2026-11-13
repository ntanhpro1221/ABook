"""Text oracle, independent of spoken_tokens/phonemize; adapted from judge2.

Class is evidence supplied by the book/roster, never inferred from G2P output.
English-origin words may use native English or the policy's Vietnamese reading.
No acoustic inference and no word-specific fixes, except explicit owner rulings.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from abook.english_vi import vietnamized_english
from abook.readaloud import abbreviations, names
from abook.readaloud.english_policy import POLICY
from abook.readaloud.vieneu_engine import _sea
from abook.romanization import romanized_reading

OWNER = {
    ("Dan", "western"): "đan",
    ("Rose", "western"): "râu dơ",
    ("to", "loanword"): "tu",
    ("No", "loanword"): "nâu",
    ("Y", "acronym"): "i",
}
MARKS = "\u0301\u0300\u0309\u0303\u0323"
TONES = frozenset("23456ɜ7")


def normalized_phones(value: str) -> str:
    """Exactly feat_text.py normalization (length and stress are not tone)."""
    return re.sub(r"[ˈˌ\s.,!?…\"“”:;\-\u032a]", "", value).replace("ː", "").replace("1", "")


def words(value: str) -> list[str]:
    value = unicodedata.normalize("NFC", value)
    value = re.sub(r"</?[a-z-]+>|\[note\d+\]", " ", value)
    return re.findall(r"[^\W\d_]+|\d+", value.lower())


from g2pgate_dictionary import vietnamese_phone


def canonical_reading(token: str, token_class: str) -> str | None:
    """None means unsupported policy spelling, NOT genuine text ambiguity."""
    if (token, token_class) in OWNER:
        return OWNER[token, token_class]
    if token_class in {"vietnamese", "chinese"}:
        return " ".join(words(token))  # Chinese corpus uses the written Sino-Vietnamese reading.
    if token_class in {"japanese", "korean"}:
        reading = romanized_reading(token, "ja" if token_class == "japanese" else "ko")
        return " ".join(words(reading)) if reading else None
    if token_class == "mixed":
        if re.search(r"(.)\1{2,}", token, re.IGNORECASE):
            from abook.readaloud import shouts

            said = [token]
            shouts.read_shouts([token], said, "ja")
            if said != [token]:
                return " ".join(words(said[0]))
        if any(not ch.isascii() for ch in token):
            return " ".join(words(token.replace("Ð", "Đ")))
        if "-" in token and any(part.lower() in names.HONORIFICS for part in token.split("-")[1:]):
            reading = names.honorific_reading(token, "ja")
            if reading:
                return " ".join(words(reading))
        # A suffix belongs to its name, while case boundaries retain separate components.
        langs = ("ko", "ja") if any(m in token.lower() for m in names.KO_MARKS) else ("ja", "ko")
        for lang in langs:
            reading = romanized_reading(token, lang)
            if reading:
                return " ".join(words(reading))
        return vietnamized_english(token)
    if token_class == "acronym":
        lower = token.lower()
        if lower in POLICY["case_sensitive_abbreviations"] and not token.isupper():
            return lower
        expansion = POLICY["vietnamese_abbreviations"].get(lower) or POLICY["spoken_abbreviations"].get(lower)
        if lower in {"lv", "lvl"}:
            expansion = abbreviations.LEVEL_NAMES[lower]
        if expansion:
            return " ".join(words(expansion))
        return (
            " ".join(words(" ".join(abbreviations.LETTERS[ch] for ch in lower)))
            if lower.isascii() and lower.isalpha()
            else None
        )
    if token_class in {"loanword", "western"}:
        return names.loanword_reading(token) or vietnamized_english(token)
    raise ValueError(token_class)


def canonical_options(token: str, token_class: str) -> list[str]:
    reading = canonical_reading(token, token_class)
    options = []
    if reading:
        try:
            options.append(" ".join(vietnamese_phone(w) for w in words(reading)))
        except ValueError:
            # The dictionary attests no Vietnamese syllable for a spelling such as
            # "mylene": no Vietnamese-reading target exists, so only other options apply.
            pass
        # Owner accepted eun -> an, but rejected eum -> am (judge2 feat_text).
        if any(w.endswith("ưn") for w in words(reading)):
            options.append(
                " ".join(vietnamese_phone(w[:-2] + "ân" if w.endswith("ưn") else w) for w in words(reading))
            )
    if (token_class in {"western", "loanword"} or token_class == "mixed" and not reading) and (
        token,
        token_class,
    ) not in OWNER:
        options.append(_sea().g2p.convert("<en>" + token.lower() + "</en>"))
    if (
        token_class == "acronym"
        and token not in {"K", "Y"}
        and not (token.lower() in POLICY["case_sensitive_abbreviations"] and not token.isupper())
    ):
        # Current direct-English policy spells codes with English letter names.
        from abook.readaloud.english_policy import english_letters

        options.append(_sea().g2p.convert(english_letters(token.upper())))
    if token_class == "mixed" and "-" in token:
        head, *suffixes = token.split("-")
        from abook.readaloud.japanese_policy import _lexically_guarded

        western_head = (
            head.lower() in names.english_words()
            or _lexically_guarded(head)
            or romanized_reading(head, "ja") is None
        )
        if western_head and suffixes and all(s.lower() in names.HONORIFICS for s in suffixes):
            tail = romanized_reading("-".join(suffixes).capitalize(), "ja")
            if tail:
                options.append(
                    _sea().g2p.convert("<en>" + head.lower() + "</en>")
                    + " "
                    + " ".join(vietnamese_phone(w) for w in words(tail))
                )
    if token == "No" and token_class == "loanword":
        options.append(vietnamese_phone("nô"))
    if token == "Y" and token_class == "acronym":
        options.append(vietnamese_phone("oai"))
    if not options:
        raise ValueError(f"No attested canonical reading for {token_class}:{token}")
    return list(dict.fromkeys(options))


def ambiguity(token: str, token_class: str) -> str | None:
    if token_class == "loanword" and token.isupper() and len(token) <= 2 and re.search("[AEIOU]", token):
        return "An English word versus an initialism requires sentence context."
    if (
        token_class == "acronym"
        and token.lower() in {"vn", "ktx", "ai"}
        and not (token.lower() in POLICY["case_sensitive_abbreviations"] and not token.isupper())
    ):
        return "Context distinguishes an identifier, a word/pronoun, or a contextual expansion."
    if token_class == "acronym" and set(token.lower()) <= set("ivxlcdm"):
        return "Roman numeral versus an initialism requires the missing sentence."
    if token_class == "acronym" and len(token) >= 4 and romanized_reading(token.capitalize(), "ja"):
        return "An all-capital proper/brand word versus an initialism: spelling alone does not choose."
    return None
