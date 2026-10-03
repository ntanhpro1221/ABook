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
    # Giọng VieNeu (mô-đun tải thêm): 30 câu mỗi giọng qua đúng đường của Nghe ngay, scripts/measure_vieneu_loudness.py, đo 03-10.
    "vieneu:turbo/Adam bựa": -19.1,
    "vieneu:turbo/Trúc Ly": -19.4,
    "vieneu:turbo/Anh Khôi": -19.9,
    "vieneu:turbo/Mai Anh": -20.0,
    "vieneu:turbo/Minh Quân Pro": -19.8,
    "vieneu:turbo/Thùy Dung": -20.1,
    "vieneu:turbo/Thiền Tâm Đức": -19.7,
    "vieneu:turbo/Ngọc Huyền": -19.8,
    "vieneu:turbo/Quang Sơn": -19.7,
    "vieneu:turbo/Ngọc Trân": -19.8,
    "vieneu:turbo/Minh Đức": -20.1,
    "vieneu:turbo/Phạm Tuyên": -20.8,
    "vieneu:turbo/Thái Sơn": -20.3,
    "vieneu:turbo/Xuân Vĩnh": -20.6,
    "vieneu:turbo/Thanh Bình": -19.7,
    "vieneu:turbo/Ngọc Linh": -19.5,
    "vieneu:turbo/Đoan Trang": -19.9,
    "vieneu:turbo/Thục Đoan": -20.1,
    "vieneu:turbo/Minh Triết": -20.1,
    "vieneu:turbo/Mỹ Duyên": -19.9,
    "vieneu:turbo/Quỳnh Anh": -19.9,
    "vieneu:turbo/Đức Trí": -20.2,
    "vieneu:turbo/Kim Thanh": -20.5,
    "vieneu:turbo/Adam": -19.8,
    "vieneu:turbo/Mạnh Dũng": -19.8,
    "vieneu:nano/Adam": -19.5,
    "vieneu:nano/Ái Hân": -18.2,
    "vieneu:nano/Mỹ Duyên": -17.7,
    "vieneu:nano/Đức Trí": -18.6,
    "vieneu:nano/Hữu Quân": -17.8,
    "vieneu:nano/Xuân Tiên": -18.5,
    "vieneu:nano/Mai Anh": -18.5,
    "vieneu:nano/Trúc Ly": -18.1,
    "vieneu:nano/Anh Khôi": -18.4,
    "vieneu:nano/Minh Quân": -17.1,
    "vieneu:nano/Mạnh Dũng": -17.9,
}


def gain_db(voice_id: str) -> float:
    measured = MEASURED_LUFS.get(voice_id)
    return 0.0 if measured is None else round(min(0.0, TARGET_LUFS - measured), 1)
