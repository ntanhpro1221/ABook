"""One real server output of the Characters tab, loaded by all three clients.

`fixtures/cast_contract/cast.json` is what `GET /api/books/<id>/cast` (avatars.cast) sends for a small synthetic book: a main
narrator voice, a second narrator voice reading one whole chapter, a man, a person of unknown gender who got a female voice by
tie-break, a child and a group. This test regenerates it from the server code and fails when the file is stale, so the web
(vitest `castContract.test.ts`), Qt (`tst_cast_contract.qml`) and Android (`CastContractTest.kt`) tests always read today's
server shape. `expected.json` is the text every client must show for it (rows of "Người kể chuyện", gender cells).

Refresh after a deliberate change: ABOOK_TEST_REGEN_CAST_CONTRACT=1 pytest tests/test_cast_contract_fixture.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from abook import avatars
from abook.database import ProjectDB
from abook.models import ProjectPaths
from abook.voice_catalog import GENDER_FEMALE, GENDER_MALE, VIENEU_PRESETS

from test_cast_roles_and_name_order import _book

FIXTURE = Path(__file__).parent / "fixtures" / "cast_contract"


def _preset(gender: str, skip: int = 0) -> str:
    return [str(preset["name"]) for preset in VIENEU_PRESETS if preset["gender"] == gender][skip]


def contract_book(tmp_path: Path) -> Path:
    lines = [
        (1, "narration", "NARRATOR", "Trời mưa.", 0),
        (1, "narration", "NARRATOR", "Gió lớn.", 0),
        (1, "narration", "NARRATOR", "Đèn tắt.", 0),
        (1, "dialogue", "Soren", "“Đi thôi.”", 0),
        (1, "dialogue", "Velia", "“Ừ.”", 0),
        (1, "dialogue", "Bé Tí", "“Con đây.”", 0),
        (2, "narration", "NARRATOR", "Sáng rồi.", 0),
        (2, "narration", "NARRATOR", "Chim hót.", 0),
        (2, "dialogue", "Soren", "“Chào.”", 0),
        (2, "dialogue", "Velia", "“Chào cậu.”", 0),
        (2, "dialogue", "Dân Làng", "“Hoan hô!”", 0),
    ]
    people = {
        "SOREN": ("Soren", "male", "teen", "main"),
        "VELIA": ("Velia", "unknown", "teen", "main"),
        "BÉ TÍ": ("Bé Tí", "unknown", "child", "minor"),
    }
    root = _book(tmp_path, lines, people)
    with ProjectDB(ProjectPaths.build(root).db).connect() as connection:
        profiles = [(1, "narrator", _preset(GENDER_MALE)), (2, "vieneu@test/narrator-2", _preset(GENDER_FEMALE)),
                    (3, "vieneu@test/soren", _preset(GENDER_MALE, 1)), (4, "vieneu@test/velia", _preset(GENDER_FEMALE, 1))]
        for key, voice_key, preset in profiles:
            connection.execute("INSERT INTO voice_profiles(id, voice_key, engine, preset_name, seed, created_at, updated_at)"
                               " VALUES(?, ?, 'vieneu', ?, 1, 0, 0)", (key, voice_key, preset))
        chapter_two = connection.execute("SELECT id FROM chapters WHERE chapter_index = 2").fetchone()[0]
        connection.execute("UPDATE segments SET wav_duration = 1500")
        connection.execute("UPDATE segments SET voice_profile_id = 1 WHERE speaker = 'NARRATOR'")
        connection.execute("UPDATE segments SET voice_profile_id = 2 WHERE speaker = 'NARRATOR' AND chapter_id = ?", (chapter_two,))
        connection.execute("UPDATE segments SET voice_profile_id = 3 WHERE speaker IN ('Soren', 'Dân Làng')")
        connection.execute("UPDATE segments SET voice_profile_id = 4 WHERE speaker IN ('Velia', 'Bé Tí')")
        connection.commit()
    return root


def server_cast(tmp_path: Path) -> dict:
    return json.loads(json.dumps(avatars.cast(contract_book(tmp_path)), ensure_ascii=False))


def test_the_shared_cast_fixture_is_todays_server_output(tmp_path: Path) -> None:
    cast = server_cast(tmp_path)
    target = FIXTURE / "cast.json"
    text = json.dumps(cast, ensure_ascii=False, indent=1) + "\n"
    if os.environ.get("ABOOK_TEST_REGEN_CAST_CONTRACT"):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    assert json.loads(target.read_text(encoding="utf-8")) == cast, "cast.json chung của ba nền cũ so với máy chủ: chạy lại với ABOOK_TEST_REGEN_CAST_CONTRACT=1"


def test_the_fixture_covers_what_the_clients_must_show() -> None:
    cast = json.loads((FIXTURE / "cast.json").read_text(encoding="utf-8"))
    expected = json.loads((FIXTURE / "expected.json").read_text(encoding="utf-8"))
    narrator = cast["narrator"]
    assert len(narrator["chapterVoices"]) == 1 and narrator["exceptChapters"], "có hàng người kể theo chương và phạm vi 'trừ'"
    assert narrator["voiceLines"] + sum(entry["lines"] for entry in narrator["chapterVoices"]) == narrator["lines"]
    notes = {person.get("genderNote") for person in cast["characters"] + cast["extras"]}
    assert {"unknown", "child", "group"} <= notes, "đủ ba lý do ô giới trống"
    shown = {person["displayName"] for person in cast["characters"] + cast["extras"]}
    assert set(expected["genders"]) == shown
    assert len(expected["narratorRows"]) == 1 + len(narrator["chapterVoices"])
