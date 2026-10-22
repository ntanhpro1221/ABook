"""Soát a83 B3: mọi đường ghi overrides.json (nút Studio dưới `project_write_lock`, sửa từ điện thoại `receive`, "Áp dụng" hộp thư `apply`)
dùng MỘT khoá, nên hai lần ghi sát nhau không nuốt nhau."""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from abook import listener_overrides as lo
from abook.io_utils import project_write_lock
from abook.webui import book_wishes, edits_inbox
from tests import book_edits_fixtures as shared
from tests import test_edits_inbox as T
from tests.test_bookfile_music import _plan


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    producer = tmp_path / "may_tinh"
    producer.mkdir()
    folder = shared.make_base_project(producer)
    _plan(folder)
    return folder


def _slow_studio_click(monkeypatch, project: Path):
    """Một lần bấm Studio (như post_pronunciation: khoá sách rồi request_pronunciation) với `_write` chậm 0,4 giây để thấy cửa sổ đọc-sửa-ghi."""
    real = lo._write

    def slow(root, data):
        if threading.current_thread().name == "studio":
            time.sleep(0.4)
        real(root, data)

    monkeypatch.setattr(lo, "_write", slow)

    def click():
        with project_write_lock(project):
            lo.request_pronunciation(project, "Zorba", "Dờ-oóc-ba", now=time.time())

    thread = threading.Thread(target=click, name="studio")
    thread.start()
    time.sleep(0.1)
    return thread


def test_phone_edits_and_a_studio_click_both_survive(monkeypatch, tmp_path: Path, project: Path) -> None:
    thread = _slow_studio_click(monkeypatch, project)
    report = edits_inbox.receive(project, T.DEVICE, "B", T.package(tmp_path, {"wishes": T.ONLY_HAILKES}), may_produce=True, now=T.HAILKES_AT + 600)
    thread.join()
    assert report["requests"] == 1
    assert {"zorba", "hailkes"} <= {key.lower() for key in lo.read_overrides(project).get("pronunciations", {})}


def test_apply_from_the_inbox_and_a_studio_click_both_survive(monkeypatch, tmp_path: Path, project: Path) -> None:
    edits_inbox.receive(project, T.DEVICE, "B", T.package(tmp_path, {"wishes": T.ONLY_HAILKES}), now=T.HAILKES_AT + 30)  # chưa được điều khiển: vào hộp thư
    thread = _slow_studio_click(monkeypatch, project)
    edits_inbox.apply(project, T.DEVICE, None, now=T.HAILKES_AT + 600)
    thread.join()
    assert {"zorba", "hailkes"} <= {key.lower() for key in lo.read_overrides(project).get("pronunciations", {})}


def test_fold_alone_waits_for_the_studio_click(monkeypatch, project: Path) -> None:
    thread = _slow_studio_click(monkeypatch, project)
    book_wishes.fold(project, T.ONLY_HAILKES, now=T.HAILKES_AT + 600)
    thread.join()
    assert {"zorba", "hailkes"} <= {key.lower() for key in lo.read_overrides(project).get("pronunciations", {})}
