"""ZeroTTS provider using the existing optional, pinned Studio module, on CPU."""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Mapping

from .model import Synthesis, Voice, VoiceError, stop_if_cancelled, unit_made
from .vieneu import reading_tag, seed_of, timed_synthesis, units

PREFIX = "zerotts"
NAMES = {"baotrang": ("Bảo Trang", "female"), "giahuy": ("Gia Huy", "male"), "huuduc": ("Hữu Đức", "male"),
         "kimoanh": ("Kim Oanh", "female"), "quangminh": ("Quang Minh", "male")}


def make_engine(found: Any) -> Any:
    from ..webui import zerotts_module

    factory = zerotts_module.import_engine(found)
    return factory(found.model, intra_op_num_threads=2, warmup=True)


class ZeroTTSProvider:
    id = PREFIX
    speaks_english = True

    def __init__(self, locate: Callable[[], Any], *, engines: Callable[[Any], Any] = make_engine,
                 normalize: Callable[[str], str] | None = None) -> None:
        self.locate = locate
        self._factory = engines
        self._engine: Any = None
        self._calls = 0
        self._normalize = normalize
        self._lock = threading.RLock()

    def voices(self) -> list[Voice]:
        if self.locate() is None:
            return []
        return [Voice(f"{PREFIX}:{key}", f"{name} (ZeroTTS)", PREFIX, False, gender=gender) for key, (name, gender) in NAMES.items()]

    def forget(self) -> None:
        with self._lock:
            self._engine = None
            self._calls = 0

    def reading_tag(self, text: str, origin: str | None) -> str:
        return reading_tag(text, origin, self.speaks_english)

    def synthesize(self, text: str, native_voice: str, origin: str | None = None, readings: Mapping[str, str] | None = None) -> Synthesis:
        import numpy as np

        from . import vieneu_engine as ve

        with self._lock:
            found = self.locate()
            if found is None or native_voice not in NAMES:
                raise VoiceError("Giọng ZeroTTS này chưa tải trên máy.", "voice")
            # Same native-session recycling interval as the Studio adapter.
            if self._calls >= 25:
                self.forget()
            if self._engine is None:
                self._engine = self._factory(found)
            engine = self._engine
            toks, parts = units(text, 170, origin, self.speaks_english, readings)
            waves, pauses = [], []
            if self._normalize is None:
                from zerotts.text_norm import normalize_vi_text
                self._normalize = normalize_vi_text
            for part in parts:
                stop_if_cancelled()
                said = self._normalize(" ".join(part.pieces))
                before = time.perf_counter()
                state = np.random.get_state()
                try:
                    np.random.seed(seed_of(PREFIX, native_voice, said))
                    # A bounded generation budget, including warm-up and short benchmark sentences.
                    max_frames = max(32, int((len(said.split()) / 2 + 3) * engine.frame_rate))
                    wave = np.asarray(engine.synthesize(said, voice=native_voice, max_frames=max_frames), dtype=np.float32).reshape(-1)
                finally:
                    np.random.set_state(state)
                self._calls += 1
                if not wave.size:
                    raise VoiceError("Máy đọc không ra tiếng.", "empty")
                waves.append(wave)
                pauses.append(ve.gap_after(said))
                unit_made(wave, engine.sample_rate, said, time.perf_counter() - before)
            if not waves:
                raise VoiceError("Đoạn này không có chữ nào đọc được.", "empty")
            joined, spans = ve.join(waves, engine.sample_rate, pauses[:-1])
            return timed_synthesis(joined, engine.sample_rate, toks, parts, spans, None)
