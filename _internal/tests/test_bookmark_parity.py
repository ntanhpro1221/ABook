"""Cùng ví dụ dấu trang trên máy tính và JVM."""
import json
from pathlib import Path

import pytest

from abook.webui.listening import Listening

CASES = json.loads((Path(__file__).parent / "fixtures/listening_records/bookmark_places.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_bookmark_places(tmp_path, case):
    listening = Listening(tmp_path / "listening.json")
    def add(mark):
        return listening.add_bookmark("b", mark.get("chapterId", 1), mark["seconds"], index=mark.get("index"))
    first = add(case["old"])
    second = add(case["new"])
    assert (first["id"] == second["id"]) == case["same"]


def test_duplicate_fills_only_an_empty_note_and_keeps_creation_time(tmp_path, monkeypatch):
    listening = Listening(tmp_path / "listening.json")
    monkeypatch.setattr("abook.webui.listening.time.time", lambda: 10)
    first = listening.add_bookmark("b", 1, 64)
    monkeypatch.setattr("abook.webui.listening.time.time", lambda: 20)
    second = listening.add_bookmark("b", 1, 64, " Ghi chú mới ")
    assert (second["id"], second["note"], second["at"], second["createdAt"]) == (first["id"], "Ghi chú mới", 20, 10)
    assert listening.add_bookmark("b", 1, 64, "Thay thế")["note"] == "Ghi chú mới"
    assert len(listening.get("b")["bookmarks"]) == 1


def test_restore_keeps_id_and_outlives_the_tombstone_on_another_device(tmp_path, monkeypatch):
    spec = json.loads((Path(__file__).parent / "fixtures/listening_records/restore_bookmark.json").read_text(encoding="utf-8"))
    listening = Listening(tmp_path / "listening.json")
    listening.merge("b", {"chapters": {}, "bookmarks": [], "deleted": {spec["mark"]["id"]: spec["deletedAt"]}})
    monkeypatch.setattr("abook.webui.listening.time.time", lambda: 30)
    restored = listening.restore_bookmark("b", spec["mark"])
    assert restored == {**spec["mark"], "at": 30}
    assert spec["mark"]["id"] not in listening.get("b").get("deleted", {})
    listening.merge("b", {"bookmarks": [spec["remoteEdit"]], "deleted": {restored["id"]: spec["deletedAt"]}})
    assert listening.get("b")["bookmarks"] == [restored]
