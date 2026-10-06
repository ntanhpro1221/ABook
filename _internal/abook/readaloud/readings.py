"""Cách đọc riêng của một cuốn chỉ có chữ ("Đọc từ này là…", lớp sửa `readings` - webui/book_edits.py): {chữ hiện: chữ đọc}.

Biến đổi để đọc, chữ hiện không đổi. Áp theo TỪNG CHỮ HIỆN (đơn vị `\\S+`, `word_timing.tokens`): chữ hiện có lõi (bỏ dấu câu / ngoặc hai
đầu) trùng đúng một khoá (phân biệt hoa thường, chỉ cả từ) thì lõi ấy được thay bằng chữ đọc, dấu câu hai đầu giữ nguyên. Chữ đọc nhiều
từ được nối bằng `JOINER` để vẫn là MỘT chữ - số chữ hiện không đổi nên mốc từng chữ vẫn khớp chữ hiện (một vùng sáng cho cả cụm).

Giọng đọc trên máy (VieNeu, Supertonic) áp trong `vieneu.spoken_tokens`, sau bước đọc tên; giọng khác (Edge, giọng dùng khoá riêng, giọng
của máy) nhận `spoken_text` - chữ đem đọc đã thay. Khoá bộ đệm clip thêm `tag`: chỉ những cách đọc có mặt trong đoạn, nên đổi một cách đọc
chỉ đọc lại những đoạn có từ ấy. Bản Kotlin y hệt: `readaloud/Readings.kt`; bộ ví dụ chung tests/fixtures/book_edits/readings/.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Mapping

# Đo 06-10 (HoaiMy): Edge báo MỘT mốc cho cả "Ha-ru-tô" (550-1212 ms), dài ngang "Ha ru tô" (525-1225 ms) - không đọc dấu gạch. sea-g2p
# cũng đọc liền (names.spoken_names đã nối tên bằng gạch).
JOINER = "-"
_TOKEN = re.compile(r"\S+")


def _core_char(char: str) -> bool:
    return unicodedata.category(char)[0] in "LMN"


def core_span(token: str) -> tuple[int, int]:
    """[đầu, cuối) của lõi chữ: bỏ mọi ký tự không phải chữ / dấu thanh / số ở hai đầu ("“Haruto,”" -> "Haruto")."""
    start, end = 0, len(token)
    while start < end and not _core_char(token[start]):
        start += 1
    while end > start and not _core_char(token[end - 1]):
        end -= 1
    return start, end


def is_word(text: str) -> bool:
    """Khoá hợp lệ của một cách đọc: một chữ (không khoảng trắng), đã là lõi của chính nó, dạng NFC."""
    return bool(text) and core_span(text) == (0, len(text)) and not any(char.isspace() for char in text) \
        and unicodedata.is_normalized("NFC", text)


def spoken_form(value: str) -> str:
    """Chữ đọc thành MỘT chữ hiện: khoảng trắng giữa các từ thành `JOINER`."""
    return JOINER.join(value.split())


def _read(token: str, readings: Mapping[str, str]) -> str | None:
    start, end = core_span(token)
    if start == end:
        return None
    value = readings.get(unicodedata.normalize("NFC", token[start:end]))
    return None if value is None else token[:start] + spoken_form(value) + token[end:]


def apply_tokens(toks: list[str], out: list[str], readings: Mapping[str, str] | None) -> None:
    """Thay tại chỗ trong `out` (chữ đem đọc, cùng số phần tử với `toks`) mọi chữ hiện có cách đọc riêng."""
    if not readings:
        return
    for index, token in enumerate(toks):
        said = _read(token, readings)
        if said is not None:
            out[index] = said


def spoken_text(text: str, readings: Mapping[str, str] | None) -> str:
    """Chữ đem đọc của cả đoạn cho giọng nhận chữ thô: khoảng trắng giữ nguyên, số chữ hiện không đổi."""
    if not readings:
        return text
    return _TOKEN.sub(lambda match: _read(match.group(), readings) or match.group(), text)


def applicable(text: str, readings: Mapping[str, str] | None) -> list[tuple[str, str]]:
    """Các cách đọc có mặt trong đoạn, theo thứ tự xuất hiện lần đầu."""
    if not readings:
        return []
    seen: dict[str, str] = {}
    for token in _TOKEN.findall(text):
        start, end = core_span(token)
        key = unicodedata.normalize("NFC", token[start:end])
        if start < end and key in readings and key not in seen:
            seen[key] = readings[key]
    return list(seen.items())


def tag(text: str, readings: Mapping[str, str] | None) -> str:
    """Dấu cho khoá bộ đệm clip: "" khi đoạn không có từ nào có cách đọc riêng (khoá như trước), không thì "r" + 16 số hex của các cách
    đọc có mặt."""
    found = applicable(text, readings)
    if not found:
        return ""
    return "r" + hashlib.sha256("\n".join(f"{key}\t{value}" for key, value in found).encode("utf-8")).hexdigest()[:16]
