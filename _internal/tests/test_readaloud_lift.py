"""Bù theo clip cho giọng VieNeu (vnloud) và Supertonic (stlift): câu ngắn nhỏ hơn mức giọng được nâng lên NGAY TRONG clip (loudness.lift_db / lift_wav, service.clip), câu thường
giữ nguyên byte, đỉnh thật sau khi bù không vượt -1 dBTP, giọng khác / giọng chưa đo / clip lặng không bị đụng. Bản Kotlin (ClipLift.kt) đọc cùng
tests/fixtures/vieneu/android/lift.json; test cuối kiểm file ấy không cũ."""
from __future__ import annotations

import importlib.util
import io
import json
import wave
from pathlib import Path

import numpy as np
import pytest

from abook.readaloud import loudness, supertonic, vieneu
from abook.readaloud.cache import clip_key
from abook.readaloud.service import ReadAloud
from abook.readaloud.supertonic import Installed, SupertonicProvider
from tests.test_readaloud_supertonic import FakeEngine as SupertonicFakeEngine
from tests.test_readaloud_vieneu import FakeEngine, fake_voices  # noqa: F401 - fixture dùng chung

RATE = 24_000
VOICE = "vieneu:turbo/Đức Trí"  # -20,2 LUFS
ROOT = Path(__file__).resolve().parents[1]


def _tone(seconds: float, level: float, spike: float = 0.0, seed: int = 3) -> np.ndarray:
    n = int(seconds * RATE)
    x = np.sin(2 * np.pi * 220 * np.arange(n) / RATE) * level + np.random.default_rng(seed).standard_normal(n) * level * 0.1
    x[n // 2] += spike
    return np.clip(np.round(x * 32767), -32767, 32767).astype(np.int16).astype(np.float64) / 32767.0


def _wav(samples: np.ndarray) -> bytes:
    return vieneu.wav_bytes(samples, RATE)


def _pcm(wav: bytes) -> np.ndarray:
    with wave.open(io.BytesIO(wav), "rb") as handle:
        return np.frombuffer(handle.readframes(handle.getnframes()), dtype="<i2").astype(np.float64) / 32767.0


def _level_for(offset_db: float, base: float = 0.05) -> np.ndarray:
    """Một tiếng ngân dài 1 giây có mức đúng `offset_db` LU quanh mức giọng (chỉnh biên độ cho tới khi đo trúng)."""
    x = _tone(1.0, base)
    want = loudness.MEASURED_LUFS[VOICE] + offset_db
    return x * 10 ** ((want - loudness.clip_lufs(x, RATE)) / 20)


def test_a_quiet_clip_is_lifted_by_the_shortfall_beyond_the_dead_band() -> None:
    clip = _level_for(-5.0)
    gain = loudness.lift_db(VOICE, clip, RATE)
    assert gain == pytest.approx(5.0 - loudness.LIFT_DEADBAND_DB, abs=0.15)
    after = _pcm(loudness.lift_wav(VOICE, _wav(clip)))
    assert loudness.clip_lufs(after, RATE) == pytest.approx(loudness.clip_lufs(clip, RATE) + gain, abs=0.1)


def test_a_clip_within_the_dead_band_or_louder_than_the_voice_is_untouched_byte_for_byte() -> None:
    for offset in (-1.8, 0.0, +3.0):
        wav = _wav(_level_for(offset))
        assert loudness.lift_wav(VOICE, wav) is wav, offset


def test_the_lift_never_exceeds_the_cap_and_the_true_peak_ceiling() -> None:
    very_quiet = _level_for(-14.0)
    assert loudness.lift_db(VOICE, very_quiet, RATE) == loudness.LIFT_MAX_DB
    peaky = _tone(0.8, 0.05, spike=0.66)
    gain = loudness.lift_db(VOICE, peaky, RATE)
    assert 0.0 < gain < loudness.LIFT_MAX_DB, "đỉnh nhọn chặn bù trước khi đủ"
    after = _pcm(loudness.lift_wav(VOICE, _wav(peaky)))
    assert loudness.true_peak_dbtp(after) <= loudness.LIFT_CEILING_DBTP
    already_hot = _tone(0.8, 0.05, spike=0.99)
    assert loudness.lift_db(VOICE, already_hot, RATE) == 0.0, "đã sát trần: không nâng, cũng không hạ"


def test_silence_noise_and_clips_too_short_to_measure_are_left_alone() -> None:
    assert loudness.lift_db(VOICE, np.random.default_rng(1).standard_normal(RATE // 2) * 0.0002, RATE) == 0.0
    assert loudness.lift_db(VOICE, _tone(0.1, 0.05), RATE) == 0.0
    assert loudness.clip_lufs(_tone(0.1, 0.05), RATE) is None


def test_only_measured_vieneu_and_supertonic_voices_are_lifted() -> None:
    quiet = _tone(0.8, 0.02)
    assert loudness.lift_db(VOICE, quiet, RATE) > 0
    assert loudness.lift_db("edge:vi-VN-HoaiMyNeural", quiet, RATE) == 0.0
    assert loudness.lift_db("vieneu:turbo/Giọng chưa đo", quiet, RATE) == 0.0
    assert loudness.lifts("supertonic:F1") and loudness.lift_db("supertonic:F1", quiet, RATE) > 0
    assert not loudness.lifts("supertonic:F1#fast5"), "mã giọng trần: bậc tốc độ không có mức riêng (service.clip đưa mã trần)"
    assert not loudness.lifts("supertonic:X9")
    wav = _wav(quiet)
    assert loudness.lift_wav("edge:vi-VN-HoaiMyNeural", wav) is wav


def test_the_service_lifts_a_quiet_clip_before_it_is_cached_and_keys_it_apart(fake_voices, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    provider, engines = fake_voices
    voice = "vieneu:turbo/Thường"
    monkeypatch.setitem(loudness.MEASURED_LUFS, voice, -20.0)
    infer = engines["turbo"].infer
    engines["turbo"].infer = lambda *a, **k: infer(*a, **k) * np.float32(0.05)  # tiếng bíp 0,3 -> 0,015: nhỏ hơn mức giọng nhiều
    service = ReadAloud(tmp_path / "cache", [provider])
    clip = service.clip(voice, "Ừ.")
    assert len(engines["turbo"].calls) == 1
    raw = vieneu.wav_bytes(infer("ừ.") * np.float32(0.05), 48_000)
    cached = (tmp_path / "cache" / clip["file"]).read_bytes()
    assert cached != raw and len(cached) == len(raw), "cùng độ dài, mẫu to hơn"
    assert np.abs(_pcm(cached)).max() > 1.5 * np.abs(_pcm(raw)).max()
    key = clip_key(provider.id, "turbo/Thường", "Ừ.", loudness.LIFT_TAG)
    assert (tmp_path / "cache" / f"{key}.wav").exists(), "khoá có dấu bù, nên clip làm trước khi có bù không trúng đệm"
    assert service.clip(voice, "Ừ.") == clip and len(engines["turbo"].calls) == 2, "lần sau lấy bộ đệm (2 = cả lần tự gọi ở trên)"


def _supertonic_service(tmp_path: Path, scale: float, **kwargs) -> tuple[ReadAloud, SupertonicFakeEngine]:
    engine = SupertonicFakeEngine()
    infer = engine.infer
    engine.infer = lambda *a, **k: infer(*a, **k) * np.float32(scale)
    provider = SupertonicProvider(lambda: Installed(tmp_path, False), engines=lambda _found: engine, aligner=lambda: None, normalize=lambda pieces: " ".join(pieces).lower())
    provider.speaks_english = False
    return ReadAloud(tmp_path / "cache", [provider], **kwargs), engine


def test_a_quiet_supertonic_line_is_lifted_in_the_clip_a_normal_one_is_not(tmp_path: Path) -> None:
    quiet, _ = _supertonic_service(tmp_path / "q", 0.04)  # "Hả?" ra nhỏ hơn mức giọng nhiều
    clip = quiet.clip("supertonic:F3", "Hả?")
    cached = _pcm((tmp_path / "q" / "cache" / clip["file"]).read_bytes())
    raw_engine = SupertonicFakeEngine()
    raw = supertonic.louder(raw_engine.infer("hả?", "F3", None) * np.float32(0.04))
    assert np.abs(cached).max() > 1.5 * np.abs(raw).max(), "mẫu to hơn bản chưa bù"
    assert (tmp_path / "q" / "cache" / f"{clip_key('supertonic', 'F3', 'Hả?', loudness.LIFT_TAG)}.wav").exists(), "khoá có dấu bù"
    normal, engine = _supertonic_service(tmp_path / "n", 0.2)  # câu thường: đã quá mức giọng, giữ nguyên
    done = normal.clip("supertonic:F3", "Chờ đã nào các bạn ơi.")
    plain = SupertonicProvider(lambda: Installed(tmp_path, False), engines=lambda _found: engine, aligner=lambda: None, normalize=lambda pieces: " ".join(pieces).lower())
    plain.speaks_english = False
    assert (tmp_path / "n" / "cache" / done["file"]).read_bytes() == plain.synthesize("Chờ đã nào các bạn ơi.", "F3").audio, "byte y hệt clip chưa qua bù"


def test_both_supertonic_tiers_use_the_same_level_and_the_same_lift(tmp_path: Path) -> None:
    service, _ = _supertonic_service(tmp_path / "a", 0.04, speed=lambda _voice: "fast5")
    fast_engine = SupertonicFakeEngine()
    infer = fast_engine.infer
    fast_engine.infer = lambda *a, **k: infer(*a, **k) * np.float32(0.04)
    fast = SupertonicProvider(lambda: Installed(tmp_path, False), engines=lambda _found: fast_engine, aligner=lambda: None, normalize=lambda pieces: " ".join(pieces).lower())
    fast.speaks_english = False
    service.fast["supertonic"] = fast
    clip = service.clip("supertonic:M2", "Hả?")
    assert fast_engine.calls and (tmp_path / "a" / "cache" / f"{clip_key('supertonic', 'M2', 'Hả?', loudness.LIFT_TAG + '+fast5')}.wav").exists(), "bậc nhanh: dấu bù rồi dấu bậc"
    full = service.clip("supertonic:M2", "Hả?", quality=True)
    assert _pcm((tmp_path / "a" / "cache" / full["file"]).read_bytes()).max() == pytest.approx(_pcm((tmp_path / "a" / "cache" / clip["file"]).read_bytes()).max())


def test_the_phone_and_the_computer_lift_the_same_clips_by_the_same_amount() -> None:
    spec = importlib.util.spec_from_file_location("vieneu_android_fixtures", ROOT / "scripts" / "vieneu_android_fixtures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fresh = json.loads(json.dumps(module.lift_fixture()))
    assert fresh == json.loads((ROOT / "tests" / "fixtures" / "vieneu" / "android" / "lift.json").read_text(encoding="utf-8")), \
        "lift.json cũ: chạy lại scripts/vieneu_android_fixtures.py (xem docstring) rồi chạy cả bài JVM ClipLiftTest"
    cases = fresh["cases"]
    assert cases["very_quiet"]["liftDb"] == loudness.LIFT_MAX_DB and cases["near_voice"]["liftDb"] == 0.0 and cases["loud"]["liftDb"] == 0.0
    assert cases["silent"]["lufs"] is None and cases["tiny"]["lufs"] is None and cases["other_provider"]["liftDb"] == 0.0
    assert cases["quiet_supertonic"]["liftDb"] > 0 and 0 < cases["peaky_supertonic"]["liftDb"] < loudness.LIFT_MAX_DB
