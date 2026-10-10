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
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from xml.etree import ElementTree

from .io_utils import decode_text_bytes, discover_txt_files

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
BLOCKS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "section", "article", "tr", "dd", "dt", "pre"}
HEADINGS = {"h1", "h2", "h3"}
UNSAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')  # ký tự Windows không nhận trong tên file
BROKEN = "không phải file {kind} thật hoặc bị hỏng - thử tải lại, hoặc dùng bản TXT"

# Số của chương: chữ số, số La Mã, hay số viết bằng chữ ("Chương Một", "Hồi thứ hai").
_NUMBER_WORDS = (
    "một|hai|ba|bốn|tư|năm|lăm|sáu|bảy|tám|chín|mười|mươi|mốt|trăm|nghìn|ngàn|linh|lẻ|"
    "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
)
CHAPTER_WORDS = "chương|chuong|hồi|hoi|chapter|tiết"


def heading_pattern(words: str) -> re.Pattern[str]:
    """Dòng tiêu đề chương: một trong `words` rồi số ("Chương 12", "Hồi thứ hai", "第三章")."""
    return re.compile(
        r"^\s*(?:"
        r"(?:" + words + r")\s+(?:thứ\s+)?(?:\d+|[ivxlcdm]+|(?:(?:" + _NUMBER_WORDS + r")\s*)+)(?![\w])"
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
            "chapters": [{"title": chapter.title, "text": chapter.text} for chapter in self.chapters],
            "notes": list(self.notes),
            **({"splitOffer": self.split_offer, "splitHeadings": self.split_headings} if self.split_offer else {}),
        }


def import_text(path: Path | str, *, split_chapters: bool = False, keep_short: bool = False) -> ImportedBook:
    """Mở một thư mục TXT, hay file .epub / .docx / .pdf / .txt. Lỗi dự đoán được là `ImportFailed`. `split_chapters`: file .txt cả
    truyện thì tách thành các chương theo dòng "Chương N" (người dùng tích gợi ý `split_offer`; mặc định cả file là một chương).
    `keep_short`: bước xem trước - mục rất ngắn (`Chapter.short`) vẫn nằm trong danh sách, đúng chỗ của nó trong file, để người dùng tích
    nếu muốn giữ (`default_picks` bỏ chúng); không có thì chúng bị bỏ như trước."""
    path = Path(path)
    if path.is_dir():
        book = _txt_folder(path)
    elif path.is_file():
        suffix = path.suffix.casefold()
        if suffix == ".pdf":
            pages, title, author = pdf_pages(path)
            return import_pdf_pages(pages, title_from_filename(path.stem), title, author)
        reader = {".epub": _epub, ".docx": _docx, ".txt": lambda file: _txt_file(file, split_chapters)}.get(suffix)
        if reader is None:
            raise ImportFailed(f"Chưa đọc được file {suffix or 'không có đuôi'} - dùng .epub, .docx, .pdf, .txt hay một thư mục TXT")
        book = reader(path)
    else:
        raise ImportFailed(f"Không thấy {path}.")
    return _finish(book, keep_short, path.name)


def _finish(book: ImportedBook, keep_short: bool = False, source: str = "") -> ImportedBook:
    """Mọi định dạng đi qua đây: Unicode NFC, và gợi ý (không bỏ) dòng ghi công ở đầu chương."""
    book.title = _nfc(book.title)
    book.author = _nfc(book.author) if book.author else None
    for chapter in book.chapters:
        chapter.title, chapter.text = _nfc(chapter.title), _nfc(chapter.text)
    book.notes = [_nfc(note) for note in book.notes]
    short = sum(chapter.short for chapter in book.chapters)
    if short:
        book.notes.append(f"{short} mục rất ngắn chưa chọn - tích nếu muốn giữ." if keep_short
                          else f"Bỏ qua {short} mục rất ngắn (bìa, trang bản quyền?).")
    if not keep_short:
        book.chapters = [chapter for chapter in book.chapters if not chapter.short]
    if not book.chapters or not any(chapter.text.strip() or chapter.short for chapter in book.chapters):
        raise ImportFailed(f"Không có chương nào có chữ trong “{source or book.title}” - file rỗng hay mã hoá lạ? "
                           "Với file .txt: thử mở bằng Notepad rồi lưu lại ở dạng UTF-8.")
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
    """Lựa chọn chương mặc định của bước xem trước: mọi chương trừ mục rất ngắn (`Chapter.short`). [(số chương 1-based, tên mới "")]. Kotlin: BookImport.defaultPicks."""
    return [(number, "") for number, chapter in enumerate(book.chapters, start=1) if not chapter.short]


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


# --- Thư mục TXT -------------------------------------------------------------------------------------------------------

def _clean_text(text: str) -> str:
    """Đổi định dạng thôi: xuống dòng \\n, bỏ khoảng trắng cuối dòng, tối đa một dòng trống liền nhau, bỏ dòng trống hai đầu."""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip("\n")


def _txt_chapter(path: Path) -> Chapter:
    """Một file TXT là một chương. Tên chương: dòng đầu nếu nó là dòng tiêu đề ("Chương 1: Buổi sáng" - đúng thứ người nghe thấy ở
    đầu chương), không thì tên file ("01.txt" -> "Chương 1")."""
    from .webui.humanize import chapter_title

    text = _clean_text(decode_text_bytes(path.read_bytes()))
    first = next((line.strip() for line in text.split("\n") if line.strip()), "")
    return Chapter(first if is_heading_line(first) else chapter_title(path.stem), text)


def _txt_folder(folder: Path) -> ImportedBook:
    files = discover_txt_files(folder)  # đúng luật của Studio: các .txt nằm ngay trong thư mục, xếp tên tự nhiên
    if not files:
        raise ImportFailed("Thư mục này không có file .txt nào nằm ngay bên trong")
    return ImportedBook(title=title_from_filename(folder.resolve().name), chapters=[_txt_chapter(file) for file in files], text_has_title=True)


def _txt_file(path: Path, split: bool = False) -> ImportedBook:
    """Một file TXT là một chương - trừ khi nó là CẢ truyện (>= 2 dòng "Chương N") và người dùng tích tách: `split_txt_chapters`."""
    chapter = _txt_chapter(path)
    book = ImportedBook(title=title_from_filename(path.stem), chapters=[chapter], text_has_title=True)
    parts = split_txt_chapters(chapter.text)
    book.split_offer = len(parts)
    # Chương tách ra từ một dòng tiêu đề mang tên dòng ấy - không bao giờ trùng tên chương "Mở đầu".
    book.split_headings = sum(part.title != PREAMBLE for part in parts)
    if parts:
        # Cả truyện: tên sách gợi ý là dòng tiêu đề đầu file ("Ngọn đèn cuối cùng"), không phải tên file ("ngon_den_cuoi_cung").
        book.title = title_from_line(first_text_line(chapter.text)) or book.title
        lines = chapter.text.split("\n")
        alone = title_only_preamble(lines, _first_cut(lines))
        if split and alone:
            book.notes.append(f"Dòng đầu “{alone}” là tên truyện - dùng làm tên sách, không đọc thành một chương.")
    if split and parts:
        book.chapters = parts
    return book


def first_text_line(text: str) -> str:
    """Dòng đầu có chữ của `text`, bỏ khoảng trắng hai đầu; "" nếu không có."""
    return next((line.strip() for line in text.split("\n") if line.strip()), "")


def title_from_line(line: str) -> str:
    """`line` nếu nó trông là TIÊU ĐỀ truyện: ngắn (<= 80 ký tự, <= 12 từ), có chữ, không bắt đầu bằng gạch lời thoại / ngoặc, không
    kết bằng dấu câu, không phải dòng "Chương N"; dấu `#` Markdown đầu dòng bỏ đi. Không thì "". Một luật cho trình tạo sách (tên sách
    gợi ý của file cả truyện), "Thêm sách từ file…" và việc tách file cả truyện. Kotlin: BookImport.titleFromLine."""
    first = line.strip().lstrip("#").strip()
    if not first or len(first) > 80 or len(first.split()) > 12:
        return ""
    if is_heading_line(first) or first[0] in "-–—“\"‘'«(" or first[-1] in ".!?…,;:\"”’»)":
        return ""
    return first if any(ch.isalpha() for ch in first) else ""


def title_only_preamble(lines: list[str], cut: int) -> str:
    """Chữ trước tiêu đề chương đầu tiên (`lines[:cut]`) chỉ là MỘT dòng và dòng ấy trông là tiêu đề truyện: trả tên truyện đó. Nó là tên
    sách chứ không phải một chương "Mở đầu" 4 chữ (soát UX a8 02-10); không thì "" - chữ dẫn nhiều dòng (tên + giới thiệu) vẫn là "Mở đầu"."""
    kept = [line for line in lines[:cut] if line.strip()]
    return title_from_line(kept[0]) if len(kept) == 1 else ""


def _first_cut(lines: list[str]) -> int:
    return next((index for index, line in enumerate(lines) if is_heading_line(line, TXT_HEADING)), 0)


def split_txt_chapters(text: str) -> list[Chapter]:
    """Chữ (đã `_clean_text`) của một file TXT cả truyện -> các chương cắt ở đầu mỗi dòng tiêu đề "Chương N" (cùng luật nhận tiêu đề
    với trình tạo sách, `txt_split`: "Quyển N" không phải tiêu đề). Chữ giữ nguyên từng dòng, tiêu đề nằm trong chữ của chương; chữ
    đứng trước tiêu đề đầu tiên thành chương "Mở đầu" (không bỏ) - trừ khi nó chỉ là MỘT dòng tên truyện (`title_only_preamble`): dòng ấy
    là tên sách (`_txt_file`), người nghe được báo ở ghi chú. Dưới hai tiêu đề: [] (không có gì để tách). Kotlin: splitTxtChapters."""
    lines = text.split("\n")
    cuts = [index for index, line in enumerate(lines) if is_heading_line(line, TXT_HEADING)]
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


def _read(book: zipfile.ZipFile, name: str, kind: str = "EPUB") -> bytes:
    try:
        info = book.getinfo(name)
    except KeyError as error:
        raise ImportFailed(BROKEN.format(kind=kind)) from error
    if info.file_size > MAX_MEMBER:
        raise ImportFailed(f"có một phần quá lớn (trên 20 MB) - không giống {kind} truyện")
    return book.read(info)


def _open_zip(path: Path, kind: str) -> zipfile.ZipFile:
    try:
        book = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as error:
        raise ImportFailed(BROKEN.format(kind=kind)) from error
    if sum(info.file_size for info in book.infolist()) > MAX_TOTAL:
        book.close()
        raise ImportFailed(f"quá lớn khi giải nén (trên 300 MB) - không giống {kind} truyện")
    return book


# --- EPUB --------------------------------------------------------------------------------------------------------------

class _Text(HTMLParser):
    """Chữ của một trang XHTML: mỗi khối (đoạn, tiêu đề, dòng danh sách, <br>) một dòng; bỏ script/style/head."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.heading = ""
        self.headings: list[tuple[int, str]] = []  # (dòng của tiêu đề, chữ): mọi tiêu đề h1-h3 có chữ, theo thứ tự
        self.anchors: dict[str, int] = {}  # id / <a name> -> chỉ số dòng bắt đầu từ chỗ ấy (mục lục trỏ #mảnh vào đây)
        self.images = 0
        self._current: list[str] = []
        self._skip = 0
        self._in_heading = 0

    def _flush(self) -> None:
        line = _words("".join(self._current))
        if line:
            self.lines.append(line)
        self._current = []

    def handle_starttag(self, tag: str, attrs) -> None:  # chữ ký của HTMLParser
        if tag in {"script", "style", "head", "title"}:
            self._skip += 1
        elif tag in {"img", "image"}:
            self.images += 1
        elif tag == "br":
            self._flush()
        elif tag in BLOCKS:
            self._flush()
            if tag in HEADINGS:
                self._in_heading += 1
        if not self._skip:
            for name, value in attrs:
                key = name.partition(":")[2] or name  # như bản Kotlin: bỏ tiền tố ("xml:id" thành "id")
                if value and (key == "id" or (tag == "a" and key == "name")):
                    self.anchors.setdefault(value, len(self.lines))

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "head", "title"}:
            self._skip = max(0, self._skip - 1)
        elif tag in BLOCKS:
            if tag in HEADINGS and self._in_heading:
                self._in_heading -= 1
                text = _words("".join(self._current))
                if text:
                    self.headings.append((len(self.lines), text))
                if not self.heading:
                    self.heading = text
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._current.append(data)

    def close(self) -> None:
        super().close()
        self._flush()


def _page(raw: bytes) -> _Text:
    parser = _Text()
    parser.feed(raw.decode("utf-8", errors="replace"))
    parser.close()
    return parser


def _toc(book: zipfile.ZipFile, manifest: dict[str, tuple[str, str, str]], spine_toc: str) -> list[tuple[str, str, str]]:
    """Mục lục theo thứ tự: (href không #, mảnh sau #, tên). EPUB3 nav trước, EPUB2 NCX sau."""
    entries: list[tuple[str, str, str]] = []

    def add(base: str, target: str, label: str) -> None:
        path, _hash, fragment = target.partition("#")
        entries.append((posixpath.normpath(posixpath.join(base, unquote(path))), unquote(fragment), label))

    nav = next((href for href, _media, props in manifest.values() if "nav" in props.split()), "")
    if nav:
        root = _xml(_read(book, nav))
        for anchor in root.iter(f"{{{NS['x']}}}a"):
            href = anchor.get("href", "")
            label = _words("".join(anchor.itertext()))
            if href and label:
                add(posixpath.dirname(nav), href, label)
    ncx = manifest.get(spine_toc, ("", "", ""))[0] or next(
        (href for href, media, _props in manifest.values() if media == "application/x-dtbncx+xml"), "")
    if ncx and not entries:
        root = _xml(_read(book, ncx))
        for point in root.iter(f"{{{NS['ncx']}}}navPoint"):
            label = point.find("ncx:navLabel/ncx:text", NS)
            content = point.find("ncx:content", NS)
            if label is not None and content is not None and (label.text or "").strip():
                add(posixpath.dirname(ncx), content.get("src", ""), _words(label.text))
    return entries


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


def _epub_cover(book: zipfile.ZipFile, opf: ElementTree.Element, manifest: dict[str, tuple[str, str, str]]) -> tuple[bytes, str] | None:
    """Bìa theo manifest: mục có properties="cover-image" (EPUB3), không thì <meta name="cover" content="id"> (EPUB2)."""
    href = next((href for href, _media, props in manifest.values() if "cover-image" in props.split()), "")
    if not href:
        meta = next((node for node in opf.iterfind("opf:metadata/opf:meta", NS) if node.get("name") == "cover"), None)
        href = manifest.get(meta.get("content", ""), ("", "", ""))[0] if meta is not None else ""
    media = next((media for entry, media, _props in manifest.values() if entry == href), "")
    if not href or not media.startswith("image/"):
        return None
    try:
        info = book.getinfo(href)
    except KeyError:
        return None
    return (book.read(info), media) if info.file_size <= MAX_COVER else None


def _epub(path: Path) -> ImportedBook:
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
        for toc_href, toc_fragment, toc_label in _toc(book, manifest, spine.get("toc", "")):
            titles.setdefault(toc_href, toc_label)
            listed_in.setdefault(toc_href, []).append((toc_fragment, toc_label))
        result = ImportedBook(title=_meta_text(opf, "title") or title_from_filename(path.stem), author=_meta_text(opf, "creator"),
                              language=_meta_text(opf, "language"))
        cover = _epub_cover(book, opf, manifest)
        if cover:
            result.cover_bytes, result.cover_type = cover
        images = 0  # trang chỉ có ảnh: một ghi chú đếm, không kể tên file trong gói (mục rất ngắn: `_finish` đếm)
        for itemref in spine.iterfind("opf:itemref", NS):
            if itemref.get("linear", "yes") == "no":
                continue
            href, media, props = manifest.get(itemref.get("idref", ""), ("", "", ""))
            if not href or "nav" in props.split() or "html" not in media:
                continue
            page = _page(_read(book, href))
            # Nhiều chương trong MỘT file: mục lục trỏ vào các mảnh (#id) của file này thì cắt chữ tại các mảnh ấy, theo thứ tự đọc,
            # mỗi phần mang tên của mục lục. Chữ trước mảnh đầu là phần riêng (không tên) nếu không mục nào trỏ về đầu file.
            points = _split_points(page, listed_in.get(href, []))
            if points:
                if points[0][0] > 0:
                    points.insert(0, (0, ""))
                ends = [start for start, _label in points[1:]] + [len(page.lines)]
                parts = [(page.lines[start:end], next((text for at, text in page.headings if start <= at < end), ""), label)
                         for (start, label), end in zip(points, ends)]
            else:
                parts = [(page.lines, page.heading, titles.get(href, ""))]
            for lines, heading, listed in parts:
                if not lines and page.images and not points:
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
                elif heading and first == heading.casefold() and title.casefold() in first:
                    title, lines = lines[0], lines[1:]
                result.chapters.append(Chapter(title, "\n\n".join(lines), short=is_short))
        if images:
            result.notes.append(f"Bỏ qua {images} trang chỉ có ảnh.")
        return result


# --- DOCX --------------------------------------------------------------------------------------------------------------

def _docx_styles(book: zipfile.ZipFile) -> dict[str, str]:
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


def _docx(path: Path) -> ImportedBook:
    with _open_zip(path, "DOCX") as book:
        document = _xml(_read(book, "word/document.xml", "DOCX"), "DOCX")
        styles = _docx_styles(book)
        meta_title = meta_author = meta_language = None
        if "docProps/core.xml" in book.namelist():
            core = _xml(_read(book, "docProps/core.xml", "DOCX"), "DOCX")
            meta_title, meta_author, meta_language = (
                _meta_text(core, name) for name in ("title", "creator", "language"))
    body = document.find(f"{W}body")
    if body is None:
        raise ImportFailed(BROKEN.format(kind="DOCX"))
    sections: list[tuple[str | None, list[str]]] = [(None, [])]  # (tên chương theo kiểu Heading, các đoạn)
    book_title: str | None = None
    toc_lines = 0
    for paragraph in _docx_paragraphs(body):
        style_node = paragraph.find(f"{W}pPr/{W}pStyle")
        style_id = style_node.get(f"{W}val", "") if style_node is not None else ""
        style = styles.get(style_id, style_id.casefold())
        if TOC_STYLE.fullmatch(style):
            # Mục lục Word tự sinh (kiểu "toc 1".."toc 9"): không phải chữ của truyện, và dòng "Chương N … 3" của nó sẽ bị
            # nhận nhầm là tiêu đề chương.
            toc_lines += 1
            continue
        for line in _join_wrapped([_words(line) for line in _docx_text(paragraph)]):
            if not line:
                continue
            if style in {"heading 1", "heading 2", "heading1", "heading2"}:
                sections.append((line, []))
            else:
                if style == "title" and book_title is None:
                    book_title = line
                sections[-1][1].append(line)
    result = ImportedBook(title=meta_title or book_title or title_from_filename(path.stem), author=meta_author, language=meta_language)
    if toc_lines:
        result.notes.append(f"Bỏ qua mục lục của tài liệu ({toc_lines} dòng).")
    if len(sections) == 1:
        # Không có kiểu Heading: tách theo dòng "Chương N" (như PDF).
        result.chapters, notes = _split_on_headings(sections[0][1], result.title)
        result.notes += notes
        return result
    for title, paragraphs in sections:
        if title is None:
            if paragraphs:
                result.chapters.append(Chapter(PREAMBLE, "\n\n".join(paragraphs)))
        elif paragraphs:
            result.chapters.append(Chapter(title, "\n\n".join(paragraphs)))
        else:
            result.notes.append(f"Bỏ qua mục trống: {title}")
    return result


# --- Chia chương theo dòng tiêu đề (DOCX không có Heading, PDF) -------------------------------------------------------

def is_heading_line(line: str, pattern: re.Pattern[str] = HEADING) -> bool:
    return len(line.strip()) <= MAX_HEADING and pattern.match(line) is not None


def _split_on_headings(paragraphs: list[str], book_title: str) -> tuple[list[Chapter], list[str]]:
    """Chữ trước tiêu đề đầu tiên thành chương "Mở đầu" (không bỏ đi); không có tiêu đề nào thì cả file là một chương."""
    chapters: list[Chapter] = []
    notes: list[str] = []
    title: str | None = None
    body: list[str] = []

    def close() -> None:
        if title is None:
            if body:
                chapters.append(Chapter(PREAMBLE if any_heading else book_title, "\n\n".join(body)))
        elif body:
            chapters.append(Chapter(title, "\n\n".join(body)))
        else:
            notes.append(f"Bỏ qua mục trống: {title}")

    any_heading = any(is_heading_line(paragraph) for paragraph in paragraphs)
    for paragraph in paragraphs:
        if is_heading_line(paragraph):
            close()
            title, body = paragraph.strip(), []
        else:
            body.append(paragraph)
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
