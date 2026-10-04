"""Việt hoá một từ / tên tiếng Anh thành âm tiết tiếng Việt, cho máy đọc CHỈ nói được âm tiết Việt; theo `docs/READING_FOREIGN_NAMES.md`
mục 1 (luật chung) và mục 4 (tên tiếng Anh, gồm phán quyết chủ sách 04-10).

Máy đọc nói được âm vị Anh (VieNeu, ZeroTTS, Edge) thì GIỮ NGUYÊN chữ Anh (mục 4, đo 04-10); module này chỉ dành cho máy còn lại.
Như `romanization.py`, quy ước ở tài liệu ấy là nguồn duy nhất; không dùng `ENGLISH_TO_VIETNAMESE.md` hay tên Studio đã khoá làm chuẩn.
Bản Kotlin y hệt: `vn/abook/player/readaloud/EnglishVi.kt`; hai bên cùng đọc `tests/fixtures/english_vi/cases.json` (sinh bằng
`scripts/build_english_vi_fixture.py`), đổi một bên là phải đổi cả hai. CHƯA nối vào đường đọc.

Ba tầng (luật thuần trước, thuật toán sau; tầng LLM làm sau):
  override   bảng nhỏ cố định: ca của chủ sách + từ mượn đã vào từ điển tiếng Việt (mục 6: ra-đi-ô, gôn...)
  phonemes   từ có trong từ điển phát âm CMU (`assets/english_phones.txt.gz`, gọn từ `cmudict.dict` bằng
             `scripts/build_english_phones.py`): ARPAbet -> âm tiết Việt (tách âm tiết, cụm phụ âm chèn ơ, phụ âm cuối không hợp lệ thành âm
             tiết schwa, thanh theo luật 1.2 + phán quyết chủ sách)
  spelling   từ không có trong từ điển (tên tự chế) hay máy không có từ điển: luật chữ -> âm (ph, th, sh, ch, ck, -tion, -igh, e câm
             cuối, oo, ee, ea, ay, y cuối...) ra cùng dạng ARPAbet rồi đi chung đường trên. Nguyên âm đơn đọc theo mặt chữ (a e i o u),
             vì gần như mọi từ đi đường này là tên tự chế.

`vietnamized_english(word)` trả cách đọc nối gạch hay None (chữ lạ, viết hoa lạ / toàn hoa, hay có âm tiết mà `vietnamese_syllable.valid_spoken_form`
không nhận). Cờ trong `vietnamized_english_flags`:
  via:override / via:phonemes / via:spelling / via:face   đường đã đi (face: tên ngắn đọc theo mặt chữ, Mike -> mi-ke)
  open:...      quy ước ghi "mở" (`OPEN_CHOICES`; hiện không còn điểm nào)
  analogy:...   quy ước không nói, suy theo phán quyết / hàng gần nhất (ank: /æŋk/ -> anh theo tank -> tanh)
  fit:...       đường âm vị cho âm tiết mà bộ kiểm không nhận, nên đọc theo chữ
"""
from __future__ import annotations

import gzip
import unicodedata
from collections.abc import Mapping
from pathlib import Path

from .romanization import _tone_acute
from .vietnamese_syllable import valid_spoken_form, valid_syllable

PHONES_PATH = Path(__file__).resolve().parent / "assets" / "english_phones.txt.gz"

# Phán quyết chủ sách 04-10 (mục 4): cố định, đứng trên mọi nguồn. game -> gêm viết theo chính tả là ghêm; level -> le-vồ (le-vờ cũng được).
# Ca riêng, không suy rộng: Kate (ca-tê), Pete (pi-tờ), guild (gui), time (tham), Thomas (tho-mát), great (gờ-rít: ea không thành i),
# Gate (gết, viết ghết như ghêm: từ thường viết hoa, không theo mặt chữ như tên), Paul (pau), higher (hai-gờ), Dalton (đan-tơn), days
# (đay), Laplace (la-pờ-lết), Walt (guốt: l bỏ trước t) - t đầu từ vẫn là t (Tom -> tom, Tina -> ti-na); các ca còn lại luật cũng ra được
# (tests/english_vi_evidence.py). Sau "/" trong ghi chú chủ sách là cách đọc khác cũng được.
OWNER = {
    "game": "ghêm", "level": "le-vồ", "maple": "máp-pồ", "michael": "mai-cồ", "kate": "ca-tê",
    "mike": "mi-ke", "jake": "gia-ke", "luke": "lu-ke", "pete": "pi-tờ", "skill": "xờ-kiu", "boss": "bót", "slime": "xờ-lam", "quest": "quét",
    "guild": "gui", "thomas": "tho-mát", "boston": "bót-tơn", "rocky": "róc-ki", "time": "tham", "night": "nai", "blake": "bờ-lếch",
    "master": "mát-tơ", "zeke": "de-ke", "gold": "gôn",
    "tom": "tom", "tony": "to-ni", "team": "tim", "tank": "tanh", "tina": "ti-na", "lyle": "lai-ồ", "kyle": "cai-ồ", "doyle": "đoi-ồ",
    "fireball": "phai-bôn", "rose": "ro-xe", "great": "gờ-rít", "late": "lết", "grace": "gờ-rây", "gate": "ghết", "nate": "na-te",
    "paul": "pau", "higher": "hai-gờ", "laplace": "la-pờ-lết", "jane": "giên", "cage": "ca-ghe", "cale": "ca-le", "walt": "guốt",
    "dalton": "đan-tơn", "days": "đay", "luce": "lu-xe", "washington": "oa-sinh-tơn",
}  # Kyle: chủ sách viết kai-ồ; chính tả luật 1.5 viết c trước a (bộ kiểm âm tiết không nhận "kai"), cùng một âm
# Chữ viết tắt đã đọc thành từ (chủ sách 04-10): khoá là đúng chữ hoa như viết; chữ viết tắt khác là việc của luật mục 5.
ACRONYMS = {"VIP": "víp", "ID": "ai-đi"}
# Từ mượn đã vào từ điển tiếng Việt (mục 6; nền bằng chứng mục 2.4, từ điển S40): đọc như từ Việt. Chỉ những từ mà chữ tiếng Anh trùng gốc
# và trùng nghĩa với từ mượn; các âm tiết nối gạch như mọi đầu ra khác (từ điển viết "cao bồi", "mít tinh").
LOANWORDS = {
    "radio": "ra-đi-ô", "radar": "ra-đa", "tennis": "ten-nít", "acid": "a-xít", "piano": "pi-a-nô", "chocolate": "sô-cô-la",
    "vitamin": "vi-ta-min", "cowboy": "cao-bồi", "meeting": "mít-tinh", "dollar": "đô-la", "cafe": "cà-phê", "golf": "gôn", "card": "cạc",
}
OVERRIDES = {**LOANWORDS, **OWNER}

# Chỗ quy ước ghi "mở". Chủ sách 04-10 (lần 3, 4) đã chốt mọi điểm trước đây (tên ngắn e câm, -er cuối, cụm phụ âm đầu, l sau ai / oi).
OPEN_CHOICES: dict[str, str] = {}

# Các điểm [Chọn] và giá trị đang dùng: KẾT QUẢ QUÉT (scripts/sweep_english_vi_variants.py: thử mọi biến thể, đếm dạng có nguồn khớp trong
# tests/english_vi_evidence.py, chủ sách x100, chính thức x2, SGK / báo x1, cộng đồng x0; hoà thì lấy biến thể đứng trước, có lý do ngữ âm).
# Bản Kotlin chỉ cài các giá trị này.
CHOICES = {
    "schwa": "letter",          # AH0: "ơ" | "letter" (theo chữ cuối của cụm nguyên âm viết ra: a -> a, e -> e, i / y -> i, o / u -> ơ)
    "epenthesis": "ờ",          # vần chèn tách cụm phụ âm ĐẦU từ: "ờ" (chủ sách: xờ-kiu, bờ-lếch) | "ơ" (sách báo)
    "epenthesis_medial": "ơ",   # vần chèn cho phụ âm thừa GIỮA từ: "ơ" (Sếch-xơ-pia, Mát-xcơ-va) | "ờ"
    "l_coda": "n",              # l khép âm tiết (không phải -əl cuối): "n" (Men-bơn, Đan-tơn) | "drop"
    "il_final": "u",            # l cuối từ sau i: "u" (chủ sách: skill xờ-kiu) | "coda" (theo l_coda)
    "s_coda": "t",              # s / z trước phụ âm khác giữa từ: "t" (Bốt-tơn) | "syllable" (xơ)
    "fric_final": "stop",       # s z sh th f v ch... cuối từ: "stop" (t / p: Tô-mát, Đa-lát) | "syllable" (xờ)
    "voiced_final": "devoice",  # b d g cuối từ: "devoice" (p t c: Bớt) | "syllable" (bờ đờ gờ)
    "final_cluster": "drop",    # phụ âm thứ hai trở đi của cụm cuối: "drop" | "syllable"
    "glide_coda": "drop",       # phụ âm cuối sau ai / ao / oi (không khép được): "drop" (I-oóc-tao) | "syllable"
    "th": "th",                 # /θ/: "th" (Mét-thiu) | "x"
    "dh": "đ",                  # /ð/: "đ" (mục 4: x / đ) | "d" (Rơ-dơ-pho)
    "ae": "a",                  # /æ/: "a" (Đa-lát) | "e" (Mét-thiu)
    "aa_o": "o",                # /ɑ/ viết o: "o" (chủ sách: boss bót) | "ô" (Rốc-ki, Bốt-tơn)
    "eh": "e",                  # /ɛ/: "e" (le-vồ của chủ sách) | "ê" (Ê-đi-xơn)
    "ih": "i",                  # /ɪ/: "i" | "ê"
    "ey_p": "a",                # /eɪ/ khép bằng p: "a" (chủ sách: máp-pồ) | "ê" | "e"
    "ey_k": "ê",                # /eɪ/ khép bằng c: "ê" -> êch (chủ sách: bờ-lếch; Sếch-xơ-pia) | "a" | "e"
    "ey_t": "ê",                # /eɪ/ khép bằng t: "ê" (chủ sách: lết, gết) | "a" | "e"
    "ay_m": "am",               # /aɪ/ + m khép: "am" (chủ sách: xờ-lam, tham) | "ai" (bỏ m như ai + phụ âm khác: nai)
    "ey_nasal": "ê",            # /eɪ/ khép bằng m n ng: "ê" (gêm của chủ sách) | "e" | "a"
    "geminate": "primary",      # p t k giữa hai nguyên âm sau nguyên âm nhấn: khép âm tiết trước + đầu âm tiết sau (máp-pồ, Rốc-ki):
                                # "primary" (nhấn chính) | "stressed" (cả nhấn phụ) | "short" (chỉ nguyên âm ngắn nhấn) | "none"
    "tr": "tr",                 # t + r đầu âm tiết: "tr" (Đi-troi, Xtrây-li-a) | "split" (tơ-r)
    "short_silent_e": "face",   # tên ngắn MỘT phụ âm đầu + nguyên âm + MỘT phụ âm không phải âm mũi + e câm: "face" (theo mặt chữ, e
                                # cuối -> e: chủ sách mi-ke, de-ke, ro-xe, ca-le, lu-xe, ca-ghe) | "phonemes" (Mai, Giác)
}
# Bộ kiểm âm tiết có bật không (quét tắt đi để đếm cả biến thể bộ kiểm không nhận; dùng thật luôn bật).
_CHECK_SYLLABLES = True

_VOWELS = frozenset({"AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY", "OW", "OY", "UH", "UW"})
_GLIDE_VOWELS = frozenset({"AY", "AW", "OY"})          # nguyên âm đôi kết bằng bán âm: ai, ao, oi không đứng trước phụ âm cuối
_SHORT_VOWELS = frozenset({"AE", "EH", "IH", "AA", "AH", "UH"})
_STOPS = frozenset({"P", "T", "K"})
_ALL_STOPS = frozenset({"P", "T", "K", "B", "D", "G"})
_ONSET = {
    "B": "b", "CH": "ch", "D": "đ", "F": "ph", "G": "G", "HH": "h", "JH": "gi", "K": "K", "L": "l", "M": "m", "N": "n", "NG": "NG",
    "P": "p", "R": "r", "S": "x", "SH": "s", "T": "t", "V": "v", "Z": "d", "ZH": "gi", "W": "u", "Y": "i",
}
_PLAIN_CODA = {"P": "p", "T": "t", "K": "c", "M": "m", "N": "n", "NG": "ng"}
_VOICED_STOP_CODA = {"B": "p", "D": "t", "G": "c"}
_FRICATIVE_CODA = {"S": "t", "Z": "t", "SH": "t", "ZH": "t", "TH": "t", "DH": "t", "CH": "t", "JH": "t", "F": "p", "V": "p"}
_FRONT = ("i", "e", "ê", "y")
_GRAVE = "̀"
_SCHWA_LETTER = {"a": "a", "e": "e", "i": "i", "y": "i", "o": "ơ", "u": "ơ"}

Phone = tuple[str, int, str]  # (ARPAbet không số, nhấn: -1 phụ âm / 0 / 1 / 2, chữ nguyên âm viết ra tương ứng hay "")


class _Syl:
    """Một âm tiết đầu ra: phụ âm đầu (chữ Việt, hay K / G / NG chờ chính tả), vần, phụ âm cuối (chữ Việt), có mang huyền không."""

    __slots__ = ("coda", "grave", "nucleus", "onset")

    def __init__(self, onset: str, nucleus: str, coda: str = "", grave: bool = False) -> None:
        self.onset = onset
        self.nucleus = nucleus
        self.coda = coda
        self.grave = grave


# ---- từ điển phát âm ---------------------------------------------------------------------------------------------------

_DEFAULT_PHONES: dict[str, str] | None = None


def load_phones(path: Path) -> dict[str, str]:
    """Đọc từ điển gọn: gzip, mỗi dòng "từ PHONES" (chữ thường, ARPAbet có số nhấn ở nguyên âm). Điện thoại tải file này theo yêu cầu."""
    entries: dict[str, str] = {}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            word, _, phones = line.rstrip("\n").partition(" ")
            if word and phones:
                entries[word] = phones
    return entries


def default_phones() -> dict[str, str]:
    """Từ điển đóng kèm bản máy tính, đọc một lần; không có file thì rỗng (chỉ còn đường chính tả)."""
    global _DEFAULT_PHONES
    if _DEFAULT_PHONES is None:
        _DEFAULT_PHONES = load_phones(PHONES_PATH) if PHONES_PATH.is_file() else {}
    return _DEFAULT_PHONES


def _parse_phones(text: str, word: str) -> list[Phone]:
    phones: list[Phone] = []
    for raw in text.split():
        if raw[-1:].isdigit():
            phones.append((raw[:-1], int(raw[-1]), ""))
        else:
            phones.append((raw, -1, ""))
    return _align_letters(phones, word)


def _vowel_groups(word: str, drop_final_e: bool) -> list[str]:
    """Các cụm chữ nguyên âm (a e i o u, y khi không đứng đầu trước nguyên âm) theo thứ tự."""
    letters = word[:-1] if drop_final_e else word
    groups: list[str] = []
    current = ""
    for index, ch in enumerate(letters):
        vowel = ch in "aeiou" or (ch == "y" and not (index == 0 and letters[1:2] in tuple("aeiou")))
        if vowel:
            current += ch
        elif current:
            groups.append(current)
            current = ""
    if current:
        groups.append(current)
    return groups


_HIATUS = ("ia", "io", "iu", "ie", "ea", "eo", "ua", "uo", "oa", "oe", "ue", "ui", "eu")


def _split_hiatus(groups: list[str], count: int) -> list[str] | None:
    """Cụm chữ cho đúng `count` nguyên âm: thiếu thì tách các cụm hai chữ đọc thành hai âm (ia, io, eo...: Phi-la-đen-phi-a), lấy các cụm
    cuối trước; không đủ thì None."""
    need = count - len(groups)
    if need == 0:
        return groups
    if need < 0:
        return None
    candidates = [index for index, group in enumerate(groups) if group in _HIATUS]
    if len(candidates) < need:
        return None
    chosen = set(candidates[len(candidates) - need:])
    out: list[str] = []
    for index, group in enumerate(groups):
        out.extend([group[0], group[1]] if index in chosen else [group])
    return out


def _align_letters(phones: list[Phone], word: str) -> list[Phone]:
    """Gắn cụm chữ nguyên âm cho từng nguyên âm khi số cụm bằng số nguyên âm (bỏ e câm cuối nếu cần); không bằng thì để trống."""
    count = sum(1 for phone in phones if phone[1] >= 0)
    for drop in (False, True):
        if drop and not (len(word) > 2 and word.endswith("e") and word[-2] not in "aeiouy"):
            continue
        groups = _split_hiatus(_vowel_groups(word, drop), count)
        if groups is not None:
            out, at = [], 0
            for base, stress, _ in phones:
                if stress >= 0:
                    out.append((base, stress, groups[at]))
                    at += 1
                else:
                    out.append((base, stress, ""))
            return out
    return phones


# ---- đường chính tả: chữ -> ARPAbet ------------------------------------------------------------------------------------

_LETTER_VOWELS = "aeiouy"
_LONG = {"a": "EY", "e": "IY", "i": "AY", "o": "OW", "u": "UW", "y": "AY"}
# Nguyên âm đơn theo mặt chữ (a e i o u): đường này gần như chỉ còn tên tự chế. a, o -> AA (đọc "a", "o": chủ sách tom, to-ni, ro-xe);
# o cuối từ vẫn "ô" (_FINAL_OPEN).
_FACE = {"a": "AA", "e": "EH", "i": "IH", "o": "AA", "u": "UH", "y": "IH"}
_FINAL_OPEN = {"a": "AA", "e": "IY", "i": "IY", "o": "OW", "u": "UW", "y": "IY"}
_DIGRAPHS = (("eau", "OW"), ("igh", "AY"), ("ee", "IY"), ("ea", "IY"), ("ai", "EY"), ("ay", "EY"), ("ei", "EY"), ("ie", "IY"), ("oa", "OW"),
             ("oo", "UW"), ("ou", "AW"), ("oi", "OY"), ("oy", "OY"), ("au", "AO"), ("aw", "AO"), ("ew", "UW"))


def _is_vowel_letter(word: str, index: int) -> bool:
    ch = word[index:index + 1]
    if ch == "y":
        return not (word[index + 1:index + 2] in tuple("aeiou") and (index == 0 or word[index - 1] not in _LETTER_VOWELS))
    return ch != "" and ch in "aeiou"


def _spell_phones(word: str) -> list[Phone] | None:
    w = word
    size = len(w)
    if size == 0 or not w.isascii() or not w.isalpha():
        return None
    silent_e = size >= 3 and w[-1] == "e" and not _is_vowel_letter(w, size - 2) and any(_is_vowel_letter(w, i) for i in range(size - 2))
    syllabic_le = silent_e and w[-2] == "l" and size >= 4 and not _is_vowel_letter(w, size - 3)  # -ble, -ple, -tle: phụ âm + əl
    if syllabic_le:
        silent_e = False
    end = size - 1 if silent_e else size
    if syllabic_le:
        end = size - 2
    # e câm: nguyên âm đơn ngay trước MỘT phụ âm cuối đọc dài (Kate, Pete, Mike)
    magic = size - 3 if silent_e and _is_vowel_letter(w, size - 3) and not _is_vowel_letter(w, size - 4) else -1
    out: list[Phone] = []
    i = 0
    while i < end:
        rest = w[i:end]
        ch = w[i]
        if _is_vowel_letter(w, i):
            if i == magic:
                out.append((_LONG[ch], 0, ch))
                i += 1
                continue
            digraph = next(((letters, phone) for letters, phone in _DIGRAPHS if rest.startswith(letters)), None)
            if rest in ("ey", "ay") or (rest == "ie" and size <= 4):
                digraph = (rest, "IY" if rest != "ay" else "EY")
            if rest.startswith("ow"):
                digraph = ("ow", "OW" if rest == "ow" else "AW")
            if rest == "ue":
                digraph = ("ue", "UW")
            if digraph is not None:
                letters, phone = digraph
                out.append((phone, 0, letters))
                i += len(letters)
                continue
            after = w[i + 1:i + 2]
            if after == "r" and not _is_vowel_letter(w, i + 2) and i + 1 < end:
                # ar, or, er / ir / ur / yr trước phụ âm hay cuối từ
                if ch == "a":
                    out.extend([("AA", 0, ch), ("R", -1, "")])
                elif ch == "o":
                    out.extend([("AO", 0, ch), ("R", -1, "")])
                else:
                    out.append(("ER", 0, ch))
                i += 2
                continue
            if ch == "a" and w[i + 1:i + 3] == "nk":
                out.append(("AE", 0, ch))  # ank -> anh như đường âm vị (tank -> tanh)
            elif i == end - 1:
                out.append((_FINAL_OPEN[ch], 0, ch))
            else:
                out.append((_FACE[ch], 0, ch))
            i += 1
            continue
        # phụ âm
        if rest.startswith(("tion", "sion")):
            out.extend([("SH" if ch == "t" else "ZH", -1, ""), ("AH", 0, "io"), ("N", -1, "")])
            i += 4
            continue
        if rest.startswith("tch"):
            out.append(("CH", -1, ""))
            i += 3
            continue
        two = rest[:2]
        if two in ("ch", "sh", "th", "ph", "ck", "ng", "wh", "dg"):
            out.append(({"ch": "CH", "sh": "SH", "th": "TH", "ph": "F", "ck": "K", "ng": "NG", "wh": "W", "dg": "JH"}[two], -1, ""))
            i += 2
            continue
        if two == "gh":
            if i == 0:
                out.append(("G", -1, ""))
            i += 2  # gh giữa / cuối từ câm (light, Hugh)
            continue
        if two == "qu":
            out.extend([("K", -1, ""), ("W", -1, "")])
            i += 2
            continue
        if i == 0 and two in ("kn", "gn", "wr"):
            out.append(("N" if two != "wr" else "R", -1, ""))
            i += 2
            continue
        if two == "gu" and _is_vowel_letter(w, i + 2):
            out.append(("G", -1, ""))
            i += 2
            continue
        if ch == w[i + 1:i + 2] and ch != "c":
            i += 1  # phụ âm đôi đọc một lần
            continue
        following = w[i + 1:i + 2]
        if ch == "c":
            if following in ("e", "i", "y"):
                out.append(("S", -1, ""))
            elif following == "c":
                out.append(("K", -1, ""))
                i += 1
                if w[i + 1:i + 2] in ("e", "i", "y"):
                    out.append(("S", -1, ""))
            else:
                out.append(("K", -1, ""))
        elif ch == "g":
            out.append(("JH" if following in ("e", "i", "y") else "G", -1, ""))
        elif ch == "x":
            out.extend([("Z", -1, "")] if i == 0 else [("K", -1, ""), ("S", -1, "")])
        elif ch == "y":
            out.append(("Y", -1, ""))
        elif ch == "h":
            if i == 0 or _is_vowel_letter(w, i + 1):
                out.append(("HH", -1, ""))  # h sau nguyên âm, trước phụ âm hay cuối từ thì câm (Sarah, Ahrin)
        elif ch == "w":
            out.append(("W", -1, ""))
        elif ch == "j":
            out.append(("JH", -1, ""))
        elif ch == "n" and following == "k":
            out.append(("NG", -1, ""))  # nk đọc /ŋk/ (tank, Frankie)
        elif ch == "q":
            out.append(("K", -1, ""))
        else:
            out.append(({"b": "B", "d": "D", "f": "F", "k": "K", "l": "L", "m": "M", "n": "N", "p": "P", "r": "R", "s": "S", "t": "T",
                         "v": "V", "z": "Z"}[ch], -1, ""))
        i += 1
    if syllabic_le:
        out.extend([("AH", 0, "e"), ("L", -1, "")])
    # mọi nguyên âm nhấn 0: chữ không cho biết trọng âm, nên không nhân đôi phụ âm (Li-ta-na, không "Lít-ta-na")
    if not any(phone[1] >= 0 for phone in out):
        return None
    return out


def _face_short(word: str) -> list[Phone]:
    """Tên ngắn + e câm đọc theo MẶT CHỮ (chủ sách 04-10: Mike -> mi-ke, Jake -> gia-ke, Rose -> ro-xe, Nate -> na-te): nguyên âm đọc như
    chữ, e cuối đọc e. Chỉ gọi khi `_short_silent_e` đúng."""
    phones = _spell_phones(word[:-1]) or []
    if word[-2] in "cg" and phones:
        phones[-1] = ("S" if word[-2] == "c" else "G", -1, "")  # c trước e mềm (Luce -> lu-xe), g cứng (Cage -> ca-ghe): chủ sách 04-10
    vowel = word[-3]
    return [(_FACE[vowel], 0, vowel) if phone[1] >= 0 else phone for phone in phones] + [("EH", 0, "e")]


def _short_silent_e(word: str) -> bool:
    """MỘT phụ âm đầu (một chữ, hay ch / sh / th / ph / wh) + một nguyên âm + MỘT phụ âm (trừ âm mũi m n và h w x y) + e câm: Jake,
    Zeke, Rose, Cale, Luce, Cage (chủ sách 04-10). Âm mũi đi đường âm vị (Jane -> giên, game -> ghêm), cũng như cụm phụ âm đầu
    (Blake -> bờ-lếch, Grace -> gờ-rây) và từ viết thường (make, late)."""
    onset = word[:-3]
    if not (word.endswith("e") and word[-2] in "bcdfgjklpqrstvz" and word[-3] in "aeiou"):
        return False
    return (len(onset) == 1 and onset not in "aeiouy") or onset in ("ch", "sh", "th", "ph", "wh")


# ---- ARPAbet -> âm tiết Việt -------------------------------------------------------------------------------------------

def _onset_letter(base: str) -> str:
    if base == "TH":
        return CHOICES["th"]
    if base == "DH":
        return CHOICES["dh"]
    return _ONSET[base]


def _epenthetic(base: str, initial: bool = False) -> _Syl:
    """Phụ âm không có nguyên âm của mình: âm tiết chèn ơ (luật 1.1: Mát-xơ-cơ-va); ở cụm đầu từ theo `epenthesis` (chủ sách: xờ-kiu,
    bờ-lếch), giữa từ theo `epenthesis_medial`."""
    vowel = CHOICES["epenthesis" if initial else "epenthesis_medial"]
    if base == "W":
        return _Syl("", "u")
    if base == "Y":
        return _Syl("", "i")
    if vowel == "ờ":
        return _Syl(_onset_letter(base), "ơ", "", True)
    return _Syl(_onset_letter(base), "ơ")


def _final_syllable(base: str, flags: list[str]) -> _Syl:
    """Phụ âm cuối không đứng được cuối âm tiết Việt thành âm tiết schwa MỞ, thanh HUYỀN (chủ sách 04-10): l -> lồ, phụ âm khác -> Cờ."""
    if base == "L":
        flags.append("analogy:l_syllable")
        return _Syl("l", "ô", "", True)
    flags.append("analogy:final_syllable")
    if base in ("W", "Y"):
        return _Syl("", "u" if base == "W" else "i", "", True)
    return _Syl(_onset_letter(base), "ơ", "", True)


def _coda_letter(base: str, final: bool) -> str | None:
    """Chữ Việt khép âm tiết cho một phụ âm ("" = bỏ), hay None khi phụ âm ấy phải thành âm tiết riêng."""
    if base in _PLAIN_CODA:
        return _PLAIN_CODA[base]
    if base == "L":
        return "n" if CHOICES["l_coda"] == "n" else ""
    if base == "R":
        return ""
    if base in _VOICED_STOP_CODA:
        if final and CHOICES["voiced_final"] == "syllable":
            return None
        return _VOICED_STOP_CODA[base]
    if base in _FRICATIVE_CODA:
        if final:
            return _FRICATIVE_CODA[base] if CHOICES["fric_final"] == "stop" else None
        if base in ("S", "Z"):
            return "t" if CHOICES["s_coda"] == "t" else None
        return _FRICATIVE_CODA[base]
    return None


def _is_schwa(phone: Phone) -> bool:
    return phone[0] == "AH" and phone[1] == 0


def _nucleus(phone: Phone, coda: str, r_colored: bool) -> str:
    base, stress, letters = phone
    if base == "AA":
        return CHOICES["aa_o"] if "o" in letters else "a"
    if base == "AO":
        if "a" in letters and "o" not in letters:
            return "a"
        return "oo" if r_colored and coda in ("c", "ng") else "o"  # Niu Oóc, Poóc-len: o dài trước c / ng viết oo
    if base == "AE":
        return CHOICES["ae"]
    if base == "AH":
        if stress == 0:
            if CHOICES["schwa"] == "letter" and letters:
                return _SCHWA_LETTER.get(letters[-1], "ơ")  # chữ cuối của cụm: Virginia -> ni-a, nation -> ơn
            return "ơ"
        return "ă" if coda else "a"
    if base == "EH":
        return CHOICES["eh"]
    if base == "IH":
        return CHOICES["ih"]
    if base == "EY":
        if not coda:
            return "ây"
        if coda in ("m", "n", "ng"):
            return CHOICES["ey_nasal"]
        return CHOICES["ey_p" if coda == "p" else "ey_k" if coda in ("c", "ch") else "ey_t"]
    if base == "AY" and coda == "m":
        return "a"  # xờ-lam, tham (chủ sách 04-10; CHOICES["ay_m"])
    return {"IY": "i", "UH": "u", "UW": "u", "OW": "ô", "ER": "ơ", "AY": "ai", "AW": "ao", "OY": "oi"}[base]


def _glide_w(nucleus: str) -> str | None:
    """w + vần: oa, oă, oe, uê, uy, uây, uơ, uâ, oai; vần khác thì None (w thành âm tiết u riêng)."""
    if nucleus.startswith("ây"):
        return "u" + nucleus
    if nucleus[:1] in ("a", "ă"):
        return "o" + nucleus
    if nucleus[:1] == "e":
        return "o" + nucleus
    if nucleus[:1] in ("ê", "ơ", "â"):
        return "u" + nucleus
    if nucleus == "i":
        return "uy"
    return None


def _syllabify(phones: list[Phone], flags: list[str], word_start: bool = True) -> list[_Syl] | None:
    """`word_start` False: phần sau của từ ghép (w ở đó không thành gu)."""
    # /aɪər/ (fire, higher): ơ sau ai nuốt vào ai, r bỏ (chủ sách 04-10: fireball -> phai-bôn)
    phones = [phone for index, phone in enumerate(phones)
              if not (phone[0] == "ER" and phone[1] == 0 and index > 0 and phones[index - 1][0] == "AY")]
    vowels = [index for index, phone in enumerate(phones) if phone[1] >= 0]
    if not vowels:
        return None
    out: list[_Syl] = []
    onset, glide = _onset_run([phone[0] for phone in phones[:vowels[0]]], out, flags, phones[vowels[0]] if word_start else None)
    w_gu = onset == "G" and vowels[0] == 1 and phones[0][0] == "W"  # w đầu từ đã thành gu (_onset_run)
    for k, at in enumerate(vowels):
        vowel = phones[at]
        last = k == len(vowels) - 1
        run = [phone[0] for phone in (phones[at + 1:] if last else phones[at + 1:vowels[k + 1]])]
        # -əl cuối từ: schwa + l thành "ồ" (l bỏ), thanh huyền - chủ sách 04-10 (máp-pồ, mai-cồ, le-vồ)
        if last and _is_schwa(vowel) and run[:1] == ["L"]:
            _emit(out, onset, glide, "ô", "", True)
            for base in run[1:]:
                if CHOICES["final_cluster"] == "syllable":
                    out.append(_final_syllable(base, flags))
            return out
        r_colored = False
        if run[:1] == ["R"] and (last or len(run) >= 2):
            run = run[1:]  # r sau nguyên âm bỏ (Poóc-len, Niu Oóc)
            r_colored = True
        can_close = vowel[0] not in _GLIDE_VOWELS or (vowel[0] == "AY" and run[:1] == ["M"] and CHOICES["ay_m"] == "am")
        il_final = False
        coda, coda_phone = "", ""
        tail: list[_Syl] = []
        next_onset, next_glide = "", ""
        if last:
            if run[:1] == ["L"] and vowel[0] in ("IH", "IY") and CHOICES["il_final"] == "u":
                il_final = True  # skill -> xờ-kiu (chủ sách 04-10): l cuối sau i thành u
                run = run[1:]
                for base in run:
                    if CHOICES["final_cluster"] == "syllable":
                        tail.append(_final_syllable(base, flags))
                run = []
            if vowel[0] == "EY" and run[:1] == ["S"]:
                run = []  # /eɪ/ + s cuối: ây, s bỏ (chủ sách 04-10: Grace -> gờ-rây)
            if run:
                first = run[0]
                coda_phone = first
                letter = _coda_letter(first, True) if can_close else ("" if CHOICES["glide_coda"] == "drop" else None)
                if first == "L" and not can_close:
                    # l sau ai / ao / oi: âm tiết "ồ" KHÔNG phụ âm đầu, l bỏ (chủ sách 04-10: lai-ồ, kai-ồ, đoi-ồ)
                    tail.append(_Syl("", "ô", "", True))
                elif letter is None:
                    tail.append(_final_syllable(first, flags))
                else:
                    coda = letter
                for base in run[1:]:
                    if CHOICES["final_cluster"] == "syllable":
                        tail.append(_final_syllable(base, flags))
        else:
            head, next_onset, next_glide = _split_onset(run)
            if next_onset == "NG":
                head, next_onset = head + ["NG"], ""  # ng tiếng Anh không mở âm tiết: Hê-minh-uây
            if not run and vowel[0] == "ER":
                next_onset = "R"  # r của ơ trước nguyên âm mở âm tiết sau: Cô-lô-ra-đô, ca-mê-ra
            liquid_stop = ""
            if next_onset in ("L", "R") and head and head[-1] in _ALL_STOPS:
                # tắc + l / r giữa từ: tách thành "Cờ" thanh huyền, âm tiết trước không khép bằng nó (chủ sách 04-10: Laplace -> la-pờ-lết)
                liquid_stop, head = head[-1], head[:-1]
            geminate = CHOICES["geminate"]
            if not head and not liquid_stop and next_onset and len(run) == 1 and run[0] in _STOPS and can_close and vowel[1] >= 1 and (
                geminate == "stressed" or (geminate == "primary" and vowel[1] == 1)
                or (geminate == "short" and vowel[0] in _SHORT_VOWELS)
            ):
                coda = _PLAIN_CODA[run[0]]  # máp-pồ, Rốc-ki: phụ âm tắc vừa khép âm tiết nhấn vừa mở âm tiết sau
            if head and can_close:
                letter = _coda_letter(head[0], False)
                if letter is not None:
                    coda, coda_phone = letter, head[0]
                    head = head[1:]
            tail = [_epenthetic(base) for base in head]
            if liquid_stop:
                tail.append(_Syl(_onset_letter(liquid_stop), "ơ", "", True))
        nucleus = _nucleus(vowel, coda, r_colored)
        if vowel[0] == "AO" and coda_phone == "L" and coda:
            nucleus = "ô"  # /ɔːl/ -> ôn (chủ sách 04-10: fireball -> phai-bôn, như gôn)
        if k == 0 and w_gu and not coda:
            onset = ""  # guô chỉ đứng trước phụ âm cuối: âm tiết mở giữ w như cũ (Warrior -> Oa-ri-ơ)
            flags.remove("analogy:w_gu")
        elif k == 0 and w_gu and vowel[0] in ("AO", "AA"):
            nucleus = "ô"  # gu + âm o đọc guô (chủ sách 04-10: Walt -> guốt): water -> guốt-tơ
        if vowel[0] == "AE" and coda == "ng" and run[:2] == ["NG", "K"]:
            nucleus, coda = "a", "nh"  # /æŋk/ -> anh (chủ sách 04-10: tank -> tanh; rank, thank theo đó)
            flags.append("analogy:ank")
        if il_final:
            nucleus += "u"
        _emit(out, onset, glide, nucleus, coda, False)  # -er cuối: ơ thanh ngang (chủ sách 04-10: mát-tơ)
        out.extend(tail)
        onset, glide = next_onset, next_glide
    return out


def _onset_run(run: list[str], out: list[_Syl], flags: list[str], first_vowel: Phone | None) -> tuple[str, str]:
    head, onset, glide = _split_onset(run)
    out.extend(_epenthetic(base, True) for base in head)
    if run == ["W"] and first_vowel is not None and (
        first_vowel[0] in ("AO", "OW") or (first_vowel[0] == "AA" and "o" in first_vowel[2])
    ):
        # w đầu từ trước âm o -> gu (chủ sách 04-10: Walt -> guốt; như won -> guôn của tiếng Hàn); w trước âm khác giữ oa / uy / oe
        # (Oa-sinh-tơn). Các từ ngoài Walt suy theo, có cờ
        flags.append("analogy:w_gu")
        onset = "G"
    return onset, glide


def _split_onset(run: list[str]) -> tuple[list[str], str, str]:
    """Tách dãy phụ âm trước một nguyên âm thành (phần đầu, phụ âm đầu của âm tiết, bán âm w / y)."""
    if not run:
        return [], "", ""
    glide = ""
    if run[-1] in ("W", "Y"):
        glide = run[-1]
        run = run[:-1]
        if not run:
            return [], "", glide
    if len(run) >= 2 and run[-2:] == ["T", "R"] and CHOICES["tr"] == "tr":
        return run[:-2], "tr", glide
    return run[:-1], run[-1], glide


def _fits(letter: str, nucleus: str, coda: str, grave: bool) -> bool:
    """Âm tiết ghép ra có là âm tiết tiếng Việt không (bộ kiểm tắt thì luôn có)."""
    return not _CHECK_SYLLABLES or valid_syllable(_render(_Syl(letter, nucleus, coda, grave)))


def _emit(out: list[_Syl], onset: str, glide: str, nucleus: str, coda: str, grave: bool) -> None:
    letter = _onset_letter(onset) if onset and onset != "tr" else onset
    if glide == "W":
        joined = "uô" if nucleus == "ô" and coda else _glide_w(nucleus)  # uô chỉ đứng trước phụ âm cuối: Walt -> Uôn
        if joined is not None and not _fits(letter, joined, coda, grave):
            # vần ghép không có trong tiếng Việt (uên, oáp, oép): uê -> oe (Wayne -> Oen), còn lại w thành âm tiết u riêng (Dwarf -> Đu-óp)
            joined = "oe" + nucleus[1:] if joined == "uê" and _fits(letter, "oe" + nucleus[1:], coda, grave) else None
        if joined is not None:
            out.append(_Syl(letter, joined, coda, grave))
            return
        out.append(_Syl(letter, "u"))
        letter = ""
    elif glide == "Y":
        if nucleus.startswith("i"):
            out.append(_Syl(letter, nucleus, coda, grave))  # y + i: một âm i
            return
        if nucleus == "u" and not coda:
            out.append(_Syl(letter, "iu", "", grave))  # Mét-thiu, Niu
            return
        out.append(_Syl(letter, "i"))
        letter = ""
    out.append(_Syl(letter, nucleus, coda, grave))


def _render(syllable: _Syl) -> str:
    onset, nucleus, coda = syllable.onset, syllable.nucleus, syllable.coda
    if not coda and nucleus in ("ă", "â", "oă"):
        nucleus = {"ă": "a", "â": "ơ", "oă": "oa"}[nucleus]
    if nucleus == "oo" and coda not in ("c", "ng"):
        nucleus = "o"
    if onset == "K":
        for glide in ("oai", "oa", "oă", "oe", "uy", "uê", "uơ", "uâ"):
            if nucleus.startswith(glide):
                onset, nucleus = "qu", nucleus[1:]
                if nucleus == "y" and coda not in ("", "t", "nh"):
                    nucleus = "i"  # quy, quýt, quỳnh nhưng quin, quích (y chỉ khép bằng t / nh)
                break
        else:
            onset = "k" if nucleus[:1] in _FRONT else "c"
    elif onset == "G":
        onset = "gh" if nucleus[:1] in _FRONT else "g"
    elif onset == "NG":
        onset = "ngh" if nucleus[:1] in _FRONT else "ng"
    elif onset == "gi" and nucleus[:1] == "i":
        onset = "g"  # gi + in viết gin, gi + i viết gi
    if coda in ("ng", "c") and nucleus.endswith(("i", "ê")) and nucleus[-2:-1] not in ("i", "y", "u"):
        coda = "nh" if coda == "ng" else "ch"  # kinh, ích: -nh / -ch sau i, ê đơn (luật chính tả)
    if coda in ("c", "t", "p", "ch"):
        nucleus = _tone_acute(nucleus)
    elif syllable.grave:
        nucleus = unicodedata.normalize("NFC", nucleus + _GRAVE)
    return onset + nucleus + coda


def _validated(syllables: list[_Syl], capital: bool) -> str | None:
    pieces = [_render(syllable) for syllable in syllables]
    if not pieces or (_CHECK_SYLLABLES and any(not valid_spoken_form(piece) for piece in pieces)):
        return None
    word = "-".join(pieces)
    return word[:1].upper() + word[1:] if capital else word


# ---- cửa vào -----------------------------------------------------------------------------------------------------------

def _part_case(part: str) -> bool | None:
    """True nếu viết hoa chữ đầu, False nếu toàn chữ thường, None nếu không phải chữ ASCII hay viết hoa lạ (toàn hoa, hoa giữa chữ)."""
    if not part or not part.isascii() or not part.isalpha():
        return None
    if part == part.lower():
        return False
    if part[0].isupper() and part[1:] == part[1:].lower():
        return True
    return None


def _compound_parts(key: str, dictionary: Mapping[str, str]) -> tuple[str, str] | None:
    """Từ ghép không có trong từ điển mà hai nửa có (sandworm = sand + worm): đọc từng phần (chủ sách 04-10: fireball -> phai-bôn).
    Mỗi nửa ít nhất COMPOUND_NAME_MIN_PART chữ như cách tách tên ghép của Studio; nửa đầu dài nhất trước."""
    from .analysis import COMPOUND_NAME_MIN_PART

    for cut in range(len(key) - COMPOUND_NAME_MIN_PART, COMPOUND_NAME_MIN_PART - 1, -1):
        if key[:cut] in dictionary and key[cut:] in dictionary:
            return key[:cut], key[cut:]
    return None


def _read_word(key: str, capital: bool, dictionary: Mapping[str, str], overrides: bool, flags: list[str], word_start: bool = True,
               ) -> str | None:
    if overrides and key in OVERRIDES:
        flags.append("via:override")
        reading = OVERRIDES[key]
        return reading[:1].upper() + reading[1:] if capital else reading
    phones: list[Phone] | None = None
    route = "via:phonemes"
    if capital and _short_silent_e(key) and CHOICES["short_silent_e"] == "face":
        phones, route = _face_short(key), "via:face"
    if phones is None and key in dictionary:
        phones = _parse_phones(dictionary[key], key)
    if phones is None:
        parts = _compound_parts(key, dictionary)
        if parts is not None:
            inner: list[str] = []
            readings = [_read_word(part, capital and index == 0, dictionary, overrides, inner, word_start and index == 0)
                        for index, part in enumerate(parts)]
            if all(readings):
                flags.append("via:compound")
                flags.extend(inner)
                return "-".join(readings)
    if phones is not None:
        trial: list[str] = []
        syllables = _syllabify(phones, trial, word_start)
        reading = None if syllables is None else _validated(syllables, capital)
        if reading is not None:
            flags.append(route)
            flags.extend(trial)
            return reading
        flags.append("fit:spelling")
    phones = _spell_phones(key)
    if phones is None:
        return None
    trial = []
    syllables = _syllabify(phones, trial, word_start)
    reading = None if syllables is None else _validated(syllables, capital)
    if reading is None:
        return None
    flags.append("via:spelling")
    flags.extend(trial)
    return reading


def vietnamized_english_flags(word: str, dictionary: Mapping[str, str] | None = None, overrides: bool = True,
                              ) -> tuple[str, tuple[str, ...]] | None:
    """(cách đọc, cờ) hay None. `dictionary` None = từ điển đóng kèm (`default_phones`); `{}` = máy không có từ điển (chỉ đường chính tả).
    `overrides` False = chỉ luật (quét và bộ thử đo luật, không đo bảng ghi đè). Từ nối gạch (Jean-Paul) đọc từng bộ phận, cách nhau dấu
    cách."""
    value = unicodedata.normalize("NFC", str(word).strip())
    if not value or any(ch.isspace() for ch in value):
        return None
    phones = default_phones() if dictionary is None else dictionary
    flags: list[str] = []
    readings: list[str] = []
    for part in value.split("-"):
        if overrides and part in ACRONYMS:
            flags.append("via:override")
            readings.append(ACRONYMS[part])
            continue
        case = _part_case(part)
        if case is None:
            return None
        reading = _read_word(part.lower(), case, phones, overrides, flags)
        if reading is None:
            return None
        readings.append(reading)
    return " ".join(readings), tuple(dict.fromkeys(flags))


def vietnamized_english(word: str, dictionary: Mapping[str, str] | None = None, overrides: bool = True) -> str | None:
    """Cách đọc nối gạch của một từ / tên tiếng Anh bằng âm tiết Việt, hay None khi không chắc."""
    found = vietnamized_english_flags(word, dictionary, overrides)
    return None if found is None else found[0]
