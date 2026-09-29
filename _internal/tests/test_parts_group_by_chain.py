"""Các phần của một cuốn ("Làm tiếp cuốn này") gom theo chuỗi continues.json, không theo tên (soát UX 29-09, N10)."""
from __future__ import annotations

import json
from pathlib import Path

from ebook_reader import continuation


def _project(root: Path, name: str, previous: str | None = None, part: int = 2) -> Path:
    folder = root / name
    folder.mkdir()
    (folder / continuation.DB_NAME).write_bytes(b"")
    if previous:
        (folder / continuation.LINK_FILE).write_text(json.dumps({"previous": previous, "part": part}), encoding="utf-8")
    return folder


def test_a_part_knows_its_first_part_and_place_whatever_its_title(tmp_path: Path) -> None:
    first = _project(tmp_path, "lo18")
    second = _project(tmp_path, "doi_ten_roi", previous="lo18")  # phần 2 đã đổi tên hiện, vẫn nối
    third = _project(tmp_path, "phan_3", previous="doi_ten_roi", part=3)
    alone = _project(tmp_path, "lo18_phan_2_la")  # tên như một phần mà không nối gì: dự án lẻ
    assert continuation.series_of(second) == (first.resolve(), 2)
    assert continuation.series_of(third) == (first.resolve(), 3)
    assert continuation.series_of(first) is None, "phần đầu: giao diện nhận ra nhờ các phần trỏ về nó"
    assert continuation.series_of(alone) is None


def test_a_part_whose_first_part_is_gone_stands_alone(tmp_path: Path) -> None:
    assert continuation.series_of(_project(tmp_path, "phan_2", previous="da_xoa")) is None


def test_a_loop_in_the_links_does_not_hang(tmp_path: Path) -> None:
    a = _project(tmp_path, "a", previous="b")
    _project(tmp_path, "b", previous="a")
    assert continuation.series_of(a) is not None
