"""T2: chụp yêu cầu, rút rồi áp; không đổi sách, biên nhận hay cảnh báo."""
from pathlib import Path
from unittest.mock import Mock

import pytest

from abook import listener_overrides as lo, pipeline as pipeline_module
from abook.config import build_settings
from abook.webui import cancelled
from tests.test_listener_overrides import _Pipeline, _book, _events, _statuses


def _ask(root: Path, section: str, at: float) -> str:
    if section == "pronunciations":
        lo.request_pronunciation(root, "Hailkes", "Hên-khơ", now=at)
    elif section == "lines":
        lo.request_line(root, "c1s0", "t10", emotion="sad", now=at)
    elif section == "speakers":
        lo.request_speaker(root, "c1s0", "t10", "Mai", now=at)
    elif section == "voices":
        lo.request_voice(root, "Mai", gender="female", now=at)
    else:
        lo.request_retake(root, "c1s0", "t10", now=at)
    return next(iter(lo.read_overrides(root)[section]))


@pytest.mark.parametrize("section", ["pronunciations", "lines", "speakers", "voices", "retakes"])
@pytest.mark.parametrize("restore_previous", [False, True])
def test_withdrawn_snapshot_is_neither_applied_nor_acknowledged(tmp_path, monkeypatch, section, restore_previous):
    paths, db = _book(tmp_path)
    db.finalize_casting()
    if restore_previous:
        _ask(paths.root, section, 3.0)
    key = _ask(paths.root, section, 5.0)
    previous = lo.read_overrides(paths.root)[section][key].get("replaced")
    before = [dict(row) for row in db.list_segments()]
    real_read = lo.read_overrides
    captured = []

    def read_then_withdraw(root):
        snapshot = real_read(root)
        if not captured:
            captured.append(snapshot)
            assert cancelled.withdraw_requests(root, section, [key], 5.0, now=6.0) == [key]
        return snapshot

    monkeypatch.setattr(pipeline_module, "read_overrides", read_then_withdraw)
    apply = Mock(side_effect=AssertionError("yêu cầu đã rút không được áp"))
    method = {"pronunciations": "pronunciation", "lines": "line", "speakers": "speaker",
              "voices": "voice", "retakes": "retake"}[section]
    monkeypatch.setattr(db, "apply_listener_" + method, apply)
    pipeline = _Pipeline(paths, db)
    pipeline.settings = build_settings()
    assert pipeline._apply_listener_overrides() == set()
    apply.assert_not_called()
    assert db.listener_receipts() == {}, "đã rút trước lúc áp: không biên nhận đã áp"
    assert [dict(row) for row in db.list_segments()] == before
    assert _events(db, "LISTENER_OVERRIDE_REJECTED") == []
    if previous is not None:
        assert real_read(paths.root)[section][key] == previous
    else:
        assert key not in real_read(paths.root).get(section, {})


@pytest.mark.parametrize("invalid_second", [False, True])
def test_withdrawal_between_requests_is_read_even_when_the_file_stamp_is_stale(tmp_path, monkeypatch, invalid_second):
    paths, db = _book(tmp_path)
    db.finalize_casting()
    lo.request_retake(paths.root, "c1s0", "t10", now=5.0)
    lo.request_retake(paths.root, "c1s1", "stale" if invalid_second else "t11", now=5.0)
    # Mô phỏng stat còn cũ: quyết định áp phải dựa trên yêu cầu đọc lại từ đĩa.
    monkeypatch.setattr(pipeline_module, "file_stamp", lambda _path: (1, 1, 1), raising=False)
    real_apply = db.apply_listener_retake
    calls = []

    def apply_then_withdraw(**kwargs):
        calls.append(kwargs["stable_id"])
        result = real_apply(**kwargs)
        if kwargs["stable_id"] == "c1s0":
            cancelled.withdraw_requests(paths.root, "retakes", ["c1s1"], 5.0, now=6.0)
        return result

    monkeypatch.setattr(db, "apply_listener_retake", apply_then_withdraw)
    assert _Pipeline(paths, db)._apply_listener_overrides() == {1}
    assert calls == ["c1s0"]
    assert _statuses(db)["c1s1"] == "verified"
    assert set(db.listener_receipts()) == {("retakes", "c1s0")}
    assert _events(db, "LISTENER_OVERRIDE_REJECTED") == []


def test_untouched_requests_keep_their_order_seeds_and_receipts(tmp_path, monkeypatch):
    paths, db = _book(tmp_path)
    db.finalize_casting()
    lo.request_retakes(paths.root, [("c1s1", "t11"), ("c1s0", "t10")], now=5.0)
    saved = lo.overrides_path(paths.root).read_bytes()
    real_apply = db.apply_listener_retake
    calls = []

    def apply(**kwargs):
        calls.append(kwargs)
        return real_apply(**kwargs)

    monkeypatch.setattr(db, "apply_listener_retake", apply)
    pipeline = _Pipeline(paths, db)
    assert pipeline._apply_listener_overrides() == {1}
    assert calls == [{"stable_id": sid, "text_sha256": sha, "requested_at": 5.0}
                     for sid, sha in [("c1s0", "t10"), ("c1s1", "t11")]]
    assert set(db.listener_receipts()) == {("retakes", "c1s0"), ("retakes", "c1s1")}
    rows = {row["stable_id"]: dict(row) for row in db.list_segments()}
    assert [rows[sid]["listener_retakes"] for sid in ("c1s0", "c1s1")] == [1, 1]
    assert pipeline._apply_listener_overrides() == set()
    assert {row["stable_id"]: dict(row) for row in db.list_segments()} == rows
    assert lo.overrides_path(paths.root).read_bytes() == saved
