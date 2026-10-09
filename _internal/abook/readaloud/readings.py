"""Cách đọc riêng của một cuốn chỉ có chữ ("Đọc từ này là…", lớp sửa `readings` - webui/book_edits.py): {khoá: chữ đọc}.

Khoá là MỘT chữ ("Haruto") hay một CỤM 2..6 chữ liền nhau nối bằng một dấu cách ("Hạ Vy", "ông Tư"; `is_key`). Biến đổi để đọc, chữ hiện không
đổi. Duyệt theo TỪNG CHỮ HIỆN (đơn vị `\\S+`, `word_timing.tokens`) từ trái sang phải, ở mỗi chỗ thử khoá DÀI NHẤT (theo số chữ) trước: các chữ hiện có lõi
(bỏ dấu câu / ngoặc hai đầu) trùng đúng từng chữ của khoá (phân biệt hoa thường, chỉ cả từ) và không có dấu câu chen GIỮA cụm ("Hạ, Vy" không khớp
"Hạ Vy") thì phần lõi được thay bằng chữ đọc, dấu câu đầu cụm và đuôi cụm giữ nguyên. Số chữ hiện không đổi nên mốc từng chữ vẫn khớp chữ hiện:
chữ đọc tách theo khoảng trắng thành m từ, chia đều cho k chữ hiện của cụm (nhóm đầu nhận phần dư), mỗi nhóm nối bằng `JOINER` thành MỘT chữ.
m < k: các chữ hiện cuối không còn từ nào, chữ đọc của chúng là "" (dấu câu đuôi cụm dính vào từ đọc cuối) - nơi tiêu thụ bỏ chữ rỗng.

Giọng đọc trên máy (VieNeu, Supertonic) áp trong `vieneu.spoken_tokens`, sau bước đọc tên (`vieneu.units` bỏ chữ rỗng khi ghép câu); giọng khác (Edge,
giọng dùng khoá riêng, giọng của máy) nhận `spoken_text` - chữ đem đọc đã thay (chữ rỗng mất khỏi chuỗi: `spoken_layout` kèm bảng chữ hiện -> chữ đem
đọc, `expand_words` trả mốc về đủ chữ hiện). Khoá bộ đệm clip thêm `tag`: chỉ những cách đọc có mặt trong đoạn, nên đổi một cách đọc chỉ đọc lại những
đoạn có cụm ấy. Bản Kotlin y hệt: `readaloud/Readings.kt`; bộ ví dụ chung tests/fixtures/book_edits/readings/.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Mapping

# Đo 06-10 (HoaiMy): Edge báo MỘT mốc cho cả "Ha-ru-tô" (550-1212 ms), dài ngang "Ha ru tô" (525-1225 ms) - không đọc dấu gạch. sea-g2p
# cũng đọc liền (names.spoken_names đã nối tên bằng gạch).
JOINER = "-"
KEY_WORDS_MAX = 6  # khoá dài nhất: 6 chữ liền nhau
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
    """Một chữ (không khoảng trắng), đã là lõi của chính nó, dạng NFC."""
    return bool(text) and core_span(text) == (0, len(text)) and not any(char.isspace() for char in text) \
        and unicodedata.is_normalized("NFC", text)


def is_key(text: str) -> bool:
    """Khoá hợp lệ của một cách đọc: 1..`KEY_WORDS_MAX` chữ (`is_word`) nối bằng MỘT dấu cách, dạng NFC."""
    words = text.split(" ")
    return 1 <= len(words) <= KEY_WORDS_MAX and all(is_word(word) for word in words) and unicodedata.is_normalized("NFC", text)


def spoken_form(value: str) -> str:
    """Chữ đọc thành MỘT chữ hiện: khoảng trắng giữa các từ thành `JOINER`."""
    return JOINER.join(value.split())


def _phrase_key(toks: list[str], at: int, count: int) -> str | None:
    """Khoá `count` chữ mà các chữ hiện `toks[at:at+count]` đang mang, None khi chúng không thể là một cụm: chữ nào không có lõi, hay có dấu câu CHEN GIỮA
    (đuôi ngoài lõi của chữ không phải cuối cụm, đầu ngoài lõi của chữ không phải đầu cụm)."""
    words = []
    for offset in range(count):
        token = toks[at + offset]
        start, end = core_span(token)
        if start == end or (offset and start) or (offset < count - 1 and end != len(token)):
            return None
        words.append(unicodedata.normalize("NFC", token[start:end]))
    return " ".join(words)


def _matches(toks: list[str], readings: Mapping[str, str]) -> list[tuple[int, int, str]]:
    """[(chữ hiện đầu, số chữ, khoá)] các cụm có cách đọc riêng, trái sang phải, khoá dài nhất thắng, mỗi chữ hiện thuộc nhiều nhất một cụm.
    Khoá có chữ đọc không còn từ nào không tính."""
    longest = min(KEY_WORDS_MAX, max((key.count(" ") + 1 for key, value in readings.items() if value.split()), default=0))
    found: list[tuple[int, int, str]] = []
    at = 0
    while at < len(toks):
        for count in range(min(longest, len(toks) - at), 0, -1):
            key = _phrase_key(toks, at, count)
            if key is not None and readings.get(key, "").split():
                found.append((at, count, key))
                at += count
                break
        else:
            at += 1
    return found


def _groups(value: str, count: int) -> list[str]:
    """Chữ đọc chia cho `count` chữ hiện: m từ thành `count` nhóm liền nhau đều nhất (nhóm đầu nhận phần dư), mỗi nhóm nối bằng `JOINER`; m < count thì nhóm cuối rỗng."""
    words = value.split()
    size, extra = divmod(len(words), count)
    groups, at = [], 0
    for index in range(count):
        take = size + (1 if index < extra else 0)
        groups.append(JOINER.join(words[at:at + take]))
        at += take
    return groups


def _spoken(toks: list[str], readings: Mapping[str, str]) -> list[str]:
    """Chữ đem đọc của từng chữ hiện (cùng số phần tử với `toks`; "" là chữ hiện không còn từ nào để đọc): chữ không thuộc cách đọc nào giữ nguyên."""
    out = list(toks)
    for at, count, key in _matches(toks, readings):
        groups = _groups(readings[key], count)
        first, last = core_span(toks[at])[0], core_span(toks[at + count - 1])[1]
        pieces = [toks[at][:first] + groups[0]] + groups[1:]
        spoken = max(index for index, group in enumerate(groups) if group)  # nhóm cuối còn từ: dấu câu đuôi cụm dính vào nó
        pieces[spoken] += toks[at + count - 1][last:]
        out[at:at + count] = pieces
    return out


def apply_tokens(toks: list[str], out: list[str], readings: Mapping[str, str] | None) -> None:
    """Thay tại chỗ trong `out` (chữ đem đọc, cùng số phần tử với `toks`) mọi chữ hiện có cách đọc riêng; chữ hiện cuối cụm không còn từ nào thành ""."""
    if not readings:
        return
    said = _spoken(toks, readings)
    for index, token in enumerate(toks):
        if said[index] != token:
            out[index] = said[index]


def spoken_layout(text: str, readings: Mapping[str, str] | None) -> tuple[str, list[int | None]]:
    """(chữ đem đọc của cả đoạn, bảng) cho giọng nhận chữ thô. Khoảng trắng giữ nguyên; chữ hiện không còn từ nào (cụm đọc ngắn hơn số chữ) mất khỏi chuỗi cùng
    khoảng trắng đứng trước nó. `bảng[i]` = số thứ tự trong chữ đem đọc của chữ hiện `i`, None cho chữ đã mất - xem `expand_words`."""
    matches = list(_TOKEN.finditer(text))
    if not readings:
        return text, list(range(len(matches)))
    said = _spoken([match.group() for match in matches], readings)
    parts: list[str] = []
    slots: list[int | None] = []
    kept = 0
    cursor = 0
    for match, word in zip(matches, said):
        if word:
            parts.append(text[cursor:match.start()] + word)
            slots.append(kept)
            kept += 1
        else:
            slots.append(None)
        cursor = match.end()
    parts.append(text[cursor:])
    return "".join(parts), slots


def spoken_text(text: str, readings: Mapping[str, str] | None) -> str:
    """Chữ đem đọc của cả đoạn cho giọng nhận chữ thô (`spoken_layout`)."""
    return spoken_layout(text, readings)[0]


def expand_words(words: list[list[int]], slots: list[int | None]) -> list[list[int]]:
    """Mốc từng chữ của chữ đem đọc -> mốc từng chữ HIỆN: chữ đã mất khỏi chuỗi đứng ở cuối mốc chữ trước nó (mốc rỗng)."""
    out: list[list[int]] = []
    for slot in slots:
        if slot is not None and slot < len(words):
            out.append(list(words[slot]))
        else:
            end = out[-1][1] if out else 0
            out.append([end, end])
    return out


def applicable(text: str, readings: Mapping[str, str] | None) -> list[tuple[str, str]]:
    """Các cách đọc có mặt trong đoạn (khoá một chữ hay cụm), theo thứ tự xuất hiện lần đầu."""
    if not readings:
        return []
    seen: dict[str, str] = {}
    for _at, _count, key in _matches(_TOKEN.findall(text), readings):
        seen.setdefault(key, readings[key])
    return list(seen.items())


def tag(text: str, readings: Mapping[str, str] | None) -> str:
    """Dấu cho khoá bộ đệm clip: "" khi đoạn không có từ nào có cách đọc riêng (khoá như trước), không thì "r" + 16 số hex của các cách
    đọc có mặt."""
    found = applicable(text, readings)
    if not found:
        return ""
    return "r" + hashlib.sha256("\n".join(f"{key}\t{value}" for key, value in found).encode("utf-8")).hexdigest()[:16]
