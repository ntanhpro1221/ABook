"""Độ to của từng giọng đọc: chỉnh lúc PHÁT (âm lượng của phần tử audio), không bao giờ mã hoá lại clip (bộ nhớ đệm dùng chung mọi mức).

Đo bằng BS.1770 (LUFS tích hợp) trên 60 câu, phiên Nhạc (docs/MUSIC_RESEARCH.md): giọng Studio nằm quanh -20,3 LUFS, đích -20 LUFS.
`gain_db` = đích - đo, luôn <= 0 (phần tử audio chỉ giảm được, không khuếch đại). Giọng chưa đo: 0 dB.
"""
from __future__ import annotations

TARGET_LUFS = -20.0

# mã giọng (đúng như `id` trong danh sách giọng) -> LUFS đã đo
MEASURED_LUFS = {
    "edge:vi-VN-HoaiMyNeural": -18.3,
    "edge:vi-VN-NamMinhNeural": -19.7,
}


def gain_db(voice_id: str) -> float:
    measured = MEASURED_LUFS.get(voice_id)
    return 0.0 if measured is None else round(min(0.0, TARGET_LUFS - measured), 1)
