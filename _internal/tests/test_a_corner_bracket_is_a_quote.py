"""Ngoặc góc 「…」 của bản dịch light novel Nhật là ngoặc thoại (patch_a_corner_bracket_is_a_quote)."""
from __future__ import annotations

from abook.analysis import DIALOGUE_OPENERS
from abook.text_processing import normalize_text, segment_chapter_text


def _kinds(text: str) -> list[tuple[str, str]]:
    return [(row["kind_hint"], row["text"]) for row in segment_chapter_text(1, text)]


def test_a_whole_line_in_corner_brackets_is_dialogue() -> None:
    rows = _kinds("""「Đến giờ kiểm kê. Tôi ra quầy nhé.」

「Nhớ mang theo bút.」

Hai người gấp sổ hàng.""")
    assert rows == [
        ("dialogue", '“Đến giờ kiểm kê. Tôi ra quầy nhé.”'),
        ("dialogue", '“Nhớ mang theo bút.”'),
        ("narration", 'Hai người gấp sổ hàng.'),
    ]


def test_two_corner_bracket_lines_each_open_their_own_quote() -> None:
    # Khoá "thoại nối tiếp cùng người nói" của analysis bỏ qua câu mở bằng ngoặc thoại. 「 không nằm trong
    # DIALOGUE_OPENERS, nên câu phải tới đó dưới dạng “.
    rows = segment_chapter_text(1, "「Đi đâu vậy?」\n\n「Ra chợ.」")
    assert all(str(row["text"])[0] in DIALOGUE_OPENERS for row in rows)


def test_a_term_in_corner_brackets_inside_narration_stays_narration() -> None:
    rows = _kinds('Tấm thẻ cô ấy「đóng dấu」được cất vào hộp chì bên cạnh máy in.')
    assert [kind for kind, _ in rows] == ["narration"]


def test_white_corner_brackets_are_left_alone() -> None:
    # 『』 là thuật ngữ, bảng hệ thống, ngoặc lồng - không phải ngoặc thoại.
    assert normalize_text('Bậc thiết kế: C 『Gom đủ 300 mảnh đồng để mở bản vẽ』') == (
        'Bậc thiết kế: C 『Gom đủ 300 mảnh đồng để mở bản vẽ』'
    )
    assert _kinds("『Dị năng』 của cô ấy rất mạnh.") == [("narration", "『Dị năng』 của cô ấy rất mạnh.")]


def test_a_text_without_corner_brackets_is_unchanged() -> None:
    text = """“Lucien, chọn giúp tớ màu tem nhé.”

Douglas cười nói."""
    assert normalize_text(text) == text
