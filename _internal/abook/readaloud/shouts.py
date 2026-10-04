"""Tiếng kêu trong "Nghe ngay": thán từ Latin ("Umm", "Oh") và thán từ kéo dài ("Aaaa", "Hmmm", "rồiiii") đọc thành âm tiếng Việt - biến đổi để đọc, chữ hiện không đổi.

sea-g2p đọc "Aaaa" thành "a a a a" và "Hmmm" thành chữ cái; người nghe cần một tiếng kéo dài. Quy ước (bộ thử TN, gold_spec 3.10 và quyết định phân xử 04-10):
thán từ gốc MỘT lần bằng âm tiết Việt, rồi "…", rồi - chỉ khi chữ bị kéo là nguyên âm đứng riêng được thành một âm tiết (a, e, ê, i, o, ô, ơ, u, ư) - nguyên âm ấy một
lần, mang thanh của âm tiết gốc ("rồi… ì", "tớ… ớ"). Chữ kéo là phụ âm hay "y" thì chỉ "<gốc>…" ("hừm…", "không…", "hầy…"). Toàn hoa cùng luật. "ー" sau nguyên âm
là kéo ("Aー" -> "a… a"). Nhận ra bằng một chữ lặp từ ba lần liền (hay "ー"); thán từ Latin cố định (`INTERJECTIONS`) thì khớp cả dạng không kéo.

Chỉ đọc khi tách được gốc: gốc là thán từ trong bảng, âm tiết tiếng Việt, hay tiếng kêu kiểu Nhật đọc được bằng luật romaji ("Kyaaa" -> "ki-a… a"). Còn lại
("Weisss", "www", nhiều chỗ kéo trong một chữ) giữ nguyên. Bản Kotlin y hệt: `readaloud/Shouts.kt`, chung fixture tests/fixtures/vieneu/android/text.json.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from ..analysis import is_vietnamese_syllable
from ..romanization import romanized_reading
from . import names
from .names import split_token

INTERJECTIONS = {"umm": "ừm", "ugh": "ức", "boom": "bùm", "oh": "ô", "hmm": "hừm", "shh": "suỵt", "ah": "a", "eh": "ê", "hm": "hừm", "huh": "hả", "ooh": "ô",
                 "hic": "hích", "urgh": "ức"}
LAUGH_SYLLABLES = {"ha": "ha", "he": "hê", "hi": "hi", "ho": "hô", "fu": "phu"}  # tiếng cười lặp ("Haha" -> "ha ha", "Hehe" -> "hê hê", "fufu" -> "phu phu")
LAUGH = re.compile(r"(?:ha|he|hi|ho|fu){2,}", re.IGNORECASE)
TONE_MARKS = "\u0300\u0301\u0303\u0309\u0323"  # huyền, sắc, ngã, hỏi, nặng (còn lại là dấu mũ / móc / trăng: thuộc về chữ)
STANDALONE = frozenset("aeêioôơuư")  # nguyên âm đứng riêng được thành một âm tiết: chữ kéo là chữ này thì nhắc lại nó sau "…"
VOWELS = frozenset("aăâeêioôơuưy")
MIN_RUN = 3  # một chữ lặp chừng ấy lần liền là kéo dài
ROMAN_LETTERS = frozenset("ivx")
RANK_NOUNS = frozenset(("hạng", "cấp", "rank", "class", "loại", "bậc"))  # "hạng AAA", "hạng SSS": chữ hạng, không phải tiếng kéo
GLUE = re.compile(r"(?:\.{2,}|[…~—–])+")  # chỗ ngắt dính liền giữa tiếng kêu và chữ sau nó
CLOSING = "\"'“”‘’()[]«»"  # dấu bao quanh chữ đứng trước
JAPANESE_CRY = re.compile(r"(?:^|[bcdfghjklmnpqrstvxz])y|w")  # kya, nya, ya, uwa: tiếng kêu Nhật, không phải âm tiết Việt dù hình thức hợp lệ ("kya" qua phép kiểm âm tiết)


def dedupe(text: str) -> str:
    """Gộp mỗi chuỗi chữ lặp thành một chữ ("umm" -> "um")."""
    return re.sub(r"(.)\1+", r"\1", text)


_DEDUPED = {dedupe(word): reading for word, reading in INTERJECTIONS.items()}


def _plain(char: str) -> str:
    """Chữ không dấu thanh ("ớ" -> "ơ"; dấu mũ / móc / trăng giữ)."""
    return unicodedata.normalize("NFC", "".join(c for c in unicodedata.normalize("NFD", char) if c not in TONE_MARKS))


def _tone(word: str) -> str:
    return next((c for c in unicodedata.normalize("NFD", word) if c in TONE_MARKS), "")


def _latin(char: str) -> bool:
    return char.isalpha() and (ord(char) < 0x250 or 0x1E00 <= ord(char) <= 0x1EFF)


def _letters(core: str) -> list[str] | None:
    """Các chữ của `core` (NFC, chữ thường) với "ー" thay bằng chữ nguyên âm đứng trước nhắc lại hai lần; None khi có chữ ngoài Latin."""
    chars: list[str] = []
    for char in unicodedata.normalize("NFC", core).lower():
        if char == "ー":
            if not chars or _plain(chars[-1]) not in VOWELS:
                return None
            chars += [chars[-1]] * 2
        elif _latin(char):
            chars.append(char)
        else:
            return None
    return chars


def _runs(chars: list[str]) -> list[tuple[int, int]]:
    bases = [_plain(char) for char in chars]
    runs: list[tuple[int, int]] = []
    start = 0
    for index in range(1, len(bases) + 1):
        if index == len(bases) or bases[index] != bases[start]:
            if index - start >= MIN_RUN:
                runs.append((start, index))
            start = index
    return runs


@lru_cache(maxsize=4096)
def stretch_reading(core: str) -> str | None:
    """Cách đọc của `core` (chữ cái đầu tới cuối, không dấu câu) khi nó là thán từ Latin hay tiếng kêu kéo dài; None khi để nguyên."""
    chars = _letters(core)
    if not chars or (core.isupper() and ROMAN_LETTERS.issuperset(chars) and len(chars) >= MIN_RUN):  # "III", "XXX": số La Mã / chữ X, không phải tiếng kéo
        return None
    word = "".join(chars)
    if word in INTERJECTIONS:
        return INTERJECTIONS[word]
    if LAUGH.fullmatch(word) and all(word[i:i + 2] == word[:2] for i in range(0, len(word), 2)):
        return " ".join(LAUGH_SYLLABLES[word[i:i + 2]] for i in range(0, len(word), 2))
    runs = _runs(chars)
    if len(runs) != 1:
        return _collapsed(chars, runs)
    start, end = runs[0]
    letter = _plain(chars[start])
    one = "".join(chars[:start] + [chars[start]] + chars[end:])  # chuỗi kéo gộp thành một chữ
    base = _DEDUPED.get(dedupe(one))
    append = base if base in ("a", "ô", "ê") else ""
    if base is None:
        ascii_word = one.isascii()
        japanese = romanized_reading(one, "ja") if ascii_word else None
        consonant = "".join(chars[:start] + chars[end:])
        if ascii_word and JAPANESE_CRY.search(one) and japanese:
            base = japanese
        elif is_vietnamese_syllable(one):
            base = one
        elif letter not in VOWELS and consonant and is_vietnamese_syllable(consonant):
            base = consonant  # "Haizzz" -> "hai": chữ kéo không thuộc âm tiết
        elif japanese:
            base = japanese
        else:
            return None
        if letter in STANDALONE:
            append = unicodedata.normalize("NFC", unicodedata.normalize("NFD", letter) + _tone(base))
    return f"{base}…" + (f" {append}" if append and letter in STANDALONE else "")


def _collapsed(chars: list[str], runs: list[tuple[int, int]]) -> str | None:
    """Chữ có NHIỀU chỗ kéo ("Cccchhhhàaaaaaoooo" -> "chào… ò"): gộp mỗi chỗ kéo thành một chữ (giữ dấu thanh ở chữ đầu của chỗ ấy); chỉ đọc khi gộp ra đúng một âm tiết tiếng Việt.
    Chỗ kéo cuối là nguyên âm đứng riêng thì nhắc lại nó một lần sau "…", mang thanh của âm tiết."""
    if len(runs) < 2:
        return None
    keep = [True] * len(chars)
    for start, end in runs:
        for index in range(start + 1, end):
            keep[index] = False
    base = "".join(char for char, kept in zip(chars, keep) if kept)
    if not is_vietnamese_syllable(base):
        return None
    letter = _plain(chars[runs[-1][0]])
    append = unicodedata.normalize("NFC", unicodedata.normalize("NFD", letter) + _tone(base)) if runs[-1][1] == len(chars) and letter in STANDALONE else ""
    return f"{base}…" + (f" {append}" if append else "")


def read_shouts(toks: list[str], out: list[str]) -> None:
    """Thay tại chỗ, trong `out`, token (chưa bị đổi so với `toks`) là thán từ / tiếng kêu kéo dài bằng cách đọc của nó, giữ dấu câu quanh (dấu "-" đuôi của
    "Xoạttt-" bỏ); số chữ không đổi. Chữ dính liền vào phần sau qua "…", "..", "~" hay "—" ("Ummm…Ý", "màaaa—nếu") thì chỉ xét phần trước. Chữ hoa cả là hạng
    ("hạng AAA", "AAA+++") thì để viết tắt đọc."""
    for index, token in enumerate(toks):
        if out[index] != token:
            continue
        glued = GLUE.search(token, len(split_token(token)[0]))
        head, rest = (token[:glued.start()], token[glued.start():]) if glued else (token, "")
        before, core, after = split_token(head)
        if not core or (core.isupper() and (after.startswith("+") or (index and toks[index - 1].lower().strip(CLOSING) in RANK_NOUNS))):
            continue
        reading = stretch_reading(core)
        if not reading:
            continue
        rest = rest.lstrip("~") if reading.endswith("…") else rest
        if reading.endswith("…") and rest[:1] in ("…", "."):
            reading = reading[:-1]  # "…" đã có ngay sau chữ
        out[index] = before + reading + names.closing(after.replace("-", "") if "…" in reading else after, reading) + rest
