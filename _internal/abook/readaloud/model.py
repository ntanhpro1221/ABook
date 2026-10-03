"""Kiểu dùng chung của các nhà cung cấp giọng đọc."""
from __future__ import annotations

from dataclasses import dataclass

from .mapping import Boundary


@dataclass
class Synthesis:
    """Kết quả một lần đọc: file audio + các mảnh nhà cung cấp báo (chưa nối vào chữ hiện - `mapping.map_boundaries`) + độ dài."""

    audio: bytes
    boundaries: list[Boundary]
    duration_ms: int
    ext: str = "mp3"
    mime: str = "audio/mpeg"


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
