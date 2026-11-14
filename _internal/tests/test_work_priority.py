"""Original, model-free review snapshots and real project invalidation."""
import copy
import itertools
import json
import sqlite3
from pathlib import Path

from abook.listener_overrides import request_speaker
from abook.webui import work_priority
from abook.webui.work_items import work_items, work_view
from tests.test_voice_review_range import review_book

CONTRACT = Path(__file__).parent / "fixtures/work_priority/contract.json"


def test_permutations_ties_and_shared_contract():
    fixture = json.loads(CONTRACT.read_text(encoding="utf-8"))
    before = copy.deepcopy(fixture)
    for cards in itertools.permutations(fixture["cards"]):
        items = work_priority.rank(list(cards), fixture["rows"], set(fixture["upcoming"]))
        assert [item["key"] for item in items] == fixture["order"]
        assert items == fixture["items"]
    assert fixture == before
    first = fixture["items"][0]["priority"]
    assert (first["lines"], first["recordedLines"], first["recordedChapters"], first["estimatedActions"]) == (2, 1, 1, 1)
    assert len(fixture["cases"]) == 10


def test_duplicate_ids_equivalent_decisions_and_distinct_pending_states():
    fixture = json.loads(CONTRACT.read_text(encoding="utf-8"))
    item = fixture["cards"][0]
    duplicate = {**item, "key": "zz-duplicate", "lines": item["lines"] * 2}
    items = work_priority.rank([duplicate, item], fixture["rows"], {2})
    assert len(items) == 1 and items[0]["priority"]["lines"] == 2
    assert items[0]["priority"]["overlapLines"] == 0
    assert len(work_priority.rank([duplicate], fixture["rows"], {2})[0]["lines"]) == 2
    pending = {**item, "key": "pending", "requested": "Lan", "undo": {"endpoint": "speaker", "decisions": []}}
    refused = {**item, "key": "refused", "refused": {"section": "speakers", "key": "b", "requestedAt": 1}}
    items = work_priority.rank([item, pending, refused], fixture["rows"], {2})
    assert len(items) == 3
    assert next(x for x in items if x["key"] == "pending")["undo"] == pending["undo"]
    assert next(x for x in items if x["key"] == "refused")["refused"] == refused["refused"]


def test_same_assignment_combines_candidates_and_keeps_context_and_voice_tools():
    fixture = json.loads(CONTRACT.read_text(encoding="utf-8"))
    item = fixture["cards"][0]
    role = {**item, "key": "role", "kind": "unnamed", "suggestedName": "Người gác",
            "pickVoice": {"name": "MAI"}, "choices": [{"label": "Hạ", "value": "HA"}]}
    remote = {**item, "contextLines": item["lines"], "contextExamples": []}
    items = work_priority.rank([remote, role], fixture["rows"], {2})
    assert len(items) == 1
    assert {choice["value"] for choice in items[0]["choices"]} == {"HA", "LAN"}
    assert items[0]["suggestedName"] == "Người gác" and items[0]["contextLines"] == remote["lines"]
    assert items[0]["priority"]["estimatedActions"] == 1


def test_urgency_precedes_impact_per_action_and_tentative_only_breaks_equal_benefit():
    cards = [{"kind": "audio", "key": "audio", "affected": 10, "chapters": [1]},
             {"kind": "gender", "key": "voice", "affected": 6, "chapters": [1], "askLast": True},
             {"kind": "speaker", "key": "urgent", "affected": 1, "chapters": [2]}]
    assert [item["key"] for item in work_priority.rank(cards, {}, {2})] == ["urgent", "voice", "audio"]


def test_scope_count_is_not_example_count_and_unknown_is_not_zero():
    fixture = json.loads(CONTRACT.read_text(encoding="utf-8"))
    item = {**fixture["cards"][0], "lines": [{"stableId": "missing", "textSha256": "h"}]}
    result = work_priority.rank([item], fixture["rows"], {2})[0]["priority"]
    assert result["lines"] == 1 and result["recordedLines"] is None and result["recordedChapters"] is None
    item = {"kind": "audio", "key": "audio:1", "affected": 20, "examples": [{"chapterId": 1}]}
    result = work_priority.rank([item], fixture["rows"], set())[0]["priority"]
    assert result["lines"] == 20 and result["recordedLines"] is None and result["estimatedActions"] == 2


def test_upcoming_changes_after_other_window_and_no_projection_writes(tmp_path):
    project = review_book(tmp_path)
    db_path = project / "project.sqlite3"
    before = db_path.read_bytes()
    first = work_view(project)
    assert first == work_view(project)
    assert all(item.get("priority") for item in first["items"])
    assert before == db_path.read_bytes()
    with sqlite3.connect(db_path) as db:
        db.execute("UPDATE chapters SET status='completed'")
        db.execute("UPDATE segments SET wav_path='recorded.wav' WHERE stable_id='b'")
    second = work_view(project)
    caller = next(item for item in second["items"] if item["kind"] == "caller")
    assert caller["priority"]["upcoming"] is False
    assert caller["priority"]["recordedLines"] == 1
    request_speaker(project, "b", "sha-b", "LUCIEN", now=42)
    third = work_view(project)
    caller = next(item for item in third["items"] if item["kind"] == "caller")
    assert caller["requested"] and caller["undo"]
    assert caller["priority"]["upcoming"] is False
    assert work_items(project) == third


def test_missing_audio_column_and_chapter_status_are_unknown(tmp_path):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("CREATE TABLE segments(stable_id,chapter_id,text,speaker);"
                     "CREATE TABLE chapters(id,chapter_index);"
                     "INSERT INTO segments VALUES('a',1,'Một buổi tập.','MAI');")
    rows, upcoming = work_priority.read_snapshot(db)
    assert rows["a"]["recorded"] is None and not upcoming
