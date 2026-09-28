"""Sách đã xong không tự chạy lại: sửa của người nghe ghi SAU lần chạy cuối phải hiện thành nút "Áp dụng N thay đổi"
(soát UX 29-09: mọi thẻ báo "chờ lần chạy tới" mà trang dự án "Hoàn tất" không có nút chạy nào)."""
from __future__ import annotations

import json
from pathlib import Path

from ebook_reader.listener_overrides import overrides_path, request_pronunciation, request_speakers
from ebook_reader.webui.store import pending_changes


def test_only_requests_written_after_the_last_run_are_pending(tmp_path: Path) -> None:
    request_pronunciation(tmp_path, "Hailkes", "Hên-cơ", now=100.0)
    request_speakers(tmp_path, [("s1", "sha1"), ("s2", "sha2")], "LUCIEN", now=300.0)
    assert pending_changes(tmp_path, since=50.0) == 3
    assert pending_changes(tmp_path, since=200.0) == 2, "cách đọc tên đã áp ở lần chạy lúc 200"
    assert pending_changes(tmp_path, since=400.0) == 0


def test_no_file_or_a_broken_entry_is_not_a_change(tmp_path: Path) -> None:
    assert pending_changes(tmp_path, since=0.0) == 0
    overrides_path(tmp_path).write_text(json.dumps({"speakers": {"s1": "LUCIEN", "s2": {"requested_at": "x"}},
                                                     "voices": {"A": {"requested_at": 9.0}}}), encoding="utf-8")
    assert pending_changes(tmp_path, since=1.0) == 1
