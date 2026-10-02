"""Đoạn và không khí của đoạn cho nhạc nền (webui/music_scenes.py): tính từ cảm xúc từng câu, không cần model."""
from __future__ import annotations

from ebook_reader.webui.music_scenes import MAX_SCENE_SECONDS, chapter_scenes, line_point


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
