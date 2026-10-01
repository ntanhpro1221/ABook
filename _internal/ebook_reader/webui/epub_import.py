"""Tạo sách từ file EPUB (01-10, chủ sách: "phần studio ưu tiên hơn").

Studio nhận các chương TXT (một file một chương). Một file EPUB được tách thành đúng dạng ấy - mỗi mục trong spine có chữ là
một chương, dòng đầu là tên chương (theo mục lục nav/NCX, không thì tiêu đề đầu tiên trong chương) - vào một thư mục trong
thư viện; phần còn lại của trình tạo sách (quét, xếp, đếm chữ, phân tích) không biết gì về EPUB.

EPUB là file người dùng tải từ đâu đó - không tin: chỉ đọc mục có tên trong manifest, không ghi tên file nào lấy từ gói (tên
chương là số thứ tự), giới hạn cỡ giải nén, và từ chối XML khai báo entity (không có defusedxml trong runtime).
"""
from __future__ import annotations

import hashlib
import posixpath
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree

MAX_MEMBER = 20 * 1024 * 1024  # một chương XHTML lớn hơn thế là bất thường
MAX_TOTAL = 300 * 1024 * 1024
MIN_CHARS = 80  # mục ngắn hơn (bìa, trang bản quyền) bỏ qua - trừ khi mục lục gọi nó là một chương
NS = {
    "c": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
    "ncx": "http://www.daisy.org/z3986/2005/ncx/",
    "x": "http://www.w3.org/1999/xhtml",
}
BLOCKS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "section", "article", "tr", "dd", "dt", "pre"}
HEADINGS = {"h1", "h2", "h3"}


class EpubError(ValueError):
    pass


def _xml(raw: bytes) -> ElementTree.Element:
    head = raw[:4096].decode("utf-8", errors="replace")
    if "<!ENTITY" in head.upper():
        raise EpubError("EPUB khai báo entity XML - không mở")
    try:
        return ElementTree.fromstring(raw)
    except ElementTree.ParseError as error:
        raise EpubError(f"EPUB hỏng: {error}") from error


class _Text(HTMLParser):
    """Chữ của một trang XHTML: mỗi khối (đoạn, tiêu đề, dòng danh sách, <br>) một dòng; bỏ script/style/head."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.heading = ""
        self._current: list[str] = []
        self._skip = 0
        self._in_heading = 0
        self._heading_text: list[str] = []

    def _flush(self) -> None:
        line = " ".join("".join(self._current).split())
        if line:
            self.lines.append(line)
        self._current = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001 - chữ ký của HTMLParser
        if tag in {"script", "style", "head", "title"}:
            self._skip += 1
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
                    self.heading = " ".join("".join(self._current).split())
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._current.append(data)

    def close(self) -> None:
        super().close()
        self._flush()


def _text(raw: bytes) -> tuple[str, list[str]]:
    parser = _Text()
    parser.feed(raw.decode("utf-8", errors="replace"))
    parser.close()
    return parser.heading, parser.lines


def _toc(book: zipfile.ZipFile, opf_dir: str, manifest: dict[str, tuple[str, str, str]], spine_toc: str) -> dict[str, str]:
    """Tên chương theo mục lục: href (không #) -> tên đầu tiên trỏ tới nó. EPUB3 nav trước, EPUB2 NCX sau."""
    titles: dict[str, str] = {}
    nav = next((href for href, _media, props in manifest.values() if "nav" in props.split()), "")
    if nav:
        root = _xml(_read(book, nav))
        nav_dir = posixpath.dirname(nav)
        for anchor in root.iter(f"{{{NS['x']}}}a"):
            href = anchor.get("href", "")
            label = " ".join("".join(anchor.itertext()).split())
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
                titles.setdefault(src, " ".join(label.text.split()))
    return titles


def _read(book: zipfile.ZipFile, name: str) -> bytes:
    try:
        info = book.getinfo(name)
    except KeyError as error:
        raise EpubError(f"EPUB thiếu {name}") from error
    if info.file_size > MAX_MEMBER:
        raise EpubError(f"{name} trong EPUB quá lớn")
    return book.read(info)


def chapters(path: Path) -> list[tuple[str, list[str]]]:
    """(tên chương, các dòng) theo thứ tự đọc của EPUB."""
    try:
        book = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as error:
        raise EpubError(f"Không mở được EPUB: {error}") from error
    with book:
        if sum(info.file_size for info in book.infolist()) > MAX_TOTAL:
            raise EpubError("EPUB giải nén quá lớn")
        container = _xml(_read(book, "META-INF/container.xml"))
        rootfile = container.find(".//c:rootfile", NS)
        if rootfile is None or not rootfile.get("full-path"):
            raise EpubError("EPUB không có rootfile")
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
            raise EpubError("EPUB không có spine")
        titles = _toc(book, opf_dir, manifest, spine.get("toc", ""))
        result: list[tuple[str, list[str]]] = []
        for itemref in spine.iterfind("opf:itemref", NS):
            if itemref.get("linear", "yes") == "no":
                continue
            href, media, props = manifest.get(itemref.get("idref", ""), ("", "", ""))
            if not href or "nav" in props.split() or "html" not in media:
                continue
            heading, lines = _text(_read(book, href))
            listed = titles.get(href, "")
            if not lines or (sum(len(line) for line in lines) < MIN_CHARS and not listed):
                continue
            title = listed or heading or lines[0][:80]
            if lines and " ".join(lines[0].split()) == title:
                lines = lines[1:]
            result.append((title, lines))
        if not result:
            raise EpubError("EPUB không có chương nào có chữ")
        return result


def title_of(path: Path) -> str:
    """Tên sách trong metadata (dc:title), không có thì tên file."""
    try:
        with zipfile.ZipFile(path) as book:
            container = _xml(_read(book, "META-INF/container.xml"))
            rootfile = container.find(".//c:rootfile", NS)
            opf = _xml(_read(book, rootfile.get("full-path", ""))) if rootfile is not None else None
    except (OSError, zipfile.BadZipFile, EpubError):
        return path.stem
    title = opf.find(".//{http://purl.org/dc/elements/1.1/}title") if opf is not None else None
    return " ".join((title.text or "").split()) if title is not None and (title.text or "").strip() else path.stem


def extract(path: Path, folder_root: Path) -> Path:
    """Tách EPUB thành thư mục chương TXT trong `folder_root` (đặt tên theo file + băm nội dung: mở lại cùng file thì dùng
    lại thư mục, file khác cùng tên không đè lên nhau). Trả về thư mục ấy."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", path.stem).strip() or "epub"
    folder = folder_root / f"{stem[:80]} - {digest}"
    if folder.is_dir() and any(folder.glob("*.txt")):
        return folder
    found = chapters(path)
    folder.mkdir(parents=True, exist_ok=True)
    width = max(4, len(str(len(found))))
    for index, (title, lines) in enumerate(found, start=1):
        body = "\n\n".join([title, *lines]) + "\n"
        (folder / f"{index:0{width}d}.txt").write_bytes(body.encode("utf-8"))
    return folder
