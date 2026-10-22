"""Biên nhận "đã áp" cho yêu cầu của người nghe: dây chuyền ghi vào sổ sau mỗi yêu cầu đã xét, và nút "Áp dụng" đếm theo đó.

Trước đây `store.changes_since` suy "đã áp" từ `max(book.updated_at, lần Studio khởi động)`: yêu cầu lưu trong lúc thu chương
cuối (dây chuyền chỉ đọc yêu cầu TRƯỚC mỗi chương), hay ở khe giữa READY và recovery (server ghi mốc khởi động sau READY), bị
coi là đã áp dù dây chuyền chưa đọc nó - bộ đếm về 0, mất nút.
"""

from __future__ import annotations

from pathlib import Path

from abook.database import ProjectDB
from abook.listener_overrides import overrides_path, request_pronunciation, request_retake
from abook.models import ProjectPaths
from abook.webui import store
from tests.test_listener_overrides import _Pipeline, _book, _chapter_statuses, _statuses


def _since(paths: ProjectPaths) -> float:
    return store.changes_since(paths.root, 0.0)


def _pending(paths: ProjectPaths) -> int:
    return store.pending_changes(paths.root, _since(paths))


def _reopen(paths: ProjectPaths) -> ProjectDB:
    return ProjectDB(paths.db)


def _unprocessed(db: ProjectDB) -> None:
    with db.connect() as conn:
        conn.execute("UPDATE segments SET status='analyzed', wav_path=NULL, wav_sha256=NULL")
        conn.execute("UPDATE chapters SET status='pending'")


def test_a_reading_saved_while_the_last_chapter_records_is_applied_before_the_book_finishes(tmp_path: Path) -> None:
    paths, db = _book(tmp_path)
    db.finalize_casting()
    _unprocessed(db)

    def listener_edits(index: int) -> None:
        if index == 3 and not overrides_path(paths.root).exists():  # chương cuối: sau lần đọc đầu chương, trước hết
            request_pronunciation(paths.root, "Hailkes", "Hên-khơ", now=1.0)

    pipeline = _Pipeline(paths, db, on_chapter=listener_edits)
    pipeline._process_all_chapters(verifier=None)

    assert pipeline.processed == [1, 2, 3, 1, 3], "ranh giới cuối: chương có tên Hailkes thu lại"
    assert set(_statuses(db).values()) == {"verified"} and set(_chapter_statuses(db).values()) == {"completed"}
    assert _pending(paths) == 0, "đã áp thật: không còn gì chờ"


def test_a_request_the_pipeline_has_not_read_stays_waiting_whatever_the_book_clock_says(tmp_path: Path) -> None:
    """Khe READY -> recovery: server ghi mốc khởi động SAU yêu cầu, và sổ ghi thêm sau đó - nhưng dây chuyền chưa đọc nó."""
    paths, db = _book(tmp_path)
    db.finalize_casting()
    request_pronunciation(paths.root, "Hailkes", "Hên-khơ", now=100.0)
    pipeline = _Pipeline(paths, db)
    assert pipeline._apply_listener_overrides() == {1, 3}
    assert _pending(paths) == 0

    request_pronunciation(paths.root, "Hailkesson", "Hên-khơ-sơn", now=150.0)  # sau lần đọc cuối của dây chuyền
    store.mark_run_started(paths.root, 200.0)  # server ghi mốc sau READY
    with db.connect() as conn:
        conn.execute("UPDATE book SET updated_at=300.0 WHERE id=1")
    assert _pending(paths) == 1, "mốc khởi động / sổ muộn hơn yêu cầu không phải bằng chứng đã áp"
    assert store.pending_details(paths.root, _since(paths))["items"], "hộp xem trước cũng thấy"

    pipeline._apply_listener_overrides()
    assert _pending(paths) == 0, "biên nhận khớp thì mới hết"


def test_a_new_request_replacing_an_applied_one_waits_again(tmp_path: Path) -> None:
    paths, db = _book(tmp_path)
    db.finalize_casting()
    request_pronunciation(paths.root, "Hailkes", "Hên-khơ", now=100.0)
    pipeline = _Pipeline(paths, db)
    pipeline._apply_listener_overrides()
    assert _pending(paths) == 0
    request_pronunciation(paths.root, "Hailkes", "Hai-kơ", now=100.0)  # cùng giờ, khác nội dung: băm khác
    assert _pending(paths) == 1
    request_pronunciation(paths.root, "Hailkes", "Hai-kơ", now=500.0)  # cùng nội dung, giờ mới: lần bấm khác
    assert _pending(paths) == 1


def test_a_crash_between_the_commit_and_the_receipt_applies_again_without_redoing(tmp_path: Path, monkeypatch) -> None:
    paths, db = _book(tmp_path)
    db.finalize_casting()
    request_retake(paths.root, "c1s1", "t11", now=700.0)

    def crash(*_args, **_kwargs) -> None:
        raise RuntimeError("chết giữa commit và biên nhận")

    monkeypatch.setattr(ProjectDB, "record_listener_receipt", crash)
    pipeline = _Pipeline(paths, db)
    try:
        pipeline._apply_listener_overrides()
    except RuntimeError:
        pass
    else:
        raise AssertionError("biên nhận hỏng phải làm lần áp dừng, không nuốt")
    monkeypatch.undo()

    with _reopen(paths).connect() as conn:
        assert conn.execute("SELECT listener_retakes FROM segments WHERE stable_id='c1s1'").fetchone()[0] == 1
    assert _pending(paths) == 1, "chưa có biên nhận: còn chờ"

    second = _Pipeline(paths, _reopen(paths))  # lần chạy sau
    assert second._apply_listener_overrides() == set(), "câu đã đặt lại rồi: không đặt lại lần nữa"
    with _reopen(paths).connect() as conn:
        assert conn.execute("SELECT listener_retakes FROM segments WHERE stable_id='c1s1'").fetchone()[0] == 1
    assert _pending(paths) == 0, "đối chiếu sổ rồi ghi biên nhận"


def test_a_book_the_pipeline_never_swept_keeps_the_old_clock_rule(tmp_path: Path) -> None:
    """Sách chưa qua lần quét nào (chưa phân vai xong, hay làm từ bản trước): vẫn suy từ mốc như cũ."""
    paths, db = _book(tmp_path)
    request_pronunciation(paths.root, "Hailkes", "Hên-khơ", now=100.0)
    assert store.pending_changes(paths.root, 50.0) == 1
    assert store.pending_changes(paths.root, 150.0) == 0
