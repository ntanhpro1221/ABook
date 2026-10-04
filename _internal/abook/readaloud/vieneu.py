"""Giọng VieNeu cho "Nghe ngay" (docs/LISTEN_ANYTHING.md mục 3): giọng đọc ngay trên máy, không cần mạng, có khi người dùng đã tải mô-đun
"Giọng VieNeu" (webui/vieneu_module.py). Máy chưa tải thì danh sách giọng rỗng; gói đóng sẵn không có numpy nên engine chỉ nạp khi cần.

Một clip = MỘT đoạn của chương. Đoạn được chia thành các "khúc" theo câu như vieneu (`units`: gói câu tới `max_chars` ký tự, câu quá dài cắt ở
dấu phẩy rồi ở khoảng trắng, khúc dưới 20 ký tự gộp vào khúc kề - khúc 1-2 chữ đứng riêng làm model "nói thêm"), đọc từng khúc, ghép với khoảng
nghỉ tối thiểu như vieneu (0,5 giây sau câu, 0,3 giây sau dấu phẩy). Không đọc riêng từng cụm giữa hai dấu phẩy: bộ chuẩn hoá của sea-g2p bỏ dấu
phẩy cuối cụm và chốt dấu chấm, nên mỗi dấu phẩy sẽ thành giọng xuống của cuối câu.

Mốc từng chữ hiện: mỗi khúc biết chính xác chỗ của nó trong clip, rồi căn chữ của khúc ấy vào audio của nó bằng `word_timing.line_words` -
bộ căn CTC (122 MB, phần tuỳ chọn của mô-đun, mặc định có trên máy tính) nếu có, không thì chia thời gian theo âm tiết neo vào các khoảng lặng
dò bằng năng lượng ở chỗ dấu câu.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import threading
import time
import unicodedata
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import abbreviations, names, shouts, symbols
from .model import Synthesis, Voice, VoiceError

PREFIX = "vieneu"
TIERS = ("turbo", "nano")
TIER_LABEL = {"turbo": "VieNeu", "nano": "VieNeu Nano"}
VOICE_FILES = {"turbo": "voices_v3_turbo.json", "nano": "voices_v3_nano.json"}
MAX_CHARS = {"turbo": 256, "nano": 140}  # như vieneu: Nano học trên đoạn <= 15 giây nên khúc ngắn hơn
MIN_UNIT_CHARS = 20
SENTENCE_END = ".!?…"
PHRASE_END = ",;:"
CLOSERS = "\"'”’)]»"
OPENERS = "\"'“‘([«"
ROMAN = re.compile(r"X{0,3}(?:IX|IV|V?I{0,3})")  # I..XXXIX (chuỗi rỗng khớp, bị loại riêng)
_ROMAN_VALUE = {"I": 1, "V": 5, "X": 10}
_DIGITS = ("", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín")
# Dấu bộ chuẩn hoá của sea-g2p đọc sai: "~" luôn là "khoảng", "500,000" là "năm trăm", "<Tên>" là "nhỏ hơn ... lớn hơn", "a / b" là "a trên b".
TILDES = re.compile(r"~+")
THOUSANDS = re.compile(r"(?<![0-9.,])[0-9]{1,3}(?:,[0-9]{3})+(?![0-9]|[.,][0-9])")  # kiểu Anh: 1,500 là một nghìn rưỡi; thập phân Việt "1,5" thì không khớp
FRAMES_OPEN = "【〔「『{"  # khung của bảng trạng thái / lời thoại kiểu Nhật: chữ La Mã sát trong khung vẫn là số
FRAMES_CLOSE = "】〕」』}"
SYSTEM_OPEN = "【〔[{"  # khung của bảng trạng thái / thông báo hệ thống: sea-g2p bỏ khung mà không ngắt, người nghe cần một nhịp ở hai đầu
SYSTEM_CLOSE = "】〕]}"
DASHES = "—–―"
FULLWIDTH = {"，": ",", "：": ":", "；": ";", "。": ".", "！": "!", "？": "?", "、": ","}  # dấu câu CJK: sea-g2p bỏ qua, người nghe mất nhịp
ANGLE_OPEN = "<《〈"
ANGLE_CLOSE = ">》〉"
ANGLE_REACH = 24  # ngoặc nhọn mở và đóng cách nhau tối đa bấy nhiêu chữ hiện (lời nghĩ trong <...> có thể dài cả câu)
PUNCT_MARKS = ".,;:!?…"
RANGE = re.compile(r"(?<![\w/.,-])([0-9]{1,4})((?:-[0-9]{1,4})+)(?![\w/-]|[.,][0-9])")  # 3-4000, 1-1, 1-3-1
EMOTICON = re.compile(r"(?:[:;=]['\-^o]?[()dDpP3vV/\|*]+|>[:;=]['\-^o]?[()]+|<3+|-_-|\^_*\^|[Tt]_[Tt]|>_<|orz|OTZ)")
ARROW_FORWARD = re.compile(r"(?<![<=-])(?:-+|=+)>|[→⇒➜➡➔⟶⟹]")  # "->", "-->", "=>", "→": sea-g2p đọc "sang" / "đến" / "suy ra"; "<->" (hai chiều) để nguyên
ARROW_BACK = re.compile(r"<(?:-+|={2,})(?!>)|[←⇐⟵⟸]")  # "<-", "<--", "←": không có cách đọc thành lời (sea-g2p đọc "nhỏ hơn"): bỏ; "<=" là so sánh, để nguyên
ARROW_STATS = frozenset("hp mp sp exp xp lv lvl level cấp hạng rank điểm giá str agi vit int dex luk atk def máu mana tiền vàng tuổi".split())  # nhãn chỉ số: mũi tên cạnh nó là đổi giá trị
ARROW_COUNTED = frozenset("trang chương tập bước phần mục tầng ngày tháng năm hồi bài page step chapter từ tuyến đường bay".split())  # đánh số / chỉ đường: mũi tên là "đến"
ARROW_TIME = re.compile(r"[0-9]{1,2}(?:[hHgG][0-9]{0,2}|:[0-9]{2})")  # 8h, 8h30, 10g, 8:00
ARROW_TIME_WORDS = frozenset("giờ sáng trưa chiều tối khuya".split())
RANGE_CODES = frozenset("lớp phòng tầng combo feed số thắng thua truyện".split())  # "lớp 1-7", "phòng 4-13": mã, hai số đọc liền không có "đến"
RANGE_RATIO = frozenset("tỉ tỷ lệ".split())  # "tỉ lệ 3-7"
GLUED = re.compile(r"((?:\.{2,}|[…—–])+)")  # chỗ dính liền hai từ trong một chữ hiện (tách để đọc từng từ, mảnh dấu giữ nguyên)
STUTTER_ONSETS = ("ngh", "ng", "nh", "kh", "ch", "gh", "gi", "th", "tr", "ph", "qu")  # phụ âm đầu ghép của tiếng Việt: nói lắp "C-Chuyện" là "chờ… chuyện"
STUTTER_SOUND = {"k": "c", "w": "v", "z": "d", "j": "gi", "f": "ph"}
STUTTER = re.compile(r"([^\w]*)([^\W\d_]{1,3})-+([^\W\d_].*)$", re.DOTALL)
STUTTER_ALONE = re.compile(r"([^\w]*)([^\W\d_]{1,3})-+([^\w]*)$")
# Số La Mã MỘT chữ (I, V, X) hay là chữ cái ("ông X", "tia X", "điểm V"): chỉ đọc thành số sau danh từ đánh số (hay tên riêng viết hoa kép: "Louis X").
NUMBERED_NOUNS = frozenset(unicodedata.normalize("NFC", word) for word in (
    "chương", "phần", "tập", "quyển", "hồi", "mục", "khoá", "khóa", "lớp", "cấp", "hạng", "bậc", "đệ", "đời", "kỳ", "kì", "số", "bài", "điều",
    "khoản", "chặng", "vòng", "màn", "cảnh", "tầng"))
NUMBERED_PAIRS = frozenset(unicodedata.normalize("NFC", pair) for pair in ("thế kỷ", "thế kỉ", "thế chiến"))
ALIGN_RATE = 16_000
BENCH_TEXT = "Chiếc thuyền nhỏ trôi chậm giữa dòng sông, mang theo những mùa hè đã xa. Trời hôm nay đẹp quá."


@dataclass(frozen=True)
class Installed:
    """Những gì mô-đun đã đặt trên máy (vieneu_module.installed): thư mục từng giọng, file giọng có sẵn, có dùng bộ căn chữ không."""

    voices: Path
    turbo: tuple[Path, Path] | None = None  # (thư mục model, thư mục bộ giải mã)
    nano: Path | None = None
    aligner: bool = False


@dataclass
class Unit:
    """Một khúc: chữ hiện từ `first` tới `last` (kể cả), đem đọc như các câu `pieces`."""

    first: int
    last: int
    pieces: list[str] = field(default_factory=list)

    def text(self, toks: list[str]) -> str:
        return " ".join(toks[self.first:self.last + 1])


def roman_value(core: str) -> int | None:
    """Số La Mã viết HOA hợp lệ I..XXXIX (đúng chuẩn: không IIII, VX...), None nếu `core` không phải."""
    if not core or not ROMAN.fullmatch(core):
        return None
    total = 0
    for index, letter in enumerate(core):
        value = _ROMAN_VALUE[letter]
        total += -value if index + 1 < len(core) and _ROMAN_VALUE[core[index + 1]] > value else value
    return total


def vietnamese_number(value: int) -> str:
    """1..39 thành chữ: mười bốn, mười lăm, hai mươi mốt, hai mươi lăm, ba mươi."""
    tens, ones = divmod(value, 10)
    head = "" if tens == 0 else "mười" if tens == 1 else f"{_DIGITS[tens]} mươi"
    tail = "" if ones == 0 else "lăm" if ones == 5 and tens else "mốt" if ones == 1 and tens > 1 else _DIGITS[ones]
    return f"{head} {tail}".strip()


def _word(token: str) -> str:
    return unicodedata.normalize("NFC", token.lstrip(OPENERS).rstrip(CLOSERS))


def _capitalised(word: str) -> bool:
    return word.isalpha() and word[0].isupper()


def numbered_by(toks: list[str], index: int) -> bool:
    """Từ đứng trước `toks[index]` có đánh số được không: danh từ đánh số ("chương", "thế kỷ"...) hay hai tên riêng viết hoa liền nhau ("Louis X")."""
    before = _word(toks[index - 1]) if index >= 1 else ""
    if before.lower() in NUMBERED_NOUNS:
        return True
    earlier = _word(toks[index - 2]) if index >= 2 else ""
    if f"{earlier} {before}".lower() in NUMBERED_PAIRS:
        return True
    return _capitalised(before) and _capitalised(earlier)


def _digit(char: str) -> bool:
    return "0" <= char <= "9" and len(char) == 1


def _tilde(token: str) -> str:
    def replace(match: re.Match) -> str:
        left = token[match.start() - 1] if match.start() else ""
        right = token[match.end()] if match.end() < len(token) else ""
        if _digit(left) and _digit(right):
            return " đến "
        if _digit(right) and not left.isalnum():
            return match.group()  # "~50 người": để sea-g2p đọc "khoảng"
        return " " if left.isalpha() and right.isalpha() else ""  # "Hmm~", "Har~kun"
    return TILDES.sub(replace, token)


def _tildes(out: list[str]) -> None:
    """"~" kéo dài giọng ("Hmm~") thì bỏ, giữa hai số ("3~5", "10,000 ~ 15,000") là "đến", trước số ("~50") là "khoảng" (sea-g2p đọc)."""
    for index, token in enumerate(out):
        if "~" not in token:
            continue
        if token.strip(OPENERS + CLOSERS + PUNCT_MARKS).strip("~"):  # còn chữ khác: xét trong chính chữ này
            out[index] = _tilde(token)
            continue
        before = out[index - 1].rstrip(CLOSERS) if index else ""  # "~" đứng riêng: nhìn chữ kề hai bên
        after = out[index + 1].lstrip(OPENERS) if index + 1 < len(out) else ""
        number_after = bool(after) and _digit(after[0])
        said = TILDES.sub("đến" if number_after and bool(before) and _digit(before[-1]) else "~" if number_after else "", token)
        if index and not said.strip(CLOSERS + PUNCT_MARKS):  # "Ô ~," -> "Ô,": dấu câu còn lại dính vào chữ trước
            out[index - 1] += said
            said = ""
        out[index] = said


def _core(token: str) -> str:
    """Chữ của `token` bỏ dấu câu và ngoặc hai đầu ("[Cường" -> "Cường", "1940." -> "1940")."""
    first, last = 0, len(token)
    while first < last and not token[first].isalnum():
        first += 1
    while last > first and not token[last - 1].isalnum():
        last -= 1
    return token[first:last]


def _arrow_says(plain: list[str], index: int, token: str, match: re.Match) -> str:
    """Mũi tên đổi giá trị / trạng thái ("HP: 1780 --> 1940", "Lv 5 -> Lv 6", "Cân lực : 100 ⇒ 200") đọc "thành"; chỉ hướng đi / khoảng / trình tự ("Tokyo -> Osaka", "8h -> 10h",
    "Bước 1 -> Bước 2", "trang 3 -> 5") đọc "đến" (chủ sách 04-10: "tùy ngữ cảnh"). Xét hai vế (phần cùng chữ hay chữ liền trước / sau) và tối đa 3 chữ đứng trước vế trái (trong cùng câu):
    nhãn chỉ số ("HP", "Lv", "cấp", "điểm", "giá"...) hay vế trái / phải là chỉ số -> thành; hai mũi tên trở lên trong câu ("A -> B -> C": chuỗi bước) -> rồi; giờ giấc ("8h", "8:00", "giờ"), danh từ đánh số / chỉ đường
    ("trang", "bước", "từ", "tuyến"...) -> đến; dấu ":" trong cùng câu (ô trạng thái đang đổi: "Nghề: A -> B") -> thành; hai tên riêng viết hoa một chữ ("Tokyo -> Osaka") -> đến; vế phải bắt đầu chữ thường
    ("tốn công vô ích -> tạ": kết quả) -> nên; còn lại (không rõ) -> thành."""
    left = _core(token[:match.start()])
    left_at = index if left else index - 1
    if not left and left_at >= 0:
        left = _core(plain[left_at])
    right = _core(token[match.end():])
    right_at = index
    if not right and index + 1 < len(plain):
        right, right_at = _core(plain[index + 1]), index + 1
    labels: list[str] = []
    colon = False
    for back in range(left_at - 1, max(left_at - 4, -1), -1):
        word = plain[back].rstrip(CLOSERS)
        if word and word[-1] in SENTENCE_END:
            break
        colon = colon or word.endswith(":")
        labels.append(_core(word).lower())
    stat = lambda word: word.lower() in ARROW_STATS or word.lower().rstrip("0123456789") in ARROW_STATS  # "Lv5" -> "lv"
    scale = lambda at: 0 <= at < len(plain) and any(char in "★☆" for char in plain[at])  # "★★★☆☆ -> ★★★★☆": thang sao đổi
    if any(stat(word) for word in labels) or stat(left) or stat(right) or scale(left_at) or scale(right_at):
        return "thành"
    numeric = lambda word: any(char.isdigit() for char in word)
    if (numeric(left) or numeric(right)) and any(":" in word for word in plain[max(0, index - 6):index]):
        return "thành"  # "Thể lực : 120 ⇒ 240 ⇒ 480": bảng chỉ số đang đổi
    if _arrow_count(plain, index) >= 2:
        return "rồi"
    when = lambda word: bool(ARROW_TIME.fullmatch(word)) or word.lower() in ARROW_TIME_WORDS
    if any(word in ARROW_COUNTED for word in labels) or when(left) or when(right):
        return "đến"
    if colon:
        return "thành"
    named = lambda word: len(word) >= 3 and word.isalpha() and word[0].isupper() and word[1:].islower()
    beside = [plain[at] if 0 <= at < len(plain) else "" for at in (left_at - 1, right_at + 1)]  # tên nhiều chữ ("Tân Thủ -> Pháp Sư") không chắc là nơi chốn
    if named(left) and named(right) and not any(named(_core(word)) for word in beside):
        return "đến"
    clause = sum(1 for word in plain[max(0, index - 4):index] if _core(word).isalpha()) >= 3  # vế trước đủ dài để là một mệnh đề ("tốn công vô ích -> tạ")
    return "nên" if right[:1].islower() and clause else "thành"


def _arrow_count(plain: list[str], index: int) -> int:
    """Số mũi tên quanh `plain[index]` (tới 4 chữ mỗi bên, không qua chữ hết câu): từ hai trở lên là chuỗi bước ("A -> B -> C"), hai mũi tên xa nhau ("64 -> 79, Nhanh nhẹn 59 -> 74") thì không."""
    ends = lambda word: (bool(word.rstrip(CLOSERS)) and word.rstrip(CLOSERS)[-1] in SENTENCE_END + ",;") or word.lower() in ("và", "hoặc", "and", "or")  # hết câu / vế: mũi tên hai bên là hai việc riêng
    first, last = index, index
    while first > max(0, index - 4) and not ends(plain[first - 1]):
        first -= 1
    while last < min(len(plain) - 1, index + 4) and not ends(plain[last]):
        last += 1
    return len(ARROW_FORWARD.findall(" ".join(plain[first:last + 1])))


def _arrow(token: str, at_start: bool, says: Callable[[re.Match], str], at_end: bool = False) -> str:
    def replace(match: re.Match, word: str) -> str:
        left = token[match.start() - 1] if match.start() else ""
        right = token[match.end()] if match.end() < len(token) else ""
        if not left and at_start:
            word = ""  # "-> Bước tiếp": mũi tên đầu dòng chỉ là dấu đầu mục
        if at_end and not token[match.end():].strip(CLOSERS + PUNCT_MARKS + "〙】」』〕"):
            word = ""  # "Khu Hẻm Tử Thần→〙": mũi tên cuối đoạn chỉ về phía không có gì
        if word:
            return (" " if left and (left.isalnum() or left in "%)]”’") else "") + word + (" " if right and (right.isalnum() or right in "$([“‘") else "")
        return " " if left.isalnum() and right.isalnum() else ""
    token = ARROW_FORWARD.sub(lambda match: replace(match, says(match)), token)
    return ARROW_BACK.sub(lambda match: replace(match, ""), token)


def _arrows(out: list[str], toks: list[str] | None = None) -> None:
    """Mũi tên chữ: "1780 --> 1940", "A -> B", "=>", "→" là "thành" hay "đến" tuỳ chỗ (`_arrow_says`; sea-g2p đọc "sang" / "đến" / "suy ra"); mũi tên ngược "<-", "←" không có lời để đọc thì bỏ;
    mũi tên đứng đầu đoạn hay đầu câu là dấu đầu mục, cũng bỏ. Chữ xung quanh lấy từ `toks` (chữ hiện, chưa đổi sang cách đọc: "HP" chứ không phải "hát pê") khi có."""
    plain = toks if toks is not None and len(toks) == len(out) else out
    for index, token in enumerate(out):
        if not any(char in token for char in "<>=→⇒➜➡➔⟶⟹←⇐⟵⟸"):
            continue
        before = out[index - 1].rstrip(CLOSERS) if index else ""
        out[index] = _arrow(token, not before or before[-1] in SENTENCE_END, lambda match: _arrow_says(plain, index, token, match), index + 1 == len(out))


def _angle(out: list[str]) -> None:
    """<Tên kỹ năng> -> Tên kỹ năng (sea-g2p đọc "nhỏ hơn ... lớn hơn"): bỏ ngoặc nhọn bao chữ, cụm từ hai chữ trở lên thêm dấu phẩy hai bên để ngắt.
    "<" chỉ là ngoặc khi liền một chữ cái và có ">" đóng trong ANGLE_REACH chữ; "3 < 5", "<3", ">:)" để nguyên."""
    index = 0
    while index < len(out):
        body = out[index].lstrip(OPENERS)
        start = len(out[index]) - len(body)
        nxt = out[index + 1].lstrip(OPENERS) if index + 1 < len(out) else ""
        run = len(body) - len(body.lstrip(ANGLE_OPEN)) if body else 0
        inner = body[run:]  # "<<Ray Hawk>>" cũng là ngoặc: chữ sau dấu mở
        bracket = inner[:1].isalpha() or (inner[:1] in "\"“'‘" and inner[1:2].isalpha()) or (not inner and nxt[:1].isalpha()) or (inner[:1].isdigit() and ">" in inner[1:])  # "<50/50>": số trong ngoặc phải đóng ngay trong chữ này ("<3" là trái tim)
        before = out[index - 1].strip(OPENERS + PUNCT_MARKS + CLOSERS) if index else ""
        compare = body == "<" and all(len(word) == 1 or word.isdigit() for word in (before, nxt.strip(PUNCT_MARKS + CLOSERS)) if word) and bool(before) and bool(nxt)  # "a < b", "x < 10": so sánh, không phải ngoặc
        if not body or body[0] not in ANGLE_OPEN or (body[0] == "<" and (not bracket or compare)):
            index += 1
            continue
        end = None
        for last in range(index, min(len(out), index + ANGLE_REACH)):
            text = out[last]
            for at in range(start + run if last == index else 0, len(text)):
                if text[at] in ANGLE_CLOSE and not (text[at] == ">" and at and text[at - 1] in "-="):
                    end = (last, at)
                    break
            if end:
                break
        if end is None:
            if body[0] == "<" and (inner[:1].isalpha() or nxt[:1].isupper()):  # "< Thật Tuyệt vời" không có ngoặc đóng: dấu mở chỉ là trang trí
                out[index] = out[index][:start] + out[index][start + run:]
            index += 1
            continue
        last, at = end
        size = len(out[last][at:]) - len(out[last][at:].lstrip(ANGLE_CLOSE))
        head, rest = out[last][:at], out[last][at + size:]  # rest: phần còn lại của chữ sau ngoặc đóng ("Star〉[Cầu" -> "[Cầu")
        out[last] = head + (" " if head[-1:].isalnum() and rest[:1].isalnum() else "") + rest  # hai chữ dính hai bên ngoặc ("《Water》x1000") được tách
        out[index] = out[index][:start] + out[index][start + run:]
        if last > index:  # tên nhiều chữ: dấu phẩy trước và sau để ngắt
            if head[-1:].isalnum() and rest[:1] not in tuple(PUNCT_MARKS) and (rest.lstrip(CLOSERS) or last + 1 < len(out)):
                out[last] = head + "," + rest
            core = out[index - 1].rstrip(CLOSERS) if index else ""
            if core and core[-1].isalnum():
                out[index - 1] = core + "," + out[index - 1][len(core):]
        index = last + 1


def _range(match: re.Match, mode: str = "") -> str:
    parts = [match.group(1)] + match.group(2).split("-")[1:]
    if len(parts) == 2:
        first, second = parts
        if mode == "duel" and first == second == "1":
            return "1 chọi 1"  # "đấu 1-1": một chọi một
        if mode == "join":
            return f"{first} {second}"  # "lớp 1-7", "tỉ lệ 3-7": mã / tỉ số, không phải khoảng
        if int(first) < int(second):
            return f"{first} đến {second}"  # sea-g2p bỏ mất "đến" ở "3-4000"
        return f"{first} {second}" if first == second or (len(first) == 1 and len(second) == 1) else match.group()  # "1-1" (lớp), "3-1" (tỉ số): hai số liền
    if all(len(part) <= 2 and not part.startswith("0") for part in parts):
        return " ".join(parts)  # "1-3-1": dãy số, không phải khoảng
    return match.group()  # ngày "01-10-2026", điện thoại "090-123-4567"


def _range_mode(plain: list[str], index: int) -> str:
    """Chữ đứng trước một dãy "a-b" nói nó là khoảng ("" -> "đến"), mã / tỉ số ("join": hai số liền), hay trận đấu ("duel")."""
    before: list[str] = []
    for word in plain[max(0, index - 8):index][::-1]:
        if word.rstrip(CLOSERS)[-1:] in tuple(SENTENCE_END):
            break
        before.append(symbols.core(word).lower())
    if set(before[:1]) & RANGE_CODES or set(before) & RANGE_RATIO or (not before and plain[index].endswith(".")):
        return "join"
    return "duel" if set(before[:3]) & symbols.DUEL_WORDS else ""


def _numbers(out: list[str], toks: list[str] | None = None) -> None:
    """Số mà sea-g2p đọc chưa đúng ý người nghe: "3-4000" là "ba đến bốn nghìn", "1-1" / "1-3-1" là các số liền ("lớp 1-7", "tỉ lệ 3-7" cũng liền, "đấu 1-1" là "một chọi một"). Phân số, "x2", "$5"
    nằm ở `symbols`."""
    plain = toks if toks is not None and len(toks) == len(out) else out
    for index, token in enumerate(out):
        if not any(char.isdigit() for char in token):
            continue
        mode = _range_mode(plain, index) if RANGE.search(token) else ""
        out[index] = RANGE.sub(lambda match: _range(match, mode), token)


def _emoticons(out: list[str]) -> None:
    """Mặt cười chữ (":3", ":))", ">:)", "<3", "-_-", "orz") không đọc được: bỏ, giữ dấu câu theo sau ("nào >:)!" -> "nào !")."""
    for index, token in enumerate(out):
        body = token.rstrip("!?.,\"”’…")
        if body and EMOTICON.fullmatch(body.lstrip("\"“‘")):
            out[index] = token[len(body):]


def stutter_sound(frag: str, rest: str) -> str:
    """Tiếng nói lắp của `frag` ở đầu `rest` ("C" trước "chuyện" -> "chờ", "T" trước "tôi" -> "tờ"): phụ âm đầu của chữ sau + "ờ"; nguyên âm đứng riêng ("E" trước "em") thì chính nó. Phụ âm đầu
    ghép (kh, ch, ng...) lấy từ chữ sau khi chữ lắp là phần đầu của nó."""
    lowered, word = frag.lower(), unicodedata.normalize("NFC", rest).lower()
    if unicodedata.normalize("NFD", lowered)[0] in "aeiouy":
        return lowered
    onset = next((o for o in STUTTER_ONSETS if o.startswith(lowered) and word.startswith(o)), lowered)
    return STUTTER_SOUND.get(onset, onset) + "ờ"


def _stars(out: list[str]) -> None:
    """"*" là trang trí / nhấn ("*từ*", "(*)", "*Kà-ran*"): bỏ. Chữ cái đứng trước dấu kiểm duyệt ("đ*") đọc như nói lắp ("đờ…")."""
    for index, token in enumerate(out):
        if "*" not in token:
            continue
        censored = re.fullmatch(r"([^\w]*)([^\W\d_])\*+([^\w]*)", token)
        out[index] = censored.group(1) + stutter_sound(censored.group(2), censored.group(2)) + "…" + censored.group(3) if censored else token.replace("*", "")


def _stutters(toks: list[str], out: list[str], origin: str | None, speaks_english: bool) -> None:
    """Nói lắp "T-tôi", "C-Chuyện", "Ng-ngài", "E-em", "[Kh- Không": phần lắp đọc bằng âm ("tờ… tôi", "chờ… chuyện", "e… em") thay vì tên chữ cái; phần còn lại của chữ đọc như bình thường
    (nên "T-Tsukinoki-senpai" vẫn qua luật tên). Chỉ khi phần lắp là phần đầu của chữ sau và không phải một âm tiết đầy đủ ("Hà-Hà")."""
    for index, token in enumerate(toks):
        match = STUTTER.fullmatch(token)
        alone = match is None
        tail = ""
        if match:
            rest = match.group(3)
        else:
            match = STUTTER_ALONE.fullmatch(token)  # "Kh-" rồi chữ sau ở token kế
            if match is None or index + 1 >= len(toks):
                continue
            rest, tail = toks[index + 1].lstrip(OPENERS), match.group(3)
        before, frag = match.group(1), match.group(2)
        if not unicodedata.normalize("NFC", rest).lower().startswith(frag.lower()):
            continue
        if len(frag) > 1 and any(char in "aeiouy" for char in unicodedata.normalize("NFD", frag.lower())):  # đã là một âm tiết: "Hà-Hà"
            continue
        sound = stutter_sound(frag, rest)
        if alone:
            out[index] = before + sound + ("" if tail.lstrip(CLOSERS)[:1] in tuple(PUNCT_MARKS) else "…") + tail
        else:
            out[index] = before + sound + "… " + spoken_tokens([rest], origin, speaks_english)[0]


def _fullwidth(out: list[str]) -> None:
    """Dấu câu CJK ("đi，nhà ta", "734：Chúng ta") thành dấu thường; dính liền chữ sau thì thêm một khoảng trắng."""
    for index, token in enumerate(out):
        if not any(char in FULLWIDTH for char in token):
            continue
        said = []
        for at, char in enumerate(token):
            said.append(FULLWIDTH.get(char, char))
            if char in FULLWIDTH and token[at + 1:at + 2].isalnum():
                said.append(" ")
        out[index] = "".join(said)


def _dashes(out: list[str]) -> None:
    """Gạch ngang dính liền chữ ("Babi—người", "nên— Cảm ơn") là một chỗ ngắt; sea-g2p chỉ ngắt khi gạch cách chữ hai bên nên ở đây mất nhịp: đổi thành dấu phẩy."""
    for index, token in enumerate(out):
        if not any(char in token for char in DASHES):
            continue
        said: list[str] = []
        at = 0
        while at < len(token):
            end = at
            while end < len(token) and token[end] in DASHES:
                end += 1
            if end == at:
                said.append(token[at])
                at += 1
                continue
            after = token[end:end + 1]
            if at and token[at - 1].isalnum() and after.isalnum():
                said.append(", ")
            elif at and token[at - 1].isalnum() and not after and index + 1 < len(out):
                said.append(",")
            else:
                said.append(token[at:end])
            at = end
        out[index] = "".join(said)


def _frames(out: list[str]) -> None:
    """【Tên kỹ năng】, [Thông báo], 〔..〕 dính liền chữ ("là【Song Kiếm Thuật】rất", hay đứng sát chữ ở token kề) thêm dấu phẩy ở chỗ khung mở và đóng (nhịp ngắt hai đầu, như dấu ngoặc đơn);
    khung chỉ chứa số ("[1]") là chỉ số chú thích: để nguyên."""
    quotes = "\"'“‘«("
    for index in range(len(out)):
        token = out[index]
        if not any(char in token for char in SYSTEM_OPEN + SYSTEM_CLOSE) or token.strip(SYSTEM_OPEN + SYSTEM_CLOSE + quotes + CLOSERS + PUNCT_MARKS).isdigit():
            continue
        said: list[str] = []
        for at, char in enumerate(token):
            if char in SYSTEM_OPEN and at and token[at - 1].isalnum():
                said.append(",")
            said.append(char)
            if char in SYSTEM_CLOSE and at + 1 < len(token) and token[at + 1].isalnum():
                said.append(",")
        token = "".join(said)
        if token.lstrip(quotes)[:1] in SYSTEM_OPEN and index:  # khung mở ở đầu chữ: dấu phẩy gắn vào chữ trước
            core = out[index - 1].rstrip(CLOSERS.replace("]", ""))
            if core[-1:].isalnum():
                out[index - 1] = core + "," + out[index - 1][len(core):]
        core = token.rstrip("\"'”’»)")
        if core[-1:] in SYSTEM_CLOSE and index + 1 < len(out) and out[index + 1].lstrip(quotes.replace("(", "") + "【〔[{")[:1].isalnum():
            token = core + "," + token[len(core):]
        out[index] = token


def reading_marks(out: list[str], toks: list[str] | None = None) -> None:
    """Dấu câu / ký hiệu mà sea-g2p đọc sai thành lời (nó đọc "~" là "khoảng", "500,000" là "năm trăm"): sửa tại chỗ, số chữ không đổi. `toks` là chữ hiện tương ứng với `out` (cho `_arrows` xét ngữ cảnh)."""
    _fullwidth(out)
    symbols.prepare(out)
    _emoticons(out)
    _arrows(out, toks)
    _tildes(out)
    for index, token in enumerate(out):
        out[index] = THOUSANDS.sub(lambda match: match.group().replace(",", ""), token)
    _numbers(out, toks)
    _angle(out)
    symbols.read_symbols(toks, out)
    _dashes(out)
    _frames(out)
    _stars(out)
    for index, token in enumerate(out):  # 《》〈〉 còn sót (không có cặp) cũng chỉ là khung; hai chữ dính hai bên khung được tách ("có《Cỏ sạch》là")
        out[index] = re.sub("[" + ANGLE_OPEN[1:] + ANGLE_CLOSE[1:] + "]+", lambda match: " " if match.start() and token[match.start() - 1].isalnum() and token[match.end():][:1].isalnum() else "", token)


def spoken_tokens(toks: list[str], origin: str | None = None, speaks_english: bool = True) -> list[str]:
    """Chữ hiện -> chữ đem đọc (biến đổi để đọc, chữ hiện không đổi): số La Mã HOA hợp lệ (I..XXXIX) đứng riêng sau một từ ("Phổ thông II",
    "Chương IV", "Thế chiến II") hay làm đề mục đầu đoạn ("I. Mở đầu") thì đọc thành số tiếng Việt - bộ chuẩn hoá của sea-g2p chỉ biết
    "Benedict III", còn "thông II" nó đọc "i i". Số MỘT chữ (I, V, X) chỉ khi từ trước đánh số được (`numbered_by`): "ông X", "tia X", "điểm V" là chữ cái.
    Giữ nguyên "I am" đầu câu, chữ "I" sau dấu câu và không biến viết tắt (CV, MC, VIP) thành số. Cuốn có gốc Nhật / Hàn (`origin` "ja" / "ko", `names.book_origin`) thì tên
    romaji / RR đọc theo luật phiên âm ("Haruto" -> "Ha-ru-tô"; `names.spoken_names`), từ tiếng Anh thật vẫn để sea-g2p đọc - trừ giọng không nói được âm Anh (`speaks_english` False: Supertonic) thì
    từ / tên Anh được Việt hoá thành âm tiết ("Rose" -> "Râu-dơ"). Với MỌI cuốn và giọng: thán từ kéo dài ("Aaaa" -> "a… a", `shouts`), viết tắt toàn hoa đọc tên chữ cái
    ("HP" -> "hát pê", `abbreviations`), hậu tố gọi nối gạch ("Ariel-sama" -> "Ariel-xa-ma", `names.honorific_reading`). Sau cùng `reading_marks`
    sửa "~", nghìn kiểu Anh, <ngoặc nhọn>, " / "."""
    out = list(toks)
    _stutters(toks, out, origin, speaks_english)
    shouts.read_shouts(toks, out)
    _read_words(toks, out, origin, speaks_english)
    reading_marks(out, toks)
    return out


def _roman_numbers(toks: list[str], out: list[str]) -> None:
    """Số La Mã đứng đúng chỗ thành số tiếng Việt, tại chỗ trong `out` - xem `spoken_tokens`."""
    for index, token in enumerate(toks):
        core = token.lstrip(OPENERS + FRAMES_OPEN).rstrip(CLOSERS + FRAMES_CLOSE + ".,;:!?…")
        value = roman_value(core)
        if value is None:
            continue
        if index == 0:  # đề mục "I. Mở đầu": số có dấu chấm / ngoặc ngay sau và còn chữ theo sau
            if len(toks) < 2 or token.lstrip(OPENERS)[len(core):] not in (".", ")"):
                continue
        else:  # sau một từ có chữ thường, không dính dấu câu (sau dấu câu là chữ "I" của câu mới); hay nối tiếp số La Mã vừa đọc ("Mục II, III")
            before = toks[index - 1].lstrip(OPENERS).rstrip(CLOSERS)
            if out[index - 1] == toks[index - 1]:
                if not (before.isalpha() and any(c.islower() for c in before)) or (len(core) == 1 and not numbered_by(toks, index)):
                    continue
        out[index] = token.replace(core, vietnamese_number(value), 1)


def _read_words(toks: list[str], out: list[str], origin: str | None, speaks_english: bool) -> None:
    """Các bước đọc từng chữ (cấp độ, viết tắt, tên, từ mượn). Chữ dính liền hai từ qua "…" hay "—" ("rồi…Senpai", "Babi—người", "DP?”…Tốn") được tách tạm thành từng mảnh để mỗi từ được xét riêng
    rồi ghép lại; chữ đã bị đổi ở bước trước giữ nguyên."""
    pieces: list[str] = []
    said: list[str] = []
    owner: list[int] = []
    for index, token in enumerate(toks):
        parts = GLUED.split(token) if out[index] == token else [token]
        for part in parts:
            pieces.append(part)
            said.append(part if out[index] == token else out[index])
            owner.append(index)
            if out[index] != token:
                break
    _roman_numbers(pieces, said)
    abbreviations.read_levels(pieces, said, speaks_english)
    abbreviations.read_titles(pieces, said, speaks_english)
    abbreviations.read_shouted_honorifics(pieces, said, origin)
    abbreviations.spell_abbreviations(pieces, said)
    names.spoken_names(pieces, origin, speaks_english, said)
    rebuilt = [""] * len(toks)
    for part, reading, index in zip(pieces, said, owner):
        rebuilt[index] += reading
    out[:] = rebuilt


def _ends(token: str, marks: str) -> bool:
    core = token.rstrip(CLOSERS)
    return bool(core) and core[-1] in marks


def _groups(toks: list[str], first: int, last: int, marks: str) -> list[tuple[int, int]]:
    out, start = [], first
    for index in range(first, last + 1):
        if _ends(toks[index], marks) or index == last:
            out.append((start, index))
            start = index + 1
    return out


def _length(toks: list[str], first: int, last: int) -> int:
    return sum(len(token) for token in toks[first:last + 1]) + (last - first)


def _pack(toks: list[str], spans: list[tuple[int, int]], max_chars: int) -> list[tuple[int, int]]:
    """Gộp các khoảng liền nhau thành khoảng dài nhất không quá `max_chars` ký tự."""
    out: list[tuple[int, int]] = []
    for first, last in spans:
        if out and _length(toks, out[-1][0], last) <= max_chars:
            out[-1] = (out[-1][0], last)
        else:
            out.append((first, last))
    return out


def units(text: str, max_chars: int, origin: str | None = None, speaks_english: bool = True) -> tuple[list[str], list[Unit]]:
    """Chữ hiện của đoạn + các khúc đem đọc (mọi chữ hiện thuộc đúng một khúc, theo thứ tự). `origin`: gốc của cuốn ("ja" / "ko"), `speaks_english`:
    giọng nói được âm Anh không - xem `spoken_tokens`."""
    from ..webui.word_timing import tokens

    toks = tokens(text)
    if not toks:
        return toks, []
    said = spoken_tokens(toks, origin, speaks_english)
    pieces: list[tuple[int, int]] = []
    for first, last in _groups(toks, 0, len(toks) - 1, SENTENCE_END):
        if _length(toks, first, last) <= max_chars:
            pieces.append((first, last))
            continue
        for p_first, p_last in _pack(toks, _groups(toks, first, last, PHRASE_END), max_chars):  # câu dài: cắt ở dấu phẩy, rồi ở khoảng trắng
            if _length(toks, p_first, p_last) <= max_chars:
                pieces.append((p_first, p_last))
            else:
                pieces += _pack(toks, [(i, i) for i in range(p_first, p_last + 1)], max_chars)
    result: list[Unit] = []
    for first, last in pieces:  # gói câu vào khúc như vieneu (pack_sentences_into_chunks)
        if result and _length(toks, result[-1].first, last) <= max_chars:
            result[-1].last = last
            result[-1].pieces.append(" ".join(word for word in said[first:last + 1] if word))
        else:
            result.append(Unit(first, last, [" ".join(word for word in said[first:last + 1] if word)]))
    while len(result) > 1:  # khúc quá ngắn gộp vào khúc kề ngắn hơn (bằng nhau: khúc sau)
        short = [i for i, unit in enumerate(result) if _length(toks, unit.first, unit.last) < MIN_UNIT_CHARS]
        if not short:
            break
        i = min(short, key=lambda k: _length(toks, result[k].first, result[k].last))
        right = i + 1 < len(result)
        if right and i > 0:
            right = _length(toks, result[i + 1].first, result[i + 1].last) <= _length(toks, result[i - 1].first, result[i - 1].last)
        a, b = (i, i + 1) if right else (i - 1, i)
        result[a] = Unit(result[a].first, result[b].last, result[a].pieces + result[b].pieces)
        del result[b]
    return toks, result


def resample(wave_data: Any, rate: int, target: int = ALIGN_RATE) -> Any:
    """Đổi tần số mẫu bằng FFT (cắt phổ = lọc thông thấp lý tưởng) - đủ cho bộ căn chữ 16 kHz."""
    import numpy as np

    data = np.asarray(wave_data, dtype=np.float32)
    if rate == target or data.size == 0:
        return data
    count = max(1, int(round(data.size * target / rate)))
    spectrum = np.fft.rfft(data)
    keep = count // 2 + 1
    trimmed = np.zeros(keep, dtype=spectrum.dtype)
    trimmed[:min(keep, spectrum.size)] = spectrum[:min(keep, spectrum.size)]
    return (np.fft.irfft(trimmed, count) * (count / data.size)).astype(np.float32)


def wav_bytes(samples: Any, rate: int) -> bytes:
    import numpy as np

    pcm = (np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0) * 32767.0).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm.tobytes())
    return buffer.getvalue()


def timed_synthesis(audio: Any, rate: int, toks: list[str], parts: list[Unit], spans: list[tuple[int, int]], aligner: Any) -> Synthesis:
    """Clip WAV của cả đoạn + mốc từng chữ hiện: mỗi khúc `parts` đã biết chỗ của nó (`spans`, theo mẫu), chữ của khúc ấy được căn vào audio
    của riêng nó. Dùng chung cho mọi giọng chạy trên máy (VieNeu, Supertonic)."""
    from ..webui import word_timing

    duration = len(audio) * 1000 // rate
    words: list[list[int]] = []
    for unit, (start, stop) in zip(parts, spans):
        if stop <= start:  # khúc không ra tiếng: các chữ đứng ở chỗ khúc ấy
            words += [[start * 1000 // rate, start * 1000 // rate] for _ in range(unit.last - unit.first + 1)]
            continue
        found, _how, _confidence = word_timing.line_words(resample(audio[start:stop], rate), unit.text(toks), start / rate, aligner)
        words += found
    previous = 0
    for pair in words:  # không lùi, không quá cuối clip
        pair[0] = min(max(pair[0], previous), duration)
        pair[1] = min(max(pair[1], pair[0]), duration)
        previous = pair[0]
    return Synthesis(wav_bytes(audio, rate), [], duration, "wav", "audio/wav", words=words)


def reading_tag(text: str, origin: str | None, speaks_english: bool = True) -> str:
    """Khác "" khi cách đọc tên / từ Anh làm đoạn này nghe khác `spoken_tokens(toks)` trần: khoá bộ đệm clip phải có nó, không thì clip cũ (đọc tên bằng âm Anh)
    bị dùng lại sau khi cuốn đổi gốc hay giọng đổi cách đọc. "ja" / "ko" = tên đọc theo luật phiên âm; "en<số>" = từ Anh được Việt hoá (`names.ENGLISH_READING`),
    nối bằng "+". Đoạn không có gì đổi thì "" - clip cũ vẫn dùng được. Dùng chung cho mọi giọng đọc tên (VieNeu, Supertonic)."""
    from ..webui.word_timing import tokens

    toks = tokens(text)
    plain = spoken_tokens(toks)
    named = spoken_tokens(toks, origin) if origin in names.ORIGINS else plain
    tags = [origin] if named != plain else []
    if not speaks_english and spoken_tokens(toks, origin, False) != named:
        tags.append(f"en{names.ENGLISH_READING}")
    return "+".join(tags)


def seed_of(*parts: str) -> int:
    """Hạt giống cố định theo giọng + chữ: cùng đoạn cùng giọng luôn ra cùng audio (bộ đệm, đọc lại)."""
    return int(hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:8], 16)


class VieneuProvider:
    """`locate()`: nơi mô-đun đặt các phần (None = chưa tải gì). `engines`: bộ dựng engine theo tầng (bài thử thay bằng engine giả)."""

    id = PREFIX
    speaks_english = True  # sea-g2p cho âm vị Anh: chữ Anh để nguyên (đo 04-10)

    def __init__(self, locate: Callable[[], Installed | None], *, engines: Callable[[str, Installed], Any] | None = None,
                 aligner: Callable[[], Any] | None = None) -> None:
        self.locate = locate
        self._make = engines or _real_engine
        self._aligner = aligner or _real_aligner
        self._lock = threading.Lock()
        self._engine_lock = threading.Lock()  # nạp engine mất vài giây: danh sách giọng không phải chờ
        self._engines: dict[tuple[str, str], Any] = {}
        self._presets: dict[tuple[str, str, float], dict[str, dict[str, Any]]] = {}

    # ---- giọng ------------------------------------------------------------------------------------------------------------------
    def _tiers(self, installed: Installed | None) -> list[str]:
        if installed is None:
            return []
        return [tier for tier in TIERS if getattr(installed, tier) is not None and (installed.voices / VOICE_FILES[tier]).is_file()]

    def presets(self, tier: str, installed: Installed) -> dict[str, dict[str, Any]]:
        """Giọng có sẵn của một tầng, theo thứ tự hiện (Turbo: giọng chọn lọc trước theo `featured`, rồi theo file), đọc một lần cho mỗi file."""
        path = installed.voices / VOICE_FILES[tier]
        try:
            stamp = path.stat().st_mtime
        except OSError:
            return {}
        key = (tier, str(path), stamp)
        with self._lock:
            hit = self._presets.get(key)
            if hit is None:
                data = json.loads(path.read_bytes().decode("utf-8")).get("presets") or {}
                order = sorted(enumerate(data.items()), key=lambda item: (item[1][1].get("featured") is None,
                                                                          item[1][1].get("featured") or 0, item[0]))
                hit = {name: value for _, (name, value) in order}
                self._presets = {k: v for k, v in self._presets.items() if k[:2] != key[:2]}
                self._presets[key] = hit
            return hit

    def voices(self) -> list[Voice]:
        installed = self.locate()
        out: list[Voice] = []
        for tier in self._tiers(installed):
            assert installed is not None
            for name, preset in self.presets(tier, installed).items():
                gender = str(preset.get("gender") or "")  # danh sách giọng ghi sẵn nam / nữ (bản Kotlin: VieneuPreset.gender)
                out.append(Voice(f"{PREFIX}:{tier}/{name}", f"{name} ({TIER_LABEL[tier]})", PREFIX, False,
                                 gender=gender if gender in ("female", "male") else ""))
        return out

    # ---- engine -----------------------------------------------------------------------------------------------------------------
    def engine(self, tier: str, installed: Installed) -> Any:
        where = str(installed.turbo if tier == "turbo" else installed.nano)
        with self._engine_lock:
            hit = self._engines.get((tier, where))
            if hit is None:
                try:
                    hit = self._make(tier, installed)
                except (OSError, ValueError, KeyError, ImportError) as error:
                    raise VoiceError(f"Giọng VieNeu chưa sẵn sàng ({error}) - hãy tải lại Giọng VieNeu trong Cài đặt.", "voice") from error
                self._engines = {k: v for k, v in self._engines.items() if k[0] != tier}
                self._engines[(tier, where)] = hit
            return hit

    def forget(self) -> None:
        """Mô-đun vừa cập nhật: nạp lại engine và danh sách giọng ở lần dùng sau."""
        with self._engine_lock:
            self._engines.clear()
        with self._lock:
            self._presets.clear()

    def _voice(self, native: str) -> tuple[str, str, Installed, dict[str, Any]]:
        tier, _, name = native.partition("/")
        installed = self.locate()
        if tier not in self._tiers(installed):
            raise VoiceError("Giọng VieNeu này chưa tải trên máy.", "voice")
        assert installed is not None
        preset = self.presets(tier, installed).get(name)
        if preset is None:
            raise VoiceError("Không có giọng VieNeu này.", "voice")
        return tier, name, installed, preset

    def _speak(self, tier: str, name: str, installed: Installed, preset: dict[str, Any], text: str,
               origin: str | None = None) -> tuple[Any, int, list[str], list[Unit], list[tuple[int, int]]]:
        """Đọc cả đoạn: (sóng âm, tần số mẫu, chữ hiện, các khúc, [đầu, cuối) của từng khúc theo mẫu). `origin`: gốc của cuốn, xem `spoken_tokens`."""
        import numpy as np

        from . import vieneu_engine as ve

        engine = self.engine(tier, installed)
        toks, parts = units(text, MAX_CHARS[tier], origin, self.speaks_english)
        speaker = np.asarray(preset["speaker_emb"], dtype=np.float32)
        waves, pauses = [], []
        for unit in parts:
            phonemes = ve.phonemize(unit.pieces)
            seed = seed_of(tier, name, " ".join(unit.pieces))
            if not phonemes:
                audio = np.zeros(0, dtype=np.float32)
            elif tier == "turbo":
                codes = ve.strip_encoder_pad_frame(np.asarray(preset["codes"], dtype=np.int64)) if preset.get("codes") is not None else None
                audio = engine.infer(phonemes, speaker, codes, rng=np.random.RandomState(seed))
            else:
                audio = engine.infer(phonemes, speaker, np.asarray(preset["style"], dtype=np.float32), seed=seed)
            waves.append(audio)
            pauses.append(ve.GAP_SECONDS["sentence" if phonemes.rstrip()[-1:] in ".!?" else "minor"])
        joined, spans = ve.join(waves, engine.SAMPLE_RATE, pauses[:-1])
        if not joined.size:
            raise VoiceError("Đoạn này không có chữ nào đọc được.", "empty")
        return joined, engine.SAMPLE_RATE, toks, parts, spans

    def reading_tag(self, text: str, origin: str | None) -> str:
        return reading_tag(text, origin, self.speaks_english)

    def synthesize(self, text: str, native_voice: str, origin: str | None = None) -> Synthesis:
        tier, name, installed, preset = self._voice(native_voice)
        audio, rate, toks, parts, spans = self._speak(tier, name, installed, preset, text, origin)
        return timed_synthesis(audio, rate, toks, parts, spans, self._aligner() if installed.aligner else None)

    def benchmark(self, tier: str) -> dict[str, Any]:
        """Tự đo vài giây sau khi tải: nạp engine, đọc một đoạn mẫu ngắn bằng giọng đầu tiên. RTF = giây máy làm / giây nghe được (dưới 1 là
        kịp nghe); `firstAudioMs` = thời gian làm cả đoạn mẫu (~5 giây nghe) - clip là cả đoạn, nên đoạn đầu chương phát được sau chừng ấy."""
        installed = self.locate()
        if tier not in self._tiers(installed):
            raise VoiceError("Giọng VieNeu này chưa tải trên máy.", "voice")
        assert installed is not None
        name, preset = next(iter(self.presets(tier, installed).items()))
        began = time.perf_counter()
        self.engine(tier, installed)
        self._speak(tier, name, installed, preset, "Xin chào.")  # lần chạy đầu của onnxruntime chậm hơn hẳn: không tính
        loaded = time.perf_counter()
        audio, rate, *_ = self._speak(tier, name, installed, preset, BENCH_TEXT)
        done = time.perf_counter()
        seconds = len(audio) / rate
        return {"rtf": round((done - loaded) / seconds, 3), "firstAudioMs": round((done - loaded) * 1000),
                "loadMs": round((loaded - began) * 1000), "audioSeconds": round(seconds, 2)}


def _real_engine(tier: str, installed: Installed) -> Any:
    from . import vieneu_engine as ve

    if tier == "turbo":
        assert installed.turbo is not None
        return ve.TurboEngine(installed.turbo[0], installed.turbo[1])
    assert installed.nano is not None
    return ve.NanoEngine(installed.nano)


def _real_aligner() -> Any:
    from ..webui import word_timing

    return word_timing.get_aligner()
