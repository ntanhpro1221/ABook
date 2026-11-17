"""cast.json is the book's source of truth: tiers, gender and narrator voices are decided once, at export.

The listener apps display exactly what cast.json records. These tests pin the export rule:
- a speaker with many lines across chapters is a main role even when the registry calls them an NPC;
- an NPC with a couple of lines is never a main role;
- gender comes from the registry, then gendered words in the label, then the assigned voice (never for children);
- narrator voices that differ by chapter are structured entries naming the chapters as the Chapters tab titles them.
All names and lines are synthetic.
"""
from __future__ import annotations

from pathlib import Path

from abook.database import ProjectDB
from abook.models import ProjectPaths
from abook.voice_catalog import GENDER_FEMALE, GENDER_MALE, VIENEU_PRESETS
from abook.webui import store

from test_cast_roles_and_name_order import _book


def _writer(root: Path):
    return ProjectDB(ProjectPaths.build(root).db).connect()


def _preset(gender: str) -> str:
    return next(str(preset["name"]) for preset in VIENEU_PRESETS if preset["gender"] == gender)


def test_many_lines_across_chapters_is_a_main_role_even_for_an_npc() -> None:
    assert store.cast_role("NPC_LOCAL::c00001::cô gái", None, 150, 9, 9, chapters=2) == "characters"
    assert store.cast_role("Npc Cô Gái Áo Xanh", None, 100, 3, 9, chapters=3) == "characters"
    assert store.cast_role("Npc Cô Gái Áo Xanh", None, 150, 1, 9, chapters=1) == "extras", "một chương: vẫn là vai phụ"
    assert store.cast_role("Npc Cô Gái Áo Xanh", None, 99, 9, 9, chapters=9) == "extras"


def test_an_npc_with_one_or_two_lines_is_never_main_and_a_lead_is_never_an_extra() -> None:
    for lines in (1, 2):
        assert store.cast_role("NPC BÁC BẢO VỆ", None, lines, 2, 9, chapters=2) == "extras"
    assert store.cast_role("Soren", None, 563, 1, 1, chapters=9) == "characters"
    assert store.cast_role("Soren", {"importance": "minor"}, 500, 1, 9, chapters=4) == "characters"


def _gendered_book(tmp_path: Path) -> Path:
    lines = [
        (1, "dialogue", "Soren", "“Đi thôi.”", 0),
        (1, "dialogue", "Người Phụ Nữ Áo Đỏ", "“Đợi đã.”", 0),
        (1, "dialogue", "Velia", "“Ừ.”", 1),
        (1, "dialogue", "Bé Tí", "“Con đây.”", 0),
        (2, "dialogue", "Soren", "“Chào.”", 0),
        (2, "dialogue", "Velia", "“Chào cậu.”", 0),
        (2, "dialogue", "NPC Nhóm Trẻ Thả Diều", "“Lên rồi!”", 0),
        (2, "dialogue", "Ông Lão Quét Sân", "“Hừm.”", 0),
        (2, "dialogue", "Dân Làng", "“Hoan hô!”", 0),
    ]
    people = {
        "SOREN": ("Soren", "male", "teen", "main"),
        "NGƯỜI PHỤ NỮ ÁO ĐỎ": ("Người Phụ Nữ Áo Đỏ", "unknown", "adult", "minor"),
        "VELIA": ("Velia", "unknown", "teen", "main"),
        "BÉ TÍ": ("Bé Tí", "unknown", "child", "minor"),
        "NPC NHÓM TRẺ THẢ DIỀU": ("NPC Nhóm Trẻ Thả Diều", "unknown", "child", "minor"),
    }
    root = _book(tmp_path, lines, people)
    with _writer(root) as connection:
        for key, preset in ((1, _preset(GENDER_FEMALE)), (2, _preset(GENDER_MALE))):
            connection.execute("INSERT INTO voice_profiles(id, voice_key, engine, preset_name, seed, created_at, updated_at)"
                               " VALUES(?, ?, 'vieneu', ?, 1, 0, 0)", (key, f"vieneu@test/{preset}", preset))
        connection.execute("UPDATE segments SET voice_profile_id = 1 WHERE speaker IN ('Velia', 'Bé Tí')")
        connection.execute("UPDATE segments SET voice_profile_id = 2 WHERE speaker = 'Dân Làng'")
        connection.execute("UPDATE segments SET voice_profile_id = 2 WHERE speaker = 'Soren'")
        connection.commit()
    return root


def test_gender_comes_from_the_registry_then_the_label_then_the_voice_but_never_a_child_voice(tmp_path: Path) -> None:
    view = store.cast(_gendered_book(tmp_path))
    gender = {person["name"]: person["gender"] for person in view["characters"] + view["extras"]}
    assert gender["Soren"] == "Nam", "sổ nhân vật"
    assert gender["Người Phụ Nữ Áo Đỏ"] == "Nữ", "chữ chỉ giới trong nhãn"
    assert gender["Velia"] == "Nữ", "giọng phân vai đã gán"
    assert gender["Bé Tí"] == "", "trẻ em đọc giọng nữ theo luật, không phải vì là nữ"


def test_an_empty_gender_says_why_and_is_never_invented(tmp_path: Path) -> None:
    """Groups and children keep an empty gender; `genderNote` tells the apps which word to show (vi.json "Nhóm" / "Trẻ em")."""
    view = store.cast(_gendered_book(tmp_path))
    people = {person["name"]: person for person in view["characters"] + view["extras"]}
    assert (people["NPC Nhóm Trẻ Thả Diều"]["gender"], people["NPC Nhóm Trẻ Thả Diều"]["genderNote"]) == ("", "group")
    assert (people["Bé Tí"]["gender"], people["Bé Tí"]["genderNote"]) == ("", "child")
    assert people["Ông Lão Quét Sân"]["gender"] == "Nam" and "genderNote" not in people["Ông Lão Quét Sân"]
    assert "genderNote" not in people["Soren"]
    assert (people["Dân Làng"]["gender"], people["Dân Làng"]["genderNote"]) == ("", "group"), "giọng nam cấp cho nhóm không làm nhóm thành nam"


def test_group_labels() -> None:
    for label in ("Nhóm trẻ ném tuyết", "NPC Đám đông", "NPC_LOCAL::c00001::bọn lính gác", "Mọi người", "Các cô gái", "Dân làng"):
        assert store.cast_gender_note(label, None, "") == "group", label
    for label in ("Đội Trưởng", "Đoàn Dự", "Nhómxyz", "Cảnh Sát", "NPC Người Lạ"):
        assert store.cast_gender_note(label, None, "") == "unknown", label
    assert store.cast_gender_note("Nhóm trẻ", None, "male") == ""


def test_narrator_chapter_voices_are_structured_and_name_the_chapters_as_titled() -> None:
    profiles = {
        1: {"id": 1, "voice_key": "narrator", "preset_name": "Giọng Chính"},
        2: {"id": 2, "voice_key": "vieneu@test/Giọng Hai", "preset_name": "Giọng Hai"},
    }
    reads = [
        {"chapter_id": 1, "voice_profile_id": 1, "lines": 10, "seconds": 20.0},
        {"chapter_id": 2, "voice_profile_id": 2, "lines": 6, "seconds": 12.04},
        {"chapter_id": 3, "voice_profile_id": 1, "lines": 4, "seconds": 8.0},
        {"chapter_id": 3, "voice_profile_id": 2, "lines": 1, "seconds": 1.0},
        {"chapter_id": 4, "voice_profile_id": 2, "lines": 5, "seconds": 9.0},
    ]
    titles = {1: "Mở đầu", 2: "Chương 1", 3: "Chương 2", 4: "Chương 3"}
    voices, except_chapters = store._narrator_chapter_voices(reads, profiles, titles)
    assert voices == [{"voice": "Giọng Hai", "profile": {"key": "vieneu@test/Giọng Hai", "preset": "Giọng Hai"},
                       "chapters": [{"id": 2, "title": "Chương 1"}, {"id": 3, "title": "Chương 2"}, {"id": 4, "title": "Chương 3"}],
                       "lines": 12, "seconds": 22.0}]
    assert except_chapters == [{"id": 2, "title": "Chương 1"}, {"id": 4, "title": "Chương 3"}], \
        "chương 2 giọng chính vẫn đọc vài câu: không thuộc 'trừ'"


def test_the_narrator_entry_counts_the_main_voice_on_its_own(tmp_path: Path) -> None:
    lines = [
        (1, "narration", "NARRATOR", "Trời mưa.", 0),
        (1, "narration", "NARRATOR", "Gió lớn.", 0),
        (1, "dialogue", "Soren", "“Đi thôi.”", 0),
        (2, "narration", "NARRATOR", "Sáng rồi.", 0),
        (2, "dialogue", "Soren", "“Chào.”", 0),
    ]
    root = _book(tmp_path, lines, {"SOREN": ("Soren", "male", "teen", "main")})
    with _writer(root) as connection:
        connection.execute("INSERT INTO voice_profiles(id, voice_key, engine, preset_name, seed, created_at, updated_at)"
                           " VALUES(1, 'narrator', 'vieneu', ?, 1, 0, 0)", (_preset(GENDER_MALE),))
        connection.execute("INSERT INTO voice_profiles(id, voice_key, engine, preset_name, seed, created_at, updated_at)"
                           " VALUES(2, 'vieneu@test/hai', 'vieneu', ?, 1, 0, 0)", (_preset(GENDER_FEMALE),))
        chapter_two = connection.execute("SELECT id FROM chapters WHERE chapter_index = 2").fetchone()[0]
        connection.execute("UPDATE segments SET voice_profile_id = 1 WHERE speaker = 'NARRATOR'")
        connection.execute("UPDATE segments SET voice_profile_id = 2 WHERE speaker = 'NARRATOR' AND chapter_id = ?", (chapter_two,))
    with store.connect(root) as connection:
        title = store.chapter_names(connection)[chapter_two]["name"]
    narrator = store.cast(root)["narrator"]
    assert narrator["lines"] == 3 and narrator["voiceLines"] == 2
    assert [entry["voice"] for entry in narrator["chapterVoices"]] == [_preset(GENDER_FEMALE)]
    assert narrator["chapterVoices"][0]["chapters"] == [{"id": chapter_two, "title": title}]
    assert narrator["exceptChapters"] == [{"id": chapter_two, "title": title}]
    assert all(isinstance(entry, dict) for entry in narrator["chapterVoices"]), "không chuỗi định dạng sẵn"
