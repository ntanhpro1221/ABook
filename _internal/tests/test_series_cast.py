"""A real two-project series keeps every narrator and the packaged chapter identities."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from abook.webui import bookfile
from abook.voice_balance import engine_version, voice_key
from tests.test_webui_listen_and_sync import make_project


@pytest.mark.parametrize(("second_narrator", "second_alternate"), [
    ("Đức Trí", "Thanh Bình"), ("Ngọc Linh", "Thanh Bình"), ("Ngọc Linh", "Đức Trí"),
    ("Thanh Bình", "Ngọc Linh")])
def test_series_narrators_use_global_chapters_and_add_every_voice(tmp_path: Path, second_narrator: str,
                                                                second_alternate: str) -> None:
    parts = [make_project(tmp_path / f"p{number}", f"Synthetic · Phần {number}") for number in (1, 2)]
    for number, root in enumerate(parts, 1):
        settings = json.loads((root / "book_settings.json").read_text(encoding="utf-8"))
        settings["voices"]["narrator_voice"] = "Đức Trí" if number == 1 else second_narrator
        (root / "book_settings.json").write_text(json.dumps(settings), encoding="utf-8")
        with sqlite3.connect(root / "project.sqlite3") as connection:
            connection.execute("UPDATE voice_profiles SET preset_name=? WHERE id=1", (settings["voices"]["narrator_voice"],))
            if number == 2 and second_alternate != "Thanh Bình":
                connection.execute("UPDATE voice_profiles SET preset_name=?, voice_key=? WHERE id=2",
                                   (second_alternate, voice_key("vieneu", engine_version("vieneu"), second_alternate)))
                # The existing character still uses the fixture's male voice when the chapter narrator changes.
                connection.execute("INSERT INTO voice_profiles(id,voice_key,preset_name,engine) VALUES (3,?,?, 'vieneu')",
                                   (voice_key("vieneu", engine_version("vieneu"), "Thanh Bình"), "Thanh Bình"))
                connection.execute("UPDATE segments SET voice_profile_id=3, signal_json=? WHERE speaker='LUCIEN'",
                                   (json.dumps({"voice_profile_id": 3}),))
            # Each part has a whole chapter read by another voice; their local chapter ids overlap.
            connection.execute("UPDATE segments SET voice_profile_id=2, signal_json=? WHERE chapter_id=2",
                               (json.dumps({"voice_profile_id": 2}),))
    out = bookfile.pack_series(parts, tmp_path / "series.abook", partial=True)
    with bookfile.BookFile(out) as opened:
        opened.verify()
        cast = json.loads(opened.read("cast.json"))["narrator"]
        chapters = {chapter["id"]: chapter["title"] for chapter in opened.book["chapters"]}

    first, second = bookfile.PART_SPAN, 2 * bookfile.PART_SPAN
    assert (cast["lines"], cast["seconds"]) == (8, 14.0)
    voices = {voice["voice"]: voice for voice in cast["chapterVoices"]}
    shared_alternate = second_alternate == "Thanh Bình"
    reused_main = second_narrator == "Thanh Bình"
    alternate_totals = (4, 7.0) if reused_main else (4, 4.0) if shared_alternate else (2, 2.0)
    assert (voices["Thanh Bình"]["lines"], voices["Thanh Bình"]["seconds"]) == alternate_totals
    alternate_chapters = [first + 2, second + 1] if reused_main else [first + 2, second + 2] if shared_alternate else [first + 2]
    assert voices["Thanh Bình"]["chapters"] == [{"id": key, "title": chapters[key]} for key in alternate_chapters]
    excluded = list(alternate_chapters)
    if reused_main:
        assert (cast["voiceLines"], cast["voiceSeconds"]) == (2, 5.0)
        assert set(voices) == {"Thanh Bình", "Ngọc Linh"}
        assert (voices["Ngọc Linh"]["lines"], voices["Ngọc Linh"]["seconds"]) == (2, 2.0)
        assert voices["Ngọc Linh"]["chapters"] == [{"id": second + 2, "title": chapters[second + 2]}]
        excluded = [first + 2, second + 1, second + 2]
    elif second_narrator == "Đức Trí":
        assert (cast["voiceLines"], cast["voiceSeconds"]) == (4, 10.0)
        assert set(voices) == {"Thanh Bình"}
    else:
        assert (cast["voiceLines"], cast["voiceSeconds"]) == ((2, 5.0) if shared_alternate else (4, 7.0))
        assert set(voices) == {"Thanh Bình", second_narrator}
        assert (voices[second_narrator]["lines"], voices[second_narrator]["seconds"]) == (2, 5.0)
        assert voices[second_narrator]["chapters"] == [{"id": second + 1, "title": chapters[second + 1]}]
        excluded.insert(1, second + 1)
    assert cast["exceptChapters"] == [{"id": key, "title": chapters[key]} for key in excluded]
    assert cast["voiceLines"] + sum(voice["lines"] for voice in voices.values()) == cast["lines"]
    assert cast["voiceSeconds"] + sum(voice["seconds"] for voice in voices.values()) == cast["seconds"]
