"""Chữ đem đọc cho giọng nhận chữ thô nhưng đọc hay hơn khi được chuẩn hoá như giọng trên máy (Edge: `EdgeProvider.normalises_text`).

Đo a39 (Whisper large-v3-turbo, 74 câu bịa x 2 giọng Edge): tỉ lệ âm tiết sai 29% với chữ thô, 12% với đúng chữ mà đường VieNeu gửi
(`vieneu.spoken_tokens`) - thắng lớn ở tên Nhật + kính ngữ (33% -> 2%), tiếng kêu / thán từ ("Grrr" đừng đánh vần), nghìn kiểu Anh "1,500",
ký hiệu "+50" "x2" "3-5" "100/250", viết tắt ("MP" đừng đọc "Megapixel"). Nên Edge dùng CÙNG bước biến đổi với giọng trên máy, không bộ luật con riêng;
giọng dùng khoá (Azure, Google, FPT, Viettel) chưa đo nên vẫn nhận chữ thô (+ cách đọc riêng của cuốn: `readings.spoken_layout`).

Khác giọng trên máy, Edge nhận một chuỗi và báo mốc từng MẢNH nó đọc. Một chữ hiện có thể thành nhiều chữ đọc ("Aaaa" -> "a… a") hay không còn chữ nào
(cụm đọc ngắn hơn số chữ hiện, `readings`), nên `layout` trả chuỗi đem đọc + khoảng chữ đọc của từng chữ hiện, `expand_words` trả mốc về đủ chữ hiện.
Edge nói được tiếng Anh (`speaks_english` True): chữ Anh để nguyên cho nó đọc. Bản Kotlin y hệt: `readaloud/SpokenText.kt`; bộ ví dụ chung tests/fixtures/readaloud/spoken/.
"""
from __future__ import annotations

from typing import Mapping

from . import readings as book_readings, vieneu
from .mapping import fold, tokens

TAG = "tn"  # dấu trong khoá bộ đệm: clip Edge làm từ chữ thô (bản trước) không bao giờ trúng đệm của chữ đã chuẩn hoá


def tag(text: str, origin: str | None, speaks_english: bool = True) -> str:
    """Dấu cách đọc của đoạn trong khoá bộ đệm: [TAG] + gốc của cuốn khi nó làm tên đọc khác (`vieneu.reading_tag`), nối bằng "+"."""
    return "+".join(part for part in (vieneu.reading_tag(text, origin, speaks_english), TAG) if part)


def layout(text: str, origin: str | None, speaks_english: bool = True,
           readings: Mapping[str, str] | None = None) -> tuple[str, list[tuple[int, int] | None]]:
    """(chuỗi đem đọc, khoảng) cho giọng nhận chữ thô. Chuỗi = các chữ đọc của `vieneu.spoken_tokens` nối bằng một dấu cách ("_" giữ chữ "o" lẻ là việc của
    engine VieNeu, bỏ như Studio). `khoảng[i]` = (chữ đọc đầu, chữ đọc cuối) của chữ hiện `i`, None khi chữ ấy không còn chữ đọc nào - xem `expand_words`.
    Chuẩn hoá làm đoạn hết sạch chữ (không thể xảy ra với đoạn có chữ, nhưng Edge từ chối chuỗi rỗng) thì đọc nguyên chữ thô."""
    shown = tokens(text)
    said = [word if word == shown_word else word.replace("_", "") for shown_word, word in zip(shown, vieneu.spoken_tokens(shown, origin, speaks_english, readings))]
    flat: list[str] = []
    spans: list[tuple[int, int] | None] = []
    for word in said:
        parts = tokens(word)
        spans.append((len(flat), len(flat) + len(parts) - 1) if parts else None)
        flat += parts
    if not fold(" ".join(flat)):
        return text, [(index, index) for index in range(len(shown))]
    return " ".join(flat), spans


def expand_words(words: list[list[int]], spans: list[tuple[int, int] | None]) -> list[list[int]]:
    """Mốc từng chữ ĐỌC (`mapping.map_boundaries` trên chuỗi của `layout`) -> mốc từng chữ HIỆN: chữ hiện thành nhiều chữ đọc trải từ đầu chữ đọc đầu tới cuối chữ đọc cuối;
    chữ không còn chữ đọc nào đứng ở cuối mốc chữ trước nó (`readings.expand_words`)."""
    merged: list[list[int]] = []
    slots: list[int | None] = []
    for span in spans:
        if span is None or span[1] >= len(words):
            slots.append(None)
            continue
        merged.append([words[span[0]][0], words[span[1]][1]])
        slots.append(len(merged) - 1)
    return book_readings.expand_words(merged, slots)
