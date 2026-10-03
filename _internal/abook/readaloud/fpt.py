"""FPT.AI Text to Speech (khoá API của người dùng; 100.000 ký tự miễn phí mỗi tháng), 7 giọng vùng miền.

Theo tài liệu chính thức https://docs.fpt.ai/docs/en/speech/api/text-to-speech/ (đọc 03-10):
- `POST https://api.fpt.ai/hmi/tts/v5`, thân là chữ thuần UTF-8 (3-5000 ký tự), header `api_key` (khoá), `voice` (banmai, lannhi, leminh,
  myan, thuminh, giahuy, linhsan), `speed` (-3..3, 0 = thường), `format` (mp3 | wav).
- Trả JSON `{"async": <link mp3>, "error": 0, "message": ..., "request_id": ...}`: file chưa có ngay ("5 giây tới 2 phút tuỳ độ dài") -> hỏi
  lại link ấy tới khi có (link không kèm khoá). `error` khác 0 là lỗi.
- Không có mốc từng chữ: chia theo âm tiết (spread.py).
"""
from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import urlsplit

from . import byok
from .byok import Limits
from .model import Synthesis, VoiceError

URL = "https://api.fpt.ai/hmi/tts/v5"
KEY_HEADER = "api_key"  # đúng chính tả trong tài liệu (gạch dưới)
NAME = "FPT.AI"
MAX_CHARS = 4500  # trần 5000 ký tự mỗi lượt
POLL_SECONDS = 1.0
POLL_LIMIT = 120.0  # "tới 2 phút"
VOICES = [["banmai", "Ban Mai - miền Bắc", "female"], ["thuminh", "Thu Minh - miền Bắc", "female"], ["leminh", "Lê Minh - miền Bắc", "male"],
          ["myan", "Mỹ An - miền Trung", "female"], ["giahuy", "Gia Huy - miền Trung", "male"], ["lannhi", "Lan Nhi - miền Nam", "female"],
          ["linhsan", "Linh San - miền Nam", "female"]]
_QUOTA_WORDS = ("quota", "limit", "exceed", "credit", "balance", "hết", "vượt", "hạn mức")


class FptProvider(byok.KeyedProvider):
    id = "fpt"
    speaks_english = True  # chưa đo: giữ cách đọc cũ tới khi đo
    name = NAME
    limits = Limits(max_chars=MAX_CHARS, free="Miễn phí 100.000 ký tự mỗi tháng", timings="estimated")

    def __init__(self, keys: Any, *, url: str = URL, poll_seconds: float = POLL_SECONDS, poll_limit: float = POLL_LIMIT) -> None:
        super().__init__(keys)
        self.url = url
        self.poll_seconds = poll_seconds
        self.poll_limit = poll_limit

    def _voices(self, entry: dict[str, Any]) -> list[list[str]]:
        return [list(voice) for voice in VOICES]  # danh sách cố định của tài liệu; khoá được kiểm bằng lần đọc thử

    def _ask(self, key: str, voice: str, text: str) -> str:
        """Gửi chữ, trả link file sẽ có."""
        status, body, _ = byok.request("POST", self.url, {KEY_HEADER: key, "voice": voice, "speed": "0", "format": "mp3",
                                                          "Content-Type": "text/plain; charset=utf-8"}, text.encode("utf-8"), name=NAME)
        try:
            answer = json.loads(body)
        except ValueError:
            answer = {}
        detail = str(answer.get("message", "")) if isinstance(answer, dict) else ""
        if status != 200:
            raise byok.failure(status, NAME, detail)
        if not isinstance(answer, dict) or answer.get("error") not in (0, "0") or not answer.get("async"):
            if any(word in detail.lower() for word in _QUOTA_WORDS):
                raise byok.failure(429, NAME, detail)
            raise VoiceError(f"{NAME} không đọc được đoạn này ({detail[:200] or 'không rõ lý do'}).", "service")
        link = str(answer["async"])
        if urlsplit(link).scheme not in ("https", "http"):
            raise VoiceError(f"{NAME} trả link lạ.", "service")
        return link

    def _fetch(self, link: str) -> bytes:
        """Hỏi lại link tới khi file có (máy chủ trả 404 / 403 khi chưa xong)."""
        deadline = time.monotonic() + self.poll_limit
        while True:
            status, body, headers = byok.request("GET", link, {}, name=NAME)
            if status == 200 and body and "json" not in headers.get("content-type", ""):
                return body
            if status not in (200, 202, 403, 404) or time.monotonic() > deadline:
                raise VoiceError(f"{NAME} chưa làm xong file âm thanh.", "timeout" if status in (200, 202, 403, 404) else "service")
            time.sleep(self.poll_seconds)

    def _synthesize(self, entry: dict[str, Any], text: str, native_voice: str) -> Synthesis:
        def speak(piece: str) -> bytes:
            sent = piece if len(piece) >= 3 else piece + "..."  # FPT nhận tối thiểu 3 ký tự
            return self._fetch(self._ask(entry["key"], native_voice, sent))

        return byok.estimated_synthesis(text, MAX_CHARS, speak, NAME)
