"""Giọng trực tuyến: dịch vụ đọc to của Microsoft Edge (giọng thần kinh vi-VN HoaiMy, NamMinh), nói chuyện bằng WebSocket thuần thư viện chuẩn.

Giao thức theo dự án mã nguồn mở `edge-tts` (rany2/edge-tts, LGPL-3.0; client này viết lại từ đặc tả giao thức, riêng mã token `Sec-MS-GEC` v2 ở edge_token.py chuyển từ `drm.py` của dự án ấy): một kết nối
mỗi đoạn <= 4096 byte chữ; gửi `speech.config` (bật WordBoundary, MP3 24 kHz 48 kbps đơn kênh) rồi một SSML; nhận khung nhị phân (đầu 2 byte
độ dài header + header + MP3) và khung văn bản `audio.metadata` (WordBoundary: Offset / Duration tính bằng tick 100 ns) tới `turn.end`.
Dịch vụ không chính thức: có thể đổi mã/chữ ký bất cứ lúc nào (hằng số bên dưới là điểm sửa duy nhất); lỗi nói rõ lý do để giao diện đổi
sang giọng máy. Mạng không có -> `EdgeOffline` (reason "offline").
Mọi người cùng bị HTTP 403 (reason "rejected") dù đồng hồ đúng = Microsoft lại đổi cách tính token (đã đổi v1 -> v2 tháng 10/2026): đối chiếu `drm.py` / `constants.py` của edge-tts bản mới nhất.
"""
from __future__ import annotations

import json
import re
import secrets
import socket
import ssl
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
from email.utils import parsedate_to_datetime
from urllib.parse import quote
from xml.sax.saxutils import escape, unescape

from . import mp3, websocket
from .edge_token import TRUSTED_CLIENT_TOKEN, generate_sec_ms_gec_v2
from .mapping import Boundary
from .model import Synthesis, VoiceError

HOST = "speech.platform.bing.com"
PATH = "/consumer/speech/synthesize/readaloud/edge/v1"
CHROMIUM_FULL_VERSION = "143.0.3650.75"
SEC_MS_GEC_VERSION = f"2-{CHROMIUM_FULL_VERSION}"  # "2-" = token v2 (edge_token.py); v1 (SHA-256 thường) bị dịch vụ từ chối 403 từ tháng 10/2026
OUTPUT_FORMAT = "audio-24khz-48kbitrate-mono-mp3"
BITRATE_BPS = 48_000  # CBR: byte -> thời gian chính xác, dùng để cộng dồn mốc giữa các đoạn và đo độ dài clip
TICKS_PER_MS = 10_000
MAX_CHUNK_BYTES = 4000  # dịch vụ nhận <= 4096 byte chữ đã escape mỗi SSML
CONNECT_TIMEOUT = 4.0  # nối + bắt tay TLS + nâng cấp WebSocket. Bắt tay thật: p50 0,49 s, p95 0,71 s, p99 1,15 s (222 lượt đo a48-a51); thỉnh thoảng một lần treo ~10 s (a51: 8 / 95 mảnh khi nhiều kết nối mở cùng lúc): hết giờ sớm rồi thử lại (EdgeConnectTimeout)
READ_TIMEOUT = 25.0
TOTAL_TIMEOUT = 90.0
RETRIES = 2  # lượt bị cắt giữa chừng thử lại tối đa chừng này lần (kết nối mới)
# Đọc song song các câu của MỘT đoạn (soát a49: chữ Edge chưa từng đọc ra audio chỉ nhanh cỡ 1x thời gian thật, đoạn 15 giây mất 13-27 giây; các yêu cầu song song không làm
# nhau chậm đi - 5 đoạn mới cùng lúc 13-19 giây thay vì 49 giây nối tiếp). Điện thoại (EdgeTts.kt) dùng đúng các hằng số và luật cắt này, bộ ví dụ chung
# tests/fixtures/readaloud/edge/pieces.json: đổi một bên thì đổi cả hai bên và bộ ví dụ.
PIECE_PARALLEL = 3  # tối đa chừng này mảnh một đoạn (và chừng này kết nối cùng lúc cho một clip)
EDGE_CONNECTIONS = 8  # trần kết nối Edge đang mở của cả tiến trình: đọc trước (tới 8 đoạn) x mảnh không mở hàng chục ổ cắm cùng lúc
WHOLE_CHARS = 100  # đoạn ngắn hơn chừng này ký tự giữ một yêu cầu: câu đơn 90-100 ký tự đo 5,8-13,9 giây, cắt đôi không nhanh hơn mà tốn thêm một lần nối (~0,45 giây)
MIN_PIECE_CHARS = 50  # mảnh không nhỏ hơn chừng này (gộp câu ngắn): mảnh quá ngắn thêm chỗ nối mà không rút ngắn thời gian chờ
LONG_SENTENCE_CHARS = 200  # câu dài hơn chừng này được cắt tiếp ở ; : , (sau dấu có khoảng trắng - không bao giờ giữa chữ hay số như "3,5")

# Chỗ nối giữa hai mảnh (soát a51: 26 chỗ nối đo 0,95-0,99 giây lặng). Mỗi lượt của Edge kết thúc bằng ~0,85 giây lặng đuôi + ~0,13 giây lặng đầu của mảnh kế, trong khi Edge tự nghỉ
# giữa hai câu TRONG một lượt chỉ 0,86 giây (đo a52, 6 chỗ: khoảng cách mốc 862-875 ms; sau dấu phẩy 137-263 ms). Nên cắt đuôi mảnh không phải mảnh cuối, giữ lại JOIN_TAIL_*_MS sau
# mốc hết chữ cuối (dấu câu quyết định nghỉ bao lâu) cho chỗ nối nghỉ đúng cỡ Edge nghỉ ở dấu ấy: hết câu 730 ms (+ ~130 ms đầu mảnh kế = 0,86 giây), dấu phẩy / chỗ cắt khác 100 ms (= ~0,23 giây).
# Cắt theo KHUNG MP3 (24 kHz, 48 kbps CBR, không đệm: 144 byte = 24 ms mỗi khung): khung nào không đúng dạng ấy thì giữ nguyên cả mảnh. Chữ cuối kết thúc trong khoảng -27..+15 ms quanh mốc
# hết chữ (đo 30 mảnh) nên 100 ms còn dư cho bộ giải mã. Điện thoại (EdgeTts.kt `EdgeJoin`) dùng đúng các hằng số này và bộ ví dụ tests/fixtures/readaloud/edge/join_tail.json.
JOIN_TAIL_SENTENCE_MS = 730
JOIN_TAIL_OTHER_MS = 100
MP3_FRAME_BYTES = 144
MP3_FRAME_MS = 24

DEFAULT_VOICE = "vi-VN-HoaiMyNeural"
VOICES = [("vi-VN-HoaiMyNeural", "Hoài My", "female"), ("vi-VN-NamMinhNeural", "Nam Minh", "male")]


class EdgeError(VoiceError):
    """Lỗi của dịch vụ. `reason`: "offline" (không có mạng), "timeout", "rejected" (dịch vụ từ chối / đổi giao thức), "service" (trả lỗi / không có audio)."""


class EdgeOffline(EdgeError):
    reason = "offline"


class EdgeTimeout(EdgeError):
    reason = "timeout"


class EdgeRejected(EdgeError):
    reason = "rejected"


class EdgeDropped(EdgeError):
    """Dịch vụ cắt kết nối giữa lượt (đo 03-10: thỉnh thoảng, vài phần trăm lượt, với đúng cùng chữ vừa đọc được) - thử lại là xong.
    Cũng dùng cho lỗi thoáng qua lúc bắt tay: HTTP 429 / 5xx, kết nối bị reset (soát 03-10: một lần reset từng làm đoạn ấy rơi về giọng
    máy như mất mạng)."""


class EdgeConnectTimeout(EdgeDropped):
    """Nối được tới máy chủ (DNS xong) mà bắt tay không xong trong CONNECT_TIMEOUT. Là một EdgeDropped (thử lại được; a51: một lần treo từng báo "không có mạng" làm cả chương dừng);
    hết lần thử mà lần nào cũng treo thì `_speak_piece` đổi nó thành EdgeOffline (mạng bị chặn thật)."""


_clock_skew = 0.0  # giây: lệch giữa đồng hồ máy và đồng hồ máy chủ, học từ header Date của lần bị từ chối (403)


def gec_token(now: float | None = None, skew: float | None = None) -> str:
    """`Sec-MS-GEC` (v2): "<CS64>-<SHA-256 biến thể>" của "<Windows file time làm tròn xuống 5 phút><token>" - xem edge_token.py."""
    return generate_sec_ms_gec_v2((time.time() if now is None else now) + (_clock_skew if skew is None else skew))


_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def clean(text: str) -> str:
    """Dịch vụ từ chối vài ký tự điều khiển (dấu tab dọc hay có trong PDF quét)."""
    return _CONTROL.sub(" ", text)


def escaped_bytes(text: str) -> int:
    return len(escape(text).encode("utf-8"))


def split_text(text: str, limit: int = MAX_CHUNK_BYTES, measure: Callable[[str], int] = escaped_bytes) -> list[str]:
    """Cắt chữ thành các đoạn có `measure` (mặc định: số byte UTF-8 của bản đã escape) không quá `limit`, ưu tiên cắt ở hết câu rồi tới khoảng
    trắng. Ghép lại đúng chữ gốc (bỏ khoảng trắng đầu / cuối đoạn). Giọng dùng khoá (byok) cắt theo số ký tự: `measure=len`."""
    text = text.strip()
    pieces: list[str] = []
    while text:
        if measure(text) <= limit:
            pieces.append(text)
            break
        # Cửa sổ ký tự lớn nhất còn vừa limit.
        low, high = 1, len(text)
        while low < high:
            middle = (low + high + 1) // 2
            if measure(text[:middle]) <= limit:
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


_SENTENCE_END = ".!?…"
_SENTENCE_CLOSERS = "\"'”’)]»"
_CLAUSE_MARKS = ";:,"


def split_sentences(text: str) -> list[str]:
    """Cắt ở hết câu: dấu . ! ? … (và dấu đóng ngoặc / nháy đi liền), rồi khoảng trắng, rồi chữ KHÔNG viết thường. Giữ nguyên câu như
    "Anh A. Nguyễn" (chữ đơn trước dấu chấm = tên viết tắt) và `"Thật à?" anh hỏi` (sau dấu hỏi là chữ thường). Điện thoại cài lại đúng luật này."""
    out: list[str] = []
    start = 0
    i = 0
    n = len(text)
    while i < n:
        if text[i] not in _SENTENCE_END:
            i += 1
            continue
        end = i + 1
        while end < n and text[end] in _SENTENCE_END:
            end += 1
        close = end
        while close < n and text[close] in _SENTENCE_CLOSERS:
            close += 1
        after = close
        while after < n and text[after].isspace():
            after += 1
        initial = text[i] == "." and end == i + 1 and i >= 1 and text[i - 1].isalpha() and (i == 1 or not text[i - 2].isalnum())
        if after > close and after < n and not text[after].islower() and not initial:
            out.append(text[start:close].strip())
            start = after
            i = after
        else:
            i = end
    out.append(text[start:].strip())
    return [piece for piece in out if piece]


def split_clauses(sentence: str) -> list[str]:
    """Một câu dài thành các vế: cắt sau ; : , khi sau dấu có khoảng trắng."""
    out: list[str] = []
    start = 0
    for i in range(len(sentence) - 1):
        if sentence[i] in _CLAUSE_MARKS and sentence[i + 1].isspace():
            out.append(sentence[start:i + 1].strip())
            start = i + 1
    out.append(sentence[start:].strip())
    return [piece for piece in out if piece]


def _group_units(units: list[str]) -> list[str]:
    """Gộp các câu / vế liền nhau thành tối đa PIECE_PARALLEL mảnh cân bằng độ dài (mỗi mảnh >= MIN_PIECE_CHARS). Nhiều mảnh hơn số kết nối cùng lúc chỉ xếp hàng
    thêm một vòng chờ ~5-10 giây của Edge, nên 8 câu 60 ký tự thành 3 mảnh chứ không phải 8."""
    total = sum(len(unit) for unit in units)
    count = min(PIECE_PARALLEL, len(units), max(1, total // MIN_PIECE_CHARS))
    prefix = [0]
    for unit in units:
        prefix.append(prefix[-1] + len(unit))
    cuts = [0]
    for j in range(1, count):
        # Chỗ cắt thứ j: số câu ở j mảnh đầu sao cho độ dài dồn gần nhất total*j/count (hoà thì lấy sớm hơn); còn chỗ cho các mảnh sau.
        best = min(range(cuts[-1] + 1, len(units) - (count - j) + 1), key=lambda at: (abs(prefix[at] * count - total * j), at))
        cuts.append(best)
    cuts.append(len(units))
    groups = [units[cuts[g]:cuts[g + 1]] for g in range(count)]
    lengths = [prefix[cuts[g + 1]] - prefix[cuts[g]] for g in range(count)]
    while len(groups) > 1 and min(lengths) < MIN_PIECE_CHARS:
        small = lengths.index(min(lengths))
        neighbours = [x for x in (small - 1, small + 1) if 0 <= x < len(groups)]
        other = min(neighbours, key=lambda x: (lengths[x], x))
        first, second = sorted((small, other))
        groups[first:second + 1] = [groups[first] + groups[second]]
        lengths[first:second + 1] = [lengths[first] + lengths[second]]
    return [" ".join(group) for group in groups]


def speech_pieces(text: str) -> list[str]:
    """Các mảnh gửi Edge song song cho MỘT đoạn: đoạn ngắn (< WHOLE_CHARS) một mảnh; còn lại cắt ở hết câu (câu dài hơn LONG_SENTENCE_CHARS cắt tiếp ở ; : ,),
    gộp thành tối đa PIECE_PARALLEL mảnh cân bằng; mảnh quá giới hạn byte của dịch vụ cắt tiếp bằng `split_text`. Ghép các mảnh theo thứ tự cho đúng chữ gốc."""
    text = text.strip()
    if len(text) >= WHOLE_CHARS:
        units: list[str] = []
        for sentence in split_sentences(text):
            units += split_clauses(sentence) if len(sentence) > LONG_SENTENCE_CHARS else [sentence]
        if len(units) > 1:
            return [part for piece in _group_units(units) for part in split_text(piece)]
    return split_text(text)


def join_tail_ms(piece: str) -> int:
    """Bao lâu sau mốc hết chữ cuối của `piece` còn giữ audio khi mảnh ấy đứng trước một mảnh khác: hết câu (dấu . ! ? … , có thể kèm dấu đóng nháy / ngoặc) nghỉ như Edge nghỉ giữa hai câu, còn lại ngắn."""
    body = piece.rstrip().rstrip(_SENTENCE_CLOSERS)
    return JOIN_TAIL_SENTENCE_MS if body and body[-1] in _SENTENCE_END else JOIN_TAIL_OTHER_MS


def trim_join_tail(audio: bytes, piece: str, boundaries: list[Boundary]) -> bytes:
    """Cắt phần lặng đuôi của một mảnh không phải mảnh cuối, ở ranh giới khung MP3, giữ tới mốc hết chữ cuối + [join_tail_ms]. Không có mốc, hay khung nào không đúng dạng
    24 kHz / 48 kbps / 144 byte (thẻ ID3, khung đệm, rác...) thì trả nguyên; không bao giờ cắt vào chữ."""
    if not boundaries or not audio or len(audio) % MP3_FRAME_BYTES:
        return audio
    keep = -(-(boundaries[-1].end_ms + join_tail_ms(piece)) // MP3_FRAME_MS)  # làm tròn LÊN: không cắt sớm hơn
    if keep * MP3_FRAME_BYTES >= len(audio):
        return audio
    for at in range(0, len(audio), MP3_FRAME_BYTES):
        if mp3.frame_at(audio, at) != (MP3_FRAME_BYTES, 576, 24_000):
            return audio
    return audio[:keep * MP3_FRAME_BYTES]


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


def read_turn(connection: websocket.Connection, compensation_ticks: int, deadline: float, *, label: str = "Dịch vụ đọc to",
              strict: bool = True, on_close: Callable[[websocket.Closed], VoiceError | None] | None = None) -> tuple[bytes, list[Boundary]]:
    """Nhận một lượt đọc tới `turn.end`: MP3 (khung nhị phân `Path:audio`) + WordBoundary của `audio.metadata` (cộng mốc bù). Dùng chung cho Edge
    và Azure Speech (cùng giao thức tin, azure.py). `label`: tên dịch vụ trong câu báo lỗi; `strict`: tin lạ là lỗi (Edge) hay bỏ qua (Azure gửi
    thêm tin khác); `on_close`: đổi khung CLOSE của máy chủ thành lỗi riêng (Azure báo hết hạn mức bằng lý do đóng) - None thì như bị cắt."""
    audio = bytearray()
    boundaries: list[Boundary] = []
    while True:
        if time.monotonic() > deadline:
            raise EdgeTimeout(f"{label} trả lời quá chậm.")
        try:
            kind, payload = connection.recv()
        except TimeoutError as error:
            raise EdgeTimeout(f"{label} không trả lời.") from error
        except websocket.Closed as error:
            mapped = on_close(error) if on_close is not None else None
            if mapped is not None:
                raise mapped from error
            raise EdgeDropped(f"{label} đóng kết nối sớm ({error.code}).") from error
        except websocket.WebSocketError as error:
            # Kết nối bị reset / khung hỏng GIỮA lượt: dịch vụ cắt ngang (thử lại là xong), không phải "không có mạng" - mạng thật sự mất thì lần nối mới báo EdgeOffline.
            raise EdgeDropped(f"Mất kết nối giữa chừng: {error}") from error
        if kind == websocket.TEXT:
            raw, _, body = payload.partition(b"\r\n\r\n")
            path = parse_headers(raw).get("Path", "")
            if path == "audio.metadata":
                boundaries += parse_metadata(body.decode("utf-8"), compensation_ticks)
            elif path == "turn.end":
                return bytes(audio), boundaries
            elif strict and path not in ("turn.start", "response"):
                raise EdgeError(f"{label} gửi tin lạ: {path!r}")
        elif len(payload) >= 2:
            header_length = int.from_bytes(payload[:2], "big")
            if header_length + 2 > len(payload):
                raise EdgeError("Khung audio hỏng (độ dài header sai).")
            headers = parse_headers(payload[2:2 + header_length])
            data = payload[2 + header_length:]
            if headers.get("Path") == "audio" and data:
                audio += data


_connections = threading.BoundedSemaphore(EDGE_CONNECTIONS)  # mọi EdgeClient trong tiến trình dùng chung
SLOT_POLL = 0.25  # mảnh chờ chỗ kết nối xem lại clip đã bỏ chưa sau chừng này giây


class _Clip:
    """Các mảnh của MỘT clip đang đọc song song. Một mảnh hỏng -> `abort()`: cắt ổ cắm các mảnh còn đang đọc (trả chỗ EDGE_CONNECTIONS ngay, không giữ
    tới hạn chung) và không mảnh nào mở kết nối / thử lại nữa. Điện thoại: ClipCancel trong EdgeTts.kt."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._open: set[websocket.Connection] = set()
        self.aborted = False

    def opened(self, connection: websocket.Connection) -> bool:
        with self._lock:
            if not self.aborted:
                self._open.add(connection)
            return not self.aborted

    def closed(self, connection: websocket.Connection) -> None:
        with self._lock:
            self._open.discard(connection)

    def abort(self) -> None:
        with self._lock:
            self.aborted = True
            live = list(self._open)
        for connection in live:
            connection.abort()


class _ClipAborted(EdgeError):
    """Mảnh dừng vì mảnh khác của clip đã hỏng; không bao giờ tới người gọi (synthesize ném lỗi của mảnh hỏng)."""


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
            if rejected.status == 429 or rejected.status >= 500:
                raise EdgeDropped(f"Dịch vụ đọc to đang bận (HTTP {rejected.status}).") from rejected
            raise EdgeRejected(f"Dịch vụ đọc to từ chối kết nối (HTTP {rejected.status}); có thể Microsoft đã đổi giao thức.") from rejected
        except (ConnectionResetError, ConnectionAbortedError) as error:
            raise EdgeDropped("Dịch vụ đọc to cắt kết nối lúc bắt tay.") from error
        except (socket.gaierror, ConnectionRefusedError) as error:
            raise EdgeOffline("Không có mạng để dùng giọng trực tuyến.") from error
        except TimeoutError as error:
            raise EdgeConnectTimeout("Không bắt tay kịp với dịch vụ đọc to (quá giờ).") from error
        except ssl.SSLError as error:
            raise EdgeError(f"Không bắt tay TLS được với dịch vụ đọc to: {error}") from error
        except websocket.WebSocketError as error:
            raise EdgeError(f"Dịch vụ đọc to trả lời lạ: {error}") from error
        except OSError as error:
            # ENETUNREACH / EHOSTUNREACH / "network is down"...: cũng là không có mạng.
            raise EdgeOffline("Không có mạng để dùng giọng trực tuyến.") from error

    def _speak_one(self, voice: str, text: str, compensation_ticks: int, deadline: float, *, clip: _Clip | None = None) -> tuple[bytes, list[Boundary]]:
        # Giữ một chỗ trong EDGE_CONNECTIONS suốt đời kết nối (không giữ khi nghỉ chờ thử lại, nên không có chuyện giữ chỗ mà đợi chỗ).
        slots = _connections
        while not slots.acquire(timeout=max(0.0, min(SLOT_POLL, deadline - time.monotonic()))):
            if clip is not None and clip.aborted:
                raise _ClipAborted("Clip đã bỏ.")
            if time.monotonic() >= deadline:
                raise EdgeTimeout("Dịch vụ đọc to đang quá tải ở máy này (quá nhiều đoạn đọc cùng lúc).")
        try:
            if clip is not None and clip.aborted:
                raise _ClipAborted("Clip đã bỏ.")
            connection = self._connect()
            try:
                if clip is not None and not clip.opened(connection):
                    raise _ClipAborted("Clip đã bỏ.")
                try:
                    connection.send_text(config_message())
                    connection.send_text(ssml_message(uuid.uuid4().hex, build_ssml(voice, text)))
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as error:
                    raise EdgeDropped("Dịch vụ đọc to cắt kết nối lúc nhận chữ.") from error
                return read_turn(connection, compensation_ticks, deadline)
            finally:
                if clip is not None:
                    clip.closed(connection)
                connection.close()
        finally:
            slots.release()

    def _speak_piece(self, voice: str, piece: str, deadline: float, clip: _Clip | None = None) -> tuple[bytes, list[Boundary]]:
        """Một mảnh, thử lại khi dịch vụ cắt lượt; mốc tính từ đầu mảnh (người gọi cộng độ dài audio các mảnh trước). Clip đã bỏ thì thôi, không thử lại."""
        for attempt in range(RETRIES + 1):
            try:
                return self._speak_one(voice, piece, 0, deadline, clip=clip)
            except EdgeDropped as error:
                if attempt == RETRIES or (clip is not None and clip.aborted):
                    if attempt == RETRIES and isinstance(error, EdgeConnectTimeout):
                        raise EdgeOffline("Không kết nối được tới dịch vụ đọc to (quá giờ).") from error  # lần nào cũng treo: mạng bị chặn thật
                    raise
                if attempt:  # lần thử lại đầu nối lại NGAY (kết nối mới): chỉ lần sau mới nghỉ, để mạng chập chờn có thời gian hồi
                    time.sleep(0.3 * (attempt + 1))
        raise AssertionError("unreachable")

    def synthesize(self, text: str, voice: str = DEFAULT_VOICE) -> Synthesis:
        """Đọc `text` bằng `voice` (mã đầy đủ, vd "vi-VN-HoaiMyNeural"): MP3 + các WordBoundary (ms từ đầu clip) + độ dài.
        Đoạn dài đọc theo `speech_pieces`, các mảnh song song (tối đa PIECE_PARALLEL); mảnh ĐẦU TIÊN hỏng (theo thời gian, không đợi các mảnh trước nó)
        làm cả clip hỏng ngay với chính lỗi ấy - cùng các loại lỗi như khi đọc nối tiếp - và các mảnh còn lại bị cắt (điện thoại: EdgeTts.kt cùng luật)."""
        deadline = time.monotonic() + TOTAL_TIMEOUT
        pieces = speech_pieces(clean(text))
        if len(pieces) <= 1:
            results = [self._speak_piece(voice, piece, deadline) for piece in pieces]
        else:
            clip = _Clip()
            pool = ThreadPoolExecutor(max_workers=min(PIECE_PARALLEL, len(pieces)), thread_name_prefix="edge-piece")
            try:
                futures = [pool.submit(self._speak_piece, voice, piece, deadline, clip) for piece in pieces]
                # Mảnh tự dừng ở hạn chung (read_turn / chờ chỗ); +1 giây chỉ để chắc không treo nếu một mảnh không tôn trọng hạn.
                done, _ = wait(futures, timeout=max(0.0, deadline - time.monotonic()) + 1.0, return_when=FIRST_EXCEPTION)
                failed = [future for future in futures if future in done and future.exception() is not None]
                if failed:
                    raise failed[0].exception()  # nhiều mảnh hỏng cùng lúc: lấy mảnh đứng trước cho ổn định
                if len(done) < len(futures):
                    raise EdgeTimeout("Dịch vụ đọc to quá lâu không trả lời.")
                results = [future.result() for future in futures]
            finally:
                clip.abort()  # thành công thì không còn kết nối nào mở - vô hại
                pool.shutdown(wait=False, cancel_futures=True)
        audio = bytearray()
        boundaries: list[Boundary] = []
        for index, (data, found) in enumerate(results):
            if index < len(results) - 1:
                data = trim_join_tail(data, pieces[index], found)  # cắt lặng đuôi trước khi bù mốc cho mảnh sau
            # Mốc của mỗi mảnh tính từ đầu mảnh ấy: bù bằng độ dài audio các mảnh trước (CBR nên chính xác).
            shift_ms = len(audio) * 8 * 1000 // BITRATE_BPS
            boundaries += [Boundary(b.text, b.start_ms + shift_ms, b.end_ms + shift_ms, b.char) for b in found] if shift_ms else found
            audio += data
        if not audio:
            raise EdgeError("Dịch vụ đọc to không trả về âm thanh (chữ này có thể không đọc được).")
        duration = len(audio) * 8 * 1000 // BITRATE_BPS
        return Synthesis(bytes(audio), boundaries, max(duration, boundaries[-1].end_ms if boundaries else 0))
