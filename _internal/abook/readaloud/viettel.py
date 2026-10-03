"""Viettel AI TTS (token của người dùng; 50.000 ký tự miễn phí trong tháng đầu), giọng ba miền.

Viettel không công bố tài liệu tĩnh (trang https://viettelai.vn/tai-lieu là ứng dụng web); định dạng dưới đây đọc từ chính trang ấy và trang
thử giọng của viettelai.vn (03-10):
- `POST https://viettelai.vn/tts/speech_synthesis`, JSON `{"text", "voice", "speed": 1.0, "tts_return_option": 3 (mp3), "token",
  "without_filter": false}`; trang thử giọng gửi token trong header `token`, bảng điều khiển gửi trong thân `token` - ở đây gửi cả hai, cùng
  một máy chủ, không bao giờ trong địa chỉ. Trả thẳng MP3; lỗi là JSON có `vi_message` / `en_message`; 429 = hết lượt dùng thử / hạn mức.
- Danh sách giọng: `GET https://viettelai.vn/tts/voices` -> `[{name, description, code, location}]`.
- Không có mốc từng chữ: chia theo âm tiết (spread.py).
"""
from __future__ import annotations

import json
from typing import Any

from . import byok
from .byok import Limits
from .model import Synthesis, VoiceError

BASE = "https://viettelai.vn"
NAME = "Viettel AI"
MAX_CHARS = 2000  # trang của Viettel cắt văn bản dài thành nhiều lượt; giữ mỗi lượt vừa phải


def _detail(body: bytes) -> str:
    try:
        answer = json.loads(body)
    except ValueError:
        return ""
    if not isinstance(answer, dict):
        return ""
    return str(answer.get("vi_message") or answer.get("en_message") or answer.get("message") or "")[:200]


class ViettelProvider(byok.KeyedProvider):
    id = "viettel"
    speaks_english = True  # chưa đo: giữ cách đọc cũ tới khi đo
    name = NAME
    limits = Limits(max_chars=MAX_CHARS, free="Miễn phí 50.000 ký tự trong tháng đầu", timings="estimated")

    def __init__(self, keys: Any, *, base: str = BASE) -> None:
        super().__init__(keys)
        self.base = base.rstrip("/")

    def _voices(self, entry: dict[str, Any]) -> list[list[str]]:
        status, body, _ = byok.request("GET", f"{self.base}/tts/voices", {"token": entry["key"]}, name=NAME)
        if status != 200:
            raise byok.failure(status, NAME, _detail(body))
        try:
            listed = json.loads(body)
        except ValueError as error:
            raise VoiceError(f"{NAME} trả danh sách giọng hỏng.", "service") from error
        voices = []
        for item in listed if isinstance(listed, list) else []:
            if isinstance(item, dict) and item.get("code"):
                label = str(item.get("name") or item["code"]).replace(" chất lượng cao", "")
                described = str(item.get("description") or "").split()  # "Nữ miền Bắc"
                region = " ".join(described[1:])
                voices.append([str(item["code"]), f"{label} - {region}" if region else label,
                               self.gender(described[0] if described else "")])
        return voices

    def _synthesize(self, entry: dict[str, Any], text: str, native_voice: str) -> Synthesis:
        def speak(piece: str) -> bytes:
            payload = {"text": piece, "voice": native_voice, "speed": 1.0, "tts_return_option": 3, "token": entry["key"], "without_filter": False}
            status, body, headers = byok.request("POST", f"{self.base}/tts/speech_synthesis",
                                                 {"token": entry["key"], "Content-Type": "application/json"},
                                                 json.dumps(payload).encode("utf-8"), name=NAME)
            if status != 200:
                raise byok.failure(status, NAME, _detail(body))
            if "json" in headers.get("content-type", ""):
                raise VoiceError(f"{NAME} không đọc được đoạn này ({_detail(body) or 'không rõ lý do'}).", "service")
            return body

        return byok.estimated_synthesis(text, MAX_CHARS, speak, NAME)
