"""Rãnh nhạc nền của một cuốn (webui/music_plan.py): máy dựng, người dùng sửa, dựng lại vẫn giữ lựa chọn của người dùng."""
from __future__ import annotations

import json
from pathlib import Path

from ebook_reader.webui import music_plan
from tests.test_webui_listen_and_sync import make_project

TRACKS = [
    {"link": "https://x/calm.mp3", "valence": 0.2, "arousal": -0.5, "family": "piano", "duration": 200,
     "source": "incompetech"},
    {"link": "https://x/other.mp3", "valence": 0.1, "arousal": -0.4, "family": "eastern", "duration": 200,
     "source": "incompetech"},
]


def near(_v: float, _a: float) -> list[dict]:
    return TRACKS


def lookup(links: list[str]) -> dict[str, dict]:
    return {link: {"title": link.rsplit("/", 1)[-1], "creator": "Kevin MacLeod", "attribution": f"{link} CC BY"}
            for link in links}


def test_a_book_gets_a_music_track_on_by_default(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    plan = music_plan.build(project, near, lookup, catalog_revision="r1")
    assert plan["enabled"] is True and plan["catalogRevision"] == "r1"
    assert plan["scenes"] and all(scene["link"] for scene in plan["scenes"])
    assert all(plan["tracks"][link]["attribution"] for link in plan["tracks"]), "mỗi bài kèm ghi công"
    assert music_plan.read_plan(project) == plan


def test_the_users_choices_survive_a_rebuild(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    first = music_plan.build(project, near, lookup)
    key = first["scenes"][0]["key"]
    music_plan.write_overrides(project, {"pins": {key: "https://x/other.mp3"}, "family": "eastern", "levelDb": -26})
    again = music_plan.build(project, near, lookup)
    assert again["scenes"][0]["link"] == "https://x/other.mp3" and again["scenes"][0]["pinned"] is True
    assert (again["family"], again["levelDb"]) == ("eastern", -26.0)
    music_plan.write_overrides(project, {"pins": {key: None}, "silence": {key: True}})
    silent = music_plan.build(project, near, lookup)
    assert silent["scenes"][0]["link"] is None and silent["scenes"][0]["silenced"] is True


def test_turning_music_off_gives_the_player_nothing_to_play(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    plan = music_plan.build(project, near, lookup)
    chapter = plan["scenes"][0]["chapterId"]
    assert music_plan.chapter_cues(plan, chapter)
    music_plan.write_overrides(project, {"enabled": False})
    assert music_plan.chapter_cues(music_plan.build(project, near, lookup), chapter) == []


def test_neighbouring_scenes_with_the_same_track_play_on(tmp_path: Path) -> None:
    plan = {"enabled": True, "scenes": [
        {"chapterId": 1, "start": 0.0, "end": 100.0, "link": "a", "key": "1:1"},
        {"chapterId": 1, "start": 100.4, "end": 200.0, "link": "a", "key": "1:9"},
        {"chapterId": 1, "start": 200.4, "end": 300.0, "link": None, "key": "1:20"},
        {"chapterId": 1, "start": 300.4, "end": 400.0, "link": "b", "key": "1:30"},
    ]}
    assert music_plan.chapter_cues(plan, 1) == [
        {"start": 0.0, "end": 200.0, "link": "a", "key": "1:1"},
        {"start": 300.4, "end": 400.0, "link": "b", "key": "1:30"},
    ]


def test_overrides_are_clamped_and_unknown_styles_dropped(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    saved = music_plan.write_overrides(project, {"levelDb": 5, "family": "dubstep", "ban": ["https://x/calm.mp3"]})
    assert saved["levelDb"] == -6.0 and saved["family"] is None and saved["banned"] == ["https://x/calm.mp3"]
    assert json.loads((project / music_plan.OVERRIDES_FILE).read_text(encoding="utf-8"))["banned"] == ["https://x/calm.mp3"]
