"""Bộ phát hiện "người kể khác ở một đoạn" (narrator_sections, ngưỡng P_RULE.md): đoạn có/không "tôi", tên người kể ở ngôi ba,
dòng ngắt cảnh của file nguồn, và không báo gì khi không có người kể hay chữ nguồn lệch hàng đã chia."""
from __future__ import annotations

from abook import narrator_sections
from abook.text_processing import segment_chapter_text

FIRST = "Tôi bước vào lớp. Tôi nhìn quanh và thấy cả phòng yên tĩnh, tôi ngồi xuống chỗ quen thuộc, tôi mở sách ra đọc."
THIRD = ("Kakeru bước vào lớp. Kakeru nhìn quanh và thấy cả phòng yên tĩnh, Kakeru ngồi xuống chỗ quen thuộc, "
         "Kakeru mở sách ra đọc.")
NO_PRONOUN = "Gió thổi qua sân trường. Lá rơi đầy trên mặt đất, và chuông reo từ xa vọng lại trong buổi chiều muộn."


def _detect(raw: str, narrator: str = "Kakeru"):
    rows = segment_chapter_text(1, raw, max_chars=340)
    return rows, narrator_sections.detect(raw, rows, narrator)


def test_a_section_told_in_first_person_is_not_flagged() -> None:
    _rows, found = _detect(f"{FIRST}\n\n***\n\n{FIRST}\n")
    assert found == []


def test_a_section_that_names_the_narrator_in_third_person_is_flagged_with_its_seq_range() -> None:
    rows, found = _detect(f"{FIRST}\n\n***\n\n{THIRD}\n\n◇\n\n{FIRST}\n")
    assert len(found) == 1
    middle = [row for row in rows if "Kakeru" in row["text"]]
    assert (found[0]["from_seq"], found[0]["to_seq"]) == (middle[0]["seq"], middle[-1]["seq"])
    assert found[0]["r3"] >= 2 and found[0]["r1"] < 1


def test_a_section_with_hardly_any_toi_is_flagged_even_without_the_name() -> None:
    _rows, found = _detect(f"{FIRST}\n\n***\n\n{NO_PRONOUN}\n")
    assert len(found) == 1


def test_thresholds_are_the_pre_registered_ones() -> None:
    name = narrator_sections.name_pattern("Kakeru Sorano")
    rows = [{"kind_hint": "narration", "text": " ".join(["chữ"] * 996 + ["Kakeru", "Kakeru", "tôi", "tôi"]), "seq": 0}]
    # r3 = 2 và r1 = 2: r3 > r1/4 -> báo; r1 >= 1 chỉ cứu khi r3 < 2.
    assert narrator_sections.measure(rows, [0], name)["flagged"] is True
    rows = [{"kind_hint": "narration", "text": " ".join(["chữ"] * 996 + ["Kakeru", "tôi", "tôi", "tôi"]), "seq": 0}]
    assert narrator_sections.measure(rows, [0], name)["flagged"] is False  # r3 = 1 < 2, r1 = 3 >= 1
    rows = [{"kind_hint": "narration", "text": " ".join(["chữ"] * 1000), "seq": 0}]
    assert narrator_sections.measure(rows, [0], name)["flagged"] is True  # r1 = 0 < 1


def test_dialogue_does_not_count_as_narration() -> None:
    name = narrator_sections.name_pattern("Kakeru")
    rows = [{"kind_hint": "dialogue", "text": "Kakeru, Kakeru, Kakeru!", "seq": 0}]
    result = narrator_sections.measure(rows, [0], name)
    assert result["words"] == 0 and result["flagged"] is False  # không có lời dẫn: không quyết được, không báo


def test_a_common_word_in_the_name_matches_only_in_full() -> None:
    name = narrator_sections.name_pattern("NGƯỜI ĐƯA TANG")
    assert name.findall("Người ta nói đưa tang xong") == []  # token thường không tính
    assert name.findall("Người đưa tang bước tới") != []  # đủ tên (không phân biệt hoa thường)


def test_break_lines_are_symbols_or_standalone_numbers_not_a_lone_dash() -> None:
    for line in ("***", "◇ ◆ ◇", "──────", "・・・", "12", "IV", "~ ~ ~"):
        assert narrator_sections.is_break_line(line), line
    for line in ("—", "-", "Chương 12", "", "Tôi đi."):
        assert not narrator_sections.is_break_line(line), line


def test_no_narrator_or_a_source_that_no_longer_matches_the_rows_proposes_nothing() -> None:
    raw = f"{FIRST}\n\n***\n\n{THIRD}\n"
    rows = segment_chapter_text(1, raw, max_chars=340)
    assert narrator_sections.detect(raw, rows, "") == []
    assert narrator_sections.detect(raw + "\n\nMột đoạn mới thêm sau khi chia.\n", rows, "Kakeru") == []
