"""Synthetic tones with the quiet boundaries required of a sentence take."""
import numpy as np


def quiet_edges(audio, sample_rate=48_000):
    audio = np.asarray(audio, dtype=np.float32).copy()
    n = min(len(audio)//2, round(sample_rate * .02))
    if n:
        ramp = np.linspace(0, 1, n, dtype=np.float32)
        audio[:n] *= ramp
        audio[-n:] *= ramp[::-1]
    return audio
