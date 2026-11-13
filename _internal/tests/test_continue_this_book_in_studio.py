"""Studio: "Làm tiếp cuốn này" - trình tạo sách điền sẵn phần kế tiếp, và sách tạo ra đã được gieo từ phần trước."""
from __future__ import annotations

from pathlib import Path
import io
import json
import os
from types import SimpleNamespace

import pytest

from abook import continuation
from abook.database import ProjectDB
from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung


def test_the_next_part_is_offered_then_created_with_the_old_voices(studio, tmp_path: Path) -> None:  # noqa: F811
    from abook.webui.library import book_id

    paths, app, server, _runner = studio
    continuation.save_source_hint(paths.root, [tmp_path / "001.txt"])
    (tmp_path / "002.txt").write_text("Lucien quay lại.\n", encoding="utf-8")
    source = book_id(paths.root)
    assert _call(server, "GET", f"/api/books/{source}/parts") == (200, {"parts": []}), "phần lẻ: không có gì để chỉ sang"

    status, plan = _call(server, "GET", f"/api/books/{source}/continuation")
    assert status == 200
    assert plan["paths"] == [], "a continuation never discovers sources from the ledger"
    assert plan["folder"] == str(tmp_path), "remember the original folder, not the book's copied sources"
    assert (plan["title"], plan["part"], plan["analyzed"]) == ("T · Phần 2", 2, True)
    assert plan["carries"]["voices"] >= 2

    status, scan = _call(server, "POST", "/api/scan", {"paths": [str(tmp_path)], "seedFrom": source})
    assert status == 200 and [row["name"] for row in scan["files"]] == ["002.txt"]
    status, created = _call(server, "POST", "/api/books", {
        "paths": [row["path"] for row in scan["files"]], "title": plan["title"], "profile": plan["profile"], "narrator": plan["narrator"],
        "firstPerson": plan["firstPerson"], "seedFrom": source,
    })
    assert status == 201, created
    root = app.library.resolve(created["id"])
    assert continuation.chain_of(root) == [paths.root.resolve(), root.resolve()]
    copied = continuation._input_paths(root)
    assert len(copied) == 1 and copied[0].is_relative_to(root / "sources")
    assert copied[0].read_bytes() == (tmp_path / "002.txt").read_bytes()
    (tmp_path / "002.txt").unlink()
    assert copied[0].read_text(encoding="utf-8") == "Lucien quay lại.\n", "the book uses its own copy"
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
    assert plan["paths"] == []
    status, scan = _call(server, "POST", "/api/scan", {"paths": [str(tmp_path / "003.txt")], "seedFrom": plan["sourceId"]})
    assert status == 200 and [row["name"] for row in scan["files"]] == ["003.txt"]


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


@pytest.mark.parametrize("hint", [r"\\attacker.example\share", "//attacker.example/share", r"\\?\C:\outside", "outside"])
def test_a_hint_is_displayed_without_any_filesystem_probe(studio, tmp_path: Path, monkeypatch, hint: str) -> None:
    from abook.webui.library import book_id

    paths, _app, server, _runner = studio
    if hint == "outside":
        hint = str(tmp_path / "outside")
    (paths.root / continuation.SOURCE_HINT_FILE).write_text(json.dumps({"folder": hint}), encoding="utf-8")
    forbidden = hint.replace("\\", "/").casefold().rstrip("/")

    def guard(original):
        def checked(value, *args, **kwargs):
            text = str(value).replace("\\", "/").casefold().rstrip("/")
            assert text != forbidden and not text.startswith(forbidden + "/"), "a stored hint must not authorize I/O"
            return original(value, *args, **kwargs)
        return checked

    for module, name in ((os, "stat"), (os, "lstat"), (os, "scandir"), (io, "open")):
        monkeypatch.setattr(module, name, guard(getattr(module, name)))
    assert continuation.next_chapters(paths.root) == []
    status, plan = _call(server, "GET", f"/api/books/{book_id(paths.root)}/continuation")
    assert status == 200 and plan["paths"] == [] and plan["folder"] == hint


def test_the_picker_uses_an_existing_hint_and_cancel_reads_nothing(studio, tmp_path: Path) -> None:
    from abook.webui.server import Handler

    _paths, app, server, _runner = studio
    calls = []
    app.dialogs = SimpleNamespace(
        pick_files=lambda *args: calls.append(args) or [],
        pick_folder=lambda *args: calls.append(args) or None,
    )
    for route in ("files", "folder"):
        status, result = _call(server, "POST", f"/api/dialog/{route}", {"title": "Chọn chương mới", "start": str(tmp_path)})
        assert status == 200 and result == ({"paths": []} if route == "files" else {"path": None})
        assert calls[-1][:2] == ("Chọn chương mới", str(tmp_path))
    assert Handler._picker_start(str(tmp_path / "missing")) == ""
    assert Handler._picker_start(r"\\attacker.example\share") == ""
