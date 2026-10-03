"""Giọng trực tuyến dùng khoá của chính người dùng ("Bring your own key", docs/LISTEN_ANYTHING.md mục 3): phần chung của các bộ nối.

Mỗi nhà cung cấp một file (azure.py, google.py, fpt.py, viettel.py), cùng một khuôn `KeyedProvider`: `voices()` (chỉ khi khoá đã kiểm tra
được), `synthesize(chữ, giọng)` (như mọi giọng: một đoạn -> MP3 + mảnh mốc), `check()` (một lần đọc thật nhỏ để biết khoá dùng được) và
`limits` (hạn mức để giao diện nói cho người dùng). Ta không trả tiền, không tạo tài khoản: khoá là của người dùng, chữ của sách đi tới nhà
cung cấp ấy và có thể bị tính tiền vào tài khoản của họ - giao diện nói rõ điều này.

Khoá chỉ đi trong header của chính nhà cung cấp, không bao giờ trong địa chỉ (URL / query) hay câu báo lỗi; không theo chuyển hướng HTTP (urllib
mặc định chép cả header sang máy chủ mới). Lỗi đổi thành `VoiceError` với lý do: "auth" (khoá sai / bị khoá), "quota" (hết hạn mức / gọi quá
dày), "offline", "timeout", "service", "rejected" - giao diện dựa vào đó để đọc tạm đoạn ấy bằng giọng kế (Edge, rồi giọng của máy).
"""
from __future__ import annotations

import socket
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from .keys import KeyStore
from .mapping import Boundary
from .model import Synthesis, Voice, VoiceError

TIMEOUT = 25.0
MAX_RESPONSE = 64 * 1024 * 1024
PROBE_TEXT = "Xin chào."  # lần "Kiểm tra": 9 ký tự, gần như không tốn hạn mức
USER_AGENT = "ABook-ReadAloud"


@dataclass(frozen=True)
class Limits:
    """`max_chars`: chữ mỗi lượt gọi (đoạn dài hơn cắt nhiều lượt); `free`: hạn mức miễn phí nói cho người dùng (nhà cung cấp có thể đổi);
    `timings`: "exact" (nhà cung cấp báo mốc từng chữ) hay "estimated" (chia theo âm tiết - spread.py); `region`: cần vùng (Azure)."""

    max_chars: int
    free: str
    timings: str
    region: bool = False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:  # 3xx thành HTTPError, không gửi khoá sang máy khác
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def request(method: str, url: str, headers: dict[str, str], body: bytes | None = None, *, name: str,
            timeout: float = TIMEOUT) -> tuple[int, bytes, dict[str, str]]:
    """Một lượt HTTP(S): (mã, thân, header chữ thường). Mã lỗi HTTP vẫn trả về (bộ nối tự đọc thân lỗi); mạng hỏng -> VoiceError."""
    prepared = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT, **headers}, method=method)
    try:
        with _OPENER.open(prepared, timeout=timeout) as response:
            return response.status, response.read(MAX_RESPONSE), {k.lower(): v for k, v in response.headers.items()}
    except urllib.error.HTTPError as error:
        try:
            data = error.read(MAX_RESPONSE)
        except OSError:
            data = b""
        return error.code, data, {k.lower(): v for k, v in (error.headers or {}).items()}
    except TimeoutError as error:
        raise VoiceError(f"{name} không trả lời (quá giờ).", "timeout") from error
    except urllib.error.URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):  # quá giờ lúc NỐI (như edge.py): coi như không có mạng
            raise VoiceError(f"Không kết nối được tới {name} (quá giờ).", "offline") from error
        raise VoiceError(f"Không có mạng để dùng giọng {name}.", "offline") from error
    except OSError as error:
        raise VoiceError(f"Không có mạng để dùng giọng {name}.", "offline") from error


def failure(status: int, name: str, detail: str = "") -> VoiceError:
    """Mã HTTP lỗi -> lỗi có lý do. `detail`: câu ngắn của nhà cung cấp (không bao giờ chứa khoá - ta không gửi khoá trong thân)."""
    tail = f" ({detail[:200]})" if detail else ""
    if status in (401, 403):
        return VoiceError(f"{name} từ chối khoá của bạn - kiểm tra lại khoá trong Cài đặt{tail}.", "auth")
    if status in (402, 429):
        return VoiceError(f"Khoá {name} đã hết hạn mức hoặc gọi quá dày{tail}.", "quota")
    if status >= 500:
        return VoiceError(f"{name} đang trục trặc (HTTP {status}){tail}.", "service")
    return VoiceError(f"{name} không nhận yêu cầu (HTTP {status}){tail}.", "rejected")


def estimated_synthesis(text: str, max_chars: int, speak: Callable[[str], bytes], name: str) -> Synthesis:
    """Đọc bằng một giọng không báo mốc (FPT.AI, Viettel AI): cắt `text` thành mảnh <= `max_chars` ký tự, `speak(mảnh)` -> MP3, nối lại; mỗi
    mảnh tự chia thời gian thật của nó (mp3.duration_ms) theo âm tiết (spread.py), mốc cộng dồn và vị trí ký tự tính theo chữ gốc."""
    from . import edge, mp3, spread

    audio = bytearray()
    boundaries: list[Boundary] = []
    offset = 0
    cleaned = edge.clean(text)
    cursor = 0
    for piece in edge.split_text(cleaned, max_chars, len):
        data = speak(piece)
        length = mp3.duration_ms(data)
        start = cleaned.find(piece, cursor)  # các mảnh nối nhau theo thứ tự trong chữ gốc
        cursor = start + len(piece) if start >= 0 else cursor
        for found in spread.boundaries(piece, length):
            char = found.char + start if start >= 0 and found.char is not None else None
            boundaries.append(Boundary(found.text, found.start_ms + offset, found.end_ms + offset, char))
        audio += data
        offset += length
    if not audio:
        raise VoiceError(f"{name} không trả về âm thanh.", "service")
    return Synthesis(bytes(audio), boundaries, offset)


class KeyedProvider:
    """Khuôn chung. Lớp con đặt `id`, `name`, `limits` và viết `_voices(entry)` (-> [[mã, tên], ...] giọng vi-VN) và
    `_synthesize(entry, chữ, mã giọng)`; `entry` là mục trong KeyStore (`key`, `region`...). Mỗi giọng là [mã, tên, giới] với giới
    "female" / "male" / ""."""

    id = ""
    name = ""
    limits = Limits(0, "", "estimated")
    keyed = True

    def __init__(self, keys: KeyStore) -> None:
        self.keys = keys

    def _voices(self, entry: dict[str, Any]) -> list[list[str]]:
        raise NotImplementedError

    @staticmethod
    def gender(value: object) -> str:
        text = str(value or "").strip().lower()
        return "female" if text in ("female", "nữ") else "male" if text in ("male", "nam") else ""

    def _synthesize(self, entry: dict[str, Any], text: str, native_voice: str) -> Synthesis:
        raise NotImplementedError

    def voices(self) -> list[Voice]:
        entry = self.keys.get(self.id)
        if not entry.get("key") or not entry.get("valid"):
            return []
        return [Voice(f"{self.id}:{item[0]}", f"{item[1]} ({self.name})", self.id, True, gender=item[2] if len(item) > 2 else "")
                for item in entry.get("voices") or [] if isinstance(item, list) and len(item) >= 2]

    def synthesize(self, text: str, native_voice: str) -> Synthesis:
        entry = self.keys.get(self.id)
        if not entry.get("key"):
            raise VoiceError(f"Chưa có khoá {self.name}.", "auth")
        try:
            return self._synthesize(entry, text, native_voice)
        except VoiceError as error:
            if error.reason == "auth":
                self.keys.mark(self.id, False)  # khoá bị thu hồi / sai: giọng thôi hiện cho tới lần kiểm tra lại
            raise

    def check(self) -> dict[str, Any]:
        """"Kiểm tra" trong Cài đặt: lấy danh sách giọng tiếng Việt rồi đọc thử một câu thật ngắn. Lỗi khoá / hạn mức / không có giọng thì
        đánh dấu khoá chưa dùng được; lỗi mạng thì giữ nguyên trạng thái cũ."""
        entry = self.keys.get(self.id)
        if not entry.get("key"):
            return {"ok": False, "reason": "auth", "message": "Chưa nhập khoá."}
        try:
            voices = self._voices(entry)
            if not voices:
                raise VoiceError(f"Tài khoản {self.name} này không có giọng tiếng Việt.", "voice")
            self._synthesize(entry, PROBE_TEXT, voices[0][0])
        except VoiceError as error:
            if error.reason in ("auth", "quota", "voice", "rejected"):
                self.keys.mark(self.id, False)
            return {"ok": False, "reason": error.reason, "message": str(error)}
        self.keys.mark(self.id, True, voices)
        return {"ok": True, "voices": len(voices)}

    def describe(self) -> dict[str, Any]:
        """Cho Cài đặt: tên, hạn mức, trạng thái khoá (bản che)."""
        return {"id": self.id, "name": self.name, "limits": asdict(self.limits), **self.keys.public(self.id)}
