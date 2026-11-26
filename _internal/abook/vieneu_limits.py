"""Shared VieNeu input limits for Studio and immediate reading; no engine imports."""
from __future__ import annotations

import json
import re
from pathlib import Path

INPUT_POLICY = json.loads(Path(__file__).with_name("vieneu_input_policy.json").read_text(encoding="utf-8"))

FATAL_TTS_MARKERS = tuple(INPUT_POLICY["fatal_error_markers"])
# Somebody else's memory pressure, which ends when they end. Release what this process
# holds, wait, and try the attempt again.
TRANSIENT_TTS_MEMORY_MARKERS = tuple(INPUT_POLICY["memory_error_markers"])


def is_transient_tts_memory_error(error: BaseException) -> bool:
    """A failure that ends when whoever took the memory gives it back."""
    message = str(error).casefold()
    if any(marker in message for marker in FATAL_TTS_MARKERS):
        return False
    return any(marker in message for marker in TRANSIENT_TTS_MEMORY_MARKERS)


VIENEU_MAX_UNBROKEN_CHARS = INPUT_POLICY["max_unbroken_chars"]
VIENEU_HALVING_DEPTH = INPUT_POLICY["halving_depth"]
VIENEU_OOM_HALVING_MIN_CHARS = INPUT_POLICY["oom_halving_min_chars"]
_VIENEU_LENGTH_MARKERS = tuple(INPUT_POLICY["length_error_markers"])
_UNBROKEN_RUN = re.compile(r"\S{%d,}" % (VIENEU_MAX_UNBROKEN_CHARS + 1))


def break_unsplittable_runs(text: str) -> str:
    """Chèn khoảng trắng vào chuỗi không khoảng trắng dài hơn `VIENEU_MAX_UNBROKEN_CHARS` để bộ chia mẩu của VieNeu cắt được.
    Chỉ bản gửi VieNeu; chữ khác giữ nguyên từng byte."""
    def cut(match: re.Match[str]) -> str:
        run = match.group(0)
        return " ".join(run[start:start + VIENEU_MAX_UNBROKEN_CHARS] for start in range(0, len(run), VIENEU_MAX_UNBROKEN_CHARS))

    return _UNBROKEN_RUN.sub(cut, text)


def must_halve_vieneu_text(error: BaseException, text: str) -> bool:
    """Lỗi do mẩu quá dài: bộ đệm KV không vừa prompt (luôn), hay hết bộ nhớ trên mẩu dài hơn một mẩu VieNeu."""
    message = str(error).casefold()
    if any(marker in message for marker in _VIENEU_LENGTH_MARKERS):
        return True
    out_of_memory = isinstance(error, MemoryError) or type(error).__name__ == "OutOfMemoryError" or is_transient_tts_memory_error(error)
    return out_of_memory and len(text) > VIENEU_OOM_HALVING_MIN_CHARS


def halve_at_word(text: str) -> tuple[str, str] | None:
    """Hai nửa của `text`, cắt ở khoảng trắng gần giữa nhất (không có khoảng trắng: cắt giữa chuỗi). None khi không còn chia được."""
    stripped = text.strip()
    if len(stripped) < 2:
        return None
    middle = len(stripped) // 2
    gaps = [match.span() for match in re.finditer(r"\s+", stripped)]
    if gaps:
        start, end = min(gaps, key=lambda span: abs((span[0] + span[1]) / 2 - middle))
        return stripped[:start], stripped[end:]
    return stripped[:middle], stripped[middle:]
