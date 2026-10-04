"""Viết tắt TOÀN HOA trong "Nghe ngay": đọc tên chữ cái hệ a-bê-xê ("HP" -> "hát pê", "NPC" -> "en pê xê") - biến đổi để đọc, chữ hiện không đổi.

sea-g2p đọc "MP" thành "mờ phê" và để "VIT", "ATK" nguyên chữ cho giọng đọc tự đoán. Quy ước (bộ thử TN, gold_spec 3.1-3.5): viết tắt đọc tên chữ cái, dạng nói gọn
khi đọc liền, với MỌI giọng (kể cả giọng nói được tiếng Anh). Chỉ đọc khi chắc là viết tắt: 2-5 chữ cái Latin HOA, không dính số ("10KG", "LV5" để sea-g2p đọc đơn vị),
không phải từ tiếng Anh viết hoa cả ("LINE", "MAX", "TIP", "YES": `english_words.txt`; vài viết tắt nằm trong danh sách ấy nên có bảng riêng; những từ này đổi sang chữ thường vì
sea-g2p đọc chữ hoa cả thành từng chữ cái), không phải tiếng Nhật viết hoa cả ("BAKA": đọc được bằng luật romaji), không nằm trong câu viết hoa cả ("ONII-CHAN LO LẮNG CHO CON KÌA": đang gào, không phải viết tắt). Ngoại lệ đọc như từ
(chủ sách): VIP "víp", ID "ai-đi", OK "ô kê", TV "ti vi". Bản Kotlin y hệt: `readaloud/Abbreviations.kt`.
"""
from __future__ import annotations

import re

from ..romanization import romanized_reading
from . import names
from .names import english_words, split_token

LETTERS = {
    "a": "a", "b": "bê", "c": "xê", "d": "đê", "e": "e", "f": "ép", "g": "giê", "h": "hát", "i": "i", "j": "gi", "k": "ca", "l": "e-lờ", "m": "em",
    "n": "en", "o": "ô", "p": "pê", "q": "quy", "r": "e-rờ", "s": "ét", "t": "tê", "u": "u", "v": "vê", "w": "vê-kép", "x": "ích", "y": "i-dài", "z": "dét",
}
AS_WORDS = {"vip": "víp", "id": "ai-đi", "ok": "ô kê", "tv": "ti vi"}
SPELLED_ENGLISH = frozenset("abc ceo cia dna exp fbi hiv ibm nba usa".split())  # có trong english_words.txt, có nguyên âm, nhưng là viết tắt
SHOUT_WORDS = frozenset("no oh ah eh uh um ha ho yo hi he we me my up so to of or on ya ye go do if in is an by at".split())  # từ Anh hai chữ gào lên
LAUGH = re.compile(r"(?:ha|he|hi|ho)+")  # "HAHA": tiếng cười, không phải viết tắt
ROMAN_LETTERS = frozenset("ivx")  # "IIII" nằm trong danh sách từ Anh nhưng không phải từ; "IIIII" đọc được như romaji
PAREN_ABBREVIATION = re.compile(r"(?<=.)\(([A-Z]{2,5})\)")  # "đó.”(GM)": viết tắt trong ngoặc dính vào chữ trước
LEVEL_NAMES = {"lv": "lờ vê", "lvl": "lờ vê lờ"}  # chủ sách 04-10: Lv không chắc là cấp độ thì đọc tên chữ cái, l = lờ, v = vê
MIN_LETTERS, MAX_LETTERS = 2, 5
ROMAJI_FROM = 4  # từ bấy nhiêu chữ, đọc được bằng luật romaji ("BAKA", "SUGOI") thì là chữ Nhật viết hoa, không phải viết tắt


def _caps(core: str) -> bool:
    """Có ít nhất hai chữ cái và không chữ thường nào (chữ hoa cả, kể cả có dấu hay nối gạch)."""
    return sum(ch.isalpha() for ch in core) >= 2 and not any(ch.islower() for ch in core)


def _shouty(core: str) -> bool:
    return _caps(core) and (not core.isascii() or "-" in core)


def _word(lower: str) -> bool:
    """Từ tiếng Anh (hay tiếng gào) viết hoa cả, không phải viết tắt."""
    if len(lower) == 2:
        return lower in SHOUT_WORDS
    return lower in english_words() and lower not in SPELLED_ENGLISH and any(ch in "aeiouy" for ch in lower)


def spelled(core: str) -> str | None:
    """Cách đọc của `core` (đã bỏ dấu câu quanh) khi nó là chữ HOA cả cần đổi để đọc, None khi để nguyên: viết tắt thì tên chữ cái; từ tiếng Anh / tiếng Nhật / tiếng cười viết
    hoa cả ("LINE", "BAKA", "HAHA") thì chữ thường - sea-g2p đọc chữ hoa cả thành từng chữ cái, mà đó là một từ."""
    if not (len(core) >= MIN_LETTERS and core.isascii() and core.isalpha() and core.isupper()):
        return None
    lower = core.lower()
    if lower in AS_WORDS:
        return AS_WORDS[lower]
    if ROMAN_LETTERS.issuperset(lower):
        return " ".join(LETTERS[ch] for ch in lower)  # "IIII", "XXX": số La Mã không hợp lệ hay chữ X, đọc từng chữ cái
    if _word(lower) or (len(lower) >= 4 and LAUGH.fullmatch(lower)):
        return lower
    if len(lower) > MAX_LETTERS:
        return None
    if len(lower) >= ROMAJI_FROM and romanized_reading(lower, "ja") is not None:
        return lower
    return " ".join(LETTERS[ch] for ch in lower)


def read_levels(toks: list[str], out: list[str], speaks_english: bool = True) -> None:
    """"Lv" / "Lvl" / "LV" liền trước một số ("Lv 5", "Lv.5", "Lv5", "Lvl.10") là cấp độ: để chữ "level" (giọng không nói được âm Anh thì Việt hoá như từ Anh khác). Không đi với số thì không
    chắc nghĩa gì: đọc tên chữ cái ("lờ vê"). Thay tại chỗ, giữ dấu câu quanh; số chữ không đổi."""
    for index, token in enumerate(toks):
        if out[index] != token:
            continue
        before, core, after = split_token(token)
        word = core.lower()
        if word not in LEVEL_NAMES:
            continue
        glued = after.lstrip(".:")
        following = toks[index + 1].lstrip("([“\"'") if index + 1 < len(toks) else ""
        if glued[:1].isdigit() or (after in ("", ".", ":") and following[:1].isdigit()):
            level = "level" if speaks_english else names.english_reading("level") or "level"
            out[index] = before + level + (" " + glued if glued[:1].isdigit() else "")
        else:
            out[index] = before + LEVEL_NAMES[word] + names.closing(after, LEVEL_NAMES[word])


def spell_abbreviations(toks: list[str], out: list[str]) -> None:
    """Thay tại chỗ, trong `out`, token (chưa bị đổi so với `toks`) là viết tắt TOÀN HOA bằng tên chữ cái, giữ dấu câu quanh; số chữ không đổi."""
    parts = [split_token(token) for token in toks]
    shouting = [_shouty(core) for _, core, _ in parts]
    for index, token in enumerate(toks):
        if out[index] != token:
            continue
        before, core, after = parts[index]
        if "(" in token:
            out[index] = PAREN_ABBREVIATION.sub(lambda m: "(" + (spelled(m.group(1)) or m.group(1)) + ")", token)
            if out[index] != token:
                continue
        if not core or before[-1:].isdigit() or after[:1].isdigit():
            continue
        reading = spelled(core)
        if reading is None:
            continue
        first = last = index  # đang gào: trong dãy chữ hoa cả có chữ có dấu / nối gạch (không phải một dãy viết tắt như "HP MP SP")
        while first and _caps(parts[first - 1][1]):
            first -= 1
        while last + 1 < len(toks) and _caps(parts[last + 1][1]):
            last += 1
        if last > first and any(shouting[first:last + 1]):
            continue
        out[index] = before + reading + names.closing(after, reading)


def read_shouted_honorifics(toks: list[str], out: list[str], origin: str | None) -> None:
    """Gọi viết hoa cả ("ONII-CHAN", "NEE-SAN", "OPPA") đọc như dạng thường của nó (`names.honorific_reading`: "o-ni-i-chan", "ne-e-xan") - luật hậu tố của `names` chỉ nhận chữ thường / viết hoa đầu,
    còn chữ hoa cả sẽ bị `spell_abbreviations` bỏ qua ở câu đang gào và sea-g2p đọc nguyên "onii chan". Thay tại chỗ, giữ dấu câu quanh; số chữ không đổi."""
    for index, token in enumerate(toks):
        if out[index] != token:
            continue
        before, core, after = split_token(token)
        letters = core.replace("-", "")
        if len(letters) < 3 or not (core.isascii() and letters.isalpha() and letters.isupper()):
            continue
        reading = names.honorific_reading(core.lower(), origin)
        if reading:
            out[index] = before + reading + after


TITLES = {"mr": "mister", "mrs": "missus", "ms": "miss", "dr": "doctor", "st": "saint"}  # danh xưng viết tắt trước tên: đọc đủ chữ Anh (gold_spec: "mr." là "mister")
TITLE_NEEDS_NAME = frozenset(("dr", "st"))  # "Dr." / "St." chỉ là danh xưng khi liền trước một tên viết hoa ("Dr. Stone", "St. Louis"); "Mr." / "Ms." / "Mrs." thì luôn
TITLE_GLUED = re.compile(r"(mrs|mr|ms|dr|st)\.(?=[^\W\d_])", re.IGNORECASE)  # "mr.lyle": dấu chấm dính liền tên
TITLE_OPENERS = "\"'“‘([«"


def read_titles(toks: list[str], out: list[str], speaks_english: bool = True) -> None:
    """"Mr." / "Mrs." / "Ms." / "Dr." / "St." trước tên đọc đủ chữ Anh ("mister", "missus", "miss", "doctor", "saint"): sea-g2p đọc "mờ rờ" hay để nguyên "mr." làm cả câu bị ngắt ở dấu chấm.
    Dấu chấm bỏ theo ("mr.lyle" -> "mister lyle"). Giọng không nói được âm Anh thì Việt hoá chữ ấy như từ Anh khác. Thay tại chỗ; số chữ không đổi."""
    for index, token in enumerate(toks):
        if out[index] != token:
            continue
        before, core, after = split_token(token)
        if not core or before[-1:].isdigit():
            continue
        following = toks[index + 1].lstrip(TITLE_OPENERS) if index + 1 < len(toks) else ""
        glued = TITLE_GLUED.match(core)
        if glued:  # "mr.lyle"
            key, rest = glued.group(1).lower(), core[glued.end():]
            if key in TITLE_NEEDS_NAME and not rest[:1].isupper():
                continue
            tail = " " + rest + after
        else:
            key = core.lower()
            if key not in TITLES or core[1:] != core[1:].lower():
                continue
            dotted = after.startswith(".")
            if not following[:1].isalpha() or (key in TITLE_NEEDS_NAME and not following[:1].isupper()) or (not dotted and (key == "st" or core[:1].islower())):
                continue
            tail = after[1:] if dotted else after
        word = TITLES[key]
        word = (names.english_reading(word) or word) if not speaks_english else word
        out[index] = before + word + tail
