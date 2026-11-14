"""Original metadata fixtures shared with TypeScript, QML and Kotlin."""
import json
import sqlite3
from pathlib import Path

import pytest

from abook.webui.casting_review import casting_chapter
from abook.webui.script_scope import project_scenes, scope_lines, scope_revision
from tests.test_casting_review import make_book

FIXTURE = json.loads((Path(__file__).parent / "fixtures/script_scope.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda case: case["name"])
def test_shared_scope_contract(case):
    lines = [{**line, "scene": None} if case.get("noMarkers") else line for line in FIXTURE["lines"]]
    candidates = scope_lines(lines, case["anchor"], case["mode"], case["start"], case["end"])
    assert [line["stableId"] for line in candidates] == case["ids"]
    selected = [line for line in candidates if bool(line["wish"] or line["lineWish"]) == (line["stableId"] in case.get("toggled", []))]
    assert [line["stableId"] for line in selected] == case["selected"]


def test_marker_is_after_narration_and_changes_invalidate_preview():
    lines = FIXTURE["lines"]
    projected = project_scenes(lines)
    assert [line["scene"] for line in projected[:13]] == [1] * 12 + [2]
    moved = [{**line, "sceneBreak": line["seq"] == 3} for line in lines]
    other = project_scenes(moved)
    assert other[3]["scene"] == 1 and other[4]["scene"] == 2
    assert scope_revision(projected) != scope_revision(other)
    changed = [{**line, "textSha256": "changed"} if line["seq"] == 0 else line for line in projected]
    assert scope_revision(changed) != scope_revision(projected)
    assert all(line["scene"] is None for line in project_scenes([{**line, "sceneBreak": False} for line in lines]))


def test_casting_projects_markers_and_opaque_npc_identity_without_writes(tmp_path):
    project = make_book(tmp_path)
    role = "NPC_LOCAL::c00001::người gác"
    with sqlite3.connect(project / "project.sqlite3") as db:
        db.execute("UPDATE segments SET speaker=? WHERE stable_id IN ('b','d','e','h')", (role,))
        db.execute("UPDATE segments SET scene_break=1 WHERE stable_id='d'")
        db.execute("UPDATE segments SET speaker='NPC_LOCAL::c00002::người gác' WHERE stable_id='j'")
    db_before = (project / "project.sqlite3").read_bytes()
    view = casting_chapter(project, 1)
    selected = scope_lines(view["lines"], "b", "scene", 0, 99)
    assert [line["stableId"] for line in selected] == ["b", "d"]
    assert [line["stableId"] for line in scope_lines(view["lines"], "e", "scene", 0, 99)] == ["e", "h"]
    assert (project / "project.sqlite3").read_bytes() == db_before
    assert not (project / "overrides.json").exists()
    second = casting_chapter(project, 2)
    assert all(line["stableId"] not in ("b", "d", "e", "h") for line in second["lines"])
    with sqlite3.connect(project / "project.sqlite3") as db:
        db.execute("UPDATE segments SET scene_break=0 WHERE stable_id='d'")
    fresh = casting_chapter(project, 1)
    assert fresh["scopeRevision"] != view["scopeRevision"]
    assert all(line["scene"] is None for line in fresh["lines"])


def test_empty_or_unknown_modes_do_not_choose_anything():
    assert scope_lines([], "x", "chapter", 0, 99) == []
    assert scope_lines(FIXTURE["lines"], "s000", "bad", 0, 99) == []


def test_scope_posts_only_current_refs_and_changed_source_rejects_entire_group(tmp_path):
    from abook.listener_overrides import read_overrides, speaker_requests
    from abook.webui.library import Preferences, book_id
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import FakeRunner, _request

    project = make_book(tmp_path)
    with sqlite3.connect(project / "project.sqlite3") as db:
        db.execute("UPDATE segments SET scene_break=1 WHERE stable_id='d'")
    preferences = Preferences(tmp_path / "prefs/preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs/l.json"))
    server = Server(app, port=0).start()
    headers = {"X-Ebook-Token": "t", "Content-Type": "application/json"}
    endpoint = f"/api/books/{book_id(project)}/speaker"
    try:
        lines = scope_lines(casting_chapter(project, 1)["lines"], "c", "scene", 0, 99)
        assert [line["stableId"] for line in lines] == ["c", "d"]
        body = {"lines": [{"stableId": line["stableId"], "textSha256": line["textSha256"]} for line in lines],
                "speaker": "Khách mới", "newGender": "unknown", "seen": {line["stableId"]: "" for line in lines}}
        with sqlite3.connect(project / "project.sqlite3") as db:
            db.execute("UPDATE segments SET text_sha256='changed' WHERE stable_id='d'")
        status, _data, _headers = _request(server.port, "POST", endpoint, body=body, headers=headers)
        assert status == 400
        assert speaker_requests(read_overrides(project)) == []
        body["lines"][1]["textSha256"] = "changed"
        before = (project / "project.sqlite3").read_bytes()
        status, data, _headers = _request(server.port, "POST", endpoint, body=body, headers=headers)
        assert status == 200 and json.loads(data)["lines"] == 2
        assert [entry["stable_id"] for entry in speaker_requests(read_overrides(project))] == ["c", "d"]
        assert (project / "project.sqlite3").read_bytes() == before
        assert not (project / "aliases.json").exists()
    finally:
        server.stop()
