"""Mốc thời gian từng chữ (webui/word_timing.py): chữ -> âm tiết, căn CTC, đường dự phòng, bộ nhớ đệm, định dạng trong `.abook`.

Audio thử: bốn câu tiếng Việt do chính dự án viết, đọc bằng Edge TTS (tests/fixtures/word_timing, ~28 KB mỗi câu, kèm mốc từng chữ do Edge báo -
`truth.json`). Edge báo đầu chữ sớm ~100 ms (độ trễ codec MP3): so sánh sau khi bù MỘT hằng số, như lượt đo 03-10. Bài thử CTC cần model
(ABOOK_WORD_ALIGN_DIR hay bản dựng ở LLM_Train/word_align/package); không có thì bỏ qua, các bài khác vẫn chạy.
"""
from __future__ import annotations

import json
import sqlite3
import statistics
import zipfile
from pathlib import Path

import numpy as np
import pytest
import soundfile

from abook import io_utils
from abook.webui import bookfile, packages, store, word_timing
from abook.webui.bookfile import BookFile
from abook.webui.fingerprints import Fingerprints
from tests.test_webui_listen_and_sync import make_project

FIXTURES = Path(__file__).parent / "fixtures" / "word_timing"
TRUTH = json.loads((FIXTURES / "truth.json").read_text(encoding="utf-8"))
PACKAGE = Path("D:/Novels/LLM_Train/word_align/package")
BREAK = 0.4

needs_ffmpeg = pytest.mark.skipif(not io_utils.ffmpeg_available(), reason="không có ffmpeg")


@pytest.fixture(autouse=True)
def _on(monkeypatch: pytest.MonkeyPatch) -> None:
    word_timing.reset()
    monkeypatch.setenv(word_timing.ENV_SWITCH, "1")
    monkeypatch.delenv(word_timing.ENV_DIR, raising=False)
    monkeypatch.delenv(word_timing.ENV_RUNTIME, raising=False)
    monkeypatch.setattr(word_timing, "_studio", None)
    yield
    word_timing.reset()


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> Path:
    import os

    folder = Path(os.environ.get("ABOOK_WORD_ALIGN_TEST_DIR") or PACKAGE)
    if not word_timing._complete(folder):
        pytest.skip("không có model căn chữ ở " + str(folder))
    pytest.importorskip("onnxruntime")
    monkeypatch.setenv(word_timing.ENV_DIR, str(folder))
    return folder


def _wave(index: int) -> np.ndarray:
    return word_timing.decode(FIXTURES / TRUTH[index]["file"])


def _units(text: str, edge_words: list) -> list[tuple[list[int], float]]:
    """Từng "chữ" của Edge (có chữ gồm nhiều chữ hiện, vd "6 giờ 30 phút") -> (các chỉ số chữ hiện, đầu chữ theo Edge)."""
    spans, position = [], 0
    for token in word_timing.tokens(text):
        start = text.index(token, position)
        spans.append((start, start + len(token)))
        position = start + len(token)
    out, cursor, lowered = [], 0, text.lower()
    for word, start, _stop in edge_words:
        found = lowered.find(word.lower(), cursor)
        if found < 0:
            continue
        cursor = found + len(word)
        out.append(([i for i, (a, b) in enumerate(spans) if a < cursor and b > found], start))
    return out


def _within(found: list[list[int]], truth: dict, limit: float = 0.1) -> float:
    """Tỉ lệ đầu chữ lệch ≤ `limit` giây so với Edge, sau khi bù MỘT hằng số cho cả câu (Edge báo sớm ~100 ms do độ trễ codec MP3)."""
    units = _units(truth["text"], truth["words"])
    errors = [min(found[i][0] for i in indices) / 1000 - start for indices, start in units]
    shift = statistics.median(errors)
    return sum(abs(error - shift) <= limit for error in errors) / len(errors)


# ---- chữ -> âm tiết ---------------------------------------------------------------------------------------------------------------
def test_numbers_are_read_out_as_syllables() -> None:
    assert word_timing.spoken_syllables("42") == ["bốn", "mươi", "hai"]
    assert word_timing.spoken_syllables("2.500.000đ".replace("đ", "")) == ["hai", "triệu", "năm", "trăm", "nghìn"]
    assert word_timing.spoken_syllables("1945,") == ["một", "nghìn", "chín", "trăm", "bốn", "mươi", "lăm"]
    assert word_timing.spoken_syllables("6:30") == ["sáu", "ba", "mươi"], "dấu giữa chữ tách thành hai số"
    assert word_timing.spoken_syllables("“—”") == [] and word_timing.spoken_syllables("...") == []
    assert word_timing.spoken_syllables("Linh,") == ["linh"]


def test_displayed_tokens_are_the_whitespace_separated_units() -> None:
    assert word_timing.tokens("  Trời vừa  hửng\u00a0sáng,\n sương ") == ["Trời", "vừa", "hửng", "sáng,", "sương"]
    assert word_timing.tokens("") == []


def test_targets_separate_syllables_with_the_word_boundary_label() -> None:
    vocab = {"<pad>": 0, "|": 4, "a": 5, "b": 6, "c": 7, "h": 8, "p": 9}
    ids, owner = word_timing.targets(["ab", "—", "ca-hp"], vocab)
    assert ids == [5, 6, 4, 7, 5, 4, 8, 9] and owner == [0, 0, -1, 2, 2, -1, 2, 2], "chữ không có âm nào không có nhãn"


def test_finish_makes_words_contiguous_and_gives_a_silent_token_no_time_of_its_own() -> None:
    words = word_timing.finish([[0.10, 0.40], [0.50, 0.80], None, [1.20, 1.50]])
    assert words == [[100, 500], [500, 800], [800, 1200], [1200, 1500]], "một chữ kết thúc đúng chỗ chữ sau bắt đầu; chữ lặng đứng yên"
    assert word_timing.finish([[0.5, 0.9], [0.3, 0.4]]) == [[500, 500], [500, 500]], "đầu chữ không lùi"
    assert word_timing.finish([]) == [] and len(word_timing.finish([None, None])) == 2


def test_forced_alignment_puts_each_label_on_its_frames_and_needs_a_blank_between_repeats() -> None:
    blank = 0
    emission = np.log(np.full((8, 3), 0.01))
    for frame, label in enumerate([0, 1, 1, 0, 2, 2, 2, 0]):
        emission[frame, label] = np.log(0.98)
    labelled, confidence = word_timing.forced_align(emission, [1, 2], blank)  # type: ignore[misc]
    assert labelled == [-1, 0, 0, -1, 1, 1, 1, -1] and confidence > 0.9
    assert word_timing.forced_align(emission[:2], [1, 1], blank) is None, "hai nhãn giống nhau liền nhau cần ít nhất ba khung"
    assert word_timing.forced_align(emission, [], blank) is None


# ---- căn một câu ---------------------------------------------------------------------------------------------------------------------
@needs_ffmpeg
def test_ctc_puts_nearly_every_word_start_within_100_ms(model: Path) -> None:
    aligner = word_timing.get_aligner()
    assert aligner is not None
    for index, truth in enumerate(TRUTH):
        words, method, confidence = word_timing.line_words(_wave(index), truth["text"], 0.0, aligner)
        assert method == word_timing.CTC and confidence > 0.9
        assert len(words) == len(word_timing.tokens(truth["text"]))
        assert _within(words, truth) >= 0.95, truth["text"]
        assert all(a[1] == b[0] for a, b in zip(words, words[1:])), "một chữ kết thúc đúng chỗ chữ sau bắt đầu"
        assert all(start <= end for start, end in words)


@needs_ffmpeg
def test_a_text_the_voice_did_not_say_falls_back_to_the_spread(model: Path) -> None:
    aligner = word_timing.get_aligner()
    words, method, _ = word_timing.line_words(_wave(0), TRUTH[3]["text"], 0.0, aligner)
    assert method == word_timing.SPREAD and len(words) == len(word_timing.tokens(TRUTH[3]["text"]))


@needs_ffmpeg
def test_without_a_model_the_spread_with_pauses_still_lands_close() -> None:
    for index, truth in enumerate(TRUTH):
        words, method, _ = word_timing.line_words(_wave(index), truth["text"], 0.0, None)
        assert method == word_timing.SPREAD and len(words) == len(word_timing.tokens(truth["text"]))
        assert _within(words, truth) >= 0.8, truth["text"]
        assert all(a[1] == b[0] for a, b in zip(words, words[1:]))


def test_the_spread_follows_a_real_pause_instead_of_spreading_evenly() -> None:
    """Hai cụm, giữa chúng 0,6 giây lặng: chữ sau dấu phẩy phải bắt đầu sau khoảng lặng, không giữa cụm đầu (chia đều sẽ rơi vào đó)."""
    rate = word_timing.SAMPLE_RATE
    rng = np.random.default_rng(1)
    speech = lambda seconds: (0.3 * rng.standard_normal(int(seconds * rate))).astype(np.float32)  # noqa: E731
    wave = np.concatenate([np.zeros(int(0.1 * rate), np.float32), speech(1.0), np.zeros(int(0.6 * rate), np.float32), speech(0.5),
                           np.zeros(int(0.1 * rate), np.float32)])
    words = word_timing.finish(word_timing.spread_words(wave, "một hai ba, bốn năm", 0.0))
    assert abs(words[3][0] - 1700) <= 60, "chữ đầu cụm hai bắt đầu ngay sau khoảng lặng (1,1 + 0,6 giây)"
    assert abs(words[2][1] - words[3][0]) <= 1, "chữ cuối cụm một nối thẳng sang chữ sau (một chữ kết thúc đúng chỗ chữ sau bắt đầu)"


# ---- một chương, bộ nhớ đệm ---------------------------------------------------------------------------------------------------------
def _chapter_project(tmp_path: Path) -> tuple[Path, list[float]]:
    """Cuốn của test đồng bộ, chương 1 thay bằng audio thật: bốn câu fixture nối nhau cách 0,4 giây, lưu MP3."""
    project = make_project(tmp_path)
    pieces = [_wave(i) for i in range(len(TRUTH))]
    rate = word_timing.SAMPLE_RATE
    chapter: list[np.ndarray] = []
    for piece in pieces:
        chapter += [piece, np.zeros(int(BREAK * rate), np.float32)]
    audio = project / "output" / "chapters" / "00001_645.mp3"
    soundfile.write(str(audio), np.concatenate(chapter), rate, format="MP3")
    database = sqlite3.connect(project / "project.sqlite3")
    database.execute("DELETE FROM segments WHERE chapter_id = 1")
    now = 1.0
    rows = [(10 + i, 1, i + 1, 0, int(BREAK * 1000), TRUTH[i]["text"], "narration", "NARRATOR", 1, "verified", "", "x", len(piece) / rate, now)
            for i, piece in enumerate(pieces)]
    database.executemany("INSERT INTO segments VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    database.commit()
    database.close()
    return project, [len(piece) / rate for piece in pieces]


@needs_ffmpeg
def test_a_chapter_is_aligned_once_and_the_script_carries_the_words(tmp_path: Path, model: Path) -> None:
    project, _ = _chapter_project(tmp_path)
    assert all("words" not in segment for segment in store.chapter_script(project, 1)["segments"]), "chưa căn thì chưa có"

    summary = word_timing.prepare(project)
    assert summary["mode"] == "process" and summary["ctc"] == 4 and summary["spread"] == 0 and summary["cached"] == 0

    script = store.chapter_script(project, 1)
    for segment, truth in zip(script["segments"], TRUTH):
        words = segment["words"]
        assert len(words) == len(word_timing.tokens(segment["text"])) and words[0][0] >= round(segment["start"] * 1000) - 300
        assert words[-1][1] <= round(segment["end"] * 1000) + 300, "mốc chữ nằm trong khoảng của câu (cộng lề)"
        relative = [[a - round(segment["start"] * 1000), b - round(segment["start"] * 1000)] for a, b in words]
        assert _within(relative, truth) >= 0.95


@needs_ffmpeg
def test_packing_again_aligns_nothing_and_a_changed_line_aligns_alone(tmp_path: Path, model: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, _ = _chapter_project(tmp_path)
    word_timing.prepare(project)
    first = store.chapter_script(project, 1)

    with monkeypatch.context() as patched:
        patched.setattr(word_timing, "decode", lambda _path: pytest.fail("đã căn rồi mà vẫn giải mã audio"))
        again = word_timing.prepare(project)
    assert again["cached"] == 4 and again["ctc"] == again["spread"] == 0
    assert store.chapter_script(project, 1)["segments"] == first["segments"]

    database = sqlite3.connect(project / "project.sqlite3")
    database.execute("UPDATE segments SET text = text || ' thêm' WHERE id = 12")
    database.commit()
    database.close()
    assert "words" not in store.chapter_script(project, 1)["segments"][2], "chữ đổi thì mốc cũ không còn dùng"
    changed = word_timing.prepare(project)
    assert changed["cached"] == 3 and changed["ctc"] + changed["spread"] == 1, "chỉ câu đổi chữ được căn lại"
    assert all("words" in segment for segment in store.chapter_script(project, 1)["segments"])


@needs_ffmpeg
def test_new_audio_for_the_chapter_throws_the_old_timings_away(tmp_path: Path, model: Path) -> None:
    project, _ = _chapter_project(tmp_path)
    word_timing.prepare(project)
    audio = project / "output" / "chapters" / "00001_645.mp3"
    data, rate = soundfile.read(str(audio))
    soundfile.write(str(audio), np.concatenate([np.zeros(int(0.5 * rate)), data]), rate, format="MP3")
    word_timing._hashes.clear()
    assert all("words" not in segment for segment in store.chapter_script(project, 1)["segments"]), "audio khác thì mốc cũ không dùng được"
    summary = word_timing.prepare(project)
    assert summary["cached"] == 0 and summary["ctc"] == 4


@needs_ffmpeg
def test_without_a_model_the_chapter_is_spread_and_a_model_later_replaces_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, _ = _chapter_project(tmp_path)
    first = word_timing.prepare(project)
    assert first["spread"] == 4 and first["ctc"] == 0
    assert all("words" in segment for segment in store.chapter_script(project, 1)["segments"])
    folder = Path(PACKAGE)
    if word_timing._complete(folder):
        pytest.importorskip("onnxruntime")
        monkeypatch.setenv(word_timing.ENV_DIR, str(folder))
        better = word_timing.prepare(project)
        assert better["ctc"] == 4 and better["cached"] == 0, "câu căn dự phòng được căn lại khi đã có model"


def test_a_stamp_from_other_audio_is_not_trusted(tmp_path: Path) -> None:
    audio = tmp_path / "chuong.mp3"
    audio.write_bytes(b"abc")
    text = "một hai"
    segment = {"id": 1, "text": text, "start": 0.0, "end": 1.0}
    word_timing._save(tmp_path, 7, {"version": word_timing.VERSION, "audio": {"sha256": "x", "size": 3, "mtimeNs": audio.stat().st_mtime_ns},
                                    "lines": {"1": {"textSha256": word_timing.text_sha(text), "span": [0, 1000], "method": "ctc",
                                                    "words": [[0, 400], [400, 900]]}}})
    assert word_timing.attach(tmp_path, 7, [segment], audio) == 1 and segment["words"] == [[0, 400], [400, 900]]
    other = {"id": 1, "text": text, "start": 0.0, "end": 1.0}
    audio.write_bytes(b"abcd")
    assert word_timing.attach(tmp_path, 7, [other], audio) == 0 and "words" not in other
    wrong = {"id": 1, "text": text + " ba", "start": 0.0, "end": 1.0}
    audio.write_bytes(b"abc")
    word_timing._save(tmp_path, 7, {"version": word_timing.VERSION, "audio": {"size": 3, "mtimeNs": audio.stat().st_mtime_ns},
                                    "lines": {"1": {"textSha256": "khac", "span": [0, 1000], "words": [[0, 1]]}}})
    assert word_timing.attach(tmp_path, 7, [wrong], audio) == 0, "chữ không khớp mã băm thì bỏ"


# ---- định dạng + đóng gói ---------------------------------------------------------------------------------------------------------------
@needs_ffmpeg
def test_the_words_round_trip_through_the_book_file_and_reading_tolerates_their_absence(tmp_path: Path, model: Path,
                                                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    project, _ = _chapter_project(tmp_path)
    packed = bookfile.pack(project, tmp_path / "co_chu.abook")  # đóng gói tự căn
    with BookFile(packed) as book:
        book.verify()
        script = json.loads(book.read("scripts/1.json"))
    assert script["segments"] == store.chapter_script(project, 1)["segments"]
    assert all(len(segment["words"]) == len(word_timing.tokens(segment["text"])) for segment in script["segments"])
    library = tmp_path / "thu_vien"
    folder, how = packages.import_file(packed, library, [], Fingerprints(tmp_path / "fp.json"))
    assert how == "new" and packages.script(folder, 1)["segments"] == script["segments"], "người nghe đọc đúng `words` trong file"

    monkeypatch.setenv(word_timing.ENV_SWITCH, "0")  # không căn được (hay sách làm trước khi có tính năng này): file vẫn mở, không `words`
    bare = bookfile.pack(make_project(tmp_path / "khac"), tmp_path / "khong_chu.abook")
    with BookFile(bare) as book:
        book.verify()
        assert all("words" not in segment for segment in json.loads(book.read("scripts/1.json"))["segments"])
    folder, _ = packages.import_file(bare, library, [], Fingerprints(tmp_path / "fp.json"))
    assert all("words" not in segment for segment in packages.script(folder, 1)["segments"])


def test_packing_never_fails_because_the_words_could_not_be_aligned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(word_timing, "in_process", lambda: True)
    monkeypatch.setattr(word_timing, "align_chapter", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("hỏng giữa chừng")))
    project = make_project(tmp_path)
    summary = word_timing.prepare(project)
    assert "hỏng giữa chừng" in summary["error"]
    path = bookfile.pack(project, tmp_path / "sach.abook")
    with zipfile.ZipFile(path) as archive:
        assert "scripts/1.json" in archive.namelist()


def test_a_machine_without_numpy_hands_the_work_to_the_studio_python(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = make_project(tmp_path)
    called: list[list[int]] = []

    class Studio:
        python = Path("python.exe")
        app_root = tmp_path

        def installed(self) -> bool:
            return True

        def outdated(self) -> list[str]:
            return []

    monkeypatch.setattr(word_timing, "in_process", lambda: False)
    monkeypatch.setattr(word_timing, "_studio", lambda: Studio())
    monkeypatch.setattr(word_timing, "_run_in_studio",
                        lambda studio, root, ids, progress, cancelled: called.append(list(ids)) or {"ctc": 3, "lines": 3})
    summary = word_timing.prepare(project, [1])
    assert summary["mode"] == "studio" and called == [[1]] and summary["ctc"] == 3
    monkeypatch.setattr(word_timing, "_studio", None)
    nothing = word_timing.prepare(project, [1])
    assert nothing["mode"] == "off" and "Studio" in nothing["error"], "không có cách nào thì nói rõ, không ném lỗi"
    monkeypatch.setenv(word_timing.ENV_SWITCH, "0")
    assert word_timing.prepare(project)["error"] == "" and not word_timing.enabled()


def test_the_model_folder_is_found_from_the_override_the_runtime_or_the_studio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def make(folder: Path) -> Path:
        folder.mkdir(parents=True)
        for name in word_timing.MODEL_FILES:
            (folder / name).write_bytes(b"x")
        return folder

    assert word_timing.model_dir() is None or word_timing.model_dir().name == "wordalign"
    monkeypatch.setattr(word_timing, "_complete", lambda folder: all((folder / n).is_file() for n in word_timing.MODEL_FILES)
                        and "runtime" not in folder.parts[-3:-1])
    studio = make(tmp_path / "studio" / "wordalign")
    monkeypatch.setattr(word_timing, "_studio", lambda: type("S", (), {"word_align": studio})())
    assert word_timing.model_dir() == studio
    runtime = make(tmp_path / "rt" / "models" / "wordalign")
    monkeypatch.setenv(word_timing.ENV_RUNTIME, str(tmp_path / "rt"))
    assert word_timing.model_dir() == runtime
    override = make(tmp_path / "chi_dinh")
    monkeypatch.setenv(word_timing.ENV_DIR, str(override))
    assert word_timing.model_dir() == override
    (override / "vocab.json").unlink()
    assert word_timing.model_dir() == runtime, "thư mục chỉ định thiếu file thì không dùng"


def test_the_background_job_aligns_then_repacks_and_reports_coverage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = make_project(tmp_path)
    seen: list[str] = []
    monkeypatch.setattr(word_timing, "prepare", lambda root, **kw: seen.append("prepare") or {"error": "", "ctc": 2, "spread": 0, "cached": 0})
    job = word_timing.Job()
    assert job.status(project) == {"state": "idle", "lines": 3, "words": 0}
    job.start(project, lambda: seen.append("repack") or tmp_path / "x.abook")
    for _ in range(100):
        if job.status(project)["state"] != "running":
            break
        import time

        time.sleep(0.05)
    status = job.status(project)
    assert seen == ["prepare", "repack"] and status["state"] == "done" and status["file"].endswith("x.abook")


@needs_ffmpeg
def test_the_studio_python_really_aligns_through_the_command_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """App đóng gói không có numpy: `prepare` chạy `python -m abook.webui.word_timing align --json` bằng Python của Studio (ở đây: chính
    interpreter này làm "Studio") và đọc tiến độ + kết quả từ các dòng JSON nó in."""
    import sys

    internal = Path(__file__).resolve().parents[1]
    project, _ = _chapter_project(tmp_path)

    class Studio:
        python = Path(sys.executable)
        app_root = internal

        def installed(self) -> bool:
            return True

        def outdated(self) -> list[str]:
            return []

        def environment(self) -> dict[str, str]:
            return {"PYTHONPATH": str(internal), "PYTHONUTF8": "1"}

    ticks: list[tuple[int, int]] = []
    monkeypatch.setattr(word_timing, "in_process", lambda: False)
    monkeypatch.setattr(word_timing, "_studio", lambda: Studio())
    summary = word_timing.prepare(project, progress=lambda done, total: ticks.append((done, total)))
    assert summary["error"] == "" and summary["mode"] == "studio" and summary["chapters"] == 1 and summary["spread"] + summary["ctc"] == 4
    assert ticks and ticks[-1] == (4, 4)
    assert all("words" in segment for segment in store.chapter_script(project, 1)["segments"])


# ---- đồng bộ điện thoại: mốc chữ đổi thì gói là bản mới, không đổi thì không tải lại ----------------------------------------------------
def _book_version(project: Path, tmp_path: Path) -> tuple[str, dict]:
    from abook.webui.library import book_id
    from abook.webui.listening import Listening
    from abook.webui.sync import manifest

    book = manifest(project, book_id(project), Listening(tmp_path / "listening.json"))
    return book["version"], book


def test_a_book_without_word_timings_keeps_its_sync_version_and_an_unchanged_one_is_not_downloaded_again(tmp_path: Path) -> None:
    import hashlib

    project = make_project(tmp_path)
    first, book = _book_version(project, tmp_path)
    again, _ = _book_version(project, tmp_path)
    assert "wordsVersion" not in book and first == again, "chưa căn chữ: phiên bản như trước khi có tính năng, gọi lại vẫn y nguyên"
    old = hashlib.sha256(json.dumps([[(c["id"], c["size"]) for c in book["chapters"]], 0], sort_keys=True).encode()).hexdigest()[:16]
    assert first == old, "băm không có mục `words` khi sách chưa căn - điện thoại đã tải không thấy gì đổi"

    word_timing._save(project, 1, {"version": word_timing.VERSION, "audio": {}, "lines": {}})
    aligned, with_words = _book_version(project, tmp_path)
    assert aligned != first and with_words["wordsVersion"] and with_words["version"] == aligned
    assert _book_version(project, tmp_path)[0] == aligned, "căn xong rồi thì gọi lại vẫn một phiên bản: điện thoại tải một lần"

    word_timing._save(project, 2, {"version": word_timing.VERSION, "audio": {}, "lines": {"1": {}}})
    assert _book_version(project, tmp_path)[0] != aligned, "căn thêm chương: bản mới"


def test_the_phone_library_lists_the_same_words_stamp_as_the_manifest_and_the_book_file_never_carries_it(tmp_path: Path) -> None:
    from abook.webui.library import Library, Preferences
    from abook.webui.listening import Listening
    from abook.webui.sync import Devices, SyncApp

    root = tmp_path / "thu_vien"
    root.mkdir()
    project = make_project(root)
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(root)})
    app = SyncApp(Library(preferences), Listening(tmp_path / "listening.json"), Devices(tmp_path / "devices.json"), "Máy thử")
    assert "wordsVersion" not in app.library_view()[0]

    word_timing._save(project, 1, {"version": word_timing.VERSION, "audio": {}, "lines": {}})
    listed = app.library_view()[0]["wordsVersion"]
    assert listed and listed == _book_version(project, tmp_path)[1]["wordsVersion"] == word_timing.stamp(project)

    packed = bookfile.pack(project, tmp_path / "sach.abook")
    with BookFile(packed) as book:
        assert "wordsVersion" not in json.loads(book.read("book.json")), "file sách không mang dấu của máy làm ra nó"
