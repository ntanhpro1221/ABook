"""Phát LUỒNG clip của giọng trên máy (VieNeu, Supertonic) cho đoạn người nghe đang đứng chờ: tiếng đầu tới sau khi đọc xong KHÚC đầu, không phải cả đoạn.

Giọng trên máy đọc một đoạn theo khúc (`vieneu.units`) rồi ghép (`vieneu_engine.join`); clip cuối vẫn làm và vào bộ đệm y như không phát luồng - ở đây chỉ
NGHE từng khúc vừa xong (`model.hearing` / `model.unit_made`) và đẩy nó tới trình phát qua cùng chỗ nhận của Edge (`service.StreamListener`, máy chủ: bản ghi
A / W / E). Tiếng đi dưới dạng FLAC không nén trong MP4 phân mảnh (flac_mp4.py): đúng các mẫu int16 của file WAV cuối.

- Ghép: `vieneu_engine.Joiner` (chính phép ghép của `join`), mẫu int16: `vieneu.wav_bytes` (bỏ đầu WAV 44 byte), mốc chữ của khúc: `vieneu.timed_synthesis` trên đúng
  khúc ấy ở đúng chỗ của nó - cùng lời gọi bộ căn chữ như lúc làm clip cuối, nên bộ căn nhớ kết quả ([remembering_aligner]) và clip cuối không căn lại.
- Đoạn chỉ một khúc thì không phát luồng ([for_clip] trả None): khúc đầu LÀ cả clip, tiếng đầu không tới sớm hơn được, còn luồng thì tốn thêm một lần bù độ to.
- Bù độ to cả clip (`loudness.lift_wav`) chỉ biết khi xong: clip nhiều khúc mà bị bù (hiếm) thì tiếng luồng khác clip cuối - [LocalStream.close] so và báo
  `replaced()`: trình phát chuyển sang file cuối tại chỗ đang nghe.
- Bắt đầu phát ([ready_to_play]): chỉ khi các khúc còn lại sẽ kịp xong trước khi tiếng tới chúng, theo tốc độ đo ngay trên clip này - máy chậm hơn thời gian thực thì đệm
  trước, không phát rồi đứt. Bản điện thoại: readaloud/LocalLive.kt (cùng phép, cùng hằng số).
- Hoặc khi người nghe đã hết tiếng trước đoạn này (`reach`, [LocalStream.release]): từ lúc ấy giữ khúc đã đọc xong chỉ làm khoảng lặng dài thêm (dev/gap, OPPO, Supertonic nhanh: lặng
  4,0 s sau tiêu đề chương và 9,1 s trước một đoạn dài trong khi khúc đầu đã xong; phát ngay thì 0,5 + 0,6 s và 0,1 + 1,3 s, chỗ ngắt rơi vào cuối câu).
"""
from __future__ import annotations

import copy
import hashlib
import math
import threading
import time
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from . import flac_mp4, supertonic, vieneu
from .model import listening, unit_made

if TYPE_CHECKING:
    from . import vieneu_engine as ve

MIME = flac_mp4.MIME
SAFETY = 1.2  # đệm sai số cho ước độ dài / tốc độ của các khúc còn lại ([ready_to_play])
REMEMBER = 64  # kết quả căn chữ giữ lại cho clip cuối (mỗi khúc một)


def ready_to_play(made_s: float, work_s: float, chars_done: int, chars_left: Sequence[int], speed: float = 1.0) -> bool:
    """Bắt đầu phát được chưa: đã có `made_s` giây tiếng sau `work_s` giây máy làm (của `chars_done` ký tự), còn các khúc `chars_left` (ký tự, theo thứ tự),
    người nghe nghe ở tốc độ `speed`. r = work_s / made_s (giây máy cho mỗi giây tiếng), khúc k ước L_k = made_s / chars_done * ký tự. Được khi với MỌI khúc
    còn lại k: SAFETY * r * (L_1 + ... + L_k) <= (made_s + L_1 + ... + L_{k-1}) / speed - khúc k xong trước khi tiếng tới đầu nó."""
    if not chars_left:
        return True
    if made_s <= 0 or chars_done <= 0:
        return False
    rate, per_char = work_s / made_s, made_s / chars_done
    ahead, need = made_s, 0.0
    for chars in chars_left:
        length = per_char * chars
        need += SAFETY * rate * length
        if need > ahead / max(speed, 0.1):
            return False
        ahead += length
    return True


class _Remembering:
    """Bộ căn chữ nhớ kết quả của các lần căn trong lúc phát luồng ([LocalStream] căn từng khúc), để clip cuối (`timed_synthesis`, cùng sóng, cùng chữ, cùng
    chỗ) lấy lại thay vì căn lần nữa. Ngoài lúc phát luồng thì chỉ chuyển lời gọi."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self._kept: dict[tuple[bytes, str, float], Any] = {}
        self._guard = threading.Lock()

    def align(self, wave: Any, text: str, offset: float = 0.0) -> Any:
        import numpy as np

        if not listening():
            return self.inner.align(wave, text, offset)
        key = (hashlib.sha1(np.ascontiguousarray(wave).tobytes()).digest(), text, float(offset))
        with self._guard:
            hit = self._kept.pop(key, None)
        if hit is not None:
            return copy.deepcopy(hit)
        found = self.inner.align(wave, text, offset)
        with self._guard:
            self._kept[key] = copy.deepcopy(found)
            while len(self._kept) > REMEMBER:
                self._kept.pop(next(iter(self._kept)))
        return found


_remembered: tuple[Any, _Remembering] | None = None
_remembered_guard = threading.Lock()


def remembering_aligner() -> Any:
    """`aligner=` của VieneuProvider / SupertonicProvider: bộ căn chung (`word_timing.get_aligner`) bọc [_Remembering]; None khi máy không có bộ căn."""
    global _remembered
    from ..webui import word_timing

    found = word_timing.get_aligner()
    if found is None:
        return None
    with _remembered_guard:
        if _remembered is None or _remembered[0] is not found:
            _remembered = (found, _Remembering(found))
        return _remembered[1]


class _Reporting:
    """Engine VieNeu bọc: mỗi `infer` (một khúc) báo sóng vừa ra cho người nghe khúc ([model.unit_made]); mọi thứ khác chuyển thẳng. Sóng `infer` trả là đúng thứ
    `vieneu._speak` ghép vào clip (khúc không có âm vị thì không gọi engine: clip ghép thêm khúc rỗng - [LocalStream.close] nhận ra)."""

    def __init__(self, engine: Any) -> None:
        self._engine = engine

    def infer(self, phonemes: str, *args: Any, **kwargs: Any) -> Any:
        began = time.perf_counter()
        wave = self._engine.infer(phonemes, *args, **kwargs)
        unit_made(wave, self._engine.SAMPLE_RATE, phonemes, time.perf_counter() - began)
        return wave

    def __getattr__(self, name: str) -> Any:
        return getattr(self._engine, name)


def reporting(make: Callable[[str, Any], Any] | None) -> Callable[[str, Any], Any]:
    """`engines=` của VieneuProvider: bộ dựng `make` (None = engine ONNX) mà engine nào cũng báo từng khúc ([_Reporting])."""
    build = make or vieneu._real_engine  # cùng gói: đúng bộ dựng mặc định của VieneuProvider
    return lambda tier, installed: _Reporting(build(tier, installed))


def plan(provider: Any, native: str, text: str, origin: str | None, readings: Any) -> tuple[list[str], list[vieneu.Unit]]:
    """Chữ hiện + các khúc của đoạn, đúng như nhà cung cấp sẽ chia (`vieneu.units` với cỡ khúc của giọng)."""
    if provider.id == vieneu.PREFIX:
        return vieneu.units(text, vieneu.MAX_CHARS[native.partition("/")[0]], origin, provider.speaks_english, readings)
    return supertonic.cut(text, origin, provider.speaks_english, readings)  # khúc đầu của Supertonic được cắt ngắn


def for_clip(listener: Any, provider: Any, native: str, text: str, origin: str | None, readings: Any, speed: float = 1.0,
             reach: float = math.inf) -> LocalStream | None:
    """Người nghe khúc cho một lượt `provider.synthesize(text, native, origin, readings)` của giọng trên máy (service.ReadAloud.clip), cùng bộ căn chữ giọng ấy dùng.
    `reach`: lúc (time.perf_counter) người nghe hết tiếng trước đoạn này ([LocalStream]). None khi đoạn chỉ một khúc: phát luồng không làm tiếng đầu tới sớm hơn (đo 20-10: Supertonic đoạn một khúc chậm thêm 0,1-0,2 s vì bù độ to hai lần)."""
    toks, parts = plan(provider, native, text, origin, readings)
    if len(parts) < 2:
        return None
    installed = provider.locate()
    aligner = remembering_aligner() if installed is not None and installed.aligner else None
    return LocalStream(listener, toks, parts, aligner, speed=speed, reach=reach)


class LocalStream:
    """Người nghe từng khúc của MỘT clip giọng trên máy (đặt bằng `model.hearing`), đẩy tiếng + mốc chữ tạm tới `listener` ([service.StreamListener]).
    `toks`, `parts`: [plan]; `aligner`: bộ căn của nhà cung cấp (None = chia theo âm tiết); `speed`: tốc độ phát của người nghe.
    `reach`: lúc (theo `clock`) người nghe hết tiếng trước đoạn này - từ đó khúc đã đọc xong đi ngay, kể cả khi [ready_to_play] chưa cho (inf: không biết / không phát);
    `later(giây, việc)`: chạy `việc` sau từng ấy giây ở luồng khác (bài thử tự gọi) - khi `reach` tới giữa hai khúc."""

    def __init__(self, listener: Any, toks: list[str], parts: list[vieneu.Unit], aligner: Any, *, speed: float = 1.0,
                 clock: Callable[[], float] = time.perf_counter, reach: float = math.inf,
                 later: Callable[[float, Callable[[], None]], Any] | None = None) -> None:
        self.listener = listener
        self.toks = toks
        self.parts = parts
        self.aligner = aligner
        self.speed = speed
        self.clock = clock
        self.reach = reach
        self.later = later or _schedule
        self.started = False
        self.closed = False  # [close] / [drop] đã chạy: [release] muộn không gửi gì
        self._waking = False
        self._timer: Any = None
        self._guard = threading.Lock()  # khúc mới (luồng đọc), [release] (luồng hẹn giờ), [close]
        self.broken = False  # lỗi trong lúc đẩy luồng: thôi đẩy, clip cuối vẫn làm (trình phát chuyển sang file cuối - [close])
        self._joiner: ve.Joiner | None = None
        self._rate = 0
        self._pause = 0.0
        self._work = 0.0  # giây máy đã làm clip này: từ đầu khúc đầu tới lúc khúc mới nhất sẵn sàng (không tính nạp model)
        self._last_at = 0.0
        self._words: list[list[int]] = []
        self._held: list[bytes] = []  # khúc đã đọc mà chưa gửi (chờ [ready_to_play])
        self._sent = hashlib.sha1()  # PCM đã gửi, để [close] so với clip cuối
        self._sent_samples = 0
        self._sequence = 0

    def __call__(self, wave: Any, rate: int, said: str, seconds: float) -> None:
        if self.broken:
            return
        if self._joiner is None:
            self._last_at = self.clock() - seconds
        with self._guard:
            try:
                self._unit(wave, rate, said)
            except Exception:  # noqa: BLE001 - đẩy luồng hỏng không được làm hỏng lượt đọc: clip cuối vẫn ra, trình phát chuyển sang nó
                self.broken = True

    def _unit(self, wave: Any, rate: int, said: str) -> None:
        import numpy as np

        from . import vieneu_engine as ve  # numpy: bản cài chỉ để nghe không có (như supertonic.py)

        if self._joiner is None:
            self._joiner, self._rate = ve.Joiner(rate), rate
        index = len(self._joiner.spans)
        pad, piece = self._joiner.add(wave, self._pause)
        self._pause = ve.gap_after(said)
        start, stop = self._joiner.spans[-1]
        pcm = vieneu.wav_bytes(np.concatenate([np.zeros(pad, dtype=np.float32), piece]), rate)[44:]
        if index < len(self.parts):
            placed = np.concatenate([np.zeros(start, dtype=np.float32), piece])  # khúc ở đúng chỗ của nó: cùng lời gọi bộ căn như timed_synthesis cuối
            self._words += vieneu.timed_synthesis(placed, rate, self.toks, [self.parts[index]], [(start, stop)], self.aligner).words or []
        self._held.append(pcm)
        now = self.clock()
        self._work += now - self._last_at
        self._last_at = now
        made = self._joiner.samples / rate
        done = sum(len(part.text(self.toks)) for part in self.parts[:index + 1])
        left = [len(part.text(self.toks)) for part in self.parts[index + 1:]]
        if self.started or now >= self.reach or ready_to_play(made, self._work, done, left, self.speed):
            self._flush()
        elif not self._waking and self.reach != math.inf:
            self._waking = True  # người nghe hết tiếng trước khi khúc kế đọc xong: cho họ nghe khúc này từ lúc ấy
            self._timer = self.later(max(0.0, self.reach - now), self.release)

    def release(self) -> None:
        """`reach` đã qua: các khúc đang giữ đi ngay (không gì khi luồng đã bắt đầu, đã hỏng hay clip đã xong)."""
        with self._guard:
            if self.closed or self.broken:
                return
            try:
                self._flush()
            except Exception:  # noqa: BLE001 - như [__call__]
                self.broken = True

    def _flush(self) -> None:
        if not any(self._held):
            return
        first = not self.started
        if first:
            self.started = True
            self.listener.started()
            self.listener.format(MIME)
        for pcm in self._held:
            if not pcm:
                continue
            self._sequence += 1
            data = flac_mp4.fragment(pcm, self._sent_samples, self._rate, self._sequence)
            self._sent.update(pcm)
            self._sent_samples += len(pcm) // 2
            self.listener.audio((flac_mp4.init_segment(self._rate) if first else b"") + data)
            first = False
        self._held = []
        duration = self._sent_samples * 1000 // self._rate
        shown = [[min(a, duration), min(b, duration)] for a, b in self._words[:len(self.toks)]]
        self.listener.words(shown + [[duration, duration]] * (len(self.toks) - len(shown)), duration, duration)

    def close(self, wav: bytes) -> None:
        """Clip cuối đã xong (`wav` = đúng các byte vào bộ đệm): tiếng đã phát luồng khác nó (bù độ to cả clip, khúc rỗng, lỗi giữa chừng) thì báo `replaced()`.
        Chưa phát gì (máy chậm, chờ tới hết): không làm gì - người nghe nhận clip như thường."""
        with self._guard:
            self.closed = True
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        if not self.started:
            return
        if self.broken or hashlib.sha1(wav[44:]).digest() != self._sent.digest():
            self.listener.replaced()

    def drop(self) -> None:
        """Lượt đọc hỏng / bị bỏ: thôi gửi (một [release] hẹn trước không còn ghi vào lời đáp lỗi)."""
        with self._guard:
            self.closed = True
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None


def _schedule(delay: float, task: Callable[[], None]) -> threading.Timer:
    timer = threading.Timer(delay, task)
    timer.daemon = True
    timer.start()
    return timer
