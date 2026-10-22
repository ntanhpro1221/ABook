"""musedge: shared boundary cases, consumed by Python, JVM and the web player."""
import json
from pathlib import Path

import pytest

from abook.webui import book_edits, music_mix, music_plan, music_scenes, music_select
from abook.webui.music_catalog import MusicCatalog
from tests.catalog_signing import TEST_PUBLIC_KEY
from tests.test_webui_listen_and_sync import make_project

FIXTURE = Path(__file__).parent / "fixtures/music/edge_cases.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES["pinCases"], ids=lambda c: str(c["seconds"]))
def test_pinning_a_shorter_or_longer_track_on_a_tail_keeps_the_next_entry_time(case):
    applied = book_edits.apply_music(case["music"], case["edits"])
    assert applied == case["applied"]
    cues = music_plan.packaged_cues(applied, 1)
    assert not cues[0].get("tail")
    tracks = {name: dict(info) for name, info in applied["tracks"].items()}
    tracks[cues[0]["track"]]["seconds"] = case["seconds"]
    timeline = music_mix.music_timeline(cues, None, tracks)
    following = [part for part in timeline if part["track"] == cues[1]["track"]]
    assert following[0]["from"] == case["expectedNext"]
    assert all(part["from"] < part["to"] for part in timeline)


def test_loop_end_past_eof_is_clamped_even_when_end_less_crossfade_is_valid():
    case = CASES["loop"]
    bounds = music_mix.track_loop_bounds(case, case["seconds"])
    assert bounds.end == bounds.loop_end == case["expectedEnd"]
    assert bounds.loop_start == case["loopStart"]
    assert music_mix.loop_schedule(bounds, 110)[0][0] == case["expectedOpen"]


@pytest.mark.parametrize("case", CASES["selectorCases"], ids=lambda c: c["mode"])
def test_selector_spread_and_variance_match_shared_kotlin_ranking_and_choices(case):
    tracks = case["tracks"]
    ranked = music_select.rank(case["scenes"][0], lambda v, a: tracks, book_key=case["bookKey"], limit=10)
    assert [{"link": t["link"], "score": t["score"]} for t in ranked] == case["rank"]
    assert [t["link"] for t in ranked] != case["plainOrder"], "fixture must detect dropping sd/vetVar"
    chosen = music_select.choose(case["scenes"], lambda v, a: tracks, book_key=case["bookKey"],
                                 track_info=lambda link: next(t for t in tracks if t["link"] == link))
    assert [s["link"] for s in chosen] == case["chosen"]


def test_a_chapter_containing_only_notes_currently_gets_a_normal_music_scene():
    notes = CASES["notes"]
    script = {key: notes[key] for key in ("chapterId", "segments")}
    scenes = music_scenes.chapter_scenes(script)
    assert scenes == notes["expectedScenes"]
    assert len(scenes) == 1 and scenes[0]["end"] == 3.965 and scenes[0]["lines"] == 2
    track = {"link": "https://example.invalid/calm.mp3", "valence": .15, "arousal": -.55, "duration": 240, "source": "incompetech"}
    chosen = music_select.choose(scenes, lambda v, a: [track], book_key="notes")
    assert music_plan.chapter_cues({"enabled": True, "scenes": chosen}, 1)[0]["link"] == track["link"]


def test_a_valid_empty_catalog_builds_silent_scenes_and_no_player_cues(tmp_path, monkeypatch):
    catalog = MusicCatalog(tmp_path / "catalog-cache", str(FIXTURE.parent / "empty_catalog"), public_key=TEST_PUBLIC_KEY)
    assert catalog.manifest()["revision"] == "edge-empty"
    assert catalog.near(.15, -.55) == []
    project = make_project(tmp_path)
    # Exercise the normal script -> scenes -> selector -> persisted plan -> player response path, without loading a model.
    monkeypatch.setattr(music_plan.music_nnlite, "model", lambda: None)
    monkeypatch.setattr(music_plan.music_moods, "load", lambda root: None)
    monkeypatch.setattr(music_plan.music_bounds, "load", lambda root: {})
    plan = music_plan.build(project, catalog.near, catalog.lookup, catalog_revision="edge-empty")
    assert plan["scenes"] and all(s["link"] is None for s in plan["scenes"])
    assert plan["tracks"] == {}
    assert music_plan.read_plan(project) == plan
    for chapter in {s["chapterId"] for s in plan["scenes"]}:
        assert music_plan.chapter_cues(plan, chapter) == CASES["emptyResponse"]["cues"] == []
    assert music_plan.package(project, [1, 2], lambda link: pytest.fail("silent cue must not request an audio file")) is None
