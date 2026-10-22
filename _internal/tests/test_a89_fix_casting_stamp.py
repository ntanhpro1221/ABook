"""a89 T7: dây chuyền áp một yêu cầu chỉ ghi sổ + biên nhận (không đụng overrides.json) - dấu của tab Kịch bản phải đổi, để thẻ "đang chờ" không ở lại."""
from __future__ import annotations

from pathlib import Path

from abook import listener_overrides as lo
from abook.webui.casting_review import casting_stamp
from tests.test_listener_speakers import _book


def test_the_stamp_moves_when_the_pipeline_records_a_receipt_without_touching_overrides(tmp_path: Path) -> None:
    paths, db = _book(tmp_path)
    assert casting_stamp(paths.root) == 0
    lo.request_speakers(paths.root, [("c1s2", "sha-c1s2")], "NATASHA", now=100.0)
    requested = casting_stamp(paths.root)
    assert requested > 0
    mtime = (paths.root / "overrides.json").stat().st_mtime_ns
    db.record_listener_receipt("speakers", "c1s2", 100.0, "x")
    applied = casting_stamp(paths.root)
    assert (paths.root / "overrides.json").stat().st_mtime_ns == mtime, "dây chuyền không ghi overrides.json"
    assert applied != requested and 0 < applied < 2**53
    db.record_listener_receipt("speakers", "c1s3", 101.0, "y")
    assert casting_stamp(paths.root) not in (requested, applied)


def test_the_stamp_is_steady_while_nothing_new_happens(tmp_path: Path) -> None:
    paths, db = _book(tmp_path)
    db.record_listener_receipt("speakers", "c1s2", 100.0, "x")
    assert casting_stamp(paths.root) == casting_stamp(paths.root)
