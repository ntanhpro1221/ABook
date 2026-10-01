"""Studio: "Sửa thiết lập" của sách chưa bắt đầu (soát UX a5 01-10, #4).

Cài đặt khoá theo sách từ lúc tạo, nên đổi giọng kể, chất lượng, chương hay người xưng "tôi" là TẠO LẠI: trình tạo sách
điền sẵn mọi lựa chọn cũ (GET /api/books/<id>/redo), tạo xong thì cuốn cũ vào Thùng rác (`replaces`), bìa đi theo. Sách
đã chạy bước nào thì không - có thứ để mất."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung


def _created(server, tmp_path: Path, **choices) -> str:
    (tmp_path / "nguon").mkdir(exist_ok=True)
    for name, text in (("001.txt", "Chương 1\n\nLucien đi.\n"), ("002.txt", "Chương 2\n\nNatasha về.\n")):
        (tmp_path / "nguon" / name).write_text(text, encoding="utf-8")
    body = {"paths": [str(tmp_path / "nguon")], "title": "Sách thử", "profile": "high_quality", "narrator": "",
            "firstPerson": "", "start": False, **choices}
    status, created = _call(server, "POST", "/api/books", body)
    assert status == 201, created
    return created["id"]


@pytest.fixture
def recycled(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    from ebook_reader.webui import actions

    moved: list[Path] = []

    def recycle(path: Path) -> None:  # không đụng Thùng rác thật của máy chạy test
        moved.append(path)
        shutil.rmtree(path)

    monkeypatch.setattr(actions, "move_to_recycle_bin", recycle)
    return moved


def test_a_book_not_started_comes_back_with_its_choices_and_is_replaced(studio, tmp_path: Path,  # noqa: F811
                                                                        recycled: list[Path]) -> None:
    _paths, app, server, _runner = studio
    old = _created(server, tmp_path, firstPerson="Lucien", dropCreditLines=False)
    old_root = app.library.resolve(old)
    (old_root / "cover.jpg").write_bytes(b"\xff\xd8bia")

    status, plan = _call(server, "GET", f"/api/books/{old}/redo")
    assert status == 200 and plan["started"] is False
    assert [Path(path).name for path in plan["paths"]] == ["001.txt", "002.txt"]
    assert (plan["title"], plan["profile"], plan["firstPerson"], plan["dropCreditLines"]) == (
        "Sách thử", "high_quality", "Lucien", False)
    assert plan["seedFrom"] == ""

    status, created = _call(server, "POST", "/api/books", {
        "paths": plan["paths"][:1], "title": plan["title"], "profile": plan["profile"], "narrator": plan["narrator"],
        "firstPerson": "", "replaces": old, "start": False})
    assert status == 201, created
    assert "replaceError" not in created
    assert recycled == [old_root.resolve()], "cuốn cũ vào Thùng rác"
    new_root = app.library.resolve(created["id"])
    assert (new_root / "cover.jpg").read_bytes() == b"\xff\xd8bia", "bìa đã chọn đi theo"
    assert (tmp_path / "nguon" / "002.txt").is_file(), "file truyện gốc không bị đụng"


def test_a_book_that_has_started_is_not_replaced(studio, tmp_path: Path, recycled: list[Path]) -> None:  # noqa: F811
    from ebook_reader.webui.library import book_id

    paths, _app, server, _runner = studio  # sách của fixture đã phân tích xong
    started = book_id(paths.root)
    status, plan = _call(server, "GET", f"/api/books/{started}/redo")
    assert status == 200 and plan["started"] is True

    before = sorted(path.name for path in tmp_path.iterdir())
    (tmp_path / "nguon").mkdir()
    (tmp_path / "nguon" / "001.txt").write_text("Chương 1\n\nLucien.\n", encoding="utf-8")
    status, data = _call(server, "POST", "/api/books", {
        "paths": [str(tmp_path / "nguon")], "title": "Khác", "profile": "high_quality", "narrator": "", "firstPerson": "",
        "replaces": started, "start": False})
    assert status == 409 and "đã bắt đầu" in data["error"]
    assert recycled == [] and paths.root.is_dir()
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted([*before, "nguon"]), "không tạo cuốn mồ côi"
