"""Studio: "Làm tiếp cuốn này" - trình tạo sách điền sẵn phần kế tiếp, và sách tạo ra đã được gieo từ phần trước."""
from __future__ import annotations

from pathlib import Path

from ebook_reader import continuation
from ebook_reader.database import ProjectDB
from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung


def test_the_next_part_is_offered_then_created_with_the_old_voices(studio, tmp_path: Path) -> None:  # noqa: F811
    from ebook_reader.webui.library import book_id

    paths, app, server, _runner = studio
    (tmp_path / "002.txt").write_text("Lucien quay lại.\n", encoding="utf-8")
    source = book_id(paths.root)
    assert _call(server, "GET", f"/api/books/{source}/parts") == (200, {"parts": []}), "phần lẻ: không có gì để chỉ sang"

    status, plan = _call(server, "GET", f"/api/books/{source}/continuation")
    assert status == 200
    assert [Path(path).name for path in plan["paths"]] == ["002.txt"]
    assert (plan["title"], plan["part"], plan["analyzed"]) == ("T · Phần 2", 2, True)
    assert plan["carries"]["voices"] >= 2

    status, created = _call(server, "POST", "/api/books", {
        "paths": plan["paths"], "title": plan["title"], "profile": plan["profile"], "narrator": plan["narrator"],
        "firstPerson": plan["firstPerson"], "seedFrom": source,
    })
    assert status == 201, created
    root = app.library.resolve(created["id"])
    assert continuation.chain_of(root) == [paths.root.resolve(), root.resolve()]
    voices = ProjectDB(root / "project.sqlite3").locked_character_voices()
    assert {"LUCIEN", "NATASHA"} <= set(voices), "người đã gặp giữ giọng ở phần sau"

    # Trang dự án của mỗi phần chỉ sang phần kia (soát UX 29-09).
    status, first = _call(server, "GET", f"/api/books/{source}/parts")
    assert status == 200
    assert [(part["id"], part["part"], part["current"]) for part in first["parts"]] == [(source, 1, True), (created["id"], 2, False)]
    assert first["parts"][1]["title"] == "T · Phần 2"
    status, second = _call(server, "GET", f"/api/books/{created['id']}/parts")
    assert [part["current"] for part in second["parts"]] == [False, True]

    status, plan = _call(server, "GET", f"/api/books/{created['id']}/continuation")
    assert status == 200 and plan["part"] == 3 and plan["paths"] == [], "phần 2 đã lấy chương mới cuối cùng"
    assert plan["sourceTitle"] == "T", "tên cuốn, không phải tên phần"

    # Bấm "Làm tiếp" ở phần 1 khi đã có phần 2: nối sau phần 2, không làm lại chương phần 2 đã làm.
    (tmp_path / "003.txt").write_text("Natasha trở lại.\n", encoding="utf-8")
    status, plan = _call(server, "GET", f"/api/books/{source}/continuation")
    assert status == 200 and plan["sourceId"] == created["id"] and plan["part"] == 3
    # Và NÓI ra (soát UX a6 01-10, B1): mở từ phần 1, nối sau "T · Phần 2".
    assert (plan["clickedTitle"], plan["latestTitle"]) == ("T", "T · Phần 2")
    assert [Path(path).name for path in plan["paths"]] == ["003.txt"]


def test_an_unknown_previous_part_creates_nothing(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, _app, server, _runner = studio
    (tmp_path / "002.txt").write_text("Lucien quay lại.\n", encoding="utf-8")
    before = sorted(path.name for path in tmp_path.iterdir())

    status, data = _call(server, "POST", "/api/books", {
        "paths": [str(tmp_path / "002.txt")], "title": "T (phần 2)", "profile": "high_quality", "narrator": "",
        "firstPerson": "", "seedFrom": "khong-co-cuon-nay",
    })

    assert status == 404 and "Không tìm thấy" in data["error"]
    assert sorted(path.name for path in tmp_path.iterdir()) == before, "không để lại dự án mồ côi"
