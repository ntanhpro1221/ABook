"""Câu thoại gán cho X mà GỌI X ("Kasagi-san, ...") mà luật tự sửa (`_repair_dialogue_turns_by_address`) không chắc để sửa
(không có hoặc hơn một người đối thoại có tên) thì hộp "Việc cần anh" hỏi "ai nói câu này": người nói KHÔNG bị đổi, ứng viên là
người có tên nói quanh câu. Câu luật đã sửa được không sinh thẻ. Đo 09-10 trên 10 lượt cổng: 30 câu như thế, 30/30 sai theo
đáp án, người đúng nằm trong các lựa chọn của thẻ ở 28/30.
"""
from __future__ import annotations

from pathlib import Path

from test_nobody_calls_their_own_name import _project, _repair

from abook.database import ProjectDB
from abook.listener_overrides import NARRATOR, UNNAMED
from abook.webui.casting_review import casting_chapter
from abook.webui.work_items import work_items


def _registered(root: Path, lines: list[tuple[int, str, str, str, str]]) -> tuple[ProjectDB, Path]:
    """Sách như sau bước phân vai: luật gọi tên đã chạy, mỗi người nói có trong sổ nhân vật."""
    db = _project(root, lines)
    _repair(db)
    for speaker in {str(row["speaker"]) for row in db.list_segments() if str(row["speaker"]) != "NARRATOR"}:
        character = db.upsert_character(canonical_name=speaker.casefold(), display_name=speaker, gender="unknown", age="adult",
                                        personality="", mentions=1, importance="main", confidence=1.0)
        db.set_character_for_speaker(speaker, character)
    return db, root


def _vocative_cards(project: Path) -> list[dict]:
    return [item for item in work_items(project)["items"] if item["kind"] == "vocative"]


def test_a_call_the_rule_cannot_resolve_becomes_a_card_and_the_speaker_stays(tmp_path: Path) -> None:
    # Hai người đối thoại có tên quanh câu gọi Kasagi: luật không biết là ai, nên để nguyên.
    db, project = _registered(tmp_path / "a", [
        (1, "dialogue", "“Kasagi-san, phải làm sao thì em mới chịu đây!?”", "KASAGI", "female"),
        (2, "narration", "Sanae cúi đầu.", "NARRATOR", "unknown"),
        (3, "dialogue", "“Em không biết.”", "SANAE", "female"),
        (4, "narration", "Cả phòng im lặng.", "NARRATOR", "unknown"),
        (5, "dialogue", "“Thôi kệ đi.”", "RUTH", "female"),
    ])
    assert [str(row["speaker"]) for row in db.list_segments()][:1] == ["KASAGI"], "không tự sửa khi không chắc"
    (card,) = _vocative_cards(project)
    assert card["currentValue"] == "KASAGI" and card["lines"][0]["stableId"] == "s0"
    assert [choice["value"] for choice in card["choices"]] == ["SANAE", "RUTH", NARRATOR, UNNAMED]
    hint = next(line["hint"] for line in casting_chapter(project, 1)["lines"] if line["stableId"] == "s0")
    assert hint["kind"] == "vocative" and "Kasagi" in hint["note"]


def test_a_call_with_nobody_else_around_still_asks_with_the_narrator_and_the_unnamed_extra(tmp_path: Path) -> None:
    _db, project = _registered(tmp_path / "a", [
        (1, "dialogue", "“Kasagi-san, đợi em với!”", "KASAGI", "female"),
        (2, "narration", "Cô bé chạy theo.", "NARRATOR", "unknown"),
    ])
    (card,) = _vocative_cards(project)
    assert [choice["value"] for choice in card["choices"]] == [NARRATOR, UNNAMED]


def test_a_call_the_rule_already_fixed_makes_no_card(tmp_path: Path) -> None:
    db, project = _registered(tmp_path / "a", [
        (1, "dialogue", "“Ăn cơm chưa?”", "SHIZUKA", "female"),
        (2, "narration", "Cô quay sang cậu.", "NARRATOR", "unknown"),
        (3, "dialogue", "“Này Kou, trả lời đi chứ.”", "KOU", "male"),
    ])
    assert [str(row["speaker"]) for row in db.list_segments()] == ["SHIZUKA", "NARRATOR", "SHIZUKA"]
    assert _vocative_cards(project) == []
    assert all(line["hint"] is None for line in casting_chapter(project, 1)["lines"])


def test_an_inner_thought_that_says_the_name_is_not_a_card(tmp_path: Path) -> None:
    _db, project = _registered(tmp_path / "a", [
        (1, "dialogue", "“Ăn cơm chưa?”", "SHIZUKA", "female"),
        (2, "thought", "(Kou ơi là Kou, sao lại thế này.)", "KOU", "male"),
        (3, "dialogue", "“Chưa.”", "KOU", "male"),
    ])
    assert _vocative_cards(project) == []
