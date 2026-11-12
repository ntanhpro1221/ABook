"""The book's own name readings reach every place a line is voiced: the voice preview and the synthesis-pool workers.

A capital word such as "KAEL" is read as a name ("Kael") only because the BOOK proves it is one - here, by the character list.
Without that proof the same line is spelled out, letter by letter. The preview and the pool workers read the book through a
read-only stand-in for the project database; when the stand-in had no character list, the preview answered 422 and a worker
failed every line. These tests voice one line through each of those paths - in this process, and in the real second process -
and look at the text the model was given.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from abook.tts import TTSCoordinator
from abook.tts_pool import ReadOnlyVoiceDB, SynthesisPool
from abook.webui.actions import FakeRunner
from abook.webui.library import Preferences
from abook.webui.listening import Listening
from abook.webui.reading_preview import PreviewVoiceDB
from abook.webui.server import App, Server
from tests import recording_voice
from tests.test_reading_preview import _book_with_names, _job, _post, _script, _segment_id, _voices
from tests.test_voice_profile_lock import FakeVieNeuRuntime
from tests.test_webui_listen_and_sync import _request

# Unshouted capitals in the middle of a sentence: a name only if the book says so. (Shouted, "KAEL!" reads as a word anyway.)
LINE = '“Natasha, đưa KAEL tập phiếu trước lúc quầy kiểm kê đóng cửa nhé.”'
VOICES = ["narrator", "v_lucien", "v_natasha", "v_anon_m"]
PROCESS_SECONDS = 240  # a real python starts and imports the voice stack; slow when the machine is busy


def _book(tmp_path: Path, *, on_the_roster: bool):
    """The sample book, its line c1s1 holding the capital word; with `on_the_roster` the character list names KAEL."""
    paths, db = _book_with_names(tmp_path)
    with db.connect() as conn:
        conn.execute("UPDATE segments SET text=? WHERE stable_id='c1s1'", (LINE,))
        if on_the_roster:
            conn.execute("UPDATE characters SET canonical_name='KAEL', display_name='Kael' WHERE canonical_name='LUCIEN'")
    return paths, db


def _line(db) -> dict[str, Any]:
    with db.connect() as conn:
        return dict(conn.execute("SELECT * FROM segments WHERE stable_id='c1s1'").fetchone())


def _settings(db) -> dict[str, Any]:
    with db.connect() as conn:
        return json.loads(str(conn.execute("SELECT settings_json FROM book WHERE id=1").fetchone()["settings_json"]))


def _reads_the_name(text: str) -> bool:
    """True when the capital word went to the model as a name, False when it went as letters; anything else is a failure."""
    folded = text.casefold()
    as_name, as_letters = "kael" in folded, "k a e l" in folded
    assert as_name != as_letters, f"neither or both readings in what the model was given: {text!r}"
    return as_name


STAND_INS = {
    "ReadOnlyVoiceDB": lambda path: ReadOnlyVoiceDB(path),
    "PreviewVoiceDB": lambda path: PreviewVoiceDB(path, "natasha", "Natasha", "Na-ta-xa", "listener_choice"),
}


@pytest.mark.parametrize("stand_in", sorted(STAND_INS))
@pytest.mark.parametrize("on_the_roster", [True, False])
def test_a_stand_in_reads_the_line_as_the_project_database_does(tmp_path: Path, stand_in: str, on_the_roster: bool) -> None:
    paths, db = _book(tmp_path, on_the_roster=on_the_roster)
    row = _line(db)
    whole = TTSCoordinator(_settings(db), db, lambda _message: None)
    reader = TTSCoordinator(_settings(db), STAND_INS[stand_in](paths.db), lambda _message: None)

    assert reader._book_name_readings() == whole._book_name_readings() == ({"KAEL": "Kael"} if on_the_roster else {})
    assert _reads_the_name(reader.spoken_text(row)) is on_the_roster
    assert _reads_the_name(whole.spoken_text(row)) is on_the_roster


@pytest.mark.parametrize("on_the_roster", [True, False])
def test_the_preview_reads_a_roster_name_the_way_the_book_does(tmp_path: Path, monkeypatch, on_the_roster: bool) -> None:
    """The preview job itself (the code the preview process runs), with the model replaced: what the model is asked to say."""
    paths, db = _book(tmp_path, on_the_roster=on_the_roster)
    runtime = FakeVieNeuRuntime()
    _voices(runtime, monkeypatch)
    out = tmp_path / "out" / "clip.wav"

    result = _script()["run_job"](_job(paths, _segment_id(db, "c1s1"), "Natasha", "Na-ta-xa", out), {}, lambda _m: None)

    assert result["ok"] and out.is_file()
    text, _kwargs = runtime.calls[0]
    assert "Na-ta-xa" in text, "the reading being tried is still laid over the book's table"
    assert _reads_the_name(text) is on_the_roster


def test_the_real_preview_process_reads_a_roster_name_the_way_the_book_does(tmp_path: Path) -> None:
    """Nothing replaced but the model: HTTP -> a real python running the preview script -> the read-only database -> the name
    rules. The model is a package named `vieneu` put first on the child's import path, which writes down what it is given."""
    paths, _db = _book(tmp_path / "book", on_the_roster=True)
    folder, environment = recording_voice.install(tmp_path / "voice", VOICES)
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path / "book")})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    previews = app.previews
    spawn = previews.launcher

    def launch(command: list[str], child_environment: dict[str, str], cwd: Path):
        path = os.pathsep.join([str(folder), child_environment["PYTHONPATH"]])
        return spawn(command, {**child_environment, **environment, "PYTHONPATH": path}, cwd)

    previews.fake = lambda: False  # the real path: no ABOOK_PREVIEW_FAKE, so the script does not put its own tone in place
    previews.studio = lambda: None  # this python, the code beside the app
    previews.probe = lambda: (8000, 16.0)  # the model is a tone: the card is never touched
    previews.launcher = launch
    server = Server(app, port=0).start()
    try:
        status, data, _ = _post(server, paths, {"surface": "Natasha", "spokenForm": "Na-ta-xa"}, timeout=PROCESS_SECONDS)
        assert status == 200, (data, (previews.root / "preview.log").read_text(encoding="utf-8", errors="replace")[-2000:])
        result = json.loads(data)
        assert result["text"] == LINE
        status, clip, _ = _request(server.port, "GET", result["url"], headers={"X-Ebook-Token": "t"}, timeout=PROCESS_SECONDS)
        assert status == 200 and clip[:4] == b"RIFF" and len(clip) > 1000
    finally:
        app.close()
        server.stop()

    spoken = recording_voice.said(folder)
    assert len(spoken) == 1 and spoken[0]["voice"] == "v_lucien"
    assert "Na-ta-xa" in spoken[0]["text"]
    assert _reads_the_name(spoken[0]["text"]) is True


def test_a_real_pool_worker_reads_a_roster_name_the_way_the_book_does(tmp_path: Path, monkeypatch) -> None:
    """A real spawned synthesis-pool worker: `_worker_init` builds the coordinator over `ReadOnlyVoiceDB`, `_worker_job` voices
    the line. Only the model is replaced (CPU only), by the same recording package, first on the import path the child gets."""
    paths, db = _book(tmp_path / "book", on_the_roster=True)
    folder, environment = recording_voice.install(tmp_path / "voice", VOICES)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    # A spawned worker takes its import path from this process (multiprocessing hands `sys.path` over), not from PYTHONPATH.
    monkeypatch.syspath_prepend(str(folder))
    out = tmp_path / "out" / "c1s1.wav"

    with SynthesisPool(_settings(db), paths.db, workers=1, stall_seconds=PROCESS_SECONDS) as pool:
        results = pool.synthesize_many([{"row": _line(db), "output": str(out), "seed_salt": "primary_0"}])

    assert len(results) == 1 and "error" not in results[0], results
    assert results[0]["stable_id"] == "c1s1" and results[0]["checksum"] and out.is_file() and out.stat().st_size > 1000
    spoken = recording_voice.said(folder)
    assert len(spoken) == 1 and spoken[0]["voice"] == "v_lucien"
    assert _reads_the_name(spoken[0]["text"]) is True
