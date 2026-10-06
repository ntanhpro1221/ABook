"""Tiếng kêu trong ngoặc giữa câu kể, ngay sau lời dẫn nêu tên người kêu, giữ người nói model trả lời."""
from __future__ import annotations

from abook.analysis import _repair_in_sentence_quote_speakers
from abook.database import IN_SENTENCE_QUOTE_NARRATOR_NOTE


def row(stable_id: str, paragraph: int, text: str) -> dict[str, object]:
    return {"stable_id": stable_id, "chapter_id": 1, "paragraph_index": paragraph, "text": text}


def data(kind: str, speaker: str) -> dict[str, object]:
    return {"kind": kind, "speaker": speaker, "personality_hint": "", "notes": ""}


def repaired(lead_in: str, quoted: str, tail: str, speaker: str) -> dict[str, object]:
    group = [row("a", 5, lead_in), row("b", 5, quoted), row("c", 5, tail)]
    result = {"a": data("narration", "NARRATOR"), "b": data("dialogue", speaker),
              "c": data("narration", "NARRATOR")}
    _repair_in_sentence_quote_speakers(group, result)
    return result["b"]


def test_a_cry_after_a_lead_in_naming_its_speaker_keeps_that_speaker() -> None:
    # Hai thầy gán nhãn 06-10: “à” sau "X khẽ bật ra một tiếng" là của X, app từng ép về người kể.
    kept = repaired("Nói tới đây, Minami khẽ bật ra một tiếng", "“à”", ", rồi cúi mặt cười ngượng.", "Minami")
    assert kept["speaker"] == "Minami"
    assert "_host_note_markers" not in kept


def test_a_cry_after_a_speech_verb_keeps_a_speaker_named_by_part_of_the_label() -> None:
    kept = repaired("Cuối cùng Takeda thốt lên", "“hả”", "rồi đứng sững.", "Takeda Ren")
    assert kept["speaker"] == "Takeda Ren"


def test_a_capitalised_cry_split_from_its_tail_keeps_a_hyphenated_speaker() -> None:
    # Cùng lô thầy gán nhãn: lời dẫn "X kêu", tiếng kêu viết hoa, rồi "một tiếng rồi..." nối tiếp câu kể.
    kept = repaired("Nghe tôi nói vậy xong, Ji-woo kêu", '"Hừ"', "một tiếng rồi quay ngoắt đi.", "Ji-woo")
    assert kept["speaker"] == "Ji-woo"


def test_a_cry_whose_lead_in_names_someone_else_goes_back_to_the_narrator() -> None:
    narrated = repaired("Nói tới đây, Minami khẽ bật ra một tiếng", "“à”", ", rồi cúi mặt cười ngượng.", "Sora")
    assert narrated["speaker"] == "NARRATOR"
    assert IN_SENTENCE_QUOTE_NARRATOR_NOTE in narrated["_host_note_markers"]


def test_a_cry_without_a_sound_verb_before_it_goes_back_to_the_narrator() -> None:
    # Lời dẫn không dừng ở động từ phát ra tiếng: chữ người kể trích lại (đáp án chuẩn ghi NARRATOR cho dáng này).
    narrated = repaired("Minami chỉ khẽ", "“hừm”", "rồi quay đi.", "Minami")
    assert narrated["speaker"] == "NARRATOR"


def test_a_term_after_a_named_speech_verb_still_goes_back_to_the_narrator() -> None:
    narrated = repaired("Dù Minami nói", "“không sao”", "nhưng mặt cô tái đi.", "Minami")
    assert narrated["speaker"] == "NARRATOR"


def test_a_title_quoted_mid_sentence_still_goes_back_to_the_narrator() -> None:
    narrated = repaired("Cả làng gọi Minami là", "“Ma Vương”", "suốt ba năm liền.", "Minami")
    assert narrated["speaker"] == "NARRATOR"
