"""Câu hỏi "'Tôi' là ai?" lúc tạo sách: máy nhận ra truyện kể ngôi thứ nhất, gợi ý tên, và lưu câu trả lời - 2026-09-27.

Trên chương ngôi thứ nhất YMP 248 model đúng 34% người nói khi không biết "tôi" là ai, 89% khi biết
(test_a_first_person_book_names_its_narrator_to_the_model.py). Đo trên kho: truyện ngôi thứ nhất có 34-58% đoạn lời kể
chứa "tôi/tớ/mình", ngôi thứ ba 7-23% - "mình" phản thân ("cảm xúc của mình") không được tính, nó đầy ở ngôi thứ ba.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ebook_reader.first_person import first_person_hint
from ebook_reader.webui import actions

FIRST_PERSON = (
    "Tôi bước vào lớp học. Tôi nhìn quanh một lượt.\n\n"
    "“Samael, cậu đến muộn rồi,” Juliana nói.\n\n"
    "Tôi nhún vai rồi ngồi xuống.\n\n"
    "“Samael, trả lời đi,” Vince nói.\n\n"
    "Tôi không đáp.\n\n"
    "“Thôi được rồi, Samael.”\n\n"
    "Tôi mở sách ra.\n"
)
THIRD_PERSON = (
    "Tamaki bước vào lớp học. Cô kìm nén cảm xúc của mình.\n\n"
    "“Tamaki, cậu đến muộn rồi,” Iruka nói.\n\n"
    "Tamaki nhún vai rồi ngồi xuống, tự nhủ với bản thân của mình.\n\n"
    "Iruka lắc đầu.\n"
)


def _chapters(folder: Path, text: str, count: int = 3) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for index in range(1, count + 1):
        path = folder / f"{index:03d}.txt"
        path.write_text(text, encoding="utf-8")
        paths.append(path)
    return paths


def test_a_first_person_book_is_recognised_and_its_narrator_suggested(tmp_path: Path) -> None:
    hint = first_person_hint(_chapters(tmp_path / "ymp", FIRST_PERSON))

    assert hint["firstPerson"] is True
    assert hint["rate"] >= 0.3
    assert hint["suggestions"][0] == "Samael"


def test_reflexive_minh_does_not_make_a_third_person_book_first_person(tmp_path: Path) -> None:
    hint = first_person_hint(_chapters(tmp_path / "yamiyo", THIRD_PERSON))

    assert hint["firstPerson"] is False
    assert hint["rate"] == 0.0


def test_the_answer_is_saved_as_the_books_first_person_identity(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _chapters(source, FIRST_PERSON, count=2)

    root = actions.create_book(tmp_path / "library", [str(source)], "Thử", "balanced", "", "  Samael ")

    settings = json.loads((root / "book_settings.json").read_text(encoding="utf-8"))
    assert settings["voices"]["first_person_identity"] == "Samael"


def test_a_third_person_book_gets_no_identity(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _chapters(source, THIRD_PERSON, count=2)

    root = actions.create_book(tmp_path / "library", [str(source)], "Thử", "balanced", "", "")

    settings = json.loads((root / "book_settings.json").read_text(encoding="utf-8"))
    assert "first_person_identity" not in settings["voices"]


def test_a_pronoun_is_refused_as_the_narrator(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _chapters(source, FIRST_PERSON, count=2)

    with pytest.raises(ValueError, match="đại từ"):
        actions.create_book(tmp_path / "library", [str(source)], "Thử", "balanced", "", "tôi")
