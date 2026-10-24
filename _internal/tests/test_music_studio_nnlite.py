"""Nhạc theo cảnh của Studio dùng NN-lite + LVJ thay học sinh q06 (Corpus research/music/SPEC_studio_nnlite.md): `music_plan.build` dựng đoạn bằng đúng hàm của
Nghe ngay (`music_nnlite.chapter_scenes`), cả ranh LB (PLAN_studio_lb §6.1); model không nạp được thì đường cũ không học sinh, không ranh LB; gói q06 không còn
trong bộ cài."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from abook.webui import music_bounds, music_moods, music_nnlite, music_nnscene, music_plan, music_scenes, music_select
from tests.test_music_nnscene import chapter_text

NEAR = lambda _v, _a: [{"link": "https://x/calm.mp3", "valence": 0.0, "arousal": 0.0, "family": "ambient"}]  # noqa: E731
LOOKUP = lambda links: {link: {"title": "t"} for link in links}  # noqa: E731
ROOT = Path(__file__).resolve().parent.parent


def _script(chapter: int = 1) -> dict:
    """Kịch bản có nhãn câu như Studio: câu của chương bịa, xen câu buồn / câu hồi hộp."""
    script, _ = music_nnscene.chapter_script(chapter, "T", chapter_text(0, chapter))
    for index, segment in enumerate(script["segments"]):
        if index % 7 == 3:
            segment.update(emotion="sad", intensity=2)
        elif index % 11 == 5:
            segment.update(emotion="afraid", intensity=3)
    return script


@pytest.fixture(autouse=True)
def fresh_model(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(music_nnlite, "_loaded", None)
    yield
    monkeypatch.setattr(music_nnlite, "_loaded", None)


@pytest.fixture
def book(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    scripts = [_script(1), _script(2)]
    monkeypatch.setattr(music_plan, "book_scripts", lambda _root: iter(scripts))
    return scripts


def test_the_studio_plan_is_built_with_nn_lite_and_lvj_with_the_weak_mood_floor(tmp_path: Path, book: list[dict]) -> None:
    plan = music_plan.build(tmp_path, NEAR, LOOKUP, persist=False)
    scenes = plan["scenes"]
    assert scenes and all(scene["moodSource"] == "student" for scene in scenes)
    assert all(scene["levelSource"] == {"V": "lvj", "E": "lvj", "T": "lvj"} for scene in scenes), "mục NN-lite có chapterP nên LVJ chạy"
    assert all(scene["confidence"] >= music_select.WEAK_MOOD for scene in scenes), "sàn WEAK_MOOD như Nghe ngay"
    plain = [scene for script in book
             for scene in music_scenes.book_scenes([script], None, {script["chapterId"]: {music_nnlite.LB_SOURCE: music_nnlite.scene_bounds(script)}})]
    assert [(s["chapterId"], s["firstSegment"], s["lastSegment"]) for s in scenes] == [(s["chapterId"], s["firstSegment"], s["lastSegment"]) for s in plain], \
        "học sinh không đổi ranh đoạn: ranh của app + ranh LB"
    assert [s["valence"] for s in scenes] != [s["valence"] for s in plain]


def test_the_studio_scenes_are_the_shared_function_chapter_by_chapter(tmp_path: Path, book: list[dict]) -> None:
    got = music_plan.build(tmp_path, NEAR, LOOKUP, persist=False)["scenes"]
    wanted = [scene for script in book for scene in music_nnlite.chapter_scenes(script, music_nnlite.student_items, music_nnlite.scene_bounds)]
    for scene, expected in zip(got, wanted):
        assert all(scene[field] == expected[field] for field in expected), scene["key"]
    assert len(got) == len(wanted)



def test_the_lb_bounds_reach_the_studio_plan_of_a_sample_chapter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.test_music_nnlite import LB, _unique
    script, cuts = _unique(next(chapter for chapter in LB["chapters"] if len(chapter["bounds"]) >= 2))
    monkeypatch.setattr(music_plan, "book_scripts", lambda _root: iter([script]))
    scenes = music_plan.build(tmp_path, NEAR, LOOKUP, persist=False)["scenes"]
    lb = [scene["firstSegment"] for scene in scenes if scene["reason"] == music_nnlite.LB_REASON]
    assert lb and set(lb) <= set(cuts), "ranh LB vào plan Studio, đúng chỗ model LB chia"
    without = music_nnlite.chapter_scenes(script, music_nnlite.student_items)
    assert [s["firstSegment"] for s in scenes] != [s["firstSegment"] for s in without], "ranh LB đổi đoạn so với không LB"

def test_listen_now_and_the_studio_share_one_function(book: list[dict]) -> None:
    """Nghe ngay và Studio cùng một hàm: không ranh LB / moods / boundaries thì hai đường ra y hệt."""
    script = book[0]
    assert music_nnscene.chapter_scenes(script, music_nnlite.student_items, music_nnlite.scene_bounds) == \
        music_nnlite.chapter_scenes(script, music_nnlite.student_items, music_nnlite.scene_bounds)
    assert music_nnscene.chapter_scenes(script, music_nnlite.student_items) == music_nnlite.chapter_scenes(script, music_nnlite.student_items)


def test_without_the_model_the_studio_plan_takes_the_old_route_without_a_student(tmp_path: Path, book: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(music_nnlite, "MODEL_FILE", tmp_path / "khong_co.bin")
    scenes = music_plan.build(tmp_path, NEAR, LOOKUP, persist=False)["scenes"]
    plain = music_scenes.book_scenes(book)
    assert scenes and not any(scene["moodSource"] == "student" for scene in scenes)
    assert len(scenes) == len(plain) and all(all(scene[f] == p[f] for f in p) for scene, p in zip(scenes, plain))


def test_a_chapter_the_student_cannot_use_takes_the_old_route_with_the_moods_and_bounds_it_had(book: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    script = book[0]
    bounds = {"llm": {script["segments"][25]["id"]: "llm"}}
    base = music_scenes.chapter_scenes(script, None, bounds)
    moods = [{"chapterId": script["chapterId"], "firstSegment": s["firstSegment"], "lastSegment": s["lastSegment"], "V": 0.5, "E": 0.0, "T": -0.5} for s in base]
    nothing = lambda *_: None  # noqa: E731 - học sinh bỏ chương
    assert music_nnlite.chapter_scenes(script, nothing, moods=moods, boundaries=bounds) == music_scenes.chapter_scenes(script, moods, bounds)
    assert {s["moodSource"] for s in music_nnlite.chapter_scenes(script, nothing, moods=moods, boundaries=bounds)} == {"chapter"}


def test_the_llm_bounds_and_moods_still_shape_the_background_scenes_the_student_reads(tmp_path: Path, book: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    script = book[0]
    split = script["segments"][25]["id"]
    monkeypatch.setattr(music_bounds, "load", lambda _root: {script["chapterId"]: {"llm": {split: "llm"}}})
    seen: list[list[dict]] = []
    real = music_nnlite.student_items

    def student(chapter: dict, base: list[dict]) -> list[dict] | None:
        seen.append(base)
        return real(chapter, base)

    monkeypatch.setattr(music_nnlite, "student_items", student)
    scenes = music_plan.build(tmp_path, NEAR, LOOKUP, persist=False)["scenes"]
    assert any(scene["reason"] == "llm" for scene in scenes if scene["chapterId"] == script["chapterId"])
    assert seen and all(not any(scene.get("moodSource") == "student" for scene in base) for base in seen), "đoạn nền KHÔNG có học sinh"
    assert any(s["reason"] == "llm" for s in seen[0]), "học sinh đoán trên đoạn đã có ranh LLM"
    assert {s["moodSource"] for s in scenes} == {"student"}


def test_the_moods_file_is_used_for_the_background_scenes_and_the_student_still_wins(tmp_path: Path, book: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    base = music_scenes.book_scenes(book)
    moods = [{"chapterId": s["chapterId"], "firstSegment": s["firstSegment"], "lastSegment": s["lastSegment"], "V": 0.5, "E": 0.0, "T": -0.5} for s in base]
    monkeypatch.setattr(music_moods, "load", lambda _root: {"scenes": moods})
    scenes = music_plan.build(tmp_path, NEAR, LOOKUP, persist=False)["scenes"]
    assert all(scene["moodSource"] == "student" and "llmValence" in scene for scene in scenes), "P0 vào đoạn nền (llmValence), học sinh chỉnh quanh mức chương"


def test_the_plan_cache_key_names_nn_lite_with_lvj() -> None:
    assert music_nnscene.student_tag("abc") == "nnlite-lvj1-abc" and music_nnscene.student_tag("") == "none"
    assert music_nnscene.student_tag(music_nnlite.sha()).startswith("nnlite-lvj1-")


def test_the_q06_package_is_gone_from_the_app() -> None:
    assert importlib.util.find_spec("abook.webui.music_scene_student") is None
    needles = ("music_scene_student", "scene_q06", "scene_head_q06", "chapter_head_q06", "Học sinh không khí cảnh")
    roots = [ROOT / "abook", ROOT / "ui" / "src", ROOT / "mobile" / "android" / "app" / "src" / "main", ROOT / "mobile" / "src", ROOT / "shell" / "src-tauri"]
    found = []
    for root in roots:
        for path in root.rglob("*") if root.is_dir() else ():
            if path.suffix not in (".py", ".ts", ".tsx", ".kt", ".rs", ".json", ".txt", ".md") or "node_modules" in path.parts or "target" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            found += [f"{path.relative_to(ROOT)}: {needle}" for needle in needles if needle in text]
    assert not found, found
