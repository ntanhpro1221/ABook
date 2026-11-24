"""Chữ nói lắp viết bằng gạch nối ("K-khoan", "X-xin", "K-K-khoan", "H-Hinohara"): một đến ba chữ cái, gạch, rồi một chữ BẮT ĐẦU bằng đúng các chữ cái ấy
(không phân biệt hoa thường). Từ ghép thật không khớp vì phần sau không mở đầu bằng tiền tố: "X-quang", "A-đam", "e-mail", "T-shirt", "B-52". Phần lặp bằng cả chữ
("Ha-ha", "Hi-hi") là tiếng cười, không phải nói lắp.

Chữ cái + kính ngữ không bao giờ đứng một mình ("S-san", "Sa-san", "K-kun") là biệt danh viết tắt ("Mình sẽ ra ngoài cùng với S-san" - hoshizora, 4 câu; "giới
thiệu Sa-san"), không phải nói lắp: không ai lắp vào chữ "san". Tiếng gọi đứng riêng được ("senpai", "sensei", "nii") thì "S-senpai" vẫn là nói lắp.

Chỉ dùng để quyết định cách ĐỌC (luật đọc của VieNeu, và để không gửi chữ lắp đi phiên âm như một tên riêng). Chữ truyện hiển thị không đổi."""

from __future__ import annotations

import re
import unicodedata

_DASHES = "-–—"
_PARTS = re.compile(r"((?:[^\W\d_]{1,3}[" + _DASHES + r"]+)+)([^\W\d_].*)$", re.DOTALL)
_PREFIX = re.compile(r"[^\W\d_]{1,3}")
_LETTERS = re.compile(r"[^\W\d_]+")
BOUND_HONORIFICS = frozenset(("san", "kun", "chan", "sama", "dono", "ssi"))  # không có "tan", "han": cũng là chữ Việt / tên Hoa ("T-tan", "H-Han")


def split(word: str) -> tuple[list[str], str] | None:
    """("K-K-khoan") -> (["K", "K"], "khoan"); None khi chữ không phải nói lắp. `word` là lõi chữ (không dính dấu câu ngoài)."""
    match = _PARTS.fullmatch(unicodedata.normalize("NFC", word))
    if match is None:
        return None
    prefixes, rest = _PREFIX.findall(match.group(1)), match.group(2)
    head = _LETTERS.match(rest).group().casefold()
    if head in BOUND_HONORIFICS:
        return None
    if all(head.startswith(prefix.casefold()) and len(head) > len(prefix) for prefix in prefixes):
        return prefixes, rest
    return None


def word(token: str) -> str:
    """Chữ thật sau mọi lần lắp ("K-K-khoan" -> "khoan"); chữ không lắp trả lại nguyên."""
    parts = split(token)
    return token if parts is None else parts[1]
