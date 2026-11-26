"""VieNeu không bao giờ nhận một mẩu vượt bộ đệm của nó.

Sự cố 26-11: một đoạn là 15.023 chữ "ồ" liền. Bộ chuẩn hoá chỉ nhận nguyên âm kéo dài KHÔNG dấu thanh, nên chuỗi đi nguyên vào
VieNeu; VieNeu chỉ cắt mẩu ở khoảng trắng, nên prompt 1.413 token không vừa bộ đệm 1.024 ("does not fit a cache"), hay CUDA OOM rồi
tiến trình treo 1,5 giờ. Không GPU ở đây: VieNeu là một stub từ chối mẩu dài hơn N ký tự đúng như bản thật từ chối. Mọi chuỗi là
chuỗi tổng hợp, không có chữ truyện.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest

from abook.audio_io import AudioQualityError
from abook.text_processing import normalize_vocalizations_for_tts
from abook.tts import (
    VIENEU_HALVING_DEPTH,
    VIENEU_MAX_UNBROKEN_CHARS,
    VieNeuEngine,
    break_unsplittable_runs,
    halve_at_word,
)

SAMPLE_RATE = 24_000
SAMPLES_PER_CHAR = 50


class _CachedVieNeu:
    """Như VieNeu v3 Turbo: mẩu dài hơn `limit` ký tự không vừa bộ đệm."""

    def __init__(self, limit: int, error: type[BaseException] = ValueError, message: str | None = None) -> None:
        self.limit = limit
        self.error = error
        self.message = message
        self.calls: list[str] = []

    def infer(self, text: str, **_kwargs: object) -> np.ndarray:
        self.calls.append(text)
        if len(text) > self.limit:
            raise self.error(self.message or f"prompt of {len(text) * 3} tokens does not fit a cache of {self.limit * 3}")
        return np.full(len(text) * SAMPLES_PER_CHAR, 0.5, dtype=np.float32)


def _engine(stub: _CachedVieNeu) -> VieNeuEngine:
    engine = VieNeuEngine({"tts": {"sample_rate": SAMPLE_RATE, "batch_size": 1}}, lambda _line: None)
    engine.tts = stub
    engine.voices = ["giong"]
    engine.sample_rate = SAMPLE_RATE
    return engine


def _speak(engine: VieNeuEngine, text: str) -> np.ndarray:
    row = {"text": text, "speaker": "NARRATOR"}
    profile = {"engine": "vieneu", "preset_name": "giong", "voice_key": "giong"}
    return engine.generate_one(row, profile, 7, sampling={})


# ---- bản gửi TTS -------------------------------------------------------------------------------------------------------------------


def test_fifteen_thousand_held_accented_vowels_become_one_short_cry() -> None:
    assert normalize_vocalizations_for_tts("ồ" * 15023) == "Ồ... ồ"


@pytest.mark.parametrize(
    ("written", "spoken"),
    [
        ("“ồồồồ!”", "“Ồ... ồ!”"),
        ("ỒỒỒỒ", "Ồ... ồ"),
        ("ứứứ", "Ứ... ứ"),
        ("ơơơơ", "Ơ... ơ"),
        ("Áaaaa", "Á... a"),
        ("aaaa", "A... a"),
    ],
)
def test_a_held_vowel_with_or_without_a_tone_mark_reads_the_same_way(written: str, spoken: str) -> None:
    assert normalize_vocalizations_for_tts(written) == spoken


@pytest.mark.parametrize(
    ("written", "spoken"),
    [
        ("hhhhhhh", "hhhh"),
        ("Zzzzzzzzz", "Zzzz"),
        ("Khôôôôôông", "Khôôôông"),
    ],
)
def test_any_other_letter_run_is_capped_at_the_repetition_limit(written: str, spoken: str) -> None:
    assert normalize_vocalizations_for_tts(written) == spoken


def test_a_held_vowel_glued_to_another_letter_is_capped_too() -> None:
    assert normalize_vocalizations_for_tts("x" + "ồ" * 15023) == "xồồồồ"


@pytest.mark.parametrize("text", ["1000000", "Khôôôông", "Ôaaa", "Có 1000000 người ở đây."])
def test_numbers_and_short_stretches_are_left_alone(text: str) -> None:
    assert normalize_vocalizations_for_tts(text) == text


# ---- engine VieNeu -----------------------------------------------------------------------------------------------------------------


def test_a_piece_vieneu_refuses_is_halved_until_every_piece_fits() -> None:
    words = " ".join(f"tu{index:03d}" for index in range(200))  # 1.199 ký tự, khoảng trắng đều
    stub = _CachedVieNeu(limit=200)
    wave = _speak(_engine(stub), words)
    spoken = [text for text in stub.calls if len(text) <= stub.limit]
    assert spoken, "không mẩu nào được đọc"
    assert " ".join(spoken).split() == words.split(), "chia đôi phải giữ đủ và đúng thứ tự mọi từ"
    assert wave.size >= sum(len(text) for text in spoken) * SAMPLES_PER_CHAR * 0.9


def test_a_run_without_spaces_is_broken_before_vieneu_sees_it() -> None:
    stub = _CachedVieNeu(limit=400)
    wave = _speak(_engine(stub), "ồ" * 15023)
    read = [text for text in stub.calls if len(text) <= stub.limit]
    assert wave.size > 0
    assert "".join("".join(read).split()) == "ồ" * 15023
    assert all(len(word) <= VIENEU_MAX_UNBROKEN_CHARS for text in read for word in text.split())


def test_a_short_piece_out_of_memory_is_left_to_the_memory_wait_path() -> None:
    """OOM trên mẩu ngắn là máy thiếu bộ nhớ, không phải mẩu quá dài: không chia (chia sẽ làm audio phụ thuộc tình trạng máy)."""
    stub = _CachedVieNeu(limit=10, error=RuntimeError, message="CUDA out of memory. Tried to allocate 2.00 GiB")
    with pytest.raises(AudioQualityError, match="out of memory"):
        _speak(_engine(stub), "một câu ngắn thôi")
    assert len(stub.calls) == 1


def test_a_long_piece_out_of_memory_is_halved() -> None:
    words = " ".join(["chữ"] * 150)  # 599 ký tự
    stub = _CachedVieNeu(limit=300, error=RuntimeError, message="CUDA out of memory. Tried to allocate 2.00 GiB")
    assert _speak(_engine(stub), words).size > 0
    assert all(len(text) <= 300 for text in stub.calls[1:])


def test_halving_has_a_floor_and_then_the_original_error_surfaces() -> None:
    stub = _CachedVieNeu(limit=0)  # từ chối mọi mẩu
    with pytest.raises(AudioQualityError, match="does not fit a cache"):
        _speak(_engine(stub), " ".join(["chữ"] * 400))
    assert len(stub.calls) < 2 ** (VIENEU_HALVING_DEPTH + 1)


def test_the_same_text_is_read_byte_for_byte_when_nothing_is_refused() -> None:
    stub = _CachedVieNeu(limit=10_000)
    _speak(_engine(stub), "Một câu bình thường, không có gì lạ.")
    assert stub.calls == ["Một câu bình thường, không có gì lạ."]


def test_halving_cuts_at_the_space_nearest_the_middle() -> None:
    assert halve_at_word("một hai ba bốn") == ("một hai", "ba bốn")
    assert halve_at_word("abcdef") == ("abc", "def")
    assert halve_at_word("a") is None


def test_breaking_runs_touches_only_runs_longer_than_the_limit() -> None:
    text = "câu thường " + "x" * (VIENEU_MAX_UNBROKEN_CHARS * 2 + 1) + " 1000000"
    broken = break_unsplittable_runs(text)
    assert broken.startswith("câu thường ") and broken.endswith(" 1000000")
    assert broken.replace(" ", "") == text.replace(" ", "")
    assert break_unsplittable_runs("x" * VIENEU_MAX_UNBROKEN_CHARS) == "x" * VIENEU_MAX_UNBROKEN_CHARS


# ---- lỗi ở luồng chính không để tiến trình sống mãi ---------------------------------------------------------------------------------


def test_a_refused_piece_on_the_main_thread_lets_the_process_exit() -> None:
    internal = Path(__file__).resolve().parents[1]
    script = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(internal)!r})
        sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})
        from test_vieneu_never_gets_a_piece_past_its_cache import _CachedVieNeu, _engine, _speak
        _speak(_engine(_CachedVieNeu(limit=0)), "ồ" * 15023)
        """
    )
    done = subprocess.run([sys.executable, "-X", "utf8", "-c", script], capture_output=True, text=True,
                          encoding="utf-8", timeout=120, cwd=internal,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert done.returncode != 0
    assert "does not fit a cache" in done.stderr
