"""Hộp xem trước của "Áp dụng N thay đổi" (soát UX a6 01-10: bấm là chạy ngay, không nói sẽ thu lại gì, hết bao lâu):
store.pending_details nói từng thay đổi bằng lời, số câu ĐÃ THU sẽ thu lại, ở chương nào, và thời gian ước theo tốc độ thật
của chính cuốn ấy - cùng cách chọn mục với số trên nút."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from abook import listener_overrides
from abook.webui import store
from tests.test_webui_listen_and_sync import make_project


def _project(tmp_path: Path) -> Path:
    project = make_project(tmp_path)
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("ALTER TABLE segments ADD COLUMN stable_id TEXT")
    db.execute("UPDATE segments SET stable_id = 's' || id")
    # Câu 2 cũng đã thu (câu 3 có sẵn bản thu trong fixture); câu 1 chưa thu.
    db.execute("UPDATE segments SET wav_path = 'x.wav' WHERE id = 2")
    db.commit()
    db.close()
    return project


def test_every_change_is_named_and_the_retake_is_measured(tmp_path: Path) -> None:
    project = _project(tmp_path)
    since = time.time() - 1
    listener_overrides.request_voice(project, "LUCIEN", preset="Thanh Bình", now=time.time())
    listener_overrides.request_pronunciation(project, "sáng", "sáng sớm", now=time.time())
    listener_overrides.request_retake(project, "s3", "x", now=time.time())

    details = store.pending_details(project, since)
    labels = [item["label"] for item in details["items"]]
    assert "Giọng của Lucien: Thanh Bình" in labels
    assert "“sáng” đọc là “sáng sớm”" in labels
    assert any(label.startswith("Thu lại “") for label in labels)
    assert len(details["items"]) == store.pending_changes(project, since), "số mục khớp số trên nút"
    # Câu 2 ("Trời đã sáng.") có từ "sáng"; câu 3 của Lucien (giọng + thu lại) - hai câu, một chương.
    assert details["lines"] == 2 and len(details["chapters"]) == 1
    # Chương 1 làm 20 giây cho 3 câu -> ~6,7 giây một câu.
    assert 12 <= details["seconds"] <= 14


def test_nothing_waiting_means_nothing_to_redo(tmp_path: Path) -> None:
    project = _project(tmp_path)
    assert store.pending_details(project, time.time()) == {"items": [], "lines": 0, "chapters": [], "seconds": 0.0}


def test_people_are_named_as_the_reader_sees_them(tmp_path: Path) -> None:
    # Soát lần đầu: hộp hiện "là lời của NPC_LOCAL::c00003::r2ce…::người dân", "LOUise", "cảm xúc excited", ngoặc kép hai lớp.
    project = _project(tmp_path)
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("UPDATE segments SET text = '“Ai đó?”' WHERE id = 2")
    db.commit()
    db.close()
    since = time.time() - 1
    listener_overrides.request_speaker(project, "s2", "x", "NPC_LOCAL::c00003::r2ce8a10554acb22e::người dân", now=time.time())
    listener_overrides.request_line(project, "s2", "x", emotion="excited", now=time.time())

    labels = [item["label"] for item in store.pending_details(project, since)["items"]]
    assert "“Ai đó?” là lời của người dân" in labels
    assert "“Ai đó?”: cảm xúc hào hứng" in labels


def test_one_change_can_be_dropped_from_the_box_and_the_older_wish_comes_back(tmp_path: Path) -> None:
    # Soát UX a6 01-10: muốn bỏ một mục trong "Áp dụng N thay đổi" thì phải đi tìm lại đúng thẻ ở ba tab khác nhau.
    import json

    from abook.webui.actions import FakeRunner
    from abook.webui.library import Preferences, book_id
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import _request

    root = tmp_path / "thu_vien"
    project = _project(root)
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(root)})
    app = App(preferences=preferences, runner=FakeRunner(), token="phien")
    server = Server(app, port=0).start()
    try:
        since = time.time() - 5
        listener_overrides.request_voice(project, "LUCIEN", preset="Thanh Bình", now=since + 1)
        listener_overrides.request_voice(project, "LUCIEN", preset="Quốc Tuấn", now=since + 2)
        listener_overrides.request_retake(project, "s3", "x", now=since + 3)
        items = store.pending_details(project, since)["items"]
        voice = next(item for item in items if item["kind"] == "voice")
        retake = next(item for item in items if item["kind"] == "retake")
        assert voice["label"] == "Giọng của Lucien: Quốc Tuấn"
        path = f"/api/books/{book_id(project)}/pending-changes/withdraw"
        headers = {"X-Ebook-Token": "phien"}
        for item in (voice, retake):
            status, data, _ = _request(server.port, "POST", path, headers=headers, body={
                "section": item["section"], "key": item["key"], "requestedAt": item["requestedAt"]})
            assert status == 200, data
        labels = [item["label"] for item in store.pending_details(project, since)["items"]]
        assert labels == ["Giọng của Lucien: Thanh Bình"], "lựa chọn trước đó trở lại, câu không còn chờ thu lại"
        # Bấm lần nữa (hộp cũ còn mở): không bỏ nhầm lựa chọn đã trở lại.
        status, data, _ = _request(server.port, "POST", path, headers=headers, body={
            "section": voice["section"], "key": voice["key"], "requestedAt": voice["requestedAt"]})
        assert status == 409 and "mở lại hộp" in json.loads(data)["error"]
    finally:
        server.stop()
        app.close()


def test_a_whole_chapter_retake_is_one_change_and_drops_as_one(tmp_path: Path) -> None:
    # Menu "…" của chương: "Thu lại cả chương" - mọi câu đã thu, MỘT lần bấm = một thay đổi trên nút và trong hộp.
    import json

    from abook.webui.actions import FakeRunner
    from abook.webui.library import Preferences, book_id
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import _request

    root = tmp_path / "thu_vien"
    project = _project(root)
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("ALTER TABLE segments ADD COLUMN text_sha256 TEXT")
    db.execute("UPDATE segments SET text_sha256 = 'h' || id")
    db.commit()
    db.close()
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(root)})
    app = App(preferences=preferences, runner=FakeRunner(), token="phien")
    server = Server(app, port=0).start()
    try:
        since = time.time() - 1
        headers = {"X-Ebook-Token": "phien"}
        status, data, _ = _request(server.port, "POST", f"/api/books/{book_id(project)}/chapters/1/retake", headers=headers)
        assert status == 200 and json.loads(data)["lines"] == 2, "câu 2 và 3 đã thu; câu 1 chưa thu"
        assert store.pending_changes(project, since) == 1
        (item,) = store.pending_details(project, since)["items"]
        assert item["label"] == "Thu lại cả chương (2 câu)" and item["lines"] == 2 and sorted(item["keys"]) == ["s2", "s3"]
        status, data, _ = _request(server.port, "POST", f"/api/books/{book_id(project)}/pending-changes/withdraw", headers=headers,
                                   body={"section": "retakes", "key": item["key"], "keys": item["keys"],
                                         "requestedAt": item["requestedAt"]})
        assert status == 200, data
        assert store.pending_changes(project, since) == 0
        status, _data, _ = _request(server.port, "POST", f"/api/books/{book_id(project)}/chapters/2/retake", headers=headers)
        assert status == 400, "chương chưa thu câu nào"
    finally:
        server.stop()
        app.close()
