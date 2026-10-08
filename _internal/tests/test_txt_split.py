"""Một file TXT chứa cả truyện (soát UX a5 01-10): bước 1 ĐỀ XUẤT tách theo "Chương N", mặc định không tách; tách thì
ghi các chương ra thư mục mới, file gốc giữ nguyên, chữ giữ nguyên từng dòng."""
from __future__ import annotations

from pathlib import Path

from abook.webui import actions, txt_split

WHOLE_BOOK = """Ánh Trăng Phương Bắc
Tác giả: Ai Đó

Chương 1: Gặp lại

“Nasdell, cậu tới rồi!” Lucien reo lên.

CHƯƠNG 2 - Lên đường

Chương trình của họ bắt đầu lúc trời vừa sáng.

Hồi lâu sau mới có người lên tiếng.

Chương Ba

Biển hiện ra trước mắt họ.
"""


def test_a_whole_book_in_one_file_is_offered_a_split_not_given_one(tmp_path: Path) -> None:
    source = tmp_path / "Truyen tron bo.txt"
    source.write_text(WHOLE_BOOK, encoding="utf-8")
    original = source.read_bytes()

    scan = actions.scan_inputs([str(source)])
    assert scan["totals"]["chapters"] == 1, "mặc định vẫn là một chương - chỉ đề xuất"
    offer = scan["files"][0]["split"]
    # "Chương trình…" và "Hồi lâu sau…" là câu văn, không phải tiêu đề.
    assert offer == {"chapters": 4, "titles": ["Chương 1: Gặp lại", "CHƯƠNG 2 - Lên đường", "Chương Ba"], "preamble": True, "titleLine": ""}

    folder = txt_split.split(source, tmp_path / "lib" / actions.SPLIT_FOLDER)
    assert source.read_bytes() == original
    names = sorted(path.name for path in folder.glob("*.txt"))
    assert names == ["0000 Mở đầu.txt", "0001 Chương 1 Gặp lại.txt", "0002 CHƯƠNG 2 - Lên đường.txt", "0003 Chương Ba.txt"]
    second = (folder / "0002 CHƯƠNG 2 - Lên đường.txt").read_text(encoding="utf-8")
    assert second.startswith("CHƯƠNG 2 - Lên đường\n\nChương trình của họ")
    assert "Hồi lâu sau mới có người lên tiếng." in second
    assert (folder / "0000 Mở đầu.txt").read_text(encoding="utf-8") == "Ánh Trăng Phương Bắc\nTác giả: Ai Đó\n"
    # Tách lại cùng file: dùng lại thư mục cũ.
    assert txt_split.split(source, tmp_path / "lib" / actions.SPLIT_FOLDER) == folder
    rescan = actions.scan_inputs([str(folder)])
    assert rescan["totals"]["chapters"] == 4
    assert rescan["suggestedTitle"] == "Truyen tron bo", "tên sách gợi ý không dính mã băm của thư mục"


def test_one_chapter_per_file_is_left_alone(tmp_path: Path) -> None:
    folder = tmp_path / "truyen"
    folder.mkdir()
    (folder / "001.txt").write_text("Chương 1\n\nMột câu.\n", encoding="utf-8")
    (folder / "002.txt").write_text("Chương 2\n\nHai câu.\n", encoding="utf-8")
    assert all(row["split"] is None for row in actions.scan_inputs([str(folder)])["files"])


def test_chinese_headings_split_too(tmp_path: Path) -> None:
    source = tmp_path / "zh.txt"
    source.write_text("第一章 开始\n他来了。\n第二章 结束\n他走了。\n", encoding="utf-8")
    assert txt_split.plan(source) == {"chapters": 2, "titles": ["第一章 开始", "第二章 结束"], "preamble": False, "titleLine": ""}
    names = sorted(path.name for path in txt_split.split(source, tmp_path / "out").glob("*.txt"))
    assert names == ["0001 第一章 开始.txt", "0002 第二章 结束.txt"]


def test_a_lone_title_line_is_the_book_name_when_it_matches_the_title_and_stays_a_chapter_when_it_does_not(tmp_path: Path) -> None:
    source = tmp_path / "ngon_den_cuoi_cung.txt"
    source.write_text("Ngọn đèn cuối cùng\n\nChương 1: Chuyến phà đêm\n\nSương xuống.\n\nChương 2: Căn nhà\n\nĐèn sáng.\n", encoding="utf-8")
    offer = txt_split.plan(source)
    assert offer is not None and offer["titleLine"] == "Ngọn đèn cuối cùng" and offer["chapters"] == 3, "chương 'Mở đầu' vẫn tính trong đề xuất; bước tạo sách trừ nó"
    root = tmp_path / "out"

    same = txt_split.split(source, root, "  ngọn ĐÈN cuối cùng ")
    assert sorted(path.name for path in same.glob("*.txt")) == ["0001 Chương 1 Chuyến phà đêm.txt", "0002 Chương 2 Căn nhà.txt"]
    assert same.name == "ngon_den_cuoi_cung", "tên thư mục vẫn là tên file (tên sách do trình tạo sách giữ, không đọc lại từ đây)"

    other = txt_split.split(source, root, "Tên khác do tôi đặt")
    assert other != same, "giữ hay bỏ dòng tên truyện ra hai bộ chương khác nhau"
    assert sorted(path.name for path in other.glob("*.txt"))[0] == "0000 Mở đầu.txt", "tên sách khác dòng ấy: chữ không bị bỏ, vẫn là chương 'Mở đầu'"
    assert (other / "0000 Mở đầu.txt").read_text(encoding="utf-8") == "Ngọn đèn cuối cùng\n"
    assert txt_split.split(source, root) != same, "không có tên sách thì không bỏ gì"


def test_a_two_line_lead_is_never_taken_for_a_title(tmp_path: Path) -> None:
    source = tmp_path / "a.txt"
    source.write_text("Ánh Trăng\nTác giả: Ai Đó\n\nChương 1\nA\n\nChương 2\nB\n", encoding="utf-8")
    offer = txt_split.plan(source)
    assert offer is not None and offer["titleLine"] == ""
    assert (txt_split.split(source, tmp_path / "out", "Ánh Trăng") / "0000 Mở đầu.txt").is_file()
