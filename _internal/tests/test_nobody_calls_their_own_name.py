"""Không ai gọi tên chính mình: câu thoại gán cho X mà GỌI X ("..., Shizuka.") hay nhắc X kèm kính ngữ ("Shizuka-san") là
của người khác (`first_person.addressed_names`, `character_registry._repair_dialogue_turns_by_address`).

Đo 09-10 trên 10 lượt cổng 19 chương: câu gán cho chính người nó gọi/kính ngữ sai 100% theo đáp án. Sửa theo chuỗi lượt
xen kẽ hai người (câu gọi tên làm neo) hoặc theo người đối thoại duy nhất quanh đó: F1 giọng +9,7 cộng dồn, không lượt nào
giảm.
"""
from __future__ import annotations

from pathlib import Path

from abook.analysis import opens_a_new_turn
from abook.character_registry import _repair_dialogue_turns_by_address
from abook.database import ProjectDB
from abook.first_person import addressed_names

NAMES = {"Kou", "Shizuka", "Karui"}


def test_a_call_at_the_head_or_tail_of_a_line_names_who_is_spoken_to() -> None:
    assert addressed_names("“Này Kou, cậu đi đâu đấy?”", NAMES) == {"Kou"}
    assert addressed_names("“Kou, đợi đã!”", NAMES) == {"Kou"}
    assert addressed_names("“Nghĩ lắm mệt đầu ra, Kou.”", NAMES) == {"Kou"}
    assert addressed_names("“Kou ơi, ăn cơm thôi.”", NAMES) == {"Kou"}
    assert addressed_names("“Cảm ơn Shizuka nhiều lắm.”", NAMES) == {"Shizuka"}
    # Kính ngữ: không ai tự gọi mình "-san", ở đâu trong câu cũng thế, kể cả câu tự giới thiệu.
    assert addressed_names("“Chắc Shizuka-san sẽ thấy nóng hơn.”", NAMES) == {"Shizuka"}


def test_a_name_that_is_only_mentioned_is_not_a_call() -> None:
    # Tên giữa câu kẹp dấu câu: Forbidden 094 - đại tư tế hỏi Karui về người thứ ba, câu không phải của ai trong cặp.
    assert addressed_names("“Về chuyện của cậu, Karui và Amae sẽ… Hmm? Karui… Tsukshi đâu rồi?”", NAMES) == set()
    assert addressed_names("“Kou đầu teo nên chắc không sao đâu.”", NAMES) == set()
    # Tự giới thiệu đọc đúng tên người nói; "gọi là X" là nói về cái tên.
    assert addressed_names("“Chào anh, tôi là chủ nhà khu kí túc, Kasagi Shizuka.”", NAMES) == set()
    assert addressed_names("“Ở đây ai cũng gọi là Kou, cậu cứ thế mà gọi.”", NAMES) == set()
    assert addressed_names("“Kou ơi.”", set()) == set()


def test_a_new_turn_is_an_opened_quote_a_dash_or_a_closed_previous_line() -> None:
    assert opens_a_new_turn("“Đi thôi.”", "“Ừ.”")
    assert opens_a_new_turn("“Đi thôi.", "- Ừ.")
    assert not opens_a_new_turn("“Nghe này, ta chỉ nói một lần thôi.", "Ngày mai cả đoàn lên đường.”")


def _project(root: Path, lines: list[tuple[int, str, str, str, str]]) -> ProjectDB:
    """`lines`: (đoạn văn, loại, chữ, người nói, giới)."""
    root.mkdir(parents=True)
    source = root / "001.txt"
    source.write_bytes("\n".join(text for _p, _k, text, _s, _g in lines).encode("utf-8"))
    db = ProjectDB(root / "project.sqlite3")
    db.initialize_book(title="Thử", project_root=root, settings={}, settings_hash="s", input_manifest_hash="m")
    chapter = db.ensure_chapters([{"chapter_index": 1, "title": "001", "input_path": source, "input_sha256": "x",
                                   "input_size": 1, "output_mp3": root / "001.mp3"}])[0]
    db.replace_chapter_segments(chapter, [
        {"stable_id": f"s{seq}", "seq": seq, "paragraph_index": paragraph, "text": text, "text_sha256": f"t{seq}",
         "kind_hint": kind}
        for seq, (paragraph, kind, text, _speaker, _gender) in enumerate(lines)
    ])
    with db.transaction() as conn:
        for seq, (_paragraph, kind, _text, speaker, gender) in enumerate(lines):
            conn.execute("UPDATE segments SET kind=?, speaker=?, gender=? WHERE stable_id=?",
                         (kind, speaker, gender, f"s{seq}"))
    return db


def _repair(db: ProjectDB, aliases: dict[str, set[str]] | None = None) -> list[str]:
    said: list[str] = []
    _repair_dialogue_turns_by_address(db, said.append, aliases or {})
    return [str(row["speaker"]) for row in sorted(db.list_segments(), key=lambda row: int(row["seq"]))]


def test_an_exchange_follows_the_one_order_the_calls_allow(tmp_path: Path) -> None:
    # Model lệch một nhịp: câu đầu gọi Koutarou mà gán cho chính anh ta. Chỉ thứ tự SHIZUKA-KOU-SHIZUKA-KOU hợp neo.
    db = _project(tmp_path / "b", [
        (1, "dialogue", "“Koutarou, cậu về rồi à?”", "SATOMI KOUTAROU", "male"),
        (2, "dialogue", "“Ừ, vừa về.”", "KASAGI SHIZUKA", "female"),
        (3, "dialogue", "“Vậy ăn cơm luôn nhé.”", "SATOMI KOUTAROU", "male"),
        (4, "dialogue", "“Được.”", "SATOMI KOUTAROU", "male"),
    ])
    aliases = {"SATOMI KOUTAROU": {"SATOMI KOUTAROU"}, "KASAGI SHIZUKA": {"KASAGI SHIZUKA"}}
    assert _repair(db, aliases) == ["KASAGI SHIZUKA", "SATOMI KOUTAROU", "KASAGI SHIZUKA", "SATOMI KOUTAROU"]
    genders = {str(row["speaker"]): str(row["gender"]) for row in db.list_segments()}
    assert genders == {"KASAGI SHIZUKA": "female", "SATOMI KOUTAROU": "male"}


def test_an_exchange_without_a_call_or_with_a_third_voice_is_left_alone(tmp_path: Path) -> None:
    no_call = _project(tmp_path / "a", [
        (1, "dialogue", "“Cậu về rồi à?”", "KOU", "male"),
        (2, "dialogue", "“Ừ, vừa về.”", "KOU", "male"),
        (3, "dialogue", "“Vậy ăn cơm luôn nhé.”", "SHIZUKA", "female"),
    ])
    assert _repair(no_call) == ["KOU", "KOU", "SHIZUKA"]
    # Ba người trong chuỗi: không biết ai xen kẽ với ai; câu gọi Kou cũng không có người đối thoại DUY NHẤT.
    three = _project(tmp_path / "c", [
        (1, "dialogue", "“Kou, cậu về rồi à?”", "KOU", "male"),
        (2, "dialogue", "“Ừ, vừa về.”", "SHIZUKA", "female"),
        (3, "dialogue", "“Ăn cơm thôi.”", "KENJI", "male"),
    ])
    assert _repair(three) == ["KOU", "SHIZUKA", "KENJI"]


def test_a_lone_line_that_calls_its_own_speaker_goes_to_the_one_partner(tmp_path: Path) -> None:
    db = _project(tmp_path / "a", [
        (1, "dialogue", "“Ăn cơm chưa?”", "SHIZUKA", "female"),
        (2, "narration", "Cô quay sang cậu.", "NARRATOR", "unknown"),
        (3, "dialogue", "“Này Kou, trả lời đi chứ.”", "KOU", "male"),
        (4, "thought", "(Kou ơi là Kou.)", "KOU", "male"),
    ])
    # Nội tâm không đụng tới; câu thoại về người đối thoại duy nhất quanh đó.
    assert _repair(db) == ["SHIZUKA", "NARRATOR", "SHIZUKA", "KOU"]


def test_a_name_inside_a_descriptive_label_is_someone_else(tmp_path: Path) -> None:
    # "Bạn của Saki" gọi Saki là đúng vai: tên trong nhãn mô tả là người khác, không phải người nói.
    db = _project(tmp_path / "a", [
        (1, "dialogue", "“Chào, Saki-chan. Sao đứng như trời trồng thế kia?”", "Bạn của Saki", "female"),
        (2, "narration", "Saki giật mình.", "NARRATOR", "unknown"),
        (3, "dialogue", "“À, không có gì.”", "SAKI", "female"),
    ])
    assert _repair(db) == ["Bạn của Saki", "NARRATOR", "SAKI"]


def test_a_lone_line_with_two_possible_partners_is_left_alone(tmp_path: Path) -> None:
    db = _project(tmp_path / "a", [
        (1, "dialogue", "“Ăn cơm chưa?”", "SHIZUKA", "female"),
        (2, "narration", "Kenji cười.", "NARRATOR", "unknown"),
        (3, "dialogue", "“Này Kou, trả lời đi chứ.”", "KOU", "male"),
        (4, "narration", "Cả hai nhìn cậu.", "NARRATOR", "unknown"),
        (5, "dialogue", "“Thôi kệ cậu ta.”", "KENJI", "male"),
    ])
    assert _repair(db) == ["SHIZUKA", "NARRATOR", "KOU", "NARRATOR", "KENJI"]
