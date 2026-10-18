"""Đường "student" của `music_scenes.apply_student` (mức chương như CL + hình trong chương do học sinh đoán; NN-lite, music_nnlite.py, cho cả Nghe ngay lẫn Studio):
số tính tay trên đoạn dựng sẵn, và `chapter_scenes` nhận mục học sinh. Không cần model, không mạng."""
from __future__ import annotations

import copy

import numpy as np
import pytest

from abook.webui import music_scenes


def _text(rng: np.random.Generator, words: int = 3) -> str:
    return " ".join(f"w{i}" for i in rng.integers(0, 24, size=words))


def _chapter(chapter: int, first_id: int, *, seed: int, blocks: int = 3) -> dict:
    """`blocks` khúc 12 câu x 6 giây (72 giây), cách nhau bằng dòng ngăn cảnh: mỗi khúc một đoạn."""
    rng = np.random.default_rng(seed)
    segments, clock, index = [], 0.0, first_id
    for block in range(blocks):
        if block:
            segments.append({"id": index, "text": "***", "kind": "narration", "emotion": "neutral", "intensity": 0,
                             "start": clock, "end": clock + 1.0})
            index, clock = index + 1, clock + 1.4
        for _ in range(12):
            segments.append({"id": index, "text": _text(rng), "kind": "narration", "emotion": "neutral", "intensity": 0,
                             "start": clock, "end": clock + 6.0})
            index, clock = index + 1, clock + 6.4
    return {"chapterId": chapter, "segments": segments}


@pytest.fixture
def book() -> list[dict]:
    return [_chapter(1, 1, seed=1), _chapter(2, 101, seed=2)]


# ---- áp vào đoạn --------------------------------------------------------------------------------------------------------------------
def _scene(start: float, end: float, label_v: float, label_t: float, first: int, last: int, *, p_v: float | None = None,
           p_t: float | None = None) -> dict:
    """Đoạn ngay từ `_view` (chưa qua mức chương). Có P0 (p_v, p_t) thì valence / tension là của P0 và moodSource "llm"; không thì đường nhãn."""
    llm = p_v is not None
    return {"chapterId": 7, "firstSegment": first, "lastSegment": last, "start": start, "end": end,
            "valence": p_v if llm else label_v, "arousal": 0.25, "tension": p_t if llm else label_t,
            "moodSource": "llm" if llm else "labels", "labelValence": label_v, "labelTension": label_t, "emotions": {"joy": 0.5}}


def _item(first: int, last: int, d_v: float, d_e: float, d_t: float, chapter: int = 7) -> dict:
    return {"chapterId": chapter, "firstSegment": first, "lastSegment": last, "dV": d_v, "dE": d_e, "dT": d_t}


# Ba đoạn 60 / 120 / 60 giây (w = 60, 120, 60; tổng 240). Nhãn V = .2 / 0 / -.2 nên TB = 0 và L_V = .068. dV = .3 / 0 / -.2 -> TB = .025.
# dT = .1 / -.2 / .4 -> TB = .025. Độ lệch căn giữa lại: dV - TB = .275 / -.025 / -.225, dT - TB = .075 / -.225 / .375.
ITEMS = [_item(1, 10, 0.3, -0.1, 0.1), _item(11, 20, 0.0, 0.2, -0.2), _item(21, 30, -0.2, -0.1, 0.4)]
VALENCE = [pytest.approx(0.068 + 0.275, abs=6e-4), pytest.approx(0.068 - 0.025, abs=6e-4), pytest.approx(0.068 - 0.225, abs=6e-4)]


def test_apply_student_with_p0_on_every_scene_takes_the_t_level_from_p0_with_numbers_worked_by_hand() -> None:
    # P0 chấm T = .8 / .6 / .4 -> TB = (48 + 72 + 24) / 240 = .6 -> L_T = 1.066 * .6 - .49 = .1496. Hình đầy đủ (k = 1, không nhân .5).
    scenes = [_scene(0, 60, 0.2, 0.1, 1, 10, p_v=0.5, p_t=0.8), _scene(60, 180, 0.0, 0.2, 11, 20, p_v=0.1, p_t=0.6),
              _scene(180, 240, -0.2, 0.0, 21, 30, p_v=-0.3, p_t=0.4)]
    before = copy.deepcopy(scenes)
    got = music_scenes.apply_student(scenes, ITEMS)
    assert scenes == before, "thuần hàm: không sửa đoạn đưa vào"
    assert [s["valence"] for s in got] == VALENCE
    assert [s["tension"] for s in got] == [pytest.approx(0.1496 + 0.075, abs=6e-4), pytest.approx(0.1496 - 0.225, abs=6e-4),
                                           pytest.approx(0.1496 + 0.375, abs=6e-4)]
    assert all(s["moodSource"] == "student" for s in got)
    assert [(s["studentValence"], s["studentArousal"], s["studentTension"]) for s in got] == [(0.3, -0.1, 0.1), (0.0, 0.2, -0.2),
                                                                                         (-0.2, -0.1, 0.4)], "độ lệch thô"
    assert [(s["llmValence"], s["llmTension"]) for s in got] == [(0.5, 0.8), (0.1, 0.6), (-0.3, 0.4)], "giữ giá trị P0 để so"
    # arousal: mức = TB nhãn .25 (mọi đoạn .25); dE = -.1 / .2 / -.1 -> TB = (-6 + 24 - 6) / 240 = .05 -> .25 - .15 / .25 + .15 / .25 - .15
    assert [s["arousal"] for s in got] == [pytest.approx(0.1, abs=6e-4), pytest.approx(0.4, abs=6e-4), pytest.approx(0.1, abs=6e-4)]
    for field in ("labelValence", "labelTension", "emotions", "start", "end", "firstSegment", "lastSegment"):
        assert [s[field] for s in got] == [s[field] for s in scenes], field


def test_apply_student_takes_the_energy_shape_from_the_student_around_the_label_level_with_numbers_worked_by_hand() -> None:
    # Q06-E (Corpus PLAN_q06_e.md): mức E giữ TB nhãn câu theo thời lượng, hình E từ dE. Nhãn arousal .6 / 0 / .2 -> TB = (36 + 0 + 12) / 240
    # = .2; dE - TB = -.15 / .15 / -.15 -> .05 / .35 / .05. Có P0 hay không thì E cũng vậy (P0 không chấm E).
    scenes = [_scene(0, 60, 0.2, 0.1, 1, 10), _scene(60, 180, 0.0, 0.2, 11, 20), _scene(180, 240, -0.2, 0.0, 21, 30)]
    for scene, arousal in zip(scenes, (0.6, 0.0, 0.2)):
        scene["arousal"] = arousal
    got = music_scenes.apply_student(scenes, ITEMS)
    assert [s["arousal"] for s in got] == [pytest.approx(0.05, abs=6e-4), pytest.approx(0.35, abs=6e-4), pytest.approx(0.05, abs=6e-4)]
    hot = [dict(scene, arousal=0.95) for scene in scenes]
    assert max(s["arousal"] for s in music_scenes.apply_student(hot, ITEMS)) == 1.0, "kẹp về thang [-1, 1]"


def test_apply_student_without_p0_on_every_scene_takes_the_t_level_from_the_labels_with_numbers_worked_by_hand() -> None:
    # Đoạn giữa chưa có P0 -> L_T = 4.022 * TB(nhãn T) - .056. Nhãn T = .1 / .2 / 0 -> TB = (6 + 24 + 0) / 240 = .125 -> L_T = .44675.
    scenes = [_scene(0, 60, 0.2, 0.1, 1, 10, p_v=0.5, p_t=0.8), _scene(60, 180, 0.0, 0.2, 11, 20),
              _scene(180, 240, -0.2, 0.0, 21, 30, p_v=-0.3, p_t=0.4)]
    got = music_scenes.apply_student(scenes, ITEMS)
    assert [s["valence"] for s in got] == VALENCE, "mức V luôn từ nhãn câu"
    assert [s["tension"] for s in got] == [pytest.approx(0.44675 + 0.075, abs=6e-4), pytest.approx(0.44675 - 0.225, abs=6e-4),
                                           pytest.approx(0.44675 + 0.375, abs=6e-4)]
    assert all(s["moodSource"] == "student" for s in got)
    assert ["llmValence" in s for s in got] == [True, False, True] and ["llmTension" in s for s in got] == [True, False, True], "P0 chỉ ở đoạn có"
    assert (got[0]["llmValence"], got[0]["llmTension"], got[2]["llmValence"], got[2]["llmTension"]) == (0.5, 0.8, -0.3, 0.4)
    labels = [_scene(0, 60, 0.2, 0.1, 1, 10), _scene(60, 180, 0.0, 0.2, 11, 20), _scene(180, 240, -0.2, 0.0, 21, 30)]
    assert [s["tension"] for s in music_scenes.apply_student(labels, ITEMS)] == [s["tension"] for s in got], "không P0 nào: cùng mức"
    assert not any("llmValence" in s or "llmTension" in s for s in music_scenes.apply_student(labels, ITEMS))


def _with_level(items: list[dict], level: float) -> list[dict]:
    return [dict(item, chapterV=level) for item in items]


def test_apply_student_takes_the_v_level_from_the_chapter_head_with_numbers_worked_by_hand() -> None:
    # chapterV = .25 thay L_V = .068 (từ nhãn); hình V vẫn dV - TB(dV) = .275 / -.025 / -.225 -> .525 / .225 / .025.
    scenes = [_scene(0, 60, 0.2, 0.1, 1, 10, p_v=0.5, p_t=0.8), _scene(60, 180, 0.0, 0.2, 11, 20, p_v=0.1, p_t=0.6),
              _scene(180, 240, -0.2, 0.0, 21, 30, p_v=-0.3, p_t=0.4)]
    items = _with_level(ITEMS, 0.25)
    before = copy.deepcopy(items)
    got = music_scenes.apply_student(scenes, items)
    assert items == before
    assert [s["valence"] for s in got] == [pytest.approx(0.525, abs=6e-4), pytest.approx(0.225, abs=6e-4), pytest.approx(0.025, abs=6e-4)]
    # Mức T giữ nguyên: P0 đủ -> L_T = .1496 như khi chưa có chapterV, không đổi theo chapterV.
    assert [s["tension"] for s in got] == [pytest.approx(0.1496 + 0.075, abs=6e-4), pytest.approx(0.1496 - 0.225, abs=6e-4),
                                           pytest.approx(0.1496 + 0.375, abs=6e-4)]
    assert [s["tension"] for s in got] == [s["tension"] for s in music_scenes.apply_student(scenes, ITEMS)]
    assert all(s["levelSource"] == {"V": "student", "T": "p0"} and s["moodSource"] == "student" for s in got)
    assert [s["arousal"] for s in got] == [s["arousal"] for s in music_scenes.apply_student(scenes, ITEMS)], "mức E không đổi"


def test_apply_student_takes_the_v_level_from_the_chapter_head_and_the_t_level_from_the_labels_without_p0() -> None:
    # Không P0: L_T = .44675 (nhãn) như cũ; chapterV = -.4 -> V = -.125 / -.425 / -.625. Mức T không đổi theo chapterV.
    scenes = [_scene(0, 60, 0.2, 0.1, 1, 10), _scene(60, 180, 0.0, 0.2, 11, 20), _scene(180, 240, -0.2, 0.0, 21, 30)]
    got = music_scenes.apply_student(scenes, _with_level(ITEMS, -0.4))
    assert [s["valence"] for s in got] == [pytest.approx(-0.125, abs=6e-4), pytest.approx(-0.425, abs=6e-4), pytest.approx(-0.625, abs=6e-4)]
    assert [s["tension"] for s in got] == [pytest.approx(0.44675 + 0.075, abs=6e-4), pytest.approx(0.44675 - 0.225, abs=6e-4),
                                           pytest.approx(0.44675 + 0.375, abs=6e-4)]
    assert all(s["levelSource"] == {"V": "student", "T": "labels"} for s in got)
    other = music_scenes.apply_student(scenes, _with_level(ITEMS, 0.6))
    assert [s["tension"] for s in other] == [s["tension"] for s in got], "T không phụ thuộc chapterV"


def test_apply_student_clips_the_chapter_level_and_a_one_scene_chapter_sits_at_it() -> None:
    scenes = [_scene(0, 60, 0.0, 0.1, 1, 10), _scene(60, 120, 0.0, 0.1, 11, 20)]
    got = music_scenes.apply_student(scenes, _with_level([_item(1, 10, 0.3, 0, 0), _item(11, 20, -0.3, 0, 0)], 1.4))  # kẹp 1 -> 1.3 / .7
    assert [s["valence"] for s in got] == [1.0, pytest.approx(0.7)]
    got, = music_scenes.apply_student([_scene(0, 90, 0.3, 0.1, 1, 10)], _with_level([_item(1, 10, 0.0, 0.0, 0.0)], -1.7))
    assert got["valence"] == -1.0 and got["levelSource"] == {"V": "student", "T": "labels"}
    got, = music_scenes.apply_student([_scene(0, 90, 0.3, 0.1, 1, 10)], _with_level([_item(1, 10, 0.0, 0.0, 0.0)], 0.2))
    assert got["valence"] == 0.2, "một đoạn: đúng mức chương, không phụ thuộc nhãn"


def test_apply_student_falls_back_to_the_label_level_without_a_usable_chapter_level() -> None:
    scenes = [_scene(0, 60, 0.2, 0.1, 1, 10), _scene(60, 180, 0.0, 0.2, 11, 20), _scene(180, 240, -0.2, 0.0, 21, 30)]
    labels = music_scenes.apply_student(scenes, ITEMS)
    assert [s["valence"] for s in labels] == VALENCE and all(s["levelSource"] == {"V": "labels", "T": "labels"} for s in labels)
    for odd in (None, "x", float("nan"), float("inf")):
        got = music_scenes.apply_student(scenes, [dict(ITEMS[0], chapterV=odd), *ITEMS[1:]])
        assert [s["valence"] for s in got] == [s["valence"] for s in labels] and got[0]["levelSource"]["V"] == "labels", odd
    partial = music_scenes.apply_student(scenes, [dict(ITEMS[0], chapterV=0.25), *ITEMS[1:]])
    assert partial[0]["levelSource"]["V"] == "labels", "thiếu ở một đoạn: cả chương về nhãn"


def test_apply_student_clips_to_the_scale_and_keeps_a_one_scene_chapter_at_the_level() -> None:
    hot = [_scene(0, 60, 0.0, 0.5, 1, 10), _scene(60, 120, 0.0, 0.5, 11, 20)]  # L_T = 4.022 * .5 - .056 = 1.955 -> kẹp 1
    got = music_scenes.apply_student(hot, [_item(1, 10, 0, 0, 0.3), _item(11, 20, 0, 0, -0.3)])
    assert [s["tension"] for s in got] == [1.0, pytest.approx(0.7)]
    # Một đoạn: độ lệch 0 -> đoạn = mức chương: L_V = 1.876 * .3 + .068 = .6308, L_T = 4.022 * .1 - .056 = .3462.
    got, = music_scenes.apply_student([_scene(0, 90, 0.3, 0.1, 1, 10)], [_item(1, 10, 0.0, 0.0, 0.0)])
    assert (got["valence"], got["tension"], got["arousal"]) == (0.631, 0.346, 0.25) and got["moodSource"] == "student"


def test_apply_student_gives_up_when_any_scene_has_no_item() -> None:
    scenes = [_scene(0, 60, 0.2, 0.1, 1, 10), _scene(60, 120, 0.1, 0.2, 11, 20)]
    before = copy.deepcopy(scenes)
    assert music_scenes.apply_student(scenes, [_item(1, 10, 0.1, 0.1, 0.1)]) is None
    assert music_scenes.apply_student(scenes, [_item(1, 10, 0.1, 0.1, 0.1), _item(11, 19, 0.1, 0.1, 0.1)]) is None, "ranh giới khác thì không khớp"
    assert music_scenes.apply_student(scenes, [_item(1, 10, 0.1, 0.1, 0.1), _item(11, 20, 0.1, 0.1, 0.1, chapter=8)]) is None
    assert music_scenes.apply_student(scenes, [_item(1, 10, 0.1, 0.1, 0.1), {**_item(11, 20, 0.0, 0.0, 0.0), "dV": "hỏng"}]) is None
    assert music_scenes.apply_student(scenes, None) is None and music_scenes.apply_student(scenes, []) is None
    assert music_scenes.apply_student([], [_item(1, 10, 0, 0, 0)]) is None and scenes == before


def test_chapter_scenes_takes_the_shape_from_the_student_and_falls_back_to_the_chapter_level(book: list[dict]) -> None:
    script = book[0]
    plain = music_scenes.chapter_scenes(script)
    items = [_item(s["firstSegment"], s["lastSegment"], d, -d, d / 2, chapter=1) for s, d in zip(plain, (0.2, -0.1, -0.1))]
    moods = [{"chapterId": 1, "firstSegment": s["firstSegment"], "lastSegment": s["lastSegment"], "V": v, "E": 0.0, "T": t}
             for s, v, t in zip(plain, (2.0, 0.0, -2.0), (1.0, 0.0, -1.0))]
    level = music_scenes.chapter_scenes(script, moods)
    assert [s["moodSource"] for s in level] == ["chapter"] * 3
    got = music_scenes.chapter_scenes(script, moods, student=items)
    assert [s["moodSource"] for s in got] == ["student"] * 3
    weights = [s["end"] - s["start"] for s in plain]
    mean = lambda values: sum(w * v for w, v in zip(weights, values)) / sum(weights)  # noqa: E731
    centred = lambda key: [item[key] - mean([i[key] for i in items]) for item in items]  # noqa: E731
    level_v = max(-1.0, min(1.0, 1.876 * mean([s["valence"] for s in plain]) + 0.068))  # nhãn V = valence đường nhãn
    level_t = 1.066 * mean([s["llmTension"] for s in level]) - 0.49  # đủ P0: mức T từ P0
    assert [s["valence"] for s in got] == [pytest.approx(level_v + d, abs=2e-3) for d in centred("dV")]
    assert [s["tension"] for s in got] == [pytest.approx(max(-1.0, min(1.0, level_t + d)), abs=2e-3) for d in centred("dT")]
    assert [(s["llmValence"], s["llmTension"]) for s in got] == [(s["llmValence"], s["llmTension"]) for s in level]
    assert [(s["studentValence"], s["studentTension"]) for s in got] == [(i["dV"], i["dT"]) for i in items]
    level_e = mean([s["arousal"] for s in plain])  # mức E = TB nhãn câu, hình E từ dE (Q06-E)
    assert [s["arousal"] for s in got] == [pytest.approx(max(-1.0, min(1.0, level_e + d)), abs=2e-3) for d in centred("dE")]
    assert [s["studentArousal"] for s in got] == [i["dE"] for i in items]
    for field in ("start", "end", "firstSegment", "lastSegment", "reason", "lines", "sd", "emotions", "confidence"):
        assert [s[field] for s in got] == [s[field] for s in level], field  # ranh giới, chữ không đổi
    # Không có LLM: học sinh vẫn chạy, mức T từ nhãn.
    no_llm = music_scenes.chapter_scenes(script, None, None, items)
    assert [s["moodSource"] for s in no_llm] == ["student"] * 3
    level_t_labels = 4.022 * mean([s["labelTension"] for s in no_llm]) - 0.056
    assert [s["tension"] for s in no_llm] == [pytest.approx(max(-1.0, min(1.0, level_t_labels + d)), abs=2e-3) for d in centred("dT")]
    # Thiếu mục ở một đoạn của chương: đường hôm nay (mức chương của P0 / nhãn).
    assert music_scenes.chapter_scenes(script, moods, student=items[:2]) == level
    assert music_scenes.chapter_scenes(script, None, None, items[:2]) == plain
    everything = music_scenes.book_scenes(book, moods, student=items)  # chương 2 không có mục nào (và không có LLM): đường nhãn
    assert everything[:3] == got and {s["moodSource"] for s in everything[3:]} == {"labels"}
