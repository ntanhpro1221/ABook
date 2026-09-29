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


# Từ TỰ XƯNG không đổi theo người nghe trong một cảnh: hai nhóm câu của một nhãn mà tự xưng khác hẳn ("ta" / "tôi") là hai
# giọng. "em", "anh", "con", "cháu" vừa tự xưng vừa gọi người nghe - không tính ở đây.
SELF_TERMS = frozenset({"tôi", "tớ", "mình", "ta", "tao", "thiếp", "chúng ta", "chúng tôi", "chúng mình", "chúng tớ",
                        "bọn ta", "bọn mình", "bọn tao"})
SPLIT_MIN_LINES = 2  # mỗi nhóm phải có ít nhất bấy nhiêu câu
SPLIT_MARGIN = 0.5  # nhóm lạ phải kém nhóm quen bấy nhiêu log-likelihood MỖI TỪ dưới hồ sơ các chương khác


def _voices(lines: list[tuple[Any, Counter]]) -> list[tuple[set[str], list[Any]]]:
    """Các "giọng" của một nhãn: từ xưng hô nối nhau khi đi chung một câu (một người dùng chúng cùng lúc); câu không có từ
    nào thì không thuộc giọng nào. Nhiều câu nhất đứng trước."""
    parent: dict[str, str] = {}

    def find(word: str) -> str:
        while parent.setdefault(word, word) != word:
            parent[word] = parent[parent[word]]
            word = parent[word]
        return word

    for _row, bag in lines:
        words = list(bag)
        for word in words[1:]:
            parent[find(word)] = find(words[0])
    groups: dict[str, tuple[set[str], list[Any]]] = {}
    for row, bag in lines:
        if bag:
            words, rows = groups.setdefault(find(next(iter(bag))), (set(), []))
            words.update(bag)
            rows.append(row)
    return sorted(groups.values(), key=lambda group: -len(group[1]))


def _two_people(first: set[str], second: set[str]) -> bool:
    """Hai nhóm từ tách hẳn có phải hai NGƯỜI không, hay một người gọi hai người nghe bằng hai từ ("con" với mẹ, "cậu" với
    bạn): tự xưng khác nhau, hoặc cả hai nhóm đều có từ hai từ trở lên."""
    own_first, own_second = first & SELF_TERMS, second & SELF_TERMS
    if own_first and own_second and not own_first & own_second:
        return True
    return len(first) >= 2 and len(second) >= 2


def split_doubts(rows: list[Any], narrator_of: Callable[[int], str],
                 named: Callable[[str], bool]) -> list[tuple[str, list[Any], list[str], list[str], int]]:
    """"Hai người chung một tên": trong chương kể ngôi thứ nhất, câu thoại của MỘT nhãn chia làm hai giọng xưng hô không
    bao giờ đi chung câu (8B-v5 gán 21 câu của một bà thầy bói vô danh cho LUCIA: "cậu… ta" so với "anh… bà").

    Trả (nhãn, các câu nghi là của người khác, từ của nhóm ấy, từ của nhóm kia, số câu nhóm kia). Nhóm nghi là nhóm LỆCH
    khỏi cách nhãn ấy xưng hô ở các chương KHÁC của cuốn - chưa có hồ sơ ấy (nhãn chỉ nói ở chương này) thì không hỏi: không
    biết nhóm nào là người thật. Đo 29-09 (luật hai nhóm + tự xưng, trước khi lọc ngôi kể và đòi hồ sơ): bộ LN 12 chương
    15/15 lần báo đúng ở v3, v6, 8B-v5; truyện kể ngôi ba (Tam quốc, Tắt đèn) thì phần lớn báo nhầm - một người đổi xưng hô
    theo vai vế ("ta… ngươi" với tướng dưới, "tôi… ngài" với chúa) - nên chỉ xét chương có người kể."""
    dialogue = [row for row in rows if str(row["kind"]) == "dialogue" and named(str(row["speaker"] or ""))]
    bags = {id(row): tokens(str(row["text"] or "")) for row in dialogue}
    by_label: dict[str, dict[int, list[Any]]] = defaultdict(lambda: defaultdict(list))
    for row in dialogue:
        by_label[str(row["speaker"])][int(row["chapter_id"])].append(row)
    found = []
    for label, chapters in by_label.items():
        for chapter_id, chapter_rows in chapters.items():
            narrator = narrator_of(chapter_id)
            # Người kể thì không: câu dính người kể đã có thẻ xưng hô từng câu (address_doubts), và hồ sơ của người kể ở
            # các chương khác nhiễm chính những câu model gộp vào - 29-09 HDST 130: nhóm "tôi" (đúng là Ed) bị chọn nhầm
            # làm nhóm lạ vì Ed ở chương 062 đã mang lời người khác.
            if not narrator or _same_person(label, narrator):
                continue
            voices = [group for group in _voices([(row, bags[id(row)]) for row in chapter_rows])
                      if len(group[1]) >= SPLIT_MIN_LINES]
            if len(voices) < 2 or not _two_people(voices[0][0], voices[1][0]):
                continue
            elsewhere: Counter = Counter()
            for other_id, other_rows in chapters.items():
                if other_id != chapter_id:
                    for row in other_rows:
                        elsewhere.update(bags[id(row)])
            if sum(elsewhere.values()) < MIN_OWN:
                continue

            def fit(group: tuple[set[str], list[Any]]) -> float:
                bag: Counter = Counter()
                for row in group[1]:
                    bag.update(bags[id(row)])
                return _log_likelihood(bag, elsewhere) / max(1, sum(bag.values()))

            usual, odd = sorted(voices[:2], key=fit, reverse=True)
            if fit(usual) - fit(odd) < SPLIT_MARGIN:
                continue
            found.append((label, odd[1], sorted(odd[0]), sorted(usual[0]), len(usual[1])))
    return found


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
