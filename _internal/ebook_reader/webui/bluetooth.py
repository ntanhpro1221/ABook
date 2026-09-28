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
đã CLOSE. RESET là "bỏ luồng này ngay, cả hai chiều": ứng dụng cục bộ đóng ngang (trình phát tua ra ngoài bộ đệm, đổi
chương, dừng) thì bên kia phải thôi gửi - không thì nó chờ tín dụng mãi, giữ luồng, luồng đọc và socket tới khi hết chỗ.
DATA tới một luồng không còn thì đáp RESET (bên kia tưởng luồng còn sống); WINDOW, CLOSE, RESET tới luồng không còn là
khung trễ, bỏ qua - không bao giờ đáp RESET cho RESET. Cùng giao thức ở phía Android: mobile/.../BtMux.kt.

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
OPEN, DATA, CLOSE, WINDOW, RESET = 1, 2, 3, 4, 5
HEADER = struct.Struct(">BII")
MAX_DATA = 16 * 1024
WINDOW_SIZE = 256 * 1024
MAX_STREAMS = 64
DIAL_SECONDS = 10  # nối vào cổng đồng bộ của chính máy này; nối được rồi thì KHÔNG hạn giờ đọc (hỏi dài 25 giây)
RETRY_SECONDS = 20  # Bluetooth tắt / card rút ra: thử mở lại sau ngần này


class LinkClosed(Exception):
    """Đường hầm đứt (tắt Bluetooth, ra ngoài tầm, máy kia đóng app)."""


def _close_socket(sock: socket.socket) -> None:
    """shutdown trước close: luồng khác đang chặn trong recv/sendall trên socket này thoát ngay."""
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass


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
    def __init__(self, mux: "Mux", number: int, local: socket.socket | None) -> None:
        self.mux, self.number, self.local = mux, number, local
        self.credit = WINDOW_SIZE  # bên kia nhận được bấy nhiêu byte nữa
        self.changed = threading.Condition()
        self.outgoing: queue.Queue[bytes | None] = queue.Queue()  # từ đường hầm xuống socket cục bộ; None = bên kia hết
        self.queued = 0  # byte đã nhận mà chưa ghi xuống - bên kia giữ đúng tín dụng thì không bao giờ quá WINDOW_SIZE
        self.sent_eof = False
        self.got_eof = False
        self.closed = False

    def start(self, local: socket.socket | None = None) -> None:
        """Bắt đầu bơm hai chiều; `local` cho luồng bên kia mở (nối xong cổng đồng bộ mới có). Luồng đã bị đóng trong lúc
        nối (RESET, đường hầm đứt) thì đóng luôn socket vừa nối."""
        if local is not None:
            with self.changed:
                if not self.closed:
                    self.local = local
            if self.local is not local:
                _close_socket(local)
                return
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
        assert self.local is not None
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
        except LinkClosed:
            return  # đường hầm đứt: shutdown() đã đóng mọi luồng
        except OSError:
            self.close(reset=True)  # ứng dụng cục bộ cắt ngang (RST), hay luồng vừa bị đóng
            return
        self.sent_eof = True
        try:
            self.mux._send(CLOSE, self.number)
        except LinkClosed:
            return
        self._maybe_done()

    def _drain(self) -> None:
        """đường hầm -> socket cục bộ; trả tín dụng sau khi đã ghi."""
        assert self.local is not None
        try:
            while True:
                data = self.outgoing.get()
                if data is None:
                    if not self.closed:
                        self.local.shutdown(socket.SHUT_WR)
                    break
                self.local.sendall(data)
                with self.changed:
                    self.queued -= len(data)
                self.mux._send(WINDOW, self.number, struct.pack(">I", len(data)))
        except LinkClosed:
            return
        except OSError:
            self.close(reset=True)  # ứng dụng cục bộ đã đóng kết nối: bên kia phải thôi gửi
            return
        self.got_eof = True
        self._maybe_done()

    def _maybe_done(self) -> None:
        if self.sent_eof and self.got_eof:
            self.close()

    def close(self, *, reset: bool = False) -> None:
        """Đóng luồng (một lần). `reset`: đóng ngang - báo bên kia bỏ luồng, để nó không chờ tín dụng mãi."""
        with self.changed:
            if self.closed:
                return
            self.closed = True
            self.changed.notify_all()
        if self.local is not None:
            _close_socket(self.local)
        self.outgoing.put(None)
        self.mux._forget(self.number)
        if reset:
            try:
                self.mux._send(RESET, self.number)
            except LinkClosed:
                pass


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
            if not self.alive or len(self.streams) >= MAX_STREAMS:
                local.close()
                raise LinkClosed("đường hầm đã đóng" if not self.alive else "quá nhiều luồng")
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
                    if kind == DATA:
                        self._send(RESET, number)  # bên kia tưởng luồng còn sống: bảo nó thôi gửi
                    continue  # WINDOW/CLOSE/RESET trễ của luồng đã xong: bỏ
                elif kind == RESET:
                    stream.close()
                elif kind == DATA:
                    if not stream.receive(payload):
                        stream.close(reset=True)  # gửi quá tín dụng: sai giao thức
                elif kind == CLOSE:
                    stream.outgoing.put(None)
                elif kind == WINDOW:
                    amount = struct.unpack(">I", payload)[0] if len(payload) == 4 else 0
                    if 0 < amount <= WINDOW_SIZE:
                        stream.grant(amount)
                    else:
                        stream.close(reset=True)
        except (OSError, LinkClosed, struct.error):
            pass
        finally:
            self.shutdown()

    def _accept(self, number: int) -> None:
        """Bên kia mở luồng: nhận chỗ ngay (DATA tới trước khi nối xong thì xếp hàng), nối cổng cục bộ ở luồng riêng - nối
        chậm không được làm mọi luồng khác đứng theo luồng đọc."""
        with self.lock:
            refused = (not self.alive or self.dial is None or len(self.streams) >= MAX_STREAMS
                       or number in self.streams)
            stream = None if refused else _Stream(self, number, None)
            if stream is not None:
                self.streams[number] = stream
        if stream is None:
            self._send(RESET, number)
            return
        threading.Thread(target=self._dial, args=(stream,), name=f"bt-dial-{number}", daemon=True).start()

    def _dial(self, stream: _Stream) -> None:
        assert self.dial is not None
        try:
            local = self.dial()
        except OSError:
            stream.close(reset=True)  # cổng đồng bộ tắt: bên gọi thấy luồng bị bỏ, không treo
            return
        stream.start(local)

    def shutdown(self) -> None:
        with self.lock:
            if not self.alive:
                return
            self.alive = False  # open()/_accept() kiểm cờ này dưới cùng khoá: không luồng nào đăng ký sau ảnh chụp dưới
            streams = list(self.streams.values())
        for stream in streams:
            stream.close()
        _close_socket(self.link)


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


def _bth_address(text: str) -> int:
    """"AA:BB:CC:DD:EE:FF" (getsockname của socket RFCOMM) -> BTH_ADDR; không đọc được thì 0 (mọi card)."""
    try:
        return int(text.replace(":", ""), 16) if text else 0
    except ValueError:
        return 0


class _SdpRecord:
    """Bản ghi SDP cho kênh RFCOMM `channel`: điện thoại gọi createRfcommSocketToServiceRecord(SERVICE_UUID) là tìm thấy.
    Giữ mọi cấu trúc sống cùng đối tượng (Windows giữ con trỏ tới lúc xoá bản ghi). Như mẫu bthcxn của Microsoft: địa chỉ
    là getsockname() của socket đang nghe (địa chỉ card + kênh), dùng cho cả LocalAddr lẫn RemoteAddr."""

    def __init__(self, channel: int, name: str, radio: str = "") -> None:
        self.guid = _GUID.of(SERVICE_UUID)
        self.address = _SOCKADDR_BTH(AF_BTH, _bth_address(radio), _GUID(), channel)
        self.info = _CSADDR_INFO()
        self.info.LocalAddr.lpSockaddr = ctypes.cast(ctypes.pointer(self.address), ctypes.c_void_p)
        self.info.LocalAddr.iSockaddrLength = ctypes.sizeof(self.address)
        self.info.RemoteAddr.lpSockaddr = self.info.LocalAddr.lpSockaddr
        self.info.RemoteAddr.iSockaddrLength = self.info.LocalAddr.iSockaddrLength
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
        ws2 = ctypes.WinDLL("ws2_32", use_last_error=True)  # mã lỗi lưu ngay sau lời gọi, ctypes không kịp ghi đè
        if ws2.WSASetServiceW(ctypes.byref(self.query), operation, 0) != 0:
            raise OSError(ctypes.get_last_error(), "WSASetServiceW")

    def delete(self) -> None:
        try:
            self._call(RNRSERVICE_DELETE)
        except OSError:
            pass


class BluetoothServer:
    """Bên phục vụ trên máy tính: nghe RFCOMM, đăng ký SDP, mỗi điện thoại kết nối là một Mux nối vào cổng đồng bộ. Không
    có Bluetooth (máy không có card, tắt sóng) thì `error` nói rõ, cổng Wi-Fi vẫn chạy như thường - và cứ RETRY_SECONDS
    lại thử mở: người dùng bật Bluetooth theo lời nhắc là điện thoại kết nối được, không phải tắt mở đồng bộ. Tắt sóng khi
    đang nghe cũng thế: bỏ socket hỏng, báo lỗi, chờ sóng quay lại."""

    def __init__(self, sync_port: int, name: str = SERVICE_NAME, *, retry_seconds: float = RETRY_SECONDS) -> None:
        self.sync_port = sync_port
        self.name = name
        self.retry_seconds = retry_seconds
        self.socket: socket.socket | None = None
        self.record: _SdpRecord | None = None
        self.channel = 0
        self.address = ""  # địa chỉ card Bluetooth của máy này ("AA:BB:..."), để điện thoại ghép qua Wi-Fi biết đường dự phòng
        self.error = ""
        self.links: set[Mux] = set()
        self._lock = threading.Lock()
        self._stopped = threading.Event()

    def start(self) -> "BluetoothServer":
        if os.name != "nt" or not hasattr(socket, "AF_BLUETOOTH"):
            self.error = "Máy này chưa hỗ trợ Bluetooth cho ABook"
            return self
        self._stopped.clear()
        server = self._listen()  # lần đầu ngay tại chỗ: màn đồng bộ thấy lỗi (Bluetooth tắt) ngay khi bật
        threading.Thread(target=self._supervise, args=(server,), name="bt-server", daemon=True).start()
        return self

    def _listen(self) -> socket.socket | None:
        server = None
        try:
            server = self._rfcomm()
            try:
                # Chỉ máy đã ghép Bluetooth với máy tính (Cài đặt Windows) mới kết nối được - rồi mới tới mã 6 số của app.
                server.setsockopt(SOL_RFCOMM, SO_BTH_AUTHENTICATE, 1)
            except OSError as error:
                # Không bật được xác thực thì KHÔNG nghe: máy lạ trong tầm sóng không được chạm tới cổng đồng bộ.
                raise _AuthenticationUnavailable(error) from error
            server.bind(("00:00:00:00:00:00", BT_PORT_ANY))
            server.listen(4)
            radio, channel = server.getsockname()[:2]
            record = _SdpRecord(int(channel), self.name, str(radio))
        except _AuthenticationUnavailable as error:
            self.error = f"Không bật được xác thực Bluetooth nên không mở Bluetooth: {error.__cause__}"
            self._close_quietly(server)
            return None
        except OSError as error:
            self.error = ("Bluetooth của máy tính đang tắt - bật trong Cài đặt Windows để điện thoại kết nối qua Bluetooth"
                          if getattr(error, "winerror", None) in (10050, 10047) else f"Không mở được Bluetooth: {error}")
            self._close_quietly(server)
            return None
        except Exception as error:  # noqa: BLE001 - Bluetooth hỏng kiểu gì cũng không được kéo đổ cổng Wi-Fi
            self.error = f"Không mở được Bluetooth: {type(error).__name__}: {error}"
            self._close_quietly(server)
            return None
        with self._lock:
            if self._stopped.is_set():
                record.delete()
                self._close_quietly(server)
                return None
            self.socket, self.record, self.channel, self.error = server, record, int(channel), ""
            self.address = "" if str(radio).strip("0:") == "" else str(radio).upper()
        return server

    @staticmethod
    def _rfcomm() -> socket.socket:
        return socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)

    def _supervise(self, server: socket.socket | None) -> None:
        while not self._stopped.is_set():
            if server is not None:
                self._accept(server)
                self._drop_listener(server)
            if self._stopped.wait(self.retry_seconds):
                return
            server = self._listen()

    def _accept(self, server: socket.socket) -> None:
        while not self._stopped.is_set():
            try:
                link, _address = server.accept()
            except OSError as error:
                if not self._stopped.is_set():
                    self.error = f"Bluetooth ngừng nghe ({error}) - sẽ tự mở lại khi sóng quay lại"
                return
            mux = Mux(link, dial=self._dial, odd=False)
            with self._lock:
                if self._stopped.is_set():
                    mux.shutdown()
                    return
                self.links.add(mux)
            threading.Thread(target=self._serve, args=(mux,), name="bt-link", daemon=True).start()

    def _dial(self) -> socket.socket:
        local = socket.create_connection(("127.0.0.1", self.sync_port), timeout=DIAL_SECONDS)
        local.settimeout(None)  # hỏi dài 25 giây, trả lời chậm (/match, /studio) không được bị cắt thành EOF
        return local

    def _drop_listener(self, server: socket.socket) -> None:
        with self._lock:
            record = self.record if self.socket is server else None
            if self.socket is server:
                self.socket, self.record = None, None
        if record is not None:
            record.delete()
        self._close_quietly(server)

    def _serve(self, mux: Mux) -> None:
        try:
            mux.run()
        finally:
            with self._lock:
                self.links.discard(mux)

    @staticmethod
    def _close_quietly(server: socket.socket | None) -> None:
        if server is not None:
            try:
                server.close()
            except OSError:
                pass

    def view(self) -> dict[str, object]:
        with self._lock:
            return {"running": self.socket is not None, "channel": self.channel, "error": self.error,
                    "connections": len(self.links), "address": self.address}

    def stop(self) -> None:
        self._stopped.set()
        with self._lock:
            server, self.socket = self.socket, None
            record, self.record = self.record, None
            links = list(self.links)
        if record is not None:
            record.delete()
        self._close_quietly(server)
        for mux in links:
            mux.shutdown()


class _AuthenticationUnavailable(Exception):
    pass
