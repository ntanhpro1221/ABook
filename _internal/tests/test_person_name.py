"""Tên người nói cho người đọc (webui/humanize.person_name)."""

from __future__ import annotations

import pytest

from abook.webui.humanize import person_name


@pytest.mark.parametrize(
    ("raw", "shown"),
    [
        ("VIỄN CỔ MỘC NÃI Y", "Viễn Cổ Mộc Nãi Y"),  # sổ nhân vật viết hoa hết
        ("AZUMA", "Azuma"),
        ("LOUIS IV", "Louis IV"),
        ("NPC_LOCAL::c00006::r0b2::người lùn", "người lùn"),
        ("LOUise", "Louise"),  # model gõ vài chữ đầu hoa rồi thường (soát UX 29-09)
        ("Oanh LOUise", "Oanh Louise"),
        ("McDonald", "McDonald"),  # hoa SAU chữ thường: cách viết thật, giữ
        ("LeBlanc", "LeBlanc"),
        ("Lucia", "Lucia"),
        ("bà thầy bói", "bà thầy bói"),
    ],
)
def test_person_name_reads_like_a_name(raw: str, shown: str) -> None:
    assert person_name(raw) == shown


def test_a_reading_is_shown_with_each_word_capitalised() -> None:
    """Cách đọc để HIỆN (tiêu đề thẻ cách đọc): "rên-ta-rô" - phần tên máy tách từ "Nam rên-ta-rô" - thành "Rên-ta-rô"."""
    from abook.webui.humanize import shown_reading

    assert shown_reading("rên-ta-rô") == "Rên-ta-rô"
    assert shown_reading("Mu-rờ-lốc Cu-ô toa hain") == "Mu-rờ-lốc Cu-ô Toa Hain"
    assert shown_reading("ơ-lin") == "Ơ-lin"
