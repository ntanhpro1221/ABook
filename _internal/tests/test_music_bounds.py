"""Ranh giới cảnh do LLM chia (webui/music_bounds.py, "Y"): prompt và cửa sổ đúng bản đã đo, ánh xạ số câu -> id, tính cả cuốn tất định và
làm tiếp được, đoạn của music_plan / music_moods khớp nhau, móc của worker. Không gọi Ollama thật: HTTP được thay bằng bản giả."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from abook import worker
from abook.webui import music_bounds, music_moods, music_nnlite, music_plan, music_scenes, store
from tests.test_webui_listen_and_sync import make_project

# Băm SHA-256 (UTF-8) của SEG_PROMPT trong LLM_Train/music/seg_scenes.py lúc viết: lời gọi đã được đo bằng đúng chuỗi này.
SEG_PROMPT_SHA256 = "fcb3a5229d73f0c64bc1aeab875836a03d838845654d3c4ee7318197e07af0df"


def test_the_prompt_is_the_one_that_was_measured() -> None:
    assert hashlib.sha256(music_bounds.SEG_PROMPT.encode("utf-8")).hexdigest() == SEG_PROMPT_SHA256
    assert '{{"bat_dau": [' in music_bounds.SEG_PROMPT and music_bounds.SEG_PROMPT.endswith("{text}")
    assert (music_bounds.MODEL, music_bounds.PROMPT_VERSION, music_bounds.FILE) == ("qwen3.5:4b", "csseg-1", "music_bounds.json")
    assert (music_bounds.WINDOW, music_bounds.OVERLAP) == (12000, 2000)


# ---- cửa sổ -------------------------------------------------------------------------------------------------------------------

def _chapter(chapter: int, lines: int, *, first_id: int = 1000, step: int = 3, seconds: float = 6.0, wide: bool = False) -> dict:
    """Chương `lines` câu: `seq` 1..lines, `id` là khoá DB cả cuốn (cách nhau `step`, khác `seq`), mỗi câu `seconds` giây."""
    segments, clock = [], 0.0
    for index in range(lines):
        text = f"Câu  {chapter}-{index}\t thứ " + "chữ " * (index % 17 + (60 if wide else 0))
        segments.append({"id": first_id + index * step, "seq": index + 1, "text": text, "kind": "narration", "emotion": "neutral",
                         "intensity": 0, "start": clock, "end": clock + seconds})
        clock += seconds + 0.4
    return {"chapterId": chapter, "segments": segments}


def _reference_windows(rows: list[tuple[int, str]]) -> list[str]:
    """Bản chép NGUYÊN VĂN `windows` của LLM_Train/music/seg_scenes.py (chỉ đổi `s['id']` thành số câu đưa vào)."""
    segs = [{"id": number, "text": text} for number, text in rows]
    window, overlap = 12000, 2000
    lines = [f"{s['id']}\t{' '.join(str(s.get('text') or '').split())}" for s in segs]
    out, start = [], 0
    while start < len(lines):
        size, end = 0, start
        while end < len(lines) and size + len(lines[end]) + 1 <= window:
            size += len(lines[end]) + 1
            end += 1
        end = max(end, start + 1)
        out.append("\n".join(lines[start:end]))
        if end >= len(lines):
            break
        back, size = end, 0
        while back > start + 1 and size < overlap:
            back -= 1
            size += len(lines[back]) + 1
        start = back
    return out


def test_windows_match_the_measured_ones_string_by_string_and_show_the_chapter_numbers() -> None:
    script = _chapter(1, 420, wide=True)
    segments = script["segments"]
    mine = music_bounds.windows(segments)
    assert len(mine) >= 4, "đủ dài để có nhiều cửa sổ và phần lấn"
    assert mine == _reference_windows([(s["seq"], s["text"]) for s in segments])
    # Model thấy `seq` của chương, KHÔNG phải `id` của DB (id ở đây 1000, 1003, ...).
    assert mine[0].split("\n")[0].startswith("1\tCâu 1-0 thứ") and "\t1000\t" not in mine[0] and "1003\t" not in mine[0]
    assert all(len(window) <= music_bounds.WINDOW for window in mine)
    first = {int(line.split("\t")[0]) for line in mine[0].split("\n")}
    second = {int(line.split("\t")[0]) for line in mine[1].split("\n")}
    assert first & second, "cửa sổ sau lấn sang cửa sổ trước"
    assert music_bounds.windows([]) == []


def test_a_very_long_sentence_still_gets_its_own_window_like_the_measured_code() -> None:
    segments = [{"id": 1, "seq": 1, "text": "a " * 9000}, {"id": 2, "seq": 2, "text": "ngắn"}]
    assert music_bounds.windows(segments) == _reference_windows([(1, "a " * 9000), (2, "ngắn")])


def test_numbers_are_the_chapter_seq_and_fall_back_to_the_position_when_it_is_missing_or_not_unique() -> None:
    assert music_bounds.local_numbers([{"seq": 5}, {"seq": 9}, {"seq": 12}]) == [5, 9, 12]
    assert music_bounds.local_numbers([{"id": 7}, {"id": 9}]) == [1, 2], "chữ đọc theo chụp từ bản cũ chưa mang seq"
    assert music_bounds.local_numbers([{"seq": 1}, {"seq": 1}]) == [1, 2]
    assert music_bounds.local_numbers([{"seq": 1}, {"id": 2}]) == [1, 2]
    assert music_bounds.local_numbers([]) == []


def test_the_chapter_script_carries_the_seq_of_every_sentence(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    for chapter, expected in ((1, [1, 2, 3]), (2, [1, 2])):
        segments = store.chapter_script(project, chapter)["segments"]
        assert [segment["seq"] for segment in segments] == expected
    assert [s["id"] for s in store.chapter_script(project, 2)["segments"]] == [4, 5], "id là khoá DB cả cuốn, khác seq"


# ---- ánh xạ số câu -> id --------------------------------------------------------------------------------------------------------

def test_bound_numbers_map_back_to_ids_dropping_unknown_duplicate_and_first_sentence() -> None:
    segments = _chapter(1, 50)["segments"]  # id = 1000 + 3 * (seq - 1)
    got = music_bounds.chapter_bounds(segments, [30, 12, 12, 999, 0, -4, 1, 31])
    assert got == [1000 + 3 * 11, 1000 + 3 * 29, 1000 + 3 * 30], "theo thứ tự đọc, không trùng, bỏ số ngoài chương và câu đầu"
    assert music_bounds.chapter_bounds(segments, []) == []


# ---- hỏi một cửa sổ -----------------------------------------------------------------------------------------------------------

class FakeSession:
    def __init__(self, response: Any) -> None:
        self.response, self.calls = response, []

    def post(self, url: str, json: dict, timeout: float) -> Any:  # noqa: A002 - đúng tên tham số của requests
        self.calls.append((url, json, timeout))
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"response": self.response})


def test_ask_window_sends_the_measured_request_and_reads_the_numbers() -> None:
    session = FakeSession('{"bat_dau": [12, "40", 77.0]}')
    assert music_bounds.ask_window("http://127.0.0.1:11439/", "1\ta\n2\tb", session=session) == [12, 40, 77]
    (url, body, timeout), = session.calls
    assert url == "http://127.0.0.1:11439/api/generate" and timeout == 300
    assert body == {"model": "qwen3.5:4b", "prompt": music_bounds.SEG_PROMPT.format(text="1\ta\n2\tb"), "stream": False,
                    "think": False, "format": "json",
                    "options": {"temperature": 0, "num_ctx": 16384, "num_predict": 300}}
    assert "seed" not in body["options"], "phép đo không đặt seed"


def test_a_window_the_model_answers_badly_has_no_bounds() -> None:
    for bad in ("không phải JSON", '{"khac": [1]}', '{"bat_dau": "hai"}', '{"bat_dau": [1, "x"]}', '{"bat_dau": 5}', "[1, 2]", "null", None):
        assert music_bounds.ask_window("http://x", "t", session=FakeSession(bad)) == [], bad


def test_ollama_not_answering_raises() -> None:
    def broken() -> None:
        raise ConnectionError("Ollama chết")

    session = SimpleNamespace(post=lambda url, json, timeout: SimpleNamespace(raise_for_status=broken))
    with pytest.raises(ConnectionError):
        music_bounds.ask_window("http://x", "t", session=session)


# ---- load ---------------------------------------------------------------------------------------------------------------------

def test_load_gives_the_shape_book_scenes_wants_and_ignores_a_wrong_or_broken_file(tmp_path: Path) -> None:
    assert music_bounds.load(tmp_path) is None
    good = {"version": 1, "prompt": music_bounds.PROMPT_VERSION, "chapters": {"7": [30, 61], "8": []}}
    path = tmp_path / music_bounds.FILE
    path.write_text(json.dumps(good), encoding="utf-8")
    assert music_bounds.load(tmp_path) == {7: {"llm": {30: "llm", 61: "llm"}}, 8: {"llm": {}}}
    for changed in ({"prompt": "csseg-0"}, {"version": 2}, {"chapters": [1]}, {"chapters": {"7": 5}}, {"chapters": {"x": [1]}}):
        path.write_text(json.dumps({**good, **changed}), encoding="utf-8")
        assert music_bounds.load(tmp_path) is None, changed
    path.write_text("{hỏng", encoding="utf-8")
    assert music_bounds.load(tmp_path) is None


# ---- compute ------------------------------------------------------------------------------------------------------------------

def _answer(text: str) -> list[int]:
    """Ollama giả cố định: cứ mỗi số câu chia hết cho 25 là một cảnh mới (đọc từ chính cột đầu của cửa sổ)."""
    return [number for number in (int(line.split("\t")[0]) for line in text.split("\n")) if number % 25 == 0]


@pytest.fixture
def book(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    # Chương 1 và 3 một cửa sổ; chương 2 nhiều cửa sổ (câu rộng); chương 3 ngắn (một đoạn).
    scripts = [_chapter(1, 100), _chapter(2, 420, first_id=5000, wide=True), _chapter(3, 28, first_id=9000)]
    monkeypatch.setattr(music_plan, "book_scripts", lambda _root: iter(scripts))
    monkeypatch.setattr(music_moods, "model_digest", lambda _base: "digest-1")
    monkeypatch.setattr(music_nnlite, "model", lambda: None)  # đây là bài thử RANH GIỚI: không học sinh NN-lite (đường dựng có nó: test_music_studio_nnlite.py)
    monkeypatch.setattr(music_bounds.time, "strftime", lambda *_args: "2026-10-15T00:00:00+0700")  # "built" cố định cho phép so từng byte
    return scripts


def _asking(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    asked: list[str] = []

    def ask(_base: str, text: str, *, session: Any = None) -> list[int]:
        asked.append(text)
        return _answer(text)

    monkeypatch.setattr(music_bounds, "ask_window", ask)
    return asked


def _compute(root: Path, **kwargs: Any) -> int:
    return music_bounds.compute(root, "http://x", log=lambda _line: None, **kwargs)


def _read(root: Path) -> dict:
    return json.loads((root / music_bounds.FILE).read_text(encoding="utf-8"))


def test_compute_asks_every_window_once_and_writes_the_ids_of_the_scene_starts(tmp_path: Path, book: list[dict],
                                                                              monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _asking(monkeypatch)
    expected = sum(len(music_bounds.windows(script["segments"])) for script in book)
    assert expected > 3 and _compute(tmp_path) == expected == len(asked)
    saved = _read(tmp_path)
    assert (saved["version"], saved["prompt"], saved["model"], saved["digest"]) == (1, "csseg-1", "qwen3.5:4b", "digest-1")
    ids = {script["chapterId"]: [s["id"] for s in script["segments"] if s["seq"] % 25 == 0] for script in book}
    assert saved["chapters"] == {str(chapter): ids[chapter] for chapter in ids}
    assert saved["chapters"]["1"] == [1000 + 3 * 24, 1000 + 3 * 49, 1000 + 3 * 74, 1000 + 3 * 99], "id của câu, không phải số câu"
    assert list(saved["chapters"]) == ["1", "2", "3"]


def test_the_file_is_the_same_byte_for_byte_straight_through_or_stopped_and_resumed(tmp_path: Path, book: list[dict],
                                                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _asking(monkeypatch)
    straight, again = tmp_path / "a", tmp_path / "b"
    straight.mkdir()
    again.mkdir()
    _compute(straight)
    total = len(asked)
    first_chapter = len(music_bounds.windows(book[0]["segments"]))
    for stop_at in (first_chapter, first_chapter + 1, total - 1):  # đúng giữa hai chương / giữa chương 2 / trước cửa sổ cuối
        for leftover in again.iterdir():
            leftover.unlink()
        asked.clear()
        assert _compute(again, stop_requested=lambda: len(asked) >= stop_at) == stop_at
        done = ["1", "2"] if stop_at == total - 1 else ["1"]
        assert list(_read(again)["chapters"]) == done, "chương dở dang không được ghi nửa chừng"
        asked.clear()
        _compute(again)
        assert (again / music_bounds.FILE).read_bytes() == (straight / music_bounds.FILE).read_bytes(), stop_at
        assert b"\r" not in (again / music_bounds.FILE).read_bytes()


def test_a_chapter_cut_in_the_middle_is_not_written_and_uses_the_cues(tmp_path: Path, book: list[dict],
                                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _asking(monkeypatch)
    first_chapter = len(music_bounds.windows(book[0]["segments"]))
    assert _compute(tmp_path, stop_requested=lambda: len(asked) > first_chapter) == first_chapter + 1
    assert list(_read(tmp_path)["chapters"]) == ["1"]
    assert set(music_bounds.load(tmp_path)) == {1}, "chương 2 chưa có đủ ranh: không dùng nửa chừng"


def test_same_digest_keeps_finished_chapters_and_another_digest_redoes_the_book(tmp_path: Path, book: list[dict],
                                                                              monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _asking(monkeypatch)
    first = _compute(tmp_path)
    before = (tmp_path / music_bounds.FILE).read_bytes()
    asked.clear()
    assert _compute(tmp_path) == 0 and not asked
    assert (tmp_path / music_bounds.FILE).read_bytes() == before, "không có gì mới thì không ghi lại file"
    monkeypatch.setattr(music_moods, "model_digest", lambda _base: "digest-2")
    assert _compute(tmp_path) == first
    assert _read(tmp_path)["digest"] == "digest-2"


def test_a_chapter_whose_sentences_changed_is_asked_again(tmp_path: Path, book: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    _asking(monkeypatch)
    _compute(tmp_path)
    book[0] = _chapter(1, 100, first_id=2000)  # đổi id câu: ranh cũ không còn trỏ vào đâu
    asked = _asking(monkeypatch)
    assert _compute(tmp_path) == len(asked) == len(music_bounds.windows(book[0]["segments"]))
    assert _read(tmp_path)["chapters"]["1"][0] == 2000 + 3 * 24


def test_pausing_waits_between_windows_without_asking(tmp_path: Path, book: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _asking(monkeypatch)
    sleeps: list[float] = []
    # Chỉ đồng hồ của music_bounds: thay `time.sleep` toàn cục thì bắt cả lời ngủ của luồng nền do test khác để lại (hàng đợi sản xuất ngủ 15 giây).
    clock = music_bounds.time
    monkeypatch.setattr(music_bounds, "time", SimpleNamespace(**{name: getattr(clock, name) for name in dir(clock) if not name.startswith("_")}))
    monkeypatch.setattr(music_bounds.time, "sleep", sleeps.append)
    paused = lambda: bool(asked) and len(sleeps) < 3  # noqa: E731
    total = _compute(tmp_path, pause_requested=paused)
    assert len(sleeps) == 3 and total == len(asked)


def test_a_network_error_keeps_the_finished_chapters(tmp_path: Path, book: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def ask(_base: str, text: str, *, session: Any = None) -> list[int]:
        calls.append(text)
        if len(calls) == 2:
            raise ConnectionError("Ollama chết")
        return _answer(text)

    monkeypatch.setattr(music_bounds, "ask_window", ask)
    with pytest.raises(ConnectionError):
        _compute(tmp_path)
    assert list(_read(tmp_path)["chapters"]) == ["1"]


def test_compute_without_the_model_raises_and_writes_nothing(tmp_path: Path, book: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(music_moods, "model_digest", lambda _base: None)
    with pytest.raises(music_moods.MoodsUnavailable):
        _compute(tmp_path)
    assert not (tmp_path / music_bounds.FILE).exists()


# ---- chương nhiều ranh -----------------------------------------------------------------------------------------------------------

def test_dense_chapters_are_counted_logged_and_announced_without_changing_the_bounds(tmp_path: Path, book: list[dict],
                                                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    def ask(_base: str, text: str, *, session: Any = None) -> list[int]:
        # Chương 1 bị chia dày (cứ 10 câu một cảnh), chương 2 và 3 thưa như bình thường (cứ 25 câu).
        period = 10 if "Câu 1-" in text.split("\n")[0] else 25
        return [number for number in (int(line.split("\t")[0]) for line in text.split("\n")) if number % period == 0]

    monkeypatch.setattr(music_bounds, "ask_window", ask)
    lines: list[str] = []
    events: list[tuple[str, dict]] = []
    music_bounds.compute(tmp_path, "http://x", log=lines.append, emit=lambda kind, payload: events.append((kind, payload)))
    saved = _read(tmp_path)
    expected = {}
    for script in book:
        ids = saved["chapters"][str(script["chapterId"])]
        scenes = music_scenes.chapter_scenes(script, boundaries={"llm": {i: "llm" for i in ids}})
        per_hour = len(scenes) / ((scenes[-1]["end"] - scenes[0]["start"]) / 3600)
        expected[script["chapterId"]] = (len(ids), len(scenes), per_hour)
    dense = [chapter for chapter, (_b, _s, rate) in expected.items() if rate > 36]
    assert 0 < len(dense) < len(book), "bộ thử có cả chương dày và chương thưa"
    assert saved["dense"] == dense
    assert [(kind, payload["chapterId"]) for kind, payload in events] == [("music_bounds_dense", chapter) for chapter in dense]
    for kind, payload in events:
        bounds, scenes, rate = expected[payload["chapterId"]]
        assert payload == {"chapterId": payload["chapterId"], "bounds": bounds, "scenes": scenes, "perHour": round(rate, 1)}
    assert len(lines) == 3
    for line, chapter in zip(lines, expected):
        bounds, scenes, rate = expected[chapter]
        assert line == f"Chia cảnh (LLM): chương {chapter} - {bounds} ranh LLM, {scenes} đoạn, {rate:.1f} đoạn/giờ đọc"
    # Chỉ đếm: ranh trong file vẫn là đúng những gì model trả (không gộp bớt vì dày).
    assert saved["chapters"]["1"] == [s["id"] for s in book[0]["segments"] if s["seq"] % 10 == 0]
    assert dense == [1] and music_bounds.DENSE_PER_HOUR == 36.0


# ---- đoạn của music_plan / music_moods ---------------------------------------------------------------------------------------------

NEAR = lambda _v, _a: [{"link": "https://x/calm.mp3", "valence": 0.0, "arousal": 0.0, "family": "ambient"}]  # noqa: E731
LOOKUP = lambda links: {link: {"title": "t"} for link in links}  # noqa: E731


def _spans(scenes: list[dict]) -> list[tuple]:
    return [(scene["chapterId"], scene["firstSegment"], scene["lastSegment"]) for scene in scenes]


def test_without_the_file_the_plan_is_the_cue_scenes_exactly(tmp_path: Path, book: list[dict]) -> None:
    plan = music_plan.build(tmp_path, NEAR, LOOKUP)
    baseline = music_scenes.book_scenes(book)
    assert _spans(plan["scenes"]) == _spans(baseline) and not (tmp_path / music_bounds.FILE).exists()
    for scene, plain in zip(plan["scenes"], baseline):
        assert all(scene[field] == plain[field] for field in plain), scene["key"]


def test_with_the_file_the_plan_scenes_are_the_book_scenes_with_the_llm_bounds(tmp_path: Path, book: list[dict],
                                                                              monkeypatch: pytest.MonkeyPatch) -> None:
    _asking(monkeypatch)
    _compute(tmp_path)
    bounds = music_bounds.load(tmp_path)
    plan = music_plan.build(tmp_path, NEAR, LOOKUP)
    expected = music_scenes.book_scenes(book, boundaries=bounds)
    assert _spans(plan["scenes"]) == _spans(expected) != _spans(music_scenes.book_scenes(book))
    for scene, wanted in zip(plan["scenes"], expected):
        assert all(scene[field] == wanted[field] for field in wanted), scene["key"]
    assert any(scene["reason"] == "llm" for scene in plan["scenes"])


def test_the_moods_are_keyed_on_the_same_scenes_as_the_plan(tmp_path: Path, book: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    _asking(monkeypatch)
    _compute(tmp_path)
    monkeypatch.setattr(music_moods, "ask", lambda _base, text, *, session=None: {"V": 1.0, "E": 0.0, "T": -1.0})
    music_moods.compute(tmp_path, "http://x", log=lambda _line: None)
    moods = music_moods.load(tmp_path)["scenes"]
    plan = music_plan.build(tmp_path, NEAR, LOOKUP)
    assert [(m["chapterId"], m["firstSegment"], m["lastSegment"]) for m in moods] == _spans(plan["scenes"])
    assert all(scene["moodSource"] == "chapter" for scene in plan["scenes"]), "không đoạn nào của llmVT bị bỏ âm thầm"
    # Nếu moods tính trên đoạn của luật dấu hiệu thì khoá đoạn lệch plan: chứng minh bằng cách tính lại không có ranh LLM.
    assert _spans(music_scenes.book_scenes(book)) != _spans(plan["scenes"])


def test_a_file_made_after_the_moods_makes_them_recomputed_for_the_new_scenes(tmp_path: Path, book: list[dict],
                                                                              monkeypatch: pytest.MonkeyPatch) -> None:
    asked_moods: list[str] = []
    monkeypatch.setattr(music_moods, "ask", lambda _base, text, *, session=None: asked_moods.append(text) or {"V": 0.0, "E": 0.0, "T": 0.0})
    music_moods.compute(tmp_path, "http://x", log=lambda _line: None)
    before = len(asked_moods)
    _asking(monkeypatch)
    _compute(tmp_path)
    asked_moods.clear()
    got = music_moods.compute(tmp_path, "http://x", log=lambda _line: None)
    assert got == len(asked_moods) > 0 and before > 0
    assert [(m["chapterId"], m["firstSegment"], m["lastSegment"]) for m in music_moods.load(tmp_path)["scenes"]] \
        == _spans(music_scenes.book_scenes(book, boundaries=music_bounds.load(tmp_path)))


# ---- móc ------------------------------------------------------------------------------------------------------------------------

def test_run_after_analysis_skips_without_the_model_or_when_music_is_off_and_never_unloads(tmp_path: Path, book: list[dict],
                                                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    asked, released = _asking(monkeypatch), []
    monkeypatch.setattr(music_moods, "release", released.append)
    events: list[tuple[str, dict]] = []
    run = lambda: music_bounds.run_after_analysis(tmp_path, "http://x", lambda: False, lambda _text: None,  # noqa: E731
                                                  lambda kind, payload: events.append((kind, payload)))
    monkeypatch.setattr(music_moods, "model_digest", lambda _base: None)
    run()
    assert not asked and not (tmp_path / music_bounds.FILE).exists()
    monkeypatch.setattr(music_moods, "model_digest", lambda _base: "digest-1")
    music_plan.write_overrides(tmp_path, {"enabled": False})
    run()
    assert not asked and not (tmp_path / music_bounds.FILE).exists()
    music_plan.write_overrides(tmp_path, {"enabled": True})
    run()
    assert asked and not released, "llmVT chạy ngay sau và dỡ model"
    assert events[-1] == ("music_bounds_done", {"asked": len(asked)})


def test_the_worker_hook_runs_the_scene_split_before_the_moods_and_defers_its_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(music_moods, "run_after_analysis", lambda *_a, **_k: calls.append("moods"))
    monkeypatch.setattr(music_bounds, "run_after_analysis", lambda *_a, **_k: calls.append("bounds"))
    run = lambda: worker.run_music_after_analysis(tmp_path, "http://x", lambda: False, lambda _line: None,  # noqa: E731
                                                  lambda *_args: None, pause_requested=lambda: False)
    run()
    assert calls == ["bounds", "moods"]

    def broken(*_args: Any, **_kwargs: Any) -> None:
        calls.append("bounds")
        raise ConnectionError("Ollama chết")

    calls.clear()
    monkeypatch.setattr(music_bounds, "run_after_analysis", broken)
    with pytest.raises(ConnectionError):  # lỗi tới dây chuyền (music_moods_skipped) sau khi các việc sau đã chạy
        run()
    assert calls == ["bounds", "moods"]


# ---- đổi bài mỗi giờ của cả cuốn (music_plan.build, SCENEY_SPEC 5b) ---------------------------------------------------------------

def _cue_plan(*chapters: list[tuple[float, float, str | None]]) -> dict:
    """Plan tối thiểu: mỗi chương một danh sách (đầu, cuối, bài) của các đoạn."""
    scenes = [{"chapterId": number, "key": f"{number}-{index}", "start": start, "end": end, "link": link}
              for number, spans in enumerate(chapters, 1) for index, (start, end, link) in enumerate(spans)]
    return {"enabled": True, "scenes": scenes}


def test_switches_per_hour_counts_cues_minus_one_per_chapter_over_the_hours_of_the_book() -> None:
    # Chương 1: hai đoạn đầu cùng bài gộp thành một mốc -> 2 mốc, 1 đổi bài. Chương 2: 2 bài khác nhau -> 1 đổi bài. Tổng 2 đổi bài / 1 giờ.
    plan = _cue_plan([(0, 600, "a"), (600, 1200, "a"), (1200, 1800, "b")], [(0, 900, "a"), (900, 1800, "c")])
    assert music_plan.switches_per_hour(plan) == pytest.approx(2.0)
    plan = _cue_plan([(0, 1800, "a"), (1800, 3600, "b")], [(0, 1800, "a"), (1800, 3600, "c")], [(0, 3600, None)])
    assert music_plan.switches_per_hour(plan) == pytest.approx(2 / 3.0), "chương im lặng không có mốc, không âm; vẫn tính giờ"
    assert music_plan.switches_per_hour({"enabled": False, "scenes": plan["scenes"]}) is None
    assert music_plan.switches_per_hour({"enabled": True, "scenes": []}) is None


def test_every_build_logs_the_rate_and_announces_it_only_above_the_cap(tmp_path: Path, book: list[dict]) -> None:
    lines: list[str] = []
    events: list[tuple[str, dict]] = []
    plan = music_plan.build(tmp_path, NEAR, LOOKUP, log=lines.append, emit=lambda kind, payload: events.append((kind, payload)))
    # NEAR cho một bài duy nhất: mọi đoạn cùng bài gộp thành một mốc, không đổi bài nào.
    assert music_plan.switches_per_hour(plan) == 0.0 and events == []
    assert lines == ["Nhạc nền: 0.0 đổi bài/giờ cả cuốn (trần 22)"]
    # 2 đổi bài trong 300 giây = 24 / giờ, vượt trần 22.
    lines.clear()
    music_plan.report_switches(_cue_plan([(0, 100, "a"), (100, 200, "b"), (200, 300, "a")]), lines.append,
                               lambda kind, payload: events.append((kind, payload)))
    assert lines == ["Nhạc nền: 24.0 đổi bài/giờ cả cuốn (trần 22)"] and events == [("music_switches_high", {"perHour": 24.0})]
    # Đúng trần thì không báo: 11 đổi bài trong 1800 giây = 22 / giờ.
    events.clear()
    spans = [(index * 150.0, index * 150.0 + 150.0, "ab"[index % 2]) for index in range(12)]
    music_plan.report_switches(_cue_plan(spans), lambda _line: None, lambda kind, payload: events.append((kind, payload)))
    assert events == []


def test_the_rate_and_the_high_event_land_in_the_projects_runtime_events(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sqlite3

    project = make_project(tmp_path)  # có project.sqlite3 với bảng runtime_events (bản rút gọn); dựng lại đủ cột như sổ thật
    with sqlite3.connect(project / "project.sqlite3") as connection:
        connection.executescript("DROP TABLE runtime_events; CREATE TABLE runtime_events (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                                 "timestamp REAL NOT NULL, level TEXT NOT NULL, code TEXT NOT NULL, message TEXT NOT NULL, details_json TEXT);")

    def events() -> list[tuple]:
        with sqlite3.connect(project / "project.sqlite3") as connection:
            return connection.execute("SELECT level, code, message, details_json FROM runtime_events ORDER BY id").fetchall()

    monkeypatch.setattr(music_plan, "switches_per_hour", lambda _plan: 18.5)
    music_plan.build(project, NEAR, LOOKUP)  # không truyền log / emit: ghi vào nhật ký chạy của dự án
    assert events() == [("info", "LOG", "Nhạc nền: 18.5 đổi bài/giờ cả cuốn (trần 22)", None)], "dưới trần: chỉ dòng nhật ký"
    monkeypatch.setattr(music_plan, "switches_per_hour", lambda _plan: 31.46)
    music_plan.build(project, NEAR, LOOKUP)
    rows = events()
    assert [row[1] for row in rows] == ["LOG", "LOG", "music_switches_high"]
    assert rows[1][2] == "Nhạc nền: 31.5 đổi bài/giờ cả cuốn (trần 22)"
    assert rows[2][0] == "warning" and json.loads(rows[2][3]) == {"perHour": 31.5}


def test_a_project_without_a_ledger_falls_back_to_python_logging(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    import logging

    assert music_plan.record_event(tmp_path, "info", "LOG", "x") is False, "thư mục không phải dự án"
    plan = _cue_plan([(0, 100, "a"), (100, 200, "b"), (200, 300, "a")])
    with caplog.at_level(logging.INFO, logger=music_plan.__name__):
        music_plan.report_switches(plan, music_plan.project_log(tmp_path), music_plan.project_emit(tmp_path))
    assert "24.0 đổi bài/giờ" in caplog.text and "music_switches_high" in caplog.text
