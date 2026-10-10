"""Bộ ví dụ DÙNG CHUNG cho bộ nhập sách (abook/importers.py, docs/LISTEN_ANYTHING.md mục 2): pytest và test JVM của app Android
(BookImportTest.kt) cùng đọc `tests/fixtures/import/` - hai bản cài (Python, Kotlin) phải ra ĐÚNG những chương này.

    fixtures/import/epub3.epub, epub2.epub   EPUB3 (nav, bìa properties="cover-image") và EPUB2 (NCX, bìa <meta name="cover">);
                                             EPUB3 có thực thể HTML (&ocirc; &#147; &copy không chấm phẩy) cả trong mục lục
    fixtures/import/split.epub               EPUB3 có nhiều chương trong MỘT file XHTML, mục lục trỏ vào mảnh (#id, <a name>); chữ dẫn
                                             trước mảnh đầu, mảnh không có trong trang, mục lẻ chỉ một mảnh
    fixtures/import/headings.docx           DOCX có kiểu Heading 1/2, Title, tab, xuống dòng cứng, chữ đã xoá, bảng, mục lục Word
    fixtures/import/plain.docx               DOCX không có kiểu Heading: tách theo dòng "Chương N"; viết bằng xmlns mặc định (không "w:")
    fixtures/import/story.pdf                PDF có lớp chữ: tiêu đề chạy (kèm số trang), số trang, đoạn vắt qua trang, gạch nối cuối dòng
    fixtures/import/scan.pdf                 PDF không có lớp chữ (scan) -> lỗi "cần OCR"
    fixtures/import/txt/                     thư mục TXT: UTF-8 có BOM + CRLF, UTF-16 LE, cp1258, thứ tự tự nhiên (1, 2, 10), file
                                             chỉ có khoảng trắng, file ".txt" không tên, "01"/"1" trùng số, chữ số Ả Rập
    fixtures/import/whole.txt                MỘT file TXT cả truyện: chữ dẫn trước chương đầu, ba dòng "Chương N", một dòng ghi công,
                                             câu văn mở đầu bằng "Chương trình" (không phải tiêu đề). expected/whole.json = KHÔNG tách
                                             (mặc định), expected/whole.split.json = người dùng tích "Tách thành N chương"
    fixtures/import/titled.txt               như whole.txt nhưng chữ dẫn chỉ là MỘT dòng tên truyện: tên sách = dòng ấy; tách thì không có
                                             chương "Mở đầu" (expected/titled.json, titled.split.json)
    fixtures/import/expected/keep_short.json epub3 và split đọc với keep_short=True: mục rất ngắn đứng đúng chỗ trong danh sách, short=true,
                                             `defaults` = các chương tích sẵn (không có mục ngắn), ghi chú "N mục rất ngắn chưa chọn"
    fixtures/import/expected/clip_title.json  bảng ví dụ của `importers.clip_title` (tên chương cắt ở ranh giới từ + "…"); hai bên cùng khớp
    fixtures/import/expected/name_title.json  bảng ví dụ của `importers.title_from_filename` (tên sách từ tên file: "_" và "--" thành dấu cách); hai bên cùng khớp
    fixtures/import/notes3.epub, notes2.epub, endnotes.epub, notes.docx   chú thích: EPUB3 (noteref + aside), Calibre (sup + a href), chương Endnotes
                                             kiểu Standard Ebooks, DOCX (footnotes.xml / endnotes.xml); expected/<tên>.fn_*.json = người nghe tích đề xuất
    fixtures/import/tail_credits.txt, tail_credits_epub.epub   chương kết bằng dòng ủng hộ / "đọc tại" / nguồn / converter (gợi ý, mặc định không bỏ) và ca âm (thoại, URL trong lời thoại)
    fixtures/import/expected/tail_credit_lines.json   từng dòng / từng đoạn cuối chương -> có gợi ý không (`tail_credit_suggestions`); hai bên cùng khớp
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
                 + "\n<p>&Ocirc;ng T&aacute;m c&#432;&#7901;i: &#147;Ph&agrave; c&#x169; r&#7891;i.&#148; &copy 1975 &abreve;</p>"
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
           f'<li><a href="text/ch1.xhtml">{_esc(CHAPTERS[0][0]).replace(" ", "&nbsp;", 1)}</a></li>\n'
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


SPLIT_PAD = "Nước sông vẫn chảy chậm qua những bãi bồi, mang theo mùi phù sa và tiếng gà gáy từ xóm bên kia."


def build_epub_split() -> bytes:
    """Nhiều chương trong MỘT file XHTML, mục lục (nav) trỏ vào các mảnh: book.xhtml (mục đầu không mảnh, hai mảnh `id` và `a name`,
    một mảnh không có trong trang), extra.xhtml (chữ dẫn trước mảnh đầu -> phần riêng), tail.xhtml (chữ dẫn ngắn -> bỏ), solo.xhtml
    (một mảnh duy nhất -> vẫn một chương như trước)."""
    pad = SPLIT_PAD
    book = _xhtml(
        "<h1>Chương 1: Bến sông</h1>\n<p>Buổi sáng ở bến sông bắt đầu bằng tiếng chèo khua nhẹ. " + pad + "</p>\n"
        "<p>Bà Sáu gánh hai thúng cá ra chợ sớm.</p>\n"
        '<h2 id="c2">Chương 2: Chợ nổi</h2>\n<p>Ghe xuồng chen nhau dưới cầu, ai cũng rao to hàng của mình. ' + pad + "</p>\n"
        '<div><a name="c3"></a><h2>Gặp gỡ</h2></div>\n<p>Chương ba mở ra bằng một cuộc gặp tình cờ giữa hai người bạn cũ. ' + pad + "</p>\n"
        "<p>Họ hẹn nhau chiều mai, cùng một bến.</p>")
    extra = _xhtml(
        "<p>Lời dẫn dài của người ghi chép, đứng trước phần đầu và không có mục nào trong mục lục gọi tên nó cả. " + pad + "</p>\n"
        '<h3 id="p1">Phần một</h3>\n<p>Phần một kể về con đường đất đỏ dẫn ra bến. ' + pad + "</p>\n"
        '<h3 id="p2">Phần hai</h3>\n<p>Phần hai kể về chiếc cầu tre bắc qua kênh nhỏ. ' + pad + "</p>")
    tail = _xhtml(
        "<p>Lời dẫn ngắn.</p>\n"
        '<p id="t1">Đoạn mở đầu của mục thứ nhất, đủ dài để không bị coi là trang trống. ' + pad + "</p>\n"
        '<p id="t2">Đoạn mở đầu của mục thứ hai, cũng đủ dài như vậy. ' + pad + "</p>")
    solo = _xhtml('<h2 id="top">Một mục lẻ</h2>\n<p>Chỉ có một mục lục trỏ vào file này, nên nó vẫn là một chương trọn vẹn. ' + pad + "</p>")
    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Sách một file nhiều chương</dc:title><dc:creator>{AUTHOR}</dc:creator><dc:language>vi</dc:language>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="book" href="text/book.xhtml" media-type="application/xhtml+xml"/>
    <item id="extra" href="text/extra.xhtml" media-type="application/xhtml+xml"/>
    <item id="tail" href="text/tail.xhtml" media-type="application/xhtml+xml"/>
    <item id="solo" href="text/solo.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="book"/><itemref idref="extra"/><itemref idref="tail"/><itemref idref="solo"/></spine>
</package>"""
    nav = ('<?xml version="1.0" encoding="utf-8"?>\n<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
           '<body><nav epub:type="toc"><ol>\n'
           '<li><a href="text/book.xhtml">Chương 1: Bến sông</a></li>\n'
           '<li><a href="text/book.xhtml#khong-co-mach-nay">Mục trỏ vào mảnh không có</a></li>\n'
           '<li><a href="text/book.xhtml#c2">Chương 2: Chợ nổi</a></li>\n'
           '<li><a href="text/book.xhtml#c3">Chương 3: Gặp gỡ</a></li>\n'
           '<li><a href="text/extra.xhtml#p1">Phần một</a></li>\n<li><a href="text/extra.xhtml#p2">Phần hai</a></li>\n'
           '<li><a href="text/tail.xhtml#t1">Mục thứ nhất</a></li>\n<li><a href="text/tail.xhtml#t2">Mục thứ hai</a></li>\n'
           '<li><a href="text/solo.xhtml#top">Một mục lẻ</a></li>\n</ol></nav></body></html>')
    entries = [("mimetype", b"application/epub+zip"), ("META-INF/container.xml", CONTAINER.encode()), ("OEBPS/content.opf", opf.encode()),
               ("OEBPS/nav.xhtml", nav.encode()), ("OEBPS/text/book.xhtml", book), ("OEBPS/text/extra.xhtml", extra),
               ("OEBPS/text/tail.xhtml", tail), ("OEBPS/text/solo.xhtml", solo)]
    return _zip(entries, stored_first="mimetype")


# --- EPUB hình dạng sách thật (soát a22): mỗi file một lỗi đã gặp, chữ tự viết ------------------------------------------

NAV_NS = 'xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"'
LINE = "Con đò chở khách qua sông từ sáng đến tối, mỗi chuyến chừng mười lăm phút, và người lái đò nhớ mặt từng người."


def _book(title: str, pages: list[tuple[str, str]], *, nav: str | None = None, ncx: str | None = None, extra: tuple[tuple[str, bytes, str], ...] = (),
          version: str = "3.0", raw_pages: dict[str, bytes] | None = None, drop: tuple[str, ...] = (), rename: dict[str, str] | None = None) -> bytes:
    """EPUB nhỏ: `pages` = [(tên file trong OEBPS/text, thân XHTML)] theo thứ tự đọc; `nav` / `ncx` = nội dung tệp mục lục (None = không có);
    `extra` = [(đường trong OEBPS, byte, media)] khai trong manifest; `raw_pages` thay byte của trang; `drop` = mục khai báo mà không có
    trong gói; `rename` = tên trong zip khác tên khai báo (zip NFD)."""
    items, spine, entries = [], [], []
    for number, (name, body) in enumerate(pages, start=1):
        items.append(f'<item id="p{number}" href="text/{name}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="p{number}"/>')
        entries.append((f"OEBPS/text/{name}", (raw_pages or {}).get(name) or _xhtml(body)))
    if nav is not None:
        items.append('<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>')
        entries.append(("OEBPS/nav.xhtml", f'<?xml version="1.0" encoding="utf-8"?>\n<html {NAV_NS}><body>{nav}</body></html>'.encode()))
    if ncx is not None:
        items.append('<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>')
        entries.append(("OEBPS/toc.ncx", ncx.encode()))
    for path, data, media in extra:
        items.append(f'<item id="x{len(items)}" href="{path}" media-type="{media}"/>')
        entries.append((f"OEBPS/{path}", data))
    toc_attr = ' toc="ncx"' if ncx is not None else ""
    opf = (f'<?xml version="1.0" encoding="utf-8"?>\n<package xmlns="http://www.idpf.org/2007/opf" version="{version}" unique-identifier="id">'
           f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>{title}</dc:title><dc:language>vi</dc:language></metadata>'
           f'<manifest>{"".join(items)}</manifest><spine{toc_attr}>{"".join(spine)}</spine></package>')
    entries = [(name, data) for name, data in entries if name not in drop]
    entries = [((rename or {}).get(name, name), data) for name, data in entries]
    return _zip([("mimetype", b"application/epub+zip"), ("META-INF/container.xml", CONTAINER.encode()), ("OEBPS/content.opf", opf.encode()),
                 *entries], stored_first="mimetype")


def build_nav_pages() -> bytes:
    """EPUB3 kiểu Project Gutenberg: tệp nav có <nav> mốc (landmarks) ĐỨNG TRƯỚC mục lục, và <nav> danh sách số trang trỏ vào giữa
    chương - chỉ <nav epub:type="toc"> là chương (BUG1)."""
    pages = [(f"c{n}.xhtml", f"<h2>Chương {n}</h2>\n<p>{LINE}</p>\n<p id=\"page{n}a\">{LINE}</p>\n<p id=\"page{n}b\">{LINE}</p>") for n in (1, 2)]
    nav = ('<nav epub:type="landmarks"><ol><li><a epub:type="bodymatter" href="text/c1.xhtml">Bắt đầu đọc</a></li></ol></nav>'
           '<nav epub:type="toc"><ol><li><a href="text/c1.xhtml">Chương 1: Bến đò</a></li><li><a href="text/c2.xhtml">Chương 2: Mưa</a></li></ol></nav>'
           '<nav epub:type="page-list"><ol>' + "".join(f'<li><a href="text/c{n}.xhtml#page{n}{k}">{n}{k}</a></li>' for n in (1, 2) for k in "ab")
           + "</ol></nav>")
    return _book("Mục lục có số trang", pages, nav=nav)


def _ncx(points: list[tuple[str, str]]) -> str:
    body = "".join(f'<navPoint id="n{number}"><navLabel><text>{_esc(label)}</text></navLabel><content src="{src}"/></navPoint>'
                   for number, (label, src) in enumerate(points, start=1))
    return f'<?xml version="1.0" encoding="utf-8"?>\n<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><navMap>{body}</navMap></ncx>'


def _chapters(count: int, *, names: str = "c{n}.xhtml") -> list[tuple[str, str]]:
    return [(names.format(n=n), f"<h1>Chương {n}: Bến số {n}</h1>\n<p>{LINE}</p>\n<p>{LINE}</p>") for n in range(1, count + 1)]


def build_toc_broken() -> bytes:
    """NCX hỏng XML (thẻ không đóng): không phải "file hỏng" - đọc theo spine, tên chương từ tiêu đề trong chữ, có ghi chú (BUG3)."""
    ncx = _ncx([("Chương 1", "text/c1.xhtml")]).replace("</text>", "", 1)
    return _book("Mục lục hỏng", _chapters(2), ncx=ncx, version="2.0")


def build_toc_missing() -> bytes:
    """Manifest khai toc.ncx và một trang của spine mà gói không có (tải chưa trọn): phần còn lại vẫn đọc được (BUG3)."""
    return _book("Thiếu tệp", _chapters(3), ncx=_ncx([]), version="2.0", drop=("OEBPS/toc.ncx", "OEBPS/text/c2.xhtml"))


def build_calibre_split() -> bytes:
    """Chương dài bị cắt thành nhiều file (Calibre: index_split_000, _001…), mục lục chỉ trỏ file đầu của mỗi chương: file sau NỐI vào
    chương trước (BUG2) - trừ file mở bằng tiêu đề chương riêng (mục lục thiếu chương 3) và trang tên sách / trang giới thiệu (BUG6)."""
    pages = [
        ("titlepage.xhtml", "<h1>Chuyến đò ngang</h1>\n<p>Lê Thử Nghiệm</p>"),
        ("index_split_000.xhtml", f"<h2>Chương 1: Bến đò</h2>\n<p>{LINE}</p>"),
        ("index_split_001.xhtml", f"<p>Phần sau của chương một, Calibre cắt ra file riêng. {LINE}</p>"),
        ("index_split_002.xhtml", f"<h2>Chương 2: Mưa</h2>\n<p>{LINE}</p>"),
        ("index_split_003.xhtml", f"<p>Phần sau của chương hai. {LINE}</p>"),
        ("index_split_004.xhtml", f"<p><b>Chương 3: Nước lên</b></p>\n<p>{LINE}</p>"),
        ("index_split_005.xhtml", f"<p>Phần sau của chương ba. {LINE}</p>"),
        ("about.xhtml", f"<p>Sách điện tử này được làm để thử, không bán. {LINE}</p>"),
    ]
    ncx = _ncx([("Chương 1: Bến đò", "text/index_split_000.xhtml"), ("Chương 2: Mưa", "text/index_split_002.xhtml")])
    return _book("Chương cắt nhiều file", pages, ncx=ncx, version="2.0")


def build_hoi_txt() -> bytes:
    """TXT cả truyện chia "Hồi thứ nhất / nhì / ba" (BUG4); "Hồi nhất định…" ở đầu câu không phải tiêu đề."""
    return ("Ba hồi trên sông\n\nHồi thứ nhất\nCon đò rời bến lúc trời còn tối.\n\nHồi thứ nhì\nMưa xuống trắng mặt sông.\n"
            "Hồi nhất định phải kể cho hết, ông lái nói thế.\n\nHồi thứ ba\nĐò cập bến bên kia.\n").encode()


def build_toc_txt() -> bytes:
    """TXT cả truyện mở bằng MỤC LỤC: các dòng "Chương N" liền nhau không có chữ là mục lục, không thành chương rỗng; tên sách không
    phải "MỤC LỤC" (BUG5). Phần mục lục ở lại trong "Mở đầu" (không bỏ chữ), có cờ "Mục lục" (BUG6)."""
    return ("MỤC LỤC\nChương 1: Bến đò\nChương 2: Mưa\nChương 3: Nước lên\n\n"
            f"Chương 1: Bến đò\n\n{LINE}\n\nChương 2: Mưa\n\n{LINE}\n\nChương 3: Nước lên\n\n{LINE}\n").encode()


def build_gutenberg_txt() -> bytes:
    """TXT kiểu Project Gutenberg (chữ tự viết): dòng đầu "The Project Gutenberg eBook of …", rồi "Title:" / "Author:", mục lục "CHAPTER I."
    liền nhau (BUG5) - tên sách / tác giả lấy từ "Title:" / "Author:", không phải cả câu đầu."""
    return ("﻿The Project Gutenberg eBook of Bến đò ngang\r\n\r\nBản này tự viết để thử, mượn hình dạng của sách Project Gutenberg.\r\n\r\n"
            "Title: Bến đò ngang\r\n\r\nAuthor: Lê Thử Nghiệm\r\n\r\n*** START OF THE PROJECT GUTENBERG EBOOK BẾN ĐÒ NGANG ***\r\n\r\n"
            "Contents\r\n\r\n CHAPTER I.   Bến\r\n CHAPTER II.  Mưa\r\n\r\n\r\n"
            f"CHAPTER I.\r\nBến\r\n\r\n{LINE}\r\n\r\nCHAPTER II.\r\nMưa\r\n\r\n{LINE}\r\n").encode()


# Dòng xin ủng hộ / quảng cáo / nguồn ở CUỐI chương (BUG11 của a22; `importers.tail_credit_suggestions`, Kotlin BookImport.tailCreditSuggestions): gợi ý, mặc định
# không bỏ gì. Chương 1: ủng hộ + "đọc tại"; chương 2: dòng ghi công ở đầu + nguồn / converter / "hết chương" ở cuối (có dòng "***" chen giữa); chương 3 chỉ có ca ÂM:
# thoại có chữ "ủng hộ", câu truyện nhắc ngân hàng, URL trong lời thoại, và dòng ủng hộ bị một câu truyện chen phía sau -> không gợi ý gì.
TAIL_CHAPTERS: list[tuple[str, list[str]]] = [
    ("Chương 1: Bến đò", [LINE, LINE, "Xin ủng hộ nhóm dịch: Momo 0912345678 - Agribank 1234567890123", "Đọc truyện mới nhất tại truyenthu.vn"]),
    ("Chương 2: Mưa", ["Dịch: Nhóm Lục Bình", LINE, LINE, "***", "Nguồn: truyenthu.vn", "Converter: Nhóm Lục Bình", "--- Hết chương ---"]),
    ("Chương 3: Nước lên", [LINE, "“Anh nhớ ủng hộ quán này nhé,” bà chủ quán nói với cậu bé.",
                            "Xin ủng hộ: Momo 0912345678",
                            "Rồi trời tạnh hẳn, người lái đò thả dây buộc đò vào cọc.",
                            "Anh đứng trước cửa ngân hàng Agribank rất lâu, rồi mới bước vào trong.",
                            "“Đọc truyện tại truyenthu.vn đi,” cô bảo."]),
]


# Từng dòng đứng một mình ở cuối chương (`importers.tail_credit_suggestions`, Kotlin tailCreditSuggestions): dòng xin ủng hộ / quảng cáo / nguồn thì được gợi ý,
# lời thoại, câu truyện nhắc ngân hàng, URL trong lời thoại, dòng quá dài thì KHÔNG (thà bỏ sót hơn gợi ý nhầm). expected/tail_credit_lines.json.
TAIL_LINE_CASES: list[tuple[str, bool]] = [(line, True) for line in [
    "Xin ủng hộ: Momo 0912345678", "Xin ủng hộ nhóm dịch qua Agribank 1234567890123", "Ủng hộ nhóm dịch tại Momo: 0912 345 678", "Donate paypal.me/nhomdich",
    "Ủng hộ qua PayPal: nhom@example.org", "Momo: 0912345678", "Vietcombank 0011001234567 - NGUYEN VAN A", "STK 123456789012 Techcombank",
    "Đọc truyện mới nhất tại truyenthu.vn", "Đọc chương mới nhất tại: truyenthu.vn - nhanh nhất", "Đọc full tại https://truyenthu.vn/doc/12",
    "Nguồn: truyenthu.vn", "Nguồn truyện: https://truyenthu.net/x", "Source: www.truyenthu.com", "Converter: Nhóm Lục Bình", "Translator: NicK",
    "https://truyenthu.vn/chuong-12", "www.truyenthu.vn", "truyenthu.vn/doc", "--- Hết chương ---", "[Hết chương 12]", "Hết chương",
]] + [(line, False) for line in [
    "“Anh nhớ ủng hộ quán này nhé,” bà chủ quán nói.", "— Xin ủng hộ cho quỹ này, ông nói.", "Anh đứng trước cửa ngân hàng Agribank rất lâu, rồi mới bước vào trong.",
    "“Đọc truyện tại truyenthu.vn đi,” cô bảo.", "Cô nói: xem trang www.truyenthu.vn đi nhé, rồi cô cười.", "Ủng hộ chính sách của thành phố, ông nói và rời đi.",
    "Đọc truyện cho con nghe vào buổi tối ở nhà.", "Nguồn: nơi sâu thẳm của con tim.", "- Nguồn: truyenthu.vn", "Hết.", "Ông ngồi nhìn dòng sông.",
    "Xin ủng hộ: " + "Momo 0912345678 " * 10,
]]
# Nhiều dòng: chuỗi liền nhau từ dòng cuối lên; câu truyện chen giữa thì dừng; dòng "***" bước qua; chỉ 6 dòng cuối được xét.
TAIL_SOURCE_CASES = [
    "Chương 1\n\nLời truyện.\n\nĐọc truyện mới nhất tại truyenthu.vn\nXin ủng hộ: Momo 0912345678\n",
    "Chương 1\n\nXin ủng hộ: Momo 0912345678\nRồi trời tạnh hẳn.\n",
    "Chương 1\n\nLời truyện.\n\n---\nNguồn: truyenthu.vn\n***\nXin ủng hộ: Momo 0912345678\n\n\n",
    "Chương 1\n" + "\n".join(f"Nguồn: truyenthu.vn/{n}" for n in range(1, 9)) + "\n",
    "Nguồn: truyenthu.vn\n",
]


def build_tail_credits_txt() -> bytes:
    """TXT cả truyện, ba chương kết bằng dòng ủng hộ / nguồn / ca âm (TAIL_CHAPTERS)."""
    nl = chr(10)
    chapters = (nl + nl).join(title + nl + nl + (nl + nl).join(lines) for title, lines in TAIL_CHAPTERS)
    return ("Chuyến đò có ghi công" + nl + nl + chapters + nl).encode()


def build_tail_credits_epub() -> bytes:
    """Như tail_credits.txt (tail_credits_epub.epub) nhưng EPUB3: mỗi chương một file, mỗi dòng một <p>."""
    pages = [(f"c{n}.xhtml", f"<h2>{_esc(title)}</h2>" + chr(10) + chr(10).join(f"<p>{_esc(line)}</p>" for line in lines))
             for n, (title, lines) in enumerate(TAIL_CHAPTERS, start=1)]
    items = "".join(f'<li><a href="text/c{n}.xhtml">{_esc(title)}</a></li>' for n, (title, _lines) in enumerate(TAIL_CHAPTERS, start=1))
    return _book("Chuyến đò có ghi công", pages, nav='<nav epub:type="toc"><ol>' + items + "</ol></nav>")


HIDDEN_CSS = ("/* ẩn */ .an { display: none } span.so-trang, #ghi.chu { visibility: hidden !important }\n"
              "@media print { .chi-khi-in { display: none } }\n.dep { color: #333 } p a { display: none }")


def build_hidden() -> bytes:
    """Chữ ẩn của nguồn HTML (BUG7) và cách đọc ruby (BUG14): không lọt vào chữ. Luật CSS trong @media print và bộ chọn phức tạp không
    tính; <img aria-hidden> (thẻ rỗng) không nuốt phần sau; chú thích <aside epub:type="footnote"> vẫn ở lại (không bỏ chữ)."""
    body = (f"<h2>Chương 1: Chữ ẩn</h2>\n<p>{LINE}</p>\n<p class=\"an\">CSS_AN đăng lại xin ghi nguồn.</p>\n"
            "<div hidden=\"hidden\"><p>THUOC_TINH_HIDDEN</p></div>\n<p aria-hidden=\"true\">ARIA_AN</p>\n"
            "<p class=\"dep\">Câu có <span style=\"display: none\">STYLE_AN</span>chữ ẩn giữa câu<span class=\"so-trang\">SO_TRANG_CSS</span>"
            "<span epub:type=\"pagebreak\" id=\"page7\" title=\"7\">7</span> và <img aria-hidden=\"true\" src=\"x.png\" alt=\"\"/>vẫn liền mạch.</p>\n"
            "<p id=\"ghi\" class=\"chu\">ID_LOP_AN</p>\n<p class=\"chi-khi-in\">Chỉ ẩn khi in, trên màn hình vẫn đọc.</p>\n"
            "<p>Đọc <a href=\"#x\">liên kết</a> như chữ thường.</p>\n<noscript><p>NOSCRIPT</p></noscript>\n"
            "<p>Cô ấy dùng <ruby>魔法<rp>(</rp><rt>まほう</rt><rp>)</rp></ruby> thật.</p>\n"
            "<p span=\"x\">Câu có chú thích.</p>\n<aside epub:type=\"footnote\" id=\"n1\"><p>Lời chú thích vẫn ở lại.</p></aside>")
    return _book("Chữ ẩn", [("c1.xhtml", body)], extra=(("style/main.css", HIDDEN_CSS.encode(), "text/css"),),
                 raw_pages={"c1.xhtml": _xhtml(body, '<link rel="stylesheet" href="../style/main.css"/>').replace(
                     b'xmlns="http://www.w3.org/1999/xhtml"', b'xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"')})


def build_dropcap() -> bytes:
    """Chữ cái đầu chương vẽ bằng ảnh, alt là đúng chữ ấy (BUG8): "M" + "ọi chuyện" = "Mọi chuyện"; ảnh minh hoạ có alt dài, hay alt một
    chữ mà chữ sau cách ra, thì không ghép."""
    body = (f"<h2>Chương 1: Bến đò</h2>\n<p><img class=\"dropcap\" src=\"m.png\" alt=\"M\"/><span class=\"smcap\">ọi chuyện</span> bắt đầu ở bến. {LINE}</p>\n"
            f"<p><img src=\"h.png\" alt=\"Hình minh hoạ bến đò\"/>Ảnh trên là bến đò.</p>\n<p><img src=\"a.png\" alt=\"A\"/> rời ra một quãng.</p>")
    return _book("Chữ cái đầu bằng ảnh", [("c1.xhtml", body)])


def build_glued() -> bytes:
    """Thẻ làm dính chữ (BUG9): ô bảng, hr giữa chữ trần, figure / figcaption, aside, <pre> giữ xuống dòng, số chú thích <sup>."""
    body = (f"<h2>Chương 1: Bảng và thơ</h2>\n<p>{LINE}</p>\n<table><tr><th>Chỉ số</th><th>Giá trị</th></tr><tr><td>Sức mạnh</td><td>120</td></tr></table>\n"
            "<div>Cảnh một kết thúc.<hr/>Cảnh hai bắt đầu.</div>\n"
            "<div>Trước ảnh<figure><img src=\"x.png\" alt=\"\"/><figcaption>Bến đò lúc sáng</figcaption></figure>Sau ảnh</div>\n"
            "<div>Câu trước<aside>Lời bên lề</aside>Câu sau</div>\n<pre>Dòng thơ một\nDòng thơ hai\n  Dòng thơ ba</pre>\n"
            "<p>Có chú thích<sup>1</sup> rồi nói tiếp<sup>[2]</sup>, mét vuông là m<sup>2</sup> nhé.</p>")
    return _book("Chữ dính", [("c1.xhtml", body)])


def build_pt_cp1252() -> bytes:
    """TXT tiếng Bồ Đào Nha (tự viết) lưu cp1252 (BUG13): cp1258 nhận được mọi byte nhưng ra "năo", "situaçăo" - phải đọc là cp1252."""
    return ("Capítulo 1\r\n\r\nA situação não é fácil, mas a mãe já está aqui com as informações.\r\n"
            "Ele sabia que a lição era clara: são as ações que contam, não as palavras.\r\n").encode("cp1252")


def build_zh_gbk() -> bytes:
    """TXT tiếng Trung (tự viết) lưu GBK (BUG13): cp1258 / cp1252 nhận mọi byte và ra chữ rác - phải đọc là GB18030."""
    return "第一章 渡口\r\n\r\n他走进房间，看见桌上放着一封信。信上只有一句话：明天早上见。\r\n".encode("gbk")


def build_bom_join() -> bytes:
    """TXT nối từ hai file UTF-8 có BOM (BUG13): dấu BOM giữa file không được làm "Chương 2" mất tư cách tiêu đề, và không lọt vào chữ."""
    return "﻿Chương 1\nCon đò rời bến.\n\n﻿Chương 2\nMưa xuống trắng mặt sông.\n".encode()


def build_declared() -> bytes:
    """Trang XHTML khai báo bảng mã (BUG13): một trang windows-1258 thật; một trang khai `<meta charset=iso-8859-1>` mà byte là UTF-8
    (khai sai - UTF-8 đọc trọn được thì tin UTF-8)."""
    vi = ('<?xml version="1.0" encoding="windows-1258"?>\n<html xmlns="http://www.w3.org/1999/xhtml"><head><title>x</title></head><body>\n'
          "<h2>Chương 1: Bến đò</h2>\n<p>Người lái đò nhớ tên từng khách qua sông. Sáng nào ông cũng ra bến từ khi trời còn tối, ngồi chờ bên chiếc đèn dầu nhỏ, nghe tiếng nước vỗ vào mạn đò. Khách đến thì ông chở, không ai đến thì ông ngồi nhìn sông.</p>\n</body></html>")
    lying = _xhtml(f"<h2>Chương 2: Mưa</h2>\n<p>{LINE}</p>", head='<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1"/>')
    return _book("Khai báo bảng mã", [("c1.xhtml", ""), ("c2.xhtml", "")], raw_pages={"c1.xhtml": encode_cp1258(vi), "c2.xhtml": lying})


def _bold(text: str, style: str | None = None) -> str:
    return _para(style=style, runs=f'<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">{_esc(text)}</w:t></w:r>')


def build_docx_title_h1() -> bytes:
    """DOCX (BUG12): Heading 1 duy nhất ở đầu là tên sách; chương là dòng in đậm "Chương N" - không phải một chương to tên sách."""
    body = _para("Bến đò ngang", "Heading1")
    for number, name in ((1, "Bến đò"), (2, "Mưa")):
        body += _bold(f"Chương {number}: {name}") + _para(LINE) + _para("Người lái đò ngồi chờ khách bên chiếc đèn dầu nhỏ.")
    return _docx(body, None)


def build_docx_scenes() -> bytes:
    """DOCX (BUG12): Heading 1 là chương, Heading 2 là cảnh - cảnh là một dòng trong chương, không phải chương rỗng + chương "Cảnh 1"."""
    body = ""
    for number in (1, 2):
        body += _para(f"Chương {number}", "Heading1")
        for scene in (1, 2):
            body += _para(f"Cảnh {scene}", "Heading2") + _para(LINE)
    return _docx(body, None)


def build_docx_roman() -> bytes:
    """DOCX (BUG12): chương là dòng in đậm "I. KHỞI ĐẦU" (số La Mã); trang tên sách / tác giả ở đầu file có cờ, không bị bỏ; dòng
    "V. Năm" KHÔNG in đậm vẫn là chữ."""
    body = _bold("Bến đò ngang") + _para("Nguyễn Văn Thử")
    for roman, name in (("I", "KHỞI ĐẦU"), ("II", "MƯA")):
        body += _bold(f"{roman}. {name}") + _para(LINE) + _para("V. Năm người khách cuối cùng lên đò khi trời đã tối.")
    return _docx(body, None)


def build_nested() -> bytes:
    """Tên (BUG15): tên sách "… — Mục lục" (tên trang mục lục Wikisource) bỏ đuôi; nút cha "Quyển một" trỏ cùng file với chương con đầu
    không cướp tên chương ấy."""
    nav = ('<nav epub:type="toc"><ol><li><a href="text/c1.xhtml">Quyển một</a><ol><li><a href="text/c1.xhtml">Chương 1: Bến đò</a></li>'
           '<li><a href="text/c2.xhtml">Chương 2: Mưa</a></li></ol></li></ol></nav>')
    return _book("Bến đò ngang — Mục lục", [("c1.xhtml", f"<p>{LINE}</p>"), ("c2.xhtml", f"<p>{LINE}</p>")], nav=nav)


def build_index_split() -> bytes:
    """Tên (BUG15): file TXT tên do công cụ đặt ("index_split_003") mà dòng đầu là tiêu đề - tên chương là dòng ấy."""
    return f"Sương sớm\n\n{LINE}\n".encode()


def build_nfd_names() -> bytes:
    """Tên trong zip viết Unicode dạng rời (NFD, zip làm trên macOS), manifest và mục lục viết dạng gộp (BUG3)."""
    pages = _chapters(2, names="Chương {n}.xhtml")
    nav = '<nav epub:type="toc"><ol>' + "".join(f'<li><a href="text/{name}">Chương {n}: Bến số {n}</a></li>'
                                               for n, (name, _body) in enumerate(pages, start=1)) + "</ol></nav>"
    rename = {f"OEBPS/text/{name}": unicodedata.normalize("NFD", f"OEBPS/text/{name}") for name, _body in pages}
    return _book("Tên tệp dạng rời", pages, nav=nav, rename=rename)


def _ops(body: str) -> bytes:
    """Trang XHTML khai báo không gian tên epub: (epub:type="noteref"…)."""
    return _xhtml(body).replace(b'xmlns="http://www.w3.org/1999/xhtml"', b'xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"')


def build_notes_epub3() -> bytes:
    """Chú thích kiểu EPUB3 (chữ giả): dấu gọi epub:type="noteref" (trong <sup> hay trần) và role="doc-noteref"; lời chú là <aside
    epub:type="footnote"> hay role="doc-footnote", có cái nằm GIỮA chương (đặt xuống cuối chương, theo thứ tự gặp) có cái ở cuối."""
    pages = [
        ("c1.xhtml", (f'<h2>Chương 1: Bến đò</h2>\n<p>Con đò cập bến sau cơn mưa<sup><a epub:type="noteref" href="#fn1" id="r1">1</a></sup> và người lái đò '
                     f'buộc dây vào cọc.</p>\n<aside epub:type="footnote" id="fn1"><p>1. Lời chú thứ nhất đứng giữa chương.</p></aside>\n<p>{LINE}</p>\n'
                     '<p>Khách xuống đò<a epub:type="noteref" href="#fn2" id="r2">[2]</a> từng người một.</p>\n'
                     '<aside epub:type="footnote" id="fn2"><p>2. Lời chú thứ hai đứng cuối chương.</p></aside>')),
        ("c2.xhtml", (f'<h2>Chương 2: Mưa</h2>\n<p>Mưa rơi suốt đêm<a role="doc-noteref" href="#fn3" id="r3">*</a> trên mái tôn.</p>\n<p>{LINE}</p>\n'
                     '<div role="doc-footnote" id="fn3"><p>* Lời chú thứ ba, dùng vai ARIA.</p></div>\n<p>Rồi trời tạnh hẳn.</p>')),
    ]
    nav = ('<nav epub:type="toc"><ol><li><a href="text/c1.xhtml">Chương 1: Bến đò</a></li><li><a href="text/c2.xhtml">Chương 2: Mưa</a></li></ol></nav>')
    return _book("Chú thích EPUB3", pages, nav=nav, raw_pages={name: _ops(body) for name, body in pages})


def build_notes_epub2() -> bytes:
    """Chú thích kiểu Calibre (EPUB2, chữ giả): <sup><a href="#fn1">1</a></sup> trỏ tới <p id="fn1"> cuối chương, và <a href="notes.xhtml#n1">
    <sup>1</sup></a> trỏ sang trang "Chú thích" riêng; nhãn quay lại trong lời chú (<a href="#r1">1</a>) không phải dấu gọi."""
    pages = [
        ("c1.xhtml", (f'<h2>Chương 1: Bến đò</h2>\n<p>Con đò cập bến sau cơn mưa<sup class="calibre3"><a id="r1" href="#fn1">1</a></sup> rồi đi tiếp.</p>\n'
                     f'<p>{LINE}</p>\n<p class="calibre5" id="fn1"><a href="#r1">1</a>. Lời chú một của chương một.</p>')),
        ("c2.xhtml", (f'<h2>Chương 2: Mưa</h2>\n<p>Mưa rơi<a href="notes.xhtml#n1"><sup>1</sup></a> suốt đêm.</p>\n<p>{LINE}</p>\n'
                     '<p>Gió thổi<a href="notes.xhtml#n2"><sup>2</sup></a> mạnh.</p>')),
        ("notes.xhtml", '<h2>Chú thích</h2>\n<div id="n1"><p>1. Lời chú về mưa.</p></div>\n<div id="n2"><p>2. Lời chú về gió.</p></div>'),
    ]
    ncx = _ncx([("Chương 1: Bến đò", "text/c1.xhtml"), ("Chương 2: Mưa", "text/c2.xhtml"), ("Chú thích", "text/notes.xhtml")])
    return _book("Chú thích kiểu Calibre", pages, ncx=ncx, version="2.0")


def build_endnotes_epub() -> bytes:
    """Chương "Endnotes" riêng kiểu Standard Ebooks (chữ giả): dấu gọi epub:type="noteref" trỏ sang endnotes.xhtml#note-N, lời chú là
    <li epub:type="endnote"> trong <section epub:type="backmatter endnotes"> kèm nút quay lại ↩︎ (epub:type="backlink")."""
    pages = [
        ("c1.xhtml", (f'<section id="chapter-1" epub:type="chapter"><h2 epub:type="title">Chương 1: Bến đò</h2>\n<p>Con đò đã cũ<a href="endnotes.xhtml#note-1" '
                     f'id="noteref-1" epub:type="noteref">1</a>, nhưng vẫn chạy tốt.</p>\n<p>{LINE}</p></section>')),
        ("c2.xhtml", (f'<section id="chapter-2" epub:type="chapter"><h2 epub:type="title">Chương 2: Mưa</h2>\n<p>Mưa rơi<a href="endnotes.xhtml#note-2" '
                     f'id="noteref-2" epub:type="noteref">2</a> suốt đêm, gió thổi<a href="endnotes.xhtml#note-3" id="noteref-3" epub:type="noteref">3</a> mạnh.</p>\n'
                     f'<p>{LINE}</p></section>')),
        ("endnotes.xhtml", ('<section id="endnotes" epub:type="backmatter endnotes"><h2 epub:type="title">Endnotes</h2>\n<ol>\n'
                           '<li id="note-1" epub:type="endnote"><p>Lời chú một, về con đò. <a href="c1.xhtml#noteref-1" epub:type="backlink">↩︎</a></p></li>\n'
                           '<li id="note-2" epub:type="endnote"><p>Lời chú hai, về cơn mưa. <a href="c2.xhtml#noteref-2" epub:type="backlink">↩︎</a></p></li>\n'
                           '<li id="note-3" epub:type="endnote"><p>Lời chú ba, về ngọn gió. <a href="c2.xhtml#noteref-3" epub:type="backlink">↩︎</a></p></li>\n'
                           '</ol></section>')),
    ]
    nav = ('<nav epub:type="toc"><ol><li><a href="text/c1.xhtml">Chương 1: Bến đò</a></li><li><a href="text/c2.xhtml">Chương 2: Mưa</a></li>'
           '<li><a href="text/endnotes.xhtml">Endnotes</a></li></ol></nav>')
    return _book("Chương Endnotes", pages, nav=nav, raw_pages={name: _ops(body) for name, body in pages})


# --- DOCX -------------------------------------------------------------------------------------------------------------

W_NS ='xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
STYLES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles {W_NS}>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/></w:style>
  <w:style w:type="paragraph" w:styleId="Tieude1"><w:name w:val="heading 1"/></w:style>
  <w:style w:type="paragraph" w:styleId="TOC1"><w:name w:val="toc 1"/></w:style>
</w:styles>"""


def _para(text: str = "", style: str | None = None, *, runs: str | None = None) -> str:
    props = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    body = runs if runs is not None else (f'<w:r><w:t xml:space="preserve">{_esc(text)}</w:t></w:r>' if text else "")
    return f"<w:p>{props}{body}</w:p>"


def _docx(body: str, core: str | None, *, default_namespace: bool = False, extra: tuple[tuple[str, str], ...] = ()) -> bytes:
    document = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document {W_NS}><w:body>{body}</w:body></w:document>'
    if default_namespace:  # cùng tài liệu, phần tử không có tiền tố (xmlns mặc định) - hợp lệ, vài bộ ghi DOCX làm vậy
        document = document.replace(W_NS, W_NS.replace("xmlns:w", "xmlns") + " " + W_NS).replace("<w:", "<").replace("</w:", "</")
    content_types = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="xml" ContentType="application/xml"/></Types>')
    entries = [("[Content_Types].xml", content_types.encode()), ("word/document.xml", document.encode()),
               ("word/styles.xml", STYLES.encode())]
    if core:
        entries.append(("docProps/core.xml", core.encode()))
    entries += [(name, data.encode()) for name, data in extra]
    return _zip(entries)


def build_docx_headings() -> bytes:
    core = ('<?xml version="1.0" encoding="UTF-8"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>' + BOOK_TITLE + '</dc:title><dc:creator>' + AUTHOR
            + '</dc:creator><dc:language>vi-VN</dc:language></cp:coreProperties>')
    body = _para(BOOK_TITLE, "Title") + _para("Một câu đề tặng đứng trước chương đầu tiên.")
    body += "".join(_para(runs=f'<w:hyperlink w:anchor="_Toc{n}"><w:r><w:t>{_esc(title)}</w:t></w:r><w:r><w:tab/><w:t>{n + 2}</w:t></w:r>'
                               '</w:hyperlink>', style="TOC1") for n, (title, _p) in enumerate(CHAPTERS, start=1))
    body += _para(CHAPTERS[0][0], "Heading1")
    body += _para(CHAPTERS[0][1][0])
    # Xuống dòng cứng giữa câu (chữ thường ở dòng sau) nối lại; sau dấu hết câu, dòng viết hoa (thơ) hay thoại thì giữ.
    body += _para(runs='<w:r><w:t>Hai dòng</w:t><w:tab/><w:t>có tab</w:t><w:br/><w:t>và xuống dòng cứng.</w:t><w:br/>'
                       '<w:t>Dòng thơ viết hoa</w:t><w:br/><w:t>Không nối vào dòng trên</w:t><w:br/><w:t>- câu thoại riêng.</w:t></w:r>')
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
    return _docx(body, None, default_namespace=True)


def _note_ref(kind: str, number: int) -> str:
    return f'<w:r><w:rPr><w:rStyle w:val="{kind.title()}Reference"/></w:rPr><w:{kind}Reference w:id="{number}"/></w:r>'


def _note_part(kind: str, notes: list[tuple[int, str]]) -> str:
    """word/footnotes.xml hay endnotes.xml: hai lời chú mẫu (separator, continuationSeparator) rồi các lời chú thật."""
    body = "".join(f'<w:{kind} w:type="{type_}" w:id="{number}"><w:p><w:r><w:{type_}/></w:r></w:p></w:{kind}>'
                   for number, type_ in ((-1, "separator"), (0, "continuationSeparator")))
    body += "".join(f'<w:{kind} w:id="{number}"><w:p><w:pPr><w:pStyle w:val="Footnote"/></w:pPr><w:r><w:rPr><w:rStyle w:val="{kind.title()}Reference"/></w:rPr>'
                    f'<w:{kind}Ref/></w:r><w:r><w:t xml:space="preserve"> {_esc(text)}</w:t></w:r></w:p></w:{kind}>' for number, text in notes)
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:{kind}s {W_NS}>{body}</w:{kind}s>'


def build_notes_docx() -> bytes:
    """DOCX có chú thích Word thật (chữ giả): w:footnoteReference / w:endnoteReference trong chữ, lời chú ở word/footnotes.xml và endnotes.xml
    (kèm separator). Số chú thích Word không nằm trong chữ - lời chú thì chưa từng vào sách; nay chỉ đề xuất, tích mới đưa về cuối chương."""
    def run(text: str) -> str:
        return f'<w:r><w:t xml:space="preserve">{_esc(text)}</w:t></w:r>'

    body = _para("Chương 1: Bến đò", "Heading1")
    body += _para(runs=run("Con đò cập bến sau cơn mưa") + _note_ref("footnote", 2) + run(" rồi người lái đò buộc dây."))
    body += _para(LINE)
    body += _para(runs=run("Khách xuống đò từng người một") + _note_ref("footnote", 3) + run(", không ai nói gì."))
    body += _para("Chương 2: Mưa", "Heading1")
    body += _para(runs=run("Mưa rơi suốt đêm") + _note_ref("endnote", 2) + run(" trên mái tôn."))
    body += _para(LINE)
    body += _para(runs=run("Rồi trời tạnh") + _note_ref("footnote", 4) + run("."))
    extra = (("word/footnotes.xml", _note_part("footnote", [(2, "Lời chú thứ nhất."), (3, "Lời chú thứ hai."), (4, "Lời chú thứ tư.")])),
             ("word/endnotes.xml", _note_part("endnote", [(2, "Lời chú cuối sách về cơn mưa.")])))
    return _docx(body, None, extra=extra)


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
        pages.append([f"TRUYỆN THỬ NGHIỆM · {number}", *lines[start:start + per_page], f"Trang {number}"])
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
        "3.txt": b" \r\n\t\r\n",  # chỉ có khoảng trắng: không thành chương, có ghi chú
        "01.txt": "Bản trùng số với 1.txt - xếp theo tên gốc, đứng trước.\n".encode("utf-8"),
        ".txt": "Không có tên, chỉ có đuôi: không phải file .txt (như Path.suffix).\n".encode("utf-8"),
        "\u0661\u0661.txt": "Tên bằng chữ số Ả Rập: vẫn là số 11.\n".encode("utf-8"),
        "ghi chu.md": b"Not a chapter: the importer only takes .txt files.\n",
    }


WHOLE_STORY = (
    "Chuyến phà cuối ngày\nMột truyện ngắn thử nghiệm.\n\n"
    "Chương 1: Bến phà lúc bình minh\n\nSương còn phủ kín mặt sông.\nÔng Tám đẩy chiếc phà ra khỏi bến.\n\n"
    "Chương 2: Người khách lạ\nDịch: Nhóm Lục Bình\n\n\nChuyến đầu tiên chỉ có một hành khách.\n"
    "Chương trình của ngày hôm ấy rất đơn giản: đưa người qua sông.\n\n"
    "Chương 3\nMưa kéo đến lúc xế chiều.\n"
)


def whole_txt() -> bytes:
    return WHOLE_STORY.encode("utf-8")


# Cả truyện mà chữ dẫn chỉ là MỘT dòng tên truyện: tên sách gợi ý là dòng ấy, tách thì không có chương "Mở đầu" 4 chữ.
WHOLE_TITLED = (
    "Ngọn đèn cuối cùng\n\n"
    "Chương 1: Chuyến phà đêm\n\nSương xuống rất sớm.\n\n"
    "Chương 2: Căn nhà bên sông\n\nĐèn còn sáng.\n"
)


def whole_titled_txt() -> bytes:
    return WHOLE_TITLED.encode("utf-8")


# --- toàn bộ ----------------------------------------------------------------------------------------------------------

SOURCES = {
    "epub3.epub": build_epub3, "epub2.epub": build_epub2, "split.epub": build_epub_split, "headings.docx": build_docx_headings, "plain.docx": build_docx_plain,
    "story.pdf": build_story_pdf, "scan.pdf": build_scan_pdf,
}
# Hình dạng sách thật (soát a22): expected/<tên>.json như mọi file trên; BookImportTest.real_world_book_shapes_give_exactly_what_python_gives.
REAL_WORLD = {
    "nav_pages.epub": build_nav_pages, "toc_broken.epub": build_toc_broken, "toc_missing.epub": build_toc_missing,
    "nfd_names.epub": build_nfd_names, "calibre_split.epub": build_calibre_split,
    "hoi.txt": build_hoi_txt, "toc_txt.txt": build_toc_txt, "gutenberg.txt": build_gutenberg_txt,
    "hidden.epub": build_hidden, "dropcap.epub": build_dropcap, "glued.epub": build_glued,
    "pt_cp1252.txt": build_pt_cp1252, "zh_gbk.txt": build_zh_gbk, "bom_join.txt": build_bom_join, "declared.epub": build_declared,
    "title_h1.docx": build_docx_title_h1, "scenes.docx": build_docx_scenes, "roman.docx": build_docx_roman,
    "nested.epub": build_nested, "index_split_003.txt": build_index_split,
    "tail_credits.txt": build_tail_credits_txt, "tail_credits_epub.epub": build_tail_credits_epub,
}
# Chú thích trong sách nhập (BUG10 của a22): đề xuất, mặc định KHÔNG áp. expected/<tên>.json = mặc định; <tên>.<lựa chọn>.json = người nghe tích (NOTE_CHOICES,
# cùng dạng JSON mà giao diện gửi: `importers.footnote_choice_from_json`). BookImportTest.footnote_books_give_exactly_what_python_gives.
NOTE_BOOKS = {"notes3.epub": build_notes_epub3, "notes2.epub": build_notes_epub2, "endnotes.epub": build_endnotes_epub, "notes.docx": build_notes_docx}
NOTE_CHOICES = {"fn_marks": {"hideMarks": True}, "fn_end": {"hideMarks": True, "notes": "end"}, "fn_drop": {"notes": "drop"}}
SOURCES.update(REAL_WORLD)
SOURCES.update(NOTE_BOOKS)


# Tên chương đặt từ dòng đầu (`importers.clip_title`, Kotlin BookImport.clipTitle): đủ ngắn, rơi giữa từ (lùi về dấu cách), từ cuối quá dài
# (cắt cứng), không dấu cách, đúng sau một từ, dấu câu bị bỏ trước "…", ký tự ngoài mặt phẳng cơ bản (đếm theo ký tự, không theo đơn vị UTF-16).
CLIP_TITLE_CASES = [
    ("Chương một", 50),
    ("Trời hôm ấy rất đẹp, cả làng đều ra đồng gặt lúa sớm hơn mọi năm và không ai nhớ nổi vì sao", 50),
    ("a" * 60, 50),
    ("Trời hôm ấy rất đẹp, cả làng đều ra đồng gặt lúa sớm hơn", 52),
    ("Một hai ba bốn năm sáu bảy tám chín mười, mười một mười hai mười ba", 41),
    ("Mở đầu " + "x" * 90, 80),
    ("Chuyện 😀 của chúng ta bắt đầu từ một buổi chiều mưa rất lớn ở bến phà cũ kỹ", 30),
    ("Một hai ba - bốn năm sáu bảy tám chín mười mười một", 15),
]


# Tên sách đặt từ tên file (`importers.title_from_filename`, Kotlin BookImport.titleFromFilename): "_" và "--" trở lên thành dấu cách, "-" đơn
# và hoa thường giữ nguyên, khoảng trắng gọn lại, tên chỉ toàn gạch thì giữ nguyên.
NAME_TITLE_CASES = [
    "Tam_Quoc_Dien_Nghia", "Re-Zero kara Hajimeru", "ten__file--hai___gach", "  _Truyen_  moi _ ", "Sách - Tập 1", "ĐÃ_ĐƯỢC_VIẾT_HOA",
    "a-b-c", "___", "---", "Chương_1-Mở_đầu", "",
]


def dumps(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def source_files() -> dict[str, bytes]:
    """Mọi file đầu vào của bộ ví dụ (đường tương đối trong FIXTURES -> byte)."""
    files = {name: build() for name, build in SOURCES.items()}
    files.update({f"txt/{name}": data for name, data in txt_files().items()})
    files["whole.txt"] = whole_txt()
    files["titled.txt"] = whole_titled_txt()
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
    # Một file TXT cả truyện: không tách (mặc định) và có tách (người dùng tích ô gợi ý).
    out["expected/whole.json"] = dumps(importers.import_text(root / "whole.txt").to_dict())
    out["expected/whole.split.json"] = dumps(importers.import_text(root / "whole.txt", split_chapters=True).to_dict())
    out["expected/titled.json"] = dumps(importers.import_text(root / "titled.txt").to_dict())
    out["expected/titled.split.json"] = dumps(importers.import_text(root / "titled.txt", split_chapters=True).to_dict())
    for name in NOTE_BOOKS:
        for label, choice in NOTE_CHOICES.items():
            out[f"expected/{name.rsplit('.', 1)[0]}.{label}.json"] = dumps(
                importers.import_text(root / name, footnotes=importers.footnote_choice_from_json(choice)).to_dict())
    for name in REAL_WORLD:
        if name.endswith(".txt"):  # TXT cả truyện: cả khi người nghe tích "Tách thành N chương"
            out[f"expected/{name[:-4]}.split.json"] = dumps(importers.import_text(root / name, split_chapters=True).to_dict())
    # Bước xem trước giữ cả mục rất ngắn (bìa, trang bản quyền) làm chương CHƯA CHỌN, đúng chỗ của chúng trong file (`keep_short`).
    kept = {}
    for name in ("epub3.epub", "split.epub"):
        book = importers.import_text(root / name, keep_short=True)
        kept[name] = {"chapters": [{"title": chapter.title, "short": chapter.short, "text": chapter.text} for chapter in book.chapters],
                      "defaults": [number for number, _name in importers.default_picks(book)], "notes": book.notes}
    out["expected/keep_short.json"] = dumps(kept)
    out["expected/clip_title.json"] = dumps([{"text": text, "limit": limit, "clipped": importers.clip_title(text, limit)}
                                             for text, limit in CLIP_TITLE_CASES])
    out["expected/name_title.json"] = dumps([{"stem": stem, "title": importers.title_from_filename(stem)} for stem in NAME_TITLE_CASES])
    out["expected/tail_credit_lines.json"] = dumps({
        "lines": [{"line": line, "suggested": importers.tail_credit_suggestions(line + "\n") == [line]} for line, _want in TAIL_LINE_CASES],
        "sources": [{"source": source, "tail": importers.tail_credit_suggestions(source),
                     "all": [[line, at_end] for line, at_end in importers.chapter_credit_suggestions(source)]} for source in TAIL_SOURCE_CASES]})
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
