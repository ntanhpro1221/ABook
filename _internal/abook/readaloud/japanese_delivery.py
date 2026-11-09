"""Keep one automatic Japanese word together at the VieNeu phoneme boundary."""
from __future__ import annotations

import re
from typing import Callable, Iterable, Mapping

from .japanese_policy import POLICY, contextual_names, reading

_WORD = re.compile(r"[^\W\d_]+_?(?:-[^\W\d_]+_?)+")
_MARKED = re.compile(r"<en>([^<>\s]+)</en>")


def groups(tokens: list[str], origin: str | None, readings: Mapping[str, str] | None = None) -> set[str]:
    """Automatic spellings only; a listener's different reading never matches."""
    from .names import split_token
    from .readings import applicable

    if applicable(" ".join(tokens), readings):
        return set()

    contextual = contextual_names(tokens, origin)
    result: set[str] = set()
    for index, token in enumerate(tokens):
        _, core, _ = split_token(token)
        said = reading(core, origin, contextual=index in contextual)
        if said:
            result.update(match.group().casefold() for match in _WORD.finditer(said))
    return result


def mark(text: str, words: Iterable[str] | None = None) -> str:
    """Protect syllable boundaries through sea-g2p's existing English envelope.

    This string is private to inference. Stored spellings, ASR text and offsets
    use the ordinary Vietnamese reading. The phonemizer consumes the envelope.
    """
    chosen = None if words is None else {word.casefold() for word in words}
    joiner = POLICY["delivery"]["joiner"]
    return _WORD.sub(lambda m: "<en>" + m.group().replace("-", joiner) + "</en>"
                     if chosen is None or m.group().casefold() in chosen else m.group(), text)


def anchor_spans(text: str, anchors: Iterable[dict]) -> list[tuple[int, int]]:
    """Exact, nonoverlapping automatic spans; shared by phonemes and audio."""
    spans = set()
    for anchor in anchors:
        if (anchor.get("reading_namespace") == POLICY["namespace"]
                and anchor.get("source") != "listener_choice"):
            start, end = int(anchor["spoken_start"]), int(anchor["spoken_end"])
            if 0 <= start < end <= len(text) and text[start:end] == anchor["spoken_form"]:
                spans.add((start, end))
    # Nested or overlapping anchors have no unique delivery owner.
    selected = sorted(spans)
    return [(start, end) for start, end in selected
            if not any(a < end and b > start and (a, b) != (start, end) for a, b in selected)]


def mark_anchors(text: str, anchors: Iterable[dict]) -> str:
    """Use the exact materialized spans of automatic Japanese Studio anchors."""
    for start, end in reversed(anchor_spans(text, anchors)):
        text = text[:start] + mark(text[start:end]) + text[end:]
    return text


def phonemes(text: str, final: bool, plain: Callable[[str, bool], str]) -> str:
    """Join only marked words, retaining every phone and the source word boundary.

    Prefixes have a real following word while they are normalized, so a comma
    never becomes trailing punctuation and disappears. Only exact prefixes of
    the full ordinary stream can identify a name's span.
    """
    joiner = POLICY["delivery"]["joiner"]
    matches = [m for m in _MARKED.finditer(text) if joiner in m[1]
               and _WORD.fullmatch(m[1].replace(joiner, "-"))]
    if not matches:
        return plain(text, final)
    parts, spans = [], []
    cursor = length = 0
    for match in matches:
        prefix = text[cursor:match.start()]
        word = match[1].replace(joiner, "-")
        parts.extend((prefix, word))
        length += len(prefix)
        spans.append((length, length + len(word)))
        length += len(word)
        cursor = match.end()
    ordinary = "".join([*parts, text[cursor:]])
    baseline = plain(ordinary, final)
    context = POLICY["delivery"]["context_word"]
    context_phones = plain(context, False)

    def prefix_phones(end: int) -> str | None:
        value = plain(ordinary[:end] + " " + context, False)
        if value == context_phones:
            return ""
        suffix = " " + context_phones
        return value[:-len(suffix)] if context_phones and value.endswith(suffix) else None

    replacements = []
    for start, end in spans:
        left, right = prefix_phones(start), prefix_phones(end)
        if (left is None or right is None or not baseline.startswith(left)
                or not baseline.startswith(right) or not right.startswith(left)):
            continue
        first, last = len(left), len(right)
        if first < len(baseline) and baseline[first] == " ":
            first += 1
        if first >= last:
            continue
        if last < len(baseline) and baseline[last] not in " .,!?;:…)]}\"'’”":
            continue
        word = baseline[first:last]
        if not word or any(char in ".,!?;:…<>" for char in word):
            continue
        compact = "".join(word.split())
        if POLICY["delivery"]["stress"] in {"first", "secondary"}:
            seen = False
            kept = []
            for char in compact:
                if char in "ˈˌ":
                    if seen:
                        if POLICY["delivery"]["stress"] == "secondary":
                            kept.append("ˌ")
                        continue
                    seen = True
                kept.append(char)
            compact = "".join(kept)
        replacements.append((first, last, compact))
    for first, last, compact in reversed(replacements):
        baseline = baseline[:first] + compact + baseline[last:]
    return baseline
