"""A stand-in for the VieNeu model that a CHILD process can import: a tone per line, and a record of every text it was given.

Tests that run synthesis in a real second process (a synthesis-pool worker, the voice-preview process) cannot patch the model
there. `install` writes a package named `vieneu` into a folder; with that folder first on the child's import path, everything
else in the child is the real code - `TTSCoordinator`, the read-only database, the name rules - and only the model is a tone.
What the model was asked to say is appended to a file the test reads back.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SAID = "ABOOK_TEST_SAID"
VOICES = "ABOOK_TEST_VOICES"

# Fake voices have no measured record in the balance table; like the preview's own fake voice, they get neutral constants.
_PACKAGE = '''
import json
import os

import numpy as np

from abook import voice_balance

_NAMES = json.loads(os.environ["%(voices)s"])
voice_balance.register_neutral_voices({"engine": "vieneu", "preset_name": name} for name in _NAMES)


class Vieneu:
    sample_rate = 48_000

    def __init__(self, **_kwargs):
        pass

    def list_preset_voices(self):
        return [(name, name) for name in _NAMES]

    def infer(self, text, **kwargs):
        with open(os.environ["%(said)s"], "a", encoding="utf-8") as said:
            said.write(json.dumps({"text": text, "voice": kwargs.get("voice")}, ensure_ascii=False) + "\\n")
        moments = np.arange(int(min(6.0, 0.5 + 0.07 * len(text)) * self.sample_rate)) / self.sample_rate
        wave = (0.2 * np.sin(2 * np.pi * 220 * moments)).astype(np.float32)
        edge = round(self.sample_rate * 0.02)  # quiet edges, as a real take has
        ramp = np.linspace(0.0, 1.0, edge, dtype=np.float32)
        wave[:edge] *= ramp
        wave[-edge:] *= ramp[::-1]
        return wave
''' % {"voices": VOICES, "said": SAID}


def install(folder: Path, voices: list[str]) -> tuple[Path, dict[str, str]]:
    """Write the package under `folder`; returns (the folder to put first on the child's import path, the environment the
    child needs). The record is `folder / "said.jsonl"`: read it with `said`."""
    package = folder / "vieneu"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(_PACKAGE, encoding="utf-8")
    return folder, {SAID: str(folder / "said.jsonl"), VOICES: json.dumps(voices, ensure_ascii=False)}


def said(folder: Path) -> list[dict[str, Any]]:
    """Every text the model was given in the child, in order."""
    record = folder / "said.jsonl"
    if not record.is_file():
        return []
    return [json.loads(line) for line in record.read_text(encoding="utf-8").splitlines() if line.strip()]
