"""TLS cho cổng đồng bộ trong mạng LAN: chứng chỉ tự ký, ghim vân tay lúc ghép ("tin ở lần ghép đầu").

Trước đây mọi thứ giữa điện thoại và máy tính - mã ghép, mã thiết bị, chỗ nghe, audio - đi dạng rõ qua HTTP, nên ai cùng
Wi-Fi cũng đọc được mã thiết bị rồi dùng lại. Giờ mỗi máy phục vụ (máy tính, điện thoại chia sẻ thư viện) giữ MỘT cặp khoá +
chứng chỉ tự ký, sinh một lần và nằm cạnh tuỳ chọn của app. Lúc ghép, bên kết nối nhận chứng chỉ ấy, ghi lại vân tay SHA-256
của nó cùng thiết bị; từ đó chỉ nhận ĐÚNG chứng chỉ này. Vân tay đổi (máy kia cài lại, hay có kẻ chen giữa) là lỗi rõ ràng
bảo ghép lại - không bao giờ lặng lẽ rơi về HTTP. Không có CA, không kiểm tên máy: vân tay thay cho cả hai.

Không dùng thư viện ngoài: `cryptography` không nằm trong Python nhúng của app (shell/python/requirements.txt), và thêm gói
Python là đổi `uv.lock` - tức đổi hash chất lượng giữa cuốn sách. `ssl` của thư viện chuẩn chỉ biết NẠP chứng chỉ, không sinh,
nên chứng chỉ ECDSA P-256 sinh ở đây bằng số học thuần Python (một phép nhân điểm: vài chục mili giây). Điện thoại sinh của nó
bằng AndroidKeyStore (Pin.kt).
"""
from __future__ import annotations

import hashlib
import http.client
import os
import secrets
import ssl
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

FILE_NAME = "sync-tls.pem"
VALID_YEARS = 20  # UTCTime chỉ tới 2049; máy kiểm vân tay, không kiểm hạn
COMMON_NAME = "ABook"
HANDSHAKE_SECONDS = 10.0

# ---- ECDSA P-256 (secp256r1) -------------------------------------------------------------------------------------
_P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
_B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
_G = (0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296,
      0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5)
_Jacobian = tuple[int, int, int]


def _double(point: _Jacobian) -> _Jacobian:
    x, y, z = point
    if y == 0:
        return (0, 1, 0)
    s = 4 * x * y * y % _P
    m = (3 * x * x + _P - 3 * pow(z, 4, _P)) % _P  # a = -3
    x2 = (m * m - 2 * s) % _P
    return x2, (m * (s - x2) - 8 * pow(y, 4, _P)) % _P, 2 * y * z % _P


def _add(first: _Jacobian, second: _Jacobian) -> _Jacobian:
    if first[2] == 0:
        return second
    if second[2] == 0:
        return first
    x1, y1, z1 = first
    x2, y2, z2 = second
    z1z1, z2z2 = z1 * z1 % _P, z2 * z2 % _P
    u1, u2 = x1 * z2z2 % _P, x2 * z1z1 % _P
    s1, s2 = y1 * z2 * z2z2 % _P, y2 * z1 * z1z1 % _P
    if u1 == u2:
        return _double(first) if s1 == s2 else (0, 1, 0)
    h, r = (u2 - u1) % _P, (s2 - s1) % _P
    h2 = h * h % _P
    h3 = h * h2 % _P
    v = u1 * h2 % _P
    x3 = (r * r - h3 - 2 * v) % _P
    return x3, (r * (v - x3) - s1 * h3) % _P, h * z1 * z2 % _P


def _multiply(scalar: int, point: tuple[int, int]) -> tuple[int, int]:
    result: _Jacobian = (0, 1, 0)
    addend: _Jacobian = (point[0], point[1], 1)
    while scalar:
        if scalar & 1:
            result = _add(result, addend)
        addend = _double(addend)
        scalar >>= 1
    inverse = pow(result[2], -1, _P)
    return result[0] * inverse * inverse % _P, result[1] * inverse * inverse * inverse % _P


def _sign(private: int, message: bytes) -> tuple[int, int]:
    z = int.from_bytes(hashlib.sha256(message).digest(), "big")
    while True:
        k = secrets.randbelow(_N - 1) + 1
        r = _multiply(k, _G)[0] % _N
        s = pow(k, -1, _N) * (z + r * private) % _N
        if r and s:
            return r, s


# ---- DER ---------------------------------------------------------------------------------------------------------
def _tlv(tag: int, body: bytes) -> bytes:
    if len(body) < 0x80:
        return bytes([tag, len(body)]) + body
    size = len(body).to_bytes((len(body).bit_length() + 7) // 8, "big")
    return bytes([tag, 0x80 | len(size)]) + size + body


def _seq(*parts: bytes) -> bytes:
    return _tlv(0x30, b"".join(parts))


def _integer(value: int) -> bytes:
    body = value.to_bytes(max(1, (value.bit_length() + 8) // 8), "big")  # +8: bit cao nhất của byte đầu luôn 0 (số dương)
    return _tlv(0x02, body)


def _oid(dotted: str) -> bytes:
    arcs = [int(part) for part in dotted.split(".")]
    body = bytearray([arcs[0] * 40 + arcs[1]])
    for arc in arcs[2:]:
        chunk = [arc & 0x7F]
        arc >>= 7
        while arc:
            chunk.append(0x80 | (arc & 0x7F))
            arc >>= 7
        body += bytes(reversed(chunk))
    return _tlv(0x06, bytes(body))


def _bits(body: bytes) -> bytes:
    return _tlv(0x03, b"\x00" + body)


def _utc(moment: float) -> bytes:
    return _tlv(0x17, time.strftime("%y%m%d%H%M%SZ", time.gmtime(moment)).encode("ascii"))


_ECDSA_SHA256 = _seq(_oid("1.2.840.10045.4.3.2"))
_NAME = _seq(_tlv(0x31, _seq(_oid("2.5.4.3"), _tlv(0x0C, COMMON_NAME.encode("utf-8")))))
_EXTENSIONS = _tlv(0xA3, _seq(
    _seq(_oid("2.5.29.19"), _tlv(0x01, b"\xff"), _tlv(0x04, _seq())),                       # basicConstraints CA:FALSE
    _seq(_oid("2.5.29.15"), _tlv(0x01, b"\xff"), _tlv(0x04, _tlv(0x03, b"\x07\x80"))),      # keyUsage digitalSignature
    _seq(_oid("2.5.29.37"), _tlv(0x04, _seq(_oid("1.3.6.1.5.5.7.3.1")))),                   # extKeyUsage serverAuth
    _seq(_oid("2.5.29.17"), _tlv(0x04, _seq(_tlv(0x82, b"abook.local")))),                  # subjectAltName DNS
))


def generate(now: float | None = None) -> tuple[bytes, bytes]:
    """(chứng chỉ DER, khoá riêng PEM kiểu SEC1) - chứng chỉ tự ký ECDSA P-256 / SHA-256, hạn VALID_YEARS năm."""
    now = time.time() if now is None else now
    private = secrets.randbelow(_N - 1) + 1
    x, y = _multiply(private, _G)
    public = b"\x04" + x.to_bytes(32, "big") + y.to_bytes(32, "big")
    curve = _oid("1.2.840.10045.3.1.7")
    to_be_signed = _seq(
        _tlv(0xA0, _integer(2)),                                  # version 3
        _integer(int.from_bytes(secrets.token_bytes(16), "big") >> 1),
        _ECDSA_SHA256,
        _NAME,
        _seq(_utc(now - 86400), _utc(now + VALID_YEARS * 365 * 86400)),
        _NAME,
        _seq(_seq(_oid("1.2.840.10045.2.1"), curve), _bits(public)),
        _EXTENSIONS,
    )
    r, s = _sign(private, to_be_signed)
    certificate = _seq(to_be_signed, _ECDSA_SHA256, _bits(_seq(_integer(r), _integer(s))))
    key = _seq(_integer(1), _tlv(0x04, private.to_bytes(32, "big")), _tlv(0xA0, curve), _tlv(0xA1, _bits(public)))
    return certificate, _pem("EC PRIVATE KEY", key)


def _pem(label: str, der: bytes) -> bytes:
    import base64

    body = base64.encodebytes(der).replace(b"\n", b"").decode("ascii")
    lines = [body[start:start + 64] for start in range(0, len(body), 64)]
    return ("\n".join([f"-----BEGIN {label}-----", *lines, f"-----END {label}-----"]) + "\n").encode("ascii")


# ---- vân tay ------------------------------------------------------------------------------------------------------
def fingerprint(der: bytes) -> str:
    """SHA-256 của chứng chỉ DER, 64 ký tự hex thường - dạng lưu và gửi qua mạng (Kotlin: Pin.fingerprint)."""
    return hashlib.sha256(der).hexdigest()


def display(value: str) -> str:
    """Vân tay để người dùng nhìn: nhóm 4 ký tự, hoa - "AB12 CD34 ..."."""
    return " ".join(value[start:start + 4] for start in range(0, len(value), 4)).upper()


# ---- danh tính của một máy phục vụ ------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Identity:
    """Chứng chỉ + khoá riêng của máy này. `path` None: bản tạm trong bộ nhớ (bài thử)."""

    certificate: bytes
    key_pem: bytes
    path: Path | None = None

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.certificate)

    def server_context(self) -> ssl.SSLContext:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        if self.path is not None:
            context.load_cert_chain(self.path)
            return context
        # `ssl` chỉ nạp được từ file: bản trong bộ nhớ qua một file tạm, xoá ngay sau khi nạp.
        handle, name = tempfile.mkstemp(suffix=".pem")
        try:
            with os.fdopen(handle, "wb") as out:
                out.write(self._pem())
            context.load_cert_chain(name)
        finally:
            os.unlink(name)
        return context

    def _pem(self) -> bytes:
        return _pem("CERTIFICATE", self.certificate) + self.key_pem


def _read_pem(path: Path) -> Identity | None:
    """Đọc lại file đã lưu; hỏng (cắt dở, sửa tay) thì None để sinh mới - vân tay đổi, thiết bị phải ghép lại."""
    import base64

    try:
        text = path.read_text(encoding="ascii")
        body = text.split("-----BEGIN CERTIFICATE-----")[1].split("-----END CERTIFICATE-----")[0]
        key = text[text.index("-----BEGIN EC PRIVATE KEY-----"):].encode("ascii")
        identity = Identity(base64.b64decode("".join(body.split())), key, path)
        identity.server_context()  # chứng chỉ và khoá phải khớp nhau
        return identity
    except (OSError, ValueError, IndexError, ssl.SSLError):
        return None


_SAVE = threading.Lock()


def load_or_create(path: Path) -> Identity:
    """Danh tính đã lưu ở `path`, hay sinh mới và lưu (ghi nguyên tử, chỉ chủ file đọc được khi hệ điều hành cho phép)."""
    path = Path(path)
    with _SAVE:
        found = _read_pem(path)
        if found is not None:
            return found
        certificate, key = generate()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(_pem("CERTIFICATE", certificate) + key)  # write_bytes: LF, không CRLF của Windows
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, path)
        return Identity(certificate, key, path)


_EPHEMERAL: Identity | None = None


def ephemeral() -> Identity:
    """Danh tính tạm của tiến trình (sinh một lần): cho máy chủ dựng mà không ai đưa danh tính - luôn là TLS, không bao giờ HTTP."""
    global _EPHEMERAL
    with _SAVE:
        if _EPHEMERAL is None:
            certificate, key = generate()
            _EPHEMERAL = Identity(certificate, key)
        return _EPHEMERAL


# ---- phía kết nối ---------------------------------------------------------------------------------------------------
class PinError(ssl.SSLError):
    """Chứng chỉ máy kia không phải chứng chỉ đã ghi lúc ghép."""


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Nối HTTPS tới máy ABook và chỉ nhận chứng chỉ có vân tay `expected`; kiểm NGAY sau bắt tay, trước khi gửi byte nào
    (kể cả mã thiết bị). `expected` None: lần ghép đầu - nhận chứng chỉ nào cũng được, `peer_fingerprint` cho biết nó là gì
    để ghi lại. Không kiểm chuỗi tin cậy, không kiểm tên máy: vân tay thay cho cả hai."""

    def __init__(self, host: str, port: int, *, expected: str | None, timeout: float = 10.0) -> None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        super().__init__(host, port, timeout=timeout, context=context)
        self.expected = expected.lower() if expected else None
        self.peer_fingerprint = ""

    def connect(self) -> None:
        super().connect()
        der = self.sock.getpeercert(binary_form=True) if isinstance(self.sock, ssl.SSLSocket) else None
        self.peer_fingerprint = fingerprint(der) if der else ""
        if self.expected is not None and self.peer_fingerprint != self.expected:
            self.close()
            raise PinError("Chứng chỉ của máy kia khác lúc ghép")
