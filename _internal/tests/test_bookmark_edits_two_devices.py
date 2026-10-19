"""Dấu trang sửa / xoá / hoàn tác giữa hai máy (soát a70 mục 7-8): ghi chú vừa sửa thắng bản cũ của máy kia, Hoàn tác xoá thắng lệnh xoá đã
sang máy kia, và dòng dấu trang vẫn hiện lúc đặt dấu gốc."""
from __future__ import annotations

from pathlib import Path

import pytest

from abook.webui import listening as listening_module
from abook.webui.listening import Listening, merge_states


@pytest.fixture(autouse=True)
def _clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Đồng hồ đi một giây mỗi lần đọc: sửa / xoá / hoàn tác nối nhau mà mốc vẫn khác nhau (time.sleep bị conftest bỏ qua)."""
    now = iter(range(1_000, 10_000))
    monkeypatch.setattr(listening_module.time, "time", lambda: float(next(now)))


def _state(listening: Listening) -> dict:
    return listening.get("b")


def test_an_edited_note_beats_the_other_devices_older_copy(tmp_path: Path) -> None:
    listening = Listening(tmp_path / "listening.json")
    mark = dict(listening.add_bookmark("b", 2, 30.0))
    other = {"bookmarks": [dict(mark)], "chapters": {}}  # máy kia có bản trước khi sửa
    listening.update_bookmark("b", mark["id"], "đoạn hay")
    mine = _state(listening)
    edited = mine["bookmarks"][0]
    assert edited["at"] > mark["at"] and edited["createdAt"] == mark["createdAt"]
    assert merge_states(mine, other)["bookmarks"][0]["note"] == "đoạn hay"
    assert merge_states(other, mine)["bookmarks"][0]["note"] == "đoạn hay", "máy kia nhận bản vừa sửa"


def test_undoing_a_delete_beats_the_tombstone_already_on_the_other_device(tmp_path: Path) -> None:
    listening = Listening(tmp_path / "listening.json")
    mark = dict(listening.add_bookmark("b", 2, 30.0, "ghi chú"))
    listening.delete_bookmark("b", mark["id"])
    other = merge_states({"bookmarks": [dict(mark)], "chapters": {}}, _state(listening))  # lệnh xoá đã sang máy kia
    assert other["bookmarks"] == [] and mark["id"] in other["deleted"]
    restored = listening.restore_bookmark("b", {**mark})
    assert restored["createdAt"] == mark["createdAt"], "Hoàn tác giữ lúc đặt dấu gốc, không thành 'vừa xong'"
    mine = merge_states(_state(listening), other)
    assert [item["id"] for item in mine["bookmarks"]] == [mark["id"]]
    theirs = merge_states(other, _state(listening))
    assert [item["id"] for item in theirs["bookmarks"]] == [mark["id"]], "máy kia cũng có lại dấu"


def test_a_tombstone_still_removes_an_unchanged_mark_and_the_later_delete_wins(tmp_path: Path) -> None:
    mark = {"id": "m1", "chapterId": 1, "seconds": 5.0, "note": "", "at": 100.0, "createdAt": 100.0}
    ours = {"bookmarks": [mark], "chapters": {}, "deleted": {"m1": 50.0}}
    theirs = {"bookmarks": [], "chapters": {}, "deleted": {"m1": 200.0}}
    merged = merge_states(ours, theirs)
    assert merged["bookmarks"] == [] and merged["deleted"]["m1"] == 200.0
    assert merge_states(theirs, {"bookmarks": [], "deleted": {"m1": 50.0}})["deleted"]["m1"] == 200.0

