"""Bộ nhập sách (abook/importers.py, docs/LISTEN_ANYTHING.md mục 2): thư mục TXT, EPUB, DOCX, PDF có lớp chữ.

Bộ ví dụ `tests/fixtures/import/` dùng chung với app Android (BookImportTest.kt): file đã commit phải đúng là thứ bản Python sinh ra
bây giờ, và hai bản cài phải ra đúng cùng một kết quả."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from abook import importers
from abook.webui import actions, txt_split
from tests import import_fixtures as shared

FIXTURES = shared.FIXTURES


def expected(name: str) -> dict:
    return json.loads((FIXTURES / "expected" / f"{name}.json").read_text(encoding="utf-8"))


def titles(book: importers.ImportedBook) -> list[str]:
    return [chapter.title for chapter in book.chapters]


def test_the_committed_fixtures_are_what_python_produces_today() -> None:
    for relative, data in shared.source_files().items():
        assert (FIXTURES / relative).read_bytes() == data, f"{relative} lỗi thời - chạy lại: python -m tests.import_fixtures"
    for relative, data in shared.expected_files(FIXTURES).items():
        assert (FIXTURES / relative).read_bytes() == data, f"{relative} lỗi thời - chạy lại: python -m tests.import_fixtures"


@pytest.mark.parametrize("name", ["epub3.epub", "epub2.epub", "headings.docx", "plain.docx", "story.pdf", "txt"])
def test_every_format_gives_the_expected_book(name: str) -> None:
    assert importers.import_text(FIXTURES / name).to_dict() == expected(name.rsplit(".", 1)[0])


def test_epub_follows_the_spine_names_chapters_from_the_nav_and_takes_the_cover() -> None:
    book = importers.import_text(FIXTURES / "epub3.epub")
    assert (book.title, book.author, book.language) == ("Chuyến phà cuối ngày", "Lê Thử Nghiệm", "vi")
    assert book.cover_type == "image/png" and book.cover_bytes is not None and book.cover_bytes.startswith(b"\x89PNG")
    assert titles(book) == ["Chương 1: Bến phà lúc bình minh", "Chương 2: Người khách lạ", "Chương 3"]
    assert "nothing()" not in book.chapters[0].text and book.chapters[0].text.endswith("Nước lớn dần."), "script bỏ, &nbsp; thành dấu cách"
    assert "Mưa kéo đến lúc xế chiều, nặng hạt và lạnh.\n\nÔng Tám" in book.chapters[2].text, "<br/> là ranh giới đoạn"
    assert all("không nằm trong thứ tự đọc chính" not in chapter.text for chapter in book.chapters), "linear=no bị bỏ"
    assert book.notes[:2] == ["Bỏ qua 1 trang chỉ có ảnh.", "Bỏ qua 1 mục rất ngắn (bìa, trang bản quyền?)."], \
        "đếm, không kể tên file nội bộ của gói"
    second = importers.import_text(FIXTURES / "epub2.epub")
    assert second.cover_type == "image/jpeg" and second.language == "vi-VN", "bìa EPUB2 theo <meta name=cover>, tên chương theo NCX"
    assert titles(second) == titles(book)[:2] + ["Chương 3: Cơn mưa cuối mùa"]


def test_epub_reads_every_html_entity_like_a_browser_even_in_the_table_of_contents() -> None:
    book = importers.import_text(FIXTURES / "epub3.epub")
    assert "Ông Tám cười: “Phà cũ rồi.” © 1975 ă" in book.chapters[0].text, "tên HTML5, số, &#147; kiểu Windows-1252, &copy không chấm phẩy"
    assert book.chapters[0].title == "Chương 1: Bến phà lúc bình minh", "&nbsp; trong mục lục (XML) không làm hỏng cả cuốn"


def test_the_kotlin_entity_table_is_pythons() -> None:
    from tests import html_entities_kotlin

    assert html_entities_kotlin.TARGET.read_bytes().decode("utf-8") == html_entities_kotlin.render(), \
        "HtmlEntities.kt lỗi thời - chạy lại: python -m tests.html_entities_kotlin"


def test_txt_order_ties_go_by_name_not_by_how_the_disk_lists_them(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.io_utils import discover_txt_files

    for name in ("1.txt", "01.txt", "001.txt"):
        (tmp_path / name).write_bytes(b"x")
    listed = sorted(tmp_path.iterdir())
    monkeypatch.setattr(Path, "iterdir", lambda self: iter(listed[::-1]))
    assert [path.name for path in discover_txt_files(tmp_path)] == ["001.txt", "01.txt", "1.txt"]


def test_a_long_book_only_normalises_the_head_of_each_chapter_for_credit_lines() -> None:
    body = "\n".join(f"Dòng {n}." for n in range(5000))
    book = importers._finish(importers.ImportedBook("x", chapters=[importers.Chapter("Chương 1", "Dịch: Nhóm Thử\n\n" + body)]))
    assert [note for note in book.notes if "ghi công" in note] and book.chapters[0].text.endswith("Dòng 4999.")


def test_a_credit_line_is_suggested_never_removed() -> None:
    book = importers.import_text(FIXTURES / "epub3.epub")
    assert book.credits == [(2, "Dịch: Nhóm Lục Bình")], "gợi ý có cấu trúc: bước xem trước cho chọn bỏ khỏi phần đọc"
    assert book.chapters[1].text.startswith("Dịch: Nhóm Lục Bình"), "chữ của truyện giữ nguyên"
    suggestion = [note for note in book.notes if "ghi công" in note]
    assert len(suggestion) == 1 and "chương 2" in suggestion[0] and "Dịch: Nhóm Lục Bình" in suggestion[0]
    assert "không tự bỏ" in suggestion[0]


def test_docx_splits_on_heading_1_and_2_and_falls_back_to_chapter_lines() -> None:
    book = importers.import_text(FIXTURES / "headings.docx")
    assert titles(book) == [importers.PREAMBLE, "Chương 1: Bến phà lúc bình minh", "Chương 2: Người khách lạ",
                            "Phần phụ trong chương hai", "Chương 3: Cơn mưa cuối mùa"]
    text = book.chapters[1].text
    assert "Hai dòng có tab\n\nvà xuống dòng cứng." in text, "xuống dòng cứng là ranh giới đoạn, tab là khoảng trắng"
    assert "Câu giữ lại và câu thêm vào." in text and "đã xoá" not in text, "chữ bị xoá khi theo dõi thay đổi không đọc"
    assert "Ô bảng thứ nhất.\n\nÔ bảng thứ hai." in book.chapters[2].text
    assert book.notes == ["Bỏ qua mục lục của tài liệu (3 dòng).", "Bỏ qua mục không có chữ: Một mục không có chữ"], \
        "mục lục Word (kiểu toc 1) không thành chữ của chương Mở đầu"
    assert "Người khách lạ\t" not in book.chapters[0].text and "Người khách lạ" not in book.chapters[0].text
    plain = importers.import_text(FIXTURES / "plain.docx")  # viết bằng xmlns mặc định, không có tiền tố "w:"
    assert titles(plain) == [importers.PREAMBLE, "Chương 1: Bến phà lúc bình minh", "Chương 2: Người khách lạ"]
    assert plain.chapters[2].text.endswith("Chương trình truyền hình hôm ấy kéo dài đến tận khuya, ai cũng mệt nhoài."), \
        "câu mở đầu bằng 'Chương trình' không phải tiêu đề"


def test_txt_folder_keeps_the_studio_order_and_reads_every_encoding() -> None:
    book = importers.import_text(FIXTURES / "txt")
    assert titles(book) == ["Chương 1", "Chương 1", "Chương hai", "9 Ngoại truyện", "Chương ba", "Chương ١١"], \
        "thứ tự tự nhiên (trùng số thì theo tên: 01 trước 1; chữ số Ả Rập cũng là số), bỏ file không phải .txt và file '.txt'; " \
        "dòng đầu là tiêu đề chương thì nó là tên chương (đúng thứ bước xem trước và trang sách hiện), không thì tên file"
    assert book.chapters[0].text.startswith("Bản trùng số")
    assert book.chapters[1].text == "Sương sớm\n\nChuyến phà đầu tiên rời bến lúc năm giờ.\nCậu bé đứng ở mạn thuyền.", "UTF-8 BOM + CRLF"
    assert book.chapters[2].text == "Chương hai\n\nTiếng máy nổ trầm đục.", "UTF-16"
    assert "Mưa rơi suốt chiều." in book.chapters[4].text, "cp1258 (dấu rời) về NFC"
    assert book.notes[0] == "Bỏ qua mục không có chữ: Chương 3", "file chỉ có khoảng trắng không thành chương, nhưng có nói ra"
    assert [chapter.text for chapter in book.chapters] == [chapter.text for chapter in importers.import_text(FIXTURES / "txt").chapters]


def test_pdf_removes_running_lines_joins_lines_and_splits_chapters() -> None:
    book = importers.import_text(FIXTURES / "story.pdf")
    assert titles(book) == ["Chương 1: Bến phà lúc bình minh", "Chương 2: Người khách lạ", "Chương 3: Cơn mưa cuối mùa"]
    joined = "\n".join(chapter.text for chapter in book.chapters)
    assert "TRUYỆN THỬ NGHIỆM" not in joined and "Trang " not in joined, "tiêu đề chạy (kèm số trang) và số trang bị bỏ"
    assert "Mát-xcơ-va xa lắm" in joined, "gạch nối thật của tên riêng giữ, chỉ nối liền"
    assert "không đầu không cuối" in joined
    assert "trôi vào bãi.”\n\nCậu bé gật đầu" in joined, "dòng cuối ngắn ngắt đoạn"
    assert "suốt quãng đường.\n\n— Ông đi đâu" in joined, "dòng thoại mở bằng gạch ngắt đoạn"
    assert [note for note in book.notes if note.startswith("Bỏ dòng lặp")] == ["Bỏ dòng lặp đầu / cuối trang: “TRUYỆN THỬ NGHIỆM · 1”"], \
        "một ghi chú cho dòng lặp, dù số trang trong nó đổi"


def test_a_soft_hyphen_at_a_line_end_is_dropped_but_a_real_hyphen_stays() -> None:
    """Chỉ có trong lớp luật (pdf.js tự bỏ dấu nối mềm trước khi đưa dòng ra, pypdf thì giữ)."""
    filler = [f"Một dòng văn xuôi dài vừa đủ để làm dòng đầy của trang thử số {k}, kết thúc không có dấu chấm" for k in range(6)]
    pages = [[*filler, "Cuối trang là chữ khô" + importers.SOFT_HYPHEN, "ng tách ở giữa từ, còn Hà-", "nội thì giữ gạch nối."]]
    book = importers.import_pdf_pages(pages, "x")
    assert "không tách ở giữa từ" in book.chapters[0].text and "Hà-nội thì giữ gạch nối." in book.chapters[0].text
    assert importers.SOFT_HYPHEN not in book.chapters[0].text


def test_the_pdf_rules_layer_replays_the_raw_pages() -> None:
    """Lớp luật chạy được từ `story.pages.json` - đúng thứ bản Kotlin (và pdf.js) đưa vào."""
    raw = json.loads((FIXTURES / "pages" / "story.pages.json").read_text(encoding="utf-8"))
    book = importers.import_pdf_pages(raw["pages"], "story", raw["title"], raw["author"])
    assert book.to_dict() == expected("story")


def test_a_pdf_without_a_text_layer_says_it_needs_ocr() -> None:
    with pytest.raises(importers.ImportFailed, match="ảnh chụp"):
        importers.import_text(FIXTURES / "scan.pdf")
    assert expected("scan") == {"error": "PDF này là ảnh chụp, chưa có chữ để đọc."}


def test_running_lines_only_go_when_they_repeat_and_chapter_headings_never_do() -> None:
    body = "Một đoạn văn đủ dài để không bị coi là tiêu đề hay số trang của cuốn sách thử nghiệm này."
    pages = [[f"Chương {n}", *(f"{body} Dòng {n}.{k}" for k in range(5)), f"- {n} -"] for n in range(1, 6)]
    book = importers.import_pdf_pages(pages, "x")
    assert [chapter.title for chapter in book.chapters] == [f"Chương {n}" for n in range(1, 6)], "tiêu đề chương lặp 'ở mọi trang' vẫn ở lại"
    assert all("- " not in chapter.text for chapter in book.chapters), "số trang '- N -' bị bỏ"
    filler = [f"{body} Dòng {k}." for k in range(5)]
    two = importers.import_pdf_pages([["Sách thử", *filler, "1"], ["Sách thử", *filler[::-1], "2"]], "x")
    assert "Sách thử" in two.chapters[0].text, "hai trang là quá ít để kết luận một dòng là tiêu đề chạy"
    assert not two.chapters[0].text.endswith("2")


def test_hostile_or_broken_files_say_why(tmp_path: Path) -> None:
    broken = tmp_path / "hong.docx"
    broken.write_bytes(b"not a zip")
    with pytest.raises(importers.ImportFailed, match="DOCX"):
        importers.import_text(broken)
    hostile = tmp_path / "doc.docx"
    document = '<?xml version="1.0"?><!DOCTYPE d [<!ENTITY a "aaaa">]><w:document xmlns:w="x"><w:body/></w:document>'
    with zipfile.ZipFile(hostile, "w") as archive:
        archive.writestr("word/document.xml", document)
    with pytest.raises(importers.ImportFailed, match="entity"):
        importers.import_text(hostile)
    bad_pdf = tmp_path / "x.pdf"
    bad_pdf.write_bytes(b"%PDF-1.4 garbage")
    with pytest.raises(importers.ImportFailed):
        importers.import_text(bad_pdf)
    odd = tmp_path / "x.mobi"
    odd.write_bytes(b"x")
    with pytest.raises(importers.ImportFailed, match="Chưa đọc được"):
        importers.import_text(odd)
    (tmp_path / "trong").mkdir()
    (tmp_path / "trong" / "1.txt").write_bytes(b"  \n")
    with pytest.raises(importers.ImportFailed, match="Không có chương nào"):
        importers.import_text(tmp_path / "trong")


def test_extract_writes_studio_chapter_files_once_and_reuses_them(tmp_path: Path) -> None:
    folder, info = importers.extract(FIXTURES / "epub3.epub", tmp_path / "lib")
    assert info["title"] == "Chuyến phà cuối ngày" and info["cover"] == "cover.png" and (folder / "cover.png").is_file()
    names = sorted(path.name for path in folder.glob("*.txt"))
    assert names == ["0001 Chương 1 Bến phà lúc bình minh.txt", "0002 Chương 2 Người khách lạ.txt", "0003 Chương 3.txt"]
    first = (folder / names[0]).read_text(encoding="utf-8")
    assert first.startswith("Chương 1: Bến phà lúc bình minh\n\nSương còn phủ kín")
    again, same = importers.extract(FIXTURES / "epub3.epub", tmp_path / "lib")
    assert again == folder and same == info and len(list((tmp_path / "lib").iterdir())) == 1


def test_studio_scan_takes_docx_and_pdf_like_epub(tmp_path: Path) -> None:
    library = tmp_path / "lib"
    scan = actions.scan_inputs([str(FIXTURES / "headings.docx"), str(FIXTURES / "story.pdf")], epub_root=library)
    assert scan["errors"] == [] and scan["suggestedTitle"] == "Chuyến phà cuối ngày"
    assert [row["firstLine"] for row in scan["files"]][:2] == [importers.PREAMBLE, "Chương 1: Bến phà lúc bình minh"]
    assert len(scan["files"]) == 5 + 3 and scan["totals"]["chapters"] == 8
    assert all(row["chars"] > 0 for row in scan["files"])
    assert any(note.startswith("story.pdf: Bỏ dòng lặp") for note in scan["notes"]) and any("headings.docx" in note for note in scan["notes"])
    scanned = actions.scan_inputs([str(FIXTURES / "scan.pdf")], epub_root=library)
    assert scanned["files"] == [] and "ảnh chụp" in scanned["errors"][0] and scanned["errors"][0].startswith("scan.pdf: ")


def test_studio_scan_of_a_folder_of_books_unpacks_each_in_name_order(tmp_path: Path) -> None:
    folder = tmp_path / "sach"
    folder.mkdir()
    (folder / "b.docx").write_bytes((FIXTURES / "plain.docx").read_bytes())
    (folder / "a.epub").write_bytes((FIXTURES / "epub2.epub").read_bytes())
    scan = actions.scan_inputs([str(folder)], epub_root=tmp_path / "lib")
    assert [Path(row["path"]).parent.name.split(" - ")[0] for row in scan["files"]] == ["a"] * 3 + ["b"] * 3


def test_remote_upload_accepts_the_new_book_types(tmp_path: Path) -> None:
    library = tmp_path / "lib"
    library.mkdir()
    for name in ("sach.docx", "sach.pdf", "sach.epub", "1.txt"):
        assert actions.upload_source(library, "Tải", name, b"x").is_dir()
    with pytest.raises(ValueError, match=r"\.docx"):
        actions.upload_source(library, "Tải", "sach.mobi", b"x")


def test_the_chapter_heading_pattern_is_shared_with_the_txt_splitter() -> None:
    for line in ("Chương 12", "chương thứ hai", "Chapter IV", "Hồi 3: Gặp gỡ", "第十章 开始"):
        assert txt_split.HEADING.match(line) and importers.HEADING.match(line), line
    assert importers.HEADING.match("Quyển 2") and not txt_split.HEADING.match("Quyển 2"), "Quyển chỉ là tiêu đề với DOCX / PDF"
    assert not importers.HEADING.match("Chương trình hôm nay")


def test_pdf_reading_uses_the_vendored_pypdf_not_an_installed_one() -> None:
    importers.import_text(FIXTURES / "story.pdf")
    import pypdf

    vendor = Path(importers.__file__).resolve().parent / "vendor" / "pypdf"
    assert Path(pypdf.__file__).resolve().parent == vendor
    assert (vendor / "LICENSE").is_file() and "SHA-256 c8b09a59" in (vendor / "README.md").read_text(encoding="utf-8")
