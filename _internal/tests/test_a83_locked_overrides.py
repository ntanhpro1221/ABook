"""Soát a83 B2 + B7 (phần trong file khoá listener_overrides.py): đọc-sửa-ghi không được ghi đè mất yêu cầu cũ khi overrides.json tạm không đọc
được, và "Thu lại cả chương" ghi MỘT lần."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from abook import listener_overrides as lo


def _five(tmp: Path) -> None:
    for index in range(5):
        lo.request_pronunciation(tmp, f"Tên{index}", "Tê-nơ", now=1000.0 + index)


def test_a_transient_read_error_never_drops_the_earlier_requests(monkeypatch, tmp_path: Path) -> None:
    _five(tmp_path)
    monkeypatch.setattr(lo, "READ_FOR_UPDATE_PAUSE_SECONDS", 0)
    real = Path.read_text

    def locked(self, *args, **kwargs):
        if self.name == "overrides.json":
            raise PermissionError(32, "The process cannot access the file because it is being used by another process")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", locked)
    with pytest.raises(lo.OverridesUnreadable):
        lo.request_pronunciation(tmp_path, "Mới", "Mơ-ới", now=2000.0)
    monkeypatch.undo()
    assert len(lo.read_overrides(tmp_path)["pronunciations"]) == 5


def test_a_brief_read_error_is_retried_and_the_request_lands_next_to_the_old_ones(monkeypatch, tmp_path: Path) -> None:
    _five(tmp_path)
    monkeypatch.setattr(lo, "READ_FOR_UPDATE_PAUSE_SECONDS", 0)
    real = Path.read_text
    state = {"n": 0}

    def flaky(self, *args, **kwargs):
        if self.name == "overrides.json" and state["n"] == 0:
            state["n"] = 1
            raise PermissionError(32, "busy")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", flaky)
    lo.request_pronunciation(tmp_path, "Mới", "Mơ-ới", now=2000.0)
    monkeypatch.undo()
    assert len(lo.read_overrides(tmp_path)["pronunciations"]) == 6


def test_no_file_and_a_hand_broken_file_still_start_from_nothing(tmp_path: Path) -> None:
    lo.request_pronunciation(tmp_path, "A", "ê", now=1.0)
    (tmp_path / lo.OVERRIDES_FILE).write_text("{ hỏng", encoding="utf-8")
    lo.request_pronunciation(tmp_path, "B", "bê", now=2.0)
    assert list(lo.read_overrides(tmp_path)["pronunciations"]) == ["b"]


def test_a_whole_chapter_retake_is_one_read_and_one_write(monkeypatch, tmp_path: Path) -> None:
    writes = []
    real = lo._write
    monkeypatch.setattr(lo, "_write", lambda root, data: (writes.append(1), real(root, data))[1])
    lines = [(f"c1s{index}", f"sha-{index}") for index in range(1000)]
    started = time.perf_counter()
    lo.request_retakes(tmp_path, lines, now=5.0)
    assert time.perf_counter() - started < 1.0
    assert len(writes) == 1
    retakes = lo.read_overrides(tmp_path)["retakes"]
    assert len(retakes) == 1000 and {entry["requested_at"] for entry in retakes.values()} == {5.0}
