"""Thẻ "Gọi hay nói" của hộp việc: câu thoại gán cho X mà chính câu ấy GỌI X - người được gọi thường là người nghe.

Luật gốc (`first_person.addressed_names`: "Kou, ...", "..., Satomi-san.", "Này Kou") dùng chung với luật tự sửa của dây chuyền,
nên nó chặt và KHÔNG đổi ở đây. Hộp việc chỉ HỎI, không sửa, nên được bắt thêm những lời gọi mà luật gốc bỏ qua - tất cả đều
không dùng LLM, chỉ đọc chữ của câu và sổ nhân vật (tên + bí danh):

- chức danh/xưng hô đứng ngay trước tên ở đầu một vế câu ("Đừng lo, anh Rowan.", "Thưa tiểu thư Mina, ...", "Cô, cô Mina!");
  tên Việt một âm tiết ("Dậu", "Minh") còn được nhận khi có "ơi" hoặc nằm sát dấu phẩy ở đầu/cuối lời thoại;
- tên trần ở rìa một CÂU giữa lời thoại ("Được rồi, Kiri. Giờ thì ...", "... rồi. Mina, cậu ..."); luật gốc chỉ nhận rìa
  của cả lời thoại;
- tên cuối lời thoại sau tiểu từ cuối câu ("Cậu ổn chứ Rowan?") hay sau tiếng gọi "oi", "hỡi" ("Oi Kiri.");
- cặp lời gọi: câu liền trước của người khác (Y) gọi X, và câu này - đang gán cho X - lại nhắc X: thường vẫn là người đang nói
  với X (nhiều khi chính Y), không phải X đáp.

Số đo trong docstring `caller_doubts`.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable

from ..analysis import is_vietnamese_syllable, strip_japanese_honorific
from ..character_registry import (
    ADDRESS_PARTNER_WINDOW, HONORIFIC_PREFIX_PATTERN, RESERVED_SPEAKERS, _address_owners, address_index, speakers_near,
)
from ..first_person import CALL_TITLES, _NAMING_A_NAME, _SAYS_WHO_I_AM, _is_speaker_tag, _name_pattern

# Chức danh đứng trước tên: đúng bộ chức danh mà bước gom tên của dây chuyền bỏ khỏi nhãn ("GIÁO SƯ GLAST" là Glast), cộng
# các tiếng xưng hô của `first_person` - một danh sách, hai nơi dùng.
_PREFIX_HEAD, _PREFIX_TAIL = "^(?:", r")\s+(.+)$"
assert HONORIFIC_PREFIX_PATTERN.pattern.startswith(_PREFIX_HEAD) and HONORIFIC_PREFIX_PATTERN.pattern.endswith(_PREFIX_TAIL)
_TITLE = rf"(?:{HONORIFIC_PREFIX_PATTERN.pattern[len(_PREFIX_HEAD):-len(_PREFIX_TAIL)]}|{'|'.join(CALL_TITLES)})"
# Tiếng gọi đứng trước cả cụm chức danh + tên ("Thưa ngài Rowan", "Xin chào anh Rowan"), hay trước tên trần ("Oi Kiri").
_CALL = r"(?:thưa|này|nè|ê|hey|chào|xin chào|oi|hỡi|nào)"
# Đầu một vế: đầu lời thoại hay sau dấu câu/dấu mở ngoặc.
_CLAUSE_START = r"(?:^|[.!?…,;:~“\"‘'«(\[\-–—]\s*)"
_TITLED_BEFORE = re.compile(rf"{_CLAUSE_START}[\W_]*(?:{_CALL}[,!]?\s+)?(?<!\w){_TITLE}\*?\s+$", re.IGNORECASE)
_CALL_BEFORE = re.compile(rf"(?<!\w){_CALL}[,!]?\s+$", re.IGNORECASE)
# Sau tên: hết vế/câu (có thể kèm "ơi", "à").
_CLAUSE_END = re.compile(r"^(?:\s*(?:ơi|à|ạ|này|nè)(?!\w))?\s*(?:[,.!?…~;:”\"’'»)\]]|$)", re.IGNORECASE)
_PARTICLE_THEN = re.compile(r"^\s*(?:ơi)(?!\w)", re.IGNORECASE)
# Tên trần ở rìa một câu GIỮA lời thoại: ", Kiri. Giờ thì ..." / "... rồi. Mina, cậu ...".
_COMMA_BEFORE = re.compile(r",\s*$")
_SENTENCE_END_AFTER = re.compile(r"^\s*[.!?…]+[”\"’']?\s+\S")
_SENTENCE_START_BEFORE = re.compile(rf"[.!?…][”\"’']?\s+(?:{_CALL}[,!]?\s+)?$", re.IGNORECASE)
_COMMA_AFTER = re.compile(r"^\s*,")
# Tên cuối lời thoại ngay sau tiểu từ cuối câu: "Cậu ổn chứ Rowan?", "phòng cậu à Mina?".
_PARTICLE_BEFORE = re.compile(r"(?<!\w)(?:chứ|nhỉ|nhé|nha|à|hả|hở|ạ|đấy|đó|vậy|thế|nào|chưa|không)\s*,?\s*$", re.IGNORECASE)
_LINE_TAIL = re.compile(r"[\W_]*")
_LINE_HEAD = re.compile(r"[\W_]*")
_FINAL_CALL_BEFORE = re.compile(r",\s*$")


@dataclass
class Call:
    """Một câu thoại gán cho người mà chính câu ấy gọi: `people` - người có tên đang nói chuyện với người ấy quanh câu (người
    nên được hỏi trước), `caller` - người vừa gọi người ấy ở câu liền trước (cặp lời gọi), không có thì ""."""

    people: list[str] = field(default_factory=list)
    caller: str = ""


@lru_cache(maxsize=8)
def _patterns(surfaces: frozenset[str], titled: frozenset[str]) -> tuple[re.Pattern[str] | None, re.Pattern[str] | None]:
    return (_name_pattern(surfaces) if surfaces else None, _name_pattern(titled) if titled else None)


def _titled_surfaces(aliases_by_speaker: dict[str, set[str]], named: set[str]) -> dict[str, set[str]]:
    """{tên Việt một âm tiết: người mang nó} - dạng mà `_address_surfaces` bỏ ("Dậu", "Minh", tên cuối của "Chu Mặc"): chỉ dùng
    khi có chức danh, tiếng gọi hoặc dấu phẩy ở rìa lời thoại."""
    owners: dict[str, set[str]] = defaultdict(set)
    for speaker in named:
        for alias in aliases_by_speaker.get(speaker, set()) | {speaker}:
            words = strip_japanese_honorific(" ".join(str(alias).split())).split()
            if not words or not all(is_vietnamese_syllable(word.casefold()) for word in words):
                continue
            given = words[-1]
            if len(given) >= 2 and given.casefold() not in RESERVED_SPEAKERS:
                for form in {given[0].upper() + given[1:].lower(), given.upper()}:
                    owners[form].add(speaker)
    return owners


def extra_calls(text: str, surfaces: frozenset[str], titled: frozenset[str] = frozenset()) -> set[str]:
    """Những cách gọi (trong `surfaces`, `titled`) mà câu thoại `text` GỌI theo các luật thêm của hộp việc (đầu file) - không gồm
    luật gốc `first_person.addressed_names`. `titled`: tên cần chức danh, tiếng gọi hoặc dấu phẩy ở rìa lời thoại."""
    plain, titled_pattern = _patterns(surfaces, titled)
    if _SAYS_WHO_I_AM.search(text):
        return set()
    found: set[str] = set()
    for pattern, bare_ok in ((plain, True), (titled_pattern, False)):
        if pattern is None:
            continue
        for match in pattern.finditer(text):
            before, after = text[:match.start(1)], text[match.end():]
            if _NAMING_A_NAME.search(before.rstrip(" ")) or _is_speaker_tag(before.rstrip(" "), after):
                continue
            if ((_TITLED_BEFORE.search(before) and _CLAUSE_END.match(after)) or _PARTICLE_THEN.match(after)
                    or (_CALL_BEFORE.search(before) and _CLAUSE_END.match(after))
                    or (not bare_ok and ((_LINE_HEAD.fullmatch(before) and _COMMA_AFTER.match(after))
                                         or (_FINAL_CALL_BEFORE.search(before) and _LINE_TAIL.fullmatch(after))))):
                found.add(match.group(1))
            elif bare_ok and (
                (_COMMA_BEFORE.search(before) and _SENTENCE_END_AFTER.match(after))
                or (_SENTENCE_START_BEFORE.search(before) and _COMMA_AFTER.match(after))
                or (_CALL_BEFORE.search(before) and _CLAUSE_END.match(after))
                or (_PARTICLE_BEFORE.search(before) and _LINE_TAIL.fullmatch(after))
            ):
                found.add(match.group(1))
    return found


def mentions(text: str, surfaces: frozenset[str], titled: frozenset[str] = frozenset()) -> set[str]:
    """Mọi cách gọi trong `surfaces` câu nhắc tới (tên Việt một âm tiết cần chức danh hoặc dấu hiệu lời gọi) - cho cặp lời gọi."""
    plain, titled_pattern = _patterns(surfaces, titled)
    found = {match.group(1) for match in plain.finditer(text)} if plain is not None else set()
    found |= extra_calls(text, frozenset(), titled)
    if titled_pattern is not None:
        found |= {match.group(1) for match in titled_pattern.finditer(text)
                  if re.search(rf"(?<!\w){_TITLE}\s+$", text[:match.start(1)], re.IGNORECASE)}
    return found


def caller_doubts(
    rows: list[Any],
    aliases_by_speaker: dict[str, set[str]],
    wanted: Callable[[Any], bool] = lambda _row: True,
) -> dict[int, Call]:
    """segments.id -> `Call` cho mỗi câu thoại (trong số `wanted`) gán cho người có tên mà câu ấy gọi - luật gốc
    (`character_registry.address_index`, như thẻ cũ), luật thêm (`extra_calls`) hay cặp lời gọi. `rows` là cả cuốn (có `id`,
    `chapter_id`, `seq`, `kind`, `speaker`, `text`): người có tên và cách gọi họ tính trên cả cuốn. Người nói KHÔNG bị đổi.

    Đo 05-11 trên đáp án (scripts/model_eval/gold, chữ chương từ Corpus, chỉ đọc; 95 chương khớp chữ của 40 truyện). Đơn vị: cặp
    "câu thoại x người có tên được nhắc trong câu" (các cách viết của một người gộp một), 1.007 cặp mà người ấy KHÔNG phải người
    nói - gán câu cho họ là sai. Bị hỏi nếu câu gán cho người ấy (chính xác = người ấy không phải người nói thật):
    luật gốc 391/395 chính xác, bắt 391/1.007; luật thêm +101/102; cặp lời gọi +6/6; cả bộ 498/503 (99,0%), bắt 498/1.007
    (49,5%). Đây là phép đo có điều kiện trên cặp nhắc tên, chưa phải precision trên nhãn triển khai của model.
    Phần không bắt phần lớn là nhắc tên ngôi ba ("Cậu thấy Mina thế nào?") - không phải lời gọi, đúng là không hỏi."""
    named, addressed = address_index(rows, aliases_by_speaker)
    _named, owners = _address_owners(rows, aliases_by_speaker)
    titled_owners = _titled_surfaces(aliases_by_speaker, named)
    surfaces, titled = frozenset(owners), frozenset(titled_owners)

    def people_of(found: set[str], table: dict[str, set[str]]) -> set[str]:
        return {person for surface in found for person in table.get(surface, ())}

    cache: dict[int, set[str]] = {}

    def called(row: Any) -> set[str]:
        key = int(row["id"])
        if key not in cache:
            if str(row["kind"]) != "dialogue":
                cache[key] = set()
            else:
                text = str(row["text"])
                extra = extra_calls(text, surfaces, titled)
                cache[key] = addressed(row) | people_of(extra, owners) | people_of(extra, titled_owners)
        return cache[key]

    def mentioned(row: Any) -> set[str]:
        found = mentions(str(row["text"]), surfaces, titled)
        return people_of(found, owners) | people_of(found, titled_owners)

    by_chapter: dict[int, dict[int, Any]] = defaultdict(dict)
    for row in rows:
        by_chapter[int(row["chapter_id"])][int(row["seq"])] = row

    def previous_line(by_seq: dict[int, Any], seq: int) -> Any | None:
        """Câu thoại liền trước, cách tối đa một đoạn kể (lời dẫn) - xa hơn thì không còn là "câu đáp"."""
        for offset in (1, 2):
            row = by_seq.get(seq - offset)
            if row is not None and str(row["kind"]) == "dialogue":
                return row
        return None

    found: dict[int, Call] = {}
    for row in rows:
        speaker = str(row["speaker"])
        if not wanted(row) or speaker not in named or str(row["kind"]) != "dialogue":
            continue
        by_seq = by_chapter[int(row["chapter_id"])]
        seq = int(row["seq"])
        caller = ""
        if speaker not in called(row):
            before = previous_line(by_seq, seq)
            if (before is None or str(before["speaker"]) == speaker or speaker not in called(before)
                    or speaker not in mentioned(row) or _SAYS_WHO_I_AM.search(str(row["text"]))):
                continue
            caller = str(before["speaker"]) if str(before["speaker"]) in named else ""
        found[int(row["id"])] = Call(_partners(by_seq, seq, speaker, named, called, caller), caller)
    return found


def _partners(by_seq: dict[int, Any], seq: int, speaker: str, named: set[str], called: Callable[[Any], set[str]],
              caller: str) -> list[str]:
    """Người nên được hỏi trước cho câu gọi `speaker`: người vừa gọi họ ở câu trước, rồi người đang trò chuyện với họ quanh câu
    (câu của người khác gọi `speaker`, hay câu của `speaker` gọi người ấy), rồi người có tên nói gần nhất (`speakers_near`)."""
    near = speakers_near(by_seq, seq, speaker, named)
    talking: list[str] = []
    for distance in range(1, ADDRESS_PARTNER_WINDOW + 1):
        for offset in (-distance, distance):
            row = by_seq.get(seq + offset)
            if row is None or str(row["kind"]) != "dialogue":
                continue
            other = str(row["speaker"])
            if other != speaker and other in named and speaker in called(row):
                talking.append(other)
            elif other == speaker:
                talking.extend(person for person in sorted(called(row)) if person != speaker and person in named)
    ranked = ([caller] if caller else []) + talking + near
    return list(dict.fromkeys(person for person in ranked if person != speaker))
