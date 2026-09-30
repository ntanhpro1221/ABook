"""Người nghe sửa cách đọc một tên trong Studio, và sách đọc lại tên ấy - kể cả sách đã xong, kể cả giữa lúc chạy.

Hộp "Việc cần duyệt" (docs/STUDIO_REVIEW.md) ghi mong muốn vào `overrides.json`; dây chuyền áp ở ranh giới an toàn bằng
`ProjectDB.apply_listener_pronunciation`: ghim cách đọc VÀ đặt lại mọi câu đã thu có từ ấy, trong một transaction.
Trước đây chỉ có `cli pronounce`, phải dừng sách mới gõ được, và với sách đã xong thì không thu lại câu nào - recovery
của sách xong đi đường tắt, không bao giờ hỏi chuỗi nói của bản thu còn đúng không.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from ebook_reader.config import build_settings, settings_hash
from ebook_reader.database import LISTENER_PRONUNCIATION_SOURCE, ProjectDB
from ebook_reader.io_utils import sha256_file
from ebook_reader.listener_overrides import (
    MULTI_WORD,
    NOT_VIETNAMESE,
    overrides_path,
    pronunciation_problem,
    pronunciation_requests,
    read_overrides,
    request_pronunciation,
)
from ebook_reader.models import ProjectPaths
from ebook_reader.pipeline import BookPipeline
from ebook_reader.recovery import recover_project
from tests.test_recovery import complete_project_with_current_qa, setup_db

LINES = {
    1: ["Hailkes gật đầu.", "Trời mưa."],
    2: ["Không ai nói gì."],
    3: ["HAILKES!", "Hailkesson đứng dậy."],
}


def _book(tmp_path: Path) -> tuple[ProjectPaths, ProjectDB]:
    """Ba chương đã thu xong hết; chương 1 và 3 có tên Hailkes (chương 3 viết hoa, và có Hailkesson - tên KHÁC)."""
    paths = ProjectPaths.build(tmp_path / "project")
    settings = build_settings()
    db = ProjectDB(paths.db)
    db.initialize_book(
        title="T",
        project_root=paths.root,
        settings=settings,
        settings_hash=settings_hash(settings),
        input_manifest_hash="manifest",
    )
    for index, lines in LINES.items():
        source = tmp_path / f"{index:03d}.txt"
        source.write_text("\n".join(lines), encoding="utf-8")
        chapter_id = db.ensure_chapters([{
            "chapter_index": index,
            "title": f"{index:03d}",
            "input_path": source,
            "input_sha256": sha256_file(source),
            "input_size": source.stat().st_size,
            "output_mp3": paths.chapters / f"{index:03d}.mp3",
        }])[0]
        db.replace_chapter_segments(chapter_id, [
            {"stable_id": f"c{index}s{seq}", "seq": seq, "text": text, "text_sha256": f"t{index}{seq}",
             "kind_hint": "narration"}
            for seq, text in enumerate(lines)
        ])
        db.update_chapter_status(chapter_id, "completed")
    with db.connect() as conn:
        conn.execute("UPDATE segments SET status='verified', wav_path='take.wav', wav_sha256='sha'")
    db.upsert_pronunciation(surface="Hailkes", normalized_surface="hailkes", spoken_form="Hên",
                            confidence=0.7, source="analysis")
    return paths, db


def _statuses(db: ProjectDB) -> dict[str, str]:
    return {str(row["stable_id"]): str(row["status"]) for row in db.list_segments()}


def _chapter_statuses(db: ProjectDB) -> dict[int, str]:
    return {int(row["chapter_index"]): str(row["status"]) for row in db.list_chapters()}


def _events(db: ProjectDB, code: str) -> list[dict[str, Any]]:
    with db.connect() as conn:
        return [json.loads(row[0] or "{}") for row in
                conn.execute("SELECT details_json FROM runtime_events WHERE code=? ORDER BY id", (code,))]


def _apply(db: ProjectDB, spoken: str = "Hên-khơ") -> dict[str, Any] | None:
    return db.apply_listener_pronunciation(surface="Hailkes", normalized_surface="hailkes", spoken_form=spoken,
                                           source=LISTENER_PRONUNCIATION_SOURCE)


def test_every_recorded_line_that_says_the_word_goes_back_for_recording(tmp_path: Path) -> None:
    _paths, db = _book(tmp_path)

    result = _apply(db)

    assert result is not None and result["reset_segments"] == 2
    assert result["previous_spoken_form"] == "Hên"
    statuses = _statuses(db)
    # Đúng phép khớp của TTS: nguyên từ, không phân biệt hoa thường. "Hailkesson" là tên khác, không đụng.
    assert statuses["c1s0"] != "verified" and statuses["c3s0"] != "verified"
    assert statuses["c1s1"] == statuses["c2s0"] == statuses["c3s1"] == "verified"
    reset = next(row for row in db.list_segments() if str(row["stable_id"]) == "c1s0")
    assert reset["wav_path"] is None and reset["wav_sha256"] is None
    # Chương đã xong có câu bị đặt lại thì phải dựng lại MP3; chương không có tên thì giữ nguyên.
    assert _chapter_statuses(db) == {1: "warning", 2: "completed", 3: "warning"}
    row = next(row for row in db.list_pronunciations(0.0) if str(row["surface"]) == "Hailkes")
    assert (str(row["spoken_form"]), int(row["locked"]), str(row["source"])) == (
        "Hên-khơ", 1, LISTENER_PRONUNCIATION_SOURCE)
    assert _events(db, "PRONUNCIATION_SET_BY_LISTENER")[0]["reset_segments"] == 2


def test_applying_the_same_reading_again_changes_nothing(tmp_path: Path) -> None:
    """File yêu cầu là trạng thái mong muốn, đọc lại ở MỌI ranh giới chương: áp lại phải là không làm gì."""
    _paths, db = _book(tmp_path)
    _apply(db)
    with db.connect() as conn:  # câu đã thu lại với cách đọc mới
        conn.execute("UPDATE segments SET status='verified', wav_path='new.wav', wav_sha256='new'")

    assert _apply(db) is None
    assert set(_statuses(db).values()) == {"verified"}
    assert len(_events(db, "PRONUNCIATION_SET_BY_LISTENER")) == 1


def test_confirming_the_machine_reading_pins_it_without_rerecording(tmp_path: Path) -> None:
    """"Đúng rồi" không đổi chuỗi nói: ghim để máy không bao giờ đổi nữa, nhưng không tốn GPU thu lại câu nào."""
    _paths, db = _book(tmp_path)

    result = _apply(db, spoken="Hên")

    assert result is not None and result["reset_segments"] == 0
    assert set(_statuses(db).values()) == {"verified"}
    assert set(_chapter_statuses(db).values()) == {"completed"}
    row = next(row for row in db.list_pronunciations(0.0) if str(row["surface"]) == "Hailkes")
    assert (int(row["locked"]), str(row["source"]), float(row["confidence"])) == (1, LISTENER_PRONUNCIATION_SOURCE, 1.0)


def test_a_crash_inside_the_apply_leaves_the_book_exactly_as_it_was(tmp_path: Path, monkeypatch) -> None:
    """AGENTS.md: đổi database phải có test crash/mở lại. Cách đọc mới mà câu cũ vẫn "xong" là sách nói dối."""
    paths, db = _book(tmp_path)

    def crash(self, conn, chapter_id):
        raise RuntimeError("máy tắt giữa transaction")

    monkeypatch.setattr(ProjectDB, "_refresh_chapter_counts_conn", crash)
    with pytest.raises(RuntimeError):
        _apply(db)
    monkeypatch.undo()

    reopened = ProjectDB(paths.db)
    assert set(_statuses(reopened).values()) == {"verified"}
    assert set(_chapter_statuses(reopened).values()) == {"completed"}
    row = next(row for row in reopened.list_pronunciations(0.0) if str(row["surface"]) == "Hailkes")
    assert str(row["spoken_form"]) == "Hên" and int(row["locked"]) == 0
    assert not _events(reopened, "PRONUNCIATION_SET_BY_LISTENER")


def test_a_finished_book_no_longer_skips_recovery_after_a_new_reading(tmp_path: Path, monkeypatch) -> None:
    """Đường tắt của sách đã xong chỉ nhìn MP3 và QA; chương có câu bị đặt lại phải kéo nó xuống đường sâu."""
    paths, settings, db, row = setup_db(tmp_path)
    complete_project_with_current_qa(paths, settings, db, row)
    monkeypatch.setattr("ebook_reader.recovery.verify_mp3", lambda _path: (True, "ok"))  # như test_recovery
    assert recover_project(paths, db, settings).completed_verified

    assert db.apply_listener_pronunciation(surface="Xin", normalized_surface="xin", spoken_form="Xinh",
                                           source=LISTENER_PRONUNCIATION_SOURCE)["reset_segments"] == 1

    report = recover_project(paths, db, settings)
    assert not report.completed_verified
    assert str(db.list_segments()[0]["status"]) in {"pending", "analyzed"}


def test_the_request_file_round_trips_and_a_new_request_replaces_the_old(tmp_path: Path) -> None:
    request_pronunciation(tmp_path, "Hailkes", "Hên-khơ", now=1.0)
    request_pronunciation(tmp_path, "hailkes", "  Hên-cơ ", now=2.0)
    request_pronunciation(tmp_path, "Noah", "Nô-ơ", now=3.0)

    assert pronunciation_requests(read_overrides(tmp_path)) == [
        {"surface": "hailkes", "spoken_form": "Hên-cơ"},
        {"surface": "Noah", "spoken_form": "Nô-ơ"},
    ]
    assert not list(tmp_path.glob(".overrides.*")), "file tạm phải được thay vào chỗ, không để lại"


def test_an_unreadable_request_file_means_no_requests(tmp_path: Path) -> None:
    overrides_path(tmp_path).write_text("{không phải json", encoding="utf-8")
    assert pronunciation_requests(read_overrides(tmp_path)) == []


def test_a_request_follows_the_same_contract_as_a_machine_reading() -> None:
    assert pronunciation_problem("Hailkes", "Hên-khơ") is None
    assert pronunciation_problem("Deck", "Deck") is None  # đọc đúng như viết: người nghe được chọn
    assert pronunciation_problem("Lucien Evans", "Lu-si-en Ê-van") == MULTI_WORD
    assert pronunciation_problem("Hailkes", "Hlkx") == NOT_VIETNAMESE


class _Tts:
    def __init__(self) -> None:
        self.forgotten = 0

    def forget_pronunciations(self) -> None:
        self.forgotten += 1


class _Qa:
    def unload(self) -> None:
        pass


class _Pipeline(BookPipeline):
    """Không gọi `BookPipeline.__init__`: chỉ vòng chương và phép áp yêu cầu là thật, thu âm là giả."""

    def __init__(self, paths: ProjectPaths, db: ProjectDB, on_chapter=None) -> None:
        self.paths = paths
        self.db = db
        self.tts = _Tts()
        self.perceptual_qa = _Qa()
        self._rejected_listener_overrides = set()
        self.logs: list[str] = []
        self.processed: list[int] = []
        self._on_chapter = on_chapter

    def log(self, message: str) -> None:
        self.logs.append(message)

    def emit(self, *_args, **_kwargs) -> None:
        pass

    def _wait_pause_or_stop(self) -> float:
        return 0.0

    def _safe_export_reports(self, incremental: bool = False) -> None:
        pass

    def _process_chapter(self, chapter, verifier) -> None:
        index = int(chapter["chapter_index"])
        self.processed.append(index)
        if self._on_chapter is not None:
            self._on_chapter(index)
        with self.db.connect() as conn:  # "thu" chương: mọi câu xong, chương xong
            conn.execute("UPDATE segments SET status='verified', wav_path='take.wav', wav_sha256='sha' "
                         "WHERE chapter_id=?", (int(chapter["id"]),))
            conn.execute("UPDATE chapters SET status='completed' WHERE id=?", (int(chapter["id"]),))


def test_nothing_is_applied_before_casting_is_locked(tmp_path: Path) -> None:
    """Trong pha phân tích, cách đọc là đầu vào của phân tích: đổi nó lúc ấy là đổi quyển sách (AGENTS.md)."""
    paths, db = _book(tmp_path)
    request_pronunciation(paths.root, "Hailkes", "Hên-khơ", now=1.0)
    pipeline = _Pipeline(paths, db)

    assert pipeline._apply_listener_overrides() == set()
    assert set(_statuses(db).values()) == {"verified"}

    db.finalize_casting()
    assert pipeline._apply_listener_overrides() == {1, 3}
    assert pipeline.tts.forgotten == 1, "bảng cách đọc đang giữ trong tiến trình phải được đọc lại"
    assert pipeline._apply_listener_overrides() == set()
    assert pipeline.tts.forgotten == 1


def test_a_request_that_cannot_apply_is_reported_once_and_skipped(tmp_path: Path) -> None:
    paths, db = _book(tmp_path)
    db.finalize_casting()
    request_pronunciation(paths.root, "Hailkes", "Hlkx", now=1.0)
    pipeline = _Pipeline(paths, db)

    for _boundary in range(3):
        assert pipeline._apply_listener_overrides() == set()
    assert [event["problem"] for event in _events(db, "LISTENER_OVERRIDE_REJECTED")] == [NOT_VIETNAMESE]
    assert set(_statuses(db).values()) == {"verified"}


def test_a_reading_changed_mid_run_rerecords_the_chapters_already_passed(tmp_path: Path) -> None:
    """Người nghe sửa lúc sách đang thu chương 2: chương 3 thu với cách đọc mới, chương 1 (đã qua) được thu lại sau."""
    paths, db = _book(tmp_path)
    db.finalize_casting()
    with db.connect() as conn:
        conn.execute("UPDATE segments SET status='analyzed', wav_path=NULL, wav_sha256=NULL")
        conn.execute("UPDATE chapters SET status='pending'")

    def listener_edits(index: int) -> None:
        if index == 2 and not overrides_path(paths.root).exists():
            request_pronunciation(paths.root, "Hailkes", "Hên-khơ", now=1.0)

    pipeline = _Pipeline(paths, db, on_chapter=listener_edits)
    pipeline._process_all_chapters(verifier=None)

    assert pipeline.processed == [1, 2, 3, 1]
    assert set(_statuses(db).values()) == {"verified"}
    assert set(_chapter_statuses(db).values()) == {"completed"}
    assert any("Hailkes" in line for line in pipeline.logs)


def test_the_cli_command_now_rerecords_too(tmp_path: Path) -> None:
    """`cli pronounce` đi cùng đường: trước đây nó chỉ ghim, và sách đã xong giữ audio đọc tên cũ mãi mãi."""
    import argparse

    from ebook_reader.cli import _command_pronounce

    paths, db = _book(tmp_path)
    (paths.root / "book_settings.json").write_text("{}", encoding="utf-8")
    result = _command_pronounce(argparse.Namespace(project_root=paths.root, surface="Hailkes", spoken="Hên-khơ",
                                                   json=False))
    assert result.exit_code == 0 and result.data["reset_segments"] == 2
    assert _chapter_statuses(db)[1] == "warning"


def test_every_listener_write_is_one_sqlite_transaction(tmp_path: Path) -> None:
    """Không ai khác được thấy nửa chừng: một kết nối khác đọc trong lúc áp chỉ thấy trước hoặc sau."""
    _paths, db = _book(tmp_path)
    seen: list[tuple[str, int]] = []
    original = ProjectDB._reset_segment_pending_conn

    def spy(conn, segment_id, reason, now):
        original(conn, segment_id, reason, now)
        other = sqlite3.connect(db.path, timeout=0.1)
        spoken = other.execute("SELECT spoken_form FROM pronunciations WHERE normalized_surface='hailkes'").fetchone()[0]
        verified = other.execute("SELECT COUNT(*) FROM segments WHERE status='verified'").fetchone()[0]
        other.close()
        seen.append((spoken, verified))

    from ebook_reader import database

    database.ProjectDB._reset_segment_pending_conn = staticmethod(spy)
    try:
        _apply(db)
    finally:
        database.ProjectDB._reset_segment_pending_conn = staticmethod(original)
    assert seen and all(state == ("Hên", 5) for state in seen)
