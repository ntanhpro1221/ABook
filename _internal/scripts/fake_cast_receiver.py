"""Chromecast / Google TV / loa Nest giả lập để thử "Phát trên Google Cast" khi không có thiết bị thật - 02-10.

Chỉ dùng thư viện chuẩn (và `abook.webui.tls` để có chứng chỉ TLS - cũng chỉ thư viện chuẩn): `python fake_cast_receiver.py
--interface 192.168.0.77` chạy được trên máy khác trong mạng. Nó trả lời mDNS `_googlecast._tcp.local` (multicast 5353, hoặc
một cổng UDP riêng cho bài thử), nghe CASTV2 qua TLS và nói đủ bốn kênh (connection, heartbeat, receiver, media) như
Default Media Receiver. "Phát" là TẢI file từ đúng URL được đưa (kiểm máy tính phục vụ đúng, có CORS) - KHÔNG bao giờ giải
mã hay phát audio - rồi cho vị trí chạy theo đồng hồ (`speed` > 1 để bài thử không đợi hết chương), hết thì IDLE / FINISHED.

Chiêu trò cho bài thử: `takeover(url)` (máy khác phát thứ khác), `stop_app()` (bấm dừng trên TV), `interrupt()`, `sleep()` /
`wake()` (thiết bị tắt nguồn: nối không được, đang nối thì đứt), `refuse_load` (LOAD_FAILED), `no_heartbeat_reply` (treo:
không trả lời tin nào, không đẩy gì). Ghi lại mọi lệnh (`actions` - "kênh.LOẠI", nội dung) và mọi lần tải (`fetches`).
"""
from __future__ import annotations

import argparse
import json
import re
import select
import socket
import ssl
import struct
import sys
import threading
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from abook.webui import tls

MDNS_GROUP = "224.0.0.251"
SERVICE = "_googlecast._tcp.local"
APP_ID = "CC1AD845"
NS = {
    "connection": "urn:x-cast:com.google.cast.tp.connection",
    "heartbeat": "urn:x-cast:com.google.cast.tp.heartbeat",
    "receiver": "urn:x-cast:com.google.cast.receiver",
    "media": "urn:x-cast:com.google.cast.media",
}
SHORT = {value: key for key, value in NS.items()}


# ---- CastMessage, viết lại độc lập với abook/webui/gcast.py (để bài thử so hai bên) --------------------------------


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        low = value & 0x7F
        value >>= 7
        out.append(low | (0x80 if value else 0))
        if not value:
            return bytes(out)


def _pack(source: str, destination: str, namespace: str, payload: str) -> bytes:
    def text(number: int, value: str) -> bytes:
        data = value.encode("utf-8")
        return _varint(number << 3 | 2) + _varint(len(data)) + data

    body = (b"\x08\x00" + text(2, source) + text(3, destination) + text(4, namespace) + b"\x28\x00" + text(6, payload))
    return struct.pack(">I", len(body)) + body


def _unpack(body: bytes) -> tuple[str, str, str, str]:
    fields: dict[int, bytes] = {}
    at = 0

    def varint() -> int:
        nonlocal at
        value = shift = 0
        while True:
            byte = body[at]
            at += 1
            value |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return value
            shift += 7

    while at < len(body):
        key = varint()
        if key & 7 == 0:
            varint()
        elif key & 7 == 2:
            size = varint()
            fields[key >> 3] = body[at:at + size]
            at += size
        else:
            raise ValueError("kiểu trường lạ")
    return tuple(fields.get(number, b"").decode("utf-8") for number in (2, 3, 4, 6))  # type: ignore[return-value]


def _ptr(offset: int) -> bytes:
    return struct.pack(">H", 0xC000 | offset)  # con trỏ nén tên DNS


class _Client:
    """Một người điều khiển đang nối vào thiết bị. Ổ cắm không chặn; đọc và ghi qua một khoá vì SSL không cho hai luồng chạm
    vào cùng một ổ cắm cùng lúc (luồng đọc của người này, luồng đẩy tin trạng thái)."""

    def __init__(self, sock: ssl.SSLSocket) -> None:
        self.sock = sock
        self.sender = ""
        self.connected: set[str] = set()  # kết nối ảo: "receiver-0", transportId
        self.lock = threading.Lock()  # một khung tin gửi xong rồi mới tới khung khác
        self.io = threading.Lock()
        self.buffer = bytearray()

    def read(self) -> bytes | None:
        """Đợi tới 0,2 giây: bytes (rỗng = người kia đóng), None = chưa có gì."""
        with self.io:
            waiting = self.sock.pending() > 0
        if not waiting and not select.select([self.sock], [], [], 0.2)[0]:
            return None
        try:
            with self.io:
                return self.sock.recv(65536)
        except (ssl.SSLWantReadError, ssl.SSLWantWriteError, BlockingIOError):
            return None

    def frames(self, data: bytes) -> list[bytes]:
        self.buffer += data
        out: list[bytes] = []
        while len(self.buffer) >= 4:
            size = struct.unpack(">I", self.buffer[:4])[0]
            if len(self.buffer) < 4 + size:
                break
            out.append(bytes(self.buffer[4:4 + size]))
            del self.buffer[:4 + size]
        return out

    def send(self, source: str, namespace: str, payload: dict[str, Any]) -> None:
        view = memoryview(_pack(source, self.sender, namespace, json.dumps(payload, separators=(",", ":"))))
        deadline = time.monotonic() + 5
        try:
            with self.lock:
                while view and time.monotonic() < deadline:
                    try:
                        with self.io:
                            sent = self.sock.send(view)
                    except (ssl.SSLWantReadError, ssl.SSLWantWriteError, BlockingIOError):
                        sent = 0
                    view = view[sent:]
                    if view:
                        select.select([self.sock], [self.sock], [], 0.05)
        except (OSError, ValueError):
            pass


class FakeCastReceiver:
    def __init__(self, name: str = "Loa Nest thử", *, host: str = "127.0.0.1", speed: float = 1.0, duration: float = 10.0,
                 video: bool = False, model: str = "Chromecast", fetch_bytes: int | None = None,
                 buffer_seconds: float = 0.05) -> None:
        self.name, self.host, self.speed, self.duration = name, host, speed, duration
        self.video, self.model, self.fetch_bytes, self.buffer_seconds = video, model, fetch_bytes, buffer_seconds
        self.device_id = uuid.uuid4().hex
        self.advertised_host = host  # địa chỉ A trong trả lời mDNS (bài thử đặt chỗ khác để xem máy tính có bị lừa không)
        self.refuse_load = False
        self.no_heartbeat_reply = False
        self.fail_fetch = False  # không tải được URL (tường lửa chặn): LOAD vẫn nhận, rồi IDLE / ERROR
        self.actions: list[tuple[str, dict[str, Any]]] = []
        self.fetches: list[dict[str, Any]] = []
        self.pings = 0
        self.connections = 0
        self._lock = threading.RLock()
        self._clients: list[_Client] = []
        self._asleep = False
        self._app: dict[str, Any] | None = None
        self._apps = 0
        self._msid = 0
        self._content = ""
        self._type = ""
        self._metadata: dict[str, Any] = {}
        self._state = "IDLE"
        self._idle = ""
        self._offset = 0.0
        self._since = 0.0
        self._loaded = 0.0
        self._autoplay = True
        self._listener: socket.socket | None = None
        self._udp: socket.socket | None = None
        self._stopping = threading.Event()

    # -- máy chủ ------------------------------------------------------------------------------------------------

    def start(self, *, mdns_port: int | None = 0, multicast: bool = False, interface: str = "") -> FakeCastReceiver:
        """`mdns_port` 0: cổng UDP ngẫu nhiên trên `host` (bài thử gửi truy vấn thẳng tới); `multicast`: nghe 5353 như
        thiết bị thật, tham gia nhóm trên card `interface`."""
        context = tls.ephemeral().server_context()
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self.host, 0))
        listener.listen(8)
        listener.settimeout(0.3)
        self._listener = listener
        threading.Thread(target=self._accept, args=(context,), daemon=True).start()
        if multicast:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            sock.bind(("", 5353))
            membership = struct.pack("4s4s", socket.inet_aton(MDNS_GROUP), socket.inet_aton(interface or self.host))
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
            self._udp = sock
        elif mdns_port is not None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.bind((self.host, mdns_port))
            self._udp = sock
        if self._udp is not None:
            self._udp.settimeout(0.5)
            threading.Thread(target=self._answer, daemon=True).start()
        threading.Thread(target=self._tick, daemon=True).start()
        return self

    @property
    def port(self) -> int:
        assert self._listener is not None
        return self._listener.getsockname()[1]

    @property
    def mdns_address(self) -> tuple[str, int]:
        assert self._udp is not None
        return self.host, self._udp.getsockname()[1]

    def stop(self) -> None:
        self._stopping.set()
        self._drop_all()
        for sock in (self._listener, self._udp):
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass

    def _accept(self, context: ssl.SSLContext) -> None:
        while not self._stopping.is_set():
            try:
                raw, _address = self._listener.accept()  # type: ignore[union-attr]
            except (TimeoutError, socket.timeout):  # noqa: UP041
                continue
            except OSError:
                return
            threading.Thread(target=self._serve, args=(raw, context), daemon=True).start()

    def _serve(self, raw: socket.socket, context: ssl.SSLContext) -> None:
        if self._asleep:
            raw.close()  # tắt nguồn: nối được TCP rồi cụt - bắt tay TLS hỏng
            return
        client = None
        try:
            raw.settimeout(10)
            sock = context.wrap_socket(raw, server_side=True)
            sock.settimeout(0.0)
            client = _Client(sock)
            with self._lock:
                self._clients.append(client)
                self.connections += 1
            while not self._stopping.is_set():
                data = client.read()
                if data is None:
                    continue
                if not data:
                    break
                for body in client.frames(data):
                    source, destination, namespace, payload = _unpack(body)
                    self._handle(client, source, destination, namespace, json.loads(payload or "{}"))
        except (OSError, ValueError, ConnectionError):
            pass
        finally:
            try:
                raw.close()
            except OSError:
                pass
            if client is not None:
                with self._lock:
                    if client in self._clients:
                        self._clients.remove(client)

    def _drop_all(self) -> None:
        with self._lock:
            clients, self._clients = self._clients, []
        for client in clients:
            try:
                client.sock.close()
            except OSError:
                pass

    # -- điều khiển cho bài thử -----------------------------------------------------------------------------------------

    def sleep(self) -> None:
        """Tắt nguồn: đang nối thì đứt, nối mới thì không được, mDNS im."""
        self._asleep = True
        self._drop_all()

    def wake(self) -> None:
        self._asleep = False

    def takeover(self, url: str) -> None:
        """Một người điều khiển khác phát thứ khác trên thiết bị (phiên phát mới)."""
        with self._lock:
            self._msid += 1
            self._content, self._state, self._idle, self._offset, self._since = url, "PLAYING", "", 0.0, time.monotonic()
            self._push_media(include_media=True)

    def launch(self) -> None:
        """Một người điều khiển khác đã mở Default Media Receiver trước khi máy tính tới."""
        with self._lock:
            self._launch()

    def _launch(self) -> None:
        if self._app is None:
            self._apps += 1
            self._app = {"appId": APP_ID, "displayName": "Default Media Receiver", "isIdleScreen": False,
                         "namespaces": [{"name": NS["media"]}, {"name": NS["connection"]}],
                         "sessionId": str(uuid.uuid4()), "statusText": "Ready To Cast",
                         "transportId": f"web-{self._apps}", "universalAppId": APP_ID}
            self._msid, self._state, self._idle, self._content = 0, "IDLE", "", ""

    def stop_app(self) -> None:
        """Bấm dừng trên TV / mở app khác: ứng dụng của người gửi biến mất."""
        with self._lock:
            app, self._app = self._app, None
            self._state, self._idle, self._offset = "IDLE", "CANCELLED", 0.0
            if app is not None:
                for client in list(self._clients):
                    if app["transportId"] in client.connected:
                        client.send(app["transportId"], NS["connection"], {"type": "CLOSE"})
                        client.connected.discard(app["transportId"])
            self._push_receiver()

    def interrupt(self) -> None:
        """Phiên phát hiện tại bị cắt (IDLE / INTERRUPTED) - như khi máy khác LOAD đè."""
        with self._lock:
            self._state, self._idle = "IDLE", "INTERRUPTED"
            self._push_media()

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def content(self) -> str:
        with self._lock:
            return self._content

    @property
    def app_running(self) -> bool:
        with self._lock:
            return self._app is not None

    def position(self) -> float:
        with self._lock:
            return self._position()

    def calls(self, name: str) -> list[dict[str, Any]]:
        with self._lock:
            return [payload for action, payload in self.actions if action == name]

    # -- trạng thái phát --------------------------------------------------------------------------------------------

    def _position(self) -> float:
        if self._state != "PLAYING":
            return self._offset
        at = self._offset + (time.monotonic() - self._since) * self.speed
        return min(at, self.duration) if self.duration else at

    def _entry(self, include_media: bool = False) -> dict[str, Any]:
        entry: dict[str, Any] = {"mediaSessionId": self._msid, "playbackRate": self.speed, "playerState": self._state,
                                 "currentTime": round(self._position(), 3), "supportedMediaCommands": 274447,
                                 "volume": {"level": 1.0, "muted": False}, "currentItemId": 1, "repeatMode": "REPEAT_OFF"}
        if self._state == "IDLE" and self._idle:
            entry["idleReason"] = self._idle
        if include_media:
            entry["media"] = {"contentId": self._content, "streamType": "BUFFERED", "contentType": self._type,
                              "metadata": self._metadata, "duration": self.duration}
        return entry

    def _push_media(self, *, include_media: bool = False, only: _Client | None = None, request: int = 0) -> None:
        """Tin MEDIA_STATUS tới người nối vào ứng dụng (`only`: chỉ người ấy, kèm requestId trả lời)."""
        if self.no_heartbeat_reply or self._app is None or not self._msid:
            return
        transport = self._app["transportId"]
        payload = {"type": "MEDIA_STATUS", "requestId": request, "status": [self._entry(include_media)]}
        for client in list(self._clients):
            if transport in client.connected and (only is None or client is only):
                client.send(transport, NS["media"], payload)

    def _push_receiver(self, *, only: _Client | None = None, request: int = 0) -> None:
        if self.no_heartbeat_reply:
            return
        status: dict[str, Any] = {"isActiveInput": True, "volume": {"level": 1.0, "muted": False}}
        if self._app is not None:
            status["applications"] = [self._app]
        payload = {"type": "RECEIVER_STATUS", "requestId": request, "status": status}
        for client in list(self._clients):
            if "receiver-0" in client.connected and (only is None or client is only):
                client.send("receiver-0", NS["receiver"], payload)

    def _tick(self) -> None:
        while not self._stopping.wait(0.05):
            with self._lock:
                if self._state == "BUFFERING" and time.monotonic() - self._loaded >= self.buffer_seconds:
                    self._state = "PLAYING" if self._autoplay else "PAUSED"
                    self._since = time.monotonic()
                    self._push_media()
                elif self._state == "PLAYING" and self.duration and self._position() >= self.duration:
                    self._state, self._idle, self._offset = "IDLE", "FINISHED", self.duration
                    self._push_media()

    def _fetch(self, url: str, msid: int) -> None:
        record: dict[str, Any] = {"url": url, "status": 0, "bytes": 0, "type": "", "cors": ""}
        try:
            if self.fail_fetch:
                raise OSError("bị chặn")
            request = urllib.request.Request(url, headers={"Range": "bytes=0-"})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=10) as response:
                record["status"], record["type"] = response.status, response.headers.get("Content-Type", "")
                record["cors"] = response.headers.get("Access-Control-Allow-Origin", "")
                while True:
                    want = 65536 if self.fetch_bytes is None else min(65536, self.fetch_bytes - record["bytes"])
                    chunk = response.read(want) if want > 0 else b""
                    if not chunk:
                        break
                    record["bytes"] += len(chunk)
        except Exception as error:  # noqa: BLE001 - thiết bị thật cũng chỉ báo "không tải được"
            record["error"] = str(error)
        with self._lock:
            self.fetches.append(record)
            if "error" in record and self._msid == msid and self._state != "IDLE":
                self._state, self._idle = "IDLE", "ERROR"  # không tải được (tường lửa...): lỗi sau khi đã nhận LOAD
                self._push_media()

    # -- tin nhận được ------------------------------------------------------------------------------------------

    def _handle(self, client: _Client, source: str, destination: str, namespace: str, payload: dict[str, Any]) -> None:
        kind = payload.get("type", "")
        request = payload.get("requestId", 0) if isinstance(payload.get("requestId"), int) else 0
        with self._lock:
            if kind == "PING":
                self.pings += 1
            else:
                self.actions.append((f"{SHORT.get(namespace, namespace)}.{kind}", payload))
            if self.no_heartbeat_reply:
                return  # treo: không trả lời gì, kể cả tin nối
            client.sender = source
            if namespace == NS["heartbeat"]:
                if kind == "PING":
                    client.send(destination, namespace, {"type": "PONG"})
            elif namespace == NS["connection"]:
                if kind == "CONNECT":
                    client.connected.add(destination)
                elif kind == "CLOSE":
                    client.connected.discard(destination)
            elif namespace == NS["receiver"]:
                self._receiver(client, kind, request, payload)
            elif namespace == NS["media"]:
                self._media(client, destination, kind, request, payload)

    def _receiver(self, client: _Client, kind: str, request: int, payload: dict[str, Any]) -> None:
        if kind == "GET_STATUS":
            self._push_receiver(only=client, request=request)
        elif kind == "LAUNCH":
            if payload.get("appId") != APP_ID:
                client.send("receiver-0", NS["receiver"], {"type": "LAUNCH_ERROR", "requestId": request,
                                                           "reason": "NOT_FOUND"})
                return
            self._launch()
            self._push_receiver(only=client, request=request)
            self._push_receiver()
        elif kind == "STOP":
            if self._app is not None and payload.get("sessionId") == self._app["sessionId"]:
                transport = self._app["transportId"]
                self._app = None
                self._state, self._idle, self._offset = "IDLE", "CANCELLED", 0.0
                for other in self._clients:
                    other.connected.discard(transport)
            self._push_receiver(only=client, request=request)
            self._push_receiver()
        else:
            client.send("receiver-0", NS["receiver"], {"type": "INVALID_REQUEST", "requestId": request,
                                                       "reason": "INVALID_COMMAND"})

    def _media(self, client: _Client, destination: str, kind: str, request: int, payload: dict[str, Any]) -> None:
        app = self._app
        if app is None or destination != app["transportId"]:
            client.send(destination, NS["media"], {"type": "INVALID_REQUEST", "requestId": request,
                                                   "reason": "INVALID_APP_SESSION"})
            return
        transport = app["transportId"]
        if kind == "LOAD":
            if self.refuse_load:
                client.send(transport, NS["media"], {"type": "LOAD_FAILED", "requestId": request, "detail": {"itemId": 1}})
                return
            media = payload.get("media") or {}
            if self._msid and self._state != "IDLE":  # LOAD đè lên bài đang phát: bài cũ nhận INTERRUPTED trước
                self._state, self._idle = "IDLE", "INTERRUPTED"
                self._push_media()
            self._msid += 1
            self._content, self._type = str(media.get("contentId", "")), str(media.get("contentType", ""))
            self._metadata = media.get("metadata") or {}
            self._autoplay = bool(payload.get("autoplay", True))
            self._state, self._idle = "BUFFERING", ""
            self._offset, self._since, self._loaded = float(payload.get("currentTime") or 0.0), time.monotonic(), time.monotonic()
            self._push_media(include_media=True, only=client, request=request)
            self._push_media(include_media=True)  # người khác nối vào ứng dụng cũng thấy
            threading.Thread(target=self._fetch, args=(self._content, self._msid), daemon=True).start()
            return
        if kind == "GET_STATUS":
            status = [self._entry()] if self._msid else []
            client.send(transport, NS["media"], {"type": "MEDIA_STATUS", "requestId": request, "status": status})
            return
        if payload.get("mediaSessionId") != self._msid or not self._msid:
            client.send(transport, NS["media"], {"type": "INVALID_REQUEST", "requestId": request,
                                                 "reason": "INVALID_MEDIA_SESSION_ID"})
            return
        if kind == "PLAY":
            if self._state == "PAUSED":
                self._state, self._since = "PLAYING", time.monotonic()
        elif kind == "PAUSE":
            if self._state in ("PLAYING", "BUFFERING"):
                self._offset, self._state, self._autoplay = self._position(), "PAUSED", False
        elif kind == "SEEK":
            target = float(payload.get("currentTime") or 0.0)
            self._offset, self._since = min(target, self.duration) if self.duration else target, time.monotonic()
        elif kind == "STOP":
            self._offset, self._state, self._idle = 0.0, "IDLE", "CANCELLED"
        else:
            client.send(transport, NS["media"], {"type": "INVALID_REQUEST", "requestId": request,
                                                 "reason": "INVALID_COMMAND"})
            return
        self._push_media(only=client, request=request)
        self._push_media()

    # -- mDNS ---------------------------------------------------------------------------------------------------

    def _answer(self) -> None:
        while not self._stopping.is_set():
            try:
                data, sender = self._udp.recvfrom(4096)  # type: ignore[union-attr]
            except (TimeoutError, socket.timeout):  # noqa: UP041
                continue
            except OSError:
                return
            if self._asleep or len(data) < 12 or data[2] & 0x80 or b"\x0b_googlecast" not in data:
                continue
            try:
                self._udp.sendto(self.mdns_response(data[:2]), sender)  # type: ignore[union-attr]
            except OSError:
                pass

    def mdns_response(self, ident: bytes = b"\x00\x00") -> bytes:
        """Trả lời kiểu "kế thừa" (RFC 6762 §6.7): lặp lại câu hỏi, TTL ngắn, tên nén. PTR ở phần trả lời; SRV, TXT, A ở phần
        thêm."""
        label = (re.sub(r"[^A-Za-z0-9]+", "-", self.name).strip("-") + "-" + self.device_id[:12]).encode("ascii", "ignore")
        host = self.device_id[:12].encode()
        data = bytearray(ident + struct.pack(">HHHHH", 0x8400, 1, 1, 0, 3))
        question = len(data)  # = 12
        data += b"".join(bytes([len(part)]) + part.encode() for part in SERVICE.split(".")) + b"\x00"
        data += struct.pack(">HH", 12, 1)
        local = question + 1 + len("_googlecast") + 1 + len("_tcp")  # vị trí nhãn "local"
        data += _ptr(question) + struct.pack(">HHI", 12, 1, 10)
        size_at = len(data)
        data += b"\x00\x00"
        instance = len(data)
        data += bytes([len(label)]) + label + _ptr(question)
        data[size_at:size_at + 2] = struct.pack(">H", len(data) - size_at - 2)
        # SRV: tên nén trỏ tới tên thể hiện; mục tiêu "<host>.local" nén vào nhãn "local"
        data += _ptr(instance) + struct.pack(">HHI", 33, 1, 10)
        size_at = len(data)
        data += b"\x00\x00" + struct.pack(">HHH", 0, 0, self.port)
        target = len(data)
        data += bytes([len(host)]) + host + _ptr(local)
        data[size_at:size_at + 2] = struct.pack(">H", len(data) - size_at - 2)
        # TXT
        pairs = [("id", self.device_id), ("cd", self.device_id.upper()), ("rm", ""), ("ve", "05"), ("md", self.model),
                 ("ic", "/setup/icon.png"), ("fn", self.name), ("ca", "5" if self.video else "4"), ("st", "0"),
                 ("bs", "FA8FCA000000"), ("nf", "1"), ("rs", "")]
        txt = b"".join(bytes([len(item)]) + item for item in (f"{key}={value}".encode() for key, value in pairs))
        data += _ptr(instance) + struct.pack(">HHIH", 16, 1, 4500, len(txt)) + txt
        # A
        data += _ptr(target) + struct.pack(">HHIH", 1, 1, 10, 4) + socket.inet_aton(self.advertised_host)
        return bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Chromecast giả lập - thử 'Phát trên Google Cast' không cần thiết bị thật")
    parser.add_argument("--name", default="Loa Nest thử")
    parser.add_argument("--interface", required=True, help="địa chỉ IP của card mạng LAN máy này (vd 192.168.0.77)")
    parser.add_argument("--speed", type=float, default=1.0, help="vị trí chạy nhanh hơn đồng hồ bao nhiêu lần")
    parser.add_argument("--duration", type=float, default=600.0, help="độ dài mỗi chương (giây) mà thiết bị 'đọc' ra")
    parser.add_argument("--video", action="store_true", help="như TV / Chromecast (có hình) thay vì loa")
    args = parser.parse_args()
    receiver = FakeCastReceiver(args.name, host=args.interface, speed=args.speed, duration=args.duration, video=args.video)
    receiver.start(multicast=True, interface=args.interface)
    print(f"{args.name}: cast://{args.interface}:{receiver.port}", flush=True)
    seen_actions = seen_fetches = 0
    try:
        while True:
            time.sleep(1)
            with receiver._lock:
                actions, fetches = receiver.actions[seen_actions:], receiver.fetches[seen_fetches:]
                seen_actions, seen_fetches = len(receiver.actions), len(receiver.fetches)
            for action, values in actions:
                if not action.endswith("GET_STATUS"):
                    shown = {key: (str(value)[:60]) for key, value in values.items() if key != "requestId"}
                    print(time.strftime("%H:%M:%S"), action, shown, flush=True)
            for fetch in fetches:
                print(time.strftime("%H:%M:%S"), "tải", fetch, flush=True)
    except KeyboardInterrupt:
        receiver.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
