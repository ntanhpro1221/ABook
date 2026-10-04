"""Một dòng nguyên vẹn trong [ … ] hay 【…】 là một giọng nói; ngoặc GIỮA câu kể và dòng không có chữ cái vẫn là lời kể."""
from __future__ import annotations

from abook.analysis import DIALOGUE_CLOSERS, DIALOGUE_OPENERS
from abook.text_processing import is_whole_line_voice, segment_chapter_text, spoken_symbols_to_words


def _kinds(text: str) -> list[tuple[str, str]]:
    return [(row["kind_hint"], row["text"]) for row in segment_chapter_text(1, text)]


def test_a_spoken_line_in_square_brackets_is_dialogue() -> None:
    assert _kinds("[Về thôi, trời tối rồi.]\n\nCô ấy gật đầu.") == [
        ("dialogue", "[Về thôi, trời tối rồi.]"),
        ("narration", "Cô ấy gật đầu."),
    ]


def test_an_inner_thought_line_in_square_brackets_is_a_voice() -> None:
    assert _kinds("[Mình có thể dẫn dắt thầy ấy đến đâu nhỉ?]") == [
        ("dialogue", "[Mình có thể dẫn dắt thầy ấy đến đâu nhỉ?]")
    ]


def test_a_system_notice_in_square_brackets_is_a_voice() -> None:
    rows = _kinds("[Bạn nhận được 30 điểm kinh nghiệm]\n\n[Cấp độ tăng!]\n\nHắn nhìn bảng thông báo.")
    assert rows == [
        ("dialogue", "[Bạn nhận được 30 điểm kinh nghiệm]"),
        ("dialogue", "[Cấp độ tăng!]"),
        ("narration", "Hắn nhìn bảng thông báo."),
    ]


def test_a_monster_cry_in_square_brackets_is_a_voice() -> None:
    assert _kinds("[GDESAAAAA!!]") == [("dialogue", "[GDESAAAAA!!]")]


def test_square_brackets_inside_a_narration_sentence_stay_narration() -> None:
    text = "Cậu ấy mở kỹ năng [Hỏa Cầu] ra xem thử."
    assert _kinds(text) == [("narration", text)]
    text = "Dòng [Hệ thống] hiện lên rồi biến mất."
    assert _kinds(text) == [("narration", text)]


def test_a_voice_followed_by_narration_on_the_same_line_is_not_a_voice() -> None:
    text = "[Đại ca!] hắn hét lên."
    assert _kinds(text) == [("narration", text)]


def test_a_line_without_letters_is_not_a_voice() -> None:
    # "[...]" và "[________!]" không có chữ nào để đọc nên không thành đơn vị; "[12]" có số nhưng không có chữ cái - vẫn là lời kể.
    assert _kinds("Hắn im lặng.\n\n[...]\n\n[________!]\n\n[12]\n\nCô ấy cũng vậy.") == [
        ("narration", "Hắn im lặng."),
        ("narration", "[12]"),
        ("narration", "Cô ấy cũng vậy."),
    ]


def test_a_reference_marker_line_is_still_dropped() -> None:
    assert _kinds("Hắn im lặng.\n\n[note25500]\n\nCô ấy cũng vậy.") == [
        ("narration", "Hắn im lặng."),
        ("narration", "Cô ấy cũng vậy."),
    ]


def test_curly_quotes_and_square_brackets_mix_in_one_chapter() -> None:
    rows = _kinds("“Đi thôi.”\n\n[Ừ, đi thôi.]\n\nHọ rời quán.\n\n[Ting! Nhiệm vụ mới.]\n\n‘Lại thế nữa rồi,’ cô nghĩ.")
    assert rows == [
        ("dialogue", "“Đi thôi.”"),
        ("dialogue", "[Ừ, đi thôi.]"),
        ("narration", "Họ rời quán."),
        ("dialogue", "[Ting! Nhiệm vụ mới.]"),
        ("thought", "‘Lại thế nữa rồi,’"),
        ("narration", "cô nghĩ."),
    ]


def test_a_stray_curly_quote_inside_a_voice_line_does_not_hang_the_next_paragraph() -> None:
    rows = _kinds("[Hắn gầm lên: “Chết đi!]\n\nCô ấy lùi lại.")
    assert rows == [("dialogue", "[Hắn gầm lên: “Chết đi!]"), ("narration", "Cô ấy lùi lại.")]


def test_a_balanced_quote_inside_a_voice_line_stays_one_unit() -> None:
    assert _kinds("[Ông vua ‘đối xử với Kaito như kẻ ngoài lề’. Nên tôi ghét ông ta.]") == [
        ("dialogue", "[Ông vua ‘đối xử với Kaito như kẻ ngoài lề’. Nên tôi ghét ông ta.]")
    ]


def test_a_whole_line_in_lenticular_brackets_is_a_voice() -> None:
    rows = _kinds("【Bạn đã lên cấp.】\n\n【Danh hiệu 〖Trứng đi bộ〗 được kích hoạt】\n\n【...】\n\nNó nhìn xuống.")
    assert rows == [
        ("dialogue", "【Bạn đã lên cấp.】"),
        ("dialogue", "【Danh hiệu 〖Trứng đi bộ〗 được kích hoạt】"),
        ("narration", "Nó nhìn xuống."),
    ]
    text = "Nó đọc dòng 【Bạn đã lên cấp】 mấy lần."
    assert _kinds(text) == [("narration", text)]


def test_white_corner_lines_behave_as_before() -> None:
    assert _kinds("『Ting.』\n\n『Số người chơi: 8』\n\nCả phòng lặng đi.") == [
        ("dialogue", "『Ting.』"), ("dialogue", "『Số người chơi: 8』"), ("narration", "Cả phòng lặng đi.")
    ]
    assert is_whole_line_voice("『123』")  # 『』 vẫn chỉ cần chữ hoặc số
    assert not is_whole_line_voice("[123]")


def test_two_voices_in_a_row_are_not_chained_to_one_speaker() -> None:
    assert "[" in DIALOGUE_OPENERS and "]" in DIALOGUE_CLOSERS
    assert "【" in DIALOGUE_OPENERS and "】" in DIALOGUE_CLOSERS


def test_the_voice_never_reads_its_own_brackets_aloud() -> None:
    for line in ("[Bạn nhận được 30 điểm kinh nghiệm]", "[GDESAAAAA!!]", "【Bạn đã lên cấp.】"):
        spoken = spoken_symbols_to_words(line)
        assert "[" not in spoken and "]" not in spoken
        assert not spoken.startswith(",") and not spoken.endswith(",")


def test_a_translator_note_line_is_not_a_voice() -> None:
    for note in (
        "[Note: Tui tiểu đường mất!!!]",
        "[ NOTE: Ở đây tác giả chơi chữ.]",
        "[*TL Note: Chúc phúc của Titania]",
        "[TL: Ý chỉ mặc cảm tự ti]",
        "[Trans: Death flag detected]",
        "[Ghi chú của dịch giả: Đau quá!!!]",
        "[Chú thích của dịch giả: Một canh giờ là hai tiếng.]",
        "[Lời nhóm dịch]",
        "[Từ chương này mình sẽ bắt đầu dịch từ bản Jap, nên sẽ chỉ cố gắng dịch sát.]",
        "[Editor: Deemo]",
    ):
        assert _kinds(note) == [("narration", note)], note


def test_speech_that_only_looks_like_a_note_stays_a_voice() -> None:
    for speech in (
        "[Ghi chú? Cậu đang nói về cái gì vậy?]",
        "[Edit nó đi, nhanh lên!]",
        "[Phiền phức thật! Ai mà ngờ mình lại phải đối đầu với một đại dịch một lần nữa!]",
        "[Mình sẽ dịch chuyển tới đó ngay.]",
        "[Notebook của tôi đâu rồi?]",
        "[Chú thích 2: Sau khi Ký chủ tiến vào Bách Thế Thư, sẽ như bước vào trò chơi.]",
        "【Ghi chú: Cây sáo của thần Pan đã bị phong ấn.】",
    ):
        assert _kinds(speech) == [("dialogue", speech)], speech


def test_a_framed_name_or_title_is_not_a_voice() -> None:
    for title in ("[Lớp A]", "[Mateo Jordana]", "[Sổ Hướng Dẫn]", "[Chương 12]", "【Hiệp Sĩ Bóng Đêm】", "[ Nhà Kho Số 3 ]"):
        assert _kinds(title) == [("narration", title)], title


def test_a_longer_or_punctuated_or_lowercase_line_in_brackets_is_still_a_voice() -> None:
    for speech in (
        "[Sổ hướng dẫn cho nhân viên văn phòng]",  # có chữ thường - chấp nhận là giọng
        "[Một Hai Ba Bốn Năm]",  # quá 4 chữ
        "[Lớp A, phòng 2]",  # có dấu phẩy
        "[Vâng!]",
        "[GDESAAAAA!!]",  # hét toàn hoa có !!
        "[Được rồi]",
        "【Bạn Đã Lên Cấp.】",
    ):
        assert _kinds(speech) == [("dialogue", speech)], speech


def test_a_one_word_cry_in_brackets_is_a_voice_not_a_title() -> None:
    for cry in ("[Kkkkkkkk]", "[Hmmm]", "[Aaaa]", "[Hmm]", "[Khụ]", "[Ừm]", "[Hả]", "[Wow]", "[Chậc]", "[Ối]", "【Haha】"):
        assert _kinds(cry) == [("dialogue", cry)], cry
    assert _kinds("[Hả?]") == [("dialogue", "[Hả?]")]


def test_a_one_word_title_that_is_not_a_cry_stays_narration() -> None:
    for title in ("[Ban]", "[Khu]", "[Trạng Thái]", "[Lớp A]"):
        assert _kinds(title) == [("narration", title)], title
