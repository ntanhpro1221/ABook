"""Phụ âm đầu theo chính tả tiếng Việt - để lời từ chối một cách đọc chỉ ra chỗ sửa.

Phép kiểm cách đọc (`analysis._valid_vietnamese_spoken_form`, qua `listener_overrides.pronunciation_problem`) chỉ nhận
âm tiết viết đúng chính tả: "kơ" không phải chữ Việt, phải viết "cơ". Người nghe gõ theo tai ("Hên-kơ" cho Hailkes - soát
UX 29-09) thì bị từ chối bằng một câu chung, không biết sai ở đâu. Ở đây chỉ sửa ba cặp phụ âm đầu người gõ hay nhầm
(c/k, g/gh, ng/ngh); máy chủ kiểm lại bản sửa bằng đúng phép kiểm kia rồi mới mời dùng.
"""

from __future__ import annotations

import re
import unicodedata

# Dấu thanh (huyền, sắc, hỏi, ngã, nặng) bỏ đi để lấy nguyên âm gốc; mũ, trăng, móc giữ lại - "ê" khác "e".
_TONES = {"̀", "́", "̉", "̃", "̣"}
_BACK = frozenset("aăâoôơuư")

# (phụ âm đầu, viết lại thành, khi nguyên âm ngay sau thuộc tập này). Dài trước ngắn; tập rỗng = phụ âm đầu hợp lệ
# có chữ đầu trùng một dòng sau ("gi", "kh", "ch") - dừng ở đó để không đọc "gi" thành "g" + "i".
_RULES: tuple[tuple[str, str, frozenset[str]], ...] = (
    ("ngh", "ng", _BACK),
    ("ng", "ngh", frozenset("ieê")),
    ("gh", "g", _BACK),
    ("gi", "gi", frozenset()),
    ("g", "gh", frozenset("eê")),
    ("kh", "kh", frozenset()),
    ("k", "c", _BACK),
    ("ch", "ch", frozenset()),
    ("c", "k", frozenset("ieêy")),
)


def _base(letter: str) -> str:
    stripped = "".join(ch for ch in unicodedata.normalize("NFD", letter.lower()) if ch not in _TONES)
    return unicodedata.normalize("NFC", stripped)


def _respell(syllable: str) -> str:
    lower = syllable.lower()
    for initial, fixed, before in _RULES:
        if not lower.startswith(initial):
            continue
        rest = syllable[len(initial):]
        if not rest or _base(rest[0]) not in before:
            return syllable
        return (fixed.capitalize() if syllable[:1].isupper() else fixed) + rest
    return syllable


def respelled(spoken_form: str) -> str:
    """Cách đọc với phụ âm đầu từng âm tiết viết theo chính tả: "Hên-kơ" -> "Hên-cơ", "Ngê-ra" -> "Nghê-ra". Không có gì
    để sửa thì trả nguyên chuỗi."""
    text = unicodedata.normalize("NFC", spoken_form)
    fixed = re.sub(r"[^\s-]+", lambda match: _respell(match.group(0)), text)
    return fixed if fixed != text else spoken_form


def respelling_note(spoken_form: str, fixed: str) -> str:
    """Câu nói chỗ sai cho người gõ: 'Tiếng Việt viết “cơ”, không viết “kơ”.'"""
    before = re.findall(r"[^\s-]+", unicodedata.normalize("NFC", spoken_form))
    after = re.findall(r"[^\s-]+", fixed)
    pairs = [(old, new) for old, new in zip(before, after) if old != new]
    if not pairs:
        return ""
    right = ", ".join(f"“{new}”" for _old, new in pairs)
    wrong = ", ".join(f"“{old}”" for old, _new in pairs)
    return f"Tiếng Việt viết {right}, không viết {wrong}."
