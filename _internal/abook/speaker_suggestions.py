"""Lõi hai thẻ gợi ý người nói của "Việc cần anh" - hàm thuần, không UI, không model, không ghi gì.

Cả hai chỉ ĐỀ XUẤT: người dùng bấm mới gộp (qua aliases.json / ghi đè người nói như các thẻ hiện có); chưa bấm thì giữ nguyên.
Số đo dẫn tới từng ngưỡng: LLM_Train/runs/NAMEFORM_12-10.md, ANONREVEAL_12-10.md (gold v2, 90 sách / 722 người).

1. `name_pair_candidates` - "Hai tên này có phải một người?": hai nhãn có tên viết GẦN giống nhau ("Arya" / "Aria"). Gộp tự
   động thì ở mọi ngưỡng đều nhập nhầm người thật (FUJIKA/FUJIKI, QUÁCH-THẠCH-PHÙ/PHỦ), nên chỉ hỏi. Ngưỡng 0,75 + bốn bộ lọc:
   hỏi nhầm 14 cặp trên 90 sách (tối đa 3 cặp/sách) mà vẫn bắt Arya/Aria; 0,80 thì mất Arya.
2. `anonymous_speaker_candidates` - "Người này có phải X?": một nhãn vô danh (`NPC_LOCAL::…::cô gái tóc đỏ`) nói trong cùng
   chương với một người CÓ TÊN mà tên ấy nằm trong lời kể quanh câu - người nghe đang nghe hai giọng cho một người (ANONREVEAL
   ca A1: 25/25 câu ra giọng khác). Nối tự động thì nhầm gấp 5 lần (tên gần thường là người nghe / người bị nhắc), nên đưa
   NHIỀU ứng viên cho người dùng chọn, và chỉ vài thẻ mỗi chương.
"""
from __future__ import annotations

import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from .analysis import (
    LOCAL_IDENTITY_EVIDENCE_WINDOW,
    RESERVED_SPEAKERS,
    _identity_name_forms,
    _text_names,
    _traits_compatible,
    is_local_speaker,
)

# Ngưỡng giống nhau của hai tên (SequenceMatcher trên chữ đã bỏ dấu, bỏ khoảng trắng/gạch). 0,75 = Arya/Aria.
NAME_PAIR_SIMILARITY = 0.75
# Tên ngắn hơn ngần này chữ cái thì không so chính tả: tên một âm tiết Hán-Việt khác nhau một chữ là hai người (Bao / Bá).
NAME_PAIR_MIN_LETTERS = 4
# Đuôi kính ngữ Nhật bỏ trước khi so: "Krum-chan" / "Rem-chan" giống nhau vì đuôi, không vì tên.
JAPANESE_SUFFIXES = ("san", "kun", "chan", "sama", "senpai", "sensei", "dono", "shi", "nii", "nee", "tan")
# Thẻ "Người này có phải X?" tối đa mỗi chương (xếp theo số câu của nhãn vô danh), và ứng viên tối đa mỗi thẻ.
ANONYMOUS_CARDS_PER_CHAPTER = 3
ANONYMOUS_CANDIDATES_PER_CARD = 4


@dataclass(frozen=True)
class NamePair:
    """`minor` (ít câu hơn) có thể là `major` viết khác; gộp thì câu của `minor` về giọng của `major`."""
    major: str
    minor: str
    similarity: float


@dataclass(frozen=True)
class AnonymousCandidate:
    """Nhãn vô danh `speaker` ở chương `chapter_id` có thể là một trong `names` (xếp: nhiều chỗ tên gần câu trước, rồi nhiều
    câu nói dưới tên trong chương trước). `lines` = số câu của nhãn vô danh trong chương."""
    chapter_id: int
    speaker: str
    lines: int
    names: tuple[str, ...]


def _is_named(speaker: str) -> bool:
    return bool(speaker) and speaker.casefold() not in RESERVED_SPEAKERS and not is_local_speaker(speaker)


def _strip_suffix(name: str) -> str:
    lowered = name.strip().casefold()
    for suffix in JAPANESE_SUFFIXES:
        if lowered.endswith("-" + suffix):
            return name.strip()[: -len(suffix) - 1]
    return name.strip()


def _has_marks(name: str) -> bool:
    """Tên có dấu tiếng Việt (Hán-Việt): hai tên chỉ khác dấu thanh là hai người."""
    return any(unicodedata.combining(part) for part in unicodedata.normalize("NFD", name)) or "đ" in name.casefold()


def _fold(name: str) -> str:
    """Hạ chữ, bỏ dấu, chỉ giữ chữ/số - để so chính tả."""
    lowered = unicodedata.normalize("NFD", name.casefold().replace("đ", "d"))
    return "".join(char for char in lowered if not unicodedata.combining(char) and char.isalnum())


def _words(name: str) -> set[str]:
    return {word for word in "".join(char if char.isalnum() else " " for char in name.casefold()).split() if word}


def name_pair_similarity(first: str, second: str) -> float | None:
    """Độ giống của hai tên nếu cặp này đáng hỏi, None nếu một bộ lọc loại nó. Bỏ đuôi kính ngữ Nhật trước mọi phép thử."""
    a, b = _strip_suffix(first), _strip_suffix(second)
    if not a or not b or a.casefold() == b.casefold():
        return None
    # Một tên chứa hẳn tên kia ("Thân" / "Thân-hậu", "Komari" / "Terakomari" thì không - chỉ xét theo TỪ): việc của thẻ
    # "tên ngắn nằm trong tên dài" (webui/work_items.py) và bước gom tên, không phải "viết khác".
    words_a, words_b = _words(a), _words(b)
    if words_a <= words_b or words_b <= words_a:
        return None
    letters_a, letters_b = _fold(a), _fold(b)
    if min(len(letters_a), len(letters_b)) < NAME_PAIR_MIN_LETTERS or letters_a == letters_b and _has_marks(a) and _has_marks(b):
        return None
    similarity = SequenceMatcher(None, letters_a, letters_b).ratio()
    if _has_marks(a) and _has_marks(b):
        # Tên Việt/Hán-Việt so CÓ dấu: Phù / Phủ, Huệ / Vệ là hai người.
        marked = SequenceMatcher(None, "".join(a.casefold().split()), "".join(b.casefold().split())).ratio()
        similarity = min(similarity, marked)
    return similarity if similarity >= NAME_PAIR_SIMILARITY else None


def name_pair_candidates(line_counts: Mapping[str, int], genders: Mapping[str, str] | None = None) -> list[NamePair]:
    """Cặp nhãn CÓ TÊN (nhãn -> số câu) có thể là một người viết hai cách. Bỏ cặp khác giới đã biết (`genders`: nhãn ->
    "male"/"female"/"unknown"). Xếp theo số câu của tên ít câu hơn (lợi mỗi lần bấm), nhiều trước."""
    genders = genders or {}
    named = sorted((speaker for speaker in line_counts if _is_named(speaker)), key=lambda speaker: (-line_counts[speaker], speaker))
    pairs: list[NamePair] = []
    for index, major in enumerate(named):
        for minor in named[index + 1:]:
            known = {genders.get(major, "unknown"), genders.get(minor, "unknown")} - {"unknown", ""}
            if len(known) > 1:
                continue
            similarity = name_pair_similarity(major, minor)
            if similarity is not None:
                pairs.append(NamePair(major=major, minor=minor, similarity=round(similarity, 3)))
    return sorted(pairs, key=lambda pair: (-line_counts[pair.minor], -pair.similarity, pair.major, pair.minor))


def _paragraph(row: Any) -> int:
    return int(row["paragraph_index"])


def anonymous_speaker_candidates(
    rows: Iterable[Any],
    per_chapter: int = ANONYMOUS_CARDS_PER_CHAPTER,
    per_card: int = ANONYMOUS_CANDIDATES_PER_CARD,
) -> list[AnonymousCandidate]:
    """Nhãn vô danh có thể là một người CÓ TÊN cùng chương. `rows`: các câu của dự án (cột chapter_id, seq, paragraph_index,
    kind, speaker, text; gender, age nếu có - như `db.list_segments()`).

    Ứng viên của một nhãn vô danh = người có tên mà (1) nói ít nhất một câu DƯỚI TÊN trong cùng chương, (2) tên ấy (tên đủ
    hay một chữ là tên, `analysis._identity_name_forms`) có trong lời kể cách một câu của nhãn vô danh không quá
    `LOCAL_IDENTITY_EVIDENCE_WINDOW` đoạn, (3) giới và tuổi không mâu thuẫn (`analysis._traits_compatible`). Mỗi chương tối
    đa `per_chapter` thẻ, nhãn nhiều câu trước."""
    by_chapter: dict[int, list[Any]] = defaultdict(list)
    for row in rows:
        by_chapter[int(row["chapter_id"])].append(row)
    found: list[AnonymousCandidate] = []
    for chapter_id, chapter_rows in sorted(by_chapter.items()):
        chapter_rows.sort(key=lambda row: int(row["seq"]))
        local: dict[str, list[Any]] = defaultdict(list)
        named: dict[str, list[Any]] = defaultdict(list)
        for row in chapter_rows:
            speaker = str(row["speaker"] or "")
            if str(row["kind"]) == "narration":
                continue
            if is_local_speaker(speaker):
                local[speaker].append(row)
            elif _is_named(speaker):
                named[speaker].append(row)
        if not local or not named:
            continue
        narration = [row for row in chapter_rows if str(row["kind"]) == "narration"]
        forms = {name: _identity_name_forms(name) for name in named}
        cards: list[AnonymousCandidate] = []
        for speaker, speaker_rows in local.items():
            paragraphs = {_paragraph(row) for row in speaker_rows}
            near = [row for row in narration
                    if any(abs(_paragraph(row) - paragraph) <= LOCAL_IDENTITY_EVIDENCE_WINDOW for paragraph in paragraphs)]
            if not near:
                continue
            hits: Counter[str] = Counter()
            for name, name_forms in forms.items():
                if not name_forms or not _traits_compatible(speaker_rows, named[name]):
                    continue
                count = sum(1 for row in near if _text_names(str(row["text"]), name_forms))
                if count:
                    hits[name] = count
            if hits:
                names = sorted(hits, key=lambda name: (-hits[name], -len(named[name]), name))[:per_card]
                cards.append(AnonymousCandidate(chapter_id=chapter_id, speaker=speaker, lines=len(speaker_rows),
                                                names=tuple(names)))
        cards.sort(key=lambda card: (-card.lines, card.speaker))
        found.extend(cards[:per_chapter])
    return found
