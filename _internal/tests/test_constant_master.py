"""Gain chương chỉ lấy từ hiệu chuẩn, limiter không nâng phần yên."""
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from abook import audio_io
from abook.config import build_settings


def test_different_chapter_levels_peaks_and_targets_have_identical_gain(tmp_path: Path):
    rate = 48000
    t = np.arange(rate * 2) / rate
    for i, (amplitude, target) in enumerate(((.005, -12), (.03, -24), (.1, -30))):
        x = amplitude * np.sin(2 * np.pi * 440 * t)
        source, output = tmp_path / f'{i}.wav', tmp_path / f'{i}.limited.wav'
        sf.write(source, x, rate, subtype='FLOAT')
        cfg = {**build_settings()['audio'], 'loudness_lufs': target}
        metrics = audio_io._master_chapter_pcm(['-i', str(source)], output, cfg, rate)
        y, _ = sf.read(output, always_2d=True)
        # Ép đúng hệ số thực trên samples, không chỉ kiểm metadata.
        expected = x * 10 ** (5 / 20)
        np.testing.assert_allclose(y[100:-100, 0], expected[100:-100], atol=2e-6)
        assert metrics['limiter_reduced_fraction'] == 0
        assert metrics['limiter_max_reduction_db'] == pytest.approx(0, abs=.001)


def test_peak_limiter_reports_envelope_and_preserves_quiet_audio(tmp_path: Path):
    rate = 48000
    t = np.arange(rate * 3) / rate
    x = .01 * np.sin(2 * np.pi * 440 * t)
    x[rate:rate+480] += .8 * np.sin(2*np.pi*1000*t[:480])
    source, output = tmp_path/'source.wav', tmp_path/'limited.wav'
    sf.write(source, x, rate, subtype='FLOAT')
    cfg = build_settings()['audio']
    metrics = audio_io._master_chapter_pcm(['-i', str(source)], output, cfg, rate)
    y, _ = sf.read(output, always_2d=True)
    assert 0 < metrics['limiter_reduced_fraction'] < .1
    assert metrics['limiter_reduced_seconds'] == pytest.approx(3*metrics['limiter_reduced_fraction'])
    assert metrics['limiter_max_reduction_db'] > 3
    # Lookahead 5 ms có thể hạ ngay trước đỉnh; cách đỉnh 20 ms phải nguyên vẹn.
    np.testing.assert_allclose(y[100:rate-960, 0], x[100:rate-960]*10**.25, atol=2e-6)
    assert max(abs(y[:, 0])) < 10**(cfg['true_peak_db']/20) + .002


def test_final_mp3_keeps_peak_ceiling_with_sparse_high_crest_peaks(tmp_path: Path):
    settings = build_settings()
    rate = settings['tts']['sample_rate']
    t = np.arange(8*rate)/rate
    x = .008*np.sin(2*np.pi*440*t) + .7*np.exp(-((t-4)/.004)**2)*np.sin(2*np.pi*1000*t)
    source = tmp_path/'crest.wav'
    sf.write(source, x, rate, subtype='PCM_16')
    result = audio_io.assemble_chapter_atomic_with_metrics([source], tmp_path/'crest.mp3', settings,
        title='Synthetic', book_title='Synthetic', track=1)
    q = result.quality
    assert q.master_gain_db == 5
    assert 0 < q.limiter_reduced_fraction < .1
    assert q.limiter_max_reduction_db > 0
    assert q.true_peak_db <= settings['audio']['true_peak_db'] + .15
    assert not q.hard_failures
