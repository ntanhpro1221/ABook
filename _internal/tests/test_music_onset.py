"""Ranh giới "lên căng" của nhạc nền (webui/music_scenes.py onset_tiles / onset_starts / chapter_scenes(onsets=...); Corpus
research/music/SPEC_app_onset.md): lát ~45 s, khe T học sinh đổi mạnh thành ranh giới không khí. Thuần hàm, không model."""
from __future__ import annotations

import json

import pytest

from abook.webui import music_scene_student, music_scenes
from abook.webui.music_scenes import book_scenes, chapter_scenes, onset_starts, onset_tiles


def _script(lines: list[tuple[str, str, int, float]]) -> dict:
    """lines: (text, emotion, intensity, giây); câu cách nhau 0,5 s (giờ đúng tuyệt đối trên số nhị phân)."""
    segments, clock = [], 0.0
    for index, (text, emotion, intensity, seconds) in enumerate(lines, 1):
        segments.append({"id": index, "text": text, "kind": "narration", "emotion": emotion, "intensity": intensity,
                         "start": clock, "end": clock + seconds})
        clock += seconds + 0.5
    return {"chapterId": 7, "segments": segments}


def _plain(n: int) -> list:
    return [("Anh bước tiếp.", "neutral", 0, 5.0) for _ in range(n)]


def test_tiles_close_at_45_seconds_and_before_a_scene_break() -> None:
    assert onset_tiles(_script(_plain(30))) == [(0, 8), (9, 17), (18, 26), (27, 29)]
    # Dòng ngăn cảnh là ranh giới cứng VÀ đánh dấu câu sau nó (cue_bounds) nên tự thành một lát.
    lines = _plain(12) + [("* * *", "neutral", 0, 1.0)] + _plain(17)
    assert onset_tiles(_script(lines)) == [(0, 8), (9, 11), (12, 12), (13, 21), (22, 29)]


def test_a_tension_jump_between_tiles_opens_a_scene_there_with_numbers_worked_by_hand() -> None:
    # 4 lát (45, 45, 45, 15 s) bắt đầu ở giây 0; 49,5; 99; 148,5. T = 0, 0, 1, 1: TB .4, sd .49 -> khe 2 lệch 2,04 sd >= 1,5.
    script = _script(_plain(30))
    assert onset_starts(script, [0.0, 0.0, 1.0, 1.0]) == [19]
    # Thang / độ dịch của T không quan trọng: chỉ hiệu giữa các lát chia cho sd.
    assert onset_starts(script, [5.0, 5.0, 8.0, 8.0]) == [19]
    scenes = chapter_scenes(script, onsets=[19])
    assert [(s["firstSegment"], s["reason"]) for s in scenes] == [(1, "chapter_start"), (19, "tension_shift")]


def test_a_jump_in_the_first_minute_or_a_small_one_adds_nothing() -> None:
    script = _script(_plain(30))
    # T = 0, 1, 1, 2: TB .8, sd .6 -> khe 1 (giây 49,5 < 60) bỏ dù lệch 1,67 sd; khe 3 (giây 148,5) nhận.
    assert onset_starts(script, [0.0, 1.0, 1.0, 2.0]) == [28]
    # Mọi khe dưới 1,5 sd: T = 0, 1, 2, 3 -> mỗi khe 1 / 1,05 sd.
    assert onset_starts(script, [0.0, 1.0, 2.0, 3.0]) == []
    # Lát không khớp (sách đã đổi) hay chương một lát: không ranh giới nào.
    assert onset_starts(script, [0.0, 1.0]) == [] and onset_starts(_script(_plain(5)), [0.0]) == []


def test_a_jump_too_close_to_another_boundary_is_dropped() -> None:
    # Dòng ngăn cảnh là câu 19: đoạn mới từ câu 20 (giây 100,5). Lát: câu 1-9, 10-18, 19, 20-28 (giây 100,5), 29-36 (giây 150).
    lines = _plain(18) + [("* * *", "neutral", 0, 1.0)] + _plain(17)
    script = _script(lines)
    assert [s["firstSegment"] for s in chapter_scenes(script, onsets=[])] == [1, 20]
    assert onset_tiles(script) == [(0, 8), (9, 17), (18, 18), (19, 27), (28, 35)]
    # Lệch > 2 sd ở khe câu 20 (trùng ranh giới) hay khe câu 29 (cách 49,5 s): cả hai < 60 s nên bỏ.
    assert onset_starts(script, [0.0, 0.0, 0.0, 1.0, 1.0]) == []
    assert onset_starts(script, [0.0, 0.0, 0.0, 0.0, 1.0]) == []


def test_the_mood_of_a_scene_is_the_plain_one_even_though_its_boundaries_count_tension() -> None:
    # Câu sợ hãi: căng thẳng cao. Ranh giới tính có cộng căng thẳng (ONSET_TUNING), không khí của đoạn thì không.
    lines = _plain(18) + [("Bóng đen lao tới!", "afraid", 3, 5.0) for _ in range(18)]
    script = _script(lines)
    plain = chapter_scenes(script)
    onset = chapter_scenes(script, onsets=[])
    assert [s["firstSegment"] for s in onset] != [] and all(s["reason"] != "tension_shift" for s in onset)
    by_first = {s["firstSegment"]: s for s in plain}
    for scene in onset:
        same = by_first.get(scene["firstSegment"])
        if same and same["lastSegment"] == scene["lastSegment"]:
            assert scene["arousal"] == same["arousal"] and scene["valence"] == same["valence"]


def test_an_onset_at_an_existing_boundary_or_the_first_line_changes_nothing() -> None:
    script = _script(_plain(30))
    assert chapter_scenes(script, onsets=[1, 999]) == chapter_scenes(script, onsets=[])


def test_without_onsets_the_book_is_cut_exactly_as_before(monkeypatch: pytest.MonkeyPatch) -> None:
    script = _script(_plain(20) + [("Kiếm chém xuống!", "angry", 3, 5.0) for _ in range(30)])
    before = json.dumps(chapter_scenes(script), sort_keys=True)
    assert json.dumps(book_scenes([script]), sort_keys=True) == before
    assert json.dumps(book_scenes([script], onsets={"8": [3]}), sort_keys=True) == before  # chương khác
    # Cờ tắt: file học sinh có `onsets` cũng không được dùng.
    monkeypatch.setattr(music_scene_student, "ONSET_TILES", False)
    assert music_scene_student.onsets_of({"onsets": {"7": [19]}}) is None
    assert music_scene_student.file_version() == music_scene_student.VERSION
    monkeypatch.setattr(music_scene_student, "ONSET_TILES", True)
    assert music_scene_student.onsets_of({"onsets": {"7": [19]}}) == {"7": [19]}
    assert music_scene_student.onsets_of(None) is None
    assert music_scene_student.file_version() == music_scene_student.VERSION + 1


def test_the_flag_is_off_by_default() -> None:
    assert music_scenes.ONSET_TUNING == (30.0, 0.3, 40.0, 60.0, 1.0)
    assert music_scene_student.ONSET_TILES is False or __import__("os").environ.get("ABOOK_MUSIC_ONSET_TILES") == "1"
