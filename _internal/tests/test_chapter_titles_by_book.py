"""Chapter titles are decided for the whole book, by structure, never one chapter at a time.

Regression from a shipped book (15-11): real headings "Lần gặp thứ N - …" were 12 words, over the standalone limit of 10,
so one chapter showed its real name and the others "Chương N". A repeated structure that opens most chapters now counts for
every chapter that has it, whatever its length; a book never mixes real names with numbered fallbacks; prose still never
becomes a title. The cases live in tests/fixtures/chapter_title_books.json, shared with the Android ChapterTitlesTest.
Titles are synthetic.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook import chapter_titles, importers
from tests.test_chapter_names_are_distinct import PROSE, _names, _project

BOOKS = json.loads((Path(__file__).parent / "fixtures/chapter_title_books.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", BOOKS, ids=[case["name"] for case in BOOKS])
def test_shared_book_cases(case) -> None:
    assert chapter_titles.book_headings(case["texts"], case["stored"]) == case["expected"]


def test_the_structure_splits_into_name_and_subtitle() -> None:
    assert chapter_titles.structural_parts("Lần gặp thứ 92 - Lời hứa từ một nơi xa") == ("lần gặp", "Lần gặp thứ 92", "Lời hứa từ một nơi xa")
    assert chapter_titles.structural_parts("Lần gặp số không: Đôi mắt") == ("lần gặp", "Lần gặp số không", "Đôi mắt")
    assert chapter_titles.heading_name("Lần gặp thứ 92 - Lời hứa") == ("Lần gặp thứ 92", "Lời hứa")
    assert chapter_titles.heading_name("Chương 3: Chiếc hộp xanh") == ("Chương 3", "Chiếc hộp xanh")
    assert chapter_titles.heading_name("Đảo pha lê") == ("Đảo pha lê", "")
    # Prose signals: closing punctuation, a lower-case or non-letter start, a number not followed by a separator.
    for line in ("Lần gặp thứ 92 - Tôi đã đến muộn.", "lần gặp thứ 92 - Lời hứa", "- Lần gặp thứ 92", "Năm 1990 tôi rời làng",
                 "Lần gặp thứ 92 - " + "rất dài " * 30):
        assert chapter_titles.structural_parts(line) is None, line


LONG = ["Lần gặp thứ 9 - Một lời hứa ở nơi không có tên trên bản đồ cũ",
        "Lần gặp thứ 41 - Buổi chiều dài nhất của mùa hè năm ấy ở nhà ga",
        "Lần gặp thứ 77 - Đây là, câu chuyện về chiếc ô màu vàng bị bỏ quên"]


def test_studio_names_long_titles_with_a_pattern(tmp_path: Path) -> None:
    root = _project(tmp_path, [[(0, "Mở đầu - Một buổi sáng"), (1, PROSE)], *[[(0, line), (1, PROSE)] for line in LONG],
                               [(0, "Chương kết - Tuyết đầu mùa"), (1, PROSE)]])
    assert _names(root) == ["Mở đầu", "Lần gặp thứ 9", "Lần gặp thứ 41", "Lần gặp thứ 77", "Chương kết"]


def test_studio_never_mixes_real_names_with_numbers(tmp_path: Path) -> None:
    root = _project(tmp_path, [[(0, PROSE), (1, "Rồi tạnh.")], [(0, "Đảo pha lê"), (1, PROSE)], [(0, PROSE), (1, "Rồi gió.")]])
    assert _names(root) == ["Chương 1", "Chương 2", "Chương 3"]


def test_studio_long_prose_without_a_pattern_stays_numbered(tmp_path: Path) -> None:
    root = _project(tmp_path, [[(0, PROSE), (1, "Rồi tạnh.")], [(0, PROSE.replace("tôi", "cô ấy")), (1, "Rồi gió.")]])
    assert _names(root) == ["Chương 1", "Chương 2"]


def test_the_importer_uses_the_same_rules() -> None:
    body = "\n\n" + PROSE
    book = importers.ImportedBook("T", text_has_title=True, chapters=[
        importers.Chapter("000", "Mở đầu - Một buổi sáng" + body), *[importers.Chapter(f"00{at + 1}", line + body)
                                                                   for at, line in enumerate(LONG)]])
    assert [chapter.name or chapter.title for chapter in importers._finish(book).chapters] == ["Mở đầu - Một buổi sáng", *LONG]

    book = importers.ImportedBook("T", text_has_title=True, chapters=[
        importers.Chapter("001", PROSE + body), importers.Chapter("002", "Đảo pha lê" + body), importers.Chapter("003", PROSE + body)])
    assert [chapter.name or chapter.title for chapter in importers._finish(book).chapters] == ["Chương 1", "Chương 2", "Chương 3"]
