"""Nhãn người nói về dạng tên CÓ THẬT trong chương: model viết một người bằng hai dạng tên ("Toko" cho Tooko, "Kim Jae Hun"
cho Kim Jaehun, "Gu Yangchen" cho người kể Gu Yangcheon) thì sổ nhân vật có hai người, hai giọng.

Luật chặt (đo 11-10 trên đầu ra thô 9 model, LLM_Train/errtax_next/snap_names.py: b9lps1234 cổng 19 79,14 -> 79,51, cổng rộng
72,94 -> 73,76; 0 câu xấu đi / ~11.000 câu). Nhãn L mà chữ chương KHÔNG viết (không phân biệt hoa thường, ranh giới từ) và không
là tên đã biết, có ĐÚNG MỘT khoá tên gần nó trong chương -> L thành dạng ấy ở mọi câu của chương. Tên trong chương = cụm 1-3 chữ
viết Hoa liền nhau (nối "-" kính ngữ được) xuất hiện >= 2 lần, các nhãn khác có trong chữ, và tên đã biết (sổ nhân vật, người kể
ngôi thứ nhất). Gần = khoá lệch <= 1 ký tự (khoá >= 9 ký tự: <= 2). Hai khoá ứng viên trở lên, hay không có -> giữ nguyên.

Thuần (không đọc sổ dự án): `character_registry.snap_labels_to_chapter_names` đem nó vào dây chuyền.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable

from .character_registry import _fold_each_char, _within_one_edit, _within_two_edits

# Nhãn không phải tên người: người kể, chưa rõ, hệ thống, NPC (cả nhãn cục bộ `NPC_LOCAL::...`).
NOT_A_NAME = frozenset({"NARRATOR", "UNKNOWN", "SYSTEM", ""})
NPC_LABEL = re.compile(r"NPC(?:$|[\s:_*-])", flags=re.IGNORECASE)
CAPITALIZED_RUN = re.compile(r"(?<![\w-])([A-ZÀ-ỸĐ][\w']*(?:-[\w']+)*(?: [A-ZÀ-ỸĐ][\w']*(?:-[\w']+)*){0,2})")
KEY_DROPPED = re.compile(r"[\s\-_'.]")
# Nguyên âm dài / phiên âm hai cách: "Tooko" = "Toko", "Yangcheon" = "Yangchen".
KEY_VOWELS = (("oo", "o"), ("uu", "u"), ("ou", "o"), ("eo", "e"), ("ii", "i"), ("aa", "a"), ("ee", "e"))
MINIMUM_KEY = 3
LONG_KEY = 9


def name_key(name: str) -> str:
    """Khoá so hai cách viết một tên: bỏ dấu, chữ thường, bỏ khoảng trắng/gạch/'/., gộp nguyên âm đôi."""
    key = KEY_DROPPED.sub("", _fold_each_char(unicodedata.normalize("NFC", name)).casefold())
    for long_vowel, short_vowel in KEY_VOWELS:
        key = key.replace(long_vowel, short_vowel)
    return key


def _close(left: str, right: str, edits: int) -> bool:
    return left == right or _within_one_edit(left, right) or (edits >= 2 and _within_two_edits(left, right))


def _written(label: str, folded_text: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(label.casefold()) + r"(?!\w)", folded_text) is not None


def is_name_label(label: str) -> bool:
    return label.upper() not in NOT_A_NAME and NPC_LABEL.match(label) is None


def snap_map(lines: Iterable[tuple[str, str]], known: Iterable[str] = ()) -> dict[str, str]:
    """{nhãn: dạng tên chương viết} cho MỘT chương; `lines` = (nhãn người nói, chữ câu) theo thứ tự câu, `known` = tên đã biết.
    Nhãn không đổi thì không có trong kết quả. Tất định: cùng chương cho cùng kết quả, thứ tự câu không quyết gì."""
    lines = list(lines)
    known = sorted({name for name in known if name})
    text = unicodedata.normalize("NFC", " ".join(text for _label, text in lines))
    folded_text = text.casefold() + " " + " ".join(known).casefold()
    forms: Counter[str] = Counter()
    for match in CAPITALIZED_RUN.finditer(text):
        words = match.group(1).split(" ")
        for start in range(len(words)):
            for end in range(start + 1, len(words) + 1):
                forms[" ".join(words[start:end])] += 1
    labels = sorted({label for label, _text in lines if label})
    names = {form for form, count in forms.items() if count >= 2}
    names |= {label for label in labels if _written(label, folded_text)} | set(known)
    keyed = [(name_key(name), name) for name in sorted(names)]
    snapped: dict[str, str] = {}
    for label in labels:
        if not is_name_label(label) or _written(label, folded_text):
            continue
        key = name_key(label)
        if len(key) < MINIMUM_KEY:
            continue
        edits = 2 if len(key) >= LONG_KEY else 1
        candidates: dict[str, set[str]] = defaultdict(set)
        for other_key, name in keyed:
            if other_key and _close(key, other_key, edits):
                candidates[other_key].add(name)
        if len(candidates) == 1:
            # Một khoá, nhiều cách viết ("Tooko" trong chữ, "TOOKO" trong sổ): lấy cách chữ chương dùng nhiều nhất.
            spellings = next(iter(candidates.values()))
            snapped[label] = max(spellings, key=lambda name: (forms[name], len(name), name))
    return snapped
