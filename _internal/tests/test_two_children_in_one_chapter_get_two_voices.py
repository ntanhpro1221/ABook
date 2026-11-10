"""Trẻ con (cả bé trai) dùng preset nữ nguyên bản theo bảng hạng nữ; dùng hết preset trước khi chia sẻ.

Chủ sách 05-11: "trẻ con thì dùng giọng của nữ đi, đừng bóp nữa, bóp đem đến âm thanh quá tệ".
"""
from abook.character_registry import PresetAllocator


def test_a_named_child_and_an_npc_child_get_different_presets():
    allocator = PresetAllocator(narrator_voice="Phạm Tuyên")
    allocator.note_chapters("AEREN", {186})
    allocator.note_chapters("NPC_LOCAL::C00020::CON TRAI", {186})
    first = allocator.choose("male", npc=False, age="child", who="AEREN")
    second = allocator.choose("male", npc=True, age="child", who="NPC_LOCAL::C00020::CON TRAI")
    assert first["name"] != second["name"]
    assert first["gender"] == second["gender"] == "female"


def test_a_boy_reads_in_the_top_female_character_voice():
    boy = PresetAllocator("Phạm Tuyên").choose("male", npc=False, age="child")
    girl = PresetAllocator("Phạm Tuyên").choose("female", npc=False, age="child")
    woman = PresetAllocator("Phạm Tuyên").choose("female", npc=False, age="adult")
    assert boy["name"] == girl["name"] == woman["name"] == "Ngọc Linh"


def test_a_child_of_unknown_gender_reads_in_a_female_voice():
    assert PresetAllocator("Phạm Tuyên").choose("unknown", npc=True, age="child")["gender"] == "female"


def test_only_a_child_changes_the_gender_of_the_preset():
    picked = [PresetAllocator("Phạm Tuyên").choose("male", npc=False, age=age)
              for age in ("teen", "young", "adult", "elderly", "unknown")]
    assert len({p["name"] for p in picked}) == 1
    assert all(p["gender"] == "male" for p in picked)


def test_a_female_narrator_is_never_a_childs_voice():
    allocator = PresetAllocator("Ngọc Linh")
    picked = [allocator.choose("male", npc=False, age="child", who=f"C{i}")["name"] for i in range(4)]
    assert "Ngọc Linh" not in picked


def test_children_in_different_chapters_still_use_unused_presets_first():
    allocator = PresetAllocator("Phạm Tuyên")
    allocator.note_chapters("A", {10})
    allocator.note_chapters("B", {20})
    first = allocator.choose("male", npc=False, age="child", who="A")
    second = allocator.choose("male", npc=True, age="child", who="B")
    assert first["name"] != second["name"]
    assert {first["gender"], second["gender"]} == {"female"}


def test_registry_casts_a_named_boy_and_a_local_boy_to_distinct_female_voices(tmp_path):
    from abook.character_registry import build_registry_and_cast
    from abook.config import build_settings
    from abook.voice_catalog import preset_by_name
    from tests.test_character_casting import _identity_db

    db = _identity_db(tmp_path, [("AEREN", "male"), ("NPC_LOCAL::C00001::CON TRAI", "male")])
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET age='child'")
    build_registry_and_cast(db, build_settings(), lambda _: None)
    with db.connect() as conn:
        voices = [r[0] for r in conn.execute(
            "SELECT v.preset_name FROM segments s JOIN voice_profiles v ON v.id=s.voice_profile_id ORDER BY s.id")]
    assert len(voices) == len(set(voices)) == 2
    assert all(preset_by_name(name)['gender'] == 'female' for name in voices)


def test_registry_keeps_the_male_voice_the_listener_pinned_for_a_boy(tmp_path):
    from abook.character_registry import build_registry_and_cast, voice_profile_spec
    from abook.config import build_settings
    from abook.voice_catalog import preset_by_name
    from tests.test_character_casting import _identity_db

    db = _identity_db(tmp_path, [("AEREN", "male")])
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET age='child'")
    spec = voice_profile_spec(preset_by_name('Thái Sơn'))
    db.upsert_voice_profile(spec)
    db.set_locked_character_voice('AEREN', spec['voice_key'])
    for _ in range(2):
        build_registry_and_cast(db, build_settings(), lambda _: None)
        with db.connect() as conn:
            assert conn.execute("SELECT v.preset_name FROM segments s JOIN voice_profiles v ON v.id=s.voice_profile_id").fetchone()[0] == 'Thái Sơn'
