"""Nhạc nền theo cảnh cho sách chỉ có chữ nghe bằng "Nghe ngay" (webui/music_nnscene.py, Corpus research/music/SPEC_nnscene_app.md): kịch bản
trần của một chương, ánh xạ câu -> đoạn màn đọc, dựng từng chương không lặp bài hơn dựng một lần, đệm theo khoá, hàng dựng nền, và đường máy chủ
(`music_cues` trả `pending` rồi mốc, luật ưu tiên: nhạc của người làm sách > lựa chọn của người nghe > theo cảnh mặc định)."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from abook.readaloud import paragraphs
from abook.webui import book_edits, music_nnlite, music_nnscene, music_plan, music_scenes, music_select
from abook.webui.music_catalog import MusicCatalog
from abook.webui.server import App, Server
from tests.catalog_signing import TEST_PUBLIC_KEY
from tests.test_music_catalog_and_select import _catalog_dir
from tests.test_music_playlist import _call, _text_book_server



@pytest.fixture(autouse=True)
def n0_path(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Các ca ở đây kiểm bộ dựng + đường máy chủ trên đường N0 (danh mục thử chỉ có vài bài quanh đích êm): không model NN-lite. NN-lite có ca riêng ở test_music_nnlite.py."""
    monkeypatch.setattr(music_nnlite, "MODEL_FILE", tmp_path_factory.getbasetemp() / "khong_co_nnlite.bin")
    monkeypatch.setattr(music_nnlite, "_loaded", None)


# ---- sách bịa ---------------------------------------------------------------------------------------------------------------

WORDS = ["gió", "đêm", "phố", "mưa", "cầu", "đèn", "sông", "bến", "người", "áo", "trăng", "thềm", "lửa", "ngõ", "chuông", "cửa"]
FAMILIES = ["piano", "eastern", "strings", "ambient", "guitar", "flute"]
TRACKS = {f"https://x/t{n:02d}.mp3": {"valence": round(0.02 + 0.015 * n, 3), "arousal": round(-0.72 + 0.012 * (n % 9), 3),
                                      "family": FAMILIES[n % len(FAMILIES)], "duration": 150 + 7 * n, "source": "incompetech"}
          for n in range(10)}


def near(_valence: float, _arousal: float) -> list[dict[str, Any]]:
    return [{"link": link, **info} for link, info in TRACKS.items()]


def lookup(links: list[str]) -> dict[str, dict[str, Any]]:
    return {link: {**TRACKS[link], "title": link.rsplit("/", 1)[-1], "creator": "K", "attribution": f"{link} CC BY"} for link in links if link in TRACKS}


def chapter_text(book: int, chapter: int, paragraph_count: int = 24) -> str:
    """Chữ một chương bịa: dòng tiêu đề, các đoạn nhiều câu, dấu ngăn cảnh "* * *" cứ vài đoạn một lần."""
    lines = [f"Chương {chapter + 1}: {WORDS[(book + chapter) % 16].capitalize()} {WORDS[(book * 3 + chapter) % 16]}", ""]
    for index in range(paragraph_count):
        sentences = [" ".join(WORDS[(book * 7 + chapter * 5 + index * 3 + word + sentence) % 16] for word in range(11)).capitalize() + "."
                     for sentence in range(4 + (index + book) % 4)]
        lines += [" ".join(sentences), ""]
        if index % 6 == 5:
            lines += ["* * *", ""]
    return "\n".join(lines).strip() + "\n"


class Book:
    """Một cuốn bịa: thứ tự chương, chữ, và các hàm `build_chapter` cần."""

    def __init__(self, tmp_path: Path, number: int, chapters: int = 9) -> None:
        self.number, self.order = number, list(range(1, chapters + 1))
        self.texts = {cid: chapter_text(number, cid) for cid in self.order}
        self.scenes = music_nnscene.SceneBook(tmp_path / f"scene{number}", {"book": "1", "catalog": "r1", "student": "none"})
        self.key = f"sach-{number}"

    def sha_of(self, cid: int) -> str:
        return music_nnscene.text_sha(self.texts[cid], None)

    def build(self, cid: int, **extra: Any) -> dict[str, Any]:
        return music_nnscene.build_chapter(self.scenes, self.order, cid, f"Chương {cid}", self.texts[cid], None, sha_of=self.sha_of, near=near,
                                           lookup=lookup, catalog_revision="r1", taxonomy=None, book_key=self.key, **extra)

    def one_shot(self, tmp_path: Path) -> list[dict[str, Any]]:
        """Plan dựng MỘT LẦN cả cuốn (đường Studio): các cảnh của mọi chương nối nhau rồi `music_plan.build`."""
        scenes: list[dict[str, Any]] = []
        for cid in self.order:
            script, _paragraph = music_nnscene.chapter_script(cid, f"Chương {cid}", self.texts[cid])
            scenes += music_nnscene.chapter_scenes(script)
        return music_plan.build(tmp_path / f"oneshot{self.number}", near, lookup, catalog_revision="r1", book_key=self.key, scenes=scenes,
                                persist=False)["scenes"]


def repeats_per_three_chapters(scenes: list[dict[str, Any]], order: list[int]) -> float:
    """Số lần "bài đã nghe trong 3 chương liền" của cả cuốn, chia số nhóm 3 chương."""
    by_chapter = {cid: [scene["link"] for scene in scenes if scene["chapterId"] == cid] for cid in order}
    groups = [order[start:start + 3] for start in range(0, len(order), 3)]
    total = 0
    for group in groups:
        links = [link for cid in group for link in by_chapter[cid] if link]
        total += len(links) - len(set(links))
    return total / len(groups)


# ---- kịch bản trần + đoạn màn đọc -----------------------------------------------------------------------------------------


def test_the_chapter_script_carries_only_what_was_measured() -> None:
    script, mapped = music_nnscene.chapter_script(3, "Tựa", chapter_text(1, 3))
    assert script["chapterId"] == 3 and len(mapped) == len(script["segments"])
    for segment in script["segments"]:
        assert set(segment) <= {"id", "text", "kind", "sceneBreak"} and segment["kind"] in ("heading", "narration")
    assert script["segments"][0]["kind"] == "heading" and all(s["kind"] == "narration" for s in script["segments"][1:])
    assert any(s.get("sceneBreak") for s in script["segments"]), "dấu * * * thành cờ sceneBreak của chính bộ tách"
    assert [segment["id"] for segment in script["segments"]] == list(range(len(script["segments"])))


def test_lines_the_listener_skips_never_reach_the_scene_script() -> None:
    text = chapter_text(1, 1)
    skipped = text.splitlines()[0]
    script, _ = music_nnscene.chapter_script(1, "T", text, [skipped])
    assert skipped not in [segment["text"] for segment in script["segments"]]
    assert music_nnscene.text_sha(text, [skipped]) != music_nnscene.text_sha(text, None)


def test_every_sentence_maps_to_the_reading_screens_paragraph_in_order() -> None:
    text = chapter_text(2, 4)
    script, mapped = music_nnscene.chapter_script(4, "T", text)
    pieces = paragraphs.split_paragraphs(paragraphs.without_lines(text, []))
    assert mapped == sorted(mapped) and mapped[0] == 0 and mapped[-1] <= len(pieces) - 1
    spoken = {index for index, piece in enumerate(pieces) if music_nnscene._letters(piece.text)}
    assert set(mapped) == spoken, "mỗi đoạn có chữ có câu bắt đầu ở đó (dấu * * * là một đoạn không chữ, không câu nào)"
    for sentence, paragraph in zip(script["segments"], mapped):
        assert sentence["text"][:12] in pieces[paragraph].text


# ---- dựng từng chương so với dựng một lần -----------------------------------------------------------------------------------


@pytest.mark.parametrize("number", [0, 1, 2])
def test_building_chapter_by_chapter_in_order_gives_the_one_shot_plan(tmp_path: Path, number: int) -> None:
    book = Book(tmp_path, number)
    reference = {scene["key"]: scene for scene in book.one_shot(tmp_path)}
    built = {}
    for cid in book.order:
        for scene in book.build(cid)["scenes"]:
            built[scene["key"]] = scene
    assert built.keys() == reference.keys()
    for key, scene in built.items():
        assert scene["link"] == reference[key]["link"], key
        assert [s["link"] for s in scene.get("siblings") or []] == [s["link"] for s in reference[key].get("siblings") or []], key


@pytest.mark.parametrize("number", [0, 1, 2])
def test_incremental_repeats_per_three_chapters_never_exceed_the_one_shot(tmp_path: Path, number: int) -> None:
    book = Book(tmp_path, number)
    one_shot = book.one_shot(tmp_path)
    # nghe lần lượt (có nghỉ giữa chừng: lần dựng sau chỉ thấy chương liền trước đã dựng)
    incremental = [scene for cid in book.order for scene in book.build(cid)["scenes"]]
    assert repeats_per_three_chapters(incremental, book.order) <= repeats_per_three_chapters(one_shot, book.order)
    # nhảy tới chương 5, nghe 5-9 rồi quay về 1-4: dựng không lịch sử ở chỗ nhảy, mà trong các chương liền nhau vẫn không lặp quá một lần
    jumped = Book(tmp_path / "jump", number)
    jumped_scenes = {cid: jumped.build(cid)["scenes"] for cid in [5, 6, 7, 8, 9, 1, 2, 3, 4]}
    flat = [scene for cid in jumped.order for scene in jumped_scenes[cid]]
    assert repeats_per_three_chapters(flat, jumped.order) <= repeats_per_three_chapters(one_shot, book.order) + 1.0


def test_a_chapter_built_after_a_jump_has_no_history_but_the_next_one_continues_from_it(tmp_path: Path) -> None:
    book = Book(tmp_path, 1)
    assert book.scenes.history(book.order, 5, book.sha_of) == [], "chương trước chưa dựng: không lịch sử"
    book.build(5)
    assert [record["chapterId"] for record in book.scenes.history(book.order, 6, book.sha_of)] == [5]
    book.build(6)
    assert [record["chapterId"] for record in book.scenes.history(book.order, 7, book.sha_of)] == [5, 6]
    assert book.scenes.history(book.order, 4, book.sha_of) == [], "chương 3 trở về trước chưa dựng"


# ---- mốc cho trình phát -----------------------------------------------------------------------------------------------------


def test_cues_carry_the_paragraph_where_each_scene_starts(tmp_path: Path) -> None:
    book = Book(tmp_path, 2)
    record = book.build(2)
    cues = music_nnscene.chapter_cues(record)
    openers = [cue for cue in cues if not cue.get("sibling")]
    assert openers and all(isinstance(cue["firstSegment"], int) for cue in openers)
    assert all("firstSegment" not in cue for cue in cues if cue.get("sibling"))
    pieces = paragraphs.split_paragraphs(paragraphs.without_lines(book.texts[2], []))
    first = [cue["firstSegment"] for cue in openers]
    assert first == sorted(first) and first[0] == 0 and first[-1] < len(pieces)
    assert [cue["start"] for cue in openers] == sorted(cue["start"] for cue in openers), "giây ước tăng dần cùng thứ tự đoạn"
    assert record["seconds"] > 0 and record["tracks"]


def test_the_plan_of_a_chapter_is_cached_until_its_text_or_key_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    book = Book(tmp_path, 0)
    first = book.build(1)
    monkeypatch.setattr(music_plan, "build", lambda *a, **k: pytest.fail("chương đã dựng không dựng lại"))
    assert book.build(1) == first
    monkeypatch.undo()
    book.texts[1] += "\nMột đoạn mới thêm vào cuối chương.\n"
    assert book.build(1)["textSha"] != first["textSha"], "chữ đổi thì dựng lại"
    # khoá đệm khác (bản danh mục, học sinh): thư mục khác, thư mục khoá cũ bị dọn
    other = music_nnscene.SceneBook(tmp_path / "scene0", {"book": "1", "catalog": "r1", "student": music_nnscene.student_tag("abc123")})
    assert other.directory != book.scenes.directory and other.read(1) is None
    assert not book.scenes.directory.exists() or not list(book.scenes.directory.glob("*.json"))
    assert music_nnscene.student_tag(None) == "none" and music_nnscene.student_tag("abc123") == "nnlite-lvj1-abc123"


# ---- học sinh là phần thêm: bỏ nó vẫn là cùng bộ dựng (đường N0) ---------------------------------------------------------------


def test_the_student_is_one_optional_step_and_dropping_it_is_the_n0_path() -> None:
    script, _ = music_nnscene.chapter_script(1, "T", chapter_text(0, 1))
    calls: list[list[dict[str, Any]]] = []

    def student(given: dict[str, Any], base: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        calls.append(base)
        return [{"chapterId": scene["chapterId"], "firstSegment": scene["firstSegment"], "lastSegment": scene["lastSegment"],
                 "dV": 0.1, "dE": -0.1, "dT": 0.2, "chapterV": 0.3} for scene in base]

    n0 = music_nnscene.chapter_scenes(script)
    assert n0 == music_scenes.book_scenes([script], None, None, None), "không học sinh = book_scenes(scripts, None, None, None)"
    with_student = music_nnscene.chapter_scenes(script, student)
    assert len(calls) == 1 and calls[0] == music_scenes.book_scenes([script]), "học sinh thấy các đoạn nền của chính chương"
    span = lambda scenes: [(s["chapterId"], s["firstSegment"], s["lastSegment"]) for s in scenes]  # noqa: E731
    assert span(with_student) == span(n0) and with_student != n0, "học sinh chỉ chỉnh V/E/T, không đổi ranh cảnh"
    assert music_nnscene.chapter_scenes(script, lambda *_: None) == n0, "học sinh trả None (chương không dùng được): cùng đường N0"



def _student_items(base: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"chapterId": scene["chapterId"], "firstSegment": scene["firstSegment"], "lastSegment": scene["lastSegment"],
             "dV": 0.1, "dE": 0.3, "dT": 0.2, "chapterV": 0.3} for scene in base]


def test_the_student_path_floors_confidence_at_weak_mood_and_nothing_else_changes() -> None:
    """NN-V (SPEC_nnv_app): đoạn `moodSource` = "student" có confidence >= WEAK_MOOD nên bộ chọn dùng V / E của học sinh, không kéo về đích êm."""
    script, _ = music_nnscene.chapter_script(1, "T", chapter_text(0, 1))
    student = lambda given, base: _student_items(base)  # noqa: E731
    raw = music_scenes.book_scenes([script], None, None, _student_items(music_scenes.book_scenes([script])))
    floored = music_nnscene.chapter_scenes(script, student)
    assert raw and all(scene["moodSource"] == "student" for scene in raw)
    assert all(float(scene["confidence"]) < music_select.WEAK_MOOD for scene in raw), "sách trần: confidence thật dưới sàn"
    assert [scene["confidence"] for scene in floored] == [music_select.WEAK_MOOD] * len(raw)
    assert [{k: v for k, v in scene.items() if k != "confidence"} for scene in floored] ==         [{k: v for k, v in scene.items() if k != "confidence"} for scene in raw], "chỉ confidence đổi"
    assert all(music_select.target_of(a) != music_select.target_of(b) for a, b in zip(floored, raw)), "đích V / E nay theo học sinh"
    assert all(music_select.target_of(a)[1] == pytest.approx(a["arousal"]) for a in floored), "confidence = WEAK_MOOD: đích E = E của đoạn"


def test_the_floor_never_touches_studios_path_or_the_n0_path() -> None:
    script, _ = music_nnscene.chapter_script(1, "T", chapter_text(0, 1))
    base = music_scenes.book_scenes([script])
    items = _student_items(base)
    # Studio gọi thẳng `book_scenes(..., items)` (không qua music_nnscene): confidence thật, không sàn.
    studio = music_scenes.book_scenes([script], None, None, items)
    assert all(float(scene["confidence"]) < music_select.WEAK_MOOD for scene in studio)
    assert studio == music_scenes.book_scenes([script], None, None, items), "thuần hàm, gọi lại không đổi"
    # N0: không đoạn học sinh -> không đổi.
    assert music_nnscene.chapter_scenes(script) == music_scenes.book_scenes([script], None, None, None)
    assert music_nnscene.chapter_scenes(script, lambda *_: None) == music_scenes.book_scenes([script], None, None, None)
    assert not any(scene.get("moodSource") == "student" for scene in music_nnscene.chapter_scenes(script))


# ---- hàng dựng nền ----------------------------------------------------------------------------------------------------------


def test_the_builder_runs_one_job_at_a_time_lowest_priority_number_first_and_never_twice() -> None:
    import threading

    gate, ran = threading.Event(), []
    builder = music_nnscene.Builder()

    def job(name: str):
        def run(_stop) -> None:
            if name == "first":
                gate.wait(5)
            ran.append(name)
        return run

    first = builder.submit("b", 1, 0, job("first"))
    time.sleep(0.05)  # việc đầu đang chạy, chờ cổng
    far, near_one, again = builder.submit("b", 4, 3, job("far")), builder.submit("b", 2, 1, job("near")), builder.submit("b", 4, 0, job("far2"))
    assert again is far and far.priority == 0, "cùng (cuốn, chương): một việc, nhận ưu tiên cao nhất"
    gate.set()
    assert first.done.wait(5) and far.done.wait(5) and near_one.done.wait(5)
    deadline = time.time() + 5
    while not builder.idle() and time.time() < deadline:
        time.sleep(0.01)
    assert ran == ["first", "far", "near"] and builder.idle()


def test_cancelling_a_book_drops_what_has_not_started_and_stops_what_is_running() -> None:
    import threading

    started, stopped = threading.Event(), threading.Event()
    builder = music_nnscene.Builder()

    def long_job(stop) -> None:
        started.set()
        while not stop():
            time.sleep(0.01)
        stopped.set()

    running = builder.submit("a", 1, 0, long_job)
    assert started.wait(5)
    queued = builder.submit("a", 2, 1, lambda _stop: pytest.fail("việc đã huỷ không chạy"))
    other = builder.submit("b", 1, 0, lambda _stop: None)
    builder.cancel_others("b")
    assert stopped.wait(5) and running.done.wait(5) and queued.done.wait(5) and queued.cancelled
    assert other.done.wait(5) and not other.cancelled


def test_a_failing_job_is_recorded_and_the_next_job_still_runs() -> None:
    builder = music_nnscene.Builder()

    def broken(_stop) -> None:
        raise RuntimeError("hỏng")

    bad = builder.submit("a", 1, 0, broken)
    good = builder.submit("a", 2, 1, lambda _stop: None)
    assert bad.done.wait(5) and good.done.wait(5) and isinstance(bad.error, RuntimeError) and good.error is None


# ---- máy chủ ----------------------------------------------------------------------------------------------------------------


def _scene_server(tmp_path: Path):
    app, book, server = _text_book_server(tmp_path)
    app._music_catalog = MusicCatalog(tmp_path / "music_cache2", str(_catalog_dir(tmp_path / "cloud2")), public_key=TEST_PUBLIC_KEY)
    app.music_track_available = lambda link, **_kwargs: True  # type: ignore[method-assign]
    return app, book, server


def _cues_when_ready(server, book: str, chapter: int = 1) -> dict[str, Any]:
    for _ in range(100):
        _status, reply = _call(server, "GET", f"/api/books/{book}/music/chapters/{chapter}")
        if not reply.get("pending"):
            return reply
        time.sleep(0.1)
    pytest.fail("nhạc theo cảnh không dựng xong")


def test_a_text_book_with_no_choice_gets_scene_cues_that_follow_the_reading_screen(tmp_path: Path) -> None:
    app, book, server = _scene_server(tmp_path)
    try:
        reply = _cues_when_ready(server, book)
        assert reply["scene"] is True and reply["cues"] and reply["estSeconds"] > 0
        assert all(isinstance(cue["firstSegment"], int) for cue in reply["cues"] if not cue.get("sibling"))
        assert all(cue["src"].startswith("/api/music/track?link=") for cue in reply["cues"]), "bài danh mục qua máy này"
        assert set(reply["credits"]) <= set(TRACKS_OF_CATALOG())
        # chương kế đã được dựng nền trước khi người nghe sang
        ahead = [cid for cid in range(2, 2 + music_nnscene.AHEAD_CHAPTERS)]
        deadline = time.time() + 10
        pending = ahead
        while pending and time.time() < deadline:
            pending = [cid for cid in ahead if _call(server, "GET", f"/api/books/{book}/music/chapters/{cid}")[1].get("pending")]
            time.sleep(0.1)
        assert not pending or ahead[0] not in pending
    finally:
        server.stop()


def TRACKS_OF_CATALOG() -> list[str]:
    from tests.test_music_catalog_and_select import TRACKS as CATALOG_TRACKS

    return list(CATALOG_TRACKS)


def test_a_chapter_not_yet_built_answers_pending_without_blocking_the_voice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import threading

    app, book, server = _scene_server(tmp_path)
    gate = threading.Event()
    real = music_nnscene.build_chapter
    monkeypatch.setattr(music_nnscene, "build_chapter", lambda *a, **k: (gate.wait(10), real(*a, **k))[1])
    monkeypatch.setattr(music_nnscene, "BUILD_WAIT_SECONDS", 0.05)
    try:
        _status, reply = _call(server, "GET", f"/api/books/{book}/music/chapters/1")
        assert reply["pending"] is True and reply["cues"] == [] and reply["levelDb"] == music_plan.DEFAULT_LEVEL_DB
        gate.set()
        assert _cues_when_ready(server, book)["cues"]
    finally:
        gate.set()
        server.stop()


def test_the_listeners_choice_beats_the_scene_default(tmp_path: Path) -> None:
    app, book, server = _scene_server(tmp_path)
    try:
        for choice in ("calm", "mine", "off"):
            _call(server, "PUT", f"/api/books/{book}/music", {"playlist": choice})
            _status, reply = _call(server, "GET", f"/api/books/{book}/music/chapters/1")
            assert reply["cues"] == [] and "pending" not in reply, choice
        _call(server, "PUT", f"/api/books/{book}/music", {"playlist": "scene"})
        assert _cues_when_ready(server, book)["cues"]
        _call(server, "PUT", f"/api/books/{book}/music", {"playlist": None})
        app.preferences.update({"autoMusic": False})
        _status, reply = _call(server, "GET", f"/api/books/{book}/music/chapters/1")
        assert reply["cues"] == [] and "pending" not in reply, "Tự chọn nhạc nền đã tắt thì chưa chọn gì = không nhạc"
        _call(server, "PUT", f"/api/books/{book}/music", {"playlist": "scene"})
        app.preferences.update({"autoMusic": False})
        assert _cues_when_ready(server, book)["cues"], "chọn rõ 'Theo cảnh' thì vẫn có nhạc"
    finally:
        server.stop()


def test_a_book_with_its_makers_music_never_gets_scene_cues(tmp_path: Path) -> None:
    import json

    app, book, server = _scene_server(tmp_path)
    try:
        folder = app._listenable(book)
        manifest = json.loads((folder / "book.json").read_text(encoding="utf-8"))
        manifest["music"] = {"levelDb": -20, "tracks": {}, "chapters": {}}
        (folder / "book.json").write_bytes(json.dumps(manifest, ensure_ascii=False).encode("utf-8"))
        _call(server, "PUT", f"/api/books/{book}/music", {"playlist": "scene"})
        assert app._scene_mode(book, folder) is False
        _status, reply = _call(server, "GET", f"/api/books/{book}/music/chapters/1")
        assert reply["cues"] == [] and "pending" not in reply and "scene" not in reply
        assert _call(server, "GET", f"/api/books/{book}/music/playlist")[1]["playlist"] is None
    finally:
        server.stop()


# ---- bài quá cỡ (soát a44): ô danh mục không có `bytes`, chỉ mảnh `tracks/` có ---------------------------------------------------------


def _real_availability(app: App) -> None:
    del app.music_track_available  # bỏ lambda của `_scene_server`: dùng hàm thật (cỡ theo danh mục, sổ bài quá cỡ)


def test_scene_music_never_picks_a_track_the_catalog_says_is_over_the_size_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui.server import MUSIC_TRACK_MAX_BYTES

    app, book, server = _scene_server(tmp_path / "plain")
    try:
        wanted = {cue["link"] for cue in _cues_when_ready(server, book)["cues"]}  # những bài máy chọn khi chưa có trần
    finally:
        server.stop()
    assert wanted
    app, book, server = _scene_server(tmp_path / "capped")
    _real_availability(app)
    try:
        catalog = app.music_catalog()
        real_lookup = catalog.lookup
        monkeypatch.setattr(catalog, "lookup", lambda links: {link: dict(info, bytes=MUSIC_TRACK_MAX_BYTES + (1 if link in wanted else 0))
                                                              for link, info in real_lookup(links).items()})
        links = {cue["link"] for cue in _cues_when_ready(server, book)["cues"]}
        assert links and not links & wanted, "bài quá cỡ lọt vào rãnh nhạc theo cảnh"
    finally:
        server.stop()


def test_a_saved_chapter_whose_track_turned_out_too_big_is_rebuilt_with_another_track(tmp_path: Path) -> None:
    from abook.webui.server import MUSIC_TRACK_MAX_BYTES

    app, book, server = _scene_server(tmp_path)
    _real_availability(app)
    try:
        before = _cues_when_ready(server, book)
        heads = [cue["key"] for cue in before["cues"] if not cue.get("sibling")]
        big = before["cues"][0]["link"]
        app._music_mark_too_big(big, MUSIC_TRACK_MAX_BYTES + 1)  # tải thật báo 413: từ giờ máy này không dùng bài ấy
        assert app.music_track_available(big) is False
        after = _cues_when_ready(server, book)
        assert big not in {cue["link"] for cue in after["cues"]}
        assert [cue["key"] for cue in after["cues"] if not cue.get("sibling")] == heads, "cảnh nào cũng còn nhạc (không im lặng)"
    finally:
        server.stop()


def test_a_catalog_that_cannot_be_read_says_why_there_is_no_scene_music(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui.music_catalog import CatalogError

    app, book, server = _scene_server(tmp_path)
    try:
        def broken(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise CatalogError("Chưa tải được danh mục nhạc nền - cần mạng ở lần đầu.")

        monkeypatch.setattr(app.music_catalog(), "manifest", broken)
        _status, reply = _call(server, "GET", f"/api/books/{book}/music/chapters/1")
        assert reply["cues"] == [] and "pending" not in reply
        assert reply["unavailable"] == "Chưa tải được danh mục nhạc nền - cần mạng ở lần đầu."
        monkeypatch.undo()
        assert "unavailable" not in _cues_when_ready(server, book), "có danh mục lại thì không còn lời báo"
    finally:
        server.stop()


# ---- tra cỡ chỉ cho bài ĐÃ CHỌN (soát a45: tra từng ứng viên là ~250 mảnh tracks/ tải lần lượt, 308 giây trước nhạc đầu tiên) --------------------


def _wide_catalog(root: Path) -> tuple[Path, dict[str, dict[str, Any]]]:
    """Danh mục 90 bài quanh đích êm (nhiều mảnh `tracks/` khác nhau): ứng viên nhiều hơn xa số bài một chương chọn."""
    from tests.catalog_signing import write_catalog

    tracks = {f"https://x/w{n:03d}.mp3": {"valence": round(0.02 + 0.004 * n, 3), "arousal": round(-0.72 + 0.006 * (n % 17), 3),
                                          "family": FAMILIES[n % len(FAMILIES)], "duration": 150 + 3 * (n % 23), "source": "incompetech"}
              for n in range(90)}
    return write_catalog(root, tracks), tracks


class _CountingCatalog(MusicCatalog):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.shards: list[str] = []

    def _fetch(self, relative: str) -> bytes:
        if relative.startswith("tracks/"):
            self.shards.append(relative.split("?")[0])
        return super()._fetch(relative)


def test_the_first_plan_fetches_only_the_track_shards_of_the_links_it_chose(tmp_path: Path) -> None:
    from abook.webui.music_catalog import shard_of

    app, book, server = _scene_server(tmp_path)
    cloud, tracks = _wide_catalog(tmp_path / "wide")
    catalog = _CountingCatalog(tmp_path / "wide_cache", str(cloud), public_key=TEST_PUBLIC_KEY)
    app._music_catalog = catalog
    _real_availability(app)
    try:
        cues = [cue for chapter in range(1, 6) for cue in _cues_when_ready(server, book, chapter)["cues"]]  # chương đang nghe + các chương dựng trước
        chosen_shards = {f"tracks/{shard_of(cue['link'])}.json" for cue in cues}
        every_shard = {f"tracks/{shard_of(link)}.json" for link in tracks}
        assert cues and len(chosen_shards) < len(every_shard) / 2, "thử nghiệm phải có nhiều ứng viên hơn bài được chọn"
        assert catalog.shards and set(catalog.shards) <= chosen_shards, f"mảnh tracks/ ngoài bài đã chọn bị tải: {sorted(set(catalog.shards) - chosen_shards)}"
        assert len(catalog.shards) == len(set(catalog.shards)), "mỗi mảnh tải một lần"
    finally:
        server.stop()


def test_a_chosen_track_found_over_size_is_dropped_and_the_chapter_is_chosen_again(tmp_path: Path) -> None:
    book = Book(tmp_path, 7, chapters=2)
    banned: set[str] = set()
    asked: list[list[str]] = []
    first_choice = {link for scene in book.build(1)["scenes"] for link in music_nnscene.chosen_links([scene])}  # mọi bài lần chọn đầu
    assert len(first_choice) >= 2
    book2 = Book(tmp_path / "again", 7, chapters=2)
    victims = sorted(first_choice)[:2]

    def verify(links: list[str]) -> bool:
        asked.append(links)
        fresh = [link for link in victims if link in links and link not in banned]
        banned.update(fresh[:1])  # mỗi vòng chỉ phát hiện MỘT bài quá cỡ: phải lặp tới khi hết
        return bool(fresh)

    record = book2.build(1, available=lambda link: link not in banned, verify=verify)
    links = set(music_nnscene.chosen_links(record["scenes"]))
    assert banned == set(victims) and not links & banned, "bài quá cỡ không còn trong plan"
    assert len(asked) == 3 and asked[-1] == music_nnscene.chosen_links(record["scenes"]), "vòng cuối xác nhận đúng các bài đã chọn"
    assert all(len(batch) == len(set(batch)) and set(batch) <= set(TRACKS) for batch in asked), "mỗi vòng một lượt, không trùng"
    assert all(scene["link"] or scene.get("silenced") or scene.get("continued") for scene in record["scenes"]), "cảnh nào cũng còn nhạc"


def test_a_cached_manifest_whose_shards_cannot_be_fetched_still_says_why_there_is_no_scene_music(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui.music_catalog import CatalogError

    app, book, server = _scene_server(tmp_path)
    try:
        catalog = app.music_catalog()
        catalog.manifest()  # mục lục đã có (lần đầu có mạng)

        def offline(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
            raise CatalogError("Không tải được danh mục nhạc nền - kiểm tra mạng.")

        monkeypatch.setattr(catalog, "near", offline)  # mảnh `cells/` chưa cất và hết mạng
        reply = _cues_when_ready(server, book)
        assert reply["cues"] == [] and not reply.get("pending")
        assert reply["unavailable"] == "Không tải được danh mục nhạc nền - kiểm tra mạng."
        monkeypatch.undo()
        assert "unavailable" not in _cues_when_ready(server, book), "có mạng lại thì không còn lời báo"
    finally:
        server.stop()
