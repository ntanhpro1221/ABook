"""Lõi hai thẻ gợi ý người nói (`abook.speaker_suggestions`): cặp tên viết gần giống, và nhãn vô danh có thể là người có tên
cùng chương. Dữ liệu giả; số đo ở LLM_Train/runs/NAMEFORM_12-10.md và ANONREVEAL_12-10.md."""
from __future__ import annotations

from abook.speaker_suggestions import (
    AnonymousCandidate,
    NamePair,
    anonymous_speaker_candidates,
    name_pair_candidates,
    name_pair_similarity,
)


def test_two_spellings_of_one_name_make_a_pair() -> None:
    pairs = name_pair_candidates({"ARIA": 40, "Arya": 16, "HIMURO": 50})

    assert pairs == [NamePair(major="ARIA", minor="Arya", similarity=0.75)]


def test_names_that_differ_only_by_a_tone_mark_are_two_people() -> None:
    assert name_pair_similarity("QUÁCH-THẠCH-PHÙ", "QUÁCH-THẠCH-PHỦ") is None
    assert name_pair_similarity("Phạm Lãi", "Phạm Lại") is None
    # Khác hẳn một chữ thì vẫn hỏi (một trong 14 cặp hỏi nhầm đã đo trên 90 sách) - thẻ chỉ hỏi, không gộp.
    assert name_pair_similarity("HUỆ-CÔNG", "VỆ-CÔNG") is not None


def test_a_name_inside_the_other_is_left_to_the_alias_card() -> None:
    assert name_pair_similarity("THÂN", "THÂN-HẬU") is None
    assert name_pair_similarity("Lucien", "Lucien Evans") is None


def test_a_japanese_suffix_does_not_make_two_names_alike() -> None:
    assert name_pair_similarity("Krum-chan", "Rem-chan") is None
    # Cùng tên, chỉ khác đuôi: không phải "viết khác".
    assert name_pair_similarity("Moffle", "Moffle-san") is None


def test_short_names_are_not_compared() -> None:
    assert name_pair_similarity("BAO", "BÁ") is None
    assert name_pair_similarity("Ako", "Akou") is None


def test_names_of_known_different_genders_are_not_paired() -> None:
    assert name_pair_candidates({"ARIA": 40, "Arya": 16}, {"ARIA": "female", "Arya": "male"}) == []
    assert len(name_pair_candidates({"ARIA": 40, "Arya": 16}, {"ARIA": "female", "Arya": "unknown"})) == 1


def test_unnamed_and_reserved_labels_are_never_paired() -> None:
    counts = {"NARRATOR": 300, "NARRATORS": 2, "NPC_LOCAL::c1::r1::Arya": 5, "Aria": 9}
    assert name_pair_candidates(counts) == []


def _row(seq: int, paragraph: int, kind: str, speaker: str, text: str, chapter: int = 1, gender: str = "female",
         age: str = "adult") -> dict:
    return {"chapter_id": chapter, "seq": seq, "paragraph_index": paragraph, "kind": kind, "speaker": speaker, "text": text,
            "gender": gender, "age": age}


GIRL = "NPC_LOCAL::c1::r1::cô gái tóc đỏ"
GUARD = "NPC_LOCAL::c1::r2::lính gác"


def test_an_unnamed_speaker_is_offered_the_named_people_beside_their_lines() -> None:
    rows = [
        _row(1, 1, "narration", "NARRATOR", "Mira bước vào phòng, theo sau là Lena."),
        _row(2, 2, "dialogue", GIRL, "“Chào mọi người.”"),
        _row(3, 3, "dialogue", "MIRA", "“Lại muộn rồi.”"),
        _row(4, 4, "dialogue", "LENA", "“Xin lỗi.”"),
        _row(5, 5, "narration", "NARRATOR", "Mira lắc đầu."),
        _row(6, 6, "dialogue", GIRL, "“Bắt đầu thôi.”"),
    ]

    # Hai ứng viên, người được nhắc nhiều lần quanh câu hơn đứng trước; người dùng chọn, không gộp tự động.
    assert anonymous_speaker_candidates(rows) == [
        AnonymousCandidate(chapter_id=1, speaker=GIRL, lines=2, names=("MIRA", "LENA")),
    ]


def test_no_card_without_a_named_speaker_of_the_same_chapter_nearby() -> None:
    far = [
        _row(1, 1, "narration", "NARRATOR", "Mira đã đi từ sáng."),
        _row(2, 2, "dialogue", "MIRA", "“Tôi đi đây.”"),
        _row(3, 20, "dialogue", GIRL, "“Ai đấy?”"),
    ]
    assert anonymous_speaker_candidates(far) == []
    # Người được nhắc nhưng không nói câu nào DƯỚI TÊN trong chương: không có giọng thứ hai nào để gộp.
    silent = [
        _row(1, 1, "narration", "NARRATOR", "Mira đứng nhìn."),
        _row(2, 2, "dialogue", GIRL, "“Ai đấy?”"),
    ]
    assert anonymous_speaker_candidates(silent) == []


def test_a_named_speaker_of_another_gender_is_not_offered() -> None:
    rows = [
        _row(1, 1, "narration", "NARRATOR", "Ren đứng cạnh cửa."),
        _row(2, 2, "dialogue", "REN", "“Vào đi.”", gender="male"),
        _row(3, 3, "dialogue", GIRL, "“Cảm ơn.”", gender="female"),
    ]
    assert anonymous_speaker_candidates(rows) == []


def test_cards_are_ranked_by_lines_and_capped_per_chapter() -> None:
    rows = [_row(1, 1, "narration", "NARRATOR", "Mira và Lena chờ ở cổng."), _row(2, 2, "dialogue", "MIRA", "“Đi thôi.”")]
    labels = [f"NPC_LOCAL::c1::r{index}::người {index}" for index in range(5)]
    seq = 3
    for index, label in enumerate(labels):
        for _ in range(index + 1):  # người 4 nói nhiều câu nhất
            rows.append(_row(seq, 2, "dialogue", label, "“…”"))
            seq += 1

    cards = anonymous_speaker_candidates(rows, per_chapter=3)

    assert [card.speaker for card in cards] == [labels[4], labels[3], labels[2]]
    assert [card.lines for card in cards] == [5, 4, 3]
