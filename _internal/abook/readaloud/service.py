"""Ghép giọng + bộ đệm + mốc chữ thành hai việc cho máy chủ giao diện: `voices()` và `clip(giọng, chữ)`.

Một clip là MỘT đoạn chữ (đoạn của chương - `textScript.paragraphsOf`) đọc ở tốc độ 1,0 kèm mốc từng chữ hiện; giao diện ghép các clip
thành chương và chỉnh tốc độ bằng playbackRate nên bộ đệm dùng chung mọi tốc độ.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Protocol

from . import edge, loudness, windows
from .cache import ClipCache, clip_key
from .mapping import fold, map_boundaries
from .model import Synthesis, Voice, VoiceError

MAX_TEXT = 20_000  # ký tự một clip; đoạn của chương dài hơn nữa là hiếm, và Edge cũng phải cắt thành nhiều lượt


class Provider(Protocol):
    id: str

    def voices(self) -> list[Voice]: ...

    def synthesize(self, text: str, native_voice: str) -> Synthesis: ...


class EdgeProvider:
    id = "edge"

    def __init__(self, client: edge.EdgeClient | None = None) -> None:
        self.client = client or edge.EdgeClient()

    def voices(self) -> list[Voice]:
        return [Voice(f"edge:{code}", name, "edge", True, code == edge.DEFAULT_VOICE) for code, name in edge.VOICES]

    def synthesize(self, text: str, native_voice: str) -> Synthesis:
        return self.client.synthesize(text, native_voice)


class DeviceProvider:
    """Giọng của máy (Windows: windows.py). Máy khác Windows chưa có: danh sách rỗng."""

    id = "device"

    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def voices(self) -> list[Voice]:
        return windows.voices(self.folder)

    def synthesize(self, text: str, native_voice: str) -> Synthesis:
        return windows.synthesize(self.folder, native_voice, text)


class ReadAloud:
    def __init__(self, folder: Path | str, providers: list[Provider] | None = None, *, limit: int | None = None) -> None:
        self.folder = Path(folder)
        kwargs = {} if limit is None else {"limit": limit}
        self.cache = ClipCache(self.folder, **kwargs)
        self.providers: dict[str, Provider] = {provider.id: provider for provider in (
            providers if providers is not None else [EdgeProvider(), DeviceProvider(self.folder / "tools")])}
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def warm(self) -> None:
        """Liệt kê giọng của máy ở luồng nền (hỏi PowerShell mất ~1 giây): lúc người nghe mở một cuốn chỉ-có-chữ, danh sách đã sẵn."""
        def run() -> None:
            for provider in self.providers.values():
                try:
                    provider.voices()
                except Exception:  # noqa: BLE001 - chỉ là làm nóng; lỗi thật sẽ hiện khi hỏi danh sách
                    pass

        threading.Thread(target=run, name="readaloud-warm", daemon=True).start()

    def voices(self) -> list[dict[str, Any]]:
        listed = []
        for provider in self.providers.values():
            for voice in provider.voices():
                listed.append({"id": voice.id, "name": voice.name, "provider": voice.provider, "online": voice.online,
                               "default": voice.default, "language": voice.language, "gain_db": loudness.gain_db(voice.id)})
        return listed

    def _resolve(self, voice_id: str) -> tuple[Provider, str]:
        name, _, native = voice_id.partition(":")
        provider = self.providers.get(name)
        if provider is None or not native or not any(voice.id == voice_id for voice in provider.voices()):
            raise VoiceError("Giọng này không có trên máy.", "voice")
        return provider, native

    def clip(self, voice_id: str, text: str, *, cached_only: bool = False) -> dict[str, Any]:
        """Clip của `text` bằng `voice_id`: `{file, duration_ms, words}` (từ bộ đệm hay đọc mới). `cached_only`: không đọc mới - chưa có thì `VoiceError("uncached")`."""
        if not fold(text):
            raise VoiceError("Đoạn này không có chữ nào để đọc.", "empty")
        if len(text) > MAX_TEXT:
            raise ValueError("Đoạn chữ quá dài để đọc một lượt")
        provider, native = self._resolve(voice_id)
        key = clip_key(provider.id, native, text)
        hit = self.cache.get(key)
        if hit is None:
            if cached_only:
                raise VoiceError("Chưa đọc đoạn này.", "uncached")
            with self._locks_guard:
                lock = self._locks.setdefault(key, threading.Lock())
            with lock:  # hai yêu cầu cùng đoạn (đọc trước + bấm nghe) chỉ đọc một lần
                hit = self.cache.get(key)
                if hit is None:
                    made = provider.synthesize(text, native)
                    words = map_boundaries(text, made.boundaries, made.duration_ms)
                    hit = self.cache.put(key, made.audio, made.ext, made.duration_ms, words)
            with self._locks_guard:
                self._locks.pop(key, None)
        return {"file": hit.file, "duration_ms": hit.duration_ms, "words": hit.words}
