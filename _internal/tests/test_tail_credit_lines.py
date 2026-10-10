"""Dòng xin ủng hộ / quảng cáo / nguồn ở CUỐI chương trong Studio (soát UX a23): sách nhập đã gợi ý bỏ chúng
(importers.tail_credit_suggestions), Studio chỉ bỏ được dòng ghi công ĐẦU chương. Trình tạo sách nay liệt kê cả dòng cuối
chương; như dòng đầu, chỉ bỏ khi người dùng đồng ý (khoá riêng `text.drop_tail_credit_lines`, sách tạo trước tách như cũ).
Một nguồn luật: importers dùng chính luật của text_processing."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from abook import importers
from abook.config import build_settings
from abook.pipeline import BookPipeline
from abook.text_processing import (
    credit_lines,
    drop_credit_lines,
    normalize_text,
    segment_chapter_text,
    tail_credit_lines,
)

TAIL = ("Chương 7: Về làng\n\nLucien bước vào làng.\n\nCô gật đầu.\n\n***\n\n"
        "Ủng hộ nhóm dịch qua Momo 0912345678\n\nĐọc truyện full tại truyenfull.vn\n")
BOTH = "Chương 8\n\nTL : NicK\n\nNgười kể bước vào làng.\n\nHết chương 8\n"
STORY_END = "Chương 9\n\nAnh nói: “Ủng hộ tôi qua Momo 0912345678 nhé.”\n\nRồi anh đi.\n"


def texts(chapter: str, **options) -> list[str]:
    return [str(row["text"]) for row in segment_chapter_text(1, chapter, **options)]


def test_tail_lines_are_read_unless_the_reader_asked() -> None:
    assert texts(TAIL)[-1] == "Đọc truyện full tại truyenfull.vn", "mặc định: không đổi nội dung"
    assert texts(TAIL, drop_credits=True) == texts(TAIL), "đồng ý bỏ dòng đầu chương không bỏ dòng cuối"
    assert texts(TAIL, drop_tail_credits=True) == ["Chương 7: Về làng", "Lucien bước vào làng.", "Cô gật đầu."]
    assert texts(BOTH, drop_credits=True, drop_tail_credits=True) == ["Chương 8", "Người kể bước vào làng."]
    assert BookPipeline._drop_credit_lines(SimpleNamespace(settings=build_settings()), "drop_tail_credit_lines") is False
    accepted = build_settings(overrides={"text": {"drop_tail_credit_lines": True}})
    assert BookPipeline._drop_credit_lines(SimpleNamespace(settings=accepted), "drop_tail_credit_lines") is True
    assert BookPipeline._drop_credit_lines(SimpleNamespace(settings=accepted)) is False, "khoá dòng đầu không đổi"


def test_the_suggestion_names_exactly_the_lines_it_would_leave_out() -> None:
    assert tail_credit_lines(TAIL) == ["Ủng hộ nhóm dịch qua Momo 0912345678", "Đọc truyện full tại truyenfull.vn"]
    assert tail_credit_lines(BOTH) == ["Hết chương 8"] and credit_lines(BOTH) == ["TL : NicK"]
    assert tail_credit_lines(STORY_END) == [], "lời nhân vật có dấu ngoặc là chữ truyện"
    for chapter in (TAIL, BOTH, STORY_END):
        for head, tail in ((True, False), (False, True), (True, True)):
            listed = (credit_lines(chapter) if head else []) + (tail_credit_lines(chapter) if tail else [])
            before = Counter(line.strip() for line in normalize_text(chapter).split("\n") if line.strip())
            after = Counter(line.strip() for line in drop_credit_lines(normalize_text(chapter), head=head, tail=tail).split("\n") if line.strip())
            assert before - after == Counter(listed), (chapter, head, tail)
    assert drop_credit_lines(normalize_text(TAIL)) == normalize_text(TAIL).strip(), "mặc định chỉ bỏ dòng đầu chương"


def test_imported_books_and_the_studio_share_one_rule() -> None:
    assert importers.tail_credit_suggestions(TAIL) == tail_credit_lines(TAIL)
    assert importers.chapter_credit_suggestions(BOTH) == [("TL : NicK", False), ("Hết chương 8", True)]
    assert not hasattr(importers, "_TAIL_RULES"), "luật dòng cuối chỉ ở text_processing"


def test_the_wizard_lists_tail_lines_and_a_book_keeps_the_readers_choice(tmp_path: Path) -> None:
    from abook.config import load_settings
    from abook.webui import actions

    source = tmp_path / "truyen"
    source.mkdir()
    (source / "001.txt").write_text(TAIL, encoding="utf-8")
    (source / "002.txt").write_text(BOTH, encoding="utf-8")

    scan = actions.scan_inputs([str(source)])
    assert [row["credits"] for row in scan["files"]] == [[], ["TL : NicK"]]
    assert [row["tailCredits"] for row in scan["files"]] == [tail_credit_lines(TAIL), ["Hết chương 8"]]

    library = tmp_path / "thu_vien"
    kept = actions.create_book(library, [str(source)], "Giữ", "high_quality", "")
    accepted = actions.create_book(library, [str(source)], "Bỏ", "high_quality", "", drop_credit_lines=True,
                                   drop_tail_credit_lines=True)
    assert "text" not in load_settings(kept / "book_settings.json"), "không đồng ý thì không ghi gì"
    assert load_settings(accepted / "book_settings.json")["text"] == {"drop_credit_lines": True, "drop_tail_credit_lines": True}


def test_narrator_sections_split_the_same_way(tmp_path: Path) -> None:
    from abook import narrator_sections

    rows = segment_chapter_text(1, TAIL, drop_tail_credits=True)
    assert narrator_sections.section_ids(TAIL, rows, drop_tail_credits=True) is not None
    assert narrator_sections.section_ids(TAIL, rows) is None, "chia khác cách sách đã chia thì không đoán"
