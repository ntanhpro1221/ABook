"""Mốc từng chữ cho giọng KHÔNG báo mốc (FPT.AI, Viettel AI): chia độ dài clip theo âm tiết, chừa chỗ ngắt ở dấu câu.

Tiếng Việt đọc các âm tiết khá đều (docs/LISTEN_ANYTHING.md "Word timings": chia theo âm tiết đã đúng ~56% trong 100 ms, chưa dò khoảng lặng),
nên mỗi chữ hiện nhận phần thời gian tỉ lệ với số âm tiết nó được đọc ra (`word_timing.syllable_count`: số đọc thành lời, tên ngoại theo cụm
nguyên âm), và sau chữ kết thúc bằng dấu câu có thêm một khoảng ngắt (dấu phẩy ngắn, hết câu dài hơn). Kết quả là các `Boundary` (một mảnh
mỗi chữ, kèm vị trí ký tự) đi qua `mapping.map_boundaries` như mọi giọng khác.

Điện thoại cài lại đúng thuật toán này (`SyllableSpread.kt`) và chạy trên cùng bộ ví dụ `tests/fixtures/readaloud/spread/` (README.md ở đó).
Toàn số nguyên.
"""
from __future__ import annotations

import re
import unicodedata

from .mapping import Boundary

SYLLABLE = 4  # đơn vị thời gian của một âm tiết
COMMA_PAUSE = 4  # sau , ; : — –  (đo trên Edge: ngắt phẩy ~ một âm tiết)
SENTENCE_PAUSE = 8  # sau . ! ? …  (~ hai âm tiết)
_CLOSERS = "\"'”’)]»"
_COMMA = ",;:—–"
_SENTENCE = ".!?…"
_TOKEN = re.compile(r"\S+")


def pause_after(token: str) -> int:
    core = token.rstrip(_CLOSERS)
    if not core:
        return 0
    if core[-1] in _SENTENCE:
        return SENTENCE_PAUSE
    if core[-1] in _COMMA:
        return COMMA_PAUSE
    return 0


def boundaries(text: str, duration_ms: int) -> list[Boundary]:
    """Một `Boundary` cho mỗi chữ hiện có âm tiết: [bắt đầu, kết thúc] ms trong `duration_ms`, `char` = vị trí chữ trong `text`.
    Chữ không đọc ra âm (dấu "—" đứng riêng) không có mảnh: `map_boundaries` nội suy nó."""
    # Đếm âm tiết như căn chữ của Studio; nhập muộn để gói readaloud nạp nhẹ.
    from ..webui.word_timing import syllable_count

    found = list(_TOKEN.finditer(text))
    weights = [SYLLABLE * syllable_count(unicodedata.normalize("NFC", match.group())) for match in found]
    pauses = [pause_after(match.group()) if index + 1 < len(found) else 0 for index, match in enumerate(found)]
    total = sum(weights) + sum(pauses)
    if total == 0 or duration_ms <= 0:
        return []
    out: list[Boundary] = []
    before = 0
    for match, weight, pause in zip(found, weights, pauses):
        if weight:
            out.append(Boundary(match.group(), duration_ms * before // total, duration_ms * (before + weight) // total, match.start()))
        before += weight + pause
    return out
