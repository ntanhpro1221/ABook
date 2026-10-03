"""Mảnh từ của nhà cung cấp giọng đọc -> mốc từng chữ hiện của đoạn chữ.

Nhà cung cấp (Edge, Windows) báo từng "mảnh" mình vừa đọc: chữ + lúc bắt đầu + lúc kết thúc. Màn đọc cần đúng MỘT cặp cho mỗi chữ hiện
(đơn vị `\\S+`, như `words.ts` `countTokens` và `word_timing.tokens`). Hai bên không trùng nhau: dấu câu, gạch ngang, số mà giọng đọc
thành lời, mảnh ghép nhiều chữ. Hàm này nối chúng lại. Điện thoại cài lại đúng thuật toán này bằng Kotlin và chạy lại trên các ví dụ trong
`tests/fixtures/readaloud/` (README.md ở đó ghi định dạng) - đổi thuật toán thì đổi cả hai bên và bộ ví dụ.

Toàn số nguyên (ms), không số thực, để hai ngôn ngữ ra cùng từng con số.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_TOKEN = re.compile(r"\S+")
# Mảnh không khớp ngay chữ đang chờ thì nhìn tới nhiều nhất chừng này chữ nữa: xa hơn là giọng đọc lời khác chữ (số, từ viết tắt), không phải
# một chữ ở xa - khớp bừa vào chữ trùng (vd "và") ở xa còn tệ hơn bỏ qua mảnh ấy.
LOOKAHEAD = 8


@dataclass(frozen=True)
class Boundary:
    """Một mảnh nhà cung cấp báo. `char`: vị trí ký tự (code point) của mảnh trong chữ đem đọc nếu nhà cung cấp cho (Windows); Edge không có."""

    text: str
    start_ms: int
    end_ms: int
    char: int | None = None


def fold(text: str) -> str:
    """Chữ để so khớp: NFC, chữ thường, chỉ giữ ký tự thuộc nhóm Unicode L* và N* (bỏ dấu câu, khoảng trắng, ký hiệu)."""
    lowered = unicodedata.normalize("NFC", text).lower()
    return "".join(ch for ch in lowered if unicodedata.category(ch)[0] in "LN")


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(text)


def _find(folded: list[str], t: int, c: int, piece: str) -> tuple[int, int, int, int] | None:
    """Mảnh `piece` (đã `fold`) nằm ở đâu, tính từ chữ `t` ký tự thứ `c` của nó: (chữ đầu, ký tự đầu, chữ cuối, ký tự cuối + 1) hay None.
    Ưu tiên chỗ khớp bắt đầu đúng đầu một chữ (hay đúng chỗ đang dở); không có thì chỗ khớp giữa chữ trong cùng tầm nhìn."""
    limit = min(len(folded), t + LOOKAHEAD + 1)
    rest: list[str] = []
    owner: list[tuple[int, int]] = []  # với mỗi ký tự của `rest`: (chữ, vị trí trong chữ ấy)
    index = t
    extra = len(piece)  # sau tầm nhìn, dựng thêm chừng đủ chỗ cho mảnh trải qua nhiều chữ
    while index < len(folded) and (index < limit or extra > 0):
        for offset in range(c if index == t else 0, len(folded[index])):
            rest.append(folded[index][offset])
            owner.append((index, offset))
            if index >= limit:
                extra -= 1
        index += 1
    text = "".join(rest)
    fallback: int | None = None
    at = text.find(piece)
    while at >= 0:
        if owner[at][0] >= limit:
            break
        word, offset = owner[at]
        if offset == 0 or (word == t and offset == c):
            return _span(owner, at, len(piece))
        if fallback is None:
            fallback = at
        at = text.find(piece, at + 1)
    return _span(owner, fallback, len(piece)) if fallback is not None else None


def _span(owner: list[tuple[int, int]], at: int, length: int) -> tuple[int, int, int, int]:
    first, offset = owner[at]
    last, last_offset = owner[at + length - 1]
    return first, offset, last, last_offset + 1


def map_boundaries(text: str, boundaries: list[Boundary], duration_ms: int) -> list[list[int]]:
    """Mốc từng chữ hiện của `text`: `[[bắt_đầu_ms, kết_thúc_ms], ...]`, đúng một cặp cho mỗi chữ `\\S+`, tính từ đầu clip.

    Đi qua các mảnh theo thứ tự, mỗi mảnh khớp với chữ chứa nó (không phân biệt hoa thường, bỏ dấu câu), chỉ tiến lên. Chữ được nhiều mảnh phủ
    thì trải từ lúc bắt đầu mảnh đầu tới lúc kết thúc mảnh cuối; mảnh phủ nhiều chữ thì chia thời gian theo số ký tự mỗi chữ. Chữ không mảnh
    nào phủ (dấu câu trơ, gạch ngang, số giọng đọc thành lời) được nội suy giữa hai chữ có mốc quanh nó theo độ dài chữ. Kết quả không giảm,
    chữ này không chồng sang chữ sau, chữ cuối kết thúc không quá `duration_ms`.
    """
    words = tokens(text)
    count = len(words)
    if count == 0:
        return []
    starts_at = [match.start() for match in _TOKEN.finditer(text)]
    folded = [fold(word) for word in words]
    start: list[int | None] = [None] * count
    end: list[int | None] = [None] * count
    t, c = 0, 0
    for piece in boundaries:
        needle = fold(piece.text)
        if not needle:
            continue
        hit = None
        if piece.char is not None:
            # Nhà cung cấp chỉ vị trí: chữ chứa vị trí ấy (hay chữ kế sau nó) là nơi thử trước. Chỉ đẩy tiến, không lùi.
            guess = _token_at(starts_at, words, piece.char)
            if guess > t:
                hit = _find(folded, guess, 0, needle)
        if hit is None:
            hit = _find(folded, t, c, needle)
        if hit is None:
            continue
        first, offset, last, stop = hit
        covered = [(index, (len(folded[index]) if index != last else stop) - (offset if index == first else 0))
                   for index in range(first, last + 1)]
        total = sum(size for _, size in covered)
        span = piece.end_ms - piece.start_ms
        before = 0
        for index, size in covered:
            lo = piece.start_ms + span * before // total
            hi = piece.start_ms + span * (before + size) // total
            before += size
            if start[index] is None:
                start[index] = lo
            end[index] = hi
        t, c = last, stop

    # Chữ không được phủ: nội suy giữa mốc kết thúc của chữ có mốc trước nó và mốc bắt đầu của chữ có mốc sau nó.
    index = 0
    while index < count:
        if start[index] is not None:
            index += 1
            continue
        run_end = index
        while run_end + 1 < count and start[run_end + 1] is None:
            run_end += 1
        left = end[index - 1] if index > 0 else 0
        right = start[run_end + 1] if run_end + 1 < count else duration_ms
        left = left if left is not None else 0
        right = right if right is not None else duration_ms
        right = max(right, left)
        weights = [len(words[i]) for i in range(index, run_end + 1)]
        total = sum(weights)
        before = 0
        for i, weight in zip(range(index, run_end + 1), weights):
            start[i] = left + (right - left) * before // total
            before += weight
            end[i] = left + (right - left) * before // total
        index = run_end + 1

    result: list[list[int]] = []
    previous = 0
    for i in range(count):
        s = min(max(start[i] or 0, previous), duration_ms)
        e = min(max(end[i] or 0, s), duration_ms)
        previous = s
        result.append([s, e])
    for i in range(count - 1):
        result[i][1] = min(result[i][1], result[i + 1][0])
    return result


def _token_at(starts_at: list[int], words: list[str], char: int) -> int:
    """Chữ chứa ký tự thứ `char` của câu; rơi vào khoảng trắng thì chữ kế sau; quá cuối thì chữ cuối."""
    for index, begin in enumerate(starts_at):
        if char < begin + len(words[index]):
            return index
    return len(words) - 1
