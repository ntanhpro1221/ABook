from pathlib import Path

import pytest

from abook.character_registry import resolve_gender
from abook.database import ProjectDB
from abook.speaker_pass import db_label
from test_speaker_pass_pipeline import make_project


@pytest.mark.parametrize("description,chapter_offset,expected", [
    ("lính gác", 0, ("male", "adult")),
    ("người hầu", 0, ("unknown", "unknown")),
    ("lính gác", 1, ("unknown", "unknown")),
])
def test_local_pass_relabel_preserves_traits_only_for_the_same_role_in_the_same_chapter(
    tmp_path: Path, description: str, chapter_offset: int, expected: tuple[str, str],
) -> None:
    db = make_project(tmp_path / "p")
    chapter = int(db.list_chapters()[0]["id"])
    old = f"NPC_LOCAL::c{chapter + chapter_offset:05d}::r0b1::lính gác"
    new = db_label(f"NPC_LOCAL:{description}", chapter)
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET speaker=?,gender='male',age='adult' WHERE stable_id IN ('c1s1','c1s3')", (old,))
    rows = {str(row["stable_id"]): row for row in db.list_segments()}
    db.commit_speaker_pass_chapter(chapter, [(rows[s]["id"], old, new) for s in ("c1s1", "c1s3")], {}, seconds=0)
    for row in ProjectDB(db.path).list_segments():
        if row["stable_id"] in {"c1s1", "c1s3"}:
            assert row["speaker"] == new
            assert (row["gender"], row["age"]) == expected


@pytest.mark.parametrize("evidence", ["unchanged", "registry", "carried_registry", "missing", "conflicting", "pinned_conflict"])
def test_changed_speakers_use_only_the_new_persons_traits(tmp_path: Path, evidence: str) -> None:
    db = make_project(tmp_path / "p")
    chapter = int(db.list_chapters()[0]["id"])
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET gender='male',age='elderly' WHERE stable_id='c1s1'")
        conn.execute("UPDATE segments SET speaker='Lan',gender='male',age='adult' WHERE stable_id='c1s4'")
        if evidence in {"unchanged", "conflicting", "pinned_conflict"}:
            conn.execute("UPDATE segments SET speaker='Lan',gender='female',age='young' WHERE stable_id='c1s3'")
        if evidence in {"conflicting", "pinned_conflict"}:
            conn.execute("UPDATE segments SET speaker='Lan',gender='male',age='child' WHERE stable_id='c1s5'")
        # Chưa qua lượt hỏi lại: không được dùng như bằng chứng đã xác nhận.
        conn.execute("UPDATE segments SET speaker='Lan',gender='male',age='elderly' WHERE stable_id='c2s1'")
    if evidence in {"registry", "pinned_conflict"}:
        db.lock_character_gender("Lan", "female")
        db.lock_character_age("Lan", "young")
    elif evidence == "carried_registry":
        db.upsert_character(canonical_name="LAN", display_name="Lan", gender="female", age="young",
                            personality="", mentions=1, importance="minor", confidence=1.0)
    rows = {str(r["stable_id"]): r for r in db.list_segments()}
    labels = [(int(rows["c1s1"]["id"]), "SAI_1", "Lan"),
              (int(rows["c1s4"]["id"]), "Lan", "Minh")]
    if evidence in {"unchanged", "conflicting", "pinned_conflict"}:
        labels.append((int(rows["c1s3"]["id"]), "Lan", "Lan"))
    if evidence in {"conflicting", "pinned_conflict"}:
        labels.append((int(rows["c1s5"]["id"]), "Lan", "Lan"))
    db.commit_speaker_pass_chapter(chapter, labels, {}, seconds=0)
    reopened = ProjectDB(db.path)
    saved = {str(r["stable_id"]): r for r in reopened.list_segments()}
    expected = ("female", "young") if evidence in {"unchanged", "registry", "carried_registry", "pinned_conflict"} else ("unknown", "unknown")
    assert (saved["c1s1"]["gender"], saved["c1s1"]["age"]) == expected
    assert (saved["c1s4"]["gender"], saved["c1s4"]["age"]) == ("unknown", "unknown")
    if evidence == "unchanged":
        assert (saved["c1s3"]["gender"], saved["c1s3"]["age"]) == ("female", "young")
        assert resolve_gender([saved["c1s1"], saved["c1s3"]], list(saved.values()))[0] == "female"


def test_confirmed_traits_survive_chapter_commit_and_reopen(tmp_path: Path) -> None:
    db = make_project(tmp_path / "p")
    chapters = db.list_chapters()
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET speaker='Lan',gender='female',age='young' WHERE stable_id='c1s1'")
        conn.execute("UPDATE segments SET gender='male',age='elderly' WHERE stable_id='c2s1'")
    rows = {str(r["stable_id"]): r for r in db.list_segments()}
    db.commit_speaker_pass_chapter(int(chapters[0]["id"]), [(rows["c1s1"]["id"], "Lan", "Lan")], {}, seconds=0)
    db = ProjectDB(db.path)
    db.commit_speaker_pass_chapter(int(chapters[1]["id"]), [(rows["c2s1"]["id"], "SAI_4", "Lan")], {}, seconds=0)
    saved = {str(r["stable_id"]): r for r in ProjectDB(db.path).list_segments()}
    assert (saved["c2s1"]["gender"], saved["c2s1"]["age"]) == ("female", "young")
