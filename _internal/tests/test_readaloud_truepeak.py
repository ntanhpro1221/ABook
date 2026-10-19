"""Trần đỉnh thật từng khúc của giọng trên máy (truepeak, Corpus research/music/SPEC_truepeak.md): khúc Nano / Turbo vừa ra khỏi engine mà đỉnh thật
vượt -1 dBTP thì hạ CẢ khúc xuống đúng trần thay vì cắt cứng ở [-1, 1] (loudness.under_ceiling); khúc không vượt giữ nguyên từng mẫu; Supertonic nâng
+4 dB nhưng không quá trần đỉnh thật (supertonic.louder). Bản Kotlin (ClipLift.underCeiling, SupertonicText.louder) đọc cùng ca trong
tests/fixtures/vieneu/android/lift.json ("ceiling"); test_readaloud_lift kiểm file ấy không cũ."""
from __future__ import annotations

import base64
import json
import threading
from pathlib import Path

import numpy as np

from abook.readaloud import loudness, supertonic, vieneu
from abook.readaloud import vieneu_engine as ve

RATE = 24_000
ROOT = Path(__file__).resolve().parents[1]
EPS_DB = 1e-4  # nhân float32: đỉnh sau khi hạ lệch trần cỡ 1e-6 dB


def _speechy(peak_db: float, seconds: float = 0.6, seed: int = 5) -> np.ndarray:
    """Tiếng giả: âm 180 Hz điều biên + nhiễu, chỉnh tới đỉnh MẪU `peak_db` dBFS (có thể > 0: như sóng thô của engine)."""
    t = np.arange(int(seconds * RATE)) / RATE
    x = np.sin(2 * np.pi * 180 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t)) + np.random.default_rng(seed).standard_normal(t.size) * 0.08
    return (x / np.abs(x).max() * 10 ** (peak_db / 20)).astype(np.float32)


def _pcm(wav: bytes) -> np.ndarray:
    return np.frombuffer(wav[44:], dtype="<i2")


# ---- (a) (b): một khúc ----------------------------------------------------------------------------------------------------------------
def test_a_raw_chunk_past_full_scale_is_lowered_whole_not_clipped() -> None:
    raw = _speechy(0.8)  # Nano thô tới +0,8 dBFS
    assert loudness.true_peak_dbtp(raw) > 0.8
    out = loudness.under_ceiling(raw)
    assert out.dtype == np.float32 and out.shape == raw.shape
    assert loudness.true_peak_dbtp(out) <= loudness.LIFT_CEILING_DBTP + EPS_DB
    ratio = out[np.abs(raw) > 0.1] / raw[np.abs(raw) > 0.1]
    assert np.allclose(ratio, ratio[0], rtol=1e-6), "một hệ số cho cả khúc: không méo, không cắt"
    pcm = _pcm(vieneu.wav_bytes(out, RATE))
    assert np.abs(pcm).max() < 32767, "không mẫu nào chạm ±1 trong file"


def test_a_chunk_under_the_ceiling_is_kept_sample_for_sample() -> None:
    chunk = _speechy(-3.5)
    assert loudness.true_peak_dbtp(chunk) <= -3.0
    assert loudness.under_ceiling(chunk) is chunk
    silent = np.zeros(100, dtype=np.float32)
    assert loudness.under_ceiling(silent) is silent and loudness.under_ceiling(np.zeros(0, dtype=np.float32)).size == 0


def test_the_ceiling_reads_the_true_peak_between_samples() -> None:
    t = np.arange(RATE // 2)
    wave = (0.95 * np.sin(2 * np.pi * t / 4 + np.pi / 4)).astype(np.float32)  # mẫu ở -3,5 dBFS, đỉnh thật giữa hai mẫu -0,45 dBTP
    assert 20 * np.log10(np.abs(wave).max()) < -3 and loudness.true_peak_dbtp(wave) > -1
    assert loudness.true_peak_dbtp(loudness.under_ceiling(wave)) <= loudness.LIFT_CEILING_DBTP + EPS_DB


# ---- (c): Supertonic ------------------------------------------------------------------------------------------------------------------
def test_supertonic_raises_four_db_only_up_to_the_true_peak_ceiling() -> None:
    chunk = _speechy(-3.5)
    tp = loudness.true_peak_dbtp(chunk)
    assert tp + supertonic.GAIN_DB > loudness.LIFT_CEILING_DBTP, "ca (c): +4 dB đẩy đỉnh thật qua trần"
    out = supertonic.louder(chunk.copy())
    assert np.array_equal(out, chunk * 10 ** ((loudness.LIFT_CEILING_DBTP - tp) / 20)), "gain = -1 - tp"
    assert abs(loudness.true_peak_dbtp(out) - loudness.LIFT_CEILING_DBTP) <= EPS_DB
    quiet = _speechy(-9.0)
    assert np.array_equal(supertonic.louder(quiet.copy()), quiet * 10 ** (supertonic.GAIN_DB / 20)), "đủ chỗ: nâng trọn +4 dB"
    hot = _speechy(-0.5)
    assert loudness.true_peak_dbtp(supertonic.louder(hot.copy())) <= loudness.LIFT_CEILING_DBTP + EPS_DB, "đã quá trần: hạ"


# ---- engine -------------------------------------------------------------------------------------------------------------------------
class _Session:
    def __init__(self, run) -> None:
        self.run = run


def _nano(tmp_path: Path, decoded: np.ndarray) -> ve.NanoEngine:
    """NanoEngine với phiên onnx giả: bộ giải mã trả đúng `decoded` (sóng thô của model)."""
    (tmp_path / "config.json").write_bytes(json.dumps({"vocab": {"a": 3}, "bos_id": 1, "eos_id": 2, "pad_id": 0}).encode("utf-8"))
    np.savez(tmp_path / "constants.npz", null_spk=np.zeros(4, dtype=np.float32), null_style=np.zeros((2, 3), dtype=np.float32))
    sessions = {
        "text": _Session(lambda _out, feed: [np.zeros((1, feed["ids"].shape[1], 8), dtype=np.float32)]),
        "dur": _Session(lambda _out, _feed: [np.array([0.0], dtype=np.float32)]),
        "ve": _Session(lambda _out, feed: [np.zeros_like(feed["x"])]),
        "dec": _Session(lambda _out, _feed: [decoded.reshape(1, 1, -1)]),
    }
    return ve.NanoEngine(tmp_path, sessions=sessions)


def test_nano_lowers_a_hot_chunk_before_trimming_and_keeps_a_normal_one(tmp_path: Path) -> None:
    hot = _speechy(0.8)
    (tmp_path / "hot").mkdir()
    out = _nano(tmp_path / "hot", hot).infer("a", np.zeros(4), np.zeros((2, 3)), seed=1)
    assert loudness.true_peak_dbtp(out) <= loudness.LIFT_CEILING_DBTP + EPS_DB and np.abs(out).max() < 1.0
    assert np.array_equal(out, ve.trim_and_fade(loudness.under_ceiling(hot), ve.NANO_RATE)), "hạ trước, rồi mới cắt lặng + fade"
    normal = _speechy(-3.5)
    (tmp_path / "normal").mkdir()
    kept = _nano(tmp_path / "normal", normal).infer("a", np.zeros(4), np.zeros((2, 3)), seed=1)
    assert np.array_equal(kept, ve.trim_and_fade(normal, ve.NANO_RATE)), "khúc không vượt: y như trước"


def test_turbo_lowers_the_kept_take() -> None:
    hot = _speechy(1.7, seed=8)  # Turbo thô tới +1,7 dBFS
    engine = ve.TurboEngine.__new__(ve.TurboEngine)
    engine._lock = threading.RLock()
    engine._anchor = lambda _emb: None
    engine._rows = lambda _phonemes, _codes: None
    engine._embed = lambda _rows, _anchor: None
    engine._generate = lambda *_args: [np.zeros(4)]
    engine.decode = lambda _frames: hot
    out = engine.infer("a", np.zeros(4), None, rng=np.random.RandomState(0), babble_retries=0)
    assert loudness.true_peak_dbtp(out) <= loudness.LIFT_CEILING_DBTP + EPS_DB
    assert np.array_equal(out, loudness.under_ceiling(hot))
    engine.decode = lambda _frames: _speechy(-3.5, seed=8)
    calm = engine.infer("a", np.zeros(4), None, rng=np.random.RandomState(0), babble_retries=0)
    assert np.array_equal(calm, _speechy(-3.5, seed=8))


# ---- khoá bộ đệm -----------------------------------------------------------------------------------------------------------------
def test_every_vieneu_and_supertonic_clip_is_keyed_anew_once_edge_is_not() -> None:
    assert loudness.LIFT_TAG == "ld2"
    for voice in ("vieneu:turbo/Đức Trí", "vieneu:turbo/Giọng chưa đo", "vieneu:nano/Nhẹ", "supertonic:F1", "supertonic:X9"):
        assert loudness.clip_tag(voice) == loudness.LIFT_TAG, voice
    for voice in ("edge:vi-VN-HoaiMyNeural", "azure:vi-VN-HoaiMyNeural", "device:vi-vn-x-gft-local"):
        assert loudness.clip_tag(voice) == "", voice


def test_the_shared_ceiling_cases_say_what_they_test() -> None:
    cases = json.loads((ROOT / "tests" / "fixtures" / "vieneu" / "android" / "lift.json").read_text(encoding="utf-8"))["ceiling"]

    def floats(text: str) -> np.ndarray:
        return np.frombuffer(base64.b64decode(text), dtype="<f4")

    for name in ("nano_raw", "turbo_raw", "between_samples"):
        assert not cases[name]["kept"] and cases[name]["truePeak"] > loudness.LIFT_CEILING_DBTP, name
        assert loudness.true_peak_dbtp(floats(cases[name]["under"])) <= loudness.LIFT_CEILING_DBTP + EPS_DB, name
    assert np.abs(floats(cases["turbo_raw"]["wave"])).max() > 1.2
    for name in ("under", "quiet"):
        assert cases[name]["kept"] and np.array_equal(floats(cases[name]["under"]), floats(cases[name]["wave"])), name
    assert abs(loudness.true_peak_dbtp(floats(cases["under"]["louder"])) - loudness.LIFT_CEILING_DBTP) <= EPS_DB
