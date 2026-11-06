"""Preset giữ mọi chủ giọng để tránh trùng người cùng chương."""
from abook.character_registry import PresetAllocator
from abook.voice_catalog import VIENEU_PRESETS


def test_a_preset_remembers_every_holder():
    a = PresetAllocator("Phạm Tuyên")
    a.reserve("Thanh Bình", who="VIKTOR")
    a.reserve("Thanh Bình", who="KANG")
    assert a.holders["Thanh Bình"] == {"VIKTOR", "KANG"}
    assert a.usage["Thanh Bình"] == 2


def test_all_holders_count_when_choosing_a_shared_preset():
    a = PresetAllocator("Phạm Tuyên")
    a.not_for_characters = frozenset(p["name"] for p in VIENEU_PRESETS
                                    if p["name"] not in {"Xuân Vĩnh", "Thanh Bình"})
    a.reserve("Xuân Vĩnh", who="VIKTOR")
    a.reserve("Xuân Vĩnh", who="KANG")
    a.reserve("Thanh Bình", who="JAY")
    a.reserve("Thanh Bình", who="OTHER")
    a.note_chapters("KANG", {71})
    a.note_chapters("NEW", {71})
    assert a.choose("male", npc=False, who="NEW")["name"] == "Thanh Bình"
