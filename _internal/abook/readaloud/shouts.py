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
import json
from pathlib import Path
from functools import lru_cache

from ..romanization import romanized_reading
from . import names
from .names import split_token

POLICY = json.loads(Path(__file__).with_name("sound_policy.json").read_text(encoding="utf-8"))
NOTE = re.compile(POLICY["note_pattern"], re.IGNORECASE)


def distinct_from_english(reading: str) -> str:
    """A generated syllable that spells an English word ("he", "hi", "I") is said in English by sea-g2p.

    Respell it as the same Vietnamese sound; `english_safe` readings were measured to stay Vietnamese.
    """
    return POLICY["english_collisions"].get(reading.casefold(), reading)


def presentation_tokens(toks: list[str]) -> tuple[list[str], list[int]]:
    """Split note anchors only in voice text; keep one owner per displayed token.

    Edge underscores are framing. Internal underscores remain identifiers.
    Other punctuation stays available to the existing structural rules.
    """
    prepared, owners = [], []
    for index, token in enumerate(toks):
        parts = NOTE.sub(" ", token).split() or [""]
        for part in parts:
            before, core, after = split_token(part)
            if core and not any(c.isalnum() for c in before + after):
                part = before.replace("_", "") + core + after.replace("_", "")
            prepared.append(part)
            owners.append(index)
    return prepared, owners


def honorific_stretch(core: str, origin: str | None) -> str | None:
    """Repeated suffix letters retain the established honorific route."""
    parts = re.split("[-‐‑‒–]", core)
    if len(parts) < 2:
        return None
    suffix = dedupe(parts[-1].lower())
    if suffix not in names.HONORIFICS or suffix == parts[-1].lower():
        return None
    canonical = "-".join(parts[:-1] + [suffix])
    from .japanese_policy import reading as japanese_reading

    reading = japanese_reading(canonical, origin) or names.honorific_reading(canonical, origin)
    return reading + "…" if reading else None


def _expanded_reading(core: str) -> str | None:
    """Phonotactic vocal patterns and bounded, readable repeated-letter forms."""
    word = core.lower()
    if not word.isascii() or not word.isalpha():
        return None
    if core.isupper() and (ROMAN_LETTERS.issuperset(word) or word in SHORT_CASED
                           or (len(set(word)) == 1 and word[0] not in VOWELS)):
        return None
    atoms = re.findall(POLICY["laugh_atom"], word) if re.fullmatch(POLICY["laugh_pattern"], word) else []
    # "FIFA", "Fifi", "Ahifa", "HIFI": a laugh in "f" is "fu" / "fw" ("Fufu", "Fuhaha", "Fwahaha"); a bare "fa", "fi", "fo" needs three beats ("Fahaha", "Fofofo")
    if atoms and (len(atoms) >= 3 or all(atom[0] == "h" or atom[1] in "uw" for atom in atoms)):
        sounds = []
        for atom in atoms:
            vowel = next(c for c in atom if c in POLICY["vowels"])
            sounds.append("phu" if atom[0] == "f" else POLICY["laugh_vowels"][vowel])
        # The opening vowel tells "Ehehe" from "Hehe"; it does not count toward the ceiling.
        lead = [POLICY["laugh_leads"][word[0]]] if word[0] in POLICY["laugh_leads"] else []
        return " ".join(lead + sounds[:POLICY["max_laugh_syllables"]])
    if re.fullmatch(POLICY["nasal_pattern"], word):
        return romanized_reading(dedupe(word), "ja")
    stretched = re.search(r"(.)\1{" + str(POLICY["min_run"] - 1) + r",}", word)
    base = re.sub(r"(.)\1{" + str(POLICY["min_run"] - 1) + r",}", r"\1", word)
    # Lexical words are not short cries merely because their letters fit a pattern.
    from ..analysis import is_vietnamese_syllable

    # "AK", "KO", "IG", "EK": two capitals are an abbreviation unless listed ("AH", "OH"); "EEG", "UGG": a doubled letter closed by "g" is one too ("EEK", "AHH", "EGGG" are cries)
    sound_case = not core.isupper() or (bool(re.search(r"(.)\1", word)) and (bool(stretched) or not word.endswith("g")))
    patterned = sound_case and word not in names.english_words() and not is_vietnamese_syllable(word) and not any(
        c not in POLICY["vowels"] + "hkgwy" for c in word)
    reading = None
    if re.fullmatch(POLICY["growl_pattern"], base) and stretched:
        reading = base[:-1]
    elif re.fullmatch(POLICY["hiss_pattern"], base) and stretched:
        reading = re.sub("[zs]+$", "", base) + "… xì"
    elif patterned and (re.fullmatch(POLICY["breath_pattern"], word)
                        or re.fullmatch(POLICY["palatal_pattern"], word)):
        plain = re.sub("[hkg]+$", "", base)
        reading = romanized_reading(plain, "ja") if plain else None
    elif stretched:
        # A proper name with one repeated final consonant remains uncertain.
        runs = _runs(list(word))
        if core.istitle() and len(runs) == 1 and runs[0][1] == len(word) and word[-1] not in POLICY["vowels"]:
            return None
        reading = base if is_vietnamese_syllable(base) else romanized_reading(base, "ja")
        if reading is None:
            reading = base if base in names.english_words() else None
    if not reading:
        return None
    reading = distinct_from_english(reading)
    if "…" in reading:
        return reading
    return reading + "…" if stretched else reading

INTERJECTIONS = {"umm": "ừm", "ugh": "ức", "boom": "bùm", "oh": "ô", "hmm": "hừm", "shh": "suỵt", "ah": "a", "eh": "ê", "hm": "hừm", "huh": "hả", "ooh": "ô",
                 "hic": "hích", "urgh": "ức", "um": "ừm", "uhm": "ừm", "uh": "ờ", "mm": "ừm",  # "Um", "Uh", "Mm" (sea-g2p đọc "mm" là "mi li mét")
                 "grr": "gừ", "pff": "phụt", "pfft": "phụt", "kkk": "khà khà", "hhh": "ha ha", "sss": "xì",
                 "hmph": "hừm", "hmpf": "hừm", "tsk": "chậc", "tch": "chậc"}  # chữ phụ âm lặp: "grrr", "pfffft", "kkkk", "hhhh", "ssss" ("mmm" là "mm" ở trên)
SHORT_CASED = frozenset(("um", "uhm", "uh", "mm"))  # chữ ngắn này viết HOA cả ("UH-60", "MM", "SSS") là viết tắt / hạng, không phải tiếng kêu
COUNT_WORDS = frozenset(("vài", "mấy", "mười"))  # ngoài `names.NUMBER_WORDS`: "vài mm"
PAIR_LETTERS = "hzm"  # chữ cuối lặp HAI lần cũng là kéo ("Ahh", "Haizz", "Hừmm"): ba lần thì mọi chữ, hai lần chỉ ba chữ này (Boss, Class, Jess là từ thật)
LAUGH_SYLLABLES = {"ha": "ha", "he": "hê", "hi": POLICY["laugh_vowels"]["i"], "ho": "hô", "fu": "phu"}  # tiếng cười lặp ("Haha" -> "ha ha", "Hehe" -> "hê hê", "fufu" -> "phu phu")
LAUGH = re.compile(r"(?:ha|he|hi|ho|fu){2,}", re.IGNORECASE)
TONE_MARKS = "\u0300\u0301\u0303\u0309\u0323"  # huyền, sắc, ngã, hỏi, nặng (còn lại là dấu mũ / móc / trăng: thuộc về chữ)
STANDALONE = frozenset("aeêioôơuư")  # nguyên âm đứng riêng được thành một âm tiết: chữ kéo là chữ này thì nhắc lại nó sau "…"
VOWELS = frozenset("aăâeêioôơuưy")
MIN_RUN = int(POLICY["min_run"])
ROMAN_LETTERS = frozenset("ivx")
RANK_NOUNS = frozenset(("hạng", "cấp", "rank", "class", "loại", "bậc"))  # "hạng AAA", "hạng SSS": chữ hạng, không phải tiếng kéo
CRY_MARK = re.compile(r"[!?！？…~～—–―─]|\.\.")  # dấu của tiếng kêu ngay sau chữ
CONSONANT_CRIES = frozenset(("mph", "tsk"))  # tiếng kêu không nguyên âm ngoài bảng thán từ, nhận cả khi viết HOA ("MMMMPH!", "TSSSK!")
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


def _basic_reading(core: str) -> str | None:
    """Cách đọc của `core` (chữ cái đầu tới cuối, không dấu câu) khi nó là thán từ Latin hay tiếng kêu kéo dài; None khi để nguyên."""
    from ..analysis import is_vietnamese_syllable

    chars = _letters(core)
    if not chars or (core.isupper() and ROMAN_LETTERS.issuperset(chars) and len(chars) >= MIN_RUN):  # "III", "XXX": số La Mã / chữ X, không phải tiếng kéo
        return None
    word = "".join(chars)
    if core.isupper() and (word in SHORT_CASED or (len(set(chars)) == 1 and _plain(chars[0]) not in VOWELS)):  # "UH-60", "MMM", "SSS": viết tắt, không phải tiếng kêu
        return None
    if word in INTERJECTIONS and not (word == "um" and core.islower()):  # "um" thường là chữ Việt ("xanh um tùm"); "Um" hoa là tiếng ừm
        return INTERJECTIONS[word]
    if LAUGH.fullmatch(word) and all(word[i:i + 2] == word[:2] for i in range(0, len(word), 2)):
        return " ".join(LAUGH_SYLLABLES[word[i:i + 2]] for i in range(0, min(len(word), 2 * POLICY["max_laugh_syllables"]), 2))
    runs = _runs(chars)
    pair = not runs and len(chars) >= 3 and chars[-1] == chars[-2] and chars[-1] in PAIR_LETTERS and (chars[-1] != "z" or [_plain(char) for char in chars[-4:-2]] == ["a", "i"])
    if pair:  # "Ahh", "Haizz", "Hừmm": chữ cuối lặp hai lần
        runs = [(len(chars) - 2, len(chars))]
    if len(runs) != 1:
        return _collapsed(chars, runs)
    start, end = runs[0]
    letter = _plain(chars[start])
    one = "".join(chars[:start] + [chars[start]] + chars[end:])  # chuỗi kéo gộp thành một chữ
    base = _DEDUPED.get(dedupe(one))
    append = base if base in ("a", "ô", "ê") else ""
    if base is None:
        ascii_word = one.isascii()
        if pair and chars[-1] == "m" and ascii_word:
            return None  # "Tamm", "Grimm", "Flamm" là tên; chỉ thán từ trong bảng hay "Hừmm", "Ưmm" (có dấu) mới là tiếng kéo
        japanese = romanized_reading(one, "ja") if ascii_word else None
        consonant = "".join(chars[:start] + chars[end:])
        if not japanese and ascii_word and letter == "h" and JAPANESE_CRY.search(consonant):
            japanese = romanized_reading(consonant, "ja")  # "Wahhh", "Uwahhh": chữ kéo là "h" thở ra
        if ascii_word and JAPANESE_CRY.search(one) and japanese:
            base = japanese
        elif is_vietnamese_syllable(one):
            base = one
        elif letter not in VOWELS and consonant and is_vietnamese_syllable(consonant):
            base = consonant  # "Haizzz" -> "hai": chữ kéo không thuộc âm tiết
        elif japanese:
            base = japanese
        else:
            trimmed = word.rstrip("h")
            return stretch_reading(trimmed) if letter in VOWELS and trimmed != word and len(trimmed) >= MIN_RUN else None  # "Haaah" -> "Haaa": "h" cuối là hơi thở
        if letter in STANDALONE:
            append = unicodedata.normalize("NFC", unicodedata.normalize("NFD", letter) + _tone(base))
    return f"{base}…" + (f" {names.lone_syllable(append)}" if append and letter in STANDALONE else "")


@lru_cache(maxsize=4096)
def stretch_reading(core: str) -> str | None:
    if core.isupper() and core.casefold() in listed_abbreviations():
        return None  # "CCCD", "CMND": a listed abbreviation is never a cry, whatever its letters
    reading = _basic_reading(core) or _expanded_reading(core)
    word = core.lower()
    if reading and not any(_plain(char) in VOWELS for char in word) and dedupe(word) not in _DEDUPED:
        if core.isupper() and dedupe(word) not in CONSONANT_CRIES:
            return None  # "SSSR" -> "sr", "PCCC" -> "pc": capitals with no vowel are a cry only when listed ("HMMM", "GRRR", "MMMMPH")
        if word in listed_abbreviations():
            return None  # "cccd": a listed abbreviation in small letters; "Mmmph", "Ssst", "drrr" stay sounds
    return reading


@lru_cache(maxsize=1)
def listed_abbreviations() -> frozenset[str]:
    """Every abbreviation the reading tables know (english_policy.json, abbreviations.py), lower-cased."""
    from . import abbreviations
    from .english_policy import POLICY as ENGLISH

    words = set(ENGLISH["vietnamese_abbreviations"]) | set(ENGLISH["spoken_abbreviations"]) | set(ENGLISH["contextual_abbreviations"])
    words |= {word.casefold() for word in ENGLISH["preserve_acronyms"] + ENGLISH["acronyms"] + ENGLISH["capital_codes"]}
    return frozenset(words | set(abbreviations.AS_WORDS) | abbreviations.SPELLED_ENGLISH | set(abbreviations.LEVEL_NAMES))


def _collapsed(chars: list[str], runs: list[tuple[int, int]]) -> str | None:
    """Chữ có NHIỀU chỗ kéo ("Cccchhhhàaaaaaoooo" -> "chào… ò"): gộp mỗi chỗ kéo thành một chữ (giữ dấu thanh ở chữ đầu của chỗ ấy); chỉ đọc khi gộp ra đúng một âm tiết tiếng Việt.
    Chỗ kéo cuối là nguyên âm đứng riêng thì nhắc lại nó một lần sau "…", mang thanh của âm tiết."""
    from ..analysis import is_vietnamese_syllable

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
    return f"{base}…" + (f" {names.lone_syllable(append)}" if append else "")


def _counted(word: str) -> bool:
    """Chữ đứng trước là số lượng ("127", "một", "vài"): chữ "mm" sau nó là đơn vị."""
    word = word.strip(CLOSING).lower()
    return word[-1:].isdigit() or word in names.NUMBER_WORDS or word in COUNT_WORDS


def _read_segment(segment: str, toks: list[str], index: int, first: bool, origin: str | None = None) -> str:
    """Đọc `segment` (token, hay phần token sau một chỗ dính liền) theo `read_shouts`; không phải tiếng kêu thì trả nguyên. Chữ đầu là tiếng kêu thì phần sau chỗ dính cũng được xét ("Um....Umm…")."""
    face = segment.strip(POLICY["frames"])
    if face.lower() in POLICY["emoticons"]:
        at = segment.index(face)
        return segment[:at] + POLICY["emoticons"][face.lower()] + segment[at + len(face):]
    glued = GLUE.search(segment, len(split_token(segment)[0]))
    head, rest = (segment[:glued.start()], segment[glued.start():]) if glued else (segment, "")
    before, core, after = split_token(head)
    previous = toks[index - 1] if first and index else ""
    if not core or any(char.isdigit() for char in before + after) or (core.isupper() and (after.startswith("+") or previous.lower().strip(CLOSING) in RANK_NOUNS)):
        return segment  # chữ dính số ("55mm", "ss1") không phải tiếng kêu
    if core.isupper() and core.isascii() and len(core) == MIN_RUN and len(set(core)) == 1 and not CRY_MARK.search(after + rest):
        return segment  # "Kỳ tích: AAA", "Kamen Rider OOO", "tài khoản YYY": ba chữ hoa giống nhau là hạng / tên / chỗ trống; có dấu kêu ("AAA!") mới là tiếng kêu
    reading = honorific_stretch(core, origin) or stretch_reading(core)
    if not reading or (core.lower() == "mm" and _counted(previous)):  # "127 mm", "vài mm" là mi-li-mét, "Mm…" là tiếng ừm
        return segment
    if rest:
        joint = GLUE.match(rest).end()
        rest = rest[:joint] + _read_segment(rest[joint:], toks, index, False, origin)
    rest = rest.lstrip("~") if reading.endswith("…") else rest
    if reading.endswith("…") and rest[:1] in ("…", "."):
        reading = reading[:-1]  # "…" đã có ngay sau chữ
    return before + reading + names.closing(after.replace("-", "") if "…" in reading else after, reading) + rest


def read_shouts(toks: list[str], out: list[str], origin: str | None = None) -> None:
    """Thay tại chỗ, trong `out`, token (chưa bị đổi so với `toks`) là thán từ / tiếng kêu kéo dài bằng cách đọc của nó, giữ dấu câu quanh (dấu "-" đuôi của
    "Xoạttt-" bỏ); số chữ không đổi. Chữ dính liền vào phần sau qua "…", "..", "~" hay "—" ("Ummm…Ý", "màaaa—nếu", "Um....Umm") thì mỗi phần được xét riêng. Chữ hoa cả là hạng
    ("hạng AAA", "AAA+++") thì để viết tắt đọc."""
    for index, token in enumerate(toks):
        if out[index] == token:
            out[index] = _read_segment(token, toks, index, True, origin)
