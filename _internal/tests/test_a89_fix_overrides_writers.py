"""a89 V5: cách đọc dùng chung và gộp xưởng từ file dự án ghi overrides.json dưới khoá ghi của dự án + guard_overrides như nút Studio."""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from abook import listener_overrides as lo
from abook.io_utils import project_write_lock
from abook.webui import notices, shared_readings, workshop_merge
from abook.webui.reviews import Reviews
from tests.test_a83_unreadable_overrides import _lock_out
from tests.test_listener_speakers import _book

ENTRIES = [{"surface": "Zorba", "spokenForm": "Dờ-oóc-ba"}]


def test_shared_readings_apply_refuses_while_overrides_are_locked(monkeypatch, tmp_path: Path) -> None:
    paths, _db = _book(tmp_path)
    for index in range(3):
        lo.request_pronunciation(paths.root, f"Tên{index}", "Tê-nơ", now=1000.0 + index)
    before = (paths.root / lo.OVERRIDES_FILE).read_bytes()
    _lock_out(monkeypatch)
    with pytest.raises(notices.Unreadable):
        shared_readings.apply(paths.root, ENTRIES, now=2000.0)
    monkeypatch.undo()
    assert (paths.root / lo.OVERRIDES_FILE).read_bytes() == before, "yêu cầu cũ phải còn nguyên"


def test_shared_readings_apply_waits_for_the_project_write_lock(tmp_path: Path) -> None:
    paths, _db = _book(tmp_path)
    done = threading.Event()
    held = threading.Event()
    release = threading.Event()

    def other_writer() -> None:
        with project_write_lock(paths.root):
            held.set()
            release.wait(5)

    thread = threading.Thread(target=other_writer)
    thread.start()
    held.wait(5)
    worker = threading.Thread(target=lambda: (shared_readings.apply(paths.root, ENTRIES, now=2000.0), done.set()))
    worker.start()
    assert not done.wait(0.3), "đang có người giữ khoá ghi của dự án: apply phải đợi"
    release.set()
    thread.join()
    worker.join()
    assert done.is_set() and (paths.root / lo.OVERRIDES_FILE).is_file()


def test_workshop_merge_refuses_while_overrides_are_locked(monkeypatch, tmp_path: Path) -> None:
    paths, _db = _book(tmp_path)
    lo.request_pronunciation(paths.root, "Cũ", "Cu", now=1000.0)
    before = (paths.root / lo.OVERRIDES_FILE).read_bytes()
    theirs = {"pronunciations": {"zorba": {"surface": "Zorba", "spoken_form": "Dờ-oóc-ba", "requested_at": 5000.0}}}
    files = {lo.OVERRIDES_FILE: json.dumps(theirs).encode("utf-8")}
    _lock_out(monkeypatch)
    with pytest.raises(notices.Unreadable):
        workshop_merge.merge_workshop(paths.root, files.get, Reviews(), 9000.0)
    monkeypatch.undo()
    assert (paths.root / lo.OVERRIDES_FILE).read_bytes() == before


def test_a_cancelled_retake_does_not_come_back_from_the_other_machines_file(tmp_path: Path) -> None:
    from abook.webui import cancelled

    paths, _db = _book(tmp_path)
    other = tmp_path / "may_kia"
    other.mkdir()
    lo.request_retake(paths.root, "c1s1", "sha-c1s1", now=100.0)
    lo.request_retake(other, "c1s1", "sha-c1s1", now=100.0)  # máy kia vẫn giữ yêu cầu cũ (file chép trước khi máy này đổi ý)
    cancelled.cancel_retake(paths.root, "c1s1", now=200.0)
    assert (lo.read_overrides(paths.root).get("retakes") or {}) == {}
    report = workshop_merge.merge_workshop(
        paths.root, lambda name: (other / name).read_bytes() if (other / name).is_file() else None, Reviews(), 3000.0)
    assert report == {"merged": 0, "kept": 0}
    assert (lo.read_overrides(paths.root).get("retakes") or {}) == {}, "yêu cầu đã rút không sống lại"
    lo.request_retake(paths.root, "c1s1", "sha-c1s1", now=500.0)  # đặt lại SAU khi rút: sống
    workshop_merge.merge_workshop(
        paths.root, lambda name: (other / name).read_bytes() if (other / name).is_file() else None, Reviews(), 3000.0)
    assert lo.read_overrides(paths.root)["retakes"]["c1s1"]["requested_at"] == 500.0


def test_a_withdrawn_edit_is_buried_on_the_machine_that_still_has_it(tmp_path: Path) -> None:
    from abook.webui import cancelled

    paths, _db = _book(tmp_path)
    here, there = tmp_path / "a", tmp_path / "b"
    here.mkdir()
    there.mkdir()
    lo.request_pronunciation(here, "Zorba", "Dờ-oóc-ba", now=100.0)
    lo.request_pronunciation(there, "Zorba", "Dờ-oóc-ba", now=100.0)
    assert cancelled.withdraw_requests(there, "pronunciations", [lo.surface_key("Zorba")], 100.0, now=150.0)
    workshop_merge.merge_workshop(
        here, lambda name: (there / name).read_bytes() if (there / name).is_file() else None, Reviews(), 3000.0)
    assert (lo.read_overrides(here).get("pronunciations") or {}) == {}
    assert cancelled.read(here)["pronunciations:" + lo.surface_key("Zorba")]["requested_at"] == 100.0
