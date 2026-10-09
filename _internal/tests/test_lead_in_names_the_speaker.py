"""Lời dẫn nêu tên người nói: đoạn kể ngay sau câu thoại mở đầu bằng "Shizuka đáp, ..." (hoặc ngay trước, kết bằng dấu hai chấm)
cho biết ai nói câu thoại ấy (`first_person.lead_in_speaker`, `character_registry._repair_dialogue_turns_by_lead_in`).

Chỉ động từ NÓI: "Eun nhe răng cười" hay "Add trả lời rồi đứng dậy" đứng sau lời của người KHÁC (phản ứng của người nghe) - soát tay
mẫu quét nhiều truyện thấy chúng lật cả chuỗi lượt, nên không tính.
"""
from __future__ import annotations

from pathlib import Path

from abook.character_registry import _repair_dialogue_turns_by_lead_in
from abook.database import ProjectDB
from abook.first_person import introduced_names, lead_in_speaker
from test_nobody_calls_their_own_name import _project

NAMES = {"Kou", "Shizuka", "Sanae"}


def test_a_lead_in_names_who_speaks_the_line_before_it() -> None:
    assert lead_in_speaker("Shizuka khẽ đáp, biểu cảm thất vọng.", NAMES, after=True) == "Shizuka"
    assert lead_in_speaker("- Sanae chen vào.", NAMES, after=True) == "Sanae"
    assert lead_in_speaker("Kou-kun hỏi lại một cách ngạc nhiên.", NAMES, after=True) == "Kou"
    # "Shizuka lên tiếng:" đứng trước câu thoại nó dẫn, không phải sau.
    assert lead_in_speaker("Shizuka lên tiếng:", NAMES, after=False) == "Shizuka"
    assert lead_in_speaker("Shizuka lên tiếng:", NAMES, after=True) is None
    assert lead_in_speaker("Kou đang nói chuyện nghiêm nghị, nhận ra ánh nhìn bối rối.", NAMES, after=True) is None
    # Tên là người bị vẫy chứ không phải chủ ngữ của "bảo rằng:".
    assert lead_in_speaker("Trên xe có một người cầm quạt lông, vẫy Kou bảo rằng:", NAMES, after=False) is None
    assert lead_in_speaker("Trên xe có một người cầm quạt lông. Kou bảo rằng:", NAMES, after=False) == "Kou"


def test_gestures_replies_negations_and_other_subjects_are_not_a_lead_in() -> None:
    # Phản ứng của người nghe, không phải người nói.
    assert lead_in_speaker("Shizuka nhe răng cười.", NAMES, after=True) is None
    assert lead_in_speaker("Kou trả lời rồi đứng dậy.", NAMES, after=True) is None
    assert lead_in_speaker("Sanae nhìn tôi chằm chằm.", NAMES, after=True) is None
    assert lead_in_speaker("Shizuka nhắm mắt không nói gì.", NAMES, after=True) is None
    # Người kể không tên, hay tên không phải chủ ngữ đứng đầu đoạn kể.
    assert lead_in_speaker("Tôi hỏi lại.", NAMES, after=True) is None
    assert lead_in_speaker("Cô ấy nói với Kou rằng trời sắp mưa.", NAMES, after=True) is None
    assert lead_in_speaker("Kou", set(), after=True) is None
    # Nghĩ thầm, đáp lại người khác bằng cử chỉ, hay đoạn kể dài dẫn sang câu thoại KẾ TIẾP: không phải người nói câu vừa xong.
    assert lead_in_speaker("Kou tự hỏi, không biết mình có nên diễn một vở opera.", NAMES, after=True) is None
    assert lead_in_speaker("Sanae chỉ đáp lại lời Kou bằng ánh mắt sắc lạnh.", NAMES, after=True) is None
    assert lead_in_speaker("Shizuka nói mà không rõ đang mắng ai; nhìn Kou nghi hoặc.", NAMES, after=True) is None
    assert lead_in_speaker("Shizuka lên tiếng:", NAMES, after=True) is None


def test_a_self_introduction_names_the_speaker() -> None:
    assert introduced_names("“Tôi là Lancel Dante.”", {"Lancel", "Karin"}) == {"Lancel"}
    assert introduced_names("“Tên tôi là Karin, rất vui được gặp.”", {"Lancel", "Karin"}) == {"Karin"}
    assert introduced_names("“Cậu là Lancel à?”", {"Lancel", "Karin"}) == set()


def _repair(db: ProjectDB, aliases: dict[str, set[str]] | None = None) -> list[str]:
    _repair_dialogue_turns_by_lead_in(db, lambda _message: None, aliases or {})
    return [str(row["speaker"]) for row in sorted(db.list_segments(), key=lambda row: int(row["seq"]))]


def test_a_line_followed_by_a_lead_in_goes_to_the_named_speaker(tmp_path: Path) -> None:
    db = _project(tmp_path / "a", [
        (1, "dialogue", "“Ăn cơm chưa?”", "SHIZUKA", "female"),
        (2, "dialogue", "“Chưa, tớ vừa về.”", "KOU", "male"),
        (3, "dialogue", "“Vậy đi ăn thôi.”", "KOU", "male"),
        (4, "narration", "Shizuka khẽ đáp.", "NARRATOR", "unknown"),
    ])
    # Câu 3 của Shizuka theo lời dẫn; câu 1-3 liền nhau nên xen kẽ SHIZUKA-KOU-SHIZUKA (câu 1 vốn đúng).
    assert _repair(db) == ["SHIZUKA", "KOU", "SHIZUKA", "NARRATOR"]
    assert {str(row["speaker"]): str(row["gender"]) for row in db.list_segments() if str(row["kind"]) == "dialogue"} == {
        "SHIZUKA": "female", "KOU": "male",
    }


def test_a_lead_in_before_the_line_also_names_the_speaker(tmp_path: Path) -> None:
    db = _project(tmp_path / "a", [
        (1, "dialogue", "“Ăn cơm chưa?”", "SHIZUKA", "female"),
        (2, "dialogue", "“Ừ, rồi.”", "KOU", "male"),
        (3, "narration", "Cô quay sang cậu.", "NARRATOR", "unknown"),
        (4, "narration", "Kou lên tiếng:", "NARRATOR", "unknown"),
        (5, "dialogue", "“Chưa, tớ vừa về.”", "SHIZUKA", "female"),
    ])
    assert _repair(db) == ["SHIZUKA", "KOU", "NARRATOR", "NARRATOR", "KOU"]


def test_a_whole_exchange_is_ordered_around_the_line_with_a_lead_in(tmp_path: Path) -> None:
    # Model gán cả chuỗi cho Kou; chỉ có lời dẫn ở câu cuối. Bốn câu liền nhau xen kẽ KOU-SHIZUKA-KOU-SHIZUKA.
    db = _project(tmp_path / "a", [
        (1, "dialogue", "“Ăn cơm chưa?”", "SHIZUKA", "female"),
        (2, "narration", "Cô quay sang cậu.", "NARRATOR", "unknown"),
        (3, "dialogue", "“Chưa, tớ vừa về.”", "KOU", "male"),
        (4, "dialogue", "“Vậy đi ăn thôi.”", "KOU", "male"),
        (5, "dialogue", "“Ừ, đi nào.”", "KOU", "male"),
        (6, "dialogue", "“Hôm nay cậu chọn quán đi.”", "KOU", "male"),
        (7, "narration", "Shizuka đáp.", "NARRATOR", "unknown"),
    ])
    assert _repair(db) == ["SHIZUKA", "NARRATOR", "KOU", "SHIZUKA", "KOU", "SHIZUKA", "NARRATOR"]


def test_a_reaction_a_call_or_a_self_introduction_leaves_the_line_alone(tmp_path: Path) -> None:
    reaction = _project(tmp_path / "a", [
        (1, "dialogue", "“Ăn cơm chưa?”", "SHIZUKA", "female"),
        (2, "dialogue", "“Chưa, tớ vừa về.”", "KOU", "male"),
        (3, "narration", "Shizuka nhe răng cười.", "NARRATOR", "unknown"),
    ])
    assert _repair(reaction) == ["SHIZUKA", "KOU", "NARRATOR"]
    # Câu gọi Shizuka thì không phải Shizuka nói, kể cả khi lời dẫn đứng sau nó nêu Shizuka.
    call = _project(tmp_path / "b", [
        (1, "dialogue", "“Ăn cơm chưa?”", "SHIZUKA", "female"),
        (2, "narration", "Cô quay sang cậu.", "NARRATOR", "unknown"),
        (3, "dialogue", "“Này Shizuka, chưa đâu.”", "KOU", "male"),
        (4, "narration", "Shizuka đáp.", "NARRATOR", "unknown"),
    ])
    assert _repair(call) == ["SHIZUKA", "NARRATOR", "KOU", "NARRATOR"]
    intro = _project(tmp_path / "c", [
        (1, "dialogue", "“Ăn cơm chưa?”", "SHIZUKA", "female"),
        (2, "narration", "Cô quay sang cậu.", "NARRATOR", "unknown"),
        (3, "dialogue", "“Tôi là Kou, vừa mới chuyển đến.”", "KOU", "male"),
        (4, "narration", "Shizuka đáp.", "NARRATOR", "unknown"),
    ])
    assert _repair(intro) == ["SHIZUKA", "NARRATOR", "KOU", "NARRATOR"]


def test_a_run_the_model_gave_to_one_person_is_not_reordered_when_the_lead_in_agrees(tmp_path: Path) -> None:
    # Lời độc thoại tách thành nhiều đoạn mở ngoặc riêng: nhãn cùng một người và lời dẫn nêu đúng người ấy - không có gì để sửa.
    db = _project(tmp_path / "a", [
        (1, "dialogue", "“Ăn cơm chưa?”", "SHIZUKA", "female"),
        (2, "narration", "Cô quay sang cậu.", "NARRATOR", "unknown"),
        (3, "dialogue", "“Cậu không hề yếu đuối.”", "KOU", "male"),
        (4, "dialogue", "“Tôi thích điểm đó của cậu.”", "KOU", "male"),
        (5, "dialogue", "“Vì vậy hãy ngẩng cao đầu lên.”", "KOU", "male"),
        (6, "narration", "Kou nói.", "NARRATOR", "unknown"),
    ])
    assert _repair(db) == ["SHIZUKA", "NARRATOR", "KOU", "KOU", "KOU", "NARRATOR"]


def test_an_exchange_with_a_third_voice_or_two_conflicting_lead_ins_is_not_reordered(tmp_path: Path) -> None:
    three = _project(tmp_path / "a", [
        (1, "dialogue", "“Ăn cơm chưa?”", "SHIZUKA", "female"),
        (2, "dialogue", "“Chưa, tớ vừa về.”", "KOU", "male"),
        (3, "dialogue", "“Vậy đi ăn thôi.”", "KENJI", "male"),
        (4, "dialogue", "“Ừ, đi nào.”", "KOU", "male"),
        (5, "narration", "Shizuka đáp.", "NARRATOR", "unknown"),
    ])
    # Chỉ câu 4 đổi (câu có lời dẫn rõ ràng); chuỗi ba người không bị xếp lại.
    assert _repair(three) == ["SHIZUKA", "KOU", "KENJI", "SHIZUKA", "NARRATOR"]
    # Hai lời dẫn trong một chuỗi mâu thuẫn với thứ tự xen kẽ (cùng nêu Kou cho hai câu liền nhau): từng câu theo lời dẫn,
    # chuỗi không bị xếp lại.
    conflict = _project(tmp_path / "b", [
        (1, "dialogue", "“Ăn cơm chưa?”", "SHIZUKA", "female"),
        (2, "narration", "Cô quay sang cậu.", "NARRATOR", "unknown"),
        (3, "narration", "Kou lên tiếng:", "NARRATOR", "unknown"),
        (4, "dialogue", "“Chưa, tớ vừa về.”", "SHIZUKA", "female"),
        (5, "dialogue", "“Vậy đi ăn thôi.”", "KOU", "male"),
        (6, "narration", "Kou đáp.", "NARRATOR", "unknown"),
    ])
    assert _repair(conflict) == ["SHIZUKA", "NARRATOR", "NARRATOR", "KOU", "KOU", "NARRATOR"]
