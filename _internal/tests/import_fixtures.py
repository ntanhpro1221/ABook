"""Bộ ví dụ DÙNG CHUNG cho bộ nhập sách (abook/importers.py, docs/LISTEN_ANYTHING.md mục 2): pytest và test JVM của app Android
(BookImportTest.kt) cùng đọc `tests/fixtures/import/` - hai bản cài (Python, Kotlin) phải ra ĐÚNG những chương này.

    fixtures/import/epub3.epub, epub2.epub   EPUB3 (nav, bìa properties="cover-image") và EPUB2 (NCX, bìa <meta name="cover">)
    fixtures/import/headings.docx            DOCX có kiểu Heading 1/2, Title, tab, xuống dòng cứng, chữ đã xoá, bảng
    fixtures/import/plain.docx               DOCX không có kiểu Heading: tách theo dòng "Chương N"
    fixtures/import/story.pdf                PDF có lớp chữ: tiêu đề chạy, số trang, đoạn vắt qua trang, gạch nối cuối dòng
    fixtures/import/scan.pdf                 PDF không có lớp chữ (scan) -> lỗi "cần OCR"
    fixtures/import/txt/                     thư mục TXT: UTF-8 có BOM + CRLF, UTF-16 LE, cp1258, thứ tự tự nhiên (1, 2, 10)
    fixtures/import/expected/<tên>.json      kết quả mong đợi (ImportedBook.to_dict, hay {"error": ...})
    fixtures/import/pages/story.pages.json   lớp thô của PDF (pypdf VÀ pdf.js phải ra đúng các dòng này)

Toàn chữ tự viết, không trích truyện nào. Sinh lại: runtime/.venv/Scripts/python.exe -m tests.import_fixtures (chỉ khi cố ý đổi
hành vi hay bộ ví dụ). File zip dùng giờ cố định nên sinh lại ra đúng từng byte.
"""
from __future__ import annotations

import io
import json
import struct
import sys
import textwrap
import unicodedata
import zipfile
import zlib
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "import"
STAMP = (2020, 1, 1, 0, 0, 0)

BOOK_TITLE = "Chuyến phà cuối ngày"
AUTHOR = "Lê Thử Nghiệm"
CHAPTERS: list[tuple[str, list[str]]] = [
    ("Chương 1: Bến phà lúc bình minh", [
        "Sương còn phủ kín mặt sông khi ông Tám đẩy chiếc phà ra khỏi bến. Tiếng máy nổ trầm đục vang lên giữa buổi sớm yên ắng, "
        "và đàn cò giật mình bay tản vào những lùm bần ven bờ.",
        "“Hôm nay nước lớn,” ông nói với cậu bé đứng bên mạn thuyền. “Con giữ chắc cây sào, đừng để phà trôi vào bãi.”",
        "Cậu bé gật đầu, siết chặt cây sào tre trong đôi bàn tay nhỏ. Cậu chưa từng thấy dòng sông nào rộng đến thế.",
    ]),
    ("Chương 2: Người khách lạ", [
        "Chuyến đầu tiên chỉ có một hành khách. Người đàn ông mặc chiếc áo mưa cũ, mang theo một cái hộp gỗ buộc dây cẩn thận, "
        "ngồi lặng lẽ ở đầu phà suốt quãng đường.",
        "— Ông đi đâu mà sớm vậy? — cậu bé hỏi.",
        "— Về quê thôi, cháu ạ. — Người lạ mỉm cười. — Mát-xcơ-va xa lắm, còn quê ta thì ngay bên kia sông.",
    ]),
    ("Chương 3: Cơn mưa cuối mùa", [
        "Mưa kéo đến lúc xế chiều, nặng hạt và lạnh. Ông Tám cho phà cập bến sớm hơn mọi hôm, buộc dây thật chặt vào cột sắt "
        "rồi đứng nhìn những giọt nước nhảy múa trên mặt sông.",
        "Cậu bé ngồi co chân trong khoang, nghe tiếng mưa gõ lên mái tôn như một bản nhạc không đầu không cuối.",
    ]),
]

# --- zip xác định -----------------------------------------------------------------------------------------------------

def _zip(entries: list[tuple[str, bytes]], *, stored_first: str | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in entries:
            info = zipfile.ZipInfo(name, STAMP)
            info.compress_type = zipfile.ZIP_STORED if name == stored_first else zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    return buffer.getvalue()


def _png(color: tuple[int, int, int], size: int = 8) -> bytes:
    """Một ảnh PNG đơn sắc nhỏ - bìa giả (chỉ cần đúng byte, không cần đẹp)."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    rows = b"".join(b"\x00" + bytes(color) * size for _ in range(size))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)) \
        + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b"")


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --- EPUB -------------------------------------------------------------------------------------------------------------

CONTAINER = ('<?xml version="1.0"?>\n<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
             '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>\n</container>')


def _xhtml(body: str, head: str = "") -> bytes:
    return ('<?xml version="1.0" encoding="utf-8"?>\n<html xmlns="http://www.w3.org/1999/xhtml"><head><title>x</title>'
            f'{head}</head><body>\n{body}\n</body></html>').encode("utf-8")


def build_epub3() -> bytes:
    ch1 = _xhtml(f"<h1>{_esc(CHAPTERS[0][0])}</h1>\n" + "\n".join(f"<p>{_esc(p)}</p>" for p in CHAPTERS[0][1])
                 + "\n<p>Nước&#160;lớn&nbsp;dần.</p>\n<script>nothing()</script>", "<style>p{margin:0}</style>")
    ch2 = _xhtml(f"<h2>{_esc(CHAPTERS[1][0])}</h2>\n<p>Dịch: Nhóm Lục Bình</p>\n"
                 + "\n".join(f"<p>{_esc(p)}</p>" for p in CHAPTERS[1][1]))
    ch3 = _xhtml("<div><h1>Cơn mưa cuối mùa</h1><div><p>" + CHAPTERS[2][1][0].replace(". ", ".<br/>") + "</p></div>"
                 f"<p>{_esc(CHAPTERS[2][1][1])}</p></div>")
    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{BOOK_TITLE}</dc:title><dc:creator>{AUTHOR}</dc:creator><dc:language>vi</dc:language>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="cover-img" href="images/bia.png" media-type="image/png" properties="cover-image"/>
    <item id="cover" href="text/cover.xhtml" media-type="application/xhtml+xml"/>
    <item id="title" href="text/title.xhtml" media-type="application/xhtml+xml"/>
    <item id="c1" href="text/ch1.xhtml" media-type="application/xhtml+xml"/>
    <item id="c2" href="text/ch%202.xhtml" media-type="application/xhtml+xml"/>
    <item id="c3" href="text/ch3.xhtml" media-type="application/xhtml+xml"/>
    <item id="back" href="text/back.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="cover"/><itemref idref="title"/><itemref idref="c1"/><itemref idref="c2"/><itemref idref="c3"/>
  <itemref idref="back" linear="no"/></spine>
</package>"""
    nav = ('<?xml version="1.0" encoding="utf-8"?>\n<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
           '<body><nav epub:type="toc"><ol>\n'
           f'<li><a href="text/ch1.xhtml">{_esc(CHAPTERS[0][0])}</a></li>\n'
           f'<li><a href="text/ch%202.xhtml#start">{_esc(CHAPTERS[1][0])}</a></li>\n'
           '<li><a href="text/ch3.xhtml">Chương 3</a></li>\n</ol></nav></body></html>')
    entries = [
        ("mimetype", b"application/epub+zip"), ("META-INF/container.xml", CONTAINER.encode()), ("OEBPS/content.opf", opf.encode()),
        ("OEBPS/nav.xhtml", nav.encode()), ("OEBPS/images/bia.png", _png((30, 90, 160))),
        ("OEBPS/text/cover.xhtml", _xhtml('<div><img src="../images/bia.png" alt=""/></div>')),
        ("OEBPS/text/title.xhtml", _xhtml(f"<p>{BOOK_TITLE}</p>")),
        ("OEBPS/text/ch1.xhtml", ch1), ("OEBPS/text/ch 2.xhtml", ch2), ("OEBPS/text/ch3.xhtml", ch3),
        ("OEBPS/text/back.xhtml", _xhtml("<p>" + "Trang này không nằm trong thứ tự đọc chính của sách nên bị bỏ qua hoàn toàn. " * 3 + "</p>")),
    ]
    return _zip(entries, stored_first="mimetype")


def build_epub2() -> bytes:
    pages = []
    for number, (title, paragraphs) in enumerate(CHAPTERS, start=1):
        short = title.split(": ", 1)[1]
        pages.append((f"text/c{number}.xhtml", _xhtml(f"<h2>{_esc(short)}</h2>\n" + "\n".join(f"<p>{_esc(p)}</p>" for p in paragraphs))))
    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>{BOOK_TITLE} (EPUB 2)</dc:title><dc:creator opf:role="aut">{AUTHOR}</dc:creator><dc:language>vi-VN</dc:language>
    <meta name="cover" content="cover-image"/>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="cover-image" href="bia.jpg" media-type="image/jpeg"/>
    <item id="a" href="text/c1.xhtml" media-type="application/xhtml+xml"/>
    <item id="b" href="text/c2.xhtml" media-type="application/xhtml+xml"/>
    <item id="c" href="text/c3.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine toc="ncx"><itemref idref="a"/><itemref idref="b"/><itemref idref="c"/></spine>
</package>"""
    points = "".join(
        f'<navPoint id="n{number}" playOrder="{number}"><navLabel><text>{_esc(title)}</text></navLabel>'
        f'<content src="text/c{number}.xhtml"/></navPoint>' for number, (title, _p) in enumerate(CHAPTERS, start=1))
    ncx = ('<?xml version="1.0" encoding="utf-8"?>\n<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
           f'<head/><docTitle><text>x</text></docTitle><navMap>{points}</navMap></ncx>')
    entries = [("mimetype", b"application/epub+zip"), ("META-INF/container.xml", CONTAINER.encode()),
               ("OEBPS/content.opf", opf.encode()), ("OEBPS/toc.ncx", ncx.encode()), ("OEBPS/bia.jpg", b"\xff\xd8\xff\xe0not-really-a-jpeg\xff\xd9")]
    entries += [(f"OEBPS/{name}", data) for name, data in pages]
    return _zip(entries, stored_first="mimetype")


# --- DOCX -------------------------------------------------------------------------------------------------------------

W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
STYLES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles {W_NS}>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/></w:style>
  <w:style w:type="paragraph" w:styleId="Tieude1"><w:name w:val="heading 1"/></w:style>
</w:styles>"""


def _para(text: str = "", style: str | None = None, *, runs: str | None = None) -> str:
    props = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    body = runs if runs is not None else (f'<w:r><w:t xml:space="preserve">{_esc(text)}</w:t></w:r>' if text else "")
    return f"<w:p>{props}{body}</w:p>"


def _docx(body: str, core: str | None) -> bytes:
    document = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document {W_NS}><w:body>{body}</w:body></w:document>'
    content_types = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="xml" ContentType="application/xml"/></Types>')
    entries = [("[Content_Types].xml", content_types.encode()), ("word/document.xml", document.encode()),
               ("word/styles.xml", STYLES.encode())]
    if core:
        entries.append(("docProps/core.xml", core.encode()))
    return _zip(entries)


def build_docx_headings() -> bytes:
    core = ('<?xml version="1.0" encoding="UTF-8"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>' + BOOK_TITLE + '</dc:title><dc:creator>' + AUTHOR
            + '</dc:creator><dc:language>vi-VN</dc:language></cp:coreProperties>')
    body = _para(BOOK_TITLE, "Title") + _para("Một câu đề tặng đứng trước chương đầu tiên.")
    body += _para(CHAPTERS[0][0], "Heading1")
    body += _para(CHAPTERS[0][1][0])
    body += _para(runs='<w:r><w:t>Hai dòng</w:t><w:tab/><w:t>có tab</w:t><w:br/><w:t>và xuống dòng cứng.</w:t></w:r>')
    body += _para(runs='<w:r><w:t xml:space="preserve">Câu giữ lại </w:t></w:r><w:del w:id="1"><w:r><w:delText>câu đã xoá </w:delText></w:r></w:del>'
                       '<w:ins w:id="2"><w:r><w:t>và câu thêm vào.</w:t></w:r></w:ins>')
    body += _para(CHAPTERS[1][0], "Heading1")
    body += "<w:tbl><w:tr><w:tc>" + _para("Ô bảng thứ nhất.") + "</w:tc><w:tc>" + _para("Ô bảng thứ hai.") + "</w:tc></w:tr></w:tbl>"
    body += _para(CHAPTERS[1][1][1])
    body += _para("Phần phụ trong chương hai", "Heading2") + _para(CHAPTERS[1][1][2])
    body += _para("Một mục không có chữ", "Tieude1")
    body += _para(CHAPTERS[2][0], "Heading1") + _para(CHAPTERS[2][1][0])
    return _docx(body, core)


def build_docx_plain() -> bytes:
    body = _para("Truyện không có kiểu tiêu đề") + _para("Lời dẫn nằm trước chương đầu.")
    for title, paragraphs in CHAPTERS[:2]:
        body += _para(title)
        for paragraph in paragraphs[:2]:
            body += _para(paragraph)
    body += _para("Chương trình truyền hình hôm ấy kéo dài đến tận khuya, ai cũng mệt nhoài.")
    return _docx(body, None)


# --- PDF (viết tay, chữ qua font Identity-H + ToUnicode nên pypdf và pdf.js đọc ra đúng Unicode) --------------------------

def build_pdf(pages: list[list[str]], title: str | None = None, author: str | None = None) -> bytes:
    """Mỗi trang là danh sách dòng chữ (đặt từ trên xuống, 16 pt một dòng); dòng đầu và cuối trang đặt sát mép như tiêu đề chạy /
    số trang. Trang không có dòng nào chỉ có một hình chữ nhật (PDF scan)."""
    chars = sorted({ch for lines in pages for line in lines for ch in line})
    cid = {ch: index + 1 for index, ch in enumerate(chars)}
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    def hex16(text: str) -> str:
        return "".join(f"{cid[ch]:04X}" for ch in text)

    def utf16(text: str) -> str:
        return "<FEFF" + text.encode("utf-16-be").hex().upper() + ">"

    catalog, tree = add(b""), add(b"")
    font = add(b"")
    cid_font, descriptor, unicode_map = add(b""), add(b""), add(b"")
    bfchars = "\n".join(f"<{cid[ch]:04X}> <{ord(ch):04X}>" for ch in chars)
    cmap = ("/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /Adobe-Identity-UCS def /CMapType 2 def\n"
            "1 begincodespacerange <0000> <FFFF> endcodespacerange\n" + (f"{len(chars)} beginbfchar\n{bfchars}\nendbfchar\n" if chars else "")
            + "endcmap CMapName currentdict /CMap defineresource pop end end").encode("ascii")
    objects[unicode_map - 1] = b"<< /Length %d >>\nstream\n" % len(cmap) + cmap + b"\nendstream"
    objects[descriptor - 1] = (b"<< /Type /FontDescriptor /FontName /AbookSample /Flags 4 /FontBBox [0 -200 1000 900] "
                               b"/ItalicAngle 0 /Ascent 800 /Descent -200 /CapHeight 700 /StemV 80 >>")
    objects[cid_font - 1] = (b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /AbookSample /CIDSystemInfo << /Registry (Adobe) "
                             b"/Ordering (Identity) /Supplement 0 >> /FontDescriptor %d 0 R /DW 600 /CIDToGIDMap /Identity >>" % descriptor)
    objects[font - 1] = (b"<< /Type /Font /Subtype /Type0 /BaseFont /AbookSample /Encoding /Identity-H /DescendantFonts [%d 0 R] "
                         b"/ToUnicode %d 0 R >>" % (cid_font, unicode_map))
    page_ids = []
    for lines in pages:
        if lines:
            ops = ["BT /F1 11 Tf"]
            y = 790.0
            for index, line in enumerate(lines):
                position = 40.0 if index == len(lines) - 1 else y  # dòng cuối: số trang sát mép dưới
                ops.append(f"1 0 0 1 56 {position:.0f} Tm <{hex16(line)}> Tj")
                y -= 16
            ops.append("ET")
            stream = "\n".join(ops).encode("ascii")
        else:
            stream = b"0.5 g 50 50 400 600 re f"
        content = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        page_ids.append(add(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
                            % (tree, font, content)))
    objects[tree - 1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (" ".join(f"{i} 0 R" for i in page_ids).encode(), len(page_ids))
    objects[catalog - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % tree
    info = ""
    if title:
        info += f"/Title {utf16(title)} "
    if author:
        info += f"/Author {utf16(author)} "
    info_id = add(f"<< {info}>>".encode("ascii")) if info else 0
    out = io.BytesIO()
    out.write(b"%PDF-1.5\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number + body + b"\nendobj\n")
    start = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    trailer = b"<< /Size %d /Root %d 0 R" % (len(objects) + 1, catalog) + (b" /Info %d 0 R" % info_id if info_id else b"") + b" >>"
    out.write(b"trailer\n" + trailer + b"\nstartxref\n%d\n%%%%EOF\n" % start)
    return out.getvalue()


def story_pdf_pages() -> list[list[str]]:
    """Chữ của PDF mẫu, đã dàn trang: tiêu đề chạy ở đầu mỗi trang, "Trang N" ở cuối, đoạn văn vắt qua trang."""
    lines: list[str] = []
    for title, paragraphs in CHAPTERS:
        lines.append(title)
        for paragraph in paragraphs:
            lines.extend(textwrap.wrap(paragraph, width=56))

    def break_inside(word: str, head_end: int, join: str) -> None:
        """Ép một chỗ ngắt dòng ngay trong `word` (sau `head_end` ký tự đầu), dòng trên kết thúc bằng `join`."""
        for index, line in enumerate(lines):
            if word in line:
                before, after = line.split(word, 1)
                lines[index:index + 1] = [before + word[:head_end] + join, word[head_end:] + after]
                return
        raise ValueError(word)

    break_inside("Mát-xcơ-va", 4, "")  # gạch nối THẬT của tên riêng nằm cuối dòng: giữ nguyên, chỉ nối liền
    per_page = 8
    pages = []
    for number, start in enumerate(range(0, len(lines), per_page), start=1):
        pages.append(["TRUYỆN THỬ NGHIỆM", *lines[start:start + per_page], f"Trang {number}"])
    return pages


def build_story_pdf() -> bytes:
    return build_pdf(story_pdf_pages(), BOOK_TITLE, AUTHOR)


def build_scan_pdf() -> bytes:
    return build_pdf([[], [], []])


# --- TXT --------------------------------------------------------------------------------------------------------------

def encode_cp1258(text: str) -> bytes:
    out = bytearray()
    for char in text:
        try:
            out += char.encode("cp1258")
            continue
        except UnicodeEncodeError:
            pass
        decomposed = unicodedata.normalize("NFD", char)
        for cut in range(len(decomposed) - 1, 0, -1):  # phần đầu gộp lại được một chữ cp1258 có sẵn, phần còn lại là dấu rời
            head = unicodedata.normalize("NFC", decomposed[:cut])
            try:
                out += head.encode("cp1258") + decomposed[cut:].encode("cp1258")
                break
            except UnicodeEncodeError:
                continue
        else:
            raise ValueError(f"cp1258 không có {char!r}")
    return bytes(out)


def txt_files() -> dict[str, bytes]:
    one = "Sương sớm\r\n\r\n\r\nChuyến phà đầu tiên rời bến lúc năm giờ.   \r\nCậu bé đứng ở mạn thuyền.\r\n"
    two = "Chương hai\n\nTiếng máy nổ trầm đục.\n"
    three = "Chương ba\n\nDịch: Nhóm Lục Bình\n\nMưa rơi suốt chiều.\n"
    return {
        "1.txt": "﻿".encode("utf-8") + one.encode("utf-8"),
        "2.txt": b"\xff\xfe" + two.encode("utf-16-le"),
        "10.txt": encode_cp1258(three),
        "9 Ngoại truyện.txt": "Một chương viết bằng UTF-8 thường, không BOM.\n".encode("utf-8"),
        "ghi chu.md": b"Not a chapter: the importer only takes .txt files.\n",
    }


# --- toàn bộ ----------------------------------------------------------------------------------------------------------

SOURCES = {
    "epub3.epub": build_epub3, "epub2.epub": build_epub2, "headings.docx": build_docx_headings, "plain.docx": build_docx_plain,
    "story.pdf": build_story_pdf, "scan.pdf": build_scan_pdf,
}


def dumps(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def source_files() -> dict[str, bytes]:
    """Mọi file đầu vào của bộ ví dụ (đường tương đối trong FIXTURES -> byte)."""
    files = {name: build() for name, build in SOURCES.items()}
    files.update({f"txt/{name}": data for name, data in txt_files().items()})
    return files


def expected_files(root: Path) -> dict[str, bytes]:
    """Kết quả mong đợi, tính bằng chính bản Python trên các file nguồn ở `root` (Kotlin phải ra y hệt)."""
    from abook import importers

    out: dict[str, bytes] = {}
    for name in [*SOURCES, "txt"]:
        stem = name.rsplit(".", 1)[0] if name != "txt" else "txt"
        try:
            value = importers.import_text(root / name).to_dict()
        except importers.ImportFailed as error:
            value = {"error": str(error)}
        out[f"expected/{stem}.json"] = dumps(value)
    pages, title, author = importers.pdf_pages(root / "story.pdf")
    out["pages/story.pages.json"] = dumps({"title": title, "author": author, "pages": pages})
    return out


def generate() -> None:
    for relative, data in source_files().items():
        target = FIXTURES / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    for relative, data in expected_files(FIXTURES).items():
        target = FIXTURES / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    generate()
    print("generated", FIXTURES)
