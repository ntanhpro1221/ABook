"""Tạo sách từ EPUB (webui/epub_import.py, actions.scan_inputs) - 2026-10-01: EPUB tách thành chương TXT trong thư viện rồi
đi tiếp như một thư mục chương."""
from __future__ import annotations

import zipfile
from pathlib import Path

from ebook_reader.webui import actions, epub_import

CONTAINER = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""
OPF = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Truyện thử EPUB</dc:title></metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="cover" href="text/cover.xhtml" media-type="application/xhtml+xml"/>
    <item id="c1" href="text/ch1.xhtml" media-type="application/xhtml+xml"/>
    <item id="c2" href="text/ch%202.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="cover"/><itemref idref="c1"/><itemref idref="c2"/></spine>
</package>"""
NAV = """<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><body>
<nav epub:type="toc"><ol>
  <li><a href="text/ch1.xhtml">Chương 1: Khởi đầu</a></li>
  <li><a href="text/ch%202.xhtml#start">Chương 2: Gặp gỡ</a></li>
</ol></nav></body></html>"""
COVER = """<html xmlns="http://www.w3.org/1999/xhtml"><body><p>Bìa</p></body></html>"""
CH1 = """<html xmlns="http://www.w3.org/1999/xhtml"><head><title>c1</title><style>p{}</style></head><body>
<h1>Chương 1: Khởi đầu</h1>
<p>&#8220;Xin chào,&#8221; Lucien nói.</p>
<p>Trời mưa.<br/>Gió thổi &amp; lá rơi.</p>
</body></html>"""
CH2 = """<html xmlns="http://www.w3.org/1999/xhtml"><body><h2 id="start">Gặp gỡ</h2>
<p>Natasha bước vào phòng.</p><script>bad()</script></body></html>"""


def _epub(path: Path, opf: str = OPF) -> Path:
    with zipfile.ZipFile(path, "w") as book:
        book.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        book.writestr("META-INF/container.xml", CONTAINER)
        book.writestr("OEBPS/content.opf", opf)
        book.writestr("OEBPS/nav.xhtml", NAV)
        book.writestr("OEBPS/text/cover.xhtml", COVER)
        book.writestr("OEBPS/text/ch1.xhtml", CH1)
        book.writestr("OEBPS/text/ch 2.xhtml", CH2)
    return path


def test_an_epub_becomes_one_txt_chapter_per_spine_item_titled_by_its_table_of_contents(tmp_path: Path) -> None:
    epub = _epub(tmp_path / "truyen.epub")
    library = tmp_path / "lib" / "Nguồn EPUB"
    scan = actions.scan_inputs([str(epub)], epub_root=library)
    assert scan["errors"] == [] and scan["suggestedTitle"] == "Truyện thử EPUB"
    assert [row["firstLine"] for row in scan["files"]] == ["Chương 1: Khởi đầu", "Chương 2: Gặp gỡ"], "bìa ngắn bị bỏ"
    first = Path(scan["files"][0]["path"])
    assert first.parent.parent == library, "tách vào thư viện, không ghi cạnh file của người dùng"
    lines = [line for line in first.read_text(encoding="utf-8").splitlines() if line]
    assert lines == ["Chương 1: Khởi đầu", "“Xin chào,” Lucien nói.", "Trời mưa.", "Gió thổi & lá rơi."]
    second = Path(scan["files"][1]["path"]).read_text(encoding="utf-8")
    assert "Natasha bước vào phòng." in second and "bad()" not in second
    # Mở lại cùng file: dùng lại thư mục đã tách, không tạo bản thứ hai.
    again = actions.scan_inputs([str(epub)], epub_root=library)
    assert [row["path"] for row in again["files"]] == [row["path"] for row in scan["files"]]
    assert len(list(library.iterdir())) == 1


def test_two_volumes_in_one_folder_keep_their_own_order_and_titles_are_read_once(tmp_path: Path) -> None:
    """Soát UX 01-10: thư mục có Tập 1 + Tập 2 thì chương hai tập xen kẽ (xếp theo tên "0001.txt"); tên chương ở mục lục
    "Chương 2: Gặp gỡ" mà tiêu đề trong chương là "Gặp gỡ" thì người nghe nghe tên chương hai lần."""
    volumes = tmp_path / "hai_tap"
    volumes.mkdir()
    _epub(volumes / "Tap 1.epub", OPF.replace("Truyện thử EPUB", "Truyện · Tập 1"))
    _epub(volumes / "Tap 2.epub", OPF.replace("Truyện thử EPUB", "Truyện · Tập 2").replace("Chương", "Hồi"))
    scan = actions.scan_inputs([str(volumes)], epub_root=tmp_path / "lib")
    assert [Path(row["path"]).parent.name.split(" - ")[0] for row in scan["files"]] == ["Tap 1", "Tap 1", "Tap 2", "Tap 2"]
    assert [row["name"] for row in scan["files"]][:2] == ["0001 Chương 1 Khởi đầu.txt", "0002 Chương 2 Gặp gỡ.txt"]
    second = Path(scan["files"][1]["path"]).read_text(encoding="utf-8").splitlines()
    assert [line for line in second if line] == ["Chương 2: Gặp gỡ", "Natasha bước vào phòng."]


def test_a_folder_with_both_txt_and_epub_says_the_epub_was_left_out(tmp_path: Path) -> None:
    mixed = tmp_path / "lan"
    mixed.mkdir()
    (mixed / "001.txt").write_text("Chương 1\n\nCâu.\n", encoding="utf-8")
    _epub(mixed / "kem.epub")
    scan = actions.scan_inputs([str(mixed)], epub_root=tmp_path / "lib")
    assert [row["name"] for row in scan["files"]] == ["001.txt"]
    assert scan["notes"] and "kem.epub" in scan["notes"][0]


def test_a_broken_or_hostile_epub_says_why_instead_of_finding_nothing(tmp_path: Path) -> None:
    broken = tmp_path / "hong.epub"
    broken.write_bytes(b"not a zip")
    hostile = _epub(tmp_path / "doc.epub", OPF.replace('<?xml version="1.0" encoding="utf-8"?>',
                                                        '<?xml version="1.0"?><!DOCTYPE p [<!ENTITY a "aaaa">]>'))
    scan = actions.scan_inputs([str(broken), str(hostile)], epub_root=tmp_path / "lib")
    assert scan["files"] == [] and len(scan["errors"]) == 2
    assert "hong.epub" in scan["errors"][0] and "entity" in scan["errors"][1]
    assert epub_import.title_of(broken) == "hong"
