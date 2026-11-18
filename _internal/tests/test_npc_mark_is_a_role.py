"""The "NPC" mark on a speaker label is a role marker, not part of the name (Lead 18-11).

"NPC Cha Rita" and "Cha Rita" are one person with one key, as before the castview branch: changing that changed the
speakers and the character book of every re-analysed book with such labels (All You Need Is Kill: 8 lines). Whether a
gold person is an NPC is kept in the gold cast (scripts/gold_fidelity GoldCast.npc), not in the name. A merge that a
trusted label holds back is recorded, never dropped silently. All names are synthetic.
"""
from __future__ import annotations

import json

from abook import speaker_labels
from abook.analysis import _canonical_speaker
from tests.test_gold_speaker_authority import pin
from tests.test_nobody_calls_their_own_name import _project


def test_the_analysis_drops_the_npc_mark_before_a_latin_name_only() -> None:
    assert _canonical_speaker("NPC Torvin Bell") == "Torvin Bell"
    assert _canonical_speaker("NPC: Torvin") == "Torvin"
    assert _canonical_speaker("NPC bác gác cổng") == "NPC bác gác cổng", "nhãn mô tả tiếng Việt giữ nguyên như trước"
    assert _canonical_speaker("narrator") == "NARRATOR"


def test_trusted_labels_key_the_npc_and_the_named_person_alike() -> None:
    key = speaker_labels.name_key
    assert key("NPC Torvin") == key("npc: torvin") == key("Npc_Torvin") == key("Torvin")
    labels = speaker_labels.SpeakerLabels({"s1": {"kind": "dialogue", "speaker": "NPC bác gác cổng", "text_sha256": "h"}})
    row = {"stable_id": "s1", "text_sha256": "h"}
    assert labels.allows(row, "Npc Bác Gác Cổng")
    assert labels.allows(row, "Bác Gác Cổng")
    assert not labels.allows(row, "Bác Bán Hàng")


def _events(db, code: str) -> list[dict]:
    with db.connect() as conn:
        return [json.loads(row["details_json"]) for row in
                conn.execute("SELECT details_json FROM runtime_events WHERE code=?", (code,))]


def test_merging_npc_x_into_x_on_a_gold_project_moves_every_line(tmp_path) -> None:
    """Gộp "NPC X" vào "X" (người nghe hay bước gom tên) trên dự án tiêm gold: mọi câu đi theo, không câu nào bị lọc."""
    db = _project(tmp_path / "book", [(1, "dialogue", "“Mở cổng kho.”", "NPC Torvin", "male"),
                                      (2, "dialogue", "“Đèn đã tắt.”", "NPC Torvin", "male"),
                                      (3, "dialogue", "“Tôi giữ chìa.”", "Torvin", "male")])
    pin(db)
    assert db.rewrite_speaker("NPC Torvin", "Torvin") == 2
    assert [row["speaker"] for row in db.list_segments()] == ["Torvin", "Torvin", "Torvin"]
    assert _events(db, "SPEAKER_REWRITE_HELD_BY_LABEL") == []


def test_a_merge_held_back_by_a_trusted_label_is_recorded(tmp_path) -> None:
    db = _project(tmp_path / "book", [(1, "dialogue", "“Mở cổng kho.”", "Torvin", "male"),
                                      (2, "dialogue", "“Đèn đã tắt.”", "Torvin", "male")])
    pin(db, [0])
    assert db.rewrite_speaker("Torvin", "Mirva") == 1
    assert [row["speaker"] for row in db.list_segments()] == ["Torvin", "Mirva"]
    held = _events(db, "SPEAKER_REWRITE_HELD_BY_LABEL")
    assert held == [{"from": "Torvin", "to": "Mirva", "stable_ids": ["s0"], "held": 1}]
