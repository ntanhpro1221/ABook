"""Soát a83 B10: người dùng bấm Hoàn tác SAU lúc dây chuyền đọc overrides.json mà TRƯỚC lúc nó áp yêu cầu ấy: yêu cầu đã rút không được áp (UI đã báo
"Đã hoàn tác")."""
from __future__ import annotations

from pathlib import Path

from abook import pipeline as pipeline_module
from abook.listener_overrides import read_overrides, request_pronunciation, withdraw_requests
from tests.test_listener_overrides import _Pipeline, _book, _statuses


def test_a_request_withdrawn_after_the_file_was_read_is_not_applied(tmp_path: Path, monkeypatch) -> None:
    paths, db = _book(tmp_path)
    db.finalize_casting()
    request_pronunciation(paths.root, "Hailkes", "Hên-khơ", now=5.0)
    real = pipeline_module.read_overrides
    calls = {"n": 0}

    def read_then_user_withdraws(root):
        data = real(root)
        calls["n"] += 1
        if calls["n"] == 1:  # đúng lần đọc ảnh chụp của vòng áp; ngay sau đó người dùng bấm Hoàn tác
            withdraw_requests(root, "pronunciations", ["hailkes"], 5.0)
        return data

    monkeypatch.setattr(pipeline_module, "read_overrides", read_then_user_withdraws)
    pipeline = _Pipeline(paths, db)
    assert pipeline._apply_listener_overrides() == set()
    assert set(_statuses(db).values()) == {"verified"}, "không câu nào bị đặt lại"
    assert "pronunciations" not in read_overrides(paths.root) or not read_overrides(paths.root)["pronunciations"]


def test_an_untouched_request_is_still_applied(tmp_path: Path) -> None:
    paths, db = _book(tmp_path)
    db.finalize_casting()
    request_pronunciation(paths.root, "Hailkes", "Hên-khơ", now=5.0)
    assert _Pipeline(paths, db)._apply_listener_overrides() == {1, 3}
