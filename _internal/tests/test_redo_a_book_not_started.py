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
    from abook.webui import actions

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
    from abook.webui.library import book_id

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


def test_changing_nothing_keeps_the_book_instead_of_throwing_it_away(studio, tmp_path: Path,  # noqa: F811
                                                                      recycled: list[Path]) -> None:
    """Cùng tên, cùng chương, cùng thiết lập: dây chuyền mở lại đúng cuốn cũ. Lần thử đầu (01-10) đã bỏ nó vào Thùng rác."""
    _paths, app, server, _runner = studio
    old = _created(server, tmp_path)
    old_root = app.library.resolve(old)
    status, plan = _call(server, "GET", f"/api/books/{old}/redo")
    status, created = _call(server, "POST", "/api/books", {
        "paths": plan["paths"], "title": plan["title"], "profile": plan["profile"], "narrator": plan["narrator"],
        "firstPerson": plan["firstPerson"], "replaces": old, "start": False})
    assert status == 201 and created["id"] == old and created.get("unchanged") is True
    assert recycled == [] and old_root.is_dir()


def test_an_analysis_cut_short_is_flagged_and_can_be_restarted_from_scratch(studio, tmp_path: Path,  # noqa: F811
                                                                             recycled: list[Path]) -> None:
    """Soát UX a8: sau Dừng giữa phân tích chỉ còn "Tiếp tục" - mà chạy tiếp ra MỘT CUỐN KHÁC (AGENTS.md). Trang dự án biết
    phân tích dở dang (`analysisInterrupted`, số câu chờ) và "Làm lại phân tích" thay bản dở bằng dự án mới, bìa đi theo."""
    import sqlite3
    from contextlib import closing

    _paths, app, server, _runner = studio
    old = _created(server, tmp_path)
    old_root = app.library.resolve(old)
    (old_root / "cover.jpg").write_bytes(b"\xff\xd8bia")
    status, fresh = _call(server, "GET", f"/api/books/{old}")
    fresh = fresh["book"]
    assert fresh["analysisInterrupted"] is False and fresh["segments"]["pending"] == 0, "chưa bắt đầu: không có gì dở dang"

    with closing(sqlite3.connect(old_root / "project.sqlite3")) as db:  # phân tích tách 3 câu, mới xong 1 thì bị ngắt
        chapter = db.execute("SELECT MIN(id) FROM chapters").fetchone()[0]
        for seq, status in enumerate(("analyzed", "pending", "pending")):
            db.execute("INSERT INTO segments(stable_id, chapter_id, seq, text, text_sha256, kind_hint, status, updated_at)"
                       " VALUES (?, ?, ?, 'Câu.', 'x', 'narration', ?, 0)", (f"s{seq}", chapter, seq, status))
        db.commit()
    status, cut = _call(server, "GET", f"/api/books/{old}")
    cut = cut["book"]
    assert cut["analysisInterrupted"] is True and 0 < cut["segments"]["pending"] == 2 < cut["segments"]["total"]
    status, plan = _call(server, "GET", f"/api/books/{old}/redo")
    assert plan["started"] is False and plan["analysisInterrupted"] is True

    status, created = _call(server, "POST", "/api/books", {
        "paths": plan["paths"], "title": plan["title"], "profile": plan["profile"], "narrator": plan["narrator"],
        "firstPerson": plan["firstPerson"], "replaces": old, "start": False})
    assert status == 201, created
    assert recycled == [old_root.resolve()], "bản dở vào Thùng rác TRƯỚC, nên dự án mới không mở lại nó"
    status, again = _call(server, "GET", f"/api/books/{created['id']}")
    again = again["book"]
    assert again["analysisInterrupted"] is False and again["segments"]["analyzed"] == 0, "bắt đầu lại từ câu đầu"
    assert (app.library.resolve(created["id"]) / "cover.jpg").read_bytes() == b"\xff\xd8bia"
