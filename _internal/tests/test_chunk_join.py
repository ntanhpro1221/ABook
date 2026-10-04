"""Chia câu dài thành mảnh (`chunk_plan`) và nối mảnh (`join_chunks`) cho các máy đọc gọi từng mảnh (ZeroTTS 170 ký tự, Supertonic 300),
cùng việc ZeroTTS nạp lại phiên ONNX định kỳ mà không đổi một byte audio (docs/VOICE_BALANCE.md, join_report 04-10)."""
from __future__ import annotations

import itertools
import math
import random
from typing import Any

import numpy as np
import pytest

import abook.tts as tts_module
from abook.config import build_settings
from abook.tts import SupertonicEngine, ZeroTTSEngine, join_chunks

LIMIT = ZeroTTSEngine.MAX_CHUNK_CHARS
SAMPLE_RATE = 48_000
KEPT = 2 * tts_module.CHUNK_TRIM_KEEP_SECONDS


def sentence(index: int, length: int, mark: str = ".") -> str:
    """Câu `length` ký tự (kể cả dấu cuối), từ cố định để đếm được."""
    words: list[str] = []
    word = 0
    while sum(len(w) + 1 for w in words) < length - 4:
        words.append(f"từ{index}{word % 10}")
        word += 1
    body = " ".join(words)
    return body[:length - 1].rstrip() + mark


def comma_sentence(index: int, length: int, mark: str = ".") -> str:
    """Câu dài `length` ký tự với dấu phẩy sau mỗi ~5 từ."""
    words = [f"vế{index}{n % 10}" for n in range(length // 4)]
    text = ""
    for n, word in enumerate(words):
        text += word + ("," if n % 5 == 4 else "") + " "
        if len(text) >= length - 2:
            break
    return text.strip().rstrip(",")[:length - 1].rstrip(",") + mark


def rejoined(plan: list[tuple[str, str]]) -> str:
    return " ".join(chunk for chunk, _end in plan)


# ---- chia mảnh ---------------------------------------------------------------------------------------------------------------------


def test_a_short_line_is_one_chunk_with_its_end_mark() -> None:
    assert ZeroTTSEngine.chunk_plan("Về rồi?") == [("Về rồi?", "?")]
    assert ZeroTTSEngine.chunks("Về rồi?") == ["Về rồi?"]
    assert ZeroTTSEngine.chunk_plan("Không dấu cuối") == [("Không dấu cuối", "")]
    assert ZeroTTSEngine.chunk_plan("Anh bảo: \"đi đi.\"") == [("Anh bảo: \"đi đi.\"", ".")], "dấu đóng ngoặc không che dấu câu"


def test_an_engine_without_a_limit_never_splits() -> None:
    class Whole(tts_module.EngineAdapter):
        pass

    text = " ".join(sentence(i, 90) for i in range(10))
    assert Whole.chunk_plan(text) == [(text, ".")]


def test_whole_sentences_are_packed_up_to_the_limit() -> None:
    sentences = [sentence(i, 60 + 7 * i, "!?."[i % 3]) for i in range(8)]
    plan = ZeroTTSEngine.chunk_plan(" ".join(sentences))
    assert len(plan) > 1 and all(len(chunk) <= LIMIT for chunk, _end in plan)
    assert rejoined(plan) == " ".join(sentences)
    for chunk, end in plan:  # mảnh gồm NGUYÊN các câu, dấu cuối mảnh là dấu cuối câu cuối
        assert chunk in " ".join(sentences) and chunk.endswith(end)
        assert any(chunk == " ".join(sentences[a:b]) for a in range(8) for b in range(a + 1, 9))
    # gộp tham lam: thêm câu kế vào mảnh nào cũng vượt trần (trừ mảnh cuối)
    for (chunk, _end), (after, _e2) in itertools.pairwise(plan):
        first_next = after.split(". ")[0].split("? ")[0].split("! ")[0]
        assert len(chunk) + 1 + len(first_next) > LIMIT or len(chunk) < tts_module.CHUNK_MIN_CHARS


def test_a_long_sentence_is_cut_at_commas_into_the_fewest_even_chunks() -> None:
    long = comma_sentence(1, 520)
    assert len(long) > 3 * LIMIT
    plan = ZeroTTSEngine.chunk_plan(long)
    sizes = [len(chunk) for chunk, _end in plan]
    assert len(plan) == math.ceil((len(long) + 1) / (LIMIT + 1)) or len(plan) == math.ceil(len(long) / LIMIT)
    assert len(plan) == 4 and max(sizes) <= LIMIT
    assert max(sizes) - min(sizes) <= 40, "chia đều, không dồn cho đủ trần rồi để mẩu thừa"
    assert rejoined(plan) == long
    assert [end for _chunk, end in plan[:-1]] == [","] * (len(plan) - 1) and plan[-1][1] == "."


def test_pieces_of_a_long_sentence_do_not_join_the_neighbouring_sentences() -> None:
    before, after = sentence(1, 100), sentence(2, 100, "?")
    long = comma_sentence(3, 330)
    plan = ZeroTTSEngine.chunk_plan(f"{before} {long} {after}")
    assert rejoined(plan) == f"{before} {long} {after}"
    assert plan[0] == (before, ".") and plan[-1] == (after, "?")
    assert all(len(chunk) <= LIMIT for chunk, _end in plan)
    assert len(plan) >= 2 + math.ceil(len(long) / LIMIT)


def test_a_sentence_without_commas_is_cut_at_words() -> None:
    long = sentence(1, 400)
    plan = ZeroTTSEngine.chunk_plan(long)
    assert len(plan) == 3 and all(len(chunk) <= LIMIT for chunk, _end in plan)
    assert rejoined(plan) == long
    assert [end for _chunk, end in plan] == ["", "", "."], "cắt giữa câu ở từ không có dấu"


def test_a_word_longer_than_the_limit_is_hard_cut() -> None:
    word = "a" * (LIMIT * 2 + 10)
    plan = ZeroTTSEngine.chunk_plan(f"Mở đầu {word} kết thúc.")
    assert all(len(chunk) <= LIMIT for chunk, _end in plan)
    assert "".join(rejoined(plan).split()) == "".join(f"Mở đầu {word} kết thúc.".split())


def test_a_short_orphan_joins_the_neighbour_when_it_still_fits() -> None:
    long = comma_sentence(1, 300)
    plan = ZeroTTSEngine.chunk_plan(f"{long} Vâng.")
    assert len(plan) == 2 and plan[-1][0].endswith("Vâng.") and plan[-1][1] == "."
    assert all(len(chunk) >= tts_module.CHUNK_MIN_CHARS for chunk, _end in plan)
    # không vừa trần thì giữ riêng
    tight = comma_sentence(2, 2 * LIMIT - 4)
    plan = ZeroTTSEngine.chunk_plan(f"{tight} Vâng.")
    assert all(len(chunk) <= LIMIT for chunk, _end in plan)


def test_chunks_rejoin_to_the_original_text_for_assorted_texts() -> None:
    rng = random.Random(7)
    for limit_engine in (ZeroTTSEngine, SupertonicEngine):
        for _ in range(60):
            parts = []
            for index in range(rng.randint(2, 14)):
                length = rng.choice([8, 25, 60, 120, 170, 240, 420, 700])
                make = rng.choice([sentence, comma_sentence])
                parts.append(make(index, length, rng.choice(".!?…")))
            text = " ".join(parts)
            plan = limit_engine.chunk_plan(text)
            assert all(0 < len(chunk) <= limit_engine.MAX_CHUNK_CHARS for chunk, _end in plan), [len(c) for c, _ in plan]
            assert rejoined(plan) == " ".join(text.split())
            assert limit_engine.chunks(text) == [chunk for chunk, _end in plan]


# ---- nối mảnh ----------------------------------------------------------------------------------------------------------------------


def burst(amplitude: float = 0.3, lead: float = 0.1, voiced: float = 0.3, trail: float = 0.12) -> np.ndarray:
    tone = amplitude * np.sin(2 * np.pi * 440 * np.arange(int(voiced * SAMPLE_RATE)) / SAMPLE_RATE)
    return np.concatenate([np.zeros(int(lead * SAMPLE_RATE)), tone, np.zeros(int(trail * SAMPLE_RATE))]).astype(np.float32)


KEEP = int(tts_module.CHUNK_TRIM_KEEP_SECONDS * SAMPLE_RATE)


def trimmed_length(wave: np.ndarray, *, head: bool, tail: bool) -> int:
    frame = int(tts_module.CHUNK_TRIM_FRAME_SECONDS * SAMPLE_RATE)  # lặng đo theo khung 5 ms
    count = wave.size // frame
    loud = np.flatnonzero(np.abs(wave[:count * frame]).reshape(count, frame).max(axis=1) > 1e-3)
    start = max(0, int(loud[0]) * frame - KEEP) if head else 0
    stop = min(wave.size, (int(loud[-1]) + 1) * frame + KEEP) if tail else wave.size
    return stop - start


def test_one_chunk_is_returned_as_it_is() -> None:
    wave = burst()
    out = join_chunks([wave], SAMPLE_RATE, ["."])
    assert out.dtype == np.float32 and np.array_equal(out, wave)
    assert join_chunks([], SAMPLE_RATE).size == 0
    loud = burst(amplitude=1.4)
    assert np.array_equal(join_chunks([loud], SAMPLE_RATE), loud), "một mảnh không qua bước nào của nối"


@pytest.mark.parametrize(
    ("mark", "total"),
    [(".", 0.27), ("…", 0.27), ("?", 0.31), ("!", 0.28), (",", 0.20), ("", 0.20), (";", 0.20)],
)
def test_the_silence_between_chunks_follows_the_end_mark_of_the_first(mark: str, total: float) -> None:
    first, second = burst(), burst()
    out = join_chunks([first, second], SAMPLE_RATE, [mark])
    gap = round((total - KEPT) * SAMPLE_RATE)
    expected = trimmed_length(first, head=False, tail=True) + gap + trimmed_length(second, head=True, tail=False)
    assert out.size == expected
    voiced_end = int(0.4 * SAMPLE_RATE) + KEEP
    assert not np.any(out[voiced_end + 1:voiced_end + gap]), "chỗ chèn là lặng tuyệt đối"
    # tổng lặng thật giữa hai tiếng = lặng chèn + hai phần mép chừa = bảng
    assert (gap + 2 * KEEP) / SAMPLE_RATE == pytest.approx(total, abs=1 / SAMPLE_RATE)


def test_inner_silence_is_trimmed_but_the_outer_edges_are_kept() -> None:
    first, second = burst(lead=0.1, trail=0.15), burst(lead=0.2, trail=0.12)
    out = join_chunks([first, second], SAMPLE_RATE, ["."])
    assert not np.any(out[:int(0.1 * SAMPLE_RATE)]), "đầu mảnh đầu giữ nguyên (cả lặng)"
    assert not np.any(out[-int(0.12 * SAMPLE_RATE):]), "cuối mảnh cuối giữ nguyên (cả lặng)"
    # lặng đầu 0,1 s + giọng 0,3 s + mép 10 ms của mảnh đầu; mảnh sau mất 0,19 s lặng đầu nhưng giữ 0,12 s lặng cuối
    expected = int(0.1 * SAMPLE_RATE) + int(0.3 * SAMPLE_RATE) + KEEP + round((0.27 - KEPT) * SAMPLE_RATE) + KEEP \
        + int(0.3 * SAMPLE_RATE) + int(0.12 * SAMPLE_RATE)
    assert out.size == expected


def test_inner_edges_fade_with_a_raised_cosine() -> None:
    first, second = burst(), burst()
    out = join_chunks([first, second], SAMPLE_RATE, [","])
    ramp = int(tts_module.CHUNK_FADE_SECONDS * SAMPLE_RATE)
    start = trimmed_length(first, head=False, tail=True) + round((0.20 - KEPT) * SAMPLE_RATE)
    assert out[start] == 0.0, "mép trong của mảnh sau bắt đầu từ 0"
    plain = second[int(0.1 * SAMPLE_RATE) - KEEP:]
    window = 0.5 - 0.5 * np.cos(np.pi * np.arange(ramp) / ramp)
    assert np.allclose(out[start:start + ramp], plain[:ramp] * window, atol=1e-6), "raised-cosine 15 ms"
    assert np.allclose(out[start + ramp:start + ramp + 200], plain[ramp:ramp + 200]), "sau đoạn fade là bản thu nguyên"


def test_a_missing_end_mark_is_a_comma_gap() -> None:
    first, second = burst(), burst()
    assert np.array_equal(join_chunks([first, second], SAMPLE_RATE), join_chunks([first, second], SAMPLE_RATE, [","]))


def test_the_peak_is_capped_after_joining() -> None:
    out = join_chunks([burst(amplitude=1.6), burst(amplitude=0.4)], SAMPLE_RATE, ["."])
    assert np.max(np.abs(out)) == pytest.approx(tts_module.CHUNK_PEAK_CEILING, abs=1e-4)
    quiet = join_chunks([burst(amplitude=0.4), burst(amplitude=0.4)], SAMPLE_RATE, ["."])
    assert np.max(np.abs(quiet)) == pytest.approx(0.4, abs=1e-3), "dưới trần thì không đổi độ to"


def test_a_total_pause_shorter_than_the_kept_edges_overlaps_the_two_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(tts_module.CHUNK_JOIN_GAP_SECONDS, ".", 0.01)
    first, second = burst(), burst()
    out = join_chunks([first, second], SAMPLE_RATE, ["."])
    overlap = int(tts_module.CHUNK_FADE_SECONDS * SAMPLE_RATE)
    expected = trimmed_length(first, head=False, tail=True) + trimmed_length(second, head=True, tail=False) - overlap
    assert out.size == expected


def test_three_chunks_use_the_mark_of_each_join() -> None:
    waves = [burst(), burst(), burst()]
    out = join_chunks(waves, SAMPLE_RATE, ["?", ","])
    gaps = round((0.31 - KEPT) * SAMPLE_RATE) + round((0.20 - KEPT) * SAMPLE_RATE)
    inner = trimmed_length(waves[1], head=True, tail=True)
    assert out.size == trimmed_length(waves[0], head=False, tail=True) + inner + trimmed_length(waves[2], head=True, tail=False) + gaps


# ---- ZeroTTS nạp lại phiên ---------------------------------------------------------------------------------------------------------


class FakeZeroTTS:
    """Máy giả: bản thu phụ thuộc số ngẫu nhiên của numpy (như đồ thị ONNX), và lúc dựng bốc vài số (như warmup)."""

    frame_rate = 12.5
    sample_rate = 48_000
    built = 0

    def __init__(self) -> None:
        type(self).built += 1
        np.random.standard_normal(5)
        self.texts: list[str] = []

    def synthesize(self, text, *, voice, max_frames):
        self.texts.append(text)
        return (np.random.standard_normal((1, 2_400)) * 0.1).astype(np.float32)


@pytest.fixture
def fake_engine(monkeypatch: pytest.MonkeyPatch) -> ZeroTTSEngine:
    FakeZeroTTS.built = 0

    def load(self: ZeroTTSEngine) -> None:
        if self.tts is None:
            self.tts, self.voices, self.sample_rate = FakeZeroTTS(), ["baotrang"], 48_000

    monkeypatch.setattr(ZeroTTSEngine, "load", load)
    return ZeroTTSEngine(build_settings(), lambda _message: None)


PROFILE: dict[str, Any] = {"engine": "zerotts", "preset_name": "baotrang", "voice_key": "k"}


def read(engine: ZeroTTSEngine, text: str, seed: int = 11) -> bytes:
    row = {"text": text, "speaker": "A", "pace": "normal"}
    return engine.generate_one(row, PROFILE, seed, sampling={"max_new_frames": 300}).tobytes()


def test_the_session_is_rebuilt_after_the_configured_number_of_calls(fake_engine: ZeroTTSEngine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ZeroTTSEngine, "RECYCLE_AFTER_CALLS", 3)
    audio = [read(fake_engine, "Về rồi?") for _ in range(7)]
    assert FakeZeroTTS.built == 3, "gọi thứ 4 và thứ 7 nạp lại"
    assert len(set(audio)) == 1, "cùng câu, giọng, hạt giống: cùng byte trước và sau khi nạp lại"
    assert read(fake_engine, "Về rồi?", seed=12) != audio[0]


def test_every_chunk_of_a_long_line_counts_as_a_call(fake_engine: ZeroTTSEngine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ZeroTTSEngine, "RECYCLE_AFTER_CALLS", 4)
    text = " ".join(sentence(i, 150) for i in range(6))  # 6 câu x 150: mỗi câu một mảnh
    assert len(ZeroTTSEngine.chunk_plan(text)) == 6
    first = read(fake_engine, text)
    assert FakeZeroTTS.built == 1 and fake_engine._calls == 6
    assert read(fake_engine, text) == first and FakeZeroTTS.built == 2, "câu nhiều mảnh không bị nạp lại giữa chừng; sang câu sau mới nạp"


def test_no_recycling_when_switched_off_and_unload_resets_the_count(fake_engine: ZeroTTSEngine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ZeroTTSEngine, "RECYCLE_AFTER_CALLS", None)
    for _ in range(5):
        read(fake_engine, "Về rồi?")
    assert FakeZeroTTS.built == 1 and fake_engine._calls == 5
    fake_engine.unload()
    assert fake_engine._calls == 0 and fake_engine.tts is None
