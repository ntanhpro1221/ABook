"""A voice's register (pitch_semitones) is applied once, at synthesis - never again at delivery.

It used to ride both `apply_pitch_variant` in tts.py (the take that every gate verified) and
`shape_segment` in the delivery pass, so a -2 profile reached the listener at -4 and a +14
child voice at +28. These tests measure F0 on a synthetic voiced tone through the real code.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import numpy as np
import parselmouth
import pytest
import soundfile as sf

from abook import expression, pipeline as pipeline_module
from abook.expression import prosody_targets
from abook.config import build_settings
from abook.pipeline import BookPipeline
from abook.tts import apply_pitch_variant

RATE = 24_000
F0_HZ = 150.0
TOLERANCE = 0.3  # semitones


def _voiced_tone(seconds: float = 1.5, f0: float = F0_HZ) -> np.ndarray:
    t = np.arange(int(RATE * seconds)) / RATE
    wave = sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 15))
    wave = 0.12 * wave
    # Edges at zero so the delivery shortcut treats it as an ordinary final take.
    fade = np.minimum(1.0, np.minimum(t, seconds - t) / 0.03)
    return (wave * fade).astype(np.float32)


def _median_f0(audio: np.ndarray, rate: int = RATE) -> float:
    pitch = parselmouth.Sound(np.asarray(audio, dtype=np.float64), sampling_frequency=rate).to_pitch(
        pitch_floor=70.0, pitch_ceiling=500.0
    )
    voiced = pitch.selected_array["frequency"]
    voiced = voiced[voiced > 0]
    assert voiced.size > 20
    return float(np.median(voiced))


def _semitones(after: float, before: float) -> float:
    return 12.0 * float(np.log2(after / before))


def _deliver(tmp_path: Path, profile: dict | None, emotion: str, intensity: int, kind: str = "dialogue") -> np.ndarray:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "take.wav"
    sf.write(source, _voiced_tone(), RATE, subtype="PCM_16")
    row = {
        "wav_path": str(source), "voice_profile_id": 1 if profile else 0, "emotion": emotion,
        "intensity": intensity, "kind": kind, "text": "Xin chào.", "scene_break": 0, "break_ms": 200, "seq": 1,
    }

    class _Db:
        @staticmethod
        def list_voice_profiles() -> list:
            return [profile] if profile else []

    pipeline = BookPipeline.__new__(BookPipeline)
    pipeline.db = _Db()
    pipeline.settings = build_settings()
    pipeline.paths = type("Paths", (), {"work": tmp_path / "work"})()
    pipeline.log = lambda *_args, **_kwargs: None
    (delivered, _ms), = pipeline._chapter_delivery_wavs({"id": 1, "chapter_index": 1}, [row])
    audio, rate = sf.read(delivered, dtype="float32")
    assert rate == RATE
    return audio


@pytest.mark.parametrize("pitch", [4, -2, 14])
def test_a_neutral_line_is_delivered_at_the_pitch_of_the_take(tmp_path: Path, pitch: int) -> None:
    profile = {"id": 1, "pitch_semitones": pitch, "formant_ratio": 1.0}
    delivered = _deliver(tmp_path, profile, "neutral", 0)
    assert abs(_semitones(_median_f0(delivered), F0_HZ)) < TOLERANCE


def test_an_expressive_line_moves_by_the_expression_target_only(tmp_path: Path) -> None:
    target = prosody_targets("sad", 3, weight=1.0, seconds=1.5)["pitch_semitones"]
    assert abs(target) > 0.5, "the test needs an emotion that actually moves pitch"
    with_register = _deliver(tmp_path / "a", {"id": 1, "pitch_semitones": 4, "formant_ratio": 1.0}, "sad", 3)
    without = _deliver(tmp_path / "b", {"id": 1, "pitch_semitones": 0, "formant_ratio": 1.0}, "sad", 3)
    moved = _semitones(_median_f0(with_register), F0_HZ)
    assert abs(moved - target) < TOLERANCE, (moved, target)
    assert abs(_semitones(_median_f0(with_register), _median_f0(without))) < TOLERANCE


def test_a_formant_warp_does_not_bring_the_register_back(tmp_path: Path) -> None:
    profile = {"id": 1, "pitch_semitones": 4, "formant_ratio": 0.95}
    delivered = _deliver(tmp_path, profile, "neutral", 0)
    assert abs(_semitones(_median_f0(delivered), F0_HZ)) < TOLERANCE


def test_synthesis_applies_the_register_once() -> None:
    shifted = apply_pitch_variant(_voiced_tone(), RATE, 4)
    assert abs(_semitones(_median_f0(shifted), F0_HZ) - 4.0) < TOLERANCE


def _function_source(module, name: str) -> ast.FunctionDef:
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(name)


def test_delivery_code_never_reads_the_register() -> None:
    """Static guard: the delivery function cannot pick the profile's pitch up to transform audio."""
    function = _function_source(pipeline_module, "_chapter_delivery_wavs")
    words = {node.value for node in ast.walk(function) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    names = {node.id for node in ast.walk(function) if isinstance(node, ast.Name)}
    assert not {word for word in words if "pitch" in word}, "delivery reads a pitch field"
    assert not {name for name in names if "pitch" in name}, "delivery holds a pitch value"
    for call in (n for n in ast.walk(function) if isinstance(n, ast.Call)):
        callee = getattr(call.func, "id", getattr(call.func, "attr", ""))
        if callee == "apply_voice_variant":
            assert isinstance(call.args[2], ast.Constant) and call.args[2].value == 0
        if callee == "shape_segment":
            assert len(call.args) == 5 and not call.keywords


def test_shape_segment_cannot_be_given_a_register() -> None:
    names = list(inspect.signature(expression.shape_segment).parameters)
    assert names == ["audio", "rate", "emotion", "intensity", "kind"]
