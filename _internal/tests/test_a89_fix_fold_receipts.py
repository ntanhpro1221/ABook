"""a89 V4: ghi biên nhận một lần trước cả nhóm; overrides giữ dấu hoàn tất cùng yêu cầu."""
from __future__ import annotations

import json

from abook import listener_overrides
from abook.webui import book_wishes
from tests.test_book_wishes import _line, _producer


def test_a_retake_group_writes_its_receipts_once_and_requests_once(tmp_path, monkeypatch):
    project, db = _producer(tmp_path)
    with db.connect() as conn:
        ids = [row[0] for row in conn.execute("SELECT stable_id FROM segments WHERE stable_id IS NOT NULL ORDER BY id")]
    assert len(ids) >= 3
    wishes = {"retakes": {}}
    for stable_id in ids:
        wishes["retakes"][stable_id] = {"requested_at": 50.0, "text_sha256": _line(db, stable_id)[1], "operation_id": "a" * 32}
    writes = []
    real = book_wishes.atomic_write_json
    monkeypatch.setattr(book_wishes, "atomic_write_json",
                        lambda path, data, **kw: (writes.append(path.name), real(path, data, **kw))[1])
    request_groups = []
    real_request = listener_overrides.request_retakes
    def request(project, members, **kwargs):
        request_groups.append((members, kwargs))
        return real_request(project, members, **kwargs)
    monkeypatch.setattr(listener_overrides, "request_retakes", request)
    report = book_wishes.fold(project, wishes, now=100.0)
    assert report["requests"] == len(ids)
    assert writes.count("retake_receipts.json") == 1
    assert set(listener_overrides.read_overrides(project)["retakes"]) == set(ids)
    receipts = json.loads((project / "retake_receipts.json").read_text(encoding="utf-8"))
    assert len(request_groups) == 1
    assert request_groups[0][1]["operation_id"] == "a" * 32
    assert set(receipts["a" * 32]["lines"]) == set(ids)
    assert set(listener_overrides.read_overrides(project)["retake_operations"]["a" * 32]) == set(ids)
    assert book_wishes.fold(project, wishes, now=200.0)["requests"] == 0, "đã làm xong: gấp lại không làm gì"
