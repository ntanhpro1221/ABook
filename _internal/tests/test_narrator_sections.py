"""Bộ phát hiện "người kể khác ở một đoạn" (narrator_sections, ngưỡng P_RULE.md): đoạn có/không "tôi", tên người kể ở ngôi ba,
dòng ngắt cảnh của file nguồn, và không báo gì khi không có người kể hay chữ nguồn lệch hàng đã chia."""
from __future__ import annotations

import pytest

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


# ---- dòng tiêu đề góc nhìn (đo 12-10, LLM_Train/runs/DCHECK_12-10.md: 6/6 là mốc đổi góc nhìn thật) -------------------------
@pytest.mark.parametrize(("line", "who"), [
    ("[POV: Mai]", "Mai"),
    ("~ Góc nhìn của Lâm Hạ ~", "Lâm Hạ"),
    ("Góc nhìn của Mai*", "Mai"),
    ("Trở lại góc nhìn của Mai", "Mai"),
    ("Trờ lại góc nhìn của Mai*", "Mai"),  # gõ nhầm như một bản dịch thật
    ("Quay về  góc nhìn   của Kenji", "Kenji"),
    ("Mai's POV", "Mai"),
    ("<<<POV Kenji>>>", "Kenji"),
    ("P.O.V: Kenji", "Kenji"),
    ("3 - [Góc nhìn của Mai]", "Mai"),  # số thứ tự khúc đứng trước
    ("Góc nhìn: Kenji Sato", "Kenji Sato"),
    ("Góc nhìn thứ 3", ""),
    ("Góc nhìn thứ ba", ""),
    ("Góc nhìn người dẫn chuyện*", ""),
    ("Quay lại góc nhìn thứ 3 nào", ""),
    ("Third person POV", ""),
])
def test_a_pov_heading_names_its_narrator_or_says_third_person(line: str, who: str) -> None:
    assert narrator_sections.pov_heading(line) == who


@pytest.mark.parametrize("line", [
    "Từ góc nhìn của tôi thì chuyện này chẳng có gì lạ.",
    "Góc nhìn của tôi thì khác.",
    "Góc nhìn của cô ấy",
    "Nhìn từ góc nhìn của Mai, mọi thứ thật lạ.",
    "Anh ấy luôn có một góc nhìn rất riêng.",
    "Ghi chú: đây là POV của Mai, các câu thoại sau vốn viết bằng một thứ tiếng khác.",  # dài hơn một tiêu đề
    "Góc nhìn",
    "POV",
    "Chương 3",
    "",
])
def test_an_ordinary_sentence_with_the_word_is_not_a_heading(line: str) -> None:
    assert narrator_sections.pov_heading(line) is None


def _heading_book(*parts: str) -> str:
    return "\n\n".join(parts) + "\n"


def test_a_heading_opens_a_section_without_a_break_line_and_proposes_its_narrator() -> None:
    raw = _heading_book(FIRST, "Góc nhìn của Mai", FIRST, FIRST, "Trở lại góc nhìn của Kakeru", FIRST)
    rows, found = _detect(raw)
    ids = narrator_sections.heading_section_ids(rows, narrator_sections.section_ids(raw, rows))
    heads = [row["seq"] for row in rows if narrator_sections.pov_heading(row["text"]) is not None]
    assert len(heads) == 2 and len(set(ids)) == 3 and all(ids[seq] != ids[seq - 1] for seq in heads)
    assert len(found) == 1, "tiêu đề trở lại người kể của sách là ranh đoạn, không phải đề xuất"
    assert found[0] == {"from_seq": heads[0], "to_seq": heads[1] - 1, "heading": "Góc nhìn của Mai", "suggested": "Mai",
                        "r1": None, "r3": None, "words": found[0]["words"]}
    assert found[0]["words"] > 0
    assert narrator_sections.section_ids(raw, rows) == [0] * len(rows), "cách cắt chữ nguồn không đổi"


def test_a_third_person_heading_in_a_first_person_book_proposes_no_narrator() -> None:
    rows, found = _detect(_heading_book(FIRST, "***", "Góc nhìn thứ 3", FIRST))
    assert [(item["suggested"], item["heading"]) for item in found] == [("", "Góc nhìn thứ 3")]
    assert found[0]["to_seq"] == rows[-1]["seq"]


def test_a_heading_naming_the_books_narrator_is_trusted_over_d() -> None:
    # Đoạn không có "tôi" (D sẽ báo) nhưng mở bằng "Góc nhìn của KAKERU SORANO" trong sách Kakeru kể: không đề xuất gì.
    _rows, found = _detect(_heading_book(FIRST, "***", "[POV: Kakeru]", NO_PRONOUN), narrator="KAKERU SORANO")
    assert found == []
    assert narrator_sections.same_narrator("Minato", "TANAKA MINATO") and narrator_sections.same_narrator("tanaka minato", "Tanaka Minato")
    assert not narrator_sections.same_narrator("Mai", "Kakeru") and not narrator_sections.same_narrator("", "Kakeru")


def test_a_third_person_book_gets_named_headings_only() -> None:
    raw = _heading_book(NO_PRONOUN, "Góc nhìn của Mai", FIRST, "Góc nhìn thứ 3", NO_PRONOUN)
    _rows, found = _detect(raw, narrator="")
    assert [item["suggested"] for item in found] == ["Mai"]


def test_a_heading_alone_before_a_break_line_covers_the_text_after_it() -> None:
    rows, found = _detect(_heading_book(FIRST, "***", "~ Góc nhìn của Mai ~", "***", FIRST, "***", FIRST))
    after = [row["seq"] for row in rows]
    assert len(found) == 1 and found[0]["from_seq"] == after[1]
    assert found[0]["to_seq"] == after[2], "tiêu đề + khúc ngay sau nó; khúc kế (sau dòng ngắt cảnh) là đoạn khác"


def test_d_still_flags_sections_without_a_heading_and_does_not_merge_across_one() -> None:
    raw = _heading_book(FIRST, "***", NO_PRONOUN, "Góc nhìn của Kakeru", NO_PRONOUN, "***", NO_PRONOUN)
    _rows, found = _detect(raw)
    assert [(item["from_seq"], item["to_seq"]) for item in found] == [(1, 1), (4, 4)], found  # không có tiêu đề thì là (1, 4)
    assert all("heading" not in item for item in found)


# ---- đại từ của người kể (DCHECK_12-10 phụ lục 04:1x: người kể xưng "ta" làm D báo nhầm cả chương) ---------------------------
TA = "Ta bước vào đại điện. Ta nhìn quanh, cả điện im phăng phắc, ta ngồi xuống ghế quen, ta mở quyển sổ ra đọc."


def test_ta_after_a_person_word_is_not_the_narrator() -> None:
    counts = narrator_sections.pronoun_counts("Chúng ta đi thôi. Hắn ta cười. Cô ta nhìn. Anh ta đứng. Bọn ta chạy. Nó ta.")
    assert counts["ta"] == 0
    assert narrator_sections.pronoun_counts("Ta đi. Rồi ta về.")["ta"] == 2
    assert narrator_sections.pronoun_counts("“Ta sẽ đi,” hắn nói.\n- Ta không sợ.")["ta"] == 0, "dòng thoại không tính"
    assert narrator_sections.pronoun_counts("Tại hạ cúi đầu. Lão phu cười.") == {"tại hạ": 1, "lão phu": 1}


def test_the_narrators_pronoun_needs_enough_evidence() -> None:
    assert narrator_sections.narrator_pronouns([TA]) is narrator_sections.PRON, "4 chữ: quá ít, giữ mẫu mặc định"
    assert narrator_sections.narrator_pronouns([FIRST * 6]) is narrator_sections.PRON, "ưu thế 'tôi': mẫu mặc định y hệt"
    pron = narrator_sections.narrator_pronouns([TA * 3, TA * 3])
    assert pron.findall("Ta đi, tôi về, tớ ở lại.") == ["Ta", "tôi", "tớ"]
    assert pron.findall("chúng ta và hắn ta") == []


def test_a_narrator_who_says_ta_is_not_flagged_but_a_third_person_section_still_is() -> None:
    raw = f"{TA}\n\n***\n\n{TA}\n"
    rows = segment_chapter_text(1, raw, max_chars=340)
    assert len(narrator_sections.detect(raw, rows, "Kakeru")) == 1, "mẫu mặc định: không có 'tôi' -> báo cả chương"
    pron = narrator_sections.narrator_pronouns([TA * 6])
    assert narrator_sections.detect(raw, rows, "Kakeru", pron=pron) == []
    # Sách "tôi" có đoạn ngôi ba: vẫn đề xuất, với mẫu tính từ chính sách ấy.
    raw = f"{FIRST}\n\n***\n\n{NO_PRONOUN}\n"
    rows = segment_chapter_text(1, raw, max_chars=340)
    assert len(narrator_sections.detect(raw, rows, "Kakeru", pron=narrator_sections.narrator_pronouns([FIRST * 6]))) == 1
