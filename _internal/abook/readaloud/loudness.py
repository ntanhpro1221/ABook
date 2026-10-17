"""Độ to của từng giọng đọc: chỉnh lúc PHÁT (âm lượng của phần tử audio), không mã hoá lại clip (bộ nhớ đệm dùng chung mọi mức) - trừ phần bù theo clip
của giọng VieNeu ở cuối file (câu ngắn nhỏ hơn mức giọng được nâng lên ngay lúc làm clip).

Đo bằng BS.1770 (LUFS tích hợp) trên 60 câu, phiên Nhạc (docs/MUSIC_RESEARCH.md): giọng Studio nằm quanh -20,3 LUFS, đích -20 LUFS.
`gain_db` = đích - đo, luôn <= 0 (phần tử audio chỉ giảm được, không khuếch đại). Giọng chưa đo: 0 dB.
"""
from __future__ import annotations

import math
from typing import Any

TARGET_LUFS = -20.0

# mã giọng (đúng như `id` trong danh sách giọng) -> LUFS đã đo
MEASURED_LUFS = {
    "edge:vi-VN-HoaiMyNeural": -18.3,
    "edge:vi-VN-NamMinhNeural": -19.7,
    # Giọng VieNeu (mô-đun tải thêm): 30 câu mỗi giọng qua đúng đường của Nghe ngay, scripts/measure_vieneu_loudness.py, đo 03-10.
    "vieneu:turbo/Adam bựa": -19.1,
    "vieneu:turbo/Trúc Ly": -19.4,
    "vieneu:turbo/Thiện Minh": -19.9,
    "vieneu:turbo/Mai Anh": -20.0,
    "vieneu:turbo/Hải Đăng": -19.8,
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
    "vieneu:turbo/Quốc Tuấn": -19.8,
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


# ---- bù theo clip cho giọng VieNeu (vnloud) -----------------------------------------------------------------------------------------------
# Giọng VieNeu đọc câu thường đúng mức đo ở trên, nhưng thoại ngắn ("Ừ.", "Hừ.") ra nhỏ hơn 3-10 LU (Đức Trí turbo: -6,2; nano: -7,3 - phiên Nhạc,
# PLAN_lx §9). `volume` của phần tử audio chỉ giảm được, nên câu nhỏ được nâng NGAY TRONG clip lúc làm ra (service.clip), trước khi vào bộ đệm;
# mức giọng ở trên vẫn chỉnh lúc phát như cũ. Bản Kotlin: readaloud/ClipLift.kt (cùng hằng số, cùng fixture: tests/fixtures/vieneu/android/lift.json).
LIFT_PREFIX = "vieneu:"
LIFT_TAG = "ld1"          # dấu trong khoá bộ đệm: clip VieNeu làm trước khi có bù không trúng đệm nữa (chỉ VieNeu, Edge giữ nguyên)
LIFT_DEADBAND_DB = 2.0    # chỉ bù phần thiếu quá 2 LU: câu thường lệch tới -2 quanh mức giọng vẫn nguyên (đo 1080 câu thường: 99,8 % trong 2 LU)
LIFT_MAX_DB = 8.0
LIFT_CEILING_DBTP = -1.0  # đỉnh thật sau khi bù (bảng FIR của music_mix.json, như bản xuất kèm nhạc)
LIFT_SAFETY_DB = 0.01     # đệm cho làm tròn int16
LIFT_PAD_SECONDS = 0.5    # đo clip ngắn như phiên Nhạc: đệm lặng hai đầu cho đủ một khối 400 ms (cổng tương đối lo phần lặng)
LIFT_MIN_SECONDS = 0.15   # ngắn hơn: không đo được cho tin cậy
LIFT_MIN_LUFS = -45.0     # nhỏ hơn: hơi thở / nhiễu, không phải lời - không bù


def lifts(voice_id: str) -> bool:
    """Giọng này được bù theo clip: giọng VieNeu đã có mức đo."""
    return voice_id.startswith(LIFT_PREFIX) and voice_id in MEASURED_LUFS


def clip_lufs(samples: Any, rate: int) -> float | None:
    """Độ to LUFS (BS.1770, một kênh) của một clip, đệm lặng `LIFT_PAD_SECONDS` hai đầu; None: quá ngắn / lặng hẳn."""
    import numpy as np

    from .. import audio_io

    x = np.asarray(samples, dtype=np.float64).reshape(-1)
    if x.size < LIFT_MIN_SECONDS * rate:
        return None
    pad = np.zeros(int(LIFT_PAD_SECONDS * rate))
    return audio_io.integrated_loudness_lufs(np.concatenate([pad, x, pad]), rate)


def true_peak_dbtp(samples: Any) -> float:
    import numpy as np

    from ..webui import music_mix, music_render

    x = np.asarray(samples, dtype=np.float64).reshape(-1, 1)
    return music_render.true_peak_db(x, music_mix.MIX["truePeakFir"]) if x.size else -math.inf


def lift_db(voice_id: str, samples: Any, rate: int) -> float:
    """Bao nhiêu dB nâng clip `samples` (mẫu thực, [-1, 1]) của giọng `voice_id`: (mức giọng - mức clip - vùng chết), kẹp [0, +8], không quá chỗ còn
    trống tới -1 dBTP; làm tròn 0,1 dB. 0 = giữ nguyên (giọng chưa đo, clip không đo được / quá nhỏ, đã đủ to hay đã sát trần đỉnh)."""
    if not lifts(voice_id):
        return 0.0
    level = clip_lufs(samples, rate)
    if level is None or level < LIFT_MIN_LUFS:
        return 0.0
    wanted = min(LIFT_MAX_DB, MEASURED_LUFS[voice_id] - level - LIFT_DEADBAND_DB)
    if wanted < 0.05:
        return 0.0
    room = LIFT_CEILING_DBTP - LIFT_SAFETY_DB - true_peak_dbtp(samples)
    return max(0.0, math.floor(min(wanted, room) * 10 + 1e-9) / 10)


def lift_wav(voice_id: str, wav: bytes) -> bytes:
    """WAV 16-bit một kênh `wav` của giọng `voice_id`, nâng theo [lift_db]; không cần nâng thì trả đúng các byte vào."""
    import io
    import wave

    import numpy as np

    from . import vieneu

    if not lifts(voice_id):
        return wav
    with wave.open(io.BytesIO(wav), "rb") as handle:
        rate, channels, width = handle.getframerate(), handle.getnchannels(), handle.getsampwidth()
        pcm = np.frombuffer(handle.readframes(handle.getnframes()), dtype="<i2")
    if channels != 1 or width != 2:
        return wav
    samples = pcm.astype(np.float64) / 32767.0
    gain = lift_db(voice_id, samples, rate)
    if gain <= 0.0:
        return wav
    return vieneu.wav_bytes(samples * 10.0 ** (gain / 20.0), rate)
