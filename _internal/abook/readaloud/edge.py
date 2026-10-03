"""Giọng trực tuyến: dịch vụ đọc to của Microsoft Edge (giọng thần kinh vi-VN HoaiMy, NamMinh), nói chuyện bằng WebSocket thuần thư viện chuẩn.

Giao thức theo dự án mã nguồn mở `edge-tts` (rany2/edge-tts 7.2.8, LGPL-3.0; ở đây viết lại từ đặc tả giao thức, không chép mã): một kết nối
mỗi đoạn <= 4096 byte chữ; gửi `speech.config` (bật WordBoundary, MP3 24 kHz 48 kbps đơn kênh) rồi một SSML; nhận khung nhị phân (đầu 2 byte
độ dài header + header + MP3) và khung văn bản `audio.metadata` (WordBoundary: Offset / Duration tính bằng tick 100 ns) tới `turn.end`.
Dịch vụ không chính thức: có thể đổi mã/chữ ký bất cứ lúc nào (hằng số bên dưới là điểm sửa duy nhất); lỗi nói rõ lý do để giao diện đổi
sang giọng máy. Mạng không có -> `EdgeOffline` (reason "offline").
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import socket
import ssl
import time
import uuid
from email.utils import parsedate_to_datetime
from urllib.parse import quote
from xml.sax.saxutils import escape, unescape

from . import websocket
from .mapping import Boundary
from .model import Synthesis, VoiceError

HOST = "speech.platform.bing.com"
PATH = "/consumer/speech/synthesize/readaloud/edge/v1"
TRUSTED_CLIENT_TOKEN = "6A5AA1D4EAFF4E9FB37E23D68491D6F4"
CHROMIUM_FULL_VERSION = "143.0.3650.75"
SEC_MS_GEC_VERSION = f"1-{CHROMIUM_FULL_VERSION}"
OUTPUT_FORMAT = "audio-24khz-48kbitrate-mono-mp3"
BITRATE_BPS = 48_000  # CBR: byte -> thời gian chính xác, dùng để cộng dồn mốc giữa các đoạn và đo độ dài clip
TICKS_PER_MS = 10_000
MAX_CHUNK_BYTES = 4000  # dịch vụ nhận <= 4096 byte chữ đã escape mỗi SSML
CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 25.0
TOTAL_TIMEOUT = 90.0
RETRIES = 2  # lượt bị cắt giữa chừng thử lại tối đa chừng này lần (kết nối mới)

DEFAULT_VOICE = "vi-VN-HoaiMyNeural"
VOICES = [("vi-VN-HoaiMyNeural", "Hoài My"), ("vi-VN-NamMinhNeural", "Nam Minh")]


class EdgeError(VoiceError):
    """Lỗi của dịch vụ. `reason`: "offline" (không có mạng), "timeout", "rejected" (dịch vụ từ chối / đổi giao thức), "service" (trả lỗi / không có audio)."""


class EdgeOffline(EdgeError):
    reason = "offline"


class EdgeTimeout(EdgeError):
    reason = "timeout"


class EdgeRejected(EdgeError):
    reason = "rejected"


class EdgeDropped(EdgeError):
    """Dịch vụ cắt kết nối giữa lượt (đo 03-10: thỉnh thoảng, vài phần trăm lượt, với đúng cùng chữ vừa đọc được) - thử lại là xong."""


_clock_skew = 0.0  # giây: lệch giữa đồng hồ máy và đồng hồ máy chủ, học từ header Date của lần bị từ chối (403)


def gec_token(now: float | None = None, skew: float | None = None) -> str:
    """`Sec-MS-GEC`: SHA-256 (chữ hoa) của "<thời gian Windows file time làm tròn xuống 5 phút><token>"."""
    seconds = (time.time() if now is None else now) + (_clock_skew if skew is None else skew) + 11_644_473_600
    seconds -= seconds % 300
    ticks = int(seconds * 10_000_000)
    return hashlib.sha256(f"{ticks}{TRUSTED_CLIENT_TOKEN}".encode("ascii")).hexdigest().upper()


_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def clean(text: str) -> str:
    """Dịch vụ từ chối vài ký tự điều khiển (dấu tab dọc hay có trong PDF quét)."""
    return _CONTROL.sub(" ", text)


def split_text(text: str, limit: int = MAX_CHUNK_BYTES) -> list[str]:
    """Cắt chữ thành các đoạn mà bản đã escape không quá `limit` byte UTF-8, ưu tiên cắt ở hết câu rồi tới khoảng trắng. Ghép lại đúng chữ gốc (bỏ khoảng trắng đầu / cuối đoạn)."""
    text = text.strip()
    pieces: list[str] = []
    while text:
        if len(escape(text).encode("utf-8")) <= limit:
            pieces.append(text)
            break
        # Cửa sổ ký tự lớn nhất còn vừa limit byte.
        low, high = 1, len(text)
        while low < high:
            middle = (low + high + 1) // 2
            if len(escape(text[:middle]).encode("utf-8")) <= limit:
                low = middle
            else:
                high = middle - 1
        window = text[:low]
        cut = max(window.rfind(". "), window.rfind("! "), window.rfind("? "), window.rfind("\n"))
        cut = cut + 1 if cut > low // 3 else window.rfind(" ")
        if cut <= 0:
            cut = low
        pieces.append(text[:cut].strip())
        text = text[cut:].strip()
    return [piece for piece in pieces if piece]


def build_ssml(voice: str, text: str) -> str:
    return (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='vi-VN'>"
        f"<voice name='{voice}'><prosody pitch='+0Hz' rate='+0%' volume='+0%'>{escape(clean(text))}</prosody></voice></speak>"
    )


def _timestamp() -> str:
    return time.strftime("%a %b %d %Y %H:%M:%S GMT+0000 (Coordinated Universal Time)", time.gmtime())


def config_message() -> str:
    return (
        f"X-Timestamp:{_timestamp()}\r\nContent-Type:application/json; charset=utf-8\r\nPath:speech.config\r\n\r\n"
        '{"context":{"synthesis":{"audio":{"metadataoptions":{"sentenceBoundaryEnabled":"false","wordBoundaryEnabled":"true"},'
        '"outputFormat":"' + OUTPUT_FORMAT + '"}}}}\r\n'
    )


def ssml_message(request_id: str, ssml: str) -> str:
    # "Z" thừa ở X-Timestamp là lỗi cố hữu của chính Edge, dịch vụ quen với nó.
    return f"X-RequestId:{request_id}\r\nContent-Type:application/ssml+xml\r\nX-Timestamp:{_timestamp()}Z\r\nPath:ssml\r\n\r\n{ssml}"


def parse_headers(raw: bytes) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in raw.decode("utf-8", "replace").split("\r\n"):
        name, _, value = line.partition(":")
        if name:
            headers[name.strip()] = value.strip()
    return headers


def parse_metadata(body: str, compensation_ticks: int) -> list[Boundary]:
    """Các WordBoundary trong một tin `audio.metadata`, đổi sang ms (tick // 10 000, làm tròn xuống) và cộng mốc bù của đoạn."""
    found: list[Boundary] = []
    for item in json.loads(body).get("Metadata", []):
        if item.get("Type") != "WordBoundary":
            continue
        data = item["Data"]
        start = data["Offset"] + compensation_ticks
        found.append(Boundary(unescape(data["text"]["Text"]), start // TICKS_PER_MS, (start + data["Duration"]) // TICKS_PER_MS))
    return found


class EdgeClient:
    """`host` / `port` / `secure` đổi được để bài thử nói chuyện với máy chủ giả trên máy này."""

    def __init__(self, *, host: str = HOST, port: int = 443, secure: bool = True, path: str = PATH,
                 connect_timeout: float = CONNECT_TIMEOUT, read_timeout: float = READ_TIMEOUT) -> None:
        self.host = host
        self.port = port
        self.secure = secure
        self.path = path
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout

    def _open(self) -> websocket.Connection:
        query = (f"?TrustedClientToken={TRUSTED_CLIENT_TOKEN}&ConnectionId={uuid.uuid4().hex}"
                 f"&Sec-MS-GEC={gec_token()}&Sec-MS-GEC-Version={quote(SEC_MS_GEC_VERSION)}")
        major = CHROMIUM_FULL_VERSION.split(".")[0]
        headers = {
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "Origin": "chrome-extension://jdiccldimpdaibmpdkjnbmckianbfold",
            "Sec-WebSocket-Version": "13",
            "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36 Edg/{major}.0.0.0",
            "Accept-Language": "en-US,en;q=0.9",
            "Cookie": f"muid={secrets.token_hex(16).upper()};",
        }
        return websocket.connect(self.host, self.port, self.path + query, headers, secure=self.secure, timeout=self.connect_timeout,
                              read_timeout=self.read_timeout)

    def _connect(self) -> websocket.Connection:
        global _clock_skew
        try:
            try:
                return self._open()
            except websocket.Rejected as rejected:
                # 403 thường là đồng hồ máy lệch so với máy chủ (token theo giờ): học độ lệch từ header Date, thử lại một lần.
                if rejected.status != 403 or not rejected.date:
                    raise
                try:
                    server = parsedate_to_datetime(rejected.date).timestamp()
                except (TypeError, ValueError):
                    raise rejected from None
                _clock_skew = server - time.time()
                return self._open()
        except websocket.Rejected as rejected:
            raise EdgeRejected(f"Dịch vụ đọc to từ chối kết nối (HTTP {rejected.status}); có thể Microsoft đã đổi giao thức.") from rejected
        except (socket.gaierror, ConnectionRefusedError, ConnectionResetError, ConnectionAbortedError) as error:
            raise EdgeOffline("Không có mạng để dùng giọng trực tuyến.") from error
        except TimeoutError as error:
            raise EdgeOffline("Không kết nối được tới dịch vụ đọc to (quá giờ).") from error
        except ssl.SSLError as error:
            raise EdgeError(f"Không bắt tay TLS được với dịch vụ đọc to: {error}") from error
        except websocket.WebSocketError as error:
            raise EdgeError(f"Dịch vụ đọc to trả lời lạ: {error}") from error
        except OSError as error:
            # ENETUNREACH / EHOSTUNREACH / "network is down"...: cũng là không có mạng.
            raise EdgeOffline("Không có mạng để dùng giọng trực tuyến.") from error

    def _speak_one(self, voice: str, text: str, compensation_ticks: int, deadline: float) -> tuple[bytes, list[Boundary]]:
        connection = self._connect()
        audio = bytearray()
        boundaries: list[Boundary] = []
        try:
            connection.send_text(config_message())
            connection.send_text(ssml_message(uuid.uuid4().hex, build_ssml(voice, text)))
            while True:
                if time.monotonic() > deadline:
                    raise EdgeTimeout("Dịch vụ đọc to trả lời quá chậm.")
                try:
                    kind, payload = connection.recv()
                except TimeoutError as error:
                    raise EdgeTimeout("Dịch vụ đọc to không trả lời.") from error
                except websocket.Closed as error:
                    raise EdgeDropped(f"Dịch vụ đọc to đóng kết nối sớm ({error.code}).") from error
                except websocket.WebSocketError as error:
                    raise EdgeOffline(f"Mất kết nối giữa chừng: {error}") from error
                if kind == websocket.TEXT:
                    raw, _, body = payload.partition(b"\r\n\r\n")
                    path = parse_headers(raw).get("Path", "")
                    if path == "audio.metadata":
                        boundaries += parse_metadata(body.decode("utf-8"), compensation_ticks)
                    elif path == "turn.end":
                        break
                    elif path not in ("turn.start", "response"):
                        raise EdgeError(f"Dịch vụ đọc to gửi tin lạ: {path!r}")
                elif len(payload) >= 2:
                    header_length = int.from_bytes(payload[:2], "big")
                    if header_length + 2 > len(payload):
                        raise EdgeError("Khung audio hỏng (độ dài header sai).")
                    headers = parse_headers(payload[2:2 + header_length])
                    data = payload[2 + header_length:]
                    if headers.get("Path") == "audio" and data:
                        audio += data
        finally:
            connection.close()
        return bytes(audio), boundaries

    def synthesize(self, text: str, voice: str = DEFAULT_VOICE) -> Synthesis:
        """Đọc `text` bằng `voice` (mã đầy đủ, vd "vi-VN-HoaiMyNeural"): MP3 + các WordBoundary (ms từ đầu clip) + độ dài."""
        deadline = time.monotonic() + TOTAL_TIMEOUT
        audio = bytearray()
        boundaries: list[Boundary] = []
        pieces = split_text(clean(text))
        for piece in pieces:
            # Mốc của mỗi đoạn tính từ đầu đoạn ấy: bù bằng độ dài audio các đoạn trước (CBR nên chính xác).
            compensation = len(audio) * 8 * 10_000_000 // BITRATE_BPS
            for attempt in range(RETRIES + 1):
                try:
                    data, found = self._speak_one(voice, piece, compensation, deadline)
                    break
                except EdgeDropped:
                    if attempt == RETRIES:
                        raise
                    time.sleep(0.3 * (attempt + 1))
            audio += data
            boundaries += found
        if not audio:
            raise EdgeError("Dịch vụ đọc to không trả về âm thanh (chữ này có thể không đọc được).")
        duration = len(audio) * 8 * 1000 // BITRATE_BPS
        return Synthesis(bytes(audio), boundaries, max(duration, boundaries[-1].end_ms if boundaries else 0))
