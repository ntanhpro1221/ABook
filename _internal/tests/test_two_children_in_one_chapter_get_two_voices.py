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
