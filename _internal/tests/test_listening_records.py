"""Hồ sơ nghe độc lập với sách, app giữ liên kết 1-N (webui/listening.py, chủ sách 27-09).

Sách không biết gì về việc nghe, hồ sơ nghe không biết mình thuộc sách nào; một sách có nhiều hồ sơ, mỗi hồ sơ gắn với
đúng một sách, mỗi sách một hồ sơ đang dùng. Mọi hàm cũ nhận mã sách làm việc trên hồ sơ đang dùng.
"""
from __future__ import annotations

import json
from pathlib import Path

from ebook_reader.webui.actions import FakeRunner
from ebook_reader.webui.library import book_id
from ebook_reader.webui.listening import DEFAULT_RECORD_NAME, Listening, default_record_id
from ebook_reader.webui.server import App, Server
from tests.test_webui_listen_and_sync import _request, library  # noqa: F401 - library là fixture


def test_the_old_file_becomes_one_default_record_per_book(tmp_path: Path) -> None:
    path = tmp_path / "listening.json"
    old = {"sach-a": {"last": {"chapterId": 3, "seconds": 812.4, "at": 1.0}, "chapters": {}, "bookmarks": [
        {"id": "m1", "chapterId": 3, "seconds": 64.0, "note": "đoạn hay", "at": 1.0}], "updatedAt": 5.0}}
    path.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")

    listening = Listening(path)

    assert listening.get("sach-a")["last"]["seconds"] == 812.4
    assert [mark["note"] for mark in listening.get("sach-a")["bookmarks"]] == ["đoạn hay"]
    [record] = listening.records("sach-a")
    assert record["name"] == DEFAULT_RECORD_NAME and record["active"]
    listening.progress("sach-a", 3, 900.0, 1000.0)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["version"] == 2 and set(saved) == {"version", "records", "links"}
    assert "sach-a" not in json.dumps(saved["records"]), "hồ sơ không biết mình thuộc sách nào"


def test_one_book_many_records_each_with_its_own_place(tmp_path: Path) -> None:
    listening = Listening(tmp_path / "listening.json")
    listening.progress("sach", 1, 300.0, 1000.0)
    listening.add_bookmark("sach", 1, 120.0, "của bố")
    first = listening.records("sach")[0]["id"]

    second = listening.create_record("sach", "Con")
    assert listening.get("sach")["bookmarks"] == [] and "last" not in listening.get("sach"), "hồ sơ mới nghe từ đầu"
    listening.progress("sach", 2, 40.0, 1000.0)

    assert listening.activate("sach", first)
    assert listening.get("sach")["last"]["chapterId"] == 1
    assert [mark["note"] for mark in listening.get("sach")["bookmarks"]] == ["của bố"]
    assert listening.activate("sach", second["id"])
    assert listening.get("sach")["last"]["chapterId"] == 2
    assert [(record["name"], record["active"]) for record in listening.records("sach")] == [
        (DEFAULT_RECORD_NAME, False), ("Con", True)]
    assert not listening.activate("sach-khac", first), "chỉ bật được hồ sơ của chính sách ấy"


def test_a_record_moves_to_another_book(tmp_path: Path) -> None:
    """Bản sản xuất mới của cùng truyện: app gắn hồ sơ cũ sang sách mới, chỗ nghe đi theo."""
    listening = Listening(tmp_path / "listening.json")
    listening.progress("ban-cu", 7, 55.0, 900.0)
    record = listening.records("ban-cu")[0]["id"]

    assert listening.move_record(record, "ban-moi")

    assert listening.get("ban-moi")["last"]["chapterId"] == 7
    assert listening.records("ban-cu") == [] and listening.book_of(record) == "ban-moi"
    assert "last" not in listening.get("ban-cu")


def test_deleting_the_active_record_falls_back_to_the_latest_other(tmp_path: Path) -> None:
    listening = Listening(tmp_path / "listening.json")
    listening.progress("sach", 1, 10.0, 100.0)
    keep = listening.records("sach")[0]["id"]
    gone = listening.create_record("sach", "Nghe lại")["id"]

    assert listening.delete_record(gone)

    assert [record["id"] for record in listening.records("sach")] == [keep]
    assert listening.records("sach")[0]["active"] and listening.get("sach")["last"]["seconds"] == 10.0
    assert not listening.delete_record(gone)


def test_names_are_trimmed_and_records_survive_a_restart(tmp_path: Path) -> None:
    path = tmp_path / "listening.json"
    listening = Listening(path)
    record = listening.create_record("sach", "  " + "x" * 200)["id"]
    assert len(listening.records("sach")[0]["name"]) == 60
    assert listening.rename_record(record, "Bố") and not listening.rename_record(record, "   ")

    again = Listening(path)

    assert [(item["name"], item["active"]) for item in again.records("sach")] == [("Bố", True)]


def test_sync_merges_into_the_named_record_not_whichever_is_active(tmp_path: Path) -> None:
    """Điện thoại gửi hồ sơ R đúng lúc máy tính vừa đổi sang hồ sơ khác: R vẫn nhận đúng phần của R."""
    listening = Listening(tmp_path / "listening.json")
    phone_record = "r-" + "a" * 16
    first = listening.merge_record("sach", phone_record, {"last": {"chapterId": 2, "seconds": 30.0, "at": 5.0}},
                                   name="Điện thoại", active_at=5.0)
    assert first["record"] == phone_record and first["book"] == "sach" and first["active"]["record"] == phone_record
    desk = listening.create_record("sach", "Máy tính")["id"]

    reply = listening.merge_record("sach", phone_record, {"last": {"chapterId": 3, "seconds": 12.0, "at": 9.0}},
                                   active_at=5.0)

    assert reply["last"]["chapterId"] == 3, "phần của điện thoại vào đúng hồ sơ của nó"
    assert "last" not in listening.get("sach"), "hồ sơ đang dùng ở máy tính không bị trộn"
    assert reply["active"]["record"] == desk and reply["activeState"] == listening.get("sach")
    assert [record["name"] for record in reply["records"]] == ["Điện thoại", "Máy tính"]


def test_the_later_choice_of_record_wins_across_devices(tmp_path: Path) -> None:
    listening = Listening(tmp_path / "listening.json")
    listening.create_record("sach", "Máy tính")
    phone_record = "r-" + "b" * 16

    reply = listening.merge_record("sach", phone_record, {}, name="Con", active_at=10**10)

    assert reply["active"]["record"] == phone_record and "activeState" not in reply
    assert [(record["name"], record["active"]) for record in listening.records("sach")] == [
        ("Máy tính", False), ("Con", True)]


def test_old_phones_still_sync_into_the_active_record(tmp_path: Path) -> None:
    listening = Listening(tmp_path / "listening.json")
    listening.merge("sach", {"last": {"chapterId": 1, "seconds": 9.0, "at": 3.0}})
    assert listening.get("sach")["last"]["seconds"] == 9.0 and len(listening.records("sach")) == 1


def test_a_record_moved_here_tells_the_phone_its_new_book(tmp_path: Path) -> None:
    listening = Listening(tmp_path / "listening.json")
    record = "r-" + "c" * 16
    listening.merge_record("ban-cu", record, {}, name="Mặc định")
    listening.move_record(record, "ban-moi")

    reply = listening.merge_record("ban-cu", record, {"last": {"chapterId": 4, "seconds": 1.0, "at": 7.0}})

    assert reply["book"] == "ban-moi" and listening.get("ban-moi")["last"]["chapterId"] == 4
    assert listening.records("ban-cu") == []


def test_the_ui_manages_the_records_of_a_book(library) -> None:  # noqa: F811 - fixture
    """API cho giao diện: xem, tạo (nghe từ đầu), bật, đổi tên, xoá hồ sơ - chỉ hồ sơ của chính cuốn ấy."""
    lib, project, listening = library
    app = App(preferences=lib.preferences, runner=FakeRunner(), token="t", listening=listening)
    server = Server(app, port=0).start()
    headers = {"X-Ebook-Token": "t"}
    base = f"/api/listen/books/{book_id(project)}"
    try:
        _status, data, _ = _request(server.port, "GET", base, headers=headers)
        assert json.loads(data)["records"] == [], "chưa nghe thì chưa có hồ sơ nào"
        _request(server.port, "POST", base + "/progress", headers=headers,
                 body={"chapterId": 1, "seconds": 5.0, "duration": 100.0})
        status, data, _ = _request(server.port, "POST", base + "/records", headers=headers, body={"name": "Con"})
        records = json.loads(data)["records"]
        assert status == 201 and [(item["name"], item["active"]) for item in records] == [
            (DEFAULT_RECORD_NAME, False), ("Con", True)]
        first = records[0]["id"]
        _status, data, _ = _request(server.port, "POST", f"{base}/records/{first}/activate", headers=headers)
        assert json.loads(data)["records"][0]["active"]
        _status, data, _ = _request(server.port, "PUT", f"{base}/records/{first}", headers=headers, body={"name": "Bố"})
        assert json.loads(data)["records"][0]["name"] == "Bố"
        status, _data, _ = _request(server.port, "PUT", f"{base}/records/{first}", headers=headers, body={"name": " "})
        assert status == 400
        status, _data, _ = _request(server.port, "DELETE", f"{base}/records/r-{'0' * 16}", headers=headers)
        assert status == 404, "hồ sơ không thuộc cuốn này"
        _status, data, _ = _request(server.port, "DELETE", f"{base}/records/{records[1]['id']}", headers=headers)
        assert [item["name"] for item in json.loads(data)["records"]] == ["Bố"]
    finally:
        server.stop()


def test_both_devices_share_one_default_record_per_book(tmp_path: Path) -> None:
    """Hồ sơ "Mặc định" mang mã suy từ mã sách ở mọi máy: máy tính và điện thoại cùng nghe một cuốn (hay cùng chuyển
    bản lưu cũ) là MỘT hồ sơ - đồng bộ gộp vào nhau, không tách đôi chỗ nghe."""
    old = tmp_path / "listening.json"
    old.write_text(json.dumps({"sach": {"bookmarks": [{"id": "m-may-tinh", "chapterId": 1, "seconds": 5.0,
                                                       "note": "", "at": 1.0}], "chapters": {}}}), encoding="utf-8")
    desktop = Listening(old)
    [record] = desktop.records("sach")
    assert record["id"] == default_record_id("sach")

    phone_state = {"bookmarks": [{"id": "m-dien-thoai", "chapterId": 2, "seconds": 9.0, "note": "", "at": 2.0}],
                   "chapters": {}}
    reply = desktop.merge_record("sach", default_record_id("sach"), phone_state)

    assert len(desktop.records("sach")) == 1 and reply["record"] == record["id"]
    assert {mark["id"] for mark in desktop.get("sach")["bookmarks"]} == {"m-may-tinh", "m-dien-thoai"}
    fresh = Listening(tmp_path / "moi.json")
    fresh.progress("sach-moi", 1, 3.0, 100.0)
    assert fresh.records("sach-moi")[0]["id"] == default_record_id("sach-moi")
