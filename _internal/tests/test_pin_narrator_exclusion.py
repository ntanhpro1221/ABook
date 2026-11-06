"""A character's pin never outranks the current narration preset."""
import json

import pytest

from abook import continuation, teller_voice
from abook.character_registry import PresetAllocator, _pinned_profile_id, build_registry_and_cast, reserve_pinned_voices
from abook.listener_overrides import UNKNOWN_PRESET
from abook.voice_catalog import preset_by_name
from abook.io_utils import stable_int
from tests.test_listener_voices import CAST, NARRATOR_VOICE, SETTINGS, VOICES, _apply, _book, _voice
from tests.test_continue_this_book import VOICE_A, VOICE_C, _project, _source_folder, _speak


def _preset(db, name):
    return {str(db.voice_profile_by_key(key)["preset_name"]) for key in _voice(db, name)}


def test_carry_refuses_the_current_narrator_pin_and_casts_the_same_gender(tmp_path):
    folder = _source_folder(tmp_path)
    source = _project(tmp_path / "library/part1", [folder / "001.txt"])
    _speak(source, "001", [("MARCUS", VOICE_A)])
    with source.connect() as conn:
        conn.execute("UPDATE voice_profiles SET preset_name=?", (NARRATOR_VOICE,))
    db = _project(tmp_path / "library/part2", [folder / "002.txt"])
    with db.connect() as conn:
        conn.execute("UPDATE book SET settings_json=?", (json.dumps(SETTINGS),))
    report = continuation.seed(source.path.parent, db.path.parent)
    assert report["voices"] == 0
    assert "MARCUS" not in db.locked_character_voices()
    _speak(db, "002", [("MARCUS", VOICE_C)], status="analyzed")
    build_registry_and_cast(db, SETTINGS, lambda _: None)
    assert NARRATOR_VOICE not in _preset(db, "MARCUS")
    assert {preset_by_name(name)["gender"] for name in _preset(db, "MARCUS")} == {"male"}


def test_existing_conflicting_pin_is_recast_by_the_full_casting_path(tmp_path):
    _paths, db = _book(tmp_path)
    with db.connect() as conn:
        conn.execute("UPDATE segments SET gender=(SELECT gender FROM characters WHERE id=canonical_character_id)")
        conn.execute("UPDATE voice_profiles SET description=?, seed=? WHERE voice_key='narrator'",
                     (VOICES["narrator_description"], stable_int("voice::narrator")))
        conn.execute("UPDATE characters SET locked_voice_key='narrator' WHERE canonical_name='LUCIEN'")
    build_registry_and_cast(db, SETTINGS, lambda _: None)
    assert NARRATOR_VOICE not in _preset(db, "LUCIEN")
    assert {preset_by_name(name)["gender"] for name in _preset(db, "LUCIEN")} == {"male"}


@pytest.mark.parametrize("name", ["LUCIEN", "ANONYMOUS_MALE", "NPC_C1_1"])
def test_existing_pins_are_checked_in_both_reservation_and_acceptance(tmp_path, name):
    _paths, db = _book(tmp_path)
    allocator = PresetAllocator(NARRATOR_VOICE)
    pins = {name: "narrator"}
    assert reserve_pinned_voices(db, pins, allocator, lambda _: None) == 0
    assert _pinned_profile_id(db, pins, name, allocator, True, lambda _: None) is None
    preset = allocator.choose("male", npc=True, who=name)
    assert preset["name"] != NARRATOR_VOICE and preset["gender"] == "male"


def test_listener_override_refuses_a_narrator_preset(tmp_path):
    _paths, db = _book(tmp_path)
    assert _apply(db, "LUCIEN", preset=NARRATOR_VOICE) == {"problem": UNKNOWN_PRESET}
    with pytest.raises(ValueError, match="người kể"):
        db.set_locked_character_voice("LUCIEN", "narrator")


def test_ordinary_pin_is_untouched(tmp_path):
    _paths, db = _book(tmp_path)
    key, = _voice(db, "LUCIEN")
    db.set_locked_character_voice("LUCIEN", key)
    allocator = PresetAllocator(NARRATOR_VOICE)
    assert reserve_pinned_voices(db, {"LUCIEN": key}, allocator, lambda _: None) == 1
    assert _pinned_profile_id(db, {"LUCIEN": key}, "LUCIEN", allocator, False, lambda _: None) == db.voice_profile_by_key(key)["id"]
    assert db.locked_character_voices()["LUCIEN"] == key


def test_narrator_setter_recasts_current_holders_and_silent_pins_atomically(tmp_path):
    _paths, db = _book(tmp_path)
    before = _voice(db, "NATASHA")
    key, = _voice(db, "LUCIEN")
    db.set_locked_character_voice("LUCIEN", key)
    db.set_locked_character_voice("SILENT", key)
    with db.connect() as conn:
        conn.execute("UPDATE characters SET gender='male' WHERE canonical_name='SILENT'")
    picked = str(CAST["LUCIEN"][1]["name"])
    teller_voice._align_narrator(db, SETTINGS, {"preset": picked, "gender": "male", "reading": NARRATOR_VOICE})
    assert db.voice_profile_by_key("narrator")["preset_name"] == picked
    for name in ("LUCIEN", "RHINE"):
        assert picked not in _preset(db, name)
        assert {preset_by_name(p)["gender"] for p in _preset(db, name)} == {"male"}
        assert {str(row["status"]) for row in db.list_segments() if row["speaker"] == name} == {"analyzed"}
    assert _voice(db, "NATASHA") == before
    for name in ("LUCIEN", "SILENT"):
        assert db.voice_profile_by_key(db.locked_character_voices()[name])["preset_name"] != picked
    with db.connect() as conn:
        assert conn.execute("SELECT status FROM chapters").fetchone()[0] == "warning"
