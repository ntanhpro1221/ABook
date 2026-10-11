"""Danh sách máy tính đã ghép (remote_books.Computers, `computers.json`) không bao giờ mất im lặng trên Windows (uxfix28 E).

Windows: đổi tên đè lên file đang có người đọc hỏng bằng PermissionError; đọc file đang bị ghi cũng có thể hỏng như vậy. Trước đây
ghi không thử lại (test_unpair_both_sides hỏng 1/8 lần), và đọc nuốt MỌI lỗi thành "chưa ghép máy nào" - lần ghi kế tiếp xoá sạch
danh sách. JSON hỏng thì giữ bản hỏng bên cạnh và báo người dùng, không ghi đè lên nó.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from abook.webui import remote_books
from abook.webui.remote_books import Computers

PAIRED = {"computers": {"m1": {"name": "Máy phòng khách", "host": "192.168.1.20", "port": 47630, "token": "t"}}}


def _paired(tmp_path: Path) -> Computers:
    path = tmp_path / "computers.json"
    path.write_bytes(json.dumps(PAIRED).encode("utf-8"))
    return Computers(path)


def _blocked_reads(monkeypatch, path: Path, times: int) -> list[int]:
    """Đọc `path` hỏng PermissionError `times` lần đầu (như lúc tiến trình khác đang đổi tên đè lên nó)."""
    count = [0]
    for name in ("read_text", "read_bytes"):
        original = getattr(Path, name)

        def blocked(self, *args, _original=original, **kwargs):
            if Path(self) == path and count[0] < times:
                count[0] += 1
                raise PermissionError(13, "Access is denied", str(path))
            return _original(self, *args, **kwargs)

        monkeypatch.setattr(Path, name, blocked)
    return count


def test_writing_survives_a_reader_holding_the_file_for_a_moment(tmp_path: Path, monkeypatch) -> None:
    computers = _paired(tmp_path)
    original, failures = os.replace, [0]

    def busy(source, target, *args, **kwargs):
        if Path(target).name == "computers.json" and failures[0] < 2:
            failures[0] += 1
            raise PermissionError(13, "Access is denied", str(target))
        return original(source, target, *args, **kwargs)

    monkeypatch.setattr(os, "replace", busy)
    computers.note("m1", lastSeen=5.0)
    assert failures[0] == 2
    assert computers.get("m1")["lastSeen"] == 5.0
    assert not list(tmp_path.glob("computers.json.*")) and not (tmp_path / "computers.tmp").exists(), "không để file tạm"


def test_a_read_blocked_for_a_moment_never_wipes_the_paired_computers(tmp_path: Path, monkeypatch) -> None:
    computers = _paired(tmp_path)
    _blocked_reads(monkeypatch, computers.path, 2)
    assert len(computers.own_id()) == 16, "đọc lại được sau một thoáng"
    assert json.loads(computers.path.read_bytes())["computers"] == PAIRED["computers"], "máy đã ghép còn nguyên"


def test_a_read_that_keeps_failing_raises_and_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    computers = _paired(tmp_path)
    before = computers.path.read_bytes()
    _blocked_reads(monkeypatch, computers.path, 10**6)
    with pytest.raises(PermissionError):
        computers.own_id()
    monkeypatch.undo()
    assert computers.path.read_bytes() == before, "không ghi đè danh sách đọc không được"


def test_a_broken_file_is_kept_aside_and_the_listener_is_told(tmp_path: Path) -> None:
    path = tmp_path / "computers.json"
    path.write_bytes(b'{"computers": {"m1": {"name": "M')  # ghi dở
    computers = Computers(path)
    assert computers.list() == []
    kept = list(tmp_path.glob("computers.json.hong-*"))
    assert len(kept) == 1 and kept[0].read_bytes() == b'{"computers": {"m1": {"name": "M'
    assert computers.broken == kept[0].name
    computers.own_id()  # ghi mới không đụng bản hỏng
    assert kept[0].exists() and json.loads(path.read_bytes())["computers"] == {}
    assert "phải ghép lại" in remote_books.broken_note(computers.broken)
    assert remote_books.broken_note(None) == ""
