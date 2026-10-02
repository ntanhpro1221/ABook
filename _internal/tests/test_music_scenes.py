"""Đoạn và không khí của đoạn cho nhạc nền (webui/music_scenes.py): tính từ cảm xúc từng câu, không cần model."""
from __future__ import annotations

import math

import pytest

from abook.webui.music_scenes import (EMOTION_CLASSES, EMOTION_SCALE, LINE_EMOTIONS, MAX_SCENE_SECONDS, chapter_scenes,
                                      line_emotions, line_point, line_tension)


def _script(lines: list[tuple[str, str, int, float]], *, timed: bool = True) -> dict:
    """lines: (text, emotion, intensity, giây)."""
    segments, clock = [], 0.0
    for index, (text, emotion, intensity, seconds) in enumerate(lines, 1):
        segments.append({"id": index, "text": text, "kind": "narration", "emotion": emotion, "intensity": intensity,
                         "start": clock if timed else None, "end": clock + seconds if timed else None})
        clock += seconds + 0.4
    return {"chapterId": 7, "segments": segments}


def _calm(n: int) -> list:
    return [("Gió thổi nhẹ qua đồi.", "tender" if i % 3 == 0 else "neutral", 1, 6.0) for i in range(n)]


def _battle(n: int) -> list:
    return [("Kiếm chém xuống!", "angry" if i % 2 else "afraid", 3, 5.0) for i in range(n)]


def test_a_calm_scene_then_a_battle_are_two_scenes_with_opposite_moods() -> None:
    scenes = chapter_scenes(_script(_calm(30) + _battle(36)))
    # khúc êm ~190 giây vượt trần 3 phút: hai khúc cùng không khí, rồi trận
    assert [scene["reason"] for scene in scenes] == ["chapter_start", "length", "mood_shift"]
    calm, battle = scenes[0], scenes[2]
    assert calm["arousal"] < 0 < battle["arousal"] and battle["valence"] < 0
    assert battle["reason"] == "mood_shift"
    assert 28 <= battle["firstSegment"] <= 34, "cắt gần chỗ không khí đổi, không trễ cả cửa sổ"
    assert battle["confidence"] > calm["confidence"]
    assert calm["start"] == 0 and scenes[1]["end"] <= battle["start"]


def test_one_outburst_does_not_change_the_music() -> None:
    lines = _calm(12) + [("“Cút đi!”", "angry", 3, 2.0)] + _calm(12)  # ngắn hơn trần 3 phút: chỉ còn câu hỏi đổi không khí
    assert len(chapter_scenes(_script(lines))) == 1


def test_a_scene_break_line_and_a_time_jump_start_new_scenes() -> None:
    lines = _calm(15) + [("* * *", "neutral", 0, 1.0)] + _calm(15) + [("Sáng hôm sau, trời trong.", "neutral", 0, 4.0)] \
        + _calm(15)
    scenes = chapter_scenes(_script(lines))
    assert [scene["reason"] for scene in scenes] == ["chapter_start", "separator", "time_jump"]


def test_a_tiny_last_scene_joins_its_neighbour() -> None:
    lines = _calm(20) + [("***", "neutral", 0, 1.0), ("Hết.", "neutral", 0, 2.0)]
    scenes = chapter_scenes(_script(lines))
    assert len(scenes) == 1 and scenes[0]["lastSegment"] == 22


def test_a_chapter_without_audio_is_split_by_text_length() -> None:
    long_calm = [("Gió thổi nhẹ qua đồi, cỏ rạp xuống rồi lại đứng lên, xa xa có tiếng chuông chùa ngân dài trong chiều muộn "
                  "khi nắng đã nhạt dần.", "tender" if i % 3 == 0 else "neutral", 1, 0.0) for i in range(30)]
    long_battle = [("Kiếm chém xuống, máu bắn tung tóe, tiếng hét vang lên khắp chiến trường, khói lửa mù mịt che kín cả "
                    "bầu trời.", "angry" if i % 2 else "afraid", 3, 0.0) for i in range(36)]
    scenes = chapter_scenes(_script(long_calm + long_battle, timed=False))
    shift = [scene for scene in scenes if scene["reason"] == "mood_shift"]
    assert len(shift) == 1 and 28 <= shift[0]["firstSegment"] <= 34
    assert scenes[-1]["arousal"] > scenes[0]["arousal"]


def test_a_long_scene_is_cut_into_pieces_of_about_three_minutes() -> None:
    scenes = chapter_scenes(_script(_calm(100)))  # ~640 giây cùng một không khí
    assert len(scenes) == 4 and [scene["reason"] for scene in scenes][1:] == ["length"] * 3
    lengths = [scene["end"] - scene["start"] for scene in scenes]
    assert max(lengths) <= MAX_SCENE_SECONDS + 10 and min(lengths) >= 120
    assert all(a["lastSegment"] + 1 == b["firstSegment"] for a, b in zip(scenes, scenes[1:]))


def test_neutral_narration_weighs_less_than_feeling() -> None:
    _v, _a, neutral, affective_n = line_point({"emotion": "neutral", "intensity": 0})
    _v, _a, sad, affective_s = line_point({"emotion": "sad", "intensity": 0})
    assert neutral < sad and not affective_n and affective_s
    assert line_point({"emotion": "sad", "intensity": 3})[0] < line_point({"emotion": "sad", "intensity": 0})[0] < 0
    assert line_point({"emotion": "neutral", "pace": "fast", "volume": "loud"})[1] > 0


def test_a_frightening_scene_is_tense_and_an_excited_one_is_not() -> None:
    afraid = chapter_scenes(_script([("Có tiếng động!", "afraid", 3, 6.0)] * 20))[0]
    excited = chapter_scenes(_script([("Thắng rồi!", "excited", 3, 6.0)] * 20))[0]
    assert afraid["tension"] > 0.5 > excited["tension"]


def test_scene_sd_is_the_weighted_spread_of_its_lines_and_merge_adds_up() -> None:
    from abook.webui.music_scenes import _Accumulator

    lines = [({"emotion": "happy", "intensity": 3}, 5.0), ({"emotion": "sad", "intensity": 3}, 3.0),
             ({"emotion": "neutral", "intensity": 0}, 8.0), ({"emotion": "afraid", "intensity": 2}, 4.0)]
    whole = _Accumulator()
    for segment, seconds in lines:
        whole.add_line(segment, seconds)
    # Tính tay theo định nghĩa: trọng số = trọng số câu x giây.
    rows = [(line_point(segment), line_tension(segment), seconds) for segment, seconds in lines]
    for axis, pick in (("valence", lambda r: r[0][0]), ("arousal", lambda r: r[0][1]), ("tension", lambda r: r[1])):
        w = [r[0][2] * r[2] for r in rows]
        mean = sum(wi * pick(r) for wi, r in zip(w, rows)) / sum(w)
        var = sum(wi * (pick(r) - mean) ** 2 for wi, r in zip(w, rows)) / sum(w)
        assert whole.sd()[axis] == pytest.approx(var ** 0.5)
    left, right = _Accumulator(), _Accumulator()
    for segment, seconds in lines[:2]:
        left.add_line(segment, seconds)
    for segment, seconds in lines[2:]:
        right.add_line(segment, seconds)
    left.merge(right)
    assert left.sd() == pytest.approx(whole.sd()) and left.point() == pytest.approx(whole.point())
    assert left.emotion_intensities() == pytest.approx(whole.emotion_intensities())
    assert _Accumulator().sd() == {"valence": 0.0, "arousal": 0.0, "tension": 0.0}


def test_every_scene_carries_sd_and_a_mixed_scene_spreads_more_than_a_uniform_one() -> None:
    uniform = chapter_scenes(_script([("Có tiếng động!", "afraid", 3, 6.0)] * 20))[0]
    mixed = chapter_scenes(_script([("Có tiếng động!", "afraid", 3, 6.0), ("Thắng rồi!", "happy", 3, 6.0)] * 10))[0]
    assert set(uniform["sd"]) == {"valence", "arousal", "tension"}
    assert all(value == pytest.approx(0.0, abs=1e-9) for value in uniform["sd"].values())
    assert mixed["sd"]["valence"] > 0.5 and mixed["sd"]["tension"] > 0.5 and mixed["sd"]["arousal"] > 0.05


def test_the_sd_of_split_pieces_is_computed_from_each_piece_not_the_whole() -> None:
    pieces = chapter_scenes(_script(_calm(100)))  # cùng không khí, chia thành các khúc ~3 phút
    assert len(pieces) == 4
    assert all(0.0 < piece["sd"]["valence"] < 0.35 for piece in pieces), "mỗi khúc có sd riêng (chỉ còn câu êm / trung tính)"


def test_a_scene_has_thirteen_independent_emotion_intensities() -> None:
    scene = chapter_scenes(_script([("Có tiếng động!", "afraid", 3, 6.0)] * 20))[0]
    assert tuple(scene["emotions"]) == EMOTION_CLASSES and len(EMOTION_CLASSES) == 13
    assert all(0.0 <= value <= 1.0 for value in scene["emotions"].values())
    # `afraid` góp fear 1,0 và tension 0,6: cả hai cùng cao, tổng vượt 1 (không ép thành phân phối).
    assert scene["emotions"]["fear"] == pytest.approx(round(1 - math.exp(-1.0 / EMOTION_SCALE), 3))
    assert scene["emotions"]["tension"] == pytest.approx(round(1 - math.exp(-0.6 / EMOTION_SCALE), 3))
    assert scene["emotions"]["fear"] + scene["emotions"]["tension"] > 1.5
    assert scene["emotions"]["joy"] == 0.0 and scene["emotions"]["moved"] == 0.0
    assert "gems" not in scene


def test_emotion_intensity_follows_label_strength_and_share_of_the_scene() -> None:
    soft = chapter_scenes(_script([("Có tiếng động!", "afraid", 0, 6.0)] * 20))[0]["emotions"]["fear"]
    strong = chapter_scenes(_script([("Có tiếng động!", "afraid", 3, 6.0)] * 20))[0]["emotions"]["fear"]
    assert soft == pytest.approx(round(1 - math.exp(-0.4 / EMOTION_SCALE), 3)) and soft < strong
    half = chapter_scenes(_script([("Có tiếng động!", "afraid", 3, 6.0), ("Gió thổi.", "neutral", 0, 6.0)] * 10))[0]
    assert half["emotions"]["fear"] == pytest.approx(round(1 - math.exp(-0.5 / EMOTION_SCALE), 3))
    blend = chapter_scenes(_script([("Buồn quá.", "sad", 3, 6.0), ("Ấm áp.", "tender", 3, 6.0)] * 10))[0]["emotions"]
    assert blend["sadness"] > 0.5 and blend["tenderness"] > 0.5, "buồn mà ấm giữ được cả hai"


def test_the_label_mapping_only_names_real_classes_and_known_labels() -> None:
    from abook.webui.music_scenes import EMOTION_VA

    assert set(LINE_EMOTIONS) == set(EMOTION_VA)
    assert all(name in EMOTION_CLASSES for mapping in LINE_EMOTIONS.values() for name in mapping)
    assert line_emotions({"emotion": "excited", "intensity": 3}) == {"joy": 0.6, "power": 0.6}
    assert line_emotions({"emotion": "no_such_label", "intensity": 1}) == {}
