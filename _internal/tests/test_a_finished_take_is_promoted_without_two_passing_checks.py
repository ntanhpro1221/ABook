"""Promote a finished take over a cut-off incumbent through the durable API.

The current-schema synthetic fixture reproduces the batch-9 failure conditions:
short text, a capped incumbent, and a finished candidate with two failed decodes.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from abook.database import SEGMENT_CANDIDATE_PROMOTED, ProjectDB

SEGMENT_SUFFIX = "5b7f60a11624"  # "Gục đi!"


def _copy(tmp_path: Path) -> ProjectDB:
    from tests.candidate_fixtures import finished_take
    return finished_take(tmp_path)


def _segment(db: ProjectDB) -> sqlite3.Row:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM segments WHERE stable_id LIKE ?", (f"%{SEGMENT_SUFFIX}",)
        ).fetchone()
    assert row is not None
    return row


def _next_attempt(db: ProjectDB, segment_id: int) -> int:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT coalesce(max(attempt), 0) FROM quality_checks WHERE segment_id=?",
            (segment_id,),
        ).fetchone()
    return int(row[0]) + 1


def _eligible_candidate(db: ProjectDB, segment: sqlite3.Row) -> sqlite3.Row:
    policy_hash = str(db.current_quality_policy()["policy_hash"])
    candidate = db.find_finished_take_over_a_cut_off_incumbent(int(segment["id"]), policy_hash)
    assert candidate is not None, "fixture phải còn ứng viên đủ bốn điều kiện"
    assert Path(str(candidate["wav_path"])).is_file(), "synthetic candidate fixture must create its WAV"
    return candidate


def test_the_finished_candidate_is_promoted(tmp_path: Path) -> None:
    db = _copy(tmp_path)
    segment = _segment(db)
    candidate = _eligible_candidate(db, segment)

    promoted = db.promote_segment_candidate(
        int(candidate["id"]),
        validated_wav_sha256=str(candidate["wav_sha256"]),
        repair_action="promote_finished_take_over_cut_off_incumbent",
        attempt=_next_attempt(db, int(segment["id"])),
        warning_code="ASR_UNVERIFIABLE_SHORT_TEXT",
        over_a_cut_off_incumbent=True,
    )

    assert str(promoted["state"]) == SEGMENT_CANDIDATE_PROMOTED
    after = _segment(db)
    assert str(after["wav_sha256"]).casefold() == str(candidate["wav_sha256"]).casefold()


def test_without_the_flag_two_failed_decodes_still_refuse(tmp_path: Path) -> None:
    """Chốt không bị tháo: đề cử thường vẫn đòi hai đường phiên đều qua."""
    db = _copy(tmp_path)
    segment = _segment(db)
    candidate = _eligible_candidate(db, segment)

    # Không có cờ, cửa đóng ngay ở tập trạng thái (dual_failed không đề cử được) - trước cả chốt
    # "two passing checks". Cả hai thông điệp đều là "từ chối"; bài này khẳng định cửa đóng.
    with pytest.raises(RuntimeError, match="two passing checks|before both ASR decodes pass"):
        db.promote_segment_candidate(
            int(candidate["id"]),
            validated_wav_sha256=str(candidate["wav_sha256"]),
            repair_action="promote_dual_decode_clarity_candidate",
            attempt=_next_attempt(db, int(segment["id"])),
            warning_code=None,
        )
