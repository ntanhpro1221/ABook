"""Sách đã xong không tự chạy lại: sửa của người nghe ghi SAU lần chạy cuối phải hiện thành nút "Áp dụng N thay đổi"
(soát UX 29-09: mọi thẻ báo "chờ lần chạy tới" mà trang dự án "Hoàn tất" không có nút chạy nào)."""
from __future__ import annotations

import json
from pathlib import Path

from abook.listener_overrides import overrides_path, request_pronunciation, request_speakers
from abook.webui.store import pending_changes


def test_only_requests_written_after_the_last_run_are_pending(tmp_path: Path) -> None:
    request_pronunciation(tmp_path, "Hailkes", "Hên-cơ", now=100.0)
    request_speakers(tmp_path, [("s1", "sha1"), ("s2", "sha2")], "LUCIEN", now=300.0)
    # Hai câu gán trong MỘT lần bấm (cả nhóm vai phụ) là một thay đổi (soát UX a6 01-10: "Gộp vào…" ba trăm câu không
    # được thành "Áp dụng 300 thay đổi").
    assert pending_changes(tmp_path, since=50.0) == 2
    assert pending_changes(tmp_path, since=200.0) == 1, "cách đọc tên đã áp ở lần chạy lúc 200"
    assert pending_changes(tmp_path, since=400.0) == 0


def test_no_file_or_a_broken_entry_is_not_a_change(tmp_path: Path) -> None:
    assert pending_changes(tmp_path, since=0.0) == 0
    overrides_path(tmp_path).write_text(json.dumps({"speakers": {"s1": "LUCIEN", "s2": {"requested_at": "x"}},
                                                     "voices": {"A": {"requested_at": 9.0}}}), encoding="utf-8")
    assert pending_changes(tmp_path, since=1.0) == 1


def test_a_run_that_found_nothing_to_redo_still_clears_the_button(tmp_path: Path) -> None:
    """"Giữ nguyên" không làm dây chuyền ghi gì vào sổ, nên chỉ `book.updated_at` thì nút "Áp dụng" không bao giờ tắt:
    Studio ghi mốc khởi động lượt chạy, và lượt ấy áp mọi yêu cầu ghi trước mốc."""
    from abook.webui.store import changes_since, mark_run_started

    request_pronunciation(tmp_path, "Arcanist", "A-rờ-ca-nít", now=500.0)
    assert changes_since(tmp_path, 100.0) == 100.0, "chưa chạy lần nào: chỉ còn mốc sổ"
    assert pending_changes(tmp_path, changes_since(tmp_path, 100.0)) == 1
    mark_run_started(tmp_path, 600.0)
    assert changes_since(tmp_path, 100.0) == 600.0
    assert pending_changes(tmp_path, changes_since(tmp_path, 100.0)) == 0
    request_pronunciation(tmp_path, "Hailkes", "Hên-cơ", now=700.0)
    assert pending_changes(tmp_path, changes_since(tmp_path, 100.0)) == 1, "ghi sau lượt chạy: lại chờ"


def test_keeping_what_the_book_already_has_is_not_a_change(tmp_path: Path) -> None:
    """Soát UX 29-09: "Giữ Banus", "Đúng rồi, giữ Na-xờ-đên", "Giữ vai phụ" đẩy số trên nút "Áp dụng N thay đổi" từ 38 lên 47
    trong khi chỉ một lần bấm đổi thật. Yêu cầu bằng đúng thứ sách đang có thì không phải thay đổi chờ áp."""
    import sqlite3

    db = sqlite3.connect(tmp_path / "project.sqlite3")
    db.executescript(
        """
        CREATE TABLE segments (stable_id TEXT, speaker TEXT);
        CREATE TABLE pronunciations (surface TEXT, spoken_form TEXT);
        INSERT INTO segments VALUES ('s1', 'Banus'), ('s2', 'Banus'), ('s3', 'NPC_LOCAL::c1::r1::trộm');
        INSERT INTO pronunciations VALUES ('Naseden', 'Na-xờ-đên'), ('Maltimus', 'Man-ti-mu');
        """
    )
    db.commit()
    db.close()
    request_speakers(tmp_path, [("s1", "a"), ("s2", "b")], "BANUS", now=10.0)
    request_speakers(tmp_path, [("s3", "c")], "NPC_LOCAL::c1::r1::trộm", now=10.0)
    request_pronunciation(tmp_path, "Naseden", "Na-xờ-đên", now=10.0)
    assert pending_changes(tmp_path, since=1.0) == 0, "toàn giữ nguyên"

    request_pronunciation(tmp_path, "Maltimus", "Man-ti-mút", now=20.0)
    request_speakers(tmp_path, [("s2", "b")], "ALI", now=20.0)
    assert pending_changes(tmp_path, since=1.0) == 2, "đổi cách đọc Maltimus + câu s2 sang Ali"
