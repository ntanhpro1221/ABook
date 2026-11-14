"""Tự phân vai chỉ lấy giọng ĐẠT; hết giọng đạt thì dùng chung giọng đạt giữa những người không bao giờ gặp nhau.

Chủ sách 15-11 ("Nơi mà hai ta đã gọi điện"): "kể cả không rõ thật mà lại dùng adam bựa? đó không phải giọng tốt, thiếu
giọng à?". Sách ấy có Adam bựa, Hải Đăng, Quốc Tuấn, Thanh Bình, Thiện Minh (chưa ai xếp hạng) và Ngọc Huyền, Trúc Ly
(NEVER_AUTO) ở vai tự phân.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from abook import voice_catalog
from abook.character_registry import PresetAllocator, build_registry_and_cast, speaking_cooccurrence
from abook.config import build_settings
from abook.database import ProjectDB
from abook.voice_catalog import NEVER_AUTO, VIENEU_PRESETS, auto_rank, casting_presets, narrator_presets

NARRATOR = "Đức Trí"


def _good(gender: str, role: str = "character") -> set[str]:
    return {str(p["name"]) for p in VIENEU_PRESETS if p["gender"] == gender and auto_rank(str(p["name"]), gender, role) is not None}


# --- luật: chỉ giọng đạt ----------------------------------------------------------------------------------------------


def test_the_automatic_pools_hold_only_good_voices() -> None:
    for gender in ("male", "female"):
        cast = {str(p["name"]) for p in casting_presets(gender, automatic=True)}
        told = {str(p["name"]) for p in narrator_presets(gender, automatic=True)}
        assert cast and cast <= _good(gender)
        assert told and told <= _good(gender, "narrator")
        assert not (cast | told) & NEVER_AUTO
    for name in ("Adam bựa", "Hải Đăng", "Quốc Tuấn", "Thanh Bình", "Thiện Minh", "Ngọc Huyền", "Trúc Ly", "Ngọc Trân"):
        gender = voice_catalog.preset_by_name(name)["gender"]
        assert auto_rank(name, gender) is None
        assert auto_rank(name, gender, "narrator") is None


def test_a_listener_still_picks_any_voice_by_hand() -> None:
    by_hand = {str(p["name"]) for g in ("male", "female") for p in casting_presets(g, automatic=False)}
    assert {"Adam bựa", "Hải Đăng", "Quốc Tuấn", "Ngọc Huyền", "Trúc Ly"} <= by_hand


@pytest.mark.parametrize("gender", ["male", "female", "unknown"])
@pytest.mark.parametrize("age", ["adult", "child", "unknown"])
def test_forty_characters_never_get_a_bad_voice(gender: str, age: str) -> None:
    allocator = PresetAllocator(NARRATOR)
    good = _good("male") | _good("female")
    for index in range(40):
        name = str(allocator.choose(gender, npc=index % 2 == 0, age=age, who=f"P{index}")["name"])
        assert name in good and name != NARRATOR, (index, name)
        if age == "child":
            assert name in _good("female")
        elif gender in ("male", "female"):
            assert name in _good(gender)


def test_an_unknown_gender_is_not_a_male_default() -> None:
    allocator = PresetAllocator(NARRATOR)
    genders = {voice_catalog.preset_by_name(str(allocator.choose("unknown", npc=False, who=f"Người {i}")["name"]))["gender"]
               for i in range(12)}
    assert genders == {"male", "female"}


def test_machine_approved_names_are_checked(tmp_path: Path) -> None:
    import json
    data = json.loads(voice_catalog.VOICE_RANK_PATH.read_text(encoding="utf-8"))
    data["machine_approved"] = {"character": {"male": ["Adam bựa"], "female": []}}
    path = tmp_path / "rank.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert voice_catalog.load_machine_approved(path)["character"]["male"] == {"Adam bựa"}
    data["machine_approved"] = {"character": {"male": ["Đức Trí"], "female": []}}
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="owner's verdict"):
        voice_catalog.load_machine_approved(path)
    data["machine_approved"] = {"character": {"female": ["Ngọc Huyền"], "male": []}}
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="owner's verdict"):
        voice_catalog.load_machine_approved(path)


def test_a_machine_approved_voice_is_cast_after_every_owner_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(voice_catalog, "MACHINE_APPROVED", {"character": {"male": frozenset({"Hải Đăng"}), "female": frozenset()},
                                                           "narrator": {"male": frozenset(), "female": frozenset()}})
    allocator = PresetAllocator(NARRATOR)
    picks = [str(allocator.choose("male", npc=False, who=f"P{i}")["name"]) for i in range(6)]
    assert picks[-1] == "Hải Đăng"
    assert "Hải Đăng" not in {str(p["name"]) for p in narrator_presets("male", automatic=True)}


# --- dùng chung giọng đạt ----------------------------------------------------------------------------------------------


def _full_male_pool(allocator: PresetAllocator) -> dict[str, str]:
    """Năm vai chính nam, mỗi người một giọng đạt (người kể Đức Trí giữ giọng thứ sáu)."""
    held = {}
    for index in range(len(_good("male")) - 1):
        who = f"MAIN{index}"
        held[who] = str(allocator.choose("male", npc=False, who=who)["name"])
    assert len(set(held.values())) == len(held)
    return held


def test_a_minor_role_shares_with_the_one_main_role_it_never_meets() -> None:
    allocator = PresetAllocator(NARRATOR)
    for index in range(5):
        allocator.note_chapters(f"MAIN{index}", {1, 2, 3} if index else {9})
    allocator.note_chapters("MINOR", {2})
    held = _full_male_pool(allocator)
    assert str(allocator.choose("male", npc=True, who="MINOR")["name"]) == held["MAIN0"]


def test_with_nobody_free_the_holder_farthest_away_in_the_book_wins() -> None:
    allocator = PresetAllocator(NARRATOR)
    for index, chapter in enumerate((10, 20, 30, 40, 50)):
        allocator.note_chapters(f"MAIN{index}", {chapter})
    allocator.note_chapters("MINOR", {12})
    held = _full_male_pool(allocator)
    assert str(allocator.choose("male", npc=True, who="MINOR")["name"]) == held["MAIN4"]


def test_a_dialogue_partner_is_avoided_before_a_chapter_mate() -> None:
    allocator = PresetAllocator(NARRATOR)
    for index in range(5):
        allocator.note_chapters(f"MAIN{index}", {1})
        allocator.note_scenes(f"MAIN{index}", {(1, 0): 5})
    allocator.note_chapters("MINOR", {1})
    allocator.note_scenes("MINOR", {(1, 0): 1})
    for index in range(4):
        allocator.note_partners(f"MAIN{index}", {"MINOR"})
    allocator.note_partners("MINOR", {f"MAIN{index}" for index in range(4)})
    held = _full_male_pool(allocator)
    assert str(allocator.choose("male", npc=True, who="MINOR")["name"]) == held["MAIN4"]


def test_a_scene_mate_is_avoided_before_a_chapter_mate() -> None:
    allocator = PresetAllocator(NARRATOR)
    for index in range(5):
        allocator.note_chapters(f"MAIN{index}", {1})
        allocator.note_scenes(f"MAIN{index}", {(1, 0 if index else 1): 3})
    allocator.note_chapters("MINOR", {1})
    allocator.note_scenes("MINOR", {(1, 0): 1})
    held = _full_male_pool(allocator)
    assert str(allocator.choose("male", npc=True, who="MINOR")["name"]) == held["MAIN0"]


def test_casting_is_deterministic_whatever_order_the_notes_come_in() -> None:
    def run(order: list[int]) -> list[str]:
        allocator = PresetAllocator(NARRATOR)
        for index in order:
            allocator.note_chapters(f"P{index}", {index % 7, index % 3 + 10})
            allocator.note_scenes(f"P{index}", {(index % 7, 0): index + 1})
            allocator.note_partners(f"P{index}", {f"P{(index + 1) % 20}"})
        return [str(allocator.choose("unknown" if i % 5 == 0 else "male", npc=False, who=f"P{i}")["name"]) for i in range(20)]
    assert run(list(range(20))) == run(list(reversed(range(20))))


# --- ai gặp ai ----------------------------------------------------------------------------------------------------------


def _row(chapter: int, seq: int, speaker: str, scene_break: int = 0) -> dict[str, object]:
    return {"chapter_id": chapter, "seq": seq, "speaker": speaker, "scene_break": scene_break}


class _Row(dict):
    def keys(self):  # sqlite3.Row-like
        return list(super().keys())


def test_cooccurrence_counts_scenes_and_dialogue_partners() -> None:
    rows = [_Row(r) for r in [
        _row(1, 0, "NARRATOR"), _row(1, 1, "A"), _row(1, 2, "B"), _row(1, 3, "NARRATOR", 1),
        _row(1, 4, "C"), _row(1, 5, "NARRATOR"), _row(1, 6, "NARRATOR"), _row(1, 7, "NARRATOR"), _row(1, 8, "NARRATOR"),
        _row(1, 9, "A"), _row(2, 0, "B"), _row(2, 1, "C"),
    ]]
    scenes, partners = speaking_cooccurrence(rows, lambda row: None if row["speaker"] == "NARRATOR" else str(row["speaker"]))
    assert scenes["A"] == {(1, 0): 1, (1, 1): 1}
    assert scenes["C"] == {(1, 1): 1, (2, 0): 1}
    # A-B kề nhau; B (cảnh 0) và C (cảnh 1) cách dấu ngăn cảnh; C và A cách 5 đoạn; B-C ở chương 2 kề nhau.
    assert partners == {"A": {"B"}, "B": {"A", "C"}, "C": {"B"}}


# --- cả cuốn ------------------------------------------------------------------------------------------------------------


def _book(tmp_path: Path, chapters: list[list[tuple[str, str]]]) -> ProjectDB:
    db = ProjectDB(tmp_path / "project.sqlite3")
    db.initialize_book(title="Book", project_root=tmp_path, settings={}, settings_hash="s", input_manifest_hash="m")
    ids = db.ensure_chapters([
        {"chapter_index": index + 1, "title": str(index + 1), "input_path": tmp_path / f"{index}.txt", "input_sha256": f"x{index}",
         "input_size": 1, "output_mp3": tmp_path / f"{index}.mp3"}
        for index in range(len(chapters))
    ])
    for chapter_id, lines in zip(ids, chapters):
        db.replace_chapter_segments(chapter_id, [
            {"stable_id": f"c{chapter_id}s{seq}", "seq": seq, "text": f"Câu {seq}.", "text_sha256": f"t{chapter_id}.{seq}",
             "kind_hint": "narration" if speaker == "NARRATOR" else "dialogue",
             "kind": "narration" if speaker == "NARRATOR" else "dialogue",
             "speaker": speaker, "gender": gender, "confidence": 0.95, "status": "analyzed"}
            for seq, (speaker, gender) in enumerate(lines)
        ])
    return db


def test_a_book_with_more_men_than_good_voices_shares_and_never_reaches_down(tmp_path: Path) -> None:
    chapters = []
    for chapter in range(12):
        lines = [("NARRATOR", "unknown")]
        # Hai vai chính nam nói ở mọi chương; mỗi chương thêm một vai nam phụ chỉ ở chương ấy.
        for _ in range(3):
            lines += [("Kenji", "male"), ("Taro", "male"), (f"Khách {chapter}", "male"), ("NARRATOR", "unknown")]
        lines += [("Người phụ nữ bí ẩn", "unknown"), ("UNKNOWN", "female")]
        chapters.append(lines)
    db = _book(tmp_path, chapters)
    settings = build_settings("balanced")
    settings["voices"]["narrator_voice"] = NARRATOR
    build_registry_and_cast(db, settings, lambda _message: None)
    with db.connect() as conn:
        cast = {str(r["canonical_name"]): str(r["preset_name"]) for r in conn.execute(
            "SELECT DISTINCT c.canonical_name, v.preset_name FROM segments s JOIN characters c ON c.id=s.canonical_character_id "
            "JOIN voice_profiles v ON v.id=s.voice_profile_id WHERE c.canonical_name<>'NARRATOR'")}
    good = _good("male") | _good("female")
    assert set(cast.values()) <= good, cast
    assert NARRATOR not in cast.values()
    mains = {cast[k] for k in cast if k.casefold() in {"kenji", "taro"}}
    assert len(mains) == 2
    # Không vai phụ nào chung giọng với hai vai chính (họ có mặt ở mọi chương, khách thì không gặp nhau).
    guests = [k for k in cast if k.casefold().startswith("khách")]
    assert len(guests) == 12
    assert not {cast[k] for k in guests} & mains
