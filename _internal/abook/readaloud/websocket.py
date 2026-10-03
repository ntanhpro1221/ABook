"""Máy khách WebSocket (RFC 6455) tối thiểu bằng thư viện chuẩn: bắt tay, khung có mặt nạ gửi đi, khung văn bản / nhị phân nhận về, ping / close.

Gói đóng sẵn không có `websockets` hay `aiohttp` (pyproject.toml bị khoá băm), mà dịch vụ đọc to của Edge chỉ nói WebSocket. Chỉ làm đủ cho
dịch vụ ấy: không nén (không xin permessage-deflate), không phân mảnh khi gửi, nhận được khung phân mảnh. Đồng bộ, một luồng.
"""
from __future__ import annotations

import base64
import hashlib
import os
import socket
import ssl
import struct
import time
from typing import Callable

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
CONTINUATION, TEXT, BINARY, CLOSE, PING, PONG = 0x0, 0x1, 0x2, 0x8, 0x9, 0xA
MAX_MESSAGE = 32 * 1024 * 1024  # một lượt đọc một đoạn không bao giờ gần cỡ này; chặn máy chủ gửi bừa


class WebSocketError(OSError):
    """Lỗi giao thức hay kết nối WebSocket."""


class Rejected(WebSocketError):
    """Máy chủ không nâng cấp lên WebSocket (bắt tay trả mã khác 101). `date`: header Date của nó (để chỉnh lệch đồng hồ)."""

    def __init__(self, status: int, date: str = "") -> None:
        super().__init__(f"Máy chủ từ chối bắt tay WebSocket (HTTP {status})")
        self.status = status
        self.date = date


class Closed(WebSocketError):
    """Máy chủ đóng kết nối. `code`: mã đóng của khung CLOSE (1005 khi không có)."""

    def __init__(self, code: int = 1005, reason: str = "") -> None:
        super().__init__(f"Kết nối đã đóng ({code} {reason})".strip())
        self.code = code
        self.reason = reason


def encode_frame(opcode: int, payload: bytes, mask_key: bytes | None = None) -> bytes:
    """Một khung hoàn chỉnh (FIN = 1). Máy khách PHẢI che (mask) khung gửi đi: `mask_key` 4 byte (mặc định ngẫu nhiên)."""
    if mask_key is None:
        mask_key = os.urandom(4)
    length = len(payload)
    head = bytearray([0x80 | opcode])
    if length < 126:
        head.append(0x80 | length)
    elif length < 65536:
        head.append(0x80 | 126)
        head += struct.pack(">H", length)
    else:
        head.append(0x80 | 127)
        head += struct.pack(">Q", length)
    masked = bytes(byte ^ mask_key[index % 4] for index, byte in enumerate(payload)) if length < 4096 else _mask_large(payload, mask_key)
    return bytes(head) + mask_key + masked


def _mask_large(payload: bytes, key: bytes) -> bytes:
    # XOR cả khối bằng số nguyên lớn: nhanh hơn nhiều so với vòng từng byte với payload lớn.
    repeated = (key * (len(payload) // 4 + 1))[: len(payload)]
    return (int.from_bytes(payload, "big") ^ int.from_bytes(repeated, "big")).to_bytes(len(payload), "big")


def read_frame(receive: Callable[[int], bytes]) -> tuple[bool, int, bytes]:
    """Đọc MỘT khung bằng `receive(n)` (trả đúng n byte hay ném lỗi): (fin, opcode, payload đã bỏ mặt nạ nếu có). Khung của máy chủ thường không che."""
    first, second = receive(2)
    fin = bool(first & 0x80)
    opcode = first & 0x0F
    masked = bool(second & 0x80)
    length = second & 0x7F
    if length == 126:
        (length,) = struct.unpack(">H", receive(2))
    elif length == 127:
        (length,) = struct.unpack(">Q", receive(8))
    if length > MAX_MESSAGE:
        raise WebSocketError(f"Khung quá lớn ({length} byte)")
    key = receive(4) if masked else b""
    payload = receive(length) if length else b""
    if masked:
        payload = _mask_large(payload, key) if length else payload
    return fin, opcode, payload


class Connection:
    """Một kết nối WebSocket đã bắt tay xong."""

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        self._closed = False

    def _receive(self, count: int) -> bytes:
        chunks: list[bytes] = []
        remaining = count
        while remaining:
            try:
                chunk = self._sock.recv(remaining)
            except socket.timeout as error:
                raise TimeoutError("Quá lâu không nhận được gì từ máy chủ") from error
            except OSError as error:
                raise WebSocketError(str(error)) from error
            if not chunk:
                raise Closed()
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def send_text(self, text: str) -> None:
        self._sock.sendall(encode_frame(TEXT, text.encode("utf-8")))

    def send_binary(self, data: bytes) -> None:
        self._sock.sendall(encode_frame(BINARY, data))

    def recv(self) -> tuple[int, bytes]:
        """Một tin nhắn trọn vẹn: (TEXT hay BINARY, nội dung). Ping được trả pong ngay; CLOSE ném `Closed`."""
        message = bytearray()
        kind = TEXT
        while True:
            fin, opcode, payload = read_frame(self._receive)
            if opcode == PING:
                self._sock.sendall(encode_frame(PONG, payload))
                continue
            if opcode == PONG:
                continue
            if opcode == CLOSE:
                code = struct.unpack(">H", payload[:2])[0] if len(payload) >= 2 else 1005
                reason = payload[2:].decode("utf-8", "replace")
                self._reply_close(code)
                raise Closed(code, reason)
            if opcode in (TEXT, BINARY):
                kind = opcode
                message = bytearray(payload)
            elif opcode == CONTINUATION:
                message += payload
            else:
                raise WebSocketError(f"Khung lạ (opcode {opcode})")
            if len(message) > MAX_MESSAGE:
                raise WebSocketError("Tin nhắn quá lớn")
            if fin:
                return kind, bytes(message)

    def _reply_close(self, code: int) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._sock.sendall(encode_frame(CLOSE, struct.pack(">H", code if 1000 <= code < 5000 and code not in (1005, 1006) else 1000)))
        except OSError:
            pass

    def close(self) -> None:
        self._reply_close(1000)
        try:
            self._sock.close()
        except OSError:
            pass


def accept_key(key: str) -> str:
    return base64.b64encode(hashlib.sha1((key + GUID).encode("ascii")).digest()).decode("ascii")


def connect(host: str, port: int, path: str, headers: dict[str, str], *, secure: bool, timeout: float,
            read_timeout: float | None = None, context: ssl.SSLContext | None = None) -> Connection:
    """Mở TCP (+ TLS), bắt tay WebSocket với các header cho trước. Không kết nối được -> `OSError` gốc (socket.gaierror, ConnectionRefusedError...);
    máy chủ trả mã khác 101 -> `Rejected`; quá giờ -> `TimeoutError`."""
    deadline = time.monotonic() + timeout
    sock = socket.create_connection((host, port), timeout=timeout)
    try:
        if secure:
            sock = (context or ssl.create_default_context()).wrap_socket(sock, server_hostname=host)
        sock.settimeout(max(0.1, deadline - time.monotonic()))
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        lines = [f"GET {path} HTTP/1.1", f"Host: {host}", "Upgrade: websocket", "Connection: Upgrade", f"Sec-WebSocket-Key: {key}"]
        lines += [f"{name}: {value}" for name, value in headers.items()]
        sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("ascii"))
        raw = b""
        while b"\r\n\r\n" not in raw:
            chunk = sock.recv(4096)
            if not chunk:
                raise WebSocketError("Máy chủ đóng kết nối giữa lúc bắt tay")
            raw += chunk
            if len(raw) > 65536:
                raise WebSocketError("Phản hồi bắt tay quá dài")
        head, _, rest = raw.partition(b"\r\n\r\n")
        text = head.decode("latin-1").split("\r\n")
        try:
            status = int(text[0].split(" ", 2)[1])
        except (IndexError, ValueError) as error:
            raise WebSocketError(f"Phản hồi bắt tay lạ: {text[0]!r}") from error
        response = {}
        for line in text[1:]:
            name, _, value = line.partition(":")
            response[name.strip().lower()] = value.strip()
        if status != 101:
            raise Rejected(status, response.get("date", ""))
        if response.get("sec-websocket-accept") != accept_key(key):
            raise WebSocketError("Sec-WebSocket-Accept sai")
        sock.settimeout(read_timeout if read_timeout is not None else timeout)  # từ đây mỗi lần chờ dữ liệu có hạn riêng
        return Connection(_Buffered(sock, rest))
    except BaseException:
        sock.close()
        raise


class _Buffered:
    """Bọc socket: byte đã đọc quá phần bắt tay (khung đầu có thể đến cùng gói với phản hồi 101) được trả trước."""

    def __init__(self, sock: socket.socket, pending: bytes) -> None:
        self._sock = sock
        self._pending = pending

    def recv(self, count: int) -> bytes:
        if self._pending:
            chunk, self._pending = self._pending[:count], self._pending[count:]
            return chunk
        return self._sock.recv(count)

    def sendall(self, data: bytes) -> None:
        self._sock.sendall(data)

    def settimeout(self, value: float | None) -> None:
        self._sock.settimeout(value)

    def close(self) -> None:
        self._sock.close()
