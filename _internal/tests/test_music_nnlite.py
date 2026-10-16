"""NN-lite (webui/music_nnlite.py, Corpus research/music/SPEC_nnlite_app.md): học sinh 2 MB chỉ chữ cho nhạc theo cảnh khi máy không có gói q06.
Hai bộ ví dụ DÙNG CHUNG với điện thoại (NnLiteTest.kt / SceneMusicTest.kt) nằm ở tests/fixtures/music/nnlite/: chữ -> token -> băm -> đặc trưng, và 4 số + mục chương; `lb_fixture.json`: khối, hồ sơ khối và ranh cảnh LB (SPEC_lb_app).
Chữ trong đó đều dựng sẵn (kho công khai)."""
from __future__ import annotations

import json
import logging
import re
import struct
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any

import pytest

from abook.webui import music_nnlite, music_nnscene, music_scenes, music_select, packages
from tests.test_music_nnscene import _scene_server, chapter_text

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "music" / "nnlite"
TEXT = json.loads((FIXTURES / "nnlite_text_fixture.json").read_text(encoding="utf-8"))
OUT = json.loads((FIXTURES / "nnlite_out_fixture.json").read_text(encoding="utf-8"))
LB = json.loads((FIXTURES / "lb_fixture.json").read_text(encoding="utf-8"))


def _number(text: str) -> float:
    """`repr` của numpy ("np.float64(0.5)") hay của float."""
    match = re.fullmatch(r"(?:np\.float64\()?(-?[0-9.e+-]+|nan|inf|-inf)\)?", text)
    assert match, text
    return float(match.group(1))


@pytest.fixture(autouse=True)
def fresh_model(monkeypatch: pytest.MonkeyPatch):
    """Mỗi ca bắt đầu với model thật của app đã nạp lại (ca nào thử file hỏng thì tự đổi MODEL_FILE)."""
    monkeypatch.setattr(music_nnlite, "_loaded", None)
    yield
    monkeypatch.setattr(music_nnlite, "_loaded", None)


# ---- chữ -> đặc trưng (bộ ví dụ chữ) ------------------------------------------------------------------------------------------------


def test_the_bundled_model_is_the_file_the_spec_describes() -> None:
    raw = music_nnlite.MODEL_FILE.read_bytes()
    assert len(raw) == OUT["model_bytes"] == 16 + 8 * OUT["buckets"] + 160
    assert raw[:4] == b"NNL1" and struct.unpack_from("<III", raw, 4) == (OUT["buckets"], 4, 4)
    assert b"\r" not in raw[:4], "file nhị phân, không phải chữ"
    assert music_nnlite.model() is not None and music_nnlite.model().buckets == 262144
    assert len(music_nnlite.sha()) == 12


def test_the_whitespace_and_punctuation_tables_are_the_ones_the_phone_must_copy() -> None:
    spaces = sorted(code for code in range(sys.maxunicode + 1) if chr(code).isspace())
    assert spaces == TEXT["whitespace"], "khoảng trắng của Python (isspace) - cũng là thứ strip / split dùng"
    assert sorted(ord(char) for char in music_nnlite.PUNCT) == TEXT["punct"]
    assert sorted(ord(char) for char in music_nnlite.DIALOG) == TEXT["dialog"]


@pytest.mark.parametrize("sample", TEXT["samples"], ids=lambda sample: sample["text"][:24] or "(rỗng)")
def test_text_tokens_hashes_and_features_match_the_shared_fixture(sample: dict[str, Any]) -> None:
    text = sample["text"]
    assert music_nnlite.normalize(text) == sample["normalized"]
    words = music_nnlite.tokens(sample["normalized"])
    assert words == sample["tokens"]
    found = music_nnlite.entries(words)
    assert [[entry, music_nnlite.fnv1a(entry), music_nnlite.fnv1a(entry) % (1 << 18), music_nnlite.fnv1a(entry) % (1 << 17)] for entry in found] == sample["entries"]
    for buckets, key in ((1 << 18, "features_2_18"), (1 << 17, "features_2_17")):
        got = music_nnlite.features(text, buckets)
        want = {int(slot): _number(value) for slot, value in sample[key]}
        assert sorted(got) == sorted(want), "cùng tập ô băm"
        assert all(abs(got[slot] - want[slot]) < 1e-12 for slot in want)
    assert all(abs(a - _number(b)) < 1e-12 for a, b in zip(music_nnlite.dense(text), sample["dense"])) and len(sample["dense"]) == 4
    assert music_nnlite.weight(text) == sample["weight"]


def test_the_fixture_covers_the_unicode_traps_the_phone_has_to_get_right() -> None:
    texts = " ".join(sample["text"] for sample in TEXT["samples"])
    assert unicodedata.normalize("NFD", texts) != texts or any(unicodedata.normalize("NFD", s["text"]) == s["text"] for s in TEXT["samples"]), "có chữ NFD"
    assert any(ord(char) > 0xFFFF for char in texts), "ngoài BMP"
    assert "İ" in texts and "ΟΔΟΣ" in texts, "hạ chữ đầy đủ: İ, sigma cuối từ"
    assert "\u001c" in texts and "　" in texts, "khoảng trắng mà Char.isWhitespace của Java hiểu khác"


# ---- 4 số và mục chương (bộ ví dụ đầu ra) ---------------------------------------------------------------------------------------------


def test_the_four_numbers_and_the_chapter_items_match_the_shared_fixture() -> None:
    model = music_nnlite.model()
    assert model is not None
    for scene in OUT["scenes"]:
        got = model.scene(scene["text"])
        assert all(abs(a - _number(b)) < OUT["tolerance"] for a, b in zip(got, scene["out"])) and len(got) == 4
        assert music_nnlite.weight(scene["text"]) == scene["weight"]
    for chapter in OUT["chapters"]:
        items = model.chapter([OUT["scenes"][index]["text"] for index in chapter["scenes"]])
        assert len(items) == len(chapter["items"])
        for got, want in zip(items, chapter["items"]):
            assert set(got) == set(want) == {"dV", "dE", "dT", "chapterV"}
            assert all(abs(got[key] - _number(want[key])) < OUT["tolerance"] for key in want)
    single = model.chapter([OUT["scenes"][27]["text"]])
    assert [(item["dV"], item["dE"], item["dT"]) for item in single] == [(0.0, 0.0, 0.0)], "chương một cảnh: độ lệch 0"
    assert model.chapter([]) == []


# ---- file hỏng / thiếu: quay về N0, một dòng log ----------------------------------------------------------------------------------------


def _bad_files(tmp_path: Path) -> dict[str, Path]:
    raw = music_nnlite.MODEL_FILE.read_bytes()
    files = {"thiếu": tmp_path / "khong_co.bin", "magic": tmp_path / "magic.bin", "cỡ": tmp_path / "size.bin", "hình": tmp_path / "shape.bin",
             "rỗng": tmp_path / "empty.bin"}
    files["magic"].write_bytes(b"XXXX" + raw[4:])
    files["cỡ"].write_bytes(raw[:-4])
    files["hình"].write_bytes(raw[:8] + struct.pack("<I", 5) + raw[12:])
    files["rỗng"].write_bytes(b"")
    return files


def test_a_missing_or_corrupt_model_falls_back_to_n0_with_one_log_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    script, _ = music_nnscene.chapter_script(1, "T", chapter_text(0, 1))
    n0 = music_nnscene.chapter_scenes(script)
    for name, path in _bad_files(tmp_path).items():
        monkeypatch.setattr(music_nnlite, "MODEL_FILE", path)
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger=music_nnlite.log.name):
            assert music_nnlite.model() is None and music_nnlite.model() is None, name
            assert music_nnlite.sha() == "" and music_nnlite.student_items(script, music_scenes.book_scenes([script])) is None
        assert len(caplog.records) == 1, f"{name}: đúng một dòng log, không lặp mỗi lần hỏi"
        assert music_nnscene.chapter_scenes(script, music_nnlite.student_items) == n0, f"{name}: không model = đường N0"


def test_a_model_that_cannot_match_a_chapters_scenes_gives_no_items() -> None:
    script, _ = music_nnscene.chapter_script(1, "T", chapter_text(0, 1))
    base = music_scenes.book_scenes([script])
    assert music_nnlite.student_items(script, base) is not None
    assert music_nnlite.student_items(script, [dict(base[0], firstSegment=10 ** 9)]) is None
    assert music_nnlite.student_items(script, []) is None


# ---- đường NN-V với mục NN-lite ------------------------------------------------------------------------------------------------------------


def test_the_items_are_the_student_shape_and_the_lite_scenes_take_the_nn_v_path() -> None:
    script, _ = music_nnscene.chapter_script(1, "T", chapter_text(0, 1))
    base = music_scenes.book_scenes([script], None, None, None)
    items = music_nnlite.student_items(script, base)
    assert items and len(items) == len(base)
    assert [(item["chapterId"], item["firstSegment"], item["lastSegment"]) for item in items] == \
        [(scene["chapterId"], scene["firstSegment"], scene["lastSegment"]) for scene in base]
    assert len({item["chapterV"] for item in items}) == 1, "chapterV cùng giá trị ở mọi đoạn của chương"
    assert len(base) > 1 and abs(sum(item["dV"] for item in items)) < 1e9
    lite = music_nnscene.chapter_scenes(script, music_nnlite.student_items)
    assert all(scene["moodSource"] == "student" for scene in lite)
    assert all(scene["confidence"] == music_select.WEAK_MOOD for scene in lite), "sàn WEAK_MOOD như NN-V"
    n0 = music_nnscene.chapter_scenes(script)
    assert [(s["firstSegment"], s["lastSegment"], s["start"], s["end"], s["reason"]) for s in lite] == \
        [(s["firstSegment"], s["lastSegment"], s["start"], s["end"], s["reason"]) for s in n0], "học sinh không đổi ranh cảnh"
    assert any(s["valence"] != 0 for s in lite) and all(s["valence"] == 0 for s in n0)


def test_items_over_a_whole_book_equal_items_chapter_by_chapter() -> None:
    scripts = [music_nnscene.chapter_script(cid, "T", chapter_text(1, cid))[0] for cid in (1, 2, 3)]
    base = music_scenes.book_scenes(scripts, None, None, None)
    model = music_nnlite.model()
    assert model is not None
    whole = model.items(scripts, base)
    per_chapter = [item for script in scripts for item in music_nnlite.student_items(script, [s for s in base if s["chapterId"] == script["chapterId"]]) or []]
    assert whole == per_chapter and len(whole) == len(base)


# ---- máy chủ: NN-lite khi không có q06, q06 thì giữ nguyên ------------------------------------------------------------------------------------


def _student_of_the_job(app: Any, book: str, monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Học sinh mà việc dựng nền của chương đầu truyền cho `music_nnscene.build_chapter` (dựng thật được thay bằng ghi lại)."""
    path, manifest = app._listenable(book), app.music_catalog().manifest()
    chapters = {chapter["id"]: chapter for chapter in packages.edited_manifest(path)["chapters"]}
    order = list(chapters)
    seen: list[Any] = []
    monkeypatch.setattr(music_nnscene, "build_chapter", lambda *args, **kwargs: seen.append(kwargs.get("student")))
    app._scene_job(book, path, order[0], order, chapters, app._scene_book(book, path, manifest), manifest)(lambda: False)
    return seen


def test_without_q06_the_server_builds_scene_music_with_the_bundled_nn_lite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, book, server = _scene_server(tmp_path)
    try:
        assert app._scene_student_mode() == "none"
        assert _student_of_the_job(app, book, monkeypatch) == [music_nnlite.student_items]
        monkeypatch.setattr(music_nnlite, "MODEL_FILE", tmp_path / "khong_co.bin")
        assert _student_of_the_job(app, book, monkeypatch) == [None], "model hỏng: đường N0"
    finally:
        server.stop()


def test_the_plan_cache_key_tells_nn_lite_from_n0_and_from_q06(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app, book, server = _scene_server(tmp_path)
    try:
        path, manifest = app._listenable(book), app.music_catalog().manifest()
        lite = app._scene_book(book, path, manifest).directory
        monkeypatch.setattr(music_nnlite, "MODEL_FILE", tmp_path / "khong_co.bin")
        n0 = app._scene_book(book, path, manifest).directory
        assert lite != n0, "model thật / không model: hai thư mục đệm, không dùng nhầm plan N0 làm plan NN-lite"
        monkeypatch.undo()
        monkeypatch.setattr(music_nnlite, "_loaded", None)
        assert app._scene_book(book, path, manifest).directory == lite
        assert music_nnscene.student_tag(None, "abc") == "nnlite-lb1-abc" and music_nnscene.student_tag(None, "") == "none"
        assert music_nnscene.student_tag("q06sha", "abc") == "q06sha", "có gói q06 thì q06"
    finally:
        server.stop()


def test_with_q06_the_server_keeps_the_q06_student_and_never_reads_the_lite_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui import music_scene_student

    app, book, server = _scene_server(tmp_path)
    try:
        monkeypatch.setattr(music_nnlite, "student_items", lambda *_: pytest.fail("có gói q06: NN-V giữ nguyên, không dùng NN-lite"))
        monkeypatch.setattr(music_nnlite, "model", lambda: pytest.fail("có gói q06: không đụng model NN-lite"))
        monkeypatch.setattr(music_nnlite, "sha", lambda: pytest.fail("có gói q06: không đụng model NN-lite"))
        monkeypatch.setattr(music_scene_student, "package_sha", lambda *_: "q06sha")
        monkeypatch.setattr(type(app), "_scene_student_mode", lambda self: "local")
        seen = _student_of_the_job(app, book, monkeypatch)
        assert len(seen) == 1 and callable(seen[0]), "học sinh q06 (hàm bọc `ChapterStudent`)"
    finally:
        server.stop()


# ---- ranh cảnh LB (SPEC_lb_app) ----------------------------------------------------------------------------------------------------------


def _sentences(*word_counts: int) -> list[dict[str, Any]]:
    return [{"id": index + 1, "text": " ".join(["chữ"] * count)} for index, count in enumerate(word_counts)]


@pytest.mark.parametrize("chapter", LB["chapters"], ids=lambda chapter: chapter["name"])
def test_lb_blocks_profiles_and_bounds_match_the_shared_fixture(chapter: dict[str, Any]) -> None:
    model = music_nnlite.model()
    assert model is not None
    assert (LB["lambda"], LB["block_words"], LB["min_blocks"]) == (music_nnlite.LB_LAMBDA, music_nnlite.LB_BLOCK_WORDS, music_nnlite.LB_MIN_BLOCKS)
    assert LB["model_bytes"] == len(music_nnlite.MODEL_FILE.read_bytes()), "bộ ví dụ sinh từ đúng model đóng sẵn"
    segments = chapter["segments"]
    spans = music_nnlite.blocks(segments)
    assert [list(span) for span in spans] == chapter["blocks"], "khối trùng tuyệt đối"
    profile = model.block_profile(segments, spans)
    assert len(profile) == len(chapter["profile"])
    assert all(abs(got - _number(want)) < LB["tolerance_profile"] for row, wants in zip(profile, chapter["profile"]) for got, want in zip(row, wants))
    assert model.scene_bounds(segments) == chapter["bounds"], "ranh trùng tuyệt đối"


def test_lb_blocks_close_at_150_words_and_a_short_tail_joins_the_last_block() -> None:
    assert music_nnlite.blocks(_sentences(100, 60, 40)) == [(0, 2)], "dư 40 < 75: gộp vào khối trước"
    assert music_nnlite.blocks(_sentences(100, 60, 80)) == [(0, 1), (2, 2)], "dư 80 >= 75: khối riêng"
    assert music_nnlite.blocks(_sentences(100, 60, 74)) == [(0, 2)] and music_nnlite.blocks(_sentences(100, 60, 75)) == [(0, 1), (2, 2)], "ngưỡng đúng 75"
    assert music_nnlite.blocks(_sentences(149, 1, 150)) == [(0, 1), (2, 2)], "đủ 150 thì đóng ở chính câu đó"
    assert music_nnlite.blocks(_sentences(20, 30)) == [(0, 1)], "chương ngắn: một khối dù dưới 75 (chưa có khối nào để gộp vào)"
    assert music_nnlite.blocks([]) == []
    assert music_nnlite.blocks([{"id": 1, "text": ""}, {"id": 2, "text": "   "}, {"id": 3}] + _sentences(200)) == [(0, 3)], "câu rỗng / thiếu chữ tính 0 chữ"


def test_lb_counts_words_like_python_split_for_unicode_spaces() -> None:
    odd = {"id": 1, "text": "a b　c d e"}  # 5 mẩu: NBSP, ideographic space, em space đều là khoảng trắng của str.split
    assert len(odd["text"].split()) == 5
    assert music_nnlite.blocks([odd] * 30) == [(0, 29)], "30 x 5 = 150 chữ: đóng đúng ở câu cuối"
    assert music_nnlite.blocks([odd] * 29 + [{"id": 2, "text": "x"}, {"id": 3, "text": "y"}]) == [(0, 30)], "145 + 2 = 147 chữ: chưa đủ 150"


def test_lb_fewer_than_four_blocks_never_cut_and_a_step_in_the_profile_is_found() -> None:
    wild = [[0.0, 0.0, 0.0], [9.0, 9.0, 9.0], [-9.0, 5.0, 0.0]]
    assert music_nnlite.partition(wild) == [] and music_nnlite.partition(wild[:2]) == [] and music_nnlite.partition([]) == []
    step = [[0.0, 0.0, 0.0]] * 3 + [[2.0, 2.0, 2.0]] * 3
    assert music_nnlite.partition(step) == [3]
    assert music_nnlite.partition(step[2:5]) == [], "3 khối: không ranh dù hồ sơ khác nhau"
    assert music_nnlite.partition([[0.0, 0.0, 0.0], [3.0, 0.0, 0.0]] * 2) == [], "bốn khối xen kẽ: mỗi đoạn >= 2 khối, và ranh không đáng"
    assert music_nnlite.partition([[0.0] * 3] * 6) == [], "đều một màu: không ranh"
    assert music_nnlite.partition([[0.0, 0.0, 0.0]] * 4 + [[0.5, 0.0, 0.0]] * 4) == [], "bước nhỏ hơn phí ranh thì không đáng một ranh"
    assert music_nnlite.partition([[0.0, 0.0, 0.0]] * 4 + [[1.2, 0.0, 0.0]] * 4) == [4], "bước đủ lớn thì cắt đúng chỗ"


def test_lb_a_uniform_chapter_has_no_bounds_and_the_script_hook_hands_back_ids_with_the_reason() -> None:
    uniform = [{"id": 10 * n + 1, "text": OUT["scenes"][0]["text"]} for n in range(60)]
    model = music_nnlite.model()
    assert model is not None and model.scene_bounds(uniform) == [] and music_nnlite.scene_bounds({"chapterId": 1, "segments": uniform}) == {}
    chapter = next(chapter for chapter in LB["chapters"] if chapter["bounds"])
    want = {bound: "mood_shift" for bound in chapter["bounds"]}
    assert music_nnlite.scene_bounds({"chapterId": 1, "segments": chapter["segments"]}) == want
    assert music_nnlite.scene_bounds({"chapterId": 1, "segments": ["bẩn", *chapter["segments"]]}) == want, "bỏ qua mục không phải câu"
    assert music_nnlite.scene_bounds({"chapterId": 1}) == {}


def test_lb_no_model_means_no_bounds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(music_nnlite, "MODEL_FILE", tmp_path / "khong_co.bin")
    assert music_nnlite.scene_bounds({"chapterId": 1, "segments": LB["chapters"][0]["segments"]}) == {}


def _unique(chapter: dict[str, Any]) -> tuple[dict[str, Any], list[int]]:
    """Kịch bản trần của một chương bộ ví dụ với `id` duy nhất (bộ ví dụ lặp id trong một pha) + id câu mở mỗi đoạn LB."""
    model = music_nnlite.model()
    assert model is not None
    segments = [{"id": index + 1, "text": s["text"], "kind": "narration"} for index, s in enumerate(chapter["segments"])]
    spans = music_nnlite.blocks(segments)
    cuts = music_nnlite.partition(model.block_profile(segments, spans))
    return {"chapterId": 7, "title": "T", "segments": segments}, [segments[spans[cut][0]]["id"] for cut in cuts]


def test_lb_bounds_split_the_lite_scenes_and_the_student_guesses_on_the_new_scenes() -> None:
    chapter = next(chapter for chapter in LB["chapters"] if len(chapter["bounds"]) >= 2)
    script, cuts = _unique(chapter)
    assert len(cuts) == len(chapter["bounds"]) >= 2
    seen: list[list[dict[str, Any]]] = []

    def student(chapter_script: dict[str, Any], base: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        seen.append(base)
        return music_nnlite.student_items(chapter_script, base)

    plain = music_nnscene.chapter_scenes(script, student)
    seen.clear()
    lb = music_nnscene.chapter_scenes(script, student, music_nnlite.scene_bounds)
    assert len(seen) == 1, "học sinh chạy MỘT lần, trên đoạn đã có ranh LB"
    shifts = [scene["firstSegment"] for scene in seen[0] if scene["reason"] == "mood_shift"]
    assert shifts and set(shifts) <= set(cuts), "đoạn nền đã mang ranh LB (lý do mood_shift) trước khi học sinh chạy"
    assert [scene["firstSegment"] for scene in lb] != [scene["firstSegment"] for scene in plain], "ranh LB đổi đoạn"
    assert [scene["firstSegment"] for scene in lb] == [scene["firstSegment"] for scene in seen[0]], "đoạn cuối = đoạn học sinh đã đoán"
    assert all(scene["moodSource"] == "student" and scene["confidence"] >= music_select.WEAK_MOOD for scene in lb), "sàn WEAK_MOOD vẫn áp"


def test_lb_leaves_n0_and_a_student_that_gives_up_exactly_as_before() -> None:
    chapter = next(chapter for chapter in LB["chapters"] if chapter["bounds"])
    script, _cuts = _unique(chapter)
    n0 = music_nnscene.chapter_scenes(script)
    assert music_nnscene.chapter_scenes(script, None, music_nnlite.scene_bounds) == n0, "không học sinh (N0): ranh LB không vào"
    assert music_nnscene.chapter_scenes(script, lambda *_: None, music_nnlite.scene_bounds) == n0, "học sinh bỏ chương: đường N0 nguyên, không ranh LB"
    calls: list[Any] = []
    music_nnscene.chapter_scenes(script, lambda s, base: calls.append(base) or music_nnlite.student_items(s, base))
    assert len(calls) == 1 and not any(scene["reason"] == "mood_shift" for scene in calls[0]), "không truyền bounds (q06): giữ nguyên"


def test_lb_a_cue_wins_a_spot_the_lite_bound_also_claims() -> None:
    segments = [{"id": 1, "text": "Mở đầu."}, {"id": 2, "text": "Câu hai."}, {"id": 3, "text": "Tiêu đề.", "kind": "heading"}, {"id": 4, "text": "Câu bốn."}]
    assert music_scenes.cue_bounds(segments) == {3: "heading"}
    out = music_scenes.with_scene_breaks(segments, {music_nnscene.LITE_SOURCE: {3: "mood_shift", 4: "mood_shift"}})
    assert (out[1]["sceneSource"], out[1]["sceneCue"]) == ("cue", "heading"), "trùng chỗ: cue thắng"
    assert (out[2]["sceneSource"], out[2]["sceneCue"]) == ("lite", "mood_shift") and "sceneBreak" not in out[0]
    assert music_scenes.hard_break(segments[3], out[2]) == "mood_shift", "lý do của đoạn mới"


def test_lb_changes_the_plan_cache_key_and_the_server_hands_the_hook_only_to_the_lite_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert music_nnscene.student_tag(None, "abc") == "nnlite-lb1-abc" != "nnlite-abc"
    app, book, server = _scene_server(tmp_path)
    try:
        path, manifest = app._listenable(book), app.music_catalog().manifest()
        chapters = {chapter["id"]: chapter for chapter in packages.edited_manifest(path)["chapters"]}
        order = list(chapters)
        seen: list[Any] = []
        monkeypatch.setattr(music_nnscene, "build_chapter", lambda *args, **kwargs: seen.append(kwargs.get("bounds")))
        app._scene_job(book, path, order[0], order, chapters, app._scene_book(book, path, manifest), manifest)(lambda: False)
        assert seen == [music_nnlite.scene_bounds]
        monkeypatch.setattr(music_nnlite, "MODEL_FILE", tmp_path / "khong_co.bin")
        app._scene_job(book, path, order[0], order, chapters, app._scene_book(book, path, manifest), manifest)(lambda: False)
        assert seen[-1] is None, "model hỏng: đường N0, không ranh"
    finally:
        server.stop()


def test_lb_bounds_need_no_numpy_on_the_player_only_install(tmp_path: Path) -> None:
    script = (
        "import json, sys\n"
        "class Block:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name.split('.')[0] == 'numpy': raise ImportError('numpy bị chặn')\n"
        "sys.meta_path.insert(0, Block())\n"
        "from abook.webui import music_nnlite, music_nnscene\n"
        "chapter = json.loads(open(sys.argv[1], encoding='utf-8').read())['chapters'][1]\n"
        "script = {'chapterId': 1, 'segments': chapter['segments']}\n"
        "music_nnscene.chapter_scenes(script, music_nnlite.student_items, music_nnlite.scene_bounds)\n"
        "print(json.dumps(music_nnlite.model().scene_bounds(chapter['segments'])))\n")
    run = subprocess.run([sys.executable, "-c", script, str(FIXTURES / "lb_fixture.json")], capture_output=True, encoding="utf-8", check=False,
                         cwd=Path(music_nnlite.__file__).parents[2])
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == LB["chapters"][1]["bounds"]
