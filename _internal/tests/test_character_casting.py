from __future__ import annotations

from pathlib import Path

import pytest

from abook.character_registry import (
    PresetAllocator,
    assert_voice_stability,
    build_registry_and_cast,
)
from abook.analysis import local_speaker_label
from abook.config import build_settings
from abook.database import (
    EXPLICIT_ATTRIBUTION_NOTE,
    ProjectDB,
    canonical_analysis_note,
)
from abook.voice_catalog import EXCLUDED_PRESETS, GENDER_FEMALE, GENDER_MALE, REGION_CENTRAL, REGION_NORTH, REGION_SOUTH, STYLE_NATURAL, preset_eligible, STYLE_STORY, VIENEU_PRESETS, casting_presets, preset_by_name


def _casting_db(tmp_path: Path) -> ProjectDB:
    db = ProjectDB(tmp_path / "project.sqlite3")
    db.initialize_book(
        title="Book",
        project_root=tmp_path,
        settings={},
        settings_hash="settings",
        input_manifest_hash="manifest",
    )
    chapter_id = db.ensure_chapters(
        [
            {
                "chapter_index": 1,
                "title": "One",
                "input_path": tmp_path / "one.txt",
                "input_sha256": "source",
                "input_size": 1,
                "output_mp3": tmp_path / "one.mp3",
            }
        ]
    )[0]
    speakers = [("NARRATOR", "unknown")]
    # Đủ nhiều để buộc phải dùng lại preset: kho có mười giọng nam phân vai được ngoài người kể.
    speakers.extend((f"Nam {index}", "male") for index in range(1, 21))
    speakers.extend((f"Nữ {index}", "female") for index in range(1, 8))
    speakers.extend(
        [
            ("NPC_LOCAL::c00001::b0001::áo xanh", "male"),
            ("NPC_LOCAL::c00001::b0001::áo đỏ", "male"),
            ("NPC_LOCAL::c00001::b0001::áo vàng", "male"),
            ("NPC_LOCAL::c00001::b0001::áo tím", "male"),
            ("NPC_LOCAL::c00001::b0002::giám mục", "male"),
            ("Giám mục", "male"),
            ("UNKNOWN", "male"),
            ("UNKNOWN", "female"),
        ]
    )
    rows = []
    for seq, (speaker, gender) in enumerate(speakers):
        rows.append(
            {
                "stable_id": f"c1s{seq}",
                "seq": seq,
                "text": f"Câu thoại thử nghiệm số {seq}.",
                "text_sha256": f"text{seq}",
                "kind_hint": "narration" if speaker == "NARRATOR" else "dialogue",
                "kind": "narration" if speaker == "NARRATOR" else "dialogue",
                "speaker": speaker,
                "gender": gender,
                "confidence": 0.95,
                "status": "analyzed",
            }
        )
    db.replace_chapter_segments(chapter_id, rows)
    return db


def _identity_db(tmp_path: Path, speakers: list[tuple[str, str]]) -> ProjectDB:
    db = ProjectDB(tmp_path / "identity-gate.sqlite3")
    db.initialize_book(
        title="Book",
        project_root=tmp_path,
        settings={},
        settings_hash="settings",
        input_manifest_hash="manifest",
    )
    chapter_id = db.ensure_chapters(
        [
            {
                "chapter_index": 1,
                "title": "One",
                "input_path": tmp_path / "one.txt",
                "input_sha256": "source",
                "input_size": 1,
                "output_mp3": tmp_path / "one.mp3",
            }
        ]
    )[0]
    db.replace_chapter_segments(
        chapter_id,
        [
            {
                "stable_id": f"c1s{seq}",
                "seq": seq,
                "text": f"Câu thoại {seq}.",
                "text_sha256": f"text-{seq}",
                "kind_hint": "dialogue",
                "kind": "dialogue",
                "speaker": speaker,
                "gender": gender,
                "confidence": 0.95,
                "status": "analyzed",
            }
            for seq, (speaker, gender) in enumerate(speakers, 1)
        ],
    )
    return db


def _canonical_note(kind: str) -> str:
    return canonical_analysis_note(
        {
            "kind": kind,
            "emotion": "neutral",
            "intensity": 1,
            "pace": "normal",
            "volume": "normal",
        }
    )


def _repair_db(tmp_path: Path, rows: list[dict[str, object]]) -> ProjectDB:
    db = ProjectDB(tmp_path / "repair.sqlite3")
    db.initialize_book(
        title="Book",
        project_root=tmp_path,
        settings={},
        settings_hash="settings",
        input_manifest_hash="manifest",
    )
    chapter_id = db.ensure_chapters(
        [
            {
                "chapter_index": 1,
                "title": "One",
                "input_path": tmp_path / "one.txt",
                "input_sha256": "source",
                "input_size": 1,
                "output_mp3": tmp_path / "one.mp3",
            }
        ]
    )[0]
    segments = []
    for row in rows:
        kind = str(row["kind"])
        stable_id = str(row["stable_id"])
        segments.append(
            {
                "text_sha256": f"text-{stable_id}",
                "kind_hint": kind,
                "emotion": "neutral",
                "intensity": 1,
                "pace": "normal",
                "volume": "normal",
                "confidence": 0.95,
                "analysis_notes": _canonical_note(kind),
                "status": "analyzed",
                **row,
            }
        )
    db.replace_chapter_segments(chapter_id, segments)
    return db


def _reconciliation_db(tmp_path: Path) -> ProjectDB:
    db = ProjectDB(tmp_path / "reconciliation.sqlite3")
    db.initialize_book(
        title="Book",
        project_root=tmp_path,
        settings={},
        settings_hash="settings",
        input_manifest_hash="manifest",
    )
    chapter_id = db.ensure_chapters(
        [
            {
                "chapter_index": 1,
                "title": "One",
                "input_path": tmp_path / "one.txt",
                "input_sha256": "source",
                "input_size": 1,
                "output_mp3": tmp_path / "one.mp3",
            }
        ]
    )[0]
    rows = [
        (1, 1, "“Lời của người đàn ông.”", "NPC_LOCAL::c00001::a::người đàn ông trung niên", "male", "adult"),
        (10, 10, "“Lời của giám mục.”", "NPC_LOCAL::c00001::b::giam muc", "male", "adult"),
        (20, 20, "“Lời nguyền đầu tiên!”", "NPC_LOCAL::c00001::c::người phụ nữ mặc áo choàng đen", "female", "adult"),
        (21, 21, "“Điên rồi!”", "NPC_LOCAL::c00001::crowd::phu nu ao choang den", "female", "unknown"),
        (22, 22, "“Độc ác quá!”", "NPC_LOCAL::c00001::crowd::phu nu ao choang den", "female", "unknown"),
        (23, 23, "“Thiêu ả đi!”", "NPC_LOCAL::c00001::crowd::phu nu ao choang den", "female", "unknown"),
        (24, 24, "Những người dân nghèo trên quảng trường gào thét đến lạc giọng.", "NARRATOR", "unknown", "unknown"),
        (30, 30, "“Từ trong biển lửa, ta sẽ chứng kiến tất cả sụp đổ.", "NPC_LOCAL::c00001::d::phu nu ao choang den", "female", "adult"),
        (31, 31, "Ta sẽ chứng kiến các ngươi trầm luân!”", "NPC_LOCAL::c00001::e::thần lửa", "male", "unknown"),
    ]
    db.replace_chapter_segments(
        chapter_id,
        [
            {
                "stable_id": f"c1s{seq}",
                "seq": seq,
                "paragraph_index": paragraph,
                "text": text,
                "text_sha256": f"text-{seq}",
                "kind_hint": "narration" if speaker == "NARRATOR" else "dialogue",
                "kind": "narration" if speaker == "NARRATOR" else "dialogue",
                "speaker": speaker,
                "gender": gender,
                "age": age,
                "confidence": 0.95,
                "analysis_notes": _canonical_note(
                    "narration" if speaker == "NARRATOR" else "dialogue"
                ),
                "status": "analyzed",
            }
            for seq, paragraph, text, speaker, gender, age in rows
        ],
    )
    return db


def test_casting_prioritizes_natural_north_then_natural_south() -> None:
    male_order = [
        (preset["region"], preset["style"])
        for preset in casting_presets(GENDER_MALE)
    ]
    female_order = [
        (preset["region"], preset["style"])
        for preset in casting_presets(GENDER_FEMALE)
    ]

    # Natural before storytelling, North before South within each. Xuân Vĩnh is back as a
    # Northern natural voice since VieNeu 3.8.1, and Adam is the one Southern natural male.
    assert male_order == [
        *[(REGION_NORTH, STYLE_NATURAL)] * 5,
        (REGION_SOUTH, STYLE_NATURAL),
        *[(REGION_NORTH, STYLE_STORY)] * 3,
        *[(REGION_SOUTH, STYLE_STORY)] * 2,
    ]
    assert female_order == [
        *[(REGION_NORTH, STYLE_NATURAL)] * 3,
        *[(REGION_NORTH, STYLE_STORY)] * 2,
        *[(REGION_SOUTH, STYLE_STORY)] * 3,
    ]
    assert REGION_CENTRAL not in {region for region, _style in male_order + female_order}


def test_clear_named_aliases_lock_to_one_character_and_voice(tmp_path: Path) -> None:
    db = _identity_db(
        tmp_path,
        [
            ("ALISA", "female"),
            ("DÌ ALISA", "female"),
            ("NPC ALISA", "female"),
            ("NPC_LOCAL::c00001::stable::Alisa", "female"),
            ("VICTOR", "male"),
            ("VICT,OR", "male"),
        ],
    )

    build_registry_and_cast(db, build_settings(), lambda _message: None)

    rows = db.list_segments()
    assert {str(row["speaker"]) for row in rows} == {"ALISA", "VICTOR"}
    for speaker in ("ALISA", "VICTOR"):
        speaker_rows = [row for row in rows if str(row["speaker"]) == speaker]
        assert len({int(row["canonical_character_id"]) for row in speaker_rows}) == 1
        assert len({int(row["voice_profile_id"]) for row in speaker_rows}) == 1


def test_adjacent_local_child_scopes_merge_to_one_character_and_voice(tmp_path: Path) -> None:
    db = _identity_db(
        tmp_path,
        [
            ("NPC_LOCAL::c00001::batch-a::cậu bé", "male"),
            ("NPC_LOCAL::c00001::batch-b::trẻ em bụi bẩn", "male"),
        ],
    )

    build_registry_and_cast(db, build_settings(), lambda _message: None)

    rows = db.list_segments()
    assert len({str(row["speaker"]) for row in rows}) == 1
    assert len({int(row["canonical_character_id"]) for row in rows}) == 1
    assert len({int(row["voice_profile_id"]) for row in rows}) == 1


def test_interleaved_local_children_remain_distinct(tmp_path: Path) -> None:
    first = "NPC_LOCAL::c00001::batch-a::cậu bé áo xanh"
    second = "NPC_LOCAL::c00001::batch-b::trẻ em áo đỏ"
    db = _identity_db(
        tmp_path,
        [(first, "male"), (second, "male"), (first, "male"), (second, "male")],
    )

    build_registry_and_cast(db, build_settings(), lambda _message: None)

    rows = db.list_segments()
    assert len({str(row["speaker"]) for row in rows}) == 2
    assert len({int(row["canonical_character_id"]) for row in rows}) == 2


def test_reconciliation_repairs_crowd_and_continuation_without_note_markers(
    tmp_path: Path,
) -> None:
    db = _reconciliation_db(tmp_path)

    build_registry_and_cast(db, build_settings(), lambda _message: None)

    rows = {int(row["seq"]): row for row in db.list_segments()}
    bishop_rows = [rows[1], rows[10]]
    witch_rows = [rows[20], rows[30], rows[31]]
    crowd_rows = [rows[21], rows[22], rows[23]]
    assert len({int(row["canonical_character_id"]) for row in bishop_rows}) == 2
    assert len({int(row["canonical_character_id"]) for row in witch_rows}) == 1
    assert len({int(row["voice_profile_id"]) for row in witch_rows}) == 1
    assert {local_speaker_label(row["speaker"]) for row in crowd_rows} == {"người dân"}
    assert {str(row["gender"]) for row in crowd_rows} == {"unknown"}
    for row in crowd_rows:
        assert str(row["analysis_notes"]) == _canonical_note(str(row["kind"]))

    first_snapshot = {
        seq: (
            str(row["speaker"]),
            str(row["gender"]),
            str(row["age"]),
            str(row["analysis_notes"]),
            int(row["canonical_character_id"]),
            int(row["voice_profile_id"]),
        )
        for seq, row in rows.items()
    }

    build_registry_and_cast(db, build_settings(), lambda _message: None)

    assert {
        int(row["seq"]): (
            str(row["speaker"]),
            str(row["gender"]),
            str(row["age"]),
            str(row["analysis_notes"]),
            int(row["canonical_character_id"]),
            int(row["voice_profile_id"]),
        )
        for row in db.list_segments()
    } == first_snapshot


def test_collective_source_attribution_remains_eligible_for_crowd_repair(
    tmp_path: Path,
) -> None:
    speaker = "NPC_LOCAL::c00001::crowd::người phụ nữ"
    db = _repair_db(
        tmp_path,
        [
            {
                "stable_id": "dialogue",
                "seq": 1,
                "paragraph_index": 7,
                "text": "“Thiêu ả đi!”",
                "kind": "dialogue",
                "speaker": speaker,
                "gender": "female",
                "age": "adult",
            },
            {
                "stable_id": "crowd-attribution",
                "seq": 2,
                "paragraph_index": 7,
                "text": "Những người dân nghèo gào thét đến lạc giọng.",
                "kind": "narration",
                "speaker": "NARRATOR",
                "gender": "unknown",
                "age": "unknown",
            },
        ],
    )

    build_registry_and_cast(db, build_settings(), lambda _message: None)

    dialogue = next(row for row in db.list_segments() if int(row["seq"]) == 1)
    assert local_speaker_label(dialogue["speaker"]) == "người dân"
    assert dialogue["analysis_notes"] == _canonical_note("dialogue")


def test_crowd_repair_uses_source_narration_hint_when_final_kind_is_thought(
    tmp_path: Path,
) -> None:
    db = _repair_db(
        tmp_path,
        [
            {
                "stable_id": "dialogue",
                "seq": 1,
                "paragraph_index": 1,
                "text": "“Đuổi hắn đi!”",
                "kind": "dialogue",
                "speaker": "NPC_LOCAL::c00001::crowd::người đàn ông",
                "gender": "male",
                "age": "adult",
            },
            {
                "stable_id": "source-crowd-thought",
                "seq": 2,
                "paragraph_index": 2,
                "text": "Đám đông đồng loạt hô vang giữa quảng trường.",
                "kind_hint": "narration",
                "kind": "thought",
                "speaker": "NARRATOR",
                "gender": "unknown",
                "age": "unknown",
            },
        ],
    )

    build_registry_and_cast(db, build_settings(), lambda _message: None)

    dialogue = next(row for row in db.list_segments() if int(row["seq"]) == 1)
    assert local_speaker_label(dialogue["speaker"]) == "người dân"


def test_named_source_attribution_stops_crowd_repair_at_individual_boundary(
    tmp_path: Path,
) -> None:
    shared_speaker = "NPC_LOCAL::c00001::shared::người phụ nữ"
    db = _repair_db(
        tmp_path,
        [
            {
                "stable_id": "named-attribution",
                "seq": 1,
                "paragraph_index": 4,
                "text": "Alisa nói:",
                "kind": "narration",
                "speaker": "NARRATOR",
                "gender": "unknown",
                "age": "unknown",
            },
            {
                "stable_id": "protected-dialogue",
                "seq": 2,
                "paragraph_index": 4,
                "text": "“Không được.”",
                "kind": "dialogue",
                "speaker": shared_speaker,
                "gender": "female",
                "age": "adult",
            },
            {
                "stable_id": "crowd-dialogue",
                "seq": 3,
                "paragraph_index": 5,
                "text": "“Thiêu ả đi!”",
                "kind": "dialogue",
                "speaker": shared_speaker,
                "gender": "female",
                "age": "adult",
            },
            {
                "stable_id": "crowd-attribution",
                "seq": 4,
                "paragraph_index": 6,
                "text": "Người dân đồng loạt gào thét ngoài quảng trường.",
                "kind": "narration",
                "speaker": "NARRATOR",
                "gender": "unknown",
                "age": "unknown",
            },
        ],
    )

    build_registry_and_cast(db, build_settings(), lambda _message: None)

    rows = {int(row["seq"]): row for row in db.list_segments()}
    assert str(rows[2]["speaker"]) == shared_speaker
    assert local_speaker_label(rows[3]["speaker"]) == "người dân"


def test_crowd_repair_stops_at_nonconsecutive_source_gap(tmp_path: Path) -> None:
    speaker = "NPC_LOCAL::c00001::crowd::người phụ nữ"
    db = _repair_db(
        tmp_path,
        [
            {
                "stable_id": "before-gap",
                "seq": 1,
                "paragraph_index": 1,
                "text": "“Ta không tham gia.”",
                "kind": "dialogue",
                "speaker": speaker,
                "gender": "female",
                "age": "adult",
            },
            {
                "stable_id": "crowd-dialogue",
                "seq": 3,
                "paragraph_index": 3,
                "text": "“Đuổi hắn đi!”",
                "kind": "dialogue",
                "speaker": speaker,
                "gender": "female",
                "age": "adult",
            },
            {
                "stable_id": "crowd-attribution",
                "seq": 4,
                "paragraph_index": 4,
                "text": "Mọi người đồng loạt hô vang.",
                "kind": "narration",
                "speaker": "NARRATOR",
                "gender": "unknown",
                "age": "unknown",
            },
        ],
    )

    build_registry_and_cast(db, build_settings(), lambda _message: None)

    rows = {int(row["seq"]): row for row in db.list_segments()}
    assert str(rows[1]["speaker"]) == speaker
    assert local_speaker_label(rows[3]["speaker"]) == "người dân"


def test_crowd_repair_stops_at_exact_speaker_identity_boundary(tmp_path: Path) -> None:
    protected_speaker = "NPC_LOCAL::c00001::individual::người phụ nữ"
    crowd_speaker = "NPC_LOCAL::c00001::crowd::người phụ nữ"
    db = _repair_db(
        tmp_path,
        [
            {
                "stable_id": "individual-dialogue",
                "seq": 1,
                "paragraph_index": 1,
                "text": "“Ta không đồng ý.”",
                "kind": "dialogue",
                "speaker": protected_speaker,
                "gender": "female",
                "age": "adult",
            },
            {
                "stable_id": "crowd-dialogue",
                "seq": 2,
                "paragraph_index": 2,
                "text": "“Đuổi hắn đi!”",
                "kind": "dialogue",
                "speaker": crowd_speaker,
                "gender": "female",
                "age": "adult",
            },
            {
                "stable_id": "crowd-attribution",
                "seq": 3,
                "paragraph_index": 3,
                "text": "Dân chúng đồng loạt la hét.",
                "kind": "narration",
                "speaker": "NARRATOR",
                "gender": "unknown",
                "age": "unknown",
            },
        ],
    )

    build_registry_and_cast(db, build_settings(), lambda _message: None)

    rows = {int(row["seq"]): row for row in db.list_segments()}
    assert str(rows[1]["speaker"]) == protected_speaker
    assert local_speaker_label(rows[2]["speaker"]) == "người dân"


def test_cross_batch_continuation_does_not_cross_nonconsecutive_seq_gap(
    tmp_path: Path,
) -> None:
    first_speaker = "NPC_LOCAL::c00001::first::người phụ nữ"
    second_speaker = "NPC_LOCAL::c00001::second::ông lão"
    db = _repair_db(
        tmp_path,
        [
            {
                "stable_id": "before-gap",
                "seq": 1,
                "paragraph_index": 1,
                "text": "“Câu nói còn dang dở.",
                "kind": "dialogue",
                "speaker": first_speaker,
                "gender": "female",
                "age": "adult",
            },
            {
                "stable_id": "after-gap",
                "seq": 3,
                "paragraph_index": 2,
                "text": "Phần tiếp theo không có dấu mở đầu.”",
                "kind": "dialogue",
                "speaker": second_speaker,
                "gender": "male",
                "age": "elderly",
            },
        ],
    )

    build_registry_and_cast(db, build_settings(), lambda _message: None)

    assert {str(row["speaker"]) for row in db.list_segments()} == {
        first_speaker,
        second_speaker,
    }


@pytest.mark.parametrize(
    "analysis_note",
    (
        "Lượt phân tích này chỉ mô tả delivery của câu.",
        canonical_analysis_note(
            {
                "kind": "dialogue",
                "emotion": "neutral",
                "intensity": 1,
                "pace": "normal",
                "volume": "normal",
            },
            (EXPLICIT_ATTRIBUTION_NOTE,),
        ),
        "personality=calm=forged",
    ),
)
def test_casting_does_not_promote_delivery_notes_to_character_personality(
    tmp_path: Path,
    analysis_note: str,
) -> None:
    db = _identity_db(tmp_path, [("ALISA", "female"), ("ALISA", "female")])
    with db.connect() as conn:
        conn.execute("UPDATE segments SET analysis_notes=?", (analysis_note,))

    build_registry_and_cast(db, build_settings(), lambda _message: None)

    character = next(
        row for row in db.list_characters() if str(row["display_name"]) == "ALISA"
    )
    assert character["personality"] == ""
    assert {str(row["analysis_notes"]) for row in db.list_segments()} == {
        analysis_note
    }


def test_casting_accepts_only_validated_legacy_personality_prefix(
    tmp_path: Path,
) -> None:
    db = _identity_db(tmp_path, [("ALISA", "female"), ("ALISA", "female")])
    with db.connect() as conn:
        conn.execute(
            "UPDATE segments SET analysis_notes='personality=calm and deliberate'"
        )

    build_registry_and_cast(db, build_settings(), lambda _message: None)

    character = next(
        row for row in db.list_characters() if str(row["display_name"]) == "ALISA"
    )
    assert character["personality"] == "calm and deliberate"


def test_legacy_personality_metadata_does_not_merge_distinct_local_identities(
    tmp_path: Path,
) -> None:
    speakers = [
        "NPC_LOCAL::c00001::batch-a::người đàn ông trung niên",
        "NPC_LOCAL::c00001::batch-b::giám mục",
    ]
    db = _identity_db(tmp_path, [(speaker, "male") for speaker in speakers])
    with db.connect() as conn:
        conn.execute("UPDATE segments SET analysis_notes='personality=priest'")

    build_registry_and_cast(db, build_settings(), lambda _message: None)

    rows = db.list_segments()
    assert {str(row["speaker"]) for row in rows} == set(speakers)
    assert len({int(row["canonical_character_id"]) for row in rows}) == 2


def test_relational_description_is_not_merged_with_named_character(tmp_path: Path) -> None:
    db = _identity_db(
        tmp_path,
        [("FELICIA", "female"), ("MẸ CỦA FELICIA", "female")],
    )

    build_registry_and_cast(db, build_settings(), lambda _message: None)

    rows = db.list_segments()
    assert {str(row["speaker"]) for row in rows} == {"FELICIA", "MẸ CỦA FELICIA"}
    assert len({int(row["canonical_character_id"]) for row in rows}) == 2


def test_gender_conflict_no_longer_fails_the_whole_book(tmp_path: Path) -> None:
    """Cho tới 2026-09-09, chỗ này ném lỗi và **cả cuốn sách dừng**.

    Lý lẽ cũ đúng theo nghĩa của nó: đừng đúc giọng khi còn chưa biết nhân vật là nam hay nữ.
    Cái nó không lường là cái giá. Lô 1 chết ở đây **sau 4 giờ phân tích trọn vẹn 3.727 đoạn**,
    vì một nhân vật phụ có đúng hai câu thoại mà model gán một nữ một nam — và vì `resume` bị
    từ chối sau khi sửa mã, toàn bộ 4 giờ ấy mất trắng chứ không chỉ phần còn lại.

    Đây là cổng đắt nhất trong dự án: chương hỏng thì mất một chương, cổng này hỏng thì mất cả
    cuốn, ngay sau khi đã trả xong phần đắt nhất của lượt chạy. Và nó vi phạm nguyên tắc đã
    chốt ở docs/SHIPPING_WITHOUT_A_LISTENER.md — *một phép kiểm không phán xử được thì không
    được chặn*.

    **Ngưỡng bằng chứng KHÔNG được hạ** để bù. Đo trên mọi project đã lưu, bằng chứng văn bản
    nhất trí ở 3 hit mâu thuẫn với model 5 lần trên 13, ở 1 hit là 17 khớp / 18 lệch — tức tung
    đồng xu. `GENDER_EVIDENCE_MINIMUM_HITS = 5` không tuỳ tiện; hạ nó là mua một lỗi im lặng để
    tránh một lỗi ồn ào. Cái đổi là **hậu quả**, không phải ngưỡng.
    """
    said: list[str] = []
    db = _identity_db(tmp_path, [("CAMIL", "female"), ("Camil", "male")])

    build_registry_and_cast(db, build_settings(), said.append)

    assert db.list_voice_profiles(), "phải đúc giọng và đi tiếp, không dừng cả cuốn sách"
    assert any("CAMIL" in line for line in said), "và phải nói ra tên nhân vật ấy"
    assert any("cli cast" in line for line in said), "kèm cách sửa"
    codes = {str(row["code"]) for row in db.list_events()}
    assert "CASTING_GENDER_UNRESOLVED" in codes, "không im lặng: phải có sự kiện để vào báo cáo"


def test_recurring_named_speaker_without_gender_no_longer_fails_the_whole_book(
    tmp_path: Path,
) -> None:
    """Cho tới 2026-09-14 chỗ này ném lỗi, và bản trước của bài này khẳng định nó phải ném.

    Bài ấy không có một dòng lý lẽ nào — khác hẳn `test_gender_conflict_no_longer_fails_the_whole_book`
    ngay bên trên, nơi lập luận được viết đủ. Và lập luận ấy áp vào đây còn mạnh hơn: **mâu thuẫn là
    model nói hai điều, thiếu là model không nói gì**. Nếu một câu hỏi không phán xử được thì không
    được chặn, thì một câu hỏi *không có dữ liệu nào để phán xử* càng không được chặn.

    Cái giá đã trả bằng tiền thật: cuốn 2 lô 2 chết 19:30 ngày 14-09 sau **5 giờ 30 phút** phân tích
    trọn 3.749 đoạn, vì `Luke` (4 câu) và `Nghe` (3 câu) — cái thứ hai còn không phải người.
    """
    said: list[str] = []
    db = _identity_db(tmp_path, [("Mag", "unknown")] * 3)

    build_registry_and_cast(db, build_settings(), said.append)

    assert db.list_voice_profiles(), "phải đúc giọng và đi tiếp, không dừng cả cuốn sách"
    assert any("MAG" in line and "cli cast" in line for line in said), "phải nói ra tên và cách sửa"
    codes = {str(row["code"]) for row in db.list_events()}
    assert "CASTING_GENDER_UNRESOLVED" in codes, "không im lặng: phải có sự kiện để vào báo cáo"


def test_a_listener_locked_gender_opens_the_gate(tmp_path: Path) -> None:
    """`cli cast` là cách chữa mà thông điệp lỗi mách; nó phải thật sự chữa được.

    Cổng cũ tính "thiếu giới tính" chỉ từ dữ liệu của model và không đọc `locked`, nên người nghe trả
    lời đúng câu hỏi được hỏi mà cổng vẫn chặn — và `_command_cast` tồn tại chính để trả lời **trước**
    khi cast chạy ("readable before casting has ever run").
    """
    said: list[str] = []
    db = _identity_db(tmp_path, [("Mag", "unknown")] * 3)
    db.lock_character_gender("Mag", "male")

    build_registry_and_cast(db, build_settings(), said.append)

    assert db.list_voice_profiles()
    assert not any("không có bằng chứng nào" in line for line in said), (
        "đã ghim thì không còn là 'thiếu bằng chứng'"
    )


def test_existing_voice_identity_instability_fails_before_recasting(tmp_path: Path) -> None:
    db = _identity_db(tmp_path, [("Lucien", "male"), ("Lucien", "male")])
    character_id = db.upsert_character(
        canonical_name="LUCIEN",
        display_name="Lucien",
        gender="male",
        age="adult",
        personality="",
        mentions=2,
        importance="main",
        confidence=0.95,
    )
    first_profile = db.upsert_voice_profile(
        {
            "voice_key": "unstable-one",
            "engine": "vieneu",
            "preset_name": "Thái Sơn",
            "description": "one",
            "seed": 1,

            "status": "ready",
        }
    )
    second_profile = db.upsert_voice_profile(
        {
            "voice_key": "unstable-two",
            "engine": "vieneu",
            "preset_name": "Quang Sơn",
            "description": "two",
            "seed": 2,

            "status": "ready",
        }
    )
    rows = db.list_segments()
    db.set_character_and_voice_for_segments([int(rows[0]["id"])], character_id, first_profile)
    db.set_character_and_voice_for_segments([int(rows[1]["id"])], character_id, second_profile)

    with pytest.raises(RuntimeError, match="voice identity instability"):
        build_registry_and_cast(db, build_settings(), lambda _message: None)


def test_same_lucien_name_locks_one_voice_across_chapters_without_identity_merging(
    tmp_path: Path,
) -> None:
    db = ProjectDB(tmp_path / "identity.sqlite3")
    db.initialize_book(
        title="Book",
        project_root=tmp_path,
        settings={},
        settings_hash="settings",
        input_manifest_hash="manifest",
    )
    chapter_ids = db.ensure_chapters(
        [
            {
                "chapter_index": index,
                "title": title,
                "input_path": tmp_path / f"{title}.txt",
                "input_sha256": f"source-{index}",
                "input_size": 1,
                "output_mp3": tmp_path / f"{title}.mp3",
            }
            for index, title in enumerate(("000", "001"), 1)
        ]
    )
    db.replace_chapter_segments(
        chapter_ids[0],
        [
            {
                "stable_id": "c1s1",
                "seq": 1,
                "text": "Hạ Phong đang nói.",
                "text_sha256": "text-hp",
                "kind_hint": "dialogue",
                "kind": "dialogue",
                "speaker": "Hạ Phong",
                "gender": "male",
                "confidence": 0.99,
                "status": "analyzed",
            },
            {
                "stable_id": "c1s2",
                "seq": 2,
                "text": "Lucien xuất hiện ở chương đầu.",
                "text_sha256": "text-lucien-1",
                "kind_hint": "dialogue",
                "kind": "dialogue",
                "speaker": "Lucien",
                "gender": "male",
                "confidence": 0.99,
                "status": "analyzed",
            },
            {
                "stable_id": "c1s3",
                "seq": 3,
                "text": "‘Nội tâm này phải do người kể đọc.’",
                "text_sha256": "text-thought",
                "kind_hint": "thought",
                "kind": "thought",
                "speaker": "Lucien",
                "gender": "male",
                "confidence": 0.99,
                "status": "analyzed",
            },
        ],
    )
    db.replace_chapter_segments(
        chapter_ids[1],
        [
            {
                "stable_id": "c2s1",
                "seq": 1,
                "text": "Lucien tiếp tục nói ở chương sau.",
                "text_sha256": "text-lucien-2",
                "kind_hint": "dialogue",
                "kind": "dialogue",
                "speaker": "Lucien",
                "gender": "male",
                "confidence": 0.99,
                "status": "analyzed",
            }
        ],
    )

    build_registry_and_cast(
        db,
        build_settings(),
        lambda _message: None,
    )

    rows = db.list_segments()
    lucien_rows = [row for row in rows if str(row["speaker"]) == "Lucien"]
    ha_phong_rows = [row for row in rows if str(row["speaker"]) == "Hạ Phong"]
    thought_rows = [row for row in rows if str(row["kind"]) == "thought"]

    # Lucien's spoken lines and his inner monologue are all his: a thought is read in the
    # voice of whoever is thinking it, so it no longer gets handed to the narrator.
    assert len(lucien_rows) == 3
    assert len({int(row["canonical_character_id"]) for row in lucien_rows}) == 1
    assert len({int(row["voice_profile_id"]) for row in lucien_rows}) == 1
    assert ha_phong_rows[0]["canonical_character_id"] != lucien_rows[0]["canonical_character_id"]
    # The thought keeps its thinker rather than being rewritten to NARRATOR, and it is
    # read in exactly the voice that speaker uses elsewhere.
    assert {str(row["speaker"]) for row in thought_rows} == {"Lucien"}
    assert {int(row["voice_profile_id"]) for row in thought_rows} == {
        int(lucien_rows[0]["voice_profile_id"])
    }


def test_central_presets_are_never_cast_through_any_path() -> None:
    """Removing a region is only real if every path that reaches presets respects it.

    `choose` has a fallback for when nothing of the requested gender is left, and that
    fallback used to scan the whole catalogue - which would have put the excluded Central
    presets straight back into the book.
    """
    for gender in (GENDER_MALE, GENDER_FEMALE):
        assert all(
            preset["region"] != REGION_CENTRAL for preset in casting_presets(gender)
        )

    central = [preset for preset in VIENEU_PRESETS if preset["region"] == REGION_CENTRAL]
    assert central, "the catalogue should still describe the presets VieNeu offers"
    for preset in central:
        # Still resolvable, so a book that locked one before the change keeps working.
        assert preset_by_name(str(preset["name"]))["region"] == REGION_CENTRAL


def test_one_character_cannot_hold_two_voices_through_different_labels(tmp_path: Path) -> None:
    """The stability check must follow the character, not the label on each line.

    A boy in a real run appeared as a named character in one place and as a local NPC in
    another, and held two voices three semitones apart. Every label had exactly one voice,
    so a per-label check reported success - and local labels were skipped outright, which
    widened the hole rather than narrowing it. The guarantee is about people, not strings.
    """

    class _Rows:
        def __init__(self, rows):
            self._rows = rows

        def list_segments(self):
            return self._rows

    same_person = 7
    rows = [
        {
            "speaker": "NPC_LOCAL::c00001::rabc::cậu bé",
            "canonical_character_id": same_person,
            "voice_profile_id": 11,
        },
        {
            "speaker": "Iven",
            "canonical_character_id": same_person,
            "voice_profile_id": 12,
        },
    ]

    with pytest.raises(RuntimeError, match="character resolved to multiple voice profiles"):
        assert_voice_stability(_Rows(rows))

    # The same two lines with one voice between them are accepted.
    rows[1]["voice_profile_id"] = 11
    assert assert_voice_stability(_Rows(rows)) is None


def test_an_excluded_preset_is_unreachable_through_every_path() -> None:
    """A voice the listener rejected must not come back through a fallback.

    This exact shape of hole let the Central presets back in once: the main catalogue
    filtered them and two fallback pools iterated the raw preset list instead. A ranking
    penalty was tried first and was not enough either - it made the voice a last resort
    rather than never, and a last resort is still reached once the pool runs thin.
    """
    for gender in ("male", "female"):
        assert not {
            str(preset["name"]) for preset in casting_presets(gender)
        } & EXCLUDED_PRESETS

    chosen: set[str] = set()
    for narrator in ("Phạm Tuyên", "Thanh Bình"):
        allocator = PresetAllocator(narrator)
        # Deep enough to exhaust every pool and force both fallback branches.
        for round_index in range(30):
            for gender in ("male", "female", "unknown"):
                for age in ("child", "teen", "adult", "elderly", "unknown"):
                    preset = allocator.choose(
                        gender, npc=round_index % 2 == 0, age=age
                    )
                    chosen.add(str(preset["name"]))

    assert chosen, "the sweep must actually cast something"
    assert not chosen & EXCLUDED_PRESETS
