"""Đặt lại một câu là bỏ bản thu của nó - và bỏ luôn lịch sử vòng sửa của bản thu ấy.

Ứng viên vòng sửa (`segment_candidates`) gắn với một bản thu gốc: `promoted` là trạng thái cuối, không bao giờ bị vô
hiệu, và recovery kiểm MỌI ứng viên promoted "vẫn là bản thu hiện tại của câu" (`_validated_promoted_candidate_conn`,
không bắt lỗi). Câu bị đặt lại - recovery thấy chuỗi nói lệch hay WAV hỏng, `retry_failed_segments`, hay người nghe đổi
cách đọc (`apply_listener_pronunciation`) - vẫn giữ ứng viên promoted của bản thu đã bỏ, nên:

1. lần recovery kế tiếp ném "promoted candidate is not the current segment artifact" và cả lần chạy không khởi động;
   với phép áp cách đọc lúc khởi động (trước recovery) thì chết ngay lần chạy ấy;
2. bản thu mới cần sửa thì vòng 0 đụng ứng viên vòng 0 của đời trước (khác bản gốc) và cấp phát từ chối;
3. các vòng cũ đã tiêu ngân sách sửa của câu dưới cùng chính sách.

Ở Tập 18, 720/3.682 câu có ứng viên promoted - chừng một câu năm. Fixture: bản lô 9 đóng băng
(`_fixtures/lo09_223_cut_off`), ứng viên thật được promote thật (`test_a_finished_take_survives_the_report`).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ebook_reader.database import ProjectDB
from tests.test_a_finished_take_survives_the_report import _copy, _promote_the_real_finished_take


def _candidates(db: ProjectDB, segment_id: int) -> int:
    with db.connect() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM segment_candidates WHERE segment_id=?", (segment_id,)).fetchone()[0])


def test_recovery_still_starts_after_a_repaired_line_is_reset(tmp_path: Path) -> None:
    db = _copy(tmp_path)
    segment_id, policy_hash, _candidate_id = _promote_the_real_finished_take(db)
    db.reconcile_segment_candidate_artifacts(policy_hash)  # trước khi đặt lại: hợp lệ

    db.reset_segment_pending(segment_id, "chuỗi nói lệch")

    db.reconcile_segment_candidate_artifacts(policy_hash)  # trước đây: RuntimeError, lần chạy không khởi động
    assert _candidates(db, segment_id) == 0
    # Bản thu mới bắt đầu lại từ vòng 0 với đủ ngân sách, không phải "đã sửa xong" bằng ứng viên của bản thu đã bỏ.
    plan = db.segment_candidate_resume_plan(segment_id, policy_hash, 2)
    assert plan["action"] != "complete" and plan.get("candidate_id") is None, plan


def test_a_listener_reading_on_a_repaired_line_does_not_break_the_next_start(tmp_path: Path) -> None:
    """Đúng đường của hộp "Việc cần bạn": áp cách đọc lúc khởi động chạy TRƯỚC recovery."""
    from ebook_reader.database import LISTENER_PRONUNCIATION_SOURCE

    db = _copy(tmp_path)
    segment_id, policy_hash, _candidate_id = _promote_the_real_finished_take(db)
    with db.connect() as conn:
        text = str(conn.execute("SELECT text FROM segments WHERE id=?", (segment_id,)).fetchone()[0])
    word = next(token for token in text.replace("!", " ").split() if token.isalpha())

    result = db.apply_listener_pronunciation(surface=word, normalized_surface=word.casefold(), spoken_form="Thử",
                                             source=LISTENER_PRONUNCIATION_SOURCE)

    assert result is not None and result["reset_segments"] >= 1
    db.reconcile_segment_candidate_artifacts(policy_hash)
    assert _candidates(db, segment_id) == 0


def test_a_crash_while_resetting_keeps_the_line_and_its_repairs_together(tmp_path: Path, monkeypatch) -> None:
    """AGENTS.md: đổi database phải có test crash/mở lại. Câu đã đặt lại mà ứng viên còn đó là đúng lỗi ở trên; câu còn
    nguyên mà ứng viên đã mất là mất bằng chứng của bản thu đang dùng. Cả hai cùng xảy ra hoặc cùng không."""
    db = _copy(tmp_path)
    segment_id, policy_hash, _candidate_id = _promote_the_real_finished_take(db)
    before = _candidates(db, segment_id)

    def crash(self, conn, chapter_id):
        raise RuntimeError("máy tắt giữa lúc đặt lại")

    monkeypatch.setattr(ProjectDB, "_refresh_chapter_counts_conn", crash)
    with pytest.raises(RuntimeError):
        db.reset_segment_pending(segment_id, "chuỗi nói lệch")
    monkeypatch.undo()

    reopened = ProjectDB(db.path)
    assert _candidates(reopened, segment_id) == before
    with reopened.connect() as conn:
        assert conn.execute("SELECT wav_path FROM segments WHERE id=?", (segment_id,)).fetchone()[0]
    reopened.reconcile_segment_candidate_artifacts(policy_hash)
