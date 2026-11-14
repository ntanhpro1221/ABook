"""Dàn nhân vật xếp đúng Vai chính / Vai phụ, tra sổ theo khoá chuẩn, và một người viết đảo họ-tên không thành hai người.

castfix 15-11: sổ nhân vật khoá chữ hoa ("FUKAMACHI") còn câu giữ cách viết hiển thị ("Fukamachi") - tra thô làm mọi nhân vật
chính rơi xuống Vai phụ, mất giới tính và tuổi, còn nhãn viết hoa ("NPC MẸ ...") thành Vai chính. Cùng sách: chị gái của nữ
chính lúc là "HAJIKANO AYA" (giọng nữ), lúc "Aya Hajikano" (giới chưa rõ -> giọng nam). Dữ liệu dưới đây tự viết.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from abook.character_registry import (
    PresetAllocator,
    canonical_speaker_names,
    gender_from_name,
    merge_reordered_names,
    resolve_gender,
)
from abook.config import build_settings, settings_hash
from abook.database import ProjectDB
from abook.io_utils import sha256_file
from abook.models import ProjectPaths
from abook.voice_catalog import GENDER_FEMALE, GENDER_MALE, VIENEU_PRESETS
from abook.webui import casting_review, store

# (chương, loại, người nói, chữ, ngăn cảnh sau câu này)
LINES = [
    (1, "dialogue", "Haru", "“Đi thôi.”", 0),
    (1, "dialogue", "Mio", "“Ừ.”", 0),
    (1, "dialogue", "NPC BÁC BẢO VỆ", "“Đóng cửa rồi.”", 1),
    (1, "dialogue", "Haru", "“Mai lại đến.”", 0),
    (1, "dialogue", "NPC BÁC BẢO VỆ", "“Ừ, mai.”", 0),
    (2, "dialogue", "Haru", "“Chào.”", 0),
    (2, "dialogue", "Kenta", "“Chào cậu.”", 0),
    (2, "dialogue", "Kenta", "“Lâu rồi nhỉ.”", 0),
    (2, "dialogue", "Kenta", "“Ngồi đi.”", 0),
    (2, "dialogue", "Kenta", "“Uống gì?”", 0),
    (2, "dialogue", "NPC BÁC BẢO VỆ", "“Lại cậu à.”", 0),
    (2, "dialogue", "Mio", "“Tớ đây.”", 0),
]
PEOPLE = {
    "HARU": ("Haru", "male", "teen", "main"),
    "MIO": ("Mio", "female", "teen", "main"),
    "KENTA": ("Kenta", "male", "adult", "main"),
    "NPC BÁC BẢO VỆ": ("NPC BÁC BẢO VỆ", "male", "elderly", "minor"),
}


def _book(tmp_path: Path) -> Path:
    paths = ProjectPaths.build(tmp_path / "project")
    settings = build_settings()
    db = ProjectDB(paths.db)
    db.initialize_book(title="T", project_root=paths.root, settings=settings, settings_hash=settings_hash(settings),
                       input_manifest_hash="manifest")
    chapter_ids = {}
    for number in (1, 2):
        source = paths.root / "sources" / f"00{number}.txt"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("\n".join(text for chapter, _k, _s, text, _b in LINES if chapter == number), encoding="utf-8")
        chapter_ids[number] = db.ensure_chapters([{
            "chapter_index": number, "title": f"00{number}", "input_path": source, "input_sha256": sha256_file(source),
            "input_size": source.stat().st_size, "output_mp3": paths.chapters / f"00{number}.mp3",
        }])[0]
        db.replace_chapter_segments(chapter_ids[number], [
            {"stable_id": f"c{number}s{seq}", "seq": seq, "text": text, "text_sha256": f"sha-{number}-{seq}", "kind_hint": kind}
            for seq, (_chapter, kind, _speaker, text, _brk) in enumerate(row for row in LINES if row[0] == number)
        ])
    with db.connect() as conn:
        for key, (display, gender, age, importance) in PEOPLE.items():
            conn.execute("INSERT INTO characters(canonical_name,display_name,gender,age,personality,importance,"
                         "mention_count,confidence,locked,created_at,updated_at) VALUES(?,?,?,?,'',?,1,1,0,0,0)",
                         (key, display, gender, age, importance))
        for number in (1, 2):
            for seq, (_chapter, kind, speaker, _text, brk) in enumerate(row for row in LINES if row[0] == number):
                conn.execute("UPDATE segments SET kind=?, speaker=?, scene_break=?, status='verified' WHERE stable_id=?",
                             (kind, speaker, brk, f"c{number}s{seq}"))
    return paths.root


def test_people_are_looked_up_by_their_normalised_key_and_keep_gender_and_age(tmp_path: Path) -> None:
    root = _book(tmp_path)
    view = store.cast(root)
    people = {person["name"]: person for person in view["characters"] + view["extras"]}
    assert people["Haru"]["gender"] and people["Haru"]["age"], "sổ khoá HARU, câu ghi Haru: vẫn là một người"
    assert people["Kenta"]["gender"] and people["Mio"]["gender"]
    assert store.original_name(root, "Haru") == "Haru"


def test_main_cast_is_who_speaks_in_more_than_one_scene_and_npcs_are_always_extras(tmp_path: Path) -> None:
    view = store.cast(_book(tmp_path))
    main = [person["name"] for person in view["characters"]]
    extras = [person["name"] for person in view["extras"]]
    assert main == ["Haru", "Mio"], "Haru, Mio nói ở ba cảnh, hai cảnh"
    assert "Kenta" in extras, "nhiều câu nhất mà chỉ một cảnh: vai phụ"
    assert "NPC BÁC BẢO VỆ" in extras, "NPC nói ở ba cảnh vẫn là vai phụ"


def test_role_rule_without_scene_breaks_falls_back_to_lines() -> None:
    assert store.cast_role("Haru", None, 3, 1, 1) == "characters"
    assert store.cast_role("Haru", None, 2, 1, 1) == "extras"
    assert store.cast_role("NPC_LOCAL::c00001::cô gái", None, 50, 9, 9) == "extras"
    assert store.cast_role("Npc Mẹ Haru", None, 50, 9, 9) == "extras"


def test_casting_review_labels_use_the_book_display_name(tmp_path: Path) -> None:
    root = _book(tmp_path)
    with store.connect(root) as connection:
        display = casting_review.display_names(connection)
    assert casting_review.label("haru", display) == "Haru"


def test_reordered_family_and_given_name_is_one_person() -> None:
    labels = Counter({"HAJIKANO AYA": 103, "Aya Hajikano": 40, "Yui Hajikano": 344, "Yoshie Hajikano": 27, "Hajikano": 5})
    mapping = canonical_speaker_names(labels, "")
    assert mapping["Aya Hajikano"] == mapping["HAJIKANO AYA"] == "HAJIKANO AYA", "đích là nhãn nhiều câu hơn"
    assert mapping["Yui Hajikano"] == "Yui Hajikano" and mapping["Yoshie Hajikano"] == "Yoshie Hajikano"
    assert mapping["Hajikano"] == "Hajikano", "họ cả nhà dùng chung: không đoán"


def test_reorder_merge_needs_the_same_words() -> None:
    representatives = {"kim minjun": "KIM MINJUN", "minjun kim": "Minjun Kim", "kim minji": "KIM MINJI"}
    merged = merge_reordered_names(representatives, Counter({"KIM MINJUN": 2, "Minjun Kim": 9, "KIM MINJI": 4}))
    assert merged == {"kim minjun": "Minjun Kim"}


def test_lone_given_name_joins_the_only_full_name_carrying_it() -> None:
    mapping = canonical_speaker_names(Counter({"Aya": 3, "Aya Hajikano": 40, "Yui Hajikano": 20}), "")
    assert mapping["Aya"] == "Aya Hajikano"


def test_gender_comes_from_the_label_when_votes_and_text_are_silent() -> None:
    assert gender_from_name(["Người Phụ Nữ Gọi Điện Thoại"]) == "female"
    assert gender_from_name(["Nam Sinh Tóc Húi Cua"]) == "male"
    assert gender_from_name(["Người Đọc Kết Quả Bầu Chọn"]) is None
    assert gender_from_name(["Anh và chị"]) is None, "hai giới: không đoán"
    rows = [{"speaker": "Người Phụ Nữ Gọi Điện Thoại", "gender": "unknown", "text": "“Tôi có một đề nghị.”"}]
    assert resolve_gender(rows, rows) == ("female", "name")


def test_unknown_gender_is_not_a_male_default() -> None:
    picks = Counter()
    for index in range(20):
        allocator = PresetAllocator("Đức Trí")
        picks[allocator.choose("unknown", npc=False, who=f"NGƯỜI {index}")["gender"]] += 1
    assert picks[GENDER_FEMALE] and picks[GENDER_MALE], picks


def test_unknown_gender_takes_the_gender_with_a_free_voice() -> None:
    allocator = PresetAllocator("Đức Trí")
    for preset in VIENEU_PRESETS:
        if preset["gender"] == GENDER_MALE:
            allocator.reserve(str(preset["name"]), who="AI ĐÓ")
    assert allocator.choose("unknown", npc=False, who="X")["gender"] == GENDER_FEMALE
