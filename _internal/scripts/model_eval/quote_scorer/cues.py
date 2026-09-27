"""Thẻ lời nói tường minh trong truyện dịch tiếng Việt ("Lucien nói:", "…," Douglas cười nói.) - cho N1 (che dấu hiệu).

Hai vị trí, theo quy ước truyện dịch (đo trên gold 27-09):
- thẻ ĐỨNG TRƯỚC: lời kể kết thúc bằng "<Tên> ... <động từ nói>:" -> nhãn cho câu thoại NGAY SAU;
- thẻ ĐỨNG SAU: lời kể bắt đầu bằng "<Tên> ... <động từ nói>" ngay sau một câu thoại -> nhãn cho câu thoại NGAY TRƯỚC.
Cho phép tối đa ba chữ giữa tên và động từ ("Douglas mỉm cười nói", "Lucien khẽ đáp").
"""

from __future__ import annotations

import re

SPEECH_VERBS = (
    "nói", "hỏi", "đáp", "trả lời", "gọi", "thì thầm", "hét", "la lên", "quát", "bảo", "lẩm bẩm", "lên tiếng",
    "cất tiếng", "mở lời", "giải thích", "nhắc", "đáp lời", "hỏi lại", "nói tiếp", "chen vào", "kêu",
    "gắt", "càu nhàu", "lầm bầm", "thốt", "hô", "ra lệnh", "phản bác", "xác nhận", "tiếp lời", "cười nói",
)
VERB = "|".join(sorted((re.escape(verb) for verb in SPEECH_VERBS), key=len, reverse=True))
# Không phải thẻ lời nói (đo trên gold 27-09): "tự hỏi" là nghĩ thầm, "trong lòng" là nội tâm, "thở dài" chỉ là cử chỉ.
NOT_SPEECH = re.compile(r"(?<!\w)(tự hỏi|tự nhủ|trong lòng|thầm nghĩ|nghĩ thầm)(?!\w)", re.IGNORECASE)


def cue_patterns(aliases: dict[str, set[str]]) -> tuple[re.Pattern, re.Pattern] | None:
    if not aliases:
        return None
    names = "|".join(re.escape(name) for name in sorted(aliases, key=len, reverse=True))
    # Tên ở vị trí CHỦ NGỮ: đầu mệnh đề cuối (sau dấu câu gần nhất) - "Sana nhìn Lucien và nhỏ giọng nói:" là Sana.
    before = re.compile(rf"(?:^|[.!?…,;]\s*)\W{{0,3}}(?P<name>{names})(?:\s+[\w-]+){{0,8}}?\s+(?:{VERB})(?!\w)"
                        rf"[^.!?…:]{{0,20}}:\s*$", re.IGNORECASE)
    after = re.compile(rf"^\W{{0,3}}(?P<name>{names})(?:\s+\w+){{0,3}}?\s+(?:{VERB})(?!\w)", re.IGNORECASE)
    return before, after


def explicit_labels(segments: list[tuple[int, str, str]], aliases: dict[str, set[str]]) -> dict[int, tuple[str, int]]:
    """seq câu thoại -> (thực thể theo thẻ, seq của đoạn lời kể chứa thẻ). Bỏ qua tên trỏ tới nhiều thực thể."""
    patterns = cue_patterns(aliases)
    if patterns is None:
        return {}
    before, after = patterns
    found: dict[int, tuple[str, int]] = {}
    for index, (seq, text, kind) in enumerate(segments):
        if kind == "dialogue" or NOT_SPEECH.search(text):
            continue
        if index + 1 < len(segments) and segments[index + 1][2] == "dialogue":
            match = before.search(text)
            if match and len(aliases[match.group("name").lower()]) == 1:
                found.setdefault(segments[index + 1][0], (next(iter(aliases[match.group("name").lower()])), seq))
        if index > 0 and segments[index - 1][2] == "dialogue":
            match = after.search(text)
            if match and len(aliases[match.group("name").lower()]) == 1:
                found.setdefault(segments[index - 1][0], (next(iter(aliases[match.group("name").lower()])), seq))
    return found
