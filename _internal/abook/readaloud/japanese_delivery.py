"""Which words of a VieNeu unit are automatic Japanese readings.

The model reads them as ordinary Vietnamese syllables (one phonological word each): joining a name into
one word lost syllables on both engines (A1, 11-11: CTC name errors 47 % joined vs 24 % split on Turbo,
58 % vs 13 % on Nano). Only `japanese_audio` uses these spans, to tighten silences inside a name.
"""
from __future__ import annotations

import re
from typing import Iterable, Mapping

from .japanese_policy import POLICY, contextual_names, reading

_WORD = re.compile(r"[^\W\d_]+_?(?:-[^\W\d_]+_?)+")


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


def anchor_spans(text: str, anchors: Iterable[dict]) -> list[tuple[int, int]]:
    """Exact, nonoverlapping automatic spans of a Studio row."""
    spans = set()
    for anchor in anchors:
        if (anchor.get("reading_namespace") == POLICY["namespace"]
                and anchor.get("source") != "listener_choice"):
            start, end = int(anchor["spoken_start"]), int(anchor["spoken_end"])
            if 0 <= start < end <= len(text) and text[start:end] == anchor["spoken_form"]:
                spans.add((start, end))
    # Nested or overlapping anchors have no unique owner.
    selected = sorted(spans)
    return [(start, end) for start, end in selected
            if not any(a < end and b > start and (a, b) != (start, end) for a, b in selected)]
