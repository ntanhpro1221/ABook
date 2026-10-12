"""Hai thẻ "Việc cần duyệt" của A+ (abook/teller_voice.py): giọng lời dẫn khác giới người kể "tôi", và nội tâm của chính "tôi".
Chỉ hiện khi máy KHÔNG tự áp được (sách đã thu, hay người dùng đã chọn giọng dẫn); mặc định không áp; áp bằng đúng ý muốn người nghe có sẵn."""
from __future__ import annotations

import json
from pathlib import Path

from abook import teller_voice
from abook.listener_overrides import read_overrides, request_voice
from abook.webui import work_items as work
from tests.test_teller_voice import _book, _settings


def _with_settings(paths, settings) -> Path:
    (paths.root / "book_settings.json").write_bytes(json.dumps(settings, ensure_ascii=False).encode("utf-8"))
    return paths.root


def _cards(root: Path, kind: str) -> list[dict]:
    return [item for item in work.work_items(root)["items"] if item["kind"] == kind]


def test_a_recorded_book_gets_both_cards_with_the_existing_wishes_as_the_choices(tmp_path: Path) -> None:
    paths, _db, settings = _book(tmp_path, recorded=True)
    root = _with_settings(paths, settings)

    (voice,) = _cards(root, "teller-voice")
    (thought,) = _cards(root, "teller-thought")

    (choice,) = voice["voiceChoices"]
    assert choice["character"] == "NARRATOR" and choice["preset"] == "Ngọc Linh" and voice["keepCharacters"] == ["NARRATOR"]
    assert "Lời dẫn" in voice["title"] and "nữ" in voice["title"]
    assert thought["key"] == "teller-thought:MAI" and thought["affected"] == 2
    assert [option["value"] for option in thought["choices"]] == ["NARRATOR"]
    assert read_overrides(root).get("voices") in (None, {}), "mặc định không áp: chưa có ý muốn nào được ghi"


def test_a_voice_the_user_chose_gets_the_card_not_an_automatic_change(tmp_path: Path) -> None:
    paths, db, settings = _book(tmp_path, narrator_auto=False)
    root = _with_settings(paths, settings)

    teller_voice.ensure(root, db, settings)

    assert len(_cards(root, "teller-voice")) == 1
    assert _cards(root, "teller-thought") == [], "nội tâm của chính “tôi” vẫn tự về giọng dẫn khi chưa thu"


def test_a_book_the_machine_handled_has_no_cards(tmp_path: Path) -> None:
    paths, db, settings = _book(tmp_path)
    root = _with_settings(paths, settings)

    teller_voice.ensure(root, db, settings)

    assert _cards(root, "teller-voice") == [] and _cards(root, "teller-thought") == []


def test_keeping_the_current_voice_or_the_character_voice_hides_the_cards(tmp_path: Path) -> None:
    paths, _db, settings = _book(tmp_path, recorded=True)
    root = _with_settings(paths, settings)
    request_voice(root, "NARRATOR", preset="", now=1.0)  # “Giữ giọng hiện tại”
    (thought,) = _cards(root, "teller-thought")
    from abook.listener_overrides import request_speakers

    request_speakers(root, [(line["stableId"], line["textSha256"]) if "textSha256" in line else (line["stableId"], "sha-" + line["stableId"])
                            for line in thought["lines"]], "MAI", now=2.0)

    assert _cards(root, "teller-voice") == []
    assert _cards(root, "teller-thought") == []


def test_a_third_person_book_has_no_cards(tmp_path: Path) -> None:
    paths, _db, settings = _book(tmp_path, recorded=True, settings=_settings(identity=""))
    root = _with_settings(paths, settings)

    assert _cards(root, "teller-voice") == [] and _cards(root, "teller-thought") == []


def test_the_screenplay_and_the_inbox_ask_who_is_the_teller_by_one_rule(tmp_path: Path) -> None:
    narrator_dir = tmp_path
    from abook import narrator_sections

    narrator_sections.decide(narrator_dir, 1, 2, 3, accepted=True, narrator="Bao", source="owner")
    (narrator_dir / "book_settings.json").write_bytes(json.dumps(_settings(chapters={"2": "Linh"})).encode("utf-8"))

    identity, chapters, chapter_of, row_of = work.first_person_lookup(narrator_dir, {10: 1, 20: 2})

    assert identity == "Mai" and chapters == {2: "Linh"}
    assert chapter_of(10) == "Mai" and chapter_of(20) == "Linh"
    assert row_of is not None and row_of({"chapter_id": 10, "seq": 2}) == "Bao" and row_of({"chapter_id": 10, "seq": 0}) == "Mai"
    (narrator_dir / "book_settings.json").write_bytes(json.dumps(_settings(identity="")).encode("utf-8"))
    assert work.first_person_lookup(narrator_dir, {10: 1})[3] is None


def test_in_the_tellers_own_voice_mode_there_is_nothing_left_to_ask(tmp_path: Path) -> None:
    paths, _db, settings = _book(tmp_path, recorded=True)
    root = _with_settings(paths, settings)
    assert _cards(root, "teller-voice") and _cards(root, "teller-thought")

    teller_voice.set_mode(root, "teller")

    assert _cards(root, "teller-voice") == [] and _cards(root, "teller-thought") == []
