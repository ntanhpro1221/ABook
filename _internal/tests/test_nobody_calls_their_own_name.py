"""Không ai gọi tên chính mình: câu thoại gán cho X mà GỌI X ("..., Neravi.") hay nhắc X kèm kính ngữ ("Neravi-san") là
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
from abook.first_person import addressed_names, is_name_answer

NAMES = {"Tavin", "Neravi", "Melvi"}


def test_name_answers_and_introductions_are_not_vocative_anchors():
    for text in ('“Tôi là Mira.”', '“Mira. Lớp 2-4.”', '“Mira. Lớp 2-4, bên cạnh phòng nhạc.”', '“Mira, Mira Solin.”', '“Mira.”', '“Mira. Mira Solin.”', '- Mira. Mira Solin. Tôi vừa chuyển tới.', '“Mira Solin. Rất hân hạnh.”'):
        assert addressed_names(text, {'Mira', 'Mira Solin'}) == set()
    assert addressed_names('“Mira, giữ chiếc ô giúp tôi!”', {'Mira'}) == {'Mira'}
    assert addressed_names('“Cô ấy viết “Mira!” ở cuối thư.”', {'Mira'}) == set()


def test_one_filtered_vocative_recovers_the_unique_exchange_phase(tmp_path):
    db = _project(tmp_path / 'consecutive', [
        (1, 'dialogue', '“Mira, bên này!”', 'MIRA', 'female'),
        (2, 'dialogue', '“Tôi còn cầm bản đồ.”', 'TAVIN', 'male'),
        (3, 'dialogue', '“Đợi tôi gấp nó lại.”', 'TAVIN', 'male'),
        (4, 'dialogue', '“Được thôi.”', 'MIRA', 'female'),
    ])
    assert _repair(db) == ['TAVIN', 'MIRA', 'TAVIN', 'MIRA']


def test_two_calls_recover_the_unique_compatible_phase(tmp_path):
    db = _project(tmp_path / 'two_calls', [
        (1, 'dialogue', '“Mira, cầm đèn giúp tôi!”', 'MIRA', 'female'),
        (2, 'dialogue', '“Tôi giữ đèn đây.”', 'TAVIN', 'male'),
        (3, 'dialogue', '“Mira, soi sang bên trái nhé!”', 'MIRA', 'female'),
        (4, 'dialogue', '“Tôi thấy cánh cửa rồi.”', 'TAVIN', 'male'),
    ])
    assert _repair(db) == ['TAVIN', 'MIRA', 'TAVIN', 'MIRA']


def test_two_correct_calls_do_not_reorder_independent_following_turns(tmp_path):
    db = _project(tmp_path / 'already_correct', [
        (1, 'dialogue', '“Mira, cầm đèn nhé!”', 'TAVIN', 'male'),
        (2, 'dialogue', '“Được thôi.”', 'MIRA', 'female'),
        (3, 'dialogue', '“Tavin, tôi thấy cửa rồi!”', 'MIRA', 'female'),
        (4, 'dialogue', '“Tôi vẫn giữ đèn đây.”', 'MIRA', 'female'),
    ])
    assert _repair(db) == ['TAVIN', 'MIRA', 'MIRA', 'MIRA']


def test_a_call_at_the_head_or_tail_of_a_line_names_who_is_spoken_to() -> None:
    assert addressed_names("“Này Tavin, cậu đi đâu đấy?”", NAMES) == {"Tavin"}
    assert addressed_names("“Tavin, đợi đã!”", NAMES) == {"Tavin"}
    assert addressed_names("“Nghĩ lắm mệt đầu ra, Tavin.”", NAMES) == {"Tavin"}
    assert addressed_names("“Tavin ơi, ăn cơm thôi.”", NAMES) == {"Tavin"}
    assert addressed_names("“Cảm ơn Neravi nhiều lắm.”", NAMES) == {"Neravi"}
    # Kính ngữ: không ai tự gọi mình "-san", ở đâu trong câu cũng thế, kể cả câu tự giới thiệu.
    assert addressed_names("“Chắc Neravi-san sẽ thấy nóng hơn.”", NAMES) == {"Neravi"}


def test_a_name_that_is_only_mentioned_is_not_a_call() -> None:
    # A third-person name between punctuation is mentioned rather than addressed.
    assert addressed_names('“Melvi và Tovra phụ trách hộp mực… Hmm? Melvi… Nerun cầm tờ phiếu nào?”', NAMES) == set()
    assert addressed_names("“Tavin đầu teo nên chắc không sao đâu.”", NAMES) == set()
    # Tự giới thiệu đọc đúng tên người nói; "gọi là X" là nói về cái tên.
    assert addressed_names('“Tôi là người giữ quầy tem mới mở, Melvor Neravi.”', NAMES) == set()
    assert addressed_names("“Ở đây ai cũng gọi là Tavin, cậu cứ thế mà gọi.”", NAMES) == set()
    assert addressed_names("“Tavin ơi.”", set()) == set()


def test_a_new_turn_is_an_opened_quote_a_dash_or_a_closed_previous_line() -> None:
    assert opens_a_new_turn('“Đẩy vào nhé.”', "“Ừ.”")
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


def test_an_address_orders_an_unattributed_two_person_run(tmp_path):
    db=_project(tmp_path/'direct',[(1,'dialogue','“Mira, bên này!”','MIRA','female'),(2,'dialogue','“Tôi còn bản đồ.”','TAVIN','male'),(3,'dialogue','“Đợi tôi gấp lại.”','TAVIN','male')])
    assert _repair(db)==['TAVIN','MIRA','TAVIN']


def test_explicit_speech_attribution_breaks_an_inferred_turn_run(tmp_path):
    db = _project(tmp_path / 'speech_tag', [
        (1, 'dialogue', '“Mira, bên này!”', 'MIRA', 'female'),
        (2, 'narration', 'Tavin nói:', 'NARRATOR', 'unknown'),
        (2, 'dialogue', '“Tôi còn cầm bản đồ.”', 'TAVIN', 'male'),
        (3, 'dialogue', '“Đợi tôi gấp nó lại.”', 'TAVIN', 'male'),
    ])
    assert _repair(db) == ['TAVIN', 'NARRATOR', 'TAVIN', 'TAVIN']


def test_a_name_answer_uses_the_previous_question_without_hiding_a_real_call(tmp_path):
    db = _project(tmp_path / 'name_answer', [
        (1, 'dialogue', '“Cậu tên là gì?”', 'Lino Venn', 'male'),
        (2, 'dialogue', '“Mira Solin. Còn cậu?”', 'Mira Solin', 'female'),
        (3, 'dialogue', '“Lino Venn. Rất hân hạnh.”', 'Lino Venn', 'male'),
    ])
    assert _repair(db) == ['Lino Venn', 'Mira Solin', 'Lino Venn']
    assert not is_name_answer(
        '“Không. Mira Solin, đừng hỏi nữa!”', previous_text='“Cậu tên là gì?”',
        names=frozenset({'Mira Solin'}),
    )
    assert not is_name_answer('“Mira, Mira Solin, tới đây!”')
    assert addressed_names('“Mira Solin, tới đây!”', {'Mira Solin'}) == {'Mira Solin'}


def test_a_relatives_label_does_not_own_the_childs_name(tmp_path):
    db = _project(tmp_path / 'relative', [
        (1, 'dialogue', '“Cậu cần gì từ Mira à?”', 'Mẹ Mira', 'female'),
        (2, 'dialogue', '“Dạ, để cháu gọi cậu ấy.”', 'Lino Venn', 'male'),
        (3, 'narration', 'Cánh cửa mở ra.', 'NARRATOR', 'unknown'),
        (4, 'dialogue', '“Có chuyện gì vậy?”', 'Mira', 'female'),
    ])
    assert _repair(db) == ['Mẹ Mira', 'Lino Venn', 'NARRATOR', 'Mira']


def test_an_exchange_without_a_call_or_with_a_third_voice_is_left_alone(tmp_path: Path) -> None:
    no_call = _project(tmp_path / "a", [
        (1, "dialogue", "“Cậu về rồi à?”", "TAVIN", "male"),
        (2, "dialogue", "“Ừ, vừa về.”", "TAVIN", "male"),
        (3, "dialogue", "“Vậy ăn cơm luôn nhé.”", "NERAVI", "female"),
    ])
    assert _repair(no_call) == ["TAVIN", "TAVIN", "NERAVI"]
    # Ba người trong chuỗi: không biết ai xen kẽ với ai; câu gọi Tavin cũng không có người đối thoại DUY NHẤT.
    three = _project(tmp_path / "c", [
        (1, "dialogue", "“Tavin, cậu về rồi à?”", "TAVIN", "male"),
        (2, "dialogue", "“Ừ, vừa về.”", "NERAVI", "female"),
        (3, "dialogue", "“Ăn cơm thôi.”", "MELVOR", "male"),
    ])
    assert _repair(three) == ["TAVIN", "NERAVI", "MELVOR"]


def test_a_lone_line_that_calls_its_own_speaker_goes_to_the_one_partner(tmp_path: Path) -> None:
    db = _project(tmp_path / "a", [
        (1, "dialogue", "“Ăn cơm chưa?”", "NERAVI", "female"),
        (2, "narration", "Cô quay sang cậu.", "NARRATOR", "unknown"),
        (3, "dialogue", "“Này Tavin, trả lời đi chứ.”", "TAVIN", "male"),
        (4, "thought", "(Tavin ơi là Tavin.)", "TAVIN", "male"),
    ])
    # Nội tâm không đụng tới; câu thoại về người đối thoại duy nhất quanh đó.
    assert _repair(db) == ["NERAVI", "NARRATOR", "NERAVI", "TAVIN"]


def test_a_name_inside_a_descriptive_label_is_someone_else(tmp_path: Path) -> None:
    # "Bạn của Mirva" gọi Mirva là đúng vai: tên trong nhãn mô tả là người khác, không phải người nói.
    db = _project(tmp_path / "a", [
        (1, "dialogue", "“Mirva-chan, cậu đang kiểm hộp mực tím à?”", "Bạn của Mirva", "female"),
        (2, "narration", "Mirva giật mình.", "NARRATOR", "unknown"),
        (3, "dialogue", "“À, không có gì.”", "MIRVA", "female"),
    ])
    assert _repair(db) == ["Bạn của Mirva", "NARRATOR", "MIRVA"]


def test_a_lone_line_with_two_possible_partners_is_left_alone(tmp_path: Path) -> None:
    db = _project(tmp_path / "a", [
        (1, "dialogue", "“Ăn cơm chưa?”", "NERAVI", "female"),
        (2, "narration", "Melvor cười.", "NARRATOR", "unknown"),
        (3, "dialogue", "“Này Tavin, trả lời đi chứ.”", "TAVIN", "male"),
        (4, "narration", "Cả hai nhìn cậu.", "NARRATOR", "unknown"),
        (5, "dialogue", "“Thôi kệ cậu ta.”", "MELVOR", "male"),
    ])
    assert _repair(db) == ["NERAVI", "NARRATOR", "TAVIN", "NARRATOR", "MELVOR"]


def test_a_name_after_a_dash_at_the_end_of_a_line_is_the_speaker_tag_not_a_call() -> None:
    # Self-written examples keep the trailing dash speaker tag distinct from a vocative.
    assert addressed_names("“Cậu lắp hộp mực nào vậy? –Velna.”", {"Velna"}) == set()
    assert addressed_names("-Cậu cất hộp mực tím chưa? –Velna", {"Velna", "Tavin"}) == set()
    assert addressed_names("“Cậu kiểm hộp mực tím nhé. — Tovren”", {"Tovren"}) == set()
    # Vẫn là tiếng gọi: gạch không đứng trước tên cuối câu, tên đầu dòng sau gạch, gạch dính chữ ("S-Suvra").
    assert addressed_names("“Đi đi, Velna.”", {"Velna"}) == {"Velna"}
    assert addressed_names("“Velna, đi đâu đấy?”", {"Velna"}) == {"Velna"}
    assert addressed_names("– Velna.", {"Velna"}) == {"Velna"}
    assert addressed_names("“Cảm ơn nhé–Velna”", {"Velna"}) == {"Velna"}


def test_a_line_tagged_with_its_speaker_by_a_dash_keeps_its_speaker(tmp_path: Path) -> None:
    lines = [
        (1, "dialogue", "-Cậu cất hộp mực tím chưa? –Velna.", "VELNA", "female"),
        (2, "narration", "Tavren nhấc khay giấy.", "NARRATOR", "unknown"),
        (3, "dialogue", "-Tôi đang lau khay giấy. –Tavren.", "TAVREN", "male"),
    ]
    assert _repair(_project(tmp_path / "a", lines)) == ["VELNA", "NARRATOR", "TAVREN"]
    # Không có gạch: "Velna." cuối câu là tiếng gọi, câu về người đối thoại duy nhất.
    called = [(p, k, text.replace(" –Velna.", " Velna.").replace(" –Tavren.", " Tavren."), s, g) for p, k, text, s, g in lines]
    assert _repair(_project(tmp_path / "b", called)) == ["TAVREN", "NARRATOR", "VELNA"]
