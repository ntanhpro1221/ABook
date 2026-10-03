"""Google Cloud Text-to-Speech (khoá API của người dùng): giọng vi-VN Standard / WaveNet / Neural2, mốc từng chữ chính xác nhờ `<mark>`.

- Khoá đi trong header `X-goog-api-key` (https://cloud.google.com/docs/authentication/api-keys-use), không bao giờ trong `?key=`.
- Danh sách giọng: `GET https://texttospeech.googleapis.com/v1/voices?languageCode=vi-VN` -> `voices[].name`
  (https://cloud.google.com/text-to-speech/docs/reference/rest/v1/voices/list). Chỉ giữ Standard / Wavenet / Neural2: các họ mới (Chirp)
  không nhận SSML nên không có `<mark>`.
- Đọc: `POST https://texttospeech.googleapis.com/v1beta1/text:synthesize` với `input.ssml`, `voice{languageCode, name}`,
  `audioConfig.audioEncoding = MP3`, `enableTimePointing = ["SSML_MARK"]` -> `audioContent` (base64) + `timepoints[{markName, timeSeconds}]`
  (https://cloud.google.com/text-to-speech/docs/reference/rest/v1beta1/text/synthesize). Mỗi chữ hiện một `<mark name="i"/>` đặt ngay trước nó,
  thêm một mark cuối: chữ i chạy từ mốc i tới mốc kế.
- Giới hạn: 5000 byte `input` mỗi lượt (https://cloud.google.com/text-to-speech/quotas) -> cắt theo chữ, cộng dồn độ dài MP3 thật (mp3.py).
  Miễn phí mỗi tháng: 4 triệu ký tự Standard, 1 triệu WaveNet / Neural2 (https://cloud.google.com/text-to-speech/pricing). Lỗi: 400
  `API_KEY_INVALID` / 403 `PERMISSION_DENIED` = khoá; 429 `RESOURCE_EXHAUSTED` = hạn mức.
"""
from __future__ import annotations

import base64
import json
import re
from typing import Any
from xml.sax.saxutils import escape

from . import byok, edge, mp3
from .byok import Limits
from .mapping import Boundary
from .model import Synthesis, VoiceError

BASE = "https://texttospeech.googleapis.com"
MAX_SSML_BYTES = 4800  # dưới trần 5000 byte của Google, chừa chỗ cho thẻ bọc
FAMILIES = re.compile(r"-(Standard|Wavenet|Neural2)-", re.IGNORECASE)
NAME = "Google Cloud"
_TOKEN = re.compile(r"\S+")


def _family_label(name: str) -> str:
    match = FAMILIES.search(name)
    family = {"standard": "Standard", "wavenet": "WaveNet", "neural2": "Neural2"}[match.group(1).lower()] if match else ""
    return f"{family} {name.rsplit('-', 1)[-1]}".strip()


def chunks(text: str) -> list[list[tuple[int, str]]]:
    """Các chữ hiện (vị trí, chữ) chia thành nhóm mà SSML của nhóm (mỗi chữ một mark) không quá MAX_SSML_BYTES. Chữ một mình đã quá dài
    (không dấu cách) thì cắt thành mảnh 1000 ký tự cùng vị trí bắt đầu khác nhau."""
    pieces: list[tuple[int, str]] = []
    for match in _TOKEN.finditer(edge.clean(text)):
        word = match.group()
        for at in range(0, len(word), 1000):
            pieces.append((match.start() + at, word[at:at + 1000]))
    groups: list[list[tuple[int, str]]] = []
    size = 0
    for piece in pieces:
        cost = len(escape(piece[1]).encode("utf-8")) + 22  # '<mark name="9999"/>' + dấu cách
        if not groups or size + cost > MAX_SSML_BYTES - 64:  # 64: <speak>, mark cuối
            groups.append([])
            size = 0
        groups[-1].append(piece)
        size += cost
    return groups


def build_ssml(group: list[tuple[int, str]]) -> str:
    body = "".join(f'<mark name="{index}"/>{escape(word)} ' for index, (_, word) in enumerate(group))
    return f'<speak>{body}<mark name="end"/></speak>'


class GoogleProvider(byok.KeyedProvider):
    id = "google"
    name = NAME
    limits = Limits(max_chars=4000, free="Miễn phí mỗi tháng: 4 triệu ký tự giọng Standard, 1 triệu WaveNet / Neural2", timings="exact")

    def __init__(self, keys: Any, *, base: str = BASE) -> None:
        super().__init__(keys)
        self.base = base.rstrip("/")

    @staticmethod
    def _error(status: int, body: bytes) -> VoiceError:
        try:
            error = json.loads(body).get("error", {})
        except (ValueError, AttributeError):
            error = {}
        detail = str(error.get("message", ""))[:200] if isinstance(error, dict) else ""
        state = str(error.get("status", "")) if isinstance(error, dict) else ""
        if status == 400 and ("API_KEY_INVALID" in body.decode("utf-8", "replace") or "API key not valid" in detail):
            return byok.failure(401, NAME, detail)
        if state == "RESOURCE_EXHAUSTED":
            return byok.failure(429, NAME, detail)
        return byok.failure(status, NAME, detail)

    def _voices(self, entry: dict[str, Any]) -> list[list[str]]:
        status, body, _ = byok.request("GET", f"{self.base}/v1/voices?languageCode=vi-VN", {"X-goog-api-key": entry["key"]}, name=NAME)
        if status != 200:
            raise self._error(status, body)
        try:
            listed = json.loads(body).get("voices", [])
        except (ValueError, AttributeError) as error:
            raise VoiceError(f"{NAME} trả danh sách giọng hỏng.", "service") from error
        found = sorted((str(item["name"]), self.gender(item.get("ssmlGender"))) for item in listed
                       if isinstance(item, dict) and "vi-VN" in (item.get("languageCodes") or []) and FAMILIES.search(str(item.get("name", ""))))
        return [[name, _family_label(name), gender] for name, gender in found]

    def _synthesize(self, entry: dict[str, Any], text: str, native_voice: str) -> Synthesis:
        audio = bytearray()
        boundaries: list[Boundary] = []
        offset = 0
        for group in chunks(text):
            payload = {"input": {"ssml": build_ssml(group)}, "voice": {"languageCode": "vi-VN", "name": native_voice},
                       "audioConfig": {"audioEncoding": "MP3"}, "enableTimePointing": ["SSML_MARK"]}
            status, body, _ = byok.request("POST", f"{self.base}/v1beta1/text:synthesize",
                                           {"X-goog-api-key": entry["key"], "Content-Type": "application/json; charset=utf-8"},
                                           json.dumps(payload).encode("utf-8"), name=NAME)
            if status != 200:
                raise self._error(status, body)
            try:
                answer = json.loads(body)
                data = base64.b64decode(answer["audioContent"])
                marks = {str(point["markName"]): round(float(point["timeSeconds"]) * 1000) for point in answer.get("timepoints", [])}
            except (ValueError, KeyError, TypeError) as error:
                raise VoiceError(f"{NAME} trả lời hỏng.", "service") from error
            length = mp3.duration_ms(data)
            end_mark = marks.get("end", length)
            for index, (char, word) in enumerate(group):
                if str(index) not in marks:
                    continue
                start = marks[str(index)]
                stop = marks.get(str(index + 1), end_mark)
                boundaries.append(Boundary(word, offset + start, offset + max(start, stop), char))
            audio += data
            offset += length
        if not audio:
            raise VoiceError(f"{NAME} không trả về âm thanh.", "service")
        return Synthesis(bytes(audio), boundaries, offset)
