"""Chữ nói lắp ("K-khoan", "X-xin", "H-Hinohara") đọc bằng luật nói lắp, không bị gửi đi phiên âm như một tên riêng (hand18 24-11: "X-xin" bị khoá
"Ếch xin", "S-san" "Ét san", "H-Hinohara" "Ết Hi-nô-ha-ra", "Kh-Kh-Khoan" giữ nguyên chữ Anh). Chữ hiển thị không đổi."""
from __future__ import annotations

import pytest

from abook.analysis import _name_candidate_contexts
from abook.readaloud import stutter, vieneu


def _candidates(*texts: str) -> set[str]:
    rows = [{"speaker": "NARRATOR", "text": text, "kind": "narration"} for text in texts]
    return {str(c["surface"]) for c in _name_candidate_contexts(rows)}


@pytest.mark.parametrize("token, prefixes, word", [
    ("K-khoan", ["K"], "khoan"),
    ("X-xin", ["X"], "xin"),
    ("X-Xin", ["X"], "Xin"),
    ("H-Hinohara", ["H"], "Hinohara"),
    ("K-K-khoan", ["K", "K"], "khoan"),
    ("Kh-Kh-Khoan", ["Kh", "Kh"], "Khoan"),
    ("Ng-ngài", ["Ng"], "ngài"),
    ("T–tôi", ["T"], "tôi"),
    ("S-senpai", ["S"], "senpai"),
    ("Hi-Himuro-kun", ["Hi"], "Himuro-kun"),
])
def test_a_stutter_is_letters_then_the_word_they_start(token: str, prefixes: list[str], word: str) -> None:
    assert stutter.split(token) == (prefixes, word)
    assert stutter.word(token) == word


@pytest.mark.parametrize("token", [
    "X-quang", "A-đam", "e-mail", "T-shirt", "B-52", "Wi-Fi",  # từ ghép / mã thật: phần sau không mở đầu bằng tiền tố
    "Ha-ha", "Hi-hi",  # tiếng cười: lặp cả chữ
    "S-san", "Sa-san", "K-kun", "Ch-chan", "S-sama",  # biệt danh viết tắt + kính ngữ không đứng riêng (hoshizora: "đi với S-san")
    "Khoan", "khoan", "Hinohara",
])
def test_compounds_codes_laughter_and_initial_nicknames_are_not_stutters(token: str) -> None:
    assert stutter.split(token) is None
    assert stutter.word(token) == token


def test_a_stutter_is_never_sent_off_as_a_name() -> None:
    assert _candidates("“K-khoan đã!”", "“X-xin lỗi.”", "“X-Xin lỗi.”", "Kh-Kh-Khoan!", "“K-K-khoan!”") == set()


def test_a_stuttered_name_still_counts_as_that_name() -> None:
    assert _candidates("H-Hinohara đứng đó.", "“H-Hinohara!”") == {"Hinohara"}


def test_an_initial_with_an_honorific_is_still_a_name_candidate() -> None:
    assert _candidates("Mình sẽ ra ngoài cùng với S-san vào ngày mai.", "“S-san là cậu sao?”") == {"S-san"}


@pytest.mark.parametrize("text, said", [
    ("K-khoan đã!", ["khoan… khoan", "đã!"]),
    ("X-xin lỗi", ["xin… xin", "lỗi"]),
    ("X-Xin lỗi", ["xin… Xin", "lỗi"]),
    ("K-K-khoan", ["khoan… khoan… khoan"]),
    ("Kh-Kh-Khoan", ["khoan… khoan… Khoan"]),
])
def test_a_stutter_repeats_the_first_syllable_of_the_word(text: str, said: list[str]) -> None:
    # Nghe máy 24-11: lặp âm tiết ("khoan… khoan") hơn lặp phụ âm + "ờ" ("khờ… khoan" - "khờ", "chờ", "nhờ" là từ có nghĩa).
    assert vieneu.spoken_tokens(text.split()) == said


@pytest.mark.parametrize("text", ["S-san", "K-kun", "X-quang", "A-đam", "T-shirt", "B-52"])
def test_no_stutter_sound_where_there_is_no_stutter(text: str) -> None:
    assert "…" not in vieneu.spoken_tokens([text])[0]


def test_a_stuttered_japanese_name_repeats_its_first_syllable() -> None:
    assert vieneu.spoken_tokens(["H-Hinohara"], "ja") == ["hi… Hi-nô-ha-ra"]


def test_a_foreign_word_written_in_one_piece_keeps_the_consonant_sound() -> None:
    # Không tách được âm tiết ("Hinohara" ngoài cuốn gốc Nhật): lặp cả chữ thì dài và lạ.
    assert vieneu.spoken_tokens(["H-Hinohara"]) == ["hờ… Hinohara"]


def test_the_stutter_rule_is_in_both_pipeline_fingerprints() -> None:
    # Nó quyết định cả chữ đem đọc lẫn ứng viên tên: đổi nó là đổi audio và sổ cách đọc.
    from abook.quality_policy import ANALYSIS_CASTING_IMPLEMENTATION_FILES, QUALITY_IMPLEMENTATION_FILES

    assert "readaloud/stutter.py" in QUALITY_IMPLEMENTATION_FILES
    assert "readaloud/stutter.py" in ANALYSIS_CASTING_IMPLEMENTATION_FILES
