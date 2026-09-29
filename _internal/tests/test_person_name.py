"""Tên người nói cho người đọc (webui/humanize.person_name)."""

from __future__ import annotations

import pytest

from ebook_reader.webui.humanize import person_name


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
