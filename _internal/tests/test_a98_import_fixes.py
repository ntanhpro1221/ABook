"""Soát a98 (nhập nguồn truyện vào Studio): mười lỗi F1-F10 chuyển từ script tái hiện thành test. Mỗi test nói hành vi ĐÚNG; trước khi sửa
chúng đỏ."""
from __future__ import annotations

import errno
import json
import os
import zipfile
from pathlib import Path

import pytest

from abook import importers
from abook.webui import actions

CONTAINER = ('<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
             '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
LOREM = "Anh Nam đi học về muộn, trời mưa rất to và cô ấy chờ ở cổng trường đến tối mới thấy anh. "


def xhtml(body: str) -> str:
    return (f'<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
            f"<head><title>t</title></head><body>{body}</body></html>")


def para(count: int = 6) -> str:
    return "".join(f"<p>{LOREM * 3} Câu số {i}.</p>" for i in range(count))


def make_epub(path: Path, pages: list[tuple[str, str]], toc: list[tuple[str, str]] | None = None) -> Path:
    items = "".join(f'<item id="p{i}" href="{name}" media-type="application/xhtml+xml"/>' for i, (name, _) in enumerate(pages))
    spine = "".join(f'<itemref idref="p{i}"/>' for i, _ in enumerate(pages))
    opf = ('<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">'
           '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Sách thử</dc:title><dc:creator>Tác Giả</dc:creator>'
           f'<dc:language>vi</dc:language></metadata><manifest>{items}<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" '
           f'properties="nav"/></manifest><spine>{spine}</spine></package>')
    with zipfile.ZipFile(path, "w") as book:
        book.writestr("mimetype", "application/epub+zip", zipfile.ZIP_STORED)
        book.writestr("META-INF/container.xml", CONTAINER)
        book.writestr("OEBPS/content.opf", opf)
        for name, page in pages:
            book.writestr("OEBPS/" + name, page)
        links = "".join(f'<li><a href="{href}">{label}</a></li>' for href, label in toc or [])
        book.writestr("OEBPS/nav.xhtml", xhtml(f'<nav epub:type="toc"><ol>{links}</ol></nav>'))
    return path


def make_pdf(path: Path, pages: list[list[str]]) -> Path:
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", f"<< /Type /Pages /Kids [{' '.join(f'{3 + 2 * i} 0 R' for i in range(len(pages)))}] /Count {len(pages)} >>"]
    for i, lines in enumerate(pages):
        content = "BT /F1 10 Tf 12 TL 50 750 Td " + " ".join(f"({line}) Tj T*" for line in lines) + " ET"
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {4 + 2 * i} 0 R /Resources << /Font << /F1 << /Type /Font "
                    "/Subtype /Type1 /BaseFont /Helvetica >> >> >> >>")
        objs.append(f"<< /Length {len(content)} >>\nstream\n{content}\nendstream")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return path


def good_epub(path: Path, count: int = 2) -> Path:
    return make_epub(path, [(f"c{i}.xhtml", xhtml(f"<h2>Chương {i}</h2>" + para())) for i in range(1, count + 1)],
                     [(f"c{i}.xhtml", f"Chương {i}") for i in range(1, count + 1)])


# ---- F1: trang phụ của EPUB ----------------------------------------------------------------------------------------------------

def matter_epub(path: Path) -> Path:
    pages = [
        ("cover.xhtml", xhtml("<h1>Sách thử</h1><p>Tác giả Tác Giả, bản dịch của nhóm dịch. Bìa sách thể hiện nhân vật chính ở giữa.</p>")),
        ("copyright.xhtml", xhtml("<p>Bản quyền thuộc về nhà xuất bản. Mọi hình thức sao chép phải được sự đồng ý bằng văn bản của tác giả và nhà "
                                  "xuất bản.</p><p>ISBN 123-456</p>")),
        ("contents.xhtml", xhtml("<h1>Mục lục</h1><p>Chương 1: Khởi đầu của một cuộc hành trình dài</p><p>Chương 2: Gặp gỡ ở cổng trường học xưa</p>")),
        ("c1.xhtml", xhtml("<h1>Chương 1: Khởi đầu</h1>" + para())),
        ("c2.xhtml", xhtml("<h1>Chương 2: Gặp gỡ</h1>" + para())),
    ]
    return make_epub(path, pages, [("c1.xhtml", "Chương 1: Khởi đầu"), ("c2.xhtml", "Chương 2: Gặp gỡ")])


def test_f1_studio_scan_flags_the_same_pages_listen_now_leaves_unticked(tmp_path: Path) -> None:
    source = matter_epub(tmp_path / "matter.epub")
    book = importers.import_text(source, keep_short=True)
    unticked = [chapter.title for number, chapter in enumerate(book.chapters, 1) if number not in {n for n, _ in importers.default_picks(book)}]
    assert len(unticked) == 3, "bìa, bản quyền, mục lục"
    scan = actions.scan_inputs([str(source)], epub_root=tmp_path / "lib")
    flagged = [row["firstLine"] for row in scan["files"] if row.get("matter")]
    plain = [row["firstLine"] for row in scan["files"] if not row.get("matter")]
    assert len(flagged) == 3 and all(isinstance(row["matter"], str) and row["matter"] for row in scan["files"] if row.get("matter"))
    assert plain == ["Chương 1: Khởi đầu", "Chương 2: Gặp gỡ"], "chỉ hai chương thật được chọn sẵn"
    assert scan["totals"]["chapters"] == 5, "danh sách vẫn đủ: người dùng tích lại được"


def test_f1_an_old_chapter_folder_without_flags_is_extracted_again(tmp_path: Path) -> None:
    source = matter_epub(tmp_path / "matter.epub")
    folder, info = importers.extract(source, tmp_path / "lib")
    assert info["matter"] and all((folder / name).is_file() for name in info["matter"])
    sidecar = folder / importers.SIDECAR
    old = json.loads(sidecar.read_text(encoding="utf-8"))
    old.pop("matter")
    sidecar.write_bytes(json.dumps(old).encode("utf-8"))
    _folder, again = importers.extract(source, tmp_path / "lib")
    assert again["matter"], "thư mục tách bởi bản cũ (không cờ) được tách lại"


# ---- F2: TXT hỏng byte ---------------------------------------------------------------------------------------------------------

def test_f2_one_broken_txt_is_reported_by_name_and_the_rest_are_scanned(tmp_path: Path) -> None:
    folder = tmp_path / "trunc"
    folder.mkdir()
    body = (LOREM * 5 + "\n\n") * 4
    for i in range(1, 4):
        (folder / f"{i:03d}.txt").write_bytes(f"Chương {i}\n\n{body}".encode())
    (folder / "004.txt").write_bytes(f"Chương 4\n\n{body}Hết rồi ệ".encode()[:-1])  # cắt giữa ký tự
    scan = actions.scan_inputs([str(folder)], epub_root=tmp_path / "lib")
    assert [row["name"] for row in scan["files"]] == ["001.txt", "002.txt", "003.txt"]
    assert len(scan["errors"]) == 1 and scan["errors"][0].startswith("004.txt")
    assert "UTF-8" in scan["errors"][0] and "codec" not in scan["errors"][0], "câu tiếng Việt kèm cách sửa, không phải lỗi thô"


# ---- F3: EPUB hỏng CRC ---------------------------------------------------------------------------------------------------------

def corrupt(good: Path, target: Path, member: str = "OEBPS/c2.xhtml") -> Path:
    raw = bytearray(good.read_bytes())
    with zipfile.ZipFile(good) as book:
        info = book.getinfo(member)
        offset = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
    raw[offset + 10] ^= 0xFF
    target.write_bytes(bytes(raw))
    return target


def test_f3_a_corrupt_epub_is_import_failed_not_a_raw_zip_error(tmp_path: Path) -> None:
    bad = corrupt(good_epub(tmp_path / "good.epub"), tmp_path / "bad.epub")
    with pytest.raises(importers.ImportFailed):
        importers.import_text(bad)


def test_f3_a_corrupt_book_does_not_take_the_other_files_down(tmp_path: Path) -> None:
    good = good_epub(tmp_path / "good.epub")
    bad = corrupt(good, tmp_path / "bad.epub")
    scan = actions.scan_inputs([str(good), str(bad)], epub_root=tmp_path / "lib")
    assert len(scan["files"]) == 2, "sách tốt vẫn quét"
    assert len(scan["errors"]) == 1 and scan["errors"][0].startswith("bad.epub") and "BadZipFile" not in scan["errors"][0]


# ---- F4: PDF -------------------------------------------------------------------------------------------------------------------

BODY = ["Anh Nam di hoc ve muon, troi mua rat to va co ay cho o cong truong", "den toi moi thay anh quay lai. Co ay noi nho nhe nhu mot loi tham.",
        "Hom sau hai nguoi cung nhau di cho mua ca va rau ve nau com toi."]


def running_pdf(path: Path, pages: int = 40) -> Path:
    sheets = []
    for i in range(pages):
        sheet = ["TRUYEN ABC - TAP 1"]
        if i % 10 == 0:
            sheet.append(f"Chuong {i // 10 + 1}")
        sheet += [BODY[(i + j) % 3] for j in range(20)] + [str(i + 1)]
        sheets.append(sheet)
    return make_pdf(path, sheets)


def chapter_files(folder: Path) -> list[Path]:
    return sorted(folder.glob("*.txt"))


def test_f4_studio_pdf_drops_running_heads_and_page_numbers_like_listen_now(tmp_path: Path) -> None:
    source = running_pdf(tmp_path / "run.pdf")
    book = importers.import_text(source)
    assert book.default_skips, "Nghe ngay tích sẵn bỏ các dòng này"
    scan = actions.scan_inputs([str(source)], epub_root=tmp_path / "lib")
    text = "\n".join(path.read_text(encoding="utf-8") for path in chapter_files(next((tmp_path / "lib").iterdir())))
    assert "TRUYEN ABC" not in text
    assert not [line for line in text.split("\n") if line.strip().isdigit()], "số trang không còn nằm trong chữ chương"
    assert not any("bỏ chọn để giữ" in note for note in scan["notes"]), "không nhắc một ô chọn mà màn Studio không có"
    assert any("TRUYEN ABC" in note for note in scan["notes"]), "nhưng nói ra đã bỏ gì"


def test_f4_many_chapters_do_not_make_hundreds_of_notes(tmp_path: Path) -> None:
    sheets = []
    for i in range(300):
        sheets.append(["TRUYEN ABC", f"Chuong {i + 1}", *[BODY[(i + j) % 3] for j in range(3)], str(i + 1)])
    source = make_pdf(tmp_path / "big.pdf", sheets)
    scan = actions.scan_inputs([str(source)], epub_root=tmp_path / "lib")
    assert len(scan["notes"]) <= 7, "tối đa 6 dòng và một dòng '…và N ghi chú nữa' như Nghe ngay"


# ---- F5: dòng "Hồi/Phần ..." ---------------------------------------------------------------------------------------------------

FIXTURE = Path(__file__).parent / "fixtures" / "import" / "a98_heading_lines.json"


def test_f5_heading_lines_shared_with_the_phone() -> None:
    for line, expected in json.loads(FIXTURE.read_text(encoding="utf-8")):
        assert importers.is_heading_line(line, importers.TXT_HEADING) is expected, line


def test_f5_a_paragraph_ending_in_a_curly_quote_does_not_split_the_story() -> None:
    body = "Trời mưa rất to, anh Nam đứng đợi ở cổng trường đến tối mới thấy cô ấy quay lại.\n\n"
    text = ("Truyện Thử\n\nChương 1: Mở\n\n" + body + "Hồi năm ngoái anh ấy đã nói với tôi: “Anh sẽ không đi đâu cả.”\n\n" + body +
            "Chương 2: Hai\n\n" + body + "Hồi hai giờ chiều cô ấy hỏi: “Anh có đi không?”\n\n" + body + "Chương 3: Ba\n\n" + body)
    titles = [chapter.title for chapter in importers.split_txt_chapters(text)]
    assert titles == ["Mở đầu", "Chương 1: Mở", "Chương 2: Hai", "Chương 3: Ba"]


# ---- F6: đĩa đầy / đường dẫn lộ ------------------------------------------------------------------------------------------------

def test_f6_a_full_disk_while_splitting_is_a_vietnamese_error_and_leaves_nothing(tmp_path: Path, monkeypatch) -> None:
    source = good_epub(tmp_path / "book.epub", 7)
    original = Path.write_bytes
    calls = {"n": 0}

    def failing(self: Path, data: bytes) -> int:
        calls["n"] += 1
        if calls["n"] > 3 and self.suffix == ".txt":
            raise OSError(errno.ENOSPC, "No space left on device", str(self))
        return original(self, data)

    monkeypatch.setattr(Path, "write_bytes", failing)
    scan = actions.scan_inputs([str(source)], epub_root=tmp_path / "lib")
    monkeypatch.setattr(Path, "write_bytes", original)
    assert len(scan["errors"]) == 1
    message = scan["errors"][0]
    assert message.startswith("book.epub") and "Errno" not in message and str(tmp_path) not in message
    assert "đầy" in message
    assert not [path for path in (tmp_path / "lib").rglob("*") if path.is_file()], "chương ghi dở được dọn"
    again = actions.scan_inputs([str(source)], epub_root=tmp_path / "lib")
    assert len(again["files"]) == 7 and not again["errors"], "có chỗ rồi thì thử lại được"


def test_f6_server_text_never_carries_a_machine_path() -> None:
    from abook.webui.server import without_local_text

    leaked = without_local_text("book.epub: [Errno 28] No space left on device: 'D:\\Users\\Nguyen Van A\\Truyện\\x.txt'")
    assert "Nguyen" not in leaked and "D:\\" not in leaked


# ---- F7: số đếm của file dài ---------------------------------------------------------------------------------------------------

def test_f7_a_long_file_is_extrapolated_and_marked_as_an_estimate(tmp_path: Path) -> None:
    folder = tmp_path / "big"
    folder.mkdir()
    paragraph = "Anh Nam đi học về muộn, trời mưa rất to và cô ấy chờ ở cổng trường đến tối mới thấy anh quay lại.\n\n"
    text = "Chương 1\n\n" + paragraph * 70000
    (folder / "whole.txt").write_text(text, encoding="utf-8", newline="\n")
    assert len(text.encode()) > actions.SCAN_WORD_LIMIT_BYTES * 1.5
    scan = actions.scan_inputs([str(folder)], epub_root=tmp_path / "lib")
    row = scan["files"][0]
    real = len(text.split())
    assert abs(row["words"] - real) / real < 0.02 and row.get("estimated") is True
    assert scan["totals"].get("estimated") is True
    small = tmp_path / "small"
    small.mkdir()
    (small / "a.txt").write_text("Chương 1\n\nXin chào.", encoding="utf-8")
    assert not actions.scan_inputs([str(small)])["totals"].get("estimated")


# ---- F9: giới hạn gửi ----------------------------------------------------------------------------------------------------------

def test_f9_a_whole_novel_fits_and_the_refusal_says_what_to_do(tmp_path: Path) -> None:
    assert actions.MAX_SOURCE_UPLOAD >= 32 * 1024 * 1024
    with pytest.raises(ValueError) as caught:
        actions.upload_source(tmp_path, "Lần gửi", "to.txt", b"x" * (actions.MAX_SOURCE_UPLOAD + 1))
    message = str(caught.value)
    assert "MB" in message and ("tách" in message or "chép" in message), "câu báo nói cách làm tiếp"


# ---- F10: TXT bảng mã cũ -------------------------------------------------------------------------------------------------------

def test_f10_tcvn3_text_gets_a_note_and_is_not_converted(tmp_path: Path) -> None:
    folder = tmp_path / "enc"
    folder.mkdir()
    tcvn = (b"Ch\xadng 1\r\n\r\nT\xabi \xaei h\xf1c v\xd2 mu\xe9n. Anh Nam \xaei ch\xa3 mua c\xb8 v\xb5 rau. \xb9nh s\xb8ng \xa9p.\r\n") * 30
    for i in (1, 2):
        (folder / f"{i:03d}.txt").write_bytes(tcvn)
    scan = actions.scan_inputs([str(folder)], epub_root=tmp_path / "lib")
    assert any("TCVN3" in note for note in scan["notes"]), scan["notes"]
    assert (folder / "001.txt").read_bytes() == tcvn, "ABook không tự đổi chữ"
    assert len([note for note in scan["notes"] if "TCVN3" in note]) == 1, "một ghi chú cho cả lô"


@pytest.mark.parametrize("text", [
    "Ação é uma coisa que não se faz. Estás à espera de alguém que já não vem, coração. José chegou à cidade com a irmã. " * 4,
    "El niño pequeño compró una piñata en España con su añejo amigo, el señor Núñez, que enseñaba español a los niños del barrio. " * 4,
])
def test_f10_other_languages_are_not_mistaken_for_old_vietnamese(tmp_path: Path, text: str) -> None:
    folder = tmp_path / "t"
    folder.mkdir()
    (folder / "001.txt").write_bytes(text.encode("cp1252"))
    scan = actions.scan_inputs([str(folder)], epub_root=tmp_path / "lib")
    assert not [note for note in scan["notes"] if "TCVN3" in note or "VNI" in note], scan["notes"]


def test_f10_vni_text_gets_a_note_and_listen_now_says_it_too(tmp_path: Path) -> None:
    folder = tmp_path / "vni"
    folder.mkdir()
    vni = ("Toâi ñi hoïc veà muoän. Anh Nam ñi chôï mua caù vaø rau, trôøi möa raát to vaø coâ aáy chôø ôû coång tröôøng ñeán toái môùi thaáy anh quay laïi.\n" * 6)
    (folder / "001.txt").write_bytes(vni.encode("cp1252"))
    assert any("VNI" in note for note in actions.scan_inputs([str(folder)], epub_root=tmp_path / "lib")["notes"])
    assert any("VNI" in note for note in importers.import_text(folder).notes), "Nghe ngay nói như Studio"
