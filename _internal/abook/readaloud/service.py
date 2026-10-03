"""Ghép giọng + bộ đệm + mốc chữ thành hai việc cho máy chủ giao diện: `voices()` và `clip(giọng, chữ)`.

Một clip là MỘT đoạn chữ (đoạn của chương - `textScript.paragraphsOf`) đọc ở tốc độ 1,0 kèm mốc từng chữ hiện; giao diện ghép các clip
thành chương và chỉnh tốc độ bằng playbackRate nên bộ đệm dùng chung mọi tốc độ.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable, Protocol

from . import azure, edge, fpt, google, loudness, names, supertonic, vieneu, viettel, windows
from .byok import KeyedProvider
from .cache import ClipCache, clip_key
from .keys import KeyStore
from .mapping import fold, map_boundaries
from .model import Synthesis, Voice, VoiceError
from .prepare import SHARE as PREPARE_SHARE
from .prepare import Prepare

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
        return [Voice(f"edge:{code}", name, "edge", True, code == edge.DEFAULT_VOICE, gender=gender) for code, name, gender in edge.VOICES]

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


def keyed_providers(keys: KeyStore) -> list[KeyedProvider]:
    """Giọng dùng khoá của người dùng (byok.py), Azure đứng đầu: nhà chính thức của chính các giọng Edge."""
    return [azure.AzureProvider(keys), google.GoogleProvider(keys), fpt.FptProvider(keys), viettel.ViettelProvider(keys)]


class ReadAloud:
    """`keys`: kho khoá của giọng dùng khoá riêng - có thì (khi `providers` để trống) các giọng ấy xếp sau Edge, trước giọng của máy.
    `vieneu_locate`: nơi mô-đun "Giọng VieNeu" đặt các phần (webui/vieneu_module.installed) - có thì thêm giọng VieNeu vào danh sách;
    `supertonic_locate`: như vậy cho mô-đun "Giọng Supertonic" (webui/supertonic_module.installed);
    `rtf`: tốc độ tự đo của giọng (để "Làm trước" ước thời gian)."""

    def __init__(self, folder: Path | str, providers: list[Provider] | None = None, *, limit: int | None = None,
                 keys: KeyStore | None = None, vieneu_locate: Callable[[], vieneu.Installed | None] | None = None,
                 supertonic_locate: Callable[[], supertonic.Installed | None] | None = None,
                 rtf: Callable[[str], float | None] = lambda _voice: None) -> None:
        self.folder = Path(folder)
        kwargs = {} if limit is None else {"limit": limit}
        self.cache = ClipCache(self.folder, **kwargs)
        if providers is None:
            providers = [EdgeProvider(), *(keyed_providers(keys) if keys is not None else []), DeviceProvider(self.folder / "tools")]
        self.providers: dict[str, Provider] = {provider.id: provider for provider in providers}
        self.vieneu = vieneu.VieneuProvider(vieneu_locate) if vieneu_locate is not None else None
        if self.vieneu is not None:
            self.providers[self.vieneu.id] = self.vieneu
        self.supertonic = supertonic.SupertonicProvider(supertonic_locate) if supertonic_locate is not None else None
        if self.supertonic is not None:
            self.providers[self.supertonic.id] = self.supertonic
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._live = 0  # clip của người đang nghe đang được đọc: "Làm trước" nhường
        # Gốc Nhật / Hàn của từng cuốn (máy đoán + người dùng ghi đè); cạnh thư mục bộ đệm, không nằm trong đó (bộ đệm dọn mọi file .json lâu không dùng).
        self.origins = names.BookOrigins(self.folder.with_name(self.folder.name + "-book-origins.json"))
        self.prepare = Prepare(lambda voice, text, origin: self.clip(voice, text, background=True, origin=origin), lambda: self._live,
                               int(self.cache.limit * PREPARE_SHARE), rtf)

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
                               "default": voice.default, "language": voice.language, "gender": voice.gender,
                               "gain_db": loudness.gain_db(voice.id)})
        return listed

    def _resolve(self, voice_id: str) -> tuple[Provider, str]:
        name, _, native = voice_id.partition(":")
        provider = self.providers.get(name)
        if provider is None or not native or not any(voice.id == voice_id for voice in provider.voices()):
            if isinstance(provider, KeyedProvider) and native:
                # Khoá vừa bị từ chối / bị gỡ: lý do "auth" để trình phát đọc tạm đoạn này bằng giọng kế thay vì dừng.
                raise VoiceError(f"Khoá {provider.name} chưa dùng được - kiểm tra lại trong Cài đặt.", "auth")
            raise VoiceError("Giọng này không có trên máy.", "voice")
        return provider, native

    # ---- giọng dùng khoá của người dùng (Cài đặt "Giọng trực tuyến dùng khóa của bạn") ------------------------------------------------

    def keyed(self, provider_id: str) -> KeyedProvider:
        provider = self.providers.get(provider_id)
        if not isinstance(provider, KeyedProvider):
            raise KeyError(provider_id)
        return provider

    def online_providers(self) -> list[dict[str, Any]]:
        return [provider.describe() for provider in self.providers.values() if isinstance(provider, KeyedProvider)]

    def set_key(self, provider_id: str, key: str, region: str = "") -> dict[str, Any]:
        """Lưu khoá (+ vùng). `key` rỗng = giữ khoá đã lưu, chỉ đổi vùng (giao diện không bao giờ có lại khoá thật). Chưa có khoá -> ValueError."""
        provider = self.keyed(provider_id)
        key = key.strip() or str(provider.keys.get(provider_id).get("key") or "")
        if not key:
            raise ValueError("Thiếu khoá")
        provider.keys.put(provider_id, key, region)
        return provider.describe()

    def remove_key(self, provider_id: str) -> dict[str, Any]:
        provider = self.keyed(provider_id)
        provider.keys.remove(provider_id)
        return provider.describe()

    def check_key(self, provider_id: str) -> dict[str, Any]:
        provider = self.keyed(provider_id)
        return {**provider.check(), "provider": provider.describe()}

    def clip(self, voice_id: str, text: str, *, cached_only: bool = False, background: bool = False, origin: str | None = None) -> dict[str, Any]:
        """Clip của `text` bằng `voice_id`: `{file, duration_ms, words}` (từ bộ đệm hay đọc mới). `cached_only`: không đọc mới - chưa có thì `VoiceError("uncached")`.
        `background`: việc "Làm trước" (prepare.py) - không tính là người đang nghe chờ. `origin`: gốc của cuốn ("ja" / "ko", `names.BookOrigins`) - giọng đọc
        trên máy (VieNeu) đọc tên romaji / RR theo luật phiên âm; giọng khác bỏ qua."""
        if not fold(text):
            raise VoiceError("Đoạn này không có chữ nào để đọc.", "empty")
        if len(text) > MAX_TEXT:
            raise ValueError("Đoạn chữ quá dài để đọc một lượt")
        provider, native = self._resolve(voice_id)
        reads_names = isinstance(provider, vieneu.VieneuProvider)
        key = clip_key(provider.id, native, text, provider.reading_tag(text, origin) if reads_names else "")
        hit = self.cache.get(key)
        if hit is None:
            if cached_only:
                raise VoiceError("Chưa đọc đoạn này.", "uncached")
            with self._locks_guard:
                lock = self._locks.setdefault(key, threading.Lock())
                self._live += 0 if background else 1
            try:
                with lock:  # hai yêu cầu cùng đoạn (đọc trước + bấm nghe) chỉ đọc một lần
                    hit = self.cache.get(key)
                    if hit is None:
                        made = provider.synthesize(text, native, origin) if reads_names else provider.synthesize(text, native)
                        words = made.words if made.words is not None else map_boundaries(text, made.boundaries, made.duration_ms)
                        hit = self.cache.put(key, made.audio, made.ext, made.duration_ms, words)
            finally:
                with self._locks_guard:
                    self._locks.pop(key, None)
                    self._live -= 0 if background else 1
        return {"file": hit.file, "duration_ms": hit.duration_ms, "words": hit.words}
