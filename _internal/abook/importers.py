"""Nhập sách từ file người dùng có sẵn: thư mục TXT, EPUB, DOCX, PDF có lớp chữ (docs/LISTEN_ANYTHING.md, mục 2).

Một hàm: `import_text(path) -> ImportedBook` (tên sách, tác giả, ngôn ngữ, bìa, các chương `{title, text}`, và `notes` - những
điều người dùng nên biết hay GỢI Ý họ chấp nhận). Studio dùng nó để biến EPUB/DOCX/PDF thành thư mục chương TXT (`extract`,
phần còn lại của trình tạo sách không biết gì về định dạng gốc); "Nghe ngay" dùng thẳng các chương. Bản Kotlin của điện thoại
là `BookImport.kt`; hai bên cùng đọc bộ ví dụ `tests/fixtures/import/` (tests/import_fixtures.py) nên PHẢI ra đúng cùng một kết quả.

Luật của chủ sách: không bao giờ tự sửa chữ của truyện. Ở đây chỉ có ĐỔI ĐỊNH DẠNG - bỏ thẻ, gộp khoảng trắng, nối dòng PDF thành
đoạn, chuẩn hoá Unicode NFC. Dòng ghi công của người dịch / biên tập KHÔNG bị bỏ: nó nằm trong `notes` như một gợi ý.

Các file này là file người dùng tải từ đâu đó - không tin: chỉ đọc mục có tên trong manifest, không ghi tên file nào lấy từ gói
(tên chương là số thứ tự), giới hạn cỡ giải nén, và từ chối XML khai báo entity (không có defusedxml trong runtime). DOCX và
EPUB chỉ cần zipfile + ElementTree; PDF cần `pypdf` (BSD-3-Clause, thuần Python; chép nguyên vào `abook/vendor/pypdf`, không phụ thuộc gói cài sẵn).
"""
from __future__ import annotations

import hashlib
import html.entities
import json
import posixpath
import re
import sys
import unicodedata
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field, replace
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from xml.etree import ElementTree

from .io_utils import decode_text, discover_txt_files

IMPORT_SUFFIXES = (".epub", ".docx", ".pdf")  # file sách mà `import_text` mở (cùng .txt và thư mục TXT)
MAX_MEMBER = 20 * 1024 * 1024  # một mục XHTML / XML lớn hơn thế là bất thường
MAX_TOTAL = 300 * 1024 * 1024
MAX_COVER = 20 * 1024 * 1024
MIN_CHARS = 80  # mục EPUB ngắn hơn (bìa, trang bản quyền) bỏ qua - trừ khi mục lục gọi nó là một chương
PREAMBLE = "Mở đầu"  # chữ đứng trước tiêu đề chương đầu tiên (như txt_split)
MAX_HEADING = 120  # dòng dài hơn là một câu văn mở đầu bằng "Chương…", không phải tiêu đề
SOFT_HYPHEN = "\u00ad"  # dấu nối mềm của máy dàn trang
SIDECAR = "import.json"  # `extract` ghi cạnh các chương: tên sách, tác giả, ghi chú (đọc lại không phải mở lại file gốc)
TITLE_FROM_LINE = 80  # tên chương lấy từ dòng đầu khi mục không có tiêu đề: dài hơn thì `clip_title` cắt ở ranh giới từ (Kotlin cùng số)
CREDIT_HEAD_LINES = 64 # số dòng đầu chương đưa cho `credit_lines` (nó chỉ xem 6 dòng có chữ đầu tiên)

NS = {
    "c": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
    "ncx": "http://www.daisy.org/z3986/2005/ncx/",
    "x": "http://www.w3.org/1999/xhtml",
    "dc": "http://purl.org/dc/elements/1.1/",
}
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MC_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"
TOC_STYLE = re.compile(r"toc ?\d|toc ?heading")  # tên kiểu (viết thường) của mục lục Word tự sinh
HEADING_LEVELS = {"heading 1": 1, "heading1": 1, "heading 2": 2, "heading2": 2}  # kiểu tiêu đề Word -> cấp
BOLD_ROMAN = re.compile(r"\s*[IVXLC]+\.\s+\S")  # dòng in đậm "I. KHỞI ĐẦU": tiêu đề chương khi có từ hai dòng như thế
TITLE_PAGE_LINES = 3  # chữ trước chương đầu chỉ vài dòng ngắn, không câu nào kết thúc: trang tên sách / tác giả
TITLE_PAGE_WIDTH = 80
BLOCKS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "section", "article", "tr", "dd", "dt", "pre",
          "figure", "figcaption", "aside"}
LISTS = {"ol", "ul"}  # danh sách: không ngắt dòng, nhưng có thể là vùng lời chú (<ol epub:type="endnotes">)
CELLS = {"td", "th"}  # ô bảng: cách nhau một dấu cách ("Sức mạnh 120", không "Sức mạnh120")
NOTE_MARK = re.compile(r"\[?\d{1,3}\]?|\*{1,3}|†")  # chữ trong <sup> là số chú thích: tách khỏi chữ đứng trước ("thích 1", không "thích1")
UNIT_POWER = re.compile(r"(?<![^\W\d_])[kcdm]?m$")  # ... trừ lũy thừa đơn vị: "m<sup>2</sup>" vẫn là "m2"
NOTE_LABEL = re.compile(r"[\[(]?\d{1,3}[\])]?|\*{1,3}|†|‡|[¹²³⁰⁴⁵⁶⁷⁸⁹]+")  # nhãn của dấu gọi chú thích là liên kết: "1", "[2]", "(3)", "*", "†", "²"
NOTE_MARK_MAX = 12  # dấu gọi có epub:type="noteref" mang nhãn bất kỳ, nhưng không dài hơn chừng này ký tự
NOTE_OPEN, NOTE_SEP, NOTE_CLOSE = "\ue000", "\ue001", "\ue002"  # bao quanh dấu gọi chú thích trong dòng đang đọc: `_resolve_notes` quyết giữ hay bỏ rồi gỡ chúng
_NOTE_SPAN = re.compile(NOTE_OPEN + r"(\d+)" + NOTE_SEP + r"(.*?)" + NOTE_CLOSE)
NOTE_TYPES = {"footnote", "endnote", "rearnote"}  # epub:type / role (bỏ "doc-") của MỘT lời chú
NOTE_AREA_TYPES = {"footnotes", "endnotes", "rearnotes"}  # ... của vùng chứa các lời chú (chương Endnotes)
MAX_NOTE_LINES = 40  # đích của dấu gọi dài hơn thế (không phải lời chú, vd cả một chương) thì thôi
NOTE_CONTEXT = 24  # số ký tự chữ đứng trước dấu gọi, cho ví dụ ở bước xem trước
NOTE_EXAMPLES = 3  # số ví dụ ở bước xem trước
NOTE_EXAMPLE_WIDTH = 80  # lời chú trong ví dụ cắt ở chừng này ký tự (ranh giới từ)
SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
HEADINGS = {"h1", "h2", "h3"}
WRAPPERS = {"body", "section", "div", "article", "main"}  # khối bọc cả trang: vai của chúng (trước chữ đầu tiên) là vai của trang
UNSAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')  # ký tự Windows không nhận trong tên file
BROKEN = "không phải file {kind} thật hoặc bị hỏng - thử tải lại, hoặc dùng bản TXT"

# Số của chương: chữ số, số La Mã, hay số viết bằng chữ ("Chương Một", "Hồi thứ hai").
_NUMBER_WORDS = (
    "một|hai|ba|bốn|tư|năm|lăm|sáu|bảy|tám|chín|mười|mươi|mốt|trăm|nghìn|ngàn|linh|lẻ|"
    "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
)
# Số thứ tự chỉ đứng sau "thứ" ("Hồi thứ nhất", "Chương thứ nhì", "Hồi thứ nhứt"): "Hồi nhất định…" là câu văn, không phải tiêu đề.
_ORDINAL_WORDS = "nhất|nhứt|nhì"
CHAPTER_WORDS = "chương|chuong|hồi|hoi|chapter|tiết"


def heading_pattern(words: str) -> re.Pattern[str]:
    """Dòng tiêu đề chương: một trong `words` rồi số ("Chương 12", "Hồi thứ hai", "第三章")."""
    return re.compile(
        r"^\s*(?:"
        r"(?:" + words + r")\s+(?:thứ\s+(?:" + _ORDINAL_WORDS + r")|(?:thứ\s+)?(?:\d+|[ivxlcdm]+|(?:(?:" + _NUMBER_WORDS + r")\s*)+))(?![\w])"
        r"|第\s*[\d一二三四五六七八九十百千零〇两]+\s*[章回]"
        r")",
        re.IGNORECASE,
    )


# DOCX / PDF không có tiêu đề thật thì tách theo dòng "Chương N" / "Chapter N" / "Hồi N" / "Quyển N".
HEADING = heading_pattern(CHAPTER_WORDS + "|quyển|quyen")
# File TXT cả truyện tách theo "Chương N" thôi (như trình tạo sách, webui/txt_split.py): "Quyển N" là tên tập, không phải chương.
TXT_HEADING = heading_pattern(CHAPTER_WORDS)


class ImportFailed(ValueError):
    """Không nhập được; câu chữ cho người dùng đọc (nói lý do và cách khác để đi tiếp)."""


@dataclass
class Chapter:
    title: str
    text: str  # các đoạn cách nhau một dòng trống; KHÔNG gồm tên chương (trừ file TXT: nguyên văn file)
    short: bool = False  # mục EPUB rất ngắn (bìa, trang bản quyền): bị bỏ, trừ khi `import_text(keep_short=True)` đưa nó về như chương CHƯA CHỌN
    name: str = ""  # tên người dùng đặt ở bước xem trước (`select_chapters`); rỗng = `title`. Chỉ là tên: `text` và tên trong chữ không đổi
    matter: str = ""  # có vẻ không phải truyện (bìa, bản quyền, mục lục…): lý do cho người nghe. KHÔNG bị bỏ - chỉ chưa tích sẵn ở bước xem trước


@dataclass
class ImportedBook:
    title: str
    author: str | None = None
    language: str | None = None
    cover_bytes: bytes | None = None
    cover_type: str | None = None  # media type của bìa ("image/jpeg")
    chapters: list[Chapter] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    text_has_title: bool = False  # file TXT: tên chương nằm sẵn trong chữ (EPUB / DOCX / PDF: tên chương là trường riêng)
    credits: list[tuple[int, str]] = field(default_factory=list)  # (số chương, dòng ghi công) - gợi ý, như trong `notes`
    split_offer: int = 0  # file TXT cả truyện: số chương nếu tách theo các dòng "Chương N" (0 = không có gì để tách); người dùng tích mới tách
    split_headings: int = 0  # số dòng "Chương N" ấy; ít hơn `split_offer` một khi chữ trước tiêu đề đầu thành chương "Mở đầu"
    footnote_found: int = 0  # EPUB / DOCX có cấu trúc: số lời chú tìm thấy (đề xuất ở bước xem trước, `FootnoteChoice`); 0 = không có
    footnote_marks: int = 0  # ... trong đó số dấu gọi (số chú thích) nằm trong chữ của sách - ô "Không đọc số chú thích" chỉ có nghĩa khi > 0
    footnote_examples: list[tuple[str, str]] = field(default_factory=list)  # (dấu gọi kèm chữ đứng trước: "…trees²", lời chú) vài ví dụ

    def chapter_source(self, chapter: Chapter) -> str:
        """Chữ của chương như FILE NGUỒN mà Studio đọc: TXT nguyên văn (tên chương nằm sẵn trong chữ); EPUB / DOCX / PDF: tên
        chương, một dòng trống, rồi chữ. Kết thúc bằng một dòng mới. Dùng cho thư mục chương của Studio (`extract`) và cho chữ của
        sách chỉ-chữ (webui/textbook.py) - một nơi. Kotlin: BookImport.chapterSource."""
        body = chapter.text if self.text_has_title else f"{chapter.title}\n\n{chapter.text}"
        return body + "\n"

    def to_dict(self) -> dict[str, Any]:
        """Dạng JSON của bộ ví dụ dùng chung với Kotlin (bìa chỉ ghi cỡ + sha256)."""
        cover = None
        if self.cover_bytes is not None:
            cover = {"type": self.cover_type, "bytes": len(self.cover_bytes),
                     "sha256": hashlib.sha256(self.cover_bytes).hexdigest()}
        return {
            "title": self.title, "author": self.author, "language": self.language, "cover": cover,
            "chapters": [{"title": chapter.title, "text": chapter.text, **({"matter": chapter.matter} if chapter.matter else {})}
                         for chapter in self.chapters],
            "notes": list(self.notes),
            **({"splitOffer": self.split_offer, "splitHeadings": self.split_headings} if self.split_offer else {}),
            **({"footnotes": self.footnote_offer()} if self.footnote_found else {}),
        }

    def footnote_offer(self) -> dict[str, Any]:
        """Đề xuất về chú thích cho bước xem trước (và bộ ví dụ): số lời chú tìm thấy, số dấu gọi nằm trong chữ, vài ví dụ {mark: "…trees²", note}."""
        return {"found": self.footnote_found, "marks": self.footnote_marks,
                "examples": [{"mark": mark, "note": note} for mark, note in self.footnote_examples]}


@dataclass(frozen=True)
class FootnoteChoice:
    """Chú thích trong sách nhập: ĐỀ XUẤT người nghe tích ở bước xem trước (mặc định KHÔNG áp - ABook không tự bỏ hay sửa chữ của truyện;
    bỏ tích là về như cũ). Mặc định (cả hai trống): chữ như trong sách, chỉ lời chú nằm GIỮA chương được đặt xuống cuối chương đó (chữ không đổi,
    chỉ đổi chỗ để không cắt ngang câu) và chương toàn lời chú thì chưa tích. Kotlin: BookImport.FootnoteChoice."""
    hide_marks: bool = False  # không đọc số chú thích (dấu gọi) trong chữ
    notes: str = ""  # "" = như trong sách; "end" = đọc lời chú ở cuối chương chứa dấu gọi (kể cả lời chú ở chương Endnotes riêng); "drop" = bỏ lời chú


NO_FOOTNOTES = FootnoteChoice()  # không tích gì: sách như trong file


def footnote_choice_from_json(raw: Any) -> FootnoteChoice:
    """`footnotes` của lời gọi xem trước / thêm sách: {"hideMarks": bool, "notes": ""|"end"|"drop"}; None = không tích gì. Dạng sai: `ImportFailed`."""
    if raw is None:
        return FootnoteChoice()
    if not isinstance(raw, dict):
        raise ImportFailed("Lựa chọn về chú thích không hợp lệ")
    hide, notes = raw.get("hideMarks", False), raw.get("notes", "")
    if not isinstance(hide, bool) or notes not in ("", "end", "drop"):
        raise ImportFailed("Lựa chọn về chú thích không hợp lệ")
    return FootnoteChoice(hide, notes)


def import_text(path: Path | str, *, split_chapters: bool = False, keep_short: bool = False,
                footnotes: FootnoteChoice | None = None) -> ImportedBook:
    """Mở một thư mục TXT, hay file .epub / .docx / .pdf / .txt. Lỗi dự đoán được là `ImportFailed`. `split_chapters`: file .txt cả
    truyện thì tách thành các chương theo dòng "Chương N" (người dùng tích gợi ý `split_offer`; mặc định cả file là một chương).
    `keep_short`: bước xem trước - mục rất ngắn (`Chapter.short`) vẫn nằm trong danh sách, đúng chỗ của nó trong file, để người dùng tích
    nếu muốn giữ (`default_picks` bỏ chúng); không có thì chúng bị bỏ như trước. `footnotes`: EPUB / DOCX có chú thích - lựa chọn người dùng đã
    tích ở bước xem trước (`FootnoteChoice`); không có thì như trong sách."""
    path = Path(path)
    if path.is_dir():
        book = _txt_folder(path)
    elif path.is_file():
        suffix = path.suffix.casefold()
        if suffix == ".pdf":
            pages, title, author = pdf_pages(path)
            return import_pdf_pages(pages, title_from_filename(path.stem), title, author)
        choice = footnotes or FootnoteChoice()
        reader = {".epub": lambda file: _epub(file, choice), ".docx": lambda file: _docx(file, choice),
                  ".txt": lambda file: _txt_file(file, split_chapters)}.get(suffix)
        if reader is None:
            raise ImportFailed(f"Chưa đọc được file {suffix or 'không có đuôi'} - dùng .epub, .docx, .pdf, .txt hay một thư mục TXT")
        book = reader(path)
    else:
        raise ImportFailed(f"Không thấy {path}.")
    return _finish(book, keep_short, path.name)


def _finish(book: ImportedBook, keep_short: bool = False, source: str = "") -> ImportedBook:
    """Mọi định dạng đi qua đây: Unicode NFC, và gợi ý (không bỏ) dòng ghi công ở đầu chương."""
    book.title = TOC_SUFFIX.sub("", _nfc(book.title)) or _nfc(book.title)  # "Lều chõng — Mục lục" (tên trang mục lục Wikisource) -> "Lều chõng"
    book.author = _nfc(book.author) if book.author else None
    for chapter in book.chapters:
        chapter.title, chapter.text = _nfc(chapter.title).replace(BOM, ""), _nfc(chapter.text).replace(BOM, "")
    book.notes = [_nfc(note) for note in book.notes]
    for chapter in book.chapters:
        chapter.matter = chapter.matter or text_matter(chapter.title, chapter.text)
    if all(chapter.matter or chapter.short for chapter in book.chapters):
        for chapter in book.chapters:  # cả cuốn "không phải truyện" là nhận nhầm (TXT cả truyện mở bằng lời Project Gutenberg): không cờ nào
            chapter.matter = ""
    short = sum(chapter.short for chapter in book.chapters)
    if short:
        book.notes.append(f"{short} mục rất ngắn chưa chọn - tích nếu muốn giữ." if keep_short
                          else f"Bỏ qua {short} mục rất ngắn (bìa, trang bản quyền?).")
    if not keep_short:
        book.chapters = [chapter for chapter in book.chapters if not chapter.short]
    if not book.chapters or not any(chapter.text.strip() or chapter.short for chapter in book.chapters):
        raise ImportFailed(f"Không có chương nào có chữ trong “{source or book.title}” - file rỗng hay mã hoá lạ? "
                           "Với file .txt: thử mở bằng Notepad rồi lưu lại ở dạng UTF-8.")
    matter = sum(bool(chapter.matter) and not chapter.short for chapter in book.chapters)
    if matter and keep_short:
        book.notes.append(f"{matter} mục có vẻ không phải truyện (bìa, bản quyền, mục lục…) chưa chọn - tích nếu muốn nghe.")
    if len(book.chapters) > 1:
        # File TXT rỗng (hay chỉ có khoảng trắng) không thành chương - nói ra, để số chương ít hơn số file có lý do. Mục rất ngắn mà chỉ có
        # tên (trang đề tựa) thì ở lại: người dùng quyết có tích nó không.
        book.notes += [f"Bỏ qua mục trống: {chapter.title}" for chapter in book.chapters if not chapter.text.strip() and not chapter.short]
        book.chapters = [chapter for chapter in book.chapters if chapter.text.strip() or chapter.short]
    for number, chapter in enumerate(book.chapters, start=1):
        # Tên chương tính là một dòng của chương (cửa sổ 6 dòng đầu), như file chương mà Studio đọc.
        for line in credit_suggestions(book.chapter_source(chapter)):
            book.credits.append((number, line))
            book.notes.append(f"Gợi ý: chương {number} có dòng ghi công ở đầu - “{line}”. Có thể bỏ khỏi phần đọc, nhưng ABook không tự bỏ.")
    return book


def default_picks(book: ImportedBook) -> list[tuple[int, str]]:
    """Lựa chọn chương mặc định của bước xem trước: mọi chương trừ mục rất ngắn (`Chapter.short`) và mục có vẻ không phải truyện
    (`Chapter.matter`). [(số chương 1-based, tên mới "")]. Kotlin: BookImport.defaultPicks."""
    return [(number, "") for number, chapter in enumerate(book.chapters, start=1) if not chapter.short and not chapter.matter]


def select_chapters(book: ImportedBook, picks: list[tuple[int, str]]) -> ImportedBook:
    """Cuốn chỉ gồm các chương người dùng tích ở bước xem trước, theo THỨ TỰ TRONG FILE (không theo thứ tự `picks`). `picks`: (số chương
    1-based trong `book.chapters`, tên mới - rỗng hay trùng tên cũ là giữ tên cũ). Chỉ đổi TÊN (`Chapter.name`, tên hiện ở thư viện / trang sách, như
    đổi tên chương ở lớp sửa): chữ của chương không đổi, kể cả dòng tên nằm trong chữ (TXT, đầu chương EPUB). `credits` đánh số lại theo cuốn mới. Không chọn gì, hay số chương không có / lặp: `ImportFailed`. Kotlin: BookImport.selectChapters."""
    if not picks:
        raise ImportFailed("Chọn ít nhất một chương để thêm vào thư viện")
    numbers = [number for number, _name in picks]
    if len(set(numbers)) != len(numbers) or any(not 1 <= number <= len(book.chapters) for number in numbers):
        raise ImportFailed("Danh sách chương đã chọn không khớp với file - mở lại file rồi chọn lại")
    chapters, renumbered = [], {}
    for position, (number, name) in enumerate(sorted(picks), start=1):
        chapter, name = book.chapters[number - 1], _nfc(" ".join(name.split()))
        chapters.append(replace(chapter, name=name if name != chapter.title else ""))
        renumbered[number] = position
    return replace(book, chapters=chapters, credits=[(renumbered[number], line) for number, line in book.credits if number in renumbered])


def credit_suggestions(source: str) -> list[str]:
    """Dòng ghi công (người dịch, biên tập…) ở đầu một chương, `source` như file chương (`ImportedBook.chapter_source`): GỢI Ý để
    người nghe chọn bỏ khỏi phần đọc (lớp sửa `skip`), không bao giờ tự bỏ. Luật là của Studio (`text_processing.credit_lines`);
    chỉ đưa phần đầu chương - chuẩn hoá cả chương chỉ để xem 6 dòng là phần chậm nhất của cuốn hơn nghìn chương. Kotlin:
    BookImport.creditSuggestions."""
    from .text_processing import credit_lines

    return credit_lines("\n".join(source.split("\n", CREDIT_HEAD_LINES)[:CREDIT_HEAD_LINES]))


BOM = "\ufeff"  # dấu BOM lọt giữa chữ (nối nhiều file): vô hình, nhưng làm "Chương 1" ở đầu dòng không còn là tiêu đề


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def title_from_filename(stem: str) -> str:
    """Tên sách đặt từ tên file/thư mục: "_" và chuỗi "--" trở lên là dấu cách của người đặt tên file ("Tam_Quoc__Dien_Nghia" ->
    "Tam Quoc Dien Nghia"); một dấu "-" đơn là của tên ("Re-Zero") và hoa thường giữ nguyên. Không còn gì thì giữ nguyên `stem`.
    Kotlin cùng luật: BookImport.titleFromFilename (bảng ví dụ chung expected/name_title.json)."""
    return " ".join(re.sub(r"_+|-{2,}", " ", stem).split()) or stem


def clip_title(text: str, limit: int) -> str:
    """Tên hiển thị dài quá `limit` ký tự thì cắt ở ranh giới từ rồi thêm "…" (cắt trơn để lại "…nư" giữa từ). CHỈ cho tên chương /
    tên file đặt từ dòng đầu - chữ truyện không qua đây."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if not text[limit].isspace():  # nhát cắt rơi giữa một từ: lùi về dấu cách gần nhất (nếu từ cuối không chiếm quá nửa)
        space = cut.rfind(" ")
        if space >= limit // 2:
            cut = cut[:space]
    return cut.rstrip(" .,;:!?-–—") + "…"


def _words(text: str) -> str:
    """Gộp mọi khoảng trắng thành một dấu cách, Unicode NFC (PDF hay mang chữ tiếng Việt dạng rời; luật nhận tiêu đề cần dạng gộp)."""
    return _nfc(" ".join(text.split()))


# Phần không phải truyện (bìa, trang tên sách, bản quyền, mục lục…): KHÔNG bỏ - chỉ chưa tích sẵn ở bước xem trước, kèm lý do (`Chapter.matter`).
MATTER_TYPES = (  # epub:type / role của trang -> lý do; cụ thể trước, chung sau
    ("cover", "Trang bìa"), ("titlepage", "Trang tên sách"), ("halftitlepage", "Trang tên sách"), ("copyright-page", "Trang bản quyền"),
    ("imprint", "Trang bản quyền"), ("colophon", "Trang bản quyền"), ("toc", "Mục lục"), ("landmarks", "Mục lục"),
    ("endnotes", "Chú thích"), ("footnotes", "Chú thích"), ("rearnotes", "Chú thích"),
    ("frontmatter", "Phần đầu sách"), ("backmatter", "Phần cuối sách"),
)
MATTER_NAMES = {"cover": "Trang bìa", "title": "Trang tên sách", "titlepage": "Trang tên sách", "toc": "Mục lục", "nav": "Mục lục",
                "copyright": "Trang bản quyền", "license": "Trang bản quyền", "colophon": "Trang bản quyền", "imprint": "Trang bản quyền",
                "about": "Trang giới thiệu", "endnotes": "Chú thích", "footnotes": "Chú thích"}
# Tên file trong gói: đúng một từ ấy, chỉ kèm số / dấu nối / "page" ("cover.xhtml", "001_titlepage", "copyright-page") - "chapter_title_3" không tính.
_MATTER_NAME = re.compile(r"[\W_\d]*(" + "|".join(MATTER_NAMES) + r")(?:[\W_]*page)?[\W_\d]*")
_TOC_TITLES = {"mục lục", "muc luc", "contents", "table of contents"}
_NOTE_TITLES = {"chú thích", "endnotes", "end notes", "footnotes", "notes"}  # tên chương toàn lời chú
TOC_SUFFIX = re.compile(r"\s+[—–-]\s*(?:mục lục|muc luc)\s*$", re.IGNORECASE)
MATTER_HEAD = 400  # số ký tự đầu chương xét lời Project Gutenberg / Wikisource


def name_matter(href: str) -> str:
    """Lý do "không phải truyện" theo tên file trong gói EPUB (`MATTER_NAMES`); "" nếu không. Kotlin: BookImport.nameMatter."""
    match = _MATTER_NAME.fullmatch(posixpath.splitext(posixpath.basename(href))[0].casefold())
    return MATTER_NAMES[match.group(1)] if match else ""


def text_matter(title: str, text: str) -> str:
    """Lý do "không phải truyện" theo chữ - mọi định dạng: tên / dòng đầu là "Mục lục", "Contents", "Chú thích", "Endnotes"; lời của Project Gutenberg hay
    Wikisource ở đầu chương. "" nếu không. Kotlin: BookImport.textMatter."""
    head = f"{title}\n{text[:MATTER_HEAD]}".casefold()
    first = first_text_line(text).casefold().rstrip(" :.")
    clean = title.casefold().strip()
    if clean in _TOC_TITLES or first in _TOC_TITLES or clean.endswith(("— mục lục", "- mục lục")):
        return "Mục lục"
    if clean in _NOTE_TITLES or first in _NOTE_TITLES:
        return "Chú thích"
    if "project gutenberg" in head:
        return "Trang của Project Gutenberg"
    if "wikisource" in head:
        return "Trang của Wikisource"
    return ""


# --- Thư mục TXT -------------------------------------------------------------------------------------------------------

def _clean_text(text: str) -> str:
    """Đổi định dạng thôi: xuống dòng \\n, bỏ khoảng trắng cuối dòng, tối đa một dòng trống liền nhau, bỏ dòng trống hai đầu."""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").replace(BOM, "").split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip("\n")


# Bảng mã đoán được (`io_utils.decode_text`) không phải UTF: báo người dùng - đoán sai thì chữ lạ, và họ biết cách sửa.
MEANINGLESS_NAME = re.compile(r"index_split_\d+|untitled(?:[\s_-]*\d+)?|part\d+|text\d+|split_\d+", re.IGNORECASE)  # tên file do công cụ đặt
ENCODING_NAMES = {"cp1258": "tiếng Việt Windows (cp1258)", "windows-1252": "Tây Âu (cp1252)", "gb18030": "tiếng Trung (GB18030)"}


def _txt_chapter(path: Path) -> tuple[Chapter, str]:
    """Một file TXT là một chương (cùng bảng mã đã đọc). Tên chương: dòng đầu nếu nó là dòng tiêu đề ("Chương 1: Buổi sáng" - đúng thứ
    người nghe thấy ở đầu chương), không thì tên file ("01.txt" -> "Chương 1")."""
    from .webui.humanize import chapter_title

    text, encoding = decode_text(path.read_bytes())
    text = _clean_text(text)
    first = next((line.strip() for line in text.split("\n") if line.strip()), "")
    if is_heading_line(first):
        return Chapter(first, text), encoding
    # Tên file vô nghĩa ("index_split_003", "Untitled") mà dòng đầu trông là tiêu đề ("Sương sớm"): tên chương là dòng ấy.
    named = MEANINGLESS_NAME.fullmatch(path.stem) and title_from_line(first)
    return Chapter(named or chapter_title(path.stem), text), encoding


def _encoding_notes(encodings: Iterable[str]) -> list[str]:
    found = set(encodings)
    names = [name for encoding, name in ENCODING_NAMES.items() if encoding in found]
    return [f"File chữ không phải UTF-8 - đã đọc theo bảng mã {', '.join(names)}. Nếu chữ lạ, lưu lại file dạng UTF-8 rồi nhập lại."] if names else []


def _txt_folder(folder: Path) -> ImportedBook:
    files = discover_txt_files(folder)  # đúng luật của Studio: các .txt nằm ngay trong thư mục, xếp tên tự nhiên
    if not files:
        raise ImportFailed("Thư mục này không có file .txt nào nằm ngay bên trong")
    read = [_txt_chapter(file) for file in files]
    return ImportedBook(title=title_from_filename(folder.resolve().name), chapters=[chapter for chapter, _ in read], text_has_title=True,
                        notes=_encoding_notes(encoding for _, encoding in read))


def _txt_file(path: Path, split: bool = False) -> ImportedBook:
    """Một file TXT là một chương - trừ khi nó là CẢ truyện (>= 2 dòng "Chương N") và người dùng tích tách: `split_txt_chapters`."""
    chapter, encoding = _txt_chapter(path)
    book = ImportedBook(title=title_from_filename(path.stem), chapters=[chapter], text_has_title=True, notes=_encoding_notes([encoding]))
    parts = split_txt_chapters(chapter.text)
    book.split_offer = len(parts)
    # Chương tách ra từ một dòng tiêu đề mang tên dòng ấy - không bao giờ trùng tên chương "Mở đầu".
    book.split_headings = sum(part.title != PREAMBLE for part in parts)
    if parts:
        # Cả truyện: tên sách gợi ý là dòng tiêu đề đầu file ("Ngọn đèn cuối cùng"), không phải tên file ("ngon_den_cuoi_cung").
        book.title = title_from_line(first_text_line(chapter.text)) or book.title
        lines = chapter.text.split("\n")
        alone = title_only_preamble(lines, next(iter(_txt_cuts(lines)), 0))
        if split and alone:
            book.notes.append(f"Dòng đầu “{alone}” là tên truyện - dùng làm tên sách, không đọc thành một chương.")
    title, author = gutenberg_header(chapter.text)
    book.title, book.author = title or book.title, author or None
    if split and parts:
        book.chapters = parts
    return book


_PG_FIELD = re.compile(r"(title|author)\s*:\s*(.+)", re.IGNORECASE)
PG_HEAD_LINES = 60  # số dòng đầu file xét phần đầu của Project Gutenberg (tới dòng "*** START OF")


def gutenberg_header(text: str) -> tuple[str, str]:
    """File TXT của Project Gutenberg mở bằng "The Project Gutenberg eBook of …" rồi các dòng "Title: …", "Author: …": (tên, tác giả) từ
    đó - không thì ("", ""). Tên sách không bao giờ là cả câu "The Project Gutenberg eBook of …". Kotlin: BookImport.gutenbergHeader."""
    lines = text.split("\n", PG_HEAD_LINES)[:PG_HEAD_LINES]
    if "project gutenberg" not in first_text_line("\n".join(lines)).casefold():
        return "", ""
    found: dict[str, str] = {}
    for line in lines:
        if line.lstrip().startswith("***"):
            break
        match = _PG_FIELD.fullmatch(line.strip())
        if match:
            found.setdefault(match.group(1).casefold(), _words(match.group(2)))
    return found.get("title", ""), found.get("author", "")


def first_text_line(text: str) -> str:
    """Dòng đầu có chữ của `text`, bỏ khoảng trắng hai đầu; "" nếu không có."""
    return next((line.strip() for line in text.split("\n") if line.strip()), "")


def title_from_line(line: str) -> str:
    """`line` nếu nó trông là TIÊU ĐỀ truyện: ngắn (<= 80 ký tự, <= 12 từ), có chữ, không bắt đầu bằng gạch lời thoại / ngoặc, không
    kết bằng dấu câu, không phải dòng "Chương N"; dấu `#` Markdown đầu dòng bỏ đi. Không thì "". Một luật cho trình tạo sách (tên sách
    gợi ý của file cả truyện), "Thêm sách từ file…" và việc tách file cả truyện. Kotlin: BookImport.titleFromLine."""
    first = line.strip().lstrip("#").strip()
    if not first or len(first) > 80 or len(first.split()) > 12 or first.casefold() in _TOC_TITLES:
        return ""
    if is_heading_line(first) or first[0] in "-–—“\"‘'«(" or first[-1] in ".!?…,;:\"”’»)":
        return ""
    return first if any(ch.isalpha() for ch in first) else ""


def title_only_preamble(lines: list[str], cut: int) -> str:
    """Chữ trước tiêu đề chương đầu tiên (`lines[:cut]`) chỉ là MỘT dòng và dòng ấy trông là tiêu đề truyện: trả tên truyện đó. Nó là tên
    sách chứ không phải một chương "Mở đầu" 4 chữ (soát UX a8 02-10); không thì "" - chữ dẫn nhiều dòng (tên + giới thiệu) vẫn là "Mở đầu"."""
    kept = [line for line in lines[:cut] if line.strip()]
    return title_from_line(kept[0]) if len(kept) == 1 else ""


def _txt_cuts(lines: list[str]) -> list[int]:
    """Các dòng tiêu đề "Chương N" của file TXT cả truyện, TRỪ mục lục: một chuỗi >= 2 tiêu đề liền nhau không có chữ nào giữa chúng
    ("MỤC LỤC / Chương 1… / Chương 2…" đầu file) không phải chương - chúng ở lại trong chữ dẫn, không thành những chương rỗng.
    Kotlin: BookImport.txtCuts."""
    cuts = [index for index, line in enumerate(lines) if is_heading_line(line, TXT_HEADING)]
    kept: list[int] = []
    run: list[int] = []  # các tiêu đề liền nhau chưa có chữ
    for start, end in zip(cuts, [*cuts[1:], len(lines)]):
        run.append(start)
        if any(line.strip() for line in lines[start + 1:end]):
            if len(run) <= 2:  # tiêu đề lẻ không có chữ vẫn là chương như trước; chỉ chuỗi >= 2 tiêu đề trống (mục lục) bị bỏ qua
                kept += run
            else:
                kept.append(start)
            run = []
    return kept + (run if len(run) == 1 else [])


def split_txt_chapters(text: str) -> list[Chapter]:
    """Chữ (đã `_clean_text`) của một file TXT cả truyện -> các chương cắt ở đầu mỗi dòng tiêu đề "Chương N" (cùng luật nhận tiêu đề
    với trình tạo sách, `txt_split`: "Quyển N" không phải tiêu đề). Chữ giữ nguyên từng dòng, tiêu đề nằm trong chữ của chương; chữ
    đứng trước tiêu đề đầu tiên thành chương "Mở đầu" (không bỏ) - trừ khi nó chỉ là MỘT dòng tên truyện (`title_only_preamble`): dòng ấy
    là tên sách (`_txt_file`), người nghe được báo ở ghi chú. Dưới hai tiêu đề: [] (không có gì để tách). Kotlin: splitTxtChapters."""
    lines = text.split("\n")
    cuts = _txt_cuts(lines)
    if len(cuts) < 2:
        return []
    # Chữ dẫn chỉ là một dòng tên truyện thì không thành chương "Mở đầu" - nó là tên sách (`title_only_preamble`).
    lead = any(line.strip() for line in lines[: cuts[0]]) and not title_only_preamble(lines, cuts[0])
    chapters = [Chapter(PREAMBLE, "\n".join(lines[: cuts[0]]).strip("\n"))] if lead else []
    for position, start in enumerate(cuts):
        end = cuts[position + 1] if position + 1 < len(cuts) else len(lines)
        chapters.append(Chapter(lines[start].strip(), "\n".join(lines[start:end]).strip("\n")))
    return chapters


# --- XML an toàn -------------------------------------------------------------------------------------------------------

_XML_ENTITIES = {"amp", "lt", "gt", "quot", "apos"}
_NAMED_ENTITY = re.compile(rb"&([A-Za-z][A-Za-z0-9]{0,31});")


def _html_entities_as_numbers(raw: bytes) -> bytes:
    """Mục lục / NCX hay mang thực thể HTML (`&nbsp;`) mà XML không biết - ElementTree sẽ coi cả cuốn là hỏng. Đổi chúng thành số
    (`&#160;`) trước khi đọc, như bộ đọc thẻ của bản Kotlin vẫn hiểu chúng. Tên lạ thì để nguyên (vẫn là file hỏng)."""
    def numeric(match: re.Match[bytes]) -> bytes:
        name = match.group(1).decode("ascii")
        value = None if name in _XML_ENTITIES else html.entities.html5.get(f"{name};")
        return match.group(0) if value is None else "".join(f"&#{ord(char)};" for char in value).encode("ascii")

    return _NAMED_ENTITY.sub(numeric, raw) if b"&" in raw else raw


def _xml(raw: bytes, kind: str = "EPUB") -> ElementTree.Element:
    head = raw[:4096].decode("utf-8", errors="replace")
    if "<!ENTITY" in head.upper():
        raise ImportFailed("có nội dung XML lạ (khai báo entity) - không mở để giữ an toàn máy")
    try:
        return ElementTree.fromstring(_html_entities_as_numbers(raw))
    except ElementTree.ParseError as error:
        raise ImportFailed(BROKEN.format(kind=kind)) from error


class _Zip(zipfile.ZipFile):
    """Gói EPUB / DOCX: tra mục theo tên chịu được Unicode dạng rời (NFD - zip làm trên macOS) khi manifest viết dạng gộp (hay ngược lại)."""

    _by_nfc: dict[str, zipfile.ZipInfo] | None = None

    def member(self, name: str) -> zipfile.ZipInfo | None:
        """Mục `name`, hay None nếu gói không có. Kotlin: BookImport.member."""
        try:
            return self.getinfo(name)
        except KeyError:
            pass
        if self._by_nfc is None:  # một lần cho mỗi gói: cuốn nghìn chương NFD không quét lại nghìn lần
            self._by_nfc = {_nfc(info.filename): info for info in self.infolist()}
        return self._by_nfc.get(_nfc(name))


def _read(book: _Zip, name: str, kind: str = "EPUB") -> bytes:
    info = book.member(name)
    if info is None:
        raise ImportFailed(BROKEN.format(kind=kind))
    if info.file_size > MAX_MEMBER:
        raise ImportFailed(f"có một phần quá lớn (trên 20 MB) - không giống {kind} truyện")
    return book.read(info)


def _open_zip(path: Path, kind: str) -> _Zip:
    try:
        book = _Zip(path)
    except (OSError, zipfile.BadZipFile) as error:
        raise ImportFailed(BROKEN.format(kind=kind)) from error
    if sum(info.file_size for info in book.infolist()) > MAX_TOTAL:
        book.close()
        raise ImportFailed(f"quá lớn khi giải nén (trên 300 MB) - không giống {kind} truyện")
    return book


# --- EPUB --------------------------------------------------------------------------------------------------------------

# Chữ ẩn của nguồn HTML không phải chữ truyện người đọc thấy: bỏ là đổi định dạng, không phải sửa chữ. Thẻ rỗng (void) không bao giờ mở
# vùng ẩn - `<img aria-hidden="true">` không có thẻ đóng, ẩn nó không được nuốt phần còn lại của trang.
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "image", "input", "link", "meta", "source", "track", "wbr"}
HIDDEN_TAGS = {"noscript", "rt", "rp"}  # rt / rp của ruby: cách đọc in nhỏ trên chữ gốc - đọc chữ gốc một lần
_HIDDEN_STYLE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.IGNORECASE)
_SIMPLE_SELECTOR = re.compile(r"([a-z][\w-]*)?((?:[.#][\w-]+)*)", re.IGNORECASE)


@dataclass(frozen=True)
class _Hidden:
    """Một bộ chọn CSS đơn giản mà stylesheet trong gói ẩn đi (`display:none` / `visibility:hidden`): thẻ, id, các lớp - rỗng = mọi."""
    tag: str
    id: str
    classes: frozenset[str]


def css_hidden(css: str) -> list[_Hidden]:
    """Các bộ chọn đơn giản (`.lop`, `#id`, `the`, `the.lop`, `.a.b`) mà `css` ẩn đi. Bỏ qua bộ chọn phức tạp (khoảng trắng, >, :, [ ])
    và mọi khối @ (@media print…: không phải thứ người đọc thấy trên màn hình). Kotlin: BookImport.cssHidden."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    found: list[_Hidden] = []
    depth, start, selector = 0, 0, ""
    for index, char in enumerate(css):
        if char == "{":
            if depth == 0:
                selector, start = css[start:index].strip(), index + 1
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0:
                if not selector.startswith("@") and _HIDDEN_STYLE.search(css[start:index]):
                    for one in selector.split(","):
                        match = _SIMPLE_SELECTOR.fullmatch(one.strip())
                        if match and one.strip():
                            parts = re.findall(r"[.#][\w-]+", match.group(2) or "")
                            found.append(_Hidden((match.group(1) or "").casefold(), next((part[1:] for part in parts if part[0] == "#"), ""),
                                                 frozenset(part[1:] for part in parts if part[0] == ".")))
                start = index + 1
    return found


def _hides(tag: str, attrs: dict[str, str], rules: list[_Hidden]) -> bool:
    """Phần tử này ẩn với người đọc: `hidden`, `aria-hidden="true"`, style nội tuyến display:none / visibility:hidden, <noscript>, rt / rp
    của ruby, số trang (epub:type="pagebreak" / role="doc-pagebreak"), hay một luật CSS đơn giản của gói (`css_hidden`). Kotlin: BookImport.hides."""
    if tag in VOID:
        return False
    if tag in HIDDEN_TAGS or "hidden" in attrs or attrs.get("aria-hidden", "").strip().casefold() == "true":
        return True
    if _HIDDEN_STYLE.search(attrs.get("style", "")) or "pagebreak" in _types(attrs.items()):
        return True
    classes = set(attrs.get("class", "").split())
    return any((not rule.tag or rule.tag == tag) and (not rule.id or rule.id == attrs.get("id")) and rule.classes <= classes
               for rule in rules)


@dataclass
class _Mark:
    """Một dấu gọi chú thích trong chữ (liên kết tới lời chú): đích, nhãn ("2", "[1]"), chữ đứng ngay trước, id của chính dấu, dòng chứa nó."""
    href: str
    label: str
    before: str
    id: str
    line: int


class _Text(HTMLParser):
    """Chữ của một trang XHTML: mỗi khối (đoạn, tiêu đề, dòng danh sách, <br>) một dòng; bỏ script/style/head và chữ ẩn (`_hides`).
    Chú thích: dấu gọi (`_Mark`) nằm trong dòng giữa NOTE_OPEN…NOTE_CLOSE (`_resolve_notes` gỡ chúng: giữ hay bỏ chữ của dấu); lời chú là
    những khoảng dòng (`spans` theo id, `notes` / `areas` theo kiểu epub:type / role)."""

    def __init__(self, hidden: list[_Hidden] | None = None, backlinks_hidden: bool = False) -> None:
        super().__init__(convert_charrefs=True)
        self._rules = hidden or []
        self._backlinks_hidden = backlinks_hidden  # nút quay lại "↩︎" của lời chú (epub:type="backlink"): ẩn khi lời chú được đặt về cuối chương
        self._stack: list[list[Any]] = []  # khối đang mở: [thẻ, dòng bắt đầu, [id…], kiểu: 0 thường / 1 lời chú / 2 vùng lời chú]
        self._links: list[dict[str, Any]] = []  # <a> đang mở: href, chỗ bắt đầu trong `_current`, có noteref / backlink, id, đang trong <sup> / chứa <sup>
        self.spans: dict[str, tuple[int, int]] = {}  # id -> [dòng đầu, dòng cuối) của khối chứa phần tử có id ấy
        self.notes: list[tuple[int, int]] = []  # khoảng dòng của từng lời chú có kiểu (epub:type footnote / endnote / rearnote)
        self.areas: list[tuple[int, int]] = []  # ... của vùng toàn lời chú (epub:type endnotes…)
        self.marks: list[_Mark] = []
        self.note_lines: set[int] = set()  # các dòng thuộc lời chú (`_resolve_notes`)
        self._hidden_tag = ""  # thẻ mở vùng ẩn đang bỏ qua, và số thẻ cùng tên đang mở bên trong nó
        self._hidden_depth = 0
        self._cap = ""  # chữ cái đầu chương vẽ bằng ảnh (<img alt="M">): chờ xem chữ ngay sau có dính liền không
        self._pre = 0  # trong <pre>: xuống dòng của nguồn là xuống dòng thật (thơ, thư), không gộp
        self._sup: list[int] = []  # chỗ (số mảnh trong `_current`) bắt đầu mỗi <sup> đang mở
        self.lines: list[str] = []
        self.heading = ""
        self.headings: list[tuple[int, str]] = []  # (dòng của tiêu đề, chữ): mọi tiêu đề h1-h3 có chữ, theo thứ tự
        self.anchors: dict[str, int] = {}  # id / <a name> -> chỉ số dòng bắt đầu từ chỗ ấy (mục lục trỏ #mảnh vào đây)
        self.images = 0
        self.types: set[str] = set()  # vai (epub:type / role) của <body> và các khối bọc ngoài trước chữ đầu tiên ("frontmatter", "cover"…)
        self._current: list[str] = []
        self._skip = 0
        self._in_heading = 0

    def _flush(self) -> None:
        self._cap = ""
        self._sup = [0] * len(self._sup)  # dòng mới: <sup> đang mở bắt đầu từ đầu dòng (không còn chữ đứng trước để tách)
        for link in self._links:
            link["start"] = 0
        line = _words("".join(self._current))
        if line:
            self.lines.append(line)
        self._current = []

    def handle_starttag(self, tag: str, attrs) -> None:  # chữ ký của HTMLParser
        if self._hidden_depth:
            self._hidden_depth += tag == self._hidden_tag
            self._anchor(tag, attrs, own=False)
            return
        if not self._skip and (_hides(tag, {name: value or "" for name, value in attrs}, self._rules)
                               or (self._backlinks_hidden and tag == "a" and "backlink" in _types(attrs))):
            if tag in BLOCKS:
                self._flush()
            self._hidden_tag, self._hidden_depth = tag, 1
            self._anchor(tag, attrs, own=False)
            return
        if tag in {"script", "style", "head", "title"}:
            self._skip += 1
        elif tag in {"img", "image"}:
            self.images += 1
            alt = next((value or "" for name, value in attrs if name == "alt"), "")
            self._cap = alt if len(alt) == 1 and alt.isalpha() else ""
        elif tag in {"br", "hr"}:  # hr: ngắt cảnh - ít nhất là ranh giới đoạn, không để hai cảnh dính vào nhau
            self._flush()
        elif tag in CELLS:
            self._current.append(" ")
        elif tag == "sup":
            self._sup.append(len(self._current))
            if self._links:
                self._links[-1]["sup"] = True
        elif tag == "a":
            fields = {name: value or "" for name, value in attrs}
            kinds = _types(attrs)
            self._links.append({"href": fields.get("href", "").strip(), "start": len(self._current), "noteref": "noteref" in kinds,
                                "id": fields.get("id", ""), "in_sup": bool(self._sup), "sup": False})
        elif tag in BLOCKS:
            self._flush()
            if tag in HEADINGS:
                self._in_heading += 1
            self._pre += tag == "pre"
        if tag in BLOCKS or tag in LISTS:
            kinds = _types(attrs)
            self._stack.append([tag, len(self.lines), [], 1 if kinds & NOTE_TYPES else 2 if kinds & NOTE_AREA_TYPES else 0])
        if tag in WRAPPERS and not self.lines and not "".join(self._current).strip():
            self.types |= _types(attrs)
        self._anchor(tag, attrs)

    def _anchor(self, tag: str, attrs, own: bool = True) -> None:
        """Mảnh của thẻ (`id` của mọi phần tử, `name` của <a>) - kể cả trong vùng ẩn: mục lục trỏ vào đó vẫn là một chỗ trong trang.
        `own`: phần tử không nằm trong vùng ẩn - id của nó thuộc khối đang mở (đích của dấu gọi chú thích: `spans`)."""
        if not self._skip:
            for name, value in attrs:
                key = name.partition(":")[2] or name  # như bản Kotlin: bỏ tiền tố ("xml:id" thành "id")
                if value and (key == "id" or (tag == "a" and key == "name")):
                    self.anchors.setdefault(value, len(self.lines))
                    if own and self._stack:
                        self._stack[-1][2].append(value)

    def _close_block(self, tag: str) -> None:
        """Khối `tag` đóng: các khối mở bên trong nó (thẻ không đóng) đóng cùng; mỗi khối ghi khoảng dòng của nó cho id / kiểu lời chú."""
        for at in range(len(self._stack) - 1, -1, -1):
            if self._stack[at][0] == tag:
                while len(self._stack) > at:
                    self._finish_block(self._stack.pop())
                return

    def _finish_block(self, block: list[Any]) -> None:
        _tag, start, ids, kind = block
        end = len(self.lines)
        if end > start:
            for value in ids:
                self.spans.setdefault(value, (start, end))
            if kind == 1:
                self.notes.append((start, end))
            elif kind == 2:
                self.areas.append((start, end))

    def handle_endtag(self, tag: str) -> None:
        if self._hidden_depth:
            if tag == self._hidden_tag:
                self._hidden_depth -= 1
                if not self._hidden_depth and tag in BLOCKS:
                    self._flush()
            return
        if tag in {"script", "style", "head", "title"}:
            self._skip = max(0, self._skip - 1)
        elif tag in CELLS:
            self._current.append(" ")
        elif tag == "sup" and self._sup:
            at = self._sup.pop()
            before, mark = "".join(self._current[:at]), "".join(self._current[at:]).strip()
            if NOTE_MARK.fullmatch(mark) and before[-1:].isalpha() and not (mark in {"2", "3"} and UNIT_POWER.search(before)):
                self._current.insert(at, " ")  # (dấu gọi là liên kết thì `_end_link` đã tự đặt dấu cách trong NOTE_OPEN…NOTE_CLOSE: mark không còn khớp)
        elif tag == "a" and self._links:
            self._end_link(self._links.pop())
        elif tag in BLOCKS:
            self._pre -= tag == "pre" and self._pre > 0
            if tag in HEADINGS and self._in_heading:
                self._in_heading -= 1
                text = _words("".join(self._current))
                if text:
                    self.headings.append((len(self.lines), text))
                if not self.heading:
                    self.heading = text
            self._flush()
            self._close_block(tag)
        elif tag in LISTS:
            self._close_block(tag)

    def handle_data(self, data: str) -> None:
        if not self._skip and not self._hidden_depth:
            if self._cap and data:
                # Chữ cái đầu là ảnh ("M" + "ọi chuyện…"): chỉ ghép khi chữ ngay sau dính liền - ảnh minh hoạ, chữ cách ra thì không.
                data, self._cap = (self._cap + data if data[0].isalpha() else data), ""
            if self._pre:
                first, *rest = data.split("\n")
                self._current.append(first)
                for line in rest:
                    self._flush()
                    self._current.append(line)
                return
            self._current.append(data)

    def _end_link(self, link: dict[str, Any]) -> None:
        """</a>: nếu liên kết là dấu gọi chú thích - epub:type="noteref" / role="doc-noteref", hay nhãn như số trong <sup> (`<sup><a href="#fn1">1</a></sup>`,
        `<a href="#fn1"><sup>1</sup></a>`) trỏ vào một mảnh (#id) - bọc chữ của nó trong NOTE_OPEN…NOTE_CLOSE (kèm dấu cách tách khỏi chữ đứng trước)
        và ghi `_Mark`; có phải dấu gọi thật hay không (đích có là lời chú) còn do `_resolve_notes` quyết."""
        href, start = link["href"], link["start"]
        if "#" not in href or _EXTERNAL.match(href):
            return
        text = "".join(self._current[start:])
        label = _words(text)
        if not label or len(label) > NOTE_MARK_MAX:
            return
        if not (link["noteref"] or (NOTE_LABEL.fullmatch(label) and (link["in_sup"] or link["sup"]))):
            return
        before = "".join(self._current[:start])
        lead = "" if text[:1].isspace() or not before[-1:].isalpha() or (label in {"2", "3"} and UNIT_POWER.search(before)) else " "
        self._current[start:] = [f"{NOTE_OPEN}{len(self.marks)}{NOTE_SEP}{lead}", *self._current[start:], NOTE_CLOSE]
        self.marks.append(_Mark(href, label, _note_context(before), link["id"], len(self.lines)))

    def close(self) -> None:
        super().close()
        self._flush()
        while self._stack:
            self._finish_block(self._stack.pop())


_EXTERNAL = re.compile(r"[a-z][a-z0-9+.-]*:", re.IGNORECASE)  # liên kết ra ngoài (http:, mailto:) không phải dấu gọi chú thích


def _note_context(before: str) -> str:
    """Chữ đứng ngay trước một dấu gọi (tối đa NOTE_CONTEXT ký tự, không cắt giữa từ) - ngữ cảnh cho ví dụ ở bước xem trước. Kotlin: BookImport.noteContext."""
    flat = " ".join(_NOTE_SPAN.sub("", before).split())  # số của dấu gọi đứng trước không phải chữ truyện
    if len(flat) <= NOTE_CONTEXT:
        return flat
    tail = flat[-NOTE_CONTEXT:]
    if flat[-NOTE_CONTEXT - 1] != " " and " " in tail:
        tail = tail[tail.index(" ") + 1:]
    return tail


def _types(attrs: Iterable[tuple[str, str | None]]) -> set[str]:
    """Vai của một phần tử: các từ của `epub:type` (thuộc tính `type` có tiền tố / không gian tên - `<ol type="a">` không tính) và
    của `role` bỏ tiền tố "doc-" (`role="doc-pagebreak"` = "pagebreak"). Kotlin: BookImport.types."""
    found: set[str] = set()
    for key, value in attrs:
        local = key.rpartition("}")[2]
        prefixed = local != key or ":" in local
        local = local.rpartition(":")[2].casefold()
        if value and ((local == "type" and prefixed) or local == "role"):
            found.update(token.casefold().removeprefix("doc-") for token in value.split())
    return found


_DECLARED_ENCODING = re.compile(rb"""<\?xml[^>]*?encoding\s*=\s*["']([\w.:-]+)|<meta[^>]*?charset\s*=\s*["']?([\w.:-]+)""", re.IGNORECASE)
ENCODING_ALIASES = {"gb2312": "gb18030", "gbk": "gb18030", "x-gbk": "gb18030", "iso-8859-1": "windows-1252", "latin1": "windows-1252",
                    "us-ascii": "windows-1252", "ascii": "windows-1252"}  # như trình duyệt (WHATWG): nhãn cũ đọc bằng bảng mã rộng hơn


def markup_text(raw: bytes) -> str:
    """Chữ của một trang XHTML: UTF-8 (hay UTF-16 có BOM) nếu đọc trọn được - nhiều file khai báo sai -, không thì theo khai báo
    `<?xml encoding>` / `<meta charset>` trong 2 KB đầu, không có khai báo thì UTF-8 (byte hỏng thành �)."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    match = _DECLARED_ENCODING.search(raw[:2048])
    name = (match.group(1) or match.group(2)).decode("ascii").lower() if match else "utf-8"
    try:
        return raw.decode(ENCODING_ALIASES.get(name, name), errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _page(raw: bytes, hidden: list[_Hidden] | None = None, backlinks_hidden: bool = False) -> _Text:
    parser = _Text(hidden, backlinks_hidden)
    parser.feed(markup_text(raw))
    parser.close()
    return parser


@dataclass
class _Unit:
    """Một lời chú trong sách: các dòng [start, end) của trang `page`, và các dấu gọi trỏ tới nó (trang, dòng, số thứ tự dấu trong trang) theo thứ tự đọc."""
    page: int
    start: int
    end: int
    refs: list[tuple[int, int, int]] = field(default_factory=list)


@dataclass
class _Notes:
    found: int = 0
    marks: int = 0
    examples: list[tuple[str, str]] = field(default_factory=list)
    by_page: dict[int, list[_Unit]] = field(default_factory=dict)  # trang -> lời chú nằm ở trang ấy
    by_dest: dict[int, list[_Unit]] = field(default_factory=dict)  # trang -> lời chú có dấu gọi đầu tiên ở trang ấy (theo thứ tự đọc)


def _resolve_notes(entries: list[tuple[str, _Text]], hide_marks: bool) -> _Notes:
    """Chú thích của cả cuốn EPUB (mọi trang đã đọc, theo thứ tự đọc): dấu gọi nào trỏ tới lời chú nào (cùng trang hay trang khác), lời chú là các
    dòng nào (`_Text.note_lines`), vài ví dụ cho bước xem trước. Gỡ NOTE_OPEN…NOTE_CLOSE khỏi chữ: dấu gọi đã nhận ra được bỏ chữ khi `hide_marks`,
    còn lại giữ nguyên. Không bỏ dòng nào - chỉ số dòng của mọi trang vẫn như cũ (mục lục còn trỏ vào đó). Kotlin: BookImport.resolveNotes."""
    spans: dict[tuple[str, str], tuple[int, int, int]] = {}
    mark_ids: set[tuple[str, str]] = set()
    typed: set[tuple[int, int, int]] = set()
    for at, (path, page) in enumerate(entries):
        for name, (start, end) in page.spans.items():
            spans.setdefault((path, name), (at, start, end))
        mark_ids.update((path, mark.id) for mark in page.marks if mark.id)
        typed.update((at, start, end) for start, end in page.notes)
    heading_lines = [{line for line, _text in page.headings} for _path, page in entries]
    refs: dict[tuple[int, int, int], list[tuple[int, int, int]]] = {}
    resolved: list[dict[int, tuple[int, int, int]]] = [{} for _ in entries]  # trang -> {số thứ tự dấu gọi: lời chú}
    for at, (path, page) in enumerate(entries):
        inside = [*page.notes, *page.areas]  # dấu trong một lời chú (nhãn "1" quay lại chỗ gọi) không phải dấu gọi
        for number, mark in enumerate(page.marks):
            if any(start <= mark.line < end for start, end in inside):
                continue
            target, _hash, fragment = mark.href.partition("#")
            where = posixpath.normpath(posixpath.join(posixpath.dirname(path), unquote(target))) if target else path
            fragment = unquote(fragment)
            found = spans.get((where, fragment)) if fragment and (where, fragment) not in mark_ids else None
            if found is None:
                continue
            at_page, start, end = found
            if found not in typed and (end - start > MAX_NOTE_LINES or any(start <= line < end for line in heading_lines[at_page])):
                continue
            if at_page == at and start <= mark.line < end:
                continue
            refs.setdefault(found, []).append((at, mark.line, number))
            resolved[at][number] = found
    # Lời chú nằm gọn trong lời chú khác (<aside epub:type="footnote"><p id="fn1">…) thì là một: lấy khối ngoài; dấu gọi trỏ vào khối trong về khối ngoài.
    outer: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    keys_by_page: dict[int, list[tuple[int, int, int]]] = {}
    for key in typed | set(refs):
        keys_by_page.setdefault(key[0], []).append(key)
    for keys in keys_by_page.values():
        top = None
        for key in sorted(keys, key=lambda item: (item[1], -item[2])):
            if top is not None and key[2] <= top[2]:
                outer[key] = top
            else:
                top = outer[key] = key
    units: dict[tuple[int, int, int], _Unit] = {}
    for key in sorted(set(outer.values())):
        units[key] = _Unit(*key)
    for key, marks in refs.items():
        units[outer[key]].refs += marks
    notes = _Notes(found=len(units), marks=sum(len(by_mark) for by_mark in resolved))
    for unit in units.values():
        unit.refs.sort()
        notes.by_page.setdefault(unit.page, []).append(unit)
        if unit.refs:
            notes.by_dest.setdefault(unit.refs[0][0], []).append(unit)
    for listed in notes.by_dest.values():
        listed.sort(key=lambda unit: unit.refs[0])
    for at, (_path, page) in enumerate(entries):
        for number, line in enumerate(page.lines):
            if NOTE_OPEN in line:
                page.lines[number] = " ".join(_NOTE_SPAN.sub(
                    lambda match, found=resolved[at]: "" if hide_marks and int(match.group(1)) in found else match.group(2), line).split())
        flagged: set[int] = set()
        for unit in notes.by_page.get(at, []):
            flagged.update(range(unit.start, unit.end))
        for start, end in page.areas:
            flagged.update(line for line in range(start, end) if line not in heading_lines[at])
        page.note_lines = flagged
    seen: set[tuple[int, int, int]] = set()
    for at, (_path, page) in enumerate(entries):
        for number, mark in enumerate(page.marks):
            key = outer[resolved[at][number]] if number in resolved[at] else None
            if key is None or key in seen or len(notes.examples) >= NOTE_EXAMPLES:
                continue
            seen.add(key)
            core = mark.label.strip("[]()")
            text = " ".join(entries[key[0]][1].lines[key[1]:key[2]])
            text = re.sub(r"^[\[(]?" + re.escape(core) + r"[\])]?[.:)]?\s+", "", text.strip()).strip(" \u00a0\u21a9\ufe0e\ufe0f")
            if text:
                sup = core.translate(SUPERSCRIPT) if core.isdigit() else mark.label
                notes.examples.append((("…" + mark.before if mark.before else "") + sup, clip_title(text, NOTE_EXAMPLE_WIDTH)))
    return notes


def _notes_only(page: _Text) -> bool:
    """Trang chỉ có lời chú (và tiêu đề của nó): chương "Endnotes" - có cờ "Chú thích", không bỏ."""
    headings = {line for line, _text in page.headings}
    return any(page.lines[line] for line in page.note_lines) and all(
        line in page.note_lines or line in headings or not text for line, text in enumerate(page.lines))


def _part_lines(entries: list[tuple[str, _Text]], notes: _Notes, at: int, start: int, end: int, mode: str) -> tuple[list[str], list[str], bool]:
    """Các dòng [start, end) của trang `at` (một chương hay cả trang) thành (thân, lời chú ở cuối, có lời chú bị bỏ / dời đi). Lời chú nằm giữa chương
    đứng ở CUỐI chương, theo thứ tự trong trang - chữ không đổi, chỉ đổi chỗ. `mode`: "" như trên; "end" - lời chú của mọi dấu gọi trong chương này,
    cả lời chú ở trang khác (chương Endnotes), theo thứ tự dấu gọi; "drop" - bỏ lời chú. Kotlin: BookImport.partLines."""
    page = entries[at][1]
    lines, flagged = page.lines, page.note_lines
    body = [lines[line] for line in range(start, end) if line not in flagged]
    tail: list[str] = []
    touched = any(line in flagged for line in range(start, end))
    if mode == "end":
        covered = {line for unit in notes.by_page.get(at, []) if unit.refs and start <= unit.start < end for line in range(unit.start, unit.end)}
        for unit in notes.by_dest.get(at, []):
            if start <= unit.refs[0][1] < end:
                tail += entries[unit.page][1].lines[unit.start:unit.end]
        tail += [lines[line] for line in range(start, end) if line in flagged and line not in covered]
    elif mode != "drop":
        tail = [lines[line] for line in range(start, end) if line in flagged]
    return [line for line in body if line], [line for line in tail if line], touched and mode in ("end", "drop")


def _toc(book: _Zip, manifest: dict[str, tuple[str, str, str]], spine_toc: str) -> tuple[list[tuple[str, str, str]], bool]:
    """Mục lục theo thứ tự: (href không #, mảnh sau #, tên). EPUB3 nav trước, EPUB2 NCX sau. Kèm: gói CÓ khai báo mục lục (nav / NCX) hay
    không. Tệp mục lục hỏng hay thiếu không làm hỏng cả cuốn - chữ vẫn đọc theo thứ tự đọc (spine), chỉ mất tên chương của mục lục."""
    entries: list[tuple[str, str, str]] = []

    def add(base: str, target: str, label: str) -> None:
        path, _hash, fragment = target.partition("#")
        entries.append((posixpath.normpath(posixpath.join(base, unquote(path))), unquote(fragment), label))

    nav = next((href for href, _media, props in manifest.values() if "nav" in props.split()), "")
    root = _toc_root(book, nav)
    if root is not None:
        # Tệp nav có nhiều <nav>: mục lục (epub:type="toc"), mốc (landmarks), danh sách số trang (page-list) - chỉ mục lục là chương;
        # đọc cả số trang thì mỗi chỗ ngắt trang thành một "chương". Không <nav> nào ghi "toc" thì lấy <nav> đầu.
        navs = list(root.iter(f"{{{NS['x']}}}nav"))
        listing = next((node for node in navs if "toc" in _types(node.attrib.items())), navs[0] if navs else root)
        for anchor in listing.iter(f"{{{NS['x']}}}a"):
            href = anchor.get("href", "")
            label = _words("".join(anchor.itertext()))
            if href and label:
                add(posixpath.dirname(nav), href, label)
    ncx = manifest.get(spine_toc, ("", "", ""))[0] or next(
        (href for href, media, _props in manifest.values() if media == "application/x-dtbncx+xml"), "")
    root = _toc_root(book, ncx) if not entries else None
    if root is not None:
        for point in root.iter(f"{{{NS['ncx']}}}navPoint"):
            label = point.find("ncx:navLabel/ncx:text", NS)
            content = point.find("ncx:content", NS)
            if label is not None and content is not None and (label.text or "").strip():
                add(posixpath.dirname(ncx), content.get("src", ""), _words(label.text))
    # Nút cha trỏ cùng chỗ với nút con đầu ("Quyển một" và "Chương 12" cùng trỏ c1.xhtml): tên chương là tên nút con.
    entries = [entry for index, entry in enumerate(entries) if index + 1 == len(entries) or entries[index + 1][:2] != entry[:2]]
    return entries, bool(nav or ncx)


def _toc_root(book: _Zip, href: str) -> ElementTree.Element | None:
    """Tệp mục lục `href` đã đọc; không khai báo, thiếu trong gói hay hỏng XML: None (cuốn vẫn đọc được theo spine)."""
    if not href:
        return None
    try:
        return _xml(_read(book, href))
    except ImportFailed:
        return None


def _split_points(page: _Text, entries: list[tuple[str, str]]) -> list[tuple[int, str]]:
    """Một file chứa nhiều chương: các mục lục (mảnh, tên) trỏ vào file này -> [(dòng bắt đầu, tên)] theo thứ tự đọc. Chỉ tính mục
    không mảnh (đầu file) và mục có mảnh mà trang thật sự có; dưới hai điểm thì không tách ([])."""
    points: list[tuple[int, str]] = []
    seen: set[str] = set()
    for fragment, label in entries:
        if fragment in seen:
            continue
        seen.add(fragment)
        if not fragment:
            points.append((0, label))
        elif fragment in page.anchors:
            points.append((page.anchors[fragment], label))
    return sorted(points, key=lambda point: point[0]) if len(points) >= 2 and page.lines else []


def _meta_text(opf: ElementTree.Element, name: str) -> str | None:
    node = opf.find(f".//dc:{name}", NS)
    text = _words(node.text or "") if node is not None else ""
    return text or None


def _epub_cover(book: _Zip, opf: ElementTree.Element, manifest: dict[str, tuple[str, str, str]]) -> tuple[bytes, str] | None:
    """Bìa theo manifest: mục có properties="cover-image" (EPUB3), không thì <meta name="cover" content="id"> (EPUB2)."""
    href = next((href for href, _media, props in manifest.values() if "cover-image" in props.split()), "")
    if not href:
        meta = next((node for node in opf.iterfind("opf:metadata/opf:meta", NS) if node.get("name") == "cover"), None)
        href = manifest.get(meta.get("content", ""), ("", "", ""))[0] if meta is not None else ""
    media = next((media for entry, media, _props in manifest.values() if entry == href), "")
    if not href or not media.startswith("image/"):
        return None
    info = book.member(href)
    return (book.read(info), media) if info is not None and info.file_size <= MAX_COVER else None


def _epub(path: Path, choice: FootnoteChoice = NO_FOOTNOTES) -> ImportedBook:
    with _open_zip(path, "EPUB") as book:
        container = _xml(_read(book, "META-INF/container.xml"))
        rootfile = container.find(".//c:rootfile", NS)
        if rootfile is None or not rootfile.get("full-path"):
            raise ImportFailed(BROKEN.format(kind="EPUB"))
        opf_path = rootfile.get("full-path", "")
        opf = _xml(_read(book, opf_path))
        opf_dir = posixpath.dirname(opf_path)
        manifest = {
            item.get("id", ""): (posixpath.normpath(posixpath.join(opf_dir, unquote(item.get("href", "")))),
                                 item.get("media-type", ""), item.get("properties", ""))
            for item in opf.iterfind("opf:manifest/opf:item", NS)
        }
        spine = opf.find("opf:spine", NS)
        if spine is None:
            raise ImportFailed(BROKEN.format(kind="EPUB"))
        titles: dict[str, str] = {}  # href -> tên đầu tiên trỏ tới nó
        listed_in: dict[str, list[tuple[str, str]]] = {}  # href -> [(mảnh, tên)] theo thứ tự mục lục
        toc, declared = _toc(book, manifest, spine.get("toc", ""))
        for toc_href, toc_fragment, toc_label in toc:
            titles.setdefault(toc_href, toc_label)
            listed_in.setdefault(toc_href, []).append((toc_fragment, toc_label))
        result = ImportedBook(title=_meta_text(opf, "title") or title_from_filename(path.stem), author=_meta_text(opf, "creator"),
                              language=_meta_text(opf, "language"))
        if declared and not toc:
            result.notes.append("Mục lục trong file không đọc được - tên chương lấy từ chữ của từng chương.")
        cover = _epub_cover(book, opf, manifest)
        if cover:
            result.cover_bytes, result.cover_type = cover
        # Có mục lục thì file của thứ tự đọc không có mục nào, không phải phần đầu / cuối sách và không mở bằng tiêu đề riêng là
        # PHẦN SAU của chương trước (Calibre cắt chương dài thành index_split_001, _002…) - nối vào, đừng thành "chương" tên là câu văn.
        has_toc = any(manifest.get(ref.get("idref", ""), ("",))[0] in titles for ref in spine.iterfind("opf:itemref", NS))
        hidden = [rule for href, media, _props in manifest.values() if media == "text/css" and book.member(href) is not None
                  for rule in css_hidden(_read(book, href).decode("utf-8", errors="replace"))]
        images = 0  # trang chỉ có ảnh: một ghi chú đếm, không kể tên file trong gói (mục rất ngắn: `_finish` đếm)
        missing = 0  # mục của thứ tự đọc mà gói không có (tải chưa trọn): bỏ qua + đếm, phần còn lại vẫn đọc được
        entries: list[tuple[str, _Text]] = []  # (đường trong gói, trang) theo thứ tự đọc: chú thích cần nhìn cả cuốn trước khi dựng chương
        for itemref in spine.iterfind("opf:itemref", NS):
            if itemref.get("linear", "yes") == "no":
                continue
            href, media, props = manifest.get(itemref.get("idref", ""), ("", "", ""))
            if not href or "nav" in props.split() or "html" not in media:
                continue
            if book.member(href) is None:
                missing += 1
                continue
            entries.append((href, _page(_read(book, href), hidden, choice.notes == "end")))
        notes = _resolve_notes(entries, choice.hide_marks)
        result.footnote_found, result.footnote_marks, result.footnote_examples = notes.found, notes.marks, notes.examples
        stored: list[tuple[list[str], list[str]]] = []  # thân + lời chú ở cuối của từng chương trong `result.chapters` (nối file sau vào chương trước)
        for at, (href, page) in enumerate(entries):
            # Nhiều chương trong MỘT file: mục lục trỏ vào các mảnh (#id) của file này thì cắt chữ tại các mảnh ấy, theo thứ tự đọc,
            # mỗi phần mang tên của mục lục. Chữ trước mảnh đầu là phần riêng (không tên) nếu không mục nào trỏ về đầu file.
            points = _split_points(page, listed_in.get(href, []))
            if points:
                if points[0][0] > 0:
                    points.insert(0, (0, ""))
                ends = [start for start, _label in points[1:]] + [len(page.lines)]
                parts = [(start, end, next((text for at_line, text in page.headings if start <= at_line < end), ""), label)
                         for (start, label), end in zip(points, ends)]
            else:
                parts = [(0, len(page.lines), page.heading, titles.get(href, ""))]
            page_matter = (next((reason for kind, reason in MATTER_TYPES if kind in page.types), "") or name_matter(href)
                           or ("Chú thích" if not points and _notes_only(page) else ""))
            for start, end, heading, listed in parts:
                body, tail, removed = _part_lines(entries, notes, at, start, end, choice.notes)
                lines = [*body, *tail]
                if (has_toc and not points and not listed and not page_matter and not page.heading and lines
                        and not is_heading_line(lines[0]) and not text_matter("", "\n\n".join(lines))
                        and result.chapters and not result.chapters[-1].matter):
                    stored[-1] = (stored[-1][0] + body, stored[-1][1] + tail)
                    result.chapters[-1].text = "\n\n".join(filter(None, [*stored[-1][0], *stored[-1][1]]))
                    continue
                if not lines and page.images and not points and not removed:
                    images += 1
                    continue
                if not lines:
                    continue
                is_short = sum(len(line) for line in lines) < MIN_CHARS and not listed  # bìa, trang bản quyền: `_finish` bỏ, hay để người dùng tích
                title = listed or heading or clip_title(lines[0], TITLE_FROM_LINE)
                first = lines[0].casefold()
                # Dòng đầu là tiêu đề của chính chương: bỏ khi nó đã nằm trong tên chương ("Gặp gỡ" trong "Chương 2: Gặp gỡ"),
                # hay lấy nó làm tên khi nó đầy đủ hơn tên mục lục - không để người nghe nghe tên chương hai lần.
                if first == title.casefold() or (heading and first == heading.casefold() and first in title.casefold()):
                    lines = lines[1:]
                    body, tail = (body[1:], tail) if body else (body, tail[1:])
                elif heading and first == heading.casefold() and title.casefold() in first:
                    title, lines = lines[0], lines[1:]
                    body, tail = (body[1:], tail) if body else (body, tail[1:])
                if removed and not lines:
                    continue  # trang chỉ có lời chú (chương Endnotes) mà lời chú đã đặt về chương của chúng / bị bỏ: không còn gì
                result.chapters.append(Chapter(title, "\n\n".join(lines), short=is_short, matter=page_matter))
                stored.append((body, tail))
        if images:
            result.notes.append(f"Bỏ qua {images} trang chỉ có ảnh.")
        if missing:
            result.notes.append(f"Bỏ qua {missing} phần bị thiếu trong file (file có thể tải chưa trọn).")
        return result


# --- DOCX --------------------------------------------------------------------------------------------------------------

def _docx_styles(book: _Zip) -> dict[str, str]:
    """styleId -> tên kiểu viết thường ("heading 1", "title"); Word luôn ghi tên tiếng Anh của kiểu có sẵn."""
    try:
        root = _xml(_read(book, "word/styles.xml", "DOCX"), "DOCX")
    except ImportFailed:
        return {}
    styles = {}
    for style in root.iter(f"{W}style"):
        name = style.find(f"{W}name")
        if name is not None:
            styles[style.get(f"{W}styleId", "")] = name.get(f"{W}val", "").casefold()
    return styles


def _docx_paragraphs(element: ElementTree.Element) -> Iterator[ElementTree.Element]:
    """Mọi đoạn theo thứ tự trong file, kể cả trong bảng và khung chữ; bỏ bản dự phòng (mc:Fallback lặp lại khung chữ)."""
    for child in element:
        if child.tag == MC_FALLBACK:
            continue
        if child.tag == f"{W}p":
            yield child
        yield from _docx_paragraphs(child)


def _docx_text(element: ElementTree.Element) -> list[str]:
    """Các dòng của một đoạn: xuống dòng cứng (Shift+Enter) tách dòng; tab = khoảng trắng; chữ đã xoá (w:delText) không có mặt."""
    lines = [""]
    for child in element:
        tag = child.tag
        if tag in (f"{W}pPr", f"{W}p", f"{W}txbxContent", MC_FALLBACK):
            continue
        if tag == f"{W}t":
            lines[-1] += child.text or ""
        elif tag == f"{W}tab":
            lines[-1] += " "
        elif tag == f"{W}noBreakHyphen":
            lines[-1] += "-"
        elif tag == f"{W}br" and child.get(f"{W}type", "textWrapping") == "textWrapping":
            lines.append("")
        elif tag in (f"{W}footnoteReference", f"{W}endnoteReference"):  # chữ của lời chú ở footnotes.xml / endnotes.xml: giữ chỗ để biết dấu gọi ở đâu
            lines[-1] += NOTE_OPEN + ("f" if tag == f"{W}footnoteReference" else "e") + child.get(f"{W}id", "") + NOTE_CLOSE
        else:
            nested = _docx_text(child)
            lines[-1] += nested[0]
            lines.extend(nested[1:])
    return lines


def _join_wrapped(lines: list[str]) -> list[str]:
    """Xuống dòng cứng giữa câu (chữ dán từ web/PDF: mỗi dòng hiển thị kết thúc bằng Shift+Enter) -> nối lại, kẻo câu bị đọc
    thành hai đoạn có quãng nghỉ ở giữa. Chỉ nối khi dòng trước chưa hết câu và dòng sau mở đầu bằng chữ thường; thơ, thoại
    từng dòng ("- ...") hay dòng kết thúc bằng dấu câu giữ nguyên. Chữ không đổi, chỉ chỗ ngắt đoạn."""
    joined: list[str] = []
    for line in lines:
        previous = joined[-1] if joined else ""
        if previous and line and line[0].islower() and not previous.endswith(_SENTENCE_END + (":", ";")):
            if previous.endswith(SOFT_HYPHEN):
                joined[-1] = previous[:-1] + line
            else:
                joined[-1] = f"{previous} {line}"
        else:
            joined.append(line)
    return joined


def _docx_bold(paragraph: ElementTree.Element) -> bool:
    """Mọi đoạn chạy có chữ trong đoạn đều in đậm (w:b, không phải w:val="0")."""
    runs = [run for run in paragraph.iter(f"{W}r") if "".join(node.text or "" for node in run.iter(f"{W}t")).strip()]

    def bold(run: ElementTree.Element) -> bool:
        node = run.find(f"{W}rPr/{W}b")
        return node is not None and node.get(f"{W}val", "true").casefold() not in {"0", "false", "off"}

    return bool(runs) and all(bold(run) for run in runs)


def title_page(text: str) -> bool:
    """Chữ trước chương đầu chỉ là trang tên sách / tác giả: vài dòng ngắn, không dòng nào kết thúc câu."""
    lines = [line for line in text.split("\n\n") if line.strip()]
    return 0 < len(lines) <= TITLE_PAGE_LINES and all(
        len(line) <= TITLE_PAGE_WIDTH and not line.rstrip().endswith((".", "!", "?", "…", "。")) for line in lines)


_DOCX_REF = re.compile(NOTE_OPEN + r"([fe])(-?\d+)" + NOTE_CLOSE)


def _docx_notes(book: _Zip) -> dict[tuple[str, str], list[str]]:
    """Lời chú Word: {("f" | "e", id): các dòng} từ word/footnotes.xml và word/endnotes.xml (bỏ separator / continuationSeparator). Phần hỏng hay thiếu: bỏ qua."""
    notes: dict[tuple[str, str], list[str]] = {}
    for key, kind, part in (("f", "footnote", "word/footnotes.xml"), ("e", "endnote", "word/endnotes.xml")):
        if book.member(part) is None:
            continue
        try:
            root = _xml(_read(book, part, "DOCX"), "DOCX")
        except ImportFailed:
            continue
        for note in root.iter(f"{W}{kind}"):
            if note.get(f"{W}type", "normal") != "normal":
                continue
            lines = [line for paragraph in _docx_paragraphs(note) for line in (_words(text) for text in _docx_text(paragraph)) if line]
            if lines:
                notes[(key, note.get(f"{W}id", ""))] = lines
    return notes


def _docx(path: Path, choice: FootnoteChoice = NO_FOOTNOTES) -> ImportedBook:
    with _open_zip(path, "DOCX") as book:
        document = _xml(_read(book, "word/document.xml", "DOCX"), "DOCX")
        styles = _docx_styles(book)
        word_notes = _docx_notes(book)
        meta_title = meta_author = meta_language = None
        if "docProps/core.xml" in book.namelist():
            core = _xml(_read(book, "docProps/core.xml", "DOCX"), "DOCX")
            meta_title, meta_author, meta_language = (
                _meta_text(core, name) for name in ("title", "creator", "language"))
    body = document.find(f"{W}body")
    if body is None:
        raise ImportFailed(BROKEN.format(kind="DOCX"))
    items: list[tuple[int, str, bool, bool]] = []  # (cấp tiêu đề - 0 là chữ thường, dòng, cả đoạn in đậm, là lời chú đặt về cuối chương)
    book_title: str | None = None
    toc_lines = 0
    cited: set[tuple[str, str]] = set()  # lời chú đã có dấu gọi (mỗi lời chú một lần)
    examples: list[tuple[str, str]] = []
    references = 0  # số dấu gọi đã gặp: số thứ tự Word đánh cho chú thích
    for paragraph in _docx_paragraphs(body):
        style_node = paragraph.find(f"{W}pPr/{W}pStyle")
        style_id = style_node.get(f"{W}val", "") if style_node is not None else ""
        style = styles.get(style_id, style_id.casefold())
        if TOC_STYLE.fullmatch(style):
            # Mục lục Word tự sinh (kiểu "toc 1".."toc 9"): không phải chữ của truyện, và dòng "Chương N … 3" của nó sẽ bị
            # nhận nhầm là tiêu đề chương.
            toc_lines += 1
            continue
        level, bold = HEADING_LEVELS.get(style, 0), _docx_bold(paragraph)
        for raw in _join_wrapped([_words(line) for line in _docx_text(paragraph)]):
            line, cites = _DOCX_REF.sub("", raw), []
            for match in _DOCX_REF.finditer(raw):
                key = (match.group(1), match.group(2))
                references += 1
                if key in word_notes and key not in cited:
                    cited.add(key)
                    cites.append(key)
                    if len(examples) < NOTE_EXAMPLES:
                        before = _note_context(_DOCX_REF.sub("", raw[:match.start()]))
                        examples.append((("…" + before if before else "") + str(references).translate(SUPERSCRIPT),
                                         clip_title(" ".join(word_notes[key]), NOTE_EXAMPLE_WIDTH)))
            if line:
                if not level and style == "title" and book_title is None:
                    book_title = line
                items.append((level, line, bold, False))
            if choice.notes == "end":  # lời chú Word (chưa từng vào sách): đề xuất, tích mới đưa về cuối chương chứa dấu gọi
                items += [(0, text, False, True) for key in cites for text in word_notes[key]]
    levels = [level for level, *_ in items if level]
    if levels.count(1) == 1 and len(items) > 1 and items[0][0] == 1 and not is_heading_line(items[0][1]):
        # Heading 1 duy nhất, ở đầu, không phải "Chương N": tên sách. Chương theo cấp kế (Heading 2), không có thì dòng "Chương N" / đậm.
        book_title, items, chapter_levels = book_title or items[0][1], items[1:], {2}
    elif 1 in levels and 2 in levels:
        chapter_levels = {1}  # Heading 1 là chương, Heading 2 là cảnh trong chương: một dòng của chương
    else:
        chapter_levels = {1, 2}
    result = ImportedBook(title=meta_title or book_title or title_from_filename(path.stem), author=meta_author, language=meta_language,
                          footnote_found=len(cited), footnote_examples=examples)
    if toc_lines:
        result.notes.append(f"Bỏ qua mục lục của tài liệu ({toc_lines} dòng).")
    if not any(level in chapter_levels for level, *_ in items):
        # Không có kiểu Heading: tách theo dòng "Chương N" (như PDF), và dòng in đậm "I. KHỞI ĐẦU" khi có từ hai dòng như thế.
        roman = [index for index, (_, line, bold, _note) in enumerate(items) if bold and is_heading_line(line, BOLD_ROMAN)]
        result.chapters, notes = _split_on_headings([line for _, line, _, _ in items], result.title, roman if len(roman) >= 2 else (),
                                                    {index for index, item in enumerate(items) if item[3]})
        result.notes += notes
    else:
        sections: list[tuple[str | None, list[str], list[str]]] = [(None, [], [])]  # (tên chương theo kiểu Heading, các đoạn, lời chú ở cuối)
        for level, line, _, note in items:
            if level in chapter_levels:
                sections.append((line, [], []))
            else:
                sections[-1][2 if note else 1].append(line)
        for title, paragraphs, tail in sections:
            if title is None:
                if paragraphs:
                    result.chapters.append(Chapter(PREAMBLE, "\n\n".join([*paragraphs, *tail])))
            elif paragraphs:
                result.chapters.append(Chapter(title, "\n\n".join([*paragraphs, *tail])))
            else:
                result.notes.append(f"Bỏ qua mục trống: {title}")
    first = result.chapters[0] if len(result.chapters) > 1 else None
    if first is not None and first.title == PREAMBLE and title_page(first.text):
        first.matter = "Trang tên sách"  # không bỏ: chưa tích, kèm lý do
    return result


# --- Chia chương theo dòng tiêu đề (DOCX không có Heading, PDF) -------------------------------------------------------

def is_heading_line(line: str, pattern: re.Pattern[str] = HEADING) -> bool:
    return len(line.strip()) <= MAX_HEADING and pattern.match(line) is not None


def _split_on_headings(paragraphs: list[str], book_title: str, extra: Iterable[int] = (), note_lines: Iterable[int] = ()) -> tuple[list[Chapter], list[str]]:
    """Chữ trước tiêu đề đầu tiên thành chương "Mở đầu" (không bỏ đi); không có tiêu đề nào thì cả file là một chương. `extra`: số thứ tự
    các dòng cũng là tiêu đề (DOCX: dòng in đậm "I. KHỞI ĐẦU"). `note_lines`: số thứ tự các dòng là lời chú (DOCX, người nghe tích đọc lời chú):
    không bao giờ là tiêu đề, và đứng ở cuối chương."""
    chapters: list[Chapter] = []
    notes: list[str] = []
    title: str | None = None
    body: list[str] = []
    tail: list[str] = []

    def close() -> None:
        if title is None:
            if body:
                chapters.append(Chapter(PREAMBLE if any_heading else book_title, "\n\n".join([*body, *tail])))
        elif body:
            chapters.append(Chapter(title, "\n\n".join([*body, *tail])))
        else:
            notes.append(f"Bỏ qua mục trống: {title}")

    extra, note_lines = set(extra), set(note_lines)
    headings = [index not in note_lines and (is_heading_line(paragraph) or index in extra) for index, paragraph in enumerate(paragraphs)]
    any_heading = any(headings)
    for index, (paragraph, heading) in enumerate(zip(paragraphs, headings, strict=True)):
        if heading:
            close()
            title, body, tail = paragraph.strip(), [], []
        else:
            (tail if index in note_lines else body).append(paragraph)
    close()
    if not any_heading:
        notes.append("Không thấy tiêu đề chương (Chương N, Chapter N…) - cả file là một chương.")
    return chapters, notes


# --- PDF có lớp chữ ----------------------------------------------------------------------------------------------------

_PAGE_NUMBER = re.compile(r"^[\s\-–—·|]*(?:trang|page|tr\.?|p\.?)?\s*\d{1,5}(?:\s*(?:/|of|trên)\s*\d{1,5})?[\s\-–—·|]*$", re.IGNORECASE)
_SENTENCE_END = tuple(".!?…”\"»’)。")
_DIALOGUE_START = ("-", "–", "—", "“", "\"", "«", "‘")
RUNNING_ZONE = 2  # số dòng đầu và cuối mỗi trang có thể là tiêu đề chạy / số trang
RUNNING_MIN_PAGES = 3
SCAN_CHARS_PER_PAGE = 30  # trung bình dưới mức này là PDF scan


def _page_lines(raw: str) -> list[str]:
    """Các dòng CÓ CHỮ của một trang (đã gộp khoảng trắng). Dòng trống không thuộc lớp thô: pypdf và pdf.js không đồng ý chỗ nào
    có dòng trống, nên ranh giới đoạn chỉ do độ dài dòng + dấu câu quyết (`_join_paragraphs`)."""
    lines = (_words(line) for line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
    return [line for line in lines if line]


def _running_key(line: str) -> str:
    return re.sub(r"\d+", "#", line.casefold())


def _strip_running(pages: list[list[str]]) -> tuple[list[list[str]], list[str]]:
    """Bỏ số trang và tiêu đề chạy đầu / cuối trang (dòng lặp lại ở >= 40% số trang, chữ số coi như nhau). Trả (các trang, các
    dòng đã bỏ - cho `notes`). Dòng tiêu đề chương không bao giờ bị coi là dòng lặp."""
    zones: list[list[int]] = []
    for lines in pages:
        filled = [index for index, line in enumerate(lines) if line]
        zones.append(filled[:RUNNING_ZONE] + filled[-RUNNING_ZONE:] if len(filled) > RUNNING_ZONE else filled)
    counts: dict[str, int] = {}
    for lines, zone in zip(pages, zones):
        for key in {_running_key(lines[index]) for index in zone if not is_heading_line(lines[index])}:
            counts[key] = counts.get(key, 0) + 1
    repeated = {key for key, seen in counts.items() if len(pages) >= RUNNING_MIN_PAGES and seen >= 3 and seen * 5 >= len(pages) * 2}
    removed: list[str] = []
    noted: set[str] = set()  # một ghi chú cho mỗi dòng lặp, dù số trang trong nó đổi theo trang
    result: list[list[str]] = []
    for lines, zone in zip(pages, zones):
        drop = set()
        for index in zone:
            line = lines[index]
            if is_heading_line(line):
                continue
            edge = index in (zone[0], zone[-1])
            key = _running_key(line)
            if key in repeated or (edge and _PAGE_NUMBER.match(line)):
                drop.add(index)
                if key not in noted and not _PAGE_NUMBER.match(line) and len(removed) < 5:
                    noted.add(key)
                    removed.append(line)
        result.append([line for index, line in enumerate(lines) if index not in drop])
    return result, removed


def _join_paragraphs(pages: list[list[str]]) -> list[str]:
    """Các dòng của PDF -> đoạn văn. Một dòng cuối câu mà ngắn hơn hẳn dòng đầy (hay dòng kế mở đầu bằng
    gạch / ngoặc thoại) ngắt đoạn; "chữ-" cuối dòng nối liền (không dấu cách, giữ gạch nối) với chữ thường dòng sau, dấu nối mềm U+00AD thì bỏ; còn lại nối bằng một dấu cách. Hết trang KHÔNG
    ngắt đoạn (đoạn văn vắt qua trang)."""
    sizes = sorted(len(line) for page in pages for line in page if line)
    full = sizes[int(len(sizes) * 0.9)] if sizes else 0
    paragraphs: list[str] = []
    current = ""
    last = 0  # độ dài dòng vật lý vừa nối vào `current`
    for page in pages:
        for line in page:
            if is_heading_line(line):
                if current:
                    paragraphs.append(current)
                paragraphs.append(line)
                current = ""
                continue
            if not current:
                current = line
            elif current.endswith(SOFT_HYPHEN):  # dấu nối mềm của máy dàn trang: bỏ nó, chữ liền nhau
                current = current[:-1] + line
            elif current.endswith("-") and len(current) > 1 and current[-2].isalpha() and line[0].islower():
                # "Mát-" + "xcơ-va": gạch nối thường trong tiếng Việt là của chính từ (Mát-xcơ-va, ba-lô) - giữ nó, chỉ nối liền.
                current += line
            elif current.endswith(_SENTENCE_END) and (last < full * 0.75 or line.startswith(_DIALOGUE_START)):
                paragraphs.append(current)
                current = line
            else:
                current = f"{current} {line}"
            last = len(line)
    if current:
        paragraphs.append(current)
    return paragraphs


def _vendored_pypdf():
    """pypdf trong `abook/vendor/pypdf` (chép nguyên từ wheel, xem README ở đó). Nó tự gọi nhau bằng tên tuyệt đối
    (`from pypdf._utils import ...`) nên thư mục `abook/vendor` phải nằm trên sys.path; đứng ĐẦU để bản chép luôn thắng bản cài sẵn."""
    vendor = str(Path(__file__).resolve().parent / "vendor")
    if vendor not in sys.path:
        sys.path.insert(0, vendor)
    try:
        import pypdf
    except ImportError as error:
        raise ImportFailed("Thiếu thư viện đọc PDF (abook/vendor/pypdf) - cài lại ABook hay dùng bản EPUB/TXT") from error
    return pypdf


def pdf_pages(path: Path) -> tuple[list[list[str]], str, str]:
    """Lớp THÔ của PDF: (các dòng của từng trang, tên sách trong metadata, tác giả). Tầng này là phần duy nhất cần thư viện PDF - trên
    điện thoại nó là pdf.js (ui/src/shared/pdfPages.ts), và cả hai ra cùng `*.pages.json` của bộ ví dụ."""
    PdfReader = _vendored_pypdf().PdfReader
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ImportFailed("PDF này có mật khẩu - ABook chưa mở được")
        raw_pages = [page.extract_text() or "" for page in reader.pages]
        metadata = reader.metadata
    except ImportFailed:
        raise
    except Exception as error:  # pypdf báo file hỏng bằng đủ loại lỗi (PyPdfError, ValueError, KeyError, đệ quy...)
        raise ImportFailed(BROKEN.format(kind="PDF")) from error
    title = _words(str(metadata.title or "")) if metadata else ""
    author = _words(str(metadata.author or "")) if metadata else ""
    return [_page_lines(raw) for raw in raw_pages], title, author


def import_pdf_pages(pages: list[list[str]], stem: str, title: str = "", author: str = "") -> ImportedBook:
    """Lớp LUẬT của PDF: từ các dòng của từng trang đến các chương (bỏ tiêu đề chạy + số trang, nối dòng thành đoạn, chia chương).
    Không đụng thư viện PDF - bản Kotlin (BookImport.fromPdfPages) cùng luật, cùng bộ ví dụ."""
    if not pages:
        raise ImportFailed(BROKEN.format(kind="PDF"))
    chars = sum(len(line) for lines in pages for line in lines)
    if chars < SCAN_CHARS_PER_PAGE * len(pages):
        raise ImportFailed("PDF này là ảnh chụp, chưa có chữ để đọc.")
    result = ImportedBook(title=title or stem, author=author or None)
    empty = sum(1 for lines in pages if not any(lines))
    if empty:
        result.notes.append(f"{empty} trang không có chữ (ảnh hay trang trống) - bỏ qua.")
    pages, removed = _strip_running(pages)
    for line in removed:
        result.notes.append(f"Bỏ dòng lặp đầu / cuối trang: “{line}”")
    chapters, notes = _split_on_headings(_join_paragraphs(pages), result.title)
    result.chapters, result.notes = chapters, result.notes + notes
    return _finish(result)


# --- Studio: thư mục chương TXT ----------------------------------------------------------------------------------------

def extract(path: Path, folder_root: Path) -> tuple[Path, dict[str, Any]]:
    """Tách EPUB / DOCX / PDF thành thư mục chương TXT trong `folder_root` (đặt tên theo file + băm nội dung: mở lại cùng file thì
    dùng lại thư mục, file khác cùng tên không đè lên nhau). Trả (thư mục, thông tin: title, author, language, notes, cover)."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
    stem = UNSAFE_NAME.sub(" ", path.stem).strip() or path.suffix.lstrip(".") or "sach"
    folder = folder_root / f"{stem[:80]} - {digest}"
    sidecar = folder / SIDECAR
    if sidecar.is_file() and any(folder.glob("*.txt")):
        return folder, json.loads(sidecar.read_text(encoding="utf-8"))
    book = import_text(path)
    folder.mkdir(parents=True, exist_ok=True)
    width = max(4, len(str(len(book.chapters))))
    for index, chapter in enumerate(book.chapters, start=1):
        body = book.chapter_source(chapter)
        label = clip_title(_words(UNSAFE_NAME.sub(" ", chapter.title)), 50).strip(" .")
        (folder / f"{index:0{width}d}{' ' + label if label else ''}.txt").write_bytes(body.encode("utf-8"))
    cover = ""
    if book.cover_bytes:
        cover = "cover" + {"image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}.get(book.cover_type or "", ".jpg")
        (folder / cover).write_bytes(book.cover_bytes)
    info = {"title": book.title, "author": book.author, "language": book.language, "notes": book.notes, "cover": cover}
    sidecar.write_bytes(json.dumps(info, ensure_ascii=False, indent=1).encode("utf-8") + b"\n")
    return folder, info
