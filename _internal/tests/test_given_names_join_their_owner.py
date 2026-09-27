"""Truyện Trung, Việt gọi người bằng tên (chữ cuối): "DU" là Chu Du, "THÁO" là Tào Tháo - một người, một giọng.

Đo 27-09 trên Tam quốc Hồi 50-52: cả ba model đều ghi "DU", "THÁO" cho hàng chục câu, nên người nghe nghe Chu Du bằng
hai giọng (scripts/model_eval/voice_identity.py, docs/ANALYSIS_RESEARCH.md "Một người một giọng").
"""
from __future__ import annotations

from pathlib import Path

from ebook_reader.character_registry import build_registry_and_cast, canonical_speaker_names, merge_given_names
from ebook_reader.config import build_settings
from tests.test_character_casting import _identity_db


def reps(*names: str) -> dict[str, str]:
    return {name.casefold(): name for name in names}


def test_a_given_name_joins_the_one_full_name_it_ends() -> None:
    assert merge_given_names(reps("DU", "CHU DU", "THÁO", "TÀO THÁO", "KHỔNG MINH")) == {
        "du": "CHU DU", "tháo": "TÀO THÁO"}


def test_two_full_names_with_that_ending_are_not_guessed() -> None:
    assert merge_given_names(reps("LONG", "PHÁO LONG", "TRIỆU LONG")) == {}


def test_european_names_end_in_a_family_name_and_stay_apart() -> None:
    # chữ cuối của tên kiểu Âu là họ chung của cả nhà: EVANS có thể là cha của LUCIEN EVANS
    assert merge_given_names(reps("EVANS", "LUCIEN EVANS", "LEO", "LEO CARTER")) == {}


def test_a_label_without_marks_matches_by_letters_but_marks_must_agree() -> None:
    assert merge_given_names(reps("VAN", "TRIỆU VÂN")) == {"van": "TRIỆU VÂN"}, "model rơi dấu"
    assert merge_given_names(reps("VÂN", "LÊ VĂN")) == {}, "vân và văn là hai tên"


def test_a_courtesy_name_with_a_hyphen_is_one_word() -> None:
    assert merge_given_names(reps("TỬ-LONG", "TRIỆU TỬ-LONG")) == {"tử-long": "TRIỆU TỬ-LONG"}


def test_a_wife_called_by_her_husbands_name_never_takes_his_voice() -> None:
    # Tắt đèn: "chị Dậu" là vợ anh Dậu. Chữ cuối của tên mở bằng chữ xưng hô có thể là tên của người khác.
    assert merge_given_names(reps("DẬU", "CHỊ DẬU")) == {}
    assert merge_given_names(reps("DẬU", "CHỊ DẬU", "NGUYỄN VĂN DẬU")) == {"dậu": "NGUYỄN VĂN DẬU"}
    assert merge_given_names(reps("CẢ", "BÁC CẢ", "DẦN", "MẸ DẦN")) == {}


def test_a_title_after_a_name_is_not_a_given_name() -> None:
    # "Trịnh lão" là ông lão họ Trịnh; một mình "LÃO" là ông lão nào đó, không phải tên riêng
    assert merge_given_names(reps("LÃO", "TRỊNH LÃO", "CA", "LÝ CA")) == {}


def test_the_whole_naming_pass_sends_every_label_of_a_person_to_one_name() -> None:
    names = canonical_speaker_names({"CHU DU": 3, "DU": 24, "Du": 2, "TÀO THÁO": 3, "THÁO": 17, "NARRATOR": 40}, "")
    assert {label: names[label] for label in ("CHU DU", "DU", "Du")} == {"CHU DU": "CHU DU", "DU": "CHU DU", "Du": "CHU DU"}
    assert names["THÁO"] == "TÀO THÁO" and "NARRATOR" not in names


def test_casting_gives_a_person_called_by_given_name_one_character_and_voice(tmp_path: Path) -> None:
    db = _identity_db(tmp_path, [("CHU DU", "male"), ("DU", "male"), ("DU", "male"), ("TÀO THÁO", "male"),
                                 ("THÁO", "male")])

    build_registry_and_cast(db, build_settings(), lambda _message: None)

    rows = db.list_segments()
    assert {str(row["speaker"]) for row in rows} == {"CHU DU", "TÀO THÁO"}
    for speaker in ("CHU DU", "TÀO THÁO"):
        speaker_rows = [row for row in rows if str(row["speaker"]) == speaker]
        assert len({int(row["canonical_character_id"]) for row in speaker_rows}) == 1
        assert len({int(row["voice_profile_id"]) for row in speaker_rows}) == 1
