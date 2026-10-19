"""Kiểu dùng chung của các nhà cung cấp giọng đọc."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Callable, Iterator

from .mapping import Boundary


@dataclass
class Synthesis:
    """Kết quả một lần đọc: file audio + các mảnh nhà cung cấp báo (chưa nối vào chữ hiện - `mapping.map_boundaries`) + độ dài.
    `words`: nhà cung cấp tự tính sẵn mốc từng chữ hiện (VieNeu căn chữ vào audio của chính nó) thì dùng thẳng, bỏ qua `boundaries`."""

    audio: bytes
    boundaries: list[Boundary]
    duration_ms: int
    ext: str = "mp3"
    mime: str = "audio/mpeg"
    words: list[list[int]] | None = None


@dataclass(frozen=True)
class Voice:
    """Một giọng. `id` có tiền tố nhà cung cấp ("edge:vi-VN-HoaiMyNeural", "device:<mã Windows>"); `online`: gửi chữ ra ngoài máy;
    `gender`: "female" / "male" / "" (không rõ) - gợi ý trong Cài đặt."""

    id: str
    name: str
    provider: str
    online: bool
    default: bool = False
    language: str = "vi-VN"
    gender: str = ""


class VoiceError(Exception):
    """Lỗi của một giọng. `reason`: "offline", "timeout", "rejected", "service", "voice" (giọng không có), "empty" (chữ không đọc được);
    giọng dùng khoá của người dùng (byok.py) thêm "auth" (khoá sai / bị khoá / chưa có) và "quota" (hết hạn mức của tài khoản)."""

    reason = "service"

    def __init__(self, message: str, reason: str | None = None) -> None:
        super().__init__(message)
        if reason is not None:
            self.reason = reason


# Lượt đọc trên máy đang chạy mà không ai cần nữa (người nghe nhảy đi chỗ khác, Huỷ xuất sách nói): `ReadAloud.clip` đặt cờ của lượt ấy ở đây quanh lời
# gọi giọng, engine (vieneu_engine, supertonic) hỏi `stop_if_cancelled()` giữa các khúc và giữa các bước - không phải truyền qua readaloud/vieneu.py
# (file khoá). Mỗi luồng một giá trị (ContextVar), nên lượt đọc của luồng khác không bị ảnh hưởng.
_cancelled: ContextVar[Callable[[], bool] | None] = ContextVar("readaloud_cancelled", default=None)


@contextmanager
def cancellable(cancelled: Callable[[], bool] | None) -> Iterator[None]:
    """Trong khối này, `stop_if_cancelled()` ném VoiceError "cancelled" khi `cancelled()` đúng (None = không bao giờ)."""
    token = _cancelled.set(cancelled)
    try:
        yield
    finally:
        _cancelled.reset(token)


def stop_if_cancelled() -> None:
    """Engine gọi giữa các khúc / bước: lượt đọc này đã bị bỏ thì dừng ngay, không gì vào bộ đệm."""
    check = _cancelled.get()
    if check is not None and check():
        raise VoiceError("Đã bỏ lượt đọc này.", "cancelled")


# Phát luồng giọng trên máy (local_stream.py): `ReadAloud.clip` đặt người nghe từng khúc ở đây quanh lời gọi giọng, rồi mỗi khúc vừa đọc xong - đúng sóng âm
# sẽ được ghép vào clip - được báo cho nó (`unit_made`). VieNeu báo từ engine bọc (local_stream.reporting: vieneu._speak là file khoá), Supertonic từ chính
# `_speak`. Không có người nghe (mọi lượt khác: làm trước, xuất, tự đo) thì không làm gì. Mỗi luồng một giá trị như `_cancelled`.
_units: ContextVar[Callable[[object, int, str, float], None] | None] = ContextVar("readaloud_units", default=None)


@contextmanager
def hearing(listener: Callable[[object, int, str, float], None] | None) -> Iterator[None]:
    """Trong khối này, `unit_made(sóng, tần số mẫu, chữ đem đọc, giây máy làm)` tới `listener` (None = không ai nghe)."""
    token = _units.set(listener)
    try:
        yield
    finally:
        _units.reset(token)


def listening() -> bool:
    return _units.get() is not None


def unit_made(wave: object, rate: int, said: str, seconds: float) -> None:
    """Một khúc vừa đọc xong: `wave` = sóng âm đúng như sẽ ghép vào clip (`rate` mẫu mỗi giây), `said` = âm vị / chữ đem đọc (khoảng nghỉ sau nó - vieneu_engine.gap_after),
    `seconds` = thời gian máy làm khúc ấy."""
    listener = _units.get()
    if listener is not None:
        listener(wave, rate, said, seconds)
