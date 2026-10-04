"""Bộ kiểm một âm tiết tiếng Việt viết đúng chính tả: phụ âm đầu + vần + thanh.

Chặt hơn `analysis._valid_vietnamese_spoken_form` (file khoá, giữ nguyên) ở ba chỗ mà bộ kia để lọt: chính tả g/gh ("Gen" -> "Ghen"),
vần khép p / t / c / ch chỉ đi với thanh sắc hay nặng ("Mêch", "Got"), và vần không có trong tiếng Việt ("Ain": ai không nhận phụ âm cuối).
Dùng cho mọi đường ĐỌC TÊN do máy sinh ra (romanization.py, english_vi.py); cách đọc người nghe tự gõ vẫn qua bộ cũ, rộng tay hơn.

Bản Kotlin y hệt: mobile/android/.../VietnameseSyllable.kt; bộ ví dụ dùng chung ở tests/fixtures/vietnamese_syllable/cases.json (đổi một bên là phải đổi cả hai).
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

# dài trước ngắn
ONSETS = ("ngh", "ng", "nh", "ch", "gh", "gi", "kh", "ph", "th", "tr", "qu", "b", "c", "d", "đ", "g", "h", "k", "l", "m", "n", "p", "r", "s", "t", "v", "x", "")

# Nhân vần: nguyên âm đơn, nguyên âm đôi, và nhân có âm lướt cuối (ai, ao, ...; không nhận phụ âm cuối thêm).
SIMPLE = frozenset("a ă â e ê i y o ô ơ u ư".split())
DIPHTHONG = frozenset("ia iê yê uyê ua uô ưa ươ oa oă oe uê uâ uy uơ oo".split())
GLIDE_END = frozenset("ai ao au ay âu ây eo êu iu oi ôi ơi ui ưi ưu iêu yêu uôi ươi ươu oai oay oeo oao uây uyu uya".split())
NUCLEI = SIMPLE | DIPHTHONG | GLIDE_END

# Nhân phải có phụ âm cuối mới thành âm tiết ("ă", "iê", "uô"... không đứng một mình); ia, ua, ưa, uơ, uê, ơ thì đứng một mình được.
NEEDS_CODA = frozenset("ă â iê yê uô ươ uâ oă oo uyê".split())

# Vần khép: phụ âm cuối -> nhân đi được với nó. ưn có vì văn bản của Bộ Ngoại giao viết Cưn (Geun), không phải vì từ thường có; ơc, ơng, ưp, oáp, oép thì không.
CODA_NUCLEI: dict[str, frozenset[str]] = {
    "c": frozenset("a ă â o ô u ư e iê uô ươ oa oă oe oo".split()),
    "ch": frozenset("a ê i oa uê uy".split()),
    "m": frozenset("a ă â e ê i o ô ơ u ư iê yê uô ươ oa oă".split()),
    "n": frozenset("a ă â e ê i o ô ơ u ư iê yê uô ươ oa oă oe uâ uyê".split()),
    "ng": frozenset("a ă â e o ô u ư iê uô ươ oa oă uâ oo".split()),
    "nh": frozenset("a ê i oa uê uy y".split()),
    "p": frozenset("a ă â e ê i o ô ơ u iê ươ".split()),
    "t": frozenset("a ă â e ê i y o ô ơ u ư iê yê uô ươ oa oă oe uâ uyê uy".split()),
}
CLOSED_TONES = ("c", "ch", "p", "t")  # chỉ thanh sắc hay nặng
FRONT = ("e", "ê", "i", "y")  # nguyên âm đứng sau c / ng / g phải viết k / ngh / gh

_TONES = {0x300: "f", 0x301: "s", 0x309: "r", 0x303: "x", 0x323: "j"}
_KEEP = (0x306, 0x302, 0x31B)  # ă â ê ô ơ ư
_VOWELS = "aeiouy"
_SEPARATORS = re.compile(r"[ -]")


def _strip(syllable: str) -> tuple[str, str] | None:
    """(chữ thường không thanh, thanh) hay None khi có dấu lạ hay hai thanh."""
    tone = ""
    base = ""
    out: list[str] = []
    for ch in unicodedata.normalize("NFD", syllable.lower()):
        code = ord(ch)
        if 0x300 <= code <= 0x36F:
            if code in _TONES:
                if tone or not base or base not in _VOWELS:  # hai thanh, hay thanh đặt trên phụ âm (ñ)
                    return None
                tone = _TONES[code]
            elif code not in _KEEP:
                return None
            else:
                out.append(ch)
        else:
            out.append(ch)
            base = ch
    return unicodedata.normalize("NFC", "".join(out)), tone


def _rhyme_ok(onset: str, rest: str, tone: str, *, gi_absorbed: bool = False) -> bool:
    for coda in ("", "c", "ch", "m", "n", "ng", "nh", "p", "t"):
        if coda:
            if not rest.endswith(coda):
                continue
            nucleus = rest[: -len(coda)]
        else:
            nucleus = rest
        if nucleus not in NUCLEI:
            continue
        front = nucleus[0] in FRONT
        if onset == "c" and front or onset == "k" and not front:
            continue
        if onset == "g" and front and not gi_absorbed:  # g + e, ê, i viết gh (gi: i đã nằm trong chữ gi)
            continue
        if onset in ("gh", "ngh") and not front or onset == "ng" and front:
            continue
        if onset == "qu" and nucleus[0] in ("u", "o"):
            continue
        if onset == "gi" and nucleus[0] in ("i", "y"):  # gi + i viết gi
            continue
        if nucleus in ("yê", "yêu") and onset not in ("", "qu"):  # yên, yêu, quyên; sau phụ âm khác viết iê / uyê
            continue
        if not coda:
            if nucleus in NEEDS_CODA:
                continue
        else:
            if nucleus in GLIDE_END:
                continue
            if nucleus not in CODA_NUCLEI[coda]:
                continue
            if nucleus == "y" and onset != "qu":
                continue
            if coda in CLOSED_TONES and tone not in ("s", "j"):
                continue
        return True
    return False


@lru_cache(maxsize=200000)
def valid_syllable(syllable: str) -> bool:
    """Một âm tiết (không dấu cách, không gạch nối), hoa hay thường, có thanh hay không."""
    syllable = unicodedata.normalize("NFC", syllable)
    if not syllable or len(syllable) > 8:  # nghiêng, nguyệch: dài nhất 7
        return False
    stripped = _strip(syllable)
    if stripped is None:
        return False
    text, tone = stripped
    if not text.isalpha():
        return False
    for onset in ONSETS:
        if not text.startswith(onset):
            continue
        rest = text[len(onset):]
        if not rest:
            if onset == "gi":  # gì, gí
                return True
            continue
        if _rhyme_ok(onset, rest, tone):
            return True
        if onset == "gi" and _rhyme_ok("g", "i" + rest, tone, gi_absorbed=True):  # gin, giêng = g + iê + ng
            return True
    return False


def valid_spoken_form(text: str) -> bool:
    """Cả cách đọc: mọi âm tiết (tách bằng dấu cách hay gạch nối) phải hợp lệ; rỗng hay có đoạn rỗng là không."""
    pieces = _SEPARATORS.split(" ".join(text.split()))
    return bool(pieces) and all(valid_syllable(piece) for piece in pieces)
