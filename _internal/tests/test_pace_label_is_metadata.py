"""Analysis pace labels cannot change a take, frame budget or QA verdict."""
import numpy as np
import pytest

from abook.audio_io import AudioQualityError, segment_duration_policy, validate_audio_array
from abook.config import build_settings
from abook.tts import vieneu_sampling_for_segment


@pytest.mark.parametrize("duration", [1.5, 3.0, 5.0, 9.0, 14.0])
@pytest.mark.parametrize("scale", [0.7, 1.0])
def test_same_take_has_same_verdict_for_every_label(duration, scale, monkeypatch):
    from abook import voice_balance
    monkeypatch.setattr(voice_balance, "pace_gate_scale", lambda *_: scale)
    settings = build_settings("high_quality")
    rate = 24000
    samples = np.arange(int(rate * duration)) / rate
    audio = (0.1 * np.sin(2 * np.pi * 220 * samples)).astype(np.float32)
    audio[:2400] = audio[-2400:] = 0
    text = "mot hai ba bon nam sau bay tam chin muoi mot hai ba bon nam sau"
    verdicts = []
    budgets = []
    sampling = []
    for pace in ("slow", "normal", "fast", "unknown"):
        row = {"text": text, "pace": pace}
        try:
            _audio, metrics = validate_audio_array(audio, text, settings, rate, segment=row)
            verdicts.append(("ok", metrics))
        except AudioQualityError as exc:
            verdicts.append(("error", str(exc)))
        budgets.append(segment_duration_policy(text, settings, row))
        sampling.append(vieneu_sampling_for_segment(row, settings=settings))
    assert all(verdict == verdicts[0] for verdict in verdicts)
    assert all(budget == budgets[0] for budget in budgets)
    assert all(value == sampling[0] for value in sampling)
    assert "silence_p" not in sampling[0]
