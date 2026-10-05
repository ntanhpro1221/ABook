"""Câu nội tâm đọc bằng giọng người đang nghĩ; chỉ câu không ai nhận mới về người kể (chủ sách 20-09).

Phân tích và cơ sở dữ liệu đã giữ người nghĩ từ trước; chỗ còn ép mọi câu nội tâm về người kể là lúc dựng tiếng
(`tts._voice_profile_for_row`, `_spoken_row`) và kiểm khoá giọng của bản thu thử (`_expected_segment_voice_profile_conn`).
Cả bốn nơi hỏi một luật: `database.thought_reads_as_narrator`.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from abook.config import build_settings
from abook.database import ProjectDB, thought_reads_as_narrator
from abook.tts import TTSCoordinator


@pytest.mark.parametrize(
    "kind, speaker, voice_profile_id, expected",
    [
        ("thought", "Lucien", 7, False),
        ("thought", "lucien", 7, False),
        ("thought", "NARRATOR", 7, True),
        ("thought", "narrator", 7, True),
        ("thought", "UNKNOWN", 7, True),
        ("thought", "", 7, True),
        ("thought", None, 7, True),
        ("thought", "Lucien", None, True),
        (" Thought ", "Lucien", 7, False),
        # Lời kể và lời thoại không bao giờ bị luật này chạm tới, dù người nói là ai.
        ("narration", "NARRATOR", 7, False),
        ("narration", "Lucien", None, False),
        ("dialogue", "Lucien", 7, False),
        ("dialogue", "UNKNOWN", None, False),
        (None, "Lucien", 7, False),
    ],
)
def test_the_rule(kind, speaker, voice_profile_id, expected) -> None:
    assert thought_reads_as_narrator(kind, speaker, voice_profile_id) is expected


def _book(tmp_path: Path) -> tuple[ProjectDB, int, int]:
    db = ProjectDB(tmp_path / "project.sqlite3")
    narrator = db.upsert_voice_profile({
        "voice_key": "narrator", "engine": "vieneu", "preset_name": "Phạm Tuyên",
        "description": "Người kể", "seed": 1, "pitch_semitones": 0, "status": "ready",
    })
    lucien = db.upsert_voice_profile({
        "voice_key": "lucien", "engine": "vieneu", "preset_name": "Thanh Bình",
        "description": "Lucien", "seed": 2, "pitch_semitones": 0, "status": "ready",
    })
    return db, narrator, lucien


def _row(kind: str, speaker: str, profile_id: int | None) -> dict:
    return {"stable_id": "s1", "text": "Mình phải làm gì đây?", "kind": kind, "speaker": speaker,
            "voice_profile_id": profile_id}


def test_synthesis_picks_the_thinker_or_the_narrator(tmp_path: Path) -> None:
    db, narrator, lucien = _book(tmp_path)
    coordinator = TTSCoordinator(build_settings(), db, lambda _message: None)

    def profile_id(kind: str, speaker: str, profile: int | None) -> int:
        return int(coordinator._voice_profile_for_row(_row(kind, speaker, profile))["id"])

    assert profile_id("thought", "Lucien", lucien) == lucien
    assert profile_id("thought", "NARRATOR", narrator) == narrator
    assert profile_id("thought", "UNKNOWN", lucien) == narrator
    assert profile_id("thought", "Lucien", None) == narrator
    # Lời kể và lời thoại: vẫn đúng giọng của chính dòng.
    assert profile_id("dialogue", "Lucien", lucien) == lucien
    assert profile_id("narration", "NARRATOR", narrator) == narrator

    spoken = coordinator._spoken_row(_row("thought", "Lucien", lucien))
    assert spoken["speaker"] == "Lucien" and int(spoken["voice_profile_id"]) == lucien
    spoken = coordinator._spoken_row(_row("thought", "UNKNOWN", lucien))
    assert spoken["speaker"] == "NARRATOR" and int(spoken["voice_profile_id"]) == narrator
    spoken = coordinator._spoken_row(_row("dialogue", "Lucien", lucien))
    assert spoken["speaker"] == "Lucien" and int(spoken["voice_profile_id"]) == lucien


def test_the_candidate_voice_lock_expects_the_same_profile(tmp_path: Path) -> None:
    db, narrator, lucien = _book(tmp_path)
    with db.connect() as conn:
        conn.execute("UPDATE voice_profiles SET locked=1")
        conn.row_factory = sqlite3.Row

        def expected(kind: str, speaker: str, profile: int | None) -> int:
            segment = _row(kind, speaker, profile)
            return int(ProjectDB._expected_segment_voice_profile_conn(conn, segment)["id"])

        assert expected("thought", "Lucien", lucien) == lucien
        assert expected("thought", "NARRATOR", narrator) == narrator
        assert expected("thought", "UNKNOWN", lucien) == narrator
        assert expected("dialogue", "Lucien", lucien) == lucien
        assert expected("narration", "NARRATOR", narrator) == narrator
