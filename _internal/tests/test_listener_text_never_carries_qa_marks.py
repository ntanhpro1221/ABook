"""Internal marks (QA verdicts, line ids, machine codes, raw local-role labels) never reach text a listener sees.

Owner rule 15-11: a shipped book showed "Cần nghe lại" as the subtitle of six chapters. Every package goes through `seal`,
which refuses listener-visible text carrying such a mark. QA state (qualityPassed, qualityWarning, failedLines, levelQa) and other
internal fields belong to the project only (owner ruling 15-11): book.json is whitelisted, export drops the rest, seal refuses it.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from abook.webui import bookfile


def _book(**chapter) -> dict:
    return {"title": "Sách thử", "narrator": "Giọng A", "cover": None,
            "chapters": [{"id": 1, "index": 1, "title": "Chương 1", "subtitle": "", "fullTitle": "Chương 1",
                          "file": "chapters/1.mp3", **chapter}]}


def test_clean_listener_text_passes() -> None:
    cast = {"narrator": {"voice": "Giọng A", "chapterVoices": [{"voice": "Giọng B", "chapters": [{"id": 1, "title": "Chương 1"}]}],
                         "exceptChapters": [{"id": 1, "title": "Chương 1"}]},
            "characters": [{"name": "NPC_LOCAL::c00001::bác gác", "displayName": "Bác gác", "firstChapter": "Chương 1",
                            "gender": "Nam", "age": "Người lớn"}], "extras": [], "carried": []}
    assert bookfile.listener_text_problems(_book(), cast) == []


@pytest.mark.parametrize("field, value", [
    ("subtitle", "Cần nghe lại"),
    ("subtitle", "Lần gặp đầu · Cần nghe lại"),
    ("fullTitle", "Chương 1 · Cần thu lại"),
    ("title", "Chương 1 c00001_s0002"),
    ("subtitle", "TTS_PACE_OUTLIER"),
])
def test_a_mark_in_a_chapter_title_is_found(field: str, value: str) -> None:
    assert bookfile.listener_text_problems(_book(**{field: value}), None) == [f"chapters[1].{field}: {value}"]


def test_a_mark_in_the_cast_is_found() -> None:
    cast = {"narrator": {"voice": "Giọng A", "exceptChapters": [{"id": 1, "title": "Chương 1 · Cần nghe lại"}]},
            "characters": [], "extras": [{"name": "x", "displayName": "NPC_LOCAL::c00001::bác gác"}], "carried": []}
    assert len(bookfile.listener_text_problems(_book(), cast)) == 2


def test_seal_refuses_a_package_whose_listener_text_carries_a_mark(tmp_path: Path) -> None:
    with pytest.raises(bookfile.BookFileError, match="dấu nội bộ"):
        bookfile.seal(_book(subtitle="Cần nghe lại"), {"chapters/1.mp3": b"audio"}, tmp_path / "x.abook",
                      producer="test", version=1)
    assert not (tmp_path / "x.abook").exists()


def test_the_npc_mark_is_identity_in_data_but_never_shown() -> None:
    """"NPC X" stays the key (`name`, used to match lines) but the shown name is "X" (humanize.person_name)."""
    from abook.webui.humanize import person_name

    assert [person_name(name) for name in ("NPC Bà Lão Bán Hoa", "NPC_BÁC_GÁC", "Npc: cô gái")] == ["Bà Lão Bán Hoa", "Bác Gác", "cô gái"]
    cast = {"narrator": {"voice": "Giọng A"}, "characters": [],
            "extras": [{"name": "NPC Bà Lão Bán Hoa", "displayName": "Bà Lão Bán Hoa"}], "carried": []}
    assert bookfile.listener_text_problems(_book(), cast) == []
    cast["extras"][0]["displayName"] = "NPC Bà Lão Bán Hoa"
    assert bookfile.listener_text_problems(_book(), cast) == ["cast.extras.displayName: NPC Bà Lão Bán Hoa"]
    assert bookfile.listener_text_problems({**_book(), "title": "Tôi chuyển sinh thành NPC"}, None) == [], "chữ NPC trong tên sách là chữ thật"


def test_seal_refuses_a_script_line_whose_speaker_shows_a_mark(tmp_path: Path) -> None:
    script = '{"segments": [{"speaker": "Bà Lão"}, {"speaker": "NPC Bà Lão Bán Hoa"}]}'.encode()
    assert bookfile.script_speaker_problems("scripts/1.json", script) == ["scripts/1.json.speaker: NPC Bà Lão Bán Hoa"]
    assert bookfile.script_speaker_problems("scripts/1.json", '{"segments": [{"speaker": "An \\"Cáo\\""}]}'.encode()) == []
    with pytest.raises(bookfile.BookFileError, match="dấu nội bộ"):
        bookfile.seal(_book(), {"chapters/1.mp3": b"audio", "scripts/1.json": script}, tmp_path / "x.abook", producer="test", version=1)
    assert not (tmp_path / "x.abook").exists()


QA_FIELDS = [
    ("chapters", "qualityPassed", False), ("chapters", "qualityWarning", "Cần nghe lại: c00001_s0002"),
    ("chapters", "failedLines", [{"id": 2, "reason": "failed"}]), ("book", "levelQa", {"chapters": []}),
    ("expected", "qualityPassed", False), ("expected", "failedLines", []), ("volume", "qualityWarning", ""),
]


def _with(where: str, key: str, value) -> dict:
    book = _book()
    book["audioCoverage"] = {"expected": [{"id": 1, "title": "Chương 1", "audioSha256": None, "segments": []}], "missing": [],
                             "partial": False}
    book["volumes"] = [{"id": 1, "number": 1, "title": "Quyển 1", "cover": None,
                        "chapters": [{"id": 1, "index": 1, "title": "Chương 1"}]}]
    target = {"book": book, "chapters": book["chapters"][0], "expected": book["audioCoverage"]["expected"][0],
              "volume": book["volumes"][0]["chapters"][0]}[where]
    target[key] = value
    return book


@pytest.mark.parametrize("where, key, value", QA_FIELDS)
def test_qa_state_is_not_a_package_field(where: str, key: str, value, tmp_path: Path) -> None:
    """Even an empty or passing QA field is refused: listeners never need it, so the whitelist leaves it out."""
    book = _with(where, key, value)
    assert bookfile.package_field_problems(book) and all(problem.endswith("." + key) for problem in bookfile.package_field_problems(book))
    with pytest.raises(bookfile.BookFileError, match="QA / nội bộ"):
        bookfile.seal(book, {"chapters/1.mp3": b"audio"}, tmp_path / "x.abook", producer="test", version=1)
    assert not (tmp_path / "x.abook").exists()
    stripped = bookfile.listener_book(book)
    assert bookfile.package_field_problems(stripped) == []
    assert stripped["chapters"][0]["title"] == "Chương 1" and stripped["audioCoverage"]["expected"][0]["id"] == 1


def test_a_clean_book_passes_the_whitelist(tmp_path: Path) -> None:
    book = _with("book", "author", "Tác giả thử")
    assert bookfile.package_field_problems(book) == []
    bookfile.seal(book, {"chapters/1.mp3": b"audio"}, tmp_path / "x.abook", producer="test", version=1)
    assert (tmp_path / "x.abook").is_file()


def test_no_reader_takes_qa_state_from_a_package() -> None:
    """Python, Android, web and Qt sources never read the QA fields: they come from the project (store.chapters) or nowhere."""
    root = Path(__file__).resolve().parents[1]
    readers = [path for pattern in ("abook/**/*.py", "mobile/android/app/src/main/**/*.kt", "ui/src/**/*.ts", "ui/src/**/*.tsx",
                                    "desktop_qt/**/*.qml", "desktop_qt/**/*.cpp")
               for path in root.glob(pattern) if "node_modules" not in path.parts]
    assert len(readers) > 100
    for path in readers:
        text = path.read_text(encoding="utf-8", errors="replace")
        for field in ("qualityPassed", "qualityWarning", "failedLines", "levelQa"):
            assert f'"{field}"' not in text and f"'{field}'" not in text and f".{field}" not in text, f"{path.name} đọc {field}"
