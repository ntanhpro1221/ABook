"""Trẻ con dùng preset theo phái và bảng hạng, dùng hết preset trước khi chia sẻ."""
from abook.character_registry import PresetAllocator


def test_a_named_child_and_an_npc_child_get_different_presets():
    allocator = PresetAllocator(narrator_voice="Phạm Tuyên")
    allocator.note_chapters("AEREN", {186})
    allocator.note_chapters("NPC_LOCAL::C00020::CON TRAI", {186})
    first = allocator.choose("male", npc=False, age="child", who="AEREN")
    second = allocator.choose("male", npc=True, age="child", who="NPC_LOCAL::C00020::CON TRAI")
    assert first["name"] != second["name"]


def test_age_does_not_change_the_ranked_preset():
    picked = [PresetAllocator("Phạm Tuyên").choose("male", npc=False, age=age)
              for age in ("child", "teen", "adult", "elderly")]
    assert len({p["name"] for p in picked}) == 1
    assert all(p["gender"] == "male" for p in picked)


def test_children_in_different_chapters_still_use_unused_presets_first():
    allocator = PresetAllocator("Phạm Tuyên")
    allocator.note_chapters("A", {10})
    allocator.note_chapters("B", {20})
    first = allocator.choose("male", npc=False, age="child", who="A")
    second = allocator.choose("male", npc=True, age="child", who="B")
    assert first["name"] != second["name"]
