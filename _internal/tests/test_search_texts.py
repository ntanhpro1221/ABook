"""Ô "Tìm trong sách" với sách dài (server `get_search_texts`): một yêu cầu trả chữ của cả lô chương thay vì hỏi từng chương (sách 3000
chương mất ~20 giây). Chỉ số câu phải TRÙNG màn đọc (`?at=`): mỗi chương đúng các câu của `get_script` (hay đúng chữ của `get_chapter_text`
với chương chỉ-có-chữ - giao diện tự chia đoạn như màn đọc). Chương hỏng chỉ hỏng chương ấy; lô có giới hạn.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from abook.webui import book_edits, packages, remote_books, remote_studio
from abook.webui import server as server_module
from abook.webui.library import book_id
from abook.webui.server import Server
from tests import book_edits_fixtures as shared
from tests import import_fixtures
from tests.test_book_edits import _app
from tests.test_webui_listen_and_sync import _request, make_project

TOKEN = {"X-Ebook-Token": "t"}


def _get(port: int, path: str) -> tuple[int, Any]:
    status, data, _ = _request(port, "GET", path, headers=TOKEN)
    return status, json.loads(data) if data[:1] in (b"{", b"[") else data


def _reader_segments(port: int, identifier: str, chapter: int) -> list[dict[str, Any]] | None:
    """Các câu màn đọc thấy (get_script), chỉ phần ô tìm dùng: chữ + dấu ngăn cảnh."""
    status, script = _get(port, f"/api/books/{identifier}/chapters/{chapter}/script")
    if status != 200:
        return None
    return [{"text": s["text"], **({"sceneBreak": True} if s.get("sceneBreak") else {})} for s in script["segments"]]


@pytest.fixture()
def serve(tmp_path: Path):
    servers: list[Server] = []

    def start(library: Path) -> int:
        server = Server(_app(tmp_path, library), port=0).start()
        servers.append(server)
        return server.port

    yield start
    for server in servers:
        server.stop()


def _imported(tmp_path: Path) -> tuple[Path, Path, str]:
    library = tmp_path / "thu_vien"
    folder = library / packages.IMPORTED_FOLDER / "base"
    shutil.copytree(shared.BASE, folder)
    return library, folder, book_id(folder)


def test_an_imported_book_gives_each_chapter_the_sentences_the_reader_shows(tmp_path: Path, serve) -> None:
    library, folder, identifier = _imported(tmp_path)
    # Lớp sửa của người nghe (tên nhân vật, tên chương) không đổi chữ hay thứ tự câu: chỉ số câu vẫn trùng màn đọc.
    book_edits.set_character_name(folder, "LUCIEN", "Lu-xi-en")
    book_edits.set_chapter_title(folder, 1, "Chương Một", None)
    script = json.loads((folder / "scripts" / "2.json").read_text(encoding="utf-8"))
    script["segments"][0]["sceneBreak"] = True
    (folder / "scripts" / "2.json").write_bytes(json.dumps(script, ensure_ascii=False).encode("utf-8"))
    port = serve(library)

    status, found = _get(port, f"/api/listen/books/{identifier}/search-texts?chapters=2,1,9")

    assert status == 200
    assert [item["id"] for item in found["chapters"]] == [2, 1, 9], "theo đúng thứ tự xin"
    for item in found["chapters"][:2]:
        assert item["segments"] == _reader_segments(port, identifier, item["id"]) and item["segments"]
    assert found["chapters"][0]["segments"][0] == {"text": script["segments"][0]["text"], "sceneBreak": True}
    assert found["chapters"][2] == {"id": 9, "failed": True}, "chương không có: báo hỏng như get_script 404"


def test_a_damaged_chapter_fails_alone(tmp_path: Path, serve) -> None:
    library, folder, identifier = _imported(tmp_path)
    (folder / "scripts" / "1.json").write_bytes(b"{ hong")
    port = serve(library)

    status, found = _get(port, f"/api/listen/books/{identifier}/search-texts?chapters=1,2")

    assert status == 200
    assert found["chapters"][0] == {"id": 1, "failed": True}
    assert found["chapters"][1]["segments"] == _reader_segments(port, identifier, 2)
    (folder / "scripts" / "1.json").write_bytes(json.dumps({"segments": [{"text": "Câu."}, {"speaker": "LUCIEN"}]}).encode("utf-8"))
    status, found = _get(port, f"/api/listen/books/{identifier}/search-texts?chapters=1,2")
    assert status == 200 and found["chapters"][0] == {"id": 1, "failed": True}, "câu không có chữ: chương hỏng, không phải cả lô"
    assert found["chapters"][1]["segments"] == _reader_segments(port, identifier, 2)


def test_a_text_book_gives_the_raw_text_of_each_chapter_the_reader_splits(tmp_path: Path, serve) -> None:
    library = tmp_path / "thu_vien"
    app = _app(tmp_path / "studio", library)
    added = app.add_text_book(str(import_fixtures.FIXTURES / "epub3.epub"))
    folder = app._listenable(added["id"])
    # Dòng người nghe bỏ khỏi phần đọc: máy chủ vẫn trả chữ nguyên (như get_chapter_text), giao diện bỏ dòng khi chia đoạn như màn đọc.
    book_edits.set_skip_line(folder, [2], "Dịch: Nhóm Lục Bình", True)
    port = serve(library)
    identifier = added["id"]

    status, found = _get(port, f"/api/listen/books/{identifier}/search-texts?chapters=1,2,3&text=1,2,3")
    _status, as_script = _get(port, f"/api/listen/books/{identifier}/search-texts?chapters=2")

    assert status == 200
    for item in found["chapters"]:
        _status, chapter = _get(port, f"/api/listen/books/{identifier}/chapters/{item['id']}/text")
        assert item == {"id": item["id"], "text": chapter["text"]}
    assert "Dịch: Nhóm Lục Bình" in found["chapters"][1]["text"]
    assert as_script["chapters"] == [{"id": 2, "failed": True}], "không kịch bản giả - như get_script 404"


def test_a_studio_project_gives_the_sentences_of_its_reader_script(tmp_path: Path, serve) -> None:
    library = tmp_path / "thu_vien"
    library.mkdir()
    project = make_project(library)
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("ALTER TABLE segments ADD COLUMN scene_break INTEGER")
    db.execute("UPDATE segments SET scene_break=1 WHERE id=2")
    db.execute("UPDATE segments SET seq=9 WHERE id=1")  # thứ tự đọc là `seq`, không phải mã câu
    db.commit()
    db.close()
    port = serve(library)
    identifier = book_id(project)

    status, found = _get(port, f"/api/listen/books/{identifier}/search-texts?chapters=1,2,3&text=2")

    assert status == 200
    assert found["chapters"][0]["segments"] == _reader_segments(port, identifier, 1)
    assert [s["text"] for s in found["chapters"][0]["segments"]] == ["Trời đã sáng.", "“Đi thôi.”", "Chương 646 - Trở về (1)"]
    assert found["chapters"][0]["segments"][0]["sceneBreak"] is True
    assert found["chapters"][1:] == [{"id": 2, "failed": True}, {"id": 3, "failed": True}], "dự án không có chương chỉ-có-chữ; chương 3 không có"
    status, found = _get(port, f"/api/listen/books/{identifier}/search-texts?chapters=2")
    assert found["chapters"][0]["segments"] == _reader_segments(port, identifier, 2), "chương đang thu vẫn tìm được"


def test_a_lot_is_bounded_in_chapters_and_in_text(tmp_path: Path, serve, monkeypatch: pytest.MonkeyPatch) -> None:
    library, _folder, identifier = _imported(tmp_path)
    port = serve(library)
    many = ",".join(str(n) for n in range(1, server_module.SEARCH_TEXT_CHAPTERS + 2))

    assert _get(port, f"/api/listen/books/{identifier}/search-texts?chapters={many}")[0] == 400
    assert _get(port, f"/api/listen/books/{identifier}/search-texts")[0] == 400
    assert _get(port, f"/api/listen/books/{identifier}/search-texts?chapters=1,x")[0] == 400
    monkeypatch.setattr(server_module, "SEARCH_TEXT_CHARS", 1)
    status, found = _get(port, f"/api/listen/books/{identifier}/search-texts?chapters=1,2")
    assert status == 200 and [item["id"] for item in found["chapters"]] == [1], "chữ quá nhiều: trả trước phần đã đọc, giao diện xin tiếp"


def test_a_book_of_another_computer_keeps_asking_chapter_by_chapter(tmp_path: Path, serve, monkeypatch: pytest.MonkeyPatch) -> None:
    library, _folder, identifier = _imported(tmp_path)
    port = serve(library)
    monkeypatch.setattr(remote_books, "remote_of", lambda book: {"device": "may-khac"})

    status, _found = _get(port, f"/api/listen/books/{identifier}/search-texts?chapters=1")

    assert status == 409, "chữ chưa đệm phải hỏi máy kia từng chương - giao diện tìm từng chương như cũ"


def test_a_paired_device_can_search_a_book() -> None:
    assert remote_studio.permitted("GET", "/api/listen/books/abc/search-texts", producing=False), "thiết bị chỉ nghe cũng tìm được"
    assert not remote_studio.permitted("POST", "/api/listen/books/abc/search-texts")
