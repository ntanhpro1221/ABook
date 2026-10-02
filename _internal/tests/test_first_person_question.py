"""Câu hỏi "'Tôi' là ai?" lúc tạo sách: máy nhận ra truyện kể ngôi thứ nhất, gợi ý tên, và lưu câu trả lời - 2026-09-27.

Trên chương ngôi thứ nhất YMP 248 model đúng 34% người nói khi không biết "tôi" là ai, 89% khi biết
(test_a_first_person_book_names_its_narrator_to_the_model.py). Đo trên kho: truyện ngôi thứ nhất có 34-58% đoạn lời kể
chứa "tôi/tớ/mình", ngôi thứ ba 7-23% - "mình" phản thân ("cảm xúc của mình") không được tính, nó đầy ở ngôi thứ ba.
29-09: đếm thêm THEO CHƯƠNG (>= 30% chương có >= 20% lời kể xưng "tôi") - tỉ lệ gộp bỏ sót HDST (29,6%) và Nageki (24,1%).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook.first_person import first_person_hint
from abook.webui import actions

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


def _chapter(first_person_lines: int, narration: int = 10) -> str:
    """Một chương `narration` đoạn lời kể, `first_person_lines` đoạn trong số đó xưng "tôi", xen lời thoại."""
    lines = []
    for index in range(narration):
        lines.append("Tôi đứng lặng nhìn ra cửa sổ." if index < first_person_lines else "Gió thổi qua hành lang dài.")
        lines.append("“Đi thôi.”")
    return "\n\n".join(lines) + "\n"


def _book(folder: Path, chapters: list[str]) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, text in enumerate(chapters, 1):
        path = folder / f"{index:03d}.txt"
        path.write_text(text, encoding="utf-8")
        paths.append(path)
    return paths


def test_a_first_person_book_with_third_person_interludes_is_still_recognised(tmp_path: Path) -> None:
    """Nageki (29-09): 12/20 chương kể "tôi" nhưng chen chương ngoại truyện ngôi ba - gộp cả cuốn chỉ 24% "tôi", dưới
    ngưỡng 30%, nên Studio từng không hỏi "Tôi là ai?" và cuốn chạy không có dòng người kể."""
    hint = first_person_hint(_book(tmp_path / "nageki", [_chapter(3)] * 6 + [_chapter(0)] * 4))

    assert hint["rate"] < 0.3
    assert hint["firstPerson"] is True
    assert (hint["chaptersWithI"], hint["chaptersSampled"]) == (6, 10)


def test_a_third_person_book_with_a_few_first_person_letters_is_not(tmp_path: Path) -> None:
    """Ngôi ba nhưng vài chương có thư/nhật ký xưng "tôi" (Đã bảo là cùng nhau tự sát: 3/20 chương)."""
    hint = first_person_hint(_book(tmp_path / "romcom", [_chapter(3)] * 2 + [_chapter(0)] * 8))

    assert hint["firstPerson"] is False
    assert hint["chaptersWithI"] == 2


def test_the_narrator_others_call_by_name_is_suggested_first(tmp_path: Path) -> None:
    """Yamiyo (29-09): "Tomobe" chỉ có trong lời người khác gọi, lời kể toàn "tôi" - trước đây không lọt 6 gợi ý, vì tên hay
    gặp nhất là những người được KỂ về ("Onizuki", "Soba")."""
    chapter = "\n\n".join(
        ["Onizuki bước vào, Onizuki ngồi xuống.", "Tôi nhìn theo Onizuki.", "“Chào anh, Tomobe.”",
         "Onizuki mỉm cười.", "“Đi thôi, Tomobe.”", "Tôi gật đầu với Onizuki."]
    ) + "\n"
    hint = first_person_hint(_book(tmp_path / "yamiyo", [chapter] * 3))

    assert hint["suggestions"][0] == "Tomobe"
    assert "Onizuki" in hint["suggestions"]


def test_short_chapters_are_not_counted_chapter_by_chapter(tmp_path: Path) -> None:
    hint = first_person_hint(_book(tmp_path / "short", [_chapter(1, narration=3)] * 5))

    assert hint["chaptersSampled"] == 0


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
