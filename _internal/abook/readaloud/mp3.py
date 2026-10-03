"""Độ dài thật của một file MP3 (lớp III) bằng cách đi qua từng khung - không giải mã, không thư viện ngoài.

Giọng dùng khoá (Google, FPT.AI, Viettel AI) trả MP3 mà không nói độ dài hay tốc độ bit chắc chắn; nhiều lượt gọi của một đoạn nối liền nhau
(mỗi lượt một dòng MP3 riêng) nên phải cộng đúng từng khung. Điện thoại có bản Kotlin cùng cách tính (`Mp3.kt`).
Định dạng khung: ISO/IEC 11172-3 và 13818-3 (đầu khung 4 byte; độ dài = 144 * bitrate / tần số + đệm với MPEG-1, 72 * ... với MPEG-2/2.5).
"""
from __future__ import annotations

# kbps theo chỉ số 1..14 (0 = "free", 15 = hỏng): MPEG-1 lớp III, MPEG-2/2.5 lớp III.
_BITRATES_V1 = (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)
_BITRATES_V2 = (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160)
_RATES = {3: (44100, 48000, 32000), 2: (22050, 24000, 16000), 0: (11025, 12000, 8000)}  # phiên bản (2 bit) -> tần số


def _skip_id3(data: bytes, at: int) -> int:
    """Bỏ thẻ ID3v2 ở `at` nếu có (độ dài 4 byte "syncsafe" 7 bit mỗi byte, + 10 byte đầu, + 10 byte chân nếu cờ có)."""
    if data[at:at + 3] == b"ID3" and len(data) >= at + 10:
        size = (data[at + 6] << 21) | (data[at + 7] << 14) | (data[at + 8] << 7) | data[at + 9]
        footer = 10 if data[at + 5] & 0x10 else 0
        return at + 10 + size + footer
    return at


def frame_at(data: bytes, at: int) -> tuple[int, int, int] | None:
    """Khung lớp III bắt đầu ở `at`: (độ dài byte, số mẫu, tần số) hay None nếu không phải đầu khung hợp lệ."""
    if at + 4 > len(data) or data[at] != 0xFF or data[at + 1] & 0xE0 != 0xE0:
        return None
    version = (data[at + 1] >> 3) & 0x03  # 3 = MPEG-1, 2 = MPEG-2, 0 = MPEG-2.5, 1 = dành riêng
    layer = (data[at + 1] >> 1) & 0x03  # 1 = lớp III
    bitrate_index = data[at + 2] >> 4
    rate_index = (data[at + 2] >> 2) & 0x03
    if version == 1 or layer != 1 or bitrate_index in (0, 15) or rate_index == 3:
        return None
    rate = _RATES[version][rate_index]
    padding = (data[at + 2] >> 1) & 0x01
    if version == 3:
        return 144_000 * _BITRATES_V1[bitrate_index] // rate + padding, 1152, rate
    return 72_000 * _BITRATES_V2[bitrate_index] // rate + padding, 576, rate


def duration_ms(data: bytes) -> int:
    """Tổng độ dài (ms, làm tròn xuống) của mọi khung MP3 lớp III trong `data`; thẻ ID3 (đầu hay giữa các dòng nối nhau) và rác bị bỏ qua.
    Không có khung nào -> 0."""
    at = 0
    micros = 0
    while at < len(data):
        skipped = _skip_id3(data, at)
        if skipped != at:
            at = skipped
            continue
        frame = frame_at(data, at)
        if frame is None:
            at += 1  # dò lại đầu khung
            continue
        size, samples, rate = frame
        micros += samples * 1_000_000 // rate
        at += size
    return micros // 1000
