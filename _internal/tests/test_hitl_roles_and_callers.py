"""Chapter role and remote voice review use the existing nonblocking listener requests."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from abook.listener_overrides import read_overrides, request_speakers
from abook.webui.work_items import work_items
from tests.test_work_items import make_book

ROLE = "NPC_LOCAL::c00001::người gác"


def role_book(tmp_path: Path) -> Path:
    project = make_book(tmp_path)
    with sqlite3.connect(project / "project.sqlite3") as db:
        db.execute("UPDATE characters SET canonical_name=?, display_name='người gác', gender='male' WHERE id=3", (ROLE.upper(),))
        db.execute("UPDATE segments SET speaker=? WHERE id IN (4,5)", (ROLE,))
        db.execute("INSERT INTO chapters VALUES (2,2,'002')")
        db.execute("INSERT INTO segments (id,stable_id,chapter_id,seq,text,kind,speaker,status,text_sha256)"
                   " VALUES (20,'other-chapter',2,0,'Xin chào.','dialogue',?,'analyzed','sha-other')",
                   ("NPC_LOCAL::c00002::người gác",))
    return project


def local_card(project: Path) -> dict:
    return next(item for item in work_items(project)["items"]
                if item.get("suggestedName") and item.get("currentValue") == ROLE)


def test_local_role_names_and_voice_picker_only_cover_that_chapter(tmp_path: Path) -> None:
    card = local_card(role_book(tmp_path))
    assert card["affected"] == 2
    assert {line["stableId"] for line in card["lines"]} == {"d", "e"}
    assert card["chapters"] == [1]
    assert card["suggestedName"] == "Người gác chương 1"
    assert card["pickVoice"] == {"name": ROLE.upper(), "displayName": "người gác"}
    assert "chương này" in card["problem"]


def test_keeping_the_local_role_closes_its_review(tmp_path: Path) -> None:
    project = role_book(tmp_path)
    card = local_card(project)
    request_speakers(project, [(line["stableId"], line["textSha256"]) for line in card["lines"]], ROLE, now=10)
    assert not any(item.get("currentValue") == ROLE for item in work_items(project)["items"])


def test_local_role_does_not_reopen_lines_already_decided_in_a_cross_chapter_group(tmp_path: Path) -> None:
    project = role_book(tmp_path)
    with sqlite3.connect(project / "project.sqlite3") as db:
        db.execute("INSERT INTO segments (id,stable_id,chapter_id,seq,text,kind,speaker,status,text_sha256)"
                   " VALUES (21,'third-line',1,20,'Xin chào.','dialogue',?,'analyzed','sha-third')", (ROLE,))
    request_speakers(project, [("d", "sha-d")], "LUCIEN", now=10)
    card = local_card(project)
    assert card["affected"] == 2
    assert {line["stableId"] for line in card["lines"]} == {"e", "third-line"}
    assert "d" not in card["seen"]
    request_speakers(project, [(line["stableId"], line["textSha256"]) for line in card["lines"]], "HEIDI", now=11)
    assert read_overrides(project)["speakers"]["d"]["speaker"] == "LUCIEN"


def test_a_fully_split_local_role_stays_decided(tmp_path: Path) -> None:
    project = role_book(tmp_path)
    request_speakers(project, [("d", "sha-d")], "LUCIEN", now=10)
    request_speakers(project, [("e", "sha-e")], "HEIDI", now=11)
    assert not any(item.get("suggestedName") and item.get("currentValue") == ROLE
                   for item in work_items(project)["items"])


def test_more_affected_role_lines_rank_above_single_caller_lines(tmp_path: Path) -> None:
    project = role_book(tmp_path)
    with sqlite3.connect(project / "project.sqlite3") as db:
        db.execute("UPDATE segments SET text='Đầu dây bên kia có tiếng đáp.' WHERE id=1")
    cards = [item for item in work_items(project)["items"] if item.get("suggestedName") or item["kind"] == "caller"]
    assert [item["affected"] for item in cards] == sorted((item["affected"] for item in cards), reverse=True)
    assert cards[0]["affected"] == 2 and cards[-1]["affected"] == 1


@pytest.mark.parametrize("cue", [
    "Giọng nói vang lên qua điện thoại.", "Đầu dây bên kia im lặng rồi đáp.",
    "Một giọng nói từ ngoài cửa vang lên.", "Bộ đàm vang lên giữa đêm.",
])
def test_caller_review_explains_the_narration_cue_and_keeps_machine_default(tmp_path: Path, cue: str) -> None:
    project = make_book(tmp_path)
    with sqlite3.connect(project / "project.sqlite3") as db:
        db.execute("UPDATE segments SET text=? WHERE id=1", (cue,))
    card = next(item for item in work_items(project)["items"] if item["kind"] == "caller")
    assert card["lines"] == [{"stableId": "b", "textSha256": "sha-b"}]
    assert cue in card["problem"] and card["examples"][0]["before"] == cue
    assert card["currentValue"] == "HEIDI" and card["suggested"] is False
    assert "máy đề xuất" in card["keepLabel"]
    assert "phoneFilter" not in card
    request_speakers(project, [("b", "sha-b")], "HEIDI", now=10)
    assert not any(item["kind"] == "caller" for item in work_items(project)["items"])


def test_mentions_in_dialogue_and_other_chapters_do_not_create_remote_voice_reviews(tmp_path: Path) -> None:
    project = make_book(tmp_path)
    with sqlite3.connect(project / "project.sqlite3") as db:
        db.execute("UPDATE segments SET text='Đầu dây bên kia có ai không?' WHERE id=2")
        db.execute("INSERT INTO chapters VALUES(2,2,'002')")
        db.execute("INSERT INTO segments(id,chapter_id,seq,text,kind) VALUES(20,2,0,'Đầu dây bên kia.','narration')")
    assert not any(item["kind"] == "caller" for item in work_items(project)["items"])


def test_role_request_api_is_atomic_on_stale_source_and_never_writes_sqlite(tmp_path: Path) -> None:
    from abook.webui.library import Preferences, book_id
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import FakeRunner, _request

    project = role_book(tmp_path)
    preferences = Preferences(tmp_path / "prefs" / "p.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    headers = {"X-Ebook-Token": "t"}
    endpoint = f"/api/books/{book_id(project)}"
    before = (project / "project.sqlite3").read_bytes()
    try:
        status, data, _ = _request(server.port, "GET", endpoint + "/work", headers=headers)
        assert status == 200
        card = next(item for item in json.loads(data)["items"] if item.get("suggestedName") and item.get("currentValue") == ROLE)
        bad_lines = [card["lines"][0], {**card["lines"][1], "textSha256": "stale"}]
        status, _, _ = _request(server.port, "POST", endpoint + "/speaker", headers=headers, body={"lines": bad_lines, "speaker": "LUCIEN"})
        assert status == 400 and not read_overrides(project).get("speakers")
        status, data, _ = _request(server.port, "POST", endpoint + "/speaker", headers=headers, body={"lines": card["lines"], "speaker": "LUCIEN"})
        assert status == 200 and json.loads(data)["lines"] == 2
        assert set(read_overrides(project)["speakers"]) == {"d", "e"}
        assert (project / "project.sqlite3").read_bytes() == before
    finally:
        server.stop()


def test_group_request_survives_reopen_and_only_resets_affected_audio(tmp_path: Path) -> None:
    from abook.database import ProjectDB
    from tests.test_listener_speakers import _book, _segment
    from tests.test_listener_overrides import _Pipeline

    paths, db = _book(tmp_path)
    request_speakers(paths.root, [("c1s1", "sha-c1s1"), ("c1s2", "sha-c1s2")], "NATASHA", now=10)
    pipeline = _Pipeline(paths, ProjectDB(paths.db))
    assert pipeline._apply_listener_overrides() == {1}
    reopened = ProjectDB(paths.db)
    for stable_id in ("c1s1", "c1s2"):
        row = _segment(reopened, stable_id)
        assert row["speaker"] == "NATASHA" and row["wav_path"] is None and row["status"] == "analyzed"
    assert _segment(reopened, "c1s3")["status"] == "verified"
    assert _Pipeline(paths, reopened)._apply_listener_overrides() == set()


def test_naming_a_group_locks_one_gender_and_one_voice_for_all_its_lines(tmp_path: Path) -> None:
    from abook.config import build_settings
    from abook.character_registry import assert_voice_stability
    from abook.database import ProjectDB
    from tests.test_listener_speakers import _book, _segment
    from tests.test_listener_overrides import _Pipeline

    paths, db = _book(tmp_path)
    request_speakers(paths.root, [("c1s1", "sha-c1s1"), ("c1s2", "sha-c1s2")], "Người gác chương 1", now=10, new_gender="female")
    pipeline = _Pipeline(paths, ProjectDB(paths.db))
    pipeline.settings = build_settings()
    assert pipeline._apply_listener_overrides() == {1}
    rows = [_segment(db, stable_id) for stable_id in ("c1s1", "c1s2")]
    assert {row["canonical_name"] for row in rows} == {"NGƯỜI GÁC CHƯƠNG 1"}
    assert {row["gender"] for row in rows} == {"female"}
    assert len({row["voice_key"] for row in rows}) == 1
    assert _segment(db, "c1s3")["status"] == "verified"
    assert_voice_stability(ProjectDB(paths.db))


def test_registered_chapter_voice_action_survives_the_optional_book_merge(tmp_path: Path) -> None:
    project = role_book(tmp_path)
    cards = work_items(project)["items"]
    merged = next(item for item in cards if item["key"] == "unnamed-role:người gác")
    local = next(item for item in cards if item.get("currentValue") == ROLE and item.get("pickVoice"))
    assert {line["stableId"] for line in merged["lines"]} == {"d", "e", "g", "other-chapter"}
    assert {line["stableId"] for line in local["lines"]} == {"d", "e"}
    assert local["pickVoice"]["name"] == ROLE.upper()
    assert "pickVoice" not in merged
