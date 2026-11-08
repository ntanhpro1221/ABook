"""Casting callers retain the attribution evidence required by validation."""
import pytest

from abook.character_registry import build_registry_and_cast
from abook.config import build_settings
from abook.database import ProjectDB
from abook.analysis import local_speaker_label
from tests.test_character_casting import _repair_db


@pytest.mark.parametrize("confidence", [0.6, 0.95])
def test_generic_crowd_speech_tag_survives_casting_and_reopen(tmp_path, confidence):
    db = _repair_db(tmp_path, [
        {"stable_id": "call", "seq": 0, "paragraph_index": 0,
         "text": "“Đồng ý!”", "kind": "dialogue",
         "speaker": "NPC_LOCAL::c00001::test::người phụ nữ", "gender": "female",
         "age": "adult", "confidence": confidence},
        {"stable_id": "tag", "seq": 1, "paragraph_index": 0,
         "text": "Người dân hét lớn.", "kind": "narration", "speaker": "NARRATOR"},
    ])
    build_registry_and_cast(db, build_settings(), lambda _: None)
    reopened = ProjectDB(db.path)
    row = next(r for r in reopened.list_segments() if r["stable_id"] == "call")
    assert local_speaker_label(row["speaker"]) == "người dân"
    assert row["gender"] == "unknown"
    assert row["voice_profile_id"] is not None
    before = (row["speaker"], row["canonical_character_id"], row["voice_profile_id"])
    build_registry_and_cast(reopened, build_settings(), lambda _: None)
    row = next(r for r in reopened.list_segments() if r["stable_id"] == "call")
    assert (row["speaker"], row["canonical_character_id"], row["voice_profile_id"]) == before


@pytest.mark.parametrize("line_hint", ["dialogue", "narration"])
@pytest.mark.parametrize("tag_hint", ["narration", "dialogue"])
def test_accepted_speech_tag_keeps_an_individual_out_of_a_later_crowd(tmp_path, line_hint, tag_hint):
    speaker = "NPC_LOCAL::c00001::test::người phụ nữ"
    db = _repair_db(tmp_path, [
        {"stable_id": "tag", "seq": 0, "paragraph_index": 0,
         "text": "Alisa nói:", "kind": "narration", "kind_hint": tag_hint, "speaker": "NARRATOR"},
        {"stable_id": "line", "seq": 1, "paragraph_index": 0,
         "text": "“Đồng ý!”", "kind": "dialogue", "kind_hint": line_hint,
         "speaker": speaker, "gender": "female", "age": "adult"},
        {"stable_id": "crowd", "seq": 2, "paragraph_index": 1,
         "text": "Đám đông hét lớn.", "kind": "narration", "speaker": "NARRATOR"},
    ])
    build_registry_and_cast(db, build_settings(), lambda _: None)
    row = next(r for r in ProjectDB(db.path).list_segments() if r["stable_id"] == "line")
    assert row["speaker"] == speaker
    assert row["gender"] == "female"
