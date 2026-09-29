"""Xưng hô như tín hiệu người nói - thẻ "Ai nói câu này?" cho truyện kể ngôi thứ nhất (hộp "Việc cần duyệt").

Mỗi nhân vật có cặp xưng/gọi khá riêng ("ta… ngươi", "tớ… cậu", "tôi… tiểu thư"). Dựng hồ sơ đại từ của từng người nói
trong CHƯƠNG từ chính nhãn máy gán (không cần LLM, không cần GPU), rồi hỏi về câu dính người kể "tôi" - đang gán cho người
kể mà xưng hô giống một người khác hẳn, hay ngược lại. Nhầm người kể là lỗi lớn nhất của mọi model trên bộ LN (hơn nửa số câu
sai, ANALYSIS_RESEARCH.md 29-09).

Đo 29-09 trên bộ LN 12 chương (research/ln/ln_pronoun_profile.py trong ABook-Private), biên 1: câu bị hỏi SAI THẬT 85-95%
(nền 38-46%). Chỉ câu dính người kể, vì truyện ngôi ba kiểu Trung (Tam quốc, Throne of Magical Arcana) ai cũng "ta/ngươi":
xét mọi câu thì toàn hỏi nhầm câu đúng. Máy KHÔNG tự đổi (lãi không đều giữa các truyện: Love Unseen hai người xưng hô
giống nhau) - người nghe quyết.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Any, Callable

PRONOUNS = (
    "tôi", "tớ", "mình", "ta", "tao", "ngươi", "mày", "cậu", "ngài", "thiếp", "chàng", "nàng", "huynh", "đệ", "muội", "tỷ",
    "tỉ", "em", "anh", "chị", "cô", "ông", "bà", "con", "cháu", "bác", "chú", "nhóc", "lão", "bạn",
    "chúng ta", "chúng tôi", "chúng mình", "chúng tớ", "chúng mày", "bọn ta", "bọn mình", "bọn tao", "bọn mày",
)
# "người", "chúng"/"các"/"bọn" đứng một mình đa nghĩa - không đếm. Ngôi ba ("cô ấy", "anh ta", "ông kia") không phải xưng hô
# với người nghe; "cô" của "cô độc/cô gái/cô đơn" không phải đại từ.
_TOKEN = re.compile(r"(?<![\wÀ-ỹ])(" + "|".join(sorted(PRONOUNS, key=len, reverse=True)) + r")(?![\wÀ-ỹ])", re.IGNORECASE)
# Cả cụm ngôi ba bị bỏ trước khi đếm - kể cả "ta" của "anh ta" (không phải "ta" = tôi).
_THIRD_PERSON = re.compile(
    r"(?<![\wÀ-ỹ])(?:anh|chị|cô|ông|bà|cậu|em|con|chú|bác|lão|hắn|nó)\s+(?:ấy|kia|ta)(?![\wÀ-ỹ])", re.IGNORECASE
)
_NOT_PRONOUN = {"cô": re.compile(r"\s+(độc|gái|đơn|nương|bé|lập)", re.IGNORECASE)}
MARGIN = 1.0  # log-likelihood hơn nhau ít nhất bấy nhiêu mới hỏi
MIN_OWN = 8  # hồ sơ người đang được gán (không tính câu đang xét) phải có ít nhất bấy nhiêu đại từ
MIN_LINES = 4  # người được đề xuất phải nói ít nhất bấy nhiêu câu trong chương


def tokens(text: str) -> Counter:
    found: Counter = Counter()
    text = _THIRD_PERSON.sub(" ", text)
    for match in _TOKEN.finditer(text):
        word = match.group(1).casefold()
        if word in _NOT_PRONOUN and _NOT_PRONOUN[word].match(text[match.end():match.end() + 8]):
            continue
        found[word] += 1
    return found


def _log_likelihood(bag: Counter, profile: Counter) -> float:
    total = sum(profile.values())
    return sum(count * math.log((profile[word] + 0.5) / (total + 0.5 * len(PRONOUNS))) for word, count in bag.items())


def _same_person(label: str, name: str) -> bool:
    return bool(name) and bool({word.casefold() for word in label.split()} & {word.casefold() for word in name.split()})


def address_doubts(rows: list[Any], narrator_of: Callable[[int], str]) -> list[tuple[Any, str, list[str]]]:
    """(câu, người xưng hô giống hơn, các đại từ trong câu) cho câu thoại dính người kể của chương (`narrator_of(chapter_id)`,
    rỗng = chương kể ngôi ba: bỏ qua) mà xưng hô hợp người kia hơn người đang được gán ít nhất `MARGIN`."""
    by_chapter: dict[int, list[Any]] = defaultdict(list)
    for row in rows:
        by_chapter[int(row["chapter_id"])].append(row)
    found: list[tuple[Any, str, list[str]]] = []
    for chapter_id, chapter_rows in by_chapter.items():
        narrator = narrator_of(chapter_id)
        if not narrator:
            continue
        profiles: dict[str, Counter] = defaultdict(Counter)
        lines: Counter = Counter()
        bags = []
        for row in chapter_rows:
            label = str(row["speaker"] or "")
            bag = tokens(str(row["text"] or ""))
            bags.append(bag)
            profiles[label].update(bag)
            lines[label] += 1
        for row, bag in zip(chapter_rows, bags):
            if not bag:
                continue
            label = str(row["speaker"] or "")
            own = profiles[label] - bag  # không để câu đang xét tự xác nhận người đang được gán
            if sum(own.values()) < MIN_OWN:
                continue
            here = _log_likelihood(bag, own)
            best, best_score = "", here
            for other, profile in profiles.items():
                if other == label or lines[other] < MIN_LINES:
                    continue
                score = _log_likelihood(bag, profile)
                if score > best_score:
                    best, best_score = other, score
            if not best or best_score - here < MARGIN:
                continue
            if not (_same_person(label, narrator) or _same_person(best, narrator)):
                continue
            found.append((row, best, sorted(bag)))
    return found
