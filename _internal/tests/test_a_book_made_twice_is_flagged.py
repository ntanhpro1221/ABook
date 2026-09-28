"""Tạo sách từ truyện đã có dự án: bước chọn truyện báo "Truyện này đã có dự án" (soát UX 29-09 - tạo lại cùng truyện
không có lời nào, người dùng có hai dự án mà không biết). So NỘI DUNG file như chapters.input_sha256 của dây chuyền, nên
truyện chép sang thư mục khác vẫn nhận ra; không chặn - vẫn tạo được dự án mới."""
from __future__ import annotations

import shutil
from pathlib import Path

from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung


def test_the_same_story_copied_elsewhere_is_recognised(studio, tmp_path: Path) -> None:  # noqa: F811
    from ebook_reader.webui.library import book_id

    paths, _app, server, _runner = studio
    copy = tmp_path / "elsewhere" / "chuong 1.txt"
    copy.parent.mkdir()
    shutil.copyfile(tmp_path / "001.txt", copy)
    status, data = _call(server, "POST", "/api/scan", {"paths": [str(copy.parent)]})
    assert status == 200
    assert [(item["id"], item["shared"], item["chapters"]) for item in data["existing"]] == [(book_id(paths.root), 1, 1)]
    assert data["existing"][0]["title"] == "T"


def test_a_different_story_is_not_flagged(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, _app, server, _runner = studio
    other = tmp_path / "other" / "001.txt"
    other.parent.mkdir()
    other.write_text("Một truyện khác hẳn.\n", encoding="utf-8")
    status, data = _call(server, "POST", "/api/scan", {"paths": [str(other.parent)]})
    assert status == 200 and data["existing"] == []
