"""Bluetooth (RFCOMM) cho mạng trạm - chủ sách 27-09: "stream Bluetooth để sau là vẫn phải làm đấy nhé".

Không đổi giao thức: MỘT kết nối RFCOMM mang NHIỀU luồng TCP của đúng cổng đồng bộ HTTP (sync.py). Bên kết nối (điện thoại)
mở một cổng TCP cục bộ; mỗi kết nối vào cổng ấy - trình phát nghe thẳng, đồng bộ chỗ nghe, điều khiển, ghép mã 6 số - thành
một luồng trong đường hầm; bên phục vụ (máy tính) nhận luồng và nối thẳng vào cổng đồng bộ của chính nó. Nên mọi thứ chạy
qua Wi-Fi cũng chạy qua Bluetooth mà sync.py không phải biết. Âm thanh chương (MP3 64-128 kbps = 8-16 KB/s) nghe thẳng thoải
mái trên RFCOMM (~100-250 KB/s thực tế); tải cả chương 20 MB mất vài phút.

RFCOMM chỉ cho một kết nối mỗi kênh mỗi cặp máy, nên phải tự ghép kênh. Khung: loại (1 byte), luồng (4 byte), độ dài (4
byte), big-endian, rồi dữ liệu (DATA tối đa 4 KB). Trình phát ngừng đọc khi bộ đệm đầy, nên mỗi luồng có cửa sổ tín dụng
riêng như HTTP/2 (64 KB mỗi chiều): bên gửi chỉ gửi trong phần tín dụng, bên nhận trả tín dụng sau khi ĐÃ ghi xuống socket
cục bộ (mỗi 16 KB) - một luồng nghẽn không làm luồng khác đứng. Cả đường hầm còn một cửa sổ chung 256 KB (WINDOW luồng 0):
trần bộ nhớ nhận, bao nhiêu luồng cũng vậy. CLOSE là "hết dữ liệu theo chiều này" (half-close); luồng xong khi cả hai chiều
đã CLOSE. RESET là "bỏ luồng này ngay, cả hai chiều": ứng dụng cục bộ đóng ngang (trình phát tua ra ngoài bộ đệm, đổi
chương, dừng) thì bên kia phải thôi gửi - không thì nó chờ tín dụng mãi, giữ luồng, luồng đọc và socket tới khi hết chỗ.
DATA tới một luồng không còn thì đáp RESET (bên kia tưởng luồng còn sống); WINDOW, CLOSE, RESET tới luồng không còn là
khung trễ, bỏ qua - không bao giờ đáp RESET cho RESET. Cùng giao thức ở phía Android: mobile/.../BtMux.kt.

Công bằng (08-10, đo thật: tải 3 MB ở 143 KB/s thì một yêu cầu nhỏ bên cạnh chờ ~3,5 giây): mỗi luồng xếp khung của nó vào
hàng riêng, MỘT luồng ghi chọn khung theo deficit round robin (Shreedhar-Varghese 1996) - luồng nhỏ chỉ chờ mỗi luồng lớn một
khung 4 KB (~27 ms). Khung điều khiển (WINDOW, RESET, ACK) đi trước, tối đa CONTROL_BURST khung liền khi DATA đang chờ.
`write()` trả về không có nghĩa đã tới: bộ đệm socket/RFCOMM nuốt hàng trăm KB và mọi thứ xếp sau chúng. Nên bên nhận báo
số byte đã đọc khỏi đường hầm (ACK, luồng 0, mỗi 4 KB) và bên gửi giữ không quá IN_FLIGHT byte chưa được báo. Luồng đọc
không bao giờ chờ ai: khung trả lời chỉ được xếp hàng cho luồng ghi.

Windows: Python có sẵn socket RFCOMM (AF_BLUETOOTH, từ 3.9); bản ghi SDP (để điện thoại tìm dịch vụ theo UUID) đăng ký bằng
WSASetServiceW qua ctypes - không thêm gói nào (thêm gói là đổi uv.lock, tức đổi hash chất lượng). Chiều ngược lại (máy
tính dùng thư viện của điện thoại): tra SDP bằng WSALookupService* để biết kênh, rồi `Gateway` mở cổng cục bộ như điện thoại
làm (cuối file).
"""
from __future__ import annotations

import ctypes
import itertools
import os
import queue
import re
import socket
import struct
import threading
import time
import uuid
from collections import deque
from typing import Callable, Iterator

SERVICE_UUID = uuid.UUID("a1f667fe-352a-49b7-9b91-a5463677cac0")  # dịch vụ ABook (điện thoại dùng đúng UUID này)
SERVICE_NAME = "ABook"
OPEN, DATA, CLOSE, WINDOW, RESET, ACK = 1, 2, 3, 4, 5, 6
HEADER = struct.Struct(">BII")
MAX_DATA = 4 * 1024  # khung DATA lớn nhất, cũng là phần mỗi lượt của một luồng
STREAM_WINDOW = 64 * 1024  # tín dụng mỗi luồng mỗi chiều
LINK_WINDOW = 256 * 1024  # tín dụng chung cả đường hầm mỗi chiều = trần bộ nhớ nhận
UPDATE_AFTER = 16 * 1024  # trả tín dụng khi đã tiêu chừng này
ACK_AFTER = 4 * 1024  # báo đã đọc khỏi đường hầm sau chừng này byte
IN_FLIGHT = 16 * 1024  # byte đã ghi xuống kết nối mà bên kia chưa báo đọc (~0,1 giây ở 150 KB/s)
CONTROL_BURST = 4
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


class _Outbox:
    """Mọi khung ra của một đầu đường hầm, cho MỘT luồng ghi. Khung điều khiển (`send`) đi trước, tối đa CONTROL_BURST khung
    liền khi DATA đang chờ; khung của từng luồng (`push`: OPEN, DATA, CLOSE - giữ đúng thứ tự trong luồng) xếp hàng riêng và
    được chọn theo deficit round robin, mỗi lượt MAX_DATA byte. DATA còn cần tín dụng chung (`credit`, WINDOW luồng 0); mọi
    khung luồng dừng khi đã có `limit` byte đi mà bên kia chưa báo đọc (`acked`) - khung điều khiển thì không bao giờ dừng
    (ACK hai chiều không được chờ nhau)."""

    def __init__(self, *, limit: int = IN_FLIGHT, credit: int = LINK_WINDOW) -> None:
        self.ready = threading.Condition()
        self.control: deque[bytes] = deque()
        self.queues: dict[int, deque[tuple[int, bytes]]] = {}
        self.active: deque[int] = deque()  # luồng có khung chờ, theo lượt
        self.deficit: dict[int, int] = {}
        self.turn: int | None = None  # luồng đang trong lượt (đã cộng phần lượt này)
        self.burst = 0
        self.link_credit = credit
        self.in_flight = 0
        self.limit = limit
        self.closed = False

    def send(self, kind: int, number: int, payload: bytes = b"") -> None:
        with self.ready:
            if self.closed:
                raise LinkClosed()
            self.control.append(HEADER.pack(kind, number, len(payload)) + payload)
            self.ready.notify_all()

    def push(self, number: int, kind: int, payload: bytes = b"") -> None:
        with self.ready:
            if self.closed:
                raise LinkClosed()
            waiting = self.queues.get(number)
            if waiting is None:
                waiting = self.queues[number] = deque()
                self.deficit[number] = 0
                self.active.append(number)
            waiting.append((kind, payload))
            self.ready.notify_all()

    def drop(self, number: int) -> None:
        """Bỏ mọi khung chưa gửi của một luồng (RESET): bên kia đã hay sẽ quên luồng ấy."""
        with self.ready:
            if self.queues.pop(number, None) is not None:
                self.active.remove(number)
                del self.deficit[number]
                if self.turn == number:
                    self.turn = None

    def credit(self, amount: int) -> None:
        with self.ready:
            self.link_credit += amount
            self.ready.notify_all()

    def acked(self, amount: int) -> None:
        with self.ready:
            self.in_flight = max(0, self.in_flight - amount)
            self.ready.notify_all()

    def close(self) -> None:
        with self.ready:
            self.closed = True
            self.ready.notify_all()

    def next(self, timeout: float | None = None) -> bytes | None:
        """Khung kế tiếp cho luồng ghi, chờ tới khi có khung gửi được. None: đã đóng (hay hết `timeout`)."""
        with self.ready:
            while not self.closed:
                frame = self._pick()
                if frame is not None:
                    self.in_flight += len(frame)
                    return frame
                if not self.ready.wait(timeout):
                    return None
            return None

    def _pick(self) -> bytes | None:
        if self.control and self.burst < CONTROL_BURST:
            self.burst += 1
            return self.control.popleft()
        frame = self._next_in_turn()
        if frame is not None:
            self.burst = 0
            return frame
        return self.control.popleft() if self.control else None

    def _next_in_turn(self) -> bytes | None:
        if self.in_flight >= self.limit:
            return None
        for _ in range(len(self.active) + 1):
            if not self.active:
                return None
            number = self.active[0]
            waiting = self.queues[number]
            kind, payload = waiting[0]
            cost = len(payload)
            if kind == DATA and cost > self.link_credit:
                self.active.rotate(-1)  # chờ tín dụng chung; luồng sau vẫn có thể gửi OPEN/CLOSE
                self.turn = None
                continue
            if self.turn != number:
                self.turn = number
                self.deficit[number] += MAX_DATA
            if cost > self.deficit[number]:
                self.active.rotate(-1)  # hết lượt
                self.turn = None
                continue
            waiting.popleft()
            self.deficit[number] -= cost
            if not waiting:
                del self.queues[number], self.deficit[number]
                self.active.popleft()
                self.turn = None
            if kind == DATA:
                self.link_credit -= cost
            return HEADER.pack(kind, number, cost) + payload
        return None


class _Stream:
    def __init__(self, mux: "Mux", number: int, local: socket.socket | None) -> None:
        self.mux, self.number, self.local = mux, number, local
        self.credit = STREAM_WINDOW  # bên kia nhận được bấy nhiêu byte nữa
        self.changed = threading.Condition()
        self.outgoing: queue.Queue[bytes | None] = queue.Queue()  # từ đường hầm xuống socket cục bộ; None = bên kia hết
        self.queued = 0  # byte đã nhận mà chưa ghi xuống
        self.unreturned = 0  # byte đã ghi xuống mà chưa trả tín dụng
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

    def receive(self, data: bytes) -> None:
        """Dữ liệu bên kia gửi cho luồng này (luồng đọc gọi - không bao giờ chờ). Quá tín dụng là sai giao thức: RESET."""
        with self.changed:
            if not self.closed and self.queued + self.unreturned + len(data) <= STREAM_WINDOW:
                self.queued += len(data)
                self.outgoing.put(data)
                return
            overflow = not self.closed
        self.mux._consumed(len(data))  # không giữ thì trả tín dụng chung ngay
        if overflow:
            self.close(reset=True)

    def grant(self, amount: int) -> None:
        with self.changed:
            self.credit += amount
            self.changed.notify_all()

    def _pump(self) -> None:
        """socket cục bộ -> hàng của luồng này, chỉ trong phần tín dụng."""
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
                with self.changed:  # xếp dưới khoá: đã đóng (RESET) thì không còn khung nào lọt vào sau `drop`
                    if self.closed:
                        return
                    self.credit -= len(data)
                    self.mux.out.push(self.number, DATA, data)
            with self.changed:
                if self.closed:
                    return
                self.sent_eof = True
                self.mux.out.push(self.number, CLOSE)
        except LinkClosed:
            return  # đường hầm đứt: shutdown() đã đóng mọi luồng
        except OSError:
            self.close(reset=True)  # ứng dụng cục bộ cắt ngang (RST), hay luồng vừa bị đóng
            return
        self._maybe_done()

    def _drain(self) -> None:
        """đường hầm -> socket cục bộ; trả tín dụng (luồng và chung) sau khi đã ghi."""
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
                    if self.closed:
                        return  # close() đã trả tín dụng chung cho mọi byte còn giữ, kể cả chỗ này
                    self.queued -= len(data)
                    self.unreturned += len(data)
                    grant = self.unreturned if self.unreturned >= UPDATE_AFTER else 0
                    if grant:
                        self.unreturned = 0
                if grant:
                    self.mux.out.send(WINDOW, self.number, struct.pack(">I", grant))
                self.mux._consumed(len(data))
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

    def close(self, *, reset: bool = False, abandoned: bool = False) -> None:
        """Đóng luồng (một lần). `reset`: đóng ngang - báo bên kia bỏ luồng, để nó không chờ tín dụng mãi. `abandoned`: bên
        kia đã bỏ luồng (nó gửi RESET). Hai trường hợp ấy bỏ luôn khung chưa gửi; đóng thường thì khung còn xếp vẫn đi hết."""
        with self.changed:
            if self.closed:
                return
            self.closed = True
            leftover, self.queued = self.queued, 0
            self.changed.notify_all()
        if self.local is not None:
            _close_socket(self.local)
        self.outgoing.put(None)
        self.mux._forget(self.number)
        if leftover:
            self.mux._consumed(leftover)
        if reset or abandoned:
            self.mux.out.drop(self.number)
        if reset:
            try:
                self.mux.out.send(RESET, self.number)
            except LinkClosed:
                pass


class Mux:
    """Một đầu đường hầm trên một kết nối byte (RFCOMM, hay socket thường khi thử). `dial`: bên phục vụ - mở kết nối cục bộ
    cho mỗi luồng bên kia mở. `open(sock)`: bên kết nối - đưa một socket cục bộ vào đường hầm. `limit`: IN_FLIGHT (thử)."""

    def __init__(self, link: socket.socket, *, dial: Callable[[], socket.socket] | None = None, odd: bool = True,
                 limit: int = IN_FLIGHT) -> None:
        self.link = link
        self.dial = dial
        self.streams: dict[int, _Stream] = {}
        self.lock = threading.Lock()
        self.out = _Outbox(limit=limit)
        self.numbers = itertools.count(1 if odd else 2, 2)
        self.alive = True
        self._credit_lock = threading.Lock()
        self._held = 0  # byte DATA đã nhận mà chưa tiêu (trần LINK_WINDOW)
        self._unreturned = 0  # byte đã tiêu mà chưa trả tín dụng chung
        threading.Thread(target=self._write, name="bt-write", daemon=True).start()

    def _write(self) -> None:
        """Luồng ghi duy nhất của kết nối."""
        while True:
            frame = self.out.next()
            if frame is None:
                return
            try:
                self.link.sendall(frame)
            except OSError:
                self.shutdown()
                return

    def _consumed(self, amount: int) -> None:
        """`amount` byte DATA đã ghi xuống (hay bỏ): trả tín dụng chung, gộp mỗi UPDATE_AFTER."""
        with self._credit_lock:
            self._held -= amount
            self._unreturned += amount
            grant = self._unreturned if self._unreturned >= UPDATE_AFTER else 0
            if grant:
                self._unreturned = 0
        if grant:
            try:
                self.out.send(WINDOW, 0, struct.pack(">I", grant))
            except LinkClosed:
                pass

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
        self.out.push(number, OPEN)
        stream.start()
        return number

    def run(self) -> None:
        """Đọc khung tới khi đường hầm đứt; đứt thì đóng mọi luồng. Không bao giờ chờ luồng nào: chỉ xếp hàng."""
        read = 0
        try:
            while True:
                kind, number, length = HEADER.unpack(_read_exact(self.link, HEADER.size))
                if length > MAX_DATA:
                    raise LinkClosed("khung quá lớn")
                payload = _read_exact(self.link, length) if length else b""
                read += HEADER.size + length
                if read >= ACK_AFTER:
                    self.out.send(ACK, 0, struct.pack(">I", read))
                    read = 0
                amount = struct.unpack(">I", payload)[0] if kind in (WINDOW, ACK) and length == 4 else 0
                if number == 0:
                    if kind == ACK:
                        self.out.acked(amount)
                    elif kind == WINDOW:
                        if not 0 < amount <= LINK_WINDOW:
                            raise LinkClosed("tín dụng chung sai")
                        self.out.credit(amount)
                    continue
                if kind == DATA:
                    with self._credit_lock:
                        self._held += length
                        if self._held + self._unreturned > LINK_WINDOW:
                            raise LinkClosed("gửi quá tín dụng chung")
                with self.lock:
                    stream = self.streams.get(number)
                if kind == OPEN:
                    self._accept(number)
                elif stream is None:
                    if kind == DATA:
                        self._consumed(length)
                        self.out.send(RESET, number)  # bên kia tưởng luồng còn sống: bảo nó thôi gửi
                    continue  # WINDOW/CLOSE/RESET trễ của luồng đã xong: bỏ
                elif kind == RESET:
                    stream.close(abandoned=True)
                elif kind == DATA:
                    stream.receive(payload)
                elif kind == CLOSE:
                    stream.outgoing.put(None)
                elif kind == WINDOW:
                    if 0 < amount <= STREAM_WINDOW:
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
            self.out.send(RESET, number)
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
        self.out.close()
        for stream in streams:
            stream.close()
        _close_socket(self.link)


class LocalPort:
    """Bên kết nối: cổng TCP cục bộ (127.0.0.1) mà mọi kết nối vào đều đi qua đường hầm - trình phát, đồng bộ... chỉ việc
    dùng http://127.0.0.1:<port> như một máy tính trong mạng. `mux`: bất cứ thứ gì có `alive` và `open(socket)` - Mux, hay
    Gateway (mở RFCOMM lười)."""

    def __init__(self, mux: "Mux | Gateway", port: int = 0) -> None:
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


# ---- Windows: bên GỌI - tra SDP tìm kênh RFCOMM của điện thoại, rồi đường hầm cục bộ ---------------------------------------
# Máy tính dùng thư viện của điện thoại (điện thoại bật "Cho máy khác nghe thư viện này" thì nghe RFCOMM cùng UUID,
# BluetoothShare). Android biết kênh nhờ createRfcommSocketToServiceRecord; Windows thì phải tự hỏi bản ghi SDP của máy kia
# (WSALookupServiceBeginW/NextW/End qua ctypes, như PyBluez) rồi mới connect((địa chỉ, kênh)).

# LUP_FLUSHCACHE là 0x1000 (0x2000 là LUP_FLUSHPREVIOUS): sai cờ thì Windows trả bản ghi SDP cũ trong bộ nhớ đệm, không hỏi
# điện thoại, và ABook không bao giờ hiện ra (thử sóng thật 08-10).
LUP_RETURN_ADDR, LUP_FLUSHCACHE = 0x0100, 0x1000
LOOKUP_FLAGS = LUP_FLUSHCACHE | LUP_RETURN_ADDR
WSAEFAULT, WSASERVICE_NOT_FOUND, WSA_E_NO_MORE, WSANO_DATA = 10014, 10108, 10110, 11004
BLUETOOTH_OFF = (10050, 10047, 10051)  # mạng/địa chỉ không dùng được: không có card hay tắt sóng
CONNECT_SECONDS = 15  # hạn RFCOMM connect; tra SDP nằm ngoài hạn này (Windows tự hết hạn)
GATEWAY_RETRY_SECONDS = 10  # vừa hỏng (ngoài tầm, điện thoại tắt Bluetooth): trả lỗi ngay, không quay số lại (như Android)
GATEWAY_IDLE_SECONDS = 60  # không luồng nào mở ngần này thì đóng RFCOMM - mở lại khi cần
FIRST_PORT, PORT_SPAN = 47670, 32  # cổng cục bộ ổn định theo địa chỉ, cùng dải với BluetoothLink.kt: 47670 + (hash & 31)
SOCKADDR_BTH_SIZE = ctypes.sizeof(_SOCKADDR_BTH)

_ADDRESS = re.compile(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}")


def normalize_address(text: str) -> str:
    """"aa-bb-cc-dd-ee-ff" / "AA:BB:..." -> "AA:BB:CC:DD:EE:FF" (Android in hoa); không phải địa chỉ Bluetooth thì ""."""
    clean = (text or "").strip().upper().replace("-", ":")
    return clean if _ADDRESS.fullmatch(clean) else ""


def stable_port(address: str) -> int:
    """Cổng cục bộ của đường hầm tới `address`: cùng cách tính với BluetoothLink.kt (String.hashCode của Java, 5 bit thấp),
    nên một máy giữ cùng cổng qua các lần mở lại."""
    value = 0
    for char in address:
        value = (31 * value + ord(char)) & 0xFFFFFFFF
    return FIRST_PORT + (value & (PORT_SPAN - 1))


class ServiceNotFound(OSError):
    """Máy kia ngoài tầm sóng, hay không mở dịch vụ ABook (không có bản ghi SDP với UUID này)."""


class _ServiceQuery:
    """WSAQUERYSETW hỏi "máy `address` có dịch vụ SERVICE_UUID không, ở kênh nào". Giữ mọi cấu trúc sống cùng đối tượng."""

    def __init__(self, address: str) -> None:
        self.guid = _GUID.of(SERVICE_UUID)
        self.query = _WSAQUERYSETW()
        self.query.dwSize = ctypes.sizeof(self.query)
        self.query.lpServiceClassId = ctypes.pointer(self.guid)
        self.query.dwNameSpace = NS_BTH
        self.query.lpszContext = f"({address})"


def channels_of(result: _WSAQUERYSETW) -> list[int]:
    """Kênh RFCOMM trong một kết quả tra SDP: RemoteAddr của mỗi CSADDR_INFO là SOCKADDR_BTH, `port` là kênh. Bỏ mục không
    phải địa chỉ Bluetooth hay kênh ngoài 1-30."""
    channels = []
    for index in range(result.dwNumberOfCsAddrs if result.lpcsaBuffer else 0):
        remote = result.lpcsaBuffer[index].RemoteAddr
        if not remote.lpSockaddr or remote.iSockaddrLength < SOCKADDR_BTH_SIZE:
            continue
        address = ctypes.cast(remote.lpSockaddr, ctypes.POINTER(_SOCKADDR_BTH)).contents
        if address.addressFamily == AF_BTH and 1 <= address.port <= 30:
            channels.append(int(address.port))
    return channels


class _Ws2:
    """Ba lời gọi WSALookupService của Windows. `dll`/`last_error` thay được để bài thử không chạm Bluetooth thật."""

    def __init__(self, dll: object = None, last_error: Callable[[], int] | None = None) -> None:
        self.dll = dll if dll is not None else ctypes.WinDLL("ws2_32", use_last_error=True)
        self.last_error = last_error or ctypes.get_last_error
        if dll is None:
            self.dll.WSALookupServiceBeginW.argtypes = [ctypes.POINTER(_WSAQUERYSETW), ctypes.c_ulong,
                                                        ctypes.POINTER(ctypes.c_void_p)]
            self.dll.WSALookupServiceNextW.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
                                                       ctypes.c_void_p]
            self.dll.WSALookupServiceEnd.argtypes = [ctypes.c_void_p]

    def lookup(self, query: _WSAQUERYSETW) -> Iterator[ctypes.Array]:
        """Từng bộ đệm kết quả (WSAQUERYSETW, con trỏ bên trong trỏ vào chính bộ đệm). Hết kết quả thì dừng."""
        handle = ctypes.c_void_p()
        if self.dll.WSALookupServiceBeginW(ctypes.byref(query), LOOKUP_FLAGS, ctypes.byref(handle)) != 0:
            raise OSError(self.last_error(), "WSALookupServiceBeginW")
        try:
            size = 4096
            while True:
                buffer = ctypes.create_string_buffer(size)
                length = ctypes.c_ulong(size)
                if self.dll.WSALookupServiceNextW(handle, LOOKUP_FLAGS, ctypes.byref(length), buffer) == 0:
                    yield buffer
                    continue
                code = self.last_error()
                if code == WSAEFAULT and length.value > size:
                    size = length.value  # bộ đệm nhỏ quá: Windows nói cần bao nhiêu
                    continue
                if code in (WSA_E_NO_MORE, WSANO_DATA, WSASERVICE_NOT_FOUND):
                    return
                raise OSError(code, "WSALookupServiceNextW")
        finally:
            self.dll.WSALookupServiceEnd(handle)


def find_channel(address: str, *, ws2: _Ws2 | None = None) -> int:
    """Kênh RFCOMM của dịch vụ ABook trên máy `address`; `ServiceNotFound` nếu máy ấy không có."""
    query = _ServiceQuery(address)
    try:
        for buffer in (ws2 or _Ws2()).lookup(query.query):
            channels = channels_of(_WSAQUERYSETW.from_buffer(buffer))
            if channels:
                return channels[0]
    except OSError as error:
        if error.errno not in (WSASERVICE_NOT_FOUND, WSANO_DATA):
            raise
    raise ServiceNotFound("Không thấy ABook trên máy kia qua Bluetooth - máy kia đã bật ABook, Bluetooth và "
                          "“Cho máy khác nghe thư viện này” chưa, và có trong tầm sóng không?")


def connect_rfcomm(address: str, *, ws2: _Ws2 | None = None) -> socket.socket:
    """Một kết nối RFCOMM tới dịch vụ ABook của `address` (đã ghép Bluetooth trong Cài đặt Windows). CHẶN tới vài chục giây
    khi máy kia ngoài tầm - chỉ gọi từ luồng nền (Gateway)."""
    if os.name != "nt" or not hasattr(socket, "AF_BLUETOOTH"):
        raise OSError("Máy này chưa hỗ trợ Bluetooth cho ABook")
    try:
        channel = find_channel(address, ws2=ws2)
        link = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    except ServiceNotFound:
        raise
    except OSError as error:
        raise OSError("Bluetooth của máy tính đang tắt - bật trong Cài đặt Windows" if error.errno in BLUETOOTH_OFF
                      else f"Không tra được ABook trên máy kia qua Bluetooth: {error}") from error
    try:
        try:
            link.setsockopt(SOL_RFCOMM, SO_BTH_AUTHENTICATE, 1)  # chỉ nối máy đã ghép; không bật được thì để TLS ghim vân tay gác
        except OSError:
            pass
        link.settimeout(CONNECT_SECONDS)
        link.connect((address, channel))
        link.settimeout(None)
    except OSError as error:
        _close_socket(link)
        raise OSError(f"Không kết nối được máy kia qua Bluetooth ({error})") from error
    return link


class Gateway:
    """Đường hầm Bluetooth tới MỘT máy (điện thoại) cho máy tính: cổng TCP 127.0.0.1:<ổn định theo địa chỉ> mà mọi kết nối
    vào đều là một luồng Mux trên MỘT kết nối RFCOMM (phía điện thoại là BluetoothShare). Cho `https://127.0.0.1:<port>` làm
    gốc của máy ấy - TLS đi nguyên vẹn qua đường hầm nên vân tay ghim vẫn kiểm đúng chứng chỉ của máy kia.

    Lười: RFCOMM chỉ mở khi có kết nối đầu tiên (hay `warm`), mở lại khi đứt, đóng sau GATEWAY_IDLE_SECONDS không luồng. Quay số
    luôn ở luồng riêng - `open`/`warm` không bao giờ chặn người gọi (giao diện, luồng hỏi trình phát). Vừa hỏng thì trả lỗi
    ngay trong GATEWAY_RETRY_SECONDS."""

    def __init__(self, address: str, *, connect: Callable[[str], socket.socket] | None = None,
                 retry_seconds: float = GATEWAY_RETRY_SECONDS, idle_seconds: float = GATEWAY_IDLE_SECONDS) -> None:
        self.address = address
        self.connect = connect
        self.retry_seconds = retry_seconds
        self.idle_seconds = idle_seconds
        self.last_error = ""
        self.closed = False
        self._mux: Mux | None = None
        self._failed_at: float | None = None
        self._last_used = time.monotonic()
        self._dialing = threading.Lock()  # một lần quay số một lúc; các luồng sau chờ kết quả của lần ấy
        self._lock = threading.Lock()
        self._stopped = threading.Event()
        try:
            self.local = LocalPort(self, stable_port(address))
        except OSError:
            self.local = LocalPort(self, 0)  # cổng ổn định đang bận: để hệ thống chọn
        self.port = self.local.port
        threading.Thread(target=self._reap, name="bt-gateway-idle", daemon=True).start()

    @property
    def alive(self) -> bool:
        """Cho LocalPort (nó chỉ cần `alive` và `open`): còn nhận kết nối cục bộ tới khi `close`."""
        return not self.closed

    @property
    def up(self) -> bool:
        mux = self._mux
        return mux is not None and mux.alive

    def open(self, client: socket.socket) -> None:
        threading.Thread(target=self._carry, args=(client,), name="bt-carry", daemon=True).start()

    def warm(self) -> None:
        """Mở RFCOMM ở nền nếu chưa mở (người gọi sắp dùng đường này): yêu cầu đầu chưa kịp thì yêu cầu sau đã có đường."""
        if not self.up and not self.closed and not self._dialing.locked():
            threading.Thread(target=self._try_link, name="bt-warm", daemon=True).start()

    def _try_link(self) -> None:
        try:
            self._link()
        except (OSError, LinkClosed):
            pass

    def _carry(self, client: socket.socket) -> None:
        try:
            self._link().open(client)
            self._last_used = time.monotonic()
        except (OSError, LinkClosed):
            _close_socket(client)  # lý do nằm ở `last_error`; ứng dụng thấy kết nối bị đóng
        except Exception as error:  # noqa: BLE001 - Bluetooth stack lỗi kiểu gì cũng không được làm sập app
            self.last_error = f"Không kết nối được qua Bluetooth: {type(error).__name__}: {error}"
            _close_socket(client)

    def _link(self) -> Mux:
        with self._dialing:
            if self.closed:
                raise OSError("Đã thôi ghép máy này")
            mux = self._mux
            if mux is not None and mux.alive:
                return mux
            if self._failed_at is not None and time.monotonic() - self._failed_at < self.retry_seconds:
                raise OSError(self.last_error or "Không kết nối được qua Bluetooth")
            try:
                link = (self.connect or connect_rfcomm)(self.address)
            except OSError as error:
                self._failed_at, self.last_error = time.monotonic(), str(error) or "Không kết nối được qua Bluetooth"
                raise
            fresh = Mux(link, odd=True)  # điện thoại phục vụ số chẵn (BluetoothShare: odd = false), bên gọi số lẻ
            with self._lock:
                if self.closed:
                    fresh.shutdown()
                    raise OSError("Đã thôi ghép máy này")
                self._mux = fresh
            threading.Thread(target=fresh.run, name="bt-link", daemon=True).start()
            self._failed_at, self.last_error = None, ""
            self._last_used = time.monotonic()
            return fresh

    def _reap(self) -> None:
        """Đóng RFCOMM khi không còn luồng nào đã GATEWAY_IDLE_SECONDS: không giữ sóng Bluetooth (và pin điện thoại) cho máy
        không ai dùng."""
        while not self._stopped.wait(max(0.05, min(15.0, self.idle_seconds / 4))):
            mux = self._mux
            if mux is None or not mux.alive:
                continue
            with mux.lock:
                busy = bool(mux.streams)
            now = time.monotonic()
            if busy:
                self._last_used = now
            elif now - self._last_used > self.idle_seconds:
                mux.shutdown()

    def close(self) -> None:
        with self._lock:
            self.closed = True
            mux = self._mux
        self._stopped.set()
        self.local.close()
        if mux is not None:
            mux.shutdown()


_gateways: dict[str, Gateway] = {}
_gateways_lock = threading.Lock()


def gateway(address: str, *, connect: Callable[[str], socket.socket] | None = None) -> Gateway:
    """Đường hầm tới máy `address` ("AA:BB:..." hay "bt:AA:BB:..."; một cho mỗi địa chỉ, dựng lần đầu cần). Địa chỉ hỏng:
    ValueError."""
    clean = normalize_address(address.removeprefix("bt:"))
    if not clean:
        raise ValueError(f"Địa chỉ Bluetooth không hợp lệ: {address}")
    with _gateways_lock:
        found = _gateways.get(clean)
        if found is None or found.closed:
            found = _gateways[clean] = Gateway(clean, connect=connect)
        return found


def last_error(address: str) -> str:
    clean = normalize_address(address.removeprefix("bt:"))
    with _gateways_lock:
        found = _gateways.get(clean)
    return found.last_error if found is not None else ""


def forget(address: str) -> None:
    """Thôi ghép máy `address`: đóng cổng cục bộ và kết nối RFCOMM của nó."""
    clean = normalize_address(address.removeprefix("bt:"))
    with _gateways_lock:
        found = _gateways.pop(clean, None)
    if found is not None:
        found.close()


# ---- Windows: thiết bị Bluetooth đã ghép với máy tính ---------------------------------------------------------------------
# Android 8+ không cho app đọc địa chỉ Bluetooth của chính nó (trả 02:00:00:00:00:00), nên điện thoại KHÔNG báo được địa chỉ lúc
# ghép Wi-Fi. Máy tính tự tìm: liệt kê thiết bị đã ghép trong Cài đặt Windows (bthprops.cpl, chỉ đọc danh sách của hệ điều hành -
# không dò sóng, không nối thiết bị nào) rồi chọn cái trùng tên điện thoại, hay để người dùng chọn một lần.

MAJOR_COMPUTER, MAJOR_PHONE = 1, 2  # lớp thiết bị Bluetooth (bit 8-12 của ulClassofDevice)


class _SYSTEMTIME(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ushort) for name in ("year", "month", "weekday", "day", "hour", "minute", "second", "millis")]


class _BLUETOOTH_DEVICE_SEARCH_PARAMS(ctypes.Structure):
    _fields_ = [("dwSize", ctypes.c_ulong), ("fReturnAuthenticated", ctypes.c_int), ("fReturnRemembered", ctypes.c_int),
                ("fReturnUnknown", ctypes.c_int), ("fReturnConnected", ctypes.c_int), ("fIssueInquiry", ctypes.c_int),
                ("cTimeoutMultiplier", ctypes.c_ubyte), ("hRadio", ctypes.c_void_p)]


class _BLUETOOTH_DEVICE_INFO(ctypes.Structure):
    _fields_ = [("dwSize", ctypes.c_ulong), ("address", ctypes.c_ulonglong), ("ulClassofDevice", ctypes.c_ulong),
                ("fConnected", ctypes.c_int), ("fRemembered", ctypes.c_int), ("fAuthenticated", ctypes.c_int),
                ("stLastSeen", _SYSTEMTIME), ("stLastUsed", _SYSTEMTIME), ("szName", ctypes.c_wchar * 248)]


def address_text(value: int) -> str:
    """BTH_ADDR (số 48 bit, byte cao nhất trước) -> "AA:BB:CC:DD:EE:FF"."""
    return ":".join(f"{(value >> shift) & 0xFF:02X}" for shift in range(40, -8, -8))


def paired_device(info: _BLUETOOTH_DEVICE_INFO) -> dict[str, object]:
    """Một BLUETOOTH_DEVICE_INFO -> {"name", "address", "kind": "phone" | "computer" | "other"} (phần thuần, test được)."""
    major = (info.ulClassofDevice >> 8) & 0x1F
    return {"name": str(info.szName), "address": address_text(info.address),
            "kind": "phone" if major == MAJOR_PHONE else "computer" if major == MAJOR_COMPUTER else "other"}


def paired_devices(*, dll: object = None) -> list[dict[str, object]]:
    """Thiết bị đã ghép (hay được nhớ) trong Cài đặt Windows, mỗi cái {"name", "address", "kind"}; bỏ tai nghe, loa... không phải
    điện thoại / máy tính. Không có Bluetooth hay không phải Windows: danh sách rỗng. `dll` thay được để bài thử không chạm hệ thống."""
    if dll is None:
        if os.name != "nt":
            return []
        try:
            dll = ctypes.WinDLL("bthprops.cpl")
        except OSError:
            return []
        dll.BluetoothFindFirstDevice.argtypes = [ctypes.POINTER(_BLUETOOTH_DEVICE_SEARCH_PARAMS),
                                                 ctypes.POINTER(_BLUETOOTH_DEVICE_INFO)]
        dll.BluetoothFindFirstDevice.restype = ctypes.c_void_p
        dll.BluetoothFindNextDevice.argtypes = [ctypes.c_void_p, ctypes.POINTER(_BLUETOOTH_DEVICE_INFO)]
        dll.BluetoothFindDeviceClose.argtypes = [ctypes.c_void_p]
    params = _BLUETOOTH_DEVICE_SEARCH_PARAMS()
    params.dwSize = ctypes.sizeof(params)
    params.fReturnAuthenticated = params.fReturnRemembered = params.fReturnConnected = 1
    params.fReturnUnknown = params.fIssueInquiry = 0  # chỉ đọc danh sách đã ghép: không dò sóng
    info = _BLUETOOTH_DEVICE_INFO()
    info.dwSize = ctypes.sizeof(info)
    handle = dll.BluetoothFindFirstDevice(ctypes.byref(params), ctypes.byref(info))
    if not handle:
        return []  # không có card Bluetooth, hay chưa có thiết bị nào
    found: list[dict[str, object]] = []
    try:
        while True:
            device = paired_device(info)
            if device["kind"] != "other" and normalize_address(str(device["address"])):
                found.append(device)
            if not dll.BluetoothFindNextDevice(handle, ctypes.byref(info)):
                break
    finally:
        dll.BluetoothFindDeviceClose(handle)
    return found


def match_by_name(name: str, devices: list[dict[str, object]]) -> str:
    """Địa chỉ của thiết bị đã ghép trùng tên `name` (không phân biệt hoa thường, bỏ khoảng trắng thừa); ưu tiên điện thoại.
    Không có, hay có NHIỀU máy cùng tên (không biết cái nào) thì "" - đừng đoán, người dùng chọn tay."""
    wanted = " ".join((name or "").casefold().split())
    if not wanted:
        return ""
    same = [device for device in devices if " ".join(str(device["name"]).casefold().split()) == wanted]
    phones = [device for device in same if device["kind"] == "phone"]
    pool = phones or same
    return str(pool[0]["address"]) if len({device["address"] for device in pool}) == 1 else ""
