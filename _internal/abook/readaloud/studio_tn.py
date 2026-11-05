"""Studio đọc chữ bằng cùng bộ chuẩn hoá theo chữ với "Nghe ngay" (`vieneu.spoken_tokens`): số La Mã, viết tắt, thán từ kéo dài, kính ngữ, ký hiệu theo
ngữ cảnh, "~", nghìn kiểu Anh... Không có luật nào ở đây - chỉ phần ghép: chữ được tách tại chỗ (khoảng trắng giữ nguyên), chữ chồng lên cách đọc trong bảng phát âm
của cuốn được GIỮ NGUYÊN (bảng của cuốn thắng, như `readings.apply_tokens` ở Nghe ngay), và trả kèm bảng dịch vị trí để mốc anchor của Studio trỏ đúng sau khi chuỗi đổi
độ dài."""
from __future__ import annotations

import re
import unicodedata
from typing import Sequence

from ..text_processing import STRETCHED_SIGH_PATTERN, VOCAL_CUE_PATTERN
from . import vieneu


def separate_digit_quotes(text: str) -> str:
    """Keep quote/prime marks away from numbers in voice text only.

    sea-g2p interprets adjacent quotes as seconds/inches. Spaces preserve offsets
    (including protected pronunciation spans) and never change the number reading.
    Unicode initial/final quotation punctuation covers curly, angle and CJK quotes;
    modifier primes, straight/fullwidth quotes and accent lookalikes need listing.
    """
    def quote(character: str) -> bool:
        name = unicodedata.name(character, "")
        return (unicodedata.category(character) in {"Pi", "Pf"}
                or any(kind in name for kind in ("QUOTATION MARK", "PRIME", "APOSTROPHE", "DITTO MARK"))
                or character in (
            "\"'`´ʹʺʻʼʽʾʿˈˊˋˮ′″‴‵‶‷⁗＂＇「」『』〝〞〟"
        ))

    marks = "".join({character for character in text if quote(character)})
    if not marks:
        return text
    group = "[" + re.escape(marks) + "]+"
    return re.sub(r"(?<=\d)" + group + "|" + group + r"(?=\d)",
                  lambda match: " " * len(match.group()), text)


def studio_tn(text: str, origin: str | None, speaks_english: bool,
              protected_spans: Sequence[tuple[int, int]] = ()) -> tuple[str, list[int]]:
    """(chữ đem đọc, bảng dịch vị trí). `protected_spans`: các khoảng [bắt đầu, kết thúc) của `text` đã là cách đọc của bảng phát âm - mọi chữ chạm vào một
    khoảng được giữ nguyên. Bảng dịch vị trí có `len(text) + 1` phần tử: phần tử `i` là vị trí mới của vị trí cũ `i` (vị trí nằm trong chữ đã đổi dồn về đầu chữ mới,
    vị trí nằm trong khoảng trắng đã bỏ dồn về chỗ bỏ); biên của khoảng được giữ nguyên dịch đúng theo độ lệch các chữ đứng trước."""
    from ..webui.word_timing import _TOKEN

    matches = list(_TOKEN.finditer(text))
    identity = list(range(len(text) + 1))
    if not matches:
        return separate_digit_quotes(text), identity
    toks = [match.group() for match in matches]
    said = [w if w == t else w.replace("_", "") for t, w in zip(toks, vieneu.spoken_tokens(toks, origin, speaks_english))]  # "o_": dấu giữ chữ "o" lẻ riêng của Nghe ngay (vieneu_engine.keep_lone_o), Studio không dùng
    for index, match in enumerate(matches):
        if any(match.start() < end and match.end() > start for start, end in protected_spans):
            said[index] = toks[index]
    if said == toks:
        return separate_digit_quotes(text), identity
    # Cả chuỗi cũ thành các đoạn liền nhau [bắt đầu, kết thúc, chữ mới]: khoảng đầu, từng chữ, khoảng giữa, khoảng cuối.
    pieces: list[list] = []
    cursor = 0
    token_at: list[int] = []
    for index, match in enumerate(matches):
        pieces.append([cursor, match.start(), text[cursor:match.start()]])
        token_at.append(len(pieces))
        pieces.append([match.start(), match.end(), said[index]])
        cursor = match.end()
    pieces.append([cursor, len(text), text[cursor:]])
    for index, word in enumerate(said):  # chữ đổi thành rỗng: bỏ luôn một khoảng trắng kề (sau nó; chữ cuối thì trước nó)
        if word == "":
            at = token_at[index]
            if index + 1 < len(matches):
                pieces[at + 1][2] = ""
            elif index > 0:
                pieces[at - 1][2] = ""
    parts: list[str] = []
    mapping = [0] * (len(text) + 1)
    new_length = 0
    for start, end, new in pieces:
        old = text[start:end]
        prefix = 0
        while prefix < min(len(old), len(new)) and old[prefix] == new[prefix]:
            prefix += 1
        suffix = 0
        while (suffix < min(len(old), len(new)) - prefix
               and old[-suffix - 1] == new[-suffix - 1]):
            suffix += 1
        for position in range(start, end):
            offset = position - start
            if len(old) == len(new) or offset < prefix:
                mapped = offset
            elif suffix and offset >= len(old) - suffix:
                mapped = len(new) - (len(old) - offset)
            else:
                mapped = prefix
            mapping[position] = new_length + mapped
        parts.append(new)
        new_length += len(new)
    mapping[len(text)] = new_length
    return separate_digit_quotes("".join(parts)), mapping


def studio_tn_tagged(text: str, anchor_tags: list[frozenset[int]], origin: str | None,
                     speaks_english: bool, *,
                     changed_words: list[tuple[int, int, int, int]] | None = None,
                     unprotected_anchors: frozenset[int] = frozenset(),
                     ) -> tuple[str, list[frozenset[int]]]:
    """`studio_tn` cho chuỗi Studio đang mang dấu anchor theo từng ký tự (`anchor_tags[i]`: các anchor có ký tự `i` là cách đọc của bảng phát âm). Khoảng của mỗi
    anchor là chữ được giữ nguyên; trả chuỗi mới cùng dấu anchor đã dịch theo để các bước sau (`_normalize_with_anchor_spans`) vẫn tìm đúng khoảng của anchor."""
    bounds: dict[int, list[int]] = {}
    for position, tags in enumerate(anchor_tags):
        for anchor_index in tags:
            span = bounds.setdefault(anchor_index, [position, position + 1])
            span[0], span[1] = min(span[0], position), max(span[1], position + 1)
    # Những gì `normalize_vocalizations_for_tts` (chạy sau) đã có luật riêng của Studio thì để nó lo: hiệu lệnh "[thở dài]" (bước theo chữ không được đụng vào ngoặc của nó)
    # và "Haizzz" (Studio đọc "Hầy", sách chữ đọc "hai").
    cues = [match.span() for pattern in (VOCAL_CUE_PATTERN, STRETCHED_SIGH_PATTERN) for match in pattern.finditer(text)]
    protected = [span for index, span in bounds.items() if index not in unprotected_anchors]
    new_text, mapping = studio_tn(text, origin, speaks_english, [*protected, *cues])
    if changed_words is not None:
        from ..webui.word_timing import _TOKEN

        for match in _TOKEN.finditer(text):
            start, end = match.span()
            before, after = match.group(), new_text[mapping[start]:mapping[end]]
            if (before != after and any(c.isalpha() for c in before)
                    and not any(c.isdigit() for c in before)
                    and any(c.isalpha() for c in after)
                    and not any(anchor_tags[start:end])
                    and not any(start < b and end > a for a, b in cues)):
                changed_words.append((start, end, mapping[start], mapping[end]))
    if new_text == text:
        return text, anchor_tags
    marks: list[set[int]] = [set() for _character in new_text]
    for anchor_index, (start, end) in bounds.items():
        for position in range(mapping[start], mapping[end]):
            marks[position].add(anchor_index)
    return new_text, [frozenset(mark) for mark in marks]
