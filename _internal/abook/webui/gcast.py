"""Phát sang Chromecast, Google TV, loa Nest bằng giao thức Cast (CASTV2) - 02-10, bên cạnh DLNA (cast.py).

Chủ sách muốn phát sang đúng loại thiết bị Google (Chromecast, TV Google TV, Nest Mini) mà DLNA không có. Mọi thứ còn lại
dùng chung với DLNA: phiên phát, vòng hỏi mỗi giây, lưu chỗ nghe, sang chương, cổng audio `CastMedia`. File này chỉ lo hai
việc: TÌM thiết bị (mDNS) và NÓI CHUYỆN với một thiết bị (`GoogleCast`, một `cast.Backend`).

Tìm: truy vấn mDNS `_googlecast._tcp.local` (PTR) gửi từ cổng TẠM với bit QU - theo RFC 6762 §6.7 (người hỏi "kế thừa", cổng
nguồn khác 5353) thiết bị trả THẲNG về cổng ấy, nên không bao giờ phải bind cổng 5353 giành với dịch vụ mDNS của Windows.
Gửi ra từng card mạng như SSDP. Thiết bị gói đủ trong một trả lời: PTR (tên), SRV (cổng), TXT (id, fn tên, md kiểu, ca khả
năng), A.

Nói: TLS tới cổng SRV (thường 8009) rồi CASTV2 - mỗi tin là 4 byte độ dài (big-endian) + một CastMessage protobuf viết tay
(vài trường, không cần thư viện protobuf). Kênh: connection (CONNECT / CLOSE), heartbeat (PING mỗi 5 giây), receiver (mở
ứng dụng "Default Media Receiver" CC1AD845), media (LOAD, PLAY, PAUSE, SEEK, STOP). Một luồng đọc cho mỗi thiết bị giữ bản
chụp tin mới nhất để `status()` không bao giờ đợi mạng; vẫn nhịp PING và khi đứt thì tự nối lại.

An toàn - trả lời mDNS là dữ liệu từ mạng LAN: chỉ nối tới ĐÚNG địa chỉ IP đã trả lời (A trong gói mà trỏ chỗ khác thì bỏ
thiết bị ấy), chỉ địa chỉ riêng / loopback; tin có trần 64 KiB; TLS không kiểm chứng chỉ (thiết bị Cast dùng chứng chỉ của Google
cấp theo máy, không có tên máy để kiểm) - cũng không gửi gì ngoài lệnh phát chương, và URL audio là cổng `CastMedia` của máy này
dưới mã ngẫu nhiên.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import select
import socket
import ssl
import struct
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from .cast import UPNP_ERRORS, Backend, CastError, Renderer, Status, Track, _clean, _lan, probe

MDNS_GROUP = ("224.0.0.251", 5353)
SERVICE = "_googlecast._tcp.local"
CAST_PORT = 8009
APP_ID = "CC1AD845"  # Default Media Receiver: phát file audio / video theo URL
NS_CONNECTION = "urn:x-cast:com.google.cast.tp.connection"
NS_HEARTBEAT = "urn:x-cast:com.google.cast.tp.heartbeat"
NS_RECEIVER = "urn:x-cast:com.google.cast.receiver"
NS_MEDIA = "urn:x-cast:com.google.cast.media"
MAX_FRAME = 64 * 1024

CONNECT_SECONDS = 4.0  # TLS tới thiết bị
REPLY_SECONDS = 8.0  # thiết bị trả lời một lệnh thường
LAUNCH_SECONDS = 15.0  # mở ứng dụng phát (TV đánh thức màn hình mất vài giây)
LOAD_SECONDS = 15.0  # đưa chương: thiết bị báo bắt đầu tải
HEARTBEAT_SECONDS = 5.0  # PING mỗi chừng ấy giây (thiết bị cũng bỏ người gửi im quá ~10 giây)
STATUS_SECONDS = 5.0  # hỏi lại trạng thái phát mỗi chừng ấy giây (giữa hai lần, vị trí ước theo đồng hồ)
DEAD_SECONDS = 15.0  # im lặng chừng ấy giây: coi như không trả lời, nối lại
RECONNECT_SECONDS = 4.0  # nối lại sau khi đứt: thử mỗi chừng ấy giây
TICK = 0.25  # luồng đọc tỉnh dậy mỗi chừng ấy giây để gửi PING, xem còn nghe được không

IDLE_REASONS = {"FINISHED": "finished", "ERROR": "error", "INTERRUPTED": "interrupted", "CANCELLED": "interrupted"}
PLAYER_STATES = {"PLAYING": "PLAYING", "PAUSED": "PAUSED_PLAYBACK", "BUFFERING": "TRANSITIONING", "LOADING": "TRANSITIONING"}


# ---- CastMessage (protobuf viết tay) ---------------------------------------------------------------------------------


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        low = value & 0x7F
        value >>= 7
        out.append(low | (0x80 if value else 0))
        if not value:
            return bytes(out)


def _text(number: int, value: str) -> bytes:
    data = value.encode("utf-8")
    return _varint(number << 3 | 2) + _varint(len(data)) + data


@dataclass(frozen=True)
class Message:
    source: str
    destination: str
    namespace: str
    payload: str


def encode(source: str, destination: str, namespace: str, payload: str) -> bytes:
    """CastMessage: 1 protocol_version = 0 (CASTV2_1_0), 2 source_id, 3 destination_id, 4 namespace, 5 payload_type = 0
    (STRING), 6 payload_utf8."""
    return (_varint(1 << 3) + _varint(0) + _text(2, source) + _text(3, destination) + _text(4, namespace)
            + _varint(5 << 3) + _varint(0) + _text(6, payload))


def frame(message: bytes) -> bytes:
    return struct.pack(">I", len(message)) + message


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = shift = 0
    while True:
        if offset >= len(data) or shift > 63:
            raise CastError("thiết bị trả lời lạ")
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7


def decode(data: bytes) -> Message:
    """Đọc một CastMessage: biết varint và chuỗi (length-delimited), trường lạ thì bỏ qua; payload nhị phân thành rỗng."""
    fields: dict[int, bytes | int] = {}
    offset = 0
    while offset < len(data):
        key, offset = _read_varint(data, offset)
        number, wire = key >> 3, key & 7
        if wire == 0:
            value, offset = _read_varint(data, offset)
            fields[number] = value
        elif wire == 2:
            size, offset = _read_varint(data, offset)
            if offset + size > len(data):
                raise CastError("thiết bị trả lời lạ")
            fields[number] = data[offset:offset + size]
            offset += size
        elif wire == 1 and offset + 8 <= len(data):
            offset += 8
        elif wire == 5 and offset + 4 <= len(data):
            offset += 4
        else:
            raise CastError("thiết bị trả lời lạ")

    def string(number: int) -> str:
        value = fields.get(number, b"")
        return value.decode("utf-8", "replace") if isinstance(value, bytes) else ""

    return Message(string(2), string(3), string(4), string(6) if fields.get(5, 0) == 0 else "")


class Framer:
    """Ráp các tin từ luồng byte: 4 byte độ dài rồi tin; độ dài quá MAX_FRAME là thiết bị lạ - CastError."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[bytes]:
        self._buffer += data
        frames: list[bytes] = []
        while len(self._buffer) >= 4:
            size = struct.unpack(">I", self._buffer[:4])[0]
            if size > MAX_FRAME:
                raise CastError("thiết bị trả lời lạ")
            if len(self._buffer) < 4 + size:
                break
            frames.append(bytes(self._buffer[4:4 + size]))
            del self._buffer[:4 + size]
        return frames


# ---- tìm thiết bị (mDNS) -------------------------------------------------------------------------------------------------


def query() -> bytes:
    """Hỏi PTR `_googlecast._tcp.local` với bit QU (0x8000): trả lời về thẳng người hỏi."""
    name = b"".join(bytes([len(label)]) + label.encode("ascii") for label in SERVICE.split(".")) + b"\x00"
    return struct.pack(">HHHHHH", 0, 0, 1, 0, 0, 0) + name + struct.pack(">HH", 12, 0x8000 | 1)


def _name(data: bytes, offset: int) -> tuple[str, int]:
    """Tên DNS (có nén) tại `offset` -> (tên, vị trí sau tên ở chỗ gốc). Con trỏ chỉ được trỏ lùi: không thể vòng."""
    labels: list[str] = []
    after = -1
    while True:
        if offset >= len(data):
            raise ValueError("cụt")
        size = data[offset]
        if size == 0:
            return ".".join(labels), after if after >= 0 else offset + 1
        if size & 0xC0 == 0xC0:
            if offset + 1 >= len(data):
                raise ValueError("cụt")
            pointer = (size & 0x3F) << 8 | data[offset + 1]
            if pointer >= offset:
                raise ValueError("con trỏ tới trước")
            after = after if after >= 0 else offset + 2
            offset = pointer
            continue
        if size & 0xC0 or offset + 1 + size > len(data):
            raise ValueError("nhãn hỏng")
        labels.append(data[offset + 1:offset + 1 + size].decode("utf-8", "replace"))
        offset += 1 + size
        if len(labels) > 40:
            raise ValueError("tên quá dài")


@dataclass(frozen=True)
class Found:
    """Một thiết bị Cast đã trả lời mDNS: `host` là địa chỉ đã gửi gói trả lời."""

    host: str
    port: int
    instance: str
    txt: tuple[tuple[str, str], ...]

    def field(self, key: str) -> str:
        return next((value for name, value in self.txt if name == key), "")


def parse(data: bytes, source: str) -> list[Found]:
    """Thiết bị Cast trong một gói trả lời mDNS từ `source`. Gói hỏng, không phải trả lời, hay địa chỉ A của máy trỏ chỗ khác
    `source` thì bỏ - mDNS là dữ liệu từ mạng, không để một máy lạ chỉ máy này sang địa chỉ nó chọn."""
    if len(data) < 12:
        return []
    try:
        _ident, flags, questions, answers, authority, additional = struct.unpack(">HHHHHH", data[:12])
        if not flags & 0x8000 or questions > 8 or answers + authority + additional > 64:
            return []
        offset = 12
        for _ in range(questions):
            _label, offset = _name(data, offset)
            offset += 4
        pointers: list[str] = []
        services: dict[str, tuple[int, str]] = {}
        texts: dict[str, tuple[tuple[str, str], ...]] = {}
        addresses: dict[str, set[str]] = {}
        for _ in range(answers + authority + additional):
            label, offset = _name(data, offset)
            kind, _klass, _ttl, size = struct.unpack(">HHIH", data[offset:offset + 10])
            offset += 10
            if offset + size > len(data):
                return []
            key = label.lower()
            if kind == 12:
                if key == SERVICE:
                    pointers.append(_name(data, offset)[0])
            elif kind == 33 and size >= 7:
                services[key] = (struct.unpack(">H", data[offset + 4:offset + 6])[0], _name(data, offset + 6)[0].lower())
            elif kind == 16:
                texts[key] = _txt(data[offset:offset + size])
            elif kind == 1 and size == 4:
                addresses.setdefault(key, set()).add(socket.inet_ntoa(data[offset:offset + 4]))
            offset += size
    except (ValueError, struct.error, IndexError):
        return []
    found: list[Found] = []
    for instance in pointers:
        key = instance.lower()
        port, target = services.get(key, (CAST_PORT, ""))
        if target and addresses.get(target) and source not in addresses[target]:
            continue  # A trỏ sang máy khác: thiết bị ấy không phải máy vừa trả lời
        if 0 < port < 65536:
            found.append(Found(source, port, instance, texts.get(key, ())))
    return found


def _txt(data: bytes) -> tuple[tuple[str, str], ...]:
    out: list[tuple[str, str]] = []
    offset = 0
    while offset < len(data):
        size = data[offset]
        item = data[offset + 1:offset + 1 + size].decode("utf-8", "replace")
        offset += 1 + size
        name, _equals, value = item.partition("=")
        if name:
            out.append((name.lower(), value))
    return tuple(out)


def search(timeout: float = 2.0, *, addresses: Iterable[str] | None = None,
           targets: Iterable[tuple[str, int]] = ()) -> list[Found]:
    """Hỏi mDNS ra từng card mạng (multicast 224.0.0.251, TTL 255) và thẳng tới `targets` (bài thử, thiết bị giả); gom trả
    lời trong `timeout` giây. Cổng nguồn tạm - không bao giờ 5353."""
    def accept(data: bytes, source: str) -> list[tuple[Any, Any]]:
        return [((item.host, item.instance), item) for item in parse(data, source)] if _lan(source) else []

    return [item for _key, item in probe(query(), MDNS_GROUP, timeout, accept, addresses=addresses, targets=targets,
                                         ttl=255)]


def describe(found: Found) -> Renderer | None:
    """Thiết bị phát từ trả lời mDNS: mã 12 hex theo `id` trong TXT (như mã DLNA theo UDN), tên `fn`, kiểu theo `ca` (bit 1 =
    có hình -> TV, còn lại loa). None nếu địa chỉ không ở trong nhà."""
    if not _lan(found.host):
        return None
    label = found.instance.split("." + SERVICE)[0] if found.instance.lower().endswith("." + SERVICE) else found.instance
    capabilities = found.field("ca")
    name = _clean(found.field("fn") or label, 80) or found.host
    return Renderer(id=hashlib.sha1((found.field("id") or label).encode("utf-8")).hexdigest()[:12], name=name,
                    kind="tv" if capabilities.isdigit() and int(capabilities) & 1 else "speaker", host=found.host,
                    protocol="gcast", port=found.port)


def discover(timeout: float = 2.0, *, addresses: Iterable[str] | None = None,
             targets: Iterable[tuple[str, int]] = ()) -> list[Renderer]:
    """`search` rồi `describe` - mỗi thiết bị một lần (mã trùng thì giữ cái thấy đầu)."""
    seen: dict[str, Renderer] = {}
    for found in search(timeout, addresses=addresses, targets=targets):
        renderer = describe(found)
        if renderer is not None:
            seen.setdefault(renderer.id, renderer)
    return list(seen.values())


# ---- nói chuyện với một thiết bị --------------------------------------------------------------------------------------


class GoogleCast(Backend):
    """Một thiết bị Cast. Kết nối mở ở lần `load` đầu và giữ tới `close`; luồng đọc cache MEDIA_STATUS / RECEIVER_STATUS.

    Vòng đời: CONNECT receiver-0 -> GET_STATUS -> LAUNCH (nếu Default Media Receiver chưa chạy) -> CONNECT transportId ->
    LOAD (có vị trí bắt đầu - không tua sau). Bị chiếm máy = ứng dụng của ta biến khỏi RECEIVER_STATUS, MEDIA_STATUS có
    contentId không phải của ta hay mediaSessionId mới, IDLE INTERRUPTED / CANCELLED mà ta không gây ra, hay đối phương CLOSE."""

    def __init__(self, renderer: Renderer) -> None:
        self.host, self.port = renderer.host, renderer.port or CAST_PORT
        self._sender = f"sender-{secrets.token_hex(4)}"
        self._cond = threading.Condition()
        self._send_lock = threading.Lock()  # một khung tin gửi xong rồi mới tới khung khác
        self._io = threading.Lock()  # SSL không cho đọc và ghi cùng lúc từ hai luồng: mỗi lần chạm vào ổ cắm giữ khoá này
        self._sock: ssl.SSLSocket | None = None
        self._thread: threading.Thread | None = None
        self._closed = False
        self._wake = threading.Event()
        self._connected = False
        self._heard = 0.0  # lần cuối nhận được tin (bất kỳ) từ thiết bị
        self._attached = 0.0  # lần nối gần nhất
        self._ids = 0
        self._inbox: dict[int, list[dict[str, Any]]] = {}
        # ứng dụng nhận
        self._session_id = ""
        self._transport_id = ""
        self._transport_open = False
        self._launched = False  # ứng dụng do máy này mở: lúc trả máy thì đóng nó
        self._releasing = False
        # đang phát
        self._loading = False
        self._adopted = False  # đã nhận trả lời cho LOAD đang chờ
        self._pending = ("", "", None)  # (mã trong URL, URL, mediaSessionId cũ) của LOAD đang chờ
        self._stopping = False
        self._interrupted = False
        self._msid: int | None = None
        self._token = ""
        self._content = ""
        self._duration = 0.0
        self._entry: dict[str, Any] = {}
        self._entry_at = 0.0

    # -- kết nối ------------------------------------------------------------------------------------------------

    def _dial(self) -> ssl.SSLSocket:
        if not _lan(self.host):
            raise CastError("địa chỉ thiết bị không ở trong nhà")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        try:
            raw = socket.create_connection((self.host, self.port), timeout=CONNECT_SECONDS)
            raw.settimeout(CONNECT_SECONDS)
            sock = context.wrap_socket(raw)
        except OSError as error:  # kể cả ssl.SSLError
            raise CastError("không nối được - thiết bị đã tắt hay rời mạng?") from error
        sock.settimeout(0.0)  # từ đây không chặn: `_read` / `_write` tự đợi bằng select, ngoài khoá `_io`
        return sock

    def _attach(self, sock: ssl.SSLSocket, *, ask: bool) -> None:
        with self._cond:
            if self._closed:  # đóng giữa lúc đang nối lại
                sock.close()
                raise CastError("đã đóng kết nối với thiết bị")
            self._sock, self._connected, self._attached = sock, True, time.monotonic()
            if not ask:  # nối lại thì `_heard` giữ nguyên: thiết bị chưa nói gì thì vẫn chưa nghe được
                self._heard = self._attached
            self._transport_open = False
            self._cond.notify_all()
        self._send(NS_CONNECTION, "receiver-0", {"type": "CONNECT"})
        if ask:  # nối lại giữa phiên: hỏi xem ứng dụng của ta còn không
            self._send(NS_RECEIVER, "receiver-0", {"type": "GET_STATUS", "requestId": self._next()})

    def _ready(self) -> None:
        """Mở kết nối, mở ứng dụng phát và nối vào nó (nếu chưa)."""
        with self._cond:
            if self._closed:
                raise CastError("đã đóng kết nối với thiết bị")
            first = self._thread is None
        if first:
            self._attach(self._dial(), ask=False)
            self._thread = threading.Thread(target=self._run, name="gcast-reader", daemon=True)
            self._thread.start()
        if self._session_id and self._transport_open:
            return
        if not self._connected:
            raise CastError("mất kết nối - thiết bị đã tắt hay rời mạng?")
        replies = self._ask(NS_RECEIVER, "receiver-0", {"type": "GET_STATUS"}, timeout=REPLY_SECONDS,
                            accept=lambda replies: any(reply.get("type") == "RECEIVER_STATUS" for reply in replies))
        app = self._app(replies)
        if app is None:
            replies = self._ask(NS_RECEIVER, "receiver-0", {"type": "LAUNCH", "appId": APP_ID}, timeout=LAUNCH_SECONDS,
                                accept=self._launched_in)
            app = self._app(replies)
            self._launched = True
        if app is None or not app.get("transportId"):
            raise CastError("thiết bị không mở được trình phát")
        with self._cond:
            self._session_id, self._transport_id, self._transport_open = app["sessionId"], app["transportId"], True
        self._send(NS_CONNECTION, self._transport_id, {"type": "CONNECT"})

    @staticmethod
    def _app(replies: list[dict[str, Any]]) -> dict[str, Any] | None:
        for reply in reversed(replies):
            for app in (reply.get("status") or {}).get("applications") or []:
                if isinstance(app, dict) and app.get("appId") == APP_ID and app.get("sessionId"):
                    return app
        return None

    def _launched_in(self, replies: list[dict[str, Any]]) -> bool:
        for reply in replies:
            if reply.get("type") in ("LAUNCH_ERROR", "INVALID_REQUEST"):
                raise CastError("thiết bị không mở được trình phát")
        app = self._app(replies)
        return app is not None and bool(app.get("transportId"))

    # -- luồng đọc ----------------------------------------------------------------------------------------------

    def _run(self) -> None:
        """Đọc tin, trả PONG, gửi PING; đứt hay im quá DEAD_SECONDS thì nối lại tới khi được hay bị đóng."""
        while not self._closed:
            sock = self._sock
            if sock is not None:
                self._serve(sock)
            with self._cond:
                self._connected = False
                self._cond.notify_all()
            try:
                sock and sock.close()
            except OSError:
                pass
            while not self._closed:
                self._wake.wait(RECONNECT_SECONDS)
                try:
                    self._attach(self._dial(), ask=True)
                    break
                except CastError:
                    continue

    def _serve(self, sock: ssl.SSLSocket) -> None:
        framer = Framer()
        ping = status = time.monotonic()
        try:
            while not self._closed and self._sock is sock:
                now = time.monotonic()
                if now - max(self._heard, self._attached) > DEAD_SECONDS:
                    return
                if now - ping >= HEARTBEAT_SECONDS:
                    ping = now
                    self._send(NS_HEARTBEAT, "receiver-0", {"type": "PING"})
                if now - status >= STATUS_SECONDS and self._transport_open and self._msid is not None:
                    status = now
                    self._send(NS_MEDIA, self._transport_id, {"type": "GET_STATUS", "requestId": self._next()})
                data = self._read(sock)
                if data is None:
                    continue
                if not data:
                    return
                for raw in framer.feed(data):
                    self._handle(decode(raw))
        except (OSError, ValueError, CastError):  # ValueError: ổ cắm đã đóng từ luồng khác
            return

    def _read(self, sock: ssl.SSLSocket) -> bytes | None:
        """Đợi tới TICK giây cho dữ liệu: bytes (rỗng = thiết bị đóng), None = chưa có gì."""
        with self._io:
            waiting = sock.pending() > 0
        if not waiting and not select.select([sock], [], [], TICK)[0]:
            return None
        try:
            with self._io:
                return sock.recv(65536)
        except (ssl.SSLWantReadError, ssl.SSLWantWriteError, BlockingIOError):
            return None  # mới tới một phần bản ghi TLS (hay bản ghi nội bộ như vé phiên TLS 1.3)

    def _write(self, sock: ssl.SSLSocket, data: bytes) -> None:
        """Gửi hết `data` (gọi khi giữ `_send_lock`); quá REPLY_SECONDS mà thiết bị không nhận thì OSError."""
        view = memoryview(data)
        deadline = time.monotonic() + REPLY_SECONDS
        while view:
            try:
                with self._io:
                    sent = sock.send(view)
            except (ssl.SSLWantReadError, ssl.SSLWantWriteError, BlockingIOError):
                sent = 0
            view = view[sent:]
            if view:
                if time.monotonic() > deadline:
                    raise OSError("thiết bị không nhận")
                select.select([sock], [sock], [], 0.05)

    def _handle(self, message: Message) -> None:
        with self._cond:
            self._heard = time.monotonic()
        try:
            payload = json.loads(message.payload) if message.payload else {}
        except ValueError:
            return
        if not isinstance(payload, dict):
            return
        kind = payload.get("type")
        if message.namespace == NS_HEARTBEAT:
            if kind == "PING":
                try:
                    self._send(NS_HEARTBEAT, message.source, {"type": "PONG"})
                except CastError:
                    pass
            return
        if message.namespace == NS_CONNECTION:
            if kind == "CLOSE" and self._session_id and not self._releasing and message.source in (
                    self._transport_id, "receiver-0"):
                with self._cond:
                    self._interrupted = True  # thiết bị đóng nối với ta: máy khác chiếm, hay ứng dụng đã tắt
                    self._cond.notify_all()
            return
        request = payload.get("requestId")
        reattach = False
        with self._cond:
            if isinstance(request, int) and request in self._inbox:
                self._inbox[request].append(payload)
            if message.namespace == NS_RECEIVER and kind == "RECEIVER_STATUS":
                reattach = self._on_receiver(payload.get("status") or {})
            elif message.namespace == NS_MEDIA and kind == "MEDIA_STATUS":
                for entry in payload.get("status") or []:
                    if isinstance(entry, dict):
                        self._on_media(entry)
            self._cond.notify_all()
        if reattach:  # nối lại sau khi đứt và ứng dụng của ta vẫn còn: nối vào nó, hỏi lại đang phát gì
            try:
                self._send(NS_CONNECTION, self._transport_id, {"type": "CONNECT"})
                self._send(NS_MEDIA, self._transport_id, {"type": "GET_STATUS", "requestId": self._next()})
            except CastError:
                pass

    def _on_receiver(self, status: dict[str, Any]) -> bool:
        """Gọi khi giữ khoá. True: phải nối lại vào ứng dụng của ta."""
        if not self._session_id or self._releasing:
            return False
        ours = next((app for app in status.get("applications") or []
                     if isinstance(app, dict) and app.get("sessionId") == self._session_id), None)
        if ours is None:
            self._interrupted = True  # ứng dụng của ta không còn: có người mở app khác hay tắt trên TV
            return False
        if not self._transport_open:
            self._transport_open = True
            return bool(self._transport_id)
        return False

    def _on_media(self, entry: dict[str, Any]) -> None:
        """Gọi khi giữ khoá. Tin về phiên phát của ta thì ghi lại; về phiên khác thì là bị chiếm máy."""
        msid = entry.get("mediaSessionId")
        state = entry.get("playerState")
        if self._loading:  # chờ trả lời LOAD của ta: tin về bài cũ (còn phát, hay IDLE INTERRUPTED) không đáng kể
            token, url, previous = self._pending
            content = (entry.get("media") or {}).get("contentId") or url
            if (isinstance(msid, int) and msid != previous and token in content
                    and (state != "IDLE" or entry.get("idleReason") == "ERROR")):
                self._msid, self._entry, self._entry_at = msid, entry, time.monotonic()
                self._token, self._content, self._adopted, self._interrupted = token, url, True, False
                self._duration = 0.0
                self._note(entry)
            return
        if self._msid is None or self._interrupted:
            return
        content = (entry.get("media") or {}).get("contentId") or ""
        if content and self._token not in content:
            self._interrupted = True
            self._content = content
            return
        if msid != self._msid:
            if isinstance(msid, int) and msid > self._msid:
                self._interrupted = True  # có phiên phát mới mà không phải của ta
            return
        self._entry, self._entry_at = entry, time.monotonic()
        self._note(entry)
        if state == "IDLE" and entry.get("idleReason") in ("INTERRUPTED", "CANCELLED") and not self._stopping:
            self._interrupted = True

    def _note(self, entry: dict[str, Any]) -> None:
        media = entry.get("media") or {}
        if isinstance(media.get("duration"), (int, float)):
            self._duration = float(media["duration"])
        if media.get("contentId"):
            self._content = media["contentId"]

    # -- gửi / hỏi ----------------------------------------------------------------------------------------------

    def _next(self) -> int:
        with self._cond:
            self._ids += 1
            return self._ids

    def _send(self, namespace: str, destination: str, body: dict[str, Any]) -> None:
        data = frame(encode(self._sender, destination, namespace, json.dumps(body, separators=(",", ":"))))
        with self._send_lock:
            sock = self._sock
            if sock is None or self._closed:
                raise CastError("mất kết nối - thiết bị đã tắt hay rời mạng?")
            try:
                self._write(sock, data)
            except (OSError, ValueError) as error:
                raise CastError("không trả lời - thiết bị đã tắt hay rời mạng?") from error

    def _ask(self, namespace: str, destination: str, body: dict[str, Any], *, timeout: float,
             accept: Callable[[list[dict[str, Any]]], bool], request: int | None = None) -> list[dict[str, Any]]:
        """Gửi lệnh có requestId rồi đợi tới khi `accept(các trả lời đã nhận)` True. `accept` ném CastError để báo lỗi."""
        request = request or self._next()
        with self._cond:
            self._inbox[request] = []
        try:
            self._send(namespace, destination, {**body, "requestId": request})
            deadline = time.monotonic() + timeout
            with self._cond:
                while True:
                    replies = list(self._inbox[request])
                    if accept(replies):
                        return replies
                    left = deadline - time.monotonic()
                    if self._closed or not self._connected:
                        raise CastError("mất kết nối - thiết bị đã tắt hay rời mạng?")
                    if left <= 0:
                        raise CastError("không trả lời - thiết bị đã tắt hay rời mạng?")
                    self._cond.wait(min(left, TICK))
        finally:
            with self._cond:
                self._inbox.pop(request, None)

    def _media(self, kind: str, timeout: float = REPLY_SECONDS, **extra: Any) -> None:
        with self._cond:
            msid = self._msid
        if msid is None or not self._transport_open:
            raise CastError(UPNP_ERRORS[702])

        def accept(replies: list[dict[str, Any]]) -> bool:
            for reply in replies:
                if reply.get("type") in ("INVALID_REQUEST", "LOAD_FAILED"):
                    raise CastError(UPNP_ERRORS[402])
            return any(reply.get("type") == "MEDIA_STATUS" for reply in replies)

        self._ask(NS_MEDIA, self._transport_id, {"type": kind, "mediaSessionId": msid, **extra}, timeout=timeout,
                  accept=accept)

    # -- Backend ------------------------------------------------------------------------------------------------

    def load(self, track: Track, seconds: float) -> float:
        self._ready()
        media: dict[str, Any] = {"contentId": track.url, "contentType": track.mime, "streamType": "BUFFERED",
                                 "metadata": {"metadataType": 3, "title": track.title, "albumName": track.album}}
        if track.art:
            media["metadata"]["images"] = [{"url": track.art}]
        request = self._next()
        with self._cond:
            self._loading, self._adopted, self._stopping = True, False, False
            self._pending = (track.url.rsplit("/", 1)[-1].split(".", 1)[0], track.url, self._msid)

        def accept(replies: list[dict[str, Any]]) -> bool:
            for reply in replies:
                if reply.get("type") == "LOAD_FAILED":
                    raise CastError(UPNP_ERRORS[716])
                if reply.get("type") in ("INVALID_REQUEST", "LOAD_CANCELLED"):
                    raise CastError(UPNP_ERRORS[402])
            if self._adopted and self._entry.get("idleReason") == "ERROR":
                raise CastError(UPNP_ERRORS[716])
            return self._adopted

        try:
            self._ask(NS_MEDIA, self._transport_id,
                      {"type": "LOAD", "sessionId": self._session_id, "media": media, "autoplay": True,
                       "currentTime": round(float(seconds), 2)}, timeout=LOAD_SECONDS, accept=accept, request=request)
        finally:
            with self._cond:
                self._loading = False
        return float(seconds)

    def play(self) -> None:
        self._media("PLAY")

    def pause(self) -> bool:
        self._media("PAUSE")
        return False

    def stop(self, timeout: float = 5.0) -> None:
        with self._cond:
            self._stopping = True
        self._media("STOP", timeout)

    def seek(self, seconds: float) -> None:
        self._media("SEEK", currentTime=round(float(seconds), 2))

    def status(self) -> Status:
        with self._cond:
            now = time.monotonic()
            if self._closed or not self._connected or now - self._heard > DEAD_SECONDS:
                raise CastError("không trả lời - thiết bị đã tắt hay rời mạng?")
            entry, at = self._entry, self._entry_at
            if self._msid is None or not entry:
                return Status("NO_MEDIA_PRESENT", 0.0, 0.0, "", "interrupted" if self._interrupted else "")
            raw = entry.get("playerState")
            state = PLAYER_STATES.get(raw, "STOPPED")
            position = float(entry.get("currentTime") or 0.0)
            if state == "PLAYING":
                position += max(0.0, now - at) * float(entry.get("playbackRate") or 1.0)
                if self._duration > 0:
                    position = min(position, self._duration)
            reason = ""
            if self._interrupted:
                state, reason = "STOPPED", "interrupted"
            elif raw == "IDLE":
                reason = IDLE_REASONS.get(entry.get("idleReason") or "", "")
                if reason == "interrupted" and self._stopping:
                    reason = ""
            return Status(state, position, self._duration, self._content, reason)

    def close(self, release: bool = False) -> None:
        with self._cond:
            if self._closed:
                return
            leave = release and self._launched and bool(self._session_id) and self._connected
            self._releasing = True
        if leave:  # ứng dụng do ta mở: đóng nó, màn hình TV / loa về như cũ
            try:
                self._ask(NS_RECEIVER, "receiver-0", {"type": "STOP", "sessionId": self._session_id}, timeout=2.0,
                          accept=lambda replies: any(reply.get("type") == "RECEIVER_STATUS" for reply in replies))
            except CastError:
                pass
        with self._cond:
            self._closed = True
            sock, self._sock, self._connected = self._sock, None, False
            self._cond.notify_all()
        self._wake.set()
        if sock is not None:
            try:
                with self._send_lock:
                    for destination in (self._transport_id, "receiver-0"):
                        if destination:
                            self._write(sock, frame(encode(self._sender, destination, NS_CONNECTION, '{"type":"CLOSE"}')))
            except (OSError, ValueError):
                pass
            try:
                sock.close()
            except OSError:
                pass
