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
from dataclasses import dataclass, field
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
CREDIT_HEAD_LINES = 64  # số dòng đầu chương đưa cho `credit_lines` (nó chỉ xem 6 dòng có chữ đầu tiên)

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


class ImportFailed(ValueError):
    """Không nhập được; câu chữ cho người dùng đọc (nói lý do và cách khác để đi tiếp)."""


@dataclass
class Chapter:
    title: str
    text: str  # các đoạn cách nhau một dòng trống; KHÔNG gồm tên chương (trừ file TXT: nguyên văn file)


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
        }


def import_text(path: Path | str) -> ImportedBook:
    """Mở một thư mục TXT, hay file .epub / .docx / .pdf. Lỗi dự đoán được là `ImportFailed`."""
    path = Path(path)
    if path.is_dir():
        book = _txt_folder(path)
    elif path.is_file():
        suffix = path.suffix.casefold()
        if suffix == ".pdf":
            pages, title, author = pdf_pages(path)
            return import_pdf_pages(pages, path.stem, title, author)
        reader = {".epub": _epub, ".docx": _docx, ".txt": _txt_file}.get(suffix)
        if reader is None:
            raise ImportFailed(f"Chưa đọc được file {suffix or 'không có đuôi'} - dùng .epub, .docx, .pdf, .txt hay một thư mục TXT")
        book = reader(path)
    else:
        raise ImportFailed(f"Không thấy {path}.")
    return _finish(book)


def _finish(book: ImportedBook) -> ImportedBook:
    """Mọi định dạng đi qua đây: Unicode NFC, và gợi ý (không bỏ) dòng ghi công ở đầu chương."""
    book.title = _nfc(book.title)
    book.author = _nfc(book.author) if book.author else None
    for chapter in book.chapters:
        chapter.title, chapter.text = _nfc(chapter.title), _nfc(chapter.text)
    book.notes = [_nfc(note) for note in book.notes]
    if not book.chapters or not any(chapter.text.strip() for chapter in book.chapters):
        raise ImportFailed("Không có chương nào có chữ")
    if len(book.chapters) > 1:
        # File TXT rỗng (hay chỉ có khoảng trắng) không thành chương - nói ra, để số chương ít hơn số file có lý do.
        book.notes += [f"Bỏ qua mục không có chữ: {chapter.title}" for chapter in book.chapters if not chapter.text.strip()]
        book.chapters = [chapter for chapter in book.chapters if chapter.text.strip()]
    for number, chapter in enumerate(book.chapters, start=1):
        # Tên chương tính là một dòng của chương (cửa sổ 6 dòng đầu), như file chương mà Studio đọc.
        for line in credit_suggestions(book.chapter_source(chapter)):
            book.credits.append((number, line))
            book.notes.append(f"Gợi ý: chương {number} có dòng ghi công ở đầu - “{line}”. Có thể bỏ khỏi phần đọc, nhưng ABook không tự bỏ.")
    return book


def credit_suggestions(source: str) -> list[str]:
    """Dòng ghi công (người dịch, biên tập…) ở đầu một chương, `source` như file chương (`ImportedBook.chapter_source`): GỢI Ý để
    người nghe chọn bỏ khỏi phần đọc (lớp sửa `skip`), không bao giờ tự bỏ. Luật là của Studio (`text_processing.credit_lines`);
    chỉ đưa phần đầu chương - chuẩn hoá cả chương chỉ để xem 6 dòng là phần chậm nhất của cuốn hơn nghìn chương. Kotlin:
    BookImport.creditSuggestions."""
    from .text_processing import credit_lines

    return credit_lines("\n".join(source.split("\n", CREDIT_HEAD_LINES)[:CREDIT_HEAD_LINES]))


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


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
    return ImportedBook(title=folder.resolve().name, chapters=[_txt_chapter(file) for file in files], text_has_title=True)


def _txt_file(path: Path) -> ImportedBook:
    return ImportedBook(title=path.stem, chapters=[_txt_chapter(path)], text_has_title=True)


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

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "head", "title"}:
            self._skip = max(0, self._skip - 1)
        elif tag in BLOCKS:
            if tag in HEADINGS and self._in_heading:
                self._in_heading -= 1
                if not self.heading:
                    self.heading = _words("".join(self._current))
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


def _toc(book: zipfile.ZipFile, manifest: dict[str, tuple[str, str, str]], spine_toc: str) -> dict[str, str]:
    """Tên chương theo mục lục: href (không #) -> tên đầu tiên trỏ tới nó. EPUB3 nav trước, EPUB2 NCX sau."""
    titles: dict[str, str] = {}
    nav = next((href for href, _media, props in manifest.values() if "nav" in props.split()), "")
    if nav:
        root = _xml(_read(book, nav))
        nav_dir = posixpath.dirname(nav)
        for anchor in root.iter(f"{{{NS['x']}}}a"):
            href = anchor.get("href", "")
            label = _words("".join(anchor.itertext()))
            if href and label:
                titles.setdefault(posixpath.normpath(posixpath.join(nav_dir, unquote(href.split("#")[0]))), label)
    ncx = manifest.get(spine_toc, ("", "", ""))[0] or next(
        (href for href, media, _props in manifest.values() if media == "application/x-dtbncx+xml"), "")
    if ncx and not titles:
        root = _xml(_read(book, ncx))
        ncx_dir = posixpath.dirname(ncx)
        for point in root.iter(f"{{{NS['ncx']}}}navPoint"):
            label = point.find("ncx:navLabel/ncx:text", NS)
            content = point.find("ncx:content", NS)
            if label is not None and content is not None and (label.text or "").strip():
                src = posixpath.normpath(posixpath.join(ncx_dir, unquote(content.get("src", "").split("#")[0])))
                titles.setdefault(src, _words(label.text))
    return titles


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
        titles = _toc(book, manifest, spine.get("toc", ""))
        result = ImportedBook(title=_meta_text(opf, "title") or path.stem, author=_meta_text(opf, "creator"),
                              language=_meta_text(opf, "language"))
        cover = _epub_cover(book, opf, manifest)
        if cover:
            result.cover_bytes, result.cover_type = cover
        images = short = 0  # trang chỉ có ảnh, mục rất ngắn: một ghi chú đếm, không kể tên file trong gói
        for itemref in spine.iterfind("opf:itemref", NS):
            if itemref.get("linear", "yes") == "no":
                continue
            href, media, props = manifest.get(itemref.get("idref", ""), ("", "", ""))
            if not href or "nav" in props.split() or "html" not in media:
                continue
            page = _page(_read(book, href))
            lines, heading = page.lines, page.heading
            listed = titles.get(href, "")
            if not lines and page.images:
                images += 1
                continue
            if not lines:
                continue
            if sum(len(line) for line in lines) < MIN_CHARS and not listed:
                short += 1
                continue
            title = listed or heading or lines[0][:80]
            first = lines[0].casefold()
            # Dòng đầu là tiêu đề của chính chương: bỏ khi nó đã nằm trong tên chương ("Gặp gỡ" trong "Chương 2: Gặp gỡ"),
            # hay lấy nó làm tên khi nó đầy đủ hơn tên mục lục - không để người nghe nghe tên chương hai lần.
            if first == title.casefold() or (heading and first == heading.casefold() and first in title.casefold()):
                lines = lines[1:]
            elif heading and first == heading.casefold() and title.casefold() in first:
                title, lines = lines[0], lines[1:]
            result.chapters.append(Chapter(title, "\n\n".join(lines)))
        if images:
            result.notes.append(f"Bỏ qua {images} trang chỉ có ảnh.")
        if short:
            result.notes.append(f"Bỏ qua {short} mục rất ngắn (bìa, trang bản quyền?).")
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
        for line in _docx_text(paragraph):
            line = _words(line)
            if not line:
                continue
            if style in {"heading 1", "heading 2", "heading1", "heading2"}:
                sections.append((line, []))
            else:
                if style == "title" and book_title is None:
                    book_title = line
                sections[-1][1].append(line)
    result = ImportedBook(title=meta_title or book_title or path.stem, author=meta_author, language=meta_language)
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
            result.notes.append(f"Bỏ qua mục không có chữ: {title}")
    return result


# --- Chia chương theo dòng tiêu đề (DOCX không có Heading, PDF) -------------------------------------------------------

def is_heading_line(line: str) -> bool:
    return len(line.strip()) <= MAX_HEADING and HEADING.match(line) is not None


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
            notes.append(f"Bỏ qua mục không có chữ: {title}")

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
        label = _words(UNSAFE_NAME.sub(" ", chapter.title))[:50].strip(" .")
        (folder / f"{index:0{width}d}{' ' + label if label else ''}.txt").write_bytes(body.encode("utf-8"))
    cover = ""
    if book.cover_bytes:
        cover = "cover" + {"image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}.get(book.cover_type or "", ".jpg")
        (folder / cover).write_bytes(book.cover_bytes)
    info = {"title": book.title, "author": book.author, "language": book.language, "notes": book.notes, "cover": cover}
    sidecar.write_bytes(json.dumps(info, ensure_ascii=False, indent=1).encode("utf-8") + b"\n")
    return folder, info
