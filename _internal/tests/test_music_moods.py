"""Không khí cả đoạn do LLM đọc (webui/music_moods.py): hỏi / đọc kết quả / tính cả cuốn / áp vào đoạn nhạc, và móc sau pha
phân tích của dây chuyền (pipeline.py `after_analysis`). Không gọi Ollama thật: HTTP được thay bằng bản giả."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import abook.pipeline as pipeline_module
from abook.webui import music_moods, music_plan, music_scenes
from tests.test_webui_listen_and_sync import make_project

# Băm SHA-256 (UTF-8) của PROMPT trong LLM_Train/music/segment_mood_llm.py lúc viết: lời gọi đã được đo bằng đúng chuỗi này.
PROMPT_SHA256 = "223949ec98518ba0947bd145e56e8120466bb8181a33598a1ec8108cf8c48e9b"


def test_the_prompt_is_the_one_that_was_measured() -> None:
    assert hashlib.sha256(music_moods.PROMPT.encode("utf-8")).hexdigest() == PROMPT_SHA256
    assert '{{"V": số, "E": số, "T": số}}' in music_moods.PROMPT and music_moods.PROMPT.endswith("{text}")


class FakeSession:
    """Thay `requests`: ghi lại lời gọi và trả lời `response` (chuỗi JSON Ollama bọc trong khoá "response")."""

    def __init__(self, response: str | None) -> None:
        self.response, self.calls = response, []

    def post(self, url: str, json: dict, timeout: float) -> Any:  # noqa: A002 - đúng tên tham số của requests
        self.calls.append((url, json, timeout))
        body = {"response": self.response}
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: body)


def test_ask_sends_the_measured_request_and_parses_the_scores() -> None:
    session = FakeSession('{"V": 1.5, "E": -0.5, "T": 2}')
    got = music_moods.ask("http://127.0.0.1:11439/", "Câu một.\nCâu hai.", session=session)
    assert got == {"V": 1.5, "E": -0.5, "T": 2.0}
    (url, body, timeout), = session.calls
    assert url == "http://127.0.0.1:11439/api/generate" and timeout == 300
    assert body == {"model": "qwen3.5:4b", "prompt": music_moods.PROMPT.format(text="Câu một.\nCâu hai."), "stream": False,
                    "think": False, "format": "json", "options": {"temperature": 0, "num_ctx": 16384}, "keep_alive": "5m"}


def test_ask_clamps_to_the_scale_and_rejects_malformed_answers() -> None:
    assert music_moods.ask("http://x", "t", session=FakeSession('{"V": 9, "E": -7, "T": "1"}')) == {"V": 2.0, "E": -2.0, "T": 1.0}
    for bad in ('{"V": 1, "E": 1}', "không phải JSON", '{"V": "cao", "E": 0, "T": 0}', "[1, 2, 3]", None):
        assert music_moods.ask("http://x", "t", session=FakeSession(bad)) is None, bad


def test_scene_text_is_one_line_per_sentence_inside_the_range() -> None:
    segments = [{"text": f"  Câu   {n}\n tiếp "} for n in range(5)]
    assert music_moods.scene_text(segments, 1, 3) == "Câu 1 tiếp\nCâu 2 tiếp\nCâu 3 tiếp"


def test_model_digest_finds_the_model_with_or_without_latest(monkeypatch: pytest.MonkeyPatch) -> None:
    def tags(models: list[dict]) -> None:
        reply = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"models": models})
        monkeypatch.setattr("requests.get", lambda url, timeout: reply)

    tags([{"name": "qwen3:8b", "digest": "aaa"}, {"name": "qwen3.5:4b", "digest": "bbb"}])
    assert music_moods.model_digest("http://x") == "bbb"
    tags([{"name": "qwen3.5:4b:latest", "model": "qwen3.5:4b:latest", "digest": "ccc"}])
    assert music_moods.model_digest("http://x") == "ccc"
    tags([{"name": "qwen3:8b", "digest": "aaa"}])
    assert music_moods.model_digest("http://x") is None

    def down(url: str, timeout: float) -> None:
        raise ConnectionError("Ollama tắt")

    monkeypatch.setattr("requests.get", down)
    assert music_moods.model_digest("http://x") is None


# ---- load / compute --------------------------------------------------------------------------------------------------

def _script(chapter: int, lines: int, *, ids: int = 1) -> dict:
    """Chương `lines` câu, mỗi câu 6 giây, id từ `ids`. Câu trung tính: một đoạn duy nhất khi dài dưới 3 phút."""
    segments, clock = [], 0.0
    for index in range(lines):
        segments.append({"id": ids + index, "text": f"Câu {chapter}-{index}.", "kind": "narration", "emotion": "neutral",
                         "intensity": 0, "start": clock, "end": clock + 6.0})
        clock += 6.4
    return {"chapterId": chapter, "segments": segments}


@pytest.fixture
def book(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    scripts = [_script(1, 12), _script(2, 12, ids=101)]
    monkeypatch.setattr(music_plan, "book_scripts", lambda _root: iter(scripts))
    monkeypatch.setattr(music_moods, "model_digest", lambda _base: "digest-1")
    return scripts


def _asking(monkeypatch: pytest.MonkeyPatch, answers: list[Any] | None = None) -> list[str]:
    asked: list[str] = []

    def ask(_base: str, text: str, *, session: Any = None) -> dict | None:
        asked.append(text)
        return {"V": 1.0, "E": 0.0, "T": -1.0}

    monkeypatch.setattr(music_moods, "ask", ask)
    return asked


def test_load_ignores_a_file_made_with_another_prompt_or_version(tmp_path: Path) -> None:
    assert music_moods.load(tmp_path) is None
    good = {"version": 1, "prompt": music_moods.PROMPT_VERSION, "scenes": [{"chapterId": 1}]}
    (tmp_path / music_moods.FILE).write_text(json.dumps(good), encoding="utf-8")
    assert music_moods.load(tmp_path) == good
    for changed in ({"prompt": "vet-0"}, {"version": 2}, {"scenes": None}):
        (tmp_path / music_moods.FILE).write_text(json.dumps({**good, **changed}), encoding="utf-8")
        assert music_moods.load(tmp_path) is None, changed
    (tmp_path / music_moods.FILE).write_text("{hỏng", encoding="utf-8")
    assert music_moods.load(tmp_path) is None


def test_compute_asks_each_scene_once_and_writes_the_file(tmp_path: Path, book: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _asking(monkeypatch)
    assert music_moods.compute(tmp_path, "http://x", log=lambda _text: None) == 2 == len(asked)
    saved = music_moods.load(tmp_path)
    assert saved["digest"] == "digest-1" and saved["model"] == "qwen3.5:4b"
    assert [(item["chapterId"], item["firstSegment"], item["lastSegment"]) for item in saved["scenes"]] == [(1, 1, 12), (2, 101, 112)]
    assert saved["scenes"][0]["V"] == 1.0 and saved["scenes"][0]["T"] == -1.0
    assert asked[1].startswith("Câu 2-0.") and asked[1].count("\n") == 11, "mỗi câu một dòng, đúng các câu của đoạn"


def test_compute_keeps_scenes_with_the_same_digest_and_redoes_all_for_another(tmp_path: Path, book: list[dict],
                                                                              monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _asking(monkeypatch)
    music_moods.compute(tmp_path, "http://x", log=lambda _text: None)
    asked.clear()
    assert music_moods.compute(tmp_path, "http://x", log=lambda _text: None) == 0 and not asked
    monkeypatch.setattr(music_moods, "model_digest", lambda _base: "digest-2")
    assert music_moods.compute(tmp_path, "http://x", log=lambda _text: None) == 2
    assert music_moods.load(tmp_path)["digest"] == "digest-2"


def test_compute_drops_scenes_that_no_longer_exist_and_asks_only_for_the_new_ones(tmp_path: Path, book: list[dict],
                                                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    _asking(monkeypatch)
    music_moods.compute(tmp_path, "http://x", log=lambda _text: None)
    book[1] = _script(2, 12, ids=201)  # chương 2 đổi id câu: đoạn cũ không còn
    asked = _asking(monkeypatch)
    assert music_moods.compute(tmp_path, "http://x", log=lambda _text: None) == 1 == len(asked)
    assert [item["firstSegment"] for item in music_moods.load(tmp_path)["scenes"]] == [1, 201]


def test_stopping_midway_keeps_what_was_done(tmp_path: Path, book: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _asking(monkeypatch)
    # Dừng sau lượt hỏi đầu tiên (chương 1 xong, chương 2 chưa hỏi).
    assert music_moods.compute(tmp_path, "http://x", stop_requested=lambda: bool(asked), log=lambda _text: None) == 1
    assert [item["chapterId"] for item in music_moods.load(tmp_path)["scenes"]] == [1]
    # Làm tiếp: chỉ còn chương 2.
    assert music_moods.compute(tmp_path, "http://x", log=lambda _text: None) == 1
    assert [item["chapterId"] for item in music_moods.load(tmp_path)["scenes"]] == [1, 2]


def test_pausing_waits_between_questions_without_asking(tmp_path: Path, book: list[dict],
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _asking(monkeypatch)
    # Tạm dừng (gác pin) sau lượt đầu: đứng chờ, không hỏi thêm; ba lần ngủ rồi bỏ tạm dừng thì làm tiếp tới hết.
    sleeps: list[float] = []
    monkeypatch.setattr(music_moods.time, "sleep", sleeps.append)
    paused = lambda: bool(asked) and len(sleeps) < 3  # noqa: E731
    assert music_moods.compute(tmp_path, "http://x", pause_requested=paused, log=lambda _text: None) == 2
    assert len(sleeps) == 3 and len(asked) == 2


def test_a_network_error_midway_still_saves_finished_scenes(tmp_path: Path, book: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def ask(_base: str, text: str, *, session: Any = None) -> dict | None:
        calls.append(text)
        if len(calls) == 2:
            raise ConnectionError("Ollama chết")
        return {"V": 0.0, "E": 0.0, "T": 0.0}

    monkeypatch.setattr(music_moods, "ask", ask)
    with pytest.raises(ConnectionError):
        music_moods.compute(tmp_path, "http://x", log=lambda _text: None)
    assert [item["chapterId"] for item in music_moods.load(tmp_path)["scenes"]] == [1]


def test_a_scene_the_model_cannot_answer_is_left_to_the_labels(tmp_path: Path, book: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(music_moods, "ask", lambda _base, text, *, session=None: None)
    assert music_moods.compute(tmp_path, "http://x", log=lambda _text: None) == 2
    assert music_moods.load(tmp_path)["scenes"] == []


def test_compute_without_the_model_raises(tmp_path: Path, book: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(music_moods, "model_digest", lambda _base: None)
    with pytest.raises(music_moods.MoodsUnavailable):
        music_moods.compute(tmp_path, "http://x")


def test_run_after_analysis_skips_without_the_model_or_when_music_is_off(tmp_path: Path, book: list[dict],
                                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    asked, released = _asking(monkeypatch), []
    monkeypatch.setattr(music_moods, "release", released.append)
    events: list[tuple[str, dict]] = []
    run = lambda: music_moods.run_after_analysis(tmp_path, "http://x", lambda: False, lambda _text: None,  # noqa: E731
                                                 lambda kind, payload: events.append((kind, payload)))
    monkeypatch.setattr(music_moods, "model_digest", lambda _base: None)
    run()
    assert not asked and not released
    monkeypatch.setattr(music_moods, "model_digest", lambda _base: "digest-1")
    music_plan.write_overrides(tmp_path, {"enabled": False})
    run()
    assert not asked and not released
    music_plan.write_overrides(tmp_path, {"enabled": True})
    run()
    assert len(asked) == 2 and released == ["http://x"] and events == [("music_moods_done", {"asked": 2})]


def test_run_after_analysis_unloads_the_model_even_when_it_fails(tmp_path: Path, book: list[dict],
                                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    def ask(_base: str, text: str, *, session: Any = None) -> dict | None:
        raise ConnectionError("hỏng")

    released: list[str] = []
    monkeypatch.setattr(music_moods, "ask", ask)
    monkeypatch.setattr(music_moods, "release", released.append)
    with pytest.raises(ConnectionError):
        music_moods.run_after_analysis(tmp_path, "http://x", lambda: False, lambda _text: None, lambda *_args: None)
    assert released == ["http://x"]


# ---- áp vào đoạn ------------------------------------------------------------------------------------------------------

def _scene_script(*, ids: int = 1, lines: int = 12, emotion: str = "neutral") -> dict:
    segments, clock = [], 0.0
    for index in range(lines):
        segments.append({"id": ids + index * 10, "text": "Gió thổi nhẹ.", "kind": "narration", "emotion": emotion,
                         "intensity": 2, "start": clock, "end": clock + 6.0})
        clock += 6.4
    return {"chapterId": 7, "segments": segments}


def _mood(first: int, last: int, v: float, t: float, chapter: int = 7) -> dict:
    return {"chapterId": chapter, "firstSegment": first, "lastSegment": last, "V": v, "E": 0.0, "T": t}


def test_a_scene_takes_valence_and_tension_from_the_llm_weighted_by_overlap() -> None:
    script = _scene_script(ids=1)  # id 1, 11, 21, ... không liền nhau: so theo vị trí câu, không theo id
    ids = [segment["id"] for segment in script["segments"]]
    moods = [_mood(ids[0], ids[2], 2.0, 2.0), _mood(ids[3], ids[11], -2.0, 0.0)]  # 3 câu rồi 9 câu, mỗi câu 6 giây
    plain, = music_scenes.chapter_scenes(script)
    scene, = music_scenes.chapter_scenes(script, moods)
    # Giá trị LLM (trung bình theo giây của phần chồng lên đoạn) được giữ ở llmValence / llmTension; mức chương (một đoạn duy nhất:
    # phần dời bằng 0) đặt valence = 1.876 * nhãn + .068 và tension = 1.066 * T_LLM - .49 (nhãn trung tính: valence nhãn = 0).
    assert scene["llmValence"] == pytest.approx(-0.5, abs=1e-3) and scene["llmTension"] == pytest.approx(0.25, abs=1e-3)
    assert scene["labelValence"] == 0.0
    assert scene["valence"] == pytest.approx(0.068, abs=1e-3) and scene["tension"] == pytest.approx(1.066 * 0.25 - 0.49, abs=1e-3)
    assert scene["moodSource"] == "chapter" and plain["moodSource"] == "labels"
    for field in ("arousal", "sd", "emotions", "confidence", "start", "end", "firstSegment", "lastSegment", "reason", "lines"):
        assert scene[field] == plain[field], field


def _level_scene(start: float, end: float, label: float, p_v: float, p_t: float, source: str = "llm") -> dict:
    """Đoạn tối thiểu cho `apply_chapter_level`: valence / tension đang là của LLM (p_v, p_t trên [-1, 1])."""
    return {"start": start, "end": end, "labelValence": label, "valence": p_v, "tension": p_t, "arousal": 0.3,
            "moodSource": source}


def test_chapter_level_shifts_the_llm_shape_around_the_chapter_level_with_numbers_worked_by_hand() -> None:
    # Ba đoạn 60 / 120 / 60 giây. TB(nhãn) = (.2*60 + 0*120 - .2*60) / 240 = 0 -> L_V = .068.
    # TB(pT) = (.8*60 + .6*120 + .4*60) / 240 = .6 -> L_T = 1.066 * .6 - .49 = .1496. TB(pV) = (.5*60 + .1*120 - .3*60) / 240 = .1.
    scenes = [_level_scene(0, 60, 0.2, 0.5, 0.8), _level_scene(60, 180, 0.0, 0.1, 0.6), _level_scene(180, 240, -0.2, -0.3, 0.4)]
    before = [dict(scene) for scene in scenes]
    got = music_scenes.apply_chapter_level(scenes)
    assert scenes == before, "thuần hàm: không sửa đoạn đưa vào"
    assert [scene["valence"] for scene in got] == [pytest.approx(0.268), pytest.approx(0.068), pytest.approx(-0.132)]
    assert [scene["tension"] for scene in got] == [pytest.approx(0.25), pytest.approx(0.15), pytest.approx(0.05)]  # .2496 / .1496 / .0496
    assert [scene["llmValence"] for scene in got] == [0.5, 0.1, -0.3]
    assert [scene["llmTension"] for scene in got] == [0.8, 0.6, 0.4]
    assert all(scene["moodSource"] == "chapter" and scene["arousal"] == 0.3 for scene in got)


def test_chapter_level_is_clipped_to_the_scale() -> None:
    # Hai đoạn dài bằng nhau, nhãn +.45: L_V = 1.876 * .45 + .068 = .9122; pV = 1 / 0 (TB .5) dời +-.25: .9122 + .25 > 1 -> 1.0,
    # còn đoạn kia .9122 - .25 = .6622 (clip chỉ cắt phần vượt).
    top = music_scenes.apply_chapter_level([_level_scene(0, 60, 0.45, 1.0, 0.0), _level_scene(60, 120, 0.45, 0.0, 0.0)])
    assert [scene["valence"] for scene in top] == [1.0, pytest.approx(0.662)]
    # Mức L_V cũng bị cắt TRƯỚC khi cộng phần dời: nhãn +.9 -> L_V = 1.7564 -> 1, rồi 1 +- .25 -> 1.0 và .75; nhãn -.9 -> -1.6 -> -1,
    # rồi -1 +- .25 -> -.75 và -1.0. T = -1 mọi đoạn: L_T = -1.556 -> -1.
    high = music_scenes.apply_chapter_level([_level_scene(0, 60, 0.9, 0.5, 1.0), _level_scene(60, 120, 0.9, -0.5, 1.0)])
    assert [scene["valence"] for scene in high] == [1.0, 0.75]
    low = music_scenes.apply_chapter_level([_level_scene(0, 60, -0.9, 0.5, -1.0), _level_scene(60, 120, -0.9, -0.5, -1.0)])
    assert [scene["valence"] for scene in low] == [-0.75, -1.0] and [scene["tension"] for scene in low] == [-1.0, -1.0]
    # T = +1 mọi đoạn: L_T = 1.066 - .49 = .576 (P0 chấm cao nhất cũng không còn cho tension 1).
    peak = music_scenes.apply_chapter_level([_level_scene(0, 60, 0.0, 0.0, 1.0), _level_scene(60, 120, 0.0, 0.0, 1.0)])
    assert [scene["tension"] for scene in peak] == [pytest.approx(0.576)] * 2


def test_chapter_level_leaves_a_chapter_alone_when_any_scene_has_no_llm_reading() -> None:
    mixed = [_level_scene(0, 60, 0.2, 0.5, 0.8), _level_scene(60, 120, 0.0, 0.1, 0.6, source="labels")]
    assert music_scenes.apply_chapter_level(mixed) == mixed
    assert music_scenes.apply_chapter_level([]) == []
    assert music_scenes.apply_chapter_level([_level_scene(5, 5, 0.2, 0.5, 0.8)])[0]["moodSource"] == "llm", "tổng thời lượng 0"
    # Qua chapter_scenes: LLM mới đọc đoạn đầu -> đoạn đầu "llm", đoạn sau "labels", không đoạn nào thành "chapter"; vẫn có nhãn.
    script = _two_scene_script()
    first_ids = [segment["id"] for segment in script["segments"]]
    scenes = music_scenes.chapter_scenes(script, [_mood(first_ids[0], first_ids[11], 2.0, 2.0)])
    assert [scene["moodSource"] for scene in scenes] == ["llm", "labels"]
    assert all("labelValence" in scene for scene in scenes)


def _two_scene_script() -> dict:
    """Hai đoạn trung tính dài bằng nhau (~76 giây): 12 câu, rồi câu mở "Sáng hôm sau" (ranh giới cứng) và 11 câu nữa."""
    script = _scene_script(ids=1, lines=24)
    script["segments"][12]["text"] = "Sáng hôm sau, gió vẫn thổi nhẹ."
    return script


def test_chapter_scenes_applies_the_chapter_level_when_every_scene_was_read_by_the_llm() -> None:
    script = _two_scene_script()
    ids = [segment["id"] for segment in script["segments"]]
    # Đoạn 1: V = 2 -> pV = 1, T = 2 -> pT = 1. Đoạn 2: V = 0, T = 0. Hai đoạn dài bằng nhau; nhãn trung tính: TB(nhãn) = 0.
    moods = [_mood(ids[0], ids[11], 2.0, 2.0), _mood(ids[12], ids[23], 0.0, 0.0)]
    first, second = music_scenes.chapter_scenes(script, moods)
    assert (first["lines"], second["lines"]) == (12, 12) and second["reason"] == "time_jump"
    # L_V = .068; TB(pV) = .5 -> .068 + .5 * (1 - .5) = .318 và .068 - .25 = -.182. L_T = 1.066 * .5 - .49 = .043 -> .293 và -.207.
    assert (first["valence"], second["valence"]) == (pytest.approx(0.318, abs=1e-3), pytest.approx(-0.182, abs=1e-3))
    assert (first["tension"], second["tension"]) == (pytest.approx(0.293, abs=1e-3), pytest.approx(-0.207, abs=1e-3))
    assert (first["llmValence"], second["llmValence"]) == (1.0, 0.0)
    assert first["moodSource"] == second["moodSource"] == "chapter"


def test_without_moods_the_scenes_are_exactly_the_label_scenes() -> None:
    script = _scene_script(emotion="sad")
    baseline = music_scenes.chapter_scenes(script)
    other_chapter = [_mood(1, 111, 2.0, 2.0, chapter=99)]
    unknown_ids = [_mood(5, 6, 2.0, 2.0)]  # id không có trong chương
    for moods in (None, [], other_chapter, unknown_ids):
        got = music_scenes.chapter_scenes(script, moods)
        assert got == baseline and all(scene["moodSource"] == "labels" for scene in got)
    assert baseline[0]["valence"] < 0, "đường nhãn: câu buồn cho valence âm"
    # Khác hệ cũ đúng một khoá: labelValence (đường nhãn trước khi LLM ghi đè) - ở đoạn "labels" nó chính là valence.
    assert all(scene["labelValence"] == scene["valence"] and "llmValence" not in scene for scene in baseline)


def test_the_llm_never_changes_where_the_scenes_split() -> None:
    lines = [("Gió thổi nhẹ.", "tender", 1, 6.0)] * 30 + [("Kiếm chém xuống!", "angry", 3, 5.0)] * 36
    segments, clock = [], 0.0
    for index, (text, emotion, intensity, seconds) in enumerate(lines, 1):
        segments.append({"id": index, "text": text, "kind": "narration", "emotion": emotion, "intensity": intensity,
                         "start": clock, "end": clock + seconds})
        clock += seconds + 0.4
    script = {"chapterId": 7, "segments": segments}
    moods = [_mood(1, 66, -2.0, 2.0)]
    shape = lambda scenes: [(s["firstSegment"], s["lastSegment"], s["reason"], s["start"], s["end"]) for s in scenes]  # noqa: E731
    assert shape(music_scenes.chapter_scenes(script, moods)) == shape(music_scenes.chapter_scenes(script))
    # Chương toàn đoạn LLM đọc thì thành "chapter" (mức chương, `apply_chapter_level`) - ranh giới vẫn y nguyên.
    assert all(scene["moodSource"] == "chapter" for scene in music_scenes.chapter_scenes(script, moods))


def test_a_built_plan_uses_the_moods_file_and_a_kept_plan_keeps_its_scenes(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    near = lambda _v, _a: [{"link": "https://x/calm.mp3", "valence": 0.0, "arousal": 0.0, "family": "ambient"}]  # noqa: E731
    lookup = lambda links: {link: {"title": "t"} for link in links}  # noqa: E731
    first = music_plan.build(project, near, lookup)
    assert all(scene["moodSource"] == "labels" for scene in first["scenes"])
    items = [{"chapterId": s["chapterId"], "firstSegment": s["firstSegment"], "lastSegment": s["lastSegment"],
              "V": 2.0, "E": 0.0, "T": -2.0} for s in first["scenes"]]
    (project / music_moods.FILE).write_text(json.dumps({"version": 1, "prompt": music_moods.PROMPT_VERSION, "scenes": items}),
                                            encoding="utf-8")
    second = music_plan.build(project, near, lookup)
    # Mọi đoạn LLM chấm V = 2, T = -2 -> pV = 1, pT = -1 giống nhau, phần dời bằng 0: tension = L_T = 1.066 * -1 - .49 -> -1.0
    # (clip); valence = L_V = 1.876 * TB(nhãn, trọng số giây) + .068 của chương ấy, cắt vào [-1, 1].
    assert all(s["moodSource"] == "chapter" and s["tension"] == -1.0 and s["llmValence"] == 1.0 for s in second["scenes"])
    for chapter in {s["chapterId"] for s in second["scenes"]}:
        scenes = [s for s in second["scenes"] if s["chapterId"] == chapter]
        label = sum((s["end"] - s["start"]) * s["labelValence"] for s in scenes) / sum(s["end"] - s["start"] for s in scenes)
        assert all(s["valence"] == pytest.approx(max(-1.0, min(1.0, 1.876 * label + 0.068)), abs=2e-3) for s in scenes)
    # Đưa sẵn đoạn (keep_scenes) thì không tính lại: đoạn đã mang valence / tension / moodSource.
    kept = music_plan.build(project, near, lookup, scenes=music_plan.scenes_of(first))
    assert all(s["moodSource"] == "labels" for s in kept["scenes"])


# ---- móc của dây chuyền -----------------------------------------------------------------------------------------------

class _Stop(Exception):
    """Dừng `run()` ngay sau pha phân tích (bài thử không cần pha giọng)."""


class _Analyzer:
    base_url = "http://ollama"
    stop_during_analysis = False
    instances: list["_Analyzer"] = []

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self.calls: list[str] = []
        _Analyzer.instances.append(self)

    def analyze_all(self, *_args: Any, **_kwargs: Any) -> None:
        self.calls.append("analyze_all")
        if _Analyzer.stop_during_analysis:
            raise pipeline_module.AnalysisRequestStopped("dừng")

    def release_model(self) -> None:
        self.calls.append("release_model")

    def unload(self) -> None:
        self.calls.append("unload")


def _pipeline(monkeypatch: pytest.MonkeyPatch, *, pending: bool, hook: Any) -> tuple[Any, list[str], list[tuple[str, dict]]]:
    _Analyzer.instances, _Analyzer.stop_during_analysis = [], False
    monkeypatch.setattr(pipeline_module, "OllamaBookAnalyzer", _Analyzer)
    logs: list[str] = []
    events: list[tuple[str, dict]] = []
    status = "pending" if pending else "analyzed"
    db = SimpleNamespace(begin_run_generation=lambda: None, update_book=lambda **_kw: None, casting_is_finalized=lambda: True,
                         list_segments=lambda: [{"status": status}, {"status": "analyzed"}])
    pipeline = object.__new__(pipeline_module.BookPipeline)
    pipeline.db, pipeline.settings, pipeline.quality_policy_hash = db, {}, "x"
    pipeline.stop_requested = lambda: False
    pipeline.emit = lambda kind, payload: events.append((kind, payload))
    pipeline.after_analysis = hook
    pipeline._completed_noop = False
    pipeline.log = logs.append
    pipeline._recover = lambda: None
    pipeline._ensure_segments = lambda: None
    pipeline._state = lambda *_args: None
    pipeline._wait_pause_or_stop = lambda: None
    pipeline._resource_gate = lambda *_args, **_kw: None
    pipeline._safe_export_reports = lambda **_kw: None

    def done(*_args: Any, **_kwargs: Any) -> None:
        raise _Stop

    pipeline.tts = SimpleNamespace(prepare_voice_presets=done)
    return pipeline, logs, events


def test_the_hook_runs_after_a_finished_analysis_with_the_model_already_unloaded(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    pipeline, _logs, _events = _pipeline(monkeypatch, pending=True, hook=lambda base: seen.append(base))
    with pytest.raises(_Stop):
        pipeline.run(recovery_already_run=True)
    assert seen == ["http://ollama"]
    assert _Analyzer.instances[0].calls == ["analyze_all", "release_model", "unload"], "dỡ model phân tích trước khi móc chạy"


def test_a_failing_hook_never_breaks_the_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    def hook(_base: str) -> None:
        raise RuntimeError("Ollama chết")

    pipeline, logs, events = _pipeline(monkeypatch, pending=True, hook=hook)
    with pytest.raises(_Stop):  # vẫn đi tiếp tới pha giọng
        pipeline.run(recovery_already_run=True)
    assert ("music_moods_skipped", {"reason": "Ollama chết"}) in events
    assert any("Ollama chết" in line for line in logs) and _Analyzer.instances[0].calls[-1] == "unload"


def test_the_hook_does_not_run_when_the_analysis_was_already_done(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    pipeline, _logs, _events = _pipeline(monkeypatch, pending=False, hook=seen.append)  # resume vào cuốn đã phân tích
    with pytest.raises(_Stop):
        pipeline.run(recovery_already_run=True)
    assert not seen


def test_the_hook_does_not_run_when_the_analysis_is_stopped(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    pipeline, _logs, _events = _pipeline(monkeypatch, pending=True, hook=seen.append)
    _Analyzer.stop_during_analysis = True
    with pytest.raises(pipeline_module.PipelineStopped):
        pipeline.run(recovery_already_run=True)
    assert not seen and _Analyzer.instances[0].calls == ["analyze_all", "unload"]
