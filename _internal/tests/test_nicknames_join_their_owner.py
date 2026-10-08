"""Biệt danh là cùng một người: "Kou" của Satomi Koutarou, "Mackenzie" của Matsudaira Kenji - một người, một giọng.

Cổng 22 lượt (08-10, Rokujouma 014/015): model ghi bạn thân gọi Koutarou là "Kou" thành nhãn "KOU" (271 câu), và
"MACKENZIE" tách khỏi "MATSUDAIRA KENJI" (83 câu) - mỗi người hai giọng. Chỉ gộp khi chữ của sách cho bằng chứng; hai người
có tên chung tiền tố phải giữ nguyên hai người.
"""
from __future__ import annotations

from abook.character_registry import canonical_speaker_names

ROKUJOUMA = "\n".join([
    "“Mày nói gì thế, Kou? Đừng so sánh người cẩn thận như anh với chú mày chứ.”",
    "Tên đang di chuyển ấy là Satomi Koutarou, 15 tuổi.",
    "Bạn thuở nhỏ cùng tuổi kia là Matsudaira Kenji, người hay gọi cậu là Kou.",
    "Đổi lại, Koutarou gọi thân mật cậu bạn là Mackenzie.",
    "“Này, Kou… mày chắc là không muốn tham gia clb bóng chày à?” Kenji hỏi Koutarou với giọng nghiêm túc.",
    "“Tên đầy đủ là Matsudaira Kenji nên cứ gọi tắt là Mackenzie.”",
    "Satomi Koutarou gật đầu. Koutarou thở dài. Koutarou cười. Matsudaira Kenji vẫy tay.",
])


def test_a_short_form_of_the_given_name_joins_its_owner() -> None:
    counts = {"KOU": 17, "SATOMI KOUTAROU": 60, "KOUTAROU": 9, "Mackenzie": 12, "KENJI": 30, "SHIZUKA": 8}
    mapping = canonical_speaker_names(counts, ROKUJOUMA)
    assert mapping["KOU"] == mapping["KOUTAROU"] == mapping["SATOMI KOUTAROU"] == "SATOMI KOUTAROU"
    assert mapping["Mackenzie"] == mapping["KENJI"] == "MATSUDAIRA KENJI", "sách tự nối hai tên trong một câu"
    assert mapping["SHIZUKA"] == "SHIZUKA"


def test_a_caller_in_the_same_sentence_is_not_the_nickname_owner() -> None:
    """"Koutarou gọi thân mật cậu bạn là Mackenzie": Koutarou là NGƯỜI GỌI - không có câu "tên đầy đủ" thì không nối."""
    book = "\n".join(line for line in ROKUJOUMA.split("\n") if "Tên đầy đủ" not in line)
    mapping = canonical_speaker_names({"MACKENZIE": 12, "SATOMI KOUTAROU": 60, "MATSUDAIRA KENJI": 30}, book)
    assert mapping["MACKENZIE"] == "MACKENZIE"


def test_two_people_sharing_a_prefix_stay_apart() -> None:
    # Mai và Maika đứng chung một câu: hai người
    together = "Mai và Maika đi học. Mai cười. Hoshino Maika gật đầu. Hoshino Maika bước ra. Maika im lặng. Maika chạy."
    assert canonical_speaker_names({"MAI": 5, "HOSHINO MAIKA": 9}, together)["MAI"] == "MAI"
    # một tên thứ ba trong sách cũng mở bằng "Kou": "Kou" là ai thì chữ không nói
    third = ROKUJOUMA + "\nKouji bước vào. Kouji ngồi xuống."
    assert canonical_speaker_names({"KOU": 17, "SATOMI KOUTAROU": 60}, third)["KOU"] == "KOU"
    # một nhãn khác cũng mở bằng "Kou"
    mapping = canonical_speaker_names({"KOU": 17, "SATOMI KOUTAROU": 60, "KOUHEI": 4}, ROKUJOUMA)
    assert mapping["KOU"] == "KOU"


def test_a_short_name_the_book_uses_more_than_the_long_one_is_its_own_person() -> None:
    """Yamiyo: "Miko" (140 lần, cô đồng) và "Mikoto" (2 lần) là hai thứ khác nhau."""
    book = "Miko đứng dậy. Miko gật đầu. Miko cười. Kurose Mikoto bước vào. Kurose Mikoto đi ra."
    assert canonical_speaker_names({"MIKO": 9, "KUROSE MIKOTO": 3}, book)["MIKO"] == "MIKO"


def test_without_the_book_nothing_joins() -> None:
    mapping = canonical_speaker_names({"KOU": 17, "SATOMI KOUTAROU": 60, "MACKENZIE": 5, "MATSUDAIRA KENJI": 9}, "")
    assert mapping["KOU"] == "KOU" and mapping["MACKENZIE"] == "MACKENZIE"
