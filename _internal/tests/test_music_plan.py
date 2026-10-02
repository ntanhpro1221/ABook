"""Rãnh nhạc nền của một cuốn (webui/music_plan.py): máy dựng, người dùng sửa, dựng lại vẫn giữ lựa chọn của người dùng."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import soundfile

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


def test_the_gain_puts_every_track_the_same_distance_under_the_voice() -> None:
    quiet, loud = (music_plan.cue_gain_db(-18.0, lufs, 0.30) for lufs in (-26.0, -10.0))
    assert math.isclose(quiet - loud, 16.0, abs_tol=0.01), "bài to hơn 16 LU thì hạ hơn đúng 16 dB"
    # Giọng -20 LUFS, levelDb -18: nhạc phải ở -38 LUFS -> bài -26 LUFS chỉ cần hạ 12 dB.
    assert quiet == -12.0 and loud == -28.0
    assert music_plan.cue_gain_db(-20.0, -30.0, 0.30) == -10.0


def test_the_gain_never_boosts_a_track_above_its_own_level() -> None:
    assert music_plan.cue_gain_db(-6.0, -40.0, 0.30) == 0.0, "volume HTML / ExoPlayer tối đa 1"


def test_a_track_that_covers_the_speech_band_sits_lower_and_the_correction_is_clamped() -> None:
    base = music_plan.cue_gain_db(-20.0, -20.0, 0.30)
    assert base == -20.0
    assert math.isclose(music_plan.cue_gain_db(-20.0, -20.0, 0.80) - base, -4.0, abs_tol=0.01)
    assert math.isclose(music_plan.cue_gain_db(-20.0, -20.0, 0.10) - base, 1.6, abs_tol=0.01)
    assert math.isclose(music_plan.cue_gain_db(-20.0, -20.0, 5.0) - base, -6.0, abs_tol=0.01), "kẹp -6 dB"
    assert math.isclose(music_plan.cue_gain_db(-20.0, -20.0, -5.0) - base, 6.0, abs_tol=0.01), "kẹp +6 dB"


def test_a_missing_loudness_means_the_median_track_and_a_missing_band_means_no_correction() -> None:
    assert music_plan.cue_gain_db(-20.0, None, None) == music_plan.cue_gain_db(-20.0, -16.6, 0.30) == -23.4
    assert music_plan.DEFAULT_TRACK_LUFS == -16.6 and music_plan.VOICE_LUFS == -20.0


def test_cues_get_their_gain_from_the_catalog_loudness_or_measure_a_cached_file(tmp_path: Path) -> None:
    cues = [{"link": "https://x/a.mp3", "key": "a"}, {"link": "https://x/b.mp3", "key": "b"},
            {"link": "https://x/c.mp3", "key": "c"}, {"link": "https://x/d.mp3", "key": "d", "gainDb": -3.0}]
    # b: không có lufs, file đã có trong bộ đệm = sin 1 kHz stereo biên độ 0,1 (BS.1770 ~ -20 LUFS)
    t = np.arange(48000 * 3) / 48000
    tone = (0.1 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
    cached = tmp_path / "b.mp3"
    soundfile.write(cached, np.stack([tone, tone], axis=1), 48000, format="WAV")
    tracks = {"https://x/a.mp3": {"lufs": -26.0, "speechBand": 0.3}, "https://x/b.mp3": {}, "https://x/c.mp3": {}}
    music_plan.apply_gain(cues, -20.0, tracks, lambda link: cached if link.endswith("b.mp3") else None)
    assert cues[0]["gainDb"] == -14.0
    assert abs(cues[1]["gainDb"] - (-20.0)) < 1.0, "độ to đo từ file: ~ -20 LUFS -> hạ ~20 dB"
    assert cues[2]["gainDb"] == music_plan.cue_gain_db(-20.0, None, None), "chưa có file: trung vị danh mục"
    assert cues[3]["gainDb"] == -3.0, "mốc đã có gainDb (sách đóng gói) giữ nguyên"
    assert cached.with_suffix(".lufs").is_file(), "đo một lần rồi ghi cạnh bộ đệm"
    cached.unlink()  # chỉ còn số đã ghi: lần sau không giải mã lại
    again = [{"link": "https://x/b.mp3", "key": "b"}]
    music_plan.apply_gain(again, -20.0, tracks, lambda _link: cached)
    assert again[0]["gainDb"] == cues[1]["gainDb"]


def test_a_built_plan_carries_the_loudness_and_speech_band_of_its_tracks(tmp_path: Path) -> None:
    project = make_project(tmp_path)

    def with_loudness(links: list[str]) -> dict[str, dict]:
        return {link: {"title": "t", "lufs": -21.5, "speechBand": 0.42} for link in links}

    plan = music_plan.build(project, near, with_loudness, catalog_revision="r1")
    assert plan["tracks"] and all(info["lufs"] == -21.5 and info["speechBand"] == 0.42 for info in plan["tracks"].values())
