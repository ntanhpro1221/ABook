"""Ghép giọng + bộ đệm + mốc chữ thành hai việc cho máy chủ giao diện: `voices()` và `clip(giọng, chữ)`.

Một clip là MỘT đoạn chữ (đoạn của chương - `textScript.paragraphsOf`) đọc ở tốc độ 1,0 kèm mốc từng chữ hiện; giao diện ghép các clip
thành chương và chỉnh tốc độ bằng playbackRate nên bộ đệm dùng chung mọi tốc độ.
"""
from __future__ import annotations

import math
import threading
import time
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Protocol

from . import azure, edge, fpt, google, local_stream, loudness, names, readings as book_readings, spoken, supertonic, vieneu, viettel, windows
from .byok import KeyedProvider
from .cache import ClipBooks, ClipCache, clip_key
from .keys import KeyStore
from .mapping import Boundary, fold, map_boundaries, tokens
from .model import Synthesis, Voice, VoiceError, cancellable, hearing
from .prepare import SHARE as PREPARE_SHARE
from .prepare import Prepare

MAX_TEXT = 20_000  # ký tự một clip; đoạn của chương dài hơn nữa là hiếm, và Edge cũng phải cắt thành nhiều lượt
# Giọng trên máy (VieNeu, Supertonic: có `forget`) không đọc gì chừng này giây thì nhả model (vài trăm MB, soát a69: máy chủ giữ ~550 MB suốt 80 phút nghe Edge);
# lần dùng sau nạp lại như lần đầu. Điện thoại cùng số (LocalEngines.IDLE_MS).
IDLE_SECONDS = 180


class Provider(Protocol):
    id: str
    speaks_english: bool  # nói được âm Anh thì chữ Anh để nguyên cho nó đọc; không thì Việt hoá (`names.spoken_names`)

    def voices(self) -> list[Voice]: ...

    def synthesize(self, text: str, native_voice: str) -> Synthesis: ...


class StreamListener(Protocol):
    """Người nghe một clip đang được đọc (máy chủ giao diện: phát luồng về trình phát). Gọi từ các luồng đọc, tuần tự."""

    def started(self) -> None:
        """Đúng lúc byte tiếng ĐẦU TIÊN về (trước đó lỗi thì `clip` ném `VoiceError` như thường, chưa gọi gì)."""

    def audio(self, data: bytes) -> None: ...

    def words(self, words: list[list[int]], duration_ms: int, heard_ms: int = 0) -> None:
        """Mốc từng chữ hiện tạm tính trên phần đã phát (chữ chưa tới đứng cuối phần ấy); `duration_ms` = độ dài phần đã phát; cái sau thay cái trước. `heard_ms` = mốc kết thúc của chữ
        THẬT cuối cùng Edge đã báo: chữ có mốc bắt đầu từ đó trở đi là chữ chưa tới (bị dồn về cuối phần đã phát), chữ trước đó thì đã có tiếng - luồng đứt giữa chừng thì phần tiếp
        bắt đầu từ chữ đầu tiên chưa có tiếng (trình phát, uxfix58)."""

    def format(self, mime: str) -> None:
        """Kiểu tiếng của luồng, trước `audio` đầu - chỉ giọng trên máy (local_stream.MIME); không gọi = MP3 (Edge)."""

    def replaced(self) -> None:
        """Giọng trên máy: tiếng đã phát luồng khác clip cuối (local_stream.LocalStream.close) - người nghe chuyển sang clip cuối."""

    def cut(self, word: int) -> None:
        """Một mảnh giữa clip hỏng hẳn (uxfix63, [edge.StreamSink]): tiếng sẽ dừng trước chữ HIỆN `word` (0-based) - phần trước nó vẫn về hết rồi luồng mới báo lỗi. Người nghe xin phần tiếp từ
        chữ ấy ngay, không đợi lỗi. Gọi sau `started()`, nhiều nhất một lần."""


def _shown_words(words: list[list[int]], spans: list[tuple[int, int] | None] | None, slots: list[int | None] | None) -> list[list[int]]:
    """Mốc từng chữ ĐỌC -> mốc từng chữ HIỆN (chữ hiện thành nhiều chữ đọc, hay không còn chữ nào): `spoken.expand_words` / `readings.expand_words`."""
    if spans is not None:
        return spoken.expand_words(words, spans)
    if slots is not None:
        return book_readings.expand_words(words, slots)
    return words


class _Live:
    """Nối [edge.StreamSink] (tiếng + mốc Edge, theo thứ tự clip cuối) với [StreamListener]: `started()` ở byte đầu, tiếng chuyển thẳng, mốc chữ tạm tính qua đúng đường tính cuối
    (`map_boundaries` + `_shown_words`) trên phần ĐÃ phát - không dày hơn một lần mỗi WORDS_EVERY giây, và luôn một lần khi một mảnh phát hết."""

    WORDS_EVERY = 0.5

    def __init__(self, listener: StreamListener, said: str, spans: list[tuple[int, int] | None] | None, slots: list[int | None] | None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.listener = listener
        self.said = said
        self.spans = spans
        self.slots = slots
        self.clock = clock
        self.started = False
        self.found: list[Boundary] = []
        self.sent_ms = 0
        self._bytes = 0
        self._told: float | None = None  # lúc gửi mốc chữ gần nhất
        self._pending = False  # có mốc mới chưa gửi
        self._cut: int | None = None  # chỗ tiếng dừng ([cut]) báo trước byte đầu: gửi ngay sau nó

    def audio(self, data: bytes) -> None:
        if not self.started:
            self.started = True
            self.listener.started()
        self.listener.audio(data)
        self._bytes += len(data)
        self.sent_ms = self._bytes * 8 * 1000 // edge.BITRATE_BPS
        if self._cut is not None:
            self.listener.cut(self._cut)
            self._cut = None
        if self._pending:
            self._tell(force=False)

    def cut(self, words: int) -> None:
        """[edge.StreamSink.cut]: `words` chữ ĐỌC đầu có tiếng -> chữ HIỆN đầu tiên còn chữ đọc nào từ đó trở đi (chữ hiện thành nhiều chữ đọc mà bị cắt giữa: đọc lại cả chữ ấy), qua đúng đường
        đổi mốc của `_tell` (mốc giả: mỗi chữ đọc mang số thứ tự của nó)."""
        marks = [[index, index] for index in range(len(tokens(self.said)))]
        shown = _shown_words(marks, self.spans, self.slots)
        word = next((index for index, (_, last) in enumerate(shown) if last >= words), len(shown))
        if self.started:
            self.listener.cut(word)
        else:
            self._cut = word

    def boundaries(self, found: list[Boundary]) -> None:
        self.found += found
        self._pending = True
        if self.started:
            self._tell(force=False)

    def piece_done(self) -> None:
        if self.started and self._pending:
            self._tell(force=True)

    def _tell(self, *, force: bool) -> None:
        now = self.clock()
        if not force and self._told is not None and now - self._told < self.WORDS_EVERY:
            return
        self._told = now
        self._pending = False
        heard = self.found[-1].end_ms if self.found else 0
        duration = max(self.sent_ms, heard)
        self.listener.words(_shown_words(map_boundaries(self.said, self.found, duration), self.spans, self.slots), duration, heard)


class EdgeProvider:
    id = "edge"
    speaks_english = True  # đo 04-10: Edge đọc "Rose", "Mike", "laptop" để nguyên ra tiếng Anh nhận được
    normalises_text = True  # nhận chữ đã chuẩn hoá như giọng trên máy (spoken.py; đo a39: âm tiết sai 29% -> 12%); giọng khác không có cờ này nhận chữ thô
    ranks_requests = True  # `synthesize(rank=...)`: hết chỗ kết nối thì clip gần người nghe hơn đứng trước (edge.ConnectionSlots)

    def __init__(self, client: edge.EdgeClient | None = None) -> None:
        self.client = client or edge.EdgeClient()

    def voices(self) -> list[Voice]:
        return [Voice(f"edge:{code}", name, "edge", True, code == edge.DEFAULT_VOICE, gender=gender) for code, name, gender in edge.VOICES]

    def synthesize(self, text: str, native_voice: str, *, rank: int = edge.RANK_BACKGROUND, sink: edge.StreamSink | None = None,
                   cancelled: Callable[[], bool] | None = None) -> Synthesis:
        return self.client.synthesize(text, native_voice, rank=rank, sink=sink, cancelled=cancelled)


class DeviceProvider:
    """Giọng của máy (Windows: windows.py). Máy khác Windows chưa có: danh sách rỗng."""

    id = "device"
    speaks_english = True  # chưa đo (giọng Windows tiếng Việt): giữ cách đọc cũ tới khi đo

    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def voices(self) -> list[Voice]:
        return windows.voices(self.folder)

    def synthesize(self, text: str, native_voice: str) -> Synthesis:
        return windows.synthesize(self.folder, native_voice, text)


def _take(lock: threading.Lock, cancelled: Callable[[], bool] | None) -> None:
    """Giữ `lock` (lượt đọc cùng đoạn của người khác đang chạy thì chờ nó); `cancelled()` đúng trong lúc chờ thì thôi - VoiceError "cancelled"."""
    if cancelled is None:
        lock.acquire()
        return
    while not lock.acquire(timeout=edge.CANCEL_POLL):
        if cancelled():
            raise VoiceError("Đã bỏ lượt đọc này.", "cancelled")


def keyed_providers(keys: KeyStore) -> list[KeyedProvider]:
    """Giọng dùng khoá của người dùng (byok.py), Azure đứng đầu: nhà chính thức của chính các giọng Edge."""
    return [azure.AzureProvider(keys), google.GoogleProvider(keys), fpt.FptProvider(keys), viettel.ViettelProvider(keys)]


class ReadAloud:
    """`keys`: kho khoá của giọng dùng khoá riêng - có thì (khi `providers` để trống) các giọng ấy xếp sau Edge, trước giọng của máy.
    `vieneu_locate`: nơi mô-đun "Giọng VieNeu" đặt các phần (webui/vieneu_module.installed) - có thì thêm giọng VieNeu vào danh sách;
    `vieneu_engines`: bộ dựng engine VieNeu theo tầng (webui/vieneu_module.make_engine: Turbo dùng bản tăng tốc khi có); bỏ trống = engine ONNX;
    `supertonic_locate`: như vậy cho mô-đun "Giọng Supertonic" (webui/supertonic_module.installed);
    `rtf`: tốc độ tự đo của giọng (để "Làm trước" ước thời gian).
    Bậc "Nhanh hơn" của "Tốc độ giọng trên máy" (webui/voice_speed.py, chỉ Nghe ngay, chỉ giọng Supertonic): `speed(giọng)` = dấu bậc đang dùng ("fast<số bước>",
    "" = bậc chất lượng); khi khác rỗng, clip đọc bằng nhà cung cấp thứ hai của giọng ấy - `supertonic_fast_locate` (supertonic_module.installed_fast) - và dấu
    ấy vào khoá bộ đệm.
    `model_mark(giọng, dấu bậc)`: dấu model của giọng trên máy (8 hex: ghim các file model đang dùng + lịch đọc - supertonic_module / vieneu_module.model_mark),
    vào khoá bộ đệm của giọng có `reading_tag`: cập nhật model hay đổi lịch đọc thì clip cũ không trúng nữa, đoạn được đọc lại một lần."""

    def __init__(self, folder: Path | str, providers: list[Provider] | None = None, *, limit: int | None = None,
                 keys: KeyStore | None = None, vieneu_locate: Callable[[], vieneu.Installed | None] | None = None,
                 supertonic_locate: Callable[[], supertonic.Installed | None] | None = None,
                 vieneu_engines: Callable[[str, vieneu.Installed], Any] | None = None,
                 rtf: Callable[[str], float | None] = lambda _voice: None,
                 speed: Callable[[str], str] = lambda _voice: "",
                 supertonic_fast_locate: Callable[[], supertonic.Installed | None] | None = None,
                 model_mark: Callable[[str, str], str] = lambda _voice, _tier: "", clock: Callable[[], float] = time.monotonic,
                 spare: Callable[[], bool] = lambda: True) -> None:
        self.folder = Path(folder)
        kwargs = {} if limit is None else {"limit": limit}
        self.cache = ClipCache(self.folder, pin_file=self.folder.with_name(self.folder.name + "-clip-pins.txt"), **kwargs)
        if providers is None:
            providers = [EdgeProvider(), *(keyed_providers(keys) if keys is not None else []), DeviceProvider(self.folder / "tools")]
        self.providers: dict[str, Provider] = {provider.id: provider for provider in providers}
        # giọng trên máy báo từng khúc vừa đọc (phát luồng, local_stream.py); bộ căn chữ nhớ phần đã căn lúc phát luồng cho clip cuối
        self.vieneu = (vieneu.VieneuProvider(vieneu_locate, engines=local_stream.reporting(vieneu_engines), aligner=local_stream.remembering_aligner)
                       if vieneu_locate is not None else None)
        if self.vieneu is not None:
            self.providers[self.vieneu.id] = self.vieneu
        self.supertonic = supertonic.SupertonicProvider(supertonic_locate, aligner=local_stream.remembering_aligner) if supertonic_locate is not None else None
        if self.supertonic is not None:
            self.providers[self.supertonic.id] = self.supertonic
        # Bậc "Nhanh hơn": nhà cung cấp thứ hai của cùng giọng (engine riêng, nên Nghe ngay và việc xuất không tranh nhau một engine).
        self.fast: dict[str, Provider] = {}
        if supertonic_fast_locate is not None:
            self.fast[supertonic.PREFIX] = supertonic.SupertonicProvider(supertonic_fast_locate, aligner=local_stream.remembering_aligner)
        self._speed = speed
        self._model_mark = model_mark
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._live = 0  # clip của người đang nghe đang được đọc: "Làm trước" nhường
        self._rtf = rtf
        # Gốc Nhật / Hàn của từng cuốn (máy đoán + người dùng ghi đè); cạnh thư mục bộ đệm, không nằm trong đó (bộ đệm dọn mọi file .json lâu không dùng).
        self.origins = names.BookOrigins(self.folder.with_name(self.folder.name + "-book-origins.json"))
        # Cuốn nào đã làm ra clip nào ("bản đọc đã làm" của cuốn): cạnh thư mục bộ đệm như `origins`.
        self.books = ClipBooks(self.folder.with_name(self.folder.name + "-clip-books.jsonl"))
        self.prepare = Prepare(lambda voice, text, origin, readings, book: self.clip(voice, text, background=True, pin=True, origin=origin, readings=readings, book=book),
                               lambda: self._live, int(self.cache.limit * PREPARE_SHARE), rtf, lambda: self.cache.pinned_bytes() >= int(self.cache.limit * PREPARE_SHARE))
        # Nhả model của giọng trên máy khi thôi dùng ([release_idle]): lúc dùng gần nhất / số việc đang dùng, theo nhà cung cấp; giọng đã nhả không còn trong `_used`.
        self._clock = clock
        self._idle_guard = threading.Lock()
        self._used: dict[str, float] = {}
        self._using: dict[str, int] = {}
        self._idle_timer: threading.Timer | None = None
        self._spare = spare  # máy còn dư để nạp sẵn model chưa ai bấm nghe ([preload]): không chạy pin yếu, không thiếu RAM
        self._preloading: set[str] = set()

    @property
    def live(self) -> int:
        """Số clip của người đang nghe đang được đọc: việc nền (Làm trước, xuất sách nói) đứng chờ khi khác 0."""
        return self._live

    def speed(self, voice_id: str) -> float | None:
        """Tốc độ tự đo của giọng (giây máy làm cho mỗi giây nghe) - để ước thời gian; None nếu chưa đo / giọng không đo được."""
        return self._rtf(voice_id)

    def warm(self) -> None:
        """Liệt kê giọng của máy ở luồng nền (hỏi PowerShell mất ~1 giây): lúc người nghe mở một cuốn chỉ-có-chữ, danh sách đã sẵn."""
        def run() -> None:
            for provider in self.providers.values():
                try:
                    provider.voices()
                except Exception:  # noqa: BLE001 - chỉ là làm nóng; lỗi thật sẽ hiện khi hỏi danh sách
                    pass

        threading.Thread(target=run, name="readaloud-warm", daemon=True).start()

    def forget(self, provider_id: str) -> None:
        """Mô-đun giọng `provider_id` vừa cập nhật / gỡ (hay lâu không dùng, [release_idle]): nạp lại engine của cả hai bậc ở lần dùng sau."""
        for provider in (self.providers.get(provider_id), self.fast.get(provider_id)):
            if provider is not None and hasattr(provider, "forget"):
                provider.forget()

    # ---- nhả model của giọng trên máy khi thôi dùng -------------------------------------------------------------------------------

    def _engine_use(self, provider_id: str, step: int) -> None:
        """Giọng có engine (`forget`) vừa được dùng: `step` +1 lúc bắt đầu một việc dùng nó, -1 lúc xong. Hẹn lần soát nhả model nếu chưa hẹn."""
        if not hasattr(self.providers.get(provider_id), "forget"):
            return
        with self._idle_guard:
            self._used[provider_id] = self._clock()
            self._using[provider_id] = self._using.get(provider_id, 0) + step
            if self._idle_timer is None:
                self._schedule_idle(IDLE_SECONDS)

    def _schedule_idle(self, delay: float) -> None:
        self._idle_timer = threading.Timer(delay, self._idle_check)
        self._idle_timer.daemon = True
        self._idle_timer.start()

    def _idle_check(self) -> None:
        self.release_idle()
        with self._idle_guard:
            self._idle_timer = None
            if self._used:  # còn giọng chưa nhả: soát lại lúc giọng dùng lâu nhất đủ IDLE_SECONDS (đang bận thì 1/6 chừng ấy nữa)
                self._schedule_idle(max(IDLE_SECONDS / 6, IDLE_SECONDS - (self._clock() - min(self._used.values()))))

    @contextmanager
    def holding(self, voice_id: str) -> Iterator[None]:
        """Việc nền dài dùng `voice_id` (xuất sách nói): trong lúc này model của giọng ấy không bị nhả, kể cả khi việc đứng chờ người nghe giữa các đoạn."""
        provider_id = voice_id.partition(":")[0]
        self._engine_use(provider_id, 1)
        try:
            yield
        finally:
            self._engine_use(provider_id, -1)

    def release_idle(self) -> list[str]:
        """Nhả model của mọi giọng trên máy không ai dùng đã IDLE_SECONDS (cả hai bậc tốc độ, `forget`); không nhả giọng đang đọc, đang được việc nền giữ
        ([holding]) hay đang được "Làm trước". Trả các nhà cung cấp vừa nhả."""
        job = self.prepare.status()
        preparing = str(job.get("voice") or "").partition(":")[0] if job.get("state") == "running" else ""
        with self._idle_guard:
            now = self._clock()
            idle = [name for name, at in self._used.items()
                    if name != preparing and not self._using.get(name) and now - at >= IDLE_SECONDS]
            for name in idle:
                del self._used[name]
                self.forget(name)
        return idle

    def preload(self, voice_id: str) -> bool:
        """Nạp sẵn model của giọng trên máy `voice_id` ở luồng nền (trang sách / trình phát của cuốn đang mở): bấm phát không phải chờ nạp (~4,6 s trên OPPO, livejoin3).
        Không đọc gì; tính như một lần dùng (nhả lại sau [IDLE_SECONDS] không ai dùng). Bỏ qua (False) với giọng không có engine, giọng chưa tải, model đã nạp / đang nạp, hay
        máy không còn dư (`spare`: chạy pin dưới 20 %, thiếu RAM). Trả ngay; True = đã bắt đầu nạp."""
        try:
            provider, native = self._resolve(voice_id)
        except VoiceError:
            return False
        tier = self._speed(voice_id)
        if tier and provider.id in self.fast:
            provider = self.fast[provider.id]
        load = self._loader(provider, native)
        if load is None or not self._spare():
            return False
        with self._idle_guard:
            slot = f"{id(provider)}:{native}"
            if slot in self._preloading:
                return False
            self._preloading.add(slot)

        def run() -> None:
            self._engine_use(provider.id, 1)
            try:
                load()
            except Exception:  # noqa: BLE001 - chỉ là nạp sẵn; lỗi thật sẽ hiện khi đọc
                pass
            finally:
                self._engine_use(provider.id, -1)
                with self._idle_guard:
                    self._preloading.discard(slot)

        threading.Thread(target=run, name="readaloud-preload", daemon=True).start()
        return True

    def _loader(self, provider: Provider, native: str) -> Callable[[], Any] | None:
        """Việc nạp engine của `provider` cho giọng `native` mà không đọc gì; None = giọng này không có engine để nạp sẵn."""
        if isinstance(provider, supertonic.SupertonicProvider):
            return lambda: provider.preload(native)
        if isinstance(provider, vieneu.VieneuProvider):
            def load() -> None:
                installed = provider.locate()
                if installed is not None:
                    provider.engine(native.partition("/")[0], installed)
            return load
        return None

    def benchmark(self, provider_id: str, tier: str) -> dict[str, Any]:
        """Tự đo sau khi tải mô-đun (`benchmark` của nhà cung cấp): việc này cũng nạp model, nên tính như một lần dùng."""
        self._engine_use(provider_id, 1)
        try:
            return self.providers[provider_id].benchmark(tier)  # type: ignore[attr-defined]
        finally:
            self._engine_use(provider_id, -1)

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

    def clip(self, voice_id: str, text: str, *, cached_only: bool = False, background: bool = False, origin: str | None = None,
             readings: Mapping[str, str] | None = None, book: str | None = None, rank: int = edge.RANK_BACKGROUND,
             stream: StreamListener | None = None, cancelled: Callable[[], bool] | None = None, quality: bool = False, pin: bool = False) -> dict[str, Any]:
        """Clip của `text` bằng `voice_id`: `{file, duration_ms, words}` (từ bộ đệm hay đọc mới). `cached_only`: không đọc mới - chưa có thì `VoiceError("uncached")`.
        `background`: việc "Làm trước" (prepare.py) - không tính là người đang nghe chờ. `origin`: gốc của cuốn ("ja" / "ko", `names.BookOrigins`) - giọng đọc
        trên máy (VieNeu, Supertonic: có `reading_tag`) đọc tên romaji / RR theo luật phiên âm, Supertonic còn Việt hoá từ Anh (`speaks_english` False); Edge (`normalises_text`) nhận
        đúng chữ mà giọng trên máy nhận (`spoken.layout`: tên, tiếng kêu, số, ký hiệu, viết tắt), mốc từng chữ về đủ chữ hiện; giọng dùng khoá bỏ qua.
        `readings`: cách đọc riêng của cuốn ({chữ hiện: chữ đọc}, readings.py) - MỌI giọng: giọng trên máy áp sau bước đọc tên, giọng khác nhận chữ
        đem đọc đã thay (cùng số chữ, nên mốc từng chữ vẫn khớp chữ hiện); khoá bộ đệm có dấu của những cách đọc có trong đoạn.
        `book`: mã cuốn đang nghe - clip được ghi vào sổ của cuốn để biết "bản đọc đã làm" của cuốn nặng bao nhiêu và xoá được ([cache_usage], [clear_book]).
        `rank`: số đoạn người nghe phải nghe trước đoạn này (trình phát: 0 = đang đứng chờ đúng nó - nhảy tới, mở chương; 1 = đoạn kế...) - giọng có `ranks_requests` (Edge) cho đoạn gần người nghe hơn
        đi trước khi hết chỗ kết nối; không nói thì đứng sau mọi đoạn có rank.
        `stream`: người nghe clip đang đọc (uxfix56) - CHỈ khi chưa có trong bộ đệm, không `cached_only` / `background`, giọng có `ranks_requests` và `rank` == 0 (đoạn người nghe đang đứng chờ):
        tiếng + mốc chữ tạm chảy tới đó ngay khi về (`StreamListener`); xong vẫn vào bộ đệm đúng như không phát luồng và trả dict như thường (người gọi gửi bản cuối). Ngoài ra `stream` bị bỏ qua.
        Giọng trên máy cũng vậy khi `stream.local` (trình phát nhận được FLAC), KHÔNG cần `rank` 0 (livejoin: đoạn đọc trước mà người nghe tới khi nó còn đang đọc dở nhập luồng thay vì đợi đọc xong cả đoạn): từng khúc vừa đọc xong đi ngay (local_stream.py, chờ đủ tiếng theo `stream.speed`,
        hay tới `stream.reach` - lúc người nghe hết tiếng trước đoạn này), clip cuối không đổi một byte.
        `cancelled`: người gọi bỏ clip được giữa chừng (Huỷ xuất sách nói soát a62; người nghe nhảy đi nơi khác - máy chủ giao diện: trình phát đóng kết nối): đang chờ lượt
        đọc cùng đoạn, đang đọc bằng giọng có `ranks_requests` (Edge, ổ cắm bị cắt) hay bằng giọng trên máy (engine hỏi `model.stop_if_cancelled` giữa các khúc và các bước,
        uxfix70) thì dừng trong vòng một phần giây với `VoiceError` lý do "cancelled" và không có gì vào bộ đệm. Giọng khác đọc nốt đoạn đang đọc.
        `quality`: luôn bậc chất lượng của giọng (xuất sách nói, MP3 / M4B) - không thì giọng có hai bậc đọc bậc mà "Tốc độ giọng trên máy" đang dùng (`speed`);
        clip bậc nhanh có dấu bậc trong khoá nên không bao giờ đứng thay clip chất lượng. Ngược lại thì được (uxfix70): nghe ở bậc nhanh mà đoạn đã có clip bậc chất lượng
        (làm trước khi đổi bậc, hay xuất sách nói) thì dùng clip ấy, không đọc lại.
        `pin`: "Làm trước" (prepare.py) - clip được GHIM trong bộ đệm (cache.py) tới khi người nghe tới nó; một lần gọi không phải nền (nghe, kể cả `cached_only`) bỏ ghim clip ấy."""
        if not fold(text):
            raise VoiceError("Đoạn này không có chữ nào để đọc.", "empty")
        if len(text) > MAX_TEXT:
            raise ValueError("Đoạn chữ quá dài để đọc một lượt")
        provider, native = self._resolve(voice_id)
        tier = "" if quality else self._speed(voice_id)
        if tier and provider.id in self.fast:
            provider = self.fast[provider.id]
        else:
            tier = ""
        reads_names = hasattr(provider, "reading_tag")
        normalised = getattr(provider, "normalises_text", False)
        if reads_names:
            name_tag = provider.reading_tag(text, origin)
        else:
            name_tag = spoken.tag(text, origin, provider.speaks_english) if normalised else ""
        # giọng VieNeu / Supertonic: khúc dưới trần đỉnh thật, câu ngắn nhỏ được nâng ngay trong clip (loudness.under_ceiling, lift_wav) - dấu riêng trong khoá
        lifted = loudness.lifts(voice_id)
        tags = (name_tag, book_readings.tag(text, readings), loudness.clip_tag(voice_id))

        def key_at(tier_tag: str) -> str:
            """Khoá của đoạn ở bậc `tier_tag` ("" = chất lượng): dấu đọc + dấu bậc + dấu model (chỉ giọng trên máy)."""
            mark = self._model_mark(voice_id, tier_tag) if reads_names else ""
            return clip_key(provider.id, native, text, "+".join(tag for tag in (*tags, tier_tag, mark) if tag))

        key = key_at(tier)
        hit = None
        if tier:  # nghe ở bậc nhanh: clip bậc chất lượng của đoạn này đã có thì dùng nó (không bao giờ ngược lại)
            quality_key = key_at("")
            hit = self.cache.get(quality_key)
            if hit is not None:
                key = quality_key
        if hit is None:
            hit = self.cache.get(key)
        if hit is None:
            if cached_only:
                raise VoiceError("Chưa đọc đoạn này.", "uncached")
            with self._locks_guard:
                lock = self._locks.setdefault(key, threading.Lock())
                self._live += 0 if background else 1
            self._engine_use(provider.id, 1)  # giọng trên máy: đang dùng, không nhả model ([release_idle])
            try:
                _take(lock, cancelled)
                try:  # hai yêu cầu cùng đoạn (đọc trước + bấm nghe) chỉ đọc một lần
                    hit = self.cache.get(key)
                    if hit is None:
                        spans = None
                        if normalised and not reads_names:
                            said, spans = spoken.layout(text, origin, provider.speaks_english, readings)
                            slots = None
                        else:
                            said, slots = (text, None) if reads_names else book_readings.spoken_layout(text, readings)
                        local = None  # giọng trên máy phát luồng: người nghe từng khúc (local_stream.LocalStream)
                        try:
                            if not reads_names:
                                ranked = getattr(provider, "ranks_requests", False)
                                if ranked and stream is not None and rank == 0 and not background:
                                    made = provider.synthesize(said, native, rank=rank, sink=_Live(stream, said, spans, slots))
                                elif ranked and cancelled is not None:
                                    made = provider.synthesize(said, native, rank=rank, cancelled=cancelled)
                                else:
                                    made = provider.synthesize(said, native, rank=rank) if ranked else provider.synthesize(said, native)
                            else:
                                if stream is not None and not background and getattr(stream, "local", False):  # mọi rank: đoạn đọc trước cũng nhập luồng được khi người nghe tới nó lúc còn đang đọc dở
                                    local = local_stream.for_clip(stream, provider, native, text, origin, readings if tags[1] else None, getattr(stream, "speed", 1.0),
                                                                  getattr(stream, "reach", math.inf))
                                with cancellable(cancelled), hearing(local):  # engine hỏi cờ giữa các khúc / bước (model.stop_if_cancelled)
                                    made = provider.synthesize(text, native, origin, readings) if tags[1] else provider.synthesize(text, native, origin)
                            if lifted and made.ext == "wav":
                                made = replace(made, audio=loudness.lift_wav(voice_id, made.audio))
                            if local is not None:
                                local.close(made.audio)
                        except BaseException:
                            if local is not None:
                                local.drop()
                            raise
                        words = made.words if made.words is not None else map_boundaries(said, made.boundaries, made.duration_ms)
                        words = _shown_words(words, spans, slots)  # chữ hiện thành nhiều chữ đọc / cụm đọc ngắn hơn số chữ hiện: mốc về đủ chữ hiện
                        if pin:
                            self.cache.pin(key)  # trước khi ghi: lần tỉa ngay trong lúc ghi đã thấy nó là clip ghim
                        hit = self.cache.put(key, made.audio, made.ext, made.duration_ms, words)
                finally:
                    lock.release()
            finally:
                self._engine_use(provider.id, -1)
                with self._locks_guard:
                    self._locks.pop(key, None)
                    self._live -= 0 if background else 1
        if pin:
            self.cache.pin(hit.key)
        elif not background:
            self.cache.unpin(hit.key)
        if book:
            self.books.note(book, key)
        return {"file": hit.file, "duration_ms": hit.duration_ms, "words": hit.words}

    def cache_usage(self, book: str | None) -> dict[str, int]:
        """Dung lượng bản đọc đã làm: `book` (của cuốn này) và `total` (cả bộ đệm, mọi cuốn), tính bằng byte."""
        mine = 0
        if book:
            keys = self.books.keys(book)
            mine, present = self.cache.usage(keys)
            if len(present) < len(keys):
                self.books.forget(book, keys - present)  # bộ đệm đã dọn những clip này
        return {"book": mine, "total": self.cache.size()}

    def clear_book(self, book: str) -> dict[str, int]:
        """Xoá bản đọc đã làm của cuốn `book` (chỉ clip nó đã làm ra / đã nghe; cuốn khác không bị đụng, trừ đoạn trùng chữ y hệt); trả [cache_usage] sau đó."""
        self.prepare.forget(book)  # trước khi xoá: việc làm trước đang chạy sẽ ghi clip mới vào sổ của cuốn
        keys = self.books.keys(book)
        self.cache.remove(keys)
        self.books.forget(book, keys)
        return self.cache_usage(book)

    def clear_all(self) -> dict[str, int]:
        """Dọn mọi bản đọc đã làm của cả máy ("Dọn bản đọc đã làm" ở Cài đặt > Giọng đọc); trả [cache_usage] sau đó."""
        self.prepare.forget(None)
        self.cache.clear()
        self.books.forget_all()
        return self.cache_usage(None)
