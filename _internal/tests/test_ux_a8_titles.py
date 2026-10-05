"""Soát UX a8 (05-10), mục 16: tên sách gợi ý lấy từ dòng tiêu đề của truyện, tên chương không mang số thứ tự của file."""

from __future__ import annotations

from pathlib import Path

import pytest

from abook.webui import actions, humanize


def _story(path: Path, text: str) -> str:
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_single_file_story_suggests_its_title_line_instead_of_the_file_name(tmp_path: Path) -> None:
    source = _story(tmp_path / "whole.txt", "Chuyến phà cuối ngày\nMột truyện ngắn thử nghiệm.\n\nChương 1: Bến phà\nTrời sáng.\n")
    assert actions.scan_inputs([source])["suggestedTitle"] == "Chuyến phà cuối ngày"


@pytest.mark.parametrize("first_line", [
    "Chương 1: Bến phà lúc bình minh",
    "Trời vừa sáng thì người lái phà đã ra bến, nhìn mặt sông còn phủ sương.",
    "Anh ta bước vào quán.",
    "- Chào anh, anh đi đâu đấy?",
    "“Em đi đâu đấy?”",
    "Một hai ba bốn năm sáu bảy tám chín mười mười một mười hai mười ba",
    "12345",
])
def test_first_line_that_is_not_a_title_keeps_the_file_name(tmp_path: Path, first_line: str) -> None:
    source = _story(tmp_path / "whole.txt", f"{first_line}\n\nNội dung truyện.\n")
    assert actions.scan_inputs([source])["suggestedTitle"] == "whole"


def test_file_order_prefix_is_not_part_of_the_chapter_name() -> None:
    assert humanize.chapter_title("0000 Mở đầu") == "Mở đầu"
    assert humanize.chapter_title("001 - Chương 1") == "Chương 1"
    assert humanize.chapter_title("01.Mở đầu") == "Mở đầu"
    # Số thật trong tên thì giữ; tên file chỉ là số thì đọc thành "Chương N" như trước.
    assert humanize.chapter_title("1984 và sau đó") == "1984 và sau đó"
    assert humanize.chapter_title("100 ngày") == "100 ngày"
    assert humanize.chapter_title("0645") == "Chương 645"
    assert humanize.chapter_title("Mở đầu") == "Mở đầu"
    assert humanize.chapter_names("0000 Mở đầu", None) == ("Mở đầu", "")
