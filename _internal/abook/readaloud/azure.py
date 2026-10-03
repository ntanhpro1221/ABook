"""Azure Speech (khoá + vùng của người dùng): nhà chính thức của đúng các giọng thần kinh mà Edge đọc to, nên là chỗ dựa tự nhiên nếu dịch vụ
của Edge đóng.

- Danh sách giọng: REST `GET https://<vùng>.tts.speech.microsoft.com/cognitiveservices/voices/list`, header `Ocp-Apim-Subscription-Key`
  (https://learn.microsoft.com/azure/ai-services/speech-service/rest-text-to-speech#get-a-list-of-voices), lọc `Locale == "vi-VN"`.
- Đọc: REST `cognitiveservices/v1` KHÔNG trả mốc từng chữ (mốc chỉ có qua Speech SDK - cùng trang trên, mục "Tip"). SDK nói WebSocket
  `wss://<vùng>.tts.speech.microsoft.com/tts/cognitiveservices/websocket/v1` với header `Ocp-Apim-Subscription-Key` + `X-ConnectionId`, rồi
  gửi `speech.config`, `synthesis.context` (bật `wordBoundaryEnabled`, chọn `outputFormat`) và `ssml`; nhận `audio` nhị phân + `audio.metadata`
  (WordBoundary, tick 100 ns) tới `turn.end` - đúng khung tin của dịch vụ Edge, nên dùng lại `websocket.py` và `edge.read_turn`. Nguồn: SDK mã mở
  của Microsoft, https://github.com/microsoft/cognitive-services-speech-sdk-js (src/common.speech/SpeechSynthesisConnectionFactory.ts,
  SynthesisAdapterBase.ts, SynthesisContext.ts, SpeechServiceConfig.ts, HeaderNames.ts; đọc 03-10).
- Mã lỗi (trang REST ở trên): 401 khoá sai / sai vùng, 429 hết hạn mức hay gọi quá dày. Bậc miễn phí F0: 0,5 triệu ký tự / tháng (giọng thần kinh).
"""
from __future__ import annotations

import json
import re
import socket
import ssl
import time
import uuid
from typing import Any

from . import byok, edge, websocket
from .byok import Limits
from .mapping import Boundary
from .model import Synthesis, VoiceError

HOST = "{region}.tts.speech.microsoft.com"
WS_PATH = "/tts/cognitiveservices/websocket/v1"
VOICES_PATH = "/cognitiveservices/voices/list"
OUTPUT_FORMAT = "audio-24khz-48kbitrate-mono-mp3"  # CBR 48 kbps như Edge: byte -> thời gian chính xác
BITRATE_BPS = 48_000
REGION = re.compile(r"^[a-z0-9]{2,40}$")
TOTAL_TIMEOUT = 90.0
NAME = "Azure Speech"


def valid_region(region: str) -> bool:
    return bool(REGION.match(region or ""))


def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())


def message(path: str, request_id: str, content_type: str, body: str) -> str:
    return f"Path:{path}\r\nX-RequestId:{request_id}\r\nX-Timestamp:{_timestamp()}\r\nContent-Type:{content_type}\r\n\r\n{body}"


def speech_config() -> str:
    return json.dumps({"context": {"system": {"name": "SpeechSDK", "version": "1.44.0", "build": "Python", "lang": "Python"},
                                   "os": {"platform": "ABook", "name": "ABook", "version": "1"}}})


def synthesis_context() -> str:
    return json.dumps({"synthesis": {"audio": {"metadataOptions": {"bookmarkEnabled": False, "punctuationBoundaryEnabled": "false",
                                                                   "sentenceBoundaryEnabled": "false", "sessionEndEnabled": True,
                                                                   "visemeEnabled": False, "wordBoundaryEnabled": "true"},
                                               "outputFormat": OUTPUT_FORMAT},
                                     "language": {"autoDetection": False}}})


def ssml(voice: str, text: str) -> str:
    from xml.sax.saxutils import escape

    return (f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='vi-VN'><voice name='{escape(voice, {chr(39): '&apos;'})}'>"
            f"{escape(edge.clean(text))}</voice></speak>")


def _closed(error: websocket.Closed) -> VoiceError | None:
    """Azure đóng kết nối kèm lý do khi hết hạn mức / khoá hỏng giữa lượt (mã 1007/1008/1011 + chữ)."""
    reason = (error.reason or "").lower()
    if "quota" in reason or "429" in reason or "throttl" in reason or "exceed" in reason:
        return VoiceError(f"Khoá {NAME} đã hết hạn mức hoặc gọi quá dày.", "quota")
    if "auth" in reason or "401" in reason or "subscription" in reason:
        return VoiceError(f"{NAME} từ chối khoá của bạn - kiểm tra lại khoá trong Cài đặt.", "auth")
    if error.code in (1007, 1008) and reason:
        return VoiceError(f"{NAME} không nhận yêu cầu: {error.reason[:200]}", "rejected")
    return None


class AzureProvider(byok.KeyedProvider):
    id = "azure"
    name = NAME
    limits = Limits(max_chars=3000, free="Bậc miễn phí F0: 500.000 ký tự mỗi tháng", timings="exact", region=True)

    def __init__(self, keys: Any, *, host: str | None = None, port: int = 443, secure: bool = True,
                 connect_timeout: float = 10.0, read_timeout: float = 25.0) -> None:
        super().__init__(keys)
        self.host = host  # bài thử: máy chủ giả trên máy này (mặc định theo vùng)
        self.port = port
        self.secure = secure
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout

    def _host(self, entry: dict[str, Any]) -> str:
        region = str(entry.get("region") or "")
        if not valid_region(region):
            raise VoiceError(f"Vùng {NAME} chưa đúng (ví dụ: southeastasia).", "auth")
        return self.host or HOST.format(region=region)

    def _voices(self, entry: dict[str, Any]) -> list[list[str]]:
        host = self._host(entry)
        scheme = "https" if self.secure else "http"
        port = "" if (self.secure and self.port == 443) or (not self.secure and self.port == 80) else f":{self.port}"
        status, body, _ = byok.request("GET", f"{scheme}://{host}{port}{VOICES_PATH}", {"Ocp-Apim-Subscription-Key": entry["key"]}, name=NAME)
        if status != 200:
            raise byok.failure(status, NAME)
        try:
            listed = json.loads(body)
        except ValueError as error:
            raise VoiceError(f"{NAME} trả danh sách giọng hỏng.", "service") from error
        return [[str(item["ShortName"]), str(item.get("LocalName") or item.get("DisplayName") or item["ShortName"]), self.gender(item.get("Gender"))]
                for item in listed if isinstance(item, dict) and item.get("Locale") == "vi-VN" and item.get("ShortName")]

    def _connect(self, entry: dict[str, Any]) -> websocket.Connection:
        host = self._host(entry)
        headers = {"Ocp-Apim-Subscription-Key": entry["key"], "X-ConnectionId": uuid.uuid4().hex}
        try:
            return websocket.connect(host, self.port, WS_PATH, headers, secure=self.secure, timeout=self.connect_timeout,
                                     read_timeout=self.read_timeout)
        except websocket.Rejected as rejected:
            raise byok.failure(rejected.status, NAME) from rejected
        except TimeoutError as error:
            raise VoiceError(f"Không kết nối được tới {NAME} (quá giờ).", "offline") from error
        except ssl.SSLError as error:
            raise VoiceError(f"Không bắt tay TLS được với {NAME}: {error}", "service") from error
        except websocket.WebSocketError as error:
            raise VoiceError(f"{NAME} trả lời lạ: {error}", "service") from error
        except (socket.gaierror, OSError) as error:
            raise VoiceError(f"Không có mạng để dùng giọng {NAME}.", "offline") from error

    def _synthesize(self, entry: dict[str, Any], text: str, native_voice: str) -> Synthesis:
        deadline = time.monotonic() + TOTAL_TIMEOUT
        audio = bytearray()
        boundaries: list[Boundary] = []
        for piece in edge.split_text(edge.clean(text), self.limits.max_chars, len):
            compensation = len(audio) * 8 * 10_000_000 // BITRATE_BPS  # mốc mỗi lượt tính từ đầu lượt ấy
            connection = self._connect(entry)
            try:
                request_id = uuid.uuid4().hex
                connection.send_text(message("speech.config", request_id, "application/json", speech_config()))
                connection.send_text(message("synthesis.context", request_id, "application/json", synthesis_context()))
                connection.send_text(message("ssml", request_id, "application/ssml+xml", ssml(native_voice, piece)))
                data, found = edge.read_turn(connection, compensation, deadline, label=NAME, strict=False, on_close=_closed)
            except edge.EdgeError as error:
                raise VoiceError(str(error), error.reason) from error
            finally:
                connection.close()
            audio += data
            boundaries += found
        if not audio:
            raise VoiceError(f"{NAME} không trả về âm thanh.", "service")
        duration = len(audio) * 8 * 1000 // BITRATE_BPS
        return Synthesis(bytes(audio), boundaries, max(duration, boundaries[-1].end_ms if boundaries else 0))
