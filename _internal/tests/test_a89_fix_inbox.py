"""a89 T3: hộp thư thay đổi từ điện thoại - "Bỏ qua" không mất hẳn (khay đã bỏ qua + khôi phục), "Áp dụng" nói rõ việc nào bị loại."""
from __future__ import annotations

from pathlib import Path

from abook.webui import edits_inbox
from tests.test_edits_inbox import DEVICE, FOLDABLE, _overrides, package, project  # noqa: F401 - fixture `project`
from tests import book_edits_fixtures as shared


def _inbox(tmp_path: Path, project: Path, wishes: dict) -> None:
    edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, {"wishes": wishes}), now=1000.0)


def test_a_skipped_item_waits_in_the_tray_and_can_be_restored(tmp_path: Path, project: Path) -> None:
    _inbox(tmp_path, project, shared.WISHES)
    first = edits_inbox.view(project)["devices"][0]["items"][0]
    assert edits_inbox.skip(project, DEVICE, [first["id"]]) == {"removed": 1, "left": 5}
    view = edits_inbox.view(project)
    assert view["waiting"] == 5
    assert [row["id"] for row in view["skipped"][0]["items"]] == [first["id"]] and view["skipped"][0]["name"] == "Pixel"
    assert edits_inbox.restore(project, DEVICE, [first["id"]]) == {"restored": 1, "left": 0}
    again = edits_inbox.view(project)
    assert again["waiting"] == 6 and again["skipped"] == []
    assert first["id"] in [row["id"] for row in again["devices"][0]["items"]]


def test_skipping_everything_then_restoring_everything_brings_the_device_back(tmp_path: Path, project: Path) -> None:
    _inbox(tmp_path, project, shared.WISHES)
    assert edits_inbox.skip(project, DEVICE, None) == {"removed": 6, "left": 0}
    view = edits_inbox.view(project)
    assert view["devices"] == [] and len(view["skipped"][0]["items"]) == 6
    assert edits_inbox.restore(project, DEVICE, None) == {"restored": 6, "left": 0}
    assert edits_inbox.view(project)["waiting"] == 6
    assert edits_inbox.restore(project, DEVICE, None) == {"restored": 0, "left": 0}


def test_restoring_keeps_the_newer_item_the_inbox_already_has(tmp_path: Path, project: Path) -> None:
    again = {"pronunciations": {"hailkes": {"requested_at": 1759400099.0, "spoken_form": "Hai-ơ-kơ", "surface": "Hailkes"}}}
    _inbox(tmp_path, project, shared.WISHES)
    edits_inbox.skip(project, DEVICE, None)
    _inbox(tmp_path, project, again)
    edits_inbox.restore(project, DEVICE, None)
    wishes = edits_inbox._load(project)["devices"][DEVICE]["wishes"]
    assert wishes["pronunciations"]["hailkes"]["spoken_form"] == "Hai-ơ-kơ"
    assert edits_inbox.view(project)["waiting"] == 6


def test_the_tray_is_bounded(tmp_path: Path, project: Path, monkeypatch) -> None:
    monkeypatch.setattr(edits_inbox, "MAX_SKIPPED", 2)
    _inbox(tmp_path, project, shared.WISHES)
    edits_inbox.skip(project, DEVICE, None)
    assert len(edits_inbox.view(project)["skipped"][0]["items"]) == 2


def test_applying_names_the_items_that_could_not_be_applied(tmp_path: Path, project: Path) -> None:
    stale = {"retakes": {"c9_s0001_zzzzzz": {"requested_at": 1759400005.0, "text_sha256": "0" * 64}}}
    _inbox(tmp_path, project, stale)
    done = edits_inbox.apply(project, DEVICE, None, now=2000.0)
    assert (done["requests"], done["skipped"]) == (0, 1)
    assert len(done["dropped"]) == 1 and done["dropped"][0]["label"], done


def test_applying_something_that_fits_drops_nothing(tmp_path: Path, project: Path) -> None:
    _inbox(tmp_path, project, FOLDABLE)
    done = edits_inbox.apply(project, DEVICE, None, now=2000.0)
    assert done["requests"] == 3 and done["dropped"] == []
    assert _overrides(project).get("pronunciations")
