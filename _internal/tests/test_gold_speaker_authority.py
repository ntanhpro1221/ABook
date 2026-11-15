"""Original examples: answer labels win every family of speaker repair."""
from __future__ import annotations

import copy
import json

import pytest

from abook import analysis as A
from abook import character_registry as C
from abook import speaker_labels as L
from abook.config import build_settings
from abook.database import EXPLICIT_ATTRIBUTION_NOTE, ProjectDB
from tests.test_nobody_calls_their_own_name import _project


def batch(lines):
    rows, result = [], {}
    for i, (paragraph, kind, text, speaker) in enumerate(lines):
        sid = f"s{i}"
        rows.append({"stable_id": sid, "chapter_id": 1, "seq": i, "paragraph_index": paragraph,
                     "text": text, "text_sha256": f"hash{i}", "kind_hint": kind})
        result[sid] = {"kind": kind, "speaker": speaker, "gender": "unknown", "age": "unknown",
                       "confidence": .5, "emotion": "neutral", "intensity": 0,
                       "pace": "normal", "volume": "normal", "notes": "", "personality_hint": ""}
    return rows, result


@pytest.mark.parametrize("repair,lines,target", [
    (A._repair_explicit_attribution, [(0, "narration", "Mirva nói:", "NARRATOR"),
      (0, "dialogue", "“Hộp mực còn đầy.”", "Tavin")], "s1"),
    (A._repair_addressee_speakers, [(0, "dialogue", "“Mirva, cất lọ mực này đi!”", "Mirva")], "s0"),
    (A._repair_same_paragraph_speakers, [(0, "dialogue", "“Đèn màu tím.”", "Mirva"),
      (0, "dialogue", "“Bản đồ màu xanh.”", "Tavin")], "s1"),
    (A._repair_continued_dialogue_speakers, [(0, "dialogue", "“Tôi đếm từng lọ mực", "Mirva"),
      (1, "dialogue", "rồi ghi vào sổ.”", "Tavin")], "s1"),
    (A._repair_in_sentence_quote_speakers, [(0, "narration", "Trên hộp ghi", "NARRATOR"),
      (0, "dialogue", "“mực tím”", "Mirva"), (0, "narration", ", bên dưới có mã hàng.", "NARRATOR")], "s1"),
])
def test_each_batch_repair_has_a_live_trigger_and_skips_the_answer(repair, lines, target):
    rows, original = batch(lines)
    if repair is A._repair_same_paragraph_speakers:
        A._record_host_note_marker(original["s0"], EXPLICIT_ATTRIBUTION_NOTE)
    ordinary = copy.deepcopy(original)
    repair(rows, ordinary)
    assert ordinary[target]["speaker"] != original[target]["speaker"], "fixture must exercise a real overwrite"
    protected = copy.deepcopy(original)
    protected[target][L.MARKER] = True
    before = copy.deepcopy(protected[target])
    repair(rows, protected)
    assert protected[target] == before


def pin(db, indexes=None, identities=None):
    rows = list(db.list_segments())
    chosen = rows if indexes is None else [rows[i] for i in indexes]
    L.install(db, {str(row["stable_id"]): {"kind": str(row["kind"]), "speaker": str(row["speaker"])}
                   for row in chosen}, identities or {})
    return rows


@pytest.mark.parametrize("repair,lines", [
    (C._repair_dialogue_turns_by_lead_in, [(1, "dialogue", "“Tôi mang hộp mực.”", "TAVIN", "female"),
      (2, "dialogue", "“Cất chiếc đèn đi.”", "MIRVA", "female"),
      (3, "narration", "Tavin đáp.", "NARRATOR", "unknown")]),
    (C._repair_dialogue_turns_by_address, [(1, "dialogue", "“Mirva, giữ đèn giúp tôi!”", "MIRVA", "female"),
      (2, "dialogue", "“Tôi giữ bản đồ.”", "TAVIN", "female"),
      (3, "dialogue", "“Cầm chắc tay nhé.”", "TAVIN", "female"),
      (4, "dialogue", "“Được, tôi hiểu rồi.”", "MIRVA", "female")]),
    (C._repair_cross_batch_dialogue_continuations, [(1, "dialogue", "“Tôi đếm từng lọ mực", "MIRVA", "female"),
      (2, "dialogue", "rồi ghi vào sổ.”", "TAVIN", "female")]),
    (C._repair_crowd_dialogue_blocks, [(1, "dialogue", "“Mở cổng kho!”", "NPC_LOCAL::c00001::b1::người phụ nữ", "female"),
      (2, "narration", "Đám đông hô lớn.", "NARRATOR", "unknown")]),
])
def test_each_registry_repair_cannot_overwrite_pinned_rows(tmp_path, repair, lines):
    def run(db):
        if repair in (C._repair_dialogue_turns_by_lead_in, C._repair_dialogue_turns_by_address):
            repair(db, lambda _: None, {})
        else:
            repair(db, lambda _: None)
    ordinary = _project(tmp_path / "ordinary", lines)
    before = [str(r["speaker"]) for r in ordinary.list_segments()]
    run(ordinary)
    assert [str(r["speaker"]) for r in ordinary.list_segments()] != before
    db = _project(tmp_path / "answer", lines)
    pin(db)
    db = ProjectDB(db.path)  # Protection survives reopening, without a schema change.
    run(db)
    assert [str(r["speaker"]) for r in db.list_segments()] == before


def test_only_explicit_identity_links_allow_name_merges_and_the_rest_of_the_book_still_repairs(tmp_path):
    db = _project(tmp_path / "book", [(1, "dialogue", "“Hộp mực đã đến.”", "Mirva", "female"),
                             (2, "dialogue", "“Chiếc đèn còn sáng.”", "Mirva", "female")])
    rows = pin(db, [0], {"Mirva": "Mirva Solin", "Mirva Solin": "Mirva Solin"})
    assert db.rewrite_speaker("Mirva", "Tavin") == 1
    assert [r["speaker"] for r in db.list_segments()] == ["Mirva", "Tavin"]
    assert db.rewrite_speaker("Mirva", "Solin Mirva") == 1
    assert db.get_segment(int(rows[0]["id"]))["speaker"] == "Solin Mirva"


def test_a_guessed_short_name_merge_cannot_merge_two_answer_people(tmp_path):
    db = _project(tmp_path / "book", [(1, "dialogue", "“Tôi đếm mực.”", "Mirva", "female"),
                             (2, "dialogue", "“Tôi đếm đèn.”", "Mirva Solin", "female")])
    pin(db)
    C._canonicalize_named_speakers(db, lambda _: None)
    assert {r["speaker"] for r in db.list_segments()} == {"Mirva", "Mirva Solin"}


def test_source_binding_and_model_json_cannot_forge_authority(tmp_path):
    rows, values = batch([(0, "narration", "Mirva nói:", "NARRATOR"),
                           (0, "dialogue", "“Đèn vẫn sáng.”", "Tavin")])
    payload = {"segments": [{"id": sid, **data, L.MARKER: True} for sid, data in values.items()]}
    assert A._validate(rows, payload)["s1"]["speaker"] == "Mirva"
    authority = L.SpeakerLabels({"s1": {"speaker": "Tavin", "text_sha256": "hash1"}})
    answer = A._validate(rows, payload, speaker_labels=authority)["s1"]
    assert answer["speaker"] == "Tavin" and L.MARKER not in answer
    rows[1]["text_sha256"] = "changed"
    with pytest.raises(ValueError, match="source hash"):
        A._validate(rows, payload, speaker_labels=authority)


def test_bracket_first_person_and_near_name_rules_cannot_redirect_answers(tmp_path):
    db = _project(tmp_path / "book", [(1, "dialogue", "『Chiếc hộp có mực tím.』", "Mirva", "female"),
                             (2, "thought", "(Cần kiểm đèn.)", "Tôi", "female"),
                             (3, "dialogue", "“Tavin mở bản đồ.”", "Tavinn", "female")])
    pin(db)
    (db.path.parent / "bracket_rule.json").write_text(json.dumps({"speaker": "Tavin"}), encoding="utf-8")
    settings = build_settings(overrides={"voices": {"first_person_identity": "Tavin"}})
    C.resolve_first_person_labels(db, settings, lambda _: None)
    C.snap_labels_to_chapter_names(db, settings, lambda _: None)
    C._canonicalize_named_speakers(db, lambda _: None)
    assert {r["speaker"].casefold() for r in db.list_segments()} == {"mirva", "tôi", "tavinn"}


@pytest.mark.parametrize("repair,first,second", [
    (C._merge_local_speakers_with_named_identity, "NPC_LOCAL::c00001::b1::người phụ nữ", "Người phụ nữ đeo khăn đỏ"),
    (C._merge_adjacent_local_speakers, "NPC_LOCAL::c00001::b1::Meravi", "NPC_LOCAL::c00001::b2::Meravi"),
])
def test_local_identity_merges_need_answer_identity_links(tmp_path, repair, first, second):
    lines = [(1, "dialogue", "“Đèn vừa được sửa.”", first, "female"),
             (2, "dialogue", "“Mực đã được thay.”", second, "female")]
    ordinary = _project(tmp_path / "ordinary", lines)
    repair(ordinary, lambda _: None)
    assert len({r["speaker"] for r in ordinary.list_segments()}) == 1
    protected = _project(tmp_path / "protected", lines)
    pin(protected)
    repair(protected, lambda _: None)
    assert [r["speaker"] for r in protected.list_segments()] == [first, second]


def test_unattributed_thought_normalization_skips_only_pinned_rows(tmp_path):
    db = _project(tmp_path / "book", [(1, "thought", "(Kiểm tra mực.)", "UNKNOWN", "unknown"),
                                     (2, "thought", "(Kiểm tra đèn.)", "UNKNOWN", "unknown")])
    pin(db, [0])
    assert db.normalize_thought_speakers() == 1
    assert [r["speaker"] for r in db.list_segments()] == ["UNKNOWN", "NARRATOR"]


def test_speaker_pass_preserves_answers_and_can_still_label_other_rows(tmp_path):
    db = _project(tmp_path / "book", [(1, "dialogue", "“Đem bản đồ ra đây.”", "Meravi", "female"),
                                     (2, "dialogue", "“Đặt cạnh hộp mực.”", "Meravi", "female")])
    rows = pin(db, [0])
    with db.connect() as conn:
        conn.execute("UPDATE segments SET status='analyzed'")
    assert db.commit_speaker_pass_chapter(int(rows[0]["chapter_id"]),
           [(int(r["id"]), "Meravi", "Tavin") for r in rows], {"calls": 2}, seconds=0) == 1
    assert [r["speaker"] for r in db.list_segments()] == ["Meravi", "Tavin"]


def test_a_failed_name_rewrite_rolls_back_and_reopens_with_the_same_answers(tmp_path):
    import sqlite3

    db = _project(tmp_path / "book", [(1, "dialogue", "“Mực tím còn đủ.”", "Meravi", "female"),
                                     (2, "dialogue", "“Đèn cũng còn đủ.”", "Meravi", "female")])
    pin(db)
    with db.connect() as conn:
        conn.execute("CREATE TRIGGER fail_second_label BEFORE UPDATE OF speaker ON segments "
                     "WHEN OLD.stable_id='s1' BEGIN SELECT RAISE(ABORT,'simulated write failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match="simulated write failure"):
        db.rewrite_speaker("Meravi", "MERAVI")
    # Remove only the injected fault; production rejects extra schema objects.
    with db.connect() as conn:
        conn.execute("DROP TRIGGER fail_second_label")
    reopened = ProjectDB(db.path)
    assert [r["speaker"] for r in reopened.list_segments()] == ["Meravi", "Meravi"]
    assert reopened.rewrite_speaker("Meravi", "Tavin") == 0


def test_a_protected_continuation_is_the_anchor_for_the_next_unlabeled_line(tmp_path):
    db = _project(tmp_path / "book", [(1, "dialogue", "“Đếm từng lọ mực", "Meravi", "female"),
                                     (2, "dialogue", "và kiểm từng chiếc đèn", "Tavin", "female"),
                                     (3, "dialogue", "trước khi khóa cửa.”", "UNKNOWN", "unknown")])
    pin(db, [1])
    C._repair_cross_batch_dialogue_continuations(db, lambda _: None)
    assert [r["speaker"] for r in db.list_segments()] == ["Meravi", "Tavin", "Tavin"]


def test_a_structural_heading_lock_cannot_replace_an_answer_speaker():
    rows, values = batch([(0, "dialogue", "Chương 1", "Meravi")])
    rows[0]["source_role"] = "chapter_heading"
    rows[0]["seq"] = 0
    rows[0]["kind_hint"] = "narration"
    ordinary = copy.deepcopy(values)
    assert A._apply_host_structural_locks(rows, ordinary)
    assert ordinary["s0"]["speaker"] == "NARRATOR"
    authority = L.SpeakerLabels({"s0": {"speaker": "Meravi", "text_sha256": "hash0"}})
    assert A._apply_host_structural_locks(rows, values, speaker_labels=authority) == ()
    assert values["s0"]["speaker"] == "Meravi"


@pytest.mark.parametrize("gold,kind,speaker", [("Meravi", "dialogue", "Tavin"), ("Meravi", "narration", "Meravi"),
                                               ("NARRATOR", "narration", "Meravi")])
def test_an_analysis_write_cannot_undo_an_answer_even_through_its_kind(tmp_path, gold, kind, speaker):
    db = _project(tmp_path / "book", [(1, "dialogue", "“Cất hộp mực.”", gold, "female")])
    rows = pin(db)
    with pytest.raises(ValueError, match="authoritative speaker"):
        db.update_analysis(int(rows[0]["id"]), {"kind": kind, "speaker": speaker}, .5)
    assert ProjectDB(db.path).get_segment(int(rows[0]["id"]))["speaker"] == gold


def test_a_batch_analysis_write_rolls_back_if_any_answer_would_be_overwritten(tmp_path):
    db = _project(tmp_path / "book", [(1, "dialogue", "“Đếm lọ mực.”", "Meravi", "female"),
                                     (2, "dialogue", "“Đếm chiếc đèn.”", "Meravi", "female")])
    rows = pin(db, [1])
    db.lock_analysis_model(model_name="fake", model_digest="sha256:fake")
    _, values = batch([(0, "dialogue", "“Đếm lọ mực.”", "Tavin"),
                       (1, "dialogue", "“Đếm chiếc đèn.”", "Tavin")])
    A._canonicalize_analysis_notes(values)
    with pytest.raises(ValueError, match="authoritative speaker"):
        db.update_analysis_batch_with_event(
            [{"segment_id": int(row["id"]), "stable_id": row["stable_id"], "text_sha256": row["text_sha256"],
              "data": values[str(row["stable_id"])]} for row in rows],
            low_confidence_threshold=.5, event_level="info", event_code="TEST", event_message="test",
            event_details={}, analysis_model_name="fake", analysis_model_digest="sha256:fake")
    assert [r["speaker"] for r in ProjectDB(db.path).list_segments()] == ["Meravi", "Meravi"]
