"""Dòng ghi công người dịch / biên tập ở đầu chương ("*Edit: Lắc", "TL : NicK", "Translator: NicK") - 17 chương Throne, 172
chương Nise bị đọc to như câu kể. Chủ sách 29-09: app KHÔNG BAO GIỜ tự sửa nội dung - trình tạo sách phát hiện và ĐỀ XUẤT
bỏ chúng khỏi phần đọc; chỉ sách mà người dùng đồng ý mới bỏ, mọi sách khác tách y như trước."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from abook.config import build_settings
from abook.pipeline import BookPipeline
from abook.text_processing import credit_lines, drop_credit_lines, segment_chapter_text

NISE = "Chương 85: Hồn Xiêu Phách Lạc\n\nTranslator: NicK\n\nEditor: Deemo\n\n______________________\n\n“Ồ… Ta biết rồi.”\n\nCô gật đầu."
THRONE = "Chương 655 - Dạ tiệc\n\n*Edit: Lắc\n\nLucien bước vào sảnh."


def texts(chapter: str, **options) -> list[str]:
    return [str(row["text"]) for row in segment_chapter_text(1, chapter, **options)]


def test_nothing_is_left_out_unless_the_reader_asked() -> None:
    assert "Translator: NicK" in texts(NISE) and "*Edit: Lắc" in texts(THRONE), "mặc định: không đổi nội dung"
    assert BookPipeline._drop_credit_lines(SimpleNamespace(settings=build_settings())) is False
    assert "text" not in build_settings(), "cài đặt mặc định không mang lựa chọn nào"


def test_an_accepted_suggestion_leaves_the_credits_out_of_the_reading() -> None:
    assert "Translator: NicK" not in texts(NISE, drop_credits=True) and "Editor: Deemo" not in texts(NISE, drop_credits=True)
    assert texts(THRONE, drop_credits=True) == ["Chương 655 - Dạ tiệc", "Lucien bước vào sảnh."]
    accepted = build_settings(overrides={"text": {"drop_credit_lines": True}})
    assert BookPipeline._drop_credit_lines(SimpleNamespace(settings=accepted)) is True


def test_the_suggestion_names_exactly_the_lines_it_would_leave_out() -> None:
    assert credit_lines(NISE) == ["Translator: NicK", "Editor: Deemo"]
    assert credit_lines(THRONE) == ["*Edit: Lắc"]


def test_story_lines_that_look_like_credits_are_never_suggested() -> None:
    # Giữa chương 211 của Throne: một câu truyện mở bằng "Tác giả:" - không phải nhãn ghi công, không ở đầu chương.
    story = "Chương 211\n\nTác giả: Lucien Evans X, Arcanist cấp một, pháp sư bậc một.”\n\nHọ đọc lại lần nữa."
    assert credit_lines(story) == [] and drop_credit_lines(story) == story
    # Nhãn ghi công nhưng phần sau là một câu (có dấu kết câu) thì cũng là truyện.
    assert credit_lines("Chương 3\n\nDịch: ông lão dịch lại bức thư cho cả làng nghe.") == []
    # Chỉ đầu chương: cùng dòng ấy ở sâu trong chương là của truyện.
    late = "Chương 1\n\n" + "\n\n".join(f"Câu kể thứ {n}." for n in range(1, 9)) + "\n\nEditor: Deemo"
    assert credit_lines(late) == []


def test_the_wizard_counts_the_credits_and_a_book_keeps_the_readers_choice(tmp_path: Path) -> None:
    from abook.config import load_settings
    from abook.webui import actions

    source = tmp_path / "truyen"
    source.mkdir()
    for number in (1, 2):
        (source / f"{number:03d}.txt").write_text(
            f"Chương {number}: Mở đầu\n\nTL : NicK\n\nNgười kể bước vào làng.\n", encoding="utf-8")
    (source / "003.txt").write_text("Chương 3: Sau đó\n\nKhông có ghi công ở đây.\n", encoding="utf-8")

    scan = actions.scan_inputs([str(source)])
    assert [row["credits"] for row in scan["files"]] == [["TL : NicK"], ["TL : NicK"], []]

    library = tmp_path / "thu_vien"
    kept = actions.create_book(library, [str(source)], "Giữ", "high_quality", "")
    accepted = actions.create_book(library, [str(source)], "Bỏ", "high_quality", "", drop_credit_lines=True)
    assert "text" not in load_settings(kept / "book_settings.json"), "không đồng ý thì không ghi gì"
    assert load_settings(accepted / "book_settings.json")["text"] == {"drop_credit_lines": True}
