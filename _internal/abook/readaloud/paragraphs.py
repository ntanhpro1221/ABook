"""Các đoạn của một chương chỉ-có-chữ - bản Python của `splitParagraphs` / `sceneBreakGaps` trong ui/src/listen/textScript.ts.

Mỗi đoạn là một clip trong bộ đệm giọng đọc (khoá clip = giọng + chữ của đoạn), nên xuất sách nói ở máy chủ (webui/listen_export.py) phải chia chương
ra ĐÚNG các đoạn như màn đọc và lõi đọc to của điện thoại (Paragraphs.kt) - mới tái dùng được clip đã làm trước / đã nghe. Đổi một bên là đổi cả ba bên; cùng
bộ ví dụ tests/fixtures/scene_break/cases.json (tests/test_listen_paragraphs_shared.py = textScript.test.ts = SceneBreakTest.kt).

Chữ "\\s" của JavaScript gồm U+00A0 và U+FEFF mà "\\s" của Python không có (Python có thêm U+001C-U+001F và U+0085 mà JS không có): viết rõ tập ký tự, như
Paragraphs.kt. Tập ký tự dựng từ mã số, không gõ ký tự vô hình vào mã nguồn. Luật dòng ngăn cảnh không chép lại: dùng thẳng `text_processing.is_scene_break_line`.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .. import text_processing as tp

# Đúng tập của "\s" trong JavaScript: tab, xuống dòng, VT, FF, CR, dấu cách, NBSP, U+1680, U+2000-U+200A, U+2028, U+2029, U+202F, U+205F, U+3000, U+FEFF.
_JS_SPACE_CODES = (9, 10, 11, 12, 13, 32, 0xA0, 0x1680, *range(0x2000, 0x200B), 0x2028, 0x2029, 0x202F, 0x205F, 0x3000, 0xFEFF)
JS_SPACE_CHARS = "".join(map(chr, _JS_SPACE_CODES))
_CLASS = "".join(re.escape(char) for char in JS_SPACE_CHARS)
_SPACES = re.compile(f"[{_CLASS}]+")
_NEWLINES = re.compile(r"\r\n?")
_BLANK_LINE = re.compile(chr(10) + "[ " + chr(9) + chr(0xA0) + "]*" + chr(10))  # dòng trống: xuống dòng, vài dấu cách / tab / NBSP, xuống dòng
_NOTE_MARKER = re.compile(r"\[" + f"[{_CLASS}]*" + r"note[0-9]+" + f"[{_CLASS}]*" + r"\]", re.IGNORECASE)
_SENTENCE_END = ".!?…\"”»’)」』】。！？~–—"  # dấu kết câu ở cuối dòng: dòng như vậy là trọn một đoạn
_WHOLE_LINE = 200  # dài hơn mọi khổ dòng của máy dàn trang: chắc chắn là trọn một đoạn
CREDIT_WINDOW = tp.CREDIT_WINDOW_LINES
SCENE_BREAK_MS = tp.SCENE_BREAK_MS


@dataclass(frozen=True)
class Paragraph:
    """Một đoạn của chương: chữ, và có phải dòng ngăn cảnh không (kể cả luật "đứng riêng một đoạn")."""

    text: str
    scene_break: bool


def squeeze(text: str) -> str:
    return _SPACES.sub(" ", text).strip(JS_SPACE_CHARS)


def without_note_markers(text: str) -> str:
    """Bỏ mã chú thích của trang web chép lẫn vào chữ ("[note54360]"); "[Note]" không số, "[1]" giữ nguyên."""
    return _NOTE_MARKER.sub("", text)


def is_speakable(text: str) -> bool:
    """Đoạn có chữ hay số để đọc lên (chữ cái hoặc chữ số Unicode), không phải "* * *", "…"."""
    return any(unicodedata.category(char)[0] in "LN" for char in text)


def _text_paragraphs(lines: list[str]) -> list[str]:
    """Các dòng của một khối không có dòng ngăn cảnh: bị bẻ giữa câu thì nối thành một đoạn; đa số dòng kết thúc bằng dấu kết câu, hay có dòng quá dài, thì mỗi dòng một đoạn."""
    if len(lines) < 2:
        return lines
    ended = sum(1 for line in lines[:-1] if line[-1] in _SENTENCE_END)
    return lines if ended * 2 > len(lines) - 1 or any(len(line) > _WHOLE_LINE for line in lines) else [" ".join(lines)]


def _plain(texts: list[str]) -> list[Paragraph]:
    return [Paragraph(text, False) for text in texts]


def _block_paragraphs(block: str) -> list[Paragraph]:
    lines = [line for line in (squeeze(raw) for raw in block.split(chr(10))) if line]
    out: list[Paragraph] = []
    run: list[str] = []
    for line in lines:
        if not tp.is_scene_break_line(line, alone=len(lines) == 1):
            run.append(line)
            continue
        out += _plain(_text_paragraphs(run))
        out.append(Paragraph(line, True))
        run = []
    return out + _plain(_text_paragraphs(run))


def split_paragraphs(text: str) -> list[Paragraph]:
    """Các đoạn của chương (`splitParagraphs`): có dòng trống ngăn đoạn thì đoạn là phần giữa hai dòng trống; không có dòng trống nào thì mỗi dòng một đoạn."""
    clean = _NEWLINES.sub(chr(10), without_note_markers(text))
    if _BLANK_LINE.search(clean):
        return [paragraph for block in _BLANK_LINE.split(clean) for paragraph in _block_paragraphs(block)]
    lines = [line for line in (squeeze(raw) for raw in clean.split(chr(10))) if line]
    return [Paragraph(line, tp.is_scene_break_line(line, alone=len(lines) == 1)) for line in lines]


def paragraphs_of(text: str) -> list[str]:
    return [paragraph.text for paragraph in split_paragraphs(text)]


def without_lines(text: str, skip: list[str] | tuple[str, ...] | None) -> str:
    """Chữ của chương trừ các dòng người nghe đã chọn bỏ khỏi phần đọc (lớp sửa `skip`); chỉ xét CREDIT_WINDOW dòng có chữ đầu chương (`withoutLines`)."""
    if not skip:
        return text
    seen = 0
    kept: list[str] = []
    for line in _NEWLINES.sub(chr(10), text).split(chr(10)):
        shown = squeeze(without_note_markers(line))  # `skip` ghi từ chữ đã bỏ mã chú thích
        if shown and seen < CREDIT_WINDOW:
            seen += 1
            if shown in skip:
                continue
        kept.append(line)
    return chr(10).join(kept)


def scene_break_gaps(paragraphs: list[Paragraph]) -> list[int]:
    """Quãng lặng (ms) của từng đoạn (`sceneBreakGaps`): chỉ dòng ngăn cảnh ĐẦU của một chuỗi dòng ngăn cảnh liền nhau có quãng lặng, và chỉ khi có đoạn đọc được ở cả
    trước lẫn sau nó. Các đoạn còn lại 0."""
    gaps = [0] * len(paragraphs)
    spoken = False
    first = -1
    for index, paragraph in enumerate(paragraphs):
        if paragraph.scene_break:
            if spoken and first < 0:
                first = index
        elif is_speakable(paragraph.text):
            if first >= 0:
                gaps[first] = SCENE_BREAK_MS
            first = -1
            spoken = True
    return gaps
