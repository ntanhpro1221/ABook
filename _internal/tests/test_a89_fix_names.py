"""a89 T1: tên và cách đọc người nghe gõ được kiểm ở máy chủ (name_rules.py), không chỉ ở giao diện."""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pytest

from abook import listener_overrides as lo
from abook import names
from abook.webui import name_rules
from abook.webui.library import Preferences, book_id
from abook.webui.listening import Listening
from abook.webui.server import App, Server
from tests.test_listener_speakers import _book
from tests.test_webui_listen_and_sync import FakeRunner, _request


@pytest.fixture
def studio(tmp_path: Path):
    paths, _db = _book(tmp_path)
    (paths.root / "book_settings.json").write_text("{}", encoding="utf-8")
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()

    def post(endpoint: str, body: dict) -> tuple[int, dict]:
        status, data, _ = _request(server.port, "POST", f"/api/books/{book_id(paths.root)}/{endpoint}", headers={"X-Ebook-Token": "t"}, body=body)
        return status, json.loads(data)

    try:
        yield paths, post
    finally:
        server.stop()


def _line(paths, stable_id: str = "c1s1") -> dict:
    return {"stableId": stable_id, "textSha256": f"sha-{stable_id}"}


def test_clean_is_nfc_without_invisible_characters() -> None:
    assert name_rules.clean("Lu​cien  Hà") == unicodedata.normalize("NFC", "Lucien Hà")
    assert name_rules.clean("A﻿B­C‮") == "ABC"
    assert name_rules.clean("a\tb\nc") == "a b c"


@pytest.mark.parametrize("typed", ["​​", "﻿", "‍ ⁠"])
def test_a_name_of_only_invisible_characters_is_refused(typed: str) -> None:
    with pytest.raises(name_rules.NameProblem, match="không nhìn thấy"):
        name_rules.person(typed)


def test_empty_is_the_original_name_only_when_allowed() -> None:
    assert name_rules.person("   ", allow_empty=True) == ""
    with pytest.raises(name_rules.NameProblem, match="chưa gõ tên"):
        name_rules.person("   ")


def test_too_long_is_told_not_cut() -> None:
    with pytest.raises(name_rules.NameProblem, match="tối đa 80"):
        name_rules.person("x" * 81)
    assert name_rules.person("x" * 80) == "x" * 80


@pytest.mark.parametrize("typed", ["Người kể", "NARRATOR", "vai phụ không tên", "Anonymous_Male", "a::b"])
def test_machine_names_are_reserved(typed: str) -> None:
    with pytest.raises(name_rules.NameProblem, match="tên máy dùng"):
        name_rules.person(typed)


def test_a_duplicate_of_another_person_is_refused_but_a_near_name_is_not() -> None:
    with pytest.raises(name_rules.NameProblem, match="Đã có “Natasha” trong sách — bạn đặt tên khác để tránh nhầm người."):
        name_rules.person("natasha ", ["Lucien", "Natasha"])
    assert name_rules.person("Natasa", ["Natasha"]) == "Natasa"
    assert name_rules.person("Hạ", ["Hà"]) == "Hạ"


def test_rename_refuses_invisible_long_reserved_and_duplicate(studio) -> None:
    paths, post = studio
    for bad, part in (("​", "không nhìn thấy"), ("x" * 120, "tối đa 80"), ("Người kể", "tên máy dùng"), ("natasha", "Đã có “Natasha” trong sách")):
        status, answer = post("characters/rename", {"character": "LUCIEN", "name": bad})
        assert status == 400 and part in answer["error"], (bad, answer)
    assert names.shown(paths.root, "LUCIEN") in (None, "")


def test_rename_stores_nfc_and_without_invisible_characters(studio) -> None:
    paths, post = studio
    status, answer = post("characters/rename", {"character": "LUCIEN", "name": unicodedata.normalize("NFD", "Lu​ciên")})
    assert status == 200, answer
    assert answer["name"] == unicodedata.normalize("NFC", "Luciên")
    assert names.shown(paths.root, "LUCIEN") == answer["name"]


def test_rename_to_its_own_name_or_empty_is_not_a_duplicate(studio) -> None:
    _paths, post = studio
    assert post("characters/rename", {"character": "LUCIEN", "name": "Lucien"})[0] == 200
    status, answer = post("characters/rename", {"character": "LUCIEN", "name": ""})
    assert status == 200 and answer["renamed"] is False


def test_a_new_person_goes_through_the_same_rules(studio) -> None:
    paths, post = studio
    for bad, part in (("​", "không nhìn thấy"), ("Lucien", "Đã có “Lucien” trong sách"), ("Vai phụ không tên", "tên máy dùng"), ("y" * 90, "tối đa 80")):
        status, answer = post("speaker", {**_line(paths), "speaker": bad, "newGender": "male"})
        assert status == 400 and part in answer["error"], (bad, answer)
    assert not lo.read_overrides(paths.root).get("speakers")
    status, answer = post("speaker", {**_line(paths), "speaker": "Ma​ria", "newGender": "female"})
    assert status == 200, answer
    assert answer["speaker"] == "Maria"
    assert lo.read_overrides(paths.root)["speakers"]["c1s1"]["speaker"] == "Maria"


def test_an_existing_person_is_not_checked_as_a_new_name(studio) -> None:
    paths, post = studio
    status, answer = post("speaker", {**_line(paths, "c1s3"), "speaker": "Lucien"})
    assert status == 200, answer


def test_a_reading_surface_is_cleaned_and_told_when_too_long(studio) -> None:
    paths, post = studio
    status, answer = post("pronunciation", {"surface": "Lu​cien", "spokenForm": "Lu xi en"})
    assert status == 200, answer
    assert answer["surface"] == "Lucien"
    status, answer = post("pronunciation", {"surface": "​", "spokenForm": "a"})
    assert status == 400 and "không nhìn thấy" in answer["error"]
    status, answer = post("pronunciation", {"surface": "z" * 200, "spokenForm": "a"})
    assert status == 400 and "tối đa 80" in answer["error"]
    status, answer = post("pronunciation", {"surface": "Natasha", "spokenForm": "na ta sa " * 30})
    assert status == 400 and "tối đa 120" in answer["error"]


def test_a_surface_that_never_occurs_is_saved_with_a_warning(studio) -> None:
    paths, post = studio
    status, answer = post("pronunciation", {"surface": "Zxqvw", "spokenForm": "da cờ"})
    assert status == 200, answer
    assert answer["warning"] == "Đã ghi nhưng chưa có câu chứa “Zxqvw” để đổi — bạn kiểm tra chữ đã gõ."
    status, answer = post("pronunciation", {"surface": "Natasha", "spokenForm": "na ta sa"})
    assert status == 200 and "warning" not in answer


def test_the_shared_cases_give_what_the_kotlin_player_gives() -> None:
    """Bộ ví dụ dùng chung với NameRulesTest.kt (tests/fixtures/book_edits/name_rules.json): hai bản cài phải ra đúng những kết quả này."""
    cases = json.loads((Path(__file__).parent / "fixtures" / "book_edits" / "name_rules.json").read_text(encoding="utf-8"))
    assert len(cases) >= 20
    for case in cases:
        function = name_rules.clean if case["fn"] == "tidy" else getattr(name_rules, case["fn"])
        arguments = [case["input"]] + ([case.get("others", [])] if case["fn"] == "person" else [])
        keywords = {"allow_empty": case.get("allowEmpty", False)} if case["fn"] == "person" else {}
        if "error" in case:
            with pytest.raises(name_rules.NameProblem) as problem:
                function(*arguments, **keywords)
            assert str(problem.value) == case["error"], case
        else:
            assert function(*arguments, **keywords) == case["out"], case
