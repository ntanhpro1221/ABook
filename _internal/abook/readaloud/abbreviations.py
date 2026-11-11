"""Spoken abbreviations; displayed text is unchanged.

Owner readings and Vietnamese expansions come from english_policy.json, shared
with Kotlin. VN distinguishes prose from identifiers; AI also has pronoun guards.
Dictionary words in capitals are words. Short unresolved codes retain the letter
route; VieNeu's direct English policy selects English letter names for that route.
"""
from __future__ import annotations

import re

from ..romanization import romanized_reading
from . import names
from .names import english_words, split_token
from .english_policy import POLICY

LETTERS = {
    "a": "a", "b": "bê", "c": "xê", "d": "đê", "e": "e", "f": "ép", "g": "giê", "h": "hát", "i": "i", "j": "gi", "k": "ca", "l": "e-lờ", "m": "em",
    "n": "en", "o": "ô", "p": "pê", "q": "quy", "r": "e-rờ", "s": "ét", "t": "tê", "u": "u", "v": "vê", "w": "vê-kép", "x": "ích", "y": "i-dài", "z": "dét",
}
AS_WORDS = {"id": "ai-đi", **POLICY["spoken_abbreviations"]}
SPELLED_ENGLISH = frozenset("abc ceo cia dna exp fbi hiv ibm nba usa".split())  # có trong english_words.txt, có nguyên âm, nhưng là viết tắt
SHOUT_WORDS = frozenset("no oh ah eh uh um ha ho yo hi he we me my up so to of or on ya ye go do if in is an by at".split())  # từ Anh hai chữ gào lên
LAUGH = re.compile(r"(?:ha|he|hi|ho)+")  # "HAHA": tiếng cười, không phải viết tắt
ROMAN_LETTERS = frozenset("ivx")  # "IIII" nằm trong danh sách từ Anh nhưng không phải từ; "IIIII" đọc được như romaji
PAREN_ABBREVIATION = re.compile(r"(?<=.)\(([A-Z]{2,5})\)")  # "đó.”(GM)": viết tắt trong ngoặc dính vào chữ trước
LEVEL_NAMES = {"lv": "lờ vê", "lvl": "lờ vê lờ"}  # chủ sách 04-10: Lv không chắc là cấp độ thì đọc tên chữ cái, l = lờ, v = vê
from .shouts import POLICY as SOUND_POLICY

MIN_LETTERS, MAX_LETTERS = 2, int(SOUND_POLICY["max_acronym_letters"])
ROMAJI_FROM = 4  # từ bấy nhiêu chữ, đọc được bằng luật romaji ("BAKA", "SUGOI") thì là chữ Nhật viết hoa, không phải viết tắt
WORD_FROM = 3  # tên / từ hét viết hoa ("YUI!", "BUG!") ngắn nhất; hai chữ hoa luôn là viết tắt
_CAPITALS = re.compile(r"(?<![\w'’/@#&+])(?<!(?<!\.)\.)(?<!\w-)[A-Z]{%d,}(?![\w'’/@#&+])(?![-.]\w)" % WORD_FROM)  # chữ đứng riêng: không dính số, gạch nối tên, đường dẫn
_VOWEL = re.compile(r"[aeiou]|(?<=[^aeiouy])y")  # "y" sau phụ âm là nguyên âm ("MYTHS", "LYNX"); "YYDS" không có nguyên âm nào
_INTERJECTION = re.compile(r"[^aeiou]{0,2}[aeiou]+h")  # "WAH!?", "YAH!", "UOH!": thán từ kết bằng "h"
_STRETCH = re.compile(r"(.)\1{2,}")  # chữ kéo dài: "NORDDDDD", "WUTTTT"
_CRY_SHAPED = re.compile(r"(.)\1\1|[aeiouh]$")  # tiếng kêu: có chữ kéo dài ("AHHH", "KENGGG") hay kết bằng nguyên âm / "h"; "UKG", "EEG" là mã
_CRY = re.compile(r"[^\w()]*[!?]")  # dấu kêu ngay sau chữ: "YUI!", "YUI…!", "YUI~!?"; "(AOE)!" là chú giải
_ONSETS = frozenset("bl br by ch cl cr dr dw fl fr gh gl gr gw gy hy jh kh kl kn kr kw ky my ny ph pl pr py rh ry sc sh sk sl sm sn sp st sv sw th tr ts tw vl wh wr zh"
                    " chr sch scr shr spl spr str thr thw".split())
_CODAS = frozenset("bb ch ck ct dd ds ff ft gg gh gs ht ks ld lf lk ll lm lp ls lt mb mm mp ms nd ng nk nn ns nt ph pp ps pt rb rc rd rf rg rk rl rm rn rp rs rt sh sk sp ss st th ts tt tz wk wl wn ws xt zz"
                   " cks ght lls lms lts mph mps nch nds ngh ngs nks nth nts rch rds rgh rks rld rms rns rst rth rts sts tch".split())


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


def standard_reading(core: str, toks: list[str], index: int, before: str = "", after: str = "") -> str | None:
    """Owner readings shared with Kotlin; VN distinguishes prose from an identifier."""
    lower = core.casefold()
    if lower in POLICY["case_sensitive_abbreviations"] and not core.isupper():
        return None
    if pronoun_ai(toks, index):
        return None
    if contextual_letters(core, toks, index):
        return None
    contextual = POLICY["contextual_abbreviations"].get(lower)
    if contextual:
        previous = [split_token(t)[1].casefold() for t in toks[max(0, index - 2):index]]
        code = (any(w in POLICY["code_context"] for w in previous)
                or bool(re.search(r"[\w]$", before)) or bool(re.match(r"[-_/]?\d|[-_/][\w]", after)))
        return contextual["code" if code else "prose"]
    return POLICY["spoken_abbreviations"].get(lower) or POLICY["vietnamese_abbreviations"].get(lower)


def pronoun_ai(toks: list[str], index: int) -> bool:
    return (split_token(toks[index])[1] == "AI" and index + 1 < len(toks)
            and split_token(toks[index + 1])[1].casefold() in POLICY["pronoun_following"])


def contextual_letters(core: str, toks: list[str], index: int) -> bool:
    cues = POLICY["contextual_letter_names"].get(core.casefold(), [])
    return any(split_token(t)[1].casefold() in cues for t in toks[max(0, index - 3):index])


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
    if len(lower) > 5 and sum(ch in "aeiou" for ch in lower) >= 2:
        return None  # Long pronounceable capitals can be names or words.
    if len(lower) >= ROMAJI_FROM and romanized_reading(lower, "ja") is not None:
        return lower if len(lower) <= 5 else None
    return " ".join(LETTERS[ch] for ch in lower)


def _letters(lower: str) -> str:
    return " ".join(LETTERS[ch] for ch in lower)


def _word_shaped(lower: str) -> bool:
    """Chữ có dáng một từ đọc được ("kwang", "thud", "combo", "lyra"), không phải một mã ("crce", "ussr", "lmao", "oecd"): có nguyên âm, cụm phụ âm đầu / cuối là cụm quen."""
    first, *middle, last = re.split("[aeiouy]+", lower)
    if first == lower:
        return False
    return (len(first) < 2 or first in _ONSETS) and (len(last) < 2 or last in _CODAS) and all(len(run) <= 3 for run in middle)


def _capital_word(core: str) -> bool:
    """Chữ HOA cả đang bị đọc tên chữ cái mà CÓ THỂ là một tên / từ: từ ba chữ, có nguyên âm, không có trong bảng viết tắt nào, không phải âm tiết Việt (đã có đường riêng),
    không phải một chữ lặp ("AAA", "OOO": hạng hay tiếng kêu, `shouts` quyết)."""
    from ..analysis import is_vietnamese_syllable
    from .shouts import listed_abbreviations

    lower = core.lower()
    return (len(core) <= MAX_LETTERS and bool(_VOWEL.search(lower)) and len(set(lower)) > 1 and lower not in listed_abbreviations()
            and not ROMAN_LETTERS.issuperset(lower) and spelled(core) == _letters(lower) and not is_vietnamese_syllable(lower))


def _written_as_word(lower: str, origin: str | None) -> str | None:
    """Dạng viết của chữ HOA cả đọc được thành từ ("yui" -> "Yui", "norddddd" -> "Nord…"), None khi không đọc được. Không có bằng chứng trong cuốn: romaji trọn vẹn (cuốn gốc Nhật hay chưa rõ gốc: "yui", "aki"), từ Anh trong bộ từ vựng chung ("bug", "idol"), từ bốn chữ trở lên có dáng một từ
    ("kael", "kwang"), thán từ kết bằng "h" ("wah"), hay chữ có dáng tiếng kêu (`_CRY_SHAPED`) mà bộ đọc tiếng kêu nhận ở dạng viết hoa đầu ("Ahhh" -> "a…"; "Ukg" bị nó đọc "u" nên không tính)."""
    from . import shouts
    from .japanese_policy import lexical_guard, syllables

    word = lower.capitalize()
    short = _STRETCH.sub(r"\1", lower)
    if short != lower and len(short) >= WORD_FROM and _VOWEL.search(short) and (short in lexical_guard() or _word_shaped(short)):
        # "NORDDDDD!" là "Nord" kéo dài: viết "Nord…". Chữ mà bộ đọc tiếng kêu đã tự đọc ở dạng HOA ("YESSSS" -> "yes…", "MARYYYY" -> "mary…") thì để nó.
        cry = [lower.upper()]
        shouts.read_shouts(list(cry), cry, origin)
        if cry != [lower.upper()]:
            return None
        return short.capitalize() + ("…" if list(_STRETCH.finditer(lower))[-1].end() == len(lower) else "")
    if origin in (None, "ja") and syllables(lower) and romanized_reading(lower, "ja") is not None:
        return word
    if lower in lexical_guard() or (len(lower) >= 4 and _word_shaped(lower)) or _INTERJECTION.fullmatch(lower):
        return word
    if not _CRY_SHAPED.search(lower):
        return None
    cry = [word]
    shouts.read_shouts(list(cry), cry, origin)
    return word if cry != [word] else None


def _shouted_word(core: str) -> bool:
    """Chữ HOA cả bên cạnh là một từ đang gào: có dấu ("CÚT"), hay từ Anh / Nhật / tên từ bốn chữ ("LOVE", "MISAKI") - không phải một viết tắt khác ("STR, AGI")."""
    if not _caps(core):
        return False
    if not core.isascii():
        return True
    return core.isalpha() and len(core) >= 4 and spelled(core) != _letters(core.lower())


def proves_name(surface: str, said: str) -> bool:
    """A per-book reading that is only the capitals' own capitalized spelling ("KAEL": "Kael") is the book's proof that the capitals are a name, not a sound to say."""
    return surface.isascii() and surface.isupper() and said == surface.capitalize()


def capital_words(toks: list[str], origin: str | None = None, readings: dict | None = None) -> list[str] | None:
    """Tên / từ bị hét viết HOA cả ("YUI!", "KAEL!", "BUG!") viết lại ở dạng viết hoa đầu ("Yui!") để đọc như chính từ ấy ở chỗ khác của cuốn, không đọc tên chữ cái. None khi không có chữ nào.
    Có bằng chứng thì luôn đổi: cuốn chứng minh nó là tên (`readings` mang cách đọc là chính dạng viết hoa đầu, `japanese_policy.book_name_readings`) hay dạng viết hoa đầu đứng ngay trong đoạn này
    ("Yui chạy tới. YUI!"). Không bằng chứng: chỉ khi đọc được thành từ (`_written_as_word`) VÀ đang hét - dấu "!" / "?" ngay sau, hay đứng cạnh một từ viết hoa cả khác ("I LOVE YUI").
    Viết tắt trong bảng ("USA!", "AGI"), chữ không đọc được thành từ ("NPC!", "HP?") và hai chữ hoa giữ đường đọc tên chữ cái."""
    named: list[str] | None = None
    cores: list[str] | None = None
    for index, token in enumerate(toks):
        if not any("A" <= ch <= "Z" for ch in token):
            continue
        rewritten = token
        for match in reversed(list(_CAPITALS.finditer(token))):
            core = match.group()
            if not _capital_word(core):
                continue
            before, after = token[:match.start()], token[match.end():]
            if cores is None:
                cores = [split_token(other)[1] for other in toks]
            word = core.capitalize()
            proven = (readings is not None and readings.get(core) == word) or word in cores
            if not proven:
                word = _written_as_word(core.lower(), origin)
                if word is None:
                    continue
                cried = bool(_CRY.match(after)) and not before.endswith("(")
                beside = ((not before and index > 0 and _shouted_word(cores[index - 1]))
                          or (not after and index + 1 < len(toks) and _shouted_word(cores[index + 1])))
                if not (cried or beside):
                    continue
            rewritten = rewritten[:match.start()] + word + rewritten[match.end():]
        if rewritten != token:
            if named is None:
                named = list(toks)
            named[index] = rewritten
    return named


def read_levels(toks: list[str], out: list[str], speaks_english: bool = True) -> None:
    """"Lv" / "Lvl" / "LV" liền trước một số ("Lv 5", "Lv.5", "Lv5", "Lvl.10") là cấp độ: đọc như chữ "level" viết đủ - cách đọc Việt của bảng từ mượn (`names.LOANWORDS`: "le-vồ"), để "Lv 5" và "level 5" trong cùng cuốn nghe như nhau. Không đi với số thì không
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
            level = names.LOANWORDS.get("level") or ("level" if speaks_english else names.english_reading("level") or "level")
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
        if pronoun_ai(toks, index):
            continue
        if before[-1:].isdigit() or after[:1].isdigit():
            continue
        standard = standard_reading(core, toks, index, before, after)
        if standard:
            out[index] = before + standard + names.closing(after, standard)
            continue
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
VIETNAMISED_TITLES = {"mr": "mít-tơ", "mrs": "mít-xịt", "ms": "mít", "dr": "đốc-tơ"}  # giọng KHÔNG nói được tiếng Anh (chủ sách 04-10: Mr. "mít-tơ", Mrs. "mít-xịt", Ms. "mít", Dr. "đốc-tơ"); St. qua `names.english_reading`
TITLE_NEEDS_NAME = frozenset(("dr", "st"))  # "Dr." / "St." chỉ là danh xưng khi liền trước một tên viết hoa ("Dr. Stone", "St. Louis"); "Mr." / "Ms." / "Mrs." thì luôn
TITLE_GLUED = re.compile(r"(mrs|mr|ms|dr|st)\.(?=[^\W\d_])", re.IGNORECASE)  # "mr.lyle": dấu chấm dính liền tên
TITLE_OPENERS = "\"'“‘([«"


def read_titles(toks: list[str], out: list[str], speaks_english: bool = True) -> None:
    """"Mr." / "Mrs." / "Ms." / "Dr." / "St." trước tên đọc đủ chữ Anh ("mister", "missus", "miss", "doctor", "saint"): sea-g2p đọc "mờ rờ" hay để nguyên "mr." làm cả câu bị ngắt ở dấu chấm.
    Dấu chấm bỏ theo ("mr.lyle" -> "mister lyle"). Giọng không nói được âm Anh thì Việt hoá ("mít-xịt", `VIETNAMISED_TITLES`). Thay tại chỗ; số chữ không đổi."""
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
        if not speaks_english:
            word = VIETNAMISED_TITLES.get(key) or names.english_reading(word) or word
        out[index] = before + word + tail


# Dotted Vietnamese titles need a name; single-letter address labels need more
# evidence because H./P./Q. can also be a person's initial.
VIETNAMESE_TITLES = {
    "PGS": "phó giáo sư", "GS": "giáo sư", "TS": "tiến sĩ",
    "ThS": "thạc sĩ", "Th.S": "thạc sĩ", "BS": "bác sĩ",
    "KS": "kỹ sư", "CN": "cử nhân", "TP": "thành phố", "Tp": "thành phố",
    "P": "phường", "Q": "quận", "H": "huyện", "TX": "thị xã", "ĐH": "đại học",
}
_VI_TITLE = r"(?:PGS|GS|TS|ThS|BS|KS|CN|TP|Tp|TX|ĐH|P|Q|H)\.|Th\.S\.?"
_VI_CHAIN = re.compile(r"(?<![\w.])(?:(?:" + _VI_TITLE + r")\s*)+")
_VI_PART = re.compile(_VI_TITLE)
_ADDRESS_HEADS = {"Bến", "Bình", "Tân", "Thạnh", "Phú", "Long", "Quảng", "Thủ"}
_ADDRESS_CONTEXT = re.compile(r"(?:tại|ở|thuộc|đến|địa chỉ|địa bàn|khu vực)\s*$", re.I)


def read_vietnamese_titles(toks: list[str], out: list[str]) -> None:
    """Expand dotted titles before spelling, retaining one result per source token."""
    text = " ".join(toks)
    edits: list[tuple[int, int, str]] = []
    for chain in _VI_CHAIN.finditer(text):
        tail = text[chain.end():]
        # An all-capital word after the title is another abbreviation (TP.HCM, PGS.TS), not a name.
        head = re.match(r"[^\W\d_]+", tail)
        named = bool(head and head.group()[0].isupper() and not (len(head.group()) > 1 and head.group().isupper()))
        number = bool(re.match(r"[0-9]+(?!\w)", tail))
        for part in _VI_PART.finditer(text, chain.start(), chain.end()):
            key = part.group().rstrip(".")
            address = key in {"P", "Q", "H"}
            locality = tail.split()[:2]
            address_name = (bool(_ADDRESS_CONTEXT.search(text[:chain.start()])) or
                            (len(locality) == 2 and locality[0] in _ADDRESS_HEADS and locality[1][:1].isupper()))
            if not (named or (number and key in {"P", "Q", "H", "TP", "Tp", "TX"})):
                continue
            if address and not (number or address_name):
                continue
            word = VIETNAMESE_TITLES[key]
            if part.end() < len(text) and not text[part.end()].isspace():
                word += " "
            edits.append((part.start(), part.end(), word))
    offset = 0
    for index, token in enumerate(toks):
        if out[index] == token:
            value = token
            for start, end, word in reversed(edits):
                if offset <= start and end <= offset + len(token):
                    value = value[:start-offset] + word + value[end-offset:]
            out[index] = value
        offset += len(token) + 1
