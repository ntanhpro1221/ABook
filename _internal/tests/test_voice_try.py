"""Nghe thử một giọng bằng câu của sách trước khi đổi giọng nhân vật (hộp "Đổi giọng", hộp "Áp dụng" - soát UX Studio mục
13 và 15): một câu "đại diện" của chính nhân vật, đọc bằng ĐÚNG hồ sơ giọng dây chuyền sẽ tạo khi áp, qua cùng tiến trình và
hàng chờ của nghe thử cách đọc tên (webui/reading_preview.py) - không ghi gì vào sách, không chen vào một cuốn đang làm. Kèm
số câu đã thu sẽ thu lại và thời gian ước (số đo của cuốn, chưa đo thì số dư tay). Chữ trong bài thử là chữ tự đặt."""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path
from types import ModuleType

import pytest

import abook.tts as tts_module
from abook.config import build_settings
from abook.listener_overrides import UNKNOWN_PRESET, request_voice
from abook.tts import TTSCoordinator
from abook.tts_pool import ReadOnlyVoiceDB
from abook.webui import remote_studio, store
from abook.webui.actions import FakeRunner
from abook.webui.library import Preferences, book_id
from abook.webui.listening import Listening
from abook.webui.reading_preview import PreviewError, PreviewVoiceDB, character_line
from abook.webui.server import App, Server
from abook.webui.voice_picker import voice_choices
from tests.test_listener_voices import FEMALE, MALE, NARRATOR_VOICE, _book
from tests.test_reading_preview import Launcher, _digest, _previews, _script
from tests.test_voice_profile_lock import FakeVieNeuRuntime
from tests.test_webui_listen_and_sync import _request

CALM = "“Mình cứ đi chậm thôi, đường còn dài và trời cũng chưa tối hẳn đâu.”"  # 40-160, bình thường
ANGRY = "“Đứng lại ngay, tôi đã bảo là không được chạm vào cái hộp ấy!”"  # 40-160, giận
CANDIDATE = MALE[2]["name"]  # giọng nam chưa ai trong sách mẫu dùng


def _noah(tmp_path: Path):
    """Sách mẫu của bài thử đổi giọng; Noah có hai câu thoại dài vừa phải - một câu giận, một câu bình thường."""
    paths, db = _book(tmp_path)
    (paths.root / "book_settings.json").write_text("{}", encoding="utf-8")
    with db.connect() as conn:
        conn.execute("UPDATE segments SET text=?, emotion='angry' WHERE stable_id='c1s2'", (ANGRY,))
        conn.execute("UPDATE segments SET text=?, emotion='neutral' WHERE stable_id='c1s4'", (CALM,))
    return paths, db


def _row(paths, stable_id: str) -> sqlite3.Row:
    connection = sqlite3.connect(paths.db)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute("SELECT * FROM segments WHERE stable_id=?", (stable_id,)).fetchone()
    finally:
        connection.close()


def _line(paths, character: str, segment_id: int | None = None) -> sqlite3.Row:
    connection = store.connect(paths.root)
    try:
        return character_line(connection, character, segment_id)
    finally:
        connection.close()


# ---- câu nào được đọc ---------------------------------------------------------------------------------------------------


def test_the_try_line_is_a_calm_line_of_the_character_in_a_comfortable_length(tmp_path: Path) -> None:
    paths, _db = _noah(tmp_path)
    assert _line(paths, "NOAH")["stable_id"] == "c1s4", "câu bình thường thắng câu giận"
    with sqlite3.connect(paths.db) as conn:
        conn.execute("UPDATE segments SET emotion='sad' WHERE stable_id='c1s4'")
    assert _line(paths, "NOAH")["stable_id"] == "c1s4", "không câu nào bình thường: lời thoại gần giữa khoảng 40-160 hơn"


def test_a_character_with_only_short_lines_gets_the_nearest_and_one_with_none_is_no_line(tmp_path: Path) -> None:
    paths, _db = _noah(tmp_path)
    assert _line(paths, "LUCIEN")["stable_id"] == "c1s1", "chỉ có “Đi thôi.”: vẫn đọc được bằng câu của sách"
    with sqlite3.connect(paths.db) as conn:
        conn.execute("UPDATE segments SET voice_profile_id=NULL WHERE stable_id='c1s1'")
    with pytest.raises(PreviewError) as raised:
        _line(paths, "LUCIEN")
    assert raised.value.reason == "no-line"


def test_a_chosen_line_must_be_the_characters_own(tmp_path: Path) -> None:
    paths, _db = _noah(tmp_path)
    angry = int(_row(paths, "c1s2")["id"])
    assert int(_line(paths, "NOAH", angry)["id"]) == angry
    with pytest.raises(PreviewError) as raised:
        _line(paths, "NOAH", int(_row(paths, "c1s1")["id"]))
    assert raised.value.status == 400


# ---- tiến trình giọng: đọc bằng hồ sơ sẽ áp ------------------------------------------------------------------------------


def _voices(runtime: FakeVieNeuRuntime, monkeypatch) -> None:
    names = [NARRATOR_VOICE, *(preset["name"] for preset in MALE[:3] + FEMALE[:2])]
    runtime.list_preset_voices = lambda: [(name, name) for name in names]
    module = ModuleType("vieneu")
    module.Vieneu = lambda **_kwargs: runtime
    monkeypatch.setitem(sys.modules, "vieneu", module)

    def write(path: Path, *_args, **_kwargs):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"RIFF")
        return "checksum", {"duration": 1.0}

    monkeypatch.setattr(tts_module, "atomic_write_wav", write)


def test_the_line_is_read_in_the_voice_the_change_would_give_with_the_first_takes_seed(tmp_path: Path, monkeypatch) -> None:
    paths, db = _noah(tmp_path)
    runtime = FakeVieNeuRuntime()
    _voices(runtime, monkeypatch)
    launcher = Launcher()
    previews = _previews(tmp_path, launcher)
    shown = previews.voice_preview(paths.root, "livre", "Noah", preset=CANDIDATE)
    job = launcher.children[0].jobs[0]
    previews.shutdown()
    before = _digest(paths.db)

    result = _script()["run_job"]({**job, "id": 1, "output": str(tmp_path / "v.wav")}, {}, lambda _m: None)

    assert shown["text"] == CALM and shown["speaker"] == "Noah" and job["voice"]["preset_name"] == CANDIDATE
    assert "key" not in job and "spoken" not in job, "không chồng cách đọc nào"
    assert result["ok"] and runtime.calls[0][1]["voice"] == CANDIDATE
    assert _digest(paths.db) == before, "nghe thử không ghi gì vào sách"
    # Áp thật rồi so: lần thu đầu bằng giọng mới dùng đúng hạt giống bản nghe thử đã dùng.
    db.apply_listener_voice(character="NOAH", voices=store.book_voices(paths.root), preset=CANDIDATE)
    coordinator = TTSCoordinator(build_settings(), ReadOnlyVoiceDB(paths.db), lambda _message: None)
    assert result["seed"] == coordinator.generation_seed(_row(paths, "c1s4"), "primary_0")


def test_the_overlay_stands_in_only_for_the_lines_own_profile(tmp_path: Path) -> None:
    paths, _db = _noah(tmp_path)
    line = _row(paths, "c1s4")
    other = int(_row(paths, "c1s3")["voice_profile_id"])
    voice = {"id": int(line["voice_profile_id"]), "voice_key": "thu", "engine": "vieneu", "preset_name": CANDIDATE}
    overlay = PreviewVoiceDB(paths.db, None, None, None, None, voice)
    base = ReadOnlyVoiceDB(paths.db)

    assert overlay.voice_profile(int(line["voice_profile_id"]))["preset_name"] == CANDIDATE
    assert dict(overlay.voice_profile(other)) == dict(base.voice_profile(other))
    assert [dict(row) for row in overlay.list_pronunciations(0.0)] == [dict(row) for row in base.list_pronunciations(0.0)]
    assert len(overlay.list_voice_profiles()) == len(base.list_voice_profiles()) + 1


# ---- bản cất, hàng chờ, nhường card -----------------------------------------------------------------------------------


def test_one_clip_per_voice_and_line_and_a_repeat_is_free(tmp_path: Path) -> None:
    paths, _db = _noah(tmp_path)
    launcher = Launcher()
    previews = _previews(tmp_path, launcher)

    one = previews.voice_preview(paths.root, "livre", "NOAH", preset=CANDIDATE)
    again = previews.voice_preview(paths.root, "livre", "NOAH", preset=CANDIDATE)
    other = previews.voice_preview(paths.root, "livre", "NOAH", preset=MALE[0]["name"])
    angry = previews.voice_preview(paths.root, "livre", "NOAH", preset=CANDIDATE, segment_id=int(_row(paths, "c1s2")["id"]))

    assert one["cached"] is False and again["cached"] is True and again["url"] == one["url"]
    assert len({one["url"], other["url"], angry["url"]}) == 3
    assert len(launcher.children) == 1 and len(launcher.children[0].jobs) == 3, "cùng tiến trình; lần nghe lại không hỏi gì"
    assert previews.file("livre", one["url"].rsplit("/", 1)[1][:-4]) is not None
    previews.shutdown()


def test_the_voice_the_character_already_has_is_read_with_its_own_profile(tmp_path: Path) -> None:
    paths, _db = _noah(tmp_path)
    launcher = Launcher()
    previews = _previews(tmp_path, launcher)
    with sqlite3.connect(paths.db) as conn:
        current = conn.execute("SELECT v.preset_name FROM segments s JOIN voice_profiles v ON v.id=s.voice_profile_id"
                               " WHERE s.stable_id='c1s4'").fetchone()[0]

    previews.voice_preview(paths.root, "livre", "NOAH", preset=current)

    assert launcher.children[0].jobs[0]["voice"] is None
    previews.shutdown()


def test_a_running_book_or_a_busy_card_is_told_not_waited_for(tmp_path: Path) -> None:
    paths, _db = _noah(tmp_path)
    launcher = Launcher()
    with pytest.raises(PreviewError) as producing:
        _previews(tmp_path, launcher, busy=lambda: True).voice_preview(paths.root, "livre", "NOAH", preset=CANDIDATE)
    with pytest.raises(PreviewError) as card:
        _previews(tmp_path, launcher, probe=lambda: (1200, 16.0)).voice_preview(paths.root, "livre", "NOAH", preset=CANDIDATE)
    assert (producing.value.status, producing.value.reason) == (409, "producing")
    assert (card.value.status, card.value.reason) == (409, "gpu")
    assert launcher.children == [], "không khởi động gì"


def test_the_refusal_names_the_book_and_the_phase_that_hold_the_card(tmp_path: Path) -> None:
    paths, _db = _noah(tmp_path)

    def refusal(phase: str) -> PreviewError:
        busy = lambda: {"title": "Tắt đèn", "bookId": "tat-den", "phase": phase}  # noqa: E731
        with pytest.raises(PreviewError) as raised:
            _previews(tmp_path, Launcher(), busy=busy).voice_preview(paths.root, "livre", "NOAH", preset=CANDIDATE)
        return raised.value

    analysis = refusal("analysis")
    assert analysis.reason == "producing" and "phân tích cuốn “Tắt đèn”" in analysis.message
    assert "Đừng bấm Dừng" in analysis.message, "dừng giữa pha phân tích là đổi quyển sách: không mời"
    assert analysis.extra == {"busyBook": "Tắt đèn", "busyBookId": "tat-den", "busyPhase": "analysis"}
    synthesis = refusal("synthesis")
    assert "thu âm cuốn “Tắt đèn”" in synthesis.message and "Dừng nó" in synthesis.message
    assert "Tạm dừng" not in synthesis.message, "Tạm dừng không nhả card: không hứa điều đó"
    assert "cuốn “Tắt đèn”" in refusal("").message


def test_a_voice_the_change_would_refuse_is_refused_with_the_same_reason(tmp_path: Path) -> None:
    paths, _db = _noah(tmp_path)
    with pytest.raises(PreviewError) as raised:
        _previews(tmp_path, Launcher()).voice_preview(paths.root, "livre", "NOAH", preset=NARRATOR_VOICE)
    assert (raised.value.status, raised.value.reason) == (400, UNKNOWN_PRESET)


# ---- số câu thu lại, thời gian ước --------------------------------------------------------------------------------------


def test_the_time_is_the_books_own_pace_or_a_generous_guess(tmp_path: Path) -> None:
    paths, _db = _noah(tmp_path)
    connection = store.connect(paths.root)
    try:
        assert store.seconds_per_line(connection) == (store.FALLBACK_SECONDS_PER_LINE, False)
    finally:
        connection.close()
    now = time.time()
    with sqlite3.connect(paths.db) as conn:
        conn.execute("UPDATE chapters SET started_at=?, completed_at=?, total_segments=6", (now - 60, now))
    connection = store.connect(paths.root)
    try:
        each, measured = store.seconds_per_line(connection)
    finally:
        connection.close()
    assert measured and abs(each - 10.0) < 0.01


def test_the_picker_names_the_try_line_and_what_a_change_costs(tmp_path: Path) -> None:
    paths, _db = _noah(tmp_path)

    view = voice_choices(paths.root, "Noah")

    assert view is not None and view["tryLine"]["text"] == CALM
    assert view["rerecord"] == {"lines": 2, "seconds": round(2 * store.FALLBACK_SECONDS_PER_LINE, 1), "measured": False}


def test_the_apply_box_carries_what_it_needs_to_try_the_waiting_voice(tmp_path: Path) -> None:
    paths, _db = _noah(tmp_path)
    since = time.time() - 1
    request_voice(paths.root, "NOAH", preset=CANDIDATE, now=time.time())

    details = store.pending_details(paths.root, since)

    (item,) = [item for item in details["items"] if item["kind"] == "voice"]
    assert item["voice"]["preset"] == CANDIDATE and item["voice"]["gender"] == "" and item["lines"] == 2
    assert details["measured"] is False and details["seconds"] == round(2 * store.FALLBACK_SECONDS_PER_LINE, 1)


# ---- đường HTTP -------------------------------------------------------------------------------------------------------


@pytest.fixture()
def studio_app(tmp_path: Path):
    paths, db = _noah(tmp_path)
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    runner = FakeRunner()
    app = App(preferences=preferences, runner=runner, token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    launcher = Launcher()
    app.previews.fake = lambda: False
    app.previews.launcher = launcher
    app.previews.probe = lambda: (8000, 16.0)
    server = Server(app, port=0).start()
    try:
        yield app, server, paths, launcher, runner
    finally:
        app.close()
        server.stop()


def _post(server, paths, body):
    return _request(server.port, "POST", f"/api/books/{book_id(paths.root)}/voice/preview", headers={"X-Ebook-Token": "t"},
                    body=body, timeout=10)


def test_the_route_returns_a_playable_clip_and_changes_nothing(studio_app) -> None:
    _app, server, paths, launcher, runner = studio_app
    before = _digest(paths.db, paths.root / "overrides.json")

    status, data, _ = _post(server, paths, {"character": "NOAH", "preset": CANDIDATE})
    result = json.loads(data)
    assert status == 200 and result["text"] == CALM and result["cached"] is False
    status, clip, _ = _request(server.port, "GET", result["url"], headers={"X-Ebook-Token": "t"})
    assert status == 200 and clip.startswith(b"RIFF")
    assert _digest(paths.db, paths.root / "overrides.json") == before

    status, data, _ = _post(server, paths, {"character": "NOAH", "preset": NARRATOR_VOICE})
    assert status == 400 and json.loads(data)["reason"] == UNKNOWN_PRESET and "người kể" in json.loads(data)["error"]
    status, data, _ = _post(server, paths, {"preset": CANDIDATE})
    assert status == 400
    runner._running.add(str(paths.root))
    status, data, _ = _post(server, paths, {"character": "NOAH", "preset": MALE[0]["name"]})
    assert status == 409 and json.loads(data)["reason"] == "producing" and len(launcher.children[0].jobs) == 1


def test_a_remote_studio_may_try_a_voice_only_when_it_may_produce() -> None:
    path = "/api/books/YWJj/voice/preview"
    assert remote_studio.permitted("POST", path)
    assert not remote_studio.permitted("POST", path, producing=False), "nghe thử dùng card của máy tính"
