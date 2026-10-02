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
    assert offer == {"chapters": 4, "titles": ["Chương 1: Gặp lại", "CHƯƠNG 2 - Lên đường", "Chương Ba"], "preamble": True}

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
    assert txt_split.plan(source) == {"chapters": 2, "titles": ["第一章 开始", "第二章 结束"], "preamble": False}
    names = sorted(path.name for path in txt_split.split(source, tmp_path / "out").glob("*.txt"))
    assert names == ["0001 第一章 开始.txt", "0002 第二章 结束.txt"]
