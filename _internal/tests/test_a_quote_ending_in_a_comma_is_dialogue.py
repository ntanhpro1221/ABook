"""“Được,” Liz gật đầu. - câu trong ngoặc kết thúc bằng dấu phẩy là lời nói nối vào lời dẫn, dù lời dẫn dùng động từ gì.

Trước 28-09 bộ tách chỉ nhận ra thoại khi quanh ngoặc có một trong 13 động từ (nói, hỏi, đáp...); "gật đầu", "lầm bầm",
"lên tiếng", "giải thích" thì cả đoạn thành lời kể và câu ấy đọc bằng giọng người kể. Quét Corpus: 1.826 câu như thế ở
Young Master's POV (Hàn) và Nageki; chỉ 5 câu là thuật ngữ đặt dấu phẩy kiểu Anh ngay sau "là/gọi/danh/thành".
"""
from __future__ import annotations

from ebook_reader.text_processing import segment_chapter_text


def _kinds(text: str) -> list[tuple[str, str]]:
    return [(row["kind_hint"], row["text"]) for row in segment_chapter_text(1, text)]


def test_a_comma_quote_with_any_attribution_is_dialogue() -> None:
    assert _kinds("“Được,” Liz gật đầu.") == [("dialogue", "“Được,”"), ("narration", "Liz gật đầu.")]
    assert _kinds("“Ở chỗ này thì anh em em chẳng có cách nào tập được đâu,” cô giải thích.") == [
        ("dialogue", "“Ở chỗ này thì anh em em chẳng có cách nào tập được đâu,”"),
        ("narration", "cô giải thích."),
    ]
    assert _kinds('"Ấn tượng đấy," cô nhận xét.')[0][0] == "dialogue"


def test_a_term_after_a_naming_word_stays_narration_even_with_a_comma() -> None:
    for text in ("Nhưng họ vẫn gọi tôi là “đội trưởng,” đơn giản vì họ quá ngốc.",
                 "Chỉ cần mang danh “thợ săn,” chẳng ai quan tâm.",
                 "Một vài thợ săn hợp lại thành “tổ đội,” còn nhiều đội thì thành bang hội."):
        assert [kind for kind, _ in _kinds(text)] == ["narration"], text


def test_a_plain_emphasis_quote_is_still_narration() -> None:
    assert _kinds("Buổi tập nào của cậu cũng phải có yếu tố “thác đổ” mới chịu.") == [
        ("narration", "Buổi tập nào của cậu cũng phải có yếu tố “thác đổ” mới chịu."),
    ]
