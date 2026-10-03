"""Nghe thử một cách đọc tên trước khi lưu (webui/reading_preview.py): câu đọc thử đi đúng đường của lần thu thật - bảng cách đọc
của sách cộng MỘT dòng người nghe đang cân nhắc, giọng của người nói câu ấy, hạt giống của lần thu đầu - mà không ghi gì vào sách."""
from __future__ import annotations

import hashlib
import json
import queue
import sqlite3
import sys
import threading
import time
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

import abook.tts as tts_module
from abook import voice_balance
from abook.config import build_settings
from abook.database import LISTENER_PRONUNCIATION_SOURCE
from abook.listener_overrides import request_pronunciation
from abook.tts import TTSCoordinator
from abook.tts_pool import ReadOnlyVoiceDB
from abook.webui import reading_preview, remote_studio
from abook.webui.actions import FakeRunner
from abook.webui.library import Preferences, book_id
from abook.webui.listening import Listening
from abook.webui.reading_preview import PREVIEW_SCRIPT, PreviewError, PreviewVoiceDB, ReadingPreviews
from abook.webui.server import App, Server
from tests.test_listener_speakers import _book
from tests.test_voice_profile_lock import FakeVieNeuRuntime
from tests.test_webui_listen_and_sync import _request

LONG = "“Đi thôi, Natasha, chúng ta không còn nhiều thời gian nữa.”"  # 24-160 ký tự, có tên


def _pronounce(db, surface: str, spoken: str, *, confidence: float = 0.95, source: str = "analysis", locked: int = 0) -> None:
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO pronunciations(surface,normalized_surface,spoken_form,confidence,source,locked,created_at,updated_at)"
            " VALUES(?,?,?,?,?,?,0,0)", (surface, surface.casefold(), spoken, confidence, source, locked))


def _book_with_names(tmp_path: Path):
    """Sách mẫu của bài thử người nói, câu c1s1 (Lucien) có tên Natasha trong một câu dài vừa phải."""
    paths, db = _book(tmp_path)
    (paths.root / "book_settings.json").write_text("{}", encoding="utf-8")
    with db.connect() as conn:
        conn.execute("UPDATE segments SET text=? WHERE stable_id='c1s1'", (LONG,))
    return paths, db


def _digest(*files: Path) -> list[str]:
    return [hashlib.sha256(file.read_bytes()).hexdigest() if file.is_file() else "" for file in files]


def _script() -> dict[str, Any]:
    namespace: dict[str, Any] = {"__name__": "reading_preview_script"}  # không phải __main__: không chạy vòng lặp stdin
    exec(compile(PREVIEW_SCRIPT, "<PREVIEW_SCRIPT>", "exec"), namespace)  # noqa: S102
    return namespace


def _voices(runtime: FakeVieNeuRuntime, monkeypatch) -> None:
    runtime.list_preset_voices = lambda: [(name, name) for name in ("narrator", "v_lucien", "v_natasha", "v_anon_m")]
    # Tên giọng của sách mẫu là giả, không có bản ghi đo trong bảng cân bằng: cho chúng hằng số trung tính.
    monkeypatch.setattr(voice_balance, "_NEUTRAL", {})
    voice_balance.register_neutral_voices(
        {"engine": "vieneu", "preset_name": name, "formant_ratio": 1.0}
        for name in ("narrator", "v_lucien", "v_natasha", "v_anon_m")
    )
    module = ModuleType("vieneu")
    module.Vieneu = lambda **_kwargs: runtime
    monkeypatch.setitem(sys.modules, "vieneu", module)

    def write(path: Path, *_args, **_kwargs):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"RIFF")
        return "checksum", {"duration": 1.0}

    monkeypatch.setattr(tts_module, "atomic_write_wav", write)


def _job(paths, segment: int, surface: str, spoken: str, out: Path, **extra: Any) -> dict[str, Any]:
    return {"id": 1, "project": str(paths.root), "segment": segment, "key": surface.casefold(), "surface": surface,
            "spoken": spoken, "source": LISTENER_PRONUNCIATION_SOURCE, "salt": "primary_0", "output": str(out), **extra}


def _segment_id(db, stable_id: str) -> int:
    with db.connect() as conn:
        return int(conn.execute("SELECT id FROM segments WHERE stable_id=?", (stable_id,)).fetchone()["id"])


def test_the_overlay_replaces_a_known_name_and_inserts_a_new_one(tmp_path: Path) -> None:
    paths, db = _book_with_names(tmp_path)
    _pronounce(db, "Lucien", "Lu-si-en", confidence=0.4)  # dưới ngưỡng, chưa khoá: bảng gốc không trả
    _pronounce(db, "Rhine", "Rai", source="contextual_english_name", locked=1)
    base = ReadOnlyVoiceDB(paths.db)

    replaced = PreviewVoiceDB(paths.db, "rhine", "Rhine", "Rai-nơ", LISTENER_PRONUNCIATION_SOURCE).list_pronunciations(0.58)
    inserted = PreviewVoiceDB(paths.db, "natasha", "Natasha", "Na-ta-xa", LISTENER_PRONUNCIATION_SOURCE).list_pronunciations(0.58)

    mine = next(row for row in replaced if row["normalized_surface"] == "rhine")
    assert (mine["spoken_form"], mine["source"], mine["locked"], mine["confidence"]) == ("Rai-nơ", LISTENER_PRONUNCIATION_SOURCE, 1, 1.0)
    assert len(replaced) == len(base.list_pronunciations(0.58)), "thay đúng một dòng, không thêm dòng"
    added = next(row for row in inserted if row["normalized_surface"] == "natasha")
    assert (added["spoken_form"], added["locked"]) == ("Na-ta-xa", 1)
    assert len(inserted) == len(base.list_pronunciations(0.58)) + 1
    # Tên đang thử mà bảng gốc lọc mất (độ tin cậy thấp, chưa khoá) vẫn vào: người nghe đã chọn nó.
    forced = PreviewVoiceDB(paths.db, "lucien", "Lucien", "Lu-xi-en", LISTENER_PRONUNCIATION_SOURCE).list_pronunciations(0.58)
    assert [row["spoken_form"] for row in forced if row["normalized_surface"] == "lucien"] == ["Lu-xi-en"]
    # Xếp như bảng gốc: từ dài trước.
    lengths = [len(str(row["surface"])) for row in inserted]
    assert lengths == sorted(lengths, reverse=True)


def test_the_source_the_overlay_writes_is_the_one_a_listener_choice_is_saved_with() -> None:
    assert LISTENER_PRONUNCIATION_SOURCE == "listener_choice"


def test_the_preview_reads_the_new_name_in_the_speakers_own_voice(tmp_path: Path, monkeypatch) -> None:
    paths, db = _book_with_names(tmp_path)
    runtime = FakeVieNeuRuntime()
    _voices(runtime, monkeypatch)
    out = tmp_path / "out" / "clip.wav"

    result = _script()["run_job"](_job(paths, _segment_id(db, "c1s1"), "Natasha", "Na-ta-xa", out), {}, lambda _m: None)

    assert result["ok"] and out.is_file()
    text, kwargs = runtime.calls[0]
    assert "Na-ta-xa" in text and "Natasha" not in text
    assert kwargs["voice"] == "v_lucien", "giọng của người nói câu (Lucien), không phải của người có tên trong câu"
    assert kwargs["style"] == "tu_nhien"


def test_a_thought_is_read_by_the_narrator_like_the_real_take(tmp_path: Path, monkeypatch) -> None:
    paths, db = _book_with_names(tmp_path)
    with db.connect() as conn:
        conn.execute("UPDATE segments SET kind='thought' WHERE stable_id='c1s1'")
    runtime = FakeVieNeuRuntime()
    _voices(runtime, monkeypatch)

    result = _script()["run_job"](_job(paths, _segment_id(db, "c1s1"), "Natasha", "Na-ta-xa", tmp_path / "t.wav"), {}, lambda _m: None)

    assert result["ok"]
    assert runtime.calls[0][1]["voice"] == "narrator" and runtime.calls[0][1]["style"] == "doc_truyen"


def test_the_seed_is_the_one_the_first_real_take_would_use(tmp_path: Path, monkeypatch) -> None:
    paths, db = _book_with_names(tmp_path)
    runtime = FakeVieNeuRuntime()
    _voices(runtime, monkeypatch)
    segment = _segment_id(db, "c1s1")

    result = _script()["run_job"](_job(paths, segment, "Natasha", "Na-ta-xa", tmp_path / "s.wav"), {}, lambda _m: None)

    coordinator = TTSCoordinator(build_settings(), ReadOnlyVoiceDB(paths.db), lambda _message: None)
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM segments WHERE id=?", (segment,)).fetchone()
    assert result["seed"] == coordinator.generation_seed(row, "primary_0")
    assert result["seed"] != coordinator.generation_seed(row, "primary_1")


def test_a_preview_leaves_the_book_byte_identical(tmp_path: Path, monkeypatch) -> None:
    paths, db = _book_with_names(tmp_path)
    request_pronunciation(paths.root, "Lucien", "Lu-xi-en", now=1.0)
    runtime = FakeVieNeuRuntime()
    _voices(runtime, monkeypatch)
    before = _digest(paths.db, paths.root / "overrides.json")

    result = _script()["run_job"](_job(paths, _segment_id(db, "c1s1"), "Natasha", "Na-ta-xa", tmp_path / "b.wav"), {}, lambda _m: None)

    assert result["ok"]
    assert _digest(paths.db, paths.root / "overrides.json") == before and before[1], "SQLite và overrides.json không đổi một byte"
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM pronunciations WHERE normalized_surface='natasha'").fetchone()[0] == 0


# ---- tiến trình, hàng chờ, bản cất (giả tiến trình bằng hàng đợi) -------------------------------------------------


class FakeChild:
    """Một tiến trình giả nói đúng giao thức: đọc từng dòng JSON từ stdin, trả `ready`, `loaded` rồi kết quả."""

    def __init__(self, behaviour: str = "ok") -> None:
        self.behaviour = behaviour
        self.out: queue.Queue[str | None] = queue.Queue()
        self.stdout = iter(self.out.get, None)
        self.stdin = self
        self.killed = False
        self.jobs: list[dict[str, Any]] = []
        self.out.put(json.dumps({"event": "ready"}) + "\n")

    def write(self, text: str) -> None:
        request = json.loads(text)
        self.jobs.append(request)
        if self.behaviour == "silent":
            return
        self.out.put(json.dumps({"event": "loaded", "id": request["id"]}) + "\n")
        if self.behaviour == "fail":
            self.out.put(json.dumps({"id": request["id"], "error": "AudioQualityError: giọng không đọc được"}) + "\n")
            return
        Path(request["output"]).write_bytes(b"RIFF....WAVE")
        self.out.put(json.dumps({"id": request["id"], "ok": True, "seed": 7}) + "\n")

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass

    def poll(self) -> int | None:
        return 1 if self.killed else None

    def kill(self) -> None:
        self.killed = True
        self.out.put(None)


class Launcher:
    def __init__(self, behaviour: str = "ok") -> None:
        self.behaviour = behaviour
        self.children: list[FakeChild] = []
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], environment: dict[str, str], cwd: Path) -> FakeChild:
        self.commands.append(command)
        self.last_environment = environment
        child = FakeChild(self.behaviour)
        self.children.append(child)
        return child


def _previews(tmp_path: Path, launcher: Launcher, *, busy=lambda: False, studio=lambda: None, probe=lambda: (8000, 16.0),
              **options: Any) -> ReadingPreviews:
    return ReadingPreviews(tmp_path / "previews", studio=studio, fake=lambda: False, busy=busy, launcher=launcher,
                           probe=probe, **options)


def _ask(previews: ReadingPreviews, paths, surface: str = "Natasha", spoken: str = "Na-ta-xa", segment: int | None = None):
    return previews.preview(paths.root, "livre", surface, spoken, segment)


def test_the_shortest_line_with_the_name_is_the_default_and_a_repeat_is_free(tmp_path: Path) -> None:
    paths, db = _book_with_names(tmp_path)
    with db.connect() as conn:  # một câu dài hơn cũng có tên: không được chọn
        conn.execute("UPDATE segments SET text=? WHERE stable_id='c1s2'", (LONG + " Natasha lại nói thêm một câu nữa.",))
    launcher = Launcher()
    previews = _previews(tmp_path, launcher)

    first = _ask(previews, paths)
    again = _ask(previews, paths)

    assert first["segmentId"] == _segment_id(db, "c1s1") and first["text"] == LONG and first["speaker"] == "Lucien"
    assert first["cached"] is False and again["cached"] is True and again["url"] == first["url"]
    assert len(launcher.children) == 1 and len(launcher.children[0].jobs) == 1, "lần nghe lại không khởi động hay hỏi gì"
    assert first["url"].startswith("/media/books/livre/reading-previews/") and first["url"].endswith(".wav")
    key = first["url"].rsplit("/", 1)[1][:-4]
    assert previews.file("livre", key) is not None and previews.file("livre", "z" * 32) is None
    job = launcher.children[0].jobs[0]
    assert job["salt"] == "primary_0" and job["spoken"] == "Na-ta-xa" and job["source"] == LISTENER_PRONUNCIATION_SOURCE
    assert launcher.commands[0][:2] == [sys.executable, "-c"] and launcher.commands[0][2] == PREVIEW_SCRIPT
    assert launcher.last_environment["HF_HUB_OFFLINE"] == "1"
    previews.shutdown()


def test_a_different_reading_is_a_different_clip(tmp_path: Path) -> None:
    paths, _db = _book_with_names(tmp_path)
    launcher = Launcher()
    previews = _previews(tmp_path, launcher)

    one = _ask(previews, paths, spoken="Na-ta-xa")
    two = _ask(previews, paths, spoken="Na-ta-sa")

    assert one["url"] != two["url"] and two["cached"] is False
    assert len(launcher.children) == 1 and len(launcher.children[0].jobs) == 2, "cùng tiến trình, model nạp một lần"
    previews.shutdown()


def test_the_example_line_is_the_fallback_when_no_line_is_in_the_comfortable_range(tmp_path: Path) -> None:
    paths, db = _book_with_names(tmp_path)
    with db.connect() as conn:
        conn.execute("UPDATE segments SET text='“Natasha!”' WHERE stable_id='c1s1'")
    previews = _previews(tmp_path, Launcher())

    fresh = _ask(previews, paths)  # tên chưa có trong bảng cách đọc: câu ngắn nhất có tên
    _pronounce(db, "Natasha", "Na-ta-sa")
    listed = _ask(previews, paths, spoken="Na-ta-za")  # tên đã có: câu mẫu của mục "Cách đọc tên"

    assert fresh["text"] == "“Natasha!”" and listed["text"] == "Lucien nhìn Natasha."
    previews.shutdown()
    with pytest.raises(PreviewError) as raised:
        _previews(tmp_path, Launcher()).preview(paths.root, "livre", "Khong-co-ten", "Khong-co-ten", None)
    assert raised.value.reason == "no-line"


def test_a_failed_take_is_reported_and_the_process_is_dropped(tmp_path: Path) -> None:
    paths, _db = _book_with_names(tmp_path)
    launcher = Launcher("fail")
    previews = _previews(tmp_path, launcher)

    with pytest.raises(PreviewError) as raised:
        _ask(previews, paths)

    assert raised.value.status == 422 and "giọng không đọc được" in raised.value.message
    assert launcher.children[0].killed
    launcher.behaviour = "ok"
    assert _ask(previews, paths)["cached"] is False and len(launcher.children) == 2, "lần sau khởi động lại cho sạch"
    previews.shutdown()


def test_a_hung_process_is_killed_at_the_deadline(tmp_path: Path) -> None:
    paths, _db = _book_with_names(tmp_path)
    launcher = Launcher("silent")
    previews = _previews(tmp_path, launcher, load_timeout=0.3, job_timeout=0.3)

    started = time.monotonic()
    with pytest.raises(PreviewError) as raised:
        _ask(previews, paths)

    assert raised.value.reason == "timeout" and raised.value.status == 422
    assert launcher.children[0].killed and time.monotonic() - started < 5
    assert not list((tmp_path / "previews").glob("**/*.wav")), "không cất bản dở"


def test_a_book_starting_kills_the_process(tmp_path: Path) -> None:
    paths, _db = _book_with_names(tmp_path)
    launcher = Launcher()
    previews = _previews(tmp_path, launcher)
    _ask(previews, paths)

    previews.shutdown()

    assert launcher.children[0].killed
    assert _ask(previews, paths)["cached"] is True, "bản đã cất vẫn nghe được"
    previews.shutdown()


def test_the_process_leaves_after_it_has_been_idle(tmp_path: Path) -> None:
    paths, _db = _book_with_names(tmp_path)
    launcher = Launcher()
    previews = _previews(tmp_path, launcher, idle_seconds=0.2)
    _ask(previews, paths)

    deadline = time.monotonic() + 5
    while not launcher.children[0].killed and time.monotonic() < deadline:
        time.sleep(0.05)

    assert launcher.children[0].killed


def test_at_most_two_wait_and_the_next_is_told_to_try_later(tmp_path: Path) -> None:
    paths, _db = _book_with_names(tmp_path)
    gate = threading.Event()

    class Slow(Launcher):
        def __call__(self, command, environment, cwd):
            child = super().__call__(command, environment, cwd)
            original = child.write

            def held(text: str) -> None:
                gate.wait(10)
                original(text)

            child.write = held  # type: ignore[method-assign]
            return child

    launcher = Slow()
    previews = _previews(tmp_path, launcher)
    results: list[Any] = []

    def ask(spoken: str) -> None:
        try:
            results.append(_ask(previews, paths, spoken=spoken))
        except PreviewError as error:
            results.append(error)

    threads = [threading.Thread(target=ask, args=(spoken,)) for spoken in ("Na-ta-a", "Na-ta-b", "Na-ta-c")]
    for thread in threads:
        thread.start()
        time.sleep(0.15)  # theo thứ tự: một đang làm, hai đang chờ
    with pytest.raises(PreviewError) as raised:
        _ask(previews, paths, spoken="Na-ta-d")
    gate.set()
    for thread in threads:
        thread.join(10)

    assert raised.value.status == 429 and raised.value.reason == "busy"
    assert len(results) == 3 and all(isinstance(item, dict) for item in results)
    previews.shutdown()


def test_the_whole_request_fits_in_what_a_remote_studio_waits() -> None:
    assert reading_preview.REQUEST_BUDGET < remote_studio.FORWARD_SECONDS
    assert reading_preview.LOAD_TIMEOUT + reading_preview.JOB_TIMEOUT <= reading_preview.REQUEST_BUDGET


def test_only_the_newest_fifty_clips_of_a_book_are_kept(tmp_path: Path) -> None:
    folder = tmp_path / "previews" / "livre"
    folder.mkdir(parents=True)
    for index in range(reading_preview.KEEP_PER_BOOK + 5):
        clip = folder / f"{index:032x}.wav"
        clip.write_bytes(b"RIFF")
        stamp = 1_000_000 + index
        import os

        os.utime(clip, (stamp, stamp))
    (folder / ("a" * 32 + ".part.wav")).write_bytes(b"RIFF")

    ReadingPreviews._tidy(folder)

    names = sorted(entry.name for entry in folder.iterdir())
    assert len(names) == reading_preview.KEEP_PER_BOOK and f"{0:032x}.wav" not in names and f"{54:032x}.wav" in names


# ---- đường HTTP --------------------------------------------------------------------------------------------------


class Studio:
    def __init__(self, *, installed: bool, outdated: tuple[str, ...] = ()) -> None:
        self._installed, self._outdated = installed, outdated

    def installed(self) -> bool:
        return self._installed

    def outdated(self) -> list[str]:
        return list(self._outdated)


@pytest.fixture()
def studio_app(tmp_path: Path, monkeypatch):
    paths, db = _book_with_names(tmp_path)
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    runner = FakeRunner()
    app = App(preferences=preferences, runner=runner, token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    launcher = Launcher()
    app.previews.fake = lambda: False  # đường thật (giả tiến trình) - FakeRunner chỉ giả việc làm sách
    app.previews.launcher = launcher
    app.previews.probe = lambda: (8000, 16.0)
    server = Server(app, port=0).start()
    try:
        yield app, server, paths, db, launcher, runner
    finally:
        app.close()
        server.stop()


def _post(server, paths, body: dict[str, Any], path: str = "pronunciation/preview"):
    return _request(server.port, "POST", f"/api/books/{book_id(paths.root)}/{path}", headers={"X-Ebook-Token": "t"}, body=body)


def test_the_route_returns_a_playable_clip_and_changes_nothing_in_the_book(studio_app) -> None:
    app, server, paths, _db, launcher, _runner = studio_app
    request_pronunciation(paths.root, "Lucien", "Lu-xi-en", now=1.0)
    before = _digest(paths.db, paths.root / "overrides.json")

    status, data, _ = _post(server, paths, {"surface": "Natasha", "spokenForm": "Na-ta-xa"})
    result = json.loads(data)
    assert status == 200 and result["cached"] is False and result["text"] == LONG and result["speaker"] == "Lucien"

    status, clip, headers = _request(server.port, "GET", result["url"], headers={"X-Ebook-Token": "t"})
    assert status == 200 and clip.startswith(b"RIFF") and headers["Content-Type"] == "audio/wav"
    assert _digest(paths.db, paths.root / "overrides.json") == before
    status, data, _ = _post(server, paths, {"surface": "Natasha", "spokenForm": "Na-ta-xa"})
    assert status == 200 and json.loads(data)["cached"] is True and len(launcher.children) == 1
    status, _data, _ = _request(server.port, "GET", f"/media/books/{book_id(paths.root)}/reading-previews/{'0' * 32}.wav",
                                headers={"X-Ebook-Token": "t"})
    assert status == 404


def test_a_reading_the_pipeline_would_refuse_is_refused_before_anything_starts(studio_app) -> None:
    _app, server, paths, _db, launcher, _runner = studio_app

    status, data, _ = _post(server, paths, {"surface": "Natasha", "spokenForm": "Na ta xa 123"})
    assert status == 400 and json.loads(data)["error"]
    status, data, _ = _post(server, paths, {"surface": "Lucien Natasha", "spokenForm": "Lu-xi-en"})
    assert status == 400
    status, data, _ = _post(server, paths, {"surface": "Natasha"})
    assert status == 400
    assert launcher.children == []


def test_studio_not_installed_or_outdated_is_a_503_with_a_reason(studio_app) -> None:
    app, server, paths, _db, launcher, _runner = studio_app
    app.studio = Studio(installed=False)

    status, data, _ = _post(server, paths, {"surface": "Natasha", "spokenForm": "Na-ta-xa"})
    assert status == 503 and json.loads(data)["reason"] == "studio"
    app.studio = Studio(installed=True, outdated=("Ollama",))
    status, data, _ = _post(server, paths, {"surface": "Natasha", "spokenForm": "Na-ta-xa"})
    assert status == 503 and json.loads(data)["reason"] == "studio"
    assert launcher.children == []


def test_a_running_book_blocks_the_preview_and_starting_one_stops_the_process(studio_app) -> None:
    app, server, paths, _db, launcher, runner = studio_app
    status, _data, _ = _post(server, paths, {"surface": "Natasha", "spokenForm": "Na-ta-xa"})
    assert status == 200 and not launcher.children[0].killed

    runner._running.add(str(paths.root))  # cuốn bắt đầu chạy
    status, data, _ = _post(server, paths, {"surface": "Natasha", "spokenForm": "Na-ta-sa"})
    assert status == 409 and json.loads(data)["reason"] == "producing" and len(launcher.children) == 1
    runner._running.discard(str(paths.root))

    app._launch(paths.root)  # mọi đường bắt đầu (nút Bắt đầu, hàng đợi) đều đi qua đây
    assert launcher.children[0].killed, "cuốn bắt đầu thì model nghe thử phải nhả card"


def test_a_busy_card_is_a_409_with_a_reason(studio_app) -> None:
    app, server, paths, _db, launcher, _runner = studio_app
    app.previews.probe = lambda: (1500, 16.0)
    status, data, _ = _post(server, paths, {"surface": "Natasha", "spokenForm": "Na-ta-xa"})
    assert status == 409 and json.loads(data)["reason"] == "gpu"
    app.previews.probe = lambda: (8000, 5.9)
    status, data, _ = _post(server, paths, {"surface": "Natasha", "spokenForm": "Na-ta-xa"})
    assert status == 409 and json.loads(data)["reason"] == "gpu"
    assert launcher.children == []


def test_a_name_with_no_cast_line_is_a_422(studio_app) -> None:
    _app, server, paths, _db, _launcher, _runner = studio_app
    status, data, _ = _post(server, paths, {"surface": "Zorro", "spokenForm": "Dô-rô"})
    assert status == 422 and json.loads(data)["reason"] == "no-line"
    status, data, _ = _post(server, paths, {"surface": "Natasha", "spokenForm": "Na-ta-xa", "segmentId": 9999})
    assert status == 400


def test_the_real_process_speaks_the_protocol_with_the_fake_voice(tmp_path: Path) -> None:
    """Không giả tiến trình: python thật chạy PREVIEW_SCRIPT, giọng giả (ABOOK_FAKE_RUNNER) - cả đường từ HTTP tới file wav."""
    paths, _db = _book_with_names(tmp_path)
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    before = _digest(paths.db)
    try:
        status, data, _ = _post(server, paths, {"surface": "Natasha", "spokenForm": "Na-ta-xa"})
        result = json.loads(data)
        assert status == 200, data
        status, clip, _ = _request(server.port, "GET", result["url"], headers={"X-Ebook-Token": "t"})
        assert status == 200 and clip[:4] == b"RIFF" and len(clip) > 1000
        status, data, _ = _post(server, paths, {"surface": "Natasha", "spokenForm": "Na-ta-xa"})
        assert json.loads(data)["cached"] is True
        assert _digest(paths.db) == before
    finally:
        app.close()
        server.stop()


def test_a_remote_studio_may_preview_only_when_it_may_produce() -> None:
    book = "/api/books/YWJj"
    clip = "/media/books/YWJj/reading-previews/" + "a" * 32 + ".wav"
    assert remote_studio.permitted("POST", book + "/pronunciation/preview")
    assert remote_studio.permitted("GET", clip)
    assert not remote_studio.permitted("POST", book + "/pronunciation/preview", producing=False), "nghe thử dùng card của máy tính"
    assert not remote_studio.permitted("GET", clip, producing=False)
    assert not remote_studio.permitted("GET", "/media/books/YWJj/reading-previews/../../preferences.json")
    assert not any(pattern.fullmatch(book + "/pronunciation/preview") for _verb, pattern in remote_studio.LISTEN_ROUTES)
