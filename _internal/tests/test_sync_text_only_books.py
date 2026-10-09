"""Sách chưa có chương nào nghe được vẫn hiện ở máy đã ghép: chữ nguồn đi qua cổng đồng bộ như chương chỉ-chữ (sync.text_layer)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from abook.webui import bookfile, sync
from abook.webui.library import Library, Preferences
from abook.webui.listening import Listening
from abook.webui.sync import Devices, SyncApp
from tests.test_webui_listen_and_sync import make_project


def _text_only(root: Path) -> Path:
    """`make_project` rồi bỏ hết audio: hai chương chưa thu, mỗi chương có file chữ nguồn."""
    project = make_project(root)
    sources = []
    for number, text in ((1, "Chương một.\n\nTrời đã sáng."), (2, "Chương hai.\n\nĐêm xuống.")):
        source = project / f"nguon{number}.txt"
        source.write_bytes(text.encode("utf-8"))
        sources.append(str(source))
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("UPDATE chapters SET status = 'pending', output_mp3 = '', completed_at = NULL, input_path = ? WHERE id = 1", (sources[0],))
    db.execute("UPDATE chapters SET status = 'pending', input_path = ? WHERE id = 2", (sources[1],))
    db.commit()
    db.close()
    (project / "output" / "chapters" / "00001_645.mp3").unlink()
    return project


def _app(tmp_path: Path, root: Path) -> SyncApp:
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(root)})
    return SyncApp(Library(preferences), Listening(tmp_path / "listening.json"), Devices(tmp_path / "devices.json"), "Máy thử")


def test_a_book_with_no_audio_chapter_is_listed_for_paired_devices(tmp_path: Path) -> None:
    root = tmp_path / "thu_vien"
    root.mkdir()
    _text_only(root)
    listed = _app(tmp_path, root).library_view()
    assert [(book["chaptersTotal"], book["chaptersAvailable"], book["complete"]) for book in listed] == [(2, 0, False)]


def test_its_chapters_travel_as_text_chapters_and_the_text_is_served(tmp_path: Path) -> None:
    root = tmp_path / "thu_vien"
    root.mkdir()
    project = _text_only(root)
    app = _app(tmp_path, root)
    book = sync.manifest(project, "b", app.listening)
    assert [(c["state"], c["text"], c["available"], "file" in c) for c in book["chapters"]] == [
        ("text", "texts/1.txt", False, False), ("text", "texts/2.txt", False, False)]
    assert app.resolve_file(project, "texts/2.txt") == "Chương hai.\n\nĐêm xuống.".encode("utf-8")
    assert app.resolve_file(project, "texts/9.txt") is None

    before = book["version"]
    (project / "nguon2.txt").write_bytes("Chương hai, sửa.".encode("utf-8"))
    assert sync.manifest(project, "b", app.listening)["version"] != before, "sửa file nguồn là một phiên bản mới"


def test_the_book_file_of_such_a_book_is_the_same_text_book_as_before(tmp_path: Path) -> None:
    root = tmp_path / "thu_vien"
    root.mkdir()
    project = _text_only(root)
    book, files = bookfile.listening_layer(project)
    assert [(c["state"], c["text"], "file" in c) for c in book["chapters"]] == [("text", "texts/1.txt", False), ("text", "texts/2.txt", False)]
    assert files["texts/1.txt"] == "Chương một.\n\nTrời đã sáng.".encode("utf-8")


def test_once_a_chapter_is_audible_the_text_layer_steps_aside(tmp_path: Path) -> None:
    root = tmp_path / "thu_vien"
    root.mkdir()
    project = make_project(root)
    app = _app(tmp_path, root)
    book = sync.manifest(project, "b", app.listening)
    assert not any("text" in chapter for chapter in book["chapters"])
    assert app.resolve_file(project, "texts/1.txt") is None
