"""Tab Nhân vật: "Đổi tên" (chỉ cái tên trên màn hình, names.json cạnh sổ dự án - không đụng sổ nhân vật, giọng, audio, không
phải thay đổi chờ "Áp dụng") và "Đổi giới tính" (đi đúng đường POST /voice của thẻ "Nam hay nữ")."""
from __future__ import annotations

import json
from pathlib import Path

from abook import continuation
from abook.config import build_settings, save_settings
from abook.database import ProjectDB
from abook import names
from abook.webui import store
from abook.webui.actions import FakeRunner
from abook.webui.library import Preferences, book_id
from abook.webui.remote_studio import permitted
from abook.webui.server import App, Server
from tests.test_listener_voices import _book
from tests.test_webui_listen_and_sync import _request


def _serve(tmp_path: Path):
    paths, db = _book(tmp_path)
    save_settings(paths.settings, build_settings())
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="phien")
    server = Server(app, port=0).start()
    return paths, db, app, server, f"/api/books/{book_id(paths.root)}", {"X-Ebook-Token": "phien"}


def _person(paths, name: str) -> dict:
    cast = store.cast(paths.root)
    return next(person for person in cast["characters"] + cast["extras"] if person["name"] == name)


def test_a_rename_shows_at_once_and_clearing_restores_the_original(tmp_path: Path) -> None:
    paths, _db, app, server, url, headers = _serve(tmp_path)
    before = paths.db.read_bytes()
    try:
        assert _person(paths, "LUCIEN")["displayName"] == "Lucien" and "originalName" not in _person(paths, "LUCIEN")

        status, data, _ = _request(server.port, "POST", f"{url}/characters/rename", headers=headers,
                                   body={"character": "LUCIEN", "name": "  Lu   Xi  "})
        assert status == 200, data
        assert json.loads(data) == {"character": "LUCIEN", "name": "Lu Xi", "original": "Lucien", "renamed": True}
        lucien = _person(paths, "LUCIEN")
        assert (lucien["displayName"], lucien["originalName"], lucien["name"]) == ("Lu Xi", "Lucien", "LUCIEN"), \
            "tên hiển thị đổi, khoá người nói giữ nguyên"
        assert _person(paths, "NATASHA")["displayName"] == "Natasha", "người khác không đổi"
        # Đọc lại từ đĩa (không nhớ gì giữa hai lần gọi) và qua đường HTTP của giao diện.
        status, data, _ = _request(server.port, "GET", f"{url}/cast", headers=headers)
        assert status == 200
        assert next(p for p in json.loads(data)["characters"] if p["name"] == "LUCIEN")["displayName"] == "Lu Xi"
        assert json.loads((paths.root / names.FILE_NAME).read_text(encoding="utf-8"))["LUCIEN"]["name"] == "Lu Xi"
        script = store.chapter_script(paths.root, 1)
        assert {segment["speaker"] for segment in script["segments"] if segment["speaker"]} >= {"Lu Xi", "Natasha"}

        assert store.pending_changes(paths.root, 0.0) == 0, "đổi tên không phải thay đổi chờ áp dụng"
        assert paths.db.read_bytes() == before, "sổ nhân vật và câu không bị đụng"

        status, _data, _ = _request(server.port, "POST", f"{url}/characters/rename", headers=headers,
                                    body={"character": "LUCIEN", "name": ""})
        assert status == 200
        assert _person(paths, "LUCIEN")["displayName"] == "Lucien" and "originalName" not in _person(paths, "LUCIEN")
        assert not (paths.root / names.FILE_NAME).read_text(encoding="utf-8").count("LUCIEN"), "bỏ là bỏ hẳn mục"

        # Gõ lại đúng tên gốc cũng là trở về tên gốc.
        _request(server.port, "POST", f"{url}/characters/rename", headers=headers, body={"character": "LUCIEN", "name": "Lu Xi"})
        status, _data, _ = _request(server.port, "POST", f"{url}/characters/rename", headers=headers,
                                    body={"character": "LUCIEN", "name": "Lucien"})
        assert status == 200 and "originalName" not in _person(paths, "LUCIEN")

        for body in ({"character": "HEIDI", "name": "X"}, {"character": "NARRATOR", "name": "X"}, {"name": "X"}):
            status, _data, _ = _request(server.port, "POST", f"{url}/characters/rename", headers=headers, body=body)
            assert status == 400, body
    finally:
        server.stop()
        app.close()


def test_the_remote_studio_may_rename(tmp_path: Path) -> None:
    assert permitted("POST", "/api/books/abc123/characters/rename")


def test_changing_the_gender_is_a_pending_voice_change_with_the_recorded_count(tmp_path: Path) -> None:
    paths, _db, app, server, url, headers = _serve(tmp_path)
    try:
        assert _person(paths, "NOAH")["recorded"] == 2, "Noah có hai câu đã thu: con số hộp thoại nói trước"
        status, data, _ = _request(server.port, "POST", f"{url}/voice", headers=headers,
                                   body={"character": "NOAH", "gender": "female"})
        assert status == 200, data
        requested_at = json.loads(data)["requestedAt"]
        (item,) = store.pending_details(paths.root, 0.0)["items"]
        assert item["label"] == "Giọng của Noah: giọng nữ" and item["lines"] == 2
        assert _person(paths, "NOAH")["pendingVoice"]["gender"] == "Nữ"
        # Đã đổi tên thì hộp "Áp dụng" nói tên mới.
        _request(server.port, "POST", f"{url}/characters/rename", headers=headers, body={"character": "NOAH", "name": "Nô-ê"})
        (item,) = store.pending_details(paths.root, 0.0)["items"]
        assert item["label"] == "Giọng của Nô-ê: giọng nữ"
        # Hoàn tác (Hoàn tác trong thông báo) gỡ đúng yêu cầu ấy.
        status, _data, _ = _request(server.port, "POST", f"{url}/voice", headers=headers,
                                    body={"character": "NOAH", "withdraw": True, "requestedAt": requested_at})
        assert status == 200 and store.pending_details(paths.root, 0.0)["items"] == []
    finally:
        server.stop()
        app.close()


def test_the_next_part_inherits_the_names(tmp_path: Path) -> None:
    first_root, second_root = tmp_path / "phan1", tmp_path / "phan2"
    first_root.mkdir()
    second_root.mkdir()
    assert names.set_name(first_root, "LUCIEN", "Lu Xi", "Lucien", now=0.0)
    assert names.set_name(first_root, "NATASHA", "Na", "Natasha")
    assert not names.set_name(first_root, "NATASHA", "Na", "Natasha"), "không đổi gì: không ghi lại"
    assert names.set_name(second_root, "NATASHA", "Ta-sa", "Natasha"), "phần sau đã tự đặt: giữ"

    assert names.carry(first_root, second_root) == 1
    assert names.carry(first_root, second_root) == 0
    assert names.shown(second_root, "lucien") == "Lu Xi" and names.shown(second_root, "NATASHA") == "Ta-sa"

    # Đúng đường "Làm tiếp cuốn này".
    source_root, target_root = tmp_path / "a", tmp_path / "b"
    for root in (source_root, target_root):
        root.mkdir()
        ProjectDB(root / "project.sqlite3").initialize_book(
            title="T", project_root=root, settings={}, settings_hash="s", input_manifest_hash="m")
    names.set_name(source_root, "LUCIEN", "Lu Xi", "Lucien")
    report = continuation.seed(source_root, target_root)
    assert report["names"] == 1 and names.shown(target_root, "LUCIEN") == "Lu Xi"
