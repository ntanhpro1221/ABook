"""Internal marks (QA verdicts, line ids, machine codes, raw local-role labels) never reach text a listener sees.

Owner rule 15-11: a shipped book showed "Cần nghe lại" as the subtitle of six chapters. Every package goes through `seal`,
which refuses listener-visible text carrying such a mark. QA state (qualityPassed, qualityWarning, failedLines, levelQa) and other
internal fields belong to the project only (owner ruling 15-11): book.json is whitelisted, export drops the rest, seal refuses it.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from abook.webui import bookfile, projectfile


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
    with pytest.raises(bookfile.BookFileError, match="dấu kiểm tra nội bộ"):
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
    with pytest.raises(bookfile.BookFileError, match="dấu kiểm tra nội bộ"):
        bookfile.seal(_book(), {"chapters/1.mp3": b"audio", "scripts/1.json": script}, tmp_path / "x.abook", producer="test", version=1)
    assert not (tmp_path / "x.abook").exists()


@pytest.mark.parametrize("bad", [3, "voice", {"voice": "A"}])
def test_saving_a_malformed_cast_keeps_its_bytes_for_the_shared_error_state(bad) -> None:
    cast = {"narrator": {"chapterVoices": bad, "exceptChapters": bad}, "characters": bad, "extras": bad}
    data = bookfile.json_bytes(cast)
    files = {"cast.json": data}
    known = {"cast.json": {"size": len(data), "sha256": "verified"}}
    book = _book()
    bookfile.clean_listener_layer(book, files, known)
    assert files["cast.json"] == data and "cast.json" in known
    assert bookfile.listener_package_problems(book, files, files.__getitem__) == ([], [])


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
    with pytest.raises(bookfile.BookFileError, match="dấu kiểm tra nội bộ"):
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


SHARED = json.loads((Path(__file__).parent / "fixtures" / "book_files" / "listener_package_cases.json").read_text(encoding="utf-8"))


def shared_book(case: dict) -> dict:
    """`base` with the case's `patch` applied by dotted path (list indexes are numbers) - Kotlin ListenerPackageTest does the same."""
    book = copy.deepcopy(SHARED["base"])
    for path, value in (case.get("patch") or {}).items():
        *parents, last = path.split(".")
        target = book
        for step in parents:
            target = target[int(step)] if isinstance(target, list) else target[step]
        target[int(last) if isinstance(target, list) else last] = value
    return book


@pytest.mark.parametrize("case", SHARED["cases"], ids=[case["name"] for case in SHARED["cases"]])
def test_the_rules_shared_with_the_phone_packer(case: dict) -> None:
    """Same cases as Android ListenerPackageTest: the phone's BookDocumentWriter.seal refuses exactly what `seal` refuses."""
    files = {name: text.encode("utf-8") for name, text in (case.get("scripts") or {}).items()}
    if case.get("cast") is not None:
        files["cast.json"] = json.dumps(case["cast"], ensure_ascii=False).encode("utf-8")
    leaked, internal = bookfile.listener_package_problems(shared_book(case), files, files.__getitem__)
    assert (sorted(leaked), sorted(internal)) == (sorted(case["leaked"]), sorted(case["internal"]))


@pytest.mark.parametrize("target", SHARED["targets"])
@pytest.mark.parametrize("case", SHARED["cases"], ids=lambda case: case["name"])
def test_book_and_project_seals_enforce_the_same_shared_rules(tmp_path: Path, target: str, case: dict) -> None:
    book = shared_book(case)
    files = {name: text.encode("utf-8") for name, text in (case.get("scripts") or {}).items()}
    files["chapters/1.mp3"] = b"audio"
    if "cast" in case:
        files["cast.json"] = bookfile.json_bytes(case["cast"])
    out = tmp_path / ("x.abookproj" if target == "project" else "x.abook")
    def seal() -> None:
        if target == "book":
            bookfile.seal(book, files, out, producer="test", version=6)
        else:
            projectfile._seal(out, files, book, producer="test", title="Sách thử", workshop=projectfile.PENDING,
                              project_root="", sources=[], missing=[], version=6)
    if case["leaked"] or case["internal"]:
        with pytest.raises((bookfile.BookFileError, projectfile.ProjectFileError)) as error:
            seal()
        assert str(error.value) == bookfile._RULES["refusal"]
        assert not out.exists()
    else:
        seal()
        assert out.is_file()


@pytest.mark.parametrize("case", SHARED["cases"], ids=lambda case: case["name"])
def test_imported_listening_layers_are_cleaned_by_the_shared_rules(case: dict) -> None:
    book = shared_book(case)
    files = {name: text.encode("utf-8") for name, text in (case.get("scripts") or {}).items()}
    if "cast" in case:
        files["cast.json"] = bookfile.json_bytes(case["cast"])
    known = {name: bookfile.describe(data) for name, data in files.items()}
    original = dict(files)
    bookfile.clean_listener_layer(book, files, known)
    assert bookfile.listener_package_problems(book, files, files.__getitem__) == ([], [])
    if not case["leaked"] and not case["internal"]:
        assert book == shared_book(case)
        assert files == original


@pytest.mark.parametrize("data", [b"{", b"[]", b'"cast"'])
def test_saving_does_not_rewrite_an_unreadable_cast(data: bytes) -> None:
    files = {"cast.json": data}
    known = {"cast.json": bookfile.describe(data)}
    expected = copy.deepcopy(known)
    bookfile.clean_listener_layer(_book(), files, known)
    assert files == {"cast.json": data}
    assert known == expected
