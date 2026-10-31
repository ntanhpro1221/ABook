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
from typing import Protocol
from urllib.parse import quote
from xml.sax.saxutils import escape, unescape

from . import mp3, websocket
from .edge_token import TRUSTED_CLIENT_TOKEN, generate_sec_ms_gec_v2
from .mapping import Boundary, tokens
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
TARGET_PIECES = 6  # riêng đoạn người nghe đang đứng chờ (rank 0): cắt tới chừng này mảnh. Soát a54 (4 đoạn, mạng thật): 3 -> 6 mảnh rút thời gian chờ trung vị 6,96 -> 5,36 giây, chỗ nối vẫn 855-889 ms
RANK_BACKGROUND = 99  # [ConnectionSlots] rank của việc không có người nghe đứng chờ ngay (Làm trước, xuất sách nói, lượt gọi không nói rõ): đứng sau mọi đoạn người nghe sắp nghe
CANCEL_POLL = 0.2  # giây: clip người gọi bỏ được (`synthesize(cancelled=)`) hỏi lại chừng này một lần - Huỷ xuất sách nói dừng trong <= 1,5 giây (soát a62: chờ hết đoạn mất 7 giây)
EDGE_CONNECTIONS = 8  # trần kết nối Edge đang mở của cả tiến trình: đọc trước (tới 8 đoạn) x mảnh không mở hàng chục ổ cắm cùng lúc
WHOLE_CHARS = 100  # đoạn ngắn hơn chừng này ký tự giữ một yêu cầu: câu đơn 90-100 ký tự đo 5,8-13,9 giây, cắt đôi không nhanh hơn mà tốn thêm một lần nối (~0,45 giây)
MIN_PIECE_CHARS = 50  # mảnh không nhỏ hơn chừng này (gộp câu ngắn): mảnh quá ngắn thêm chỗ nối mà không rút ngắn thời gian chờ
LONG_SENTENCE_CHARS = 200  # câu dài hơn chừng này được cắt tiếp ở ; : , (sau dấu có khoảng trắng - không bao giờ giữa chữ hay số như "3,5")
PIECE_SLACK_PERCENT = 130  # uxfix55: câu dài hơn 130% x (tổng / số mảnh) cũng được cắt ở vế, để một câu dài không làm một mảnh dài gấp đôi các mảnh kia (a57: mảnh 209 ký tự Edge mất 7,9 giây, các mảnh khác 3,5-5,5)

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


class EdgeCancelled(EdgeError):
    """Người gọi bỏ clip giữa lượt (`synthesize(cancelled=)`: Huỷ xuất sách nói): ổ cắm các mảnh đã cắt, không có gì vào bộ đệm."""

    reason = "cancelled"


class EdgeConnectTimeout(EdgeDropped):
    """Nối được tới máy chủ (DNS xong) mà bắt tay không xong trong CONNECT_TIMEOUT. Là một EdgeDropped (thử lại được; a51: một lần treo từng báo "không có mạng" làm cả chương dừng);
    hết lần thử mà lần nào cũng treo thì `_speak_piece` đổi nó thành EdgeTimeout (có mạng mà dịch vụ không trả lời; "không có mạng" là lời sai)."""


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


def piece_limit(rank: int) -> int:
    """Số mảnh tối đa của một đoạn theo rank: đoạn người nghe đang đứng chờ (0) TARGET_PIECES, mọi đoạn khác PIECE_PARALLEL (điện thoại: EdgePieces.pieceLimit)."""
    return TARGET_PIECES if rank == 0 else PIECE_PARALLEL


def clause_threshold(total: int, limit: int) -> int:
    """Câu dài hơn chừng này ký tự được cắt tiếp ở vế (điện thoại: EdgePieces.clauseThreshold): LONG_SENTENCE_CHARS, hay thấp hơn khi một mảnh cân bằng (total / limit) mà ngắn hơn thế nhiều,
    nhưng không bao giờ dưới MIN_PIECE_CHARS."""
    return min(LONG_SENTENCE_CHARS, max(MIN_PIECE_CHARS, -(-PIECE_SLACK_PERCENT * total // (100 * limit))))


def _group_units(units: list[str], limit: int = PIECE_PARALLEL) -> list[str]:
    """Gộp các câu / vế liền nhau thành tối đa `limit` mảnh cân bằng độ dài (mỗi mảnh >= MIN_PIECE_CHARS). Nhiều mảnh hơn số kết nối cùng lúc chỉ xếp hàng
    thêm một vòng chờ ~5-10 giây của Edge, nên 8 câu 60 ký tự thành 3 mảnh chứ không phải 8. Cắt cân bằng với số mảnh nhiều nhất còn giữ mọi mảnh >= MIN_PIECE_CHARS
    (uxfix55: bớt dần số mảnh rồi cắt lại, không gộp mảnh nhỏ vào hàng xóm - vế ngắn làm gộp dây chuyền thành một mảnh duy nhất)."""
    total = sum(len(unit) for unit in units)
    prefix = [0]
    for unit in units:
        prefix.append(prefix[-1] + len(unit))
    count = min(limit, len(units), max(1, total // MIN_PIECE_CHARS))
    while True:
        cuts = [0]
        for j in range(1, count):
            # Chỗ cắt thứ j: số câu ở j mảnh đầu sao cho độ dài dồn gần nhất total*j/count (hoà thì lấy sớm hơn); còn chỗ cho các mảnh sau.
            cuts.append(min(range(cuts[-1] + 1, len(units) - (count - j) + 1), key=lambda at: (abs(prefix[at] * count - total * j), at)))
        cuts.append(len(units))
        if count == 1 or all(prefix[cuts[g + 1]] - prefix[cuts[g]] >= MIN_PIECE_CHARS for g in range(count)):
            return [" ".join(units[cuts[g]:cuts[g + 1]]) for g in range(count)]
        count -= 1


def speech_pieces(text: str, rank: int = RANK_BACKGROUND) -> list[str]:
    """Các mảnh gửi Edge song song cho MỘT đoạn: đoạn ngắn (< WHOLE_CHARS) một mảnh; còn lại cắt ở hết câu (câu dài hơn `clause_threshold` cắt tiếp ở ; : ,),
    gộp thành tối đa `piece_limit(rank)` mảnh cân bằng (đoạn rank 0 nhiều hơn các đoạn khác); mảnh quá giới hạn byte của dịch vụ cắt tiếp bằng `split_text`. Ghép các mảnh theo thứ tự cho đúng chữ gốc."""
    text = text.strip()
    if len(text) >= WHOLE_CHARS:
        limit = piece_limit(rank)
        threshold = clause_threshold(len(text), limit)
        units: list[str] = []
        for sentence in split_sentences(text):
            units += split_clauses(sentence) if len(sentence) > threshold else [sentence]
        if len(units) > 1:
            return [part for piece in _group_units(units, limit) for part in split_text(piece)]
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
              strict: bool = True, on_close: Callable[[websocket.Closed], VoiceError | None] | None = None,
              on_audio: Callable[[bytes], None] | None = None, on_boundaries: Callable[[list[Boundary]], None] | None = None) -> tuple[bytes, list[Boundary]]:
    """Nhận một lượt đọc tới `turn.end`: MP3 (khung nhị phân `Path:audio`) + WordBoundary của `audio.metadata` (cộng mốc bù). Dùng chung cho Edge
    và Azure Speech (cùng giao thức tin, azure.py). `label`: tên dịch vụ trong câu báo lỗi; `strict`: tin lạ là lỗi (Edge) hay bỏ qua (Azure gửi
    thêm tin khác); `on_close`: đổi khung CLOSE của máy chủ thành lỗi riêng (Azure báo hết hạn mức bằng lý do đóng) - None thì như bị cắt.
    `on_audio` / `on_boundaries`: gọi ngay khi nhận một khung tiếng / một tin mốc (phát luồng, `EdgeClient.synthesize(sink=...)`); kết quả trả về vẫn đủ như cũ."""
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
                found = parse_metadata(body.decode("utf-8"), compensation_ticks)
                boundaries += found
                if found and on_boundaries is not None:
                    on_boundaries(found)
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
                if on_audio is not None:
                    on_audio(data)


class ConnectionSlots:
    """Chỗ kết nối Edge của cả tiến trình (EDGE_CONNECTIONS chỗ). Hết chỗ thì người chờ xếp hàng theo `rank` (số đoạn người nghe phải nghe trước đoạn này: 0 = đoạn họ đang đứng chờ, 1 = đoạn kế...;
    mặc định [RANK_BACKGROUND]: việc nền, đọc trước không rõ ai chờ), cùng rank thì ai đến trước được trước. Mảnh đang giữ chỗ không bị đuổi; chỉ chỗ vừa nhả được trao theo hàng.
    Riêng rank 0 không chờ trần `size`: được lấy thêm tới `extra` chỗ vượt trần (a55: đoạn người nghe đứng chờ đến sau ba clip đọc trước chỉ vài ms đã phải đợi 4-11 giây vì chúng chiếm hết
    chỗ - hàng chờ chỉ xếp thứ tự người CHỜ, không đòi lại được chỗ đang giữ). Quá size + extra thì rank 0 cũng chờ; rank >= 1 chỉ được chỗ khi số chỗ giữ xuống dưới `size`.
    Điện thoại: ConnectionSlots trong EdgeTts.kt."""

    POLL = 0.25  # người chờ xem lại `abandoned` sau chừng này giây (bỏ cuộc không đánh thức hàng)

    def __init__(self, size: int, extra: int = 0) -> None:
        self.size = size
        self.extra = extra
        self.free = size  # size - số chỗ đang giữ; âm khi rank 0 đang giữ chỗ vượt trần
        self._turns = 0
        self._queue: list[tuple[int, int]] = []  # (rank, số thứ tự đến); đầu hàng = người được trao chỗ kế
        self._ready = threading.Condition()

    def acquire(self, timeout: float | None = None, rank: int = RANK_BACKGROUND, abandoned: Callable[[], bool] | None = None) -> bool:
        """Lấy một chỗ; False khi quá `timeout` (giây) hay `abandoned()` đúng (clip đã bỏ) - vị trí trong hàng giữ nguyên suốt lúc chờ."""
        deadline = None if timeout is None else time.monotonic() + timeout
        allowance = self.extra if rank == 0 else 0  # chỗ vượt trần được phép với rank này
        with self._ready:
            self._turns += 1
            ticket = (rank, self._turns)
            self._queue.append(ticket)
            self._queue.sort()
            try:
                while not (self.free + allowance > 0 and self._queue[0] == ticket):
                    left = self.POLL if deadline is None else min(self.POLL, deadline - time.monotonic())
                    if left <= 0 or (abandoned is not None and abandoned()):
                        return False
                    self._ready.wait(left)
                self.free -= 1
                return True
            finally:
                self._queue.remove(ticket)
                self._ready.notify_all()  # người kế trong hàng có thể đã tới lượt (còn chỗ), hay người này bỏ cuộc

    def release(self) -> None:
        with self._ready:
            if self.free >= self.size:
                raise ValueError("Trả chỗ kết nối quá số đã giữ")
            self.free += 1
            self._ready.notify_all()


_connections = ConnectionSlots(EDGE_CONNECTIONS, TARGET_PIECES)  # mọi EdgeClient trong tiến trình dùng chung; trần cứng EDGE_CONNECTIONS + TARGET_PIECES (chỉ đoạn rank 0 vượt EDGE_CONNECTIONS)


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


class StreamSink(Protocol):
    """Nơi nhận clip đang đọc, theo ĐÚNG thứ tự của clip cuối: mọi byte đã `audio` nối lại == `Synthesis.audio`, mọi mốc đã `boundaries` nối lại == `Synthesis.boundaries`.
    Gọi từ các luồng đọc (một lần một luồng, có khoá). Sink có thêm `piece_done()` (tuỳ chọn) thì được gọi mỗi khi một mảnh đã phát hết; có `cut(words)` (tuỳ chọn) thì được báo NGAY khi một
    mảnh không phải mảnh đầu hỏng hẳn: `words` = số chữ (`\\S+` của chữ đem đọc) đứng trước mảnh ấy - tiếng sẽ dừng đúng ở đó (các mảnh trước vẫn phát hết rồi mới ném lỗi), uxfix63."""

    def audio(self, data: bytes) -> None: ...

    def boundaries(self, found: list[Boundary]) -> None: ...


class _Part:
    """Một mảnh trong [_Relay]: đệm của lượt đọc hiện tại + phần đã đưa sink. Lượt đọc lại (thử lại sau khi bị cắt) phải cho ra đúng phần đã phát - không thì clip hỏng."""

    def __init__(self, relay: _Relay, index: int) -> None:
        self.relay = relay
        self.index = index
        self.buffer = bytearray()
        self.found: list[Boundary] = []
        self.max_end = 0  # mốc hết chữ lớn nhất của lượt hiện tại
        self.sent = bytearray()  # đã đưa sink (của mảnh này)
        self.sent_found: list[Boundary] = []
        self.final: bytes | None = None  # audio sau khi cắt đuôi, khi mảnh đã xong

    def begin(self) -> None:
        """Bắt đầu một lượt đọc (lượt đầu hay lượt thử lại)."""
        with self.relay.lock:
            self.buffer = bytearray()
            self.found = []
            self.max_end = 0

    def audio(self, data: bytes) -> None:
        with self.relay.lock:
            if self.relay.stopped:
                return
            at = len(self.buffer)
            self.buffer += data
            overlap = min(len(self.buffer), len(self.sent))
            if overlap > at and self.buffer[at:overlap] != self.sent[at:overlap]:
                raise EdgeError("Lượt đọc lại của mảnh khác với phần đã phát.")
            self.relay.pump()

    def boundaries(self, found: list[Boundary]) -> None:
        with self.relay.lock:
            if self.relay.stopped:
                return
            for boundary in found:
                at = len(self.found)
                if at < len(self.sent_found) and boundary != self.sent_found[at]:
                    raise EdgeError("Lượt đọc lại của mảnh khác với phần đã phát.")
                self.found.append(boundary)
                self.max_end = max(self.max_end, boundary.end_ms)
            self.relay.pump()

    def finish(self, data: bytes, found: list[Boundary]) -> None:
        """Mảnh đã đọc xong (`data`, `found` của lượt cuối): cắt đuôi như bản không phát luồng, rồi phát nốt."""
        with self.relay.lock:
            if self.relay.stopped:
                return
            if len(data) < len(self.sent) or found[:len(self.sent_found)] != self.sent_found:
                raise EdgeError("Lượt đọc lại của mảnh ngắn hơn phần đã phát.")
            final = data if self.index == self.relay.count - 1 else trim_join_tail(data, self.relay.pieces[self.index], found)
            self.final = final if len(final) >= len(self.sent) else data[:len(self.sent)]  # (mốc không tăng dần: phần đã phát không bao giờ rút lại)
            self.found = list(found)
            self.relay.pump()


class _Relay:
    """Phát một clip nhiều mảnh ra [StreamSink] theo thứ tự trong khi các mảnh còn đang đọc song song. Mảnh đứng đầu (mảnh sớm nhất chưa phát hết) phát byte ngay khi về;
    mảnh sau nó giữ trong bộ nhớ tới lượt. Mảnh không phải mảnh cuối chỉ phát tới khung MP3 mà `trim_join_tail` chắc chắn giữ lại (khung thứ floor(mốc hết chữ lớn nhất / MP3_FRAME_MS):
    trim giữ tới mốc hết chữ cuối + đuôi nối, làm tròn lên) cho tới khi mảnh xong và phát nốt phần còn lại. Mốc của mảnh i cộng số ms của mọi byte đã phát trước mảnh i (CBR)."""

    def __init__(self, sink: StreamSink, pieces: list[str]) -> None:
        self.sink = sink
        self.pieces = pieces
        self.count = len(pieces)
        self.lock = threading.Lock()
        self.stopped = False
        self.parts = [_Part(self, index) for index in range(len(pieces))]
        self._head = 0
        self._base = 0  # byte của các mảnh trước mảnh đứng đầu (đã phát hết)
        self._end = self.count  # chỉ phát các mảnh trước chỗ này ([cut])

    def stop(self) -> None:
        """Clip hỏng / xong: sink không nhận thêm gì."""
        with self.lock:
            self.stopped = True

    def cut(self, index: int) -> None:
        """Mảnh `index` hỏng hẳn: chỉ phát nốt các mảnh trước nó (phần dở của mảnh hỏng không bao giờ ra sink) và báo sink chữ tiếng sẽ dừng ([StreamSink])."""
        with self.lock:
            if self.stopped:
                return
            self._end = index
            told = getattr(self.sink, "cut", None)
            if told is not None:
                told(sum(len(tokens(piece)) for piece in self.pieces[:index]))

    def pump(self) -> None:
        """Đưa sink mọi thứ đã chắc chắn của mảnh đứng đầu; mảnh đứng đầu xong và phát hết thì mảnh kế lên. Gọi khi đang giữ `lock`."""
        while not self.stopped and self._head < self._end:
            part = self.parts[self._head]
            news = part.found[len(part.sent_found):]
            if news:
                shift_ms = self._base * 8 * 1000 // BITRATE_BPS
                self.sink.boundaries([Boundary(b.text, b.start_ms + shift_ms, b.end_ms + shift_ms, b.char) for b in news] if shift_ms else list(news))
                part.sent_found += news
            if part.final is not None:
                source, limit = part.final, len(part.final)
            elif self._head == self.count - 1:
                source, limit = part.buffer, len(part.buffer)
            else:
                source, limit = part.buffer, min(len(part.buffer), part.max_end // MP3_FRAME_MS * MP3_FRAME_BYTES)
            if limit > len(part.sent):
                chunk = bytes(source[len(part.sent):limit])
                self.sink.audio(chunk)
                part.sent += chunk
            if part.final is not None and len(part.sent) == len(part.final):
                self._base += len(part.final)
                self._head += 1
                done = getattr(self.sink, "piece_done", None)  # tuỳ chọn: người nghe cập nhật mốc chữ mỗi khi một mảnh phát hết
                if done is not None:
                    done()
                continue
            return


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

    def _speak_one(self, voice: str, text: str, compensation_ticks: int, deadline: float, *, clip: _Clip | None = None, rank: int = RANK_BACKGROUND,
                   part: _Part | None = None) -> tuple[bytes, list[Boundary]]:
        # Giữ một chỗ trong EDGE_CONNECTIONS suốt đời kết nối (không giữ khi nghỉ chờ thử lại, nên không có chuyện giữ chỗ mà đợi chỗ). `rank`: số đoạn người nghe phải nghe trước đoạn này (0 = đang
        # đứng chờ đúng nó) - hết chỗ thì mảnh gần người nghe hơn đi trước ([ConnectionSlots]).
        slots = _connections
        if not slots.acquire(max(0.0, deadline - time.monotonic()), rank, lambda: clip is not None and clip.aborted):
            if clip is not None and clip.aborted:
                raise _ClipAborted("Clip đã bỏ.")
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
                if part is None:
                    return read_turn(connection, compensation_ticks, deadline)
                return read_turn(connection, compensation_ticks, deadline, on_audio=part.audio, on_boundaries=part.boundaries)
            finally:
                if clip is not None:
                    clip.closed(connection)
                connection.close()
        finally:
            slots.release()

    def _speak_piece(self, voice: str, piece: str, deadline: float, clip: _Clip | None = None, rank: int = RANK_BACKGROUND,
                     part: _Part | None = None) -> tuple[bytes, list[Boundary]]:
        """Một mảnh, thử lại khi dịch vụ cắt lượt; mốc tính từ đầu mảnh (người gọi cộng độ dài audio các mảnh trước). Clip đã bỏ thì thôi, không thử lại.
        `part`: phát luồng - mỗi lượt đọc (kể cả lượt thử lại, đọc lại từ đầu) báo vào đó."""
        for attempt in range(RETRIES + 1):
            try:
                if part is None:
                    return self._speak_one(voice, piece, 0, deadline, clip=clip, rank=rank)
                part.begin()
                return self._speak_one(voice, piece, 0, deadline, clip=clip, rank=rank, part=part)
            except EdgeDropped as error:
                if attempt == RETRIES or (clip is not None and clip.aborted):
                    if attempt == RETRIES and isinstance(error, EdgeConnectTimeout):
                        # Lần nào cũng treo: có mạng (DNS xong, nối được) mà dịch vụ không trả lời - "quá giờ", không phải "không có mạng".
                        raise EdgeTimeout("Dịch vụ đọc to không trả lời (quá giờ).") from error
                    raise
                if attempt:  # lần thử lại đầu nối lại NGAY (kết nối mới): chỉ lần sau mới nghỉ, để mạng chập chờn có thời gian hồi
                    time.sleep(0.3 * (attempt + 1))
        raise AssertionError("unreachable")

    def _speak_streamed(self, relay: _Relay, index: int, voice: str, piece: str, deadline: float, clip: _Clip | None, rank: int) -> tuple[bytes, list[Boundary]]:
        part = relay.parts[index]
        data, found = self._speak_piece(voice, piece, deadline, clip, rank, part=part)
        part.finish(data, found)
        return part.final, part.found  # type: ignore[return-value]  # finish() vừa đặt (đã cắt đuôi như bản không phát luồng)

    @staticmethod
    def _wait(futures: list, timeout: float, cancelled: Callable[[], bool] | None) -> set:
        """`concurrent.futures.wait(FIRST_EXCEPTION)` hỏi `cancelled()` mỗi CANCEL_POLL giây: người gọi bỏ clip thì cắt mọi mảnh ngay ([EdgeCancelled])."""
        if cancelled is None:
            return wait(futures, timeout=timeout, return_when=FIRST_EXCEPTION)[0]
        end = time.monotonic() + timeout
        while True:
            if cancelled():
                raise EdgeCancelled("Đã bỏ lượt đọc này.")
            done, pending = wait(futures, timeout=max(0.0, min(CANCEL_POLL, end - time.monotonic())), return_when=FIRST_EXCEPTION)
            if not pending or any(future.exception() is not None for future in done) or time.monotonic() >= end:
                return done

    @classmethod
    def _gather(cls, futures: list, deadline: float, relay: _Relay | None, clips: list[_Clip],
                cancelled: Callable[[], bool] | None = None) -> list[tuple[bytes, list[Boundary]]]:
        """Kết quả các mảnh theo thứ tự đọc; mảnh ĐẦU TIÊN hỏng (theo thời gian) thì ném lỗi của nó ngay. Phát luồng mà mảnh hỏng không phải mảnh đầu (uxfix63, a59d e1: các mảnh trước nó
        còn đang về bị cắt, người nghe chỉ còn 2,8 giây tiếng mà phần nối phải đọc lại cả chúng): chỉ cắt các mảnh SAU nó, báo sink chỗ tiếng dừng ngay ([_Relay.cut]) để người nghe xin phần nối
        từ đầu mảnh hỏng trong lúc các mảnh trước vẫn về và phát hết, rồi mới ném lỗi ấy (mảnh trước hỏng nữa: lỗi của mảnh trước)."""
        def remaining() -> float:  # mảnh tự dừng ở hạn chung (read_turn / chờ chỗ); +1 giây chỉ để chắc không treo nếu một mảnh không tôn trọng hạn
            return max(0.0, deadline - time.monotonic()) + 1.0

        done = cls._wait(futures, remaining(), cancelled)
        failed =[index for index, future in enumerate(futures) if future in done and future.exception() is not None]
        if failed:
            broken = failed[0]  # nhiều mảnh hỏng cùng lúc: lấy mảnh đứng trước cho ổn định
            if relay is not None and broken > 0:
                for clip in clips[broken + 1:]:
                    clip.abort()
                relay.cut(broken)
                before = cls._wait(futures[:broken], remaining(), cancelled)
                earlier = [future for future in futures[:broken] if future in before and future.exception() is not None]
                if earlier:
                    raise earlier[0].exception()
                if len(before) < broken:
                    raise EdgeTimeout("Dịch vụ đọc to quá lâu không trả lời.")
            raise futures[broken].exception()
        if len(done) < len(futures):
            raise EdgeTimeout("Dịch vụ đọc to quá lâu không trả lời.")
        return [future.result() for future in futures]

    def synthesize(self, text: str, voice: str = DEFAULT_VOICE, *, rank: int = RANK_BACKGROUND, sink: StreamSink | None = None,
                   cancelled: Callable[[], bool] | None = None) -> Synthesis:
        """Đọc `text` bằng `voice` (mã đầy đủ, vd "vi-VN-HoaiMyNeural"): MP3 + các WordBoundary (ms từ đầu clip) + độ dài.
        Đoạn dài đọc theo `speech_pieces`, các mảnh song song (tối đa PIECE_PARALLEL, đoạn rank 0 tối đa TARGET_PIECES); mảnh ĐẦU TIÊN hỏng (theo thời gian, không đợi các mảnh trước nó)
        làm cả clip hỏng ngay với chính lỗi ấy - cùng các loại lỗi như khi đọc nối tiếp - và các mảnh còn lại bị cắt (điện thoại: EdgeTts.kt cùng luật).
        `rank`: số đoạn người nghe phải nghe trước clip này (0 = đang đứng chờ đúng nó: nhảy tới, đầu chương) - hết chỗ kết nối thì mảnh của clip gần người nghe hơn đi trước ([ConnectionSlots]).
        `sink`: phát luồng - tiếng và mốc đưa vào đó ngay khi chắc chắn, theo đúng thứ tự (xem [_Relay]); trả về vẫn đủ clip, y hệt bản không `sink`. Lỗi thì ném như cũ và sink không nhận gì thêm;
        riêng mảnh hỏng không phải mảnh đầu thì các mảnh trước nó phát hết trước khi ném ([_gather]).
        `cancelled`: người gọi bỏ clip được giữa lượt (Huỷ xuất sách nói) - hỏi mỗi CANCEL_POLL giây, đúng thì cắt ổ cắm mọi mảnh (như một mảnh hỏng, [_Clip.abort]) và ném
        [EdgeCancelled]; clip một mảnh cũng đọc ở luồng phụ để cắt được."""
        deadline = time.monotonic() + TOTAL_TIMEOUT
        pieces = speech_pieces(clean(text), rank)
        relay = _Relay(sink, pieces) if sink is not None else None
        if not pieces or (len(pieces) <= 1 and cancelled is None):
            if relay is not None:
                results = [self._speak_streamed(relay, index, voice, piece, deadline, None, rank) for index, piece in enumerate(pieces)]
            else:
                results = [self._speak_piece(voice, piece, deadline, rank=rank) for piece in pieces]
        else:
            clips = [_Clip() for _ in pieces]  # mỗi mảnh một chỗ cắt: phát luồng mà một mảnh hỏng thì chỉ cắt các mảnh sau nó
            pool = ThreadPoolExecutor(max_workers=min(piece_limit(rank), len(pieces)), thread_name_prefix="edge-piece")
            try:
                if relay is None:
                    futures = [pool.submit(self._speak_piece, voice, piece, deadline, clips[index], rank) for index, piece in enumerate(pieces)]
                else:
                    futures = [pool.submit(self._speak_streamed, relay, index, voice, piece, deadline, clips[index], rank) for index, piece in enumerate(pieces)]
                results = self._gather(futures, deadline, relay, clips, cancelled)
            finally:
                if relay is not None:
                    relay.stop()
                for clip in clips:
                    clip.abort()  # thành công thì không còn kết nối nào mở - vô hại
                pool.shutdown(wait=False, cancel_futures=True)
        audio = bytearray()
        boundaries: list[Boundary] = []
        for index, (data, found) in enumerate(results):
            if relay is None and index < len(results) - 1:
                data = trim_join_tail(data, pieces[index], found)  # cắt lặng đuôi trước khi bù mốc cho mảnh sau (phát luồng: mảnh đã cắt khi xong)
            # Mốc của mỗi mảnh tính từ đầu mảnh ấy: bù bằng độ dài audio các mảnh trước (CBR nên chính xác).
            shift_ms = len(audio) * 8 * 1000 // BITRATE_BPS
            boundaries += [Boundary(b.text, b.start_ms + shift_ms, b.end_ms + shift_ms, b.char) for b in found] if shift_ms else found
            audio += data
        if not audio:
            raise EdgeError("Dịch vụ đọc to không trả về âm thanh (chữ này có thể không đọc được).")
        duration = len(audio) * 8 * 1000 // BITRATE_BPS
        return Synthesis(bytes(audio), boundaries, max(duration, boundaries[-1].end_ms if boundaries else 0))
