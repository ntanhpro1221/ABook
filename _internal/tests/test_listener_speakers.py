"""Người nghe sửa "ai nói câu này" trong Studio, và câu được đọc lại bằng giọng của đúng người.

Hộp "Việc cần anh" ghi mong muốn vào `overrides.json` (mã câu + băm chữ, để không bao giờ áp nhầm câu đã đổi); dây chuyền
áp ở ranh giới an toàn bằng `ProjectDB.apply_listener_speaker`: gán câu cho người ấy bằng ĐÚNG nhãn và giọng sẵn có của
họ - nên "một người một giọng" (`assert_voice_stability`) vẫn đúng - và đặt lại câu nếu đã thu, trong một transaction.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ebook_reader.config import build_settings, settings_hash
from ebook_reader.database import ProjectDB
from ebook_reader.io_utils import sha256_file
from ebook_reader.listener_overrides import (
    NARRATOR,
    NO_VOICE,
    NOT_SPEECH,
    SOURCE_CHANGED,
    UNKNOWN_LINE,
    UNNAMED,
    request_speaker,
)
from ebook_reader.models import ProjectPaths
from tests.test_listener_overrides import _Pipeline

LINES = [
    ("c1s0", "narration", "NARRATOR", "Lucien nhìn Natasha."),
    ("c1s1", "dialogue", "Lucien", "“Đi thôi.”"),
    ("c1s2", "dialogue", "Lucien", "“Cô chắc chứ?”"),
    ("c1s3", "dialogue", "NATASHA", "“Chắc.”"),
    ("c1s4", "dialogue", "UNKNOWN", "“Ai đó?”"),
]
VOICES = {"NARRATOR": "narrator", "LUCIEN": "v_lucien", "NATASHA": "v_natasha", "ANONYMOUS_MALE": "v_anon_m"}


def _book(tmp_path: Path) -> tuple[ProjectPaths, ProjectDB]:
    """Một chương đã phân vai và thu xong: Lucien, Natasha, người kể, một nhóm vô danh nam."""
    paths = ProjectPaths.build(tmp_path / "project")
    settings = build_settings()
    db = ProjectDB(paths.db)
    db.initialize_book(title="T", project_root=paths.root, settings=settings, settings_hash=settings_hash(settings),
                       input_manifest_hash="manifest")
    source = tmp_path / "001.txt"
    source.write_text("\n".join(text for *_rest, text in LINES), encoding="utf-8")
    chapter_id = db.ensure_chapters([{
        "chapter_index": 1, "title": "001", "input_path": source, "input_sha256": sha256_file(source),
        "input_size": source.stat().st_size, "output_mp3": paths.chapters / "001.mp3",
    }])[0]
    db.replace_chapter_segments(chapter_id, [
        {"stable_id": stable_id, "seq": seq, "text": text, "text_sha256": f"sha-{stable_id}", "kind_hint": kind}
        for seq, (stable_id, kind, _speaker, text) in enumerate(LINES)
    ])
    with db.connect() as conn:
        for key, voice in VOICES.items():
            conn.execute("INSERT INTO voice_profiles(voice_key,engine,preset_name,description,seed,pitch_semitones,"
                         "status,locked,created_at,updated_at) VALUES(?,?,?,?,?,0,'ready',1,0,0)",
                         (voice, "vieneu", voice, voice, 1))
            gender = {"LUCIEN": "male", "NATASHA": "female", "ANONYMOUS_MALE": "male"}.get(key, "unknown")
            conn.execute("INSERT INTO characters(canonical_name,display_name,gender,age,personality,importance,"
                         "mention_count,confidence,locked,created_at,updated_at) VALUES(?,?,?,'adult','','main',1,1,0,0,0)",
                         (key, key.title(), gender))
        for stable_id, kind, speaker, _text in LINES:
            key = {"UNKNOWN": "ANONYMOUS_MALE"}.get(speaker, speaker.upper())
            conn.execute(
                "UPDATE segments SET kind=?, speaker=?, gender=?, status='verified', wav_path='take.wav', wav_sha256='sha',"
                " canonical_character_id=(SELECT id FROM characters WHERE canonical_name=?),"
                " voice_profile_id=(SELECT id FROM voice_profiles WHERE voice_key=?) WHERE stable_id=?",
                (kind, speaker, "male" if speaker == "UNKNOWN" else "unknown", key, VOICES[key], stable_id))
    db.update_chapter_status(chapter_id, "completed")
    db.finalize_casting()
    return paths, db


def _segment(db: ProjectDB, stable_id: str) -> dict[str, Any]:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT s.*, v.voice_key, c.canonical_name FROM segments s LEFT JOIN voice_profiles v ON v.id=s.voice_profile_id"
            " LEFT JOIN characters c ON c.id=s.canonical_character_id WHERE s.stable_id=?", (stable_id,)).fetchone()
    return dict(row)


def _apply(db: ProjectDB, stable_id: str, speaker: str, text_sha256: str | None = None):
    return db.apply_listener_speaker(stable_id=stable_id, text_sha256=text_sha256 or f"sha-{stable_id}", speaker=speaker)


def _one_voice_per_person(db: ProjectDB) -> None:
    from ebook_reader.character_registry import assert_voice_stability

    assert_voice_stability(db)


def test_a_line_moves_to_the_right_person_with_that_persons_own_voice(tmp_path: Path) -> None:
    _paths, db = _book(tmp_path)

    result = _apply(db, "c1s2", "NATASHA")

    assert result is not None and result["reset"] is True and result["previous_speaker"] == "Lucien"
    line = _segment(db, "c1s2")
    assert (line["speaker"], line["canonical_name"], line["voice_key"]) == ("NATASHA", "NATASHA", "v_natasha")
    assert line["status"] == "analyzed" and line["wav_path"] is None, "câu đã thu phải thu lại bằng giọng mới"
    assert _segment(db, "c1s1")["voice_key"] == "v_lucien", "câu khác của Lucien không đổi"
    _one_voice_per_person(db)
    with db.connect() as conn:
        assert conn.execute("SELECT status FROM chapters").fetchone()[0] == "warning"
        event = conn.execute("SELECT details_json FROM runtime_events WHERE code='SPEAKER_SET_BY_LISTENER'").fetchone()
    assert json.loads(event[0])["speaker"] == "NATASHA"


def test_the_narrator_and_the_unnamed_are_choices_too(tmp_path: Path) -> None:
    _paths, db = _book(tmp_path)

    _apply(db, "c1s2", NARRATOR)
    _apply(db, "c1s1", UNNAMED)  # Lucien là nam: vào nhóm vô danh NAM, không bao giờ mượn giọng khác giới

    assert (_segment(db, "c1s2")["speaker"], _segment(db, "c1s2")["voice_key"]) == ("NARRATOR", "narrator")
    unnamed = _segment(db, "c1s1")
    assert unnamed["canonical_name"] == "ANONYMOUS_MALE" and unnamed["voice_key"] == "v_anon_m"
    # Natasha là nữ và sách không có nhóm vô danh nữ hay chưa rõ giới: không có giọng hợp lệ, không áp.
    assert _apply(db, "c1s3", UNNAMED) == {"problem": NO_VOICE}
    _one_voice_per_person(db)


def test_keeping_the_current_speaker_changes_nothing(tmp_path: Path) -> None:
    """"Giữ nguyên" đóng việc trong hộp; ở dây chuyền nó không được đụng tới bản thu."""
    _paths, db = _book(tmp_path)

    assert _apply(db, "c1s1", "Lucien") is None
    assert _segment(db, "c1s1")["status"] == "verified"


@pytest.mark.parametrize(("stable_id", "speaker", "text_sha256", "problem"), [
    ("c9s9", "NATASHA", None, UNKNOWN_LINE),
    ("c1s1", "NATASHA", "sha-khac", SOURCE_CHANGED),
    ("c1s0", "NATASHA", None, NOT_SPEECH),
    ("c1s1", "HEIDI", None, NO_VOICE),
])
def test_a_request_that_cannot_apply_changes_nothing(tmp_path: Path, stable_id, speaker, text_sha256, problem) -> None:
    _paths, db = _book(tmp_path)

    assert _apply(db, stable_id, speaker, text_sha256) == {"problem": problem}
    assert {row["stable_id"]: row["status"] for row in db.list_segments()} == {sid: "verified" for sid, *_ in LINES}


def test_a_crash_inside_the_apply_leaves_the_line_as_it_was(tmp_path: Path, monkeypatch) -> None:
    paths, db = _book(tmp_path)

    def crash(self, conn, chapter_id):
        raise RuntimeError("máy tắt giữa transaction")

    monkeypatch.setattr(ProjectDB, "_refresh_chapter_counts_conn", crash)
    with pytest.raises(RuntimeError):
        _apply(db, "c1s2", "NATASHA")
    monkeypatch.undo()

    line = _segment(ProjectDB(paths.db), "c1s2")
    assert (line["speaker"], line["voice_key"], line["status"]) == ("Lucien", "v_lucien", "verified")


def test_the_pipeline_applies_a_speaker_request_at_a_boundary(tmp_path: Path) -> None:
    paths, db = _book(tmp_path)
    request_speaker(paths.root, "c1s2", "sha-c1s2", "NATASHA", now=1.0)
    request_speaker(paths.root, "c1s1", "sha-khac", "NATASHA", now=1.0)  # chữ đã đổi: báo một lần, không áp
    pipeline = _Pipeline(paths, db)

    assert pipeline._apply_listener_overrides() == {1}
    assert pipeline._apply_listener_overrides() == set()
    assert _segment(db, "c1s2")["voice_key"] == "v_natasha"
    assert _segment(db, "c1s1")["voice_key"] == "v_lucien"
    with db.connect() as conn:
        rejected = conn.execute("SELECT COUNT(*) FROM runtime_events WHERE code='LISTENER_OVERRIDE_REJECTED'").fetchone()
    assert rejected[0] == 1
