"""Bound the spoken copy without changing display units or normal inference calls."""
from __future__ import annotations

import re
from typing import Any, Callable

from ..text_processing import normalize_vocalizations_for_tts
from ..vieneu_limits import (
    VIENEU_HALVING_DEPTH, VIENEU_MAX_UNBROKEN_CHARS,
    break_unsplittable_runs, halve_at_word, must_halve_vieneu_text,
    INPUT_POLICY,
)

VERSION = INPUT_POLICY["version"]


def unit_limit(max_chars: int) -> int:
    # The existing unit packer can merge a <20-character neighbour at either
    # end. Preserve those ordinary calls while bounding the spoken copy.
    return max_chars + INPUT_POLICY["short_unit_slack_chars"]


def bounded_pieces(pieces: list[str], limit: int) -> list[list[str]]:
    # Existing shouts already handles ordinary cries. Only pathological words
    # need Studio's additional normalizer; normal pieces retain their bytes.
    prepared = [re.sub(r"\S{%d,}" % (VIENEU_MAX_UNBROKEN_CHARS + 1),
                       lambda m: normalize_vocalizations_for_tts(m.group()), p) for p in pieces]
    prepared = [break_unsplittable_runs(p) for p in prepared]
    text = " ".join(prepared)
    if len(text) <= limit:
        return [prepared]
    chunks = []
    while len(text) > limit:
        cut = text.rfind(" ", 0, limit + 1)
        if cut <= 0:
            cut = limit
        chunks.append([text[:cut]])
        text = text[cut:].lstrip()
    if text:
        chunks.append([text])
    return chunks


def read_unit(pieces: list[str], source: str, limit: int, rate: int,
              phonemize: Callable[..., str], infer: Callable[[str], Any]) -> tuple[Any, str]:
    import numpy as np
    from . import vieneu_engine as ve
    from .model import stop_if_cancelled

    def read(group: list[str], original: str, depth: int = 0) -> tuple[Any, str]:
        stop_if_cancelled()
        text = " ".join(group)
        ph = phonemize(group, source=original)
        if not ph:
            return np.zeros(0, dtype=np.float32), ph
        try:
            return infer(ph), ph
        except Exception as error:
            halves = halve_at_word(text) if depth < VIENEU_HALVING_DEPTH and must_halve_vieneu_text(error, text) else None
            if halves is None:
                raise
        # Leave the exception scope before allocating another inference's tensors.
        results = [read([half], half, depth + 1) for half in halves]
        waves, phonemes = zip(*results)
        return ve.join(list(waves), rate, [ve.gap_after(phonemes[0])])[0], phonemes[-1]

    chunks = bounded_pieces(pieces, limit)
    results = [read(group, source if len(chunks) == 1 else " ".join(group)) for group in chunks]
    if len(results) == 1:
        return results[0]
    waves, phonemes = zip(*results)
    return ve.join(list(waves), rate, [ve.gap_after(ph) for ph in phonemes[:-1]])[0], phonemes[-1]
