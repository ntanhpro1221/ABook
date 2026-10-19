"""PCM 16-bit một kênh -> FLAC trong MP4 phân mảnh (fMP4), để trình phát nối vào MediaSource từng khúc một (giọng trên máy phát luồng, local_stream.py).

MediaSource của Chromium (WebView2, trình duyệt) không nhận PCM / WAV; máy chủ Nghe ngay lại không có bộ mã MP3 / AAC / Opus. FLAC thì nhận
(`audio/mp4; codecs="flac"`), và FLAC có khung VERBATIM: mẫu int16 để nguyên, không nén - viết bằng Python thuần, giải ra ĐÚNG từng mẫu int16 của
file WAV cuối (không mất gì). Cỡ ~ PCM (96 KB mỗi giây ở 48 kHz): chỉ đi trong máy / mạng nhà.

Định dạng: FLAC (xiph.org/flac/format.html: STREAMINFO, đầu khung + CRC-8, khung con VERBATIM, CRC-16), FLAC trong ISO-BMFF (xiph flac/ISOBMFF: hộp `fLaC` + `dfLa`),
MP4 phân mảnh (ISO/IEC 14496-12: ftyp + moov(mvex) rồi moof + mdat).
"""
from __future__ import annotations

import struct
from typing import Any

MIME = 'audio/mp4; codecs="flac"'
BLOCK = 4096  # mẫu mỗi khung FLAC (khung cuối của một mảnh ngắn hơn)

# Tần số mẫu có mã riêng trong đầu khung FLAC; tần số khác: mã 0 = lấy từ STREAMINFO.
_RATE_CODES = {88200: 1, 176400: 2, 192000: 3, 8000: 4, 16000: 5, 22050: 6, 24000: 7, 32000: 8, 44100: 9, 48000: 10, 96000: 11}


def _crc_table(poly: int, width: int) -> list[int]:
    top, mask = 1 << (width - 1), (1 << width) - 1
    table = []
    for byte in range(256):
        crc = byte << (width - 8)
        for _ in range(8):
            crc = ((crc << 1) ^ poly) & mask if crc & top else (crc << 1) & mask
        table.append(crc)
    return table


_CRC8 = _crc_table(0x07, 8)


def crc8(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc = _CRC8[crc ^ byte]
    return crc


_reach: Any = None  # [_byte_parts]


def _byte_parts(length: int) -> Any:
    """Bảng (cách cuối d byte, giá trị byte) -> phần của byte ấy trong CRC-16. CRC không phản chiếu, khởi 0 là tuyến tính: crc(M) = M(x)·x^16 mod P, nên
    bit cách cuối k bit góp x^(k+16) mod P và CRC = XOR các phần - numpy làm cả khung một lượt (vòng Python từng byte: 0,15 s mỗi khúc 13 s ở 44,1 kHz)."""
    global _reach
    import numpy as np

    if _reach is None or len(_reach) < length:
        rows = max(length, 2 * BLOCK + 32)
        powers, value = np.empty(rows * 8, dtype=np.uint16), 0x8005  # x^16 mod P
        for k in range(rows * 8):
            powers[k] = value
            value = ((value << 1) ^ 0x8005) & 0xFFFF if value & 0x8000 else value << 1
        byte = np.arange(256)
        table = np.zeros((rows, 256), dtype=np.uint16)
        for bit in range(8):
            table ^= np.where((byte >> bit) & 1, powers[bit::8][:, None], 0).astype(np.uint16)
        _reach = table
    return _reach


def crc16(data: bytes) -> int:
    import numpy as np

    if not data:
        return 0
    values = np.frombuffer(data, dtype=np.uint8)
    rows = _byte_parts(len(values))[len(values) - 1::-1]  # byte i cách cuối len - 1 - i
    return int(np.bitwise_xor.reduce(rows[np.arange(len(values)), values]))


def _coded_number(value: int) -> bytes:
    """Số mẫu đầu khung theo kiểu UTF-8 mở rộng của FLAC (tới 36 bit)."""
    if value < 0x80:
        return bytes([value])
    for count, limit in ((2, 0x800), (3, 0x10000), (4, 0x200000), (5, 0x4000000), (6, 0x80000000), (7, 0x1000000000)):
        if value < limit:
            out = [0x80 | ((value >> (6 * i)) & 0x3F) for i in range(count - 2, -1, -1)]
            lead = (0xFF << (8 - count)) & 0xFF | (value >> (6 * (count - 1)))
            return bytes([lead & 0xFF, *out])
    raise ValueError("số mẫu quá lớn")


def frame(pcm: bytes, first_sample: int, rate: int) -> bytes:
    """Một khung FLAC VERBATIM: `pcm` = int16 little-endian (như trong WAV), `first_sample` = số mẫu đầu khung trong cả luồng."""
    count = len(pcm) // 2
    if not 0 < count <= 65536:
        raise ValueError("khung FLAC phải có 1..65536 mẫu")
    header = bytes([0xFF, 0xF9, 0x70 | _RATE_CODES.get(rate, 0), 0x08]) + _coded_number(first_sample) + struct.pack(">H", count - 1)
    header += bytes([crc8(header)])
    swapped = bytearray(pcm)
    swapped[0::2], swapped[1::2] = pcm[1::2], pcm[0::2]  # little-endian -> big-endian
    body = header + b"\x02" + bytes(swapped)  # khung con: 0 | VERBATIM 000001 | không bỏ bit
    return body + struct.pack(">H", crc16(body))


def _box(kind: bytes, *parts: bytes) -> bytes:
    payload = b"".join(parts)
    return struct.pack(">I", 8 + len(payload)) + kind + payload


def _full(kind: bytes, version: int, flags: int, *parts: bytes) -> bytes:
    return _box(kind, struct.pack(">I", (version << 24) | flags), *parts)


_MATRIX = struct.pack(">9I", 0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000)


def streaminfo(rate: int) -> bytes:
    """STREAMINFO (34 byte): khối 16..BLOCK mẫu, cỡ khung / tổng số mẫu / MD5 chưa biết (0)."""
    bits = (rate << 44) | (0 << 41) | (15 << 36)  # tần số 20 bit, kênh - 1 = 0, bit mẫu - 1 = 15, tổng mẫu 36 bit = 0
    return struct.pack(">HH", 16, BLOCK) + bytes(6) + bits.to_bytes(8, "big") + bytes(16)


def init_segment(rate: int) -> bytes:
    """Mảnh khởi đầu (ftyp + moov): một rãnh âm thanh FLAC một kênh 16 bit, thang thời gian = tần số mẫu."""
    ftyp = _box(b"ftyp", b"isom", struct.pack(">I", 0x200), b"isom", b"iso6", b"mp41")
    mvhd = _full(b"mvhd", 0, 0, struct.pack(">IIII", 0, 0, rate, 0), struct.pack(">IH", 0x00010000, 0x0100), bytes(10), _MATRIX, bytes(24),
                 struct.pack(">I", 2))
    tkhd = _full(b"tkhd", 0, 3, struct.pack(">IIIII", 0, 0, 1, 0, 0), bytes(8), struct.pack(">HHHH", 0, 0, 0x0100, 0), _MATRIX, struct.pack(">II", 0, 0))
    mdhd = _full(b"mdhd", 0, 0, struct.pack(">IIIIHH", 0, 0, rate, 0, 0x55C4, 0))
    hdlr = _full(b"hdlr", 0, 0, struct.pack(">I", 0), b"soun", bytes(12), b"SoundHandler\x00")
    dfla = _full(b"dfLa", 0, 0, bytes([0x80, 0, 0, 34]), streaminfo(rate))
    entry = _box(b"fLaC", bytes(6), struct.pack(">H", 1), bytes(8), struct.pack(">HHHH", 1, 16, 0, 0), struct.pack(">I", (rate << 16) if rate < 65536 else 0), dfla)
    stbl = _box(b"stbl", _full(b"stsd", 0, 0, struct.pack(">I", 1), entry), _full(b"stts", 0, 0, struct.pack(">I", 0)),
                _full(b"stsc", 0, 0, struct.pack(">I", 0)), _full(b"stsz", 0, 0, struct.pack(">II", 0, 0)), _full(b"stco", 0, 0, struct.pack(">I", 0)))
    minf = _box(b"minf", _full(b"smhd", 0, 0, struct.pack(">HH", 0, 0)), _box(b"dinf", _full(b"dref", 0, 0, struct.pack(">I", 1), _full(b"url ", 0, 1))), stbl)
    trak = _box(b"trak", tkhd, _box(b"mdia", mdhd, hdlr, minf))
    mvex = _box(b"mvex", _full(b"trex", 0, 0, struct.pack(">IIIII", 1, 1, 0, 0, 0)))
    return ftyp + _box(b"moov", mvhd, trak, mvex)


def fragment(pcm: bytes, first_sample: int, rate: int, sequence: int) -> bytes:
    """Một mảnh (moof + mdat) chở `pcm` (int16 little-endian, số byte chẵn) bắt đầu ở mẫu `first_sample` của luồng; `sequence` tăng dần từ 1.
    Chia thành các khung đều nhau không quá BLOCK mẫu."""
    count = len(pcm) // 2
    if count <= 0:
        return b""
    frames_n = -(-count // BLOCK)
    size = -(-count // frames_n)
    frames, at = [], 0
    while at < count:
        n = min(size, count - at)
        frames.append((frame(pcm[2 * at:2 * (at + n)], first_sample + at, rate), n))
        at += n

    def moof(offset: int) -> bytes:
        trun = _full(b"trun", 0, 0x000301, struct.pack(">Ii", len(frames), offset), *(struct.pack(">II", n, len(data)) for data, n in frames))
        traf = _box(b"traf", _full(b"tfhd", 0, 0x020000, struct.pack(">I", 1)), _full(b"tfdt", 1, 0, struct.pack(">Q", first_sample)), trun)
        return _box(b"moof", _full(b"mfhd", 0, 0, struct.pack(">I", sequence)), traf)

    head = moof(0)
    head = moof(len(head) + 8)  # dữ liệu mẫu bắt đầu ngay sau đầu hộp mdat
    return head + _box(b"mdat", *(data for data, _ in frames))
