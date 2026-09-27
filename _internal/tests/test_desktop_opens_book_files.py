"""Máy tính mở file sách `.abook` (webui/packages.py): nghe như sách tự làm, và không bao giờ thành hai cuốn.

Fixture: cuốn hai chương của test đồng bộ (`make_project`) - chương 1 đã có MP3, chương 2 đang thu - xuất ra file ở
"máy sản xuất", rồi mở ở một thư viện khác (máy của người nghe) hoặc chính thư viện ấy.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pytest

from ebook_reader.webui import bookfile, packages
from ebook_reader.webui.actions import FakeRunner
from ebook_reader.webui.library import Preferences, book_id
from ebook_reader.webui.listening import Listening
from ebook_reader.webui.server import ApiError, App, Server
from tests.test_webui_listen_and_sync import _request, make_project

TOKEN = {"X-Ebook-Token": "t"}


def _app(tmp_path: Path, library_root: Path) -> App:
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(library_root)})
    return App(preferences=preferences, runner=FakeRunner(), token="t",
               listening=Listening(tmp_path / "prefs" / "listening.json"))


def _produced(tmp_path: Path) -> tuple[Path, Path]:
    producer = tmp_path / "may_san_xuat"
    producer.mkdir()
    project = make_project(producer)
    return project, bookfile.pack(project, tmp_path / "sach.abook")


def _finish_second_chapter(project: Path) -> None:
    mp3 = project / "output" / "chapters" / "00002_646.mp3"
    mp3.write_bytes(b"ID3" + bytes(range(255, -1, -1)) * 40)
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("UPDATE chapters SET status='completed', output_mp3=?, completed_at=? WHERE id=2", (str(mp3), time.time()))
    db.execute("UPDATE segments SET status='verified', wav_duration=3.0 WHERE id=5")
    db.commit()
    db.close()


def test_a_book_file_opens_on_another_computer_and_plays(tmp_path: Path) -> None:
    project, file = _produced(tmp_path)
    elsewhere = tmp_path / "thu_vien_nguoi_nghe"
    elsewhere.mkdir()
    app = _app(tmp_path, elsewhere)

    opened = app.open_book_file(str(file))

    assert opened["how"] == "new"
    [book] = app.listen_library()
    assert (book["id"], book["title"], book["imported"]) == (opened["id"], "Sách thử · Tập 1", True)
    view = app.listen_book(opened["id"])
    assert [(chapter["id"], chapter["available"]) for chapter in view["chapters"]] == [(1, True), (2, False)]
    assert not view["complete"] and not view["producing"] and not view["paused"], "không có Studio nào đang dừng"
    assert app.library_view()["books"] == [], "Studio không thấy nó: không phải dự án"
    server = Server(app, port=0).start()
    try:
        status, data, _ = _request(server.port, "GET", f"/media/books/{opened['id']}/chapters/1", headers=TOKEN)
        assert status == 200 and data == (project / "output" / "chapters" / "00001_645.mp3").read_bytes()
        status, _data, _ = _request(server.port, "GET", f"/media/books/{opened['id']}/chapters/2", headers=TOKEN)
        assert status == 404, "chương chưa thu thì chưa nghe được"
        status, data, _ = _request(server.port, "GET", f"/api/books/{opened['id']}/chapters/1/script", headers=TOKEN)
        assert status == 200 and json.loads(data)["segments"], "đọc theo"
        status, data, _ = _request(server.port, "GET", f"/api/books/{opened['id']}/cast", headers=TOKEN)
        assert status == 200 and "LUCIEN" in data.decode("utf-8")
        status, _data, _ = _request(server.port, "GET", f"/media/books/{opened['id']}/samples/3", headers=TOKEN)
        assert status == 200, "câu mẫu giọng nhân vật"
        status, _data, _ = _request(server.port, "POST", f"/api/listen/books/{opened['id']}/progress", headers=TOKEN,
                                    body={"chapterId": 1, "seconds": 5.0, "duration": 10.0})
        assert status == 200
        status, _data, _ = _request(server.port, "GET", f"/api/books/{opened['id']}", headers=TOKEN)
        assert status == 404, "trang Studio của nó không có"
    finally:
        server.stop()
    assert app.listening.get(opened["id"])["last"]["seconds"] == 5.0


def test_the_folder_reads_like_the_book(tmp_path: Path) -> None:
    _project, file = _produced(tmp_path)
    app = _app(tmp_path, tmp_path / "thu_vien")

    folder = app.library.resolve_listenable(app.open_book_file(str(file))["id"])

    assert folder is not None and folder.parent.name == packages.IMPORTED_FOLDER
    assert folder.name.startswith("Sách thử · Tập 1 (") and len(folder.name) == len("Sách thử · Tập 1 (") + 9


def test_opening_the_same_file_again_goes_to_the_same_book(tmp_path: Path) -> None:
    _project, file = _produced(tmp_path)
    app = _app(tmp_path, tmp_path / "thu_vien")
    first = app.open_book_file(str(file))

    again = app.open_book_file(str(file))

    assert (again["id"], again["how"]) == (first["id"], "existing")
    assert len(app.listen_library()) == 1


def test_a_file_from_this_computer_opens_its_own_project(tmp_path: Path) -> None:
    """File do chính Studio máy này xuất ra: mở đúng dự án ấy, không chép thêm một bản."""
    project, file = _produced(tmp_path)
    app = _app(tmp_path, project.parent)

    opened = app.open_book_file(str(file))

    assert (opened["id"], opened["how"]) == (book_id(project), "project")
    assert not (project.parent / packages.IMPORTED_FOLDER).exists()


def test_a_fuller_file_of_the_same_book_replaces_it_and_keeps_the_listening(tmp_path: Path) -> None:
    project, file = _produced(tmp_path)
    app = _app(tmp_path, tmp_path / "thu_vien")
    first = app.open_book_file(str(file))
    app.listening.progress(first["id"], 1, 7.0, 10.0)
    _finish_second_chapter(project)
    fuller = bookfile.pack(project, tmp_path / "sach_du.abook")

    updated = app.open_book_file(str(fuller))

    assert (updated["id"], updated["how"]) == (first["id"], "updated"), "cùng thư mục, cùng mã: dữ liệu nghe theo"
    view = app.listen_book(first["id"])
    assert [chapter["available"] for chapter in view["chapters"]] == [True, True]
    assert view["state"]["last"]["seconds"] == 7.0
    assert app.open_book_file(str(file))["how"] == "existing", "bản ít chương hơn không đè bản đủ"


def test_a_damaged_or_foreign_file_is_refused_with_a_reason(tmp_path: Path) -> None:
    app = _app(tmp_path, tmp_path / "thu_vien")
    foreign = tmp_path / "khong_phai.abook"
    foreign.write_text("không phải sách", encoding="utf-8")

    with pytest.raises(ApiError) as refused:
        app.open_book_file(str(foreign))
    assert refused.value.status == 400 and "không phải file sách" in refused.value.message
    with pytest.raises(ApiError) as missing:
        app.open_book_file(str(tmp_path / "khong_co.abook"))
    assert missing.value.status == 404
    assert app.listen_library() == []


def test_without_the_app_window_there_is_nothing_to_pick_with(tmp_path: Path) -> None:
    with pytest.raises(ApiError) as refused:
        _app(tmp_path, tmp_path / "thu_vien").open_book_file()
    assert refused.value.status == 400


def test_a_tampered_manifest_cannot_reach_outside_the_book(tmp_path: Path) -> None:
    _project, file = _produced(tmp_path)
    app = _app(tmp_path, tmp_path / "thu_vien")
    folder = app.library.resolve_listenable(app.open_book_file(str(file))["id"])
    assert folder is not None
    (tmp_path / "bi_mat.mp3").write_bytes(b"secret")
    book = json.loads((folder / "book.json").read_text(encoding="utf-8"))
    book["chapters"][0]["file"] = "../../bi_mat.mp3"
    (folder / "book.json").write_text(json.dumps(book), encoding="utf-8")

    assert packages.chapter_file(folder, 1) is None


def test_the_manifest_name_matches_the_book_file_format() -> None:
    assert packages.MANIFEST == bookfile.MANIFEST
