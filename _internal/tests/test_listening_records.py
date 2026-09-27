"""Hồ sơ nghe độc lập với sách, app giữ liên kết 1-N (webui/listening.py, chủ sách 27-09).

Sách không biết gì về việc nghe, hồ sơ nghe không biết mình thuộc sách nào; một sách có nhiều hồ sơ, mỗi hồ sơ gắn với
đúng một sách, mỗi sách một hồ sơ đang dùng. Mọi hàm cũ nhận mã sách làm việc trên hồ sơ đang dùng.
"""
from __future__ import annotations

import json
from pathlib import Path

from ebook_reader.webui.listening import DEFAULT_RECORD_NAME, Listening


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
