"""Bluetooth (RFCOMM) cho mạng trạm - chủ sách 27-09: "stream Bluetooth để sau là vẫn phải làm đấy nhé".

Không đổi giao thức: MỘT kết nối RFCOMM mang NHIỀU luồng TCP của đúng cổng đồng bộ HTTP (sync.py). Bên kết nối (điện thoại)
mở một cổng TCP cục bộ; mỗi kết nối vào cổng ấy - trình phát nghe thẳng, đồng bộ chỗ nghe, điều khiển, ghép mã 6 số - thành
một luồng trong đường hầm; bên phục vụ (máy tính) nhận luồng và nối thẳng vào cổng đồng bộ của chính nó. Nên mọi thứ chạy
qua Wi-Fi cũng chạy qua Bluetooth mà sync.py không phải biết. Âm thanh chương (MP3 64-128 kbps = 8-16 KB/s) nghe thẳng thoải
mái trên RFCOMM (~100-250 KB/s thực tế); tải cả chương 20 MB mất vài phút.

RFCOMM chỉ cho một kết nối mỗi kênh mỗi cặp máy, nên phải tự ghép kênh. Khung: loại (1 byte), luồng (4 byte), độ dài (4
byte), big-endian, rồi dữ liệu. Trình phát ngừng đọc khi bộ đệm đầy, nên mỗi luồng có cửa sổ tín dụng riêng như HTTP/2: bên
gửi chỉ gửi trong phần tín dụng, bên nhận trả tín dụng sau khi ĐÃ ghi xuống socket cục bộ - một luồng nghẽn không làm luồng
khác đứng, và bộ nhớ đệm mỗi luồng có trần. CLOSE là "hết dữ liệu theo chiều này" (half-close); luồng xong khi cả hai chiều
đã CLOSE. Cùng giao thức ở phía Android: mobile/.../BtMux.kt.

Windows: Python có sẵn socket RFCOMM (AF_BLUETOOTH, từ 3.9); bản ghi SDP (để điện thoại tìm dịch vụ theo UUID) đăng ký bằng
WSASetServiceW qua ctypes - không thêm gói nào (thêm gói là đổi uv.lock, tức đổi hash chất lượng).
"""
from __future__ import annotations

import ctypes
import itertools
import os
import queue
import socket
import struct
import threading
import uuid
from typing import Callable

SERVICE_UUID = uuid.UUID("a1f667fe-352a-49b7-9b91-a5463677cac0")  # dịch vụ ABook (điện thoại dùng đúng UUID này)
SERVICE_NAME = "ABook"
OPEN, DATA, CLOSE, WINDOW = 1, 2, 3, 4
HEADER = struct.Struct(">BII")
MAX_DATA = 16 * 1024
WINDOW_SIZE = 256 * 1024
MAX_STREAMS = 64


class LinkClosed(Exception):
    """Đường hầm đứt (tắt Bluetooth, ra ngoài tầm, máy kia đóng app)."""


def _read_exact(link: socket.socket, size: int) -> bytes:
    chunks, got = [], 0
    while got < size:
        chunk = link.recv(size - got)
        if not chunk:
            raise LinkClosed()
        chunks.append(chunk)
        got += len(chunk)
    return b"".join(chunks)


class _Stream:
    def __init__(self, mux: "Mux", number: int, local: socket.socket) -> None:
        self.mux, self.number, self.local = mux, number, local
        self.credit = WINDOW_SIZE  # bên kia nhận được bấy nhiêu byte nữa
        self.changed = threading.Condition()
        self.outgoing: queue.Queue[bytes | None] = queue.Queue()  # từ đường hầm xuống socket cục bộ; None = bên kia hết
        self.queued = 0  # byte đã nhận mà chưa ghi xuống - bên kia giữ đúng tín dụng thì không bao giờ quá WINDOW_SIZE
        self.sent_eof = False
        self.got_eof = False
        self.closed = False

    def start(self) -> None:
        threading.Thread(target=self._pump, name=f"bt-pump-{self.number}", daemon=True).start()
        threading.Thread(target=self._drain, name=f"bt-drain-{self.number}", daemon=True).start()

    def receive(self, data: bytes) -> bool:
        """Dữ liệu bên kia gửi cho luồng này; False nếu bên kia gửi quá tín dụng (sai giao thức - đóng luồng)."""
        with self.changed:
            self.queued += len(data)
            if self.queued > WINDOW_SIZE:
                return False
        self.outgoing.put(data)
        return True

    def grant(self, amount: int) -> None:
        with self.changed:
            self.credit += amount
            self.changed.notify_all()

    def _pump(self) -> None:
        """socket cục bộ -> đường hầm, chỉ trong phần tín dụng."""
        try:
            while True:
                with self.changed:
                    while self.credit <= 0 and not self.closed:
                        self.changed.wait()
                    if self.closed:
                        return
                    budget = min(MAX_DATA, self.credit)
                data = self.local.recv(budget)
                if not data:
                    break
                with self.changed:
                    self.credit -= len(data)
                self.mux._send(DATA, self.number, data)
        except (OSError, LinkClosed):
            pass
        self.sent_eof = True
        try:
            self.mux._send(CLOSE, self.number)
        except LinkClosed:
            pass
        self._maybe_done()

    def _drain(self) -> None:
        """đường hầm -> socket cục bộ; trả tín dụng sau khi đã ghi."""
        try:
            while True:
                data = self.outgoing.get()
                if data is None:
                    self.local.shutdown(socket.SHUT_WR)
                    break
                self.local.sendall(data)
                with self.changed:
                    self.queued -= len(data)
                self.mux._send(WINDOW, self.number, struct.pack(">I", len(data)))
        except (OSError, LinkClosed):
            self.close()
        self.got_eof = True
        self._maybe_done()

    def _maybe_done(self) -> None:
        if self.sent_eof and self.got_eof:
            self.close()

    def close(self) -> None:
        with self.changed:
            if self.closed:
                return
            self.closed = True
            self.changed.notify_all()
        try:
            self.local.close()
        except OSError:
            pass
        self.outgoing.put(None)
        self.mux._forget(self.number)


class Mux:
    """Một đầu đường hầm trên một kết nối byte (RFCOMM, hay socket thường khi thử). `dial`: bên phục vụ - mở kết nối cục bộ
    cho mỗi luồng bên kia mở. `open(sock)`: bên kết nối - đưa một socket cục bộ vào đường hầm."""

    def __init__(self, link: socket.socket, *, dial: Callable[[], socket.socket] | None = None, odd: bool = True) -> None:
        self.link = link
        self.dial = dial
        self.streams: dict[int, _Stream] = {}
        self.lock = threading.Lock()
        self.send_lock = threading.Lock()
        self.numbers = itertools.count(1 if odd else 2, 2)
        self.alive = True

    def _send(self, kind: int, number: int, payload: bytes = b"") -> None:
        if not self.alive:
            raise LinkClosed()
        try:
            with self.send_lock:
                self.link.sendall(HEADER.pack(kind, number, len(payload)) + payload)
        except OSError as error:
            self.shutdown()
            raise LinkClosed() from error

    def _forget(self, number: int) -> None:
        with self.lock:
            self.streams.pop(number, None)

    def open(self, local: socket.socket) -> int:
        with self.lock:
            if len(self.streams) >= MAX_STREAMS:
                local.close()
                raise LinkClosed("quá nhiều luồng")
            number = next(self.numbers)
            stream = self.streams[number] = _Stream(self, number, local)
        self._send(OPEN, number)
        stream.start()
        return number

    def run(self) -> None:
        """Đọc khung tới khi đường hầm đứt; đứt thì đóng mọi luồng."""
        try:
            while True:
                kind, number, length = HEADER.unpack(_read_exact(self.link, HEADER.size))
                if length > MAX_DATA:
                    raise LinkClosed("khung quá lớn")
                payload = _read_exact(self.link, length) if length else b""
                with self.lock:
                    stream = self.streams.get(number)
                if kind == OPEN:
                    self._accept(number)
                elif stream is None:
                    continue  # luồng đã đóng: khung trễ, bỏ
                elif kind == DATA:
                    if not stream.receive(payload):
                        stream.close()
                        self._send(CLOSE, number)
                elif kind == CLOSE:
                    stream.outgoing.put(None)
                elif kind == WINDOW and len(payload) == 4:
                    stream.grant(struct.unpack(">I", payload)[0])
        except (OSError, LinkClosed, struct.error):
            pass
        finally:
            self.shutdown()

    def _accept(self, number: int) -> None:
        with self.lock:
            full = len(self.streams) >= MAX_STREAMS or number in self.streams
        if self.dial is None or full:
            self._send(CLOSE, number)
            return
        try:
            local = self.dial()
        except OSError:
            self._send(CLOSE, number)
            return
        stream = _Stream(self, number, local)
        with self.lock:
            self.streams[number] = stream
        stream.start()

    def shutdown(self) -> None:
        with self.lock:
            if not self.alive:
                return
            self.alive = False
            streams = list(self.streams.values())
        for stream in streams:
            stream.close()
        try:
            self.link.close()
        except OSError:
            pass


class LocalPort:
    """Bên kết nối: cổng TCP cục bộ (127.0.0.1) mà mọi kết nối vào đều đi qua đường hầm - trình phát, đồng bộ... chỉ việc
    dùng http://127.0.0.1:<port> như một máy tính trong mạng."""

    def __init__(self, mux: Mux, port: int = 0) -> None:
        self.mux = mux
        self.server = socket.create_server(("127.0.0.1", port))
        self.port = self.server.getsockname()[1]
        threading.Thread(target=self._accept, name="bt-local", daemon=True).start()

    def _accept(self) -> None:
        while self.mux.alive:
            try:
                client, _address = self.server.accept()
            except OSError:
                return
            try:
                self.mux.open(client)
            except LinkClosed:
                client.close()
                return

    def close(self) -> None:
        self.server.close()


# ---- Windows: máy chủ RFCOMM + bản ghi SDP ------------------------------------------------------------------------

AF_BTH = 32
NS_BTH = 16
BTHPROTO_RFCOMM = 3
RNRSERVICE_REGISTER, RNRSERVICE_DELETE = 0, 2
BT_PORT_ANY = -1
SOL_RFCOMM = BTHPROTO_RFCOMM
SO_BTH_AUTHENTICATE = 0x80000001 - (1 << 32)  # hằng số âm theo int C của setsockopt


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16), ("Data3", ctypes.c_uint16),
                ("Data4", ctypes.c_ubyte * 8)]

    @classmethod
    def of(cls, value: uuid.UUID) -> "_GUID":
        guid = cls()
        guid.Data1, guid.Data2, guid.Data3 = value.fields[0], value.fields[1], value.fields[2]
        guid.Data4[:] = list(value.bytes[8:])
        return guid


class _SOCKADDR_BTH(ctypes.Structure):
    _pack_ = 1  # ws2bth.h: pshpack1
    _fields_ = [("addressFamily", ctypes.c_ushort), ("btAddr", ctypes.c_ulonglong), ("serviceClassId", _GUID),
                ("port", ctypes.c_ulong)]


class _SOCKET_ADDRESS(ctypes.Structure):
    _fields_ = [("lpSockaddr", ctypes.c_void_p), ("iSockaddrLength", ctypes.c_int)]


class _CSADDR_INFO(ctypes.Structure):
    _fields_ = [("LocalAddr", _SOCKET_ADDRESS), ("RemoteAddr", _SOCKET_ADDRESS), ("iSocketType", ctypes.c_int),
                ("iProtocol", ctypes.c_int)]


class _WSAQUERYSETW(ctypes.Structure):
    _fields_ = [("dwSize", ctypes.c_ulong), ("lpszServiceInstanceName", ctypes.c_wchar_p),
                ("lpServiceClassId", ctypes.POINTER(_GUID)), ("lpVersion", ctypes.c_void_p),
                ("lpszComment", ctypes.c_wchar_p), ("dwNameSpace", ctypes.c_ulong), ("lpNSProviderId", ctypes.c_void_p),
                ("lpszContext", ctypes.c_wchar_p), ("dwNumberOfProtocols", ctypes.c_ulong),
                ("lpafpProtocols", ctypes.c_void_p), ("lpszQueryString", ctypes.c_wchar_p),
                ("dwNumberOfCsAddrs", ctypes.c_ulong), ("lpcsaBuffer", ctypes.POINTER(_CSADDR_INFO)),
                ("dwOutputFlags", ctypes.c_ulong), ("lpBlob", ctypes.c_void_p)]


class _SdpRecord:
    """Bản ghi SDP cho kênh RFCOMM `channel`: điện thoại gọi createRfcommSocketToServiceRecord(SERVICE_UUID) là tìm thấy.
    Giữ mọi cấu trúc sống cùng đối tượng (Windows giữ con trỏ tới lúc xoá bản ghi)."""

    def __init__(self, channel: int, name: str) -> None:
        self.guid = _GUID.of(SERVICE_UUID)
        self.address = _SOCKADDR_BTH(AF_BTH, 0, _GUID(), channel)
        self.info = _CSADDR_INFO()
        self.info.LocalAddr.lpSockaddr = ctypes.cast(ctypes.pointer(self.address), ctypes.c_void_p)
        self.info.LocalAddr.iSockaddrLength = ctypes.sizeof(self.address)
        self.info.iSocketType = socket.SOCK_STREAM
        self.info.iProtocol = BTHPROTO_RFCOMM
        self.query = _WSAQUERYSETW()
        self.query.dwSize = ctypes.sizeof(self.query)
        self.query.lpszServiceInstanceName = name
        self.query.lpServiceClassId = ctypes.pointer(self.guid)
        self.query.lpszComment = "ABook - nghe sách qua Bluetooth"
        self.query.dwNameSpace = NS_BTH
        self.query.dwNumberOfCsAddrs = 1
        self.query.lpcsaBuffer = ctypes.pointer(self.info)
        self._call(RNRSERVICE_REGISTER)

    def _call(self, operation: int) -> None:
        ws2 = ctypes.WinDLL("ws2_32")
        if ws2.WSASetServiceW(ctypes.byref(self.query), operation, 0) != 0:
            raise OSError(ws2.WSAGetLastError(), "WSASetServiceW")

    def delete(self) -> None:
        try:
            self._call(RNRSERVICE_DELETE)
        except OSError:
            pass


class BluetoothServer:
    """Bên phục vụ trên máy tính: nghe RFCOMM, đăng ký SDP, mỗi điện thoại kết nối là một Mux nối vào cổng đồng bộ. Không
    có Bluetooth (máy không có card, tắt sóng) thì `error` nói rõ, cổng Wi-Fi vẫn chạy như thường."""

    def __init__(self, sync_port: int, name: str = SERVICE_NAME) -> None:
        self.sync_port = sync_port
        self.name = name
        self.socket: socket.socket | None = None
        self.record: _SdpRecord | None = None
        self.channel = 0
        self.error = ""
        self.links: set[Mux] = set()

    def start(self) -> "BluetoothServer":
        if os.name != "nt" or not hasattr(socket, "AF_BLUETOOTH"):
            self.error = "Máy này chưa hỗ trợ Bluetooth cho ABook"
            return self
        try:
            server = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            try:
                # Chỉ máy đã ghép Bluetooth với máy tính (Cài đặt Windows) mới kết nối được - rồi mới tới mã 6 số của app.
                server.setsockopt(SOL_RFCOMM, SO_BTH_AUTHENTICATE, 1)
            except OSError:
                pass
            server.bind(("00:00:00:00:00:00", BT_PORT_ANY))
            server.listen(4)
            self.channel = int(server.getsockname()[1])
            self.record = _SdpRecord(self.channel, self.name)
        except OSError as error:
            self.error = ("Bluetooth của máy tính đang tắt - bật trong Cài đặt Windows để điện thoại kết nối qua Bluetooth"
                          if getattr(error, "winerror", None) in (10050, 10047) else f"Không mở được Bluetooth: {error}")
            self._close_quietly(locals().get("server"))
            return self
        except Exception as error:  # noqa: BLE001 - Bluetooth hỏng kiểu gì cũng không được kéo đổ cổng Wi-Fi
            self.error = f"Không mở được Bluetooth: {type(error).__name__}: {error}"
            self._close_quietly(locals().get("server"))
            return self
        self.socket = server
        threading.Thread(target=self._accept, name="bt-server", daemon=True).start()
        return self

    def _accept(self) -> None:
        while self.socket is not None:
            try:
                link, _address = self.socket.accept()
            except OSError:
                return
            mux = Mux(link, dial=lambda: socket.create_connection(("127.0.0.1", self.sync_port), timeout=10), odd=False)
            self.links.add(mux)
            threading.Thread(target=self._serve, args=(mux,), name="bt-link", daemon=True).start()

    def _serve(self, mux: Mux) -> None:
        try:
            mux.run()
        finally:
            self.links.discard(mux)

    @staticmethod
    def _close_quietly(server: socket.socket | None) -> None:
        if server is not None:
            try:
                server.close()
            except OSError:
                pass

    def view(self) -> dict[str, object]:
        return {"running": self.socket is not None, "channel": self.channel, "error": self.error,
                "connections": len(self.links)}

    def stop(self) -> None:
        server, self.socket = self.socket, None
        if self.record is not None:
            self.record.delete()
            self.record = None
        if server is not None:
            try:
                server.close()
            except OSError:
                pass
        for mux in list(self.links):
            mux.shutdown()
